from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.forge_v1.forge_v2 import taskbed_ledger


def _task(task_id: str, contamination_state: str = "fresh_heldout", *, max_uses_per_epoch: int = 1) -> dict:
    return {
        "task_id": task_id,
        "created_at": f"2026-07-01T00:00:{int(task_id.split('-')[-1]) if '-' in task_id else 0:02d}Z",
        "contamination_state": contamination_state,
        "provenance": {"contamination_state": contamination_state},
        "max_uses_per_epoch": max_uses_per_epoch,
    }


def test_confirm_default_requires_full_500_clean_tasks(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [_task(f"fresh-{idx}") for idx in range(taskbed_ledger.MIN_CONFIRM_TASKS - 1)],
        db_path=db,
        source="post_cutoff_pr_suite",
        taskbed="fresh_pr_suite",
    )

    with pytest.raises(taskbed_ledger.TaskbedLedgerError, match="insufficient_confirm_tasks"):
        taskbed_ledger.allocate_confirm(
            count=taskbed_ledger.MIN_CONFIRM_TASKS,
            epoch_id="epoch-1",
            lane_id="dgm",
            db_path=db,
        )

    assert taskbed_ledger.allocation_rows("missing", db_path=db) == []


def test_confirm_excludes_any_prior_explore_task(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [_task("fresh-0"), _task("fresh-1"), _task("fresh-2")],
        db_path=db,
        source="post_cutoff_pr_suite",
    )

    explore = taskbed_ledger.allocate_explore(
        count=1,
        epoch_id="epoch-1",
        lane_id="dgm",
        allocation_id="explore-1",
        db_path=db,
    )
    confirm = taskbed_ledger.allocate_confirm(
        count=2,
        min_count=2,
        epoch_id="epoch-1",
        lane_id="dgm",
        allocation_id="confirm-1",
        db_path=db,
    )

    assert explore["task_ids"] == ["fresh-0"]
    assert confirm["task_ids"] == ["fresh-1", "fresh-2"]
    assert confirm["split"] == "confirm"
    assert confirm["promotion_eligible_taskbed"] is True
    assert confirm["explore_separate_from_confirm"] is True
    assert confirm["blockers"] == []


def test_confirm_requires_clean_contamination_provenance(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [
            _task("public-0", "possible_pretrain"),
            _task("public-1", "possible_pretrain"),
            _task("fresh-2", "fresh_heldout"),
        ],
        db_path=db,
        source="mixed",
    )

    with pytest.raises(taskbed_ledger.TaskbedLedgerError, match="available=1"):
        taskbed_ledger.allocate_confirm(
            count=2,
            min_count=2,
            epoch_id="epoch-1",
            lane_id="dgm",
            db_path=db,
        )

    explore = taskbed_ledger.allocate_explore(
        count=2,
        epoch_id="epoch-1",
        lane_id="dgm",
        allocation_id="explore-public",
        db_path=db,
    )
    assert explore["split"] == "explore"
    assert explore["task_count"] == 2


def test_max_uses_per_epoch_rotates_confirm_tasks(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [_task("fresh-0", max_uses_per_epoch=1), _task("fresh-1", max_uses_per_epoch=1)],
        db_path=db,
        source="post_cutoff_pr_suite",
    )

    first = taskbed_ledger.allocate_confirm(
        count=1,
        min_count=1,
        epoch_id="epoch-1",
        lane_id="lane-a",
        allocation_id="confirm-a",
        db_path=db,
    )
    second = taskbed_ledger.allocate_confirm(
        count=1,
        min_count=1,
        epoch_id="epoch-1",
        lane_id="lane-b",
        allocation_id="confirm-b",
        db_path=db,
    )

    assert first["task_ids"] == ["fresh-0"]
    assert second["task_ids"] == ["fresh-1"]
    with pytest.raises(taskbed_ledger.TaskbedLedgerError, match="available=0"):
        taskbed_ledger.allocate_confirm(
            count=1,
            min_count=1,
            epoch_id="epoch-1",
            lane_id="lane-c",
            db_path=db,
        )

    next_epoch = taskbed_ledger.allocate_confirm(
        count=1,
        min_count=1,
        epoch_id="epoch-2",
        lane_id="lane-a",
        allocation_id="confirm-next",
        db_path=db,
    )
    assert next_epoch["task_ids"] == ["fresh-0"]


def test_task_counts_group_by_contamination_state(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [
            _task("fresh-0", "fresh_heldout"),
            _task("fresh-1", "self_mod_clean"),
            _task("public-2", "possible_pretrain"),
        ],
        db_path=db,
    )

    assert taskbed_ledger.task_counts(db_path=db) == {
        "fresh_heldout": 1,
        "possible_pretrain": 1,
        "self_mod_clean": 1,
    }
