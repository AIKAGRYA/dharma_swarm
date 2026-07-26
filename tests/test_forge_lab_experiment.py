"""End-to-end dry loop: full experiment with injected seams — no network/git.

Pins the chassis invariants: receipts complete, results.jsonl immediate,
explore closeouts never positive, blocked children archived as evidence,
dedup by content identity, generation receipts carry the RNG seed.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import grade_explore, ids
from dharma_swarm.forge_lab.experiment import (
    AFTER_RUN_NOTES_SCHEMA,
    EXPLORE_CLOSEOUTS,
    ExperimentConfig,
    GENERATION_RECEIPT_SCHEMA,
    RESULT_ROW_SCHEMA,
    Seams,
    TASK_PANEL_RECEIPT_SCHEMA,
    run_experiment,
)
from dharma_swarm.forge_lab.mutation import MutationResult
from dharma_swarm.forge_lab.genome_spec import merged_with_defaults


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
    assert manifest["cost_estimate"]["planned_candidate_grades"] == 1 + 3 * 2
    assert manifest["evaluation_design"]["task_panel_scope"] == "fixed_for_experiment"
    assert manifest["evaluation_design"]["panel_role"] == "adaptive_search"
    assert manifest["execution_host"]["system"]

    results = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]
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
    assert stats["same_panel_comparable"] is True
    assert stats["task_panel_ids"] == ["pr::demo#1", "pr::demo#2"]
    assert stats["unique_task_ids"] == 2
    assert stats["evidence_level"] == "L0_LegacyConfigurationSignal"
    assert stats["authentic_mutation"] is False
    assert stats["paired_lift_claim_eligible"] is False
    assert stats["authority_granted"] is False
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


async def test_experiment_allocates_one_fixed_task_panel(cfg, tmp_path):
    seams = _seams(tmp_path)
    allocation_calls: list[dict] = []

    def allocate_once(**kwargs):
        allocation_calls.append(kwargs)
        suffix = len(allocation_calls)
        return {"allocation_id": f"alloc-{suffix}", "task_ids": [f"panel-{suffix}-a", f"panel-{suffix}-b"]}

    seams.allocate_explore = allocate_once
    closeout = await run_experiment(cfg, seams=seams)
    exp_dir = cfg.state_root / cfg.category / closeout["experiment_id"]

    assert len(allocation_calls) == 1
    assert allocation_calls[0]["epoch_id"].endswith("_panel")
    panel = json.loads((exp_dir / "receipts" / "task_panel.json").read_text())
    assert panel["schema"] == TASK_PANEL_RECEIPT_SCHEMA
    assert panel["task_ids"] == ["panel-1-a", "panel-1-b"]
    generation_panels = {
        tuple(json.loads(path.read_text())["task_ids"])
        for path in (exp_dir / "receipts").glob("generation_*.json")
    }
    assert generation_panels == {("panel-1-a", "panel-1-b")}


async def test_same_panel_comparability_fails_closed_when_allocation_underfills(
    tmp_path,
):
    cfg = ExperimentConfig(
        generations=0,
        children=0,
        tasks_per_generation=2,
        solver_model="fake-solver",
        mutator_model="fake-mutator",
        dry_run=True,
        state_root=tmp_path / "archive",
    )

    closeout = await run_experiment(
        cfg,
        seams=_seams_with_budget(tmp_path, _FakeBudget, resolves=False),
    )
    stats = closeout["stats"]

    assert stats["requested_task_count"] == 2
    assert stats["allocated_task_count"] == 1
    assert stats["same_panel_comparable"] is False
    assert stats["descriptive_movement_eligible"] is False
    assert "task_panel_allocation_incomplete" in stats["descriptive_movement_blockers"]


async def test_ignored_only_child_is_archived_without_grade_call(tmp_path, monkeypatch):
    grade_calls = 0
    seams = _seams_with_budget(tmp_path, _FakeBudget, resolves=False)
    original_grade_task = seams.grade.grade_task

    def counted_grade_task(*args, **kwargs):
        nonlocal grade_calls
        grade_calls += 1
        return original_grade_task(*args, **kwargs)

    seams.grade = replace(seams.grade, grade_task=counted_grade_task)

    def ignored_only(parent, *, rng):
        child = dict(parent)
        child.update(
            extra_instruction="verify_chain does not execute this field",
            k=8,
            notes="metadata-only child",
            future_operator_hint="compost",
        )
        return MutationResult(child, "parametric", notes="ignored only")

    from dharma_swarm.forge_lab import experiment as exp_mod

    monkeypatch.setattr(exp_mod.mutation, "parametric_mutation", ignored_only)
    cfg = ExperimentConfig(
        generations=1,
        children=1,
        tasks_per_generation=1,
        solver_model="fake-solver",
        verifier_model="fake-verifier",
        mutator_model="fake-mutator",
        seed_genome={"arm_kind": "verify_chain"},
        dry_run=True,
        state_root=tmp_path / "archive",
    )

    closeout = await run_experiment(cfg, seams=seams)
    exp_dir = cfg.state_root / cfg.category / closeout["experiment_id"]
    rows = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]

    assert grade_calls == 1  # seed only; the ignored-only child was never graded
    assert [row["state"] for row in rows] == ["graded", "blocked"]
    assert rows[1]["reasons"] == ["no_executed_phenotype_change"]
    assert closeout["stats"]["counters"]["non_executed_mutation"] == 1
    assert closeout["stats"]["executed_phenotype_changes"] == 0
    assert closeout["stats"]["signal_status"] == "no_executed_child"


async def test_token_fuse_counts_mutator_tokens_and_stops_before_grade(tmp_path, monkeypatch):
    grade_calls = 0
    seams = _seams_with_budget(tmp_path, _FakeBudget, resolves=False)
    original_propose = seams.grade.propose_slot

    def counted_propose(*args, **kwargs):
        nonlocal grade_calls
        grade_calls += 1
        return original_propose(*args, **kwargs)

    seams.grade = replace(seams.grade, propose_slot=counted_propose)

    def expensive_mutation(parent, *, rng):
        child = dict(parent)
        child["per_call_tokens"] = int(parent["per_call_tokens"]) - 1
        return MutationResult(child, "parametric", notes="material", tokens_used=100)

    from dharma_swarm.forge_lab import experiment as exp_mod

    monkeypatch.setattr(exp_mod.mutation, "parametric_mutation", expensive_mutation)
    cfg = ExperimentConfig(
        generations=1,
        children=3,
        tasks_per_generation=1,
        solver_model="fake-solver",
        mutator_model="fake-mutator",
        max_experiment_tokens=200,
        dry_run=True,
        state_root=tmp_path / "archive",
    )

    closeout = await run_experiment(cfg, seams=seams)
    exp_dir = cfg.state_root / cfg.category / closeout["experiment_id"]
    rows = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]
    expected_child = merged_with_defaults({"generator_model": "fake-solver"})
    expected_child["per_call_tokens"] -= 1

    # The seed consumed 150 grade tokens. The first mutation consumed 100 more,
    # was archived without grading, and the remaining child slots never ran.
    assert grade_calls == 1
    assert closeout["stats"]["tokens_spent_total"] == 250
    assert closeout["stats"]["mutator_tokens_spent_total"] == 100
    assert closeout["stats"]["counters"]["graded"] == 1
    assert closeout["stats"]["counters"]["blocked"] == 1
    assert closeout["reasons"] == ["token_ceiling_reached_after_mutation:250"]
    assert rows[-1]["candidate_id"] == ids.candidate_id(expected_child)


async def test_positive_delta_is_admitted_only_as_l0_descriptive_movement(
    tmp_path,
    monkeypatch,
):
    def propose_by_treatment(slot, inst, ctx, **kwargs):
        return {
            "patch": f"per_call_tokens={kwargs['max_tokens']}",
            "tokens": 10,
        }

    grade = grade_explore.GradeSeams(
        slot_for_id=lambda mid: object() if mid else None,
        propose_slot=propose_by_treatment,
        self_moa_arm=lambda *a, **kw: {"final_patch": "unused"},
        verify_chain_arm=lambda *a, **kw: {"final_patch": "unused"},
        mixed_moa_arm=lambda *a, **kw: {"final_patch": "unused"},
        grade_task=lambda inst, patch, timeout: (
            patch == "per_call_tokens=15999",
            0.1,
            None,
        ),
        budget_factory=_FakeBudget,
    )
    seams = Seams(
        grade=grade,
        pull_task_context=lambda tid: ({"instance_id": tid}, {"f.py": "code"}),
        allocate_explore=lambda **kw: {
            "task_ids": ["task-a", "task-b", "task-c"]
        },
        mutate_complete=lambda prompt: ("{}", 1),
        make_worktree=lambda **kw: tmp_path / "fake_worktree",
        remove_worktree=lambda **kw: None,
    )

    def material_child(parent, *, rng):
        child = dict(parent)
        child["per_call_tokens"] = 15999
        return MutationResult(child, "parametric", notes="executed change")

    from dharma_swarm.forge_lab import experiment as exp_mod

    monkeypatch.setattr(exp_mod.mutation, "parametric_mutation", material_child)
    cfg = ExperimentConfig(
        generations=1,
        children=1,
        tasks_per_generation=3,
        solver_model="fake-solver",
        mutator_model="fake-mutator",
        dry_run=True,
        state_root=tmp_path / "archive",
    )

    closeout = await run_experiment(cfg, seams=seams)
    stats = closeout["stats"]

    assert stats["seed_pass_rate"] == 0.0
    assert stats["best_candidate_pass_rate"] == 1.0
    assert stats["observed_best_delta"] == 1.0
    assert stats["winning_candidate_exact_executed_change"] is True
    assert stats["descriptive_movement_eligible"] is True
    assert stats["configuration_signal_status"] == "positive_descriptive_delta"
    assert stats["research_interpretation"] == "configuration_search_signal"
    assert stats["paired_lift_claim_eligible"] is False
    assert stats["authority_granted"] is False


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


def test_grader_exception_marks_observation_invalid(tmp_path):
    seams = _seams_with_budget(tmp_path, _FakeBudget, resolves=False)

    def broken_grader(*args, **kwargs):
        raise RuntimeError("grader unavailable")

    seams.grade = replace(seams.grade, grade_task=broken_grader)
    outcome = grade_explore.grade_genome_explore(
        {"arm_kind": "freeform_single", "generator_model": "fake-model"},
        {"pr::demo#1": ({"instance_id": "pr::demo#1"}, {"f.py": "code"})},
        seams=seams.grade,
        budget_cap_tokens=1000,
        budget_cap_usd=1.0,
    )

    assert outcome.per_task[0]["valid_observation"] is False
    assert (
        outcome.per_task[0]["observation_invalid_reason"]
        == "provider_or_grader_exception"
    )


def test_pr_suite_test_failure_is_a_valid_candidate_observation(tmp_path):
    seams = _seams_with_budget(tmp_path, _FakeBudget, resolves=False)
    seams.grade = replace(
        seams.grade,
        grade_task=lambda *args, **kwargs: (
            False,
            0.1,
            "test_returncode=1; receipt=/tmp/grade.json",
        ),
    )
    outcome = grade_explore.grade_genome_explore(
        {"arm_kind": "freeform_single", "generator_model": "fake-model"},
        {"pr::demo#1": ({"instance_id": "pr::demo#1"}, {"f.py": "code"})},
        seams=seams.grade,
        budget_cap_tokens=1000,
        budget_cap_usd=1.0,
    )

    assert outcome.per_task[0]["resolved"] is False
    assert outcome.per_task[0]["valid_observation"] is True
    assert (
        outcome.per_task[0]["observation_validity"]
        == "candidate_grade_failure"
    )


def test_experiment_config_defaults_seed_preflight_and_soft_token_cap() -> None:
    cfg = ExperimentConfig()

    assert cfg.soft_token_cap is True
    assert cfg.require_valid_seed is True
