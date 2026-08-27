"""Tests for the foundry inner loop and elite grid."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

import pytest

from dharma_swarm.foundry.army import ROLE_HARD, ROLE_MASS, ArmyModel, MutationBudget
from dharma_swarm.foundry.elite_grid import EliteGrid
from dharma_swarm.foundry.evaluator import (
    Candidate,
    CallableEvaluator,
    EvalMetrics,
    EvaluationRunIdentity,
    bind_isolation_proof,
)
from dharma_swarm.foundry.loop import FoundryLoop

_SPEED = re.compile(r"SPEED=([0-9.]+)")


def _score_from_diff(diff: str, scale: float = 1.0) -> EvalMetrics:
    m = _SPEED.search(diff)
    val = float(m.group(1)) * scale if m else 0.0
    return EvalMetrics(primary_score=val, correctness_passed=True,
                       metrics={"speedup": val}, wall_clock_s=0.5)


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
    scale: float = 1.0,
    eid: str = "eval",
    *,
    proven: bool = False,
) -> CallableEvaluator:
    calls = 0

    def score(candidate, seed):
        nonlocal calls
        calls += 1
        metrics = _score_from_diff(candidate.diff, scale)
        identity = EvaluationRunIdentity.from_execution(
            run_id=f"{eid}:{candidate.candidate_id}:{seed}:{calls}",
            command=["oracle", eid, str(seed)],
            output={"score": metrics.primary_score},
        )
        return EvalMetrics(
            primary_score=metrics.primary_score,
            correctness_passed=metrics.correctness_passed,
            metrics=metrics.metrics,
            wall_clock_s=metrics.wall_clock_s,
            isolation_proof=(
                bind_isolation_proof(
                    _Proof(), candidate=candidate, evaluator_id=eid, seed=seed,
                    run_identity=identity,
                )
                if proven
                else None
            ),
            run_identity=identity,
        )

    return CallableEvaluator(evaluator_id=eid, score_fn=score)


def _honest_proposer(model, parent_id, seed):
    speed = round((seed % 5) * 0.5 + 0.5, 2)
    diff = f"--- a/kernels/k.py\n+++ b/kernels/k.py\n+SPEED={speed}\n"
    return Candidate(candidate_id=f"{model.id}-{seed}", target_id="t", diff=diff,
                     origin_model=model.id, parent_id=parent_id)


def _hacking_proposer(model, parent_id, seed):
    # Touches the grader, not the kernel — the classic out-of-scope hack.
    diff = "--- a/grader.py\n+++ b/grader.py\n+SPEED=999.0\n"
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


def test_loop_halts_on_killswitch(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "STOP").write_text("halt")
    loop = FoundryLoop(
        evaluator=_evaluator(), propose_fn=_honest_proposer,
        allowed_paths=["kernels/*.py"], state_root=state,
    )
    assert loop.run(5) == []


def test_loop_prepares_primary_and_distinct_heldout_evaluators_once():
    primary = _evaluator()
    heldout = _evaluator(0.8, "heldout")
    primary_calls = []
    heldout_calls = []
    primary.prepare = lambda: primary_calls.append("prepare")
    heldout.prepare = lambda: heldout_calls.append("prepare")
    FoundryLoop(
        evaluator=primary,
        propose_fn=_honest_proposer,
        heldout_evaluators={"h1": heldout, "h1-alias": heldout},
        allowed_paths=["kernels/*.py"],
    )
    assert primary_calls == ["prepare"]
    assert heldout_calls == ["prepare"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"per_generation": -1},
        {"timing_floor_s": float("inf")},
        {"survival_threshold": float("nan")},
        {"win_floor": float("inf")},
        {"budget": MutationBudget(cap_usd=float("inf"))},
    ],
)
def test_loop_rejects_non_finite_or_invalid_control_values(overrides):
    with pytest.raises(ValueError):
        FoundryLoop(
            evaluator=_evaluator(),
            propose_fn=_honest_proposer,
            allowed_paths=["kernels/*.py"],
            **overrides,
        )


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


def test_unproven_heldout_survivor_cannot_promote():
    promoted = []
    loop = FoundryLoop(
        evaluator=_evaluator(),
        propose_fn=_honest_proposer,
        heldout_evaluators={"h1": _evaluator(0.8, "h1")},
        allowed_paths=["kernels/*.py"],
        per_generation=6,
        on_survivor=lambda candidate, fitness, outcome: promoted.append(candidate),
    )
    reports = loop.run(2)
    assert sum(report.ring2_checked for report in reports) > 0
    assert sum(report.ring2_promotion_blocked for report in reports) > 0
    assert sum(report.ring2_survivors for report in reports) == 0
    assert promoted == []


def test_all_proven_rings_can_reach_survivor_callback():
    promoted = []
    loop = FoundryLoop(
        evaluator=_evaluator(proven=True),
        propose_fn=_honest_proposer,
        heldout_evaluators={"h1": _evaluator(0.8, "h1", proven=True)},
        allowed_paths=["kernels/*.py"],
        per_generation=6,
        on_survivor=lambda candidate, fitness, outcome: promoted.append(
            (candidate, outcome)
        ),
    )
    reports = loop.run(2)
    assert sum(report.ring2_survivors for report in reports) > 0
    assert promoted
    ring1 = promoted[0][1].isolation_proofs["ring1"]
    assert ring1["schema_version"] == "foundry_ring1_isolation.v1"
    assert ring1["primary"]
    assert ring1["determinism_recheck"]


def test_determinism_recheck_also_requires_isolation_proof():
    calls = 0

    def score(candidate, seed):
        nonlocal calls
        calls += 1
        metrics = _score_from_diff(candidate.diff)
        identity = EvaluationRunIdentity.from_execution(
            run_id=f"alternating-proof:{candidate.candidate_id}:{seed}:{calls}",
            command=["oracle", "alternating-proof", str(seed)],
            output={"score": metrics.primary_score},
        )
        return EvalMetrics(
            primary_score=metrics.primary_score,
            correctness_passed=True,
            metrics=metrics.metrics,
            wall_clock_s=metrics.wall_clock_s,
            isolation_proof=(
                bind_isolation_proof(
                    _Proof(), candidate=candidate, evaluator_id="alternating-proof",
                    seed=seed, run_identity=identity,
                )
                if calls % 2
                else None
            ),
            run_identity=identity,
        )

    promoted = []
    loop = FoundryLoop(
        evaluator=CallableEvaluator(evaluator_id="alternating-proof", score_fn=score),
        propose_fn=_honest_proposer,
        heldout_evaluators={"h1": _evaluator(0.8, "h1", proven=True)},
        allowed_paths=["kernels/*.py"],
        per_generation=6,
        on_survivor=lambda candidate, fitness, outcome: promoted.append(candidate),
    )
    reports = loop.run(2)
    assert sum(report.ring2_promotion_blocked for report in reports) > 0
    assert sum(report.ring2_survivors for report in reports) == 0
    assert promoted == []


@pytest.mark.parametrize("varying_digest", ["command", "output"])
def test_ring1_recheck_requires_matching_command_and_output(varying_digest):
    calls = 0

    def score(candidate, seed):
        nonlocal calls
        calls += 1
        metrics = _score_from_diff(candidate.diff)
        identity = EvaluationRunIdentity.from_execution(
            run_id=f"digest-recheck:{calls}",
            command=["oracle", calls if varying_digest == "command" else "stable"],
            output={
                "score": metrics.primary_score,
                "nonce": calls if varying_digest == "output" else "stable",
            },
        )
        return EvalMetrics(
            primary_score=metrics.primary_score,
            correctness_passed=True,
            isolation_proof=bind_isolation_proof(
                _Proof(), candidate=candidate, evaluator_id="digest-recheck",
                seed=seed, run_identity=identity,
            ),
            run_identity=identity,
        )

    loop = FoundryLoop(
        evaluator=CallableEvaluator(evaluator_id="digest-recheck", score_fn=score),
        propose_fn=_honest_proposer,
        allowed_paths=["kernels/*.py"],
    )
    candidate = Candidate(
        candidate_id="digest-candidate", target_id="t",
        diff="+++ b/kernels/k.py\n+SPEED=1.0\n",
    )
    fitness, _, _, promotion, proof = loop._ring1(candidate, seed=0)
    assert fitness == 1.0
    assert promotion is False
    assert proof is None


def test_win_floor_rejects_baseline_reproduction():
    loop = FoundryLoop(
        evaluator=_evaluator(),
        propose_fn=_honest_proposer,
        allowed_paths=["kernels/*.py"],
        win_floor=10.0,
        per_generation=6,
    )
    reports = loop.run(2)
    assert sum(report.ring1_wins for report in reports) == 0


def test_zero_fitness_is_never_a_win_even_with_negative_floor():
    evaluator = CallableEvaluator(
        evaluator_id="negative",
        score_fn=lambda candidate, seed: EvalMetrics(
            primary_score=-2.0,
            correctness_passed=True,
        ),
    )
    loop = FoundryLoop(
        evaluator=evaluator,
        propose_fn=_honest_proposer,
        allowed_paths=["kernels/*.py"],
        win_floor=-5.0,
        per_generation=6,
    )
    reports = loop.run(2)
    assert sum(report.ring1_wins for report in reports) == 0


def test_provider_error_is_not_a_proposal_or_budget_charge():
    def failed_provider(model, parent_id, seed):
        return Candidate(
            candidate_id=f"failed-{seed}",
            target_id="t",
            diff="",
            origin_model=model.id,
            metadata={
                "proposal_status": "provider_error",
                "provider_error": "routes_exhausted",
            },
        )

    loop = FoundryLoop(evaluator=_evaluator(), propose_fn=failed_provider, per_generation=4)
    reports = loop.run(2)
    assert sum(report.provider_failures for report in reports) > 0
    assert sum(report.proposed for report in reports) == 0
    assert sum(report.spend_usd for report in reports) == 0.0
    assert all(report.trip_reasons.get("provider_error", 0) > 0 for report in reports)
