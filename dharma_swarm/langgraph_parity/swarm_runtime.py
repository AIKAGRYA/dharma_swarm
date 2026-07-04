"""Deterministic LangGraph-style active-agent parity runtime.

This module is intentionally local and provider-free. It models the active
subagent and handoff-tool behavior needed by parity tests without touching the
production swarm hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from dharma_swarm.langgraph_parity.state import SwarmState, TransferReceipt
from dharma_swarm.langgraph_parity.tools import (
    handoff_tools_for_agent,
    normalize_handoff_policy,
    target_from_transfer_tool,
    validate_agent_name,
    visible_tool_names_for_agent,
)


@dataclass(frozen=True)
class AgentContext:
    agent_name: str
    user_input: str
    active_agent: str
    visible_tools: tuple[str, ...]
    state: SwarmState


@dataclass(frozen=True)
class AgentDecision:
    content: str
    tool_call: str | None = None


@dataclass(frozen=True)
class SwarmTurnResult:
    responding_agent: str
    active_agent_before: str
    active_agent_after: str
    content: str
    visible_tools: tuple[str, ...]
    receipt: TransferReceipt | None = None


class AgentHandler(Protocol):
    def __call__(self, context: AgentContext) -> AgentDecision | str:
        ...


@dataclass(frozen=True)
class DeterministicAgent:
    name: str
    handler: AgentHandler | None = None

    def respond(self, context: AgentContext) -> AgentDecision:
        if self.handler is None:
            return AgentDecision(content=f"{self.name}: {context.user_input}")
        response = self.handler(context)
        if isinstance(response, AgentDecision):
            return response
        return AgentDecision(content=str(response))


class DeterministicSwarmRuntime:
    """Small active-agent runtime with durable checkpointed handoffs."""

    def __init__(
        self,
        agents: Mapping[str, DeterministicAgent | AgentHandler],
        *,
        checkpoint_path: str | Path,
        default_agent: str | None = None,
        allowed_handoffs: Mapping[str, set[str] | tuple[str, ...] | list[str]] | None = None,
    ) -> None:
        if not agents:
            raise ValueError("At least one agent is required")

        self._agents = self._normalize_agents(agents)
        self.agent_names = tuple(self._agents.keys())
        for agent_name in self.agent_names:
            validate_agent_name(agent_name)

        self.default_agent = default_agent or self.agent_names[0]
        if self.default_agent not in self._agents:
            raise ValueError(f"Unknown default agent: {self.default_agent!r}")

        self.checkpoint_path = Path(checkpoint_path)
        self.handoff_policy = normalize_handoff_policy(
            self.agent_names,
            allowed_handoffs,
        )
        self.state = SwarmState.load_or_fresh(self.checkpoint_path, self.default_agent)
        self._validate_loaded_state()
        self._save()

    @property
    def active_agent(self) -> str:
        return self.state.active_agent

    def visible_tools(self, agent_name: str | None = None) -> tuple[str, ...]:
        selected_agent = agent_name or self.state.active_agent
        self._require_agent(selected_agent)
        return visible_tool_names_for_agent(selected_agent, self.handoff_policy)

    def handoff_tools(self, agent_name: str | None = None):
        selected_agent = agent_name or self.state.active_agent
        self._require_agent(selected_agent)
        return handoff_tools_for_agent(selected_agent, self.handoff_policy)

    def invoke(
        self,
        user_input: str,
        *,
        tool_call: str | None = None,
    ) -> SwarmTurnResult:
        """Run one deterministic turn for the currently active agent.

        Passing `tool_call` simulates the active subagent calling one of its
        visible `transfer_to_<agent>` tools. Without a transfer call, the active
        subagent responds directly and remains active.
        """

        active_before = self.state.active_agent
        visible_tools = self.visible_tools(active_before)
        self.state.record_user_message(user_input, active_before)
        context = AgentContext(
            agent_name=active_before,
            user_input=user_input,
            active_agent=active_before,
            visible_tools=visible_tools,
            state=self.state,
        )
        decision = self._agents[active_before].respond(context)
        requested_tool = tool_call or decision.tool_call

        if requested_tool:
            result = self._apply_transfer_tool(
                tool_name=requested_tool,
                from_agent=active_before,
                visible_tools=visible_tools,
            )
        else:
            self.state.record_agent_message(decision.content, active_before)
            result = SwarmTurnResult(
                responding_agent=active_before,
                active_agent_before=active_before,
                active_agent_after=self.state.active_agent,
                content=decision.content,
                visible_tools=visible_tools,
            )

        self.state.turn_index += 1
        self._save()
        return result

    def save_checkpoint(self) -> Path:
        return self._save()

    @classmethod
    def load(
        cls,
        agents: Mapping[str, DeterministicAgent | AgentHandler],
        *,
        checkpoint_path: str | Path,
        default_agent: str | None = None,
        allowed_handoffs: Mapping[str, set[str] | tuple[str, ...] | list[str]] | None = None,
    ) -> "DeterministicSwarmRuntime":
        return cls(
            agents,
            checkpoint_path=checkpoint_path,
            default_agent=default_agent,
            allowed_handoffs=allowed_handoffs,
        )

    def _apply_transfer_tool(
        self,
        *,
        tool_name: str,
        from_agent: str,
        visible_tools: tuple[str, ...],
    ) -> SwarmTurnResult:
        active_before = self.state.active_agent
        requested_agent = target_from_transfer_tool(tool_name)

        if requested_agent is None:
            reason = f"Rejected invalid handoff tool: {tool_name!r}"
            return self._record_rejected_transfer(
                from_agent=from_agent,
                requested_agent=None,
                tool_name=tool_name,
                reason=reason,
                visible_tools=visible_tools,
                active_before=active_before,
            )

        if requested_agent not in self._agents:
            reason = f"Rejected transfer to unknown agent: {requested_agent}"
            return self._record_rejected_transfer(
                from_agent=from_agent,
                requested_agent=requested_agent,
                tool_name=tool_name,
                reason=reason,
                visible_tools=visible_tools,
                active_before=active_before,
            )

        if tool_name not in visible_tools:
            reason = (
                f"Rejected transfer from {from_agent} to {requested_agent}: "
                "handoff tool is not visible to the active agent"
            )
            return self._record_rejected_transfer(
                from_agent=from_agent,
                requested_agent=requested_agent,
                tool_name=tool_name,
                reason=reason,
                visible_tools=visible_tools,
                active_before=active_before,
            )

        self.state.active_agent = requested_agent
        reason = f"Accepted transfer from {from_agent} to {requested_agent}"
        receipt = TransferReceipt(
            id=self.state.next_receipt_id(),
            status="accepted",
            from_agent=from_agent,
            requested_agent=requested_agent,
            tool_name=tool_name,
            reason=reason,
            active_agent_before=active_before,
            active_agent_after=self.state.active_agent,
            visible_tools=visible_tools,
            turn_index=self.state.turn_index,
        )
        self.state.record_receipt(receipt)
        return SwarmTurnResult(
            responding_agent=from_agent,
            active_agent_before=active_before,
            active_agent_after=self.state.active_agent,
            content=reason,
            visible_tools=visible_tools,
            receipt=receipt,
        )

    def _record_rejected_transfer(
        self,
        *,
        from_agent: str,
        requested_agent: str | None,
        tool_name: str,
        reason: str,
        visible_tools: tuple[str, ...],
        active_before: str,
    ) -> SwarmTurnResult:
        receipt = TransferReceipt(
            id=self.state.next_receipt_id(),
            status="rejected",
            from_agent=from_agent,
            requested_agent=requested_agent,
            tool_name=tool_name,
            reason=reason,
            active_agent_before=active_before,
            active_agent_after=self.state.active_agent,
            visible_tools=visible_tools,
            turn_index=self.state.turn_index,
        )
        self.state.record_receipt(receipt)
        return SwarmTurnResult(
            responding_agent=from_agent,
            active_agent_before=active_before,
            active_agent_after=self.state.active_agent,
            content=reason,
            visible_tools=visible_tools,
            receipt=receipt,
        )

    def _save(self) -> Path:
        return self.state.save(self.checkpoint_path)

    def _validate_loaded_state(self) -> None:
        self._require_agent(self.state.active_agent)
        self._require_agent(self.state.default_agent)

    def _require_agent(self, agent_name: str) -> None:
        if agent_name not in self._agents:
            raise ValueError(f"Unknown agent: {agent_name!r}")

    @staticmethod
    def _normalize_agents(
        agents: Mapping[str, DeterministicAgent | AgentHandler],
    ) -> dict[str, DeterministicAgent]:
        normalized: dict[str, DeterministicAgent] = {}
        for name, agent in agents.items():
            if isinstance(agent, DeterministicAgent):
                if agent.name != name:
                    raise ValueError(
                        f"Agent mapping key {name!r} does not match agent name {agent.name!r}"
                    )
                normalized[name] = agent
            else:
                normalized[name] = DeterministicAgent(name=name, handler=agent)
        return normalized
