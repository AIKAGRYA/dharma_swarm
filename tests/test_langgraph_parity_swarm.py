from __future__ import annotations

import json

from dharma_swarm.langgraph_parity.swarm_runtime import (
    AgentContext,
    DeterministicSwarmRuntime,
)
from dharma_swarm.langgraph_parity.tools import transfer_tool_name


def _agents():
    def responder(context: AgentContext) -> str:
        return f"{context.agent_name} handled {context.user_input}"

    return {
        "agent_a": responder,
        "agent_b": responder,
        "agent_c": responder,
    }


def _runtime(tmp_path):
    return DeterministicSwarmRuntime(
        _agents(),
        checkpoint_path=tmp_path / "swarm_checkpoint.json",
        default_agent="agent_a",
        allowed_handoffs={
            "agent_a": ("agent_b",),
            "agent_b": ("agent_a",),
            "agent_c": (),
        },
    )


def test_default_active_agent_is_persisted_with_allowed_tools(tmp_path):
    runtime = _runtime(tmp_path)

    assert runtime.active_agent == "agent_a"
    assert runtime.visible_tools() == ("transfer_to_agent_b",)

    checkpoint = json.loads((tmp_path / "swarm_checkpoint.json").read_text())
    assert checkpoint["active_agent"] == "agent_a"
    assert checkpoint["default_agent"] == "agent_a"


def test_transfer_resumes_target_agent_on_next_turn(tmp_path):
    runtime = _runtime(tmp_path)

    handoff = runtime.invoke(
        "please hand off",
        tool_call=transfer_tool_name("agent_b"),
    )
    assert handoff.receipt is not None
    assert handoff.receipt.status == "accepted"
    assert handoff.active_agent_before == "agent_a"
    assert handoff.active_agent_after == "agent_b"

    direct = runtime.invoke("continue")
    assert direct.responding_agent == "agent_b"
    assert direct.content == "agent_b handled continue"
    assert direct.active_agent_before == "agent_b"
    assert direct.active_agent_after == "agent_b"


def test_active_subagent_can_transfer_back_to_original_agent(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.invoke("move to b", tool_call="transfer_to_agent_b")

    back = runtime.invoke("return", tool_call="transfer_to_agent_a")
    assert back.receipt is not None
    assert back.receipt.status == "accepted"
    assert back.active_agent_before == "agent_b"
    assert back.active_agent_after == "agent_a"

    direct = runtime.invoke("again")
    assert direct.responding_agent == "agent_a"
    assert direct.content == "agent_a handled again"


def test_invalid_transfer_is_rejected_with_receipt_and_no_state_change(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.invoke("bad transfer", tool_call="transfer_to_agent_c")

    assert result.receipt is not None
    assert result.receipt.status == "rejected"
    assert result.receipt.requested_agent == "agent_c"
    assert "not visible" in result.receipt.reason
    assert result.active_agent_before == "agent_a"
    assert result.active_agent_after == "agent_a"
    assert runtime.active_agent == "agent_a"
    assert runtime.state.receipts[-1] == result.receipt


def test_handoff_tool_visibility_is_scoped_per_active_agent(tmp_path):
    runtime = _runtime(tmp_path)
    assert runtime.visible_tools("agent_a") == ("transfer_to_agent_b",)
    assert runtime.visible_tools("agent_b") == ("transfer_to_agent_a",)
    assert runtime.visible_tools("agent_c") == ()

    runtime.invoke("move to b", tool_call="transfer_to_agent_b")
    assert runtime.visible_tools() == ("transfer_to_agent_a",)


def test_checkpoint_load_survives_runtime_restart(tmp_path):
    checkpoint_path = tmp_path / "swarm_checkpoint.json"
    policy = {
        "agent_a": ("agent_b",),
        "agent_b": ("agent_a",),
        "agent_c": (),
    }
    first_runtime = DeterministicSwarmRuntime(
        _agents(),
        checkpoint_path=checkpoint_path,
        default_agent="agent_a",
        allowed_handoffs=policy,
    )
    first_runtime.invoke("move to b", tool_call="transfer_to_agent_b")
    assert first_runtime.active_agent == "agent_b"

    restarted_runtime = DeterministicSwarmRuntime.load(
        _agents(),
        checkpoint_path=checkpoint_path,
        default_agent="agent_a",
        allowed_handoffs=policy,
    )

    assert restarted_runtime.active_agent == "agent_b"
    result = restarted_runtime.invoke("after restart")
    assert result.responding_agent == "agent_b"
    assert result.content == "agent_b handled after restart"
