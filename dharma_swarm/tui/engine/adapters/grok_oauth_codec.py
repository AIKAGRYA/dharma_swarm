"""Buffered, fail-closed codec for the Grok OAuth Responses SSE wire format."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .grok_oauth_response import (
    ALLOWED_OUTPUT_ITEM_TYPES as _ALLOWED_OUTPUT_ITEM_TYPES,
    ValidatedGrokCompletion,
    contains_error_signal as _contains_error_signal,
    contains_tool_activity as _contains_tool_activity,
    token_count as _token_count,
    tool_rejection as _tool_rejection,
    tool_type as _tool_type,
    validate_final_response as _validate_final_response,
)

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


@dataclass(frozen=True, slots=True)
class _SSEFrame:
    event_type: str | None
    data: dict[str, Any] | None
    done: bool = False


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


def _malformed_sse() -> tuple[str, str]:
    return (
        "malformed_sse",
        "Grok OAuth returned a malformed SSE transcript",
    )


__all__ = ["ValidatedGrokCompletion", "validate_sse_completion"]
