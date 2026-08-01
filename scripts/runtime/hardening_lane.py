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
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_DIFF_LINES = int(os.environ.get("LANE_MAX_DIFF_LINES", "600"))
MAX_AGENT_SECONDS = int(os.environ.get("LANE_MAX_AGENT_SECONDS", "1200"))
LANE_BRANCH_PREFIX = "lane/hardening-"
# How many lane drafts may be open at once. One keeps the operator's triage
# surface to a single PR; raise deliberately.
MAX_OPEN_LANE_DRAFTS = int(os.environ.get("LANE_MAX_OPEN_DRAFTS", "1"))
# Agent + tests must fit inside the job envelope with room to write the
# receipt: 1200 + 1500 = 45 min under a 65-minute job timeout.
MAX_TEST_SECONDS = int(os.environ.get("LANE_MAX_TEST_SECONDS", "1500"))
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


# Resolved ONCE at import, which is before the agent subprocess exists. The
# agent runs as the same user as the lane and can write an executable into
# any writable directory already on PATH; a fake `git` or `gh` would then
# intercept the privileged commit/push/pr-create with GH_TOKEN in scope, and
# GIT_CONFIG_GLOBAL=/dev/null offers nothing because the attack never touches
# git config. A fake `make` is an integrity bypass rather than a credential
# one: exit 0 and every unverified diff reads as TESTS_GREEN.
#
# This removes the drop-a-binary-earlier-in-PATH move. It does NOT make the
# lane safe against a same-user agent that overwrites the resolved file
# itself — only a delivery step in a checkout and process the agent never
# touched does that, and that is still unbuilt (Greptile on PR #1162).
GIT_BIN = shutil.which("git") or "git"
GH_BIN = shutil.which("gh") or "gh"
MAKE_BIN = shutil.which("make") or "make"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run(cmd: list[str], *, timeout: int = 300, cwd: str | None = None,
         env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              check=False, cwd=cwd, env=env)
    except FileNotFoundError as exc:
        # A missing binary is a failed command, not a crashed lane: callers
        # already treat a nonzero return as fail-closed.
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


# The lane runs git in the SAME checkout the agent just wrote to, so every
# git-executes-a-program vector reachable from that checkout is in scope for
# the privileged commit and push, with the write-enabled GH_TOKEN present.
# Greptile found three on PR #1162 in succession — .git/hooks/, then
# core.fsmonitor, then gpg.program via commit.gpgSign — and the list does not
# end there (filter.*.clean runs on `git add`, credential.helper runs on
# `git push`, url.*.insteadOf redirects the push itself).
#
# So the PRIMARY control is not a denylist: .git/config is captured before the
# agent runs and restored byte-for-byte afterwards, which neutralizes every
# config-driven vector at once, including ones not yet named. The `-c` flags
# below are the second layer for the vectors already known — command-line
# `-c` outranks file config, so they hold even if a restore silently fails.
GIT_NO_EXEC = (
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    # Signing invokes an agent-nameable program (Greptile on PR #1162).
    "-c", "commit.gpgSign=false",
    "-c", "tag.gpgSign=false",
    "-c", "gpg.program=/dev/null",
    "-c", "gpg.ssh.program=/dev/null",
    # ssh transport and the pager are programs too.
    "-c", "core.sshCommand=/dev/null",
    "-c", "core.pager=cat",
    # Single-valued execution keys, so a command-line -c genuinely wins over
    # a file value set at ANY time — including by a descendant racing the
    # restore. core.gitProxy is the payload Greptile demonstrated executing
    # with the write token during the push (PR #1162); askPass and
    # diff.external are the same shape. Verified with git 2.43:
    #   git -c core.gitProxy= config --get core.gitProxy   -> empty
    "-c", "core.gitProxy=",
    "-c", "core.askPass=",
    "-c", "diff.external=",
)
# NOT closable this way, and the reason isolation is still required: both
# credential.helper and url.<base>.insteadOf are MULTI-valued, so a -c value
# is APPENDED to the file's list rather than replacing it. Verified: with
# `credential.helper = !echo EVIL` in .git/config,
# `git -c credential.helper= config --get-all credential.helper` still lists
# the attacker's helper first. A descendant that writes either key after the
# restore check wins, and no in-process guard can prevent that.
GIT_UNCLOSABLE_IN_SHARED_CHECKOUT = ("credential.helper", "url.<base>.insteadOf")
# Kept as the old name for callers/tests that referenced it.
GIT_NO_HOOKS = GIT_NO_EXEC
GIT_CONFIG_PATH = Path(".git/config")

