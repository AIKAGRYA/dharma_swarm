from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.a2a_task_lifecycle import (
    A2ATaskLifecycleError,
    block_task,
    build_task_receipt,
    claim_task,
    complete_task,
    fail_task,
    read_queue,
    reconcile_inbox_task_receipts,
    task_lifecycle_state,
    validate_task_receipt,
)


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_claim_task_rewrites_one_queue_row_and_mirrors_inbox(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {"id": "t1", "from": "opus", "to": "hermes-m5", "status": "pending", "body": "do one"},
            {"id": "t2", "from": "opus", "to": "other", "status": "pending", "body": "do two"},
        ],
    )

    claimed = claim_task("t1", agent_uid="hermes-m5", state_root=tmp_path, now="2026-05-23T00:00:00+00:00")

    rows = read_queue(tmp_path)
    assert rows[0]["id"] == "t1"
    assert rows[0]["status"] == "claimed"
    assert rows[0]["claimed_by"] == "hermes-m5"
    assert rows[0]["claimed_at"] == "2026-05-23T00:00:00+00:00"
    assert rows[0]["return_address"]["base_case"]
    assert rows[1] == {"id": "t2", "from": "opus", "to": "other", "status": "pending", "body": "do two"}

    inbox_path = Path(claimed["inbox_path"])
    assert inbox_path.exists()
    assert json.loads(inbox_path.read_text())["id"] == "t1"


def test_claim_task_rejects_other_agent_claim(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [{"id": "t1", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "other"}],
    )

    with pytest.raises(A2ATaskLifecycleError, match="already claimed"):
        claim_task("t1", agent_uid="hermes-m5", state_root=tmp_path)


def test_supervisor_block_can_close_stale_claim_with_evidence(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "t1",
                "from": "opus",
                "to": "hermes-m5",
                "status": "claimed",
                "claimed_by": "hermes-m5",
                "claimed_at": "2026-05-22T13:44:25+00:00",
            }
        ],
    )
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="cwt-supervisor",
        status="blocked",
        summary="Claim timed out without a terminal task receipt.",
        evidence={"claimed_by": "hermes-m5", "age_hours": 24.0},
        failure_reason="stale_claim_without_terminal_receipt",
        authority="operator_supervisor_block",
        completion_via="cwt_stale_claim_watch",
    )

    closed = block_task(
        "t1",
        agent_uid="cwt-supervisor",
        receipt=receipt,
        state_root=tmp_path,
        allow_supervisor_block=True,
    )

    assert closed["status"] == "blocked"
    assert closed["blocked_by"] == "cwt-supervisor"
    assert closed["supervisor_blocked_claimed_by"] == "hermes-m5"
    assert closed["receipt_validation"]["valid"] is True
    assert task_lifecycle_state(read_queue(tmp_path)[0])["state"] == "blocked_verified"


def test_supervisor_block_is_denied_without_explicit_permission(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [{"id": "t1", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "hermes-m5"}],
    )
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="cwt-supervisor",
        status="blocked",
        summary="Claim timed out without a terminal task receipt.",
        evidence={"claimed_by": "hermes-m5"},
        failure_reason="stale_claim_without_terminal_receipt",
        authority="operator_supervisor_block",
    )

    with pytest.raises(A2ATaskLifecycleError, match="claimed by hermes-m5"):
        block_task("t1", agent_uid="cwt-supervisor", receipt=receipt, state_root=tmp_path)

    assert task_lifecycle_state(read_queue(tmp_path)[0])["state"] == "claimed_open"


def test_supervisor_override_cannot_complete_other_agent_task(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [{"id": "t1", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "hermes-m5"}],
    )
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="cwt-supervisor",
        status="completed",
        summary="Supervisor must not complete another agent's claimed work.",
        evidence={"claimed_by": "hermes-m5"},
        authority="operator_supervisor_block",
    )

    with pytest.raises(A2ATaskLifecycleError, match="claimed by hermes-m5"):
        complete_task(
            "t1",
            agent_uid="cwt-supervisor",
            receipt=receipt,
            state_root=tmp_path,
        )

    assert task_lifecycle_state(read_queue(tmp_path)[0])["state"] == "claimed_open"


