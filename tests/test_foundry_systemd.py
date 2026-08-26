"""Static deployment contract tests; never touch systemd."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

import pytest

from dharma_swarm.foundry.daemon import DaemonState
from scripts.foundry import foundry_daemon

REPO = Path(__file__).resolve().parents[1]


def test_systemd_unit_restarts_crashes_but_not_terminal_kill():
    unit = (
        REPO / "scripts/foundry/systemd/sublimation-foundry.service.in"
    ).read_text()
    assert "Restart=on-failure" in unit
    assert "RestartPreventExitStatus=42" in unit
    assert "--mode campaign" in unit
    assert "--state-root @@STATE_ROOT@@" in unit
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges=true" in unit
    for directive in (
        "CapabilityBoundingSet=",
        "AmbientCapabilities=",
        "ProtectKernelLogs=true",
        "RestrictRealtime=true",
        "SystemCallArchitectures=native",
        "MemoryMax=2G",
        "TasksMax=256",
        "LimitNOFILE=4096",
        "LimitFSIZE=1G",
        "--cycle-budget 5",
    ):
        assert directive in unit


def test_install_and_status_shell_are_syntax_valid():
    for path in (
        REPO / "scripts/foundry/install_service.sh",
        REPO / "scripts/foundry/foundry-status.sh",
    ):
        proc = subprocess.run(["sh", "-n", str(path)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr


def test_installer_is_inert_and_release_identity_is_fail_closed():
    installer = (REPO / "scripts/foundry/install_service.sh").read_text()
    assert 'start_service=0' in installer
    assert '--start) start_service=1' in installer
    assert '--expected-sha)' in installer
    assert 'status --porcelain --untracked-files=normal' in installer
    assert 'https://github.com/AIKAGRYA/dharma_swarm.git' in installer
    assert 'MOONSHOT_API_KEY ZHIPU_API_KEY' in installer
    assert 'QUARANTINE.json' in installer
    assert 'systemd-analyze verify "$unit_tmp"' in installer


def test_systemd_analyze_accepts_rendered_unit_when_available(tmp_path):
    analyzer = shutil.which("systemd-analyze")
    if analyzer is None:
        pytest.skip("systemd-analyze is unavailable on this host")
    unit = (
        REPO / "scripts/foundry/systemd/sublimation-foundry.service.in"
    ).read_text()
    rendered = (
        unit.replace("@@USER@@", "nobody")
        .replace("@@REPO@@", str(REPO))
        .replace("@@PYTHON@@", "/usr/bin/python3")
        .replace("@@STATE_ROOT@@", str(tmp_path / "state"))
    )
    path = tmp_path / "sublimation-foundry.service"
    path.write_text(rendered, encoding="utf-8")
    proc = subprocess.run(
        [analyzer, "verify", str(path)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_cli_returns_restart_preventing_nonzero_for_terminal_kill(monkeypatch):
    monkeypatch.setattr(
        foundry_daemon,
        "run_daemon",
        lambda config: DaemonState(terminal_kill=True, stopped_reason="KILL"),
    )
    assert foundry_daemon.main(["--max-cycles", "1"]) == 42
