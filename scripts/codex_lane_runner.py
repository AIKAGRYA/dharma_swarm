#!/usr/bin/env python3
"""Durable Codex lane runner.

The runner keeps Codex work out of the operator's active worktrees by creating
one dedicated git worktree per lane, then records every cycle under
~/.dharma/codex_lanes so the lane remains discoverable after terminal death.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


DEFAULT_REPO = Path.home() / "dharma_swarm"
DEFAULT_STATE_ROOT = Path.home() / ".dharma" / "codex_lanes"


@dataclass(frozen=True)
class GitState:
    branch: str
    head: str
    dirty: bool
    changed: list[str]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", lowered).strip("-._")
    return normalized[:80] or "codex-lane"


def run_cmd(
    cmd: Sequence[str],
    *,
    cwd: Path,
    timeout: int = 60,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd),
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")


def git_state(worktree: Path) -> GitState:
    status = run_cmd(["git", "status", "--porcelain=v1", "--branch"], cwd=worktree)
    branch = "unknown"
    changed: list[str] = []
    if status.returncode == 0:
        lines = status.stdout.splitlines()
        if lines and lines[0].startswith("## "):
            branch = lines[0][3:].strip()
        changed = [line.rstrip() for line in lines[1:] if line.strip()]
    head = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=worktree)
    return GitState(
        branch=branch,
        head=head.stdout.strip() if head.returncode == 0 else "unknown",
        dirty=bool(changed),
        changed=changed[:80],
    )


def ensure_worktree(
    *,
    repo_root: Path,
    worktree: Path,
    branch: str,
    base_ref: str,
) -> None:
    if worktree.exists():
        probe = run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=worktree)
        if probe.returncode == 0:
            return
        raise SystemExit(f"worktree path exists but is not a git worktree: {worktree}")

    branch_exists = run_cmd(["git", "show-ref", "--verify", f"refs/heads/{branch}"], cwd=repo_root)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists.returncode == 0:
        cmd = ["git", "worktree", "add", str(worktree), branch]
    else:
        cmd = ["git", "worktree", "add", "-b", branch, str(worktree), base_ref]
    result = run_cmd(cmd, cwd=repo_root, timeout=300)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)


def read_mission(args: argparse.Namespace) -> str:
    if args.mission_file:
        return Path(args.mission_file).expanduser().read_text(encoding="utf-8").strip()
    if args.mission:
        return args.mission.strip()
    return (
        "Run a bounded Codex maintenance lane. Inspect the worktree, choose one "
        "safe high-leverage cleanup or audit slice, implement only in this lane "
        "worktree, verify, and leave a clear handoff."
    )


def build_prompt(
    *,
    lane: str,
    mission: str,
    worktree: Path,
    lane_dir: Path,
    cycle: int,
    before: GitState,
    previous_summary: str,
) -> str:
    changed = "\n".join(f"- {line}" for line in before.changed) or "- clean"
    return f"""You are running a durable Codex lane.

Lane: {lane}
Cycle: {cycle}
Worktree: {worktree}
Lane state dir: {lane_dir}

Mission:
{mission}

Before git state:
- branch: {before.branch}
- head: {before.head}
- dirty: {before.dirty}
- changed:
{changed}

Previous summary:
{previous_summary or "(none)"}

Hard rules:
- Work only inside this lane worktree and the lane state dir.
- Do not edit the operator's active main/root worktrees.
- Never push.
- Commit only if you have a coherent, verified checkpoint.
- If the worktree is dirty at start, inspect it and continue carefully; do not erase it.
- Keep the slice bounded. Prefer one small improvement, audit, or cleanup per cycle.
- Write durable notes into the lane state dir when useful.

