"""Fail-closed validators for the sealed Claude preview protocol."""

from __future__ import annotations

import math
from typing import Any

from ..events import CanonicalEventType, RateLimitEvent, UsageReport

STRICT_PREVIEW_MAX_BYTES = 4 * 1024 * 1024
STRICT_PREVIEW_MAX_FRAMES = 4096
STRICT_ACCEPT = "accept"
STRICT_DROP_TELEMETRY = "drop_telemetry"
STRICT_REJECT = "reject"


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate Claude provider JSON key")
        value[key] = item
    return value


def strict_preview_event_is_valid(event: CanonicalEventType) -> bool:
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
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in token_values
    ):
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


def strict_preview_raw_event_disposition(raw: dict[str, Any]) -> str:
    event_type = raw.get("type")
    if event_type == "rate_limit_event":
        return (
            STRICT_DROP_TELEMETRY
            if _strict_rate_limit_telemetry_is_valid(raw)
            else STRICT_REJECT
        )
    if event_type == "system" and raw.get("subtype") == "thinking_tokens":
        return (
            STRICT_DROP_TELEMETRY
            if _strict_thinking_telemetry_is_valid(raw)
            else STRICT_REJECT
        )
    return STRICT_ACCEPT if _strict_preview_raw_event_is_valid(raw) else STRICT_REJECT


def _strict_rate_limit_telemetry_is_valid(raw: dict[str, Any]) -> bool:
    if set(raw) != {"type", "rate_limit_info", "session_id", "uuid"}:
        return False
    if not _bounded_string(raw.get("session_id")) or not _bounded_string(
        raw.get("uuid")
    ):
        return False
    info = raw.get("rate_limit_info")
    if not isinstance(info, dict):
        return False
    allowed = {
        "status",
        "resetsAt",
        "rateLimitType",
        "overageStatus",
        "overageDisabledReason",
        "isUsingOverage",
        "utilization",
        "surpassedThreshold",
        "unifiedWindows",
    }
    if not set(info).issubset(allowed):
        return False
    if not _bounded_string(info.get("status")) or not _bounded_string(
        info.get("rateLimitType")
    ):
        return False
    if not _bounded_nonnegative_int(info.get("resetsAt"), maximum=10**15):
        return False
    if not isinstance(info.get("isUsingOverage"), bool):
        return False
    for key in ("overageStatus", "overageDisabledReason"):
        if key in info and not _bounded_string(info[key]):
            return False
    for key in ("utilization", "surpassedThreshold"):
        if key in info and not _unit_interval_number(info[key]):
            return False
    if "unifiedWindows" in info and not _strict_unified_windows_is_valid(
        info["unifiedWindows"]
    ):
        return False
    return True


def _strict_unified_windows_is_valid(value: object) -> bool:
    """Admit only Claude's current two-window, scalar telemetry shape."""

    if not isinstance(value, dict) or set(value) != {"five_hour", "seven_day"}:
        return False
    for window in value.values():
        if not isinstance(window, dict) or set(window) != {
            "utilization",
            "resetsAt",
        }:
            return False
        if not _unit_interval_number(window.get("utilization")):
            return False
        if not _bounded_nonnegative_int(window.get("resetsAt"), maximum=10**15):
            return False
    return True


def _strict_thinking_telemetry_is_valid(raw: dict[str, Any]) -> bool:
    if set(raw) != {
        "type",
        "subtype",
        "estimated_tokens",
        "estimated_tokens_delta",
        "session_id",
        "uuid",
    }:
        return False
    return (
        _bounded_string(raw.get("session_id"))
        and _bounded_string(raw.get("uuid"))
        and _bounded_nonnegative_int(raw.get("estimated_tokens"), maximum=10**8)
        and _bounded_nonnegative_int(raw.get("estimated_tokens_delta"), maximum=10**8)
    )


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
        if not isinstance(tools, list) or not all(
            isinstance(item, str) for item in tools
        ):
            return False
        for key in ("cwd", "permissionMode", "permission_mode", "claude_code_version"):
            if key in raw and not isinstance(raw[key], str):
                return False
        return isinstance(raw.get("mcp_servers", []), list)
    if event_type == "assistant":
        message = raw.get("message")
        if not isinstance(message, dict) or not _bounded_string(raw.get("session_id")):
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
    if not _bounded_string(raw.get("session_id")):
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
    if not isinstance(errors, list) or not all(
        isinstance(item, str) for item in errors
    ):
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


def _bounded_string(value: object, *, maximum: int = 256) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum


def _bounded_nonnegative_int(value: object, *, maximum: int) -> bool:
    return _nonnegative_int(value) and int(value) <= maximum


def _unit_interval_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(number) and 0.0 <= number <= 1.0


__all__ = [
    "STRICT_ACCEPT",
    "STRICT_DROP_TELEMETRY",
    "STRICT_PREVIEW_MAX_BYTES",
    "STRICT_PREVIEW_MAX_FRAMES",
    "STRICT_REJECT",
    "strict_preview_event_is_valid",
    "strict_preview_raw_event_disposition",
    "unique_json_object",
]
