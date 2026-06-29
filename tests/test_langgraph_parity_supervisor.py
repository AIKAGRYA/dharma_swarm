from __future__ import annotations

import pytest

from dharma_swarm.langgraph_parity.state import ParityMessage, is_routing_message
from dharma_swarm.langgraph_parity.supervisor_runtime import (
    DeterministicSubagent,
    DeterministicSupervisorRuntime,
)


def test_supervisor_delegates_to_two_agents_and_is_only_visible_final_author() -> None:
    calls: list[str] = []

    def first(messages: list[ParityMessage]) -> str:
        calls.append("researcher")
        assert messages[0].role == "user"
        return "research complete"

    def second(messages: list[ParityMessage]) -> str:
        calls.append("verifier")
        assert any(message.name == "researcher" for message in messages)
        return "verification complete"

    runtime = DeterministicSupervisorRuntime(
        [
            DeterministicSubagent("researcher", first),
            DeterministicSubagent("verifier", second),
        ],
        finalizer=lambda state: "supervisor synthesis",
    )

    result = runtime.invoke("inspect the build")

    assert calls == ["researcher", "verifier"]
    assert result.delegated_agents == ("researcher", "verifier")
    assert result.final_message == ParityMessage(
        role="assistant",
        content="supervisor synthesis",
        name="supervisor",
    )
    assert result.user_visible_messages == (result.final_message,)
    assert all(
        message.name == "supervisor"
        for message in result.user_visible_messages
        if message.role == "assistant"
    )


def test_forward_message_preserves_subagent_response_text_exactly() -> None:
    exact = "Line 1\nLine 2: keep punctuation, spacing, and casing."
    runtime = DeterministicSupervisorRuntime(
        [
            DeterministicSubagent("researcher", lambda _messages: exact),
            DeterministicSubagent("verifier", lambda _messages: "separate verifier note"),
        ],
        add_handoff_messages=False,
    )

    result = runtime.invoke("return the researcher answer", forward_from="researcher")

    assert result.output == exact
    assert result.final_message.name == "supervisor"
    assert result.final_message.metadata == {"forwarded_from": "researcher"}
    assert result.user_visible_messages == (result.final_message,)


def test_add_handoff_messages_false_hides_routing_clutter_from_subagent_state() -> None:
    seen: dict[str, list[ParityMessage]] = {}

    def capture(agent_name: str):
        def _handler(messages: list[ParityMessage]) -> str:
            seen[agent_name] = list(messages)
            return f"{agent_name} done"

        return _handler

    runtime = DeterministicSupervisorRuntime(
        [
            DeterministicSubagent("researcher", capture("researcher")),
            DeterministicSubagent("verifier", capture("verifier")),
        ],
        add_handoff_messages=False,
    )

    result = runtime.invoke("hide handoff tool chatter")

    assert not any(is_routing_message(message) for message in seen["researcher"])
    assert not any(is_routing_message(message) for message in seen["verifier"])
    assert not any("transferred" in message.content for message in seen["verifier"])
    assert not any(is_routing_message(message) for message in result.state.messages)


def test_output_mode_last_message_keeps_concise_agent_outputs() -> None:
    def multi(agent_name: str):
        return lambda _messages: [
            ParityMessage(role="assistant", content=f"{agent_name} draft"),
            ParityMessage(role="assistant", content=f"{agent_name} final"),
        ]

    runtime = DeterministicSupervisorRuntime(
        [
            DeterministicSubagent("researcher", multi("researcher")),
            DeterministicSubagent("verifier", multi("verifier")),
        ],
        add_handoff_messages=False,
        output_mode="last_message",
    )

    result = runtime.invoke("keep only last subagent messages")
    contents = [message.content for message in result.state.messages]

    assert "researcher draft" not in contents
    assert "verifier draft" not in contents
    assert "researcher final" in contents
    assert "verifier final" in contents


def test_output_mode_full_history_keeps_all_agent_outputs() -> None:
    def multi(agent_name: str):
        return lambda _messages: [
            ParityMessage(role="assistant", content=f"{agent_name} draft"),
            ParityMessage(role="assistant", content=f"{agent_name} final"),
        ]

    runtime = DeterministicSupervisorRuntime(
        [
            DeterministicSubagent("researcher", multi("researcher")),
            DeterministicSubagent("verifier", multi("verifier")),
        ],
        add_handoff_messages=False,
        output_mode="full_history",
    )

    result = runtime.invoke("keep every subagent message")
    contents = [message.content for message in result.state.messages]

    assert "researcher draft" in contents
    assert "researcher final" in contents
    assert "verifier draft" in contents
    assert "verifier final" in contents


def test_supervisor_runtime_requires_two_subagents() -> None:
    with pytest.raises(ValueError, match="at least two subagents"):
        DeterministicSupervisorRuntime(
            [DeterministicSubagent("researcher", lambda _messages: "done")]
        )
