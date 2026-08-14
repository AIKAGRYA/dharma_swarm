"""Request validation and resource bounds for sealed Grok OAuth calls."""

from __future__ import annotations

import math
from typing import Any

MAX_OUTPUT_TOKENS = 4096
DEFAULT_OUTPUT_TOKENS = 1024


class InvalidValue:
    """Sentinel for an explicitly invalid optional request value."""


INVALID = InvalidValue()


def normalize_messages(messages: Any) -> list[dict[str, str]] | None:
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


def optional_instructions(value: Any) -> str | None | InvalidValue:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return INVALID
    return value


def bounded_output_tokens(value: Any) -> int | None:
    if value is None:
        return DEFAULT_OUTPUT_TOKENS
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return min(value, MAX_OUTPUT_TOKENS)


def request_timeout(value: Any) -> float:
    try:
        timeout = float(value) if value is not None else 120.0
    except (TypeError, ValueError):
        return 120.0
    if not math.isfinite(timeout):
        return 120.0
    return min(max(timeout, 1.0), 300.0)


__all__ = [
    "DEFAULT_OUTPUT_TOKENS",
    "INVALID",
    "MAX_OUTPUT_TOKENS",
    "InvalidValue",
    "bounded_output_tokens",
    "normalize_messages",
    "optional_instructions",
    "request_timeout",
]
