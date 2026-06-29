from __future__ import annotations

import importlib.util
import json
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
            "provider_model_truth_source": "runtime_provider.actual_served",
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
    assert completed_claim.payload["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert completed_run.side_effect_key == f"delegation_run:{run_id}:completed"
    assert completed_run.payload["mission_id"] == "mission-runtime-lifecycle"
    assert completed_run.payload["artifact_refs"] == ["artifact_records:artifact-upstream"]
    assert completed_run.payload["actual_served_provider"] == "openrouter"
    assert completed_run.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in completed_run.payload
    assert "selected_model" not in completed_run.payload
    assert completed_run.payload["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert artifact_written.payload["mission_id"] == "mission-runtime-lifecycle"
    assert artifact_written.payload["artifact_refs"] == ["artifact_records:artifact-1"]
    assert artifact_written.payload["actual_served_provider"] == "openrouter"
    assert artifact_written.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in artifact_written.payload
    assert "selected_model" not in artifact_written.payload
    assert artifact_written.payload["provider_model_truth_source"] == "runtime_provider.actual_served"

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
async def test_runtime_lifecycle_receipts_use_session_mission_when_task_lacks_mission_id(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-mission-fallback",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-without-mission",
        title="No explicit mission id",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "actual_served_provider": "ollama",
            "actual_served_model": "kimi-k2.5",
            "provider_model_truth_source": "runtime_provider.actual_served",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-mission-fallback",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-mission-fallback",
            "run_id": "run-mission-fallback",
            "runtime_run_id": "run-mission-fallback",
            "trace_id": "trace-mission-fallback",
            "correlation_id": "corr-mission-fallback",
            "idempotency_key": "idem-mission-fallback",
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
        status="completed",
        result="done",
        require_identity=True,
    )
    artifact_path = tmp_path / "artifact.md"
    artifact_path.write_text("done\n", encoding="utf-8")
    await lifecycle.record_artifact(
        task=task,
        artifact_id="artifact-mission-fallback",
        artifact_kind="task_result",
        payload_path=artifact_path,
        checksum="sha256:fallback",
        run_id="run-mission-fallback",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-mission-fallback",
        limit=20,
    )
    claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "claimed"
    )
    run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    artifact_written = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "artifact_written" and receipt.status == "completed"
    )

    assert claim.payload["mission_id"] == "sess-runtime-lifecycle-mission-fallback"
    assert claim.payload["mission"] == "sess-runtime-lifecycle-mission-fallback"
    assert claim.payload["mission_id_source"] == "runtime_lifecycle_fallback"
    assert run.payload["mission_id"] == "sess-runtime-lifecycle-mission-fallback"
    assert run.payload["mission"] == "sess-runtime-lifecycle-mission-fallback"
    assert run.payload["mission_id_source"] == "runtime_lifecycle_fallback"
    assert run.payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert artifact_written.payload["mission_id"] == (
        "sess-runtime-lifecycle-mission-fallback"
    )
    assert artifact_written.payload["mission_id_source"] == "runtime_lifecycle_fallback"
    assert artifact_written.payload["artifact_refs"] == [
        "artifact_records:artifact-mission-fallback"
    ]
    with sqlite3.connect(runtime_db_path) as db:
        metadata_json = db.execute(
            "SELECT metadata_json FROM delegation_runs WHERE run_id = ?",
            ("run-mission-fallback",),
        ).fetchone()[0]
    assert json.loads(metadata_json)["mission"] == (
        "sess-runtime-lifecycle-mission-fallback"
    )
    assert json.loads(metadata_json)["mission_id"] == (
        "sess-runtime-lifecycle-mission-fallback"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-mission-fallback",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True

    from dharma_swarm.operator_core.runtime_truth import (
        runtime_truth_packets_from_runtime_db,
    )

    packets = runtime_truth_packets_from_runtime_db(
        runtime_db_path,
        observed_at="2026-06-29T16:20:00Z",
    )
    latest = next(
        packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt"
    )
    assert latest.mission_id == "sess-runtime-lifecycle-mission-fallback"
    assert "mission_id" not in latest.missing_machine_fields


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
async def test_runtime_lifecycle_accounts_agent_runner_no_provider_completion(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-agent-runner-no-provider",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-agent-runner-no-provider",
        title="Complete without attached provider",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-agent-runner-no-provider",
            "provider_execution": False,
            "provider_model_applicability": "not_applicable",
            "provider_model_truth_source": "agent_runner.no_provider_execution",
            "no_provider_model_reason": "agent_runner_no_provider_attached",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-runner-no-provider",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-agent-runner-no-provider",
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
            "run_id": "run-agent-runner-no-provider",
            "trace_id": "trace-agent-runner-no-provider",
            "correlation_id": "corr-agent-runner-no-provider",
            "idempotency_key": "idem-agent-runner-no-provider",
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
        status="completed",
        result="[mock] Agent completed without attached provider",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="completed",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-agent-runner-no-provider",
        limit=20,
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    completed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "completed"
    )

    assert completed_run.payload["provider_execution"] is False
    assert completed_run.payload["provider_model_applicability"] == "not_applicable"
    assert completed_run.payload["provider_model_truth_source"] == (
        "agent_runner.no_provider_execution"
    )
    assert completed_run.payload["no_provider_model_reason"] == (
        "agent_runner_no_provider_attached"
    )
    assert completed_claim.payload["provider_execution"] is False
    assert completed_claim.payload["provider_model_truth_source"] == (
        "agent_runner.no_provider_execution"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-agent-runner-no-provider",
    )
    assert coverage_report["summary"]["provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["production_readiness_blockers"] == []
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_preserves_unproven_provider_execution_marker(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-provider-unproven",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-provider-unproven",
        title="Provider response without actual served evidence",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-provider-unproven",
            "provider_execution": True,
            "provider_model_applicability": "actual_served_unproven",
            "provider_model_truth_source": "orchestrator.provider_execution_unproven",
            "provider_model_missing_reason": (
                "provider_execution_completed_without_actual_served_runtime_evidence"
            ),
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-provider-unproven",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-provider-unproven",
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
            "run_id": "run-provider-unproven",
            "trace_id": "trace-provider-unproven",
            "correlation_id": "corr-provider-unproven",
            "idempotency_key": "idem-provider-unproven",
        },
    )

    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="provider-backed completion with missing actual-served evidence",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-provider-unproven",
        limit=20,
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )

    assert completed_run.payload["provider_execution"] is True
    assert completed_run.payload["provider_model_applicability"] == "actual_served_unproven"
    assert completed_run.payload["provider_model_truth_source"] == (
        "orchestrator.provider_execution_unproven"
    )
    assert completed_run.payload["provider_model_missing_reason"] == (
        "provider_execution_completed_without_actual_served_runtime_evidence"
    )
    assert "actual_served_provider" not in completed_run.payload
    assert "selected_provider" not in completed_run.payload

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-provider-unproven",
    )
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_defaults_blank_terminal_receipt_to_unproven_provider(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-default-unproven",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-default-unproven",
        title="Terminal completion without route truth",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-default-unproven",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-default-unproven",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-default-unproven",
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
            "run_id": "run-default-unproven",
            "trace_id": "trace-default-unproven",
            "correlation_id": "corr-default-unproven",
            "idempotency_key": "idem-default-unproven",
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
        status="completed",
        result="completed without route truth",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="completed",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-default-unproven",
        limit=20,
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    completed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "completed"
    )
    claimed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "claimed"
    )

    assert claimed_claim.payload["provider_execution"] == "pending"
    assert claimed_claim.payload["provider_model_applicability"] == "pending_execution"
    assert claimed_claim.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.provider_execution_pending"
    )
    assert claimed_claim.payload["provider_model_pending_reason"] == (
        "worker_execution_not_terminal"
    )
    for receipt in (completed_run, completed_claim):
        assert receipt.payload["provider_execution"] is True
        assert receipt.payload["provider_model_applicability"] == "actual_served_unproven"
        assert receipt.payload["provider_model_truth_source"] == (
            "runtime_lifecycle.provider_execution_unproven"
        )
        assert receipt.payload["provider_model_missing_reason"] == (
            "terminal_receipt_missing_actual_served_or_no_provider_evidence"
        )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-default-unproven",
    )
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_accounts_provider_chain_execution_error_route(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-provider-chain-error",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-provider-chain-error",
        title="Provider chain fails after selected route",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-provider-chain-error",
            "selected_provider": "openrouter",
            "selected_model": "gpt-5.5",
            "provider_model_truth_source": "agent_runner.provider_chain_failure",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-provider-chain-error",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=60.0,
        metadata={
            "claim_id": "claim-provider-chain-error",
            "run_id": "run-provider-chain-error",
            "runtime_run_id": "run-provider-chain-error",
            "trace_id": "trace-provider-chain-error",
            "correlation_id": "corr-provider-chain-error",
            "idempotency_key": "idem-provider-chain-error",
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="execution_error",
        error="All providers failed in chain ['openrouter']",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="execution_error",
        error="All providers failed in chain ['openrouter']",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-provider-chain-error",
        limit=20,
    )
    failed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "failed"
    )

    assert failed_run.payload["failure_code"] == "execution_error"
    assert failed_run.payload["selected_provider"] == "openrouter"
    assert failed_run.payload["selected_model"] == "gpt-5.5"
    assert failed_run.payload["provider"] == "openrouter"
    assert failed_run.payload["model"] == "gpt-5.5"
    assert failed_run.payload["provider_model_truth_source"] == (
        "agent_runner.provider_chain_failure"
    )
    assert "actual_served_provider" not in failed_run.payload
    assert failed_run.payload["provider_execution"] is True
    assert failed_run.payload["provider_model_applicability"] == "failed_before_serve"
    assert failed_run.payload["provider_model_missing_reason"] == (
        "provider_chain_failed_before_actual_served_response"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-provider-chain-error",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["production_readiness_blockers"] == []
    assert coverage_report["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"failed_before_serve": 1}


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

    from dharma_swarm.operator_core.runtime_truth import (
        runtime_truth_packets_from_runtime_db,
    )

    packets = runtime_truth_packets_from_runtime_db(
        runtime_db_path,
        observed_at="2026-06-29T17:45:00Z",
    )
    latest = next(
        packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt"
    )
    assert latest.receipt_refs[0].startswith("runtime_receipts:")
    assert latest.metadata["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert "artifact_refs" not in latest.missing_machine_fields

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
    assert failed_run.payload["provider_execution"] is True
    assert failed_run.payload["provider_model_applicability"] == "actual_served_unproven"
    assert failed_run.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.provider_execution_unproven"
    )
    assert failed_run.payload["provider_model_missing_reason"] == (
        "terminal_receipt_missing_actual_served_or_no_provider_evidence"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-long-timeout",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}
