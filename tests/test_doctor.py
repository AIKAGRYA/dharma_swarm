from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

import pytest
import subprocess

from dharma_swarm.doctor import (
    _check_claude_unattended_auth,
    _check_daemon_integrity,
    _check_dgc_health_snapshot,
    _check_doctor_schedule,
    _check_message_bus_integrity,
    create_doctor_job,
    doctor_exit_code,
    load_latest_doctor_report,
    render_doctor_report,
    run_doctor,
    write_doctor_artifacts,
)


@pytest.fixture(autouse=True)
def _unreadable_pid_commands(monkeypatch):
    """Default `_pid_command` to None so pid probes are host-independent.

    `_daemon_pid_alive` disconfirms a live pid only when the command line is
    readable AND foreign; returning None means "cannot read", which never
    downgrades. Without this, tests using low pid numbers (111, 222, ...)
    would pass or fail depending on what happens to be running on the host.
    Tests that exercise the recycled-pid path override it explicitly.
    """
    monkeypatch.setattr("dharma_swarm.doctor._pid_command", lambda pid: None)


def _create_message_bus_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE messages (id TEXT)")
        conn.execute("CREATE TABLE heartbeats (agent_id TEXT, last_seen TEXT)")
        conn.execute("CREATE TABLE subscriptions (agent_id TEXT, topic TEXT)")
        conn.execute("CREATE TABLE artifacts (id TEXT)")
        conn.execute("CREATE TABLE events (event_id TEXT, consumed_at TEXT)")
        conn.execute("INSERT INTO messages (id) VALUES ('m-1')")
        conn.commit()


def test_doctor_exit_code_matrix() -> None:
    clean = {"summary": {"warn": 0, "fail": 0}}
    warn_only = {"summary": {"warn": 2, "fail": 0}}
    fail_any = {"summary": {"warn": 1, "fail": 1}}

    assert doctor_exit_code(clean, strict=False) == 0
    assert doctor_exit_code(clean, strict=True) == 0
    assert doctor_exit_code(warn_only, strict=False) == 0
    assert doctor_exit_code(warn_only, strict=True) == 1
    assert doctor_exit_code(fail_any, strict=False) == 2
    assert doctor_exit_code(fail_any, strict=True) == 2


def test_run_doctor_quick_report_shape(monkeypatch, tmp_path: Path) -> None:
    launcher = tmp_path / "dgc"
    launcher.write_text("#!/bin/sh\n_bootstrap_env()\n", encoding="utf-8")
    launcher.chmod(0o755)

    monkeypatch.setenv("DGC_ROUTER_REDIS_URL", "redis://127.0.0.1:1")
    monkeypatch.setenv("DGC_FASTTEXT_MODEL_PATH", str(tmp_path / "lid.176.bin"))
    monkeypatch.setenv("DGC_ROUTER_CANARY_PERCENT", "5")
    monkeypatch.setenv("DGC_ROUTER_LEARNING_ENABLED", "1")
    monkeypatch.setattr("dharma_swarm.doctor.shutil.which", lambda _: str(launcher))

    report = run_doctor(timeout_seconds=0.1, quick=True)
    assert isinstance(report, dict)
    assert "status" in report
    assert "summary" in report
    assert "checks" in report
    assert "assurance" in report
    assert "artifacts" in report
    assert report["summary"]["total"] >= 8
    statuses = {entry.get("status") for entry in report["checks"]}
    assert statuses.issubset({"PASS", "WARN", "FAIL"})


@pytest.mark.skipif(
    not (Path.home() / "dharma_swarm" / ".env").exists(),
    reason="Requires local .env file; skipped in CI",
)
def test_env_autoload_passes_for_delegate_launcher(monkeypatch, tmp_path: Path) -> None:
    launcher = tmp_path / "dgc"
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "from dharma_swarm.dgc_cli import main\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    monkeypatch.setattr("dharma_swarm.doctor.shutil.which", lambda _: str(launcher))
    report = run_doctor(timeout_seconds=0.1, quick=True)
    env_check = next(c for c in report["checks"] if c["name"] == "env_autoload")
    assert env_check["status"] == "PASS"


