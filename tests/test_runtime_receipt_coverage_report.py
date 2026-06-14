from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def _load_report_module():
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


def _init_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE delegation_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL,
                claim_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                assigned_by TEXT NOT NULL DEFAULT '',
                assigned_to TEXT NOT NULL DEFAULT '',
                requested_output_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                current_artifact_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT,
                failure_code TEXT NOT NULL DEFAULT '',
                receipt_json TEXT
            );
            CREATE TABLE runtime_receipts (
                receipt_id TEXT PRIMARY KEY,
                receipt_type TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                causation_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                side_effect_key TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE idempotency_records (
                idempotency_key TEXT NOT NULL,
                side_effect_key TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                result_receipt_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (idempotency_key, side_effect_key)
            );
            CREATE TABLE execution_identities (run_id TEXT PRIMARY KEY);
            CREATE TABLE task_claims (
                claim_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                claimed_at TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE artifact_records (
                artifact_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT ''
            );
            """
        )


def test_receipt_coverage_report_passes_complete_fixture(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-1",
                "task-1",
                '{"mission_id":"mission-1"}',
                "artifact-1",
                '{"receipt_id":"rr-1"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-1",
                "a2a_task",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "agent-1",
                "idem-1",
                "side-1",
                "completed",
                (
                    '{"mission_id":"mission-1","artifact_refs":["artifact-1"],'
                    '"actual_served_provider":"openrouter",'
                    '"actual_served_model":"qwen3-coder-live",'
                    '"provider_model_truth_source":"runtime_provider.actual_served"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-1",
                "side-1",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "completed",
                "rr-1",
                "2026-06-14T00:00:00Z",
                "2026-06-14T00:00:01Z",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-1", "run-1", "task-1"),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert [item["status"] for item in report["summary"]["gate_70_to_75_components"]] == [
        "pass",
        "pass",
        "pass",
        "pass",
        "pass",
    ]
    assert [item["short_label"] for item in report["gate_70_to_75_components"]] == [
        "core",
        "idempotency",
        "mission",
        "artifact",
        "active_head",
    ]
    assert report["summary"]["blockers"] == []
    assert report["summary"]["production_readiness_blockers"] == []
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 100.0
    assert report["summary"]["latest_major_task_receipts_provider_model_provenance_percent"] == 100.0
    assert report["summary"]["provider_model_coverage_complete"] is True
    assert report["summary"]["provider_model_provenance_complete"] is True
    assert report["major_task_receipts"]["with_matching_idempotency_record"] == 1
    assert report["major_task_receipts"]["latest_with_provider_model_payload"] == 1
    assert report["major_task_receipts"]["latest_with_provider_model_provenance"] == 1
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "served_field": 1
    }
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == []
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == []
    assert report["major_task_receipts"]["type_breakdown"] == [
        {
            "receipt_type": "a2a_task",
            "total": 1,
            "with_idempotency_fields": 1,
            "with_matching_idempotency_record": 1,
            "with_artifact_record": 1,
            "idempotency_gap": 0,
            "artifact_record_gap": 0,
        }
    ]
    assert report["major_task_receipts"]["field_gap_producer_groups"] == []
    assert report["major_task_receipts"]["top_missing_side_effect_groups"] == []


def test_receipt_coverage_report_counts_ds_goal_preflight_payload(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    preflight = {
        "schema_version": "dharma.ds_goal_longrun_preflight.v1",
        "read_only": True,
        "passed": False,
        "status": "blocked_unpinned_default_target",
        "default_target_repo": "/Users/dhyana/dharma_swarm_main",
        "repo_pin_source": "none",
        "score_effect": "no_score_movement_preflight_only",
    }
    payload = {
        "mission_id": "mission-ds-goal",
        "receipt_status": "completed",
        "provider_execution": False,
        "provider_model_truth_source": "runtime_control.no_provider_execution",
        "no_provider_model_reason": "living_agent_kernel_v1_no_provider_execution",
        "ds_goal_longrun_preflight": preflight,
    }
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-ds-goal-preflight",
                "delegation_run",
                "run_ds_goal_preflight",
                "task-ds-goal",
                "trace-ds-goal",
                "corr-ds-goal",
                "codex_composer",
                "idem-ds-goal",
                "delegation_run:run_ds_goal_preflight:completed",
                "completed",
                json.dumps(payload),
                "2026-06-14T00:00:01Z",
            ),
        )

    report = mod.build_report(db_path)

    assert report["major_task_receipts"]["latest_with_ds_goal_preflight_payload"] == 1
    assert report["major_task_receipts"][
        "latest_ds_goal_preflight_status_breakdown"
    ] == {
        "blocked_unpinned_default_target": 1,
    }
    assert report["major_task_receipts"]["latest_ds_goal_preflight_sample"] == [
        {
            "receipt_id": "rr-ds-goal-preflight",
            "receipt_type": "delegation_run",
            "run_id": "run_ds_goal_preflight",
            "task_id": "task-ds-goal",
            "preflight_status": "blocked_unpinned_default_target",
            "preflight_passed": False,
            "default_target_repo": "/Users/dhyana/dharma_swarm_main",
            "repo_pin_source": "none",
            "score_effect": "no_score_movement_preflight_only",
        }
    ]


def test_receipt_coverage_report_groups_major_field_gaps_by_producer(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        rows = [
            (
                "rr-ds-goal",
                "delegation_run",
                "run_ds_goal_field_gap",
                "task-ds-goal",
                "codex_composer",
                "",
                "",
                "{}",
                "2026-06-14T00:00:00Z",
            ),
            (
                "rr-orchestrator",
                "delegation_run",
                "run-orchestrator",
                "task-orchestrator",
                "agent-orchestrator",
                "idem-orchestrator",
                "side-orchestrator",
                (
                    '{"mission_id":"mission-orchestrator",'
                    '"source":"orchestrator",'
                    '"failure_code":"execution_error",'
                    '"topology":"fan_out"}'
                ),
                "2026-06-14T00:00:01Z",
            ),
        ]
        for (
            receipt_id,
            receipt_type,
            run_id,
            task_id,
            agent_id,
            idempotency_key,
            side_effect_key,
            payload,
            created_at,
        ) in rows:
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    receipt_type,
                    run_id,
                    task_id,
                    "trace-" + receipt_id,
                    "corr-" + receipt_id,
                    agent_id,
                    idempotency_key,
                    side_effect_key,
                    "completed",
                    payload,
                    created_at,
                ),
            )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-orchestrator",
                "side-orchestrator",
                "run-orchestrator",
                "task-orchestrator",
                "trace-rr-orchestrator",
                "corr-rr-orchestrator",
                "completed",
                "rr-orchestrator",
                "2026-06-14T00:00:01Z",
                "2026-06-14T00:00:02Z",
            ),
        )

    report = mod.build_report(db_path)
    groups = report["major_task_receipts"]["field_gap_producer_groups"]

    assert {
        (
            row["gap_type"],
            row["receipt_type"],
            row["producer_source"],
            row["producer_failure_code"],
            row["topology"],
            row["missing"],
        )
        for row in groups
    } == {
        (
            "artifact_evidence",
            "delegation_run",
            "ds_goal_cli",
            "sync_receipt_side_effect_key_missing",
            "cli_goal_run",
            1,
        ),
        (
            "idempotency_record",
            "delegation_run",
            "ds_goal_cli",
            "sync_receipt_side_effect_key_missing",
            "cli_goal_run",
            1,
        ),
        (
            "mission_payload",
            "delegation_run",
            "ds_goal_cli",
            "sync_receipt_side_effect_key_missing",
            "cli_goal_run",
            1,
        ),
        (
            "artifact_evidence",
            "delegation_run",
            "orchestrator",
            "execution_error",
            "fan_out",
            1,
        ),
    }
    ds_goal_groups = [
        row for row in groups if row["producer_source"] == "ds_goal_cli"
    ]
    assert ds_goal_groups
    assert {
        row["freshness_class"] for row in ds_goal_groups
    } == {"active_head_60m"}
    assert {row["age_minutes_from_head"] for row in ds_goal_groups} == {0}
    assert {
        row["recommended_action"] for row in ds_goal_groups
    } == {"repair_installed_ds_goal_wrapper_or_pin_invocations"}
    orchestrator_group = next(
        row
        for row in groups
        if row["producer_source"] == "orchestrator"
        and row["gap_type"] == "artifact_evidence"
    )
    assert orchestrator_group["freshness_class"] == "active_head_60m"
    assert orchestrator_group["recommended_action"] == (
        "repair_or_quarantine_orchestrator_error_receipts"
    )
    summary = report["major_task_receipts"]["field_gap_summary"]
    assert summary["group_count"] == 4
    assert summary["total_missing"] == 4
    assert summary["active_head_missing"] == 4
    assert summary["recent_historical_missing"] == 0
    assert summary["older_historical_missing"] == 0
    assert summary["quarantine_candidate_missing"] == 1
    assert summary["by_freshness_class"] == {"active_head_60m": 4}
    assert summary["by_gap_type"] == {
        "artifact_evidence": 2,
        "idempotency_record": 1,
        "mission_payload": 1,
    }
    assert summary["by_recommended_action"] == {
        "repair_installed_ds_goal_wrapper_or_pin_invocations": 3,
        "repair_or_quarantine_orchestrator_error_receipts": 1,
    }
    assert summary["by_producer_source"] == {
        "ds_goal_cli": 3,
        "orchestrator": 1,
    }
    queue = report["major_task_receipts"]["field_gap_action_queue"]
    assert [item["short_label"] for item in queue] == [
        "ds_goal_wrapper",
        "orchestrator_error",
    ]
    assert queue[0]["action"] == "repair_installed_ds_goal_wrapper_or_pin_invocations"
    assert queue[0]["owner_surface"] == "cli.ds_goal"
    assert queue[0]["missing"] == 3
    assert queue[0]["active_head_missing"] == 3
    assert queue[0]["operator_decision_required"] is True
    assert queue[0]["top_group"]["producer_source"] == "ds_goal_cli"
    assert queue[1]["action"] == "repair_or_quarantine_orchestrator_error_receipts"
    assert queue[1]["missing"] == 1
    assert queue[1]["required_evidence"]


def test_receipt_coverage_report_action_queue_marks_fresh_proof_without_score_motion():
    mod = _load_report_module()
    action_statuses = {
        "repair_installed_ds_goal_wrapper_or_pin_invocations": (
            "pin_mitigation_and_fail_closed_prevention_recorded_default_still_broken"
        ),
        "repair_or_quarantine_orchestrator_error_receipts": "fresh_scoped_proof_recorded",
        "inspect_orchestrator_fanout_success_receipt_fields": (
            "fresh_scoped_proof_recorded"
        ),
        "quarantine_fixture_debt_or_exclude_from_production_gate": (
            "candidate_policy_recorded_not_applied"
        ),
        "prove_fresh_dropoff_clean_then_quarantine_historical_debt": (
            "fresh_scoped_proof_recorded"
        ),
        "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt": (
            "fresh_scoped_proof_recorded"
        ),
        "prove_fresh_long_timeout_clean_then_quarantine_historical_debt": (
            "fresh_scoped_proof_recorded"
        ),
    }
    groups = [
        {
            "recommended_action": action,
            "missing": index + 1,
            "freshness_class": "older_historical",
            "gap_type": "idempotency_record",
            "receipt_type": "delegation_run",
            "producer_source": "orchestrator",
            "producer_failure_code": "<none>",
            "topology": "fan_out",
            "identifier_shape": "ordinary",
            "latest_created_at": "2026-06-14T00:00:00Z",
            "sample_agent_id": f"agent-{index}",
            "sample_task_id": f"task-{index}",
        }
        for index, action in enumerate(action_statuses)
    ]

    queue = mod._field_gap_action_queue(groups)
    by_action = {row["action"]: row for row in queue}

    assert set(by_action) == set(action_statuses)
    for action, expected_status in action_statuses.items():
        row = by_action[action]
        assert row["missing"] == list(action_statuses).index(action) + 1
        assert row["score_effect"] == "no_score_change_until_required_evidence_passes"
        assert row["fresh_proof"]["status"] == expected_status
        assert row["fresh_proof"]["proof_run_id"]
        assert row["fresh_proof"]["remaining_action"]
        assert (
            row["fresh_proof"]["score_effect"]
            == "no_score_change_until_global_gate_passes"
        )
    ds_goal_proof = by_action[
        "repair_installed_ds_goal_wrapper_or_pin_invocations"
    ]["fresh_proof"]
    assert ds_goal_proof["prevention_receipt_root"].endswith(
        "ds-goal-preflight-block-proof-20260614T2245JST/state"
    )
    assert "valid_preflight_block=1" in ds_goal_proof["prevention_evidence"]


def test_receipt_coverage_report_keeps_fixture_quarantine_candidate_out_of_score(
    tmp_path,
    capsys,
):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, assigned_to, status,"
            " failure_code, metadata_json, started_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-fixture-gap",
                "sess-fixture-gap",
                "t-ready",
                "a1",
                "failed",
                "dispatch_dropoff",
                '{"source":"orchestrator","topology":"fan_out"}',
                "2026-06-14T00:00:00+00:00",
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-fixture-gap",
                "delegation_run",
                "run-fixture-gap",
                "t-ready",
                "trace-fixture-gap",
                "corr-fixture-gap",
                "a1",
                "",
                "",
                "failed",
                "{}",
                "2026-06-14T00:00:00+00:00",
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-clean-anchor",
                "delegation_run",
                "run-clean-anchor",
                "task-clean-anchor",
                "trace-clean-anchor",
                "corr-clean-anchor",
                "agent-clean-anchor",
                "idem-clean-anchor",
                "side-clean-anchor",
                "completed",
                (
                    '{"mission_id":"mission-clean-anchor",'
                    '"artifact_refs":["artifact-clean-anchor"],'
                    '"actual_served_provider":"openrouter",'
                    '"actual_served_model":"qwen3-coder-live",'
                    '"provider_model_truth_source":"runtime_provider.actual_served"}'
                ),
                "2026-06-14T02:00:00+00:00",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-clean-anchor",
                "side-clean-anchor",
                "run-clean-anchor",
                "task-clean-anchor",
                "trace-clean-anchor",
                "corr-clean-anchor",
                "completed",
                "rr-clean-anchor",
                "2026-06-14T02:00:00+00:00",
                "2026-06-14T02:00:01+00:00",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-clean-anchor", "run-clean-anchor", "task-clean-anchor"),
        )

    report = mod.build_report(db_path)
    policy = report["major_task_receipts"]["fixture_quarantine_policy"]

    assert report["summary"]["score_gate_70_to_75"] is False
    assert policy["status"] == "candidate_not_applied"
    assert policy["applies_to_score_gate"] is False
    assert policy["candidate_missing"] == 3
    assert policy["candidate_group_count"] == 3
    assert policy["active_head_missing"] == 0
    assert policy["recent_historical_missing"] == 3
    assert policy["eligible_after_operator_decision"] is True
    assert policy["operator_decision_required"] is True
    assert policy["owner_surface"] == "test_fixtures"
    assert policy["test_runtime_db_isolation"]["enforced"] is True
    assert "fixture-shaped debt is only a candidate and is not excluded" in policy["blockers"]

    queue = report["major_task_receipts"]["field_gap_action_queue"]
    assert [item["short_label"] for item in queue] == ["fixture_quarantine"]
    assert queue[0]["score_effect"] == "no_score_change_until_required_evidence_passes"

    mod._print_text(report)
    output = capsys.readouterr().out
    assert "Fixture quarantine policy:" in output
    assert "applies_to_score_gate=false" in output
    assert "test_isolation_enforced=true" in output
    assert "fresh_proof=status=candidate_policy_recorded_not_applied" in output


def test_receipt_coverage_report_assigns_claim_timeout_owner_action(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-claim-timeout",
                "delegation_run",
                "run-claim-timeout",
                "task-claim-timeout",
                "trace-claim-timeout",
                "corr-claim-timeout",
                "agent-claim-timeout",
                "failed",
                (
                    '{"source":"orchestrator","failure_code":"claim_timeout",'
                    '"topology":"fan_out"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )

    report = mod.build_report(db_path)
    queue = report["major_task_receipts"]["field_gap_action_queue"]

    assert len(queue) == 1
    assert queue[0]["action"] == (
        "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt"
    )
    assert queue[0]["short_label"] == "claim_timeout_proof"
    assert queue[0]["owner_surface"] == "orchestrator.claim_timeout"
    assert queue[0]["missing"] == 3
    assert queue[0]["active_head_missing"] == 3
    assert queue[0]["operator_decision_required"] is True
    assert queue[0]["top_group"]["producer_failure_code"] == "claim_timeout"
    assert (
        "fresh claim_timeout proof carries idempotency, mission, and no-artifact truth"
        in queue[0]["required_evidence"]
    )
    assert report["major_task_receipts"]["field_gap_summary"][
        "by_recommended_action"
    ] == {
        "prove_fresh_claim_timeout_clean_then_quarantine_historical_debt": 3
    }


def test_receipt_coverage_report_assigns_long_timeout_owner_action(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-long-timeout",
                "delegation_run",
                "run-long-timeout",
                "task-long-timeout",
                "trace-long-timeout",
                "corr-long-timeout",
                "agent-long-timeout",
                "failed",
                (
                    '{"source":"orchestrator","failure_code":"long_timeout",'
                    '"topology":"fan_out"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )

    report = mod.build_report(db_path)
    queue = report["major_task_receipts"]["field_gap_action_queue"]

    assert len(queue) == 1
    assert queue[0]["action"] == (
        "prove_fresh_long_timeout_clean_then_quarantine_historical_debt"
    )
    assert queue[0]["short_label"] == "long_timeout_proof"
    assert queue[0]["owner_surface"] == "orchestrator.long_timeout"
    assert queue[0]["missing"] == 3
    assert queue[0]["operator_decision_required"] is True
    assert queue[0]["top_group"]["producer_failure_code"] == "long_timeout"
    assert (
        "fresh long_timeout proof carries idempotency, mission, and no-artifact truth"
        in queue[0]["required_evidence"]
    )
    assert report["major_task_receipts"]["field_gap_summary"][
        "by_recommended_action"
    ] == {
        "prove_fresh_long_timeout_clean_then_quarantine_historical_debt": 3
    }


def test_receipt_coverage_report_separates_running_provider_model_pending(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-terminal",
                "task-terminal",
                '{"mission_id":"mission-terminal"}',
                "artifact-terminal",
                '{"receipt_id":"rr-terminal"}',
            ),
        )
        rows = [
            (
                "rr-running",
                "running",
                "idem-running",
                "side-running",
                '{"mission_id":"mission-terminal","artifact_refs":["artifact-terminal"]}',
                "2026-06-14T00:00:00Z",
            ),
            (
                "rr-terminal",
                "completed",
                "idem-terminal",
                "side-terminal",
                (
                    '{"mission_id":"mission-terminal","artifact_refs":["artifact-terminal"],'
                    '"actual_served_provider":"openrouter",'
                    '"actual_served_model":"qwen3-coder-live",'
                    '"provider_model_truth_source":"runtime_provider.actual_served"}'
                ),
                "2026-06-14T00:00:01Z",
            ),
        ]
        for receipt_id, status, idempotency_key, side_effect_key, payload, created_at in rows:
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    "delegation_run",
                    "run-terminal",
                    "task-terminal",
                    "trace-terminal",
                    "corr-terminal",
                    "agent-terminal",
                    idempotency_key,
                    side_effect_key,
                    status,
                    payload,
                    created_at,
                ),
            )
            db.execute(
                "INSERT INTO idempotency_records"
                " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
                " correlation_id, status, result_receipt_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    idempotency_key,
                    side_effect_key,
                    "run-terminal",
                    "task-terminal",
                    "trace-terminal",
                    "corr-terminal",
                    "completed",
                    receipt_id,
                    created_at,
                    "2026-06-14T00:00:02Z",
                ),
            )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-terminal", "run-terminal", "task-terminal"),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 50.0
    assert (
        report["summary"]["latest_major_task_receipts_provider_model_provenance_percent"]
        == 50.0
    )
    assert report["summary"]["latest_major_task_receipts_pending_execution"] == 1
    assert report["summary"]["latest_terminal_major_task_receipts_total"] == 1
    assert (
        report["summary"]["latest_terminal_major_task_receipts_provider_model_percent"]
        == 100.0
    )
    assert (
        report["summary"][
            "latest_terminal_major_task_receipts_provider_model_provenance_percent"
        ]
        == 100.0
    )
    assert report["summary"]["terminal_provider_model_coverage_complete"] is True
    assert report["summary"]["terminal_provider_model_provenance_complete"] is True
    assert report["major_task_receipts"]["latest_terminal_with_provider_model_payload"] == 1
    assert report["major_task_receipts"]["latest_terminal_with_provider_model_provenance"] == 1
    assert report["major_task_receipts"]["latest_major_status_breakdown"] == {
        "completed": 1,
        "running": 1,
    }
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "pending_execution": 1,
        "served_field": 1,
    }
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == [
        {
            "receipt_id": "rr-running",
            "receipt_type": "delegation_run",
            "run_id": "run-terminal",
            "task_id": "task-terminal",
            "agent_id": "agent-terminal",
            "created_at": "2026-06-14T00:00:00Z",
            "provider_model_payload_class": "pending_execution",
            "provider_model_truth_source": "<pending>",
            "has_provider_payload": False,
            "has_model_payload": False,
        }
    ]
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == [
        {
            "receipt_type": "delegation_run",
            "provider_model_payload_class": "pending_execution",
            "provider_model_truth_source": "<pending>",
            "producer_source": "<unknown>",
            "producer_failure_code": "<none>",
            "topology": "<blank>",
            "missing_provider_model_provenance": 1,
            "latest_created_at": "2026-06-14T00:00:00Z",
            "sample_agent_id": "agent-terminal",
            "sample_task_id": "task-terminal",
            "sample_run_id": "run-terminal",
        }
    ]
    assert report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"served_field": 1}
    assert report["major_task_receipts"]["latest_terminal_provider_model_unproven_sample"] == []
    assert (
        report["major_task_receipts"]["latest_terminal_provider_model_unproven_producer_groups"]
        == []
    )


def test_receipt_coverage_report_blocks_probe_selected_provider_model_production_claim(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-probe",
                "task-probe",
                '{"mission_id":"mission-probe"}',
                "artifact-probe",
                '{"receipt_id":"rr-probe"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-probe",
                "delegation_run",
                "run-probe",
                "task-probe",
                "trace-probe",
                "corr-probe",
                "agent-probe",
                "idem-probe",
                "side-probe",
                "completed",
                (
                    '{"mission_id":"mission-probe","artifact_refs":["artifact-probe"],'
                    '"selected_provider":"openrouter",'
                    '"selected_model":"qwen3-coder-live",'
                    '"provider_model_truth_source":'
                    '"runtime_lifecycle_receipt_probe.selected_metadata"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-probe",
                "side-probe",
                "run-probe",
                "task-probe",
                "trace-probe",
                "corr-probe",
                "completed",
                "rr-probe",
                "2026-06-14T00:00:00Z",
                "2026-06-14T00:00:01Z",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-probe", "run-probe", "task-probe"),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert report["summary"]["blockers"] == []
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 100.0
    assert report["summary"]["latest_major_task_receipts_provider_model_provenance_percent"] == 0.0
    assert report["summary"]["provider_model_coverage_complete"] is True
    assert report["summary"]["provider_model_provenance_complete"] is False
    assert report["summary"]["production_readiness_blockers"] == [
        "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata"
    ]
    assert report["major_task_receipts"]["latest_with_provider_model_payload"] == 1
    assert report["major_task_receipts"]["latest_with_provider_model_provenance"] == 0
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "probe_selected": 1
    }
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == [
        {
            "receipt_id": "rr-probe",
            "receipt_type": "delegation_run",
            "run_id": "run-probe",
            "task_id": "task-probe",
            "agent_id": "agent-probe",
            "created_at": "2026-06-14T00:00:00Z",
            "provider_model_payload_class": "probe_selected",
            "provider_model_truth_source": (
                "runtime_lifecycle_receipt_probe.selected_metadata"
            ),
            "has_provider_payload": True,
            "has_model_payload": True,
        }
    ]
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == [
        {
            "receipt_type": "delegation_run",
            "provider_model_payload_class": "probe_selected",
            "provider_model_truth_source": (
                "runtime_lifecycle_receipt_probe.selected_metadata"
            ),
            "producer_source": "<unknown>",
            "producer_failure_code": "<none>",
            "topology": "<blank>",
            "missing_provider_model_provenance": 1,
            "latest_created_at": "2026-06-14T00:00:00Z",
            "sample_agent_id": "agent-probe",
            "sample_task_id": "task-probe",
            "sample_run_id": "run-probe",
        }
    ]


def test_receipt_coverage_report_labels_legacy_unmarked_probe_provider_model_debt(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-legacy-probe",
                "task-legacy-probe",
                '{"mission_id":"runtime-spine-provider-model-proof-2026-06-14"}',
                "artifact-legacy-probe",
                '{"receipt_id":"rr-legacy-probe"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-legacy-probe",
                "delegation_run",
                "run-legacy-probe",
                "task-legacy-probe",
                "trace-legacy-probe",
                "corr-legacy-probe",
                "runtime-spine-hardening-probe",
                "idem-legacy-probe",
                "side-legacy-probe",
                "completed",
                (
                    '{"mission_id":"runtime-spine-provider-model-proof-2026-06-14",'
                    '"artifact_refs":["artifact-legacy-probe"],'
                    '"provider":"runtime-spine-proof-provider",'
                    '"model":"runtime-spine-proof-model-v1",'
                    '"selected_provider":"runtime-spine-proof-provider",'
                    '"selected_model":"runtime-spine-proof-model-v1"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-legacy-probe",
                "side-legacy-probe",
                "run-legacy-probe",
                "task-legacy-probe",
                "trace-legacy-probe",
                "corr-legacy-probe",
                "completed",
                "rr-legacy-probe",
                "2026-06-14T00:00:00Z",
                "2026-06-14T00:00:01Z",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-legacy-probe", "run-legacy-probe", "task-legacy-probe"),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 100.0
    assert report["summary"][
        "latest_major_task_receipts_provider_model_provenance_percent"
    ] == 0.0
    assert report["summary"]["provider_model_coverage_complete"] is True
    assert report["summary"]["provider_model_provenance_complete"] is False
    assert report["summary"]["production_readiness_blockers"] == [
        "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata"
    ]
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "legacy_probe_selected_unmarked": 1
    }
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == [
        {
            "receipt_id": "rr-legacy-probe",
            "receipt_type": "delegation_run",
            "run_id": "run-legacy-probe",
            "task_id": "task-legacy-probe",
            "agent_id": "runtime-spine-hardening-probe",
            "created_at": "2026-06-14T00:00:00Z",
            "provider_model_payload_class": "legacy_probe_selected_unmarked",
            "provider_model_truth_source": "",
            "has_provider_payload": True,
            "has_model_payload": True,
        }
    ]


def test_receipt_coverage_report_accounts_for_explicit_no_provider_execution(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-kernel",
                "task-kernel",
                '{"mission_id":"mission-kernel"}',
                "artifact-kernel",
                '{"receipt_id":"rr-kernel"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-kernel",
                "delegation_run",
                "run-kernel",
                "task-kernel",
                "trace-kernel",
                "corr-kernel",
                "agent-kernel",
                "idem-kernel",
                "side-kernel",
                "completed",
                (
                    '{"mission_id":"mission-kernel","artifact_refs":["artifact-kernel"],'
                    '"provider_execution":false,'
                    '"provider_model_truth_source":"runtime_control.no_provider_execution",'
                    '"provider_model_applicability":"not_applicable",'
                    '"no_provider_model_reason":"living_agent_kernel_v1_no_provider_execution"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-kernel",
                "side-kernel",
                "run-kernel",
                "task-kernel",
                "trace-kernel",
                "corr-kernel",
                "completed",
                "rr-kernel",
                "2026-06-14T00:00:00Z",
                "2026-06-14T00:00:01Z",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-kernel", "run-kernel", "task-kernel"),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert report["summary"]["blockers"] == []
    assert report["summary"]["production_readiness_blockers"] == []
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 0.0
    assert (
        report["summary"]["latest_major_task_receipts_provider_model_provenance_percent"]
        == 100.0
    )
    assert (
        report["summary"]["latest_major_task_receipts_provider_model_accounted_percent"]
        == 100.0
    )
    assert report["summary"]["provider_model_coverage_complete"] is False
    assert report["summary"]["provider_model_provenance_complete"] is True
    assert report["summary"]["provider_model_accounted_complete"] is True
    assert report["major_task_receipts"]["latest_with_provider_model_payload"] == 0
    assert report["major_task_receipts"]["latest_with_provider_model_provenance"] == 1
    assert report["major_task_receipts"]["latest_with_provider_model_accounted"] == 1
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "no_provider_execution": 1
    }
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == []
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == []


def test_receipt_coverage_report_accounts_dispatch_dropoff_failure_code_as_no_provider_execution(
    tmp_path,
):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, status, failure_code)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-dropoff-history",
                "task-dropoff-history",
                (
                    '{"mission_id":"mission-dropoff-history",'
                    '"source":"orchestrator","failure_code":"dispatch_dropoff",'
                    '"topology":"fan_out"}'
                ),
                "failed",
                "dispatch_dropoff",
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-dropoff-history",
                "delegation_run",
                "run-dropoff-history",
                "task-dropoff-history",
                "trace-dropoff-history",
                "corr-dropoff-history",
                "agent-dropoff-history",
                "idem-dropoff-history",
                "delegation_run:run-dropoff-history:failed",
                "failed",
                (
                    '{"mission_id":"mission-dropoff-history",'
                    '"no_artifact_refs_reason":"delegation_run has no current_artifact_id",'
                    '"source":"orchestrator",'
                    '"failure_code":"dispatch_dropoff",'
                    '"topology":"fan_out"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-dropoff-history",
                "delegation_run:run-dropoff-history:failed",
                "run-dropoff-history",
                "task-dropoff-history",
                "trace-dropoff-history",
                "corr-dropoff-history",
                "completed",
                "rr-dropoff-history",
                "2026-06-14T00:00:00Z",
                "2026-06-14T00:00:01Z",
            ),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert report["summary"]["production_readiness_blockers"] == []
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 0.0
    assert (
        report["summary"]["latest_major_task_receipts_provider_model_provenance_percent"]
        == 100.0
    )
    assert (
        report["summary"]["latest_terminal_major_task_receipts_provider_model_accounted_percent"]
        == 100.0
    )
    assert report["summary"]["provider_model_accounted_complete"] is True
    assert report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert report["major_task_receipts"]["latest_with_provider_model_payload"] == 0
    assert report["major_task_receipts"]["latest_with_provider_model_provenance"] == 1
    assert report["major_task_receipts"]["latest_with_provider_model_accounted"] == 1
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "no_provider_execution": 1
    }
    assert report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == []
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == []


def test_receipt_coverage_report_accounts_ds_goal_kernel_wake_context_as_no_provider_execution(
    tmp_path,
):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, status, current_artifact_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run_ds_goal_kernelwake",
                "task-kernelwake",
                '{"mission_id":"mission-kernelwake"}',
                "completed",
                "artifact-kernelwake",
            ),
        )
        rows = [
            (
                "rr-warrant",
                "runtime_warrant",
                "granted",
                "idem-warrant",
                "side-warrant",
                '{"mission_id":"mission-kernelwake","action":"kernel_wake"}',
                "2026-06-14T00:00:00Z",
            ),
            (
                "rr-run",
                "delegation_run",
                "completed",
                "idem-run",
                "side-run",
                (
                    '{"mission_id":"mission-kernelwake",'
                    '"artifact_refs":["artifact-kernelwake"]}'
                ),
                "2026-06-14T00:00:01Z",
            ),
        ]
        for receipt_id, receipt_type, status, idempotency_key, side_effect_key, payload, created_at in rows:
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    receipt_type,
                    "run_ds_goal_kernelwake",
                    "task-kernelwake",
                    "trace-kernelwake",
                    "ds_goal:mission-kernelwake:task-kernelwake",
                    "agent-kernelwake",
                    idempotency_key,
                    side_effect_key,
                    status,
                    payload,
                    created_at,
                ),
            )
            db.execute(
                "INSERT INTO idempotency_records"
                " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
                " correlation_id, status, result_receipt_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    idempotency_key,
                    side_effect_key,
                    "run_ds_goal_kernelwake",
                    "task-kernelwake",
                    "trace-kernelwake",
                    "ds_goal:mission-kernelwake:task-kernelwake",
                    "completed",
                    receipt_id,
                    created_at,
                    "2026-06-14T00:00:02Z",
                ),
            )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-kernelwake", "run_ds_goal_kernelwake", "task-kernelwake"),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is True
    assert report["summary"]["production_readiness_blockers"] == []
    assert report["summary"]["latest_major_task_receipts_provider_model_percent"] == 0.0
    assert (
        report["summary"]["latest_major_task_receipts_provider_model_accounted_percent"]
        == 100.0
    )
    assert (
        report["summary"]["latest_terminal_major_task_receipts_provider_model_accounted_percent"]
        == 100.0
    )
    assert report["summary"]["provider_model_accounted_complete"] is True
    assert report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert report["major_task_receipts"]["latest_with_provider_model_payload"] == 0
    assert report["major_task_receipts"]["latest_with_provider_model_provenance"] == 1
    assert report["major_task_receipts"]["latest_with_provider_model_accounted"] == 1
    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "no_provider_execution": 1
    }
    assert report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == []
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == []


def test_receipt_coverage_report_keeps_ds_goal_owner_blockers_when_kernel_wake_is_accounted(
    tmp_path,
    monkeypatch,
):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    state_root = tmp_path / "state"
    census_receipt = state_root / "ops" / "live_process_census.json"
    census_receipt.parent.mkdir(parents=True)
    census_receipt.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": "2026-06-14T08:30:00Z",
                "surfaces": [
                    {
                        "id": "cli.ds_goal",
                        "label": "ds-goal runtime CLI",
                        "status": "live",
                        "proof_gaps": [
                            "ds_goal_cli_target_repo_mismatch",
                            "ds_goal_cli_target_lacks_sync_side_effect_hardening",
                        ],
                        "raw": {
                            "target_repo": "/Users/dhyana/dharma_swarm_main",
                            "target_resolution_source": (
                                "installed_wrapper_dharma_swarm_main_preference"
                            ),
                            "target_matches_current_repo": False,
                            "default_wrapper_target": {
                                "target_repo": "/Users/dhyana/dharma_swarm_main",
                                "target_resolution_source": (
                                    "installed_wrapper_dharma_swarm_main_preference"
                                ),
                            },
                            "installed_wrapper_contract": {
                                "wrapper_sha256": "abc123def4567890",
                                "dharma_swarm_repo_pin_supported": True,
                            },
                            "target_sync_receipt_hardening": {
                                "state": "sync_receipt_side_effect_keys_missing",
                            },
                            "convergence_decision_packet": {
                                "approval_state": "operator_approval_required",
                                "score_effect": (
                                    "no_score_movement_until_default_wrapper_or_"
                                    "target_is_converged_and_post_change_"
                                    "receipt_gate_evidence_passes"
                                ),
                                "operator_decision_options": [
                                    {
                                        "id": (
                                            "converge_installed_wrapper_default_"
                                            "to_audited_checkout"
                                        ),
                                    },
                                    {
                                        "id": "harden_current_default_target_checkout",
                                    },
                                    {
                                        "id": (
                                            "retain_default_with_mandatory_pin_"
                                            "or_quarantine"
                                        ),
                                    },
                                ],
                                "forbidden_without_operator_approval": [
                                    "edit_installed_wrapper",
                                    "patch_default_target_checkout",
                                    (
                                        "start_repo_native_longrun_from_unpinned_"
                                        "ds_goal"
                                    ),
                                    "declare_75_plus_from_pin_mitigation_only",
                                ],
                            },
                            "longrun_preflight_gate": {
                                "status": "blocked_unpinned_default_target",
                                "longrun_start_allowed": False,
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, metadata_json, status)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run_ds_goal_kernelwake_dirty",
                "ds_goal:mission-kernelwake-dirty",
                "task-kernelwake-dirty",
                '{"mission_id":"mission-kernelwake-dirty"}',
                "completed",
            ),
        )
        rows = [
            (
                "rr-warrant-dirty",
                "runtime_warrant",
                "granted",
                "idem-warrant-dirty",
                "side-warrant-dirty",
                '{"mission_id":"mission-kernelwake-dirty","action":"kernel_wake"}',
                "2026-06-14T00:00:00Z",
            ),
            (
                "rr-run-dirty",
                "delegation_run",
                "completed",
                "idem-run-dirty",
                "",
                '{"mission_id":"mission-kernelwake-dirty"}',
                "2026-06-14T00:00:01Z",
            ),
        ]
        for receipt_id, receipt_type, status, idempotency_key, side_effect_key, payload, created_at in rows:
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    receipt_type,
                    "run_ds_goal_kernelwake_dirty",
                    "task-kernelwake-dirty",
                    "trace-kernelwake-dirty",
                    "ds_goal:mission-kernelwake-dirty:task-kernelwake-dirty",
                    "agent-kernelwake-dirty",
                    idempotency_key,
                    side_effect_key,
                    status,
                    payload,
                    created_at,
                ),
            )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-warrant-dirty",
                "side-warrant-dirty",
                "run_ds_goal_kernelwake_dirty",
                "task-kernelwake-dirty",
                "trace-kernelwake-dirty",
                "ds_goal:mission-kernelwake-dirty:task-kernelwake-dirty",
                "completed",
                "rr-warrant-dirty",
                "2026-06-14T00:00:00Z",
                "2026-06-14T00:00:02Z",
            ),
        )

    report = mod.build_report(db_path)

    assert report["major_task_receipts"]["latest_provider_model_payload_class_breakdown"] == {
        "no_provider_execution": 1
    }
    assert report["runtime_surfaces"]["cli.ds_goal"]["status"] == "live"
    assert (
        "installed ds-goal wrapper default target does not match the audited checkout"
        in report["summary"]["production_readiness_blockers"]
    )
    assert (
        "installed ds-goal wrapper target lacks sync side-effect-key hardening"
        in report["summary"]["production_readiness_blockers"]
    )


def test_receipt_coverage_report_fails_missing_idempotency_and_payload_fields(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, metadata_json)"
            " VALUES (?, ?, ?)",
            ("run-1", "task-1", "{}"),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-1",
                "a2a_task",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "agent-1",
                "completed",
                "{}",
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-claim-1",
                "task_claim",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "agent-2",
                "claimed",
                "{}",
                "2026-06-14T00:00:01Z",
            ),
        )

    report = mod.build_report(db_path)

    assert report["summary"]["score_gate_70_to_75"] is False
    gate_components = {
        item["short_label"]: item
        for item in report["summary"]["gate_70_to_75_components"]
    }
    assert gate_components["core"]["status"] == "fail"
    assert gate_components["idempotency"]["status"] == "fail"
    assert gate_components["mission"]["status"] == "fail"
    assert gate_components["artifact"]["status"] == "fail"
    assert gate_components["active_head"]["status"] == "fail"
    assert "side_effect_key:2" in gate_components["core"]["evidence"]
    assert gate_components["idempotency"]["evidence"] == (
        "matching_idempotency=0/1; fields=0/1"
    )
    assert gate_components["active_head"]["scope"] == "strict_runtime_blocker"
    assert "major task receipts do not all join to idempotency_records" in report["summary"]["blockers"]
    assert "latest major task receipts do not all carry mission_id-like payloads" in report["summary"]["blockers"]
    assert (
        "latest major task receipts do not all carry provider/model payloads"
        in report["summary"]["production_readiness_blockers"]
    )
    assert report["summary"]["provider_model_coverage_complete"] is False
    assert report["runtime_receipts"]["side_effect_key_gap_by_type"] == [
        {
            "receipt_type": "a2a_task",
            "total": 1,
            "missing_side_effect_key": 1,
        },
        {
            "receipt_type": "task_claim",
            "total": 1,
            "missing_side_effect_key": 1,
        },
    ]
    assert report["runtime_receipts"]["latest_side_effect_key_gap_sample"] == [
        {
            "receipt_id": "rr-claim-1",
            "receipt_type": "task_claim",
            "run_id": "run-1",
            "task_id": "task-1",
            "agent_id": "agent-2",
            "status": "claimed",
            "created_at": "2026-06-14T00:00:01Z",
        },
        {
            "receipt_id": "rr-1",
            "receipt_type": "a2a_task",
            "run_id": "run-1",
            "task_id": "task-1",
            "agent_id": "agent-1",
            "status": "completed",
            "created_at": "2026-06-14T00:00:00Z",
        },
    ]
    assert report["major_task_receipts"]["type_breakdown"] == [
        {
            "receipt_type": "a2a_task",
            "total": 1,
            "with_idempotency_fields": 0,
            "with_matching_idempotency_record": 0,
            "with_artifact_record": 0,
            "idempotency_gap": 1,
            "artifact_record_gap": 1,
        }
    ]
    assert report["major_task_receipts"]["top_missing_side_effect_groups"] == [
        {
            "receipt_type": "a2a_task",
            "agent_id": "agent-1",
            "total": 1,
            "missing_side_effect_key": 1,
        }
    ]


def test_receipt_coverage_report_diagnoses_latest_side_effect_gap_producer(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, claim_id, assigned_to, status,"
            " failure_code, metadata_json, started_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-live-gap",
                "sess-tick",
                "t1",
                "claim-1",
                "a1",
                "failed",
                "dispatch_dropoff",
                (
                    '{"source":"orchestrator","failure_code":"dispatch_dropoff",'
                    '"error":"Dispatch accepted but worker unavailable",'
                    '"runtime_db_path":"/Users/dhyana/.dharma/state/runtime.db",'
                    '"topology":"fan_out"}'
                ),
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO task_claims"
            " (claim_id, task_id, session_id, agent_id, status, claimed_at,"
            " metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "claim-1",
                "t1",
                "sess-tick",
                "a1",
                "claimed",
                "2026-06-14T00:00:01Z",
                '{"source":"runtime_lifecycle"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, status, payload_json,"
            " created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-gap",
                "delegation_run",
                "run-live-gap",
                "t1",
                "trace-1",
                "corr-1",
                "a1",
                "idem-1",
                "failed",
                "{}",
                "2026-06-14T00:00:02Z",
            ),
        )

    report = mod.build_report(db_path)

    assert report["runtime_receipts"]["latest_side_effect_key_gap_diagnostics"] == [
        {
            "receipt_id": "rr-gap",
            "receipt_type": "delegation_run",
            "run_id": "run-live-gap",
            "task_id": "t1",
            "agent_id": "a1",
            "status": "failed",
            "created_at": "2026-06-14T00:00:02Z",
            "delegation_status": "failed",
            "delegation_failure_code": "dispatch_dropoff",
            "task_claim_status": "claimed",
            "identifier_shape": "fixture_shaped",
            "session_id": "sess-tick",
            "claim_id": "claim-1",
            "producer_source": "orchestrator",
            "producer_failure_code": "dispatch_dropoff",
            "producer_error": "Dispatch accepted but worker unavailable",
            "runtime_db_path": "/Users/dhyana/.dharma/state/runtime.db",
            "topology": "fan_out",
            "metadata_hints": {
                "source": "orchestrator",
                "failure_code": "dispatch_dropoff",
                "error": "Dispatch accepted but worker unavailable",
                "runtime_db_path": "/Users/dhyana/.dharma/state/runtime.db",
                "topology": "fan_out",
            },
        }
    ]


def test_receipt_coverage_report_infers_ds_goal_cli_gap_source(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    state_root = tmp_path / "state"
    census_receipt = state_root / "ops" / "live_process_census.json"
    census_receipt.parent.mkdir(parents=True)
    census_receipt.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": "2026-06-14T06:51:52Z",
                "surfaces": [
                    {
                        "id": "cli.ds_goal",
                        "label": "ds-goal runtime CLI",
                        "status": "live",
                        "proof_gaps": [
                            "ds_goal_cli_target_repo_mismatch",
                            "ds_goal_cli_target_lacks_sync_side_effect_hardening",
                        ],
                        "raw": {
                            "target_repo": "/Users/dhyana/dharma_swarm_main",
                            "target_resolution_source": (
                                "installed_wrapper_dharma_swarm_main_preference"
                            ),
                            "target_matches_current_repo": False,
                            "default_wrapper_target": {
                                "target_repo": "/Users/dhyana/dharma_swarm_main",
                                "target_resolution_source": (
                                    "installed_wrapper_dharma_swarm_main_preference"
                                ),
                            },
                            "safe_current_checkout_invocation": (
                                "DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
                                "/Users/dhyana/.dharma/bin/ds-goal"
                            ),
                            "installed_wrapper_contract": {
                                "wrapper_sha256": "abc123def4567890",
                                "dharma_swarm_repo_pin_supported": True,
                            },
                            "target_sync_receipt_hardening": {
                                "state": "sync_receipt_side_effect_keys_missing",
                            },
                            "convergence_decision_packet": {
                                "approval_state": "operator_approval_required",
                                "score_effect": (
                                    "no_score_movement_until_default_wrapper_or_"
                                    "target_is_converged_and_post_change_"
                                    "receipt_gate_evidence_passes"
                                ),
                                "operator_decision_options": [
                                    {
                                        "id": (
                                            "converge_installed_wrapper_default_"
                                            "to_audited_checkout"
                                        ),
                                    },
                                    {
                                        "id": "harden_current_default_target_checkout",
                                    },
                                    {
                                        "id": (
                                            "retain_default_with_mandatory_pin_"
                                            "or_quarantine"
                                        ),
                                    },
                                ],
                                "forbidden_without_operator_approval": [
                                    "edit_installed_wrapper",
                                    "patch_default_target_checkout",
                                    (
                                        "start_repo_native_longrun_from_unpinned_"
                                        "ds_goal"
                                    ),
                                    "declare_75_plus_from_pin_mitigation_only",
                                ],
                            },
                            "longrun_preflight_gate": {
                                "status": "blocked_unpinned_default_target",
                                "longrun_start_allowed": False,
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, assigned_to, status,"
            " metadata_json, started_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "run_ds_goal_deadbeef",
                "ds_goal:palantir-pilot-source-card-expansion-2026-06-14",
                "palantir-pilot-source-card-expansion-2026-06-14-t01",
                "palantir_pilot",
                "completed",
                "{}",
                "2026-06-14T03:43:10Z",
            ),
        )
        for receipt_type, suffix in [
            ("task_claim", "claim"),
            ("delegation_run", "run"),
        ]:
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, status,"
                " payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"rr-ds-goal-{suffix}",
                    receipt_type,
                    "run_ds_goal_deadbeef",
                    "palantir-pilot-source-card-expansion-2026-06-14-t01",
                    f"trace-{suffix}",
                    f"corr-{suffix}",
                    "palantir_pilot",
                    f"idem-{suffix}",
                    "completed",
                    "{}",
                    f"2026-06-14T03:43:1{0 if suffix == 'claim' else 1}Z",
                ),
            )

    report = mod.build_report(db_path)
    diagnostics = report["runtime_receipts"]["latest_side_effect_key_gap_diagnostics"]
    groups = report["runtime_receipts"]["side_effect_key_gap_producer_groups"]

    assert diagnostics[0]["producer_source"] == "ds_goal_cli"
    assert diagnostics[0]["producer_failure_code"] == "sync_receipt_side_effect_key_missing"
    assert diagnostics[0]["topology"] == "cli_goal_run"
    assert diagnostics[0]["metadata_hints"] == {
        "inferred_source": "ds_goal_cli",
        "inferred_failure_code": "sync_receipt_side_effect_key_missing",
        "inferred_topology": "cli_goal_run",
        "inferred_from": "ds_goal_runtime_identity",
    }
    assert {
        (row["receipt_type"], row["producer_source"], row["producer_failure_code"], row["topology"])
        for row in groups
    } == {
        (
            "task_claim",
            "ds_goal_cli",
            "sync_receipt_side_effect_key_missing",
            "cli_goal_run",
        ),
        (
            "delegation_run",
            "ds_goal_cli",
            "sync_receipt_side_effect_key_missing",
            "cli_goal_run",
        ),
    }
    assert report["major_task_receipts"]["latest_provider_model_unproven_sample"] == [
        {
            "receipt_id": "rr-ds-goal-run",
            "receipt_type": "delegation_run",
            "run_id": "run_ds_goal_deadbeef",
            "task_id": "palantir-pilot-source-card-expansion-2026-06-14-t01",
            "agent_id": "palantir_pilot",
            "created_at": "2026-06-14T03:43:11Z",
            "provider_model_payload_class": "missing",
            "provider_model_truth_source": "",
            "has_provider_payload": False,
            "has_model_payload": False,
            "receipt_producer_source": "ds_goal_cli",
            "receipt_producer_failure_code": "provider_model_provenance_missing",
            "receipt_producer_topology": "cli_goal_run",
        }
    ]
    assert report["major_task_receipts"]["latest_provider_model_unproven_producer_groups"] == [
        {
            "receipt_type": "delegation_run",
            "provider_model_payload_class": "missing",
            "provider_model_truth_source": "<blank>",
            "producer_source": "ds_goal_cli",
            "producer_failure_code": "provider_model_provenance_missing",
            "topology": "cli_goal_run",
            "missing_provider_model_provenance": 1,
            "latest_created_at": "2026-06-14T03:43:11Z",
            "sample_agent_id": "palantir_pilot",
            "sample_task_id": "palantir-pilot-source-card-expansion-2026-06-14-t01",
            "sample_run_id": "run_ds_goal_deadbeef",
        }
    ]
    context = report["runtime_surfaces"]["cli.ds_goal"]
    assert context["available"] is True
    assert context["target_repo"] == "/Users/dhyana/dharma_swarm_main"
    assert context["target_matches_current_repo"] is False
    assert context["safe_current_checkout_invocation"] == (
        "DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
        "/Users/dhyana/.dharma/bin/ds-goal"
    )
    assert (
        context["target_sync_receipt_hardening_state"]
        == "sync_receipt_side_effect_keys_missing"
    )
    assert context["convergence_decision_packet"]["approval_state"] == (
        "operator_approval_required"
    )
    assert context["longrun_preflight_status"] == (
        "blocked_unpinned_default_target"
    )
    assert context["longrun_preflight_allowed"] is False
    assert (
        "installed ds-goal wrapper default target does not match the audited checkout"
        in report["summary"]["production_readiness_blockers"]
    )
    assert (
        "installed ds-goal wrapper target lacks sync side-effect-key hardening"
        in report["summary"]["production_readiness_blockers"]
    )

    mod._print_text(report)
    output = capsys.readouterr().out
    assert "Latest major provider/model accounted: 0.0%" in output
    assert "Latest terminal provider/model accounted: 0.0%" in output
    assert "ds-goal CLI owner evidence:" in output
    assert "target=/Users/dhyana/dharma_swarm_main" in output
    assert (
        "safe=DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
        "/Users/dhyana/.dharma/bin/ds-goal"
    ) in output
    assert "convergence_decision=operator_approval_required" in output
    assert "preflight=blocked_unpinned_default_target" in output
    assert (
        "operator_options=converge_installed_wrapper_default_to_audited_checkout|"
        "harden_current_default_target_checkout|"
        "retain_default_with_mandatory_pin_or_quarantine"
    ) in output
    assert "forbidden_without_approval=edit_installed_wrapper|" in output
    assert (
        "- installed ds-goal wrapper default target does not match the audited checkout"
        in output
    )
    assert (
        "- installed ds-goal wrapper target lacks sync side-effect-key hardening"
        in output
    )


def test_receipt_coverage_report_groups_side_effect_gaps_by_producer(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        for index, task_id in enumerate(["t1", "t2"], start=1):
            run_id = f"run-gap-{index}"
            db.execute(
                "INSERT INTO delegation_runs"
                " (run_id, session_id, task_id, assigned_to, status,"
                " failure_code, metadata_json, started_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    "sess-daemon",
                    task_id,
                    "a1",
                    "failed",
                    "dispatch_dropoff",
                    '{"source":"orchestrator","topology":"fan_out"}',
                    "2026-06-14T00:00:00Z",
                ),
            )
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, status,"
                " payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"rr-gap-{index}",
                    "delegation_run",
                    run_id,
                    task_id,
                    f"trace-{index}",
                    f"corr-{index}",
                    "a1",
                    f"idem-{index}",
                    "failed",
                    "{}",
                    f"2026-06-14T00:00:0{index}Z",
                ),
            )
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, assigned_to, status,"
            " failure_code, metadata_json, started_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-gap-ordinary",
                "sess-worker",
                "task-prod",
                "agent-prod",
                "failed",
                "worker_timeout",
                '{"source":"worker","topology":"pipeline"}',
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, status,"
            " payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-gap-ordinary",
                "delegation_run",
                "run-gap-ordinary",
                "task-prod",
                "trace-ordinary",
                "corr-ordinary",
                "agent-prod",
                "idem-ordinary",
                "failed",
                "{}",
                "2026-06-14T00:00:03Z",
            ),
        )

    report = mod.build_report(db_path)

    assert report["runtime_receipts"]["side_effect_key_gap_producer_groups"] == [
        {
            "receipt_type": "delegation_run",
            "producer_source": "orchestrator",
            "producer_failure_code": "dispatch_dropoff",
            "topology": "fan_out",
            "identifier_shape": "fixture_shaped",
            "missing_side_effect_key": 2,
            "latest_created_at": "2026-06-14T00:00:02Z",
            "sample_run_id": "run-gap-2",
            "sample_task_id": "t2",
            "sample_agent_id": "a1",
            "sample_status": "failed",
        },
        {
            "receipt_type": "delegation_run",
            "producer_source": "worker",
            "producer_failure_code": "worker_timeout",
            "topology": "pipeline",
            "identifier_shape": "ordinary",
            "missing_side_effect_key": 1,
            "latest_created_at": "2026-06-14T00:00:03Z",
            "sample_run_id": "run-gap-ordinary",
            "sample_task_id": "task-prod",
            "sample_agent_id": "agent-prod",
            "sample_status": "failed",
        },
    ]


def test_receipt_coverage_report_measures_recent_gap_windows_from_db_head(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        for run_id, task_id, agent_id, metadata in [
            (
                "run-new-missing",
                "t-ready",
                "a1",
                '{"source":"orchestrator","topology":"fan_out"}',
            ),
            (
                "run-mid-missing",
                "task-prod",
                "agent-prod",
                '{"source":"worker","topology":"pipeline"}',
            ),
            (
                "run-old-missing",
                "task-old",
                "agent-old",
                '{"source":"legacy","topology":"fan_out"}',
            ),
        ]:
            db.execute(
                "INSERT INTO delegation_runs"
                " (run_id, session_id, task_id, assigned_to, status,"
                " failure_code, metadata_json, started_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    "sess-window",
                    task_id,
                    agent_id,
                    "failed",
                    "dispatch_dropoff",
                    metadata,
                    "2026-06-13T23:00:00+00:00",
                ),
            )
        rows = [
            (
                "rr-new-missing",
                "delegation_run",
                "run-new-missing",
                "t-ready",
                "a1",
                "",
                "failed",
                "2026-06-14T00:09:00+00:00",
            ),
            (
                "rr-head-filled",
                "delegation_run",
                "run-new-missing",
                "t-ready",
                "a1",
                "side-head",
                "completed",
                "2026-06-14T00:10:00+00:00",
            ),
            (
                "rr-mid-missing",
                "task_claim",
                "run-mid-missing",
                "task-prod",
                "agent-prod",
                "",
                "failed",
                "2026-06-14T00:03:00+00:00",
            ),
            (
                "rr-old-missing",
                "delegation_run",
                "run-old-missing",
                "task-old",
                "agent-old",
                "",
                "failed",
                "2026-06-13T23:00:00+00:00",
            ),
        ]
        for receipt_id, receipt_type, run_id, task_id, agent_id, side_effect_key, status, created in rows:
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    receipt_type,
                    run_id,
                    task_id,
                    f"trace-{receipt_id}",
                    f"corr-{receipt_id}",
                    agent_id,
                    f"idem-{receipt_id}",
                    side_effect_key,
                    status,
                    "{}",
                    created,
                ),
            )

    report = mod.build_report(db_path)

    assert report["summary"]["latest_runtime_receipt_created_at"] == "2026-06-14T00:10:00+00:00"
    windows = report["runtime_receipts"]["recent_side_effect_key_gap_windows"]
    assert [(row["window_minutes"], row["total"], row["missing_side_effect_key"]) for row in windows] == [
        (5, 2, 1),
        (15, 3, 2),
        (60, 3, 2),
    ]
    assert windows[0]["top_gap_producer_groups"] == [
        {
            "receipt_type": "delegation_run",
            "producer_source": "orchestrator",
            "producer_failure_code": "dispatch_dropoff",
            "topology": "fan_out",
            "identifier_shape": "fixture_shaped",
            "missing_side_effect_key": 1,
            "latest_created_at": "2026-06-14T00:09:00+00:00",
            "sample_run_id": "run-new-missing",
            "sample_task_id": "t-ready",
            "sample_agent_id": "a1",
            "sample_status": "failed",
        }
    ]
    assert report["runtime_receipts"]["active_head_side_effect_key_gate"] == {
        "gate": "active_head_side_effect_key_clean",
        "passed": False,
        "reason": "recent DB-head windows still contain blank side_effect_key receipts",
        "windows_evaluated": [5, 15, 60],
        "blocked_windows": [
            {
                "window_minutes": 5,
                "total": 2,
                "missing_side_effect_key": 1,
                "missing_side_effect_key_percent": 50.0,
            },
            {
                "window_minutes": 15,
                "total": 3,
                "missing_side_effect_key": 2,
                "missing_side_effect_key_percent": 66.67,
            },
            {
                "window_minutes": 60,
                "total": 3,
                "missing_side_effect_key": 2,
                "missing_side_effect_key_percent": 66.67,
            },
        ],
        "widest_window": {
            "window_minutes": 60,
            "anchor_created_at": "2026-06-14T00:10:00+00:00",
            "total": 3,
            "missing_side_effect_key": 2,
            "missing_side_effect_key_percent": 66.67,
        },
    }
    assert "recent DB-head windows still contain blank side_effect_key receipts" in report["summary"]["blockers"]


def test_receipt_coverage_report_active_head_gate_passes_when_recent_windows_are_clean(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, assigned_to, status,"
            " failure_code, metadata_json, started_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-clean",
                "sess-clean",
                "task-clean",
                "agent-clean",
                "completed",
                "",
                '{"source":"orchestrator","topology":"fan_out"}',
                "2026-06-14T00:00:00+00:00",
            ),
        )
        for index, created in enumerate(
            [
                "2026-06-14T00:00:00+00:00",
                "2026-06-14T00:05:00+00:00",
                "2026-06-14T00:10:00+00:00",
            ],
            start=1,
        ):
            db.execute(
                "INSERT INTO runtime_receipts"
                " (receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"rr-clean-{index}",
                    "delegation_run",
                    "run-clean",
                    "task-clean",
                    f"trace-clean-{index}",
                    f"corr-clean-{index}",
                    "agent-clean",
                    f"idem-clean-{index}",
                    f"side-clean-{index}",
                    "completed",
                    "{}",
                    created,
                ),
            )

    report = mod.build_report(db_path)

    assert report["summary"]["active_head_side_effect_key_clean"] is True
    assert report["runtime_receipts"]["active_head_side_effect_key_gate"] == {
        "gate": "active_head_side_effect_key_clean",
        "passed": True,
        "reason": "recent DB-head windows have complete side_effect_key coverage",
        "windows_evaluated": [5, 15, 60],
        "blocked_windows": [],
        "widest_window": {
            "window_minutes": 60,
            "anchor_created_at": "2026-06-14T00:10:00+00:00",
            "total": 3,
            "missing_side_effect_key": 0,
            "missing_side_effect_key_percent": 0.0,
        },
    }


def test_receipt_coverage_report_can_scope_to_one_fresh_run(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-legacy",
                "task-legacy",
                "{}",
                "",
                None,
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-legacy",
                "delegation_run",
                "run-legacy",
                "task-legacy",
                "trace-legacy",
                "corr-legacy",
                "agent-legacy",
                "completed",
                "{}",
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-1",
                "task-1",
                '{"mission_id":"mission-1"}',
                "artifact-1",
                '{"receipt_id":"rr-1"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-1",
                "delegation_run",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "agent-1",
                "idem-1",
                "side-1",
                "completed",
                '{"mission_id":"mission-1","artifact_refs":["artifact-1"]}',
                "2026-06-14T00:00:01Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-1",
                "side-1",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "completed",
                "rr-1",
                "2026-06-14T00:00:01Z",
                "2026-06-14T00:00:02Z",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-1", "run-1", "task-1"),
        )

    global_report = mod.build_report(db_path)
    scoped_report = mod.build_report(db_path, run_id="run-1")

    assert global_report["summary"]["score_gate_70_to_75"] is False
    assert scoped_report["scope"] == {
        "run_id": "run-1",
        "since_created_at": "",
        "mode": "run_id",
    }
    assert scoped_report["summary"]["score_gate_70_to_75"] is True
    assert scoped_report["summary"]["runtime_receipts_total"] == 1
    assert scoped_report["major_task_receipts"]["with_matching_idempotency_record"] == 1


def test_receipt_coverage_report_can_scope_to_fresh_since_timestamp(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-legacy",
                "task-legacy",
                "{}",
                "",
                None,
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-legacy",
                "delegation_run",
                "run-legacy",
                "task-legacy",
                "trace-legacy",
                "corr-legacy",
                "agent-legacy",
                "completed",
                "{}",
                "2026-06-14T00:00:00Z",
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, task_id, metadata_json, current_artifact_id, receipt_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "run-fresh",
                "task-fresh",
                '{"mission_id":"mission-fresh"}',
                "artifact-fresh",
                '{"receipt_id":"rr-fresh"}',
            ),
        )
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rr-fresh",
                "delegation_run",
                "run-fresh",
                "task-fresh",
                "trace-fresh",
                "corr-fresh",
                "agent-fresh",
                "idem-fresh",
                "side-fresh",
                "completed",
                '{"mission_id":"mission-fresh","artifact_refs":["artifact-fresh"]}',
                "2026-06-14T00:00:01Z",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-fresh",
                "side-fresh",
                "run-fresh",
                "task-fresh",
                "trace-fresh",
                "corr-fresh",
                "completed",
                "rr-fresh",
                "2026-06-14T00:00:01Z",
                "2026-06-14T00:00:02Z",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, run_id, task_id)"
            " VALUES (?, ?, ?)",
            ("artifact-fresh", "run-fresh", "task-fresh"),
        )

    global_report = mod.build_report(db_path)
    fresh_report = mod.build_report(db_path, since_created_at="2026-06-14T00:00:01Z")

    assert global_report["summary"]["score_gate_70_to_75"] is False
    assert fresh_report["scope"] == {
        "run_id": "",
        "since_created_at": "2026-06-14T00:00:01Z",
        "mode": "since_created_at",
    }
    assert fresh_report["summary"]["score_gate_70_to_75"] is True
    assert fresh_report["summary"]["runtime_receipts_total"] == 1
    assert fresh_report["delegation_runs"]["scoped_total"] == 1
    assert fresh_report["delegation_runs"]["receipt_json_percent"] == 100.0
    assert fresh_report["runtime_receipts"]["field_coverage"]["side_effect_key"] == {
        "filled": 1,
        "total": 1,
        "percent": 100.0,
        "missing": 0,
    }


def test_receipt_coverage_report_fails_empty_run_scope(tmp_path):
    mod = _load_report_module()
    db_path = tmp_path / "runtime.db"
    _init_db(db_path)

    report = mod.build_report(db_path, run_id="run-missing")

    assert report["summary"]["score_gate_70_to_75"] is False
    assert report["summary"]["runtime_receipts_total"] == 0
    assert "no major task receipts found for selected scope" in report["summary"]["blockers"]


def test_receipt_coverage_report_handles_missing_db(tmp_path):
    mod = _load_report_module()

    report = mod.build_report(tmp_path / "missing.db")

    assert report["db_exists"] is False
    assert report["summary"]["readable"] is False
    assert report["summary"]["score_gate_70_to_75"] is False
