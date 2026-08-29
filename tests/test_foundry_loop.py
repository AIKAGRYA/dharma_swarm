"""Tests for the foundry inner loop and elite grid."""

from __future__ import annotations

import re

from dharma_swarm.foundry.army import ROLE_HARD, ROLE_MASS, ArmyModel, MutationBudget
from dharma_swarm.foundry.elite_grid import EliteGrid
from dharma_swarm.foundry.evaluator import Candidate, CallableEvaluator, EvalMetrics
from dharma_swarm.foundry.loop import FoundryLoop

_SPEED = re.compile(r"SPEED=([0-9.]+)")


def _score_from_diff(diff: str, scale: float = 1.0) -> EvalMetrics:
    m = _SPEED.search(diff)
    val = float(m.group(1)) * scale if m else 0.0
    return EvalMetrics(primary_score=val, correctness_passed=True,
                       metrics={"speedup": val}, wall_clock_s=0.5)


def _evaluator(scale: float = 1.0, eid: str = "eval") -> CallableEvaluator:
    return CallableEvaluator(evaluator_id=eid, score_fn=lambda c, s: _score_from_diff(c.diff, scale))


def _honest_proposer(model, parent_id, seed):
    speed = round((seed % 5) * 0.5 + 0.5, 2)
    diff = (
        "--- a/kernels/k.py\n+++ b/kernels/k.py\n@@ -1 +1 @@\n"
        f"-BASE=0\n+SPEED={speed}\n"
    )
    return Candidate(candidate_id=f"{model.id}-{seed}", target_id="t", diff=diff,
                     origin_model=model.id, parent_id=parent_id)


def _hacking_proposer(model, parent_id, seed):
    # Touches the grader, not the kernel — the classic out-of-scope hack.
    diff = (
        "--- a/grader.py\n+++ b/grader.py\n@@ -1 +1 @@\n"
        "-BASE=0\n+SPEED=999.0\n"
    )
    return Candidate(candidate_id=f"hack-{model.id}-{seed}", target_id="t", diff=diff,
                     origin_model=model.id, parent_id=parent_id)


# --- EliteGrid -----------------------------------------------------------

def test_grid_keeps_fittest_per_bin():
    grid = EliteGrid()
    assert grid.add(("a",), "c1", 1.0)
    assert not grid.add(("a",), "c2", 0.5)   # worse -> rejected
    assert grid.add(("a",), "c3", 2.0)        # better -> replaces
    assert grid.best().candidate_id == "c3"
    assert grid.coverage() == 1


def test_grid_coverage_grows_with_niches():
    grid = EliteGrid()
    grid.add(("a",), "c1", 1.0)
    grid.add(("b",), "c2", 1.0)
    assert grid.coverage() == 2


# --- FoundryLoop ---------------------------------------------------------

def test_loop_finds_and_promotes_wins():
    loop = FoundryLoop(
        evaluator=_evaluator(),
        propose_fn=_honest_proposer,
        heldout_evaluators={"h1": _evaluator(0.8, "h1")},
        allowed_paths=["kernels/*.py"],
        per_generation=6,
    )
    reports = loop.run(4)
    assert len(reports) == 4
    assert sum(r.proposed for r in reports) > 0
    assert sum(r.ring1_wins for r in reports) > 0
    assert loop.grid.coverage() > 0
    assert loop.grid.best().fitness > 0
    # ring 2 ran on promoted elites
    assert sum(r.ring2_checked for r in reports) > 0


def test_loop_rejects_out_of_scope_hacks():
    loop = FoundryLoop(
        evaluator=_evaluator(),
        propose_fn=_hacking_proposer,
        allowed_paths=["kernels/*.py"],
        per_generation=5,
    )
    reports = loop.run(2)
    assert sum(r.ring1_wins for r in reports) == 0
    assert sum(r.tripwire_trips for r in reports) > 0
    assert loop.grid.coverage() == 0


def test_static_tripwire_never_invokes_evaluator():
    calls = {"n": 0}

    def score(candidate, seed):  # noqa: ARG001
        calls["n"] += 1
        return EvalMetrics(999.0, True)

    evaluator = CallableEvaluator("must-not-run", score)
    loop = FoundryLoop(
        evaluator=evaluator,
        propose_fn=_hacking_proposer,
        allowed_paths=["kernels/*.py"],
        per_generation=1,
    )
    report = loop.run_generation(0)
    assert report.trip_reasons == {"out_of_scope_diff": 1}
    assert calls["n"] == 0


def test_loop_halts_on_killswitch(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "STOP").write_text("halt")
    loop = FoundryLoop(
        evaluator=_evaluator(), propose_fn=_honest_proposer,
        allowed_paths=["kernels/*.py"], state_root=state,
    )
    assert loop.run(5) == []


def test_loop_respects_budget_with_metered_only_roster():
    metered = (
        ArmyModel("m1", ROLE_MASS, "openrouter", cost_in_per_m=100.0, cost_out_per_m=100.0),
        ArmyModel("m2", ROLE_HARD, "openrouter", cost_in_per_m=100.0, cost_out_per_m=100.0),
    )
    loop = FoundryLoop(
        evaluator=_evaluator(), propose_fn=_honest_proposer,
        allowed_paths=["kernels/*.py"], roster=metered,
        budget=MutationBudget(cap_usd=0.0), per_generation=4,
    )
    reports = loop.run(3)
    # Nothing affordable -> nothing proposed, no spend.
    assert sum(r.proposed for r in reports) == 0
    assert loop.budget.spent_usd == 0.0


def test_failed_zero_token_provider_call_is_not_charged():
    metered = (ArmyModel("paid", ROLE_MASS, "moonshot", 3.0, 3.0),)

    def failed_provider(model, parent_id, seed):
        return Candidate(
            candidate_id=f"{model.id}-{seed}",
            target_id="t",
            diff="",
            origin_model=model.id,
            metadata={
                "proposal_status": "provider_error",
                "provider_error": "timeout",
                "billable_tokens": 0,
                "budget_chargeable": False,
            },
        )

    loop = FoundryLoop(
        evaluator=_evaluator(),
        propose_fn=failed_provider,
        roster=metered,
        budget=MutationBudget(cap_usd=1.0),
        per_generation=1,
    )
    report = loop.run_generation(0)
    assert report.proposed == 0
    assert report.provider_failures == 1
    assert report.spend_usd == 0.0
    assert loop.budget.calls == 0
    assert report.trip_reasons == {"provider_error": 1}
