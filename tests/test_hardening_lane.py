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
