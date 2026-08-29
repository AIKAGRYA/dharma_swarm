"""Fitness custody honesty — mission Slice 3 verifier tests (L009, L022-L024).

Named verifier tests, one per sub-fix:
(a) test_append_graded_recomputes_pass_rate_and_refuses_mismatch
(b) test_budget_invalid_grade_lands_errored_never_fitness_bearing
(c) test_zero_attempted_tasks_grade_is_refused_never_graded

Only graded-AND-budget-valid rows may bear fitness. A caller-asserted
pass_rate aggregate, an over-cap budget, or a zero-attempt sweep must never
launder into a GRADED (fitness-bearing) row. Deterministic, no network/git.
"""

from __future__ import annotations

import json

import pytest

from dharma_swarm.forge_lab import grade_explore
from dharma_swarm.forge_lab.candidate_store import ERRORED, GRADED, CandidateStore
from dharma_swarm.forge_lab.experiment import ExperimentConfig, Seams, run_experiment
from dharma_swarm.forge_lab.freeform_explore import FreeformExploreEnvelope, MEMBRANE_REQUIREMENTS
from dharma_swarm.forge_lab.genome_spec import merged_with_defaults


class _FakeBudget:
    def __init__(self, cap_tokens: int, cap_usd: float | None = None):
        self.cap_tokens, self.cap_usd = cap_tokens, cap_usd
        self.spent, self.invalid, self.invalid_reason = 0, False, None

    def charge(self, component, tokens, **kw):
        self.spent += tokens
        if self.spent > self.cap_tokens:
            self.invalid = True
            self.invalid_reason = f"over token cap: {self.spent}/{self.cap_tokens}"
        return tokens

    def to_dict(self):
        return {
            "cap_tokens": self.cap_tokens,
            "spent_tokens": self.spent,
            "invalid": self.invalid,
            "invalid_reason": self.invalid_reason,
        }


def _fake_seams(patch: str = "diff --git a/f b/f", resolve: bool = True) -> grade_explore.GradeSeams:
    return grade_explore.GradeSeams(
        slot_for_id=lambda mid: object() if mid else None,
        propose_slot=lambda slot, inst, ctx, **kw: {"patch": patch, "tokens": 10},
        self_moa_arm=lambda *a, **kw: {"final_patch": patch},
        verify_chain_arm=lambda *a, **kw: {"final_patch": patch},
        mixed_moa_arm=lambda *a, **kw: {"final_patch": patch},
        grade_task=lambda inst, p, timeout: (resolve, 1.5, None),
        budget_factory=_FakeBudget,
    )


def _envelope(cid: str) -> FreeformExploreEnvelope:
    return FreeformExploreEnvelope(
        candidate_id=cid, parent_id=None, experiment_id="exp_custody",
        category="agent_evolution", membrane={name: True for name in MEMBRANE_REQUIREMENTS},
    )


# ------------------------------------------------------------ (a) pass_rate custody


async def test_append_graded_recomputes_pass_rate_and_refuses_mismatch(tmp_path):
    store = CandidateStore(tmp_path / "archive.jsonl", experiment_id="exp_custody")
    await store.load()
    per_task = [
        {"task_id": "t1", "resolved": True},
        {"task_id": "t2", "resolved": False},
    ]
    genome = {"arm_kind": "freeform_single", "generator_model": "m"}

    # Caller-asserted aggregate contradicts per-task truth => refused fail-closed.
    with pytest.raises(ValueError, match="pass_rate"):
        await store.append_graded(
            candidate_id="cand_lie", genome=genome, parent_id=None,
            generation=0, loop_iteration=0, role="seed_baseline",
            pass_rate=1.0, per_task=per_task, budget={}, tier="explore-fast-host-pytest",
            executed_fields=("arm_kind",), ignored_fields=(), envelope=_envelope("cand_lie"),
        )
    assert not await store.has("cand_lie")  # nothing fitness-bearing persisted

    # Honest caller: accepted, and the stored value IS the recomputed truth.
    entry = await store.append_graded(
        candidate_id="cand_honest", genome=genome, parent_id=None,
        generation=0, loop_iteration=0, role="seed_baseline",
        pass_rate=0.5, per_task=per_task, budget={}, tier="explore-fast-host-pytest",
        executed_fields=("arm_kind",), ignored_fields=(), envelope=_envelope("cand_honest"),
    )
    assert entry.fitness.correctness == 0.5
    row = CandidateStore._row(entry)
    assert row["state"] == GRADED and row["pass_rate"] == 0.5