End with exactly:
RESULT: <one short paragraph>
FILES: <comma-separated paths or "none">
TESTS: <commands run or "not run">
BLOCKERS: <short note or "none">
NEXT: <next bounded action>
"""


def codex_cmd(args: argparse.Namespace, *, worktree: Path, lane_dir: Path, output: Path) -> list[str]:
    cmd = ["codex", "exec"]
    if args.model:
        cmd.extend(["-m", args.model])
    if args.dangerous_full_auto:
        cmd.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        cmd.extend(["-s", "workspace-write"])
    cmd.extend(["-C", str(worktree), "--add-dir", str(lane_dir), "-o", str(output), "-"])
    return cmd


def run_cycle(
    args: argparse.Namespace,
    *,
    lane: str,
    mission: str,
    worktree: Path,
    lane_dir: Path,
    run_dir: Path,
    cycle: int,
) -> dict[str, Any]:
    before = git_state(worktree)
    previous_summary_path = lane_dir / "latest_summary.txt"
    previous_summary = (
        previous_summary_path.read_text(encoding="utf-8", errors="ignore")
        if previous_summary_path.exists()
        else ""
    )
    prompt = build_prompt(
        lane=lane,
        mission=mission,
        worktree=worktree,
        lane_dir=lane_dir,
        cycle=cycle,
        before=before,
        previous_summary=previous_summary[-3000:],
    )
    prompts = run_dir / "prompts"
    outputs = run_dir / "outputs"
    logs = run_dir / "logs"
    prompts.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    prompt_file = prompts / f"cycle_{cycle:03d}.md"
    output_file = outputs / f"cycle_{cycle:03d}_last_message.txt"
    stdout_file = logs / f"cycle_{cycle:03d}.log"
    prompt_file.write_text(prompt, encoding="utf-8")

    start = time.time()
    timed_out = False
    try:
        proc = run_cmd(
            codex_cmd(args, worktree=worktree, lane_dir=lane_dir, output=output_file),
            cwd=worktree,
            input_text=prompt,
            timeout=args.cycle_timeout,
        )
        rc = proc.returncode
        stdout = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        stdout = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + (
            (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        )

    stdout_file.write_text(stdout, encoding="utf-8", errors="ignore")
    summary = output_file.read_text(encoding="utf-8", errors="ignore") if output_file.exists() else stdout
    previous_summary_path.write_text(summary.strip() + "\n", encoding="utf-8")
    after = git_state(worktree)
    snapshot = {
        "cycle": cycle,
        "ts": utc_iso(),
        "duration_sec": round(time.time() - start, 2),
        "rc": rc,
        "timed_out": timed_out,
        "prompt_file": str(prompt_file),
        "output_file": str(output_file),
        "stdout_file": str(stdout_file),
        "before": asdict(before),
        "after": asdict(after),
        "summary": summary.strip()[-4000:],
    }
    write_json(lane_dir / "heartbeat.json", {**snapshot, "run_dir": str(run_dir), "worktree": str(worktree)})
    write_json(run_dir / "latest.json", snapshot)
    append_text(run_dir / "cycles.jsonl", json.dumps(snapshot, sort_keys=True))
    append_text(
        run_dir / "report.md",
        f"## Cycle {cycle:03d}\n\n- ts: {snapshot['ts']}\n- rc: {rc}\n- timed_out: {timed_out}\n- after_dirty: {after.dirty}\n\n{summary.strip()}\n",
    )
    return snapshot


def write_lane_readme(lane_dir: Path, *, lane: str, worktree: Path, session: str) -> None:
    text = f"""# Codex Lane: {lane}

- worktree: `{worktree}`
- tmux session: `{session}`
- heartbeat: `{lane_dir / 'heartbeat.json'}`
- latest run: `{lane_dir / 'latest_run.txt'}`
- report: see `runs/*/report.md`

Commands:

```bash
scripts/status_codex_lane_tmux.sh {lane}
tmux attach -t {session}
scripts/stop_codex_lane_tmux.sh {lane}
```
"""
    (lane_dir / "README.md").write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--mission", default="")
    parser.add_argument("--mission-file", default="")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO))
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--branch", default="")
    parser.add_argument("--worktree", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--hours", type=float, default=0.0, help="0 means continuous until stopped.")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--cycle-timeout", type=int, default=3600)
    parser.add_argument("--dangerous-full-auto", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--prepare-only", action="store_true", help="Create state/worktree metadata and exit before Codex runs.")
    args = parser.parse_args(argv)

    lane = slug(args.lane)
    repo_root = Path(args.repo_root).expanduser()
    state_root = Path(args.state_root).expanduser()
    lane_dir = state_root / lane
    worktree = Path(args.worktree).expanduser() if args.worktree else state_root / "worktrees" / lane
    branch = args.branch.strip() or f"codex-lane/{lane}"
    run_dir = lane_dir / "runs" / utc_stamp()
    mission = read_mission(args)
    session = f"codex_lane_{lane}"[:80]

    lane_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    ensure_worktree(repo_root=repo_root, worktree=worktree, branch=branch, base_ref=args.base_ref)
    write_lane_readme(lane_dir, lane=lane, worktree=worktree, session=session)
    (lane_dir / "latest_run.txt").write_text(str(run_dir), encoding="utf-8")
    write_json(
        lane_dir / "manifest.json",
        {
            "lane": lane,
            "branch": branch,
            "base_ref": args.base_ref,
            "repo_root": str(repo_root),
            "worktree": str(worktree),
            "lane_dir": str(lane_dir),
            "run_dir": str(run_dir),
            "created_at": utc_iso(),
            "model": args.model,
            "dangerous_full_auto": args.dangerous_full_auto,
            "poll_seconds": args.poll_seconds,
            "cycle_timeout": args.cycle_timeout,
        },
    )
    (lane_dir / "mission.md").write_text(mission.rstrip() + "\n", encoding="utf-8")
    if args.prepare_only:
        write_json(
            lane_dir / "heartbeat.json",
            {
                "ts": utc_iso(),
                "lane": lane,
                "run_dir": str(run_dir),
                "worktree": str(worktree),
                "prepared_only": True,
                "git": asdict(git_state(worktree)),
            },
        )
        return 0

    end_at = time.time() + args.hours * 3600 if args.hours > 0 else None
    cycle = 0
    while True:
        cycle += 1
        run_cycle(args, lane=lane, mission=mission, worktree=worktree, lane_dir=lane_dir, run_dir=run_dir, cycle=cycle)
        if args.once:
            break
        if args.max_cycles and cycle >= args.max_cycles:
            break
        if end_at is not None and time.time() >= end_at:
            break
        time.sleep(max(1, args.poll_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
