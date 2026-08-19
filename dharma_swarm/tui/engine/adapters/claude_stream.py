"""Subprocess stream lifecycle for the Claude provider adapter."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

from .base import CompletionRequest, ModelProfile, ProviderConfig
from .claude_preview_protocol import (
    STRICT_DROP_TELEMETRY,
    STRICT_PREVIEW_MAX_BYTES,
    STRICT_PREVIEW_MAX_FRAMES,
    STRICT_REJECT,
    strict_preview_event_is_valid,
    strict_preview_raw_event_disposition,
    unique_json_object,
)
from ..events import CanonicalEventType, ErrorEvent, SessionEnd, SessionStart


class ClaudeStreamAdapter(Protocol):
    """Adapter surface consumed by the isolated stream state machine."""

    provider_id: str
    _config: ProviderConfig
    _proc: asyncio.subprocess.Process | None

    def get_profile(self, model_id: str | None = None) -> ModelProfile: ...

    def _build_command(self, request: CompletionRequest) -> list[str]: ...

    def _build_env(self, request: CompletionRequest) -> dict[str, str]: ...

    async def _spawn_process(
        self,
        cmd: list[str],
        env: dict[str, str],
    ) -> asyncio.subprocess.Process: ...

    def _normalize_line(
        self,
        raw_line: str,
        session_id: str,
        profile: ModelProfile,
    ) -> list[CanonicalEventType]: ...


async def stream_claude(
    adapter: ClaudeStreamAdapter,
    request: CompletionRequest,
    session_id: str,
    *,
    drain_stderr: Callable[[Any], Awaitable[str]],
    terminate: Callable[[asyncio.subprocess.Process], Awaitable[None]],
) -> AsyncIterator[CanonicalEventType]:
    """Run one Claude CLI request and project its bounded NDJSON stream."""

    profile = adapter.get_profile(request.model)
    cmd = adapter._build_command(request)
    env = adapter._build_env(request)
    emitted_session_end = False

    proc = await adapter._spawn_process(cmd, env)
    adapter._proc = proc
    stderr_task = (
        asyncio.create_task(drain_stderr(proc.stderr))
        if proc.stderr is not None
        else None
    )
    stream_read_failed = False
    stream_read_error = ""
    strict_preview_protocol = bool(
        request.provider_options.get("strict_preview_protocol")
    )
    strict_preview_bytes = 0
    strict_preview_frames = 0
    strict_provider_session_id: str | None = None
    strict_max_bytes = max(
        1,
        int(
            adapter._config.extra.get(
                "strict_preview_max_bytes", STRICT_PREVIEW_MAX_BYTES
            )
        ),
    )
    strict_max_frames = max(
        1,
        int(
            adapter._config.extra.get(
                "strict_preview_max_frames", STRICT_PREVIEW_MAX_FRAMES
            )
        ),
    )

    try:
        assert proc.stdout is not None
        while True:
            try:
                line = await proc.stdout.readline()
            except Exception as exc:
                # Avoid hard-crashing provider runner on oversized/invalid lines.
                stream_read_error = f"{type(exc).__name__}: {exc}"
                yield ErrorEvent(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    code="stream_read_error",
                    message=stream_read_error,
                    retryable=True,
                )
                stream_read_failed = True
                break
            if not line:
                break
            if strict_preview_protocol:
                strict_preview_bytes += len(line)
                strict_preview_frames += 1
                if (
                    strict_preview_bytes > strict_max_bytes
                    or strict_preview_frames > strict_max_frames
                ):
                    stream_read_error = (
                        "Claude preview output exceeded its resource bound"
                    )
                    yield ErrorEvent(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        code="provider_output_limit",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        success=False,
                        error_code="provider_output_limit",
                        error_message=stream_read_error,
                    )
                    emitted_session_end = True
                    stream_read_failed = True
                    break
                if emitted_session_end:
                    stream_read_error = "Claude returned data after its terminal result"
                    yield ErrorEvent(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        code="unexpected_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        success=False,
                        error_code="unexpected_provider_event",
                        error_message=stream_read_error,
                    )
                    stream_read_failed = True
                    break
            try:
                raw_line = line.decode(
                    "utf-8",
                    errors="strict" if strict_preview_protocol else "replace",
                ).strip()
            except UnicodeDecodeError:
                stream_read_error = "Claude returned invalid UTF-8"
                yield ErrorEvent(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    code="malformed_provider_event",
                    message=stream_read_error,
                    retryable=False,
                )
                yield SessionEnd(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="malformed_provider_event",
                    error_message=stream_read_error,
                )
                emitted_session_end = True
                stream_read_failed = True
                break
            if not raw_line:
                continue
            if strict_preview_protocol:
                try:
                    parsed_raw = json.loads(
                        raw_line,
                        object_pairs_hook=unique_json_object,
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    parsed_raw = None
                if not isinstance(parsed_raw, dict):
                    stream_read_error = "Claude returned malformed provider output"
                    yield ErrorEvent(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        code="malformed_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        success=False,
                        error_code="malformed_provider_event",
                        error_message=stream_read_error,
                    )
                    emitted_session_end = True
                    stream_read_failed = True
                    break
                disposition = strict_preview_raw_event_disposition(parsed_raw)
                if disposition == STRICT_REJECT:
                    stream_read_error = "Claude returned invalid preview metadata"
                    yield ErrorEvent(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        code="malformed_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        success=False,
                        error_code="malformed_provider_event",
                        error_message=stream_read_error,
                    )
                    emitted_session_end = True
                    stream_read_failed = True
                    break
                if disposition == STRICT_DROP_TELEMETRY:
                    if (
                        strict_provider_session_id is None
                        or parsed_raw.get("session_id") != strict_provider_session_id
                    ):
                        stream_read_error = (
                            "Claude telemetry session identity did not match"
                        )
                        yield ErrorEvent(
                            provider_id=adapter.provider_id,
                            session_id=session_id,
                            code="malformed_provider_event",
                            message=stream_read_error,
                            retryable=False,
                        )
                        yield SessionEnd(
                            provider_id=adapter.provider_id,
                            session_id=session_id,
                            success=False,
                            error_code="malformed_provider_event",
                            error_message=stream_read_error,
                        )
                        emitted_session_end = True
                        stream_read_failed = True
                        break
                    continue
                raw_type = parsed_raw.get("type")
                provider_session_id = parsed_raw.get("session_id")
                identity_mismatch = (
                    raw_type == "system"
                    and strict_provider_session_id not in {None, provider_session_id}
                ) or (
                    raw_type in {"assistant", "result"}
                    and provider_session_id != strict_provider_session_id
                )
                if identity_mismatch:
                    stream_read_error = "Claude provider session identity changed"
                    yield ErrorEvent(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        code="malformed_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=adapter.provider_id,
                        session_id=session_id,
                        success=False,
                        error_code="malformed_provider_event",
                        error_message=stream_read_error,
                    )
                    emitted_session_end = True
                    stream_read_failed = True
                    break
                if raw_type == "system":
                    strict_provider_session_id = str(provider_session_id)
                raw_line = json.dumps(
                    parsed_raw,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            events = adapter._normalize_line(
                raw_line,
                session_id=session_id,
                profile=profile,
            )
            if strict_preview_protocol and not events:
                stream_read_error = "Claude returned unexpected provider output"
                yield ErrorEvent(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    code="unexpected_provider_event",
                    message=stream_read_error,
                    retryable=False,
                )
                yield SessionEnd(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="unexpected_provider_event",
                    error_message=stream_read_error,
                )
                emitted_session_end = True
                stream_read_failed = True
                break
            if strict_preview_protocol and not all(
                strict_preview_event_is_valid(event) for event in events
            ):
                stream_read_error = "Claude returned invalid preview metadata"
                yield ErrorEvent(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    code="malformed_provider_event",
                    message=stream_read_error,
                    retryable=False,
                )
                yield SessionEnd(
                    provider_id=adapter.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="malformed_provider_event",
                    error_message=stream_read_error,
                )
                emitted_session_end = True
                stream_read_failed = True
                break
            for event in events:
                if strict_preview_protocol and isinstance(event, SessionStart):
                    event.capabilities = [
                        capability
                        for capability in event.capabilities
                        if capability not in {"tool_use", "parallel_tools"}
                    ]
                    event.system_info = {
                        **event.system_info,
                        "tool_authority": "none",
                        "tools_disabled": True,
                    }
                if isinstance(event, SessionEnd):
                    emitted_session_end = True
                yield event

        if stream_read_failed:
            await terminate(proc)
        exit_code = await proc.wait()
        err_text = ""
        if stderr_task is not None:
            stderr_result = (await asyncio.gather(stderr_task, return_exceptions=True))[
                0
            ]
            if isinstance(stderr_result, str):
                err_text = stderr_result
            elif isinstance(stderr_result, BaseException):
                err_text = f"stderr read failed: {type(stderr_result).__name__}"
        if stream_read_failed and not emitted_session_end:
            yield SessionEnd(
                provider_id=adapter.provider_id,
                session_id=session_id,
                success=False,
                error_code="stream_read_error",
                error_message=stream_read_error,
            )
        elif exit_code != 0 and not emitted_session_end:
            yield ErrorEvent(
                provider_id=adapter.provider_id,
                session_id=session_id,
                code="process_exit",
                message=err_text or f"claude exited with code {exit_code}",
                retryable=False,
            )
            yield SessionEnd(
                provider_id=adapter.provider_id,
                session_id=session_id,
                success=False,
                error_code="process_exit",
                error_message=f"claude exited with code {exit_code}",
            )
        elif exit_code == 0 and not emitted_session_end and strict_preview_protocol:
            yield ErrorEvent(
                provider_id=adapter.provider_id,
                session_id=session_id,
                code="incomplete_provider_response",
                message="Claude ended before an explicit result event",
                retryable=False,
            )
            yield SessionEnd(
                provider_id=adapter.provider_id,
                session_id=session_id,
                success=False,
                error_code="incomplete_provider_response",
                error_message="Claude ended before an explicit result event",
            )
        elif exit_code == 0 and not emitted_session_end:
            yield SessionEnd(
                provider_id=adapter.provider_id,
                session_id=session_id,
                success=True,
            )
    finally:
        await terminate(proc)
        if stderr_task is not None:
            if not stderr_task.done():
                stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)
        if adapter._proc is proc:
            adapter._proc = None


__all__ = ["ClaudeStreamAdapter", "stream_claude"]
