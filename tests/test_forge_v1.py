"""Tests for the Forge v1 offline scoreboard machinery. Pure offline — no live
calls. These assert the measurement is HONEST: the budget is enforced, the
verifier scores from real test execution (not a self-report) and the gold test
cannot be edited, best-of-N keeps the passer, and the scoreboard computes lift
correctly in both directions."""
import pytest

from dharma_swarm.forge_v1.fixtures import ADD_TASK, DEMO_TASKS
from dharma_swarm.forge_v1.harness import (
    ArmResult,
    BudgetExhausted,
    TokenBroker,
    best_of_n,
    paired_bootstrap_ci,
    run_scoreboard,
    verify,
)
from dharma_swarm.forge_v1.run_real_patch import build_repair_prompt
from dharma_swarm.forge_v1.models import FlakyStub, StrongStub, WeakStub


# --- TokenBroker: equal-budget enforcement ---
def test_broker_charges_and_tracks():
    b = TokenBroker(cap=1000)
    assert b.charge(400) == 400
    assert b.charge(600) == 1000
    assert b.calls == 2
    assert b.remaining() == 0


def test_broker_aborts_over_cap():
    b = TokenBroker(cap=1000)
    b.charge(900)
    with pytest.raises(BudgetExhausted):
        b.charge(200)  # would reach 1100 > 1000
    assert b.spent == 900  # the rejected call is NOT counted


# --- verifier: real execution + gold-test protection ---
def test_verifier_passes_gold_patch():
    assert verify(ADD_TASK, ADD_TASK.gold_patch) is True


def test_verifier_fails_buggy_or_empty_patch():
    assert verify(ADD_TASK, ADD_TASK.files) is False
    assert verify(ADD_TASK, None) is False


def test_agent_cannot_edit_gold_test():
    # A patch that tries to neuter the gold test must NOT pass — the verifier
    # restores the gold test last (the DGM 'delete the detector' defense).
    cheat = {
        "test_solution.py": "import sys\nsys.exit(0)\n",  # fake-pass attempt
        "solution.py": ADD_TASK.files["solution.py"],     # still buggy
    }
    assert verify(ADD_TASK, cheat) is False


def test_verifier_rejects_candidate_path_traversal():
    assert verify(ADD_TASK, {"../escape.py": "print('escaped')\n"}) is False


def test_repair_prompt_example_uses_actual_target_path():
    prompt = build_repair_prompt(
        {"repo": "sympy/sympy", "problem_statement": "fix Add"},
        {"sympy/core/add.py": "def broken():\n    pass\n"},
    )

    assert "<<<<<<< SEARCH path=sympy/core/add.py" in prompt
    assert "django/db/models/base.py" not in prompt


def test_autoloop_matrix_imports_without_cycle():
    import dharma_swarm.forge_v1.autoloop_matrix as autoloop_matrix

    assert callable(autoloop_matrix.run_matrix)


# --- best-of-N ---
def test_best_of_n_strong_passes_in_one_call():
    r = best_of_n(StrongStub(tokens=1000), ADD_TASK, TokenBroker(cap=5000))
    assert r.passed
    assert r.samples == 1
    assert r.tokens == 1000


def test_best_of_n_weak_never_passes():
    r = best_of_n(WeakStub(tokens=1000), ADD_TASK, TokenBroker(cap=5000))
    assert not r.passed


def test_best_of_n_budget_changes_outcome():
    # Flaky hits on sample 3 (3000 tokens). Budget 2500 affords only 2 -> fail.
    tight = best_of_n(FlakyStub(hit_every=3, tokens=1000), ADD_TASK, TokenBroker(cap=2500))
    assert not tight.passed
    assert tight.samples == 2
    # Budget 5000 affords sample 3 -> pass. Same model, just more budget.
    loose = best_of_n(FlakyStub(hit_every=3, tokens=1000), ADD_TASK, TokenBroker(cap=5000))
    assert loose.passed
    assert loose.samples == 3


def test_paired_bootstrap_ci_preserves_task_pairing():
    ci = paired_bootstrap_ci([1.0, 0.0, -1.0], samples=50, seed=1)
    assert ci["n"] == 3
    assert ci["mean"] == 0.0
    assert ci["lower"] <= ci["mean"] <= ci["upper"]


# --- scoreboard end-to-end (THE test) ---
def test_scoreboard_negative_when_swarm_worse():
    rep = run_scoreboard(
        DEMO_TASKS,
        champion=lambda t, b: best_of_n(StrongStub(), t, b),
        swarm=lambda t, b: best_of_n(WeakStub(), t, b),
        budget=5000,
    )
    assert rep["champion_pass_at_1"] == 1.0
    assert rep["swarm_pass_at_1"] == 0.0
    assert rep["swarm_lift"] == -1.0
    assert rep["paired_bootstrap_ci"]["upper"] < 0
    assert rep["status"] == "measured_negative_or_zero"
    assert rep["ship_swarm"] is False


def test_scoreboard_positive_when_swarm_better():
    rep = run_scoreboard(
        DEMO_TASKS,
        champion=lambda t, b: best_of_n(WeakStub(), t, b),
        swarm=lambda t, b: best_of_n(StrongStub(), t, b),
        budget=5000,
    )
    assert rep["swarm_lift"] == 1.0
    assert rep["paired_bootstrap_ci"]["lower"] > 0
    assert rep["ship_swarm"] is True


def test_scoreboard_positive_lift_does_not_ship_without_ci_power():
    def champion(_task, _broker):
        return ArmResult(passed=False, samples=1, tokens=0)

    def swarm(task, _broker):
        return ArmResult(passed=task.name == "add-minus-bug", samples=1, tokens=0)

    rep = run_scoreboard(DEMO_TASKS, champion, swarm, budget=5000)

    assert rep["swarm_lift"] == 0.5
    assert rep["paired_bootstrap_ci"]["lower"] == 0.0
    assert rep["status"] == "positive_lift_ci_not_cleared"
    assert rep["ship_swarm"] is False
