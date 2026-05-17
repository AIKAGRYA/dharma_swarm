"""MemoryKernel receipt rows for the operator control surface."""

from __future__ import annotations

import os
from pathlib import Path

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow


ROLLBACK_ENV_VAR = "DHARMA_MEMORY_KERNEL_ROLLBACK"


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
            gap_codes=[
                f"memory_write_receipt_{blocker}"
                for blocker in status.blockers
            ],
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


def memory_promotion_candidate_row(repo_root: Path) -> ControlSurfaceRow:
    try:
        from dharma_swarm.memory_kernel import (
            DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
            load_promotion_status,
        )

        rollback_engaged = _truthy(os.environ.get(ROLLBACK_ENV_VAR, ""))
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
            gap_codes=[
                f"memory_promotion_{blocker}"
                for blocker in status.blockers
            ],
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


def memory_knowledgeops_bridge_row(repo_root: Path) -> ControlSurfaceRow:
    try:
        from dharma_swarm.memory_kernel import (
            DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
            DEFAULT_WRITE_RECEIPT_PATH,
            load_write_receipts,
        )
        from dharma_swarm.memory_kernel.promotion_gate import load_canonical_receipts

        write_path = repo_root / DEFAULT_WRITE_RECEIPT_PATH
        canonical_path = repo_root / DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH
        write_receipts, write_immutable = load_write_receipts(write_path)
        canonical_receipts, canonical_immutable = load_canonical_receipts(canonical_path)
        write_receipt_ids = {
            str(row.get("receipt_id", ""))
            for row in write_receipts
            if isinstance(row, dict)
        }
        linked = tuple(
            row for row in canonical_receipts if _has_knowledgeops_bridge_link(row)
        )
        matched = tuple(
            row
            for row in linked
            if str(row.get("source_write_receipt_id", "")) in write_receipt_ids
        )
        latest = matched[-1] if matched else {}
        blockers: list[str] = []
        if not write_path.exists():
            blockers.append("write_receipt_log_missing")
        if not canonical_path.exists():
            blockers.append("canonical_receipt_log_missing")
        if not write_immutable:
            blockers.append("write_receipt_log_not_immutable")
        if not canonical_immutable:
            blockers.append("canonical_receipt_log_not_immutable")
        if not linked:
            blockers.append("no_linked_knowledgeops_canonical_receipt")
        if linked and not matched:
            blockers.append("linked_write_receipt_missing")
        ready = not blockers
        raw = {
            "schema_version": "memory_kernel_knowledgeops_bridge.v1",
            "ready": ready,
            "blockers": tuple(blockers),
            "write_receipt_path": write_path.as_posix(),
            "canonical_receipt_path": canonical_path.as_posix(),
            "write_receipt_count": len(write_receipts),
            "canonical_receipt_count": len(canonical_receipts),
            "linked_canonical_receipt_count": len(linked),
            "matched_write_receipt_link_count": len(matched),
            "write_receipt_log_immutable": write_immutable,
            "canonical_receipt_log_immutable": canonical_immutable,
            "latest_canonical_receipt_id": str(latest.get("canonical_receipt_id", "")),
            "latest_source_write_receipt_id": str(latest.get("source_write_receipt_id", "")),
            "latest_source_proposal_id": str(latest.get("source_proposal_id", "")),
            "latest_source_decision_id": str(latest.get("source_decision_id", "")),
            "latest_target_authority_surface": str(
                latest.get("target_authority_surface", "")
            ),
        }
        row = ControlSurfaceRow(
            id="memory.knowledgeops_bridge",
            kind="memory_promotion",
            label="KnowledgeOps MemoryKernel Promotion Bridge",
            authority_role="evidence",
            declared_state="knowledgeops_decision_to_canonical_receipt_bridge",
            desired_state="accepted_decisions_link_to_reviewed_canonical_receipts",
            observed_state="ready" if ready else "blocked",
            coherence_state="bound" if ready else "partial",
            priority="p1" if ready else "p0",
            owner_module="dharma_swarm/knowledge_ops/memory_kernel_promotion_bridge.py",
            truth_owner="KnowledgeOps",
            gap_codes=[
                f"memory_knowledgeops_bridge_{blocker}"
                for blocker in blockers
            ],
            next_action=(
                ""
                if ready
                else "Run make memory-kernel-knowledgeops-bridge-smoke before live rollout"
            ),
            raw=raw,
        )
        row.add_evidence(
            "file",
            (
                f"linked={len(linked)} matched={len(matched)} "
                f"immutable={write_immutable and canonical_immutable}"
            ),
            status="present" if ready else "missing",
            provenance_chain=[
                "KnowledgeOps",
                "memory_kernel_promotion_bridge",
                "reviewed_canonical_receipt",
            ],
        )
        row.add_source_ref(
            "file",
            "dharma_swarm/knowledge_ops/memory_kernel_promotion_bridge.py",
            exists=True,
        )
        row.add_source_ref(
            "file",
            "scripts/memory_kernel_knowledgeops_bridge_smoke.py",
            exists=(repo_root / "scripts/memory_kernel_knowledgeops_bridge_smoke.py").exists(),
        )
        row.add_source_ref("file", write_path.as_posix(), exists=write_path.exists())
        row.add_source_ref("file", canonical_path.as_posix(), exists=canonical_path.exists())
        return row
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.knowledgeops_bridge",
            kind="memory_promotion",
            label="KnowledgeOps MemoryKernel Promotion Bridge",
            owner_module="dharma_swarm/knowledge_ops/memory_kernel_promotion_bridge.py",
            error=str(exc),
            next_action="Repair KnowledgeOps-to-MemoryKernel bridge projection",
        )
        row.add_source_ref(
            "file",
            "dharma_swarm/knowledge_ops/memory_kernel_promotion_bridge.py",
            exists=True,
        )
        return row


def _has_knowledgeops_bridge_link(row: dict[str, object]) -> bool:
    return (
        row.get("status") == "reviewed_canonical_receipt"
        and bool(row.get("human_approved"))
        and str(row.get("source_write_receipt_id", "")).startswith(
            "memory_kernel_write_receipt:"
        )
        and str(row.get("source_proposal_id", "")).startswith(
            "memory_promotion_proposal:"
        )
        and str(row.get("source_decision_id", "")).startswith(
            "knowledgeops_promotion_decision:"
        )
        and bool(str(row.get("target_authority_surface", "")).strip())
    )


def _memory_error_row(
    *,
    row_id: str,
    kind: str,
    label: str,
    owner_module: str,
    error: str,
    next_action: str,
) -> ControlSurfaceRow:
    return ControlSurfaceRow(
        id=row_id,
        kind=kind,
        label=label,
        authority_role="adapter",
        declared_state="projectable",
        desired_state="project_without_errors",
        observed_state="error",
        coherence_state="drifted",
        priority="p0",
        owner_module=owner_module,
        truth_owner="MemoryKernel",
        gap_codes=["memory_kernel_projection_error"],
        next_action=next_action,
        raw={"error": error},
    )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "rollback"}
