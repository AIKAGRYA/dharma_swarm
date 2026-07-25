from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import (
    build_task_receipt,
    read_queue,
    task_lifecycle_state,
)
from scripts.governance.a2a_block_verified_duplicate_open_rows import build_report
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _terminal_row(root: Path, task_id: str, *, agent_uid: str = "fable_composer") -> dict:
    proof = root / "proofs" / f"{task_id}.md"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text("co-signed proof\n", encoding="utf-8")
    receipt = build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="completed",
        summary="Task already completed with proof.",
        artifacts=[str(proof)],
        authority="test_verified_terminal_row",
        completion_via="test_fixture",
        evidence={"proof_path": str(proof)},
        timestamp="2026-06-12T00:00:00Z",
    )
    return {
        "id": task_id,
        "status": "completed",
        "closed_by": agent_uid,
        "completed_by": agent_uid,
        "closed_at": "2026-06-12T00:00:00Z",
        "closure_note": "Task already completed with proof.",
        "receipt": receipt,
        "receipt_id": receipt["receipt_id"],
    }


def test_dry_run_selects_open_duplicate_with_verified_terminal_row(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "duplicate-task",
                "status": "pending",
                "created": "2026-06-11T00:00:00Z",
                "body": "Original mandate.",
            },
            _terminal_row(tmp_path, "duplicate-task"),
            {
                "id": "ordinary-open",
                "status": "pending",
                "created": "2026-06-11T00:00:00Z",
                "body": "No duplicate proof.",
            },
        ],
    )

    report = build_report(tmp_path, timestamp="2026-07-01T05:02:48Z")

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 0
    assert report["actions"][0]["task_id"] == "duplicate-task"
    assert report["actions"][0]["duplicate_terminal_row_index"] == 1
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 2


def test_apply_blocks_exact_open_duplicate_even_when_terminal_row_comes_first(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            _terminal_row(tmp_path, "duplicate-task"),
            {
                "id": "duplicate-task",
                "status": "pending",
                "created": "2026-06-11T00:00:00Z",
                "body": "Original mandate.",
            },
            {"id": "ordinary-open", "status": "pending", "body": "Still open."},
        ],
    )

    report = build_report(tmp_path, apply=True, timestamp="2026-07-01T05:02:48Z")

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 1
    assert Path(report["backup_path"]).exists()
    rows = read_queue(tmp_path)
    assert task_lifecycle_state(rows[0])["state"] == "completed_verified"
    assert rows[1]["id"] == "duplicate-task"
    assert task_lifecycle_state(rows[1])["state"] == "blocked_verified"
    assert rows[1]["receipt"]["authority"] == "verified_duplicate_terminal_row_supervisor_block"
    assert rows[1]["receipt"]["evidence"]["duplicate_terminal_row_index"] == 0
    assert rows[1]["duplicate_terminal_receipt_id"] == rows[0]["receipt_id"]
    readiness = evaluate_a2a_readiness(tmp_path)
    assert readiness.ready is False
    assert readiness.open_tasks == 1


def test_terminal_duplicate_without_substantive_evidence_is_not_enough(tmp_path: Path) -> None:
    receipt = build_task_receipt(
        task_id="duplicate-task",
        agent_uid="fable_composer",
        status="completed",
        summary="Default evaluation alone is not enough for duplicate blocking.",
        timestamp="2026-06-12T00:00:00Z",
    )
    _write_queue(
        tmp_path,
        [
            {"id": "duplicate-task", "status": "pending", "body": "Original mandate."},
            {
                "id": "duplicate-task",
                "status": "completed",
                "closed_by": "fable_composer",
                "completed_by": "fable_composer",
                "receipt": receipt,
                "receipt_id": receipt["receipt_id"],
            },
        ],
    )

    report = build_report(tmp_path, timestamp="2026-07-01T05:02:48Z")

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "no_verified_terminal_duplicate"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1


def test_claimed_duplicate_and_all_open_duplicates_are_not_touched(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            _terminal_row(tmp_path, "claimed-duplicate"),
            {
                "id": "claimed-duplicate",
                "status": "claimed",
                "claimed_by": "other_agent",
                "body": "Claimed work remains owned by the claimant.",
            },
            {"id": "all-open", "status": "pending", "body": "First open duplicate."},
            {"id": "all-open", "status": "pending", "body": "Second open duplicate."},
        ],
    )

    report = build_report(tmp_path, apply=True, timestamp="2026-07-01T05:02:48Z")

    assert report["candidate_count"] == 0
    assert report["applied_count"] == 0
    reasons = {skip["reason"] for skip in report["skips"]}
    assert "claimed_duplicate_not_touched" in reasons
    assert "no_verified_terminal_duplicate" in reasons
    rows = read_queue(tmp_path)
    assert task_lifecycle_state(rows[1])["state"] == "claimed_open"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 3
