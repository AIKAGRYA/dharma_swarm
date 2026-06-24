from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.holon_l4_supervisor import (
    build_holon_l4_supervisor_plan,
    write_holon_l4_supervisor_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_render_launchd_supervisor_plan_is_review_only(tmp_path: Path) -> None:
    plan = build_holon_l4_supervisor_plan(
        name="codex_composer",
        mode="launchd",
        repo_root=REPO_ROOT,
        agents_root=tmp_path / "agents",
        output_dir=tmp_path / "supervisor",
        label="com.dharma.test-holon-l4",
        interval_seconds=7,
        python_executable=sys.executable,
    )
    payload = plistlib.loads(plan.launchd_plist.encode("utf-8"))

    assert plan.schema_version == "dharma.holon_l4_supervisor_plan.v1"
    assert plan.dry_run is True
    assert plan.safety["review_only"] is True
    assert plan.safety["install_performed"] is False
    assert plan.safety["service_started"] is False
    assert plan.safety["launchctl_invoked"] is False
    assert plan.receipt_hash.startswith("sha256:")
    assert payload["Label"] == "com.dharma.test-holon-l4"
    assert payload["RunAtLoad"] is False
    assert payload["KeepAlive"] is True
    assert payload["ProgramArguments"][0] == sys.executable
    assert payload["ProgramArguments"][1].endswith("scripts/holon_l4_service.py")
    assert payload["ProgramArguments"][2] == "codex_composer"
    assert "--forever" in payload["ProgramArguments"]
    assert "--lock-path" in payload["ProgramArguments"]
    assert "launchctl" not in plan.launchd_plist
    assert "tmux" not in plan.launchd_plist


def test_render_tmux_supervisor_plan_is_review_only(tmp_path: Path) -> None:
    plan = build_holon_l4_supervisor_plan(
        name="codex_composer",
        mode="tmux",
        repo_root=REPO_ROOT,
        agents_root=tmp_path / "agents",
        output_dir=tmp_path / "supervisor",
        tmux_session="holon_l4_test",
        forever=False,
        cycles=2,
        interval_seconds=0,
        python_executable=sys.executable,
    )

    assert plan.launchd_plist == ""
    assert plan.tmux_session == "holon_l4_test"
    assert "tmux new-session -d -s holon_l4_test" in plan.tmux_command
    assert "scripts/holon_l4_service.py" in plan.tmux_command
    assert "--cycles 2" in plan.tmux_command
    assert "--forever" not in plan.tmux_command
    assert plan.safety["tmux_invoked"] is False
    assert plan.safety["process_action_performed"] is False


def test_supervisor_plan_can_require_readonly_orchestration_probe(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    plan = build_holon_l4_supervisor_plan(
        name="codex_composer",
        mode="tmux",
        repo_root=REPO_ROOT,
        agents_root=tmp_path / "agents",
        output_dir=tmp_path / "supervisor",
        tmux_session="holon_l4_orchestration_test",
        live_model_probe=True,
        model_probe_first_cycle_only=True,
        allow_subprocess_model_probe=True,
        safe_subprocess_model_probe=True,
        safe_subprocess_probe_cwd=REPO_ROOT,
        model_probe_lease_id="lease:test:first-cycle",
        model_probe_lease_path=tmp_path / "leases" / "model.json",
        enable_orchestration_probe=True,
        require_orchestration=True,
        orchestration_execution_mode="bounded_subtask_execution",
        orchestration_timeout_seconds=5.0,
        use_readonly_swarm_manager_orchestrator=True,
        orchestration_state_dir=state_dir,
        python_executable=sys.executable,
    )

    command = plan.service_command
    assert "--live-model-probe" in command
    assert "--model-probe-first-cycle-only" in command
    assert "--allow-subprocess-model-probe" in command
    assert "--safe-subprocess-model-probe" in command
    assert command[command.index("--safe-subprocess-probe-cwd") + 1] == str(
        REPO_ROOT.resolve()
    )
    assert command[command.index("--model-probe-lease-id") + 1] == (
        "lease:test:first-cycle"
    )
    assert "--enable-orchestration-probe" in command
    assert "--require-orchestration" in command
    assert "--use-readonly-swarm-manager-orchestrator" in command
    assert command[command.index("--orchestration-execution-mode") + 1] == (
        "bounded_subtask_execution"
    )
    assert command[command.index("--orchestration-state-dir") + 1] == str(
        state_dir.resolve()
    )
    assert "--enable-orchestration-probe" in plan.tmux_command
    assert "--use-readonly-swarm-manager-orchestrator" in plan.tmux_command


def test_supervisor_plan_rejects_path_like_holon_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="name must be a simple"):
        build_holon_l4_supervisor_plan(
            name="../codex_composer",
            mode="launchd",
            repo_root=REPO_ROOT,
            agents_root=tmp_path / "agents",
            output_dir=tmp_path / "supervisor",
        )


def test_write_supervisor_plan_artifacts(tmp_path: Path) -> None:
    launchd = write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="launchd",
            repo_root=REPO_ROOT,
            agents_root=tmp_path / "agents",
            output_dir=tmp_path / "launchd",
            label="com.dharma.write-holon-l4",
        )
    )
    tmux = write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="tmux",
            repo_root=REPO_ROOT,
            agents_root=tmp_path / "agents",
            output_dir=tmp_path / "tmux",
            tmux_session="holon_l4_write_test",
        )
    )

    plan_path = Path(launchd.artifact_refs["supervisor_plan"])
    plist_path = Path(launchd.artifact_refs["planned_launchd_plist"])
    script_path = Path(tmux.artifact_refs["planned_tmux_command"])
    assert json.loads(plan_path.read_text(encoding="utf-8"))["receipt_hash"] == (
        launchd.receipt_hash
    )
    assert plistlib.loads(plist_path.read_bytes())["Label"] == "com.dharma.write-holon-l4"
    assert script_path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert script_path.stat().st_mode & 0o700 == 0o700
    assert not (tmp_path / "Library" / "LaunchAgents").exists()


def test_supervisor_cli_writes_reviewable_artifacts(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "holon_l4_supervisor.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "codex_composer",
            "--mode",
            "launchd",
            "--repo-root",
            str(REPO_ROOT),
            "--agents-root",
            str(tmp_path / "agents"),
            "--output-dir",
            str(tmp_path / "supervisor"),
            "--label",
            "com.dharma.cli-holon-l4",
            "--python-executable",
            sys.executable,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["receipt_hash"].startswith("sha256:")
    assert payload["safety"]["service_started"] is False
    assert Path(payload["artifact_refs"]["supervisor_plan"]).exists()
    assert Path(payload["artifact_refs"]["planned_launchd_plist"]).exists()
    assert plistlib.loads(
        Path(payload["artifact_refs"]["planned_launchd_plist"]).read_bytes()
    )["Label"] == "com.dharma.cli-holon-l4"
