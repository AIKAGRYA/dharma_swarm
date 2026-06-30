"""Tests for the formal (measured) telos gates.

These exercise the *numbers* each gate computes -- entropy, effective rank,
Shannon gap, orphan counts -- and the gaming attempts the legacy keyword gates
could not stop.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from dharma_swarm.models import GateDecision, GateResult, GateTier
from dharma_swarm.telos_formal_math import commutator_frobenius_norm
from dharma_swarm.telos_formal import (
    ActionContext,
    BeliefState,
    DataLabel,
    EvaluatorJudgment,
    FormalGateName,
    FormalTelosGatekeeper,
    InformationFlow,
    ProvenanceClaim,
    anekanta_contextuality_gate,
    effective_rank,
    epistemic_humility_gate,
    evaluate_formal_gates,
    noninterference_gate,
    observer_separation_gate,
    provenance_integrity_gate,
    requisite_variety_gate,
    shannon_entropy,
    von_neumann_entropy,
)


class _KeywordResult:
    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision
        self.gate = "legacy_keyword"
        self.reason = "stubbed keyword decision"


class _KeywordGatekeeper:
    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision
        self.calls: list[dict[str, str]] = []

    def check(self, *, action: str, content: str, tool_name: str) -> _KeywordResult:
        self.calls.append(
            {"action": action, "content": content, "tool_name": tool_name}
        )
        return _KeywordResult(self.decision)


# === Information-theoretic primitives =======================================


def test_shannon_entropy_uniform_is_log2_n():
    assert shannon_entropy([0.25, 0.25, 0.25, 0.25]) == pytest.approx(2.0)
    assert shannon_entropy([1.0, 1.0]) == pytest.approx(1.0)


def test_shannon_entropy_point_mass_is_zero():
    assert shannon_entropy([1.0, 0.0, 0.0]) == pytest.approx(0.0)


def test_shannon_entropy_normalizes_input():
    # unnormalized but proportional to uniform-over-4
    assert shannon_entropy([2.0, 2.0, 2.0, 2.0]) == pytest.approx(2.0)


def test_shannon_entropy_rejects_negative_and_zero_mass():
    with pytest.raises(ValueError):
        shannon_entropy([-0.1, 1.1])
    with pytest.raises(ValueError):
        shannon_entropy([0.0, 0.0])


def test_von_neumann_entropy_diagonal_matches_shannon():
    rho = np.diag([0.5, 0.3, 0.2]).astype(np.complex128)
    assert von_neumann_entropy(rho) == pytest.approx(shannon_entropy([0.5, 0.3, 0.2]))


def test_von_neumann_entropy_maximally_mixed():
    rho = np.eye(4, dtype=np.complex128) / 4.0
    assert von_neumann_entropy(rho) == pytest.approx(2.0)


def test_von_neumann_entropy_rejects_non_density_matrices():
    with pytest.raises(ValueError):  # trace != 1
        von_neumann_entropy(np.eye(2, dtype=np.complex128))
    with pytest.raises(ValueError):  # not Hermitian
        von_neumann_entropy(np.array([[0.5, 1.0], [0.0, 0.5]], dtype=np.complex128))
    with pytest.raises(ValueError):  # negative eigenvalue (not PSD)
        von_neumann_entropy(np.array([[1.5, 0.0], [0.0, -0.5]], dtype=np.complex128))


def test_effective_rank_orthonormal_equals_n():
    assert effective_rank(np.eye(5)) == pytest.approx(5.0)


def test_effective_rank_rank_one_is_one():
    v = np.ones((4, 1))
    gram = v @ v.T  # all-ones, rank 1
    assert effective_rank(gram) == pytest.approx(1.0)


# === Epistemic humility (anicca) ============================================


def test_humility_blocks_pure_state():
    res = epistemic_humility_gate(BeliefState(probabilities=[1.0, 0.0, 0.0]))
    assert res.result == GateResult.FAIL
    assert res.tier == GateTier.B
    assert res.measure == pytest.approx(0.0, abs=1e-9)


def test_humility_passes_mixed_state():
    res = epistemic_humility_gate(BeliefState(probabilities=[0.5, 0.3, 0.2]))
    assert res.result == GateResult.PASS
    assert res.measure > 0.0


def test_humility_blocks_dominant_belief_mass():
    ctx = ActionContext(
        belief=BeliefState(probabilities=[0.7, 0.3]),
        max_belief_mass=0.6,
    )
    report = evaluate_formal_gates(ctx)
    res = report.by_gate(FormalGateName.EPISTEMIC_HUMILITY)
    assert report.decision == GateDecision.BLOCK
    assert res is not None and res.result == GateResult.FAIL
    assert res.detail["lambda_max"] == pytest.approx(0.7)
    assert "dominant belief mass ceiling" in res.reason


def test_humility_blocks_near_certain_state_below_epsilon():
    # 99.99% on one hypothesis: tiny but nonzero entropy, below default floor
    res = epistemic_humility_gate(
        BeliefState(probabilities=[0.9999, 0.0001]), min_entropy_bits=0.05
    )
    assert res.result == GateResult.FAIL


def test_humility_coherent_pure_state_also_blocked():
    # off-diagonal coherence, still a rank-1 pure state -> entropy 0.
    # A keyword check on "confidence < 1.0" cannot see this; the gate can.
    rho = [[0.5, 0.5], [0.5, 0.5]]
    res = epistemic_humility_gate(BeliefState(density_matrix=rho))
    assert res.result == GateResult.FAIL
    assert res.measure == pytest.approx(0.0, abs=1e-9)


def test_humility_skipped_when_no_belief():
    res = epistemic_humility_gate(None)
    assert res.result == GateResult.PASS
    assert res.skipped


def test_belief_state_requires_exactly_one_representation():
    with pytest.raises(ValueError):
        BeliefState().to_density_matrix()
    with pytest.raises(ValueError):
        BeliefState(
            probabilities=[0.5, 0.5], density_matrix=[[1.0, 0.0], [0.0, 0.0]]
        ).to_density_matrix()


# === Anekantavada (contextuality) ===========================================


def test_anekanta_collinear_evaluators_fail_even_if_numerous():
    # Three evaluators that all say the same thing: effective rank ~1.
    judgments = [
        EvaluatorJudgment(evaluator_id=f"e{i}", vector=[1.0, 2.0, 3.0])
        for i in range(5)
    ]
    res = anekanta_contextuality_gate(judgments)
    assert res.result == GateResult.WARN
    assert res.measure == pytest.approx(1.0, abs=1e-6)


def test_anekanta_orthogonal_evaluators_pass():
    judgments = [
        EvaluatorJudgment(evaluator_id="mech", vector=[1.0, 0.0, 0.0]),
        EvaluatorJudgment(evaluator_id="phen", vector=[0.0, 1.0, 0.0]),
        EvaluatorJudgment(evaluator_id="sys", vector=[0.0, 0.0, 1.0]),
    ]
    res = anekanta_contextuality_gate(judgments)
    assert res.result == GateResult.PASS
    assert res.measure == pytest.approx(3.0, abs=1e-6)
    assert res.detail["mean_incompatibility"] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(
    ("theta_degrees", "expected"),
    [
        (0.0, 0.0),
        (45.0, math.sqrt(2.0) / 2.0),
        (90.0, 0.0),
    ],
)
def test_projector_commutator_identity(theta_degrees, expected):
    theta = math.radians(theta_degrees)
    projector_a = np.outer(np.array([1.0, 0.0]), np.array([1.0, 0.0]))
    vector_b = np.array([math.cos(theta), math.sin(theta)])
    projector_b = np.outer(vector_b, vector_b)
    assert commutator_frobenius_norm(projector_a, projector_b) == pytest.approx(
        expected, abs=1e-9
    )


def test_anekanta_skipped_with_fewer_than_two():
    res = anekanta_contextuality_gate(
        [EvaluatorJudgment(evaluator_id="only", vector=[1.0])]
    )
    assert res.skipped


def test_anekanta_rejects_ragged_vectors():
    with pytest.raises(ValueError):
        anekanta_contextuality_gate(
            [
                EvaluatorJudgment(evaluator_id="a", vector=[1.0, 0.0]),
                EvaluatorJudgment(evaluator_id="b", vector=[1.0]),
            ]
        )


# === Requisite variety (Ashby) ==============================================


def test_requisite_variety_sufficient_passes():
    res = requisite_variety_gate([0.25, 0.25, 0.25, 0.25], [0.5, 0.5])
    assert res.result == GateResult.PASS
    assert res.measure == pytest.approx(2.0 - 1.0)


def test_requisite_variety_insufficient_warns():
    res = requisite_variety_gate([0.5, 0.5], [0.25, 0.25, 0.25, 0.25])
    assert res.result == GateResult.WARN
    assert res.measure < 0.0


def test_requisite_variety_skipped_when_absent():
    assert requisite_variety_gate(None, [0.5, 0.5]).skipped


# === Provenance integrity (satya) ===========================================


def test_provenance_orphan_high_confidence_fails():
    claims = [
        ProvenanceClaim(claim_id="grounded", confidence=0.95, evidence_ids=["e1"]),
        ProvenanceClaim(claim_id="orphan", confidence=0.99, evidence_ids=[]),
    ]
    res = provenance_integrity_gate(claims)
    assert res.result == GateResult.FAIL
    assert "orphan" in res.reason
    assert res.measure == pytest.approx(1.0)


def test_provenance_low_confidence_orphan_is_fine():
    claims = [ProvenanceClaim(claim_id="guess", confidence=0.3, evidence_ids=[])]
    assert provenance_integrity_gate(claims).result == GateResult.PASS


def test_provenance_cycle_fails():
    claims = [
        ProvenanceClaim(claim_id="a", confidence=0.9, evidence_ids=["b"]),
        ProvenanceClaim(claim_id="b", confidence=0.9, evidence_ids=["a"]),
    ]
    res = provenance_integrity_gate(claims)
    assert res.result == GateResult.FAIL
    assert sorted(res.detail["cycle_claim_ids"]) == ["a", "b"]
    assert "circular justification" in res.reason


def test_provenance_ungrounded_chain_fails():
    claims = [
        ProvenanceClaim(claim_id="a", confidence=0.9, evidence_ids=["b"]),
        ProvenanceClaim(claim_id="b", confidence=0.4, evidence_ids=[]),
    ]
    res = provenance_integrity_gate(claims)
    assert res.result == GateResult.FAIL
    assert res.detail["ungrounded_claim_ids"] == ["a"]
    assert "ungrounded claims" in res.reason


def test_provenance_skipped_when_no_claims():
    assert provenance_integrity_gate([]).skipped


# === Non-interference (consent) =============================================


def test_noninterference_blocks_high_to_public():
    res = noninterference_gate(
        [InformationFlow(source_label=DataLabel.HIGH, sink_is_public=True)]
    )
    assert res.result == GateResult.FAIL
    assert res.tier == GateTier.A


def test_noninterference_allows_declassified_flow():
    res = noninterference_gate(
        [
            InformationFlow(
                source_label=DataLabel.HIGH, sink_is_public=True, declassified=True
            )
        ]
    )
    assert res.result == GateResult.PASS


def test_noninterference_allows_low_to_public():
    res = noninterference_gate(
        [InformationFlow(source_label=DataLabel.LOW, sink_is_public=True)]
    )
    assert res.result == GateResult.PASS


def test_noninterference_blocks_intermediate_label_to_public():
    res = noninterference_gate(
        [InformationFlow(source_label=DataLabel.INTERNAL, sink_is_public=True)]
    )
    assert res.result == GateResult.FAIL
    assert res.measure == pytest.approx(1.0)


# === Observer separation (anatta) ===========================================


def test_observer_equals_observed_fails():
    res = observer_separation_gate("agent-1", "agent-1", False, False)
    assert res.result == GateResult.FAIL


def test_measure_and_mutate_same_transaction_fails():
    res = observer_separation_gate("agent-1", "agent-2", True, True)
    assert res.result == GateResult.FAIL


def test_separated_observation_passes():
    res = observer_separation_gate("observer", "observed", True, False)
    assert res.result == GateResult.PASS


# === Aggregate report =======================================================


def test_report_blocks_on_tier_a_violation():
    ctx = ActionContext(
        action="publish secret",
        information_flows=[
            InformationFlow(source_label=DataLabel.HIGH, sink_is_public=True)
        ],
    )
    report = evaluate_formal_gates(ctx)
    assert report.decision == GateDecision.BLOCK
    leak = report.by_gate(FormalGateName.NON_INTERFERENCE)
    assert leak is not None and leak.result == GateResult.FAIL


def test_report_reviews_on_tier_c_only():
    ctx = ActionContext(
        action="decide",
        evaluator_judgments=[
            EvaluatorJudgment(evaluator_id=f"e{i}", vector=[1.0, 1.0])
            for i in range(3)
        ],
    )
    report = evaluate_formal_gates(ctx)
    assert report.decision == GateDecision.REVIEW


def test_report_allows_clean_context():
    ctx = ActionContext(
        action="ordinary step",
        belief=BeliefState(probabilities=[0.4, 0.35, 0.25]),
        provenance_claims=[
            ProvenanceClaim(claim_id="c", confidence=0.9, evidence_ids=["e"])
        ],
    )
    report = evaluate_formal_gates(ctx)
    assert report.decision == GateDecision.ALLOW


def test_report_receipt_is_deterministic():
    ctx = ActionContext(belief=BeliefState(probabilities=[0.5, 0.5]))
    r1 = evaluate_formal_gates(ctx)
    r2 = evaluate_formal_gates(ctx)
    assert r1.receipt_sha256 == r2.receipt_sha256
    assert len(r1.receipt_sha256) == 64


def test_report_receipt_canonicalizes_nonfinite_values():
    report = evaluate_formal_gates(ActionContext(action="noop"))
    payload = json.loads(report._canonical_json())
    assert payload["decision"] == GateDecision.ALLOW.value
    assert all(item["measure"] is None for item in payload["results"])
    assert all(item["threshold"] is None for item in payload["results"])


def test_report_hmac_signing_is_keyed_and_deterministic():
    report_a = evaluate_formal_gates(ActionContext(action="noop"))
    report_b = evaluate_formal_gates(ActionContext(action="noop"))
    assert report_a.sign(b"alpha") == report_b.sign(b"alpha")
    report_c = evaluate_formal_gates(ActionContext(action="noop"))
    report_d = evaluate_formal_gates(ActionContext(action="noop"))
    assert report_c.sign(b"alpha") != report_d.sign(b"beta")


def test_report_receipt_changes_with_verdict():
    clean = evaluate_formal_gates(
        ActionContext(belief=BeliefState(probabilities=[0.5, 0.5]))
    )
    blocked = evaluate_formal_gates(
        ActionContext(belief=BeliefState(probabilities=[1.0, 0.0]))
    )
    assert clean.receipt_sha256 != blocked.receipt_sha256


def test_report_receipt_detects_decision_mutation():
    report = evaluate_formal_gates(ActionContext(action="noop"))
    assert report.receipt_matches()
    original = report.receipt_sha256
    report.decision = GateDecision.BLOCK
    assert not report.receipt_matches()
    assert report.compute_receipt() != original


def test_all_gates_skipped_yields_allow():
    report = evaluate_formal_gates(ActionContext(action="noop"))
    assert report.decision == GateDecision.ALLOW
    assert all(r.skipped for r in report.results)


def test_formal_gatekeeper_keyword_block_matches_report_decision():
    gatekeeper = FormalTelosGatekeeper(
        keyword_gatekeeper=_KeywordGatekeeper(GateDecision.BLOCK)
    )
    decision, report, keyword_payload = gatekeeper.check(
        ActionContext(action="legacy block would apply"),
        content="blocked by legacy keyword gate",
        tool_name="publish",
    )

    assert decision == GateDecision.BLOCK
    assert report.decision == GateDecision.BLOCK
    assert report.receipt_matches()
    assert keyword_payload is not None
    assert keyword_payload["decision"] == GateDecision.BLOCK
    assert all(result.skipped for result in report.results)


def test_formal_gatekeeper_keyword_allow_preserves_formal_block():
    gatekeeper = FormalTelosGatekeeper(
        keyword_gatekeeper=_KeywordGatekeeper(GateDecision.ALLOW)
    )
    decision, report, keyword_payload = gatekeeper.check(
        ActionContext(
            action="overconfident claim",
            belief=BeliefState(probabilities=[1.0, 0.0]),
        )
    )

    assert decision == GateDecision.BLOCK
    assert report.decision == GateDecision.BLOCK
    assert report.receipt_matches()
    assert keyword_payload is not None
    assert keyword_payload["decision"] == GateDecision.ALLOW


def test_formal_gatekeeper_can_skip_keyword_prefilter():
    keyword = _KeywordGatekeeper(GateDecision.BLOCK)
    gatekeeper = FormalTelosGatekeeper(keyword_gatekeeper=keyword)
    decision, report, keyword_payload = gatekeeper.check(
        ActionContext(action="clean"),
        run_keyword_prefilter=False,
    )

    assert keyword.calls == []
    assert keyword_payload is None
    assert decision == GateDecision.ALLOW
    assert report.decision == GateDecision.ALLOW
    assert report.receipt_matches()
