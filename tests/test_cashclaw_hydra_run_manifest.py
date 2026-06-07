from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _manifest_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "revenue" / "cashclaw_hydra_run_manifest.py"
    spec = importlib.util.spec_from_file_location("cashclaw_hydra_run_manifest", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_manifest_records_boundaries_and_artifact_map(tmp_path, monkeypatch):
    manifest_mod = _manifest_module()
    source_config = tmp_path / "source_config.json"
    source_config.write_text(json.dumps({"sources": [{"source_config_id": "github"}]}) + "\n", encoding="utf-8")
    (tmp_path / "objective_audit.json").write_text(
        json.dumps(
            {
                "status": "running_or_incomplete",
                "complete": False,
                "requirements": [
                    {"requirement": "loop_launched", "passed": True},
                    {"requirement": "overnight_duration", "passed": False},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps(
            {
                "status": "draft_only_not_granted",
                "external_side_effects_performed": False,
                "requests": [{"lease_id": "lease-1"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "watchdog_status.json").write_text(json.dumps({"alerts": []}) + "\n", encoding="utf-8")
    (tmp_path / "summaries.json").write_text(json.dumps([{"cycle": 1, "timestamp": "2026-05-31T09:00:00+00:00"}]) + "\n", encoding="utf-8")
    monkeypatch.setattr(manifest_mod, "_matching_processes", lambda _: ["123 cashclaw_revenue_hydra.py --run-root x"])

    manifest = manifest_mod.build_run_manifest(
        run_root=tmp_path,
        source_config=source_config,
        process_substring="cashclaw_revenue_hydra.py",
    )
    manifest_mod.write_run_manifest(tmp_path, manifest)
    markdown = (tmp_path / "run_manifest.md").read_text(encoding="utf-8")

    assert manifest["hydra_process_running"] is True
    assert manifest["objective_holds"] == ["overnight_duration"]
    assert manifest["lease_status"] == "draft_only_not_granted"
    assert manifest["lease_request_count"] == 1
    assert manifest["source_count"] == 1
    assert manifest["source_config_sha256"]
    assert manifest["no_external_side_effects"] is True
    assert any("Do not send outreach" in item for item in manifest["forbidden_actions"])
    assert "lease_packet_quality_audit" in manifest["artifact_map"]
    assert any("lease_packet_quality_audit passes" in item for item in manifest["completion_criteria"])
    assert "CashClaw Hydra Run Manifest" in markdown
    assert "Completion Criteria" in markdown
    assert (tmp_path / "run_manifest.json").exists()


def test_run_manifest_uses_watchdog_process_fallback_when_pgrep_blocked(tmp_path, monkeypatch):
    manifest_mod = _manifest_module()
    (tmp_path / "objective_audit.json").write_text(
        json.dumps({"status": "running_or_incomplete", "complete": False, "requirements": []}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps({"status": "draft_only_not_granted", "external_side_effects_performed": False, "requests": []}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "watchdog_status.json").write_text(
        json.dumps({"alerts": [], "matching_processes": ["321 cashclaw_revenue_hydra.py --run-root y"]}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "summaries.json").write_text(json.dumps([]) + "\n", encoding="utf-8")
    monkeypatch.setattr(manifest_mod, "_matching_processes", lambda _: [])

    manifest = manifest_mod.build_run_manifest(
        run_root=tmp_path,
        source_config=None,
        process_substring="cashclaw_revenue_hydra.py",
    )

    assert manifest["hydra_process_running"] is True
    assert manifest["active_processes"] == ["321 cashclaw_revenue_hydra.py --run-root y"]
