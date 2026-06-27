from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def _load_audit_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "runtime_truth_100_audit.py"
    )
    spec = importlib.util.spec_from_file_location("runtime_truth_100_audit", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_burn_in_duration_gate_requires_strict_unpaused_min_duration() -> None:
    module = _load_audit_module()
    report = {
        "passed": True,
        "strict_unpaused_proven": True,
        "requested_duration_seconds": 300.0,
        "sample_count_met": True,
        "all_samples_passed": True,
        "sample_count": 6,
        "min_samples": 5,
    }

    passed, evidence = module._burn_in_duration_evidence(
        report,
        min_duration_seconds=7200.0,
    )

    assert passed is False
    assert "duration=300/7200" in evidence


def test_burn_in_duration_gate_accepts_complete_strict_report() -> None:
    module = _load_audit_module()
    report = {
        "passed": True,
        "strict_unpaused_proven": True,
        "requested_duration_seconds": 7200.0,
        "sample_count_met": True,
        "all_samples_passed": True,
        "sample_count": 25,
        "min_samples": 25,
    }

    passed, evidence = module._burn_in_duration_evidence(
        report,
        min_duration_seconds=7200.0,
    )

    assert passed is True
    assert "samples=25/25" in evidence


def test_burn_in_duration_gate_rejects_stale_report() -> None:
    module = _load_audit_module()
    report = {
        "passed": True,
        "strict_unpaused_proven": True,
        "requested_duration_seconds": 7200.0,
        "sample_count_met": True,
        "all_samples_passed": True,
        "sample_count": 25,
        "min_samples": 25,
        "completed_at": "2026-06-18T00:00:00+00:00",
    }

    passed, evidence = module._burn_in_duration_evidence(
        report,
        min_duration_seconds=7200.0,
        max_age_hours=24.0,
        now=datetime(2026, 6, 20, 0, 0, tzinfo=UTC),
    )

    assert passed is False
    assert "age_hours=48.00/24" in evidence


def test_dashboard_runtime_truth_extracts_nested_health_payload() -> None:
    module = _load_audit_module()
    payload = {
        "status": "ok",
        "data": {
            "overall_status": "healthy",
            "runtime_truth": {
                "status": "pass",
                "passed": True,
            },
        },
    }

    assert module._dashboard_runtime_truth(payload) == {
        "status": "pass",
        "passed": True,
    }


def test_find_latest_report_uses_runtime_truth_report_dir(tmp_path: Path) -> None:
    module = _load_audit_module()
    report_dir = tmp_path / "reports" / "runtime_truth"
    report_dir.mkdir(parents=True)
    older = report_dir / "runtime_truth_burn_in_2h_20260618T200000Z.json"
    newer = report_dir / "runtime_truth_burn_in_2h_20260618T210000Z.json"
    older.write_text(json.dumps({"name": "older"}), encoding="utf-8")
    newer.write_text(json.dumps({"name": "newer"}), encoding="utf-8")

    older.touch()
    newer.touch()

    assert module._find_latest_report(
        tmp_path,
        "runtime_truth_burn_in_2h_*.json",
    ) == newer
