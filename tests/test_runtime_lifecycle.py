from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.models import Task, TaskDispatch, TopologyType
from dharma_swarm.runtime_lifecycle import RuntimeLifecycle
from dharma_swarm.session_ledger import SessionLedger


def _table_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as db:
        row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0] if row else 0)


@pytest.mark.asyncio
async def test_runtime_lifecycle_preserves_structured_row_idempotence(tmp_path: Path) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-123",
        title="Write runtime extraction report",
        metadata={
            "active_claim": {
                "claimed_at": "2026-04-27T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": ["task_result"],
            "parent_run_id": "parent-run-1",
            "current_artifact_id": "artifact-upstream",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-1",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-1",
            "retry_count": 2,
            "max_retries": 4,
            "claim_timeout_seconds": 300,
        },
    )

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed")
    await lifecycle.record_task_claim(dispatch, task=task, status="completed")

    run_id = lifecycle.ensure_runtime_run_id(dispatch)
    await lifecycle.record_delegation_run(dispatch, task=task, status="running")
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="done",
    )

    payload_path = tmp_path / "artifact.md"
    payload_path.write_text("# Artifact\n", encoding="utf-8")
    await lifecycle.record_artifact(
        task=task,
        artifact_id="artifact-1",
        artifact_kind="task_result",
        payload_path=payload_path,
        manifest_path=tmp_path / "artifact.json",
        checksum="abc123",
        run_id=run_id,
        metadata={"source_test": "runtime_lifecycle"},
    )
    await lifecycle.record_artifact(
        task=task,
        artifact_id="artifact-1",
        artifact_kind="task_result",
        payload_path=payload_path,
        manifest_path=tmp_path / "artifact.json",
        checksum="abc123",
        run_id=run_id,
        metadata={"source_test": "runtime_lifecycle"},
    )

    assert _table_count(runtime_db_path, "task_claims") == 1
    assert _table_count(runtime_db_path, "delegation_runs") == 1
    assert _table_count(runtime_db_path, "artifact_records") == 1

    with sqlite3.connect(runtime_db_path) as db:
        claim_status = db.execute(
            "SELECT status FROM task_claims WHERE claim_id = ?",
            ("claim-1",),
        ).fetchone()[0]
        run_status, stored_run_id = db.execute(
            "SELECT status, run_id FROM delegation_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        artifact_run_id = db.execute(
            "SELECT run_id FROM artifact_records WHERE artifact_id = ?",
            ("artifact-1",),
        ).fetchone()[0]

    assert claim_status == "completed"
    assert run_status == "completed"
    assert stored_run_id == run_id
    assert artifact_run_id == run_id
