from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from dharma_swarm.models import Task, TaskDispatch, TopologyType
from dharma_swarm.runtime_lifecycle import RuntimeLifecycle
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.session_ledger import SessionLedger


def _table_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as db:
        row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0] if row else 0)


def _load_receipt_coverage_report():
    spec = importlib.util.spec_from_file_location(
        "runtime_receipt_coverage_report",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "runtime_receipt_coverage_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


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
            "mission_id": "mission-runtime-lifecycle",
            "actual_provider": "openrouter",
            "actual_model": "qwen3-coder-live",
            "provider_model_truth_source": "test.actual_served_metadata",
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

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id=run_id,
        limit=20,
    )
    receipt_types = {receipt.receipt_type for receipt in receipts}
    assert {
        "delegation_run",
        "child_spawned",
        "child_completed",
        "artifact",
        "artifact_written",
    } <= receipt_types

    completed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "completed"
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    artifact_written = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "artifact_written" and receipt.status == "completed"
    )
    assert completed_claim.side_effect_key == "task_claim:claim-1:completed"
    assert completed_claim.payload["mission_id"] == "mission-runtime-lifecycle"
    assert completed_claim.payload["actual_served_provider"] == "openrouter"
    assert completed_claim.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in completed_claim.payload
    assert "selected_model" not in completed_claim.payload
    assert completed_claim.payload["provider_model_truth_source"] == "test.actual_served_metadata"
    assert completed_run.side_effect_key == f"delegation_run:{run_id}:completed"
    assert completed_run.payload["mission_id"] == "mission-runtime-lifecycle"
    assert completed_run.payload["artifact_refs"] == ["artifact_records:artifact-upstream"]
    assert completed_run.payload["actual_served_provider"] == "openrouter"
    assert completed_run.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in completed_run.payload
    assert "selected_model" not in completed_run.payload
    assert completed_run.payload["provider_model_truth_source"] == "test.actual_served_metadata"
    assert artifact_written.payload["mission_id"] == "mission-runtime-lifecycle"
    assert artifact_written.payload["artifact_refs"] == ["artifact_records:artifact-1"]
    assert artifact_written.payload["actual_served_provider"] == "openrouter"
    assert artifact_written.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in artifact_written.payload
    assert "selected_model" not in artifact_written.payload
    assert artifact_written.payload["provider_model_truth_source"] == "test.actual_served_metadata"

    runtime_store = RuntimeStateStore(runtime_db_path)
    claim_idem = runtime_store.get_idempotency_record_sync(
        "idem_" + run_id,
        completed_claim.side_effect_key,
    )
    run_idem = runtime_store.get_idempotency_record_sync(
        "idem_" + run_id,
        completed_run.side_effect_key,
    )
    assert claim_idem is not None
    assert claim_idem.status == "completed"
    assert claim_idem.result_receipt_id == completed_claim.receipt_id
    assert run_idem is not None
    assert run_idem.status == "completed"
    assert run_idem.result_receipt_id == completed_run.receipt_id

    coverage_report = _load_receipt_coverage_report().build_report(runtime_db_path)
    assert coverage_report["summary"]["score_gate_70_to_75"] is True


@pytest.mark.asyncio
async def test_runtime_lifecycle_accounts_claim_timeout_as_no_provider_execution(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-claim-timeout",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-claim-timeout",
        title="Claim timeout before worker starts",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-14T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-claim-timeout",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-claim-timeout",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=60.0,
        metadata={
            "claim_id": "claim-timeout",
            "run_id": "run-claim-timeout",
            "runtime_run_id": "run-claim-timeout",
            "trace_id": "trace-claim-timeout",
            "correlation_id": "corr-claim-timeout",
            "idempotency_key": "idem-claim-timeout",
            "claim_timeout_seconds": 90,
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="claim_timeout",
        error="Claim expired before worker started",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="claim_timeout",
        error="Claim expired before worker started",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-claim-timeout",
        limit=20,
    )
    failed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "failed"
    )
    failed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "failed"
    )

    assert failed_claim.payload["provider_execution"] is False
    assert failed_claim.payload["provider_model_applicability"] == "not_applicable"
    assert failed_claim.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.claim_timeout_no_provider_execution"
    )
    assert failed_claim.payload["no_provider_model_reason"] == (
        "claim_timeout_before_worker_execution"
    )
    assert failed_run.side_effect_key == "delegation_run:run-claim-timeout:failed"
    assert failed_run.payload["failure_code"] == "claim_timeout"
    assert failed_run.payload["provider_execution"] is False
    assert failed_run.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.claim_timeout_no_provider_execution"
    )
    assert failed_run.payload["no_provider_model_reason"] == (
        "claim_timeout_before_worker_execution"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-claim-timeout",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["production_readiness_blockers"] == []
    assert coverage_report["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_long_timeout_keeps_provider_execution_unknown(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-long-timeout",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-long-timeout",
        title="Long timeout during execution",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-14T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-long-timeout",
            "timeout_seconds": 3600,
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-long-timeout",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=3600.0,
        metadata={
            "claim_id": "claim-long-timeout",
            "run_id": "run-long-timeout",
            "runtime_run_id": "run-long-timeout",
            "trace_id": "trace-long-timeout",
            "correlation_id": "corr-long-timeout",
            "idempotency_key": "idem-long-timeout",
            "claim_timeout_seconds": 3660,
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="running",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="long_timeout",
        error="Execution exceeded long timeout",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="long_timeout",
        error="Execution exceeded long timeout",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-long-timeout",
        limit=20,
    )
    failed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "failed"
    )

    assert failed_run.side_effect_key == "delegation_run:run-long-timeout:failed"
    assert failed_run.payload["failure_code"] == "long_timeout"
    assert failed_run.payload["mission_id"] == "mission-long-timeout"
    assert failed_run.payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert "provider_execution" not in failed_run.payload
    assert "provider_model_truth_source" not in failed_run.payload

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-long-timeout",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}
