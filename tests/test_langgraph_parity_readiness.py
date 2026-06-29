from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.langgraph_parity.readiness import (
    build_readiness_report,
    write_readiness_report,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_base_reports(root: Path, live_path: Path) -> None:
    _write_json(
        root / "benchmark" / "benchmark_report.json",
        {
            "distractor_domain_count": 8,
            "summary": {
                "multi_hop_task_count": 1,
                "modes": {
                    "single_agent": {},
                    "swarm": {},
                    "supervisor": {},
                },
            },
        },
    )
    _write_json(
        root / "receipts" / "gate_C_runtime_receipt_coverage_fresh_slice_20260629T094800Z.json",
        {
            "summary": {
                "score_gate_70_to_75": True,
                "runtime_receipts_total": 44,
                "major_task_receipts_total": 6,
            }
        },
    )
    _write_json(
        root / "receipts" / "gate_D_spine_dispatch_mode_report.json",
        {
            "summary": {
                "score_gate_65_to_70": True,
                "live_census_state": "proof_gaps_present",
                "live_census_proof_gap_surfaces": 1,
                "orchestrator_current_process": "legacy_default_in_current_process",
                "orchestrator_persistent_daemon": "spine_enabled_launch_spec",
            }
        },
    )
    _write_json(
        live_path,
        {
            "generated_at": "2026-06-29T15:48:34Z",
            "surfaces": [
                {
                    "id": "substrate.dharma_daemon",
                    "status": "stale",
                    "proof_gaps": ["daemon_runtime_provider_model_unproven"],
                    "human_authority_required": True,
                    "next_action": "restart only with operator approval",
                }
            ],
        },
    )


def test_readiness_report_preserves_red_global_runtime_and_maps_blockers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "reports" / "langgraph_parity"
    live_path = tmp_path / "live_process_census.json"
    _write_base_reports(root, live_path)
    _write_json(
        root / "receipts" / "gate_C_runtime_receipt_coverage_report.json",
        {
            "summary": {
                "score_gate_70_to_75": False,
                "runtime_receipts_total": 70116,
                "major_task_receipts_total": 11185,
            },
            "major_task_receipts": {
                "field_gap_action_queue": [
                    {
                        "action": "repair_or_quarantine_orchestrator_error_receipts",
                        "short_label": "orchestrator_error",
                        "disposition": "repair_or_historical_quarantine_required",
                        "owner_surface": "orchestrator",
                        "missing": 5061,
                        "operator_decision_required": True,
                        "fresh_proof": {
                            "remaining_action": (
                                "historical execution_error debt still needs repair "
                                "or operator-approved quarantine"
                            )
                        },
                    }
                ]
            },
        },
    )
    _write_json(
        root / "receipts" / "gate_E_check_a2a_readiness.stdout.txt",
        {
            "ready": False,
            "gate_status": "DEGRADED",
            "open_tasks": 2,
            "unverified_closed_tasks": 1,
            "unknown_status_tasks": 0,
            "blocker_task_id_coverage_complete": True,
            "blocker_task_ids": {
                "open_or_claimed_tasks_present": ["task-a", "task-b"],
                "unverified_closed_tasks_present": ["task-c"],
            },
        },
    )

    report = build_readiness_report(root, live_census_path=live_path)
    data = report.to_dict()

    assert data["ten_out_of_ten"] is False
    blocker_ids = {blocker["id"] for blocker in data["blockers"]}
    assert "runtime.orchestrator-error" in blocker_ids
    assert "a2a.open-or-claimed-tasks-present" not in blocker_ids
    assert "a2a.unverified-closed-tasks-present" not in blocker_ids
    assert "live_ops.substrate-dharma-daemon" in blocker_ids
    runtime_blocker = next(
        blocker
        for blocker in data["blockers"]
        if blocker["id"] == "runtime.orchestrator-error"
    )
    assert runtime_blocker["task_id"] == "lgp-runtime-orchestrator-error"
    assert runtime_blocker["missing_count"] == 5061
    assert runtime_blocker["operator_decision_required"] is True
    live_blocker = next(
        blocker
        for blocker in data["blockers"]
        if blocker["id"] == "live_ops.substrate-dharma-daemon"
    )
    assert live_blocker["operator_decision_required"] is True
    assert live_blocker["evidence"]["human_authority_required"] is True
    assert live_blocker["evidence"]["next_action"] == "restart only with operator approval"
    gate_ids = {gate["id"] for gate in data["gates"]}
    assert {
        "A.swarm_parity",
        "B.supervisor_parity",
        "C.context_tool_isolation",
        "D.benchmark",
        "E1.runtime_receipt_coverage",
        "E2.a2a_readiness",
        "E3.spine_live_ops",
        "E.runtime_truth",
    } <= gate_ids
    gate_runtime = next(
        gate for gate in data["gates"] if gate["id"] == "E1.runtime_receipt_coverage"
    )
    assert gate_runtime["status"] == "red"
    assert "runtime.orchestrator-error" in gate_runtime["blocker_ids"]
    gate_a2a = next(gate for gate in data["gates"] if gate["id"] == "E2.a2a_readiness")
    assert gate_a2a["status"] == "amber"
    assert gate_a2a["passed"] is True
    assert gate_a2a["blocker_ids"] == []
    assert gate_a2a["metrics"]["accepted_degraded"] is True
    assert set(gate_a2a["metrics"]["tracked_blocker_ids"]) == {
        "a2a.open-or-claimed-tasks-present",
        "a2a.unverified-closed-tasks-present",
    }
    gate_spine = next(
        gate for gate in data["gates"] if gate["id"] == "E3.spine_live_ops"
    )
    assert gate_spine["status"] == "amber"
    gate_e = next(gate for gate in data["gates"] if gate["id"] == "E.runtime_truth")
    assert gate_e["status"] == "red"
    assert "runtime.orchestrator-error" in gate_e["blocker_ids"]

    json_path, markdown_path = write_readiness_report(
        report,
        tmp_path / "readiness",
    )
    assert json.loads(json_path.read_text(encoding="utf-8"))["ten_out_of_ten"] is False
    assert "runtime.orchestrator-error" in markdown_path.read_text(encoding="utf-8")


def test_readiness_report_can_turn_green_when_all_inputs_are_green(
    tmp_path: Path,
) -> None:
    root = tmp_path / "reports" / "langgraph_parity"
    live_path = tmp_path / "live_process_census.json"
    _write_base_reports(root, live_path)
    _write_json(
        root / "receipts" / "gate_C_runtime_receipt_coverage_report.json",
        {
            "summary": {
                "score_gate_70_to_75": True,
                "runtime_receipts_total": 10,
                "major_task_receipts_total": 2,
            },
            "major_task_receipts": {"field_gap_action_queue": []},
        },
    )
    _write_json(
        root / "receipts" / "gate_E_check_a2a_readiness.stdout.txt",
        {
            "ready": True,
            "gate_status": "READY",
            "blocker_task_id_coverage_complete": True,
            "blocker_task_ids": {},
        },
    )
    _write_json(
        root / "receipts" / "gate_D_spine_dispatch_mode_report.json",
        {
            "summary": {
                "score_gate_65_to_70": True,
                "live_census_state": "green",
                "live_census_proof_gap_surfaces": 0,
            }
        },
    )
    _write_json(
        live_path,
        {
            "generated_at": "2026-06-29T15:48:34Z",
            "surfaces": [{"id": "substrate.dharma_daemon", "proof_gaps": []}],
        },
    )

    report = build_readiness_report(root, live_census_path=live_path)
    data = report.to_dict()

    assert data["overall_status"] == "green"
    assert data["ten_out_of_ten"] is True
    assert data["blockers"] == []
    assert all(gate["passed"] for gate in data["gates"])
