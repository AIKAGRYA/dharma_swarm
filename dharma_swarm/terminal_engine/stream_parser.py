"""Parse a single NDJSON line from Claude Code CLI into a typed event.

This module is the critical bridge between raw CLI output and the typed
event system. It handles every event type emitted by
``claude --output-format stream-json``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import event_types
from .event_types import (
    AssistantMessage,
    RateLimitEvent,
    ResultMessage,
    StreamDelta,
    SystemInit,
    TaskProgress,
    TaskStarted,
    ToolProgress,
    ToolResult,
)

logger = logging.getLogger(__name__)

Event = (
    SystemInit
    | AssistantMessage
    | ToolResult
    | StreamDelta
    | ResultMessage
    | ToolProgress
    | TaskStarted
    | TaskProgress
    | RateLimitEvent
    | None
)


def parse_ndjson_line(line: str) -> Event:
    """Parse a single NDJSON line into a typed event dataclass."""
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        logger.debug("unparseable NDJSON line: %s", line[:200])
        return None

    event_type = data.get("type", "")

    if event_type == "system":
        return _parse_system(data)
    if event_type == "assistant":
        return _parse_assistant(data)
    if event_type == "user":
        return _parse_user(data)
    if event_type == "content_block_delta":
        return _parse_stream_event(data)
    if event_type == "result":
        return _parse_result(data)
    if event_type == "tool_progress":
        return _parse_tool_progress(data)
    if event_type == "rate_limit":
        return _parse_rate_limit(data)

    logger.debug("unrecognized event type: %s", event_type)
    return None


def _parse_system(data: dict[str, Any]) -> SystemInit | TaskStarted | TaskProgress | None:
    subtype = data.get("subtype", "")
    if subtype == "init":
        return SystemInit(
            session_id=data.get("session_id", ""),
            model=data.get("model", ""),
            cwd=data.get("cwd", ""),
            permission_mode=data.get("permissionMode", ""),
            claude_code_version=data.get("claude_code_version", ""),
            tools=data.get("tools", []),
            mcp_servers=data.get("mcp_servers", []),
        )
    if subtype == "task_started":
        return TaskStarted(
            task_id=data.get("task_id", ""),
            description=data.get("description", ""),
        )
    if subtype == "task_progress":
        return TaskProgress(
            task_id=data.get("task_id", ""),
            summary=data.get("summary", ""),
        )
    logger.debug("unrecognized system subtype: %s", subtype)
    return None


def _parse_assistant(data: dict[str, Any]) -> AssistantMessage:
    raw_message = data.get("message", "")
    content_blocks: list[dict[str, Any]] = []
    if isinstance(raw_message, dict):
        content = raw_message.get("content", [])
        if isinstance(content, list):
            content_blocks = [b for b in content if isinstance(b, dict)]
        message_text = "".join(
            str(b.get("text", "")) for b in content_blocks if b.get("type") == "text"
        )
    else:
        message_text = str(raw_message)
    return AssistantMessage(
        message=message_text,
        content_blocks=content_blocks,
        usage=data.get("usage"),
        stop_reason=data.get("stop_reason", ""),
    )


def _parse_user(data: dict[str, Any]) -> ToolResult | None:
    content = data.get("content", "")
    if isinstance(content, list):
        text = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        return ToolResult(content=text)
    return ToolResult(content=str(content))


def _parse_stream_event(data: dict[str, Any]) -> StreamDelta | None:
    delta = data.get("delta", {})
    if not delta:
        logger.debug("stream event without delta: %s", data.get("type"))
        return None
    content = delta.get("text", "") or delta.get("partial_json", "")
    return StreamDelta(
        index=data.get("index", 0),
        delta_type=delta.get("type", ""),
        text=delta.get("text", ""),
        content=content,
        block_index=data.get("index", 0),
        parent_tool_use_id=data.get("parent_tool_use_id", ""),
    )


def _parse_result(data: dict[str, Any]) -> ResultMessage:
    return ResultMessage(
        subtype=data.get("subtype", ""),
        result_text=data.get("result", ""),
        is_error=bool(data.get("is_error", False)),
        total_cost_usd=float(data.get("total_cost_usd", 0) or 0),
        errors=data.get("errors", []),
        model_usage=data.get("usage", {}),
    )


def _parse_tool_progress(data: dict[str, Any]) -> ToolProgress:
    return ToolProgress(
        tool_use_id=data.get("tool_use_id", ""),
        tool_name=data.get("tool_name", ""),
        elapsed_seconds=data.get("elapsed_seconds", 0.0),
    )


def _parse_rate_limit(data: dict[str, Any]) -> RateLimitEvent | None:
    status = data.get("status", "")
    if not status:
        return None
    return RateLimitEvent(
        status=status,
        resets_at=data.get("resets_at", ""),
        utilization=data.get("utilization", 0.0),
    )
