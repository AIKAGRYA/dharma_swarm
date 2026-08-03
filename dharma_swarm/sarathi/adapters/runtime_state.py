"""Sarathi turn persistence over the existing RuntimeStateStore schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from dharma_swarm.runtime_state import (
    RuntimeReceipt,
    RuntimeStateStore,
    SessionEventRecord,
)
from dharma_swarm.spine.identity import ExecutionIdentity

from ..contracts import SarathiTurnRequest, SarathiTurnResult, TurnStatus


class RuntimeStateTurnStore:
    """Namespace Sarathi episodes and receipts in the shared runtime database."""

    def __init__(self, db_path: str | Path) -> None:
        self.runtime_state = RuntimeStateStore(
            Path(db_path),
            include_memory_plane=False,
        )

    @staticmethod
    def _owned_session_id(session_id: str, caller_id: str) -> str:
        """Keep durable episodes isolated by both caller and caller session."""
        clean_caller = caller_id.strip()
        clean_session = session_id.strip()
        if not clean_caller or not clean_session:
            raise ValueError("Sarathi history requires caller_id and session_id")
        return (
            "sarathi:"
            f"{quote(clean_caller, safe='')}:"
            f"{quote(clean_session, safe='')}"
        )

    async def load_history(
        self,
        session_id: str,
        *,
        caller_id: str,
        limit: int = 20,
    ) -> tuple[Mapping[str, Any], ...]:
        events = await self.runtime_state.list_session_events(
            session_id=self._owned_session_id(session_id, caller_id),
            ledger_kind="sarathi_turn",
            limit=max(1, int(limit)),
        )
        history: list[Mapping[str, Any]] = []
        for event in reversed(events):
            if event.event_name not in {"sarathi_input", "sarathi_reply"}:
                continue
            role = "user"
            if event.event_name == "sarathi_reply":
                receipts = await self.runtime_state.list_runtime_receipts(
                    run_id=event.run_id,
                    receipt_type="sarathi_turn",
                    limit=1,
                )
                if not any(
                    receipt.status == TurnStatus.COMPLETED.value
                    for receipt in receipts
                ):
                    continue
                role = "assistant"
            history.append(
                {
                    "role": role,
                    "content": event.event_text,
                    "event_id": event.event_id,
                }
            )
        return tuple(history)

    async def record_input(
        self,
        execution_identity: ExecutionIdentity,
        request: SarathiTurnRequest,
    ) -> str:
        event_id = f"{execution_identity.trace_id}:input"
        await self.runtime_state.record_session_event(
            SessionEventRecord(
                event_id=event_id,
                session_id=self._owned_session_id(
                    execution_identity.session_id,
                    request.caller_id,
                ),
                ledger_kind="sarathi_turn",
                event_name="sarathi_input",
                task_id=execution_identity.task_id,
                run_id=execution_identity.run_id,
                agent_id=execution_identity.agent_id,
                summary=request.message[:240],
                event_text=request.message,
                payload={
                    "schema_version": "dharma.sarathi.turn_input.v1",
                    "execution_identity": execution_identity.to_dict(),
                    "caller_id": request.caller_id,
                    "ingress": request.ingress,
                    "effect_intents": [
                        {
                            "kind": intent.kind,
                            "payload": dict(intent.payload),
                        }
                        for intent in request.effect_intents
                    ],
                    "metadata": dict(request.metadata),
                },
            )
        )
        return event_id

    async def record_result(self, result: SarathiTurnResult) -> str:
        event_id = f"{result.turn_id}:reply"
        receipt_id = f"{result.turn_id}:receipt"
        caller_id = str(result.execution_identity.metadata.get("caller_id") or "")
        await self.runtime_state.record_session_event(
            SessionEventRecord(
                event_id=event_id,
                session_id=self._owned_session_id(result.session_id, caller_id),
                ledger_kind="sarathi_turn",
                event_name="sarathi_reply",
                task_id=result.execution_identity.task_id,
                run_id=result.execution_identity.run_id,
                agent_id=result.execution_identity.agent_id,
                summary=result.reply[:240],
                event_text=result.reply,
                payload=result.to_dict(),
            )
        )
        # ``result`` is intentionally UNRECORDED until this write succeeds.
        # The durable receipt is the commit point and therefore records the
        # post-commit status/ref that the shell may return to its caller.
        committed_status = (
            TurnStatus.COMPLETED
            if result.status is TurnStatus.UNRECORDED
            else result.status
        )
        receipt_payload = result.to_dict()
        receipt_payload["status"] = committed_status.value
        receipt_payload["receipt_ref"] = receipt_id
        await self.runtime_state.record_runtime_receipt(
            RuntimeReceipt(
                receipt_id=receipt_id,
                receipt_type="sarathi_turn",
                status=committed_status.value,
                run_id=result.execution_identity.run_id,
                task_id=result.execution_identity.task_id,
                trace_id=result.execution_identity.trace_id,
                correlation_id=result.execution_identity.correlation_id,
                causation_id=result.execution_identity.causation_id,
                parent_run_id=result.execution_identity.parent_run_id,
                agent_id=result.execution_identity.agent_id,
                idempotency_key=result.execution_identity.idempotency_key,
                payload=receipt_payload,
            )
        )
        return receipt_id


__all__ = ["RuntimeStateTurnStore"]