def test_render_doctor_report_contains_header() -> None:
    report = {
        "status": "WARN",
        "summary": {"pass": 3, "warn": 1, "fail": 0},
        "checks": [
            {"name": "env_autoload", "status": "PASS", "summary": "ok", "detail": ""},
            {"name": "redis", "status": "WARN", "summary": "down", "detail": "timeout"},
        ],
        "recommended_fixes": ["Start Redis"],
    }
    text = render_doctor_report(report)
    assert "=== DGC DOCTOR ===" in text
    assert "[PASS] env_autoload: ok" in text
    assert "[WARN] redis: down" in text
    assert "Recommended fixes:" in text


def test_write_and_load_doctor_artifacts(tmp_path: Path) -> None:
    report = {
        "status": "WARN",
        "summary": {"pass": 1, "warn": 1, "fail": 0},
        "checks": [],
        "recommended_fixes": [],
        "assurance": {},
        "artifacts": {},
    }

    artifacts = write_doctor_artifacts(report, output_dir=tmp_path)

    assert Path(artifacts["json"]).exists()
    assert Path(artifacts["markdown"]).exists()
    assert Path(artifacts["history_json"]).exists()
    assert Path(artifacts["history_markdown"]).exists()

    loaded = load_latest_doctor_report(output_dir=tmp_path)
    assert loaded is not None
    assert loaded["status"] == "WARN"


def test_write_doctor_artifacts_populates_generated_at(tmp_path: Path) -> None:
    report = {
        "status": "PASS",
        "summary": {"pass": 1, "warn": 0, "fail": 0},
        "checks": [],
        "recommended_fixes": [],
        "assurance": {},
        "artifacts": {},
        "generated_at": None,
    }

    write_doctor_artifacts(report, output_dir=tmp_path)

    loaded = load_latest_doctor_report(output_dir=tmp_path)
    assert loaded is not None
    assert isinstance(loaded["generated_at"], str)
    assert loaded["generated_at"]


def test_write_doctor_artifacts_normalizes_legacy_timestamp_utc(tmp_path: Path) -> None:
    report = {
        "status": "PASS",
        "summary": {"pass": 1, "warn": 0, "fail": 0},
        "checks": [],
        "recommended_fixes": [],
        "assurance": {},
        "artifacts": {},
        "timestamp_utc": "2026-03-26T13:15:18+00:00",
    }

    write_doctor_artifacts(report, output_dir=tmp_path)

    loaded = load_latest_doctor_report(output_dir=tmp_path)
    assert loaded is not None
    assert loaded["generated_at"] == "2026-03-26T13:15:18+00:00"


