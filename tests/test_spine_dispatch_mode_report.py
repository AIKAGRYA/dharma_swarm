from __future__ import annotations

import importlib.util
import json
import plistlib
import sys
from datetime import UTC, datetime
from pathlib import Path


def _load_report_module():
    spec = importlib.util.spec_from_file_location(
        "spine_dispatch_mode_report",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "spine_dispatch_mode_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fresh_generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_dispatch_mode_report_marks_orchestrator_legacy_default_without_env():
    mod = _load_report_module()

    report = mod.build_report(env={})

    assert report["summary"]["orchestrator_mode"] == "spine_opt_in_legacy_default"
    assert (
        report["summary"]["orchestrator_current_process"]
        == "legacy_default_in_current_process"
    )
    assert report["summary"]["daemon_health_self_report"] == "not_checked"
    assert report["summary"]["score_gate_65_to_70"] is True


def test_dispatch_mode_report_can_probe_daemon_health_self_report(monkeypatch):
    mod = _load_report_module()

    def fake_fetch(url, *, timeout_seconds):
        assert url == "http://127.0.0.1:7433/health"
        assert timeout_seconds == 1.5
        return 200, {
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            }
        }

    monkeypatch.setattr(mod, "_fetch_json", fake_fetch)

    report = mod.build_report(env={}, probe_daemon_health=True)

    assert (
        report["summary"]["daemon_health_self_report"]
        == "spine_enabled_self_report"
    )
    assert report["daemon_health"]["runtime_dispatch"] == {
        "spine_dispatch_enabled": True,
        "dispatch_mode": "spine",
        "env_key_present": True,
        "source": "process_env_non_secret_boolean",
    }


def test_dispatch_mode_report_marks_missing_daemon_runtime_dispatch(monkeypatch):
    mod = _load_report_module()

    monkeypatch.setattr(
        mod,
        "_fetch_json",
        lambda url, *, timeout_seconds: (200, {"status": "ok"}),
    )

    report = mod.build_report(env={}, probe_daemon_health=True)

    assert (
        report["summary"]["daemon_health_self_report"]
        == "missing_runtime_dispatch"
    )


def test_dispatch_mode_report_rejects_schema_invalid_live_census(tmp_path, monkeypatch):
    mod = _load_report_module()
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mod, "_census_receipt_path", lambda: receipt)

    report = mod.build_report(env={})

    assert report["summary"]["live_census_state"] == "receipt_invalid"
    assert report["summary"]["live_census_proof_gap_surfaces"] == 0
    assert "schema_version is missing" in report["live_census"]["evidence"]


def test_dispatch_mode_report_rejects_live_census_without_surface_list(
    tmp_path,
    monkeypatch,
):
    mod = _load_report_module()
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": _fresh_generated_at(),
                "surfaces": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_census_receipt_path", lambda: receipt)

    report = mod.build_report(env={})

    assert report["summary"]["live_census_state"] == "receipt_invalid"
    assert "surfaces is missing or not a list" in report["live_census"]["evidence"]


