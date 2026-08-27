"""Tests for ring-2 held-out re-verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pytest

from dharma_swarm.foundry.evaluator import (
    Candidate,
    CallableEvaluator,
    EvalMetrics,
    EvaluationRunIdentity,
    bind_isolation_proof,
)
from dharma_swarm.foundry.heldout import run_heldout


def _cand() -> Candidate:
    return Candidate(candidate_id="c1", target_id="t1", diff="+ x=1")


@dataclass(frozen=True)
class _Proof:
    promotion_allowed: bool = True

    def to_dict(self):
        body = {
            "isolation_level": "docker_nonet",
            "network_disabled": self.promotion_allowed,
            "blocked": False,
            "timed_out": False,
            "exit_code": 0,
            "readonly_rootfs": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limited": True,
            "memory_limited": True,
            "memory_swap_limited": True,
            "tmpfs_limited": True,
            "non_root_user": True,
            "workdir_readonly": True,
        }
        digest = "sha256:" + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {**body, "digest": digest, "promotion_allowed": self.promotion_allowed}


def _bound_payload(
    candidate: Candidate, evaluator_id: str, seed: int, run_id: str,
) -> dict:
    identity = EvaluationRunIdentity.from_execution(
        run_id=run_id,
        command=["oracle", evaluator_id, str(seed)],
        output={"score": 1.0},
    )
    return bind_isolation_proof(
        _Proof(), candidate=candidate, evaluator_id=evaluator_id, seed=seed,
        run_identity=identity,
    ).to_dict()


def _ring1_proof(candidate: Candidate | None = None) -> dict:
    candidate = candidate or _cand()
    return {
        "schema_version": "foundry_ring1_isolation.v1",
        "promotion_allowed": True,
        "primary": _bound_payload(candidate, "ring1", 0, "ring1-primary"),
        "determinism_recheck": _bound_payload(
            candidate, "ring1", 0, "ring1-recheck"
        ),
    }


def _evaluator(score: float, *, proven: bool = False) -> CallableEvaluator:
    evaluator_id = f"held-{score}"
    calls = 0

    def score_fn(candidate, seed):
        nonlocal calls
        calls += 1
        identity = EvaluationRunIdentity.from_execution(
            run_id=f"{evaluator_id}:{candidate.candidate_id}:{seed}:{calls}",
            command=["oracle", evaluator_id, str(seed)],
            output={"score": score},
        )
        proof = (
            bind_isolation_proof(
                _Proof(), candidate=candidate, evaluator_id=evaluator_id, seed=seed,
                run_identity=identity,
            )
            if proven
            else None
        )
        return EvalMetrics(
            primary_score=score,
            correctness_passed=True,
            isolation_proof=proof,
            run_identity=identity,
        )

    return CallableEvaluator(
        evaluator_id=evaluator_id,
        score_fn=score_fn,
    )


def test_full_survival():
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(1.0), "w2": _evaluator(1.0)},
        in_loop_fitness=1.0, survival_threshold=0.5,
    )
    assert outcome.survival_rate == 1.0
    assert outcome.survived
    assert outcome.promotion_allowed is False


def test_overfit_collapses_survival():
    # In-loop claimed 1.0 but held-out workloads only deliver 0.1 → not survived.
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(0.1, proven=True), "w2": _evaluator(0.1, proven=True)},
        in_loop_fitness=1.0,
        survival_threshold=0.5,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survival_rate < 0.5
    assert not outcome.survived
    assert not outcome.promotion_allowed


def test_partial_survival_at_threshold():
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(1.0), "w2": _evaluator(0.0)},
        in_loop_fitness=1.0, survival_threshold=0.5,
    )
    assert outcome.survival_rate == 0.5
    assert outcome.survived


def test_survival_measures_gain_above_the_same_baseline():
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(101.0, proven=True)},
        baseline_fitness=100.0,
        in_loop_fitness=110.0,
        survival_threshold=0.5,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survival_rate == 0.1
    assert not outcome.survived
    assert not outcome.promotion_allowed


def test_zero_gain_cannot_promote_even_with_zero_threshold():
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(100.0, proven=True)},
        baseline_fitness=100.0,
        in_loop_fitness=110.0,
        survival_threshold=0.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survival_rate == 0.0
    assert not outcome.survived
    assert not outcome.promotion_allowed


def test_zero_in_loop_fitness_is_zero_survival():
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(1.0)}, in_loop_fitness=0.0,
    )
    assert outcome.survival_rate == 0.0
    assert not outcome.survived


def test_promotion_requires_ring1_and_every_heldout_isolation_proof():
    ring1 = _ring1_proof()
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True), "w2": _evaluator(1.0, proven=True)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=ring1,
    )
    assert outcome.survived
    assert outcome.promotion_allowed
    assert set(outcome.isolation_proofs) == {"ring1", "w1", "w2"}
    assert outcome.isolation_proofs["w1"]["schema_version"] == (
        "foundry_heldout_isolation.v1"
    )
    assert outcome.isolation_proofs["w1"]["promotion_allowed"] is True

    missing_one = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True), "w2": _evaluator(1.0)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=ring1,
    )
    assert missing_one.survived
    assert missing_one.promotion_allowed is False


def test_ring1_workload_name_is_reserved_before_evaluation():
    evaluator = CallableEvaluator(
        evaluator_id="must-not-run",
        score_fn=lambda candidate, seed: pytest.fail("reserved workload was evaluated"),
    )
    with pytest.raises(ValueError, match="reserved key 'ring1'"):
        run_heldout(
            _cand(), {"ring1": evaluator}, in_loop_fitness=1.0,
            in_loop_promotion_allowed=True, in_loop_isolation_proof=_ring1_proof(),
        )


def test_ring1_proof_bound_to_another_candidate_fails_closed():
    other = Candidate(candidate_id="c2", target_id="t1", diff="+ x=2")
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(other),
    )
    assert outcome.survived
    assert outcome.promotion_allowed is False


def test_reused_heldout_run_identity_cannot_satisfy_recheck():
    candidate = _cand()
    identity = EvaluationRunIdentity.from_execution(
        run_id="one-run", command=["oracle"], output={"score": 1.0}
    )
    proof = bind_isolation_proof(
        _Proof(), candidate=candidate, evaluator_id="reused", seed=0,
        run_identity=identity,
    )
    evaluator = CallableEvaluator(
        evaluator_id="reused",
        score_fn=lambda current, seed: EvalMetrics(
            primary_score=1.0,
            correctness_passed=True,
            isolation_proof=proof,
            run_identity=identity,
        ),
    )
    outcome = run_heldout(
        candidate,
        {"w1": evaluator},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survived
    assert outcome.promotion_allowed is False
    assert outcome.isolation_proofs["w1"]["promotion_allowed"] is False


def test_promotion_boolean_without_ring1_proof_fails_closed():
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=None,
    )
    assert outcome.survived
    assert outcome.promotion_allowed is False


def test_non_boolean_ring1_promotion_claim_fails_closed():
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed="false",
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survived
    assert outcome.promotion_allowed is False


def test_forged_nested_ring1_proof_digest_fails_closed():
    forged = _ring1_proof()
    forged["primary"] = {**forged["primary"], "digest": "sha256:" + "0" * 64}
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=forged,
    )
    assert outcome.survived
    assert outcome.promotion_allowed is False


def test_coercive_ring1_bundle_mapping_cannot_promote():
    class CoerciveBundle(dict):
        def get(self, key, default=None):
            if key == "schema_version":
                return "foundry_ring1_isolation.v1"
            if key == "promotion_allowed":
                return True
            return super().get(key, default)

    forged = CoerciveBundle(_ring1_proof())
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True)},
        in_loop_fitness=1.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=forged,
    )
    assert outcome.survived
    assert outcome.promotion_allowed is False


def test_non_finite_fitness_cannot_survive_and_threshold_must_be_finite():
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1.0, proven=True)},
        in_loop_fitness=float("nan"),
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survival_rate == 0.0
    assert not outcome.survived
    assert not outcome.promotion_allowed

    with pytest.raises(ValueError, match="survival_threshold"):
        run_heldout(
            _cand(),
            {"w1": _evaluator(1.0)},
            in_loop_fitness=1.0,
            survival_threshold=float("nan"),
        )


def test_overflowing_gain_arithmetic_fails_closed():
    outcome = run_heldout(
        _cand(),
        {"w1": _evaluator(1e308, proven=True)},
        baseline_fitness=-1e308,
        in_loop_fitness=1e308,
        survival_threshold=0.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert outcome.survival_rate == 0.0
    assert not outcome.survived
    assert not outcome.promotion_allowed


def test_flaky_heldout_score_cannot_cross_promotion_boundary():
    calls = 0

    def alternating_score(candidate, seed):
        nonlocal calls
        calls += 1
        score = 10.0 if calls % 2 else 0.0
        identity = EvaluationRunIdentity.from_execution(
            run_id=f"alternating:{calls}",
            command=["oracle", "alternating-heldout", str(seed)],
            output={"score": score},
        )
        return EvalMetrics(
            primary_score=score,
            correctness_passed=True,
            isolation_proof=bind_isolation_proof(
                _Proof(), candidate=candidate, evaluator_id="alternating-heldout",
                seed=seed, run_identity=identity,
            ),
            run_identity=identity,
        )

    evaluator = CallableEvaluator(
        evaluator_id="alternating-heldout",
        score_fn=alternating_score,
    )
    outcome = run_heldout(
        _cand(),
        {"flaky": evaluator},
        in_loop_fitness=10.0,
        in_loop_promotion_allowed=True,
        in_loop_isolation_proof=_ring1_proof(),
    )
    assert calls == 2
    assert outcome.per_workload["flaky"] == 0.0
    assert not outcome.survived
    assert not outcome.promotion_allowed
    assert outcome.isolation_proofs["flaky"]["promotion_allowed"] is False
