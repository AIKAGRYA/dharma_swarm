"""Handoff tool helpers for LangGraph parity tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from dharma_swarm.langgraph_parity.state import (
    ParityMessage,
    SupervisorParityState,
    is_routing_message,
)


TRANSFER_TOOL_PREFIX = "transfer_to_"
_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class HandoffTool:
    """Description of a deterministic transfer tool visible to one agent."""

    name: str
    source_agent: str
    target_agent: str
    description: str


def validate_agent_name(agent_name: str) -> None:
    if not _AGENT_NAME_RE.fullmatch(agent_name):
        raise ValueError(
            "Agent names must contain only letters, numbers, and underscores "
            f"for deterministic transfer tool names: {agent_name!r}"
        )


def transfer_tool_name(agent_name: str) -> str:
    validate_agent_name(agent_name)
    return f"{TRANSFER_TOOL_PREFIX}{agent_name}"


def handoff_tool_name(agent_name: str, *, prefix: str = TRANSFER_TOOL_PREFIX) -> str:
    validate_agent_name(agent_name)
    return f"{prefix}{agent_name}"


def target_from_transfer_tool(tool_name: str) -> str | None:
    if not tool_name.startswith(TRANSFER_TOOL_PREFIX):
        return None
    target = tool_name[len(TRANSFER_TOOL_PREFIX) :]
    if not target or not _AGENT_NAME_RE.fullmatch(target):
        return None
    return target


def normalize_handoff_policy(
    agent_names: tuple[str, ...],
    allowed_handoffs: Mapping[str, set[str] | tuple[str, ...] | list[str]] | None,
) -> dict[str, tuple[str, ...]]:
    """Return deterministic allowed transfer targets for each agent."""

    known = set(agent_names)
    if allowed_handoffs is None:
        return {
            agent: tuple(candidate for candidate in agent_names if candidate != agent)
            for agent in agent_names
        }

    policy: dict[str, tuple[str, ...]] = {}
    for agent in agent_names:
        raw_targets = allowed_handoffs.get(agent, ())
        targets = tuple(target for target in agent_names if target in raw_targets)
        policy[agent] = tuple(target for target in targets if target in known)
    return policy


def handoff_tools_for_agent(
    agent_name: str,
    handoff_policy: Mapping[str, tuple[str, ...]],
) -> tuple[HandoffTool, ...]:
    return tuple(
        HandoffTool(
            name=transfer_tool_name(target),
            source_agent=agent_name,
            target_agent=target,
            description=f"Transfer active agent from {agent_name} to {target}.",
        )
        for target in handoff_policy.get(agent_name, ())
    )


def visible_tool_names_for_agent(
    agent_name: str,
    handoff_policy: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    return tuple(tool.name for tool in handoff_tools_for_agent(agent_name, handoff_policy))


def create_handoff_messages(
    *,
    supervisor_name: str,
    agent_name: str,
    sequence: int,
) -> tuple[ParityMessage, ParityMessage]:
    tool_name = transfer_tool_name(agent_name)
    return (
        ParityMessage(
            role="assistant",
            content="",
            name=supervisor_name,
            metadata={
                "routing_clutter": True,
                "tool_call": tool_name,
                "handoff_sequence": sequence,
                "__handoff_destination": agent_name,
            },
        ),
        ParityMessage(
            role="tool",
            content=f"Successfully transferred to {agent_name}",
            name=tool_name,
            metadata={
                "routing_clutter": True,
                "handoff_sequence": sequence,
                "__handoff_destination": agent_name,
            },
        ),
    )


def create_handoff_back_messages(
    *,
    agent_name: str,
    supervisor_name: str,
    sequence: int,
) -> tuple[ParityMessage, ParityMessage]:
    return (
        ParityMessage(
            role="assistant",
            content=f"Transferring back to {supervisor_name}",
            name=agent_name,
            metadata={
                "routing_clutter": True,
                "__is_handoff_back": True,
                "tool_call": f"transfer_back_to_{supervisor_name}",
                "handoff_sequence": sequence,
            },
        ),
        ParityMessage(
            role="tool",
            content=f"Successfully transferred back to {supervisor_name}",
            name=f"transfer_back_to_{supervisor_name}",
            metadata={
                "routing_clutter": True,
                "__is_handoff_back": True,
                "handoff_sequence": sequence,
            },
        ),
    )


def forward_message(
    state: SupervisorParityState,
    *,
    from_agent: str,
    supervisor_name: str,
) -> ParityMessage:
    for message in reversed(state.messages):
        if (
            message.role == "assistant"
            and message.name is not None
            and message.name.lower() == from_agent.lower()
            and not is_routing_message(message)
        ):
            return ParityMessage(
                role="assistant",
                content=message.content,
                name=supervisor_name,
                metadata={"forwarded_from": from_agent},
            )
    known = sorted({message.name for message in state.messages if message.name})
    raise ValueError(f"no message from {from_agent}; known agents={known}")
