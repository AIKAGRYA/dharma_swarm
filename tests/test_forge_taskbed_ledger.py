from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_v1.forge_v2 import taskbed_ledger


def _task(task_id: str, contamination_state: str = "fresh_post_cutoff", *, max_uses_per_epoch: int = 1) -> dict:
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
            _task("fresh-2", "fresh_post_cutoff"),
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


def test_explore_prefers_globally_least_used_tasks_across_epochs(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [_task("fresh-0"), _task("fresh-1"), _task("fresh-2")],
        db_path=db,
        source="post_cutoff_pr_suite",
    )

    task_ids = []
    for epoch in range(1, 5):
        allocation = taskbed_ledger.allocate_explore(
            count=1,
            epoch_id=f"epoch-{epoch}",
            lane_id="dgm",
            allocation_id=f"explore-{epoch}",
            db_path=db,
        )
        task_ids.extend(allocation["task_ids"])

    assert task_ids == ["fresh-0", "fresh-1", "fresh-2", "fresh-0"]


def test_confirm_cross_epoch_selection_remains_oldest_clean_first(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [
            _task("public-0", "possible_pretrain"),
            _task("fresh-1"),
            _task("fresh-2"),
        ],
        db_path=db,
        source="post_cutoff_pr_suite",
    )

    first = taskbed_ledger.allocate_confirm(
        count=1,
        min_count=1,
        epoch_id="epoch-1",
        lane_id="dgm",
        allocation_id="confirm-1",
        db_path=db,
    )
    second = taskbed_ledger.allocate_confirm(
        count=1,
        min_count=1,
        epoch_id="epoch-2",
        lane_id="dgm",
        allocation_id="confirm-2",
        db_path=db,
    )

    assert first["task_ids"] == ["fresh-1"]
    assert second["task_ids"] == ["fresh-1"]


def test_allocate_task_ids_binds_exact_prediction_slice(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [_task("fresh-0"), _task("fresh-1"), _task("fresh-2")],
        db_path=db,
        source="post_cutoff_pr_suite",
    )

    allocation = taskbed_ledger.allocate_task_ids(
        split="explore",
        task_ids=["fresh-2", "fresh-0"],
        epoch_id="epoch-exact",
        lane_id="native-worker",
        allocation_id="explore-exact",
        candidate_id="candidate-with-specific-predictions",
        db_path=db,
    )

    assert allocation["split"] == "explore"
    assert allocation["task_count"] == 2
    assert set(allocation["task_ids"]) == {"fresh-0", "fresh-2"}
    assert allocation["task_ids"] != ["fresh-0", "fresh-1"]


def test_allocate_task_ids_fails_closed_for_ineligible_id(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [_task("fresh-0"), _task("fresh-1")],
        db_path=db,
        source="post_cutoff_pr_suite",
    )
    taskbed_ledger.allocate_explore(
        count=1,
        epoch_id="epoch-1",
        lane_id="explore-lane",
        allocation_id="explore-prior",
        db_path=db,
    )

    with pytest.raises(taskbed_ledger.TaskbedLedgerError, match="missing_or_ineligible=\\['fresh-0'\\]"):
        taskbed_ledger.allocate_task_ids(
            split="confirm",
            task_ids=["fresh-0", "fresh-1"],
            epoch_id="epoch-confirm",
            lane_id="confirm-lane",
            allocation_id="confirm-exact",
            min_count=2,
            db_path=db,
        )

    assert taskbed_ledger.allocation_rows("confirm-exact", db_path=db) == []


