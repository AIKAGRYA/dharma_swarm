"""Hardening lane v1: cap/receipt behavior + workflow contract pins (PR-E)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import hardening_lane  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "hardening-lane.yml"


def test_receipt_writes_schema_and_payload(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    hardening_lane.receipt({"status": "NO_WORK", "reason": "x"}, out)
    stored = json.loads(out.read_text())
    assert stored["schema"] == "dharma.hardening_lane_receipt.v1"
    assert stored["status"] == "NO_WORK"
    assert stored["generated_at"]


def test_lane_refuses_without_agent_cmd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_LANE_AGENT_CMD", raising=False)
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(
        hardening_lane, "select_target",
        lambda repo: {"kind": "mailbox", "task_id": "t", "summary": "s", "body": "b"},
    )
    out = tmp_path / "r.json"
    code = hardening_lane.main(["--repo", "o/r", "--receipt", str(out)])
    stored = json.loads(out.read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "DHARMA_LANE_AGENT_CMD" in stored["reason"]


def test_lane_refuses_non_allowlisted_agent_binary(tmp_path: Path, monkeypatch) -> None:
    # The secret is a template NAME; a shell string (or any unknown selector)
    # must be refused — no environment-derived text may reach subprocess argv.
    monkeypatch.setenv("DHARMA_LANE_AGENT_CMD", "/usr/bin/curl http://evil")
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(
        hardening_lane, "select_target",
        lambda repo: {"kind": "mailbox", "task_id": "t", "summary": "s", "body": "b"},
    )
    out = tmp_path / "r.json"
    code = hardening_lane.main(["--repo", "o/r", "--receipt", str(out)])
    stored = json.loads(out.read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "allowlist" in stored["reason"]


def test_no_work_is_a_clean_exit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(hardening_lane, "select_target", lambda repo: None)
    out = tmp_path / "r.json"
    code = hardening_lane.main(["--repo", "o/r", "--receipt", str(out)])
    assert code == 0
    assert json.loads(out.read_text())["status"] == "NO_WORK"


def test_lane_constants_enforce_ruling_caps() -> None:
    assert hardening_lane.MAX_DIFF_LINES <= 600, "tier-1 ceiling from the ruling"
    assert "mike-watch" in hardening_lane.LANE_LABELS
    assert "walk-ready" in hardening_lane.LANE_LABELS
    # Every agent template is a list of literals — the de-taint invariant.
    for name, argv in hardening_lane.AGENT_COMMANDS.items():
        assert isinstance(argv, list) and argv, name
        assert all(isinstance(part, str) for part in argv), name
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert '"--draft"' in source, "lane output must be draft-only"
    assert "git push" not in source.replace('"git", "push"', ""), (
        "only the explicit lane-branch push is allowed"
    )


def test_workflow_contract() -> None:
    doc = yaml.safe_load(WORKFLOW.read_text())
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    job = doc["jobs"]["harden"]
    assert job["steps"][0]["name"] == "Halt on loop kill-switch"
    assert "contents/docs/ops/loop_control/KILLSWITCH?ref=loop-control" in job["steps"][0]["run"]
    assert "No commit found" in job["steps"][0]["run"], "missing-branch 404 must read as absent"
    assert job["timeout-minutes"] <= 45, "runtime cap lives in the workflow"
    env = job["env"]
    assert int(env["LANE_MAX_DIFF_LINES"]) <= 600
    assert int(env["LANE_MAX_AGENT_SECONDS"]) <= 1800
    text = WORKFLOW.read_text()
    assert "DHARMA_LANE_AGENT_CMD: ${{ secrets.DHARMA_LANE_AGENT_CMD }}" in text


# --- Greptile review round on #1162 --------------------------------------


def test_agent_env_strips_github_credentials(monkeypatch) -> None:
    """The lane holds contents:write and pull-requests:write to open its own
    draft; the agent must not inherit that authority."""
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "model-key")
    env = hardening_lane.agent_env()
    assert "GH_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    assert "GITHUB_REPOSITORY" not in env
    # The agent's own model credentials are what it legitimately needs.
    assert env["ANTHROPIC_API_KEY"] == "model-key"


def test_delivery_ceiling_blocks_a_second_draft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [4242])
    out = tmp_path / "r.json"
    assert hardening_lane.main(["--repo", "o/r", "--receipt", str(out)]) == 0
    stored = json.loads(out.read_text())
    assert stored["status"] == "CAP_HIT"
    assert stored["cap"] == "open_lane_drafts"


def test_unknown_draft_count_refuses_to_deliver(tmp_path: Path, monkeypatch) -> None:
    """A failed enumeration must not read as 'zero drafts open'."""
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: None)
    out = tmp_path / "r.json"
    assert hardening_lane.main(["--repo", "o/r", "--receipt", str(out)]) == 0
    assert json.loads(out.read_text())["status"] == "BLOCKED"


def test_diff_cap_measures_the_staged_set_including_new_files() -> None:
    """git diff HEAD omits untracked files, so a new-file-only fix measured
    zero and a large new file escaped both the cap and the commit."""
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert '"git", "diff", "--cached", "--numstat"' in source
    assert '"git", "add", "-A"' in source
    assert '"git", "add", "-u"' not in source


def test_nightly_target_requires_a_completed_run() -> None:
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert 'runs[0].get("status") == "completed"' in source


def test_workflow_keeps_the_mailbox_overlay_out_of_the_worktree() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "hardening-lane.yml").read_text()
    assert "LANE_MAILBOX_ROOT" in text
    assert "git checkout origin/loop-tasks --" not in text, (
        "overlay must not land in the worktree the lane commits from"
    )
