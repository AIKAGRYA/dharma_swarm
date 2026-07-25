from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.governance.a2a_readiness_blocker_audit import build_report


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = root / "a2a_bus" / "tasks" / "queue.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _sab_receipt(task_id: str, receipt_id: str) -> dict:
    return {
        "schema": "sab.semantic_receipt.v1",
        "receipt_id": receipt_id,
        "task_id": task_id,
        "agent": "sab_agent",
        "sab_instance_id": "sab_fixture",
        "latest_post_id_seen": 1,
        "latest_witness_hash_seen": "abc123",
        "semantic_action": "synthesis",
        "claim": "Task-specific semantic claim.",
        "evidence": ["fixture evidence"],
        "action_taken": "Recorded fixture evidence.",
        "next_request": "None.",
    }


def test_audit_classifies_stale_claimed_open_row(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "claimed-old",
                "status": "claimed",
                "claimed_by": "worker",
                "claimed_at": "2026-06-01T00:00:00+00:00",
                "body": "Operator-gated task.",
            }
        ],
    )

    report = build_report(
        tmp_path,
        now=datetime(2026, 6, 3, tzinfo=timezone.utc),
        stale_after_hours=24.0,
    )

    blocker = report["blockers"][0]
    assert blocker["classification"] == "open_stale_claimed_without_terminal_receipt"
    assert blocker["age_hours"] == 48.0
    assert blocker["flags"] == ["operator_gated"]


def test_audit_validates_present_semantic_receipt_but_keeps_non_a2a_blocker(tmp_path: Path) -> None:
    receipt_id = "sab.semantic_receipt:done-semantic:20260627T0000Z"
    receipt_path = Path("reports/sab/receipts/done-semantic.semantic_receipt.json")
    full_receipt_path = tmp_path / receipt_path
    full_receipt_path.parent.mkdir(parents=True)
    full_receipt_path.write_text(
        json.dumps(_sab_receipt("done-semantic", receipt_id)),
        encoding="utf-8",
    )
    _write_queue(
        tmp_path,
        [
            {
                "id": "done-semantic",
                "status": "completed",
                "completed_by": "sab_agent",
                "receipt_id": receipt_id,
                "receipt_path": str(receipt_path),
                "required_receipt_schema": "sab.semantic_receipt.v1",
                "receipt_validation": {"schema": "sab.semantic_receipt.v1", "valid": True},
            }
        ],
    )

    report = build_report(tmp_path, artifact_roots=[tmp_path])

    blocker = report["blockers"][0]
    assert blocker["classification"] == "closed_semantic_receipt_present_non_a2a"
    assert blocker["receipt_pointer"]["exists"] is True
    assert blocker["receipt_pointer"]["validation"]["valid"] is True


def test_audit_reports_missing_pointer_and_missing_receipt(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "missing-semantic",
                "status": "completed",
                "completed_by": "sab_agent",
                "receipt_path": "reports/missing.semantic_receipt.json",
                "required_receipt_schema": "sab.semantic_receipt.v1",
            },
            {"id": "no-pointer", "status": "completed", "completed_by": "worker"},
        ],
    )

    report = build_report(tmp_path, artifact_roots=[tmp_path])
    blockers = {item["task_id"]: item for item in report["blockers"]}

    assert blockers["missing-semantic"]["classification"] == "closed_semantic_receipt_pointer_missing_file"
    assert blockers["missing-semantic"]["receipt_pointer"]["exists"] is False
    assert blockers["no-pointer"]["classification"] == "closed_missing_a2a_receipt_no_pointer"
    assert report["classification_counts"] == {
        "closed_missing_a2a_receipt_no_pointer": 1,
        "closed_semantic_receipt_pointer_missing_file": 1,
    }


def test_audit_accepts_legacy_sab_agent_id_and_absent_receipt_id(tmp_path: Path) -> None:
    receipt_path = Path("reports/sab/receipts/legacy.semantic_receipt.json")
    full_receipt_path = tmp_path / receipt_path
    full_receipt_path.parent.mkdir(parents=True)
    receipt = _sab_receipt("legacy", "unused")
    receipt.pop("receipt_id")
    receipt["agent_id"] = receipt.pop("agent")
    full_receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    _write_queue(
        tmp_path,
        [
            {
                "id": "legacy",
                "status": "completed",
                "completed_by": "sab_agent",
                "receipt_id": "sab.semantic_receipt:legacy:20260627T0000Z",
                "receipt_path": str(receipt_path),
                "required_receipt_schema": "sab.semantic_receipt.v1",
            }
        ],
    )

    report = build_report(tmp_path, artifact_roots=[tmp_path])

    blocker = report["blockers"][0]
    assert blocker["classification"] == "closed_semantic_receipt_present_non_a2a"
    assert blocker["receipt_pointer"]["validation"]["valid"] is True
