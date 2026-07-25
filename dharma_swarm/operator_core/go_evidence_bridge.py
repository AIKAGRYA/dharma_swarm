"""Bridge Go evidence receipts into the file-native closure v0 proof path.

This module is deliberately read-only: it parses sidecar receipts and maps
their payload into existing operator facts. It does not write canonical state,
create WorkPackets, dispatch agents, or mutate ontology/runtime databases.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.closure_v0 import ClosureEvidenceReceipt, WorkPacket, record_evidence_receipt
from dharma_swarm.operator_core.go_receipt_identity import (
    GoReceiptIdentityError,
    verify_identity_chain,
)
from dharma_swarm.operator_core.operating_facts import AgentOpsRunFact


GO_EVIDENCE_SCHEMA_V0 = "go_evidence_receipt.v0"


class GoEvidenceBridgeError(ValueError):
    """Raised when a Go sidecar receipt cannot be admitted to closure v0."""


@dataclass(frozen=True)
class GoEvidenceReceipt:
    receipt_id: str
    correlation_id: str
    source: str
    source_url: str
    observed_at: str
    content_hash: str
    event_uid: str
    schema_version: str
    status: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        required = (
            self.receipt_id,
            self.correlation_id,
            self.source,
            self.source_url,
            self.observed_at,
            self.content_hash,
            self.event_uid,
            self.schema_version,
            self.status,
        )
        if not all(required):
            raise GoEvidenceBridgeError("GoEvidenceReceipt missing required identity fields")
        if self.schema_version != GO_EVIDENCE_SCHEMA_V0:
            raise GoEvidenceBridgeError(f"unsupported Go evidence schema: {self.schema_version}")
        if self.status != "accepted":
            raise GoEvidenceBridgeError(f"Go receipt is not accepted: {self.status}")
        try:
            verify_identity_chain(
                source=self.source,
                source_url=self.source_url,
                content_hash_value=self.content_hash,
                correlation_id=self.correlation_id,
                event_uid=self.event_uid,
                receipt_id=self.receipt_id,
            )
        except GoReceiptIdentityError as exc:
            raise GoEvidenceBridgeError(str(exc)) from exc


def load_go_evidence_receipt(path: Path) -> GoEvidenceReceipt:
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise GoEvidenceBridgeError("Go receipt payload must be a JSON object")
    return GoEvidenceReceipt(
        receipt_id=str(raw.get("receipt_id", "")),
        correlation_id=str(raw.get("correlation_id", "")),
        source=str(raw.get("source", "")),
        source_url=str(raw.get("source_url", "")),
        observed_at=str(raw.get("observed_at", "")),
        content_hash=str(raw.get("content_hash", "")),
        event_uid=str(raw.get("event_uid", "")),
        schema_version=str(raw.get("schema_version", "")),
        status=str(raw.get("status", "")),
        payload=payload,
    )


def agentops_fact_from_go_receipt(receipt: GoEvidenceReceipt) -> AgentOpsRunFact:
    """Map a Go receipt payload into the existing AgentOps fact membrane."""
    p = receipt.payload
    return AgentOpsRunFact(
        source_path=str(p.get("source_path") or receipt.source_url),
        job_id=str(p.get("job_id", "")),
        status=str(p.get("status", "")),
        branch=str(p.get("branch", "")),
        worktree=str(p.get("worktree", "")),
        gate_state=str(p.get("gate_state", "unknown")),
        scope_state=str(p.get("scope_state", "unknown")),
        commit_state=str(p.get("commit_state", "")),
        approval_state=str(p.get("approval_state", "")),
        changed_files=tuple(str(v) for v in p.get("changed_files", ())),
        scope_violations=tuple(str(v) for v in p.get("scope_violations", ())),
        failed_gates=tuple(str(v) for v in p.get("failed_gates", ())),
        commit_hash=p.get("commit_hash"),
    )


def closure_evidence_from_go_receipt(
    packet: WorkPacket,
    receipt: GoEvidenceReceipt,
    *,
    created_at: str,
    duration_ms: float = 0.0,
) -> ClosureEvidenceReceipt:
    """Project a Go sidecar receipt into closure_v0 evidence.

    Go stays outside the decision loop; Python performs the closure projection.
    """
    return record_evidence_receipt(
        packet,
        agentops_fact_from_go_receipt(receipt),
        correlation_id=receipt.correlation_id,
        created_at=created_at,
        duration_ms=duration_ms,
    )
