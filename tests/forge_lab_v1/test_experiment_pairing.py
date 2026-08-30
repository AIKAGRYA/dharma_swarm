from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import experiment, grade_explore, mutation


class _Budget:
    def __init__(self, cap_tokens: int, cap_usd: float):
        self.spent = 0
        self.invalid = False
        self.invalid_reason = None

    def charge(self, _component: str, tokens: int, **_kwargs: object) -> int:
        self.spent += int(tokens)
        return self.spent

    def to_dict(self) -> dict[str, object]:
        return {"spent_tokens": self.spent, "invalid": False}


def test_generation_regrades_seed_and_child_on_the_exact_same_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grade = grade_explore.GradeSeams(
        slot_for_id=lambda model_id: SimpleNamespace(model_id=model_id),
        propose_slot=lambda *_args, **_kwargs: {"patch": "diff", "tokens": 10},
        self_moa_arm=lambda *_args, **_kwargs: {"final_patch": "diff"},
        verify_chain_arm=lambda *_args, **_kwargs: {"final_patch": "diff"},
        mixed_moa_arm=lambda *_args, **_kwargs: {"final_patch": "diff"},
        grade_task=lambda _inst, _patch, timeout: (False, 0.1, None),
        budget_factory=_Budget,
    )

    def mutate(parent: dict[str, object], *, rng: object) -> mutation.MutationResult:
        child = dict(parent)
        child["extra_instruction"] = "paired child"
        return mutation.MutationResult(
            genome=child,
            operator="deterministic-test",
            notes="paired child",
        )

    monkeypatch.setattr(experiment.mutation, "parametric_mutation", mutate)
    seams = experiment.Seams(
        grade=grade,
        allocate_explore=lambda **kwargs: {
            "task_ids": [f"task::{kwargs['epoch_id']}"]
        },
        pull_task_context=lambda task_id: (
            {"instance_id": task_id},
            {"f.py": "x"},
        ),
    )
    cfg = experiment.ExperimentConfig(
        generations=1,
        children=1,
        tasks_per_generation=1,
        solver_model="offline-fixture",
        verifier_model="offline-verifier",
        dry_run=True,
        source_repo=tmp_path / "source",
        state_root=tmp_path / "archive-root",
        max_experiment_tokens=1000,
        budget_cap_tokens=100,
        budget_cap_usd=0.0,
    )

    closeout = asyncio.run(experiment.run_experiment(cfg, seams))

    assert closeout["closeout_state"] == "measured_negative"
    assert closeout["stats"]["counters"]["paired_controls"] == 1
    assert closeout["stats"]["infrastructure_observations_total"] == 0
    exp_dir = next((tmp_path / "archive-root" / "agent_evolution").iterdir())
    generation = json.loads(
        (exp_dir / "receipts" / "generation_001.json").read_text(encoding="utf-8")
    )
    assert generation["paired_control"]["role"] == "paired_control"
    assert generation["children"][0]["paired_delta"] == 0.0
    assert generation["children"][0]["comparison_block_id"] == generation[
        "comparison_block_id"
    ]

    rows = [
        json.loads(line)
        for line in (exp_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    control = next(row for row in rows if row["role"] == "paired_control")
    child = next(row for row in rows if row["role"] == "candidate")
    assert [row["task_id"] for row in control["per_task"]] == [
        row["task_id"] for row in child["per_task"]
    ]
    assert control["comparison_block_id"] == child["comparison_block_id"]
