from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import fresh_task_oracle, taskbed_ledger


def _pr_task(idx: int, *, created_at: str = "2026-07-01T00:00:00Z", fail_to_pass: bool = True) -> dict:
    task = {
        "repo": "example/project",
        "pr_number": idx,
        "created_at": created_at,
        "problem_statement": f"fix regression {idx}",
    }
    if fail_to_pass:
        task["fail_to_pass"] = [f"tests/test_regression_{idx}.py::test_fix"]
    return task


def test_post_cutoff_pr_suite_imports_as_confirm_eligible(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"

    summary = fresh_task_oracle.import_fresh_tasks(
        [_pr_task(1), _pr_task(2)],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=db,
        taskbed="fresh_pr_suite",
    )

    assert summary["imported_count"] == 2
    assert summary["skipped_count"] == 0
    assert summary["derived_state_counts"] == {"fresh_post_cutoff": 2}

    confirm = taskbed_ledger.allocate_confirm(
        count=2,
        min_count=2,
        epoch_id="epoch-fresh",
        lane_id="dgm",
        allocation_id="confirm-fresh",
        db_path=db,
    )
    assert confirm["promotion_eligible_taskbed"] is True
    assert confirm["task_count"] == 2
    assert confirm["blockers"] == []


def test_old_public_task_is_skipped_by_default(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"

    summary = fresh_task_oracle.import_fresh_tasks(
        [_pr_task(1, created_at="2024-01-01T00:00:00Z")],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=db,
    )

    assert summary["imported_count"] == 0
    assert summary["skipped_count"] == 1
    assert summary["skipped"][0]["contamination_state"] == "possible_pretrain"
    assert "not_after_model_cutoff" in summary["skipped"][0]["blockers"]
    assert taskbed_ledger.task_counts(db_path=db) == {}


def test_caller_clean_label_cannot_override_oracle_derivation(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    old_claimed_clean = _pr_task(1, created_at="2024-01-01T00:00:00Z")
    old_claimed_clean["contamination_state"] = "fresh_post_cutoff"

    summary = fresh_task_oracle.import_fresh_tasks(
        [old_claimed_clean],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=db,
        include_ineligible=True,
    )

    assert summary["imported_count"] == 1
    assert summary["derived_state_counts"] == {"possible_pretrain": 1}
    assert taskbed_ledger.task_counts(db_path=db) == {"possible_pretrain": 1}

    try:
        taskbed_ledger.allocate_confirm(
            count=1,
            min_count=1,
            epoch_id="epoch-fresh",
            lane_id="dgm",
            db_path=db,
        )
    except taskbed_ledger.TaskbedLedgerError as exc:
        assert "available=0" in str(exc)
    else:
        raise AssertionError("possible_pretrain task must not allocate to CONFIRM")


def test_missing_fail_to_pass_suite_is_not_clean(tmp_path: Path) -> None:
    summary = fresh_task_oracle.import_fresh_tasks(
        [_pr_task(1, fail_to_pass=False)],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=tmp_path / "taskbed.db",
    )

    assert summary["imported_count"] == 0
    assert "missing_fail_to_pass_suite" in summary["skipped"][0]["blockers"]


def test_test_files_alone_do_not_count_as_fail_to_pass(tmp_path: Path) -> None:
    candidate = _pr_task(1, fail_to_pass=False)
    candidate["test_files"] = ["tests/test_regression.py"]

    summary = fresh_task_oracle.import_fresh_tasks(
        [candidate],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=tmp_path / "taskbed.db",
    )

    assert summary["imported_count"] == 0
    assert summary["skipped_count"] == 1
    assert "missing_fail_to_pass_suite" in summary["skipped"][0]["blockers"]
    assert taskbed_ledger.task_counts(db_path=tmp_path / "taskbed.db") == {}


def test_generated_after_freeze_requires_attested_freeze_receipt(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    claimed = _pr_task(1, created_at="2024-01-01T00:00:00Z")
    claimed["generated_after_candidate_freeze"] = True

    summary = fresh_task_oracle.import_fresh_tasks(
        [claimed],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=db,
        include_ineligible=True,
    )

    assert summary["imported_count"] == 1
    assert summary["derived_state_counts"] == {"possible_pretrain": 1}
    row = taskbed_ledger.task_for_id("pr::example/project#1", db_path=db)
    assert "unattested_generated_after_candidate_freeze" in row["provenance"]["blockers"]
    assert row["provenance"]["self_mod_clean_attested"] is False


def test_attested_generated_after_freeze_maps_to_private_fresh_state(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    claimed = _pr_task(1, created_at="2026-07-01T00:00:00Z")
    claimed["generated_after_candidate_freeze"] = True
    claimed["candidate_freeze_timestamp"] = "2026-06-30T00:00:00Z"
    claimed["candidate_freeze_receipt_sha256"] = "sha256:freeze-receipt"

    summary = fresh_task_oracle.import_fresh_tasks(
        [claimed],
        model_cutoff="2026-12-01T00:00:00Z",
        db_path=db,
    )

    assert summary["imported_count"] == 1
    assert summary["derived_state_counts"] == {"fresh_private_local_generated": 1}
    confirm = taskbed_ledger.allocate_confirm(
        count=1,
        min_count=1,
        epoch_id="epoch-private",
        lane_id="dgm",
        db_path=db,
    )
    assert confirm["promotion_eligible_taskbed"] is True


def test_jsonl_manifest_round_trip(tmp_path: Path) -> None:
    manifest = tmp_path / "tasks.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in [_pr_task(1), _pr_task(2)]) + "\n",
        encoding="utf-8",
    )

    rows = fresh_task_oracle.read_manifest(manifest)
    summary = fresh_task_oracle.import_fresh_tasks(
        rows,
        model_cutoff="2026-06-01",
        db_path=tmp_path / "taskbed.db",
    )

    assert [row["pr_number"] for row in rows] == [1, 2]
    assert summary["imported_count"] == 2
