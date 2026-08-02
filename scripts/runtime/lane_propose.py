#!/usr/bin/env python3
"""Hardening lane, phase 1 of 2: PROPOSE (untrusted).

This is the half of the lane that runs agent code. It holds NO repository
write credential, opens no PR, and pushes nothing. Its entire output is a
`git bundle` containing exactly one commit, plus a receipt — handed to
`scripts/runtime/lane_deliver.py`, which runs as a separate job on a separate
runner and re-derives every fact for itself.

Why the split exists
--------------------
PR #1162 built this lane as one process: agent, tests, commit and push in a
single checkout under one UID, with `contents: write` in scope. Fourteen
review findings later, six of them reduced to a single fact — the agent and
the delivery step shared a machine, a filesystem, a user and a process
namespace, so every guard was a point-in-time check in a space the adversary
could still write to. Greptile's T-Rex drove a real `git push` to an
attacker-controlled repository through the whole guard set (`GIT_NO_EXEC`,
`GIT_CONFIG_GLOBAL=/dev/null`, a byte-for-byte `.git/config` restore, and a
frozen `commit-tree`). The measured reason it could not be closed in-process:
`git -c` overrides single-valued keys, but `credential.helper` and
`url.<base>.insteadOf` are MULTI-valued, so `-c` only APPENDS and the
attacker's entry survives.

So this file does not try to make a shared checkout safe. It gives up the
credential instead. Nothing here can push, because there is nothing here to
push with:

- the job declares `permissions: contents: read` (public repo: that token is
  worth no more than an anonymous fetch),
- the checkout uses `persist-credentials: false`, so `.git/config` never
  holds a token,
- the agent subprocess additionally gets a stripped environment.

Everything an agent could do to this checkout — rewrite `.git/config`, drop a
fake `git` on PATH, leave a descendant that races any check, install a
`filter.*.clean` — is now a local nuisance. The delivered bytes are named by
a content-addressed SHA inside a bundle, and the process that pushes them
never existed while the agent was alive.

Target selection order (first hit wins):
1. A ready mailbox task for recipient `hardening-lane`.
2. A failing test from the most recent nightly-tests run on main.
3. Nothing -> exit 0 with a NO_WORK receipt. An idle lane is a good lane.

Receipts are run artifacts, never committed (CLAUDE.md: runtime receipts
never enter git).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_DIFF_LINES = int(os.environ.get("LANE_MAX_DIFF_LINES", "600"))
MAX_AGENT_SECONDS = int(os.environ.get("LANE_MAX_AGENT_SECONDS", "1200"))
MAX_TEST_SECONDS = int(os.environ.get("LANE_MAX_TEST_SECONDS", "1500"))
MAX_OPEN_LANE_DRAFTS = int(os.environ.get("LANE_MAX_OPEN_DRAFTS", "1"))
LANE_BRANCH_PREFIX = "lane/hardening-"
RECIPIENT = "hardening-lane"
# How far back the lane looks for its own delivered PRs when deciding whether
# a mailbox task was already attempted. Generous, because reaching it fails
# closed (see attempted_task_ids) — at one delivery per run, three times a
# week, this is roughly six years of lane output.
ATTEMPT_HISTORY_LIMIT = int(os.environ.get("LANE_ATTEMPT_HISTORY_LIMIT", "1000"))

# The DHARMA_LANE_AGENT_CMD secret selects one of these literal argv
# templates by KEY — it is a name, not a shell string. No environment-derived
# text ever enters the subprocess argv, and a mis-set secret cannot smuggle
# flags or executables: extending this table is a code change through the
# normal review door.
AGENT_COMMANDS: dict[str, list[str]] = {
    "claude": ["claude", "-p"],
    "claude-npx": ["npx", "-y", "@anthropic-ai/claude-code", "-p"],
    "codex": ["codex", "exec"],
}

# Resolved once at import — before the agent subprocess exists. This removes
# the drop-a-binary-earlier-in-PATH move for the commands this phase runs.
# It does NOT defend against an agent that overwrites the resolved file
# itself, and after the split it no longer needs to: nothing in this process
# can deliver anything, so the worst outcome is a corrupt bundle, which
# lane_deliver.py verifies and rejects.
GIT_BIN = shutil.which("git") or "git"
GH_BIN = shutil.which("gh") or "gh"
MAKE_BIN = shutil.which("make") or "make"

# Credential channels withheld from the agent. After the split this is
# defence in depth rather than the boundary — the job has no write token to
# leak — but a stripped environment stays correct and costs nothing.
AGENT_STRIPPED_ENV_PREFIXES = ("GH_", "GITHUB_", "GIT_ASKPASS", "GIT_CONFIG",
                               "MERGEMASTERMIKE_", "ACTIONS_", "RUNNER_")
AGENT_STRIPPED_ENV_KEYS = {"GITHUB_TOKEN", "GH_TOKEN", "PR_CI_HEALTH_PUSH_TOKEN",
                           "LANE_DELIVERY_PUSH_TOKEN"}

# The model credential each selector legitimately needs — and only that one.
PROVIDER_KEY_FOR_SELECTOR = {
    "claude": "ANTHROPIC_API_KEY",
    "claude-npx": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
}
ALL_PROVIDER_KEYS = frozenset(PROVIDER_KEY_FOR_SELECTOR.values())

# Paths the agent's change set may never include. Staging is BY EXPLICIT
# PATH — never `git add -A`, which would sweep in secrets, generated
# reports, or the operator mailbox (CLAUDE.md hard rule; semgrep
# dharma.scripts-no-git-add-all). lane_deliver.py enforces its own copy of
# the referee denylist against the finished commit; this list is the
# author-side half and is not load-bearing on its own.
STAGE_EXCLUDE_PREFIXES = ("roaming_mailbox/", "reports/", ".git/", ".venv/")
STAGE_EXCLUDE_SUFFIXES = (".env", ".pyc", ".pem", ".key")
STAGE_EXCLUDE_NAMES = {".env", "secrets.json"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# Distinct exit codes so callers can tell "never ran" from "ran too long"
# without either escaping as an exception and killing the receipt.
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124


def _run(cmd: list[str], *, timeout: int = 300,
         env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, check=False, env=env)
    except FileNotFoundError as exc:
        # A missing binary is a failed command, not a crashed lane.
        return subprocess.CompletedProcess(cmd, EXIT_NOT_FOUND, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        # A command that outruns its budget is a CAP HIT with a receipt, not
        # an uncaught exception. `make test-fast` exceeding MAX_TEST_SECONDS
        # used to raise straight past the receipt write and emit_status(), so
        # the run ended NO_RECEIPT_WRITTEN — losing exactly the outcome the
        # budget exists to report.
        captured = exc.stdout or b"" if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        if isinstance(captured, bytes):
            captured = captured.decode("utf-8", "replace")
        return subprocess.CompletedProcess(cmd, EXIT_TIMEOUT, captured,
                                           f"timed out after {timeout}s")


def _run_bytes(cmd: list[str], *, timeout: int = 120
               ) -> subprocess.CompletedProcess:
    """`_run` for commands whose OUTPUT IS BYTES, with the same fail-closed arms.

    `_run` is `text=True`, which is right for every other command here and
    wrong for reading a blob: comparing a decoded `str` against the worktree's
    `bytes` is never equal, so routing the byte comparison through `_run`
    would flag every path and leave the lane permanently BLOCKED. Verified:

        text=True  -> 'x = 1\\n'  (str)
        bytes      -> b'x = 1\\n' (bytes)   worktree: b'x = 1\\n'

    What it MUST share with `_run` is the exception handling. A raw
    `subprocess.run` here let TimeoutExpired and FileNotFoundError escape past
    done()/receipt()/emit_status(), ending the run NO_RECEIPT_WRITTEN — the
    exact pathology finding #7 of this PR set out to close, reintroduced by
    the function that closed a different one. (Devin on #1200.)
    """
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout,
                              check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, EXIT_NOT_FOUND, b"",
                                           str(exc).encode())
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, EXIT_TIMEOUT, b"",
                                           f"timed out after {timeout}s".encode())


def _git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return _run([GIT_BIN, *args], **kwargs)


def receipt(payload: dict, out: Path) -> None:
    payload.setdefault("schema", "dharma.lane_propose_receipt.v1")
    payload.setdefault("generated_at", _utc_stamp())
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


def emit_status(status: str) -> None:
    """Publish the phase result as a job output so the delivery job's `if:`
    can skip cleanly instead of downloading an artifact that is not there."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"status={status}\n")


def agent_env(selector: str = "") -> dict[str, str]:
    """The child environment for a subprocess this phase does not trust.

    Strips every GitHub/Git credential channel, and passes through ONLY the
    model credential the named selector actually needs. Handing every agent
    both provider keys let a compromised `claude` exfiltrate or spend the
    OpenAI credential it has no use for, and vice versa (Codex on #1200).

    Called with no selector for the test run, which needs no model credential
    at all and therefore gets neither.
    """
    keep = PROVIDER_KEY_FOR_SELECTOR.get(selector)
    drop_provider = {k for k in ALL_PROVIDER_KEYS if k != keep}
    return {
        key: value
        for key, value in os.environ.items()
        if key not in AGENT_STRIPPED_ENV_KEYS
        and key not in drop_provider
        and not key.startswith(AGENT_STRIPPED_ENV_PREFIXES)
    }


# The delivery side writes exactly one of these per lane PR. Anchored to the
# line so the free-form task description in the `- Target:` blob below it can
# never be mistaken for a consumption record (lane_deliver.py builds the
# matching line; the two must move together).
CLAIM_RE = re.compile(r"^- Consumption claim: `(\{[^`]*\})`\s*$", re.MULTILINE)


def attempted_task_ids(repo: str) -> set[str] | None:
    """Task ids this lane has already delivered a PR for, in ANY state.

    The lane has no way to write a claim back to `loop-tasks` — the proposing
    job holds `contents: read` by design. So consumption is inferred from the
    lane's own output instead: every delivered PR body carries its target,
    including the task id.

    Without this, `ready_tasks()` kept returning the same oldest task after
    its draft closed and the open-draft ceiling cleared, so every scheduled
    run spent its whole agent budget re-doing one task while newer mailbox
    tasks starved behind it.

    Returns None if the query failed, so callers can fail closed rather than
    treat "unknown" as "nothing attempted".
    """
    result = _run([
        GH_BIN, "pr", "list", "--repo", repo, "--state", "all",
        "--label", "lane-output", "--json", "body,headRefName",
        "--limit", str(ATTEMPT_HISTORY_LIMIT),
    ])
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list):
        return None
    # Truncation is indistinguishable from completeness in this response, and
    # a truncated history reads as "never attempted" — which re-selects an old
    # task and starves the newer ones, the exact failure this function exists
    # to prevent. Greptile demonstrated it at the 100-PR boundary (#1200).
    # Hitting the cap therefore fails closed rather than answering from a
    # partial view.
    if len(rows) >= ATTEMPT_HISTORY_LIMIT:
        print(f"attempt history hit the {ATTEMPT_HISTORY_LIMIT}-PR cap; "
              "cannot prove a task is unattempted", file=sys.stderr)
        return None
    seen: set[str] = set()
    for row in rows:
        if not str(row.get("headRefName", "")).startswith(LANE_BRANCH_PREFIX):
            continue
        # Read ONLY the dedicated claim line, not the whole body.
        #
        # The body also carries a `- Target:` blob holding the operator's
        # free-form task description. Scanning everything meant any text that
        # contained `"task_id": "X"` would record X as attempted, and
        # select_target() has no way to un-attempt it — permanent starvation
        # of an unrelated task.
        #
        # Measured: that does NOT currently reproduce, because the blob is
        # written through json.dumps and the embedded quotes arrive escaped
        # (`\"task_id\"`), which this pattern does not match. But the safety
        # is incidental — it holds only while every task-derived field
        # reaches the body via json.dumps, which nothing enforces. Anchoring
        # to the claim line makes it explicit instead. (Devin on #1200.)
        #
        # Strict anchoring costs no compatibility: the lane has never run, so
        # no lane PR predates this format.
        for match in CLAIM_RE.finditer(str(row.get("body", ""))):
            try:
                claimed = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            task_id = claimed.get("task_id") if isinstance(claimed, dict) else None
            if isinstance(task_id, str) and task_id:
                seen.add(task_id)
    return seen


