"""OpenRouter adapter for TUI model switching and fallback."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, AsyncIterator

import httpx

from dharma_swarm import model_pool as _model_pool
from dharma_swarm.api_keys import OPENROUTER_API_KEY_ENV, env_value
from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType

from .base import Capability, CompletionRequest, ModelProfile, ProviderAdapter, ProviderConfig
from ..events import ErrorEvent, SessionEnd, SessionStart, TextComplete, UsageReport

OPENROUTER_CAPABILITIES = (
    Capability.SYSTEM_PROMPT
    | Capability.COST_TRACKING
    | Capability.CANCEL
)


def _gemini_openrouter_id() -> str:
    """The Gemini OpenRouter route id, sourced from the ONE pool at the FLOOR.

    The Gemini lane used to hand-type the sub-floor ``google/gemini-2.5-pro``;
    the floor is gemini-3-pro, owned by the pool. We project its OpenRouter
    (``google/...``) route so the model-id literal lives only in the pool.
    """
    entry = _model_pool.get_entry("gemini-3-pro")
    if entry is not None:
        for mid in entry.model_ids:
            if mid.startswith("google/"):
                return mid
    raise AssertionError("model_pool has no google/ route for the gemini-3-pro floor")


_GEMINI_OPENROUTER_ID = _gemini_openrouter_id()


class OpenRouterAdapter(ProviderAdapter):
    """Provider adapter for OpenRouter chat completions."""

    provider_id = "openrouter"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider_id=self.provider_id,
            base_url="https://openrouter.ai/api/v1",
            default_model=DEFAULT_MODELS[ProviderType.OPENROUTER],
        )
        self._cancelled = False
        self._active_request_task: asyncio.Task[httpx.Response] | None = None
        self._profiles: dict[str, ModelProfile] = {
            DEFAULT_MODELS[ProviderType.OPENROUTER]: ModelProfile(
                provider_id=self.provider_id,
                model_id=DEFAULT_MODELS[ProviderType.OPENROUTER],
                display_name="GPT-4o Mini (OpenRouter)",
                capabilities=OPENROUTER_CAPABILITIES,
            ),
            "openai/gpt-5-codex": ModelProfile(
                provider_id=self.provider_id,
                model_id="openai/gpt-5-codex",
                display_name="Codex 5.4 (OpenRouter)",
                capabilities=OPENROUTER_CAPABILITIES,
            ),
            _GEMINI_OPENROUTER_ID: ModelProfile(
                provider_id=self.provider_id,
                model_id=_GEMINI_OPENROUTER_ID,
                display_name="Gemini 3 class (OpenRouter)",
                capabilities=OPENROUTER_CAPABILITIES,
            ),
        }

    async def list_models(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        model = model_id or self._config.default_model or DEFAULT_MODELS[ProviderType.OPENROUTER]
        return self._profiles.get(model, next(iter(self._profiles.values())))

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[SessionStart | TextComplete | UsageReport | ErrorEvent | SessionEnd]:
        profile = self.get_profile(request.model)
        model = request.model or profile.model_id
        self._cancelled = False

        api_key = (
            self._config.api_key
            or request.provider_options.get("openrouter_api_key")
            or env_value(OPENROUTER_API_KEY_ENV)
        )
        if not api_key:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="missing_api_key",
                message="OPENROUTER_API_KEY not set",
                retryable=False,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="missing_api_key",
                error_message="OPENROUTER_API_KEY not set",
            )
            return

        base_url = (self._config.base_url or "https://openrouter.ai/api/v1").rstrip("/")
        url = f"{base_url}/chat/completions"
        messages = request.messages or []
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice
        else:
            payload["tool_choice"] = "none"
        if request.system_prompt:
            payload["messages"] = [
                {"role": "system", "content": request.system_prompt},
                *messages,
            ]
        if request.max_tokens is not None:
            payload["max_tokens"] = int(request.max_tokens)
        if request.temperature is not None:
            payload["temperature"] = float(request.temperature)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if self._cancelled:
            yield self._cancelled_session_end(session_id)
            return

        try:
            timeout = float(request.provider_options.get("timeout_sec", 120))
            request_task = asyncio.create_task(
                self._post_completion(
                    url=url,
                    headers=headers,
                    payload=payload,
                    timeout=timeout,
                )
            )
            self._active_request_task = request_task
            try:
                resp = await request_task
            except asyncio.CancelledError:
                if not self._cancelled:
                    raise
                yield self._cancelled_session_end(session_id)
                return
            finally:
                if self._active_request_task is request_task:
                    self._active_request_task = None

            if self._cancelled:
                yield self._cancelled_session_end(session_id)
                return

            if resp.status_code >= 400:
                msg = resp.text.strip()[:1000]
                code = "rate_limited" if resp.status_code == 429 else f"http_{resp.status_code}"
                yield ErrorEvent(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    code=code,
                    message=msg or f"HTTP {resp.status_code}",
                    retryable=resp.status_code in {408, 409, 429, 500, 502, 503, 504},
                )
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code=code,
                    error_message=msg or f"HTTP {resp.status_code}",
                )
                return

            data = resp.json()
            rejection = _response_rejection(data)
            if rejection is not None:
                code, message = rejection
                for event in _failure_events(
                    self.provider_id, session_id, code, message
                ):
                    yield event
                return

            assert isinstance(data, dict)
            response_model = data.get("model")
            served_model = (
                response_model.strip()
                if isinstance(response_model, str) and response_model.strip()
                else None
            )
            require_served_identity = (
                request.provider_options.get("require_served_identity") is True
            )
            if require_served_identity and served_model is None:
                code = "missing_served_identity"
                message = "OpenRouter response.model is required and must be a nonblank string"
                for event in _failure_events(
                    self.provider_id, session_id, code, message
                ):
                    yield event
                return

            identity_source = (
                "response.model" if served_model is not None else "request.model"
            )
            yield SessionStart(
                provider_id=self.provider_id,
                session_id=session_id,
                model=served_model or model,
                capabilities=[
                    c.name.lower() for c in Capability if profile.capabilities & c
                ],
                tools_available=[],
                system_info={
                    "base_url": self._config.base_url or "https://openrouter.ai/api/v1",
                    "requested_model": model,
                    "served_identity_source": identity_source,
                },
            )
            content = _extract_content(data)
            yield TextComplete(
                provider_id=self.provider_id,
                session_id=session_id,
                content=content,
                role="assistant",
            )
            usage = data.get("usage", {}) if isinstance(data, dict) else {}
            yield UsageReport(
                provider_id=self.provider_id,
                session_id=session_id,
                input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage.get("completion_tokens", 0) or 0),
                total_cost_usd=_extract_cost(data),
                model_breakdown=usage if isinstance(usage, dict) else {},
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=True,
            )
        except httpx.TimeoutException:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="timeout",
                message="OpenRouter request timed out",
                retryable=True,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="timeout",
                error_message="OpenRouter request timed out",
            )
        except Exception as exc:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="openrouter_error",
                message=str(exc),
                retryable=False,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="openrouter_error",
                error_message=str(exc),
            )

    async def cancel(self) -> None:
        self._cancelled = True
        task = self._active_request_task
        if task is None or task.done():
            return
        task.cancel()
        try:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finally:
            if self._active_request_task is task and task.done():
                self._active_request_task = None

    async def close(self) -> None:
        await self.cancel()

    async def _post_completion(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        """Own the client inside the cancellable task so cleanup is awaited."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, json=payload)

    def _cancelled_session_end(self, session_id: str) -> SessionEnd:
        return SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=False,
            error_code="cancelled",
            error_message="request cancelled",
        )


