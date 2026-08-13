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
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import stat
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
from .grok_oauth_codec import validate_sse_completion
from ..events import ErrorEvent, SessionEnd, SessionStart, TextComplete, UsageReport

_GROK_OAUTH_BASE_URL = "https://cli-chat-proxy.grok.com/v1"
_GROK_OAUTH_ENDPOINT = f"{_GROK_OAUTH_BASE_URL}/responses"
_GROK_AUTH_PATH = Path.home() / ".grok" / "auth.json"
_REQUESTED_MODEL_ID = HELM_PREVIEW_GROK_4_6_MODEL_ID
_SERVED_MODEL_ID = f"{_REQUESTED_MODEL_ID}-build"
_CLIENT_VERSION = "1.0.0"
_CLIENT_IDENTIFIER = "grok-shell"
_USER_AGENT = f"xai-grok-shell/{_CLIENT_VERSION}"
_MAX_OUTPUT_TOKENS = 4096
_DEFAULT_OUTPUT_TOKENS = 1024
_MAX_AUTH_FILE_BYTES = 64 * 1024
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


class _InvalidSentinel:
    pass


class _ResponseTooLarge(Exception):
    pass


_INVALID = _InvalidSentinel()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_current_oauth_key() -> tuple[str | None, tuple[str, str] | None]:
    missing = (
        "missing_oauth_auth",
        "Grok OAuth credentials are unavailable",
    )
    insecure = (
        "insecure_oauth_auth",
        "Grok OAuth credential file permissions are not secure",
    )
    malformed = (
        "malformed_oauth_auth",
        "Grok OAuth credential file is invalid",
    )

    path = _GROK_AUTH_PATH
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None, missing
    except OSError:
        return None, missing
    if stat.S_ISLNK(metadata.st_mode):
        return None, insecure

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None, missing
    except OSError:
        return None, insecure

    try:
        opened_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_metadata.st_mode)
            or stat.S_IMODE(opened_metadata.st_mode) != 0o600
            or opened_metadata.st_uid != os.getuid()
            or opened_metadata.st_size > _MAX_AUTH_FILE_BYTES
        ):
            return None, insecure
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            raw = stream.read(_MAX_AUTH_FILE_BYTES + 1)
    except (OSError, UnicodeError):
        return None, malformed
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if not raw or len(raw.encode("utf-8")) > _MAX_AUTH_FILE_BYTES:
        return None, malformed
    try:
        data = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (TypeError, ValueError):
        return None, malformed
    if not isinstance(data, dict):
        return None, malformed

    records: list[dict[str, Any]] = []
    if "key" in data or "expires_at" in data:
        records.append(data)
    records.extend(
        value
        for value in data.values()
        if isinstance(value, dict) and ("key" in value or "expires_at" in value)
    )
    if not records:
        return None, malformed
    if len(records) != 1:
        return None, (
            "ambiguous_oauth_auth",
            "Grok OAuth credential selection is ambiguous",
        )

    # Deliberately read only the access key and its expiry.  In particular,
    # this adapter never reads, emits, or uses a refresh token.
    record = records[0]
    key = record.get("key")
    expires_at = record.get("expires_at")
    if (
        not isinstance(key, str)
        or not key.strip()
        or len(key) > 16_384
        or "\r" in key
        or "\n" in key
        or not isinstance(expires_at, str)
        or not expires_at.strip()
        or len(expires_at) > 128
    ):
        return None, malformed
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None, malformed
    if expiry.tzinfo is None:
        return None, malformed
    if expiry.astimezone(timezone.utc) <= _now_utc():
        return None, (
            "expired_oauth_auth",
            "Grok OAuth access credential is expired",
        )
    return key, None


def _request_input(messages: Any) -> list[dict[str, str]] | None:
    if not isinstance(messages, list) or not messages:
        return None
    normalized: list[dict[str, str]] = []
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


def _optional_instructions(value: Any) -> str | None | _InvalidSentinel:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return _INVALID
    return value


def _bounded_output_tokens(value: Any) -> int | None:
    if value is None:
        return _DEFAULT_OUTPUT_TOKENS
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return min(value, _MAX_OUTPUT_TOKENS)


def _request_timeout(value: Any) -> float:
    try:
        timeout = float(value) if value is not None else 120.0
    except (TypeError, ValueError):
        return 120.0
    if not math.isfinite(timeout):
        return 120.0
    return min(max(timeout, 1.0), 300.0)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate Grok OAuth credential key")
        value[key] = item
    return value


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