# Git reads THREE config scopes: system, global, local. Restoring
# .git/config covers only the local one, and the agent keeps a writable
# HOME — so $HOME/.gitconfig (or $XDG_CONFIG_HOME/git/config) could still
# supply credential.helper or url.*.insteadOf to the privileged push, which
# Greptile demonstrated end-to-end on PR #1162. These two variables make git
# load NO system and NO global config at all, which closes the remaining two
# scopes categorically rather than key by key:
#
#   $ GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
#       git config --get credential.helper   # exit 1: not found
#
# With the local restore, all three scopes are now accounted for.
GIT_TRUSTED_CONFIG_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git_env() -> dict[str, str]:
    """The lane's own environment with global and system git config disabled."""
    return {**os.environ, **GIT_TRUSTED_CONFIG_ENV}


def _git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Every git invocation in this lane: the known program-executing config
    keys forced off on the command line, and global/system config not loaded
    at all."""
    kwargs.setdefault("env", git_env())
    return _run([GIT_BIN, *GIT_NO_EXEC, *args], **kwargs)


def snapshot_git_config() -> bytes | None:
    """The repository-local git config as it stood before the agent ran."""
    try:
        return GIT_CONFIG_PATH.read_bytes()
    except OSError:
        return None


def git_config_restored(before: bytes | None) -> bool:
    """Put .git/config back exactly as it was; True if it is now trustworthy.

    False means the lane must not run a privileged git command in this
    checkout: an unrestorable config is an agent-controlled config.
    """
    if before is None:
        return False
    try:
        if GIT_CONFIG_PATH.read_bytes() != before:
            GIT_CONFIG_PATH.write_bytes(before)
        return GIT_CONFIG_PATH.read_bytes() == before
    except OSError:
        return False


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

        # LANE_MAILBOX_ROOT points at the operator-task overlay materialized
        # OUTSIDE the worktree (see .github/workflows/hardening-lane.yml):
        # the lane reads the mailbox without those files ever being able to
        # enter the diff it measures or the commit it delivers.
        mailbox_root = os.environ.get("LANE_MAILBOX_ROOT", "").strip()
        mailbox = RoamingMailbox(
            queue_root=Path(mailbox_root) if mailbox_root else None
        )
        ready = getattr(mailbox, "ready_tasks", None)
        if callable(ready):
            tasks = [t for t in ready(recipient=RECIPIENT)]
            if tasks:
                task = tasks[0]
                return {"kind": "mailbox", "task_id": task.task_id,
                        "summary": task.summary, "body": task.body}
    except Exception as exc:  # noqa: BLE001 - selection must never crash the lane
        print(f"mailbox selection unavailable: {exc}", file=sys.stderr)

    # Nightly selection is TRI-STATE. Returning None for "API failed",
    # "still running", "cancelled", or "timed out" made main() emit NO_WORK
    # with the reason "nightly green" — reporting a healthy sensor when the
    # sensor was actually unreadable (Codex on PR #1162).
    result = _run([
        GH_BIN, "api",
        f"repos/{repo}/actions/workflows/nightly-tests.yml/runs?branch=main&per_page=1",
    ])
    if result.returncode == 0:
        try:
            runs = json.loads(result.stdout).get("workflow_runs", [])
        except json.JSONDecodeError:
            runs = []
        # A run must be COMPLETED before its conclusion is final; an
        # in-progress run reporting a failure is not a verdict yet
        # (Greptile on PR #1162).
        if (runs and runs[0].get("status") == "completed"
                and runs[0].get("conclusion") == "failure"):
            return {"kind": "nightly_failure", "run_url": runs[0].get("html_url", ""),
                    "summary": "repair the failing nightly on main",
                    "body": f"Nightly run failed: {runs[0].get('html_url', '')}"}
        if runs and runs[0].get("status") == "completed" \
                and runs[0].get("conclusion") == "success":
            return None  # positively green: genuinely no work
        return {"kind": "nightly_unknown",
                "status": runs[0].get("status") if runs else "no runs",
                "conclusion": runs[0].get("conclusion") if runs else None}
    return {"kind": "nightly_unknown", "status": "api_error",
            "conclusion": None}


# Credentials the lane holds to open its draft PR, which the agent must not
# inherit: the job grants contents:write and pull-requests:write, so an
# agent with GH_TOKEN could push branches or alter PRs before the diff cap,
# the test run, or any review ever applied (Greptile on PR #1162). The agent
# needs none of them — the lane does every git and GitHub operation itself.
AGENT_STRIPPED_ENV_PREFIXES = ("GH_", "GITHUB_", "GIT_ASKPASS", "GIT_CONFIG",
                               "MERGEMASTERMIKE_", "ACTIONS_", "RUNNER_")
AGENT_STRIPPED_ENV_KEYS = {"GITHUB_TOKEN", "GH_TOKEN", "PR_CI_HEALTH_PUSH_TOKEN"}


def open_lane_drafts(repo: str) -> list[int] | None:
    """Open draft PRs this lane already delivered, or None if the query
    failed (the caller then refuses to deliver rather than guessing)."""
    result = _run([
        GH_BIN, "pr", "list", "--repo", repo, "--state", "open",
        "--label", "lane-output", "--json", "number,isDraft,headRefName",
        "--limit", "50",
    ])
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list):
        return None
    return [
        int(row["number"]) for row in rows
        if row.get("isDraft") and str(row.get("headRefName", "")).startswith(
            LANE_BRANCH_PREFIX
        )
    ]


def agent_env() -> dict[str, str]:
    """The child environment for the coding agent: the lane's own env minus
    every GitHub/Git credential channel. The agent's model API keys are
    passed through — they are what it legitimately needs."""
    return {
        key: value
        for key, value in os.environ.items()
        if key not in AGENT_STRIPPED_ENV_KEYS
        and not key.startswith(AGENT_STRIPPED_ENV_PREFIXES)
    }


# Paths the agent's change set may never include. The lane stages work
# produced by an untrusted agent, so staging is BY EXPLICIT PATH — never
# `git add -A`, which would sweep in secrets, generated reports, or the
# operator mailbox (CLAUDE.md hard rule; semgrep
# dharma.scripts-no-git-add-all; and Codex asked for the mailbox exclusion
# specifically on PR #1162).
STAGE_EXCLUDE_PREFIXES = ("roaming_mailbox/", "reports/", ".git/", ".venv/")
STAGE_EXCLUDE_SUFFIXES = (".env", ".pyc", ".pem", ".key")
STAGE_EXCLUDE_NAMES = {".env", "secrets.json"}


def agent_changed_paths() -> list[str]:
    """Every path the agent touched or created, minus the excluded set."""
    result = _git(["status", "--porcelain", "--untracked-files=all"])
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:  # rename: take the destination
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if not path or path.startswith(STAGE_EXCLUDE_PREFIXES):
            continue
        if path.endswith(STAGE_EXCLUDE_SUFFIXES):
            continue
        if Path(path).name in STAGE_EXCLUDE_NAMES:
            continue
        paths.append(path)
    return sorted(set(paths))


def stage_agent_changes() -> list[str]:
    """Stage the agent's change set by explicit path; return what was staged."""
    paths = agent_changed_paths()
    if paths:
        _git(["add", "--", *paths])
    return paths


