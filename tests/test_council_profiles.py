"""Tests for the minimal Council (spec §2): the orchestration_trace_verification
profile + shared invariants. Quarantine, decorrelation requirement, replayable
receipts, dispatch_authority stays False, and the load-bearing correctness-split
invariant: the Council CANNOT mark a wrong final outcome as correct."""

from __future__ import annotations

from dharma_swarm.council import (
    DISPATCH_AUTHORITY,
    VALID_VERDICTS,
    Council,
    CouncilReceipt,
    TraceVerificationRequest,
)
from dharma_swarm.council.council import ORCHESTRATION_TRACE_VERIFICATION


def _full_request(**overrides) -> TraceVerificationRequest:
    base = dict(
        genome_id="genome-abc",
        route_receipts=[{"genome_id": "genome-abc", "role": "planner"}],
        trace_receipts=[{"genome_id": "genome-abc", "step": "final"}],
        scorecard={"genome_id": "genome-abc", "score": 0.9},
        promotion_claim={
            "candidate_score": 0.9,
            "baseline_score": 0.7,
            "budget_parity_logged": True,
        },
    )
    base.update(overrides)
    return TraceVerificationRequest(**base)


def test_corroborated_when_decorrelated_evidence_present():
    receipt = Council().verify_orchestration_trace(_full_request())
    assert receipt.verdict == "corroborated"
    assert len(receipt.evaluator_families) >= 2
    assert len(receipt.source_families) >= 2
    assert receipt.verdict in VALID_VERDICTS


def test_quarantine_on_untrusted_input():
    receipt = Council().verify_orchestration_trace(_full_request(untrusted=True))
    assert receipt.verdict == "quarantined"
    assert receipt.quarantined is True


def test_quarantine_on_contamination_finding():
    receipt = Council().verify_orchestration_trace(
        _full_request(contamination_findings=("candidate_read_sealed_labels",))
    )
    assert receipt.verdict == "quarantined"
    assert any("candidate_read_sealed_labels" in f for f in receipt.findings)


def test_decorrelation_requirement_insufficient_with_one_source():
    # Only a scorecard -> one source family, too few evaluator families.
    receipt = Council().verify_orchestration_trace(
        TraceVerificationRequest(
            genome_id="g1",
            scorecard={"genome_id": "g1", "score": 0.5},
        )
    )
    assert receipt.verdict == "insufficient"
    assert any("decorrelation:not_met" in f for f in receipt.findings)


def test_dispatch_authority_always_false():
    for req in (_full_request(), _full_request(untrusted=True)):
        receipt = Council().verify_orchestration_trace(req)
        assert receipt.dispatch_authority is False
    assert DISPATCH_AUTHORITY is False


def test_receipt_is_replayable():
    council = Council()
    req = _full_request()
    r1 = council.verify_orchestration_trace(req)
    r2 = council.verify_orchestration_trace(req)
    assert r1.inputs_hash == r2.inputs_hash
    assert r1.verdict == r2.verdict
    assert r1.to_dict() == r2.to_dict()


def test_promotion_claim_refuted_without_budget_parity():
    receipt = Council().verify_orchestration_trace(
        _full_request(
            promotion_claim={
                "candidate_score": 0.9,
                "baseline_score": 0.7,
                "budget_parity_logged": False,
            }
        )
    )
    assert receipt.verdict == "refuted"
    assert any("budget_parity_not_logged" in f for f in receipt.findings)


def test_promotion_claim_refuted_when_candidate_not_better():
    receipt = Council().verify_orchestration_trace(
        _full_request(
            promotion_claim={
                "candidate_score": 0.6,
                "baseline_score": 0.7,
                "budget_parity_logged": True,
            }
        )
    )
    assert receipt.verdict == "refuted"


def test_trace_integrity_refutes_genome_id_mismatch():
    receipt = Council().verify_orchestration_trace(
        _full_request(route_receipts=[{"genome_id": "WRONG", "role": "planner"}])
    )
    assert receipt.verdict == "refuted"
    assert any("genome_id_missing_or_mismatch" in f for f in receipt.findings)


def test_trace_integrity_refutes_receipt_missing_genome_id():
    """A receipt with no genome_id is not tied to the requested genome and must
    not silently corroborate it (Codex P2 — reject receipts that lack ids)."""
    receipt = Council().verify_orchestration_trace(
        _full_request(route_receipts=[{}], trace_receipts=[{}])
    )
    assert receipt.verdict == "refuted"


def test_promotion_claim_refuted_when_scorecard_disagrees():
    """A forged claim whose candidate_score disagrees with the scorer evidence is
    refuted (Codex P1 — derive promotion scores from scorer evidence)."""
    receipt = Council().verify_orchestration_trace(
        _full_request(
            scorecard={"genome_id": "genome-abc", "score": 0.40},
            promotion_claim={
                "candidate_score": 0.99,  # lies about the score
                "baseline_score": 0.70,
                "budget_parity_logged": True,
            },
        )
    )
    assert receipt.verdict == "refuted"
    assert any("disagrees_with_scorer" in f for f in receipt.findings)


def test_promotion_claim_refuted_when_scorecard_belongs_to_other_genome():
    receipt = Council().verify_orchestration_trace(
        _full_request(scorecard={"genome_id": "SOMEONE-ELSE", "score": 0.9})
    )
    assert receipt.verdict == "refuted"
    assert any("scorecard_genome_mismatch" in f for f in receipt.findings)


def test_council_cannot_assert_correctness_of_wrong_outcome():
    """Load-bearing invariant (spec §2, §6.2): the Council has NO correctness
    authority. Even when the scorer says the outcome is WRONG (score 0.0) and the
    trace is internally consistent, the Council may verify trace integrity but can
    NEVER emit a verdict meaning 'this answer is correct'. The verdict vocabulary
    has no such value, and the trace can still be 'corroborated' as a faithful
    record of a WRONG run."""
    wrong_run = TraceVerificationRequest(
        genome_id="g-wrong",
        route_receipts=[{"genome_id": "g-wrong", "role": "solver"}],
        trace_receipts=[{"genome_id": "g-wrong", "step": "final", "answer": "42"}],
        scorecard={"genome_id": "g-wrong", "score": 0.0, "correct": False},
        # no promotion claim — nobody is claiming this beat controls
    )
    receipt = Council().verify_orchestration_trace(wrong_run)
    # The trace is a faithful record, so it corroborates — but that says nothing
    # about correctness. Crucially the verdict is NOT and CANNOT be "correct".
    assert receipt.verdict in VALID_VERDICTS
    assert "correct" not in VALID_VERDICTS
    assert receipt.verdict != "correct"  # the word does not exist in the vocabulary
    # And no finding claims correctness.
    assert not any("correct" in f and "incorrect" not in f for f in receipt.findings)
    # If anyone tries to ride a promotion claim on a 0.0 outcome with no real
    # lift, the Council refutes it — it does not bless it as correct.
    riding = TraceVerificationRequest(
        genome_id="g-wrong",
        route_receipts=[{"genome_id": "g-wrong"}],
        scorecard={"genome_id": "g-wrong", "score": 0.0},
        promotion_claim={
            "candidate_score": 0.0,
            "baseline_score": 0.0,
            "budget_parity_logged": True,
        },
    )
    assert Council().verify_orchestration_trace(riding).verdict == "refuted"


def test_profile_name_constant():
    receipt = Council().verify_orchestration_trace(_full_request())
    assert receipt.profile == ORCHESTRATION_TRACE_VERIFICATION
    assert isinstance(receipt, CouncilReceipt)