def test_dispatch_mode_report_flags_stale_live_census_receipt(
    tmp_path,
    monkeypatch,
):
    mod = _load_report_module()
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": "2000-01-01T00:00:00Z",
                "surfaces": [
                    {
                        "id": "substrate.dharma_daemon",
                        "label": "Dharma daemon",
                        "status": "live",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_census_receipt_path", lambda: receipt)

    report = mod.build_report(env={})

    assert report["summary"]["live_census_state"] == "receipt_stale"
    assert report["summary"]["live_census_proof_gap_surfaces"] == 0
    assert report["live_census"]["generated_at"] == "2000-01-01T00:00:00Z"
    assert "older than 24h" in report["live_census"]["evidence"]


def test_dispatch_mode_report_includes_live_census_source_gaps(tmp_path, monkeypatch):
    mod = _load_report_module()
    receipt = tmp_path / "live_process_census.json"
    generated_at = _fresh_generated_at()
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": generated_at,
                "surfaces": [
                    {
                        "id": "substrate.dharma_daemon",
                        "label": "Dharma daemon",
                        "status": "live",
                        "pids": ["93875"],
                        "proof_gaps": [
                            "daemon_dispatch_runtime_unproven",
                            "daemon_process_source_stale",
                        ],
                        "raw": {
                            "process_source_state": {
                                "state": "source_changed_after_process_start",
                            },
                            "runtime_receipt_active_head": {
                                "active_head_side_effect_key_clean": False,
                                "runtime_receipts_total": 7657,
                                "latest_created_at": "2026-06-13T22:29:48.795782+00:00",
                                "latest_age_hours": 7.4,
                                "latest_max_age_hours": 6.0,
                                "latest_fresh": False,
                                "windows": [
                                    {
                                        "window_minutes": 5,
                                        "total": 56,
                                        "missing_side_effect_key": 56,
                                        "missing_side_effect_key_percent": 100.0,
                                    },
                                    {
                                        "window_minutes": 15,
                                        "total": 60,
                                        "missing_side_effect_key": 60,
                                        "missing_side_effect_key_percent": 100.0,
                                    },
                                ],
                            },
                            "runtime_receipt_coverage": {
                                "coverage_report_available": True,
                                "runtime_receipts_total": 7769,
                                "major_task_receipts_total": 3523,
                                "latest_sample_size": 250,
                                "latest_with_provider_payload": 0,
                                "latest_with_model_payload": 0,
                                "latest_with_provider_model_payload": 0,
                                "latest_major_task_receipts_provider_model_percent": 0.0,
                                "provider_model_latest_complete": False,
                                "production_readiness_blockers": [
                                    "latest major task receipts do not all carry provider/model payloads"
                                ],
                                "field_gap_producer_groups": [
                                    {
                                        "gap_type": "mission_payload",
                                        "receipt_type": "delegation_run",
                                        "producer_source": "orchestrator",
                                        "producer_failure_code": "execution_error",
                                        "topology": "fan_out",
                                        "identifier_shape": "ordinary",
                                        "missing": 7,
                                        "latest_created_at": "2026-06-13T22:29:48.795782+00:00",
                                        "freshness_class": "recent_historical_24h",
                                        "age_minutes_from_head": 61,
                                        "recommended_action": (
                                            "repair_or_quarantine_orchestrator_error_receipts"
                                        ),
                                "sample_agent_id": "agent-a",
                                "sample_task_id": "task-a",
                                "sample_run_id": "run-a",
                            }
                        ],
                        "field_gap_summary": {
                            "total_missing": 7,
                            "group_count": 1,
                            "active_head_missing": 0,
                            "recent_historical_missing": 7,
                            "older_historical_missing": 0,
                            "quarantine_candidate_missing": 7,
                            "by_freshness_class": {"recent_historical_24h": 7},
                        },
                        "field_gap_action_queue": [
                            {
                                "short_label": "orchestrator_error",
                                "action": (
                                    "repair_or_quarantine_orchestrator_error_receipts"
                                ),
                                "missing": 7,
                                "priority": 3,
                            }
                        ],
                    },
                },
                    },
                    {
                        "id": "transport.nats",
                        "label": "Local NATS JetStream",
                        "status": "live",
                        "proof_gaps": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_census_receipt_path", lambda: receipt)

    report = mod.build_report(env={})

    assert report["summary"]["live_census_state"] == "proof_gaps_present"
    assert report["summary"]["live_census_proof_gap_surfaces"] == 1
    assert report["summary"]["live_census_source_stale_surfaces"] == 1
    assert report["summary"]["score_gate_65_to_70"] is True
    assert report["live_census"]["generated_at"] == generated_at
    assert report["live_census"]["source_stale_surfaces"][0]["id"] == "substrate.dharma_daemon"
    daemon_surface = report["live_census"]["proof_gap_surfaces"][0]
    assert daemon_surface["runtime_receipt_active_head"] == {
        "active_head_side_effect_key_clean": False,
        "runtime_receipts_total": 7657,
        "latest_created_at": "2026-06-13T22:29:48.795782+00:00",
        "latest_age_hours": 7.4,
        "latest_max_age_hours": 6.0,
        "latest_fresh": False,
        "windows": [
            {
                "window_minutes": 5,
                "total": 56,
                "missing_side_effect_key": 56,
                "missing_side_effect_key_percent": 100.0,
            },
            {
                "window_minutes": 15,
                "total": 60,
                "missing_side_effect_key": 60,
                "missing_side_effect_key_percent": 100.0,
            },
        ],
    }
    assert daemon_surface["runtime_receipt_coverage"] == {
        "coverage_report_available": True,
        "runtime_receipts_total": 7769,
        "major_task_receipts_total": 3523,
        "latest_sample_size": 250,
        "latest_with_provider_payload": 0,
        "latest_with_model_payload": 0,
        "latest_with_provider_model_payload": 0,
        "latest_with_provider_model_provenance": None,
        "latest_with_provider_model_accounted": None,
        "latest_provider_model_pending_execution": None,
        "latest_terminal_sample_size": None,
        "latest_terminal_with_provider_model_payload": None,
        "latest_terminal_with_provider_model_provenance": None,
        "latest_terminal_with_provider_model_accounted": None,
        "latest_major_task_receipts_provider_model_percent": 0.0,
        "latest_major_task_receipts_provider_model_provenance_percent": None,
        "latest_major_task_receipts_provider_model_accounted_percent": None,
        "latest_terminal_major_task_receipts_provider_model_percent": None,
        "latest_terminal_major_task_receipts_provider_model_provenance_percent": None,
        "latest_terminal_major_task_receipts_provider_model_accounted_percent": None,
        "provider_model_payload_complete": None,
        "provider_model_provenance_complete": None,
        "provider_model_accounted_complete": None,
        "terminal_provider_model_payload_complete": None,
        "terminal_provider_model_provenance_complete": None,
        "terminal_provider_model_accounted_complete": None,
        "provider_model_latest_complete": False,
        "production_readiness_blockers": [
            "latest major task receipts do not all carry provider/model payloads"
        ],
        "active_head_gap_producer_groups": [],
        "field_gap_producer_groups": [
            {
                "gap_type": "mission_payload",
                "receipt_type": "delegation_run",
                "producer_source": "orchestrator",
                "producer_failure_code": "execution_error",
                "topology": "fan_out",
                "identifier_shape": "ordinary",
                "missing": 7,
                "latest_created_at": "2026-06-13T22:29:48.795782+00:00",
                "freshness_class": "recent_historical_24h",
                "age_minutes_from_head": 61,
                "recommended_action": (
                    "repair_or_quarantine_orchestrator_error_receipts"
                ),
                "sample_agent_id": "agent-a",
                "sample_task_id": "task-a",
                "sample_run_id": "run-a",
            }
        ],
        "field_gap_summary": {
            "total_missing": 7,
            "group_count": 1,
            "active_head_missing": 0,
            "recent_historical_missing": 7,
            "older_historical_missing": 0,
            "quarantine_candidate_missing": 7,
            "by_freshness_class": {"recent_historical_24h": 7},
        },
        "field_gap_action_queue": [
            {
                "short_label": "orchestrator_error",
                "action": "repair_or_quarantine_orchestrator_error_receipts",
                "missing": 7,
                "priority": 3,
            }
        ],
        "gate_70_to_75_components": [],
        "latest_provider_model_unproven_producer_groups": [],
        "latest_provider_model_payload_class_breakdown": {},
        "latest_terminal_provider_model_payload_class_breakdown": {},
    }


def test_dispatch_mode_report_includes_ds_goal_wrapper_contract(
    tmp_path,
    monkeypatch,
):
    mod = _load_report_module()
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": _fresh_generated_at(),
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
                            "safe_current_checkout_invocation": (
                                "DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
                                "/Users/dhyana/.dharma/bin/ds-goal"
                            ),
                            "default_wrapper_target": {
                                "target_repo": "/Users/dhyana/dharma_swarm_main",
                                "target_resolution_source": (
                                    "installed_wrapper_dharma_swarm_main_preference"
                                ),
                            },
                            "installed_wrapper_contract": {
                                "wrapper_sha256": "abc123def4567890",
                                "dharma_swarm_repo_pin_supported": True,
                                "dharma_swarm_main_preference_declared": True,
                                "dharma_swarm_fallback_declared": True,
                                "execs_autonomy_spine": True,
                            },
                            "target_sync_receipt_hardening": {
                                "state": "sync_receipt_side_effect_keys_missing",
                            },
                            "convergence_decision_packet": {
                                "approval_state": "operator_approval_required",
                            },
                            "longrun_preflight_gate": {
                                "status": "blocked_unpinned_default_target",
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_census_receipt_path", lambda: receipt)
    monkeypatch.setattr(
        mod,
        "_live_census_freshness",
        lambda payload: {"state": "fresh", "age_minutes": 0.0},
    )

    report = mod.build_report(env={})

    surface = report["live_census"]["proof_gap_surfaces"][0]
    contract = surface["ds_goal_wrapper_contract"]
    assert contract["target_repo"] == "/Users/dhyana/dharma_swarm_main"
    assert contract["target_resolution_source"] == (
        "installed_wrapper_dharma_swarm_main_preference"
    )
    assert contract["target_matches_current_repo"] is False
    assert contract["wrapper_sha256"] == "abc123def4567890"
    assert contract["convergence_decision_state"] == "operator_approval_required"
    assert contract["longrun_preflight_status"] == "blocked_unpinned_default_target"
    assert mod._format_ds_goal_wrapper_contract(contract) == (
        "target=/Users/dhyana/dharma_swarm_main; "
        "source=installed_wrapper_dharma_swarm_main_preference; "
        "matches_current=false; default=/Users/dhyana/dharma_swarm_main; "
        "default_source=installed_wrapper_dharma_swarm_main_preference; "
        "wrapper_sha256=abc123def456; pin=true; main=true; fallback=true; "
        "autonomy_spine=true; hardening=sync_receipt_side_effect_keys_missing; "
        "decision=operator_approval_required; "
        "preflight=blocked_unpinned_default_target; "
        "safe=DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
        "/Users/dhyana/.dharma/bin/ds-goal"
    )


def test_dispatch_report_formats_active_head_gap_producers() -> None:
    mod = _load_report_module()

    text = mod._format_runtime_receipt_coverage(
        {
            "coverage_report_available": True,
            "latest_sample_size": 200,
            "latest_with_provider_payload": 6,
            "latest_with_model_payload": 6,
            "latest_with_provider_model_payload": 6,
            "latest_with_provider_model_provenance": 0,
            "latest_provider_model_pending_execution": 4,
            "latest_terminal_sample_size": 196,
            "latest_terminal_with_provider_model_payload": 6,
            "latest_terminal_with_provider_model_provenance": 0,
            "latest_major_task_receipts_provider_model_percent": 3.0,
            "latest_major_task_receipts_provider_model_provenance_percent": 0.0,
            "latest_terminal_major_task_receipts_provider_model_percent": 3.06,
            "latest_terminal_major_task_receipts_provider_model_provenance_percent": 0.0,
            "provider_model_latest_complete": False,
            "major_task_receipts_total": 3537,
            "active_head_gap_producer_groups": [
                {
                    "window_minutes": 15,
                    "receipt_type": "delegation_run",
                    "producer_source": "ds_goal_cli",
                    "producer_failure_code": "sync_receipt_side_effect_key_missing",
                    "missing_side_effect_key": 1,
                }
            ],
            "latest_provider_model_unproven_producer_groups": [
                {
                    "receipt_type": "delegation_run",
                    "provider_model_payload_class": "missing",
                    "producer_source": "ds_goal_cli",
                    "producer_failure_code": "sync_receipt_side_effect_key_missing",
                    "missing_provider_model_provenance": 1,
                }
            ],
            "field_gap_producer_groups": [
                {
                    "gap_type": "mission_payload",
                    "receipt_type": "delegation_run",
                    "producer_source": "orchestrator",
                    "producer_failure_code": "execution_error",
                    "topology": "fan_out",
                    "missing": 7,
                    "freshness_class": "recent_historical_24h",
                }
            ],
            "field_gap_summary": {
                "total_missing": 7,
                "group_count": 1,
                "active_head_missing": 0,
                "recent_historical_missing": 7,
                "older_historical_missing": 0,
                "quarantine_candidate_missing": 7,
                "by_freshness_class": {"recent_historical_24h": 7},
            },
            "field_gap_action_queue": [
                {
                    "short_label": "orchestrator_error",
                    "action": "repair_or_quarantine_orchestrator_error_receipts",
                    "missing": 7,
                    "priority": 3,
                    "fresh_proof": {
                        "status": "fresh_scoped_proof_recorded",
                    },
                }
            ],
            "gate_70_to_75_components": [
                {"short_label": "core", "status": "fail"},
                {"short_label": "idempotency", "status": "fail"},
                {"short_label": "mission", "status": "fail"},
                {"short_label": "artifact", "status": "fail"},
                {"short_label": "active_head", "status": "fail"},
            ],
        }
    )

    assert (
        "active_head_gap_producers="
        "15m:delegation_run/ds_goal_cli/sync_receipt_side_effect_key_missing=1"
        in text
    )
    assert (
        "provider_model_gap_producers="
        "delegation_run/missing/ds_goal_cli/sync_receipt_side_effect_key_missing=1"
        in text
    )
    assert (
        "field_gap_producers="
        "mission_payload/delegation_run/orchestrator/execution_error/"
        "fan_out=7@recent_historical_24h"
        in text
    )
    assert "field_gap_summary=total:7|recent_historical_24h:7|quarantine_candidate:7" in text
    assert "field_gap_actions=orchestrator_error:7" in text
    assert "field_gap_proofs=orchestrator_error:fresh" in text
    assert (
        "gate_70_75=core:fail|idempotency:fail|mission:fail|artifact:fail|"
        "active_head:fail"
    ) in text
    assert "terminal=6/196" in text
    assert "terminal_percent=3.06" in text
    assert "pending=4" in text


def test_dispatch_mode_report_marks_orchestrator_spine_enabled_with_env():
    mod = _load_report_module()

    report = mod.build_report(env={"DHARMA_SPINE_DISPATCH": "1"})

    assert (
        report["summary"]["orchestrator_current_process"]
        == "spine_enabled_in_current_process"
    )
    assert report["summary"]["orchestrator_mode"] == "spine_opt_in_legacy_default"


def test_dispatch_mode_report_marks_a2a_bypasses_legacy_quarantined():
    mod = _load_report_module()

    report = mod.build_report(env={})
    entries = report["entries"]
    quarantined = [entry for entry in entries if entry["mode"] == "legacy_quarantined"]
    unknown = [entry for entry in entries if entry["mode"] == "unknown_dispatch_mode"]

    assert report["summary"]["a2a_spine_native"] == 1
    assert report["summary"]["a2a_legacy_quarantined"] == 0
    assert report["summary"]["a2a_unknown"] == 0
    assert unknown == []
    assert quarantined == []
    for entry in quarantined:
        assert entry["owner"]
        assert entry["verification"]
        assert entry["current_state"] == "legacy_path_explicitly_quarantined"


def test_dispatch_mode_report_marks_persistent_daemon_legacy_default(tmp_path, monkeypatch):
    mod = _load_report_module()
    user_plist = tmp_path / "user.plist"
    repo_plist = tmp_path / "repo.plist"
    user_plist.write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && dgc orchestrate-live",
            ],
            "EnvironmentVariables": {"PATH": "/usr/bin:/bin"},
        })
    )
    monkeypatch.setattr(mod, "_USER_LAUNCH_PLIST", user_plist)
    monkeypatch.setattr(mod, "_REPO_LAUNCH_PLIST", repo_plist)

    report = mod.build_report(env={})

    assert (
        report["summary"]["orchestrator_persistent_daemon"]
        == "legacy_default_launch_spec"
    )
    launch_entry = next(
        entry
        for entry in report["entries"]
        if entry["surface"] == "orchestrator.persistent-daemon"
    )
    assert "DHARMA_SPINE_DISPATCH" in launch_entry["evidence"]


def test_dispatch_mode_report_marks_persistent_daemon_spine_launch_spec(tmp_path, monkeypatch):
    mod = _load_report_module()
    user_plist = tmp_path / "user.plist"
    repo_plist = tmp_path / "repo.plist"
    user_plist.write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && exec env PYTHONPATH=/Users/dhyana/dharma_swarm TINY_ROUTER_BACKEND=heuristic ./.venv/bin/python -m dharma_swarm.dgc_cli orchestrate-live",
            ],
            "EnvironmentVariables": {
                "DHARMA_SPINE_DISPATCH": "1",
                "PATH": "/usr/bin:/bin",
            },
        })
    )
    monkeypatch.setattr(mod, "_USER_LAUNCH_PLIST", user_plist)
    monkeypatch.setattr(mod, "_REPO_LAUNCH_PLIST", repo_plist)

    report = mod.build_report(env={})

    assert (
        report["summary"]["orchestrator_persistent_daemon"]
        == "spine_enabled_launch_spec"
    )
    launch_entry = next(
        entry
        for entry in report["entries"]
        if entry["surface"] == "orchestrator.persistent-daemon"
    )
    assert launch_entry["risk"] == "low"
    assert "repo-pinned" in launch_entry["evidence"]


