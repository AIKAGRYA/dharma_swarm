"""Real-LangGraph arm of the differential oracle.

Builds minimal ``StateGraph`` equivalents of the parity scenarios — swarm
handoffs via state-routed agent nodes over a checkpointer thread
(langgraph-swarm shape), supervisor delegation as a linear graph with an
accumulating messages channel (langgraph-supervisor shape) — using
deterministic callables as the "models" (no API keys, no network). The
ENGINE under test is langgraph itself: conditional entry routing, reducer
channels, checkpointer resume across graph rebuilds.

LangGraph-native tool semantics are preserved deliberately: a handoff tool
that is not bound to the active agent DOES NOT EXIST here, so an invalid
transfer surfaces as an unbound-tool error with no durable receipt — the
adjudicated deviation from dharma's receipts-first rejection receipts (see
docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from tests.oracle_support.scenarios import (
    SWARM_DEFAULT_AGENT,
    SWARM_POLICY,
    SupervisorScenario,
    SwarmScenario,
)

__all__ = ["run_langgraph_supervisor", "run_langgraph_swarm"]

_TRANSFER_PREFIX = "transfer_to_"


def _visible_tools(agent: str) -> list[str]:
    return [f"{_TRANSFER_PREFIX}{target}" for target in SWARM_POLICY.get(agent, ())]


# ---------------------------------------------------------------------------
# Swarm arm
# ---------------------------------------------------------------------------


class _SwarmState(TypedDict, total=False):
    active_agent: str
    turn_input: str
    tool_call: Optional[str]
    receipts: Annotated[list[dict[str, Any]], operator.add]
    turn_log: Annotated[list[dict[str, Any]], operator.add]


def _swarm_node(name: str):
    def node(state: _SwarmState) -> dict[str, Any]:
        visible = _visible_tools(name)
        tool_call = state.get("tool_call")
        if tool_call:
            if tool_call in visible:
                target = tool_call[len(_TRANSFER_PREFIX):]
                return {
                    "active_agent": target,
                    "receipts": [
                        {
                            "status": "accepted",
                            "from_agent": name,
                            "requested_agent": target,
                            "tool_name": tool_call,
                        }
                    ],
                    "turn_log": [
                        {
                            "responding_agent": name,
                            "active_before": name,
                            "active_after": target,
                            "kind": "transfer",
                        }
                    ],
                }
            # LangGraph-native: the tool was never bound to this agent, so the
            # call fails as unbound — no state change, no durable receipt.
            return {
                "turn_log": [
                    {
                        "responding_agent": name,
                        "active_before": name,
                        "active_after": name,
                        "kind": "tool_error",
                        "error": f"tool not bound: {tool_call}",
                    }
                ],
            }
        content = f"{name} handled {state.get('turn_input', '')}"
        return {
            "turn_log": [
                {
                    "responding_agent": name,
                    "active_before": name,
                    "active_after": name,
                    "kind": "respond",
                    "content": content,
                }
            ],
        }

    return node


def _build_swarm_app(saver: InMemorySaver):
    builder = StateGraph(_SwarmState)
    for name in SWARM_POLICY:
        builder.add_node(name, _swarm_node(name))
        builder.add_edge(name, END)
    builder.add_conditional_edges(
        START,
        lambda state: state.get("active_agent") or SWARM_DEFAULT_AGENT,
        {name: name for name in SWARM_POLICY},
    )
    return builder.compile(checkpointer=saver)


def run_langgraph_swarm(scenario: SwarmScenario, tmp_path: Any) -> dict[str, Any]:
    saver = InMemorySaver()
    app = _build_swarm_app(saver)
    config = {"configurable": {"thread_id": f"oracle-{scenario.spec.name}"}}

    state: dict[str, Any] = {}
    for user_input, tool_call in scenario.turns:
        state = app.invoke({"turn_input": user_input, "tool_call": tool_call}, config)
    if scenario.restart_turn is not None:
        # "Restart": a fresh compiled graph over the SAME checkpointer +
        # thread must resume the persisted channel state (active_agent).
        app = _build_swarm_app(saver)
        user_input, tool_call = scenario.restart_turn
        state = app.invoke({"turn_input": user_input, "tool_call": tool_call}, config)

    final_active = state.get("active_agent") or SWARM_DEFAULT_AGENT
    return {
        "initial_active_agent": SWARM_DEFAULT_AGENT,
        "per_agent_visible_tools": {name: _visible_tools(name) for name in SWARM_POLICY},
        "turns": list(state.get("turn_log", [])),
        "receipts": list(state.get("receipts", [])),
        "final_active_agent": final_active,
        "visible_tools_after": _visible_tools(final_active),
    }


# ---------------------------------------------------------------------------
# Supervisor arm
# ---------------------------------------------------------------------------


class _SupState(TypedDict, total=False):
    messages: Annotated[list[dict[str, Any]], operator.add]
    seen: Annotated[list[dict[str, Any]], operator.add]
    agent_outputs: Annotated[list[dict[str, Any]], operator.add]
    final: dict[str, Any]


def _is_routing(message: dict[str, Any]) -> bool:
    metadata = message.get("metadata") or {}
    return bool(
        metadata.get("routing_clutter")
        or metadata.get("__is_handoff_back")
        or message.get("role") == "tool"
    )


def _behavior_outputs(name: str, behavior: str) -> list[dict[str, Any]]:
    if behavior == "multi":
        contents = [f"{name} draft", f"{name} final"]
    elif behavior.startswith("exact:"):
        contents = [behavior[len("exact:"):]]
    else:
        contents = [behavior]
    return [
        {"role": "assistant", "content": content, "name": name, "metadata": {}}
        for content in contents
    ]


def _supervisor_agent_node(
    name: str,
    behavior: str,
    sequence: int,
    scenario: SupervisorScenario,
    supervisor_name: str = "supervisor",
):
    def node(state: _SupState) -> dict[str, Any]:
        appended: list[dict[str, Any]] = []
        if scenario.add_handoff_messages:
            tool_name = f"{_TRANSFER_PREFIX}{name}"
            appended.extend(
                [
                    {
                        "role": "assistant",
                        "content": "",
                        "name": supervisor_name,
                        "metadata": {
                            "routing_clutter": True,
                            "tool_call": tool_name,
                            "handoff_sequence": sequence,
                        },
                    },
                    {
                        "role": "tool",
                        "content": f"Successfully transferred to {name}",
                        "name": tool_name,
                        "metadata": {"routing_clutter": True},
                    },
                ]
            )

        history = list(state.get("messages", [])) + appended
        if scenario.add_handoff_messages:
            visible = history
        else:
            visible = [message for message in history if not _is_routing(message)]

        outputs = _behavior_outputs(name, behavior)
        if scenario.output_mode == "last_message":
            selected = [outputs[-1]]
        else:
            selected = list(outputs)
        appended.extend(selected)

        if scenario.add_handoff_messages:
            appended.append(
                {
                    "role": "assistant",
                    "content": f"Transferring back to {supervisor_name}",
                    "name": name,
                    "metadata": {"routing_clutter": True, "__is_handoff_back": True},
                }
            )

        return {
            "messages": appended,
            "seen": [{"agent": name, "messages": visible}],
            "agent_outputs": [
                {"agent": name, "last_content": outputs[-1]["content"]}
            ],
        }

    return node


def _supervisor_finalize_node(scenario: SupervisorScenario, supervisor_name: str = "supervisor"):
    def node(state: _SupState) -> dict[str, Any]:
        if scenario.forward_from is not None:
            forwarded = next(
                (
                    message
                    for message in reversed(state.get("messages", []))
                    if message.get("role") == "assistant"
                    and str(message.get("name", "")).lower()
                    == scenario.forward_from.lower()
                    and not _is_routing(message)
                ),
                None,
            )
            if forwarded is None:
                raise ValueError(f"no message from {scenario.forward_from}")
            final = {
                "role": "assistant",
                "content": forwarded["content"],
                "name": supervisor_name,
                "metadata": {"forwarded_from": scenario.forward_from},
            }
        elif scenario.finalizer_text is not None:
            final = {
                "role": "assistant",
                "content": scenario.finalizer_text,
                "name": supervisor_name,
                "metadata": {},
            }
        else:
            lines = [
                f"{entry['agent']}: {entry['last_content']}"
                for entry in state.get("agent_outputs", [])
            ]
            final = {
                "role": "assistant",
                "content": "\n".join(lines),
                "name": supervisor_name,
                "metadata": {},
            }
        return {"messages": [final], "final": final}

    return node


def run_langgraph_supervisor(scenario: SupervisorScenario, tmp_path: Any) -> dict[str, Any]:
    builder = StateGraph(_SupState)
    previous = START
    for sequence, (name, behavior) in enumerate(scenario.agents, start=1):
        builder.add_node(name, _supervisor_agent_node(name, behavior, sequence, scenario))
        builder.add_edge(previous, name)
        previous = name
    builder.add_node("finalize", _supervisor_finalize_node(scenario))
    builder.add_edge(previous, "finalize")
    builder.add_edge("finalize", END)
    app = builder.compile()

    initial_messages: list[dict[str, Any]] = [
        {"role": "user", "content": scenario.user_input, "name": None, "metadata": {}}
    ]
    initial_messages.extend(
        {
            "role": "assistant",
            "content": content,
            "name": "router",
            "metadata": {"routing_clutter": True},
        }
        for content in scenario.distractors
    )
    state = app.invoke({"messages": initial_messages})

    final = state["final"]
    seen: dict[str, list[dict[str, Any]]] = {
        entry["agent"]: entry["messages"] for entry in state.get("seen", [])
    }
    return {
        "delegated_agents": [name for name, _behavior in scenario.agents],
        "final_author": final["name"],
        "final_content": final["content"],
        "final_metadata": dict(final.get("metadata", {})),
        "user_visible": [{"name": final["name"], "content": final["content"]}],
        "state_contents": [
            message["content"]
            for message in state.get("messages", [])
            if message.get("role") == "assistant" and not _is_routing(message)
        ],
        "routing_free": {
            name: not any(_is_routing(message) for message in messages)
            for name, messages in seen.items()
        },
        "verifier_saw_researcher": any(
            message.get("name") == "researcher" for message in seen.get("verifier", [])
        ),
    }
