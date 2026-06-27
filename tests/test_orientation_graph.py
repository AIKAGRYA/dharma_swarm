"""Tests for scripts/governance/orientation_graph.py — read-only projection."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/orientation_graph.py"

spec = importlib.util.spec_from_file_location("orientation_graph", SCRIPT)
og = importlib.util.module_from_spec(spec)
sys.modules["orientation_graph"] = og
spec.loader.exec_module(og)


def _fresh_generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_packet_has_all_axes():
    packet = og.build_packet()
    data = og.asdict(packet)
    assert set(data) == {"identity", "organs", "tracks", "custody",
                         "liveness", "broken"}


def test_identity_serves_the_one_line():
    identity = og.build_identity()
    assert "dharma_swarm" in identity.one_line
    assert "foundations/THE_ORGANISM.md" in identity.read_first
    assert "docs/vision_maps/NORTH_STAR.md" in identity.read_first


def test_organs_project_from_portfolio_owner():
    organs = og.build_organs()
    assert organs, "portfolio owner should yield at least one organ"
    ids = {o.id for o in organs}
    assert "darshan-publication" in ids


def test_tracks_project_from_active_track_owner():
    tracks = og.build_tracks()
    assert tracks, "ACTIVE_TRACK.yaml should yield at least one active track"
    assert all(t.serves for t in tracks)


def test_runtime_spine_track_projects_readiness_cap():
    tracks = {track.id: track for track in og.build_tracks()}
    track = tracks["runtime-truth-spine-adoption-2026-06"]
    assert "baseline=54/100" in track.readiness
    assert "current=70/100" in track.readiness
    assert "cap=70/100" in track.readiness
    assert "rejected=88/100 production-ready" in track.readiness


def test_track_readiness_ignores_scoped_post_gate_prose():
    readiness = og._format_track_readiness({
        "readiness_baseline": {
            "score": 54,
            "scale": 100,
            "claim_rejected": "88/100 production-ready",
        },
        "hardening_status": {
            "current_score": 70,
            "scale": 100,
            "evidence_ref": "reports/governance/runtime.md",
            "gates_passed": [
                "54_to_60: first executable gate passed",
                "60_to_65: second executable gate passed",
                "65_to_70: third executable gate passed",
                "post_70_note: mentions 70->75 but does not pass it",
            ],
        },
    })
    assert "current=70/100" in readiness
    assert "cap=70/100" in readiness
    assert "cap=75/100" not in readiness
    assert "rejected=88/100 production-ready" in readiness


def test_custody_counts_registered_canon():
    custody = og.build_custody()
    assert custody.registered_total > 0
    assert custody.present + len(custody.missing) == custody.registered_total


def test_liveness_projects_daemon_dispatch_without_env_dump(tmp_path, monkeypatch):
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text(
        json.dumps({
            "schema_version": "live_ops_census.v1",
            "generated_at": _fresh_generated_at(),
            "surfaces": [
                {
                    "id": "substrate.dharma_daemon",
                    "label": "Dharma Swarm daemon",
                    "status": "live",
                    "raw": {
                        "dispatch_launch": {
                            "state": "spine_enabled_launch_spec",
                        },
                        "running_dispatch_proof": (
                            "not_inspected_no_secret_env_dump"
                        ),
                        "runtime_receipt_active_head": {
                            "active_head_side_effect_key_clean": False,
                            "runtime_receipts_total": 7657,
                            "latest_created_at": (
                                "2026-06-13T22:29:48.795782+00:00"
                            ),
                            "latest_age_hours": 7.4,
                            "latest_max_age_hours": 6.0,
                            "latest_fresh": False,
                            "windows": [
                                {
                                    "window_minutes": 5,
                                    "total": 56,
                                    "missing_side_effect_key": 56,
                                },
                                {
                                    "window_minutes": 15,
                                    "total": 60,
                                    "missing_side_effect_key": 60,
                                },
                            ],
                        },
                        "runtime_receipt_coverage": {
                            "latest_sample_size": 250,
                            "latest_with_provider_model_payload": 0,
                            "latest_major_task_receipts_provider_model_percent": 0.0,
                            "provider_model_latest_complete": False,
                            "field_gap_producer_groups": [
                                {
                                    "gap_type": "mission_payload",
                                    "receipt_type": "delegation_run",
                                    "producer_source": "orchestrator",
                                    "producer_failure_code": "execution_error",
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
                                    "action": (
                                        "repair_or_quarantine_orchestrator_error_receipts"
                                    ),
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
                        },
                    },
                },
                {
                    "id": "cli.ds_goal",
                    "label": "ds-goal runtime CLI",
                    "status": "live",
                    "proof_gaps": ["ds_goal_cli_target_repo_mismatch"],
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
                        },
                        "longrun_preflight_gate": {
                            "status": "blocked_unpinned_default_target",
                        },
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)

    liveness = og.build_liveness()

    assert liveness.surfaces[0]["id"] == "substrate.dharma_daemon"
    assert liveness.daemon_dispatch_launch == "spine_enabled_launch_spec"
    assert liveness.daemon_dispatch_running == (
        "not_inspected_no_secret_env_dump"
    )
    assert liveness.daemon_receipt_head == (
        "clean=false; fresh=false; age_hours=7.4; max_age_hours=6.0; "
        "total=7657; latest=2026-06-13T22:29:48.795782+00:00; "
        "windows=5m:56/56,15m:60/60"
    )
    assert liveness.daemon_provider_model_coverage == (
        "latest=0/250; percent=0.0; proof=0/250; proof_percent=unknown; "
        "accounted=0/250; accounted_percent=unknown; "
        "terminal=0/0; terminal_percent=unknown; terminal_proof=0/0; "
        "terminal_proof_percent=unknown; terminal_accounted=0/0; "
        "terminal_accounted_percent=unknown; pending=0; complete=false; "
        "field_gap_producers=mission_payload/delegation_run/orchestrator/"
        "execution_error=7@recent_historical_24h; "
        "field_gap_summary=total:7|recent_historical_24h:7|"
        "quarantine_candidate:7; field_gap_actions=orchestrator_error:7; "
        "field_gap_proofs=orchestrator_error:fresh; "
        "gate_70_75=core:fail|idempotency:fail|mission:fail|artifact:fail|"
        "active_head:fail"
    )
    assert liveness.ds_goal_wrapper_contract == (
        "target=/Users/dhyana/dharma_swarm_main; "
        "source=installed_wrapper_dharma_swarm_main_preference; "
        "default=/Users/dhyana/dharma_swarm_main; "
        "matches_current=false; wrapper_sha256=abc123def456; "
        "pin=true; hardening=sync_receipt_side_effect_keys_missing; "
        "decision=operator_approval_required; "
        "preflight=blocked_unpinned_default_target; "
        "safe=DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
        "/Users/dhyana/.dharma/bin/ds-goal"
    )
    assert liveness.surfaces[0]["proof_gaps"] == [
        "daemon_dispatch_runtime_unproven",
        "daemon_runtime_receipts_active_head_dirty",
        "daemon_runtime_receipts_stale",
    ]


def test_liveness_projects_dashboard_proof_gaps_from_census(tmp_path, monkeypatch):
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text(
        json.dumps({
            "schema_version": "live_ops_census.v1",
            "generated_at": _fresh_generated_at(),
            "surfaces": [
                {
                    "id": "dashboard.local",
                    "label": "Dashboard API and web",
                    "status": "live",
                    "raw": {
                        "control_surface_rows_probe": {
                            "state": "timeout",
                        },
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)

    liveness = og.build_liveness()

    assert liveness.surfaces[0]["id"] == "dashboard.local"
    assert liveness.surfaces[0]["proof_gaps"] == [
        "dashboard_control_surface_rows_unproven"
    ]


def test_liveness_rejects_schema_invalid_census(tmp_path, monkeypatch):
    receipt = tmp_path / "live_process_census.json"
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)

    liveness = og.build_liveness()

    assert liveness.surfaces == []
    assert liveness.generated_at == ""
    assert liveness.receipt.startswith(f"invalid receipt at {receipt}: ")
    assert "schema_version is missing" in liveness.receipt
    assert "surfaces is missing or not a list" in liveness.receipt


def test_liveness_flags_stale_valid_census(tmp_path, monkeypatch):
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
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)

    liveness = og.build_liveness()

    assert liveness.surfaces == []
    assert liveness.generated_at == "2000-01-01T00:00:00Z"
    assert liveness.receipt.startswith(f"stale receipt at {receipt}: ")
    assert "older than 24h" in liveness.receipt


def test_orientation_graph_render_is_read_only(tmp_path):
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True).stdout
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert result.returncode == 0
    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True).stdout
    assert before == after, "orientation graph must not write owner files"


def test_json_mode_is_machine_parseable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "identity" in payload and "organs" in payload


def test_orientation_subprocess_validates_census_from_repo_root_import_path(
    tmp_path,
):
    state = tmp_path / "state"
    receipt = state / "ops" / "live_process_census.json"
    generated_at = _fresh_generated_at()
    receipt.parent.mkdir(parents=True)
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
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "DHARMA_STATE_DIR": str(state)},
    )

    assert result.returncode == 0
    assert "Receipt: " + str(receipt) in result.stdout
    assert f"Generated: {generated_at}" in result.stdout
    assert "No module named 'scripts'" not in result.stdout
