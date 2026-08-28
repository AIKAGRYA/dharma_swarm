from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import pytest

from dharma_swarm.memory_kernel.promotion_gate import (
    MemoryKernelPromotionReceiptStatus,
    append_promotion_artifacts,
    build_promotion_decision,
    load_promotion_status,
    reviewed_canonical_receipt,
)
from dharma_swarm.memory_kernel.write_receipts import (
    MemoryKernelWriteReceiptInput,
    canonical_json,
    governed_write_receipt,
)


def test_human_gated_promotion_emits_reviewed_canonical_receipt(tmp_path: Path) -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )
    canonical = reviewed_canonical_receipt(write_receipt, decision)
    path = tmp_path / "canonical.jsonl"

    append_promotion_artifacts(
        decision_path=tmp_path / "decisions.jsonl",
        canonical_receipt_path=path,
        decisions=(decision,),
        canonical_receipts=(canonical,),
    )
    status = load_promotion_status(path)

    assert canonical.status == MemoryKernelPromotionReceiptStatus.REVIEWED
    assert canonical.mutation_performed is False
    assert canonical.artifact_record_only is True
    assert status.promotion_ready is True


def test_rollback_blocks_promotion_receipt(tmp_path: Path) -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )
    canonical = reviewed_canonical_receipt(write_receipt, decision, rollback_engaged=True)
    path = tmp_path / "canonical.jsonl"

    append_promotion_artifacts(
        decision_path=None,
        canonical_receipt_path=path,
        decisions=(),
        canonical_receipts=(canonical,),
    )
    status = load_promotion_status(path, rollback_engaged=True)

    assert canonical.status == MemoryKernelPromotionReceiptStatus.BLOCKED
    assert "rollback_engaged" in canonical.blockers
    assert status.promotion_ready is False
    assert "rollback_engaged" in status.blockers


def test_promotion_timestamp_is_digest_protected(tmp_path: Path) -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )
    canonical = reviewed_canonical_receipt(
        write_receipt,
        decision,
        created_at="2026-05-16T00:00:00Z",
    )
    tampered = replace(canonical, created_at="2026-05-17T00:00:00Z")
    path = tmp_path / "canonical.jsonl"

    append_promotion_artifacts(
        decision_path=None,
        canonical_receipt_path=path,
        decisions=(),
        canonical_receipts=(tampered,),
    )
    status = load_promotion_status(path)

    assert status.promotion_ready is False
    assert "no_human_approved_reviewed_canonical_receipt" in status.blockers


def test_promotion_rechecks_protected_target_even_if_receipt_policy_is_forged() -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    request = dict(write_receipt["request"])
    request["target_surface"] = "canonicalStore"
    write_receipt["request"] = request
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )

    canonical = reviewed_canonical_receipt(write_receipt, decision)

    assert canonical.status == MemoryKernelPromotionReceiptStatus.BLOCKED
    assert "protected_target_surface_not_promotable" in canonical.blockers
    assert "write_receipt_policy_recheck_not_allow" in canonical.blockers


def test_promotion_rejects_invalid_source_atom_ids_even_if_policy_is_forged() -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    request = dict(write_receipt["request"])
    request["source_atom_ids"] = ["<secret_like_redacted>"]
    write_receipt["request"] = request
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )

    canonical = reviewed_canonical_receipt(write_receipt, decision)

    assert canonical.status == MemoryKernelPromotionReceiptStatus.BLOCKED
    assert "source_atom_ids_not_admissible" in canonical.blockers
    assert "write_receipt_policy_recheck_not_allow" in canonical.blockers


def test_promotion_log_rejects_duplicate_id_with_conflicting_digest(tmp_path: Path) -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )
    first = reviewed_canonical_receipt(
        write_receipt,
        decision,
        created_at="2026-05-16T00:00:00Z",
    )
    second = reviewed_canonical_receipt(
        write_receipt,
        decision,
        created_at="2026-05-16T00:00:01Z",
    )
    conflicting = replace(second, canonical_receipt_id=first.canonical_receipt_id)
    path = tmp_path / "canonical.jsonl"

    append_promotion_artifacts(
        decision_path=None,
        canonical_receipt_path=path,
        decisions=(),
        canonical_receipts=(first,),
    )
    with pytest.raises(ValueError, match="conflicting immutable receipt"):
        append_promotion_artifacts(
            decision_path=None,
            canonical_receipt_path=path,
            decisions=(),
            canonical_receipts=(conflicting,),
        )

    path.write_text(
        canonical_json(first.to_json()) + "\n" + canonical_json(conflicting.to_json()) + "\n",
        encoding="utf-8",
    )
    status = load_promotion_status(path)

    assert status.immutable_log is False
    assert status.promotion_ready is False
    assert "promotion_receipt_log_not_immutable" in status.blockers


def test_promotion_log_fails_closed_on_malformed_jsonl(tmp_path: Path) -> None:
    write_receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:promote",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="reviewed proposal",
            reviewer_state="human_approved",
        )
    ).to_json()
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="all gates reviewed",
    )
    canonical = reviewed_canonical_receipt(write_receipt, decision)
    path = tmp_path / "canonical.jsonl"
    path.write_text(
        "{malformed json}\n" + canonical_json(canonical.to_json()) + "\n",
        encoding="utf-8",
    )

    status = load_promotion_status(path)

    assert status.immutable_log is False
    assert status.promotion_ready is False
    assert "promotion_receipt_log_not_immutable" in status.blockers
