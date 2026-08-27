"""Tests for the blind ring-1 fitness gate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import pytest

from dharma_swarm.foundry.evaluator import (
    Candidate,
    CallableEvaluator,
    EvalMetrics,
    blind_evaluate,
    canonical_digest,
)


def _candidate(diff: str = "+ pass") -> Candidate:
    return Candidate(candidate_id="c1", target_id="t1", diff=diff, origin_model="m")


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


def _evaluator(
    score: float,
    correct: bool = True,
    proof: _Proof | None = None,
) -> CallableEvaluator:
    def score_fn(candidate, seed):  # noqa: ARG001
        return EvalMetrics(primary_score=score, correctness_passed=correct,
                           metrics={"speedup": score}, wall_clock_s=0.5,
                           isolation_proof=proof)

    return CallableEvaluator(evaluator_id="eval-1", score_fn=score_fn)


def test_clean_candidate_keeps_score():
    receipt = blind_evaluate(_evaluator(1.2), _candidate(), seed=7)
    assert receipt.fitness == 1.2
    assert receipt.correctness_passed is True
    assert receipt.tripwires_fired == ()
    assert receipt.is_win()
    assert receipt.promotion_allowed is False
    assert receipt.isolation_proof is None


def test_promotion_claim_requires_and_seals_isolation_proof():
    receipt = blind_evaluate(_evaluator(1.2, proof=_Proof()), _candidate(), seed=7)
    assert receipt.promotion_allowed is True
    assert receipt.isolation_proof == {
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
        "promotion_allowed": True,
        "digest": _Proof().to_dict()["digest"],
    }
    denied = blind_evaluate(
        _evaluator(1.2, proof=_Proof(promotion_allowed=False)),
        _candidate(),
        seed=7,
    )
    assert denied.promotion_allowed is False
    assert denied.digest != receipt.digest


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
