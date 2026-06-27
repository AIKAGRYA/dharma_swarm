from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


def _load_probe_module():
    spec = importlib.util.spec_from_file_location(
        "runtime_lifecycle_receipt_probe",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "runtime_lifecycle_receipt_probe.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_runtime_lifecycle_receipt_probe_writes_scoped_coverage_proof(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-probe-test",
            run_id="run-probe-test",
            task_id="task-probe-test",
            claim_id="claim-probe-test",
            trace_id="trace-probe-test",
            correlation_id="corr-probe-test",
            session_id="sess-probe-test",
        )
    )

    assert result["run_id"] == "run-probe-test"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert Path(result["payload_path"]).exists()
    assert Path(result["manifest_path"]).exists()

    with sqlite3.connect(db_path) as db:
        completed_receipt_id = db.execute(
            """
            SELECT receipt_id
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-probe-test",),
        ).fetchone()[0]
        idem_status, result_receipt_id = db.execute(
            """
            SELECT status, result_receipt_id
            FROM idempotency_records
            WHERE idempotency_key = ?
              AND side_effect_key = ?
            """,
            (
                "idem_run-probe-test",
                "delegation_run:run-probe-test:completed",
            ),
        ).fetchone()
        artifact_run_id = db.execute(
            "SELECT run_id FROM artifact_records WHERE artifact_id = ?",
            ("artifact_run-probe-test",),
        ).fetchone()[0]

    assert idem_status == "completed"
    assert result_receipt_id == completed_receipt_id
    assert artifact_run_id == "run-probe-test"


def test_runtime_lifecycle_receipt_probe_can_stamp_provider_model_truth(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-provider-model-probe-test",
            run_id="run-provider-model-probe-test",
            task_id="task-provider-model-probe-test",
            claim_id="claim-provider-model-probe-test",
            trace_id="trace-provider-model-probe-test",
            correlation_id="corr-provider-model-probe-test",
            session_id="sess-provider-model-probe-test",
            selected_provider="openrouter",
            selected_model="qwen3-coder-live",
        )
    )

    assert result["selected_provider"] == "openrouter"
    assert result["selected_model"] == "qwen3-coder-live"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_coverage_complete"] is True
    assert result["coverage"]["summary"]["provider_model_provenance_complete"] is False
    assert result["coverage"]["summary"]["production_readiness_blockers"] == [
        "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata"
    ]
    assert (
        result["coverage"]["summary"]["latest_major_task_receipts_provider_model_percent"]
        == 100.0
    )
    assert (
        result["coverage"]["summary"]["latest_major_task_receipts_provider_model_provenance_percent"]
        == 0.0
    )
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"pending_execution": 1, "probe_selected": 1}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"probe_selected": 1}

    with sqlite3.connect(db_path) as db:
        payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-provider-model-probe-test",),
        ).fetchone()[0]

    payload = json.loads(payload_json)
    assert payload["selected_provider"] == "openrouter"
    assert payload["selected_model"] == "qwen3-coder-live"
    assert payload["provider_model_truth_source"] == (
        "runtime_lifecycle_receipt_probe.selected_metadata"
    )


def test_runtime_lifecycle_receipt_probe_can_stamp_no_provider_truth(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-no-provider-probe-test",
            run_id="run-no-provider-probe-test",
            task_id="task-no-provider-probe-test",
            claim_id="claim-no-provider-probe-test",
            trace_id="trace-no-provider-probe-test",
            correlation_id="corr-no-provider-probe-test",
            session_id="sess-no-provider-probe-test",
            no_provider_execution=True,
            no_provider_model_reason="unit_test_no_provider_execution",
        )
    )

    assert result["provider_execution"] is False
    assert result["provider_model_truth_source"] == "runtime_control.no_provider_execution"
    assert result["no_provider_model_reason"] == "unit_test_no_provider_execution"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_accounted_complete"] is True
    assert result["coverage"]["summary"]["production_readiness_blockers"] == []
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 2}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}

    with sqlite3.connect(db_path) as db:
        payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-no-provider-probe-test",),
        ).fetchone()[0]

    payload = json.loads(payload_json)
    assert payload["provider_execution"] is False
    assert payload["provider_model_applicability"] == "not_applicable"
    assert payload["provider_model_truth_source"] == (
        "runtime_control.no_provider_execution"
    )
    assert payload["no_provider_model_reason"] == "unit_test_no_provider_execution"


def test_runtime_lifecycle_receipt_probe_preserves_actual_served_provider_model(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-served-provider-model-test",
            run_id="run-served-provider-model-test",
            task_id="task-served-provider-model-test",
            claim_id="claim-served-provider-model-test",
            trace_id="trace-served-provider-model-test",
            correlation_id="corr-served-provider-model-test",
            session_id="sess-served-provider-model-test",
            actual_served_provider="openrouter",
            actual_served_model="qwen3-coder-live",
            provider_model_truth_source="runtime_provider.actual_served",
        )
    )

    assert result["actual_served_provider"] == "openrouter"
    assert result["actual_served_model"] == "qwen3-coder-live"
    assert result["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_coverage_complete"] is True
    assert result["coverage"]["summary"]["provider_model_provenance_complete"] is True
    assert result["coverage"]["summary"]["production_readiness_blockers"] == []
    assert (
        result["coverage"]["summary"][
            "latest_major_task_receipts_provider_model_provenance_percent"
        ]
        == 100.0
    )
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"pending_execution": 1, "served_field": 1}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"served_field": 1}

    with sqlite3.connect(db_path) as db:
        payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-served-provider-model-test",),
        ).fetchone()[0]

    payload = json.loads(payload_json)
    assert payload["actual_served_provider"] == "openrouter"
    assert payload["actual_served_model"] == "qwen3-coder-live"
    assert payload["provider"] == "openrouter"
    assert payload["model"] == "qwen3-coder-live"
    assert "selected_provider" not in payload
    assert "selected_model" not in payload
    assert payload["provider_model_truth_source"] == "runtime_provider.actual_served"


def test_runtime_lifecycle_receipt_probe_can_exercise_sync_store_producer(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_sync_store_probe(
            db_path,
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-sync-probe-test",
            run_id="run-sync-probe-test",
            task_id="task-sync-probe-test",
            claim_id="claim-sync-probe-test",
            trace_id="trace-sync-probe-test",
            correlation_id="corr-sync-probe-test",
            session_id="sess-sync-probe-test",
        )
    )

    assert result["probe"] == "runtime_state_sync_receipt_probe"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert Path(result["payload_path"]).exists()

    with sqlite3.connect(db_path) as db:
        completed_receipt = db.execute(
            """
            SELECT receipt_id, side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-sync-probe-test",),
        ).fetchone()
        idem_status, result_receipt_id = db.execute(
            """
            SELECT status, result_receipt_id
            FROM idempotency_records
            WHERE idempotency_key = ?
              AND side_effect_key = ?
            """,
            (
                "idem_run-sync-probe-test",
                "delegation_run:run-sync-probe-test:completed",
            ),
        ).fetchone()

    assert completed_receipt[1] == "delegation_run:run-sync-probe-test:completed"
    assert "mission-sync-probe-test" in completed_receipt[2]
    assert idem_status == "completed"
    assert result_receipt_id == completed_receipt[0]