def _failure_events(
    provider_id: str,
    session_id: str,
    code: str,
    message: str,
) -> tuple[ErrorEvent, SessionEnd]:
    return (
        ErrorEvent(
            provider_id=provider_id,
            session_id=session_id,
            code=code,
            message=message,
            retryable=False,
        ),
        SessionEnd(
            provider_id=provider_id,
            session_id=session_id,
            success=False,
            error_code=code,
            error_message=message,
        ),
    )


def _extract_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message", {})
    if isinstance(msg, dict):
        content = msg.get("content", "")
        if isinstance(content, str):
            if content.strip():
                return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if isinstance(txt, str):
                        chunks.append(txt)
            if chunks:
                return "\n".join(chunks)
        reasoning = msg.get("reasoning", "")
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning
        details = msg.get("reasoning_details", [])
        if isinstance(details, list):
            chunks = []
            for item in details:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        chunks.append(txt)
            if chunks:
                return "\n".join(chunks)
    return ""


def _response_rejection(data: Any) -> tuple[str, str] | None:
    if not isinstance(data, dict):
        return "malformed_response", "OpenRouter response must be an object"
    if _error_is_present(data.get("error")):
        return "provider_response_error", _embedded_error_message(data["error"])

    choices = data.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
    ):
        return (
            "malformed_response",
            "OpenRouter response must contain exactly one object choice",
        )
    choice = choices[0]
    if _error_is_present(choice.get("error")):
        return "provider_response_error", _embedded_error_message(choice["error"])

    message = choice.get("message")
    if not isinstance(message, dict):
        return (
            "malformed_response",
            "OpenRouter response choices[0].message is required",
        )
    if _error_is_present(message.get("error")):
        return "provider_response_error", _embedded_error_message(message["error"])
    if bool(message.get("tool_calls")):
        return "provider_tool_use_rejected", "OpenRouter response contained tool calls"
    finish_reasons = {
        str(choice.get(field, "")).strip().lower()
        for field in ("finish_reason", "native_finish_reason")
    }
    if "tool_calls" in finish_reasons:
        return (
            "provider_tool_use_rejected",
            "OpenRouter response finished for tool calls",
        )
    if "error" in finish_reasons:
        return "provider_response_error", "OpenRouter response finished with an error"

    usage = data.get("usage")
    if isinstance(usage, dict):
        server_tool_usage = (
            usage.get("server_tool_use_details"),
            usage.get("server_tool_use"),
        )
        if any(_indicates_server_tool_calls(value) for value in server_tool_usage):
            return (
                "provider_tool_use_rejected",
                "OpenRouter usage reported server tool calls",
            )
    if not _extract_content(data).strip():
        return "empty_response", "OpenRouter response contained no assistant content"
    return None


def _error_is_present(value: Any) -> bool:
    return value is not None and value != "" and value != {} and value != []


def _embedded_error_message(value: Any) -> str:
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:1000]
    if isinstance(value, str) and value.strip():
        return value.strip()[:1000]
    return "OpenRouter returned an embedded provider error"


def _indicates_server_tool_calls(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "none", "null"}
    if isinstance(value, dict):
        return any(_indicates_server_tool_calls(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_indicates_server_tool_calls(item) for item in value)
    return bool(value)


def _extract_cost(data: Any) -> float | None:
    if not isinstance(data, dict):
        return None
    usage = data.get("usage", {})
    if isinstance(usage, dict):
        # OpenRouter can include either total_cost or cost
        for key in ("total_cost", "cost"):
            if key in usage:
                try:
                    return float(usage[key])
                except Exception:
                    pass
    return None
