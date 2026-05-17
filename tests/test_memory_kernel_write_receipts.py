from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from dharma_swarm.memory_kernel.write_receipts import (
    MemoryKernelWritePolicyOutcome,
    MemoryKernelWriteReceiptInput,
    append_write_receipts,
    governed_write_receipt,
    load_write_receipt_status,
    with_digest,
)


def test_write_receipts_are_append_only_and_immutable(tmp_path: Path) -> None:
    path = tmp_path / "write_receipts.jsonl"
    receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:1",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="append proposal only",
            reviewer_state="pending_review",
        )
    )

    append_write_receipts(path, (receipt,))
    append_write_receipts(path, (receipt,))

    status = load_write_receipt_status(path)

    assert status.receipt_count == 2
    assert status.immutable_log is True

    with pytest.raises(ValueError, match="conflicting immutable receipt"):
        append_write_receipts(path, (with_digest(receipt, "bad-digest"),))


def test_write_receipt_timestamp_is_digest_protected(tmp_path: Path) -> None:
    path = tmp_path / "write_receipts.jsonl"
    receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:1",),
            proposed_operation="append_receipt",
            target_surface="memory_kernel.write_receipts",
            reason="append receipt only",
            reviewer_state="human_approved",
        ),
        created_at="2026-05-16T00:00:00Z",
    )
    tampered = replace(receipt, created_at="2026-05-17T00:00:00Z")

    append_write_receipts(path, (tampered,))
    status = load_write_receipt_status(path)

    assert status.immutable_log is False
    assert "write_receipt_log_not_immutable" in status.blockers


def test_write_receipt_policy_blocks_direct_memory_mutation(tmp_path: Path) -> None:
    path = tmp_path / "write_receipts.jsonl"
    denied = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:1",),
            proposed_operation="update",
            target_surface="chetana.projection_store",
            reason="direct write should be denied",
            reviewer_state="human_approved",
        )
    )
    allowed = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:2",),
            proposed_operation="append_receipt",
            target_surface="memory_kernel.write_receipts",
            reason="append receipt only",
            reviewer_state="human_approved",
        )
    )
    append_write_receipts(path, (denied, allowed))
    status = load_write_receipt_status(path)

    assert denied.policy_decision.outcome == MemoryKernelWritePolicyOutcome.DENY
    assert denied.policy_decision.direct_mutation_blocked is True
    assert status.ready is True
    assert status.denied_direct_mutation_count == 1


def test_write_receipt_policy_blocks_camelcase_protected_surfaces() -> None:
    protected_targets = (
        "canonicalStore",
        "ChetanaMemory",
        "promptContext",
        "runtimeState",
        "legacyMemoryDB",
        "vectorStore",
        "projectionStore",
    )

    for target in protected_targets:
        receipt = governed_write_receipt(
            MemoryKernelWriteReceiptInput(
                source_atom_ids=("memory_atom:protected-target",),
                proposed_operation="append_proposal",
                target_surface=target,
                reason="should not target protected memory surfaces",
                reviewer_state="human_approved",
            )
        )

        assert receipt.policy_decision.outcome == MemoryKernelWritePolicyOutcome.DENY
        assert receipt.policy_decision.direct_mutation_blocked is True


def test_source_atom_ids_are_redacted_and_rejected() -> None:
    receipt = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("/Users/dhyana/.dharma/API_KEY=secret-value",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="proposal from sensitive source id",
            reviewer_state="human_approved",
        )
    )

    payload = receipt.to_json()

    assert receipt.policy_decision.outcome == MemoryKernelWritePolicyOutcome.DENY
    assert "source_atom_ids_redacted_or_invalid" in receipt.policy_decision.reasons
    assert "API_KEY" not in str(payload)
    assert "secret-value" not in str(payload)
