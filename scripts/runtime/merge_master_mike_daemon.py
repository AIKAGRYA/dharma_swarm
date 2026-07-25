#!/usr/bin/env python3
"""Merge Master Mike persistent PR-control nest.

This is a supervised coordination shell around ``pr_merge_control.py``. It is
not a new merge authority. By default it runs dry-run fanout cycles, writes
wake/action receipts, and keeps Mike visible through local state, tmux, and
launchd-ready entrypoints.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_UID = "merge_master_mike"
CALLSIGN = "merge-master-mike"
DISPLAY_NAME = "@MERGE_MASTER_MIKE"
AUTHORITY = "conditional_merge"
DEFAULT_DHARMA_HOME = Path("~/.dharma")
DEFAULT_PR_REVIEW_ROOT = Path("~/.dharma/pr_review")
DEFAULT_SESSION = "merge-master-mike"
DEFAULT_INTERVAL_S = 300.0


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str
    duration_s: float


@dataclass(frozen=True)
class MikePaths:
    dharma_home: Path
    agent_home: Path
    external_home: Path
    nest: Path
    logs: Path
    cycles: Path
    receipts: Path
    action_log: Path
    wake_receipts: Path
    actions_log: Path
    living_agent: Path
    status: Path
    latest_cycle: Path


Runner = Callable[[list[str], Path, float], CommandResult]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def mike_paths(dharma_home: str | Path = DEFAULT_DHARMA_HOME) -> MikePaths:
    root = expand(dharma_home)
    external = root / "external_agents" / AGENT_UID
    return MikePaths(
        dharma_home=root,
        agent_home=root / "agents" / AGENT_UID,
        external_home=external,
        nest=external / "nest",
        logs=external / "logs",
        cycles=external / "cycles",
        receipts=external / "receipts",
        action_log=external / "logs" / "action_log.jsonl",
        wake_receipts=external / "logs" / "wake_receipts.jsonl",
        actions_log=external / "logs" / "actions.jsonl",
        living_agent=root / "agents" / AGENT_UID / "living_agent.json",
        status=external / "nest" / "status.json",
        latest_cycle=external / "cycles" / "latest.json",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))


def last_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            last = line
    if not last:
        return None
    try:
        payload = json.loads(last)
    except json.JSONDecodeError:
        return {"parse_error": last}
    return payload if isinstance(payload, dict) else {"value": payload}


def default_runner(cmd: list[str], cwd: Path, timeout_s: float) -> CommandResult:
    started = time.monotonic()
    env = dict(os.environ)
    if env.get("DHARMA_MIKE_KEEP_GITHUB_ENV_TOKEN") != "1":
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_s,
        check=False,
    )
    return CommandResult(
        code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        duration_s=round(time.monotonic() - started, 3),
    )


def nats_probe_from_receipt(paths: MikePaths) -> dict[str, Any]:
    receipt_path = paths.dharma_home / "a2a_bus" / "nats_live_receipt.json"
    payload = read_json(receipt_path, {})
    if not isinstance(payload, dict) or not payload:
        return {
            "available": False,
            "ack_verified": False,
            "code": "NATS_RECEIPT_MISSING",
            "receipt_path": str(receipt_path),
        }
    return {
        "available": bool(payload.get("ack_verified")),
        "ack_verified": bool(payload.get("ack_verified")),
        "code": payload.get("code", "UNKNOWN"),
        "ack_tier": payload.get("ack_tier"),
        "endpoint": payload.get("endpoint"),
        "rtt_ms": payload.get("rtt_ms"),
        "ts": payload.get("ts"),
        "receipt_path": str(receipt_path),
    }


def nest_readme() -> str:
    return """# Merge Master Mike Nest

This directory is the local persistent nest for `@MERGE_MASTER_MIKE`.

Mike coordinates PR review and merge-gate hygiene. Mike may inspect, packet,
delegate, render comment drafts, recommend, and execute conditional merges only
when the deterministic merge gate is clean. Mike may not approve PRs, push,
edit source, post GitHub comments, perform unconditional merges, or bypass
governance.