def test_runtime_lifecycle_receipt_probe_can_exercise_orchestrator_spine_producer(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_orchestrator_spine_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-orch-spine-probe-test",
            run_id="run-orch-spine-probe-test",
            task_id="task-orch-spine-probe-test",
            claim_id="claim-orch-spine-probe-test",
            trace_id="trace-orch-spine-probe-test",
            correlation_id="corr-orch-spine-probe-test",
            session_id="sess-orch-spine-probe-test",
            selected_provider="openrouter",
            selected_model="qwen3-coder-live",
        )
    )

    assert result["probe"] == "orchestrator_spine_dispatch_probe"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_coverage_complete"] is True
    assert result["coverage"]["summary"]["provider_model_provenance_complete"] is False
    assert result["coverage"]["summary"]["production_readiness_blockers"] == [
        "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata"
    ]
    assert result["board_updates"] >= 1
    assert result["pool_releases"] == 1

    with sqlite3.connect(db_path) as db:
        receipt_json = db.execute(
            """
            SELECT receipt_json
            FROM delegation_runs
            WHERE run_id = ?
              AND status = 'completed'
            """,
            ("run-orch-spine-probe-test",),
        ).fetchone()[0]
        completed_receipt = db.execute(
            """
            SELECT receipt_id, side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-orch-spine-probe-test",),
        ).fetchone()

    assert result["evidence_receipt_id"] in receipt_json
    assert completed_receipt[1] == "delegation_run:run-orch-spine-probe-test:completed"
    payload = json.loads(completed_receipt[2])
    assert payload["mission_id"] == "mission-orch-spine-probe-test"
    assert payload["selected_provider"] == "openrouter"
    assert payload["selected_model"] == "qwen3-coder-live"
    assert payload["provider_model_truth_source"] == (
        "runtime_lifecycle_receipt_probe.selected_metadata"
    )


def test_orchestrator_spine_probe_can_stamp_no_provider_truth(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_orchestrator_spine_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-orch-spine-no-provider-test",
            run_id="run-orch-spine-no-provider-test",
            task_id="task-orch-spine-no-provider-test",
            claim_id="claim-orch-spine-no-provider-test",
            trace_id="trace-orch-spine-no-provider-test",
            correlation_id="corr-orch-spine-no-provider-test",
            session_id="sess-orch-spine-no-provider-test",
            no_provider_execution=True,
            no_provider_model_reason="unit_test_orchestrator_no_provider_execution",
        )
    )

    assert result["probe"] == "orchestrator_spine_dispatch_probe"
    assert result["provider_execution"] is False
    assert result["provider_model_truth_source"] == "runtime_control.no_provider_execution"
    assert result["no_provider_model_reason"] == (
        "unit_test_orchestrator_no_provider_execution"
    )
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_accounted_complete"] is True
    assert result["coverage"]["summary"]["terminal_provider_model_accounted_complete"] is True
    assert result["coverage"]["summary"]["production_readiness_blockers"] == []
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 2}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}

    with sqlite3.connect(db_path) as db:
        payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-orch-spine-no-provider-test",),
        ).fetchone()[0]

    payload = json.loads(payload_json)
    assert payload["provider_execution"] is False
    assert payload["provider_model_applicability"] == "not_applicable"
    assert payload["provider_model_truth_source"] == (
        "runtime_control.no_provider_execution"
    )
    assert payload["no_provider_model_reason"] == (
        "unit_test_orchestrator_no_provider_execution"
    )


def test_orchestrator_spine_probe_can_exercise_fanout_success(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_orchestrator_spine_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-orch-fanout-success-test",
            run_id="run-orch-fanout-success-test",
            task_id="task-orch-fanout-success-test",
            claim_id="claim-orch-fanout-success-test",
            trace_id="trace-orch-fanout-success-test",
            correlation_id="corr-orch-fanout-success-test",
            session_id="sess-orch-fanout-success-test",
            topology="fan-out",
        )
    )

    assert result["probe"] == "orchestrator_spine_dispatch_probe"
    assert result["topology"] == "fan_out"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True

    with sqlite3.connect(db_path) as db:
        claim_side_effect, claim_payload_json = db.execute(
            """
            SELECT side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'task_claim'
              AND status = 'completed'
            """,
            ("run-orch-fanout-success-test",),
        ).fetchone()
        run_side_effect, run_payload_json = db.execute(
            """
            SELECT side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-orch-fanout-success-test",),
        ).fetchone()
        metadata_json = db.execute(
            """
            SELECT metadata_json
            FROM delegation_runs
            WHERE run_id = ?
              AND status = 'completed'
            """,
            ("run-orch-fanout-success-test",),
        ).fetchone()[0]

    claim_payload = json.loads(claim_payload_json)
    run_payload = json.loads(run_payload_json)
    metadata = json.loads(metadata_json)
    assert claim_side_effect == "task_claim:claim-orch-fanout-success-test:completed"
    assert run_side_effect == "delegation_run:run-orch-fanout-success-test:completed"
    assert claim_payload["mission_id"] == "mission-orch-fanout-success-test"
    assert run_payload["mission_id"] == "mission-orch-fanout-success-test"
    assert run_payload["artifact_refs"] == [
        "artifact_records:artifact_run-orch-fanout-success-test"
    ]
    assert metadata["topology"] == "fan_out"


