from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _sidecar_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "revenue" / "cashclaw_local_executor_sidecar.py"
    spec = importlib.util.spec_from_file_location("cashclaw_local_executor_sidecar", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sidecar_packet_stages_local_only_work_order(tmp_path):
    sidecar = _sidecar_module()
    request = {
        "lease_id": "revenue-lease-001-a1",
        "rank": 1,
        "lease_stage": "local_delivery_only",
        "action_id": "a1",
        "title": "Bounty one",
        "buyer": "buyer/repo",
        "source_url": "https://github.com/buyer/repo/issues/1",
        "proposed_price_usd": 100,
        "risk_flags": [],
        "delivery_plan": "/tmp/a1/delivery_plan.md",
        "source_scope_snapshot": "/tmp/a1/source_scope_snapshot.md",
        "lease_preflight": "/tmp/a1/lease_preflight.json",
    }

    packet = sidecar.build_sidecar_packet(run_root=tmp_path, request=request)

    assert packet["schema_version"] == "cashclaw_local_executor_sidecar.v1"
    assert packet["external_side_effects_performed"] is False
    assert packet["killshot_quality_gate"]["status"] == "not_run"
    assert packet["next_node"] == "LocalExecutorSidecar"
    assert any("Do not claim" in item for item in packet["forbidden_actions"])
    assert "training/acceptance_matrix.json" in packet["required_outputs"]


def test_sidecar_packet_evaluates_episode_and_writes_receipts(tmp_path):
    sidecar = _sidecar_module()
    request = {
        "lease_id": "revenue-lease-001-a1",
        "rank": 1,
        "lease_stage": "local_delivery_only",
        "action_id": "a1",
        "title": "Bounty one",
        "buyer": "buyer/repo",
        "source_url": "https://github.com/buyer/repo/issues/1",
        "proposed_price_usd": 100,
        "risk_flags": [],
    }
    episode = {
        "execution": {"external_side_effects_performed": False},
        "deliverable": {"acceptance_criteria_coverage": {"docs": "pass", "tests": "missing"}},
        "verification": {
            "git_diff_check": "pass",
            "conflict_marker_scan": "pass",
            "docker_test": {"status": "pass", "result": "1 tests, 0 failures"},
        },
        "scorecard": {
            "implementation_quality_0_100": 70,
            "test_quality_0_100": 70,
            "commercial_readiness_0_100": 70,
            "submission_readiness_0_100": 70,
            "overall_episode_quality_0_100": 70,
        },
    }

    packet = sidecar.build_sidecar_packet(run_root=tmp_path, request=request, episode=episode)
    sidecar.write_sidecar_packet(packet)

    assert packet["killshot_quality_gate"]["status"] == "iterate"
    assert packet["next_node"] == "KillshotIterationLoop"
    assert (tmp_path / "local_executor" / "a1" / "sidecar_work_order.json").exists()
    assert (tmp_path / "local_executor" / "a1" / "training" / "killshot_quality_gate.json").exists()
    written = json.loads((tmp_path / "local_executor" / "a1" / "sidecar_work_order.json").read_text())
    assert written["forbidden_actions"]


def test_select_lease_request_by_rank():
    sidecar = _sidecar_module()
    lease_requests = {
        "requests": [
            {"rank": 1, "lease_id": "one"},
            {"rank": 2, "lease_id": "two"},
        ]
    }

    assert sidecar.select_lease_request(lease_requests, rank=2)["lease_id"] == "two"


def test_sidecar_writes_idle_receipt_when_no_ready_requests(tmp_path):
    sidecar = _sidecar_module()
    lease_requests = {
        "status": "no_ready_requests",
        "requests": [],
    }

    packet = sidecar.build_idle_packet(run_root=tmp_path, rank=1, lease_requests=lease_requests)
    sidecar.write_idle_packet(packet)

    assert packet["status"] == "idle_no_ready_lease_requests"
    assert packet["external_side_effects_performed"] is False
    assert packet["next_node"] == "CashClawHydraScoutLoop"
    assert (tmp_path / "local_executor" / "_idle" / "sidecar_idle.json").exists()
    markdown = (tmp_path / "local_executor" / "_idle" / "sidecar_idle.md").read_text(encoding="utf-8")
    assert "Sidecar Idle" in markdown