Primary commands:

```bash
make mike-wake
make mike-status
make mike-cycle ARGS="--cycle-mode dry-run --max-prs 5"
make mike-cycle ARGS="--cycle-mode packet-only --max-prs 2"
make mike-cycle ARGS="--cycle-mode review --max-prs 1 --timeout-s 600"
make mike-tmux-start
make mike-tmux-stop
```

Core evidence:

- `logs/wake_receipts.jsonl`
- `logs/action_log.jsonl`
- `cycles/latest.json`
- `nest/status.json`
- `~/.dharma/pr_review/mike_fanout/<run-id>/receipt.json`

The default persistent loop is dry-run. Promote to packet-only, review, or
merge-authorized GitHub Actions only when the operator wants real queue work
and the reviewer credential lane is healthy.
"""


def delegation_lanes() -> dict[str, Any]:
    return {
        "schema": "dharma.merge_master_mike.delegation_lanes.v1",
        "agent_uid": AGENT_UID,
        "lanes": [
            {
                "agent": "copilot",
                "role": "GitHub-native review and repair lane",
                "transport": "GitHub Copilot plus A2A/NATS coordination packet",
                "required_receipt": "copilot_review_receipt.json",
            },
            {
                "agent": "codex",
                "role": "code-diff reviewer and deterministic verifier",
                "command": "make pr-run-codex PR=<number>",
                "required_receipt": "codex_review_receipt.json",
            },
            {
                "agent": "claude",
                "role": "semantic architecture reviewer and runtime-risk critic",
                "command": "make pr-run-claude PR=<number>",
                "required_receipt": "claude_review_receipt.json",
            },
            {
                "agent": "perplexity",
                "role": "external/current-state research and standards check",
                "transport": "NATS/A2A when available",
                "required_receipt": "research or blocker receipt",
            },
            {
                "agent": "devin",
                "role": "isolated repair branch implementer when a PR needs fixes",
                "transport": "NATS/A2A or GitHub task packet",
                "required_receipt": "repair branch and verification receipt",
            },
            {
                "agent": "hermes",
                "role": "fleet status, NATS/A2A, and operator-surface witness",
                "transport": "NATS/A2A",
                "required_receipt": "fleet or transport witness receipt",
            },
            {
                "agent": "warp_oz",
                "role": "Warp terminal-native operator lane for visible PR queue triage and manual wake checks",
                "transport": "NATS/A2A plus Warp.app visible terminal surface",
                "required_receipt": "warp_oz action, contact, or blocker receipt",
            },
        ],
        "forbidden": [
            "silent merge",
            "silent GitHub approval",
            "posting comments without explicit operator authorization",
            "source mutation from Mike's conditional-merge identity",
            "merge without clean deterministic gate",
            "treating tmux session existence as completion proof",
        ],
    }


def command_reference() -> str:
    return """# Merge Master Mike Command Surface

Local commands:

```bash
make mike-wake
make mike-status
make mike-cycle ARGS="--cycle-mode dry-run"
make mike-loop ARGS="--cycle-mode dry-run --interval-s 300"
make mike-tmux-start
make mike-tmux-stop
make mike-launchd-plist
```

Future GitHub comment commands should map to these local actions:

- `@merge-master-mike status` / `@mix_master_mike status` -> status receipt only
- `@merge-master-mike review` / `@mix_master_mike review` -> one bounded review fanout
- `@merge-master-mike full review` / `@mix_master_mike full review` -> packet plus reviewers
- `@merge-master-mike gate` / `@mix_master_mike gate` -> deterministic merge gate
- `@merge-master-mike delegate claude` -> Claude review lane only
- `@merge-master-mike delegate codex` -> Codex review lane only

