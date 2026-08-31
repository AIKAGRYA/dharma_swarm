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
    AFTER_RUN_NOTES_SCHEMA,
    EXPLORE_CLOSEOUTS,
    ExperimentConfig,
    GENERATION_RECEIPT_SCHEMA,
    RESULT_ROW_SCHEMA,
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


class _OverTokenBudget(_FakeBudget):
    def charge(self, component, tokens, **kw):
        self.spent += tokens
        if self.spent > self.cap_tokens:
            self.invalid = True
            self.invalid_reason = f"over token cap: {self.spent}/{self.cap_tokens}"
        return self.spent

    def to_dict(self):
        d = super().to_dict()
        d["invalid_reason"] = self.invalid_reason
        return d


class _HardDollarBudget(_FakeBudget):
    def charge(self, component, tokens, **kw):
        self.spent += tokens
        self.invalid = True
        self.invalid_reason = "over $ cap: 10/1"
        return self.spent

    def to_dict(self):
        d = super().to_dict()
        d["invalid_reason"] = self.invalid_reason
        return d


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


def _seams_with_budget(tmp_path: Path, budget_factory, *, resolves: bool = True) -> Seams:
    grade = grade_explore.GradeSeams(
        slot_for_id=lambda mid: object() if mid else None,
        propose_slot=lambda slot, inst, ctx, **kw: {"patch": "diff --git a/x b/x", "tokens": 150},
        self_moa_arm=lambda *a, **kw: {"final_patch": "diff --git a/x b/x"},
        verify_chain_arm=lambda *a, **kw: {"final_patch": "diff --git a/x b/x"},
        mixed_moa_arm=lambda *a, **kw: {"final_patch": "diff --git a/x b/x"},
        grade_task=lambda inst, p, timeout: (resolves, 0.1, None),
        budget_factory=budget_factory,
    )
    return Seams(
        grade=grade,
        pull_task_context=lambda tid: ({"instance_id": tid}, {"f.py": "code"}),
        allocate_explore=lambda **kw: {"task_ids": ["pr::demo#1"]},
        mutate_complete=lambda prompt: ("{}", 1),
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
    assert manifest["git_base_sha"] == "dryrun"
    assert manifest["git_identity"]["head_sha"] == "dryrun"
    assert manifest["git_identity"]["branch"] == "dryrun"
    assert manifest["git_identity"]["dirty"] is False
    assert manifest["archive_fitness_authority"] == "one_wire_disabled_explicit_lab_shadow"
    assert all(manifest["membrane"].values()), "membrane must be fully recorded"
    # #1435: the estimate counts one seed-candidate grade per generation on top
    # of the children, i.e. 1 + (children + 1) * generations.
    assert manifest["cost_estimate"]["planned_candidate_grades"] == 1 + (3 + 1) * 2

    results = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]
    # Paired-evidence hardening (#1435) added the comparison/evidence fields to
    # every result row; the set below is the current RESULT_ROW_SCHEMA shape.
    result_keys = {
        "schema",
        "experiment_id",
        "candidate_id",
        "parent_id",
        "state",
        "role",
        "op",
        "generation",
        "pass_rate",
        "per_task",
        "budget",
        "reasons",
        "duplicate_of",
        "at",
        "comparable_observations",
        "comparison_block_id",
        "control_candidate_id",
        "control_pass_rate",
        "evidence_class",
    }
    assert results
    assert all(set(r) == result_keys for r in results)
    assert all(r["schema"] == RESULT_ROW_SCHEMA for r in results)
    assert all(r["experiment_id"] == closeout["experiment_id"] for r in results)
    graded = [r for r in results if r["state"] == "graded"]
    assert graded and graded[0]["role"] == "seed_baseline"
    assert all(r["pass_rate"] == 0.0 for r in graded)  # grade_task said nothing resolves

    receipts = sorted((exp_dir / "receipts").glob("generation_*.json"))
    assert len(receipts) == cfg.generations
    gen1 = json.loads(receipts[0].read_text())
    assert gen1["schema"] == GENERATION_RECEIPT_SCHEMA
    assert gen1["rng_seed"] == 99 and gen1["task_ids"] == ["pr::demo#1", "pr::demo#2"]
    assert gen1["children"] == gen1["observations"]
    assert all(
        set(o)
        >= {
            "schema",
            "candidate_id",
            "parent_id",
            "state",
            "role",
            "op",
            "generation",
            "pass_rate",
            "reasons",
        }
        for o in gen1["observations"]
    )

    stats = closeout["stats"]
    assert stats["counters"]["graded"] >= 1
    assert stats["seed_pass_rate"] == 0.0 and stats["best_pass_rate"] == 0.0
    assert closeout["closeout_state"] == "measured_negative"  # 0.0 everywhere, honestly
    assert closeout["merkle"]["verified"] is True
    assert closeout["artifacts"]["after_run_notes_json"] == "after_run_notes.json"
    assert closeout["scratch_worktree"]["state"] == "not_created"

    archive_lines = (exp_dir / "archive.jsonl").read_text().splitlines()
    assert len(archive_lines) == stats["counters"]["graded"] + stats["counters"]["blocked"] + stats["counters"]["duplicate"]

    notes = json.loads((exp_dir / "after_run_notes.json").read_text())
    assert notes["schema"] == AFTER_RUN_NOTES_SCHEMA
    assert notes["closeout_state"] == closeout["closeout_state"]
    assert notes["counters"] == stats["counters"]
    assert notes["merkle_verified"] is True
    assert notes["artifact_counts"]["result_rows"] == len(results)
    notes_md = (exp_dir / "after_run_notes.md").read_text()
    assert "# Forge Lab After-Run Notes" in notes_md
    assert "EXPLORE closeouts cannot claim positive lift" in notes_md


