from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from scripts.governance.a2a_block_operator_gated_tasks import build_report
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_dry_run_selects_only_explicit_operator_gate_phrases(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "operator-gated",
                "status": "claimed",
                "claimed_by": "hermes-m5",
                "claimed_at": "2026-06-01T00:00:00Z",
                "body": "Decision is operator-gated.",
            },
            {
                "id": "approval-forbidden-only",
                "status": "pending",
                "created": "2026-06-01T00:00:00Z",
                "body": "Forbidden: external outreach without approval.",
            },
            {
                "id": "ordinary-stale",
                "status": "claimed",
                "claimed_by": "hermes-m5",
                "claimed_at": "2026-06-01T00:00:00Z",
                "body": "Please investigate and report.",
            },
        ],
    )

    report = build_report(
        tmp_path,
        timestamp="2026-06-03T00:00:00Z",
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 0
    assert report["actions"][0]["task_id"] == "operator-gated"
    assert report["actions"][0]["matched_phrase"] == "operator-gated"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 3


def test_apply_blocks_stale_claimed_operator_gated_rows_with_supervisor_receipts(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "operator-gated",
                "status": "claimed",
                "claimed_by": "hermes-m5",
                "claimed_at": "2026-06-01T00:00:00Z",
                "from": "fable",
                "body": "Proposal is operator-gated.",
            },
            {
                "id": "operator-signoff",
                "status": "pending",
                "created": "2026-06-01T00:00:00Z",
                "body": "Self-fix requires operator sign-off.",
            },
            {
                "id": "ordinary-stale",
                "status": "claimed",
                "claimed_by": "hermes-m5",
                "claimed_at": "2026-06-01T00:00:00Z",
                "body": "Please investigate and report.",
            },
        ],
    )

    report = build_report(
        tmp_path,
        apply=True,
        timestamp="2026-06-03T00:00:00Z",
    )

    assert report["candidate_count"] == 2
    assert report["applied_count"] == 2
    assert Path(report["backup_path"]).exists()
    readiness = evaluate_a2a_readiness(tmp_path)
    assert readiness.ready is False
    assert readiness.open_tasks == 1
    rows = {row["id"]: row for row in read_queue(tmp_path)}
    assert task_lifecycle_state(rows["operator-gated"])["state"] == "blocked_verified"
    assert rows["operator-gated"]["supervisor_blocked_claimed_by"] == "hermes-m5"
    assert rows["operator-gated"]["receipt"]["authority"] == "operator_gated_stale_task_supervisor_block"
    assert rows["operator-gated"]["receipt"]["evidence"]["matched_gate_phrase"] == "operator-gated"
    assert task_lifecycle_state(rows["operator-signoff"])["state"] == "blocked_verified"
    assert task_lifecycle_state(rows["ordinary-stale"])["state"] == "claimed_open"


def test_recent_operator_gate_is_not_blocked(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "recent",
                "status": "pending",
                "created": "2026-06-02T12:00:00Z",
                "body": "Decision is operator-gated.",
            }
        ],
    )

    report = build_report(
        tmp_path,
        timestamp="2026-06-03T00:00:00Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "not_stale"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1
