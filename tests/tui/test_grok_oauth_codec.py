"""Focused tests for Grok OAuth SSE validation."""

from __future__ import annotations

import pytest

from dharma_swarm.tui.engine.adapters import grok_oauth_codec
from tests.tui.test_grok_oauth_adapter import (
    SERVED_MODEL,
    _sse,
    _success_events,
)


@pytest.mark.parametrize(
    "raw",
    [
        {"finish_reason": "tool_calls"},
        {"native_finish_reason": "function_call"},
        {"stop_reason": "tool_use"},
        {"object": "response.tool_call"},
        {"kind": "computer_call"},
        {"event": "mcp_call"},
    ],
)
def test_grok_nested_discriminator_tool_evidence_is_rejected(raw: dict) -> None:
    assert grok_oauth_codec._contains_tool_activity(raw) is True


@pytest.mark.parametrize(
    "raw",
    [
        {"functionCall": {"name": "shell"}},
        {"computerUse": {"action": "click"}},
        {"webSearchCall": {"query": "secret"}},
        {"type": "functionCall"},
        {"finishReason": "toolCalls"},
    ],
)
def test_grok_camel_case_structural_tool_evidence_is_rejected(raw: dict) -> None:
    events = _success_events()
    events[-2][1]["response"]["provider_details"] = {"nested": raw}

    validated, rejection = grok_oauth_codec.validate_sse_completion(
        _sse(events),
        expected_served_model=SERVED_MODEL,
    )

    assert validated is None
    assert rejection is not None
    assert rejection[0] == "provider_tool_use_rejected"


@pytest.mark.parametrize(
    "event_name",
    ["response.tool_call", "response.failed", "future.tool_use"],
)
def test_grok_event_only_sse_blocks_fail_closed(event_name: str) -> None:
    body = f"event: {event_name}\n\n".encode() + _sse(_success_events())

    validated, rejection = grok_oauth_codec.validate_sse_completion(
        body,
        expected_served_model=SERVED_MODEL,
    )

    assert validated is None
    assert rejection is not None and rejection[0] == "malformed_sse"


@pytest.mark.parametrize("event_index", [0, 1])
def test_grok_lifecycle_model_claims_must_match_final_identity(
    event_index: int,
) -> None:
    events = _success_events()
    event_name, payload = events[event_index]
    payload["response"]["model"] = "conflicting-model"
    events[event_index] = (event_name, payload)

    validated, rejection = grok_oauth_codec.validate_sse_completion(
        _sse(events),
        expected_served_model=SERVED_MODEL,
    )

    assert validated is None
    assert rejection is not None and rejection[0] == "malformed_sse"


def test_grok_oauth_does_not_scan_assistant_narration_for_tool_words() -> None:
    narration = (
        "computer_use call mcp code_interpreter_call image_generation_call shell_call"
    )
    validated, rejection = grok_oauth_codec.validate_sse_completion(
        _sse(_success_events(content=narration)),
        expected_served_model=SERVED_MODEL,
    )

    assert rejection is None
    assert validated is not None and validated.content == narration
