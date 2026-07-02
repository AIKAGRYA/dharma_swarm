"""Stable transfer/delegate tool descriptors for parity runtimes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from dharma_swarm.langgraph_parity.state import AgentManifest

ToolKind = Literal["handoff", "delegate", "forward"]


def normalize_agent_name(agent_name: str) -> str:
    lowered = agent_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or "agent"


def handoff_tool_name(agent_name: str, *, prefix: str = "transfer_to_") -> str:
    return f"{prefix}{normalize_agent_name(agent_name)}"


@dataclass(frozen=True, slots=True)
class HandoffTool:
    name: str
    target_agent: str
    description: str
    kind: ToolKind = "handoff"
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "target_agent": self.target_agent,
            "description": self.description,
            "kind": self.kind,
            "metadata": dict(self.metadata),
        }


def create_handoff_tool(
    *,
    agent_name: str,
    name: str | None = None,
    description: str | None = None,
) -> HandoffTool:
    tool_name = name or handoff_tool_name(agent_name)
    return HandoffTool(
        name=tool_name,
        target_agent=agent_name,
        description=description or f"Ask agent '{agent_name}' for help",
        kind="handoff",
        metadata={"__handoff_destination": agent_name},
    )


def create_delegate_tool(
    *,
    agent_name: str,
    name: str | None = None,
    description: str | None = None,
) -> HandoffTool:
    tool_name = name or handoff_tool_name(agent_name, prefix="delegate_to_")
    return HandoffTool(
        name=tool_name,
        target_agent=agent_name,
        description=description or f"Delegate work to agent '{agent_name}'",
        kind="delegate",
        metadata={"__handoff_destination": agent_name},
    )


def create_forward_message_tool(supervisor_name: str = "supervisor") -> HandoffTool:
    return HandoffTool(
        name="forward_message",
        target_agent=supervisor_name,
        description="Forward the last selected subagent message without paraphrase",
        kind="forward",
        metadata={"__forwarding_supervisor": supervisor_name},
    )


def allowed_handoff_tools(
    manifest: AgentManifest,
    all_agents: dict[str, AgentManifest],
) -> tuple[HandoffTool, ...]:
    tools: list[HandoffTool] = []
    for target in manifest.handoff_targets:
        if target in all_agents:
            tools.append(create_handoff_tool(agent_name=target))
    return tuple(tools)


def allowed_tool_names(
    manifest: AgentManifest,
    all_agents: dict[str, AgentManifest],
) -> tuple[str, ...]:
    return tuple(tool.name for tool in allowed_handoff_tools(manifest, all_agents))