# ------------------------------------------------------ (b) budget-invalid custody


async def test_budget_invalid_grade_lands_errored_never_fitness_bearing(tmp_path):
    genome = merged_with_defaults({"generator_model": "m"})

    # Grade time: the 10-token charge crosses the 5-token cap. Per the Budget
    # contract ("over cap makes the run INVALID, never just a lower score")
    # the outcome must carry an error, not a score.
    outcome = grade_explore.grade_genome_explore(
        genome, {"t1": ({}, {})},
        seams=_fake_seams(), budget_cap_tokens=5, budget_cap_usd=1.0,
    )
    assert outcome.budget["invalid"] is True
    assert outcome.error is not None and outcome.error.startswith("budget_invalid")

    # Store custody: an over-cap grade is re-routed to the errored lane even if
    # a caller tries to append it as graded — never selectable as fitness.
    store = CandidateStore(tmp_path / "archive.jsonl", experiment_id="exp_custody")
    await store.load()
    entry = await store.append_graded(
        candidate_id="cand_overcap", genome=genome, parent_id=None,
        generation=0, loop_iteration=0, role="seed_baseline",
        pass_rate=0.0,
        per_task=[{"task_id": "t1", "resolved": False, "error": outcome.error}],
        budget=outcome.budget, tier=outcome.tier,
        executed_fields=("arm_kind",), ignored_fields=(), envelope=_envelope("cand_overcap"),
    )
    row = CandidateStore._row(entry)
    assert row["state"] == ERRORED
    assert any(r.startswith("budget_invalid") for r in row["reasons"])
    assert entry.status != "shadow"  # non-fitness-bearing
    assert await store.graded_entries() == []


# ------------------------------------------------------ (c) zero-attempt custody


async def test_zero_attempted_tasks_grade_is_refused_never_graded(tmp_path):
    genome = merged_with_defaults({"generator_model": "m"})

    # No tasks allocated at all: pass_rate 0.0 here is an infra zero, not a score.
    outcome = grade_explore.grade_genome_explore(
        genome, {}, seams=_fake_seams(), budget_cap_tokens=1000, budget_cap_usd=1.0,
    )
    assert outcome.pass_rate == 0.0
    assert outcome.error == "no_tasks_attempted"

    # Every task infra-failed before any generation attempt: same refusal.
    broken = merged_with_defaults({"generator_model": "m"})
    broken["generator_model"] = ""  # slot_for_id returns None
    outcome2 = grade_explore.grade_genome_explore(
        broken, {"t1": ({}, {})},
        seams=_fake_seams(), budget_cap_tokens=1000, budget_cap_usd=1.0,
    )
    assert outcome2.error == "no_tasks_attempted"

    # Full custody chain: a zero-task experiment lands errored, never GRADED.
    cfg = ExperimentConfig(
        generations=0, children=1, tasks_per_generation=2,
        solver_model="fake-model", mutator_model="fake-mutator",
        dry_run=True, state_root=tmp_path / "evolution_archive", rng_seed=7,
    )
    seams = Seams(
        grade=_fake_seams(),
        pull_task_context=lambda tid: ({"instance_id": tid}, {"f.py": "code"}),
        allocate_explore=lambda **kw: {"task_ids": []},  # taskbed came back empty
        mutate_complete=lambda prompt: ("{}", 1),
        make_worktree=lambda **kw: tmp_path / "fake_worktree",
        remove_worktree=lambda **kw: None,
    )
    closeout = await run_experiment(cfg, seams=seams)

    counters = closeout["stats"]["counters"]
    assert counters["graded"] == 0 and counters["errored"] == 1
    assert closeout["closeout_state"] == "blocked_with_evidence"

    exp_dir = cfg.state_root / cfg.category / closeout["experiment_id"]
    results = [json.loads(line) for line in (exp_dir / "results.jsonl").read_text().splitlines()]
    assert len(results) == 1
    assert results[0]["state"] == "errored"
    assert "no_tasks_attempted" in results[0]["reasons"]

    archive_rows = [
        json.loads(line)["test_results"]["forge_lab"]
        for line in (exp_dir / "archive.jsonl").read_text().splitlines()
    ]
    assert archive_rows and all(r["state"] == "errored" for r in archive_rows)
