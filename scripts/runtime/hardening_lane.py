#!/usr/bin/env python3
"""Hardening lane v1 — capped, draft-only, receipt-emitting (PR-E).

One run = at most ONE unit of hardening work, selected deterministically,
executed by a fresh-context headless agent, verified by focused tests, and
delivered ONLY as a draft PR labeled `mike-watch` + `walk-ready` that enters
the §5 review pipeline. The lane never merges, never pushes to main, and
never exceeds its caps — caps live in the WORKFLOW (timeout-minutes, env
ceilings) and are re-checked here, not trusted to any prompt.

Target selection order (first hit wins):
1. A ready mailbox task for recipient `hardening-lane`
   (roaming_mailbox ready-set; requires the PR-D join — absent = skip).
2. A failing test from the most recent nightly-tests run on main.
3. Nothing → exit 0 with a NO_WORK receipt. An idle lane is a good lane.

Agent invocation is operator-configured: the workflow passes the command in
DHARMA_LANE_AGENT_CMD (from a repo secret). No secret → the lane refuses
with a BLOCKED receipt instead of pretending (fail closed, loudly honest).

Receipts are run artifacts + step summary, never committed to git
(CLAUDE.md: runtime receipts never enter git).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_DIFF_LINES = int(os.environ.get("LANE_MAX_DIFF_LINES", "600"))
MAX_AGENT_SECONDS = int(os.environ.get("LANE_MAX_AGENT_SECONDS", "1200"))
LANE_BRANCH_PREFIX = "lane/hardening-"
LANE_LABELS = ("mike-watch", "walk-ready", "lane-output")
RECIPIENT = "hardening-lane"
# The DHARMA_LANE_AGENT_CMD secret selects one of these literal argv
# templates by key — it is a NAME, not a shell string. No environment-derived
# text ever enters the subprocess argv (PR #1162 alerts 537-540), and a
# mis-set secret cannot smuggle flags or executables: extending this table is
# a code change through the normal review door.
AGENT_COMMANDS: dict[str, list[str]] = {
    "claude": ["claude", "-p"],
    "claude-npx": ["npx", "-y", "@anthropic-ai/claude-code", "-p"],
    "codex": ["codex", "exec"],
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run(cmd: list[str], *, timeout: int = 300, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          check=False, cwd=cwd)


def receipt(payload: dict, out: Path) -> None:
    payload.setdefault("schema", "dharma.hardening_lane_receipt.v1")
    payload.setdefault("generated_at", _utc_stamp())
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


def select_target(repo: str) -> dict | None:
    """First ready mailbox task, else newest nightly failure, else None."""
    try:
        from dharma_swarm.roaming_mailbox import RoamingMailbox

        mailbox = RoamingMailbox()
        ready = getattr(mailbox, "ready_tasks", None)
        if callable(ready):
            tasks = [t for t in ready(recipient=RECIPIENT)]
            if tasks:
                task = tasks[0]
                return {"kind": "mailbox", "task_id": task.task_id,
                        "summary": task.summary, "body": task.body}
    except Exception as exc:  # noqa: BLE001 - selection must never crash the lane
        print(f"mailbox selection unavailable: {exc}", file=sys.stderr)

    result = _run([
        "gh", "api",
        f"repos/{repo}/actions/workflows/nightly-tests.yml/runs?branch=main&per_page=1",
    ])
    if result.returncode == 0:
        try:
            runs = json.loads(result.stdout).get("workflow_runs", [])
        except json.JSONDecodeError:
            runs = []
        if runs and runs[0].get("conclusion") == "failure":
            return {"kind": "nightly_failure", "run_url": runs[0].get("html_url", ""),
                    "summary": "repair the failing nightly on main",
                    "body": f"Nightly run failed: {runs[0].get('html_url', '')}"}
    return None


def diff_line_count() -> int:
    result = _run(["git", "diff", "--numstat", "HEAD"])
    total = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            for cell in parts[:2]:
                if cell.isdigit():
                    total += int(cell)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hardening lane v1")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--receipt", required=True, help="receipt output path")
    args = parser.parse_args(argv)
    out = Path(args.receipt)

    target = select_target(args.repo)
    if target is None:
        receipt({"status": "NO_WORK",
                 "reason": "no ready mailbox task, nightly green"}, out)
        return 0

    agent_choice = os.environ.get("DHARMA_LANE_AGENT_CMD", "").strip()
    if not agent_choice:
        receipt({"status": "BLOCKED", "target": target,
                 "reason": "DHARMA_LANE_AGENT_CMD secret not configured — "
                           "lane refuses to improvise an agent"}, out)
        return 0
    agent_argv = AGENT_COMMANDS.get(agent_choice)
    if agent_argv is None:
        receipt({"status": "BLOCKED", "target": target,
                 "reason": f"agent selector {agent_choice!r} is not in the "
                           f"allowlist {sorted(AGENT_COMMANDS)} — the secret "
                           "names a template, never a shell string"}, out)
        return 0

    branch = f"{LANE_BRANCH_PREFIX}{_utc_stamp()}"
    _run(["git", "checkout", "-B", branch])

    prompt = (
        "You are the hardening lane. ONE task, fresh context, no scope creep.\n"
        f"Task: {target['summary']}\n{target['body']}\n"
        "Constraints: tests/typing/security hardening only; keep the diff "
        f"under {MAX_DIFF_LINES} changed lines; run the focused tests for "
        "everything you touch; never touch .github/workflows, scripts/runtime/"
        "pr_merge_control.py, or any referee-layer path."
    )
    try:
        # agent_argv is a literal template from AGENT_COMMANDS; prompt is
        # composed above from repo-internal task data. Nothing here derives
        # from the environment.
        agent = subprocess.run(
            [*agent_argv, prompt],
            capture_output=True, text=True, timeout=MAX_AGENT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        receipt({"status": "CAP_HIT", "cap": "agent_seconds",
                 "target": target, "limit": MAX_AGENT_SECONDS}, out)
        return 0

    lines = diff_line_count()
    if lines == 0:
        receipt({"status": "NO_DIFF", "target": target,
                 "agent_exit": agent.returncode}, out)
        return 0
    if lines > MAX_DIFF_LINES:
        _run(["git", "checkout", "--", "."])
        receipt({"status": "CAP_HIT", "cap": "diff_lines", "observed": lines,
                 "limit": MAX_DIFF_LINES, "target": target}, out)
        return 0

    tests = _run(["make", "test-fast"], timeout=1800)
    if tests.returncode != 0:
        receipt({"status": "TESTS_RED", "target": target,
                 "tail": tests.stdout[-2000:]}, out)
        return 0

    _run(["git", "add", "-u"])
    _run(["git", "commit", "-m",
          f"harden: {target['summary'][:60]} [hardening-lane]"])
    push = _run(["git", "push", "-u", "origin", branch])
    if push.returncode != 0:
        receipt({"status": "PUSH_FAILED", "target": target,
                 "stderr": push.stderr[-1000:]}, out)
        return 1
    pr = _run([
        "gh", "pr", "create", "--repo", args.repo, "--draft",
        "--title", f"harden: {target['summary'][:60]}",
        "--body", (
            "Hardening-lane output (capped, draft-only). Target:\n\n"
            f"- {target}\n\nTests: `make test-fast` green at cap. "
            "Enters the §5 review pipeline; operator flips ready."
        ),
        "--label", ",".join(LANE_LABELS),
    ])
    receipt({"status": "DRAFT_PR_OPENED" if pr.returncode == 0 else "PR_CREATE_FAILED",
             "target": target, "branch": branch, "diff_lines": lines,
             "pr_output": (pr.stdout + pr.stderr)[-500:]}, out)
    return 0 if pr.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
