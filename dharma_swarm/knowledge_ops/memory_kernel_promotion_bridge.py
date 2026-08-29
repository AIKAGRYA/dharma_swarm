"""Bridge KnowledgeOps promotion decisions into MemoryKernel receipts.

This module preserves the read-only KnowledgeOps review path while adding a
governed MemoryKernel receipt chain for accepted proposals. It emits artifacts
only; it does not mutate canon, Chetana, prompt context, vectors, projections,
runtime state, or legacy memory stores.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecision as KnowledgeOpsPromotionDecision,
    MemoryPromotionDecisionKind as KnowledgeOpsPromotionDecisionKind,
    MemoryPromotionDecisionLedger,
    MemoryPromotionDecisionValidity,
)
from dharma_swarm.knowledge_ops.memory_promotion_executor import (
    MemoryPromotionDryRunResult,
    MemoryPromotionReceipt,
    MemoryPromotionRequest,
    append_memory_promotion_artifacts,
    execute_memory_promotion_dry_run,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionProposalQueue,
)
from dharma_swarm.memory_kernel.context_admission import safe_context_ref
from dharma_swarm.memory_kernel.promotion_gate import (
    MemoryKernelPromotionDecision,
    MemoryKernelPromotionReceiptStatus,
    MemoryKernelReviewedCanonicalReceipt,
    append_promotion_artifacts,
    build_promotion_decision,
    reviewed_canonical_receipt,
)
from dharma_swarm.memory_kernel.write_receipts import (
    MemoryKernelWriteReceipt,
    MemoryKernelWriteReceiptInput,
    append_write_receipts,
    governed_write_receipt,
)


DEFAULT_BRIDGE_WRITE_RECEIPT_TARGET = "memory_kernel.promotion_receipts"


@dataclass(frozen=True)
class MemoryKernelPromotionBridgeRecord:
    proposal_id: str
    knowledgeops_decision_id: str
    dry_run_request_id: str
    dry_run_receipt_id: str
    write_receipt: MemoryKernelWriteReceipt
    promotion_decision: MemoryKernelPromotionDecision
    canonical_receipt: MemoryKernelReviewedCanonicalReceipt

    def to_json(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "knowledgeops_decision_id": self.knowledgeops_decision_id,
            "dry_run_request_id": self.dry_run_request_id,
            "dry_run_receipt_id": self.dry_run_receipt_id,
            "write_receipt": self.write_receipt.to_json(),
            "promotion_decision": self.promotion_decision.to_json(),
            "canonical_receipt": self.canonical_receipt.to_json(),
        }


@dataclass(frozen=True)
class MemoryKernelPromotionBridgeResult:
    target_authority_surface: str
    write_receipt_target_surface: str
    accepted_decision_count: int
    bridge_record_count: int
    write_receipt_count: int
    canonical_receipt_count: int
    blocked_canonical_receipt_count: int
    dry_run_result: MemoryPromotionDryRunResult
    records: tuple[MemoryKernelPromotionBridgeRecord, ...]
    warnings: tuple[str, ...] = ()

    @property
    def write_receipts(self) -> tuple[MemoryKernelWriteReceipt, ...]:
        return tuple(record.write_receipt for record in self.records)

    @property
    def promotion_decisions(self) -> tuple[MemoryKernelPromotionDecision, ...]:
        return tuple(record.promotion_decision for record in self.records)

    @property
    def canonical_receipts(self) -> tuple[MemoryKernelReviewedCanonicalReceipt, ...]:
        return tuple(record.canonical_receipt for record in self.records)

    def to_json(self) -> dict[str, object]:
        return {
            "target_authority_surface": self.target_authority_surface,
            "write_receipt_target_surface": self.write_receipt_target_surface,
            "accepted_decision_count": self.accepted_decision_count,
            "bridge_record_count": self.bridge_record_count,
            "write_receipt_count": self.write_receipt_count,
            "canonical_receipt_count": self.canonical_receipt_count,
            "blocked_canonical_receipt_count": self.blocked_canonical_receipt_count,
            "warnings": self.warnings,
            "dry_run_result": self.dry_run_result.to_json(),
            "records": [record.to_json() for record in self.records],
        }


def execute_memory_kernel_promotion_bridge(
    queue: MemoryPromotionProposalQueue,
    ledger: MemoryPromotionDecisionLedger,
    *,
    target_authority_surface: str,
    write_receipt_target_surface: str = DEFAULT_BRIDGE_WRITE_RECEIPT_TARGET,
    rollback_engaged: bool = False,
) -> MemoryKernelPromotionBridgeResult:
    dry_run = execute_memory_promotion_dry_run(
        queue,
        ledger,
        target_authority_surface=target_authority_surface,
    )
    safe_target = safe_context_ref(target_authority_surface.strip())
    safe_write_target = safe_context_ref(write_receipt_target_surface.strip())
    decision_by_proposal = _valid_accept_decisions_by_proposal(ledger)
    receipt_by_request_id = {
        receipt.request_id: receipt for receipt in dry_run.receipts
    }
    records = []
    for request in dry_run.requests:
        decision = decision_by_proposal.get(request.proposal_id)
        receipt = receipt_by_request_id.get(request.request_id)
        if decision is None or receipt is None:
            continue
        records.append(
            _bridge_record(
                request=request,
                receipt=receipt,
                decision=decision,
                target_authority_surface=safe_target,
                write_receipt_target_surface=safe_write_target,
                rollback_engaged=rollback_engaged,
            )
        )
    blocked = tuple(
        record
        for record in records
        if record.canonical_receipt.status == MemoryKernelPromotionReceiptStatus.BLOCKED
    )
    warnings = [
        "knowledgeops_decisions_linked_to_memorykernel_receipts",
        "bridge_artifacts_only_no_memory_or_canon_mutation",
    ]
    if dry_run.request_count != len(records):
        warnings.append("some_dry_run_requests_not_bridged")
    if blocked:
        warnings.append("some_canonical_receipts_blocked")
    return MemoryKernelPromotionBridgeResult(
        target_authority_surface=safe_target,
        write_receipt_target_surface=safe_write_target,
        accepted_decision_count=dry_run.accepted_decision_count,
        bridge_record_count=len(records),
        write_receipt_count=len(records),
        canonical_receipt_count=len(records),
        blocked_canonical_receipt_count=len(blocked),
        dry_run_result=dry_run,
        records=tuple(records),
        warnings=tuple(warnings),
    )


def append_memory_kernel_promotion_bridge_artifacts(
    result: MemoryKernelPromotionBridgeResult,
    *,
    write_receipt_path: Path | None,
    decision_path: Path | None,
    canonical_receipt_path: Path | None,
    dry_run_request_path: Path | None = None,
    dry_run_receipt_path: Path | None = None,
    forbidden_roots: Iterable[Path] = (),
) -> None:
    if dry_run_request_path is not None or dry_run_receipt_path is not None:
        append_memory_promotion_artifacts(
            result.dry_run_result,
            request_path=dry_run_request_path,
            receipt_path=dry_run_receipt_path,
            forbidden_roots=forbidden_roots,
        )
    if write_receipt_path is not None:
        append_write_receipts(
            write_receipt_path,
            result.write_receipts,
            forbidden_roots=forbidden_roots,
        )
    append_promotion_artifacts(
        decision_path=decision_path,
        canonical_receipt_path=canonical_receipt_path,
        decisions=result.promotion_decisions,
        canonical_receipts=result.canonical_receipts,
        forbidden_roots=forbidden_roots,
    )


def knowledgeops_promotion_decision_id(
    decision: KnowledgeOpsPromotionDecision,
) -> str:
    digest = hashlib.sha256(
        json.dumps(decision.to_json(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"knowledgeops_promotion_decision:{digest[:24]}"


def _bridge_record(
    *,
    request: MemoryPromotionRequest,
    receipt: MemoryPromotionReceipt,
    decision: KnowledgeOpsPromotionDecision,
    target_authority_surface: str,
    write_receipt_target_surface: str,
    rollback_engaged: bool,
) -> MemoryKernelPromotionBridgeRecord:
    knowledgeops_decision_id = knowledgeops_promotion_decision_id(decision)
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=request.source_atom_ids,
            proposed_operation="append_proposal",
            target_surface=write_receipt_target_surface,
            reason=(
                "KnowledgeOps accepted promotion proposal "
                f"{request.proposal_id} via dry-run request {request.request_id}"
            ),
            reviewer_state="human_approved",
        )
    )
    promotion_decision = build_promotion_decision(
        write_receipt_id=write_receipt.receipt_id,
        human_approved=bool(str(request.reviewer).strip()),
        rationale=request.rationale,
        source_proposal_id=request.proposal_id,
        source_decision_id=knowledgeops_decision_id,
        target_authority_surface=target_authority_surface,
    )
    canonical_receipt = reviewed_canonical_receipt(
        write_receipt.to_json(),
        promotion_decision,
        rollback_engaged=rollback_engaged,
    )
    return MemoryKernelPromotionBridgeRecord(
        proposal_id=request.proposal_id,
        knowledgeops_decision_id=knowledgeops_decision_id,
        dry_run_request_id=request.request_id,
        dry_run_receipt_id=receipt.receipt_id,
        write_receipt=write_receipt,
        promotion_decision=promotion_decision,
        canonical_receipt=canonical_receipt,
    )


def _valid_accept_decisions_by_proposal(
    ledger: MemoryPromotionDecisionLedger,
) -> dict[str, KnowledgeOpsPromotionDecision]:
    decisions: dict[str, KnowledgeOpsPromotionDecision] = {}
    for decision, review in zip(ledger.decisions, ledger.reviews, strict=True):
        if decision.decision != KnowledgeOpsPromotionDecisionKind.ACCEPT:
            continue
        if review.validity != MemoryPromotionDecisionValidity.VALID:
            continue
        decisions.setdefault(decision.proposal_id, decision)
    return decisions