The GitHub command surface must not mark human approval, approve a PR, perform
an unconditional merge, push source, or resolve review threads.
"""


def bootstrap_nest(paths: MikePaths, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    for directory in (paths.external_home, paths.nest, paths.logs, paths.cycles, paths.receipts, paths.agent_home):
        directory.mkdir(parents=True, exist_ok=True)
    for log_path in (paths.action_log, paths.wake_receipts, paths.actions_log):
        log_path.touch(exist_ok=True)
    write_text(paths.nest / "README.md", nest_readme())
    write_json(paths.nest / "delegation_lanes.json", delegation_lanes())
    write_text(paths.nest / "COMMANDS.md", command_reference())
    payload = build_status(paths, repo_root=repo_root)
    write_json(paths.status, payload)
    return payload


def update_living_agent(paths: MikePaths, *, status: str, now: str, wake_receipt: Path | None = None) -> None:
    living = read_json(paths.living_agent, {})
    if not isinstance(living, dict):
        living = {}
    living.setdefault("agent_uid", AGENT_UID)
    living.setdefault("callsign", CALLSIGN)
    living["status"] = status
    living["authority"] = AUTHORITY
    living["last_seen_at"] = now
    living["updated_at"] = now
    living.setdefault("memory_namespace", f"agent:{AGENT_UID}")
    living.setdefault("trace_identity", f"trace:{AGENT_UID}")
    living["autonomy_policy"] = {
        "mode": "conditional_merge_coordination",
        "requires_clean_merge_gate": True,
        "can_merge_when_gate_clean": True,
        "can_approve_prs": False,
        "can_push": False,
        "can_edit_source": False,
    }
    metadata = living.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["authority"] = AUTHORITY
        metadata["registration_stage"] = "conditional_merge"
        metadata["summon_aliases"] = [
            "@merge-master-mike",
            "@merge_master_mike",
            "@mix-master-mike",
            "@mix_master_mike",
            "@mike",
            "@terminal-review",
        ]
        metadata["summon_contract"] = (
            "Assume the merge_master_mike identity, inspect the PR queue and merge-gate receipts, "
            "coordinate required reviewer lanes, and execute merge only when the deterministic gate "
            "is clean and the configured reviewer quorum is present."
        )
    embodiment = living.get("current_embodiment")
    if isinstance(embodiment, dict):
        embodiment_metadata = embodiment.setdefault("metadata", {})
        if isinstance(embodiment_metadata, dict):
            embodiment_metadata["authority"] = AUTHORITY
            embodiment_metadata["registration_stage"] = "conditional_merge"
            embodiment_metadata["summon_aliases"] = metadata.get("summon_aliases") if isinstance(metadata, dict) else []
            embodiment_metadata["summon_contract"] = metadata.get("summon_contract") if isinstance(metadata, dict) else ""
    if wake_receipt is not None:
        living["last_wake_receipt"] = str(wake_receipt)
    write_json(paths.living_agent, living)


def record_action(paths: MikePaths, action: str, summary: str, *, outputs: dict[str, Any] | None = None, status: str = "ok") -> dict[str, Any]:
    payload = {
        "schema_version": "dharma_external_agent_action_log.v1",
        "event_id": f"{action}:{AGENT_UID}:{stamp()}",
        "timestamp": utc_now(),
        "agent_uid": AGENT_UID,
        "callsign": CALLSIGN,
        "display_name": DISPLAY_NAME,
        "model_identity": "openai/codex-runtime-selected",
        "authority": AUTHORITY,
        "action": action,
        "summary": summary,
        "outputs": outputs or {},
        "status": status,
    }
    append_jsonl(paths.action_log, payload)
    return payload


def record_wake(paths: MikePaths, *, repo_root: Path = REPO_ROOT, mode: str = "manual") -> dict[str, Any]:
    now = utc_now()
    bootstrap_nest(paths, repo_root=repo_root)
    receipt = {
        "schema_version": "dharma_merge_master_mike_wake_receipt.v1",
        "receipt_id": f"wake-{AGENT_UID}-{stamp()}",
        "timestamp": now,
        "agent_uid": AGENT_UID,
        "callsign": CALLSIGN,
        "display_name": DISPLAY_NAME,
        "authority": AUTHORITY,
        "mode": mode,
        "repo_root": str(repo_root),
        "pid": os.getpid(),
        "nats": nats_probe_from_receipt(paths),
        "allowed_actions": [
            "inspect_pr_queue",
            "create_review_packets",
            "delegate_review_lanes",
            "run_merge_gate",
            "render_comment_drafts",
            "write_receipts",
            "conditional_merge_after_clean_gate",
        ],
        "forbidden_actions": [
            "unconditional_merge",
            "merge_without_clean_gate",
            "approve_prs",
            "push_code",
            "edit_source_as_mike",
            "post_github_comments_without_explicit_operator_confirmation",
        ],
    }
    append_jsonl(paths.wake_receipts, receipt)
    wake_path = paths.wake_receipts
    update_living_agent(paths, status="awake", now=now, wake_receipt=wake_path)
    record_action(
        paths,
        "wake",
        "Merge Master Mike wake receipt recorded.",
        outputs={"wake_receipts": str(paths.wake_receipts), "living_agent": str(paths.living_agent)},
    )
    write_json(paths.status, build_status(paths, repo_root=repo_root))
    return receipt


def build_fanout_command(
    *,
    pr_review_root: Path,
    cycle_mode: str,
    max_prs: int,
    limit: int,
    timeout_s: float | None,
    agents: str,
    statuses: str,
    allow_pending: bool,
    human_approved: bool,
) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/runtime/pr_merge_control.py",
        "--state-root",
        str(pr_review_root),
        "fanout",
        "--limit",
        str(limit),
        "--max-prs",
        str(max_prs),
        "--agents",
        agents,
        "--statuses",
        statuses,
    ]
    if cycle_mode == "dry-run":
        cmd.append("--dry-run")
    elif cycle_mode == "packet-only":
        cmd.append("--packet-only")
    elif cycle_mode != "review":
        raise ValueError(f"unknown cycle mode: {cycle_mode}")
    if timeout_s is not None:
        cmd.extend(["--timeout-s", str(timeout_s)])
    if allow_pending:
        cmd.append("--allow-pending")
    if human_approved:
        cmd.append("--human-approved")
    return cmd


def _convergence_advisory(limit: int = 30) -> dict[str, Any]:
    """ADVISORY ONLY: deterministic PR convergence ordering from the sibling
    policy module. Recorded into the cycle receipt for the operator and for
    Mike's ordering — it is NEVER a gate input and changes no merge authority.
    Fully guarded: any failure here degrades to an error note, never breaks the
    cycle. Quorum-repair (reviewer_quorum_repair.py) is intentionally NOT fired
    here — it is a deliberate request-only CLI organ, not cycle automation."""
    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))  # repo-root only — never shadow bare names
        from scripts.runtime import pr_convergence_policy  # noqa: PLC0415

        return pr_convergence_policy._fetch_live(limit)
    except Exception as exc:  # advisory must never break the cycle
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_cycle(
    paths: MikePaths,
    *,
    repo_root: Path = REPO_ROOT,
    pr_review_root: Path = expand(DEFAULT_PR_REVIEW_ROOT),
    cycle_mode: str = "dry-run",
    max_prs: int = 3,
    limit: int = 100,
    timeout_s: float | None = None,
    command_timeout_s: float = 900.0,
    agents: str = "codex,claude",
    statuses: str = "GITHUB_GREEN_NEEDS_PACKET,NEEDS_AGENT_REVIEW",
    allow_pending: bool = False,
    human_approved: bool = False,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    wake = record_wake(paths, repo_root=repo_root, mode=f"cycle:{cycle_mode}")
    run_id = stamp()
    cycle_dir = paths.cycles / run_id
    command = build_fanout_command(
        pr_review_root=pr_review_root,
        cycle_mode=cycle_mode,
        max_prs=max_prs,
        limit=limit,
        timeout_s=timeout_s,
        agents=agents,
        statuses=statuses,
        allow_pending=allow_pending,
        human_approved=human_approved,
    )
    started = utc_now()
    try:
        result = runner(command, repo_root, command_timeout_s)
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(
            code=124,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr="command timeout",
            duration_s=command_timeout_s,
        )
    receipt = {
        "schema_version": "dharma.merge_master_mike.cycle_receipt.v1",
        "run_id": run_id,
        "started_at": started,
        "completed_at": utc_now(),
        "agent_uid": AGENT_UID,
        "cycle_mode": cycle_mode,
        "command": command,
        "command_display": " ".join(shlex.quote(part) for part in command),
        "exit_code": result.code,
        "duration_s": result.duration_s,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
        "wake_receipt_id": wake["receipt_id"],
        "authority": {
            "can_merge": False,
            "can_approve_prs": False,
            "can_push": False,
            "can_edit_source": False,
            "github_comment_posting": "not_performed",
        },
        "advisory": {
            "convergence": _convergence_advisory(limit),
        },
    }
    write_json(cycle_dir / "receipt.json", receipt)
    write_json(paths.latest_cycle, receipt)
    write_text(
        cycle_dir / "summary.md",
        render_cycle_summary(receipt),
    )
    record_action(
        paths,
        "cycle",
        f"Ran Merge Master Mike cycle in {cycle_mode} mode.",
        outputs={"cycle_receipt": str(cycle_dir / "receipt.json"), "exit_code": result.code},
        status="ok" if result.code == 0 else "blocked",
    )
    write_json(paths.status, build_status(paths, repo_root=repo_root))
    return receipt


def render_cycle_summary(receipt: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Merge Master Mike Cycle",
            "",
            f"- Run ID: `{receipt['run_id']}`",
            f"- Mode: `{receipt['cycle_mode']}`",
            f"- Exit code: `{receipt['exit_code']}`",
            f"- Duration: `{receipt['duration_s']}s`",
            f"- Command: `{receipt['command_display']}`",
            "",
            "## Authority",
            "",
            "- Mike did not merge, approve, push, edit source, or post GitHub comments.",
            "",
            "## Stdout Tail",
            "",
            "```text",
            (receipt.get("stdout") or "").strip(),
            "```",
            "",
            "## Stderr Tail",
            "",
            "```text",
            (receipt.get("stderr") or "").strip(),
            "```",
            "",
        ]
    )


def latest_fanout(pr_review_root: Path) -> dict[str, Any] | None:
    fanout_root = pr_review_root / "mike_fanout"
    if not fanout_root.exists():
        return None
    candidates = sorted(path for path in fanout_root.glob("*/receipt.json") if path.is_file())
    if not candidates:
        return None
    payload = read_json(candidates[-1], {})
    return {
        "path": str(candidates[-1]),
        "summary_path": str(candidates[-1].with_name("summary.md")),
        "payload": payload,
    }


def build_status(paths: MikePaths, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    pr_review_root = expand(os.environ.get("DHARMA_PR_REVIEW_ROOT", str(DEFAULT_PR_REVIEW_ROOT)))
    queue = read_json(pr_review_root / "queue" / "latest.json", {})
    return {
        "schema_version": "dharma.merge_master_mike.status.v1",
        "generated_at": utc_now(),
        "agent_uid": AGENT_UID,
        "callsign": CALLSIGN,
        "display_name": DISPLAY_NAME,
        "repo_root": str(repo_root),
        "authority": AUTHORITY,
        "nest": str(paths.nest),
        "living_agent": read_json(paths.living_agent, {}),
        "wake_receipts_count": count_lines(paths.wake_receipts),
        "action_log_count": count_lines(paths.action_log),
        "latest_wake": last_jsonl(paths.wake_receipts),
        "latest_action": last_jsonl(paths.action_log),
        "latest_cycle": read_json(paths.latest_cycle, None),
        "latest_fanout": latest_fanout(pr_review_root),
        "queue_counts": queue.get("counts") if isinstance(queue, dict) else None,
        "queue_total": queue.get("total") if isinstance(queue, dict) else None,
        "nats": nats_probe_from_receipt(paths),
        "forbidden": [
            "merge without explicit confirmation",
            "merge without clean deterministic gate",
            "approve PRs",
            "push source",
            "post GitHub comments without explicit authorization",
            "treat self-review as sufficient",
        ],
    }


def render_status_markdown(status: dict[str, Any]) -> str:
    latest_cycle = status.get("latest_cycle") or {}
    latest_action = status.get("latest_action") or {}
    return "\n".join(
        [
            "# Merge Master Mike Status",
            "",
            f"- Generated: `{status['generated_at']}`",
            f"- Agent: `{status['display_name']}` / `{status['agent_uid']}`",
            f"- Authority: `{status['authority']}`",
            f"- Wake receipts: `{status['wake_receipts_count']}`",
            f"- Action log rows: `{status['action_log_count']}`",
            f"- NATS: `{status['nats'].get('code')}` ack={status['nats'].get('ack_verified')}",
            f"- Queue total: `{status.get('queue_total')}`",
            f"- Queue counts: `{status.get('queue_counts')}`",
            f"- Latest cycle: `{latest_cycle.get('run_id')}` mode=`{latest_cycle.get('cycle_mode')}` exit=`{latest_cycle.get('exit_code')}`",
            f"- Latest action: `{latest_action.get('action')}` status=`{latest_action.get('status')}`",
            "",
            "Mike may conditionally merge only after a clean deterministic gate. Mike may not approve, push, edit source, post GitHub comments without explicit authorization, or bypass governance.",
            "",
        ]
    )


def loop_cycles(args: argparse.Namespace, paths: MikePaths) -> int:
    bootstrap_nest(paths, repo_root=expand(args.repo_root))
    cycles = 0
    while True:
        receipt = run_cycle(
            paths,
            repo_root=expand(args.repo_root),
            pr_review_root=expand(args.pr_review_root),
            cycle_mode=args.cycle_mode,
            max_prs=args.max_prs,
            limit=args.limit,
            timeout_s=args.timeout_s,
            command_timeout_s=args.command_timeout_s,
            agents=args.agents,
            statuses=args.statuses,
            allow_pending=args.allow_pending,
            human_approved=args.human_approved,
        )
        cycles += 1
        if args.max_cycles and cycles >= args.max_cycles:
            return 0 if receipt["exit_code"] == 0 else int(receipt["exit_code"])
        time.sleep(args.interval_s)


def launchd_plist(*, repo_root: Path, dharma_home: Path, interval_s: float, cycle_mode: str, max_prs: int) -> str:
    python = sys.executable
    program = repo_root / "scripts" / "runtime" / "merge_master_mike_daemon.py"
    stdout = dharma_home / "logs" / "merge-master-mike.stdout.log"
    stderr = dharma_home / "logs" / "merge-master-mike.stderr.log"
    args = [
        python,
        str(program),
        "--dharma-home",
        str(dharma_home),
        "--repo-root",
        str(repo_root),
        "loop",
        "--cycle-mode",
        cycle_mode,
        "--interval-s",
        str(interval_s),
        "--max-prs",
        str(max_prs),
    ]
    arg_xml = "\n".join(f"    <string>{part}</string>" for part in args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.dharma.merge-master-mike</string>
  <key>ProgramArguments</key>
  <array>
{arg_xml}
  </array>
  <key>WorkingDirectory</key>
  <string>{repo_root}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{stdout}</string>
  <key>StandardErrorPath</key>
  <string>{stderr}</string>
</dict>
</plist>
"""


