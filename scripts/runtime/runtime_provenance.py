#!/usr/bin/env python3
"""Runtime provenance — which code are the live daemons actually executing?

The claims-vs-reality failure mode this closes: a fix lands on a branch,
the operator believes it is live, but the running process was started from
a different worktree (84+ exist) at a different commit. Every Honest Spine
phase is unverifiable without this check, so it runs inside `make onboard`.

For each live process matching the live-ops census patterns, this reports:
  - pid, process key
  - working directory (via lsof) and its git toplevel
  - branch + HEAD commit of that worktree
  - ahead/behind counts vs origin/main and dirty-file count

Exit codes: 0 = all provenance resolved (or no daemons running);
1 = at least one daemon runs code that is behind origin/main or dirty
    (only when --strict is passed).

Read-only: never mutates git state, never signals processes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Subset of live_ops_census PROCESS_PATTERNS that execute repo Python code.
# (nats / dashboards / VMs excluded: their provenance is not repo-git-shaped.)
CODE_BEARING_PATTERNS: dict[str, str] = {
    "dharma_daemon": r"dharma_swarm\.dgc_cli orchestrate-live",
    "dharma_cron": r"dharma_swarm\.dgc_cli cron daemon",
    "nats_a2a_bridge": r"dharma_swarm\.operator_core\.nats_a2a_bridge",
    "dashboard_api": r"uvicorn api\.main:app|api\.main:app",
    "forge_hydra": r"codex_overnight_autopilot\.py|forge-reality-arena-master",
    "self_improve": r"dharma_swarm\.self_improve",
}


def _run(args: list[str], cwd: Path | None = None, timeout: float = 10.0) -> str:
    try:
        out = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        return out.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _live_processes() -> list[tuple[str, int, str]]:
    ps = _run(["ps", "-axo", "pid=,command="])
    rows: list[tuple[str, int, str]] = []
    for line in ps.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, command = line.partition(" ")
        for key, pattern in CODE_BEARING_PATTERNS.items():
            if re.search(pattern, command):
                try:
                    rows.append((key, int(pid_str), command.strip()[:160]))
                except ValueError:
                    pass
                break
    return rows


def _cwd_of(pid: int) -> str:
    out = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def _git_provenance(workdir: str) -> dict[str, object]:
    if not workdir:
        return {"resolved": False, "reason": "no cwd (lsof denied or process gone)"}
    top = _run(["git", "-C", workdir, "rev-parse", "--show-toplevel"])
    if not top:
        return {"resolved": False, "reason": f"not a git worktree: {workdir}"}
    branch = _run(["git", "-C", top, "rev-parse", "--abbrev-ref", "HEAD"])
    head = _run(["git", "-C", top, "rev-parse", "--short", "HEAD"])
    dirty = _run(["git", "-C", top, "status", "--porcelain"])
    dirty_count = len([ln for ln in dirty.splitlines() if ln.strip()])
    counts = _run(
        ["git", "-C", top, "rev-list", "--left-right", "--count",
         "HEAD...origin/main"],
    )
    ahead, behind = 0, 0
    if counts:
        parts = counts.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
    return {
        "resolved": True,
        "worktree": top,
        "branch": branch,
        "head": head,
        "ahead_of_main": ahead,
        "behind_main": behind,
        "dirty_files": dirty_count,
    }


def collect() -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for key, pid, command in _live_processes():
        prov = _git_provenance(_cwd_of(pid))
        report.append({"process": key, "pid": pid, "command": command, **prov})
    return report


def render(report: list[dict[str, object]]) -> str:
    if not report:
        return ("  no code-bearing daemons running — nothing claims to be live\n"
                "  (if a daemon should be running, that absence is itself a finding)")
    lines: list[str] = []
    for row in report:
        if not row.get("resolved"):
            lines.append(
                f"  ?? {row['process']} (pid {row['pid']}): "
                f"UNRESOLVED — {row.get('reason', 'unknown')}"
            )
            continue
        drift = []
        if row["behind_main"]:
            drift.append(f"behind main by {row['behind_main']}")
        if row["dirty_files"]:
            drift.append(f"{row['dirty_files']} dirty files")
        flag = "!!" if drift else "ok"
        drift_note = f" [{'; '.join(drift)}]" if drift else ""
        lines.append(
            f"  {flag} {row['process']} (pid {row['pid']}): "
            f"{row['branch']}@{row['head']} in {row['worktree']}{drift_note}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 if any daemon is behind origin/main or dirty",
    )
    args = parser.parse_args()
    report = collect()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))
    if args.strict:
        for row in report:
            if not row.get("resolved"):
                return 1
            if row.get("behind_main") or row.get("dirty_files"):
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