def test_orchestrator_spine_probe_records_real_success_artifact_without_preseed(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_orchestrator_spine_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-orch-real-artifact-test",
            run_id="run-orch-real-artifact-test",
            task_id="task-orch-real-artifact-test",
            claim_id="claim-orch-real-artifact-test",
            trace_id="trace-orch-real-artifact-test",
            correlation_id="corr-orch-real-artifact-test",
            session_id="sess-orch-real-artifact-test",
            topology="fan-out",
            actual_served_provider="openrouter",
            actual_served_model="qwen3-coder-live",
            provider_model_truth_source="runtime_provider.actual_served",
            preseed_artifact=False,
        )
    )

    expected_artifact = "artifact_task_result_task-orch-real-artifact-test"
    assert result["preseed_artifact"] is False
    assert result["task_result_artifact_id"] == expected_artifact
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"][
        "latest_terminal_major_task_receipts_provider_model_provenance_percent"
    ] == 100.0

    with sqlite3.connect(db_path) as db:
        payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-orch-real-artifact-test",),
        ).fetchone()[0]
        current_artifact_id = db.execute(
            """
            SELECT current_artifact_id
            FROM delegation_runs
            WHERE run_id = ?
              AND status = 'completed'
            """,
            ("run-orch-real-artifact-test",),
        ).fetchone()[0]
        artifact_run_id, artifact_kind = db.execute(
            """
            SELECT run_id, artifact_kind
            FROM artifact_records
            WHERE artifact_id = ?
            """,
            (expected_artifact,),
        ).fetchone()

    payload = json.loads(payload_json)
    assert payload["artifact_refs"] == [f"artifact_records:{expected_artifact}"]
    assert payload["no_artifact_refs_reason"] == ""
    assert payload["actual_served_provider"] == "openrouter"
    assert payload["actual_served_model"] == "qwen3-coder-live"
    assert payload["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert current_artifact_id == expected_artifact
    assert artifact_run_id == "run-orch-real-artifact-test"
    assert artifact_kind == "task_result"


def test_orchestrator_spine_probe_can_exercise_fanout_execution_error(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_orchestrator_spine_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-orch-fanout-error-test",
            run_id="run-orch-fanout-error-test",
            task_id="task-orch-fanout-error-test",
            claim_id="claim-orch-fanout-error-test",
            trace_id="trace-orch-fanout-error-test",
            correlation_id="corr-orch-fanout-error-test",
            session_id="sess-orch-fanout-error-test",
            topology="fan-out",
            runner_error="synthetic execution error for receipt proof",
        )
    )

    assert result["probe"] == "orchestrator_spine_dispatch_probe"
    assert result["topology"] == "fan_out"
    assert result["runner_error"] == "synthetic execution error for receipt proof"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["board_updates"] >= 2
    assert result["pool_releases"] == 1

    with sqlite3.connect(db_path) as db:
        claim_side_effect, claim_payload_json = db.execute(
            """
            SELECT side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'task_claim'
              AND status = 'failed'
            """,
            ("run-orch-fanout-error-test",),
        ).fetchone()
        run_side_effect, run_payload_json = db.execute(
            """
            SELECT side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'failed'
            """,
            ("run-orch-fanout-error-test",),
        ).fetchone()
        failure_code, metadata_json = db.execute(
            """
            SELECT failure_code, metadata_json
            FROM delegation_runs
            WHERE run_id = ?
            """,
            ("run-orch-fanout-error-test",),
        ).fetchone()

    claim_payload = json.loads(claim_payload_json)
    run_payload = json.loads(run_payload_json)
    metadata = json.loads(metadata_json)
    assert claim_side_effect == "task_claim:claim-orch-fanout-error-test:failed"
    assert run_side_effect == "delegation_run:run-orch-fanout-error-test:failed"
    assert claim_payload["mission_id"] == "mission-orch-fanout-error-test"
    assert run_payload["mission_id"] == "mission-orch-fanout-error-test"
    assert run_payload["failure_code"] == "execution_error"
    assert run_payload["artifact_refs"] == [
        "artifact_records:artifact_run-orch-fanout-error-test"
    ]
    assert failure_code == "execution_error"
    assert metadata["topology"] == "fan_out"


