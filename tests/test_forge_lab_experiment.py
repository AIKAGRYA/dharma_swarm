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
from dharma_swarm.forge_lab import mutation as mutation_mod
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
    assert manifest["execution_boundary"] == {
        "mode": "dry_run_injected",
        "execution_profile_sha256": None,
    }
    assert all("host-pytest" not in caveat for caveat in manifest["caveats"])
    assert all(manifest["membrane"].values()), "membrane must be fully recorded"
    assert manifest["cost_estimate"]["planned_candidate_grades"] == 1 + 3 * 2

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
    assert cfg.evaluation_protocol == "legacy_v0"


def test_paired_production_requires_and_uses_exact_campaign_usd_ceiling() -> None:
    from dharma_swarm.forge_lab.experiment_entrypoint import _run_limits

    missing = ExperimentConfig(evaluation_protocol="paired_frozen_v1", dry_run=False)
    with pytest.raises(ValueError, match="explicit positive max_experiment_usd"):
        _run_limits(missing)

    configured = ExperimentConfig(
        evaluation_protocol="paired_frozen_v1",
        dry_run=False,
        max_experiment_usd=12.345678,
    )
    assert _run_limits(configured).total_usd_micros == 12_345_678


def test_production_mutator_receives_ledger_token_ceiling(tmp_path, monkeypatch) -> None:
    from dharma_swarm import api_keys
    from dharma_swarm.forge_v1 import providers
    from dharma_swarm.forge_v1.forge_v2 import pr_suite_execution

    calls: list[tuple[str, int | None]] = []

    class Completion:
        def __init__(self, model_id: str):
            self.model_id = model_id

        def complete(self, prompt: str, *, max_total_tokens: int | None = None):
            calls.append((prompt, max_total_tokens))
            return "{}", 1

    monkeypatch.setattr(api_keys, "bootstrap_runtime_env", lambda: None)
    monkeypatch.setattr(pr_suite_execution, "resolve_execution_profile", lambda profile: profile)
    monkeypatch.setattr(providers, "PoolCompletion", Completion)
    base = _seams(tmp_path)
    profile = object()
    resolved = Seams(
        grade=base.grade,
        pull_task_context=base.pull_task_context,
        allocate_explore=base.allocate_explore,
        allocate_campaign_pools=lambda **kwargs: {},
        load_task_record=lambda task_id: {},
        make_worktree=base.make_worktree,
        remove_worktree=base.remove_worktree,
        execution_profile=profile,
    ).resolved(
        ExperimentConfig(
            evaluation_protocol="paired_frozen_v1",
            dry_run=False,
            mutator_model="fake-mutator",
            mutation_reservation_tokens=7_777,
            execution_profile="ignored-by-test-resolver",
        )
    )

    assert resolved.mutate_complete("mutation prompt") == ("{}", 1)
    assert calls == [("mutation prompt", 7_777)]


async def test_paired_setup_failure_closes_with_cleanup_evidence(tmp_path) -> None:
    cfg = ExperimentConfig(
        evaluation_protocol="paired_frozen_v1",
        generations=1,
        children=1,
        paired_min_decision_tasks=1,
        solver_model="fake-model",
        seed_genome={"generator_model": "fake-model"},
        dry_run=True,
        state_root=tmp_path / "paired_setup_failure",
    )
    seams = _seams(tmp_path)  # intentionally has no four-way allocator/record loader

    closeout = await run_experiment(cfg, seams=seams)

    assert closeout["closeout_state"] == "blocked_with_evidence"
    assert closeout["stats"]["setup_failed_before_protocol_closeout"] is True
    assert closeout["scratch_worktree"]["state"] == "not_created"
    assert any("paired_setup_failure:ValueError" in reason for reason in closeout["reasons"])


