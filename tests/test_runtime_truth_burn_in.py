from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def _load_burn_in_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "runtime_truth_burn_in.py"
    )
    spec = importlib.util.spec_from_file_location("runtime_truth_burn_in", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample(*, passed: bool = True) -> dict:
    checks = [
        {
            "id": "daemon_unpaused",
            "status": "pass" if passed else "fail",
            "passed": passed,
            "evidence": "pause_present=false",
        }
    ]
    return {
        "schema_version": "runtime_truth_closeout.v1",
        "status": "pass" if passed else "fail",
        "passed": passed,
        "scope": {
            "mode": "since_created_at",
            "since_created_at": "2026-06-18T18:18:59+00:00",
            "epoch_receipt_id": "rr-runtime-truth-clean-epoch",
        },
        "checks": checks
        if not passed
        else [
            {
                "id": "daemon_unpaused",
                "status": "pass",
                "passed": True,
                "evidence": "pause_present=false",
            }
        ],
    }


def test_burn_in_report_marks_strict_unpaused_proof() -> None:
    module = _load_burn_in_module()
    now = datetime(2026, 6, 18, 18, 30, tzinfo=UTC)

    report = module.build_burn_in_report(
        [_sample(), _sample()],
        started_at=now,
        completed_at=now,
        allow_paused=False,
        requested_duration_seconds=120.0,
        interval_seconds=60.0,
        min_samples=2,
    )

    assert report["status"] == "pass"
    assert report["mode"] == "strict_unpaused"
    assert report["strict_unpaused_proven"] is True
    assert report["sample_count_met"] is True
    assert report["failed_samples"] == []


def test_burn_in_report_paused_smoke_is_not_strict_proof() -> None:
    module = _load_burn_in_module()
    now = datetime(2026, 6, 18, 18, 30, tzinfo=UTC)

    report = module.build_burn_in_report(
        [_sample()],
        started_at=now,
        completed_at=now,
        allow_paused=True,
        requested_duration_seconds=0.0,
        interval_seconds=0.0,
        min_samples=1,
    )

    assert report["status"] == "pass"
    assert report["mode"] == "paused_smoke"
    assert report["strict_unpaused_proven"] is False


def test_burn_in_report_fails_failed_samples() -> None:
    module = _load_burn_in_module()
    now = datetime(2026, 6, 18, 18, 30, tzinfo=UTC)

    report = module.build_burn_in_report(
        [_sample(passed=False)],
        started_at=now,
        completed_at=now,
        allow_paused=False,
        requested_duration_seconds=0.0,
        interval_seconds=0.0,
        min_samples=1,
    )

    assert report["status"] == "fail"
    assert report["strict_unpaused_proven"] is False
    assert report["failed_samples"] == [
        {
            "sample": 1,
            "status": "fail",
            "failed_checks": ["daemon_unpaused"],
        }
    ]


def test_write_report_writes_json_atomically(tmp_path: Path) -> None:
    module = _load_burn_in_module()
    path = tmp_path / "ops" / "runtime_truth_burn_in_latest.json"
    report = {
        "schema_version": "runtime_truth_burn_in.v1",
        "status": "pass",
    }

    module.write_report(path, report)

    assert json.loads(path.read_text(encoding="utf-8")) == report
