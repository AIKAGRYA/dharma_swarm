from __future__ import annotations

import json
from pathlib import Path

import pytest

# Cross-lane drift guard: a2a_task_lifecycle ships on the holon/spine-v1 lane
# and is absent on branches that predate it. Skip instead of breaking
# collection for the whole suite.
pytest.importorskip("dharma_swarm.operator_core.a2a_task_lifecycle")

from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness, main


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = root / "a2a_bus" / "tasks" / "queue.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_a2a_readiness_degrades_when_queue_missing(tmp_path: Path) -> None:
    report = evaluate_a2a_readiness(tmp_path)

    assert report.ready is False
    assert report.gate_status == "DEGRADED"
    assert report.reasons == ["queue_missing"]


def test_a2a_readiness_degrades_for_open_or_claimed_tasks(tmp_path: Path) -> None:
    _write_queue(
        tmp_path,
        [
            {"id": "t1", "status": "pending"},
            {"id": "t2", "status": "claimed", "claimed_by": "agent-1"},
        ],
    )

    report = evaluate_a2a_readiness(tmp_path)

    assert report.ready is False
    assert report.gate_status == "DEGRADED"
    assert report.open_tasks == 2
    assert "open_or_claimed_tasks_present" in report.reasons


def test_a2a_readiness_ready_for_verified_closed_queue(tmp_path: Path) -> None:
    receipt = build_task_receipt(
        task_id="t1",
        agent_uid="agent-1",
        status="completed",
        summary="done",
        evaluation={"overall_verdict": "pass", "criteria_results": [], "gate_results": []},
        timestamp="2026-06-05T00:00:00+00:00",
    )
    _write_queue(
        tmp_path,
        [
            {
                "id": "t1",
                "status": "completed",
                "completed_by": "agent-1",
                "receipt": receipt,
            }
        ],
    )

    report = evaluate_a2a_readiness(tmp_path)

    assert report.ready is True
    assert report.gate_status == "READY"
    assert report.reasons == []


def test_a2a_readiness_strict_exits_nonzero_when_degraded(tmp_path: Path) -> None:
    assert main(["--state-root", str(tmp_path), "--strict"]) == 2
