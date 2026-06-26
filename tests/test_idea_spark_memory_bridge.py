"""PR 4 verifier — candidate -> MemoryKernel governed receipt bridge.

Deterministic, no-network. Proves a candidate can request memory promotion with
no protected-memory mutation, that the reviewed canonical receipt links back to
the lifecycle receipt by correlation_id, and that redaction is preserved.
"""

from __future__ import annotations

from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.memory_bridge import (
    candidate_summary,
    emit_memory_kernel_receipt,
)
from dharma_swarm.idea_spark.projection import candidate_from_operator_receipt
from dharma_swarm.idea_spark.store import load_lifecycle_receipt
from dharma_swarm.memory_kernel import MemoryKernelPromotionReceiptStatus

FIXED_NOW = "2026-06-26T00:00:00Z"


def _candidate(claim: str = NOTE_FIXTURE.content):
    receipt = NOTE_FIXTURE.build_receipt()
    return candidate_from_operator_receipt(receipt, claim=claim, domain="tooling", now=FIXED_NOW)


def test_default_emit_is_a_pending_request_not_auto_approved(tmp_path) -> None:
    # Default path REQUESTS promotion; it must NOT mint human_approved with no human.
    candidate = _candidate()
    result = emit_memory_kernel_receipt(candidate, state_root=tmp_path, created_at=FIXED_NOW)
    assert result.promotion_ready is False
    assert result.canonical_receipt.status == MemoryKernelPromotionReceiptStatus.BLOCKED
    assert result.canonical_receipt.human_approved is False
    # No protected memory mutation either way.
    assert result.write_receipt.mutation_performed is False
    assert result.write_receipt.artifact_record_only is True
    assert result.canonical_receipt.mutation_performed is False
    # Receipt logs land strictly under the supplied state root.
    for path in (result.write_receipt_path, result.decision_path, result.canonical_receipt_path):
        assert path.exists()
        assert str(tmp_path) in str(path)


def test_explicit_approval_yields_promotion_ready(tmp_path) -> None:
    candidate = _candidate()
    result = emit_memory_kernel_receipt(
        candidate, state_root=tmp_path, created_at=FIXED_NOW, approve=True, reviewer="operator"
    )
    assert result.promotion_ready is True
    assert result.blockers == ()
    assert result.canonical_receipt.status == MemoryKernelPromotionReceiptStatus.REVIEWED
    assert result.canonical_receipt.human_approved is True
    assert result.write_receipt.mutation_performed is False


def test_canonical_receipt_links_back_to_candidate(tmp_path) -> None:
    candidate = _candidate()
    result = emit_memory_kernel_receipt(candidate, state_root=tmp_path, created_at=FIXED_NOW)
    assert result.canonical_receipt.source_proposal_id == candidate.candidate_id
    assert result.canonical_receipt.source_decision_id == candidate.correlation_id

    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None
    assert lifecycle.memory_write_receipt_id == result.write_receipt_id
    assert lifecycle.memory_canonical_receipt_id == result.canonical_receipt_id
    assert lifecycle.candidate_id == candidate.candidate_id
    assert lifecycle.status == "staged"


def test_receipt_ids_are_deterministic(tmp_path) -> None:
    candidate = _candidate()
    a = emit_memory_kernel_receipt(candidate, state_root=tmp_path, created_at=FIXED_NOW)
    b = emit_memory_kernel_receipt(candidate, state_root=tmp_path, created_at=FIXED_NOW)
    assert a.write_receipt_id == b.write_receipt_id
    assert a.canonical_receipt_id == b.canonical_receipt_id


def test_redaction_strips_local_paths(tmp_path) -> None:
    secret_path = "/Users/dhyana/private/secret_notes.txt"
    candidate = _candidate(
        claim=f"Idea referencing operator file {secret_path} for governed memory tooling."
    )
    result = emit_memory_kernel_receipt(
        candidate, state_root=tmp_path, created_at=FIXED_NOW, redaction_policy="summary_only"
    )
    serialized = result.write_receipt_path.read_text() + result.canonical_receipt_path.read_text()
    assert secret_path not in serialized


def test_link_only_summary_drops_claim_text() -> None:
    candidate = _candidate(claim="Confidential operator transcript body that must not leak.")
    summary = candidate_summary(candidate, redaction_policy="link_only")
    assert "Confidential operator transcript body" not in summary
    assert "link_only" in summary


def test_governed_log_never_embeds_claim_body_even_with_secrets(tmp_path) -> None:
    # The governed receipt references the candidate by id; it must not carry the
    # operator claim body, so it cannot leak even token classes the MemoryKernel
    # redactor misses (e.g. an AWS access key id).
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    candidate = _candidate(
        claim=f"Provision infra with AWS key {aws_key} and /Users/dhyana/.ssh/id_rsa password=hunter2."
    )
    result = emit_memory_kernel_receipt(candidate, state_root=tmp_path, created_at=FIXED_NOW)
    blob = (
        result.write_receipt_path.read_text()
        + result.decision_path.read_text()
        + result.canonical_receipt_path.read_text()
    )
    for secret in (aws_key, "hunter2", "id_rsa", "AWS key"):
        assert secret not in blob, secret
    # The reference (candidate_id) is present so the chain still joins.
    assert candidate.candidate_id in blob
