"""Deterministic LangGraph-style supervisor runtime."""

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
from dharma_swarm.langgraph_parity.tools import create_delegate_tool


@dataclass(frozen=True, slots=True)
class SupervisorTurnResult:
    session_id: str
    final_message: ChatMessage
    user_visible_messages: tuple[ChatMessage, ...]
    returned_messages: tuple[ChatMessage, ...]
    state: ConversationState
    checkpoint_path: Path


class SupervisorRuntime:
    """Small executable model of LangGraph supervisor semantics."""

    def __init__(
        self,
        manifests: tuple[AgentManifest, ...],
        *,
        checkpoint_store: JsonCheckpointStore,
        supervisor_name: str = "supervisor",
        output_mode: str = "last_message",
        add_handoff_messages: bool = True,
        add_handoff_back_messages: bool = True,
        mission_id: str = "",
        receipt_dir: Path | None = None,
    ) -> None:
        if output_mode not in {"last_message", "full_history"}:
            raise ValueError("output_mode must be 'last_message' or 'full_history'")
        if not manifests:
            raise ValueError("at least one agent manifest is required")
        self.agents = {manifest.name: manifest for manifest in manifests}
        self.checkpoints = checkpoint_store
        self.supervisor_name = supervisor_name
        self.output_mode = output_mode
        self.add_handoff_messages = add_handoff_messages
        self.add_handoff_back_messages = add_handoff_back_messages
        self.mission_id = mission_id
        self.receipt_dir = receipt_dir

    def load_state(self, session_id: str) -> ConversationState:
        state = self.checkpoints.load(session_id)
        if state is not None:
            return state
        return ConversationState.new(
            session_id=session_id,
            mode="supervisor",
            default_active_agent=self.supervisor_name,
            mission_id=self.mission_id,
            supervisor_authority=True,
        )

    def invoke(
        self,
        session_id: str,
        user_message: str,
        *,
        delegate_targets: tuple[str, ...],
        forward_from: str = "",
    ) -> SupervisorTurnResult:
        state = self.load_state(session_id)
        state.active_agent = self.supervisor_name
        state.append_message("user", user_message)
        started = time.perf_counter()
        agent_responses: list[ChatMessage] = []
        for target in delegate_targets:
            agent_responses.append(self._delegate(state, target, user_message))
        if forward_from:
            final_text = self.forward_message(state, from_agent=forward_from)
            metadata = {"forwarded_from": forward_from, "supervisor_final": True}
        else:
            joined = " | ".join(
                f"{message.name}: {message.content}" for message in agent_responses
            )
            final_text = f"Supervisor final: {joined}"
            metadata = {"supervisor_final": True}
        final_message = state.append_message(
            "assistant",
            final_text,
            name=self.supervisor_name,
            metadata=metadata,
        )
        self._record_receipt(
            state,
            operation="langgraph_parity.supervisor.turn",
            status="ok",
            input_text=user_message,
            output_text=final_text,
            latency_ms=int((time.perf_counter() - started) * 1000),
            attributes={
                "delegate_count": len(delegate_targets),
                "forwarded_from": forward_from,
                "output_mode": self.output_mode,
                "add_handoff_messages": self.add_handoff_messages,
                "add_handoff_back_messages": self.add_handoff_back_messages,
            },
        )
        checkpoint_path = self.checkpoints.save(state)
        returned = (final_message,) if self.output_mode == "last_message" else tuple(state.messages)
        return SupervisorTurnResult(
            session_id=session_id,
            final_message=final_message,
            user_visible_messages=(final_message,),
            returned_messages=returned,
            state=state,
            checkpoint_path=checkpoint_path,
        )

    def forward_message(self, state: ConversationState, *, from_agent: str) -> str:
        for message in reversed(state.messages):
            if message.role == "assistant" and message.name.lower() == from_agent.lower():
                if message.metadata.get("__is_handoff_back"):
                    continue
                return message.content
        known = sorted({message.name for message in state.messages if message.name})
        raise ValueError(f"no message from {from_agent}; known agents={known}")

    def _delegate(
        self,
        state: ConversationState,
        target: str,
        user_message: str,
    ) -> ChatMessage:
        if target not in self.agents:
            raise ValueError(f"unknown delegate target: {target}")
        tool = create_delegate_tool(agent_name=target)
        if self.add_handoff_messages:
            state.append_message(
                "assistant",
                "",
                name=self.supervisor_name,
                metadata={"tool_call": tool.name, "routing_clutter": True},
            )
            state.append_message(
                "tool",
                f"Successfully transferred to {target}",
                name=tool.name,
                metadata={"routing_clutter": True, "to_agent": target},
            )
        visible = [
            message
            for message in state.messages
            if not message.metadata.get("routing_clutter")
        ]
        state.set_visible_history(target, visible)
        manifest = self.agents[target]
        response = state.append_message(
            "assistant",
            f"{target} response [{manifest.domain}]: {user_message.strip()}",
            name=target,
        )
        if self.add_handoff_back_messages:
            state.append_message(
                "assistant",
                "Transferring back to supervisor",
                name=target,
                metadata={
                    "__is_handoff_back": True,
                    "tool_call": "transfer_back_to_supervisor",
                    "routing_clutter": True,
                },
            )
            state.append_message(
                "tool",
                "Successfully transferred back to supervisor",
                name="transfer_back_to_supervisor",
                metadata={"routing_clutter": True},
            )
        state.handoff_trail.append(
            HandoffTrailEntry(
                from_agent=self.supervisor_name,
                to_agent=target,
                tool_name=tool.name,
                reason="supervisor delegation",
                accepted=True,
            )
        )
        return response

    def _record_receipt(
        self,
        state: ConversationState,
        *,
        operation: str,
        status: str,
        input_text: str,
        output_text: str,
        latency_ms: int | None = None,
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        trace_id = state.metadata.setdefault("trace_id", uuid4().hex)
        side_effect_key = f"{operation}:{state.session_id}:{len(state.receipts)}"
        receipt = build_evidence_receipt(
            operation=operation,
            task_id=state.session_id,
            agent_id=self.supervisor_name,
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
        )
        payload = receipt.to_dict()
        state.receipts.append(payload)
        if self.receipt_dir is not None:
            append_receipt_jsonl(self.receipt_dir / f"{state.session_id}.jsonl", receipt)
        return payload
