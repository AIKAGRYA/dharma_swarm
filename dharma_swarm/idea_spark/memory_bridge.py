"""Candidate -> MemoryKernel governed write/promotion receipt bridge.

Requests memory promotion for a candidate summary WITHOUT mutating protected
memory. Reuses the canonical MemoryKernel chain verbatim (no second receipt
owner): ``governed_write_receipt`` -> ``build_promotion_decision`` ->
``reviewed_canonical_receipt`` -> append-only logs. The reviewed canonical
receipt id is linked back into the lifecycle receipt by ``correlation_id``, so
PR 7 retrieval can recover the memory hop.

Privacy: only a bounded *summary* (title + truncated claim) is ever emitted, and
the source receipt's redaction policy is honored (``link_only`` drops the claim
text entirely). The MemoryKernel layer additionally redacts local paths and
secret-like tokens from every free-text field.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.memory_kernel import (
    REQUIRED_PROMOTION_GATES,
    MemoryKernelPromotionDecision,
    MemoryKernelPromotionDecisionKind,
    MemoryKernelReviewedCanonicalReceipt,
    MemoryKernelWriteReceipt,
    MemoryKernelWriteReceiptInput,
    append_promotion_artifacts,
    append_write_receipts,
    build_promotion_decision,
    governed_write_receipt,
    load_promotion_status,
    reviewed_canonical_receipt,
)

from .paths import (
    memory_canonical_receipts_path,
    memory_decisions_path,
    memory_kernel_dir,
    memory_write_receipts_path,
)
from .schemas import IdeaSparkCandidate, is_valid_lifecycle_id, sanitize_lifecycle_id
from .store import update_lifecycle_receipt

_CANDIDATE_ID_PREFIX = "idea_spark_candidate:"
_CORRELATION_ID_PREFIX = "idea_spark_correlation:"

# Neutral, non-protected receipt surface (a projection log, not a memory store).
WRITE_TARGET_SURFACE = "memory_kernel.promotion_receipts"
DEFAULT_AUTHORITY_SURFACE = "knowledge_authority.shadow_canon"
_SUMMARY_LIMIT = 240


@dataclass(frozen=True)
class MemoryKernelBridgeResult:
    correlation_id: str
    candidate_id: str
    write_receipt: MemoryKernelWriteReceipt
    decision: MemoryKernelPromotionDecision
    canonical_receipt: MemoryKernelReviewedCanonicalReceipt
    write_receipt_id: str
    canonical_receipt_id: str
    promotion_ready: bool
    blockers: tuple[str, ...]
    write_receipt_path: Path
    decision_path: Path
    canonical_receipt_path: Path


def candidate_summary(
    candidate: IdeaSparkCandidate,
    *,
    redaction_policy: str = "none",
    limit: int = _SUMMARY_LIMIT,
) -> str:
    """Bounded, redaction-aware summary string for a candidate."""
    if redaction_policy == "link_only":
        # link_only: no content (title may itself be derived from the body).
        refs = ", ".join(candidate.source_refs[:2])
        return f"idea_spark_candidate {candidate.candidate_id} [link_only; refs: {refs}]"
    title = candidate.title.strip() or candidate.candidate_id
    claim = candidate.claim.strip()
    if redaction_policy in {"summary_only", "pii_redacted"}:
        claim = claim[:limit]
    return f"{title}: {claim}"[: limit + len(title) + 2]


def _source_atom_ids(candidate: IdeaSparkCandidate) -> tuple[str, str]:
    ids = (
        f"{_CANDIDATE_ID_PREFIX}"
        f"{sanitize_lifecycle_id(candidate.candidate_id, max_len=160 - len(_CANDIDATE_ID_PREFIX))}",
        f"{_CORRELATION_ID_PREFIX}"
        f"{sanitize_lifecycle_id(candidate.correlation_id, max_len=160 - len(_CORRELATION_ID_PREFIX))}",
    )
    for sid in ids:
        if not is_valid_lifecycle_id(sid):  # defense-in-depth before governed call
            raise ValueError(f"invalid memory source_atom_id: {sid!r}")
    return ids


def emit_memory_kernel_receipt(
    candidate: IdeaSparkCandidate,
    *,
    state_root: Path | None = None,
    reviewer: str = "operator",
    created_at: str | None = None,
    redaction_policy: str = "none",
    target_authority_surface: str = DEFAULT_AUTHORITY_SURFACE,
    forbidden_roots: tuple[Path, ...] = (),
    approve: bool = False,
) -> MemoryKernelBridgeResult:
    """Emit a governed memory promotion REQUEST for a candidate.

    By default (``approve=False``) this only *requests* promotion: the write
    receipt is ``pending_review`` and the canonical receipt is BLOCKED
    (not promotion-ready) — ``human_approved`` is NOT minted without a human.
    A real reviewer action (``approve=True``, with a ``reviewer``) is required to
    emit a REVIEWED canonical receipt. Either way no protected memory is mutated.
    """
    summary = candidate_summary(candidate, redaction_policy=redaction_policy)
    source_atom_ids = _source_atom_ids(candidate)
    reviewer_state = "human_approved" if approve else "pending_review"

    write_request = MemoryKernelWriteReceiptInput(
        source_atom_ids=source_atom_ids,
        proposed_operation="append_proposal",
        target_surface=WRITE_TARGET_SURFACE,
        reason=f"Operator Idea Spark candidate summary :: {summary}",
        reviewer_state=reviewer_state,
    )
    write_receipt = governed_write_receipt(write_request, created_at=created_at)

    memory_kernel_dir(state_root, ensure=True)
    write_path = memory_write_receipts_path(state_root)
    decision_path = memory_decisions_path(state_root)
    canonical_path = memory_canonical_receipts_path(state_root)

    append_write_receipts(write_path, (write_receipt,), forbidden_roots=forbidden_roots)

    decision = build_promotion_decision(
        write_receipt_id=write_receipt.receipt_id,
        reviewer=reviewer,
        rationale=f"Idea Spark promotion review :: {summary}",
        approved_gates=REQUIRED_PROMOTION_GATES if approve else (),
        decision=(
            MemoryKernelPromotionDecisionKind.APPROVE
            if approve
            else MemoryKernelPromotionDecisionKind.DEFER
        ),
        source_proposal_id=candidate.candidate_id,
        source_decision_id=candidate.correlation_id,
        target_authority_surface=target_authority_surface,
        created_at=created_at,
    )
    canonical = reviewed_canonical_receipt(
        write_receipt.to_json(), decision, created_at=created_at
    )
    append_promotion_artifacts(
        decision_path=decision_path,
        canonical_receipt_path=canonical_path,
        decisions=(decision,),
        canonical_receipts=(canonical,),
        forbidden_roots=forbidden_roots,
    )

    status = load_promotion_status(canonical_path)

    # A pending request is not a lifecycle blocker; only surface genuine
    # blockers when an approval was claimed yet the gate still blocked it.
    lifecycle_blockers = list(canonical.blockers) if approve else []
    update_lifecycle_receipt(
        candidate.correlation_id,
        state_root,
        status="staged",
        created_at=created_at,
        candidate_id=candidate.candidate_id,
        memory_write_receipt_id=write_receipt.receipt_id,
        memory_canonical_receipt_id=canonical.canonical_receipt_id,
        owner_surface=candidate.owner_surface,
        evidence_paths=[str(write_path), str(decision_path), str(canonical_path)],
        blockers=lifecycle_blockers,
    )

    return MemoryKernelBridgeResult(
        correlation_id=candidate.correlation_id,
        candidate_id=candidate.candidate_id,
        write_receipt=write_receipt,
        decision=decision,
        canonical_receipt=canonical,
        write_receipt_id=write_receipt.receipt_id,
        canonical_receipt_id=canonical.canonical_receipt_id,
        promotion_ready=status.promotion_ready,
        blockers=canonical.blockers,
        write_receipt_path=write_path,
        decision_path=decision_path,
        canonical_receipt_path=canonical_path,
    )
