"""Claude Code provider adapter (subprocess + NDJSON -> canonical events)."""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from typing import Any, AsyncIterator

from dharma_swarm import model_pool as _model_pool
from dharma_swarm.models import ProviderType

from .base import Capability, CompletionRequest, ModelProfile, ProviderAdapter, ProviderConfig
from .claude_cli import build_claude_command, build_claude_env, build_claude_prompt
from .claude_process import drain_stderr_tail, terminate_process
from ..events import (
    CanonicalEventType,
    ErrorEvent,
    RateLimitEvent,
    SessionEnd,
    SessionStart,
    TaskProgress,
    TaskStarted,
    TextComplete,
    TextDelta,
    ThinkingComplete,
    ThinkingDelta,
    ToolArgumentsDelta,
    ToolCallComplete,
    ToolProgress,
    ToolResult,
    UsageReport,
)
from ..event_types import (
    AssistantMessage as LegacyAssistantMessage,
    RateLimitEvent as LegacyRateLimitEvent,
    ResultMessage as LegacyResultMessage,
    StreamDelta as LegacyStreamDelta,
    SystemInit as LegacySystemInit,
    TaskProgress as LegacyTaskProgress,
    TaskStarted as LegacyTaskStarted,
    ToolProgress as LegacyToolProgress,
    ToolResult as LegacyToolResult,
)
from ..stream_parser import parse_ndjson_line

DHARMA_SWARM = Path(__file__).resolve().parents[4]

CLAUDE_CAPABILITIES = (
    Capability.STREAMING
    | Capability.TOOL_USE
    | Capability.THINKING
    | Capability.VISION
    | Capability.PARALLEL_TOOLS
    | Capability.RESUME
    | Capability.COST_TRACKING
    | Capability.CONTEXT_USAGE
    | Capability.SYSTEM_PROMPT
    | Capability.CANCEL
)


def _canonical_claude_model() -> str:
    entry = _model_pool.get_entry("claude-opus-4.8")
    if entry is not None:
        for provider in (ProviderType.CLAUDE_CODE, ProviderType.ANTHROPIC):
            for route in entry.routes:
                if route.provider is provider:
                    return route.model_id
    raise AssertionError("model_pool has no Claude route for claude-opus-4.8")


CLAUDE_DEFAULT_MODEL = _canonical_claude_model()


def _capability_names(caps: Capability) -> list[str]:
    names: list[str] = []
    for cap in Capability:
        if caps & cap:
            names.append(cap.name.lower())
    return names