def discard_agent_changes(paths: list[str]) -> None:
    """Undo an over-cap or failed agent run: unstage + restore tracked files,
    then remove exactly the untracked paths the agent created (never a
    blanket clean)."""
    _git(["reset", "-q", "HEAD", "--"])
    _git(["checkout", "-q", "HEAD", "--", "."])
    for path in paths:
        candidate = Path(path)
        if candidate.is_file():
            candidate.unlink(missing_ok=True)


def diff_line_count() -> int:
    """Changed lines in the STAGED set. `git diff HEAD` omits untracked
    files, so a new-file-only fix measured zero (reported NO_DIFF) and a
    large new file in a mixed change escaped the cap entirely — and then
    escaped the commit too, since `git add -u` never stages it. The caller
    stages the intended set first, so cap and commit measure the same
    thing (Greptile on PR #1162)."""
    result = _git(["diff", "--cached", "--numstat"])
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

    # Delivery ceiling BEFORE any work: without it every eligible run opened
    # another draft, so a persistently-failing nightly would produce an
    # unbounded pile of lane PRs for the operator to triage (Greptile on
    # PR #1162). Counted from live open lane drafts, not from local state,
    # so a restarted or concurrent run sees the same number.
    open_drafts = open_lane_drafts(args.repo)
    if open_drafts is None:
        receipt({"status": "BLOCKED",
                 "reason": "could not enumerate open lane drafts — refusing "
                           "to deliver without knowing the ceiling"}, out)
        return 0
    if len(open_drafts) >= MAX_OPEN_LANE_DRAFTS:
        receipt({"status": "CAP_HIT", "cap": "open_lane_drafts",
                 "observed": len(open_drafts), "limit": MAX_OPEN_LANE_DRAFTS,
                 "open": open_drafts}, out)
        return 0

    target = select_target(args.repo)
    if target is None:
        receipt({"status": "NO_WORK",
                 "reason": "no ready mailbox task; nightly positively green"}, out)
        return 0
    if target.get("kind") == "nightly_unknown":
        # Unreadable or non-terminal sensor: neither work nor health.
        receipt({"status": "BLOCKED",
                 "reason": "nightly state is not a verdict "
                           f"(status={target.get('status')!r}, "
                           f"conclusion={target.get('conclusion')!r}) — "
                           "refusing to claim the nightly is green"}, out)
        return 0

    agent_choice = os.environ.get("DHARMA_LANE_AGENT_CMD", "").strip()
    if not agent_choice:
        receipt({"status": "BLOCKED", "target": target,
                 "reason": "DHARMA_LANE_AGENT_CMD secret not configured — "
                           "lane refuses to improvise an agent"}, out)
        return 0
    # Bind the template by iteration, not AGENT_COMMANDS.get(agent_choice):
    # taint analysis propagates argument-taint through call returns, so the
    # selector must never be an argument to the expression producing argv.
    # agent_argv only ever binds to a literal template value.
    agent_argv = None
    for name, template in AGENT_COMMANDS.items():
        if name == agent_choice:
            agent_argv = list(template)
            break
    if agent_argv is None:
        receipt({"status": "BLOCKED", "target": target,
                 "reason": f"agent selector {agent_choice!r} is not in the "
                           f"allowlist {sorted(AGENT_COMMANDS)} — the secret "
                           "names a template, never a shell string"}, out)
        return 0

    branch = f"{LANE_BRANCH_PREFIX}{_utc_stamp()}"
    _git(["checkout", "-B", branch])

    # Captured AFTER the branch is created and BEFORE the agent runs, so the
    # restore target is the lane's own config, not whatever the agent leaves.
    config_before = snapshot_git_config()

    prompt = (
        "You are the hardening lane. ONE task, fresh context, no scope creep.\n"
        f"Task: {target['summary']}\n{target['body']}\n"
        "Constraints: tests/typing/security hardening only; keep the diff "
        f"under {MAX_DIFF_LINES} changed lines; run the focused tests for "
        "everything you touch; never touch .github/workflows, scripts/runtime/"
        "pr_merge_control.py, or any referee-layer path."
    )
    try:
        # The command argv is purely the literal template; the prompt travels
        # on stdin (claude -p and codex exec both read piped input). Task
        # text — which transitively derives from CLI args via select_target —
        # therefore never enters the command-argument position at all
        # (PR #1162 alerts 537-541: the taint flow was args.repo ->
        # select_target return -> prompt -> argv, present since v1).
        agent = subprocess.run(
            agent_argv,
            input=prompt,
            env=agent_env(),
            capture_output=True, text=True, timeout=MAX_AGENT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        receipt({"status": "CAP_HIT", "cap": "agent_seconds",
                 "target": target, "limit": MAX_AGENT_SECONDS}, out)
        return 0
    except FileNotFoundError:
        # The allowlisted selector names a binary the runner does not have.
        # A missing agent is a BLOCKED lane with a receipt, never an
        # uncaught crash that leaves no record (Codex on PR #1162).
        receipt({"status": "BLOCKED", "target": target,
                 "reason": f"agent binary {agent_argv[0]!r} is not installed "
                           "on this runner"}, out)
        return 0

    # Before ANY further git command touches this checkout: the agent may
    # have rewritten .git/config to make git run a program of its choosing
    # (gpg.program, filter.*.clean, credential.helper, url.*.insteadOf...).
    # Restoring the captured bytes closes the whole class; an unrestorable
    # config is an agent-controlled config, so the lane stops rather than
    # committing and pushing under it (Greptile on PR #1162).
    if not git_config_restored(config_before):
        receipt({"status": "BLOCKED", "target": target,
                 "reason": ".git/config could not be restored to its "
                           "pre-agent state — refusing to run privileged git "
                           "in an agent-controlled configuration"}, out)
        return 1

    # A nonzero agent exit means the work is unfinished — a tool, auth, or
    # context failure can leave a partial diff that happens to keep the
    # suite green. Never deliver that as a fix (Codex on PR #1162).
    if agent.returncode != 0:
        discard_agent_changes(agent_changed_paths())
        receipt({"status": "AGENT_FAILED", "target": target,
                 "agent_exit": agent.returncode,
                 "tail": (agent.stderr or agent.stdout or "")[-2000:]}, out)
        return 0

    # Stage the intended set FIRST, then measure it: the cap and the commit
    # must see the same change set, including files the agent created.
    staged = stage_agent_changes()
    lines = diff_line_count()
    if lines == 0:
        receipt({"status": "NO_DIFF", "target": target,
                 "agent_exit": agent.returncode}, out)
        return 0
    if lines > MAX_DIFF_LINES:
        discard_agent_changes(staged)
        receipt({"status": "CAP_HIT", "cap": "diff_lines", "observed": lines,
                 "limit": MAX_DIFF_LINES, "target": target,
                 "paths": staged[:20]}, out)
        return 0

    # Freeze the MEASURED content as a tree object, before anything else can
    # run. A tree SHA is content-addressed, so whatever the test process does
    # to the working tree afterwards, this identifier still resolves to
    # exactly the bytes the cap was computed over. The old flow re-staged
    # from the working tree after the tests, which let `make test-fast`
    # rewrite an already-measured file: Greptile's harness delivered a
    # 51-line commit under a receipt that said 2 (PR #1162).
    measured_tree = _git(["write-tree"]).stdout.strip()
    base_commit = _git(["rev-parse", "HEAD"]).stdout.strip()
    if not measured_tree or not base_commit:
        receipt({"status": "BLOCKED", "target": target,
                 "reason": "could not freeze the measured tree; refusing to "
                           "deliver content that was never pinned"}, out)
        return 1

    # Verification runs in the AGENT's de-privileged environment, not the
    # lane's. `make test-fast` executes a Makefile the agent may just have
    # edited, and conftest.py and pyproject.toml are equally agent-writable,
    # so this subprocess is agent-controlled code by construction — handing
    # it the lane's write-enabled GH_TOKEN would give the agent the very
    # credential the de-taint was built to withhold (Greptile on PR #1162).
    tests = _run([MAKE_BIN, "test-fast"], timeout=MAX_TEST_SECONDS, env=agent_env())
    if tests.returncode != 0:
        receipt({"status": "TESTS_RED", "target": target,
                 "tail": tests.stdout[-2000:]}, out)
        return 0

    # `make test-fast` is agent-controlled code too, so the config it ran
    # under gets restored again before the privileged commit and push — the
    # test process had every opportunity the agent process had.
    if not git_config_restored(config_before):
        receipt({"status": "BLOCKED", "target": target,
                 "reason": ".git/config was altered during the test run and "
                           "could not be restored — refusing to deliver"}, out)
        return 1

    # Commit the FROZEN tree, not the working tree. commit-tree takes the
    # content by SHA, so nothing the test run (or anything else) did to the
    # checkout after the measurement can enter the delivered commit — the
    # bytes pushed are the bytes the cap and the tests saw.
    commit = _git(["commit-tree", measured_tree, "-p", base_commit, "-m",
                   f"harden: {target['summary'][:60]} [hardening-lane]"])
    new_commit = commit.stdout.strip()
    if commit.returncode != 0 or not new_commit:
        receipt({"status": "BLOCKED", "target": target,
                 "reason": "commit-tree failed on the measured tree",
                 "stderr": commit.stderr[-1000:]}, out)
        return 1
    _git(["update-ref", f"refs/heads/{branch}", new_commit])
    push = _git(["push", "-u", "origin", f"{new_commit}:refs/heads/{branch}"])
    if push.returncode != 0:
        receipt({"status": "PUSH_FAILED", "target": target,
                 "stderr": push.stderr[-1000:]}, out)
        return 1
    pr = _run([
        GH_BIN, "pr", "create", "--repo", args.repo, "--draft",
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
