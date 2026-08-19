"""Tests for ring-2 held-out re-verification."""

from __future__ import annotations

from dharma_swarm.foundry.evaluator import Candidate, CallableEvaluator, EvalMetrics
from dharma_swarm.foundry.heldout import run_heldout


def _cand() -> Candidate:
    return Candidate(candidate_id="c1", target_id="t1", diff="+ x=1")


def _evaluator(score: float) -> CallableEvaluator:
    return CallableEvaluator(
        evaluator_id=f"held-{score}",
        score_fn=lambda c, s: EvalMetrics(primary_score=score, correctness_passed=True),
    )


def test_full_survival():
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(1.0), "w2": _evaluator(1.0)},
        in_loop_fitness=1.0, survival_threshold=0.5,
    )
    assert outcome.survival_rate == 1.0
    assert outcome.survived


def test_overfit_collapses_survival():
    # In-loop claimed 1.0 but held-out workloads only deliver 0.1 → not survived.
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(0.1), "w2": _evaluator(0.1)},
        in_loop_fitness=1.0, survival_threshold=0.5,
    )
    assert outcome.survival_rate < 0.5
    assert not outcome.survived


def test_partial_survival_at_threshold():
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(1.0), "w2": _evaluator(0.0)},
        in_loop_fitness=1.0, survival_threshold=0.5,
    )
    assert outcome.survival_rate == 0.5
    assert outcome.survived


def test_zero_in_loop_fitness_is_zero_survival():
    outcome = run_heldout(
        _cand(), {"w1": _evaluator(1.0)}, in_loop_fitness=0.0,
    )
    assert outcome.survival_rate == 0.0
    assert not outcome.survived
