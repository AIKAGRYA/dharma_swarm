"""Receipt-backed MemoryKernel operator rows.

These rows are read-only projections of governed write receipts and
human-reviewed promotion evidence.
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow


def memory_write_receipts_row(repo_root: Path) -> ControlSurfaceRow:
    try:
        from dharma_swarm.memory_kernel import (
            DEFAULT_WRITE_RECEIPT_PATH,
            load_write_receipt_status,
        )

        status = load_write_receipt_status(repo_root / DEFAULT_WRITE_RECEIPT_PATH)
        row = ControlSurfaceRow(
            id="memory.write_receipts",
            kind="memory_write_receipt",
            label="MemoryKernel Governed Write Receipts",
            authority_role="evidence",
            declared_state="append_only_receipt_api",
            desired_state="direct_mutations_blocked_receipts_append_only",
            observed_state="ready" if status.ready else "blocked",
            coherence_state="bound" if status.ready else "partial",
            priority="p1" if status.ready else "p0",
            owner_module="dharma_swarm/memory_kernel/write_receipts.py",
            truth_owner="MemoryKernel",
            gap_codes=[f"memory_write_receipt_{blocker}" for blocker in status.blockers],
            next_action=(
                ""
                if status.ready
                else "Run make memory-kernel-write-receipt-smoke before canary/live rollout"
            ),
            raw=status.to_json(),
        )
        row.add_evidence(
            "file",
            (
                f"allowed={status.allowed_receipt_count} "
                f"denied_direct={status.denied_direct_mutation_count} "
                f"immutable={status.immutable_log}"
            ),
            status="present" if status.ready else "missing",
            provenance_chain=["MemoryKernel", "write_receipts", "append_only_status"],
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/write_receipts.py", exists=True)
        row.add_source_ref(
            "file",
            status.receipt_path,
            exists=(repo_root / DEFAULT_WRITE_RECEIPT_PATH).exists(),
        )
        return row
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.write_receipts",
            kind="memory_write_receipt",
            label="MemoryKernel Governed Write Receipts",
            owner_module="dharma_swarm/memory_kernel/write_receipts.py",
            error=str(exc),
            next_action="Repair governed write receipt status projection",
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/write_receipts.py", exists=True)
        return row


def memory_promotion_candidate_row(
    repo_root: Path,
    *,
    rollback_engaged: bool,
) -> ControlSurfaceRow:
    try:
        from dharma_swarm.memory_kernel import (
            DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
            load_promotion_status,
        )

        status = load_promotion_status(
            repo_root / DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
            rollback_engaged=rollback_engaged,
        )
        row = ControlSurfaceRow(
            id="memory.live_promotion",
            kind="memory_promotion",
            label="MemoryKernel Human-Gated Promotion Candidate",
            authority_role="evidence",
            declared_state="human_gated_reviewed_receipts",
            desired_state="live_rollout_emits_reviewed_canonical_receipts_only",
            observed_state="ready" if status.promotion_ready else "blocked",
            coherence_state="bound" if status.promotion_ready else "partial",
            priority="p1" if status.promotion_ready else "p0",
            owner_module="dharma_swarm/memory_kernel/promotion_gate.py",
            truth_owner="MemoryKernel",
            gap_codes=[f"memory_promotion_{blocker}" for blocker in status.blockers],
            next_action=(
                ""
                if status.promotion_ready
                else "Run make memory-kernel-promotion-smoke before live rollout"
            ),
            raw=status.to_json(),
        )
        row.add_evidence(
            "file",
            (
                f"reviewed={status.reviewed_receipt_count} "
                f"human_approved={status.human_approved_count} "
                f"rollback={status.rollback_engaged}"
            ),
            status="present" if status.promotion_ready else "missing",
            provenance_chain=["MemoryKernel", "promotion_gate", "reviewed_canonical_receipt"],
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/promotion_gate.py", exists=True)
        row.add_source_ref(
            "file",
            status.receipt_path,
            exists=(repo_root / DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH).exists(),
        )
        return row
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.live_promotion",
            kind="memory_promotion",
            label="MemoryKernel Human-Gated Promotion Candidate",
            owner_module="dharma_swarm/memory_kernel/promotion_gate.py",
            error=str(exc),
            next_action="Repair human-gated promotion receipt status projection",
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/promotion_gate.py", exists=True)
        return row


def _memory_error_row(
    *,
    row_id: str,
    kind: str,
    label: str,
    owner_module: str,
    error: str,
    next_action: str,
) -> ControlSurfaceRow:
    row = ControlSurfaceRow(
        id=row_id,
        kind=kind,
        label=label,
        authority_role="evidence",
        declared_state="read_only_projection",
        desired_state="available",
        observed_state="error",
        coherence_state="drifted",
        priority="p0",
        owner_module=owner_module,
        truth_owner="MemoryKernel",
        gap_codes=[f"{row_id.replace('.', '_')}_error"],
        next_action=next_action,
        raw={"error": error},
    )
    row.add_evidence(
        "process",
        error,
        status="error",
        provenance_chain=["MemoryKernel", row_id, "control_surface_projection"],
    )
    return row
