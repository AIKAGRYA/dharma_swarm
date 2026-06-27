from __future__ import annotations

import argparse
import importlib.util
import sqlite3
from pathlib import Path


def _load_status_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "runtime" / "daemon_operator_status.py"
    spec = importlib.util.spec_from_file_location("daemon_operator_status", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        census=str(tmp_path / "census.json"),
        log=str(tmp_path / "swarm.log"),
        health_url="http://127.0.0.1:7433/health",
        launchd_label="gui/501/com.dharma.swarm",
        refresh_census=False,
        show_process=False,
    )


def _write_tasks_db(
    state_root: Path,
    *,
    rows: list[tuple[str, str, int]] | None = None,
) -> None:
    db_path = state_root / "db" / "tasks.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                priority TEXT NOT NULL
            )
            """
        )
        index = 0
        for status, priority, count in rows or []:
            for _ in range(count):
                index += 1
                db.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?)",
                    (f"task-{index}", status, priority),
                )


def _patch_common_runtime(
    monkeypatch,
    status_module,
    tmp_path: Path,
    daemon: dict,
    *,
    tasks_rows: list[tuple[str, str, int]] | None = None,
) -> None:
    census = {
        "summary": {"by_status": {"live": 1}, "proof_gap_surfaces": 0},
        "surfaces": [daemon],
    }
    _write_tasks_db(tmp_path, rows=tasks_rows)
    monkeypatch.setattr(status_module, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(
        status_module,
        "fetch_health",
        lambda _url: {
            "status": "ok",
            "uptime": 12.5,
            "daemon_pid": 1234,
            "health_process_pid": 1235,
            "runtime_dispatch": {"spine_dispatch_enabled": True},
        },
    )
    monkeypatch.setattr(
        status_module,
        "launchd_state",
        lambda _label: {
            "state": "running",
            "pid": "1234",
            "runs": "1",
            "last_exit_code": "0",
        },
    )
    monkeypatch.setattr(status_module, "load_json", lambda _path: census)
    monkeypatch.setattr(
        status_module,
        "log_summary",
        lambda _path: {
            "latest_tick": {
                "tick": "9",
                "dispatched": "2",
                "ready": "3",
                "blocked": "0",
                "seconds": "0.4",
            },
            "latest_pause": "",
            "latest_ancillary": "",
            "token_budget_blocks": "0",
            "rate_limits": "0",
            "credit_balance_errors": "0",
        },
    )
    monkeypatch.setattr(
        status_module,
        "git_state",
        lambda: {
            "branch": "test-branch",
            "dirty_entries": "0",
            "origin_main_divergence": "0\t0",
        },
    )
    monkeypatch.setattr(status_module, "ps_for_health", lambda _health: "")


def _ready_daemon() -> dict:
    return {
        "id": "substrate.dharma_daemon",
        "status": "live",
        "proof_state": "verified",
        "proof_gaps": [],
        "raw": {
            "dispatch_launch": {
                "state": "spine_enabled_launch_spec",
                "repo_module_invocation": True,
                "ambient_dgc_invocation": False,
                "evidence": "launch spec declares DHARMA_SPINE_DISPATCH=1 and invokes repo-pinned dharma_swarm.dgc_cli module",
            },
            "process_source_state": {"state": "runtime", "evidence": "test"},
            "runtime_receipt_coverage": {
                "coverage_report_available": True,
                "latest_sample_size": 10,
                "latest_major_task_receipts_provider_model_percent": 100.0,
                "latest_terminal_sample_size": 10,
                "latest_terminal_major_task_receipts_provider_model_percent": 100.0,
                "provider_model_readiness_basis": "latest",
                "provider_model_latest_complete": True,
                "active_head_clean": True,
                "latest_fresh": True,
                "production_readiness_blockers": [],
            },
            "runtime_receipt_active_head": {
                "active_head_side_effect_key_clean": True,
                "latest_fresh": True,
            },
            "runtime_receipt_since_boot": {
                "process_started_at": "2026-06-18T14:00:00Z",
                "since_boot_major_identity_clean": True,
                "major_since_boot_total": 2,
                "missing_side_effect_key": 0,
                "missing_idempotency_key": 0,
            },
            "runtime_truth_clean_epoch": {
                "exists": False,
                "enabled": False,
                "since_created_at": "",
                "receipt_id": "",
                "evidence": "runtime truth clean epoch file not found",
            },
        },
    }


def test_print_status_returns_zero_when_runtime_truth_ready(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    _patch_common_runtime(monkeypatch, status_module, tmp_path, _ready_daemon())

    assert status_module.print_status(_args(tmp_path)) == 0
    output = capsys.readouterr().out
    assert "launch_spec: state=spine_enabled_launch_spec repo_module=True" in output
    assert "ambient_dgc=False" in output
    assert "unpaused_burn_in_preflight: safe=True" in output
    assert "runtime_readiness_failures:" not in output


def test_print_status_returns_nonzero_for_runtime_truth_gaps(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    daemon = _ready_daemon()
    daemon["proof_gaps"] = ["daemon_runtime_provider_model_latest_incomplete"]
    coverage = daemon["raw"]["runtime_receipt_coverage"]
    coverage["provider_model_latest_complete"] = False
    coverage["production_readiness_blockers"] = ["provider_model_latest_incomplete"]
    active_head = daemon["raw"]["runtime_receipt_active_head"]
    active_head["active_head_side_effect_key_clean"] = False
    since_boot = daemon["raw"]["runtime_receipt_since_boot"]
    since_boot["since_boot_major_identity_clean"] = False
    since_boot["missing_side_effect_key"] = 1
    _patch_common_runtime(monkeypatch, status_module, tmp_path, daemon)

    assert status_module.print_status(_args(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "runtime_readiness_failures:" in output
    assert "proof_gap:daemon_runtime_provider_model_latest_incomplete" in output
    assert "provider_model_latest_incomplete" in output
    assert "runtime_receipt_active_head_side_effect_key_dirty" in output
    assert "runtime_receipt_since_boot_side_effect_key_dirty" in output


def test_print_status_returns_nonzero_when_pause_file_present(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    (tmp_path / ".PAUSE").write_text("operator hold\n", encoding="utf-8")
    _patch_common_runtime(monkeypatch, status_module, tmp_path, _ready_daemon())

    assert status_module.print_status(_args(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "pause: state=paused_by_file" in output
    assert "daemon_pause_file_present" in output


def test_print_status_returns_nonzero_when_burn_in_preflight_is_unsafe(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    _patch_common_runtime(
        monkeypatch,
        status_module,
        tmp_path,
        _ready_daemon(),
        tasks_rows=[
            ("pending", "high", 26),
            ("pending", "normal", 75),
            ("running", "normal", 1),
        ],
    )

    assert status_module.print_status(_args(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "unpaused_burn_in_preflight: safe=False" in output
    assert "pending_high_or_urgent=26" in output
    assert "pending_total=101" in output
    assert "unpaused_burn_in_preflight_unsafe" in output


def test_print_status_refreshes_census_when_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    _patch_common_runtime(monkeypatch, status_module, tmp_path, _ready_daemon())
    calls: list[Path] = []
    monkeypatch.setattr(status_module, "refresh_census", lambda path: calls.append(path))
    args = _args(tmp_path)
    args.refresh_census = True

    assert status_module.print_status(args) == 0
    assert calls == [tmp_path / "census.json"]


def test_print_status_can_skip_census_refresh(
    monkeypatch,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    _patch_common_runtime(monkeypatch, status_module, tmp_path, _ready_daemon())
    calls: list[Path] = []
    monkeypatch.setattr(status_module, "refresh_census", lambda path: calls.append(path))
    args = _args(tmp_path)
    args.refresh_census = False

    assert status_module.print_status(args) == 0
    assert calls == []


def test_print_status_reports_invalid_runtime_truth_clean_epoch(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    status_module = _load_status_module()
    daemon = _ready_daemon()
    daemon["raw"]["runtime_truth_clean_epoch"] = {
        "exists": True,
        "enabled": False,
        "since_created_at": "not-a-date",
        "receipt_id": "rr-bad-epoch",
        "evidence": "runtime truth clean epoch since_created_at is missing or invalid",
    }
    _patch_common_runtime(monkeypatch, status_module, tmp_path, daemon)

    assert status_module.print_status(_args(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "runtime_truth_clean_epoch: enabled=False" in output
    assert "runtime_truth_clean_epoch_invalid" in output
