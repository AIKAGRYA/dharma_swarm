from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.evolution_safety import is_scratch_worktree
from dharma_swarm.forge_lab.candidate_store import CandidateRecord
from dharma_swarm.forge_lab.experiment import ExperimentConfig, run_experiment
from dharma_swarm.forge_lab.identity import candidate_id_for_genome
from dharma_swarm.forge_lab.selection import draw_parent, novelty_weight
from dharma_swarm.forge_lab.worktree import (
    close_scratch_worktree,
    create_marked_scratch_worktree,
)
from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import register_task


def test_candidate_id_depends_on_genome_content_only() -> None:
    genome_a = {"b": 2, "a": {"x": 1}}
    genome_b = {"a": {"x": 1}, "b": 2}

    candidate_a, canonicalizer_a = candidate_id_for_genome(genome_a)
    candidate_b, canonicalizer_b = candidate_id_for_genome(genome_b)

    assert candidate_a == candidate_b
    assert canonicalizer_a == canonicalizer_b
    assert candidate_a.startswith("cand_")


def test_novelty_weight_uses_fitness_and_child_count() -> None:
    parent = CandidateRecord(
        candidate_id="cand_parent",
        parent_id=None,
        experiment_id="exp",
        category="agent_evolution",
        generation=0,
        loop_iteration=0,
        genome={},
        state="graded",
        role="seed_baseline",
        fitness={"weighted": 0.8},
    )
    crowded = novelty_weight(parent, {"cand_parent": 9}, novelty_pressure=0.7)
    fresh = novelty_weight(parent, {"cand_parent": 0}, novelty_pressure=0.7)

    assert fresh > crowded


def test_draw_parent_falls_back_to_novelty_when_fitness_zero() -> None:
    import random

    records = [
        CandidateRecord(
            candidate_id="cand_a",
            parent_id=None,
            experiment_id="exp",
            category="agent_evolution",
            generation=0,
            loop_iteration=0,
            genome={"a": 1},
            state="graded",
            role="seed_baseline",
            fitness={"weighted": 0.0},
        )
    ]

    draw = draw_parent(records, rng=random.Random(1))
    assert draw.parent.candidate_id == "cand_a"
    assert draw.weight > 0.0


def test_create_marked_scratch_worktree_validates_and_closes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "evolution_worktrees"
    archive = tmp_path / "archive"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(root))

    scratch = create_marked_scratch_worktree(
        experiment_id="exp_worktree_test",
        category="agent_evolution",
        archive_path=archive,
        source_repo=Path.cwd(),
        base_ref="HEAD",
        worktree_root=root,
    )
    try:
        ok, marker, reason = is_scratch_worktree(scratch.repo)
        assert ok is True, reason
        assert marker is not None
        assert marker.experiment_id == "exp_worktree_test"
        assert (scratch.repo / ".dharma_evolution_worktree.json").is_file()
    finally:
        close_scratch_worktree(scratch, source_repo=Path.cwd())

    assert not scratch.repo.exists()
    assert "closed" in scratch.registry_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_experiment_synthetic_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "evolution_worktrees"
    archive_root = tmp_path / "evolution_archive"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(root))

    closeout = await run_experiment(
        ExperimentConfig(
            experiment_id="exp_synthetic_smoke",
            generations=1,
            children=2,
            source_repo=Path.cwd(),
            base_ref="HEAD",
            archive_root=archive_root,
            worktree_root=root,
            max_usd=0.0,
        )
    )

    archive_dir = archive_root / "agent_evolution" / "exp_synthetic_smoke"
    assert closeout["closeout_state"] == "inconclusive_low_power"
    assert closeout["positive_lift_claim"] is False
    assert closeout["candidate_count"] >= 3
    assert (archive_dir / "run_manifest.json").is_file()
    assert (archive_dir / "candidate_records.jsonl").is_file()
    records = [json.loads(line) for line in (archive_dir / "candidate_records.jsonl").read_text().splitlines()]
    assert {record["role"] for record in records} >= {"seed_baseline", "candidate"}


@pytest.mark.asyncio
async def test_run_experiment_can_use_taskbed_fast_lane_without_clone_on_empty_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "evolution_worktrees"
    archive_root = tmp_path / "evolution_archive"
    db_path = tmp_path / "taskbed.db"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(root))
    register_task(
        {
            "task_id": "pr::owner/repo::1",
            "source_kind": "post_cutoff_pr_suite",
            "repo": "owner/repo",
            "fail_to_pass": ["tests/test_example.py::test_fixed"],
        },
        db_path=db_path,
        contamination_state="fresh_post_cutoff",
        source="unit",
        taskbed="pr_suite",
    )

    closeout = await run_experiment(
        ExperimentConfig(
            experiment_id="exp_taskbed_smoke",
            generations=1,
            children=1,
            source_repo=Path.cwd(),
            base_ref="HEAD",
            archive_root=archive_root,
            worktree_root=root,
            taskbed_db=db_path,
            task_count=1,
            use_taskbed=True,
        )
    )

    archive_dir = archive_root / "agent_evolution" / "exp_taskbed_smoke"
    assert closeout["closeout_state"] == "inconclusive_low_power"
    receipts = sorted((archive_dir / "grade_receipts").glob("*.json"))
    assert receipts
    payload = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert payload["grade_error"] == "empty_patch"
    assert payload["commands"] == []
