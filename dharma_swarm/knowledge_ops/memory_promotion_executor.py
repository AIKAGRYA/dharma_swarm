"""Dry-run MemoryKernel promotion request and receipt artifacts.

This module validates accepted KnowledgeOps decisions and emits append-only
artifact records. It does not write to MemoryKernel, Chetana, canon, vector,
runtime, or projection surfaces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecisionKind,
    MemoryPromotionDecisionLedger,
    MemoryPromotionDecisionValidity,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionProposal,
    MemoryPromotionProposalQueue,
    MemoryPromotionQueueStatus,
)
from dharma_swarm.memory_kernel.context_admission import (
    redact_context_text,
    safe_context_ref,
)


_PROMOTABLE_TRUTH_STATES = {"observed", "curated"}
_HIGH_RISK_VALUES = {"high", "critical"}


class MemoryPromotionExecutionMode(StrEnum):
    DRY_RUN = "dry_run"


class MemoryPromotionReceiptStatus(StrEnum):
    DRY_RUN_EMITTED = "dry_run_emitted"


@dataclass(frozen=True)
class MemoryPromotionRollbackMetadata:
    rollback_id: str
    rollback_mode: str
    tombstone_required: bool
    reason: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryPromotionTombstoneMetadata:
    tombstone_id: str
    applies_to_request_id: str
    tombstone_mode: str
    reason: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryPromotionRequest:
    request_id: str
    idempotency_key: str
    execution_mode: MemoryPromotionExecutionMode
    proposal_id: str
    source_atom_ids: tuple[str, ...]
    source_surface_ids: tuple[str, ...]
    target_authority_surface: str
    reviewer: str
    rationale: str
    approved_gates: tuple[str, ...]
    required_gates: tuple[str, ...]
    rollback_metadata: MemoryPromotionRollbackMetadata
    tombstone_metadata: MemoryPromotionTombstoneMetadata
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["execution_mode"] = self.execution_mode.value
        payload["rollback_metadata"] = self.rollback_metadata.to_json()
        payload["tombstone_metadata"] = self.tombstone_metadata.to_json()
        return payload


@dataclass(frozen=True)
class MemoryPromotionReceipt:
    receipt_id: str
    request_id: str
    idempotency_key: str
    status: MemoryPromotionReceiptStatus
    execution_mode: MemoryPromotionExecutionMode
    source_atom_ids: tuple[str, ...]
    target_authority_surface: str
    mutation_performed: bool
    artifact_record_only: bool
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["execution_mode"] = self.execution_mode.value
        return payload


@dataclass(frozen=True)
class MemoryPromotionDryRunResult:
    target_authority_surface: str
    accepted_decision_count: int
    request_count: int
    receipt_count: int
    skipped_decision_count: int
    duplicate_accept_count: int
    requests: tuple[MemoryPromotionRequest, ...]
    receipts: tuple[MemoryPromotionReceipt, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "target_authority_surface": self.target_authority_surface,
            "accepted_decision_count": self.accepted_decision_count,
            "request_count": self.request_count,
            "receipt_count": self.receipt_count,
            "skipped_decision_count": self.skipped_decision_count,
            "duplicate_accept_count": self.duplicate_accept_count,
            "warnings": self.warnings,
            "requests": [request.to_json() for request in self.requests],
            "receipts": [receipt.to_json() for receipt in self.receipts],
        }


def execute_memory_promotion_dry_run(
    queue: MemoryPromotionProposalQueue,
    ledger: MemoryPromotionDecisionLedger,
    *,
    target_authority_surface: str,
) -> MemoryPromotionDryRunResult:
    """Validate accepted decisions and build non-mutating promotion artifacts."""

    safe_target = safe_context_ref(target_authority_surface.strip())
    proposal_by_id = {proposal.proposal_id: proposal for proposal in queue.proposals}
    requests: list[MemoryPromotionRequest] = []
    receipts: list[MemoryPromotionReceipt] = []
    accepted_decisions = 0
    skipped_decisions = 0
    duplicate_accepts = 0
    seen_idempotency_keys: set[str] = set()

    for decision, review in zip(ledger.decisions, ledger.reviews, strict=True):
        if decision.decision != MemoryPromotionDecisionKind.ACCEPT:
            skipped_decisions += 1
            continue
        accepted_decisions += 1
        if review.validity != MemoryPromotionDecisionValidity.VALID:
            skipped_decisions += 1
            continue
        proposal = proposal_by_id.get(decision.proposal_id)
        if proposal is None or _proposal_blockers(proposal):
            skipped_decisions += 1
            continue

        idempotency_key = _idempotency_key(
            proposal=proposal,
            target_authority_surface=target_authority_surface,
        )
        if idempotency_key in seen_idempotency_keys:
            duplicate_accepts += 1
            skipped_decisions += 1
            continue
        seen_idempotency_keys.add(idempotency_key)

        request = _request_from_decision(
            proposal=proposal,
            reviewer=decision.reviewer,
            rationale=decision.rationale,
            approved_gates=decision.approved_gates,
            target_authority_surface=safe_target,
            idempotency_key=idempotency_key,
        )
        requests.append(request)
        receipts.append(_receipt_from_request(request))

    warnings = [
        "dry_run_no_memory_or_canon_mutation",
        "requests_and_receipts_are_append_only_artifacts",
        "rejected_deferred_invalid_and_duplicate_decisions_do_not_promote",
    ]
    if skipped_decisions:
        warnings.append("some_decisions_skipped")
    return MemoryPromotionDryRunResult(
        target_authority_surface=safe_target,
        accepted_decision_count=accepted_decisions,
        request_count=len(requests),
        receipt_count=len(receipts),
        skipped_decision_count=skipped_decisions,
        duplicate_accept_count=duplicate_accepts,
        requests=tuple(requests),
        receipts=tuple(receipts),
        warnings=tuple(warnings),
    )


def append_memory_promotion_artifacts(
    result: MemoryPromotionDryRunResult,
    *,
    request_path: Path | None,
    receipt_path: Path | None,
    forbidden_roots: Iterable[Path] = (),
) -> None:
    """Append request and receipt JSONL records outside memory surfaces."""

    roots = tuple(root.expanduser().resolve() for root in forbidden_roots)
    if request_path is not None:
        _append_jsonl(request_path, (request.to_json() for request in result.requests), roots)
    if receipt_path is not None:
        _append_jsonl(receipt_path, (receipt.to_json() for receipt in result.receipts), roots)


def _request_from_decision(
    *,
    proposal: MemoryPromotionProposal,
    reviewer: str,
    rationale: str,
    approved_gates: tuple[str, ...],
    target_authority_surface: str,
    idempotency_key: str,
) -> MemoryPromotionRequest:
    request_id = _stable_id("memory_promotion_request", idempotency_key)
    rollback = MemoryPromotionRollbackMetadata(
        rollback_id=_stable_id("memory_promotion_rollback", request_id),
        rollback_mode="append_tombstone_receipt",
        tombstone_required=True,
        reason="dry_run_artifact_can_be_countermanded_without_memory_mutation",
    )
    tombstone = MemoryPromotionTombstoneMetadata(
        tombstone_id=_stable_id("memory_promotion_tombstone", request_id),
        applies_to_request_id=request_id,
        tombstone_mode="append_only_no_delete",
        reason="supersession_or_reviewer_withdrawal_records_a_tombstone_artifact",
    )
    return MemoryPromotionRequest(
        request_id=request_id,
        idempotency_key=idempotency_key,
        execution_mode=MemoryPromotionExecutionMode.DRY_RUN,
        proposal_id=proposal.proposal_id,
        source_atom_ids=(proposal.atom_id,),
        source_surface_ids=(proposal.surface_id,),
        target_authority_surface=target_authority_surface,
        reviewer=redact_context_text(reviewer.strip()),
        rationale=redact_context_text(rationale.strip()),
        approved_gates=tuple(sorted(set(approved_gates))),
        required_gates=proposal.required_gates,
        rollback_metadata=rollback,
        tombstone_metadata=tombstone,
        warnings=(
            "artifact_only_no_target_surface_write",
            "source_content_not_serialized",
        ),
    )


def _receipt_from_request(request: MemoryPromotionRequest) -> MemoryPromotionReceipt:
    return MemoryPromotionReceipt(
        receipt_id=_stable_id("memory_promotion_receipt", request.request_id),
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        status=MemoryPromotionReceiptStatus.DRY_RUN_EMITTED,
        execution_mode=MemoryPromotionExecutionMode.DRY_RUN,
        source_atom_ids=request.source_atom_ids,
        target_authority_surface=request.target_authority_surface,
        mutation_performed=False,
        artifact_record_only=True,
        warnings=(
            "no_live_promotion_performed",
            "receipt_confirms_artifact_emission_only",
        ),
    )


def _proposal_blockers(proposal: MemoryPromotionProposal) -> tuple[str, ...]:
    blockers: list[str] = []
    if proposal.status != MemoryPromotionQueueStatus.READY_FOR_REVIEW:
        blockers.append("proposal_not_ready_for_review")
    if proposal.truth_state not in _PROMOTABLE_TRUTH_STATES:
        blockers.append("non_promotable_truth_state")
    if proposal.source_review_status in {"superseded", "contested"}:
        blockers.append(f"{proposal.source_review_status}_atom")
    if proposal.canon_risk in _HIGH_RISK_VALUES:
        blockers.append("high_canon_risk")
    if proposal.pii_risk in _HIGH_RISK_VALUES:
        blockers.append("high_pii_risk")
    if proposal.projection_of:
        blockers.append("projection_not_authority")
    if proposal.has_content:
        blockers.append("content_bearing_atom")
    if not proposal.atom_id or not proposal.surface_id:
        blockers.append("missing_source_identity")
    if not proposal.required_gates:
        blockers.append("missing_required_gates")
    return tuple(blockers)


def _append_jsonl(
    path: Path,
    rows: Iterable[dict[str, object]],
    forbidden_roots: tuple[Path, ...],
) -> None:
    resolved = path.expanduser().resolve()
    for root in forbidden_roots:
        if _is_relative_to(resolved, root):
            raise ValueError("promotion artifact outputs under memory surfaces are not allowed")
    materialized = tuple(rows)
    if not materialized:
        return
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(_safe_json_text(row) + "\n")


def _idempotency_key(
    *,
    proposal: MemoryPromotionProposal,
    target_authority_surface: str,
) -> str:
    return _stable_id(
        "memory_promotion_idempotency",
        proposal.proposal_id,
        proposal.atom_id,
        proposal.surface_id,
        target_authority_surface,
    )


def _safe_json_text(payload: object) -> str:
    return redact_context_text(json.dumps(payload, sort_keys=True))


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