def tmux_start(args: argparse.Namespace, paths: MikePaths) -> dict[str, Any]:
    tmux = shutil.which("tmux")
    if not tmux:
        return {"ok": False, "error": "tmux not found"}
    repo_root = expand(args.repo_root)
    session = args.session
    loop_cmd = [
        sys.executable,
        str(repo_root / "scripts" / "runtime" / "merge_master_mike_daemon.py"),
        "--dharma-home",
        str(paths.dharma_home),
        "--repo-root",
        str(repo_root),
        "loop",
        "--cycle-mode",
        args.cycle_mode,
        "--interval-s",
        str(args.interval_s),
        "--max-prs",
        str(args.max_prs),
    ]
    if args.max_cycles:
        loop_cmd.extend(["--max-cycles", str(args.max_cycles)])
    command_text = " ".join(shlex.quote(part) for part in loop_cmd)
    has_session = subprocess.run([tmux, "has-session", "-t", session], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if has_session.returncode != 0:
        created = subprocess.run(
            [tmux, "new-session", "-d", "-s", session, "-n", "daemon", "-c", str(repo_root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            return {"ok": False, "error": created.stdout.strip() or "tmux new-session failed", "command": command_text}

    windows = subprocess.run(
        [tmux, "list-windows", "-t", session, "-F", "#{window_name}\t#{window_id}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if windows.returncode != 0:
        return {"ok": False, "error": windows.stdout.strip() or "tmux list-windows failed", "command": command_text}

    target = ""
    for line in windows.stdout.splitlines():
        name, _, window_id = line.partition("\t")
        if name == "daemon" and window_id:
            target = window_id
            break
    if not target:
        created_window = subprocess.run(
            [tmux, "new-window", "-t", session, "-n", "daemon", "-c", str(repo_root), "-P", "-F", "#{window_id}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if created_window.returncode != 0:
            return {"ok": False, "error": created_window.stdout.strip() or "tmux new-window failed", "command": command_text}
        target = created_window.stdout.strip()

    subprocess.run([tmux, "send-keys", "-t", target, "C-c"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    sent = subprocess.run(
        [tmux, "send-keys", "-t", target, command_text, "C-m"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if sent.returncode != 0:
        return {"ok": False, "error": sent.stdout.strip() or "tmux send-keys failed", "target": target, "command": command_text}
    return {"ok": True, "session": session, "target": target, "command": command_text}


def tmux_stop(session: str) -> dict[str, Any]:
    tmux = shutil.which("tmux")
    if not tmux:
        return {"ok": False, "error": "tmux not found"}
    windows = subprocess.run(
        [tmux, "list-windows", "-t", session, "-F", "#{window_name}\t#{window_id}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if windows.returncode != 0:
        return {"ok": False, "error": windows.stdout.strip() or "tmux session not found", "session": session}
    target = ""
    for line in windows.stdout.splitlines():
        name, _, window_id = line.partition("\t")
        if name == "daemon" and window_id:
            target = window_id
            break
    if not target:
        return {"ok": False, "error": "daemon window not found", "session": session}
    stopped = subprocess.run(
        [tmux, "send-keys", "-t", target, "C-c"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return {
        "ok": stopped.returncode == 0,
        "session": session,
        "target": target,
        "error": "" if stopped.returncode == 0 else stopped.stdout.strip(),
    }


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    parser.add_argument("--repo-root", default=str(REPO_ROOT))


def add_cycle_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pr-review-root", default=str(DEFAULT_PR_REVIEW_ROOT))
    parser.add_argument("--cycle-mode", choices=("dry-run", "packet-only", "review"), default="dry-run")
    parser.add_argument("--max-prs", type=int, default=3)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout-s", type=float, default=None)
    parser.add_argument("--command-timeout-s", type=float, default=900.0)
    parser.add_argument("--agents", default="codex,claude")
    parser.add_argument("--statuses", default="GITHUB_GREEN_NEEDS_PACKET,NEEDS_AGENT_REVIEW")
    parser.add_argument("--allow-pending", action="store_true")
    parser.add_argument("--human-approved", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Create/update Mike's local nest")
    bootstrap.set_defaults(func=cmd_bootstrap)

    wake = sub.add_parser("wake", help="Record a fresh Mike wake receipt")
    wake.add_argument("--mode", default="manual")
    wake.set_defaults(func=cmd_wake)

    status = sub.add_parser("status", help="Render Mike status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    cycle = sub.add_parser("cycle", help="Run one PR-control cycle")
    add_cycle_flags(cycle)
    cycle.set_defaults(func=cmd_cycle)

    loop = sub.add_parser("loop", help="Run repeated PR-control cycles")
    add_cycle_flags(loop)
    loop.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    loop.add_argument("--max-cycles", type=int, default=0, help="0 means run until stopped")
    loop.set_defaults(func=cmd_loop)

    plist = sub.add_parser("launchd-plist", help="Render a LaunchAgent plist for Mike")
    plist.add_argument("--output", default="")
    plist.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    plist.add_argument("--cycle-mode", choices=("dry-run", "packet-only", "review"), default="dry-run")
    plist.add_argument("--max-prs", type=int, default=3)
    plist.set_defaults(func=cmd_launchd_plist)

    tmux = sub.add_parser("tmux-start", help="Start Mike's dry-run daemon lane in tmux")
    tmux.add_argument("--session", default=DEFAULT_SESSION)
    tmux.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    tmux.add_argument("--cycle-mode", choices=("dry-run", "packet-only", "review"), default="dry-run")
    tmux.add_argument("--max-prs", type=int, default=3)
    tmux.add_argument("--max-cycles", type=int, default=0)
    tmux.set_defaults(func=cmd_tmux_start)

    tmux_stop_parser = sub.add_parser("tmux-stop", help="Stop Mike's tmux daemon lane with Ctrl-C")
    tmux_stop_parser.add_argument("--session", default=DEFAULT_SESSION)
    tmux_stop_parser.set_defaults(func=cmd_tmux_stop)
    return parser


def cmd_bootstrap(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    payload = bootstrap_nest(paths, repo_root=expand(args.repo_root))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_wake(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    receipt = record_wake(paths, repo_root=expand(args.repo_root), mode=args.mode)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    status = build_status(paths, repo_root=expand(args.repo_root))
    write_json(paths.status, status)
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(render_status_markdown(status))
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    receipt = run_cycle(
        paths,
        repo_root=expand(args.repo_root),
        pr_review_root=expand(args.pr_review_root),
        cycle_mode=args.cycle_mode,
        max_prs=args.max_prs,
        limit=args.limit,
        timeout_s=args.timeout_s,
        command_timeout_s=args.command_timeout_s,
        agents=args.agents,
        statuses=args.statuses,
        allow_pending=args.allow_pending,
        human_approved=args.human_approved,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return int(receipt["exit_code"])


def cmd_loop(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    return loop_cycles(args, paths)


def cmd_launchd_plist(args: argparse.Namespace) -> int:
    repo_root = expand(args.repo_root)
    dharma_home = expand(args.dharma_home)
    text = launchd_plist(
        repo_root=repo_root,
        dharma_home=dharma_home,
        interval_s=args.interval_s,
        cycle_mode=args.cycle_mode,
        max_prs=args.max_prs,
    )
    if args.output:
        write_text(expand(args.output), text)
        print(args.output)
    else:
        print(text)
    return 0


def cmd_tmux_start(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    bootstrap_nest(paths, repo_root=expand(args.repo_root))
    result = tmux_start(args, paths)
    record_action(paths, "tmux_start", "Started Merge Master Mike tmux lane.", outputs=result, status="ok" if result.get("ok") else "blocked")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


def cmd_tmux_stop(args: argparse.Namespace) -> int:
    paths = mike_paths(args.dharma_home)
    result = tmux_stop(args.session)
    record_action(paths, "tmux_stop", "Stopped Merge Master Mike tmux lane.", outputs=result, status="ok" if result.get("ok") else "blocked")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
