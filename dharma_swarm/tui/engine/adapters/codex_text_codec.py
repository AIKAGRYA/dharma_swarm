"""Strict decoding helpers for the sealed Codex text event stream.

Only structural provider fields participate in the no-tools check.  Assistant
prose is deliberately opaque so ordinary words such as "shell" cannot be
misclassified as execution evidence.
"""

from __future__ import annotations

import json
import re
from typing import Any


_SAFE_TOP_LEVEL_EVENTS = frozenset(
    {
        "thread.started",
        "turn.started",
        "item.started",
        "item.completed",
        "turn.completed",
        "error",
    }
)
_SAFE_ITEM_TYPES = frozenset(
    {
        "agent_message",
        "message",
        "reasoning",
        "reasoning_summary",
        "thinking",
        "error",
    }
)
_TOOL_MARKERS = (
    "command",
    "computer",
    "exec",
    "function_call",
    "image",
    "mcp",
    "shell",
    "tool",
    "web_search",
    "browser",
    "apply_patch",
)
_STRUCTURAL_DISCRIMINATORS = frozenset(
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
_MAX_EVENT_NODES = 4096


def _normalize_structural_label(label: object) -> str:
    value = str(label or "").strip()
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _looks_tool_shaped(label: object) -> bool:
    normalized = _normalize_structural_label(label)
    return any(marker in normalized for marker in _TOOL_MARKERS)


def _contains_structural_tool_evidence(value: object) -> bool:
    """Reject nested tool structure without interpreting ordinary text."""

    pending: list[object] = [value]
    seen = 0
    while pending:
        current = pending.pop()
        seen += 1
        if seen > _MAX_EVENT_NODES:
            return True
        if isinstance(current, dict):
            for raw_key, child in current.items():
                key = _normalize_structural_label(raw_key)
                if _looks_tool_shaped(key):
                    return True
                if key in _STRUCTURAL_DISCRIMINATORS and _looks_tool_shaped(child):
                    return True
                if isinstance(child, (dict, list)):
                    pending.append(child)
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _extract_message_text(item: dict[str, Any]) -> str:
    text = item.get("text")
    if isinstance(text, str):
        return text
    content = item.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for part in content:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "".join(chunks)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate provider JSON key")
        result[key] = value
    return result


def _decode_provider_event(raw_line: str) -> dict[str, Any]:
    raw = json.loads(raw_line, object_pairs_hook=_unique_json_object)
    if not isinstance(raw, dict):
        raise ValueError("provider event must be a JSON object")
    return raw


def _safe_usage(raw: object) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None

    def as_nonnegative_int(value: object) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    return {
        "input_tokens": as_nonnegative_int(raw.get("input_tokens")),
        "output_tokens": as_nonnegative_int(raw.get("output_tokens")),
        "cache_read_tokens": as_nonnegative_int(raw.get("cached_input_tokens")),
    }
