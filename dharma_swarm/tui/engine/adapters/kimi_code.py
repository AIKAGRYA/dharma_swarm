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
from .kimi_code_codec import (
    has_tool_signal,
    optional_positive_int as _optional_positive_int,
    request_messages as _request_messages,
    unique_json_object as _unique_json_object,
    validate_completion as _validate_completion,
)

_has_tool_signal = has_tool_signal

_KIMI_CODE_BASE_URL = "https://api.kimi.com/coding/v1"
_KIMI_CODE_MODEL_ID = DEFAULT_MODELS[ProviderType.KIMI_CODE]
_KIMI_CODE_CAPABILITIES = (
    Capability.SYSTEM_PROMPT | Capability.CONTEXT_USAGE | Capability.CANCEL
)
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_RETRYABLE_HTTP_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})


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


__all__ = ["KimiCodeAdapter"]
