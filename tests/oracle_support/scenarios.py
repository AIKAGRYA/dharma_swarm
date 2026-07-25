"""Scenario inventory + dharma-arm runners for the differential oracle.

Each scenario is engine-agnostic DATA (turns, behaviors, config); the two
arms (this module's dharma runners; ``langgraph_arm`` for real langgraph)
interpret it independently and emit the same semantic-outcome schema. The
scenario inventory mirrors tests/test_langgraph_parity_swarm.py and
tests/test_langgraph_parity_supervisor.py (spec §3 Phase 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.langgraph_parity.state import ParityMessage, is_routing_message
from dharma_swarm.langgraph_parity.supervisor_runtime import (
    DeterministicSubagent,
    DeterministicSupervisorRuntime,
)
from dharma_swarm.langgraph_parity.swarm_runtime import DeterministicSwarmRuntime
from dharma_swarm.langgraph_parity.tools import visible_tool_names_for_agent

from tests.oracle_support.outcomes import ScenarioSpec

__all__ = [
    "EXACT_TEXT",
    "SUPERVISOR_SCENARIOS",
    "SWARM_DEFAULT_AGENT",
    "SWARM_POLICY",
    "SWARM_SCENARIOS",
    "SupervisorScenario",
    "SwarmScenario",
    "run_dharma_supervisor",
    "run_dharma_swarm",
]

# ---------------------------------------------------------------------------
# Shared scenario vocabulary (the CONTRACT, not an engine)
# ---------------------------------------------------------------------------

SWARM_POLICY: dict[str, tuple[str, ...]] = {
    "agent_a": ("agent_b",),
    "agent_b": ("agent_a",),
    "agent_c": (),
}
SWARM_DEFAULT_AGENT = "agent_a"

EXACT_TEXT = "Line 1\nLine 2: keep punctuation, spacing, and casing."

# The rejection-receipt deviation, adjudicated once and cited per scenario
# (documented in docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md):
_REJECTION_RECEIPT_DEVIATION = (
    "DELIBERATE DEVIATION (receipts-first doctrine): dharma records a durable"
    " rejected TransferReceipt for an unavailable/unknown handoff tool and the"
    " turn continues; real LangGraph never binds such a tool, so the call"
    " surfaces as an unbound-tool error with NO durable receipt. Final active"
    " agent is identical in both engines."
)


@dataclass(frozen=True)
class SwarmScenario:
    spec: ScenarioSpec
    turns: tuple[tuple[str, str | None], ...] = ()
    restart_turn: tuple[str, str | None] | None = None


@dataclass(frozen=True)
class SupervisorScenario:
    spec: ScenarioSpec
    agents: tuple[tuple[str, str], ...]  # (name, behavior)
    add_handoff_messages: bool = True
    output_mode: str = "last_message"
    finalizer_text: str | None = None
    forward_from: str | None = None
    user_input: str = "user request"
    distractors: tuple[str, ...] = ()  # routing-clutter contents in the input


SWARM_SCENARIOS: tuple[SwarmScenario, ...] = (
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_default_active_agent_and_visibility",
            kind="swarm",
            compare_fields=(
                "initial_active_agent",
                "per_agent_visible_tools",
                "final_active_agent",
            ),
        ),
    ),
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_accepted_handoff_then_resume",
            kind="swarm",
            compare_fields=("receipts", "turns", "final_active_agent"),
        ),
        turns=(("please hand off", "transfer_to_agent_b"), ("continue", None)),
    ),
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_transfer_back_to_original",
            kind="swarm",
            compare_fields=("receipts", "turns", "final_active_agent"),
        ),
        turns=(
            ("move to b", "transfer_to_agent_b"),
            ("return", "transfer_to_agent_a"),
            ("again", None),
        ),
    ),
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_rejected_transfer_tool_not_visible",
            kind="swarm",
            compare_fields=("final_active_agent", "receipts"),
            expected_divergences={"receipts": _REJECTION_RECEIPT_DEVIATION},
        ),
        turns=(("bad transfer", "transfer_to_agent_c"),),
    ),
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_rejected_transfer_unknown_agent",
            kind="swarm",
            compare_fields=("final_active_agent", "receipts"),
            expected_divergences={"receipts": _REJECTION_RECEIPT_DEVIATION},
        ),
        turns=(("ghost transfer", "transfer_to_agent_zz"),),
    ),
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_visibility_scoped_per_active_agent",
            kind="swarm",
            compare_fields=("per_agent_visible_tools", "visible_tools_after"),
        ),
        turns=(("move to b", "transfer_to_agent_b"),),
    ),
    SwarmScenario(
        spec=ScenarioSpec(
            name="swarm_checkpoint_survives_restart",
            kind="swarm",
            compare_fields=("receipts", "turns", "final_active_agent"),
        ),
        turns=(("move to b", "transfer_to_agent_b"),),
        restart_turn=("after restart", None),
    ),
)


SUPERVISOR_SCENARIOS: tuple[SupervisorScenario, ...] = (
    SupervisorScenario(
        spec=ScenarioSpec(
            name="supervisor_delegates_and_is_final_author",
            kind="supervisor",
            compare_fields=(
                "delegated_agents",
                "final_author",
                "final_content",
                "user_visible",
                "verifier_saw_researcher",
            ),
        ),
        agents=(("researcher", "research complete"), ("verifier", "verification complete")),
        finalizer_text="supervisor synthesis",
        user_input="inspect the build",
    ),
    SupervisorScenario(
        spec=ScenarioSpec(
            name="supervisor_forward_message_exact",
            kind="supervisor",
            compare_fields=(
                "final_author",
                "final_content",
                "final_metadata",
                "user_visible",
            ),
        ),
        agents=(("researcher", f"exact:{EXACT_TEXT}"), ("verifier", "separate verifier note")),
        add_handoff_messages=False,
        forward_from="researcher",
        user_input="return the researcher answer",
    ),
    SupervisorScenario(
        spec=ScenarioSpec(
            name="supervisor_hides_routing_when_handoffs_off",
            kind="supervisor",
            compare_fields=("routing_free", "delegated_agents"),
        ),
        agents=(("researcher", "researcher done"), ("verifier", "verifier done")),
        add_handoff_messages=False,
        user_input="hide handoff tool chatter",
    ),
    SupervisorScenario(
        spec=ScenarioSpec(
            name="supervisor_output_mode_last_message",
            kind="supervisor",
            compare_fields=("state_contents", "delegated_agents"),
        ),
        agents=(("researcher", "multi"), ("verifier", "multi")),
        add_handoff_messages=False,
        output_mode="last_message",
        user_input="keep only last subagent messages",
    ),
    SupervisorScenario(
        spec=ScenarioSpec(
            name="supervisor_output_mode_full_history",
            kind="supervisor",
            compare_fields=("state_contents", "delegated_agents"),
        ),
        agents=(("researcher", "multi"), ("verifier", "multi")),
        add_handoff_messages=False,
        output_mode="full_history",
        user_input="keep every subagent message",
    ),
    SupervisorScenario(
        spec=ScenarioSpec(
            name="supervisor_distractor_isolation",
            kind="supervisor",
            compare_fields=("routing_free", "state_contents", "delegated_agents"),
        ),
        agents=(("researcher", "researcher done"), ("verifier", "verifier done")),
        add_handoff_messages=False,
        user_input="real request",
        distractors=("routing noise one", "routing noise two"),
    ),
)


# ---------------------------------------------------------------------------
# Dharma arm — runs scenarios through the langgraph_parity clone
# ---------------------------------------------------------------------------


def _swarm_agents():
    def responder(context) -> str:
        return f"{context.agent_name} handled {context.user_input}"

    return {name: responder for name in SWARM_POLICY}


def _swarm_turn_entry(result) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "responding_agent": result.responding_agent,
        "active_before": result.active_agent_before,
        "active_after": result.active_agent_after,
    }
    if result.receipt is None:
        entry["kind"] = "respond"
        entry["content"] = result.content
    elif result.receipt.status == "accepted":
        entry["kind"] = "transfer"
    else:
        entry["kind"] = "transfer_rejected"
    return entry


def run_dharma_swarm(scenario: SwarmScenario, tmp_path: Path) -> dict[str, Any]:
    checkpoint = tmp_path / "dharma_swarm_checkpoint.json"
    runtime = DeterministicSwarmRuntime(
        _swarm_agents(),
        checkpoint_path=checkpoint,
        default_agent=SWARM_DEFAULT_AGENT,
        allowed_handoffs=SWARM_POLICY,
    )
    initial_active = runtime.active_agent
    turns: list[dict[str, Any]] = []
    for user_input, tool_call in scenario.turns:
        turns.append(_swarm_turn_entry(runtime.invoke(user_input, tool_call=tool_call)))
    if scenario.restart_turn is not None:
        runtime = DeterministicSwarmRuntime.load(
            _swarm_agents(),
            checkpoint_path=checkpoint,
            default_agent=SWARM_DEFAULT_AGENT,
            allowed_handoffs=SWARM_POLICY,
        )
        user_input, tool_call = scenario.restart_turn
        turns.append(_swarm_turn_entry(runtime.invoke(user_input, tool_call=tool_call)))
    return {
        "initial_active_agent": initial_active,
        "per_agent_visible_tools": {
            name: list(visible_tool_names_for_agent(name, runtime.handoff_policy))
            for name in SWARM_POLICY
        },
        "turns": turns,
        "receipts": [
            {
                "status": receipt.status,
                "from_agent": receipt.from_agent,
                "requested_agent": receipt.requested_agent,
                "tool_name": receipt.tool_name,
            }
            for receipt in runtime.state.receipts
        ],
        "final_active_agent": runtime.active_agent,
        "visible_tools_after": list(runtime.visible_tools()),
    }


def _dharma_subagent(name: str, behavior: str) -> DeterministicSubagent:
    if behavior == "multi":
        def handler(messages):
            return [
                ParityMessage(role="assistant", content=f"{name} draft"),
                ParityMessage(role="assistant", content=f"{name} final"),
            ]
    elif behavior.startswith("exact:"):
        text = behavior[len("exact:"):]

        def handler(messages, *, _text=text):
            return _text
    else:
        def handler(messages, *, _text=behavior):
            return _text
    return DeterministicSubagent(name, handler)


def run_dharma_supervisor(scenario: SupervisorScenario, tmp_path: Path) -> dict[str, Any]:
    seen: dict[str, list[ParityMessage]] = {}

    def capture(name: str, inner):
        def handler(messages):
            seen[name] = list(messages)
            return inner(messages)

        return handler

    agents = []
    for name, behavior in scenario.agents:
        base = _dharma_subagent(name, behavior)
        agents.append(DeterministicSubagent(name, capture(name, base.handler)))

    runtime = DeterministicSupervisorRuntime(
        agents,
        add_handoff_messages=scenario.add_handoff_messages,
        output_mode=scenario.output_mode,  # type: ignore[arg-type]
        finalizer=(
            (lambda state, *, _t=scenario.finalizer_text: _t)
            if scenario.finalizer_text is not None
            else None
        ),
    )

    if scenario.distractors:
        user_input: Any = [
            ParityMessage(role="user", content=scenario.user_input),
            *(
                ParityMessage(
                    role="assistant",
                    content=content,
                    name="router",
                    metadata={"routing_clutter": True},
                )
                for content in scenario.distractors
            ),
        ]
    else:
        user_input = scenario.user_input

    result = runtime.invoke(user_input, forward_from=scenario.forward_from)

    return {
        "delegated_agents": list(result.delegated_agents),
        "final_author": result.final_message.name,
        "final_content": result.final_message.content,
        "final_metadata": dict(result.final_message.metadata),
        "user_visible": [
            {"name": message.name, "content": message.content}
            for message in result.user_visible_messages
        ],
        "state_contents": [
            message.content
            for message in result.state.messages
            if message.role == "assistant" and not is_routing_message(message)
        ],
        "routing_free": {
            name: not any(is_routing_message(message) for message in messages)
            for name, messages in seen.items()
        },
        "verifier_saw_researcher": any(
            message.name == "researcher" for message in seen.get("verifier", [])
        ),
    }
