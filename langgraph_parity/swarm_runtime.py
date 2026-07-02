"""Deterministic LangGraph-style swarm active-agent runtime."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from dharma_swarm.langgraph_parity.receipts import (
    append_receipt_jsonl,
    build_evidence_receipt,
    estimate_cost_usd,
    estimate_tokens,
)
from dharma_swarm.langgraph_parity.state import (
    AgentManifest,
    ChatMessage,
    ConversationState,
    HandoffTrailEntry,
    JsonCheckpointStore,
)
from dharma_swarm.langgraph_parity.tools import (
    allowed_handoff_tools,
    create_handoff_tool,
    handoff_tool_name,
    normalize_agent_name,
)


@dataclass(frozen=True, slots=True)
class RuntimeTurnResult:
    session_id: str
    active_agent: str
    response: ChatMessage
    state: ConversationState
    receipt: dict[str, object]
    checkpoint_path: Path


class SwarmRuntime:
    """Small executable model of LangGraph swarm control semantics."""

    def __init__(
        self,
        manifests: tuple[AgentManifest, ...],
        *,
        default_active_agent: str,
        checkpoint_store: JsonCheckpointStore,
        mission_id: str = "",
        receipt_dir: Path | None = None,
    ) -> None:
        if not manifests:
            raise ValueError("at least one agent manifest is required")
        self.agents = {manifest.name: manifest for manifest in manifests}
        if default_active_agent not in self.agents:
            raise ValueError(f"default active agent not found: {default_active_agent}")
        for manifest in manifests:
            missing = [target for target in manifest.handoff_targets if target not in self.agents]
            if missing:
                raise ValueError(f"{manifest.name} has unknown handoff targets: {missing}")
        self.default_active_agent = default_active_agent
        self.checkpoints = checkpoint_store
        self.mission_id = mission_id
        self.receipt_dir = receipt_dir

    def allowed_tools(self, agent_name: str) -> tuple[str, ...]:
        manifest = self.agents[agent_name]
        return tuple(tool.name for tool in allowed_handoff_tools(manifest, self.agents))

    def load_state(self, session_id: str) -> ConversationState:
        state = self.checkpoints.load(session_id)
        if state is not None:
            return state
        return ConversationState.new(
            session_id=session_id,
            mode="swarm",
            default_active_agent=self.default_active_agent,
            mission_id=self.mission_id,
        )

    def invoke(self, session_id: str, user_message: str) -> RuntimeTurnResult:
        state = self.load_state(session_id)
        active = state.active_agent or self.default_active_agent
        state.append_message("user", user_message)
        target = self._extract_requested_transfer(user_message)
        if target:
            return self.transfer(
                session_id,
                from_agent=active,
                to_agent=target,
                reason=f"user requested {target}",
                state=state,
            )
        response = self._respond(active, user_message)
        state.append_message("assistant", response, name=active)
        self._refresh_visible_history(state, active)
        receipt = self._record_receipt(
            state,
            operation="langgraph_parity.swarm.turn",
            agent_id=active,
            status="ok",
            input_text=user_message,
            output_text=response,
            attributes={"active_agent": active, "handoff_count": len(state.handoff_trail)},
        )
        checkpoint_path = self.checkpoints.save(state)
        return RuntimeTurnResult(
            session_id=session_id,
            active_agent=state.active_agent,
            response=state.messages[-1],
            state=state,
            receipt=receipt,
            checkpoint_path=checkpoint_path,
        )

    def transfer(
        self,
        session_id: str,
        *,
        from_agent: str,
        to_agent: str,
        reason: str = "",
        state: ConversationState | None = None,
    ) -> RuntimeTurnResult:
        state = state or self.load_state(session_id)
        started = time.perf_counter()
        active = state.active_agent or self.default_active_agent
        requester = from_agent or active
        allowed_targets = set(self.agents[requester].handoff_targets)
        tool = create_handoff_tool(agent_name=to_agent)
        if to_agent not in self.agents or to_agent not in allowed_targets:
            error = f"invalid transfer target {to_agent!r} for {requester}"
            state.handoff_trail.append(
                HandoffTrailEntry(
                    from_agent=requester,
                    to_agent=to_agent,
                    tool_name=tool.name,
                    reason=reason,
                    accepted=False,
                )
            )
            response_text = error
            state.append_message(
                "assistant",
                response_text,
                name=active,
                metadata={"transfer_rejected": True},
            )
            receipt = self._record_receipt(
                state,
                operation="langgraph_parity.swarm.handoff",
                agent_id=requester,
                status="failed",
                input_text=reason,
                output_text=response_text,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_detail=error,
                attributes={
                    "from_agent": requester,
                    "to_agent": to_agent,
                    "tool_name": tool.name,
                    "accepted": False,
                },
            )
            checkpoint_path = self.checkpoints.save(state)
            return RuntimeTurnResult(
                session_id=session_id,
                active_agent=state.active_agent,
                response=state.messages[-1],
                state=state,
                receipt=receipt,
                checkpoint_path=checkpoint_path,
            )

        state.append_message(
            "tool",
            f"Successfully transferred to {to_agent}",
            name=tool.name,
            metadata={"routing_clutter": True, "to_agent": to_agent},
        )
        state.active_agent = to_agent
        response_text = self._respond(to_agent, reason or f"handoff from {requester}")
        state.append_message("assistant", response_text, name=to_agent)
        receipt = self._record_receipt(
            state,
            operation="langgraph_parity.swarm.handoff",
            agent_id=requester,
            status="ok",
            input_text=reason,
            output_text=response_text,
            latency_ms=int((time.perf_counter() - started) * 1000),
            attributes={
                "from_agent": requester,
                "to_agent": to_agent,
                "tool_name": tool.name,
                "accepted": True,
            },
        )
        state.handoff_trail.append(
            HandoffTrailEntry(
                from_agent=requester,
                to_agent=to_agent,
                tool_name=tool.name,
                reason=reason,
                accepted=True,
                receipt_id=str(receipt.get("receipt_id") or ""),
            )
        )
        self._refresh_visible_history(state, to_agent)
        checkpoint_path = self.checkpoints.save(state)
        return RuntimeTurnResult(
            session_id=session_id,
            active_agent=state.active_agent,
            response=state.messages[-1],
            state=state,
            receipt=receipt,
            checkpoint_path=checkpoint_path,
        )

    def _extract_requested_transfer(self, user_message: str) -> str:
        lowered = user_message.lower()
        for agent_name in self.agents:
            normalized = normalize_agent_name(agent_name)
            if handoff_tool_name(agent_name) in lowered:
                return agent_name
            if f"transfer to {normalized}" in lowered.replace("_", " "):
                return agent_name
        return ""

    def _respond(self, agent_name: str, user_message: str) -> str:
        manifest = self.agents[agent_name]
        return (
            f"{agent_name} direct response [{manifest.domain}]: "
            f"{user_message.strip()}"
        )

    def _refresh_visible_history(self, state: ConversationState, agent_name: str) -> None:
        visible = [
            message
            for message in state.messages
            if not message.metadata.get("routing_clutter")
        ]
        state.set_visible_history(agent_name, visible)

    def _record_receipt(
        self,
        state: ConversationState,
        *,
        operation: str,
        agent_id: str,
        status: str,
        input_text: str,
        output_text: str,
        latency_ms: int | None = None,
        error_detail: str = "",
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        trace_id = state.metadata.setdefault("trace_id", uuid4().hex)
        side_effect_key = f"{operation}:{state.session_id}:{len(state.receipts)}"
        receipt = build_evidence_receipt(
            operation=operation,
            task_id=state.session_id,
            agent_id=agent_id,
            trace_id=str(trace_id),
            status=status,
            mission_id=state.mission_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd("local_deterministic", input_tokens, output_tokens),
            latency_ms=latency_ms,
            side_effect_key=side_effect_key,
            idempotency_key=f"{state.session_id}:{len(state.receipts)}",
            attributes=attributes,
            error_detail=error_detail,
        )
        payload = receipt.to_dict()
        state.receipts.append(payload)
        if self.receipt_dir is not None:
            append_receipt_jsonl(self.receipt_dir / f"{state.session_id}.jsonl", receipt)
        return payload