def select_target(repo: str) -> dict | None:
    """First unattempted ready mailbox task, else newest nightly failure."""
    try:
        from dharma_swarm.roaming_mailbox import RoamingMailbox

        mailbox_root = os.environ.get("LANE_MAILBOX_ROOT", "").strip()
        mailbox = RoamingMailbox(
            queue_root=Path(mailbox_root) if mailbox_root else None
        )
        ready = getattr(mailbox, "ready_tasks", None)
        if callable(ready):
            tasks = list(ready(recipient=RECIPIENT))
            if tasks:
                attempted = attempted_task_ids(repo)
                if attempted is None:
                    return {"kind": "mailbox_unknown"}
                fresh = [t for t in tasks if t.task_id not in attempted]
                if fresh:
                    task = fresh[0]
                    return {"kind": "mailbox", "task_id": task.task_id,
                            "summary": task.summary, "body": task.body}
                print(f"all {len(tasks)} ready mailbox task(s) already have a "
                      "lane PR; falling through", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - selection must never crash the lane
        print(f"mailbox selection unavailable: {exc}", file=sys.stderr)

    # Nightly selection is TRI-STATE. Returning None for "API failed", "still
    # running", "cancelled" or "timed out" would report a healthy sensor when
    # the sensor was merely unreadable.
    result = _run([
        GH_BIN, "api",
        f"repos/{repo}/actions/workflows/nightly-tests.yml/runs"
        "?branch=main&per_page=1",
    ])
    if result.returncode != 0:
        return {"kind": "nightly_unknown", "status": "api_error",
                "conclusion": None}
    try:
        runs = json.loads(result.stdout).get("workflow_runs", [])
    except json.JSONDecodeError:
        runs = []
    if not runs:
        return {"kind": "nightly_unknown", "status": "no runs",
                "conclusion": None}
    run = runs[0]
    # A run must be COMPLETED before its conclusion is final.
    if run.get("status") == "completed":
        if run.get("conclusion") == "failure":
            return {"kind": "nightly_failure",
                    "run_url": run.get("html_url", ""),
                    "summary": "repair the failing nightly on main",
                    "body": f"Nightly run failed: {run.get('html_url', '')}"}
        if run.get("conclusion") == "success":
            return None  # positively green: genuinely no work
    return {"kind": "nightly_unknown", "status": run.get("status"),
            "conclusion": run.get("conclusion")}


def open_lane_drafts(repo: str) -> list[int] | None:
    """Open lane drafts, or None if the query failed.

    Advisory here: this phase checks the ceiling early so a full agent run is
    not spent on work that could never be delivered. lane_deliver.py re-runs
    the same check as the authoritative gate, because only that job's answer
    is trustworthy at push time.
    """
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


def diff_line_count() -> int:
    """Changed lines in the STAGED set, so cap and commit measure the same
    thing (`git diff HEAD` omits untracked files, which let a new-file-only
    change escape the cap entirely).

    `--no-renames` for the same reason it is on the delivery side: git's
    default rename detection collapses a pure relocation into one
    `0\t0\told => new` record that sums to zero, so an agent could `git mv`
    an 800-line file and measure as a no-op. Measured on git 2.43:

        git diff --cached --numstat              ->  0 0 big.py => moved.py
        git diff --cached --no-renames --numstat ->  0 800 / 800 0

    Devin found this on lane_deliver; the propose-side cap is the FIRST gate
    and had the identical hole, so both move together (#1200).
    """
    result = _git(["diff", "--cached", "--no-renames", "--numstat"])
    total = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            for cell in parts[:2]:
                if cell.isdigit():
                    total += int(cell)
    return total


def index_transformed_paths(paths: list[str]) -> list[str]:
    """Staged paths whose INDEX bytes differ from their WORKTREE bytes.

    Why this is fail-closed: the measured-tree / tested-tree equality check
    below compares two `write-tree` results. Anything that transforms content
    on `git add` stores transformed bytes in `measured_tree` while
    `make test-fast` reads the untransformed worktree — and because the
    transform is deterministic, the re-add reproduces the same tree hash, so
    the equality check passes over content that was never tested.

    This measures the EFFECT, not the causes. Enumerating causes was a losing
    game, and it lost twice in one PR:

      * scanning `git config` for `filter.*.clean` at every scope caught the
        `filter.lfs.clean` that Git LFS registers GLOBALLY on GitHub runners,
        so the lane reported BLOCKED on every machine with git-lfs installed;
      * scoping that scan to `--local` to fix it then missed the agent's real
        reach. The agent runs as the same UID on the same runner, so it can
        write `$HOME/.gitconfig`, or set `extensions.worktreeConfig` and hide
        the filter in `$GIT_DIR/config.worktree`, neither of which `--local`
        reads (Devin on #1200).

    And no attribute list closes it either: `core.autocrlf=true` in the global
    config transforms CRLF to LF on add with NO `.gitattributes` at all, so
    every `check-attr` reads `unspecified` while the bytes still change.
    Measured, not assumed.

    Comparing the raw bytes is scope-independent, attribute-independent and
    mechanism-independent. It is also why `git diff-files` cannot be used
    here: git re-applies the clean filter when it compares, so a transformed
    file reads as unmodified — the same determinism that defeats the tree-hash
    check. `cat-file` returns the stored object without filtering.
    """
    found: list[str] = []
    for path in paths:
        target = Path(path)
        try:
            # Deletions have no delivered bytes to diverge; symlink blobs
            # store the target string, not file content.
            if target.is_symlink() or not target.is_file():
                continue
            worktree = target.read_bytes()
        except OSError:
            continue
        blob = _run_bytes([GIT_BIN, "cat-file", "-p", f":{path}"])
        if blob.returncode != 0:
            # Staged but unreadable from the index: cannot prove the bytes
            # match, so do not claim they do.
            found.append(path)
            continue
        if blob.stdout != worktree:
            found.append(path)
    return sorted(set(found))


def sanitize_summary(text: str, limit: int = 60) -> str:
    """A one-line, control-character-free subject.

    The summary originates from the mailbox or the nightly run rather than
    from the agent, but it reaches a commit message that lane_deliver.py
    turns into a PR title, so it is normalized at the boundary regardless.
    """
    collapsed = re.sub(r"\s+", " ", str(text)).strip()
    printable = "".join(ch for ch in collapsed if ch.isprintable())
    return printable[:limit] or "hardening lane output"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hardening lane — propose")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--bundle", required=True,
                        help="output path for the git bundle handed to deliver")
    args = parser.parse_args(argv)
    out = Path(args.receipt)

    def done(status: str, payload: dict, code: int = 0) -> int:
        receipt({"status": status, **payload}, out)
        emit_status(status)
        return code

    open_drafts = open_lane_drafts(args.repo)
    if open_drafts is None:
        return done("BLOCKED", {
            "reason": "could not enumerate open lane drafts — refusing to "
                      "spend an agent run without knowing the ceiling"})
    if len(open_drafts) >= MAX_OPEN_LANE_DRAFTS:
        return done("CAP_HIT", {"cap": "open_lane_drafts",
                                "observed": len(open_drafts),
                                "limit": MAX_OPEN_LANE_DRAFTS,
                                "open": open_drafts})

    target = select_target(args.repo)
    if target is None:
        return done("NO_WORK", {
            "reason": "no ready mailbox task; nightly positively green"})
    if target.get("kind") == "mailbox_unknown":
        return done("BLOCKED", {
            "reason": "could not enumerate previously-delivered lane PRs, so "
                      "there is no way to tell an unattempted mailbox task "
                      "from one already worked — refusing to re-spend the "
                      "agent budget on a guess"})
    if target.get("kind") == "nightly_unknown":
        return done("BLOCKED", {
            "reason": "nightly state is not a verdict "
                      f"(status={target.get('status')!r}, "
                      f"conclusion={target.get('conclusion')!r}) — refusing "
                      "to claim the nightly is green"})

    agent_choice = os.environ.get("DHARMA_LANE_AGENT_CMD", "").strip()
    if not agent_choice:
        return done("BLOCKED", {
            "target": target,
            "reason": "DHARMA_LANE_AGENT_CMD secret not configured — lane "
                      "refuses to improvise an agent"})
    # Bind the template by iteration, never AGENT_COMMANDS.get(agent_choice):
    # taint analysis propagates argument-taint through call returns, so the
    # selector must not be an argument to the expression producing argv.
    agent_argv = None
    for name, template in AGENT_COMMANDS.items():
        if name == agent_choice:
            agent_argv = list(template)
            break
    if agent_argv is None:
        return done("BLOCKED", {
            "target": target,
            "reason": f"agent selector {agent_choice!r} is not in the "
                      f"allowlist {sorted(AGENT_COMMANDS)} — the secret names "
                      "a template, never a shell string"})

    branch = f"{LANE_BRANCH_PREFIX}{_utc_stamp()}"
    base_commit = _git(["rev-parse", "HEAD"]).stdout.strip()
    if not base_commit:
        return done("BLOCKED", {"target": target,
                                "reason": "could not resolve the base commit"}, 1)
    _git(["checkout", "-B", branch])

    prompt = (
        "You are the hardening lane. ONE task, fresh context, no scope creep.\n"
        f"Task: {target['summary']}\n{target['body']}\n"
        "Constraints: tests/typing/security hardening only; keep the diff "
        f"under {MAX_DIFF_LINES} changed lines; run the focused tests for "
        "everything you touch; never touch .github/workflows, scripts/runtime/"
        "pr_merge_control.py, or any referee-layer path."
    )
    try:
        # argv is purely the literal template; the prompt travels on stdin
        # (claude -p and codex exec both read piped input), so task text
        # never enters the command-argument position.
        agent = subprocess.run(
            agent_argv, input=prompt, env=agent_env(agent_choice),
            capture_output=True, text=True, timeout=MAX_AGENT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return done("CAP_HIT", {"cap": "agent_seconds", "target": target,
                                "limit": MAX_AGENT_SECONDS})
    except FileNotFoundError:
        return done("BLOCKED", {
            "target": target,
            "reason": f"agent binary {agent_argv[0]!r} is not installed on "
                      "this runner"})

    # A nonzero agent exit means unfinished work — a tool, auth or context
    # failure can leave a partial diff that happens to keep the suite green.
    if agent.returncode != 0:
        return done("AGENT_FAILED", {
            "target": target, "agent_exit": agent.returncode,
            "tail": (agent.stderr or agent.stdout or "")[-2000:]})

    # Stage the intended set FIRST, then measure it, so the cap and the
    # delivered content see the same change set.
    staged = stage_agent_changes()
    lines = diff_line_count()
    if lines == 0:
        return done("NO_DIFF", {"target": target,
                                "agent_exit": agent.returncode})
    if lines > MAX_DIFF_LINES:
        return done("CAP_HIT", {"cap": "diff_lines", "observed": lines,
                                "limit": MAX_DIFF_LINES, "target": target,
                                "paths": staged[:20]})

    # Anything that transforms content on `git add` silently decouples "what
    # was tested" from "what ships" while still passing the equality check
    # below, so it is refused outright rather than accommodated.
    transformed = index_transformed_paths(staged)
    if transformed:
        return done("BLOCKED", {
            "target": target,
            "reason": "the staged index bytes differ from the worktree bytes "
                      "for these paths, so the tested bytes are not the "
                      "delivered bytes even though the tree hashes match",
            "transformed_paths": transformed[:20]})

    # Freeze the MEASURED content as a tree object. A tree SHA is
    # content-addressed, so whatever the test run does to the working tree
    # afterwards, this identifier still resolves to the bytes the cap was
    # computed over.
    measured_tree = _git(["write-tree"]).stdout.strip()
    if not measured_tree:
        return done("BLOCKED", {
            "target": target,
            "reason": "could not freeze the measured tree; refusing to hand "
                      "over content that was never pinned"}, 1)

    tests = _run([MAKE_BIN, "test-fast"], timeout=MAX_TEST_SECONDS,
                 env=agent_env())
    if tests.returncode == EXIT_TIMEOUT:
        return done("CAP_HIT", {"cap": "test_seconds", "target": target,
                                "limit": MAX_TEST_SECONDS,
                                "tail": tests.stdout[-2000:]})
    if tests.returncode != 0:
        return done("TESTS_RED", {"target": target,
                                  "tail": tests.stdout[-2000:]})

    # Freezing the tree guarantees "we deliver what we MEASURED"; on its own
    # it breaks "we deliver what we TESTED". `make test-fast` reads the
    # working tree, so a test that rewrites a measured file would test one
    # set of bytes while the bundle ships another. Re-stage and require an
    # identical hash: any drift means the green result does not cover the
    # delivery, so nothing ships.
    _git(["reset", "-q", "HEAD", "--"])
    if staged:
        _git(["add", "--", *staged])
    post_test_tree = _git(["write-tree"]).stdout.strip()
    if post_test_tree != measured_tree:
        return done("BLOCKED", {
            "target": target,
            "reason": "the test run altered the measured content, so the "
                      "green result does not cover what would be delivered",
            "measured_tree": measured_tree,
            "post_test_tree": post_test_tree}, 1)

    subject = sanitize_summary(target["summary"])
    commit = _git(["commit-tree", measured_tree, "-p", base_commit, "-m",
                   f"harden: {subject} [hardening-lane]"])
    new_commit = commit.stdout.strip()
    if commit.returncode != 0 or not new_commit:
        return done("BLOCKED", {
            "target": target,
            "reason": "commit-tree failed on the measured tree",
            "stderr": commit.stderr[-1000:]}, 1)
    _git(["update-ref", f"refs/heads/{branch}", new_commit])

    # The hand-off. A bundle is a self-contained, content-addressed pack: the
    # delivery job fetches the commit out of it WITHOUT ever checking the
    # tree out, so no `git add`, no clean filter, and no working-tree write
    # happens on the privileged side.
    bundle = Path(args.bundle)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    made = _git(["bundle", "create", str(bundle),
                 f"{base_commit}..refs/heads/{branch}"])
    if made.returncode != 0 or not bundle.exists():
        return done("BLOCKED", {
            "target": target,
            "reason": "could not write the delivery bundle",
            "stderr": made.stderr[-1000:]}, 1)

    return done("READY_TO_DELIVER", {
        "target": target,
        "branch": branch,
        "base_commit": base_commit,
        "commit": new_commit,
        "tree": measured_tree,
        "diff_lines": lines,
        "paths": staged[:50],
        "bundle_bytes": bundle.stat().st_size,
        # Every field above is a CLAIM by an untrusted phase. lane_deliver.py
        # re-derives each of them from the bundle and from origin, and its
        # answers are the ones that gate the push.
        "trust": "untrusted — informational only; deliver re-derives",
    })


if __name__ == "__main__":
    raise SystemExit(main())
