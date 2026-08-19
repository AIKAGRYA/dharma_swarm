"""Claude CLI NDJSON normalization into canonical provider events."""

from __future__ import annotations

import json
from typing import Any

from .base import Capability, ModelProfile
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


def capability_names(caps: Capability) -> list[str]:
    names: list[str] = []
    for cap in Capability:
        if caps & cap:
            names.append(cap.name.lower())
    return names


def normalize_claude_line(
    provider_id: str,
    raw_line: str,
    session_id: str,
    profile: ModelProfile,
) -> list[CanonicalEventType]:
    """Map one legacy Claude CLI frame to canonical provider events."""

    try:
        raw: dict[str, Any] = json.loads(raw_line)
    except Exception:
        raw = {}

    parsed = parse_ndjson_line(raw_line)
    if parsed is None:
        return []

    base = {
        "provider_id": provider_id,
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
                capabilities=capability_names(profile.capabilities),
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
                arg_text = (
                    arguments if isinstance(arguments, str) else json.dumps(arguments)
                )
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
                cache_write_tokens=int(
                    usage.get("cache_creation_input_tokens", 0) or 0
                ),
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


__all__ = ["capability_names", "normalize_claude_line"]
