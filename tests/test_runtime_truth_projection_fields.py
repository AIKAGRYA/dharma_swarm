import asyncio
import sqlite3

from dharma_swarm.operator_core.runtime_truth import (
    runtime_truth_packets_from_runtime_db,
    summarize_runtime_truth_packets,
)
from dharma_swarm.runtime_state import RuntimeStateStore


def test_runtime_truth_projects_delegation_current_artifact_id(tmp_path):
    db_path = tmp_path / "runtime.db"
    asyncio.run(RuntimeStateStore(db_path).init_db())
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id, task_id,"
            " trace_id, correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-current-artifact",
                "delegation_run",
                "run-current-artifact",
                "task-current-artifact",
                "trace-current-artifact",
                "corr-current-artifact",
                "agent-current-artifact",
                "running",
                "{}",
                "2026-06-11T06:50:00Z",
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, assigned_to,"
            " current_artifact_id, status, started_at, metadata_json, trace_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-current-artifact",
                "task-current-artifact",
                "agent-current-artifact",
                "artifact-current-pointer",
                "running",
                "2026-06-11T06:49:00Z",
                '{"mission_id":"mission-current-artifact"}',
                "trace-current-artifact",
            ),
        )
        db.commit()

    packets = runtime_truth_packets_from_runtime_db(db_path, observed_at="2026-06-11T06:51:00Z")
    latest = next(packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt")

    assert list(latest.artifact_refs) == [
        "delegation_runs:run-current-artifact:current_artifact_id:artifact-current-pointer"
    ]
    assert "artifact_refs" not in latest.missing_machine_fields
    assert latest.mission_id == "mission-current-artifact"
    assert latest.proof_grade == "MISSING"
    assert "idempotency_record" in latest.missing_machine_fields

    summary = summarize_runtime_truth_packets(packets)
    assert summary["mission_id"] == "mission-current-artifact"
    assert summary["artifact_refs"] == [
        "delegation_runs:run-current-artifact:current_artifact_id:artifact-current-pointer"
    ]


def test_runtime_truth_projects_idempotency_record_ref_when_present(tmp_path):
    db_path = tmp_path / "runtime.db"
    asyncio.run(RuntimeStateStore(db_path).init_db())
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id, task_id,"
            " trace_id, correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-idem",
                "delegation_run",
                "run-idem",
                "task-idem",
                "trace-idem",
                "corr-idem",
                "agent-idem",
                "idem-key",
                "side-effect",
                "completed",
                '{"mission_id":"mission-idem"}',
                "2026-06-11T09:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, side_effect_key,"
            " run_id, task_id, trace_id, correlation_id, status,"
            " result_receipt_id, metadata_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-key",
                "side-effect",
                "run-idem",
                "task-idem",
                "trace-idem",
                "corr-idem",
                "completed",
                "rr-idem",
                "{}",
                "2026-06-11T08:59:00Z",
                "2026-06-11T09:00:00Z",
            ),
        )
        db.commit()

    packets = runtime_truth_packets_from_runtime_db(db_path, observed_at="2026-06-11T09:01:00Z")
    latest = next(packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt")

    assert latest.metadata["idempotency_record_ref"] == "idempotency_records:idem-key:side-effect"
    assert latest.metadata["idempotency_result_receipt_ref"] == "runtime_receipts:rr-idem"
    assert "idempotency_records:idem-key:side-effect" in latest.source_refs
    assert latest.retry_intent_key == "idem-key"
    assert "idempotency_record" not in latest.missing_machine_fields