class ClaudeAdapter(ProviderAdapter):
    """ProviderAdapter implementation for Claude Code CLI."""

    provider_id = "claude"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        cli_path: str = "claude",
        workdir: Path | None = None,
    ) -> None:
        self._config = config or ProviderConfig(
            provider_id=self.provider_id,
            default_model=CLAUDE_DEFAULT_MODEL,
        )
        self._cli_path = cli_path
        self._workdir = workdir or DHARMA_SWARM
        self._proc: asyncio.subprocess.Process | None = None
        self._profiles: dict[str, ModelProfile] = {
            CLAUDE_DEFAULT_MODEL: ModelProfile(
                provider_id=self.provider_id,
                model_id=CLAUDE_DEFAULT_MODEL,
                display_name="Claude Opus 4.8",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-sonnet-4-5": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-sonnet-4-5",
                display_name="Claude Sonnet 4.5",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-sonnet-4-6": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-sonnet-4-6",
                display_name="Claude Sonnet 4.6",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-opus-4": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-opus-4",
                display_name="Claude Opus 4",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-opus-4-6": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-opus-4-6",
                display_name="Claude Opus 4.6",
                capabilities=CLAUDE_CAPABILITIES,
            ),
            "claude-haiku-4-5": ModelProfile(
                provider_id=self.provider_id,
                model_id="claude-haiku-4-5",
                display_name="Claude Haiku 4.5",
                capabilities=CLAUDE_CAPABILITIES,
            ),
        }

    async def list_models(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        model = model_id or self._config.default_model or CLAUDE_DEFAULT_MODEL
        profile = self._profiles.get(model)
        if profile is not None:
            return profile
        return ModelProfile(
            provider_id=self.provider_id,
            model_id=model,
            display_name=model,
            capabilities=CLAUDE_CAPABILITIES,
        )

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[CanonicalEventType]:
        profile = self.get_profile(request.model)
        cmd = self._build_command(request)
        env = self._build_env(request)
        emitted_session_end = False

        proc = await self._spawn_process(cmd, env)
        self._proc = proc
        stderr_task = (
            asyncio.create_task(drain_stderr_tail(proc.stderr))
            if proc.stderr is not None
            else None
        )
        stream_read_failed = False
        stream_read_error = ""
        strict_preview_protocol = bool(
            request.provider_options.get("strict_preview_protocol")
        )

        try:
            assert proc.stdout is not None
            while True:
                try:
                    line = await proc.stdout.readline()
                except Exception as exc:
                    # Avoid hard-crashing provider runner on oversized/invalid stream lines.
                    stream_read_error = f"{type(exc).__name__}: {exc}"
                    yield ErrorEvent(
                        provider_id=self.provider_id,
                        session_id=session_id,
                        code="stream_read_error",
                        message=stream_read_error,
                        retryable=True,
                    )
                    stream_read_failed = True
                    break
                if not line:
                    break
                try:
                    raw_line = line.decode(
                        "utf-8",
                        errors="strict" if strict_preview_protocol else "replace",
                    ).strip()
                except UnicodeDecodeError:
                    stream_read_error = "Claude returned invalid UTF-8"
                    yield ErrorEvent(
                        provider_id=self.provider_id,
                        session_id=session_id,
                        code="malformed_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=self.provider_id,
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
                            object_pairs_hook=_unique_json_object,
                        )
                    except (TypeError, ValueError, json.JSONDecodeError):
                        parsed_raw = None
                    if not isinstance(parsed_raw, dict):
                        stream_read_error = "Claude returned malformed provider output"
                        yield ErrorEvent(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            code="malformed_provider_event",
                            message=stream_read_error,
                            retryable=False,
                        )
                        yield SessionEnd(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            success=False,
                            error_code="malformed_provider_event",
                            error_message=stream_read_error,
                        )
                        emitted_session_end = True
                        stream_read_failed = True
                        break
                    if not _strict_preview_raw_event_is_valid(parsed_raw):
                        stream_read_error = "Claude returned invalid preview metadata"
                        yield ErrorEvent(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            code="malformed_provider_event",
                            message=stream_read_error,
                            retryable=False,
                        )
                        yield SessionEnd(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            success=False,
                            error_code="malformed_provider_event",
                            error_message=stream_read_error,
                        )
                        emitted_session_end = True
                        stream_read_failed = True
                        break
                    raw_line = json.dumps(
                        parsed_raw,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                events = self._normalize_line(raw_line, session_id=session_id, profile=profile)
                if strict_preview_protocol and not events:
                    stream_read_error = "Claude returned unexpected provider output"
                    yield ErrorEvent(
                        provider_id=self.provider_id,
                        session_id=session_id,
                        code="unexpected_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=self.provider_id,
                        session_id=session_id,
                        success=False,
                        error_code="unexpected_provider_event",
                        error_message=stream_read_error,
                    )
                    emitted_session_end = True
                    stream_read_failed = True
                    break
                if strict_preview_protocol and not all(
                    _strict_preview_event_is_valid(event) for event in events
                ):
                    stream_read_error = "Claude returned invalid preview metadata"
                    yield ErrorEvent(
                        provider_id=self.provider_id,
                        session_id=session_id,
                        code="malformed_provider_event",
                        message=stream_read_error,
                        retryable=False,
                    )
                    yield SessionEnd(
                        provider_id=self.provider_id,
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
                await terminate_process(proc)
            exit_code = await proc.wait()
            err_text = ""
            if stderr_task is not None:
                stderr_result = (await asyncio.gather(stderr_task, return_exceptions=True))[0]
                if isinstance(stderr_result, str):
                    err_text = stderr_result
                elif isinstance(stderr_result, BaseException):
                    err_text = f"stderr read failed: {type(stderr_result).__name__}"
            if stream_read_failed and not emitted_session_end:
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="stream_read_error",
                    error_message=stream_read_error,
                )
            elif exit_code != 0 and not emitted_session_end:
                yield ErrorEvent(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    code="process_exit",
                    message=err_text or f"claude exited with code {exit_code}",
                    retryable=False,
                )
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="process_exit",
                    error_message=f"claude exited with code {exit_code}",
                )
            elif exit_code == 0 and not emitted_session_end and strict_preview_protocol:
                yield ErrorEvent(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    code="incomplete_provider_response",
                    message="Claude ended before an explicit result event",
                    retryable=False,
                )
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="incomplete_provider_response",
                    error_message="Claude ended before an explicit result event",
                )
            elif exit_code == 0 and not emitted_session_end:
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=True,
                )
        finally:
            await terminate_process(proc)
            if stderr_task is not None:
                if not stderr_task.done():
                    stderr_task.cancel()
                await asyncio.gather(stderr_task, return_exceptions=True)
            if self._proc is proc:
                self._proc = None

    async def cancel(self) -> None:
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        try:
            await terminate_process(proc)
        finally:
            if self._proc is proc:
                self._proc = None

    async def close(self) -> None:
        await self.cancel()

    async def _spawn_process(
        self,
        cmd: list[str],
        env: dict[str, str],
    ) -> asyncio.subprocess.Process:
        # Increase StreamReader line limit to tolerate large NDJSON tool-result
        # events (default is 64 KiB and can fail on large file reads).
        stream_limit = int(self._config.extra.get("stream_reader_limit", 2_000_000))
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._workdir),
            env=env,
            limit=stream_limit,
        )

    def _build_env(self, request: CompletionRequest) -> dict[str, str]:
        return build_claude_env(request)

    def _build_command(self, request: CompletionRequest) -> list[str]:
        return build_claude_command(
            self._cli_path,
            request,
            default_model=self._config.default_model,
            prompt=self._build_prompt(request),
        )

    def _build_prompt(self, request: CompletionRequest) -> str:
        return build_claude_prompt(request)

    def _normalize_line(
        self,
        raw_line: str,
        session_id: str,
        profile: ModelProfile,
    ) -> list[CanonicalEventType]:
        try:
            raw: dict[str, Any] = json.loads(raw_line)
        except Exception:
            raw = {}

        parsed = parse_ndjson_line(raw_line)
        if parsed is None:
            return []

        base = {
            "provider_id": self.provider_id,
            "session_id": session_id,
            "raw": raw,
        }

        events: list[CanonicalEventType] = []

        if isinstance(parsed, LegacySystemInit):
            events.append(
                SessionStart(
                    **base,
                    model=parsed.model,
                    provider_session_id=parsed.session_id or None,
                    capabilities=_capability_names(profile.capabilities),
                    tools_available=parsed.tools,
                    system_info={
                        "cwd": parsed.cwd,
                        "permission_mode": parsed.permission_mode,
                        "claude_code_version": parsed.claude_code_version,
                        "mcp_servers": parsed.mcp_servers,
                        "requested_model": profile.model_id,
                        "served_model": parsed.model,
                        "served_identity_source": "system.init.model",
                        "exact_model_proven": parsed.model == profile.model_id,
                    },
                )
            )
            return events

        if isinstance(parsed, LegacyAssistantMessage):
            for idx, block in enumerate(parsed.content_blocks):
                btype = block.get("type")
                if btype == "text":
                    events.append(
                        TextComplete(
                            **base,
                            content=str(block.get("text", "")),
                            content_index=idx,
                            role="assistant",
                        )
                    )
                elif btype == "thinking":
                    events.append(
                        ThinkingComplete(
                            **base,
                            content=str(block.get("thinking", "")),
                            is_redacted=False,
                        )
                    )
                elif btype == "redacted_thinking":
                    events.append(
                        ThinkingComplete(
                            **base,
                            content="",
                            is_redacted=True,
                        )
                    )
                elif btype == "tool_use":
                    arguments = block.get("input", {})
                    if isinstance(arguments, str):
                        arg_text = arguments
                    else:
                        arg_text = json.dumps(arguments)
                    events.append(
                        ToolCallComplete(
                            **base,
                            tool_call_id=str(block.get("id", "")),
                            tool_name=str(block.get("name", "")),
                            arguments=arg_text,
                        )
                    )
            return events

        if isinstance(parsed, LegacyToolResult):
            events.append(
                ToolResult(
                    **base,
                    tool_call_id=parsed.tool_use_id,
                    tool_name=parsed.tool_name,
                    content=parsed.content,
                    is_error=parsed.is_error,
                    structured_result=parsed.structured_result,
                    duration_ms=parsed.duration_ms,
                )
            )
            return events

        if isinstance(parsed, LegacyStreamDelta):
            if parsed.delta_type == "text_delta":
                events.append(
                    TextDelta(
                        **base,
                        content=parsed.content,
                        content_index=parsed.block_index,
                    )
                )
            elif parsed.delta_type == "thinking_delta":
                events.append(ThinkingDelta(**base, content=parsed.content))
            elif parsed.delta_type == "input_json_delta":
                events.append(
                    ToolArgumentsDelta(
                        **base,
                        tool_call_id=parsed.parent_tool_use_id or "",
                        delta=parsed.content,
                    )
                )
            return events

        if isinstance(parsed, LegacyToolProgress):
            events.append(
                ToolProgress(
                    **base,
                    tool_call_id=parsed.tool_use_id,
                    tool_name=parsed.tool_name,
                    elapsed_seconds=parsed.elapsed_seconds,
                )
            )
            return events

        if isinstance(parsed, LegacyTaskStarted):
            events.append(
                TaskStarted(
                    **base,
                    task_id=parsed.task_id,
                    description=parsed.description,
                    parent_tool_call_id=parsed.tool_use_id or None,
                )
            )
            return events

        if isinstance(parsed, LegacyTaskProgress):
            summary = parsed.last_tool_name or ""
            if parsed.usage:
                summary = (summary + " " if summary else "") + f"usage={parsed.usage}"
            events.append(TaskProgress(**base, task_id=parsed.task_id, summary=summary))
            return events

        if isinstance(parsed, LegacyRateLimitEvent):
            events.append(
                RateLimitEvent(
                    **base,
                    status=parsed.status,
                    utilization=parsed.utilization,
                    resets_at=float(parsed.resets_at) if parsed.resets_at else None,
                )
            )
            return events

        if isinstance(parsed, LegacyResultMessage):
            usage = parsed.model_usage or {}
            events.append(
                UsageReport(
                    **base,
                    input_tokens=int(usage.get("input_tokens", 0) or 0),
                    output_tokens=int(usage.get("output_tokens", 0) or 0),
                    cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
                    cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
                    thinking_tokens=int(usage.get("thinking_tokens", 0) or 0),
                    total_cost_usd=parsed.total_cost_usd,
                    model_breakdown=usage,
                )
            )
            if parsed.is_error:
                message = parsed.errors[0] if parsed.errors else (parsed.result_text or "")
                events.append(
                    ErrorEvent(
                        **base,
                        code=parsed.subtype,
                        message=message or "provider execution failed",
                    )
                )
            events.append(
                SessionEnd(
                    **base,
                    success=not parsed.is_error,
                    error_code=parsed.subtype if parsed.is_error else None,
                    error_message=(
                        parsed.errors[0]
                        if parsed.is_error and parsed.errors
                        else (parsed.result_text if parsed.is_error else None)
                    ),
                )
            )
            return events

        return events


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate Claude provider JSON key")
        value[key] = item
    return value