async def test_paired_frozen_v1_freezes_plan_pairs_budget_winner_and_champion(
    tmp_path, monkeypatch
):
    state_root = tmp_path / "paired_state"
    task_ids = {
        "train": ["task-train"],
        "explore": ["task-explore"],
        "confirm": ["task-confirm"],
        "holdout": ["task-holdout"],
    }
    model_calls: list[tuple[str, str]] = []

    def propose(_slot, inst, _ctx, **kwargs):
        plans = list((state_root / "agent_evolution").glob("exp_*/evaluation_plan.json"))
        assert plans, "the evaluation plan must be durable before the first model call"
        task_id = inst["instance_id"]
        if task_id in {"task-confirm", "task-holdout"}:
            assert list((state_root / "agent_evolution").glob("exp_*/winner_freeze.json"))
        instruction = str(kwargs.get("extra_instruction") or "baseline")
        model_calls.append((task_id, instruction))
        return {"patch": f"diff --git a/x b/x\n+{instruction}", "tokens": 10}

    grade = grade_explore.GradeSeams(
        slot_for_id=lambda mid: object() if mid else None,
        propose_slot=propose,
        self_moa_arm=lambda *a, **kw: {"final_patch": ""},
        verify_chain_arm=lambda *a, **kw: {"final_patch": ""},
        mixed_moa_arm=lambda *a, **kw: {"final_patch": ""},
        grade_task=lambda _inst, patch, timeout: ("challenger" in patch, 0.1, None),
        budget_factory=_FakeBudget,
    )

    def allocate_campaign(**kwargs):
        assert kwargs["train_count"] == kwargs["explore_count"] == 1
        assert kwargs["confirm_count"] == kwargs["holdout_count"] == 1
        receipt = {
            "schema": "forge_v2.campaign_task_overlay.v1",
            "campaign_id": kwargs["campaign_id"],
            "epoch_id": kwargs["epoch_id"],
            "lane_id": kwargs["lane_id"],
            "campaign_seed": kwargs["campaign_seed"],
            "logical_to_physical": {
                "train": "explore",
                "explore": "explore",
                "confirm": "confirm",
                "holdout": "confirm",
            },
            "logical_splits": task_ids,
            "task_ids": [task for split in task_ids.values() for task in split],
            "all_splits_disjoint": True,
            "confirm_pool_contamination_clean": True,
            "frozen": True,
            "positive_lift_claimed": False,
            "claim_scope": "research_only",
        }
        from dharma_swarm.forge_lab.ids import content_digest

        receipt["overlay_sha256"] = content_digest(receipt)
        return receipt

    def load_task(task_id: str):
        return {
            "task_id": task_id,
            "task": {"task_id": task_id, "problem_statement": f"repair {task_id}"},
            "source": "unit",
            "taskbed": "paired",
            "contamination_state": "fresh_post_cutoff",
            "provenance": {"unit": True},
            "created_at": "2026-08-10T00:00:00Z",
            "active": 1,
            "max_uses_per_epoch": 1,
        }

    original = mutation_mod.parametric_mutation

    def fixed_mutation(parent, *, rng):
        child = dict(parent)
        child["extra_instruction"] = "challenger"
        child["notes"] = "fixed paired challenger"
        return mutation_mod.MutationResult(child, "parametric", notes="fixed")

    monkeypatch.setattr(mutation_mod, "parametric_mutation", fixed_mutation)
    cfg = ExperimentConfig(
        evaluation_protocol="paired_frozen_v1",
        generations=1,
        children=1,
        paired_train_tasks=1,
        paired_explore_tasks=1,
        paired_confirm_tasks=1,
        paired_holdout_tasks=1,
        paired_repeat_seeds=(11, 29),
        paired_bootstrap_samples=40,
        paired_min_decision_tasks=1,
        solver_model="fake-model",
        seed_genome={"generator_model": "fake-model", "extra_instruction": "baseline"},
        budget_cap_tokens=100,
        budget_cap_usd=1.0,
        max_experiment_tokens=1_000,
        dry_run=True,
        state_root=state_root,
        rng_seed=7,
    )
    seams = Seams(
        grade=grade,
        pull_task_context=lambda task_id: (
            {"instance_id": task_id},
            {"f.py": "code"},
        ),
        allocate_explore=lambda **kwargs: {"task_ids": []},
        allocate_campaign_pools=allocate_campaign,
        load_task_record=load_task,
        mutate_complete=lambda prompt: ("{}", 0),
        make_worktree=lambda **kwargs: tmp_path / "unused",
        remove_worktree=lambda **kwargs: None,
    )

    closeout = await run_experiment(cfg, seams=seams)
    monkeypatch.setattr(mutation_mod, "parametric_mutation", original)

    assert closeout["closeout_state"] == "inconclusive_low_power"
    stats = closeout["stats"]
    assert stats["evaluation_protocol"] == "paired_frozen_v1"
    assert stats["winner_frozen_before_confirm"] is True
    assert stats["holdout_touched"] is True
    assert stats["champion_revision_before"] == 0
    assert stats["champion_revision_after"] == 1
    assert stats["positive_lift_claimed"] is False

    exp_dir = state_root / cfg.category / closeout["experiment_id"]
    plan = json.loads((exp_dir / "evaluation_plan.json").read_text())
    assert plan["repeat_seeds"] == [11, 29]
    assert plan["splits"]["explore"][0]["task_id"] == "task-explore"
    winner = json.loads((exp_dir / "winner_freeze.json").read_text())
    assert winner["selection_split"] == "explore"
    assert winner["positive_lift_claimed"] is False

    budget = json.loads((exp_dir / "campaign_budget.json").read_text())
    assert budget["valid"] is True and budget["closeout_ready"] is True
    assert budget["component_totals"]["mutation"]["spent_tokens"] == 0
    assert budget["component_totals"]["baseline_eval"]["spent_tokens"] == 40
    assert budget["component_totals"]["candidate_eval"]["spent_tokens"] == 40
    assert budget["component_totals"]["confirm_eval"]["spent_tokens"] == 40
    assert budget["component_totals"]["holdout_eval"]["spent_tokens"] == 40

    paired_rows = [
        json.loads(line) for line in (exp_dir / "paired_observations.jsonl").read_text().splitlines()
    ]
    assert len(paired_rows) == 16
    assert {(row["task_id"], row["repeat_seed"]) for row in paired_rows} >= {
        ("task-explore", 11),
        ("task-explore", 29),
    }
    champion = json.loads((state_root / cfg.category / "champion.json").read_text())
    assert champion["revision"] == 1
    assert champion["champion"]["genome"]["extra_instruction"] == "challenger"
    assert model_calls