def test_task_counts_group_by_contamination_state(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_tasks(
        [
            _task("fresh-0", "fresh_post_cutoff"),
            _task("fresh-1", "fresh_private_local_generated"),
            _task("public-2", "possible_pretrain"),
        ],
        db_path=db,
    )

    assert taskbed_ledger.task_counts(db_path=db) == {
        "fresh_post_cutoff": 1,
        "possible_pretrain": 1,
        "fresh_private_local_generated": 1,
    }


def _write_validation_receipt(path: Path, *, repo: str, task_id: str, status: str, started: str, finished: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blockers = [] if status == "fail_to_pass_validated" else ["validation_failed"]
    path.write_text(
        json.dumps(
            {
                "schema": "forge_v2.pr_suite_fail_to_pass_validator.v1",
                "run_id": f"validation-{task_id}",
                "repo": repo,
                "task_hint": task_id,
                "status": status,
                "started_at": started,
                "finished_at": finished,
                "validated_fail_to_pass": ["tests/test_example.py"] if not blockers else [],
                "blockers": blockers,
            }
        ),
        encoding="utf-8",
    )


def test_taskbed_quality_report_measures_per_repo_validation_and_grade_metrics(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    validations = tmp_path / "validations"
    grades = tmp_path / "grades"
    v1 = validations / "click-1.json"
    v2 = validations / "click-2.json"
    v3 = validations / "werkzeug-1.json"
    _write_validation_receipt(
        v1,
        repo="pallets/click",
        task_id="pr::pallets/click#1",
        status="fail_to_pass_validated",
        started="20260702T010000Z",
        finished="20260702T010010Z",
    )
    _write_validation_receipt(
        v2,
        repo="pallets/click",
        task_id="pr::pallets/click#2",
        status="blocked",
        started="20260702T010100Z",
        finished="20260702T010130Z",
    )
    _write_validation_receipt(
        v3,
        repo="pallets/werkzeug",
        task_id="pr::pallets/werkzeug#3",
        status="fail_to_pass_validated",
        started="20260702T020000Z",
        finished="20260702T020006Z",
    )
    taskbed_ledger.register_tasks(
        [
            {
                **_task("pr::pallets/click#1"),
                "repo": "pallets/click",
                "validation_state": "fail_to_pass_validated",
                "validation_receipt": str(v1),
            },
            {
                **_task("pr::pallets/click#2"),
                "repo": "pallets/click",
                "validation_state": "blocked",
                "validation_receipt": str(v2),
            },
            {
                **_task("pr::pallets/werkzeug#3"),
                "repo": "pallets/werkzeug",
                "validation_state": "fail_to_pass_validated",
                "validation_receipt": str(v3),
            },
        ],
        db_path=db,
        source="post_cutoff_pr_suite",
        taskbed="fresh_pr_suite",
    )
    grades.mkdir()
    (grades / "click-pass.json").write_text(
        json.dumps(
            {
                "task_id": "pr::pallets/click#1",
                "repo": "pallets/click",
                "resolved": True,
                "grade_seconds": 12.5,
                "grade_error": None,
            }
        ),
        encoding="utf-8",
    )
    (grades / "click-fail.json").write_text(
        json.dumps(
            {
                "task_id": "pr::pallets/click#2",
                "repo": "pallets/click",
                "resolved": False,
                "grade_seconds": 5.0,
                "grade_error": "test_returncode=1",
            }
        ),
        encoding="utf-8",
    )

    report = taskbed_ledger.taskbed_quality_report(db_path=db, grade_receipt_roots=[grades])
    assert report["schema"] == "forge_v2.taskbed_quality_report.v1"
    assert report["task_count"] == 3
    assert report["validated_count"] == 2
    assert report["validation_failure_rate"] == round(1 / 3, 6)
    assert report["grade_attempt_count"] == 2
    assert report["grade_resolved_count"] == 1
    assert report["grade_failure_rate"] == 0.5
    assert report["source_of_truth_mutated"] is False
    assert report["official_score_claimed"] is False
    by_repo = {item["repo"]: item for item in report["per_repo"]}
    assert by_repo["pallets/click"]["task_count"] == 2
    assert by_repo["pallets/click"]["validated_count"] == 1
    assert by_repo["pallets/click"]["validation_failure_rate"] == 0.5
    assert by_repo["pallets/click"]["validation_runtime"]["median_seconds"] == 20.0
    assert by_repo["pallets/click"]["grade_attempt_count"] == 2
    assert by_repo["pallets/click"]["grade_failure_rate"] == 0.5
    assert by_repo["pallets/click"]["grade_runtime"]["median_seconds"] == 8.8
    assert by_repo["pallets/click"]["grade_coverage"]["observed_task_rate"] == 1.0
    assert by_repo["pallets/werkzeug"]["validation_runtime"]["median_seconds"] == 6.0
    assert by_repo["pallets/werkzeug"]["grade_failure_rate"] is None
    assert by_repo["pallets/werkzeug"]["grade_coverage"]["observed_task_rate"] == 0.0


def test_write_taskbed_quality_report_writes_json_and_markdown(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    validation = tmp_path / "validation.json"
    _write_validation_receipt(
        validation,
        repo="pallets/click",
        task_id="pr::pallets/click#1",
        status="fail_to_pass_validated",
        started="20260702T010000Z",
        finished="20260702T010003Z",
    )
    taskbed_ledger.register_task(
        {
            **_task("pr::pallets/click#1"),
            "repo": "pallets/click",
            "validation_state": "fail_to_pass_validated",
            "validation_receipt": str(validation),
        },
        db_path=db,
        source="post_cutoff_pr_suite",
        taskbed="fresh_pr_suite",
    )

    result = taskbed_ledger.write_taskbed_quality_report(
        db_path=db,
        output_root=tmp_path / "quality",
        grade_receipt_roots=[],
        label="unit",
    )

    json_path = Path(result["json_path"])
    md_path = Path(result["markdown_path"])
    assert json_path.exists()
    assert md_path.exists()
    report = json.loads(json_path.read_text())
    assert report["per_repo"][0]["repo"] == "pallets/click"
    assert "Taskbed quality report" in md_path.read_text()


def test_register_task_rejects_bare_clean_contamination_state(tmp_path: Path) -> None:
    with pytest.raises(taskbed_ledger.TaskbedLedgerError, match="clean"):
        taskbed_ledger.register_task(
            {"task_id": "caller-clean", "problem_statement": "caller asserted clean"},
            contamination_state="clean",
            db_path=tmp_path / "taskbed.db",
        )


def test_register_task_boundary_maps_legacy_clean_states(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    taskbed_ledger.register_task(
        {"task_id": "legacy-fresh"},
        contamination_state="fresh_heldout",
        db_path=db,
    )
    taskbed_ledger.register_task(
        {"task_id": "legacy-private"},
        contamination_state="self_mod_clean",
        db_path=db,
    )
    assert taskbed_ledger.task_counts(db_path=db) == {
        "fresh_post_cutoff": 1,
        "fresh_private_local_generated": 1,
    }
