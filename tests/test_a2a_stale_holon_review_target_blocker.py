from __future__ import annotations

import json
from pathlib import Path

import scripts.governance.a2a_block_stale_holon_review_targets as holon_blocker
from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from scripts.governance.a2a_block_stale_holon_review_targets import build_report
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


PLAN_PATH = "/Users/dhyana/dharma_swarm/docs/sovereign_holons/08_PACKAGE_CONSOLIDATION_PLAN.md"


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
                "harness": "test-harness",
                "last_seen_at": last_seen_at,
                "status": "degraded",
            }
        ),
        encoding="utf-8",
    )


def _review_row(task_id: str, target: str, **overrides: object) -> dict:
    row = {
        "id": task_id,
        "status": "pending",
        "created": "2026-06-12T03:46:41.684009+00:00",
        "from": "operator_via_oz_warp_session",
        "to": target,
        "type": "review",
        "body": (
            "ADVERSARIAL REVIEW of the Holon Package Consolidation plan: "
            f"{PLAN_PATH} . Deliverable: write findings to "
            "~/.dharma/a2a_bus/collab/convergence/HOLON_PLAN_REVIEW_<your_seat>.md."
        ),
    }
    row.update(overrides)
    return row


def _write_stale_target_presence(root: Path) -> None:
    _write_presence(root, "opus_composer", last_seen_at="2026-06-01T00:00:00+00:00")
    _write_presence(root, "fable_5_cursor", last_seen_at="2026-06-01T00:00:00+00:00")


def test_dry_run_selects_only_stale_holon_review_targets(tmp_path: Path) -> None:
    _write_stale_target_presence(tmp_path)
    _write_queue(
        tmp_path,
        [
            _review_row("holon-plan-review-opus-20260612", "opus_composer"),
            _review_row("holon-plan-review-cursor-20260612", "fable_5_cursor"),
            _review_row("holon-plan-review-other", "opus_composer"),
            {"id": "ordinary-open", "status": "pending", "created": "2026-06-12T00:00:00Z"},
        ],
    )

    report = build_report(tmp_path, timestamp="2026-07-01T07:05:00Z")

    assert report["candidate_count"] == 2
    assert report["applied_count"] == 0
    assert {action["task_id"] for action in report["actions"]} == {
        "holon-plan-review-opus-20260612",
        "holon-plan-review-cursor-20260612",
    }
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 4


def test_apply_blocks_stale_holon_review_targets_with_supervisor_receipts(tmp_path: Path) -> None:
    _write_stale_target_presence(tmp_path)
    _write_queue(
        tmp_path,
        [
            _review_row("holon-plan-review-opus-20260612", "opus_composer"),
            _review_row("holon-plan-review-cursor-20260612", "fable_5_cursor"),
            {"id": "still-open", "status": "pending"},
        ],
    )

    report = build_report(tmp_path, apply=True, timestamp="2026-07-01T07:05:00Z")

    assert report["candidate_count"] == 2
    assert report["applied_count"] == 2
    assert Path(report["backup_path"]).exists()
    readiness = evaluate_a2a_readiness(tmp_path)
    assert readiness.ready is False
    assert readiness.open_tasks == 1
    rows = {row["id"]: row for row in read_queue(tmp_path)}
    for task_id in ("holon-plan-review-opus-20260612", "holon-plan-review-cursor-20260612"):
        row = rows[task_id]
        assert task_lifecycle_state(row)["state"] == "blocked_verified"
        assert row["receipt"]["authority"] == "stale_holon_review_target_supervisor_block"
        assert row["receipt"]["failure_reason"] == "target_review_seat_stale_and_source_plan_missing"
        assert row["receipt"]["evidence"]["supervisor_scope"] == "block_only_no_review_completion_or_target_impersonation"


def test_existing_plan_path_prevents_supervisor_block(tmp_path: Path, monkeypatch) -> None:
    _write_stale_target_presence(tmp_path)
    plan = tmp_path / "08_PACKAGE_CONSOLIDATION_PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    monkeypatch.setattr(holon_blocker, "_plan_path", lambda _row: plan)
    _write_queue(tmp_path, [_review_row("holon-plan-review-opus-20260612", "opus_composer")])

    report = build_report(tmp_path, timestamp="2026-07-01T07:05:00Z")

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "plan_path_exists"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1


def test_existing_target_deliverable_prevents_supervisor_block(tmp_path: Path) -> None:
    _write_stale_target_presence(tmp_path)
    deliverable = tmp_path / "a2a_bus" / "collab" / "convergence" / "HOLON_PLAN_REVIEW_opus_composer.md"
    deliverable.parent.mkdir(parents=True, exist_ok=True)
    deliverable.write_text("VERDICT\n", encoding="utf-8")
    _write_queue(tmp_path, [_review_row("holon-plan-review-opus-20260612", "opus_composer")])

    report = build_report(tmp_path, timestamp="2026-07-01T07:05:00Z")

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "target_deliverable_present"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1