def test_dispatch_mode_report_marks_ambient_dgc_spine_launch_unblessed(
    tmp_path, monkeypatch
):
    mod = _load_report_module()
    user_plist = tmp_path / "user.plist"
    repo_plist = tmp_path / "repo.plist"
    user_plist.write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && dgc orchestrate-live",
            ],
            "EnvironmentVariables": {
                "DHARMA_SPINE_DISPATCH": "1",
                "PATH": "/usr/bin:/bin",
            },
        })
    )
    monkeypatch.setattr(mod, "_USER_LAUNCH_PLIST", user_plist)
    monkeypatch.setattr(mod, "_REPO_LAUNCH_PLIST", repo_plist)

    report = mod.build_report(env={})

    assert (
        report["summary"]["orchestrator_persistent_daemon"]
        == "ambient_dgc_spine_launch_spec"
    )
    assert report["summary"]["score_gate_65_to_70"] is False
    launch_entry = next(
        entry
        for entry in report["entries"]
        if entry["surface"] == "orchestrator.persistent-daemon"
    )
    assert launch_entry["risk"] == "medium"
    assert "ambient dgc console script" in launch_entry["evidence"]


def test_dispatch_mode_report_exposes_direct_agent_runner_callers():
    mod = _load_report_module()

    report = mod.build_report(env={})
    entries = report["entries"]
    direct = [entry for entry in entries if entry["mode"] == "legacy_direct_runner"]
    wrapped = [entry for entry in entries if entry["mode"] == "spine_wrapped_direct_runner"]
    manual = [entry for entry in entries if entry["mode"] == "manual_live_script"]
    manual_wrapped = [entry for entry in entries if entry["mode"] == "manual_live_spine_wrapped"]

    assert report["summary"]["agent_runner_legacy_direct"] == 0
    assert report["summary"]["agent_runner_spine_wrapped"] >= 1
    assert report["summary"]["agent_runner_manual_scripts"] == 0
    assert report["summary"]["agent_runner_manual_spine_wrapped"] == 5
    assert report["summary"]["production_direct_runner_clear"] is True
    assert report["summary"]["manual_direct_runner_clear"] is True
    assert report["summary"]["score_gate_65_to_70"] is True
    assert direct == []
    assert any(entry["file"] == "dharma_swarm/thinkodynamic_director.py" for entry in wrapped)
    assert all(entry["risk"] == "low" for entry in wrapped)
    assert manual == []
    assert all(
        entry["current_state"] == "manual_operator_script_spine_wrapped_not_default_daemon"
        for entry in manual_wrapped
    )
