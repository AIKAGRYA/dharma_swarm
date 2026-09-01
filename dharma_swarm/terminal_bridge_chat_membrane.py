"""Bounded no-tools structural membrane for Helm chat events."""

from __future__ import annotations

import re

from dharma_swarm.terminal_bridge_external_preview import (
    external_preview_tool_usage_disposition,
)
from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    ErrorEvent,
    SessionEnd,
    SessionStart,
)

_ALLOWED_CHAT_EVENT_TYPES = frozenset(
    {
        "error",
        "rate_limit",
        "session_end",
        "session_start",
        "text_complete",
        "text_delta",
        "thinking_complete",
        "thinking_delta",
        "usage",
    }
)
_FORBIDDEN_CHAT_EVENT_TYPES = frozenset(
    {
        "permission_decision",
        "permission_outcome",
        "permission_resolution",
        "task_complete",
        "task_progress",
        "task_started",
        "tool_args_delta",
        "tool_call_complete",
        "tool_call_start",
        "tool_progress",
        "tool_result",
    }
)
_FORBIDDEN_CHAT_EVENT_PREFIXES = (
    "command.",
    "command_",
    "permission.",
    "permission_",
    "task.",
    "task_",
    "tool.",
    "tool_",
)
_CHAT_TOOL_STRUCTURAL_KEYS = frozenset(
    {
        "function_call",
        "function_calls",
        "image_generation_call",
        "image_generation_calls",
        "mcp_call",
        "mcp_calls",
        "server_tool_use",
        "server_tool_use_details",
        "shell_call",
        "shell_calls",
        "tool",
        "tool_call",
        "tool_calls",
        "tool_use",
        "tool_uses",
        "web_search_call",
        "web_search_calls",
    }
)
_CHAT_TOOL_TYPE_MARKERS = (
    "code_interpreter",
    "computer_call",
    "computer_use",
    "code_interpreter_call",
    "file_search",
    "function_call",
    "image_generation_call",
    "mcp_call",
    "server_tool_use",
    "shell_call",
    "tool_call",
    "tool_use",
    "web_search",
)
_CHAT_TOOL_KEY_MARKERS = (
    "code_interpreter",
    "computer_call",
    "computer_use",
    "file_search",
    "function_call",
    "image_generation",
    "mcp",
    "server_tool_use",
    "shell_call",
    "tool",
    "web_search",
)
_CHAT_TOOL_CAPABILITIES = frozenset(
    {
        "code_interpreter",
        "computer_use",
        "function_call",
        "mcp",
        "parallel_tools",
        "shell",
        "tool_use",
        "web_search",
    }
)


def chat_event_is_forbidden(event_type: object) -> bool:
    normalized = str(event_type or "").strip().lower()
    return (
        normalized not in _ALLOWED_CHAT_EVENT_TYPES
        or normalized in _FORBIDDEN_CHAT_EVENT_TYPES
        or normalized.startswith(_FORBIDDEN_CHAT_EVENT_PREFIXES)
    )


def chat_event_contains_tool_evidence(value: object) -> bool:
    """Bounded structural scan; ordinary narration strings are never parsed."""

    pending: list[object] = [value]
    seen = 0
    while pending:
        current = pending.pop()
        seen += 1
        if seen > 4096:
            return True
        if isinstance(current, dict):
            for raw_key, item in current.items():
                key = _normalize_structural_label(raw_key)
                if key == "tools":
                    if item not in (None, []):
                        return True
                    continue
                if key == "parallel_tool_calls":
                    if item not in (None, False):
                        return True
                    continue
                if key == "tool_choice":
                    if item not in (None, "none"):
                        return True
                    continue
                tool_usage = external_preview_tool_usage_disposition(key, item)
                if tool_usage is not None:
                    if not tool_usage:
                        return True
                    continue
                if key in _CHAT_TOOL_STRUCTURAL_KEYS and item not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    return True
                if (
                    any(marker in key for marker in _CHAT_TOOL_KEY_MARKERS)
                    and item not in (None, "", [], {})
                ):
                    return True
                if key in {
                    "event",
                    "finish_reason",
                    "finishreason",
                    "kind",
                    "native_finish_reason",
                    "nativefinishreason",
                    "object",
                    "stop_reason",
                    "stopreason",
                    "type",
                }:
                    normalized = _normalize_structural_label(item)
                    if any(marker in normalized for marker in _CHAT_TOOL_TYPE_MARKERS):
                        return True
                if isinstance(item, (dict, list)):
                    pending.append(item)
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _normalize_structural_label(value: object) -> str:
    label = str(value or "").strip()
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", label)
    label = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", label)
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def chat_session_start_has_tool_authority(event: SessionStart) -> bool:
    capabilities = {_normalize_structural_label(item) for item in event.capabilities}
    return bool(event.tools_available) or bool(capabilities & _CHAT_TOOL_CAPABILITIES)

def failure_events(
    *,
    provider_id: str,
    session_id: str,
    code: str,
    message: str,
    retryable: bool,
) -> list[CanonicalEventType]:
    """One lane-failure buffer: a typed error followed by a failed end."""

    return [
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
    ]