def test_daemon_integrity_warns_on_stale_pid_file(monkeypatch, tmp_path: Path) -> None:
    """No launchd expectation on this host: a stale pid file is only untidy."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("4242", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._scan_daemon_like_processes",
        lambda timeout_seconds: ([], True),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: False)

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "WARN"
    assert "stale pid files" in checks[0].detail


def test_daemon_integrity_fails_on_stale_pid_when_service_is_loaded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The actual 2026-07-25..08-01 shape: a stale pid file cited while the
    service is loaded and nothing is running. The stale-pid branch used to
    return WARN before launchd was ever consulted."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("67078", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl print: loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "FAIL"
    assert "the organism is dead" in checks[0].summary
    assert "67078" in checks[0].detail


def test_daemon_integrity_fails_on_stale_pid_when_plist_installed_but_unloaded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Installed-but-booted-out with a stale pid from the unclean exit."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("67078", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._scan_daemon_like_processes",
        lambda timeout_seconds: ([], True),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: True)

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "FAIL"
    assert "the organism is dead" in checks[0].summary


def test_daemon_integrity_keeps_warn_when_a_live_process_explains_the_stale_pid(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A running organism must never be escalated to FAIL by a stale file."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("4242", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            "777 /Users/dhyana/dharma_swarm/.venv/bin/python "
            "/Users/dhyana/dharma_swarm/.venv/bin/dgc orchestrate-live",
            "",
        ),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl print: loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "WARN"
    assert "777" in checks[0].detail


def test_daemon_integrity_fails_when_daemon_pid_was_recycled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A leftover daemon.pid pointing at any live program must not buy silence.

    Bare `kill -0` in `_read_pid_file` made `daemon_status == "alive"`, which
    skipped the stale-pid branch AND the `daemon_status != "alive"` launchd
    consultation, restoring the quiet PASS for a dead organism.
    """
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("67078", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "dharma_swarm.doctor._pid_command",
        lambda pid: "/Applications/Safari.app/Contents/MacOS/Safari",
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl print: loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "FAIL"
    assert "the organism is dead" in checks[0].summary


def test_daemon_integrity_trusts_a_daemon_pid_running_the_organism(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Negative control: a pid whose command IS the organism stays alive."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("777", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "dharma_swarm.doctor._pid_command",
        lambda pid: "/Users/dhyana/dharma_swarm/.venv/bin/python "
        "/Users/dhyana/dharma_swarm/.venv/bin/dgc orchestrate-live",
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "PASS"


def test_daemon_integrity_sees_console_script_launch_form(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """`dgc orchestrate-live` (the plist spelling) must count as a live daemon.

    Before this, the needles knew only the module/legacy forms, so a healthy
    launchd host with no pid file scanned as "no daemon process" and the new
    launchd branch turned that blind spot into a loud false FAIL.
    """
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            "777 /Users/dhyana/dharma_swarm/.venv/bin/python "
            "/Users/dhyana/dharma_swarm/.venv/bin/dgc orchestrate-live",
            "",
        ),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl print: loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "PASS"
    assert "777" in (checks[0].summary or "")


def test_daemon_integrity_sees_release_runner_launch_form(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            "901 /Users/dhyana/dharma_releases/x/.venv/bin/python -B -I "
            "-m dharma_swarm.dgc_cli orchestrate-live",
            "",
        ),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "PASS"
    assert "901" in (checks[0].summary or "")


def test_daemon_integrity_warns_on_legacy_orchestrator_pid_with_live_daemon(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("111", encoding="utf-8")
    (state_dir / "orchestrator.pid").write_text("222", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: pid == 111)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            "111 python3 -m dharma_swarm.orchestrate_live --background",
            "",
        ),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "WARN"
    assert "legacy pid file" in checks[0].summary.lower()
    assert "orchestrator=222" in checks[0].detail


def test_daemon_integrity_fails_on_multiple_processes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: pid in {111, 222})
    ps_output = "\n".join(
        [
            "111 python3 -m dharma_swarm.orchestrate_live",
            "222 /bin/bash /Users/dhyana/dharma_swarm/run_daemon.sh",
        ]
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, ps_output, ""),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "FAIL"
    assert "multiple daemon-like processes" in checks[0].summary


def test_daemon_integrity_ignores_stale_legacy_orchestrator_pid(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("111", encoding="utf-8")
    (state_dir / "orchestrator.pid").write_text("222", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: pid == 111)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "PASS"
    assert "orchestrator" not in (checks[0].detail or "")


def test_daemon_integrity_fails_when_plist_installed_but_service_absent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The 7-day silent death: no pid files, no processes, service booted
    out, plist still installed. This used to fall through to PASS."""
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: True)

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "FAIL"
    assert "organism is dead" in checks[0].summary


def test_daemon_integrity_fails_when_service_loaded_but_no_process(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl print: loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "FAIL"
    assert "loaded but no daemon process" in checks[0].summary


def test_daemon_integrity_passes_when_no_launchd_expectation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """CI / dev hosts with no plist and no service keep the quiet PASS."""
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: False)

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "daemon_integrity"
    assert checks[0].status == "PASS"


def test_message_bus_integrity_warns_on_shadow_path_and_idle_runtime(monkeypatch, tmp_path: Path) -> None:
    canonical = tmp_path / ".dharma" / "db" / "messages.db"
    shadow = tmp_path / ".dharma" / "message_bus.db"
    _create_message_bus_db(canonical)
    _create_message_bus_db(shadow)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr(
        "dharma_swarm.doctor._list_daemon_like_processes",
        lambda timeout_seconds: [(111, "python3 -m dharma_swarm.orchestrate_live")],
    )

    checks = []
    _check_message_bus_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "message_bus_integrity"
    assert checks[0].status == "WARN"
    assert "message_bus.db" in checks[0].detail
    assert "heartbeats=0" in checks[0].detail


def test_message_bus_integrity_reports_busy_timeout_and_heartbeat_window(
    monkeypatch,
    tmp_path: Path,
) -> None:
    canonical = tmp_path / ".dharma" / "db" / "messages.db"
    _create_message_bus_db(canonical)

    with sqlite3.connect(canonical) as conn:
        conn.execute("DELETE FROM heartbeats")
        conn.execute(
            "INSERT INTO heartbeats (agent_id, last_seen) VALUES (?, ?)",
            ("agent-stale", "2026-03-20T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO heartbeats (agent_id, last_seen) VALUES (?, ?)",
            ("agent-fresh", "2026-03-26T00:00:00+00:00"),
        )
        conn.commit()

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr(
        "dharma_swarm.doctor._list_daemon_like_processes",
        lambda timeout_seconds: [(111, "python3 -m dharma_swarm.orchestrate_live")],
    )

    checks = []
    _check_message_bus_integrity(checks, timeout_seconds=0.1)

    assert checks[0].name == "message_bus_integrity"
    assert "busy_timeout_ms=" in checks[0].detail
    assert "oldest_heartbeat=" in checks[0].detail
    assert "latest_heartbeat=" in checks[0].detail


def test_claude_unattended_auth_passes_with_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor.shutil.which", lambda _: "/usr/local/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    checks = []
    _check_claude_unattended_auth(checks)

    assert checks[0].name == "claude_unattended_auth"
    assert checks[0].status == "PASS"
    assert "bare-mode auth configured" in checks[0].summary


def test_claude_unattended_auth_fails_with_recent_pulse_login_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pulse_last_run = tmp_path / ".dharma" / "cron" / "last_run"
    pulse_last_run.mkdir(parents=True, exist_ok=True)
    (pulse_last_run / "pulse.json").write_text(
        json.dumps({"error": "Error (rc=1): Not logged in · Please run /login\n"}),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor.shutil.which", lambda _: "/usr/local/bin/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    checks = []
    _check_claude_unattended_auth(checks)

    assert checks[0].name == "claude_unattended_auth"
    assert checks[0].status == "FAIL"
    assert "actively failing" in checks[0].summary
    assert "pulse=" in checks[0].detail


def test_claude_unattended_auth_fails_with_recent_fast_fail_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pulse_last_run = tmp_path / ".dharma" / "cron" / "last_run"
    pulse_last_run.mkdir(parents=True, exist_ok=True)
    (pulse_last_run / "pulse.json").write_text(
        json.dumps(
            {
                "error": (
                    "ERROR: unattended Claude bare mode requires ANTHROPIC_API_KEY; "
                    "OAuth/login is ignored in --bare mode"
                )
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor.shutil.which", lambda _: "/usr/local/bin/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    checks = []
    _check_claude_unattended_auth(checks)

    assert checks[0].status == "FAIL"
    assert "pulse=" in checks[0].detail


def test_dgc_health_snapshot_fails_when_stale_and_cited_pid_dead(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The false-oracle scenario: a stale snapshot citing a dead PID must FAIL.

    This exact shape (dead PID 18104 filed as WARN for 7 days) masked the
    2026-07-25..08-01 outage. A dead cited PID is never a WARN.
    """
    state_dir = tmp_path / ".dharma"
    stigmergy_dir = state_dir / "stigmergy"
    stigmergy_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("111", encoding="utf-8")
    stale_snapshot = {
        "daemon_pid": 999999,
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "agent_count": 15,
        "source": "legacy-health-publisher",
    }
    (stigmergy_dir / "dgc_health.json").write_text(
        json.dumps(stale_snapshot),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: pid == 111)
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )

    checks = []
    _check_dgc_health_snapshot(checks)

    assert checks[0].name == "dgc_health_snapshot"
    assert checks[0].status == "FAIL"
    assert "dead daemon PID" in checks[0].summary
    assert "daemon_pid_alive=False" in checks[0].detail
    assert "daemon_pid_mismatch" in checks[0].detail


def test_dgc_health_snapshot_fails_even_when_fresh_if_cited_pid_dead(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A fresh timestamp does not launder a dead PID: still FAIL."""
    state_dir = tmp_path / ".dharma"
    stigmergy_dir = state_dir / "stigmergy"
    stigmergy_dir.mkdir(parents=True)
    fresh_snapshot = {
        "daemon_pid": 18104,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_count": 20,
        "source": "orchestrate_live",
    }
    (stigmergy_dir / "dgc_health.json").write_text(
        json.dumps(fresh_snapshot),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )

    checks = []
    _check_dgc_health_snapshot(checks)

    assert checks[0].name == "dgc_health_snapshot"
    assert checks[0].status == "FAIL"
    assert "dead daemon PID" in checks[0].summary
    assert "18104" in checks[0].detail


def test_dgc_health_snapshot_passes_when_fresh_and_cited_pid_alive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / ".dharma"
    stigmergy_dir = state_dir / "stigmergy"
    stigmergy_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("111", encoding="utf-8")
    fresh_snapshot = {
        "daemon_pid": 111,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_count": 20,
        "source": "orchestrate_live",
    }
    (stigmergy_dir / "dgc_health.json").write_text(
        json.dumps(fresh_snapshot),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: pid == 111)
    monkeypatch.setattr(
        "dharma_swarm.doctor._pid_command",
        lambda pid: "python -m dharma_swarm.dgc_cli orchestrate-live",
    )

    checks = []
    _check_dgc_health_snapshot(checks)

    assert checks[0].name == "dgc_health_snapshot"
    assert checks[0].status == "PASS"
    assert "daemon_pid_alive=True" in checks[0].detail


def test_dgc_health_snapshot_warns_after_healthy_daemon_restart(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A superseded snapshot PID must not falsely declare a live organism dead."""
    state_dir = tmp_path / ".dharma"
    stigmergy_dir = state_dir / "stigmergy"
    stigmergy_dir.mkdir(parents=True)
    (stigmergy_dir / "dgc_health.json").write_text(
        json.dumps(
            {
                "daemon_pid": 18104,
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).isoformat(),
                "agent_count": 20,
                "source": "orchestrate_live",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor._scan_daemon_like_processes",
        lambda timeout_seconds: (
            [(4242, "python -m dharma_swarm.dgc_cli orchestrate-live")],
            True,
        ),
    )

    checks = []
    _check_dgc_health_snapshot(checks)

    assert checks[0].name == "dgc_health_snapshot"
    assert checks[0].status == "WARN"
    assert "current daemon process is running" in checks[0].summary
    assert "pid=4242" in checks[0].detail
    assert "organism outage" in checks[0].fix


def test_dgc_health_snapshot_warns_when_current_process_scan_is_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """An unavailable present-time probe cannot support a hard outage claim."""
    state_dir = tmp_path / ".dharma"
    stigmergy_dir = state_dir / "stigmergy"
    stigmergy_dir.mkdir(parents=True)
    (stigmergy_dir / "dgc_health.json").write_text(
        json.dumps(
            {
                "daemon_pid": 18104,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "orchestrate_live",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor._scan_daemon_like_processes",
        lambda timeout_seconds: ([], False),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("unknown", "launchctl probe unavailable"),
    )

    checks = []
    _check_dgc_health_snapshot(checks)

    assert checks[0].name == "dgc_health_snapshot"
    assert checks[0].status == "WARN"
    assert "could not be verified" in checks[0].summary
    assert "daemon_process_scan=unavailable" in checks[0].detail


def test_dgc_health_snapshot_fails_when_cited_pid_was_recycled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """kill -0 succeeds on a reused pid; identity must still call it dead."""
    state_dir = tmp_path / ".dharma"
    stigmergy_dir = state_dir / "stigmergy"
    stigmergy_dir.mkdir(parents=True)
    (stigmergy_dir / "dgc_health.json").write_text(
        json.dumps(
            {
                "daemon_pid": 67078,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_count": 20,
                "source": "orchestrate_live",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "dharma_swarm.doctor._pid_command",
        lambda pid: "/Applications/Safari.app/Contents/MacOS/Safari",
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._scan_daemon_like_processes",
        lambda timeout_seconds: ([], True),
    )

    checks = []
    _check_dgc_health_snapshot(checks)

    assert checks[0].name == "dgc_health_snapshot"
    assert checks[0].status == "FAIL"
    assert "dead daemon PID" in checks[0].summary


def test_doctor_schedule_passes_when_job_is_armed(monkeypatch, tmp_path: Path) -> None:
    cron_dir = tmp_path / ".dharma" / "cron"
    cron_dir.mkdir(parents=True)
    next_run = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    jobs_path = cron_dir / "jobs.json"
    jobs_path.write_text(
        (
            '{"jobs": [{"id": "doc1", "name": "doctor_assurance", "enabled": true, '
            '"handler": "doctor_assurance", "next_run_at": "'
            + next_run
            + '", "last_run_at": null}]}'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)

    checks = []
    _check_doctor_schedule(checks)

    assert checks[0].name == "doctor_schedule"
    assert checks[0].status == "PASS"
    assert "armed" in checks[0].summary


def test_create_doctor_job_marks_job_urgent(monkeypatch) -> None:
    captured = {}

    def _fake_create_job(prompt, schedule, name=None, repeat=None, deliver="local", urgent=False, **extras):
        captured.update(
            {
                "prompt": prompt,
                "schedule": schedule,
                "name": name,
                "deliver": deliver,
                "urgent": urgent,
                "extras": extras,
            }
        )
        return {"id": "job1", "name": name, "urgent": urgent, **extras}

    monkeypatch.setattr("dharma_swarm.cron_scheduler.create_job", _fake_create_job)

    job = create_doctor_job(schedule="every 2h", quick=True)

    assert captured["urgent"] is True
    assert captured["name"] == "doctor_assurance"
    assert job["urgent"] is True


# --- an unreadable process table must not become a death certificate -------


def _ps_raises(*_args, **_kwargs):
    raise OSError("No such file or directory: 'ps'")


def test_daemon_integrity_will_not_declare_death_from_a_blind_ps_probe(
    monkeypatch, tmp_path: Path
) -> None:
    """`ps` failing is "we did not look", not "nothing is running".

    The PR taught this check to escalate an empty scan into a hard FAIL
    saying the organism is dead. An empty list from a probe that never ran
    must not reach that branch — it would be the mirror image of the bug
    being fixed. WARN is the honest rung.
    """
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor.subprocess.run", _ps_raises)
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl: loaded"),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: True)

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].status == "WARN"
    assert "unverified" in checks[0].summary
    assert "dead" not in (checks[0].summary or "").lower()


def test_daemon_integrity_still_fails_loudly_when_ps_really_reports_nothing(
    monkeypatch, tmp_path: Path
) -> None:
    """NEGATIVE CONTROL for the test above: the incident shape stays a FAIL.

    Same host state, but `ps` runs successfully and returns no organism.
    That IS an observation of absence, and with launchd loaded it must
    still be the loud FAIL this PR exists to produce.
    """
    (tmp_path / ".dharma").mkdir(parents=True)

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("loaded", "launchctl: loaded"),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: True)

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].status == "FAIL"
    assert "no daemon process is running" in checks[0].summary


def test_stale_pid_plus_blind_ps_probe_warns_instead_of_asserting_death(
    monkeypatch, tmp_path: Path
) -> None:
    """The stale-pid branch has the same escalation and the same gate."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("4242", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr("dharma_swarm.doctor.subprocess.run", _ps_raises)
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: True)
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].status == "WARN"
    assert "process table unreadable" in checks[0].detail


def test_stale_pid_with_a_working_ps_probe_still_fails_loudly(
    monkeypatch, tmp_path: Path
) -> None:
    """NEGATIVE CONTROL: the exact 2026-07-25..08-01 shape stays a FAIL."""
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir(parents=True)
    (state_dir / "daemon.pid").write_text("67078", encoding="utf-8")

    monkeypatch.setattr("dharma_swarm.doctor.HOME", tmp_path)
    monkeypatch.setattr("dharma_swarm.doctor._pid_alive", lambda pid: False)
    monkeypatch.setattr(
        "dharma_swarm.doctor.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr("dharma_swarm.doctor._launchd_plist_installed", lambda: True)
    monkeypatch.setattr(
        "dharma_swarm.doctor._launchd_service_state",
        lambda timeout_seconds: ("absent", "launchctl: service not loaded"),
    )

    checks = []
    _check_daemon_integrity(checks, timeout_seconds=0.1)

    assert checks[0].status == "FAIL"
    assert "the organism is dead" in checks[0].summary


def test_scan_reports_probe_failure_distinctly_from_an_empty_result() -> None:
    """The seam itself: [] with scan_ok=False is not [] with scan_ok=True."""
    from dharma_swarm.doctor import _scan_daemon_like_processes

    import dharma_swarm.doctor as doctor_mod

    original = doctor_mod.subprocess.run
    try:
        doctor_mod.subprocess.run = _ps_raises
        assert _scan_daemon_like_processes(0.1) == ([], False)

        doctor_mod.subprocess.run = (
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, "", "")
        )
        assert _scan_daemon_like_processes(0.1) == ([], True)
    finally:
        doctor_mod.subprocess.run = original
