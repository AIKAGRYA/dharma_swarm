"""Durable approval queue for VentureCell external actions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from dharma_swarm.venture_cell.domain_ceo import DomainCEOContract, DomainCEOContractError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExternalActionKind(StrEnum):
    OUTREACH = "outreach"
    PUBLICATION = "publication"
    PAYMENT = "payment"
    ON_CHAIN_TRANSACTION = "on_chain_transaction"
    PROCUREMENT_INTRO = "procurement_intro"
    PARTNER_CLAIM = "partner_claim"
    CAPITAL_SIGNAL = "capital_signal"


class ExternalActionStatus(StrEnum):
    DRAFTED = "drafted"
    RISK_REVIEWED = "risk_reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class ExternalActionDecision:
    decided_by: str
    decision: str
    reason: str
    decided_at: str = field(default_factory=_now_iso)


@dataclass
class ExternalActionRequest:
    cell_id: str
    kind: ExternalActionKind
    title: str
    requested_by: str
    payload: dict[str, object] = field(default_factory=dict)
    risk_notes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    idempotency_key: str = ""
    request_id: str = field(default_factory=lambda: f"ext_{uuid4().hex[:16]}")
    status: ExternalActionStatus = ExternalActionStatus.DRAFTED
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    decision: ExternalActionDecision | None = None
    execution_receipt_id: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["status"] = self.status.value
        return payload


class ExternalActionQueue:
    """Append-only approval queue.

    The in-memory index is convenience only. The JSONL event log is the durable
    receipt trail for draft, risk review, approval/rejection, and execution.
    """

    def __init__(self, contract: DomainCEOContract, event_log_path: str | Path):
        self.contract = contract
        self.event_log_path = Path(event_log_path)
        self._requests: dict[str, ExternalActionRequest] = {}

    def draft(self, request: ExternalActionRequest) -> ExternalActionRequest:
        if request.cell_id != self.contract.cell_id:
            raise DomainCEOContractError("external action cell_id does not match CEO contract")
        self.contract.check_external_action(request.kind.value)
        if not request.idempotency_key:
            raise DomainCEOContractError("external action requires idempotency_key")
        if request.kind in (
            ExternalActionKind.PUBLICATION,
            ExternalActionKind.PARTNER_CLAIM,
            ExternalActionKind.CAPITAL_SIGNAL,
        ):
            self.contract.data_policy.validate_public_payload(request.payload)
        self._requests[request.request_id] = request
        self._append_event("drafted", request)
        return request

    def risk_review(self, request_id: str, *, reviewer: str, notes: list[str]) -> ExternalActionRequest:
        request = self._get(request_id)
        if request.status != ExternalActionStatus.DRAFTED:
            raise DomainCEOContractError("only drafted actions can be risk-reviewed")
        if not reviewer:
            raise DomainCEOContractError("risk reviewer is required")
        request.risk_notes.extend(notes)
        request.status = ExternalActionStatus.RISK_REVIEWED
        request.updated_at = _now_iso()
        self._append_event("risk_reviewed", request, actor=reviewer)
        return request

    def decide(
        self,
        request_id: str,
        *,
        decision: str,
        decided_by: str,
        reason: str,
    ) -> ExternalActionRequest:
        request = self._get(request_id)
        if request.status != ExternalActionStatus.RISK_REVIEWED:
            raise DomainCEOContractError("approval requires risk_reviewed status")
        if decided_by != self.contract.human_governor:
            raise DomainCEOContractError("only the human_governor may approve/reject")
        if decision not in {"approved", "rejected"}:
            raise DomainCEOContractError("decision must be approved or rejected")
        request.decision = ExternalActionDecision(
            decided_by=decided_by,
            decision=decision,
            reason=reason,
        )
        request.status = (
            ExternalActionStatus.APPROVED
            if decision == "approved"
            else ExternalActionStatus.REJECTED
        )
        request.updated_at = _now_iso()
        self._append_event(decision, request, actor=decided_by)
        return request

    def execute(
        self,
        request_id: str,
        *,
        executor: str,
        execution_receipt_id: str,
    ) -> ExternalActionRequest:
        request = self._get(request_id)
        if request.status != ExternalActionStatus.APPROVED:
            raise DomainCEOContractError("external action cannot execute before approval")
        if not execution_receipt_id:
            raise DomainCEOContractError("execution requires receipt id")
        request.status = ExternalActionStatus.EXECUTED
        request.execution_receipt_id = execution_receipt_id
        request.updated_at = _now_iso()
        self._append_event("executed", request, actor=executor)
        return request

    def withdraw(self, request_id: str, *, actor: str, reason: str) -> ExternalActionRequest:
        request = self._get(request_id)
        if request.status == ExternalActionStatus.EXECUTED:
            raise DomainCEOContractError("executed actions cannot be withdrawn")
        request.status = ExternalActionStatus.WITHDRAWN
        request.updated_at = _now_iso()
        self._append_event("withdrawn", request, actor=actor, reason=reason)
        return request

    def get(self, request_id: str) -> ExternalActionRequest | None:
        return self._requests.get(request_id)

    def _get(self, request_id: str) -> ExternalActionRequest:
        request = self._requests.get(request_id)
        if request is None:
            raise DomainCEOContractError(f"external action not found: {request_id}")
        return request

    def _append_event(
        self,
        event_type: str,
        request: ExternalActionRequest,
        *,
        actor: str = "",
        reason: str = "",
    ) -> None:
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "schema": "venture_cell.external_action_event.v1",
            "event_type": event_type,
            "actor": actor,
            "reason": reason,
            "request": request.to_dict(),
            "created_at": _now_iso(),
        }
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
