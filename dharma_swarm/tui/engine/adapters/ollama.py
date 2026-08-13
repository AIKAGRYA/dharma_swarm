"""Strict local-only Ollama adapter for the Helm preview lane.

This is deliberately narrower than the general Dharma Ollama provider.  It is
an opt-in preview transport, not evidence that a Helm council seat is live.
The adapter has one fixed loopback endpoint, one configured model, and no tool
surface.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import os
import re
from typing import Any, AsyncIterator

import httpx

from dharma_swarm.ollama_config import is_ollama_cloud_model

from .base import Capability, CompletionRequest, ModelProfile, ProviderAdapter
from ..events import ErrorEvent, SessionEnd, SessionStart, TextComplete, UsageReport

OLLAMA_LOCAL_PREVIEW_ENV = "DHARMA_HELM_LOCAL_PREVIEW_MODEL"
OLLAMA_LOCAL_PREVIEW_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_LOCAL_PREVIEW_CAPABILITIES = (
    Capability.CANCEL | Capability.CONTEXT_USAGE | Capability.SYSTEM_PROMPT
)

_MODEL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,199}\Z")
_ALLOWED_PROVIDER_OPTIONS = frozenset({"require_served_identity", "timeout_sec"})
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


class OllamaAdapter(ProviderAdapter):
    """No-tools adapter for one explicitly enabled local Ollama model."""

    provider_id = "ollama"

    def __init__(self, model_id: str | None = None) -> None:
        enabled_model = os.environ.get(OLLAMA_LOCAL_PREVIEW_ENV, "").strip()
        if not enabled_model:
            raise RuntimeError(
                f"{OLLAMA_LOCAL_PREVIEW_ENV} must explicitly enable a local model"
            )
        if _is_ollama_cloud_serving_model(enabled_model):
            raise ValueError("Ollama cloud-serving models are forbidden in local preview")
        if model_id is not None and not isinstance(model_id, str):
            raise ValueError("local preview model id is invalid")
        selected_model = enabled_model if model_id is None else model_id.strip()
        if _MODEL_ID_RE.fullmatch(selected_model) is None:
            raise ValueError("local preview model id is invalid")
        if _is_ollama_cloud_serving_model(selected_model):
            raise ValueError("Ollama cloud-serving models are forbidden in local preview")
        if selected_model != enabled_model:
            raise ValueError("local preview model must exactly match the enabled model")

        self._model_id = selected_model
        self._profile = ModelProfile(
            provider_id=self.provider_id,
            model_id=selected_model,
            display_name=f"{selected_model} (local preview; not a Helm seat)",
            capabilities=OLLAMA_LOCAL_PREVIEW_CAPABILITIES,
            extra={
                "base_url": OLLAMA_LOCAL_PREVIEW_BASE_URL,
                "local_preview": True,
                "seat_evidence": False,
            },
        )
        self._cancelled = False
        self._active_request_task: asyncio.Task[httpx.Response] | None = None

    async def list_models(self) -> list[ModelProfile]:
        """Expose only the exact model named by the preview capability gate."""

        return [self._profile]

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        requested = self._model_id if model_id is None else model_id
        if requested != self._model_id:
            raise KeyError(f"model is not enabled for local preview: {requested!r}")
        return self._profile

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[
        SessionStart | TextComplete | UsageReport | ErrorEvent | SessionEnd
    ]:
        """Run one non-streaming, no-tools chat request on fixed loopback."""

        self._cancelled = False
        rejection = self._request_rejection(request)
        if rejection is not None:
            code, message = rejection
            for event in _failure_events(session_id, code, message):
                yield event
            return

        if self._active_request_task is not None and not self._active_request_task.done():
            for event in _failure_events(
                session_id,
                "adapter_busy",
                "Local Ollama preview already has an active request",
            ):
                yield event
            return

        messages = [dict(message) for message in request.messages]
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        payload: dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "stream": False,
        }
        generation_options: dict[str, Any] = {}
        if request.max_tokens is not None:
            generation_options["num_predict"] = int(request.max_tokens)
        if request.temperature is not None:
            generation_options["temperature"] = float(request.temperature)
        if request.stop_sequences:
            generation_options["stop"] = list(request.stop_sequences)
        if generation_options:
            payload["options"] = generation_options

        try:
            timeout = _timeout_seconds(request.provider_options.get("timeout_sec"))
            request_task = asyncio.create_task(
                self._post_completion(payload=payload, timeout=timeout)
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

            if 300 <= response.status_code < 400:
                for event in _failure_events(
                    session_id,
                    "redirect_rejected",
                    "Local Ollama preview rejected an HTTP redirect",
                ):
                    yield event
                return
            if response.status_code >= 400:
                code = (
                    "rate_limited"
                    if response.status_code == 429
                    else f"http_{response.status_code}"
                )
                message = f"Local Ollama request failed with HTTP {response.status_code}"
                for event in _failure_events(
                    session_id,
                    code,
                    message,
                    retryable=response.status_code in _RETRYABLE_STATUS_CODES,
                ):
                    yield event
                return

            try:
                data = response.json()
            except Exception:
                data = None
            response_rejection = _response_rejection(data, self._model_id)
            if response_rejection is not None:
                code, message = response_rejection
                for event in _failure_events(session_id, code, message):
                    yield event
                return

            assert isinstance(data, dict)
            message = data["message"]
            assert isinstance(message, dict)
            content = message["content"]
            assert isinstance(content, str)
            usage = _usage(data)

            # Identity and the no-tools response membrane are validated before
            # any positive route evidence enters the canonical event stream.
            yield SessionStart(
                provider_id=self.provider_id,
                session_id=session_id,
                model=self._model_id,
                capabilities=[
                    capability.name.lower()
                    for capability in Capability
                    if self._profile.capabilities & capability
                ],
                tools_available=[],
                system_info={
                    "base_url": OLLAMA_LOCAL_PREVIEW_BASE_URL,
                    "local_preview": True,
                    "requested_model": self._model_id,
                    "seat_evidence": False,
                    "served_identity_source": "response.model",
                    "transport_mode": "local_api",
                },
            )
            yield TextComplete(
                provider_id=self.provider_id,
                session_id=session_id,
                content=content,
                role="assistant",
            )
            yield UsageReport(
                provider_id=self.provider_id,
                session_id=session_id,
                input_tokens=usage["prompt_eval_count"],
                output_tokens=usage["eval_count"],
                model_breakdown=usage,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=True,
            )
        except httpx.TimeoutException:
            for event in _failure_events(
                session_id,
                "timeout",
                "Local Ollama request timed out",
                retryable=True,
            ):
                yield event
        except httpx.RequestError:
            for event in _failure_events(
                session_id,
                "transport_error",
                "Local Ollama request could not reach the loopback service",
                retryable=True,
            ):
                yield event
        except (TypeError, ValueError, OverflowError):
            for event in _failure_events(
                session_id,
                "invalid_request",
                "Local Ollama preview rejected invalid request options",
            ):
                yield event
        except Exception:
            # Do not copy exception strings or response bodies into durable TUI
            # events: they can contain proxy URLs, credentials, or prompt text.
            for event in _failure_events(
                session_id,
                "ollama_local_error",
                "Local Ollama preview failed",
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
        payload: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        url = f"{OLLAMA_LOCAL_PREVIEW_BASE_URL}/api/chat"
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            return await client.post(url, json=payload)

    def _request_rejection(
        self,
        request: CompletionRequest,
    ) -> tuple[str, str] | None:
        enabled_model = os.environ.get(OLLAMA_LOCAL_PREVIEW_ENV, "").strip()
        requested_model = request.model if isinstance(request.model, str) else None
        if any(
            _is_ollama_cloud_serving_model(model)
            for model in (enabled_model, self._model_id, requested_model)
        ):
            return (
                "cloud_model_rejected",
                "Local Ollama preview forbids cloud-serving model tags",
            )
        if enabled_model != self._model_id:
            return (
                "preview_gate_closed",
                "Local Ollama preview capability gate is closed",
            )
        if request.model is not None and request.model != self._model_id:
            return "model_mismatch", "Requested model is not the enabled local model"
        if not isinstance(request.tools, list) or request.tools:
            return "tools_rejected", "Local Ollama preview does not accept tools"
        if request.tool_choice is not None and request.tool_choice != "none":
            return "tools_rejected", "Local Ollama preview requires tool choice none"
        if request.enable_thinking:
            return "thinking_rejected", "Local Ollama preview does not enable thinking"
        if request.resume_session_id is not None:
            return "resume_rejected", "Local Ollama preview does not resume provider sessions"
        if not isinstance(request.messages, list) or not request.messages:
            return "invalid_messages", "Local Ollama preview requires chat messages"
        for message in request.messages:
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                return "invalid_messages", "Local Ollama preview requires plain chat messages"
            if message.get("role") not in {"assistant", "user"}:
                return "invalid_messages", "Local Ollama preview rejected a message role"
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                return "invalid_messages", "Local Ollama preview rejected empty message content"
        if request.system_prompt is not None and (
            not isinstance(request.system_prompt, str) or not request.system_prompt.strip()
        ):
            return "invalid_system_prompt", "Local Ollama preview rejected the system prompt"
        if not isinstance(request.provider_options, dict):
            return (
                "provider_options_rejected",
                "Local Ollama preview rejected provider overrides",
            )
        if set(request.provider_options) - _ALLOWED_PROVIDER_OPTIONS:
            return (
                "provider_options_rejected",
                "Local Ollama preview rejected provider overrides",
            )
        required_identity = request.provider_options.get("require_served_identity")
        if required_identity is not None and required_identity is not True:
            return (
                "provider_options_rejected",
                "Local Ollama preview identity verification cannot be disabled",
            )
        if request.max_tokens is not None and (
            isinstance(request.max_tokens, bool)
            or not isinstance(request.max_tokens, int)
            or not 0 < request.max_tokens <= 8192
        ):
            return "invalid_generation_options", "Local Ollama preview rejected max tokens"
        if request.temperature is not None and (
            isinstance(request.temperature, bool)
            or not isinstance(request.temperature, (int, float))
            or not math.isfinite(float(request.temperature))
            or not 0 <= float(request.temperature) <= 2
        ):
            return "invalid_generation_options", "Local Ollama preview rejected temperature"
        if not isinstance(request.stop_sequences, list) or any(
            not isinstance(stop, str) or not stop for stop in request.stop_sequences
        ):
            return "invalid_generation_options", "Local Ollama preview rejected stop sequences"
        return None

    def _cancelled_session_end(self, session_id: str) -> SessionEnd:
        return SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=False,
            error_code="cancelled",
            error_message="request cancelled",
        )


def _timeout_seconds(value: Any) -> float:
    timeout = 120.0 if value is None else float(value)
    if not 0 < timeout <= 300:
        raise ValueError("timeout is outside the allowed range")
    return timeout


def _is_ollama_cloud_serving_model(model: str | None) -> bool:
    """Classify cloud tags without changing the exact wire model identity."""

    normalized = model.lower() if isinstance(model, str) else model
    return is_ollama_cloud_model(normalized)


def _response_rejection(data: Any, expected_model: str) -> tuple[str, str] | None:
    if not isinstance(data, dict):
        return "malformed_response", "Local Ollama response must be an object"
    if _present(data.get("error")):
        return "provider_response_error", "Local Ollama returned an error"
    if data.get("model") != expected_model:
        return "model_mismatch", "Local Ollama served a different model"
    if data.get("done") is not True:
        return "malformed_response", "Local Ollama response was not complete"
    if _present(data.get("tool_calls")):
        return "provider_tool_use_rejected", "Local Ollama response contained tool calls"

    message = data.get("message")
    if not isinstance(message, dict):
        return "malformed_response", "Local Ollama response message is required"
    if set(message) - {"role", "content", "thinking", "images", "tool_calls"}:
        return "malformed_response", "Local Ollama response message was malformed"
    if message.get("role") != "assistant":
        return "malformed_response", "Local Ollama response role must be assistant"
    if _present(message.get("tool_calls")):
        return "provider_tool_use_rejected", "Local Ollama response contained tool calls"
    if str(data.get("done_reason", "")).strip().lower() in {
        "tool_call",
        "tool_calls",
    }:
        return "provider_tool_use_rejected", "Local Ollama response finished for tool calls"
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return "empty_response", "Local Ollama response contained no assistant content"
    for key in ("prompt_eval_count", "eval_count"):
        value = data.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return "malformed_response", "Local Ollama response usage was malformed"
    return None


def _usage(data: dict[str, Any]) -> dict[str, int]:
    return {
        "prompt_eval_count": int(data.get("prompt_eval_count", 0)),
        "eval_count": int(data.get("eval_count", 0)),
    }


def _present(value: Any) -> bool:
    return value not in {None, ""} if not isinstance(value, (dict, list)) else bool(value)


def _failure_events(
    session_id: str,
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> tuple[ErrorEvent, SessionEnd]:
    return (
        ErrorEvent(
            provider_id=OllamaAdapter.provider_id,
            session_id=session_id,
            code=code,
            message=message,
            retryable=retryable,
        ),
        SessionEnd(
            provider_id=OllamaAdapter.provider_id,
            session_id=session_id,
            success=False,
            error_code=code,
            error_message=message,
        ),
    )
