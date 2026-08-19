"""Fail-closed Grok response schema and no-tools validation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

ALLOWED_OUTPUT_ITEM_TYPES = frozenset({"reasoning", "message"})
_TOOL_TYPE_MARKERS = (
    "tool_call",
    "tool_use",
    "function_call",
    "web_search",
    "file_search",
    "computer_use",
    "computer_call",
    "local_shell",
    "shell_call",
    "mcp",
    "mcp_call",
    "code_interpreter",
    "code_interpreter_call",
    "image_generation",
    "image_generation_call",
)
_TOOL_KEY_MARKERS = (
    "tool",
    "function_call",
    "web_search",
    "file_search",
    "computer_use",
    "computer_call",
    "local_shell",
    "shell_call",
    "mcp",
    "code_interpreter",
    "image_generation",
)
_EXPLICIT_TOOL_FIELDS = frozenset(
    {
        "function_call",
        "function_calls",
        "server_tool_use",
        "server_tool_use_details",
        "tool_call",
        "tool_calls",
        "tool_use",
        "tool_uses",
        "web_search_calls",
    }
)


@dataclass(frozen=True, slots=True)
class ValidatedGrokCompletion:
    """Provider data safe to project into canonical events."""

    served_model: str
    content: str
    usage: dict[str, int]
    input_tokens: int
    output_tokens: int
    thinking_tokens: int


def validate_final_response(
    response: dict[str, Any],
    *,
    expected_served_model: str,
) -> tuple[ValidatedGrokCompletion | None, tuple[str, str] | None]:
    malformed = malformed_response()
    if contains_error_signal(response):
        return None, (
            "provider_response_error",
            "Grok OAuth returned a provider error",
        )
    if contains_tool_activity(response):
        return None, tool_rejection()
    if response.get("status") != "completed":
        return None, malformed
    served_model = response.get("model")
    if served_model != expected_served_model:
        return None, (
            "served_identity_mismatch",
            "Grok OAuth served identity did not match the accepted proxy identity",
        )
    tools = response.get("tools")
    if tools not in (None, []):
        return None, tool_rejection()
    if response.get("parallel_tool_calls") not in (None, False):
        return None, tool_rejection()
    if response.get("store") not in (None, False):
        return None, malformed
    if is_present(response.get("incomplete_details")):
        return None, (
            "provider_response_error",
            "Grok OAuth returned an incomplete response",
        )

    output = response.get("output")
    if not isinstance(output, list) or not output:
        return None, malformed
    message_texts: list[str] = []
    message_count = 0
    for item in output:
        if not isinstance(item, dict):
            return None, malformed
        item_type = item.get("type")
        if item_type not in ALLOWED_OUTPUT_ITEM_TYPES:
            if tool_type(item_type):
                return None, tool_rejection()
            return None, malformed
        if item_type == "reasoning":
            summary = item.get("summary", [])
            if not isinstance(summary, list):
                return None, malformed
            for part in summary:
                if (
                    not isinstance(part, dict)
                    or part.get("type") != "summary_text"
                    or not isinstance(part.get("text"), str)
                ):
                    return None, malformed
            continue

        message_count += 1
        if item.get("role") != "assistant":
            return None, malformed
        if item.get("status") not in (None, "completed"):
            return None, malformed
        content = item.get("content")
        if not isinstance(content, list) or not content:
            return None, malformed
        for part in content:
            if not isinstance(part, dict):
                return None, malformed
            part_type = part.get("type")
            if part_type != "output_text":
                if tool_type(part_type):
                    return None, tool_rejection()
                return None, malformed
            text = part.get("text")
            if not isinstance(text, str):
                return None, malformed
            annotations = part.get("annotations", [])
            if not isinstance(annotations, list) or annotations:
                return None, malformed
            message_texts.append(text)

    if message_count != 1:
        return None, malformed
    content = "".join(message_texts)
    if not content.strip():
        return None, (
            "empty_response",
            "Grok OAuth response contained no assistant text",
        )

    usage, usage_rejection = validated_usage(response.get("usage"))
    if usage_rejection is not None:
        return None, usage_rejection
    assert usage is not None
    return (
        ValidatedGrokCompletion(
            served_model=served_model,
            content=content,
            usage=usage,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            thinking_tokens=usage.get("reasoning_tokens", 0),
        ),
        None,
    )


def validated_usage(
    raw_usage: Any,
) -> tuple[dict[str, int] | None, tuple[str, str] | None]:
    malformed = malformed_response()
    if raw_usage is None:
        return {}, None
    if not isinstance(raw_usage, dict):
        return None, malformed
    if contains_tool_activity(raw_usage):
        return None, tool_rejection()

    usage: dict[str, int] = {}
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        if field not in raw_usage:
            continue
        count = token_count(raw_usage[field])
        if count is None:
            return None, malformed
        usage[field] = count

    input_details = raw_usage.get("input_tokens_details", {})
    if input_details is None:
        input_details = {}
    if not isinstance(input_details, dict):
        return None, malformed
    if "cached_tokens" in input_details:
        cached = token_count(input_details["cached_tokens"])
        if cached is None:
            return None, malformed
        usage["cached_tokens"] = cached

    output_details = raw_usage.get("output_tokens_details", {})
    if output_details is None:
        output_details = {}
    if not isinstance(output_details, dict):
        return None, malformed
    if "reasoning_tokens" in output_details:
        reasoning = token_count(output_details["reasoning_tokens"])
        if reasoning is None:
            return None, malformed
        usage["reasoning_tokens"] = reasoning

    if "num_server_side_tools_used" in raw_usage:
        count = token_count(raw_usage["num_server_side_tools_used"])
        if count is None:
            return None, malformed
        if count:
            return None, tool_rejection()
        usage["num_server_side_tools_used"] = 0
    return usage, None


def contains_error_signal(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "error" and is_present(item):
                return True
            if contains_error_signal(item):
                return True
    elif isinstance(value, list):
        return any(contains_error_signal(item) for item in value)
    return False


def contains_tool_activity(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = normalize_wire_name(key)
            if normalized_key == "tools":
                if item not in (None, []):
                    return True
                continue
            if normalized_key == "parallel_tool_calls":
                if item not in (None, False):
                    return True
                continue
            if normalized_key == "tool_choice":
                # The proxy may report ``auto`` even when tools is empty.
                if item not in (None, "auto", "none"):
                    return True
                continue
            if normalized_key == "num_server_side_tools_used":
                if item not in (None, 0):
                    return True
                continue
            if normalized_key in _EXPLICIT_TOOL_FIELDS and is_present(item):
                return True
            if structural_tool_key(normalized_key) and is_present(item):
                return True
            if normalized_key in {
                "event",
                "finish_reason",
                "kind",
                "native_finish_reason",
                "object",
                "stop_reason",
                "type",
            } and tool_type(item):
                return True
            if contains_tool_activity(item):
                return True
    elif isinstance(value, list):
        return any(contains_tool_activity(item) for item in value)
    return False


def tool_type(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = normalize_wire_name(value)
    return any(marker in normalized for marker in _TOOL_TYPE_MARKERS)


def normalize_wire_name(value: str) -> str:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value.strip())
    return separated.lower().replace("-", "_").replace(".", "_")


def structural_tool_key(normalized_key: str) -> bool:
    return (
        normalized_key in {"call", "calls"}
        or normalized_key.endswith(("_call", "_calls"))
        or any(marker in normalized_key for marker in _TOOL_KEY_MARKERS)
    )


def is_present(value: Any) -> bool:
    return value is not None and value != "" and value != {} and value != []


def token_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def malformed_response() -> tuple[str, str]:
    return (
        "malformed_response",
        "Grok OAuth response did not match the expected schema",
    )


def tool_rejection() -> tuple[str, str]:
    return (
        "provider_tool_use_rejected",
        "Grok OAuth response contained tool activity",
    )


__all__ = [
    "ALLOWED_OUTPUT_ITEM_TYPES",
    "ValidatedGrokCompletion",
    "contains_error_signal",
    "contains_tool_activity",
    "is_present",
    "malformed_response",
    "normalize_wire_name",
    "structural_tool_key",
    "token_count",
    "tool_rejection",
    "tool_type",
    "validate_final_response",
    "validated_usage",
]