def _strict_preview_event_is_valid(event: CanonicalEventType) -> bool:
    if isinstance(event, RateLimitEvent):
        return False
    if not isinstance(event, UsageReport):
        return True
    token_values = (
        event.input_tokens,
        event.output_tokens,
        event.cache_read_tokens,
        event.cache_write_tokens,
        event.thinking_tokens,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in token_values):
        return False
    if event.total_cost_usd is None:
        return True
    if isinstance(event.total_cost_usd, bool) or not isinstance(
        event.total_cost_usd, (int, float)
    ):
        return False
    cost = float(event.total_cost_usd)
    if not math.isfinite(cost) or cost < 0:
        return False
    event.total_cost_usd = cost
    return True


def _strict_preview_raw_event_is_valid(raw: dict[str, Any]) -> bool:
    event_type = raw.get("type")
    if not isinstance(event_type, str):
        return False
    if event_type == "system":
        if raw.get("subtype") != "init":
            return False
        if not _nonempty_string(raw.get("model")) or not isinstance(
            raw.get("session_id"), str
        ):
            return False
        tools = raw.get("tools")
        if not isinstance(tools, list) or not all(isinstance(item, str) for item in tools):
            return False
        for key in ("cwd", "permissionMode", "permission_mode", "claude_code_version"):
            if key in raw and not isinstance(raw[key], str):
                return False
        return isinstance(raw.get("mcp_servers", []), list)
    if event_type == "assistant":
        message = raw.get("message")
        if not isinstance(message, dict):
            return False
        content = message.get("content")
        if not isinstance(content, list) or not content:
            return False
        for block in content:
            if not isinstance(block, dict):
                return False
            block_type = block.get("type")
            if block_type == "text":
                if not isinstance(block.get("text"), str):
                    return False
            elif block_type == "thinking":
                if not isinstance(block.get("thinking"), str):
                    return False
            else:
                return False
        for value in (
            raw.get("uuid", ""),
            raw.get("session_id", ""),
            raw.get("parent_tool_use_id"),
            message.get("stop_reason"),
        ):
            if value is not None and not isinstance(value, str):
                return False
        return message.get("usage") is None or isinstance(message.get("usage"), dict)
    if event_type != "result":
        return False
    if raw.get("subtype") != "success" or raw.get("is_error") is not False:
        return False
    if not isinstance(raw.get("session_id", ""), str):
        return False
    for key in ("duration_ms", "num_turns"):
        if not _nonnegative_int(raw.get(key)):
            return False
    cost = raw.get("total_cost_usd")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        return False
    if not math.isfinite(float(cost)) or float(cost) < 0:
        return False
    if raw.get("result") is not None and not isinstance(raw.get("result"), str):
        return False
    errors = raw.get("errors", [])
    if not isinstance(errors, list) or not all(isinstance(item, str) for item in errors):
        return False
    usage = raw.get("model_usage", {})
    if not isinstance(usage, dict):
        return False
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "thinking_tokens",
    ):
        if key in usage and not _nonnegative_int(usage[key]):
            return False
    return True


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonnegative_int(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0