def test_orchestrator_spine_probe_preserves_actual_served_provider_model(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_orchestrator_spine_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            artifact_dir=tmp_path / "artifacts",
            mission_id="mission-orch-served-provider-model-test",
            run_id="run-orch-served-provider-model-test",
            task_id="task-orch-served-provider-model-test",
            claim_id="claim-orch-served-provider-model-test",
            trace_id="trace-orch-served-provider-model-test",
            correlation_id="corr-orch-served-provider-model-test",
            session_id="sess-orch-served-provider-model-test",
            actual_served_provider="openrouter",
            actual_served_model="qwen3-coder-live",
            provider_model_truth_source="runtime_provider.actual_served",
            topology="fan-out",
        )
    )

    assert result["probe"] == "orchestrator_spine_dispatch_probe"
    assert result["topology"] == "fan_out"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_coverage_complete"] is False
    assert result["coverage"]["summary"]["provider_model_provenance_complete"] is True
    assert result["coverage"]["summary"]["terminal_provider_model_coverage_complete"] is True
    assert result["coverage"]["summary"]["terminal_provider_model_provenance_complete"] is True
    assert result["coverage"]["summary"]["terminal_provider_model_accounted_complete"] is True
    assert (
        result["coverage"]["summary"][
            "latest_terminal_major_task_receipts_provider_model_provenance_percent"
        ]
        == 100.0
    )
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"pending_execution": 1, "served_field": 1}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"served_field": 1}
    assert result["coverage"]["summary"]["production_readiness_blockers"] == []
    assert result["board_updates"] >= 1
    assert result["pool_releases"] == 1

    with sqlite3.connect(db_path) as db:
        payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'completed'
            """,
            ("run-orch-served-provider-model-test",),
        ).fetchone()[0]
        artifact_payload_json = db.execute(
            """
            SELECT payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'artifact_written'
              AND status = 'completed'
              AND json_extract(payload_json, '$.artifact_kind') = 'orchestrator_spine_dispatch_probe'
            """,
            ("run-orch-served-provider-model-test",),
        ).fetchone()[0]

    payload = json.loads(payload_json)
    artifact_payload = json.loads(artifact_payload_json)
    assert "actual_served_provider" not in artifact_payload
    assert "actual_served_model" not in artifact_payload
    assert payload["actual_served_provider"] == "openrouter"
    assert payload["actual_served_model"] == "qwen3-coder-live"
    assert payload["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert "selected_provider" not in payload
    assert "selected_model" not in payload

    output = StringIO()
    with redirect_stdout(output):
        mod._print_text(result)
    rendered = output.getvalue()
    assert "Topology:      fan_out" in rendered
    assert "Terminal provider/model: 100.0% proof=100.0% accounted=100.0% terminal=1" in rendered
    assert "Provider/model pending execution: 1" in rendered


def test_runtime_lifecycle_receipt_probe_can_exercise_dispatch_dropoff(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_runtime_lifecycle_dropoff_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            mission_id="mission-dropoff-probe-test",
            run_id="run-dropoff-probe-test",
            task_id="task-dropoff-probe-test",
            claim_id="claim-dropoff-probe-test",
            trace_id="trace-dropoff-probe-test",
            correlation_id="corr-dropoff-probe-test",
            session_id="sess-dropoff-probe-test",
        )
    )

    assert result["probe"] == "runtime_lifecycle_dropoff_probe"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"][
        "latest_terminal_major_task_receipts_provider_model_accounted_percent"
    ] == 100.0
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1, "pending_execution": 1}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}
    assert result["artifact_id"] == ""

    with sqlite3.connect(db_path) as db:
        failed_receipt = db.execute(
            """
            SELECT receipt_id, side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'failed'
            """,
            ("run-dropoff-probe-test",),
        ).fetchone()
        idem_status, result_receipt_id = db.execute(
            """
            SELECT status, result_receipt_id
            FROM idempotency_records
            WHERE idempotency_key = ?
              AND side_effect_key = ?
            """,
            (
                "idem_run-dropoff-probe-test",
                "delegation_run:run-dropoff-probe-test:failed",
            ),
        ).fetchone()

    assert failed_receipt[1] == "delegation_run:run-dropoff-probe-test:failed"
    failed_payload = json.loads(failed_receipt[2])
    assert failed_payload["mission_id"] == "mission-dropoff-probe-test"
    assert failed_payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert failed_payload["provider_execution"] is False
    assert failed_payload["provider_model_applicability"] == "not_applicable"
    assert failed_payload["provider_model_truth_source"] == (
        "runtime_lifecycle.dispatch_dropoff_no_provider_execution"
    )
    assert failed_payload["no_provider_model_reason"] == (
        "dispatch_dropoff_before_worker_execution"
    )
    assert idem_status == "completed"
    assert result_receipt_id == failed_receipt[0]


def test_runtime_lifecycle_receipt_probe_dropoff_cli_text_handles_no_artifact(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe",
            "--producer",
            "runtime-lifecycle-dropoff",
            "--db",
            str(db_path),
            "--run-id",
            "run-dropoff-cli-test",
            "--task-id",
            "task-dropoff-cli-test",
            "--claim-id",
            "claim-dropoff-cli-test",
            "--trace-id",
            "trace-dropoff-cli-test",
            "--correlation-id",
            "corr-dropoff-cli-test",
            "--session-id",
            "sess-dropoff-cli-test",
        ],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RUNTIME_LIFECYCLE_DROPOFF_PROBE" in captured.out
    assert "70->75 gate:   PASS" in captured.out
    assert "Payload:" not in captured.out


def test_runtime_lifecycle_receipt_probe_can_exercise_claim_timeout(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_runtime_lifecycle_claim_timeout_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            mission_id="mission-claim-timeout-probe-test",
            run_id="run-claim-timeout-probe-test",
            task_id="task-claim-timeout-probe-test",
            claim_id="claim-claim-timeout-probe-test",
            trace_id="trace-claim-timeout-probe-test",
            correlation_id="corr-claim-timeout-probe-test",
            session_id="sess-claim-timeout-probe-test",
        )
    )

    assert result["probe"] == "runtime_lifecycle_claim_timeout_probe"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"][
        "latest_terminal_major_task_receipts_provider_model_accounted_percent"
    ] == 100.0
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1, "pending_execution": 1}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}
    assert result["artifact_id"] == ""

    with sqlite3.connect(db_path) as db:
        failed_receipt = db.execute(
            """
            SELECT receipt_id, side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'failed'
            """,
            ("run-claim-timeout-probe-test",),
        ).fetchone()
        idem_status, result_receipt_id = db.execute(
            """
            SELECT status, result_receipt_id
            FROM idempotency_records
            WHERE idempotency_key = ?
              AND side_effect_key = ?
            """,
            (
                "idem_run-claim-timeout-probe-test",
                "delegation_run:run-claim-timeout-probe-test:failed",
            ),
        ).fetchone()

    assert failed_receipt[1] == "delegation_run:run-claim-timeout-probe-test:failed"
    failed_payload = json.loads(failed_receipt[2])
    assert failed_payload["mission_id"] == "mission-claim-timeout-probe-test"
    assert failed_payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert failed_payload["provider_execution"] is False
    assert failed_payload["provider_model_applicability"] == "not_applicable"
    assert failed_payload["provider_model_truth_source"] == (
        "runtime_lifecycle.claim_timeout_no_provider_execution"
    )
    assert failed_payload["no_provider_model_reason"] == (
        "claim_timeout_before_worker_execution"
    )
    assert idem_status == "completed"
    assert result_receipt_id == failed_receipt[0]


def test_runtime_lifecycle_receipt_probe_claim_timeout_cli_text_handles_no_artifact(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe",
            "--producer",
            "runtime-lifecycle-claim-timeout",
            "--db",
            str(db_path),
            "--run-id",
            "run-claim-timeout-cli-test",
            "--task-id",
            "task-claim-timeout-cli-test",
            "--claim-id",
            "claim-claim-timeout-cli-test",
            "--trace-id",
            "trace-claim-timeout-cli-test",
            "--correlation-id",
            "corr-claim-timeout-cli-test",
            "--session-id",
            "sess-claim-timeout-cli-test",
        ],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RUNTIME_LIFECYCLE_CLAIM_TIMEOUT_PROBE" in captured.out
    assert "70->75 gate:   PASS" in captured.out
    assert "Payload:" not in captured.out


def test_runtime_lifecycle_receipt_probe_can_exercise_long_timeout(tmp_path):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"

    result = asyncio.run(
        mod.run_runtime_lifecycle_long_timeout_probe(
            db_path,
            ledger_dir=tmp_path / "ledgers",
            mission_id="mission-long-timeout-probe-test",
            run_id="run-long-timeout-probe-test",
            task_id="task-long-timeout-probe-test",
            claim_id="claim-long-timeout-probe-test",
            trace_id="trace-long-timeout-probe-test",
            correlation_id="corr-long-timeout-probe-test",
            session_id="sess-long-timeout-probe-test",
        )
    )

    assert result["probe"] == "runtime_lifecycle_long_timeout_probe"
    assert result["coverage"]["summary"]["score_gate_70_to_75"] is True
    assert result["coverage"]["summary"]["provider_model_accounted_complete"] is False
    assert result["coverage"]["summary"]["production_readiness_blockers"] == [
        "latest major task receipts do not all carry provider/model payloads",
        "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata",
    ]
    assert result["coverage"]["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"missing": 1, "pending_execution": 1}
    assert result["coverage"]["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}
    assert result["artifact_id"] == ""

    with sqlite3.connect(db_path) as db:
        failed_receipt = db.execute(
            """
            SELECT receipt_id, side_effect_key, payload_json
            FROM runtime_receipts
            WHERE run_id = ?
              AND receipt_type = 'delegation_run'
              AND status = 'failed'
            """,
            ("run-long-timeout-probe-test",),
        ).fetchone()
        idem_status, result_receipt_id = db.execute(
            """
            SELECT status, result_receipt_id
            FROM idempotency_records
            WHERE idempotency_key = ?
              AND side_effect_key = ?
            """,
            (
                "idem_run-long-timeout-probe-test",
                "delegation_run:run-long-timeout-probe-test:failed",
            ),
        ).fetchone()

    assert failed_receipt[1] == "delegation_run:run-long-timeout-probe-test:failed"
    failed_payload = json.loads(failed_receipt[2])
    assert failed_payload["mission_id"] == "mission-long-timeout-probe-test"
    assert failed_payload["failure_code"] == "long_timeout"
    assert failed_payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert failed_payload["provider_execution"] is True
    assert failed_payload["provider_model_applicability"] == "actual_served_unproven"
    assert failed_payload["provider_model_truth_source"] == (
        "runtime_lifecycle.provider_execution_unproven"
    )
    assert failed_payload["provider_model_missing_reason"] == (
        "terminal_receipt_missing_actual_served_or_no_provider_evidence"
    )
    assert idem_status == "completed"
    assert result_receipt_id == failed_receipt[0]


def test_runtime_lifecycle_receipt_probe_long_timeout_cli_text_handles_no_artifact(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe",
            "--producer",
            "runtime-lifecycle-long-timeout",
            "--db",
            str(db_path),
            "--run-id",
            "run-long-timeout-cli-test",
            "--task-id",
            "task-long-timeout-cli-test",
            "--claim-id",
            "claim-long-timeout-cli-test",
            "--trace-id",
            "trace-long-timeout-cli-test",
            "--correlation-id",
            "corr-long-timeout-cli-test",
            "--session-id",
            "sess-long-timeout-cli-test",
        ],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RUNTIME_LIFECYCLE_LONG_TIMEOUT_PROBE" in captured.out
    assert "70->75 gate:   PASS" in captured.out
    assert "Payload:" not in captured.out


def test_runtime_lifecycle_receipt_probe_cli_passes_no_provider_execution(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = _load_probe_module()
    db_path = tmp_path / "state" / "runtime.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe",
            "--db",
            str(db_path),
            "--run-id",
            "run-no-provider-cli-test",
            "--task-id",
            "task-no-provider-cli-test",
            "--claim-id",
            "claim-no-provider-cli-test",
            "--trace-id",
            "trace-no-provider-cli-test",
            "--correlation-id",
            "corr-no-provider-cli-test",
            "--session-id",
            "sess-no-provider-cli-test",
            "--no-provider-execution",
            "--no-provider-model-reason",
            "cli_no_provider_execution",
            "--json",
        ],
    )

    exit_code = mod.main()

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["provider_execution"] is False
    assert result["provider_model_truth_source"] == "runtime_control.no_provider_execution"
    assert result["no_provider_model_reason"] == "cli_no_provider_execution"
    assert result["coverage"]["summary"]["production_readiness_blockers"] == []


def test_runtime_lifecycle_receipt_probe_requires_live_opt_in(tmp_path, monkeypatch, capsys):
    mod = _load_probe_module()
    live_db = tmp_path / "live" / "runtime.db"
    monkeypatch.setattr(mod, "LIVE_RUNTIME_DB", live_db)
    monkeypatch.setattr(sys, "argv", ["probe", "--db", str(live_db)])

    exit_code = mod.main()

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "refusing to write live runtime.db without --allow-live" in captured.err
    assert not live_db.exists()
