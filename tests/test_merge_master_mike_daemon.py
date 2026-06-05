from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from scripts.runtime import merge_master_mike_daemon as mike


def test_bootstrap_nest_writes_core_surfaces(tmp_path: Path) -> None:
    paths = mike.mike_paths(tmp_path / ".dharma")

    status = mike.bootstrap_nest(paths, repo_root=tmp_path / "repo")

    assert status["agent_uid"] == "merge_master_mike"
    assert (paths.nest / "README.md").exists()
    assert (paths.nest / "COMMANDS.md").exists()
    assert (paths.nest / "delegation_lanes.json").exists()
    assert paths.action_log.exists()
    assert paths.wake_receipts.exists()
    lanes = json.loads((paths.nest / "delegation_lanes.json").read_text())
    assert lanes["schema"] == "dharma.merge_master_mike.delegation_lanes.v1"
    assert {lane["agent"] for lane in lanes["lanes"]} >= {"codex", "claude", "perplexity", "warp_oz"}
    assert "silent merge" in lanes["forbidden"]


def test_record_wake_receipt_updates_living_agent(tmp_path: Path) -> None:
    paths = mike.mike_paths(tmp_path / ".dharma")

    receipt = mike.record_wake(paths, repo_root=tmp_path / "repo", mode="test")

    assert receipt["schema_version"] == "dharma_merge_master_mike_wake_receipt.v1"
    assert receipt["agent_uid"] == "merge_master_mike"
    assert receipt["mode"] == "test"
    assert len(paths.wake_receipts.read_text().strip().splitlines()) == 1
    living = json.loads(paths.living_agent.read_text())
    assert living["status"] == "awake"
    assert living["last_wake_receipt"] == str(paths.wake_receipts)
    assert "unconditional_merge" in receipt["forbidden_actions"]
    assert "merge_without_clean_gate" in receipt["forbidden_actions"]
    assert "conditional_merge_after_clean_gate" in receipt["allowed_actions"]


def test_build_fanout_command_defaults_to_dry_run(tmp_path: Path) -> None:
    command = mike.build_fanout_command(
        pr_review_root=tmp_path / "review",
        cycle_mode="dry-run",
        max_prs=5,
        limit=50,
        timeout_s=120,
        agents="codex,claude",
        statuses="GITHUB_GREEN_NEEDS_PACKET",
        allow_pending=False,
        human_approved=False,
    )

    assert command[:2] == [sys.executable, "scripts/runtime/pr_merge_control.py"]
    assert command[2:5] == ["--state-root", str(tmp_path / "review"), "fanout"]
    assert "--dry-run" in command
    assert "--packet-only" not in command
    assert command[command.index("--max-prs") + 1] == "5"
    assert command[command.index("--timeout-s") + 1] == "120"


def test_build_fanout_command_packet_only_and_human_flags(tmp_path: Path) -> None:
    command = mike.build_fanout_command(
        pr_review_root=tmp_path / "review",
        cycle_mode="packet-only",
        max_prs=1,
        limit=10,
        timeout_s=None,
        agents="codex",
        statuses="NEEDS_AGENT_REVIEW",
        allow_pending=True,
        human_approved=True,
    )

    assert "--packet-only" in command
    assert "--dry-run" not in command
    assert "--allow-pending" in command
    assert "--human-approved" in command


def test_run_cycle_records_receipt_with_injected_runner(tmp_path: Path) -> None:
    paths = mike.mike_paths(tmp_path / ".dharma")
    repo = tmp_path / "repo"
    repo.mkdir()

    seen: dict[str, object] = {}

    def fake_runner(command: list[str], cwd: Path, timeout_s: float) -> mike.CommandResult:
        seen["command"] = command
        seen["cwd"] = cwd
        seen["timeout_s"] = timeout_s
        return mike.CommandResult(
            code=0,
            stdout="mike_fanout=/tmp/summary.md\nselected=0 processed=0 dry_run=True\n",
            stderr="",
            duration_s=0.01,
        )

    receipt = mike.run_cycle(
        paths,
        repo_root=repo,
        pr_review_root=tmp_path / "review",
        cycle_mode="dry-run",
        max_prs=2,
        command_timeout_s=30,
        runner=fake_runner,
    )

    assert receipt["exit_code"] == 0
    assert receipt["cycle_mode"] == "dry-run"
    assert receipt["authority"]["can_merge"] is False
    assert "--dry-run" in seen["command"]
    assert seen["cwd"] == repo
    assert seen["timeout_s"] == 30
    assert paths.latest_cycle.exists()
    latest = json.loads(paths.latest_cycle.read_text())
    assert latest["run_id"] == receipt["run_id"]
    assert mike.count_lines(paths.wake_receipts) == 1
    assert mike.count_lines(paths.action_log) >= 2


def test_status_markdown_preserves_authority_boundary(tmp_path: Path) -> None:
    paths = mike.mike_paths(tmp_path / ".dharma")
    mike.bootstrap_nest(paths, repo_root=tmp_path / "repo")

    text = mike.render_status_markdown(mike.build_status(paths, repo_root=tmp_path / "repo"))

    assert "Merge Master Mike Status" in text
    assert "conditionally merge only after a clean deterministic gate" in text
    assert "may not approve" in text


def test_default_runner_scrubs_stale_github_env_tokens(tmp_path: Path) -> None:
    old_gh = os.environ.get("GH_TOKEN")
    old_github = os.environ.get("GITHUB_TOKEN")
    try:
        os.environ["GH_TOKEN"] = "stale"
        os.environ["GITHUB_TOKEN"] = "stale"
        result = mike.default_runner(
            [
                sys.executable,
                "-c",
                "import os; print('GH_TOKEN=' + str(os.environ.get('GH_TOKEN'))); print('GITHUB_TOKEN=' + str(os.environ.get('GITHUB_TOKEN')))",
            ],
            tmp_path,
            5,
        )
    finally:
        if old_gh is None:
            os.environ.pop("GH_TOKEN", None)
        else:
            os.environ["GH_TOKEN"] = old_gh
        if old_github is None:
            os.environ.pop("GITHUB_TOKEN", None)
        else:
            os.environ["GITHUB_TOKEN"] = old_github

    assert result.code == 0
    assert "GH_TOKEN=None" in result.stdout
    assert "GITHUB_TOKEN=None" in result.stdout
