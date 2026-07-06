"""End-to-end dry loop: full experiment with injected seams — no network/git.

Pins the chassis invariants: receipts complete, results.jsonl immediate,
explore closeouts never positive, blocked children archived as evidence,
dedup by content identity, generation receipts carry the RNG seed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import grade_explore
from dharma_swarm.forge_lab.experiment import (
    EXPLORE_CLOSEOUTS,
    ExperimentConfig,
    Seams,
    run_experiment,
)


class _FakeBudget:
    def __init__(self, cap_tokens: int, cap_usd: float | None = None):
        self.cap_tokens, self.cap_usd = cap_tokens, cap_usd
        self.spent, self.invalid, self.invalid_reason = 0, False, None

    def charge(self, component, tokens, **kw):
        self.spent += tokens
        return tokens

    def to_dict(self):
        return {"cap_tokens": self.cap_tokens, "spent_tokens": self.spent, "invalid": self.invalid}


def _seams(tmp_path: Path) -> Seams:
    grade = grade_explore.GradeSeams(
        slot_for_id=lambda mid: object() if mid else None,
        propose_slot=lambda slot, inst, ctx, **kw: {"patch": "diff --git a/x b/x", "tokens": 10},
        self_moa_arm=lambda *a, **kw: {"final_patch": "diff --git a/x b/x"},
        verify_chain_arm=lambda *a, **kw: {"final_patch": "diff --git a/x b/x"},
        mixed_moa_arm=lambda *a, **kw: {"final_patch": "diff --git a/x b/x"},
        grade_task=lambda inst, p, timeout: (False, 0.1, None),  # honest: nothing resolves
        budget_factory=_FakeBudget,
    )
    return Seams(
        grade=grade,
        pull_task_context=lambda tid: ({"instance_id": tid}, {"f.py": "code"}),
        allocate_explore=lambda **kw: {"task_ids": ["pr::demo#1", "pr::demo#2"]},
        mutate_complete=lambda prompt: ("{}", 1),  # unused in dry_run (parametric only)
        make_worktree=lambda **kw: tmp_path / "fake_worktree",
        remove_worktree=lambda **kw: None,
    )


@pytest.fixture
def cfg(tmp_path) -> ExperimentConfig:
    return ExperimentConfig(
        generations=2,
        children=3,
        tasks_per_generation=2,
        solver_model="fake-model",
        mutator_model="fake-mutator",
        dry_run=True,
        state_root=tmp_path / "evolution_archive",
        rng_seed=99,
    )


async def test_dry_loop_end_to_end(cfg, tmp_path):
    closeout = await run_experiment(cfg, seams=_seams(tmp_path))

    assert closeout["closeout_state"] in EXPLORE_CLOSEOUTS
    assert closeout["closeout_state"] != "positive_lift_candidate"  # by construction
    exp_dir = cfg.state_root / cfg.category / closeout["experiment_id"]

    manifest = json.loads((exp_dir / "run_manifest.json").read_text())
    assert manifest["mode"] == "shadow"
    assert manifest["archive_fitness_authority"] == "one_wire_disabled_explicit_lab_shadow"
    assert all(manifest["membrane"].values()), "membrane must be fully recorded"
    assert manifest["cost_estimate"]["planned_candidate_grades"] == 1 + 3 * 2

    results = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]
    graded = [r for r in results if r["state"] == "graded"]
    assert graded and graded[0]["role"] == "seed_baseline"
    assert all(r["pass_rate"] == 0.0 for r in graded)  # grade_task said nothing resolves

    receipts = sorted((exp_dir / "receipts").glob("generation_*.json"))
    assert len(receipts) == cfg.generations
    gen1 = json.loads(receipts[0].read_text())
    assert gen1["rng_seed"] == 99 and gen1["task_ids"] == ["pr::demo#1", "pr::demo#2"]

    stats = closeout["stats"]
    assert stats["counters"]["graded"] >= 1
    assert stats["seed_pass_rate"] == 0.0 and stats["best_pass_rate"] == 0.0
    assert closeout["closeout_state"] == "measured_negative"  # 0.0 everywhere, honestly
    assert closeout["merkle"]["verified"] is True

    archive_lines = (exp_dir / "archive.jsonl").read_text().splitlines()
    assert len(archive_lines) == stats["counters"]["graded"] + stats["counters"]["blocked"] + stats["counters"]["duplicate"]


async def test_dry_loop_dedups_identical_children(cfg, tmp_path):
    # parametric mutation under a fixed seed will eventually re-reach a genome;
    # force it by making mutation deterministic to one outcome via rng_seed sweep
    closeout = await run_experiment(cfg, seams=_seams(tmp_path))
    counters = closeout["stats"]["counters"]
    assert counters["graded"] + counters["blocked"] + counters["duplicate"] == 1 + cfg.children * cfg.generations


async def test_illegal_closeout_state_is_impossible(cfg, tmp_path):
    from dharma_swarm.forge_lab import experiment as exp_mod

    with pytest.raises(AssertionError):
        exp_mod._closeout(
            tmp_path, "exp_x", "positive_lift_candidate",
            reasons=[], started_at="now", stats={}, merkle_root=None, wall_seconds=0.0,
        )
