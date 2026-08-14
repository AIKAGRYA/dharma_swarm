"""Sealed, text-only Grok OAuth adapter for the Helm preview.

The Grok Build CLI always exposes agent tools, so it is not an appropriate
transport for a physical no-tools seat.  This adapter instead speaks the
OAuth-backed Responses endpoint directly.  It deliberately buffers and
validates the complete SSE transcript before emitting any positive canonical
event.

The requested identity and the identity returned by the proxy are kept
separate.  ``grok-4.6-build`` is accepted as response-owned route evidence for
the exact ``grok-4.6`` request, but it is not proof that the exact public model
identity was served.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from dharma_swarm.model_catalog import HELM_PREVIEW_GROK_4_6_MODEL_ID

from .base import (
    Capability,
    CompletionRequest,
    ModelProfile,
    ProviderAdapter,
    ProviderConfig,
)
from .grok_oauth_auth import load_current_oauth_key as _load_oauth_key_from_path
from .grok_oauth_codec import validate_sse_completion
from .grok_oauth_request import (
    INVALID as _INVALID,
    MAX_OUTPUT_TOKENS as _MAX_OUTPUT_TOKENS,
    bounded_output_tokens as _bounded_output_tokens,
    normalize_messages as _request_input,
    optional_instructions as _optional_instructions,
    request_timeout as _request_timeout,
)
from ..events import ErrorEvent, SessionEnd, SessionStart, TextComplete, UsageReport

_GROK_OAUTH_BASE_URL = "https://cli-chat-proxy.grok.com/v1"
_GROK_OAUTH_ENDPOINT = f"{_GROK_OAUTH_BASE_URL}/responses"
_GROK_AUTH_PATH = Path.home() / ".grok" / "auth.json"
_REQUESTED_MODEL_ID = HELM_PREVIEW_GROK_4_6_MODEL_ID
_SERVED_MODEL_ID = f"{_REQUESTED_MODEL_ID}-build"
_CLIENT_VERSION = "1.0.0"
_CLIENT_IDENTIFIER = "grok-shell"
_USER_AGENT = f"xai-grok-shell/{_CLIENT_VERSION}"
_MAX_SSE_BYTES = 4 * 1024 * 1024
_RETRYABLE_HTTP_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})
_CAPABILITIES = Capability.SYSTEM_PROMPT | Capability.CONTEXT_USAGE | Capability.CANCEL


class GrokOAuthResponsesAdapter(ProviderAdapter):
    """Direct OAuth Responses transport with no model-side tool authority."""

    provider_id = "grok_oauth"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        # This authority boundary is sealed.  Callers cannot substitute an
        # endpoint, credential, or model through ProviderConfig.
        del config
        self._config = ProviderConfig(
            provider_id=self.provider_id,
            api_key=None,
            base_url=_GROK_OAUTH_BASE_URL,
            default_model=_REQUESTED_MODEL_ID,
        )
        self._profile = ModelProfile(
            provider_id=self.provider_id,
            model_id=_REQUESTED_MODEL_ID,
            display_name="Grok 4.6 (Grok account preview)",
            capabilities=_CAPABILITIES,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            extra={
                "transport": "responses_sse_buffered",
                "no_tools": True,
                "requested_model": _REQUESTED_MODEL_ID,
                "accepted_served_model": _SERVED_MODEL_ID,
                "served_identity_source": "response.model",
                "exact_model_proven": False,
            },
        )
        self._cancelled = False
        self._active_request_task: asyncio.Task[httpx.Response] | None = None

    async def list_models(self) -> list[ModelProfile]:
        return [self._profile]

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        requested_model = model_id or self._profile.model_id
        if requested_model != self._profile.model_id:
            raise ValueError("Grok OAuth adapter supports only its sealed model")
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
                "Grok OAuth adapter supports only its sealed model",
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
                "Grok OAuth chat is sealed to no-tools execution",
            ):
                yield event
            return

        normalized_input = _request_input(request.messages)
        instructions = _optional_instructions(request.system_prompt)
        if normalized_input is None or instructions is _INVALID:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "invalid_request",
                "Grok OAuth chat requires non-empty text-only messages",
            ):
                yield event
            return

        max_output_tokens = _bounded_output_tokens(request.max_tokens)
        if max_output_tokens is None:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "invalid_request",
                "Grok OAuth chat received an invalid token limit",
            ):
                yield event
            return

        oauth_key, auth_rejection = _load_current_oauth_key()
        if auth_rejection is not None:
            code, message = auth_rejection
            for event in _failure_events(
                self.provider_id,
                session_id,
                code,
                message,
            ):
                yield event
            return
        assert oauth_key is not None

        payload: dict[str, Any] = {
            "model": model,
            "input": normalized_input,
            "stream": True,
            "tools": [],
            # The proxy rejects tool_choice="none" when tools is empty.  An
            # empty tools array plus this false flag is the proven no-tools
            # request shape; tool_choice is intentionally omitted.
            "parallel_tool_calls": False,
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": max_output_tokens,
        }
        if isinstance(instructions, str):
            payload["instructions"] = instructions

        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {oauth_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "X-XAI-Token-Auth": "xai-grok-cli",
            "x-grok-client-version": _CLIENT_VERSION,
            "x-grok-client-identifier": _CLIENT_IDENTIFIER,
            "x-grok-model-override": model,
        }

        if self._cancelled:
            yield self._cancelled_session_end(session_id)
            return

        try:
            timeout = _request_timeout(request.provider_options.get("timeout_sec"))
            request_task = asyncio.create_task(
                self._post_completion(
                    url=_GROK_OAUTH_ENDPOINT,
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

            if 300 <= response.status_code < 400:
                for event in _failure_events(
                    self.provider_id,
                    session_id,
                    "redirect_rejected",
                    "Grok OAuth endpoint returned a redirect",
                ):
                    yield event
                return
            if response.status_code != 200:
                code = (
                    "rate_limited"
                    if response.status_code == 429
                    else f"http_{response.status_code}"
                )
                for event in _failure_events(
                    self.provider_id,
                    session_id,
                    code,
                    f"Grok OAuth endpoint returned HTTP {response.status_code}",
                    retryable=response.status_code in _RETRYABLE_HTTP_STATUSES,
                ):
                    yield event
                return

            content_type = str(response.headers.get("content-type", "")).lower()
            if not content_type.startswith("text/event-stream"):
                for event in _failure_events(
                    self.provider_id,
                    session_id,
                    "malformed_response",
                    "Grok OAuth endpoint did not return an SSE response",
                ):
                    yield event
                return

            body = response.content
            validated, rejection = validate_sse_completion(
                body,
                expected_served_model=_SERVED_MODEL_ID,
            )
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

            # Only now, after the whole provider transcript has been buffered
            # and accepted, is positive route evidence allowed to escape.
            yield SessionStart(
                provider_id=self.provider_id,
                session_id=session_id,
                model=validated.served_model,
                capabilities=[
                    capability.name.lower()
                    for capability in Capability
                    if self._profile.capabilities & capability
                ],
                tools_available=[],
                system_info={
                    "base_url": _GROK_OAUTH_BASE_URL,
                    "endpoint_path": "/v1/responses",
                    "requested_model": model,
                    "served_model": validated.served_model,
                    "served_identity_source": "response.model",
                    "exact_model_proven": False,
                    "tool_authority": "absent",
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
                thinking_tokens=validated.thinking_tokens,
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
                "Grok OAuth SSE response exceeded the safety bound",
            ):
                yield event
        except httpx.TimeoutException:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "timeout",
                "Grok OAuth request timed out",
                retryable=True,
            ):
                yield event
        except httpx.RequestError:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "transport_error",
                "Grok OAuth request failed",
                retryable=True,
            ):
                yield event
        except Exception:
            for event in _failure_events(
                self.provider_id,
                session_id,
                "grok_oauth_error",
                "Grok OAuth request failed",
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
    ) -> httpx.Response:
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
                        if len(body) + len(chunk) > _MAX_SSE_BYTES:
                            raise _ResponseTooLarge
                        body.extend(chunk)
                return httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=bytes(body),
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


class _ResponseTooLarge(Exception):
    pass


def _load_current_oauth_key() -> tuple[str | None, tuple[str, str] | None]:
    return _load_oauth_key_from_path(_GROK_AUTH_PATH)


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


__all__ = ["GrokOAuthResponsesAdapter"]
