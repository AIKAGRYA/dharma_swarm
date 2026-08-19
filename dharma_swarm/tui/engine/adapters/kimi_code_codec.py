"""Strict request and response validation for the sealed Kimi Code lane."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_FORBIDDEN_FINISH_REASONS = frozenset(
    {"function_call", "tool_call", "tool_calls", "tool_use"}
)
_STRUCTURAL_TOOL_DISCRIMINATORS = frozenset(
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
_TOOL_MARKER_FAMILIES = (
    "code_interpreter",
    "computer",
    "function_call",
    "file_search",
    "image_generation",
    "mcp",
    "shell",
    "tool",
    "web_search",
)
_USAGE_TOKEN_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cached_tokens",
)


@dataclass(frozen=True, slots=True)
class ValidatedCompletion:
    """Trusted response fields admitted after the full body is validated."""

    model: str
    content: str
    usage: dict[str, Any]
    input_tokens: int
    output_tokens: int


def validate_completion(
    data: Any,
    *,
    expected_model: str,
) -> tuple[ValidatedCompletion | None, tuple[str, str] | None]:
    """Validate one non-streamed completion without leaking rejected content."""

    malformed = "Kimi Code response did not match the expected schema"
    if not isinstance(data, dict):
        return None, ("malformed_response", malformed)
    if _is_present(data.get("error")):
        return None, (
            "provider_response_error",
            "Kimi Code returned an embedded provider error",
        )
    if has_tool_signal(data, exclude=frozenset({"choices", "usage"})):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response contained tool activity",
        )

    served_model = data.get("model")
    if not isinstance(served_model, str) or served_model != expected_model:
        return None, (
            "served_identity_mismatch",
            "Kimi Code served identity did not match the requested model",
        )

    choices = data.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
    ):
        return None, ("malformed_response", malformed)
    choice = choices[0]
    if _is_present(choice.get("error")):
        return None, (
            "provider_response_error",
            "Kimi Code returned an embedded provider error",
        )
    if has_tool_signal(choice, exclude=frozenset({"message"})):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response contained tool activity",
        )

    finish_reasons = {
        str(choice.get(field, "")).strip().lower()
        for field in ("finish_reason", "native_finish_reason")
    }
    if finish_reasons & _FORBIDDEN_FINISH_REASONS:
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response finished for tool activity",
        )
    if "error" in finish_reasons:
        return None, (
            "provider_response_error",
            "Kimi Code response finished with an error",
        )

    message = choice.get("message")
    if not isinstance(message, dict):
        return None, ("malformed_response", malformed)
    if _is_present(message.get("error")):
        return None, (
            "provider_response_error",
            "Kimi Code returned an embedded provider error",
        )
    if has_tool_signal(message):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code response contained tool activity",
        )
    role = message.get("role")
    if role not in (None, "assistant"):
        return None, ("malformed_response", malformed)
    content = message.get("content")
    if not isinstance(content, str):
        return None, ("malformed_response", malformed)
    if not content.strip():
        return None, (
            "empty_response",
            "Kimi Code response contained no assistant content",
        )

    raw_usage = data.get("usage", {})
    if raw_usage is None:
        raw_usage = {}
    if not isinstance(raw_usage, dict):
        return None, ("malformed_response", malformed)
    if has_tool_signal(raw_usage):
        return None, (
            "provider_tool_use_rejected",
            "Kimi Code usage reported tool activity",
        )
    usage: dict[str, Any] = {}
    for field in _USAGE_TOKEN_FIELDS:
        if field not in raw_usage:
            continue
        count = _token_count(raw_usage[field])
        if count is None:
            return None, ("malformed_response", malformed)
        usage[field] = count

    return (
        ValidatedCompletion(
            model=served_model,
            content=content,
            usage=dict(usage),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        ),
        None,
    )


def has_tool_signal(
    value: Any,
    *,
    exclude: frozenset[str] = frozenset(),
) -> bool:
    """Fail closed on recursive structural evidence of provider tool use."""

    pending: list[tuple[Any, bool]] = [(value, True)]
    seen = 0
    while pending:
        current, is_root = pending.pop()
        seen += 1
        if seen > 4096:
            return True
        if isinstance(current, dict):
            for raw_key, item in current.items():
                key = _normalize_structural_label(raw_key)
                if not (is_root and key in exclude):
                    if key == "tool_choice":
                        if item is not None and item != "none":
                            return True
                    elif key == "parallel_tool_calls":
                        if item not in (None, False):
                            return True
                    elif key == "num_server_side_tools_used":
                        if item not in (None, 0):
                            return True
                    elif _has_structural_tool_marker(key) and _is_present(item):
                        return True
                    if (
                        key in _STRUCTURAL_TOOL_DISCRIMINATORS
                        and _has_structural_tool_marker(item)
                    ):
                        return True
                if isinstance(item, (dict, list)):
                    pending.append((item, False))
        elif isinstance(current, list):
            pending.extend((item, False) for item in current)
    return False


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys instead of accepting last-write-wins data."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate provider JSON key")
        result[key] = value
    return result


def optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def request_messages(
    messages: Any,
    system_prompt: Any,
) -> list[dict[str, str]] | None:
    """Normalize the exact text-only request shape admitted by this lane."""

    if not isinstance(messages, list):
        return None
    normalized: list[dict[str, str]] = []
    if system_prompt is not None:
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            return None
        normalized.append({"role": "system", "content": system_prompt})
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


def _normalize_structural_label(value: Any) -> str:
    label = str(value or "").strip()
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", label)
    label = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", label)
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _has_structural_tool_marker(value: Any) -> bool:
    # Only field names and explicit discriminator strings reach this helper.
    # Ordinary response narration is never interpreted as structural evidence.
    if not isinstance(value, str):
        return False
    normalized = _normalize_structural_label(value)
    padded = f"_{normalized}_"
    return any(
        f"_{marker}_" in padded or f"_{marker}s_" in padded
        for marker in _TOOL_MARKER_FAMILIES
    )


def _is_present(value: Any) -> bool:
    return value is not None and value != "" and value != {} and value != []


def _token_count(value: Any) -> int | None:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


__all__ = [
    "ValidatedCompletion",
    "has_tool_signal",
    "optional_positive_int",
    "request_messages",
    "unique_json_object",
    "validate_completion",
]
