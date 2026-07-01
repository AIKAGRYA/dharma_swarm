from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from pathlib import Path

from dharma_swarm.operator_core.living_agent_kernel_service import run_kernel_daemon_service
from dharma_swarm.operator_core.living_agent_kernel_supervisor import (
    build_supervisor_plan,
    supervisor_status,
    write_supervisor_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_launchd_supervisor_plan_is_default_off_and_absolute(tmp_path):
    plan = build_supervisor_plan(
        mode="launchd",
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        workspace_root=tmp_path,
        daemon_id="kernel-supervisor",
        label="com.dharma.test-lak",
        interval_seconds=7,
        max_wakes=3,
    )
    payload = plistlib.loads(plan.launchd_plist.encode("utf-8"))

    assert plan.dry_run is True
    assert plan.receipt_hash.startswith("sha256:")
    assert payload["Label"] == "com.dharma.test-lak"
    assert payload["RunAtLoad"] is False
    assert payload["KeepAlive"] is True
    assert payload["ProgramArguments"][0] == sys.executable
    assert payload["ProgramArguments"][1].endswith("scripts/runtime/living_agent_kernel_service.py")
    assert payload["ProgramArguments"][1].startswith("/")
    assert "--forever" in payload["ProgramArguments"]
    assert "launchctl" not in plan.launchd_plist
    assert "tmux" not in plan.launchd_plist


def test_write_launchd_supervisor_plan_writes_review_artifacts(tmp_path):
    plan = build_supervisor_plan(
        mode="launchd",
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        workspace_root=tmp_path,
        label="com.dharma.test-lak",
    )
    written = write_supervisor_plan(plan)
    plan_path = Path(written.artifact_refs["supervisor_plan"])
    plist_path = Path(written.artifact_refs["planned_launchd_plist"])

    assert plan_path.exists()
    assert plist_path.exists()
    assert json.loads(plan_path.read_text())["receipt_hash"] == written.receipt_hash
    assert plistlib.loads(plist_path.read_bytes())["Label"] == "com.dharma.test-lak"
    assert not (tmp_path / "Library" / "LaunchAgents" / "com.dharma.test-lak.plist").exists()


def test_tmux_supervisor_plan_writes_review_script_only(tmp_path):
    plan = build_supervisor_plan(
        mode="tmux",
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        workspace_root=tmp_path,
        daemon_id="kernel-supervisor",
        tmux_session="lak_test_session",
    )
    written = write_supervisor_plan(plan)
    script_path = Path(written.artifact_refs["planned_tmux_command"])

    assert "tmux new-session -d -s lak_test_session" in written.tmux_command
    assert "--forever" in written.tmux_command
    assert script_path.exists()
    assert script_path.read_text().startswith("#!/usr/bin/env bash")
    assert script_path.stat().st_mode & 0o700 == 0o700


def test_supervisor_status_tracks_recent_and_stale_cycles(tmp_path):
    store_dir = tmp_path / "kernel"

    never = supervisor_status(
        store_dir=store_dir,
        daemon_id="kernel-supervisor",
        now="2026-06-05T00:00:00Z",
    )
    run_kernel_daemon_service(
        store_dir=store_dir,
        workspace_root=tmp_path,
        daemon_id="kernel-supervisor",
        cycles=1,
        now_fn=lambda: "2026-06-05T00:00:10Z",
    )
    recent = supervisor_status(
        store_dir=store_dir,
        daemon_id="kernel-supervisor",
        stale_after_seconds=60,
        now="2026-06-05T00:00:20Z",
    )
    stale = supervisor_status(
        store_dir=store_dir,
        daemon_id="kernel-supervisor",
        stale_after_seconds=5,
        now="2026-06-05T00:00:20Z",
    )

    assert never.status == "never_ran"
    assert recent.status == "recent"
    assert recent.cycle_count == 1
    assert recent.latest_cycle_ref["status"] == "idle"
    assert stale.status == "stale"


def test_supervisor_cli_plan_and_status_json(tmp_path):
    script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_supervisor.py"
    store_dir = tmp_path / "kernel"

    planned = subprocess.run(
        [
            sys.executable,
            str(script),
            "plan",
            "--mode",
            "launchd",
            "--repo-root",
            str(REPO_ROOT),
            "--store-dir",
            str(store_dir),
            "--workspace-root",
            str(tmp_path),
            "--label",
            "com.dharma.test-lak",
            "--write",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    status = subprocess.run(
        [
            sys.executable,
            str(script),
            "status",
            "--store-dir",
            str(store_dir),
            "--daemon-id",
            "living-agent-kernel",
            "--now",
            "2026-06-05T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)

    plan_payload = json.loads(planned.stdout)
    status_payload = json.loads(status.stdout)
    assert plan_payload["receipt_hash"].startswith("sha256:")
    assert Path(plan_payload["artifact_refs"]["supervisor_plan"]).exists()
    assert status_payload["status"] == "never_ran"