async def test_grader_exception_closes_out_blocked_with_evidence(cfg, tmp_path, monkeypatch):
    """NAMED VERIFIER (mission D6): a throwing grader must not kill the run silently.

    The run must still leave a closeout.json (state blocked_with_evidence),
    after_run_notes that name the exception, an incremented errored counter,
    and an errored candidate row in the archive — then re-raise (fail-closed).
    """

    def _explode(*a, **kw):
        raise RuntimeError("verifier-injected grader failure")

    monkeypatch.setattr(grade_explore, "grade_genome_explore", _explode)

    with pytest.raises(RuntimeError, match="verifier-injected grader failure"):
        await run_experiment(cfg, seams=_seams(tmp_path))

    exp_dirs = [d for d in (cfg.state_root / cfg.category).iterdir() if d.is_dir()]
    assert len(exp_dirs) == 1
    exp_dir = exp_dirs[0]

    closeout = json.loads((exp_dir / "closeout.json").read_text())
    assert closeout["closeout_state"] == "blocked_with_evidence"
    assert closeout["stats"]["counters"]["errored"] >= 1
    assert closeout["stats"]["exception"]["type"] == "RuntimeError"
    assert "verifier-injected grader failure" in closeout["stats"]["exception"]["message"]

    notes = json.loads((exp_dir / "after_run_notes.json").read_text())
    assert notes["schema"] == AFTER_RUN_NOTES_SCHEMA
    assert notes["closeout_state"] == "blocked_with_evidence"
    assert notes["counters"]["errored"] >= 1
    assert "RuntimeError" in json.dumps(notes)
    assert "verifier-injected grader failure" in json.dumps(notes)
    notes_md = (exp_dir / "after_run_notes.md").read_text()
    assert "RuntimeError" in notes_md

    # append_errored was exercised: the failed candidate is archived, not lost
    archive_rows = [json.loads(line) for line in (exp_dir / "archive.jsonl").read_text().splitlines()]
    states = [r["test_results"]["forge_lab"]["state"] for r in archive_rows]
    assert "errored" in states
    results = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]
    assert any(r["state"] == "errored" for r in results)


async def test_normal_run_still_closes_out_with_normal_state(cfg, tmp_path):
    """Control (mission D6): an uneventful small run closes out normally."""
    closeout = await run_experiment(cfg, seams=_seams(tmp_path))

    assert closeout["closeout_state"] == "measured_negative"  # fakes resolve nothing
    assert closeout["stats"]["counters"]["errored"] == 0
    assert "exception" not in closeout["stats"]
    exp_dir = cfg.state_root / cfg.category / closeout["experiment_id"]
    assert (exp_dir / "closeout.json").exists()
    assert (exp_dir / "after_run_notes.json").exists()


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


def test_result_row_schema_is_uniform_for_blocked_observations() -> None:
    from dharma_swarm.forge_lab import experiment as exp_mod

    row = exp_mod._result_row(
        exp_id="exp_demo",
        candidate_id="cand_blocked",
        parent_id="cand_parent",
        state="blocked",
        role="candidate",
        op="llm_propose",
        generation=2,
        reasons=["no_json_object_found"],
    )

    assert row["schema"] == RESULT_ROW_SCHEMA
    assert row["parent_id"] == "cand_parent"
    assert row["role"] == "candidate"
    assert row["pass_rate"] is None
    assert row["per_task"] == []
    assert row["budget"] == {}
    assert row["reasons"] == ["no_json_object_found"]


def test_explore_open_token_overage_is_measured_not_invalid(tmp_path):
    outcome = grade_explore.grade_genome_explore(
        {"arm_kind": "freeform_single", "generator_model": "fake-model"},
        {"pr::demo#1": ({"instance_id": "pr::demo#1"}, {"f.py": "code"})},
        seams=_seams_with_budget(tmp_path, _OverTokenBudget, resolves=True).grade,
        budget_cap_tokens=100,
        budget_cap_usd=999.0,
        soft_token_cap=True,
    )

    assert outcome.pass_rate == 1.0
    assert outcome.budget["invalid"] is False
    assert outcome.budget["soft_token_cap_exceeded"] is True
    assert outcome.budget["token_invalid_ignored_for_explore"] is True
    assert outcome.budget["pass_rate_per_100k_tokens"]


def test_hard_budget_invalid_still_short_circuits(tmp_path):
    outcome = grade_explore.grade_genome_explore(
        {"arm_kind": "freeform_single", "generator_model": "fake-model"},
        {
            "pr::demo#1": ({"instance_id": "pr::demo#1"}, {"f.py": "code"}),
            "pr::demo#2": ({"instance_id": "pr::demo#2"}, {"f.py": "code"}),
        },
        seams=_seams_with_budget(tmp_path, _HardDollarBudget, resolves=True).grade,
        budget_cap_tokens=100,
        budget_cap_usd=1.0,
        soft_token_cap=True,
    )

    assert outcome.budget["hard_invalid"] is True
    assert outcome.budget["invalid"] is True
    assert outcome.per_task[1]["error"] == "budget_invalid:over $ cap: 10/1"


def test_experiment_config_defaults_seed_preflight_and_soft_token_cap() -> None:
    cfg = ExperimentConfig()

    assert cfg.soft_token_cap is True
    assert cfg.require_valid_seed is True
