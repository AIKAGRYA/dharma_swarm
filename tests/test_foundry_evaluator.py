"""Tests for the blind ring-1 fitness gate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace

import pytest

from dharma_swarm.foundry.evaluator import (
    Candidate,
    CallableEvaluator,
    EvalMetrics,
    EvaluationRunIdentity,
    bind_isolation_proof,
    blind_evaluate,
    canonical_digest,
)


def _candidate(diff: str = "+ pass") -> Candidate:
    return Candidate(candidate_id="c1", target_id="t1", diff=diff, origin_model="m")


@dataclass(frozen=True)
class _Proof:
    promotion_allowed: bool = False

    def to_dict(self):
        body = {
            "isolation_level": "docker_nonet",
            "network_disabled": True,
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


def _evaluator(
    score: float,
    correct: bool = True,
    proof: _Proof | None = None,
) -> CallableEvaluator:
    def score_fn(candidate, seed):
        identity = EvaluationRunIdentity.from_execution(
            run_id=f"eval-1:{candidate.candidate_id}:{seed}",
            command=["oracle", "eval-1", str(seed)],
            output={"score": score, "correct": correct},
        )
        bound = (
            bind_isolation_proof(
                proof,
                candidate=candidate,
                evaluator_id="eval-1",
                seed=seed,
                run_identity=identity,
            )
            if proof is not None
            else None
        )
        return EvalMetrics(primary_score=score, correctness_passed=correct,
                           metrics={"speedup": score}, wall_clock_s=0.5,
                           isolation_proof=bound, run_identity=identity)

    return CallableEvaluator(evaluator_id="eval-1", score_fn=score_fn)


def test_clean_candidate_keeps_score():
    receipt = blind_evaluate(_evaluator(1.2), _candidate(), seed=7)
    assert receipt.fitness == 1.2
    assert receipt.correctness_passed is True
    assert receipt.tripwires_fired == ()
    assert receipt.is_win()
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof is None


def test_public_structural_proof_is_sealed_but_never_authorizes_promotion():
    receipt = blind_evaluate(_evaluator(1.2, proof=_Proof()), _candidate(), seed=7)
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof["digest"] == _Proof().to_dict()["digest"]
    binding = receipt.isolation_proof["evaluation_binding"]
    assert binding["candidate_id"] == "c1"
    assert binding["evaluator_id"] == "eval-1"
    assert binding["seed"] == 7
    assert binding["run_id"] == "eval-1:c1:7"
    assert receipt.run_identity == {
        "run_id": binding["run_id"],
        "command_digest": binding["command_digest"],
        "output_digest": binding["output_digest"],
    }
    forged_positive = blind_evaluate(
        _evaluator(1.2, proof=_Proof(promotion_allowed=True)),
        _candidate(),
        seed=7,
    )
    assert forged_positive.promotion_allowed is False
    assert forged_positive.isolation_proof is None
    assert forged_positive.digest != receipt.digest


def test_bound_observation_never_echoes_caller_promotion_claim():
    identity = EvaluationRunIdentity.from_execution(
        run_id="run-1", command=["oracle"], output={"score": 1.2}
    )
    observation = bind_isolation_proof(
        _Proof(promotion_allowed=True),
        candidate=_candidate(),
        evaluator_id="eval-1",
        seed=7,
        run_identity=identity,
    )
    assert observation.promotion_allowed is False


def test_bare_isolation_proof_cannot_promote_without_run_binding():
    identity = EvaluationRunIdentity.from_execution(
        run_id="run-1", command=["oracle"], output={"score": 1.2}
    )
    evaluator = CallableEvaluator(
        evaluator_id="eval-1",
        score_fn=lambda candidate, seed: EvalMetrics(
            primary_score=1.2,
            correctness_passed=True,
            isolation_proof=_Proof(),
            run_identity=identity,
        ),
    )
    receipt = blind_evaluate(evaluator, _candidate(), seed=7)
    assert receipt.fitness == 1.2
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof is None


@pytest.mark.parametrize(
    "mismatch",
    ["candidate", "target", "evaluator", "seed", "run", "command", "output"],
)
def test_bound_proof_cannot_be_reused_for_another_receipt_identity(mismatch):
    candidate = _candidate()
    evaluator_id = "eval-1"
    seed = 7
    identity = EvaluationRunIdentity.from_execution(
        run_id="run-1", command=["oracle", "--seed", "7"], output={"score": 1.2}
    )
    bound = bind_isolation_proof(
        _Proof(), candidate=candidate, evaluator_id=evaluator_id, seed=seed,
        run_identity=identity,
    )
    current_candidate = candidate
    current_evaluator_id = evaluator_id
    current_seed = seed
    current_identity = identity
    if mismatch == "candidate":
        current_candidate = replace(candidate, diff="+ different")
    elif mismatch == "target":
        current_candidate = replace(candidate, target_id="t2")
    elif mismatch == "evaluator":
        current_evaluator_id = "eval-2"
    elif mismatch == "seed":
        current_seed = 8
    elif mismatch == "run":
        current_identity = replace(identity, run_id="run-2")
    elif mismatch == "command":
        current_identity = EvaluationRunIdentity.from_execution(
            run_id="run-1", command=["other-oracle"], output={"score": 1.2}
        )
    else:
        current_identity = EvaluationRunIdentity.from_execution(
            run_id="run-1", command=["oracle", "--seed", "7"],
            output={"score": 9.9},
        )

    evaluator = CallableEvaluator(
        evaluator_id=current_evaluator_id,
        score_fn=lambda current, current_seed_value: EvalMetrics(
            primary_score=1.2,
            correctness_passed=True,
            isolation_proof=bound,
            run_identity=current_identity,
        ),
    )
    receipt = blind_evaluate(evaluator, current_candidate, seed=current_seed)
    assert receipt.fitness == 1.2
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof is None


def test_forged_isolation_proof_digest_cannot_promote():
    proof = _Proof()

    class ForgedProof:
        promotion_allowed = True

        def to_dict(self):
            return {**proof.to_dict(), "digest": "sha256:" + "0" * 64}

    receipt = blind_evaluate(_evaluator(1.2, proof=ForgedProof()), _candidate())
    assert receipt.fitness == 1.2
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof is None


def test_coercive_isolation_level_string_subclass_cannot_promote():
    class LyingIsolationLevel(str):
        def __eq__(self, other):
            return True

        __hash__ = str.__hash__

    class ForgedProof:
        promotion_allowed = True

        def to_dict(self):
            body = _Proof().to_dict()
            body["isolation_level"] = LyingIsolationLevel("local_restricted")
            facts = {
                key: value
                for key, value in body.items()
                if key not in {"digest", "promotion_allowed"}
            }
            body["digest"] = "sha256:" + hashlib.sha256(
                json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            return body

    receipt = blind_evaluate(_evaluator(1.2, proof=ForgedProof()), _candidate())
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof is None


def test_tripwire_forces_zero_fitness():
    receipt = blind_evaluate(
        _evaluator(9.9), _candidate(), tripwires_fired=("forbidden_primitive",)
    )
    assert receipt.fitness == 0.0
    assert not receipt.is_win()
    assert receipt.tripwires_fired == ("forbidden_primitive",)


def test_correctness_failure_forces_zero_fitness():
    receipt = blind_evaluate(
        _evaluator(5.0, correct=False, proof=_Proof()),
        _candidate(),
    )
    assert receipt.fitness == 0.0
    assert not receipt.is_win()
    assert receipt.promotion_allowed is False


@pytest.mark.parametrize("malformed", ["false", 1])
def test_non_boolean_correctness_claim_fails_closed(malformed):
    metrics = EvalMetrics(
        primary_score=5.0,
        correctness_passed=malformed,
        metrics={"speedup": 5.0},
        wall_clock_s=0.5,
        isolation_proof=_Proof(),
    )
    evaluator = CallableEvaluator(
        evaluator_id="malformed-correctness",
        score_fn=lambda candidate, seed: metrics,
    )
    receipt = blind_evaluate(evaluator, _candidate())
    assert receipt.correctness_passed is False
    assert receipt.fitness == 0.0
    assert receipt.promotion_allowed is False
    assert "invalid_evaluator_metrics" in receipt.tripwires_fired


@pytest.mark.parametrize(
    "metrics",
    [
        EvalMetrics(
            primary_score=True,
            correctness_passed=True,
            metrics={"speedup": 1.0},
            wall_clock_s=0.5,
            isolation_proof=_Proof(),
        ),
        EvalMetrics(
            primary_score=1.0,
            correctness_passed=True,
            metrics={"speedup": True},
            wall_clock_s=0.5,
            isolation_proof=_Proof(),
        ),
        EvalMetrics(
            primary_score=1.0,
            correctness_passed=True,
            metrics={"speedup": 1.0},
            wall_clock_s=True,
            isolation_proof=_Proof(),
        ),
    ],
)
def test_boolean_numeric_fields_fail_closed(metrics):
    evaluator = CallableEvaluator(
        evaluator_id="boolean-numeric",
        score_fn=lambda candidate, seed: metrics,
    )
    receipt = blind_evaluate(evaluator, _candidate())
    assert receipt.fitness == 0.0
    assert receipt.promotion_allowed is False
    assert "invalid_evaluator_metrics" in receipt.tripwires_fired


def test_negative_score_never_becomes_positive_fitness():
    receipt = blind_evaluate(_evaluator(-3.0, proof=_Proof()), _candidate())
    assert receipt.fitness == 0.0
    assert receipt.promotion_allowed is False


@pytest.mark.parametrize(
    "metrics",
    [
        EvalMetrics(
            primary_score=float("inf"),
            correctness_passed=True,
            metrics={"speedup": 1.0},
            wall_clock_s=0.5,
            isolation_proof=_Proof(),
        ),
        EvalMetrics(
            primary_score=1.0,
            correctness_passed=True,
            metrics={"speedup": float("nan")},
            wall_clock_s=0.5,
            isolation_proof=_Proof(),
        ),
        EvalMetrics(
            primary_score=1.0,
            correctness_passed=True,
            metrics={"speedup": 1.0},
            wall_clock_s=float("nan"),
            isolation_proof=_Proof(),
        ),
    ],
)
def test_non_finite_evaluator_values_fail_closed(metrics):
    evaluator = CallableEvaluator(evaluator_id="non-finite", score_fn=lambda c, s: metrics)
    receipt = blind_evaluate(evaluator, _candidate())
    assert receipt.fitness == 0.0
    assert receipt.promotion_allowed is False
    assert "invalid_evaluator_metrics" in receipt.tripwires_fired
    assert math.isfinite(receipt.wall_clock_s)
    assert all(math.isfinite(value) for value in receipt.metrics.values())


def test_digest_is_deterministic_and_sensitive():
    r1 = blind_evaluate(_evaluator(1.0), _candidate(), seed=1)
    r2 = blind_evaluate(_evaluator(1.0), _candidate(), seed=1)
    assert r1.digest == r2.digest
    r3 = blind_evaluate(_evaluator(2.0), _candidate(), seed=1)
    assert r3.digest != r1.digest


def test_canonical_digest_stable_across_key_order():
    a = canonical_digest({"b": 1, "a": 2})
    b = canonical_digest({"a": 2, "b": 1})
    assert a == b


def test_canonical_digest_rejects_non_finite_json():
    with pytest.raises(ValueError):
        canonical_digest({"score": float("nan")})
