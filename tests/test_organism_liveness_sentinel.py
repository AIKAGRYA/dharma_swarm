"""The organism liveness sentinel must fail loudly, write receipts, and
stay silent on --dry-run."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.runtime.organism_liveness_sentinel as sentinel
from scripts.runtime.organism_liveness_sentinel import CheckResult, run_sentinel


def _ok(name: str) -> CheckResult:
    return CheckResult(name=name, ok=True, detail="ok")


def _patch_healthy(monkeypatch) -> None:
    monkeypatch.setattr(
        sentinel, "check_launchd_service", lambda label=None: _ok("launchd_service")
    )
    monkeypatch.setattr(
        sentinel, "check_orchestrate_process", lambda pid: _ok("orchestrate_process")
    )


def test_all_green_writes_baseline_and_exits_zero(monkeypatch, tmp_path: Path) -> None:
    _patch_healthy(monkeypatch)
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("admission denied: x\n" * 3, encoding="utf-8")

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 0
    baseline = tmp_path / "witness" / "liveness_sentinel" / "denial_baseline.json"
    assert json.loads(baseline.read_text())["denial_count"] == 3
    receipts = list((tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*"))
    assert receipts == []


def test_denial_growth_fails_loudly_with_receipt(monkeypatch, tmp_path: Path) -> None:
    _patch_healthy(monkeypatch)
    sentinel_dir = tmp_path / "witness" / "liveness_sentinel"
    sentinel_dir.mkdir(parents=True)
    (sentinel_dir / "denial_baseline.json").write_text(
        json.dumps({"denial_count": 3}), encoding="utf-8"
    )
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("admission denied: x\n" * 588, encoding="utf-8")

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 1
    receipts = list(sentinel_dir.glob("ORGANISM_DOWN_*.json"))
    assert len(receipts) == 1
    payload = json.loads(receipts[0].read_text())
    assert payload["verdict"] == "ORGANISM_DOWN"
    denial_check = next(
        c for c in payload["checks"] if c["name"] == "admission_denials"
    )
    assert denial_check["ok"] is False
    assert denial_check["evidence"]["denial_count"] == 588


def test_dead_service_fails_and_writes_receipt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service", ok=False, detail="service NOT loaded"
        ),
    )
    monkeypatch.setattr(
        sentinel,
        "check_orchestrate_process",
        lambda pid: CheckResult(
            name="orchestrate_process", ok=False, detail="no live process"
        ),
    )

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 1
    receipts = list(
        (tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*.json")
    )
    assert len(receipts) == 1


def test_dry_run_writes_nothing_but_reports_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service", ok=False, detail="service NOT loaded"
        ),
    )
    monkeypatch.setattr(
        sentinel,
        "check_orchestrate_process",
        lambda pid: CheckResult(
            name="orchestrate_process", ok=False, detail="no live process"
        ),
    )

    rc = run_sentinel(state_root=tmp_path, dry_run=True)

    assert rc == 1
    assert not (tmp_path / "witness").exists()
