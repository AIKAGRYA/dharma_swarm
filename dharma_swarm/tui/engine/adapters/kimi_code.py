"""Strict first-party Kimi Code adapter for the terminal chat membrane.

This lane is deliberately narrower than the general-purpose Kimi provider:
it serves the canonical K3 model from the trusted Kimi Code endpoint, never
accepts tools, and emits route evidence only after the HTTP response has been
fully validated.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from dharma_swarm import model_pool as _model_pool
from dharma_swarm.api_keys import KIMI_API_KEY_ENV, env_value
from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType

from ..events import ErrorEvent, SessionEnd, SessionStart, TextComplete, UsageReport
from .base import (
    Capability,
    CompletionRequest,
    ModelProfile,
    ProviderAdapter,
    ProviderConfig,
)

_KIMI_CODE_BASE_URL = "https://api.kimi.com/coding/v1"
_KIMI_CODE_MODEL_ID = DEFAULT_MODELS[ProviderType.KIMI_CODE]
_KIMI_CODE_CAPABILITIES = (
    Capability.SYSTEM_PROMPT | Capability.CONTEXT_USAGE | Capability.CANCEL
)
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_RETRYABLE_HTTP_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})
_FORBIDDEN_FINISH_REASONS = frozenset(
    {"function_call", "tool_call", "tool_calls", "tool_use"}
)
_STRUCTURAL_TOOL_DISCRIMINATORS = frozenset(
    {
        "event",
        "finish_reason",
        "kind",
        "native_finish_reason",
        "object",
        "stop_reason",
        "stopreason",
        "type",
    }
)
_TOOL_MARKER_FAMILIES = (
    "code_interpreter",
    "computer",
    "function_call",
    "file_search",
    "image_generation",
    "mcp",
    "shell",
    "tool",
    "web_search",
)
_USAGE_TOKEN_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cached_tokens",
)


@dataclass(frozen=True, slots=True)
class _ValidatedCompletion:
    model: str
    content: str
    usage: dict[str, Any]
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class _BufferedResponse:
    status_code: int
    body: bytes


class _ResponseTooLarge(Exception):
    pass


class KimiCodeAdapter(ProviderAdapter):
    """No-tools adapter for K3 through the first-party Kimi Code API."""

    provider_id = "kimi_code"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        # The terminal route is sealed: caller-provided keys, endpoints, and
        # model overrides must never alter this provider authority boundary.
        del config
        self._config = ProviderConfig(
            provider_id=self.provider_id,
            api_key=None,
            base_url=_KIMI_CODE_BASE_URL,
            default_model=_KIMI_CODE_MODEL_ID,
        )
        pool_entry = _model_pool.entry_for_model_id(_KIMI_CODE_MODEL_ID)
        display_name = (
            f"{pool_entry.display} (Kimi Code)"
            if pool_entry is not None
            else "Kimi K3 (Kimi Code)"
        )
        self._profile = ModelProfile(
            provider_id=self.provider_id,
            model_id=_KIMI_CODE_MODEL_ID,
            display_name=display_name,
            capabilities=_KIMI_CODE_CAPABILITIES,
            max_input_tokens=pool_entry.context if pool_entry is not None else None,
            extra={
                "transport": "chat_completions",
                "no_tools": True,
                "served_identity": "exact",
            },
        )
        self._cancelled = False
        self._active_request_task: asyncio.Task[_BufferedResponse] | None = None

    async def list_models(self) -> list[ModelProfile]:
        return [self._profile]

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        requested_model = model_id or self._profile.model_id
        if requested_model != self._profile.model_id:
            raise ValueError(
                "Kimi Code terminal adapter supports only its sealed model"
            )
        return self._profile

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[
        SessionStart | TextComplete | UsageReport | ErrorEvent | SessionEnd
    ]:
        self._cancelled = False
        model = request.model or self._profile.model_id

        if model != self._profile.model_id:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "unsupported_model",
                "Kimi Code terminal adapter supports only its sealed model",
            ):
                yield event
            return
        if request.tools or (
            request.tool_choice is not None and request.tool_choice != "none"
        ):
            for event in _failure_events(
                self.provider_id,
                session_id,
                "tools_not_supported",
                "Kimi Code terminal chat is sealed to no-tools execution",
            ):
                yield event
            return

        messages = _request_messages(request.messages, request.system_prompt)
        if messages is None:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "invalid_request",
                "Kimi Code terminal chat requires text-only messages",
            ):
                yield event
            return
        max_tokens = _optional_positive_int(request.max_tokens)
        if request.max_tokens is not None and max_tokens is None:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "invalid_request",
                "Kimi Code terminal chat received an invalid token limit",
            ):
                yield event
            return

        api_key = env_value(KIMI_API_KEY_ENV)
        if not api_key:
            message = f"{KIMI_API_KEY_ENV} not set"
            for event in _failure_events(
                self.provider_id,
                session_id,
                "missing_api_key",
                message,
            ):
                yield event
            return

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "tool_choice": "none",
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{_KIMI_CODE_BASE_URL}/chat/completions"

        if self._cancelled:
            yield self._cancelled_session_end(session_id)
            return

        try:
            timeout = _request_timeout(request.provider_options.get("timeout_sec"))
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
                response = await request_task
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

            if response.status_code != 200:
                code = (
                    "rate_limited"
                    if response.status_code == 429
                    else f"http_{response.status_code}"
                )
                message = f"Kimi Code returned HTTP {response.status_code}"
                for event in _failure_events(
                    self.provider_id,
                    session_id,
                    code,
                    message,
                    retryable=response.status_code in _RETRYABLE_HTTP_STATUSES,
                ):
                    yield event
                return

            try:
                text = response.body.decode("utf-8", errors="strict")
                data = json.loads(text, object_pairs_hook=_unique_json_object)
            except (UnicodeDecodeError, ValueError, RecursionError):
                for event in _failure_events(
                    self.provider_id,
                    session_id,
                    "malformed_response",
                    "Kimi Code response was not valid JSON",
                ):
                    yield event
                return

            validated, rejection = _validate_completion(data, expected_model=model)
            if rejection is not None:
                code, message = rejection
                for event in _failure_events(
                    self.provider_id,
                    session_id,
                    code,
                    message,
                ):
                    yield event
                return
            assert validated is not None

            yield SessionStart(
                provider_id=self.provider_id,
                session_id=session_id,
                model=validated.model,
                capabilities=[
                    capability.name.lower()
                    for capability in Capability
                    if self._profile.capabilities & capability
                ],
                tools_available=[],
                system_info={
                    "base_url": _KIMI_CODE_BASE_URL,
                    "requested_model": model,
                    "served_model": validated.model,
                    "served_identity_source": "response.model",
                    "exact_model_proven": True,
                },
            )
            yield TextComplete(
                provider_id=self.provider_id,
                session_id=session_id,
                content=validated.content,
                role="assistant",
            )
            yield UsageReport(
                provider_id=self.provider_id,
                session_id=session_id,
                input_tokens=validated.input_tokens,
                output_tokens=validated.output_tokens,
                total_cost_usd=None,
                model_breakdown=validated.usage,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=True,
            )
        except _ResponseTooLarge:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "response_too_large",
                "Kimi Code response exceeded the safety bound",
            ):
                yield event
        except httpx.TimeoutException:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "timeout",
                "Kimi Code request timed out",
                retryable=True,
            ):
                yield event
        except httpx.RequestError:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "transport_error",
                "Kimi Code request failed",
                retryable=True,
            ):
                yield event
        except Exception:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "kimi_code_error",
                "Kimi Code request failed",
            ):
                yield event

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
    ) -> _BufferedResponse:
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            request = client.build_request("POST", url, headers=headers, json=payload)
            response = await client.send(request, stream=True)
            try:
                body = bytearray()
                if response.status_code == 200:
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                            raise _ResponseTooLarge
                        body.extend(chunk)
                return _BufferedResponse(
                    status_code=response.status_code,
                    body=bytes(body),
                )
            finally:
                await response.aclose()

    def _cancelled_session_end(self, session_id: str) -> SessionEnd:
        return SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=False,
            error_code="cancelled",
            error_message="request cancelled",
        )


def _request_timeout(value: Any) -> float:
    try:
        timeout = float(value) if value is not None else 120.0
    except (TypeError, ValueError):
        return 120.0
    return min(max(timeout, 1.0), 300.0)


def _failure_events(
    provider_id: str,
    session_id: str,
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> tuple[ErrorEvent, SessionEnd]:
    return (
        ErrorEvent(
            provider_id=provider_id,
            session_id=session_id,
            code=code,
            message=message,
            retryable=retryable,
        ),
        SessionEnd(
            provider_id=provider_id,
            session_id=session_id,
            success=False,
            error_code=code,
            error_message=message,
        ),
    )


def _validate_completion(
    data: Any,
    *,
    expected_model: str,
) -> tuple[_ValidatedCompletion | None, tuple[str, str] | None]:
    malformed = "Kimi Code response did not match the expected schema"
    if not isinstance(data, dict):
        return None, ("malformed_response", malformed)
    if _is_present(data.get("error")):
        return None, (
            "provider_response_error",
            "Kimi Code returned an embedded provider error",
        )
    if _has_tool_signal(data, exclude=frozenset({"choices", "usage"})):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response contained tool activity",
        )

    served_model = data.get("model")
    if not isinstance(served_model, str) or served_model != expected_model:
        return None, (
            "served_identity_mismatch",
            "Kimi Code served identity did not match the requested model",
        )

    choices = data.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
    ):
        return None, ("malformed_response", malformed)
    choice = choices[0]
    if _is_present(choice.get("error")):
        return None, (
            "provider_response_error",
            "Kimi Code returned an embedded provider error",
        )
    if _has_tool_signal(choice, exclude=frozenset({"message"})):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response contained tool activity",
        )

    finish_reasons = {
        str(choice.get(field, "")).strip().lower()
        for field in ("finish_reason", "native_finish_reason")
    }
    if finish_reasons & _FORBIDDEN_FINISH_REASONS:
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response finished for tool activity",
        )
    if "error" in finish_reasons:
        return None, (
            "provider_response_error",
            "Kimi Code response finished with an error",
        )

    message = choice.get("message")
    if not isinstance(message, dict):
        return None, ("malformed_response", malformed)
    if _is_present(message.get("error")):
        return None, (
            "provider_response_error",
            "Kimi Code returned an embedded provider error",
        )
    if _has_tool_signal(message):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response contained tool activity",
        )
    role = message.get("role")
    if role not in (None, "assistant"):
        return None, ("malformed_response", malformed)
    content = message.get("content")
    if not isinstance(content, str):
        return None, ("malformed_response", malformed)
    if not content.strip():
        return None, (
            "empty_response",
            "Kimi Code response contained no assistant content",
        )

    raw_usage = data.get("usage", {})
    if raw_usage is None:
        raw_usage = {}
    if not isinstance(raw_usage, dict):
        return None, ("malformed_response", malformed)
    if _has_tool_signal(raw_usage):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code usage reported tool activity",
        )
    usage: dict[str, Any] = {}
    for field in _USAGE_TOKEN_FIELDS:
        if field not in raw_usage:
            continue
        count = _token_count(raw_usage[field])
        if count is None:
            return None, ("malformed_response", malformed)
        usage[field] = count
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    return (
        _ValidatedCompletion(
            model=served_model,
            content=content,
            usage=dict(usage),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        None,
    )


def _has_tool_signal(
    value: Any,
    *,
    exclude: frozenset[str] = frozenset(),
) -> bool:
    pending: list[tuple[Any, bool]] = [(value, True)]
    seen = 0
    while pending:
        current, is_root = pending.pop()
        seen += 1
        if seen > 4096:
            return True
        if isinstance(current, dict):
            for raw_key, item in current.items():
                key = _normalize_structural_label(raw_key)
                if not (is_root and key in exclude):
                    if key == "tool_choice":
                        if item is not None and item != "none":
                            return True
                    elif key == "parallel_tool_calls":
                        if item not in (None, False):
                            return True
                    elif key == "num_server_side_tools_used":
                        if item not in (None, 0):
                            return True
                    elif _has_structural_tool_marker(key) and _is_present(item):
                        return True
                    if (
                        key in _STRUCTURAL_TOOL_DISCRIMINATORS
                        and _has_structural_tool_marker(item)
                    ):
                        return True
                if isinstance(item, (dict, list)):
                    pending.append((item, False))
        elif isinstance(current, list):
            pending.extend((item, False) for item in current)
    return False


def _normalize_structural_label(value: Any) -> str:
    label = str(value or "").strip()
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", label)
    label = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", label)
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _has_structural_tool_marker(value: Any) -> bool:
    # Only field names and explicit discriminator strings reach this helper.
    # Ordinary response narration is never interpreted as structural evidence.
    if not isinstance(value, str):
        return False
    normalized = _normalize_structural_label(value)
    padded = f"_{normalized}_"
    return any(
        f"_{marker}_" in padded or f"_{marker}s_" in padded
        for marker in _TOOL_MARKER_FAMILIES
    )


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate provider JSON key")
        result[key] = value
    return result


def _is_present(value: Any) -> bool:
    return value is not None and value != "" and value != {} and value != []


def _token_count(value: Any) -> int | None:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _request_messages(
    messages: Any,
    system_prompt: Any,
) -> list[dict[str, str]] | None:
    if not isinstance(messages, list):
        return None
    normalized: list[dict[str, str]] = []
    if system_prompt is not None:
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            return None
        normalized.append({"role": "system", "content": system_prompt})
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            return None
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            return None
        if not isinstance(content, str) or not content.strip():
            return None
        normalized.append({"role": role, "content": content})
    return normalized


__all__ = ["KimiCodeAdapter"]