def test_complete_task_requires_valid_receipt_and_preserves_task_body(tmp_path: Path) -> None:
    artifact = tmp_path / "outbox" / "result.md"
    artifact.parent.mkdir()
    artifact.write_text("done\n", encoding="utf-8")
    _write_queue(
        tmp_path,
        [
            {
                "id": "t1",
                "from": "opus",
                "to": "hermes-m5",
                "status": "claimed",
                "claimed_by": "hermes-m5",
                "body": "preserve me",
            }
        ],
    )
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="hermes-m5",
        status="completed",
        summary="Task finished.",
        artifacts=[str(artifact)],
        evaluation={"overall_verdict": "pass", "criteria_results": [], "gate_results": []},
        timestamp="2026-05-23T00:01:00+00:00",
    )

    closed = complete_task(
        "t1",
        agent_uid="hermes-m5",
        receipt=receipt,
        state_root=tmp_path,
        require_artifact_or_evidence=True,
    )

    assert closed["status"] == "completed"
    assert closed["completed_by"] == "hermes-m5"
    assert closed["completed_at"]
    assert closed["body"] == "preserve me"
    assert closed["receipt"]["receipt_id"] == receipt["receipt_id"]
    assert closed["receipt_validation"]["valid"] is True
    lifecycle = task_lifecycle_state(read_queue(tmp_path)[0], require_artifact_or_evidence=True)
    assert lifecycle["state"] == "completed_verified"


def test_invalid_receipt_does_not_close_task(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [{"id": "t1", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "hermes-m5"}],
    )
    bad_receipt = {"schema_version": "dharma_a2a_task_receipt.v1", "task_id": "t1"}

    with pytest.raises(A2ATaskLifecycleError):
        complete_task("t1", agent_uid="hermes-m5", receipt=bad_receipt, state_root=tmp_path)

    assert read_queue(tmp_path)[0]["status"] == "claimed"
    assert task_lifecycle_state(read_queue(tmp_path)[0])["state"] == "claimed_open"


def test_failed_and_blocked_receipts_require_failure_reason(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {"id": "t1", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "hermes-m5"},
            {"id": "t2", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "hermes-m5"},
        ],
    )

    failed_receipt = build_task_receipt(
        task_id="t1",
        agent_uid="hermes-m5",
        status="failed",
        summary="Could not complete.",
        failure_reason="missing source artifact",
    )
    blocked_receipt = build_task_receipt(
        task_id="t2",
        agent_uid="hermes-m5",
        status="blocked",
        summary="Needs operator approval.",
        failure_reason="approval required",
    )

    fail_task("t1", agent_uid="hermes-m5", receipt=failed_receipt, state_root=tmp_path)
    block_task("t2", agent_uid="hermes-m5", receipt=blocked_receipt, state_root=tmp_path)

    rows = {row["id"]: row for row in read_queue(tmp_path)}
    assert rows["t1"]["status"] == "failed"
    assert rows["t1"]["failure_reason"] == "missing source artifact"
    assert rows["t2"]["status"] == "blocked"
    assert rows["t2"]["failure_reason"] == "approval required"


def test_reconcile_inbox_task_receipts_closes_queue_row(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [{"id": "t1", "from": "opus", "to": "hermes-m5", "status": "claimed", "claimed_by": "hermes-m5"}],
    )
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="hermes-m5",
        status="completed",
        summary="Closed from inbox receipt.",
        evidence={"source": "unit-test"},
    )
    inbox = tmp_path / "a2a_bus" / "inboxes" / "hermes-m5"
    inbox.mkdir(parents=True)
    (inbox / "receipt_t1.json").write_text(json.dumps(receipt), encoding="utf-8")

    result = reconcile_inbox_task_receipts(agent_uid="hermes-m5", state_root=tmp_path)

    assert result[0]["status"] == "closed"
    assert read_queue(tmp_path)[0]["status"] == "completed"
    assert (tmp_path / "a2a_bus" / "inboxes" / "opus" / "receipt_t1_from_hermes-m5.json").exists()


def test_terminal_task_cannot_be_reclosed(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {
                "id": "t1",
                "from": "opus",
                "to": "hermes-m5",
                "status": "completed",
                "claimed_by": "hermes-m5",
            }
        ],
    )
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="hermes-m5",
        status="completed",
        summary="Second close should not be accepted.",
        evidence={"source": "unit-test"},
    )

    with pytest.raises(A2ATaskLifecycleError, match="terminal task"):
        complete_task("t1", agent_uid="hermes-m5", receipt=receipt, state_root=tmp_path)

    assert read_queue(tmp_path)[0]["status"] == "completed"
    assert "receipt" not in read_queue(tmp_path)[0]


def test_validate_task_receipt_checks_content_hash(tmp_path: Path) -> None:
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="hermes-m5",
        status="completed",
        summary="Valid.",
        evidence={"source": "unit-test"},
    )
    assert validate_task_receipt(receipt, task_id="t1", agent_uid="hermes-m5", status="completed")["valid"] is True

    receipt["summary"] = "tampered"
    validation = validate_task_receipt(receipt, task_id="t1", agent_uid="hermes-m5", status="completed")
    assert validation["valid"] is False
    assert "content_hash does not match receipt payload" in validation["errors"]
