from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import (
    build_task_receipt,
    read_queue,
    task_lifecycle_state,
)
from scripts.governance.a2a_block_stale_hermes_claims import build_report
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _write_presence(root: Path, agent_uid: str, *, last_seen_at: str) -> None:
    agent_dir = root / "agents" / agent_uid
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "living_agent.json").write_text(
        json.dumps(
            {
                "agent_uid": agent_uid,
                "callsign": agent_uid,
                "harness": "hermes",
                "last_seen_at": last_seen_at,
                "status": "active",
            }
        ),
        encoding="utf-8",
    )


def _claimed_row(task_id: str, **overrides: object) -> dict:
    row = {
        "id": task_id,
        "status": "claimed",
        "claimed_by": "hermes-m5",
        "claimed_at": "2026-06-10T00:00:00Z",
        "from": "fable_composer",
        "to": "hermes-m5",
        "type": "research",
        "body": "Investigate and report with a receipt.",
    }
    row.update(overrides)
    return row


def _write_claimant_receipt(root: Path, task_id: str) -> Path:
    inbox = root / "a2a_bus" / "inboxes" / "hermes-m5"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"receipt_{task_id}.json"
    receipt = build_task_receipt(
        task_id=task_id,
        agent_uid="hermes-m5",
        status="completed",
        summary="Hermes completed this task.",
        artifacts=[],
        evidence={"result": "terminal receipt present"},
        timestamp="2026-06-10T01:00:00+00:00",
    )
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return path


def test_dry_run_selects_only_stale_hermes_claims_without_receipts(tmp_path: Path) -> None:
    _write_presence(tmp_path, "hermes-m5", last_seen_at="2026-06-10T00:00:00+00:00")
    _write_queue(
        tmp_path,
        [
            _claimed_row("stale-hermes"),
            _claimed_row("recent-hermes", claimed_at="2026-06-30T20:00:00Z"),
            _claimed_row("other-claimant", claimed_by="other-agent"),
            {"id": "pending-row", "status": "pending", "created": "2026-06-10T00:00:00Z"},
        ],
    )

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T00:00:00Z",
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 0
    assert report["actions"][0]["task_id"] == "stale-hermes"
    assert report["actions"][0]["claimed_by"] == "hermes-m5"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 4


def test_apply_blocks_stale_hermes_claim_with_supervisor_receipt(tmp_path: Path) -> None:
    _write_presence(tmp_path, "hermes-m5", last_seen_at="2026-06-10T00:00:00+00:00")
    _write_queue(tmp_path, [_claimed_row("stale-hermes"), {"id": "still-open", "status": "pending"}])

    report = build_report(
        tmp_path,
        apply=True,
        timestamp="2026-07-01T00:00:00Z",
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 1
    assert Path(report["backup_path"]).exists()
    readiness = evaluate_a2a_readiness(tmp_path)
    assert readiness.ready is False
    assert readiness.open_tasks == 1
    rows = {row["id"]: row for row in read_queue(tmp_path)}
    blocked = rows["stale-hermes"]
    assert task_lifecycle_state(blocked)["state"] == "blocked_verified"
    assert blocked["supervisor_blocked_claimed_by"] == "hermes-m5"
    assert blocked["receipt"]["authority"] == "stale_hermes_claim_supervisor_block"
    assert blocked["receipt"]["failure_reason"] == "claimed_agent_inactive_without_terminal_receipt"
    assert blocked["receipt"]["evidence"]["supervisor_scope"] == "block_only_no_task_execution_or_completion_claimed"


def test_valid_claimant_receipt_prevents_supervisor_block(tmp_path: Path) -> None:
    _write_presence(tmp_path, "hermes-m5", last_seen_at="2026-06-10T00:00:00+00:00")
    _write_queue(tmp_path, [_claimed_row("already-receipted")])
    receipt_path = _write_claimant_receipt(tmp_path, "already-receipted")

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T00:00:00Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "claimant_terminal_receipt_present"
    assert str(receipt_path) in report["skips"][0]["detail"]
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1


def test_fresh_claimant_presence_prevents_supervisor_block(tmp_path: Path) -> None:
    _write_presence(tmp_path, "hermes-m5", last_seen_at="2026-06-30T23:00:00+00:00")
    _write_queue(tmp_path, [_claimed_row("stale-but-agent-live")])

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T00:00:00Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "claimant_presence_not_stale"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1
