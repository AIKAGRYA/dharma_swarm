from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt, read_queue
from scripts.governance.a2a_reconcile_embedded_receipts import (
    apply_embedded_terminal_receipt_actions,
    build_report,
    find_embedded_terminal_receipt_actions,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = root / "a2a_bus" / "tasks" / "queue.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_reconciler_dry_run_finds_only_valid_embedded_terminal_receipts(tmp_path: Path) -> None:
    receipt = build_task_receipt(
        task_id="expired-task",
        agent_uid="a2a_supervisor",
        status="blocked",
        summary="Lease expired with no terminal worker result.",
        evidence={"claimed_by": "worker"},
        failure_reason="stale_claim_without_terminal_receipt",
        authority="operator_supervisor_block",
    )
    _write_queue(
        tmp_path,
        [
            {
                "id": "expired-task",
                "status": "expired",
                "claimed_by": "worker",
                "receipt": receipt,
            },
            {"id": "open-task", "status": "pending"},
            {"id": "completed-without-a2a-receipt", "status": "completed"},
        ],
    )

    report = build_report(tmp_path)

    assert report["mode"] == "dry_run"
    assert report["candidate_count"] == 1
    assert report["candidates"][0]["task_id"] == "expired-task"
    assert read_queue(tmp_path)[0]["status"] == "expired"


def test_reconciler_apply_normalizes_valid_embedded_terminal_receipt(tmp_path: Path) -> None:
    receipt = build_task_receipt(
        task_id="expired-task",
        agent_uid="a2a_supervisor",
        status="blocked",
        summary="Lease expired with no terminal worker result.",
        evidence={"claimed_by": "worker"},
        failure_reason="stale_claim_without_terminal_receipt",
        authority="operator_supervisor_block",
    )
    _write_queue(
        tmp_path,
        [
            {
                "id": "expired-task",
                "status": "expired",
                "claimed_by": "worker",
                "receipt": receipt,
            }
        ],
    )

    actions = find_embedded_terminal_receipt_actions(tmp_path)
    applied = apply_embedded_terminal_receipt_actions(actions, tmp_path)

    row = read_queue(tmp_path)[0]
    assert applied[0]["status"] == "normalized"
    assert row["status"] == "blocked"
    assert row["blocked_by"] == "a2a_supervisor"
    assert row["receipt_validation"]["valid"] is True
    assert evaluate_a2a_readiness(tmp_path).ready is True


def test_reconciler_ignores_invalid_embedded_terminal_receipt(tmp_path: Path) -> None:
    receipt = build_task_receipt(
        task_id="expired-task",
        agent_uid="a2a_supervisor",
        status="blocked",
        summary="Lease expired with no terminal worker result.",
        evidence={"claimed_by": "worker"},
        failure_reason="stale_claim_without_terminal_receipt",
        authority="operator_supervisor_block",
    )
    receipt["summary"] = "tampered after hashing"
    _write_queue(
        tmp_path,
        [{"id": "expired-task", "status": "expired", "receipt": receipt}],
    )

    assert find_embedded_terminal_receipt_actions(tmp_path) == []
    assert build_report(tmp_path)["candidate_count"] == 0
