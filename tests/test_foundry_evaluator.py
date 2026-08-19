"""Tests for the blind ring-1 fitness gate."""

from __future__ import annotations

from dharma_swarm.foundry.evaluator import (
    Candidate,
    CallableEvaluator,
    EvalMetrics,
    blind_evaluate,
    canonical_digest,
)


def _candidate(diff: str = "+ pass") -> Candidate:
    return Candidate(candidate_id="c1", target_id="t1", diff=diff, origin_model="m")


def _evaluator(score: float, correct: bool = True) -> CallableEvaluator:
    def score_fn(candidate, seed):  # noqa: ARG001
        return EvalMetrics(primary_score=score, correctness_passed=correct,
                           metrics={"speedup": score}, wall_clock_s=0.5)

    return CallableEvaluator(evaluator_id="eval-1", score_fn=score_fn)


def test_clean_candidate_keeps_score():
    receipt = blind_evaluate(_evaluator(1.2), _candidate(), seed=7)
    assert receipt.fitness == 1.2
    assert receipt.correctness_passed is True
    assert receipt.tripwires_fired == ()
    assert receipt.is_win()


def test_tripwire_forces_zero_fitness():
    receipt = blind_evaluate(
        _evaluator(9.9), _candidate(), tripwires_fired=("forbidden_primitive",)
    )
    assert receipt.fitness == 0.0
    assert not receipt.is_win()
    assert receipt.tripwires_fired == ("forbidden_primitive",)


def test_correctness_failure_forces_zero_fitness():
    receipt = blind_evaluate(_evaluator(5.0, correct=False), _candidate())
    assert receipt.fitness == 0.0
    assert not receipt.is_win()


def test_negative_score_never_becomes_positive_fitness():
    receipt = blind_evaluate(_evaluator(-3.0), _candidate())
    assert receipt.fitness == 0.0


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
