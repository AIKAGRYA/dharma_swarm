"""Buffered, fail-closed codec for the Grok OAuth Responses SSE wire format."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

_ALLOWED_SSE_EVENTS = frozenset(
    {
        "response.queued",
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.output_item.done",
        "response.content_part.added",
        "response.content_part.done",
        "response.output_text.delta",
        "response.output_text.done",
        "response.reasoning_summary_part.added",
        "response.reasoning_summary_part.done",
        "response.reasoning_summary_text.delta",
        "response.reasoning_summary_text.done",
        "response.reasoning_text.delta",
        "response.reasoning_text.done",
        "response.completed",
    }
)
_PROVIDER_ERROR_EVENTS = frozenset(
    {"error", "response.error", "response.failed", "response.incomplete"}
)
_ALLOWED_OUTPUT_ITEM_TYPES = frozenset({"reasoning", "message"})
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
class _SSEFrame:
    event_type: str | None
    data: dict[str, Any] | None
    done: bool = False


@dataclass(frozen=True, slots=True)
class ValidatedGrokCompletion:
    """Provider data safe to project into canonical events."""

    served_model: str
    content: str
    usage: dict[str, int]
    input_tokens: int
    output_tokens: int
    thinking_tokens: int


def validate_sse_completion(
    body: bytes,
    *,
    expected_served_model: str,
) -> tuple[ValidatedGrokCompletion | None, tuple[str, str] | None]:
    """Validate the complete SSE transcript without exposing provider content."""

    frames, parse_rejection = _parse_sse(body)
    if parse_rejection is not None:
        return None, parse_rejection
    assert frames is not None

    created_count = 0
    completed_count = 0
    completed_index = -1
    done_index: int | None = None
    final_response: dict[str, Any] | None = None
    response_id: str | None = None
    response_models: list[str] = []
    output_deltas: list[str] = []
    output_done_text: list[str] = []
    seen_sequence_numbers: list[int] = []

    for index, frame in enumerate(frames):
        if frame.done:
            if done_index is not None:
                return None, _malformed_sse()
            done_index = index
            continue
        event_type = frame.event_type
        data = frame.data
        if event_type is None or data is None:
            return None, _malformed_sse()
        if event_type in _PROVIDER_ERROR_EVENTS or _contains_error_signal(data):
            return None, (
                "provider_response_error",
                "Grok OAuth returned a provider error",
            )
        if event_type not in _ALLOWED_SSE_EVENTS:
            if _tool_type(event_type) or _contains_tool_activity(data):
                return None, _tool_rejection()
            return None, _malformed_sse()
        if _contains_tool_activity(data):
            return None, _tool_rejection()

        claimed_response_id = data.get("response_id")
        if claimed_response_id is not None:
            matched_id = _consistent_identifier(claimed_response_id, response_id)
            if matched_id is None:
                return None, _malformed_sse()
            response_id = matched_id

        sequence_number = data.get("sequence_number")
        if sequence_number is not None:
            count = _token_count(sequence_number)
            if count is None:
                return None, _malformed_sse()
            seen_sequence_numbers.append(count)

        if event_type == "response.created":
            created_count += 1
            response_value = data.get("response")
            if not isinstance(response_value, dict):
                return None, _malformed_sse()
            matched_id = _consistent_identifier(response_value.get("id"), response_id)
            if matched_id is None:
                return None, _malformed_sse()
            response_id = matched_id
            model_claim = response_value.get("model")
            if model_claim is not None:
                if not isinstance(model_claim, str) or not model_claim:
                    return None, _malformed_sse()
                response_models.append(model_claim)
        elif event_type in {"response.queued", "response.in_progress"}:
            response_value = data.get("response")
            if not isinstance(response_value, dict):
                return None, _malformed_sse()
            matched_id = _consistent_identifier(response_value.get("id"), response_id)
            if matched_id is None:
                return None, _malformed_sse()
            response_id = matched_id
            model_claim = response_value.get("model")
            if model_claim is not None:
                if not isinstance(model_claim, str) or not model_claim:
                    return None, _malformed_sse()
                response_models.append(model_claim)
        elif event_type in {
            "response.output_item.added",
            "response.output_item.done",
        }:
            item = data.get("item")
            if not isinstance(item, dict):
                return None, _malformed_sse()
            item_type = item.get("type")
            if item_type not in _ALLOWED_OUTPUT_ITEM_TYPES:
                if _tool_type(item_type):
                    return None, _tool_rejection()
                return None, _malformed_sse()
        elif event_type in {
            "response.content_part.added",
            "response.content_part.done",
        }:
            part = data.get("part")
            if not isinstance(part, dict) or part.get("type") != "output_text":
                if isinstance(part, dict) and _tool_type(part.get("type")):
                    return None, _tool_rejection()
                return None, _malformed_sse()
        elif event_type in {
            "response.reasoning_summary_part.added",
            "response.reasoning_summary_part.done",
        }:
            part = data.get("part")
            if not isinstance(part, dict) or part.get("type") != "summary_text":
                return None, _malformed_sse()
        elif event_type == "response.output_text.delta":
            delta = data.get("delta")
            if not isinstance(delta, str):
                return None, _malformed_sse()
            output_deltas.append(delta)
        elif event_type == "response.output_text.done":
            text = data.get("text")
            if not isinstance(text, str):
                return None, _malformed_sse()
            output_done_text.append(text)
        elif event_type in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_text.delta",
        }:
            if not isinstance(data.get("delta"), str):
                return None, _malformed_sse()
        elif event_type in {
            "response.reasoning_summary_text.done",
            "response.reasoning_text.done",
        }:
            if not isinstance(data.get("text"), str):
                return None, _malformed_sse()
        elif event_type == "response.completed":
            completed_count += 1
            completed_index = index
            response_value = data.get("response")
            if not isinstance(response_value, dict):
                return None, _malformed_sse()
            matched_id = _consistent_identifier(response_value.get("id"), response_id)
            if matched_id is None:
                return None, _malformed_sse()
            response_id = matched_id
            model_claim = response_value.get("model")
            if not isinstance(model_claim, str) or not model_claim:
                return None, _malformed_sse()
            response_models.append(model_claim)
            final_response = response_value

    if (
        created_count != 1
        or completed_count != 1
        or final_response is None
        or response_id is None
        or completed_index < 0
    ):
        return None, _malformed_sse()
    if done_index is not None and done_index != len(frames) - 1:
        return None, _malformed_sse()
    last_data_index = done_index - 1 if done_index is not None else len(frames) - 1
    if completed_index != last_data_index:
        return None, _malformed_sse()
    if seen_sequence_numbers and any(
        later <= earlier
        for earlier, later in zip(
            seen_sequence_numbers,
            seen_sequence_numbers[1:],
        )
    ):
        return None, _malformed_sse()

    validated, response_rejection = _validate_final_response(
        final_response,
        expected_served_model=expected_served_model,
    )
    if response_rejection is not None:
        return None, response_rejection
    assert validated is not None
    if any(model != validated.served_model for model in response_models):
        return None, _malformed_sse()
    if output_deltas and "".join(output_deltas) != validated.content:
        return None, _malformed_sse()
    if output_done_text and "".join(output_done_text) != validated.content:
        return None, _malformed_sse()
    return validated, None


def _parse_sse(
    body: bytes,
) -> tuple[list[_SSEFrame] | None, tuple[str, str] | None]:
    if not body:
        return None, _malformed_sse()
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None, _malformed_sse()
    if text.startswith("\ufeff") or "\x00" in text:
        return None, _malformed_sse()

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    frames: list[_SSEFrame] = []
    for block in normalized.split("\n\n"):
        if not block.strip():
            continue
        event_name: str | None = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            field, separator, value = line.partition(":")
            if separator and value.startswith(" "):
                value = value[1:]
            if field == "event":
                if event_name is not None or not value:
                    return None, _malformed_sse()
                event_name = value
            elif field == "data":
                data_lines.append(value)
            elif field == "id":
                if "\x00" in value:
                    return None, _malformed_sse()
            elif field == "retry":
                if not value.isdigit():
                    return None, _malformed_sse()
            else:
                return None, _malformed_sse()
        if not data_lines:
            if event_name is not None:
                return None, _malformed_sse()
            continue
        data_text = "\n".join(data_lines)
        if data_text == "[DONE]":
            if event_name not in (None, "done"):
                return None, _malformed_sse()
            frames.append(_SSEFrame(event_type=None, data=None, done=True))
            continue
        try:
            data = json.loads(data_text, object_pairs_hook=_unique_json_object)
        except (TypeError, ValueError):
            return None, _malformed_sse()
        if not isinstance(data, dict):
            return None, _malformed_sse()
        data_type = data.get("type")
        if not isinstance(data_type, str) or not data_type:
            return None, _malformed_sse()
        if event_name is not None and event_name != data_type:
            return None, _malformed_sse()
        frames.append(_SSEFrame(event_type=data_type, data=data))
    if not frames:
        return None, _malformed_sse()
    return frames, None


def _validate_final_response(
    response: dict[str, Any],
    *,
    expected_served_model: str,
) -> tuple[ValidatedGrokCompletion | None, tuple[str, str] | None]:
    malformed = (
        "malformed_response",
        "Grok OAuth response did not match the expected schema",
    )
    if _contains_error_signal(response):
        return None, (
            "provider_response_error",
            "Grok OAuth returned a provider error",
        )
    if _contains_tool_activity(response):
        return None, _tool_rejection()
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
        return None, _tool_rejection()
    if response.get("parallel_tool_calls") not in (None, False):
        return None, _tool_rejection()
    if response.get("store") not in (None, False):
        return None, malformed
    if _is_present(response.get("incomplete_details")):
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
        if item_type not in _ALLOWED_OUTPUT_ITEM_TYPES:
            if _tool_type(item_type):
                return None, _tool_rejection()
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
                if _tool_type(part_type):
                    return None, _tool_rejection()
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

    usage, usage_rejection = _validated_usage(response.get("usage"))
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


def _validated_usage(
    raw_usage: Any,
) -> tuple[dict[str, int] | None, tuple[str, str] | None]:
    malformed = (
        "malformed_response",
        "Grok OAuth response did not match the expected schema",
    )
    if raw_usage is None:
        return {}, None
    if not isinstance(raw_usage, dict):
        return None, malformed
    if _contains_tool_activity(raw_usage):
        return None, _tool_rejection()

    usage: dict[str, int] = {}
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        if field not in raw_usage:
            continue
        count = _token_count(raw_usage[field])
        if count is None:
            return None, malformed
        usage[field] = count

    input_details = raw_usage.get("input_tokens_details", {})
    if input_details is None:
        input_details = {}
    if not isinstance(input_details, dict):
        return None, malformed
    if "cached_tokens" in input_details:
        cached = _token_count(input_details["cached_tokens"])
        if cached is None:
            return None, malformed
        usage["cached_tokens"] = cached

    output_details = raw_usage.get("output_tokens_details", {})
    if output_details is None:
        output_details = {}
    if not isinstance(output_details, dict):
        return None, malformed
    if "reasoning_tokens" in output_details:
        reasoning = _token_count(output_details["reasoning_tokens"])
        if reasoning is None:
            return None, malformed
        usage["reasoning_tokens"] = reasoning

    if "num_server_side_tools_used" in raw_usage:
        count = _token_count(raw_usage["num_server_side_tools_used"])
        if count is None:
            return None, malformed
        if count:
            return None, _tool_rejection()
        usage["num_server_side_tools_used"] = 0
    return usage, None


def _contains_error_signal(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "error" and _is_present(item):
                return True
            if _contains_error_signal(item):
                return True
    elif isinstance(value, list):
        return any(_contains_error_signal(item) for item in value)
    return False


def _contains_tool_activity(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = _normalize_wire_name(key)
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
                # Authority comes from empty tools and zero server-tool use.
                if item not in (None, "auto", "none"):
                    return True
                continue
            if normalized_key == "num_server_side_tools_used":
                if item not in (None, 0):
                    return True
                continue
            if normalized_key in _EXPLICIT_TOOL_FIELDS and _is_present(item):
                return True
            if _structural_tool_key(normalized_key) and _is_present(item):
                return True
            if normalized_key in {
                "event",
                "finish_reason",
                "kind",
                "native_finish_reason",
                "object",
                "stop_reason",
                "type",
            } and _tool_type(item):
                return True
            if _contains_tool_activity(item):
                return True
    elif isinstance(value, list):
        return any(_contains_tool_activity(item) for item in value)
    return False


def _tool_type(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = _normalize_wire_name(value)
    return any(marker in normalized for marker in _TOOL_TYPE_MARKERS)


def _normalize_wire_name(value: str) -> str:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value.strip())
    return separated.lower().replace("-", "_").replace(".", "_")


def _structural_tool_key(normalized_key: str) -> bool:
    return (
        normalized_key in {"call", "calls"}
        or normalized_key.endswith(("_call", "_calls"))
        or any(marker in normalized_key for marker in _TOOL_KEY_MARKERS)
    )


def _consistent_identifier(value: Any, expected: str | None) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        return None
    if expected is not None and value != expected:
        return None
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _is_present(value: Any) -> bool:
    return value is not None and value != "" and value != {} and value != []


def _token_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _malformed_sse() -> tuple[str, str]:
    return (
        "malformed_sse",
        "Grok OAuth returned a malformed SSE transcript",
    )


def _tool_rejection() -> tuple[str, str]:
    return (
        "provider_tool_use_rejected",
        "Grok OAuth response contained tool activity",
    )


__all__ = ["ValidatedGrokCompletion", "validate_sse_completion"]
