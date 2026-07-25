"""Property-based tests for the formal telos gate substrate."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from hypothesis import given, strategies as st

from dharma_swarm.models import GateDecision, GateResult, GateTier
from dharma_swarm.telos_formal import (
    ActionContext,
    BeliefState,
    DataLabel,
    EvaluatorJudgment,
    FormalGateName,
    FormalGateReport,
    FormalGateResult,
    InformationFlow,
    anekanta_contextuality_gate,
    epistemic_humility_gate,
    noninterference_gate,
    requisite_variety_gate,
    shannon_entropy,
    von_neumann_entropy,
)
from dharma_swarm.telos_formal_graph import analyze_provenance_claims
from dharma_swarm.telos_formal_math import commutator_frobenius_norm, effective_rank
from dharma_swarm.telos_formal_models import ProvenanceClaim


FINITE_FLOATS = st.floats(
    min_value=1e-6,
    max_value=10.0,
    allow_nan=False,
    allow_infinity=False,
)
SIGNED_FINITE_FLOATS = st.floats(
    min_value=-5.0,
    max_value=5.0,
    allow_nan=False,
    allow_infinity=False,
)
NONZERO_FINITE_FLOATS = st.floats(
    min_value=-5.0,
    max_value=5.0,
    allow_nan=False,
    allow_infinity=False,
).filter(lambda value: abs(value) > 1e-6)
NONFINITE_OR_FINITE = st.one_of(FINITE_FLOATS, st.just(float("nan")))


@st.composite
def positive_mass_vector(draw, min_size: int = 2, max_size: int = 12):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    values = draw(st.lists(FINITE_FLOATS, min_size=n, max_size=n))
    total = sum(values)
    return np.asarray([v / total for v in values], dtype=np.float64)


@st.composite
def unit_vectors(draw, min_count: int = 2, max_count: int = 8, max_dim: int = 8):
    m = draw(st.integers(min_value=min_count, max_value=max_count))
    d = draw(st.integers(min_value=1, max_value=max_dim))
    raw = np.asarray(
        draw(
            st.lists(
                st.lists(NONZERO_FINITE_FLOATS, min_size=d, max_size=d),
                min_size=m,
                max_size=m,
            )
        ),
        dtype=np.float64,
    )
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    return raw / norms


@st.composite
def psd_density_matrix(draw, min_dim: int = 2, max_dim: int = 6):
    n = draw(st.integers(min_value=min_dim, max_value=max_dim))
    raw = np.asarray(
        draw(
            st.lists(
                st.lists(SIGNED_FINITE_FLOATS, min_size=n, max_size=n),
                min_size=n,
                max_size=n,
            )
        ),
        dtype=np.float64,
    )
    gram = raw @ raw.T
    trace = float(np.trace(gram))
    if trace == 0.0:
        gram = np.eye(n, dtype=np.float64) / float(n)
    else:
        gram = gram / trace
    return gram.astype(np.complex128)


@st.composite
def formal_gate_results(draw, min_size: int = 1, max_size: int = 6):
    count = draw(st.integers(min_value=min_size, max_value=max_size))
    gates = draw(
        st.lists(
            st.sampled_from(list(FormalGateName)),
            min_size=count,
            max_size=count,
            unique=False,
        )
    )
    results = []
    for gate in gates:
        tier = draw(st.sampled_from(list(GateTier)))
        result = draw(st.sampled_from(list(GateResult)))
        measure = draw(NONFINITE_OR_FINITE)
        threshold = draw(NONFINITE_OR_FINITE)
        results.append(
            FormalGateResult(
                gate=gate,
                tier=tier,
                result=result,
                measure=measure,
                threshold=threshold,
                reason="fuzzed",
            )
        )
    decision = draw(st.sampled_from(list(GateDecision)))
    return FormalGateReport(decision=decision, results=results)


def _projector(theta: float) -> np.ndarray:
    vec = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    return np.outer(vec, vec)


# === Shannon entropy ========================================================


@given(positive_mass_vector())
def test_shannon_entropy_bounds(vector):
    n = len(vector)
    entropy = shannon_entropy(vector)
    assert 0.0 <= entropy <= math.log2(n) + 1e-9


@given(st.integers(min_value=2, max_value=12))
def test_shannon_entropy_uniform_is_maximum(n):
    vector = np.full(n, 1.0 / n, dtype=np.float64)
    assert shannon_entropy(vector) == pytest.approx(math.log2(n), abs=1e-9)


@given(st.integers(min_value=2, max_value=12))
def test_shannon_entropy_point_mass_is_zero(n):
    vector = np.zeros(n, dtype=np.float64)
    vector[0] = 1.0
    assert shannon_entropy(vector) == pytest.approx(0.0, abs=1e-9)


# === Von Neumann entropy ====================================================


@given(positive_mass_vector())
def test_von_neumann_entropy_bounds_for_diagonal_density_matrix(vector):
    rho = np.diag(vector).astype(np.complex128)
    entropy = von_neumann_entropy(rho)
    n = len(vector)
    assert 0.0 <= entropy <= math.log2(n) + 1e-9


@given(psd_density_matrix())
def test_von_neumann_entropy_bounds_for_random_psd_matrices(rho):
    entropy = von_neumann_entropy(rho)
    n = rho.shape[0]
    assert 0.0 <= entropy <= math.log2(n) + 1e-9


@given(st.integers(min_value=2, max_value=8))
def test_von_neumann_entropy_pure_state_is_zero(n):
    rho = np.zeros((n, n), dtype=np.complex128)
    rho[0, 0] = 1.0
    assert von_neumann_entropy(rho) == pytest.approx(0.0, abs=1e-9)


# === Effective rank =========================================================


@given(unit_vectors())
def test_effective_rank_bounds(unit_rows):
    gram = unit_rows @ unit_rows.T
    erank = effective_rank(gram)
    m = unit_rows.shape[0]
    assert 1.0 - 1e-9 <= erank <= m + 1e-9


@given(st.integers(min_value=2, max_value=8))
def test_effective_rank_identical_vectors_are_one(m):
    vec = np.ones((m, 1), dtype=np.float64)
    gram = vec @ vec.T
    assert effective_rank(gram) == pytest.approx(1.0, abs=1e-9)


@given(st.integers(min_value=2, max_value=8))
def test_effective_rank_orthonormal_set_is_cardinality(m):
    gram = np.eye(m, dtype=np.float64)
    assert effective_rank(gram) == pytest.approx(float(m), abs=1e-9)


# === Commutator incompatibility =============================================


@given(
    st.floats(
        min_value=0.0,
        max_value=math.pi / 2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_commutator_incompatibility_identity(theta):
    left = _projector(0.0)
    right = _projector(theta)
    value = commutator_frobenius_norm(left, right)
    expected = math.sqrt(2.0) * abs(math.sin(theta) * math.cos(theta))
    assert value == pytest.approx(expected, abs=1e-8)
    assert value == pytest.approx(commutator_frobenius_norm(right, left), abs=1e-12)


@given(st.sampled_from([0.0, math.pi / 2]))
def test_commutator_zero_for_parallel_or_orthogonal(theta):
    left = _projector(0.0)
    right = _projector(theta)
    assert commutator_frobenius_norm(left, right) == pytest.approx(0.0, abs=1e-12)


# === Epistemic humility =====================================================


@given(st.integers(min_value=2, max_value=12))
def test_epistemic_humility_pure_state_fails(n):
    vector = np.zeros(n, dtype=np.float64)
    vector[0] = 1.0
    res = epistemic_humility_gate(BeliefState(probabilities=vector.tolist()))
    assert res.result == GateResult.FAIL


@given(st.integers(min_value=2, max_value=12))
def test_epistemic_humility_uniform_distribution_passes(n):
    vector = np.full(n, 1.0 / n, dtype=np.float64)
    res = epistemic_humility_gate(BeliefState(probabilities=vector.tolist()))
    assert res.result == GateResult.PASS


@given(
    st.integers(min_value=2, max_value=12),
    st.floats(
        min_value=0.97,
        max_value=0.999999,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_epistemic_humility_dominant_belief_mass_fails(n, dominant):
    remainder = (1.0 - dominant) / (n - 1)
    vector = [dominant] + [remainder] * (n - 1)
    ceiling = dominant - 1e-6
    res = epistemic_humility_gate(
        BeliefState(probabilities=vector),
        max_belief_mass=ceiling,
    )
    assert res.result == GateResult.FAIL
    assert res.detail["lambda_max"] >= ceiling


# === Requisite variety ======================================================


@given(positive_mass_vector(), positive_mass_vector())
def test_requisite_variety_matches_entropy_comparison(regulator, disturbance):
    res = requisite_variety_gate(regulator.tolist(), disturbance.tolist())
    gap = shannon_entropy(regulator) - shannon_entropy(disturbance)
    assert (res.result == GateResult.PASS) == (gap >= -1e-9)


# === Receipt determinism / canonical JSON ==================================


@given(formal_gate_results())
def test_receipt_is_canonical_and_deterministic(report):
    first = report.compute_receipt()
    second = report.compute_receipt()
    assert first == second
    payload = json.loads(report._canonical_json())
    assert payload["decision"] == report.decision.value
    for item in payload["results"]:
        assert item["measure"] is None or isinstance(item["measure"], float)
        assert item["threshold"] is None or isinstance(item["threshold"], float)


@given(formal_gate_results())
def test_receipt_changes_when_payload_changes(report):
    original = report.compute_receipt()
    result = report.results[0]
    changed_result = result.model_copy(
        update={
            "measure": 0.123456789 if math.isfinite(result.measure) else 0.222222222,
            "result": GateResult.FAIL if result.result != GateResult.FAIL else GateResult.PASS,
        }
    )
    changed = report.model_copy(update={"results": [changed_result, *report.results[1:]]})
    assert original != changed.compute_receipt()


@given(formal_gate_results())
def test_receipt_changes_when_decision_changes(report):
    original = report.compute_receipt()
    new_decision = (
        GateDecision.BLOCK
        if report.decision != GateDecision.BLOCK
        else GateDecision.ALLOW
    )
    changed = report.model_copy(update={"decision": new_decision})
    assert original != changed.compute_receipt()


@given(formal_gate_results())
def test_receipt_hmac_is_deterministic_and_keyed(report):
    key_one = b"key-one"
    key_two = b"key-two"
    assert report.sign(key_one) == report.sign(key_one)
    assert report.sign(key_one) != report.sign(key_two)


# === Provenance graph =======================================================


@given(st.integers(min_value=2, max_value=5))
def test_provenance_cycle_and_grounding_are_detected(size):
    claims = [
        ProvenanceClaim(claim_id=f"c{i}", confidence=0.95, evidence_ids=[])
        for i in range(size)
    ]
    claims[0] = ProvenanceClaim(claim_id="c0", confidence=0.95, evidence_ids=["c1"])
    claims[1] = ProvenanceClaim(claim_id="c1", confidence=0.95, evidence_ids=["c0"])
    if size > 2:
        claims[2] = ProvenanceClaim(claim_id="c2", confidence=0.95, evidence_ids=["c1"])
    claims.append(
        ProvenanceClaim(claim_id="grounded", confidence=0.95, evidence_ids=["root"])
    )
    claims.append(
        ProvenanceClaim(claim_id="descendant", confidence=0.95, evidence_ids=["grounded"])
    )
    claims.append(
        ProvenanceClaim(claim_id="floating", confidence=0.95, evidence_ids=["c1"])
    )

    analysis = analyze_provenance_claims(claims)
    assert "c0" in analysis.cycle_claim_ids
    if size >= 2:
        assert "c1" in analysis.cycle_claim_ids
    assert "grounded" in analysis.grounded_claim_ids
    assert "descendant" in analysis.grounded_claim_ids
    assert "floating" in analysis.ungrounded_claim_ids


@given(st.integers(min_value=1, max_value=4))
def test_provenance_root_evidence_makes_claim_grounded(depth):
    root_id = "primary-source"
    claims = [ProvenanceClaim(claim_id="c0", confidence=0.9, evidence_ids=[root_id])]
    for i in range(1, depth):
        claims.append(
            ProvenanceClaim(claim_id=f"c{i}", confidence=0.9, evidence_ids=[f"c{i-1}"])
        )
    analysis = analyze_provenance_claims(claims)
    for claim in claims:
        assert claim.claim_id in analysis.grounded_claim_ids


@given(st.integers(min_value=1, max_value=4))
def test_provenance_claim_only_cycle_is_ungrounded(size):
    claims = [
        ProvenanceClaim(
            claim_id=f"c{i}",
            confidence=0.95,
            evidence_ids=[f"c{(i + 1) % size}"],
        )
        for i in range(size)
    ]
    analysis = analyze_provenance_claims(claims)
    assert set(analysis.cycle_claim_ids) == {claim.claim_id for claim in claims}
    assert set(analysis.ungrounded_claim_ids) == {claim.claim_id for claim in claims}


def test_provenance_deep_grounded_chain_is_stack_safe():
    depth = 1500
    claims = [
        ProvenanceClaim(claim_id="c0", confidence=0.9, evidence_ids=["root"])
    ]
    claims.extend(
        ProvenanceClaim(
            claim_id=f"c{i}",
            confidence=0.9,
            evidence_ids=[f"c{i - 1}"],
        )
        for i in range(1, depth)
    )

    analysis = analyze_provenance_claims(claims)
    assert len(analysis.grounded_claim_ids) == depth
    assert analysis.ungrounded_claim_ids == ()


def test_provenance_deep_cycle_is_stack_safe():
    depth = 1500
    claims = [
        ProvenanceClaim(
            claim_id=f"c{i}",
            confidence=0.9,
            evidence_ids=[f"c{(i + 1) % depth}"],
        )
        for i in range(depth)
    ]

    analysis = analyze_provenance_claims(claims)
    assert len(analysis.cycle_claim_ids) == depth
    assert len(analysis.ungrounded_claim_ids) == depth


# === Non-interference lattice ===============================================


@given(st.sampled_from(list(DataLabel)))
def test_noninterference_lattice_leakage(source_label):
    res = noninterference_gate([InformationFlow(source_label=source_label, sink_is_public=True)])
    leaks = source_label != DataLabel.LOW
    assert (res.result == GateResult.FAIL) == leaks


@given(st.sampled_from(list(DataLabel)))
def test_noninterference_declassified_flows_never_leak(source_label):
    res = noninterference_gate(
        [
            InformationFlow(
                source_label=source_label,
                sink_is_public=True,
                declassified=True,
            )
        ]
    )
    assert res.result == GateResult.PASS
