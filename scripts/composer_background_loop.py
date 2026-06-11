#!/usr/bin/env python3
"""Persistent wake loop for the opus/codex composer bus.

This supervisor is deliberately lower-authority than a build runner: it watches
the existing A2A convergence directory, wakes composers when a response is owed,
and records receipts. It does not grant repo mutation by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


HOME = Path.home()
DEFAULT_BUS_ROOT = HOME / ".dharma" / "a2a_bus"
DEFAULT_REPO_ROOT = HOME / "dharma_swarm"

AGENT_NAMES = {
    "codex": "codex_composer",
    "opus": "opus_composer",
}

OWN_PATTERNS = {
    "codex": [
        "codex_composer_view*.md",
        "codex_disagreement_ledger*.md",
        "codex_*reply*.md",
        "codex_*verdict*.md",
        "codex_*cosign*.md",
        "codex_background_reply_*.md",
        "bridge_build_receipt*.md",
        "island_design_v2_codex.md",
        "SHARED_PICTURE.md",
    ],
    "opus": [
        "opus_composer_view*.md",
        "opus_round*.md",
        "opus_*reply*.md",
        "opus_*verdict*.md",
        "opus_*cosign*.md",
        "opus_background_reply_*.md",
        "SEAT_UNIFICATION.md",
        "LONGRUN_CONFIDENCE.md",
        "island_plan_cosign_opus.md",
        "SHARED_PICTURE.md",
    ],
}

OTHER_PATTERNS = {
    "codex": [
        "opus_composer_view*.md",
        "opus_round*.md",
        "opus_*reply*.md",
        "opus_*verdict*.md",
        "opus_*cosign*.md",
        "opus_background_reply_*.md",
        "SEAT_UNIFICATION.md",
        "LONGRUN_CONFIDENCE.md",
        "island_plan_cosign_opus.md",
    ],
    "opus": [
        "codex_composer_view*.md",
        "codex_disagreement_ledger*.md",
        "codex_*reply*.md",
        "codex_*verdict*.md",
        "codex_*cosign*.md",
        "codex_background_reply_*.md",
        "bridge_build_receipt*.md",
        "island_design_v2_codex.md",
    ],
}

COMMON_TRIGGER_PATTERNS = [
    "MANDATE.md",
    "OPERATOR_STEER.md",
    "OPERATOR_STEER_*.md",
    "DAILY_HIGHEST_LEVERAGE_MISSION_*.md",
    "OPERATOR_LEASE_*.md",
    "bridge_gate_verdict_*.md",
]

RUNNING_PATTERNS = {
    "codex": "codex exec.*codex_composer",
    "opus": "(^|/)claude( |$).*opus_composer",
}

CONTEXT_PATTERNS = [
    "MANDATE.md",
    "MISSIONS.md",
    "OPERATOR_STEER.md",
    "OPERATOR_STEER_*.md",
    "DAILY_HIGHEST_LEVERAGE_MISSION_*.md",
    "OPERATOR_LEASE_*.md",
    "bridge_gate_verdict_*.md",
    "*composer_view*.md",
    "*reply*.md",
    "*verdict*.md",
    "*cosign*.md",
    "*ledger*.md",
    "bridge_build_receipt*.md",
    "SEAT_UNIFICATION.md",
    "LONGRUN_CONFIDENCE.md",
    "SHARED_PICTURE.md",
]


@dataclass(frozen=True)
class BusPaths:
    root: Path
    convergence: Path
    operator: Path
    state: Path
    run_root: Path
    receipts: Path
    heartbeat: Path
    latest_run: Path


@dataclass(frozen=True)
class AgentDecision:
    agent: str
    pending: bool
    reason: str
    trigger_key: str
    newest_trigger: Path | None
    newest_trigger_mtime: float
    newest_own: Path | None
    newest_own_mtime: float
    attempts: int


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def short_path(path: Path | None, root: Path) -> str:
    if path is None:
        return "none"
    return as_rel(path, root)


def ensure_paths(bus_root: Path) -> BusPaths:
    operator = bus_root / "operator"
    state = operator / "composer_background_loop"
    paths = BusPaths(
        root=bus_root,
        convergence=bus_root / "collab" / "convergence",
        operator=operator,
        state=state,
        run_root=state / "runs",
        receipts=state / "receipts.jsonl",
        heartbeat=state / "heartbeat.json",
        latest_run=state / "latest_run_dir.txt",
    )
    for item in [
        paths.convergence,
        paths.operator,
        paths.state,
        paths.run_root,
        bus_root / "inboxes" / "codex_composer",
        bus_root / "inboxes" / "opus_composer",
    ]:
        item.mkdir(parents=True, exist_ok=True)
    return paths


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def markdown_files_for_patterns(directory: Path, patterns: Sequence[str]) -> list[Path]:
    found: dict[Path, None] = {}
    for pattern in patterns:
        for path in directory.glob(pattern):
            if path.is_file() and path.suffix == ".md":
                found[path] = None
    return sorted(found, key=lambda item: str(item))


def newest_file(paths: Sequence[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda item: item.stat().st_mtime)


def file_fingerprint(paths: Sequence[Path], *, extra: Sequence[str] = ()) -> str:
    rows: list[str] = []
    for path in sorted(paths, key=lambda item: str(item)):
        try:
            stat = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except FileNotFoundError:
            continue
        rows.append(f"{path}:{stat.st_size}:{digest}")
    rows.extend(extra)
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()[:20]


def process_count(pattern: str) -> int:
    try:
        proc = subprocess.run(
            ["pgrep", "-f", pattern],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return 0
    if proc.returncode != 0:
        return 0
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def agent_running(agent: str) -> bool:
    return process_count(RUNNING_PATTERNS[agent]) > 0


def state_file(paths: BusPaths, agent: str) -> Path:
    return paths.state / f"{agent}_state.json"


def decide_agent(
    *,
    paths: BusPaths,
    agent: str,
    max_retries: int,
    dry_run: bool,
) -> AgentDecision:
    trigger_files = markdown_files_for_patterns(
        paths.convergence,
        [*COMMON_TRIGGER_PATTERNS, *OTHER_PATTERNS[agent]],
    )
    own_files = markdown_files_for_patterns(paths.convergence, OWN_PATTERNS[agent])
    shared_picture = paths.convergence / "SHARED_PICTURE.md"
    shared_missing = not shared_picture.exists()
    extra = ["SHARED_PICTURE.md:missing"] if shared_missing else []
    trigger_key = file_fingerprint(trigger_files, extra=extra)
    newest_trigger = newest_file(trigger_files)
    newest_own = newest_file(own_files)
    newest_trigger_mtime = newest_trigger.stat().st_mtime if newest_trigger else 0.0
    newest_own_mtime = newest_own.stat().st_mtime if newest_own else 0.0

    saved = read_json(state_file(paths, agent))
    attempts = int(saved.get("attempts", 0)) if saved.get("trigger_key") == trigger_key else 0
    if not newest_trigger and not shared_missing:
        return AgentDecision(
            agent=agent,
            pending=False,
            reason="no trigger files",
            trigger_key=trigger_key,
            newest_trigger=newest_trigger,
            newest_trigger_mtime=newest_trigger_mtime,
            newest_own=newest_own,
            newest_own_mtime=newest_own_mtime,
            attempts=attempts,
        )
    saved_success = saved.get("trigger_key") == trigger_key and saved.get("success") is True
    saved_was_dry_run = saved.get("dry_run") is True
    if saved_success and (dry_run or not saved_was_dry_run):
        return AgentDecision(
            agent=agent,
            pending=False,
            reason="trigger already handled",
            trigger_key=trigger_key,
            newest_trigger=newest_trigger,
            newest_trigger_mtime=newest_trigger_mtime,
            newest_own=newest_own,
            newest_own_mtime=newest_own_mtime,
            attempts=attempts,
        )
    if attempts >= max_retries:
        return AgentDecision(
            agent=agent,
            pending=False,
            reason=f"retry ceiling reached ({attempts}/{max_retries})",
            trigger_key=trigger_key,
            newest_trigger=newest_trigger,
            newest_trigger_mtime=newest_trigger_mtime,
            newest_own=newest_own,
            newest_own_mtime=newest_own_mtime,
            attempts=attempts,
        )
    reason = "shared picture missing" if shared_missing else "unhandled trigger fingerprint"
    return AgentDecision(
        agent=agent,
        pending=True,
        reason=reason,
        trigger_key=trigger_key,
        newest_trigger=newest_trigger,
        newest_trigger_mtime=newest_trigger_mtime,
        newest_own=newest_own,
        newest_own_mtime=newest_own_mtime,
        attempts=attempts,
    )


def read_excerpt(path: Path, *, char_limit: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= char_limit:
        return text
    return "[tail excerpt]\n" + text[-char_limit:]


def context_files(paths: BusPaths, agent: str, *, limit: int) -> list[Path]:
    all_files = markdown_files_for_patterns(paths.convergence, CONTEXT_PATTERNS)
    own = set(markdown_files_for_patterns(paths.convergence, OWN_PATTERNS[agent]))
    other = set(markdown_files_for_patterns(paths.convergence, OTHER_PATTERNS[agent]))
    common = set(markdown_files_for_patterns(paths.convergence, COMMON_TRIGGER_PATTERNS))
    ranked = list(common | own | other | set(all_files))
    ranked.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return ranked[:limit]


def build_prompt(
    *,
    paths: BusPaths,
    repo_root: Path,
    decision: AgentDecision,
    context_limit: int,
    excerpt_chars: int,
) -> str:
    agent_name = AGENT_NAMES[decision.agent]
    counterpart = "opus_composer" if decision.agent == "codex" else "codex_composer"
    files = context_files(paths, decision.agent, limit=context_limit)
    file_rows = [
        f"- {as_rel(path, paths.convergence)} | mtime={datetime.fromtimestamp(path.stat().st_mtime).isoformat()} | bytes={path.stat().st_size}"
        for path in files
    ]
    excerpts: list[str] = []
    for path in files:
        excerpts.extend(
            [
                f"### {as_rel(path, paths.convergence)}",
                "",
                "```md",
                read_excerpt(path, char_limit=excerpt_chars),
                "```",
                "",
            ]
        )

    return f"""You are {agent_name}, one of the two lead composer agents for the Dharma Swarm system.

This is a persistent background wake from the A2A filesystem bus. The operator explicitly wants
the composer pair to keep conversing and steering between direct chat turns.

Wake reason: {decision.reason}
Trigger key: {decision.trigger_key}
Newest trigger: {short_path(decision.newest_trigger, paths.convergence)}
Newest own artifact: {short_path(decision.newest_own, paths.convergence)}
Bus root: {paths.root}
Convergence home: {paths.convergence}
Repo root: {repo_root}
Counterpart: {counterpart}

Authority for this wake:
- Deliberation and routing only.
- Do not edit repo files, commit, push, deploy, contact external humans, or mark approval as granted.
- If an execution lease exists, evaluate it and draft the exact next build packet, but do not execute code in this wake.
- Treat typecheck/test self-reports from any agent as claims until independently verified.
- Preserve the standing doctrine: the two composers select and verify the highest-leverage work; workhorses execute scoped lanes; the composers still do one major daily hands-on build only under an explicit lease.
- Your final answer will be written by the supervisor to the convergence bus and copied to the other composer's inbox.

Required final artifact shape:
# {agent_name} Background Reply - {utc_stamp()}

## Verdict
State whether action is owed now.

## Evidence
Name concrete files, timestamps, or missing receipts you relied on.

## Disagreement / Risk
Name the sharpest disagreement, uncertainty, or failure mode.

## Next Packet
Write the exact next question, decision, co-sign, or build packet the other composer or operator should receive.

## Receipt
Say what you did in this wake and what you did not do.

Newest bus files:
{chr(10).join(file_rows) if file_rows else "- none"}

Bus excerpts:
{chr(10).join(excerpts) if excerpts else "(No context files found.)"}
"""


def codex_command(
    *,
    prompt: str,
    output_file: Path,
    repo_root: Path,
    bus_root: Path,
    model: str,
) -> list[str]:
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
        str(bus_root.parent),
        "--add-dir",
        str(repo_root),
        "-o",
        str(output_file),
    ]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)
    return cmd


def claude_command(
    *,
    prompt: str,
    repo_root: Path,
    bus_root: Path,
    model: str,
    max_budget_usd: str,
) -> list[str]:
    cmd = [
        "claude",
        "-p",
        "--model",
        model or "opus",
        "--add-dir",
        str(bus_root.parent),
        "--add-dir",
        str(repo_root),
        "--permission-mode",
        "dontAsk",
        "--tools",
        "Read,LS,Grep,Glob",
        "--output-format",
        "text",
        "--no-session-persistence",
    ]
    if max_budget_usd:
        cmd.extend(["--max-budget-usd", max_budget_usd])
    cmd.append(prompt)
    return cmd


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> tuple[int, str, bool]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), False
    except FileNotFoundError as exc:
        return 127, str(exc), False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return 124, stdout + stderr, True


def write_agent_artifact(
    *,
    paths: BusPaths,
    agent: str,
    stamp: str,
    trigger_key: str,
    content: str,
    source_output: Path,
    error: bool = False,
) -> Path:
    agent_name = AGENT_NAMES[agent]
    kind = "error" if error else "reply"
    target = paths.convergence / f"{agent}_background_{kind}_{stamp}.md"
    body = f"""# {agent_name} Background {kind.title()} - {stamp}
agent: {agent_name}
trigger_key: {trigger_key}
source_output: {source_output}
created: {iso_now()}

{content.strip()}
"""
    atomic_write(target, body)
    inbox_name = "opus_composer" if agent == "codex" else "codex_composer"
    inbox_target = paths.root / "inboxes" / inbox_name / target.name
    inbox_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, inbox_target)
    return target


def update_state(
    *,
    paths: BusPaths,
    decision: AgentDecision,
    success: bool,
    rc: int,
    artifact: Path | None,
    attempts: int,
    timed_out: bool,
    dry_run: bool,
) -> None:
    write_json(
        state_file(paths, decision.agent),
        {
            "agent": decision.agent,
            "updated_at": iso_now(),
            "trigger_key": decision.trigger_key,
            "success": success,
            "dry_run": dry_run,
            "rc": rc,
            "attempts": attempts,
            "timed_out": timed_out,
            "artifact": str(artifact) if artifact else "",
            "reason": decision.reason,
            "newest_trigger": str(decision.newest_trigger) if decision.newest_trigger else "",
        },
    )


def write_heartbeat(paths: BusPaths, payload: dict[str, Any]) -> None:
    write_json(
        paths.heartbeat,
        {
            "updated_at": iso_now(),
            **payload,
        },
    )


def run_agent(
    *,
    paths: BusPaths,
    repo_root: Path,
    run_dir: Path,
    decision: AgentDecision,
    timeout: int,
    dry_run: bool,
    context_limit: int,
    excerpt_chars: int,
    codex_model: str,
    opus_model: str,
    opus_max_budget_usd: str,
) -> dict[str, Any]:
    stamp = utc_stamp()
    agent_dir = run_dir / decision.agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(
        paths=paths,
        repo_root=repo_root,
        decision=decision,
        context_limit=context_limit,
        excerpt_chars=excerpt_chars,
    )
    prompt_file = agent_dir / f"prompt_{stamp}.md"
    stdout_file = agent_dir / f"stdout_{stamp}.log"
    output_file = agent_dir / f"last_message_{stamp}.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    attempts = decision.attempts + 1
    if dry_run:
        update_state(
            paths=paths,
            decision=decision,
            success=True,
            rc=0,
            artifact=None,
            attempts=attempts,
            timed_out=False,
            dry_run=True,
        )
        payload = {
            "agent": decision.agent,
            "dry_run": True,
            "pending": decision.pending,
            "reason": decision.reason,
            "trigger_key": decision.trigger_key,
            "prompt_file": str(prompt_file),
            "attempts": attempts,
        }
        append_jsonl(paths.receipts, {"timestamp": iso_now(), **payload})
        return payload

    if decision.agent == "codex":
        cmd = codex_command(
            prompt=prompt,
            output_file=output_file,
            repo_root=repo_root,
            bus_root=paths.root,
            model=codex_model,
        )
    else:
        cmd = claude_command(
            prompt=prompt,
            repo_root=repo_root,
            bus_root=paths.root,
            model=opus_model,
            max_budget_usd=opus_max_budget_usd,
        )

    write_heartbeat(
        paths,
        {
            "status": "running_agent",
            "agent": decision.agent,
            "reason": decision.reason,
            "trigger_key": decision.trigger_key,
            "prompt_file": str(prompt_file),
            "run_dir": str(run_dir),
        },
    )
    started = time.time()
    rc, combined_output, timed_out = run_command(cmd, cwd=repo_root, timeout=timeout)
    duration_sec = round(time.time() - started, 2)
    stdout_file.write_text(combined_output, encoding="utf-8", errors="ignore")
    if output_file.exists():
        model_text = output_file.read_text(encoding="utf-8", errors="replace").strip()
    else:
        model_text = combined_output.strip()
        output_file.write_text(model_text + "\n", encoding="utf-8")

    success = rc == 0 and bool(model_text.strip())
    artifact: Path | None = None
    if success:
        artifact = write_agent_artifact(
            paths=paths,
            agent=decision.agent,
            stamp=stamp,
            trigger_key=decision.trigger_key,
            content=model_text,
            source_output=output_file,
        )
    else:
        error_text = "\n".join(
            [
                "## Wake Failed",
                "",
                f"- rc: {rc}",
                f"- timed_out: {timed_out}",
                f"- stdout_file: {stdout_file}",
                f"- output_file: {output_file}",
                "",
                "```",
                combined_output[-4000:],
                "```",
            ]
        )
        artifact = write_agent_artifact(
            paths=paths,
            agent=decision.agent,
            stamp=stamp,
            trigger_key=decision.trigger_key,
            content=error_text,
            source_output=output_file,
            error=True,
        )

    update_state(
        paths=paths,
        decision=decision,
        success=success,
        rc=rc,
        artifact=artifact,
        attempts=attempts,
        timed_out=timed_out,
        dry_run=False,
    )
    payload = {
        "agent": decision.agent,
        "success": success,
        "rc": rc,
        "timed_out": timed_out,
        "duration_sec": duration_sec,
        "reason": decision.reason,
        "trigger_key": decision.trigger_key,
        "attempts": attempts,
        "prompt_file": str(prompt_file),
        "output_file": str(output_file),
        "stdout_file": str(stdout_file),
        "artifact": str(artifact) if artifact else "",
        "newest_trigger": str(decision.newest_trigger) if decision.newest_trigger else "",
    }
    append_jsonl(paths.receipts, {"timestamp": iso_now(), **payload})
    return payload


def parse_agents(raw: str) -> list[str]:
    agents = [item.strip().lower() for item in raw.split(",") if item.strip()]
    invalid = [agent for agent in agents if agent not in AGENT_NAMES]
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown composer agent(s): {', '.join(invalid)}")
    return agents or ["codex", "opus"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the persistent composer A2A wake loop.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--bus-root", default=os.environ.get("DHARMA_A2A_BUS_ROOT", str(DEFAULT_BUS_ROOT)))
    parser.add_argument("--agents", type=parse_agents, default=parse_agents(os.environ.get("DHARMA_COMPOSER_BACKGROUND_AGENTS", "codex,opus")))
    parser.add_argument("--poll-seconds", type=int, default=int(os.environ.get("DHARMA_COMPOSER_BACKGROUND_POLL_SECONDS", "60")))
    parser.add_argument("--cycle-timeout", type=int, default=int(os.environ.get("DHARMA_COMPOSER_BACKGROUND_TIMEOUT", "2700")))
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--max-retries", type=int, default=int(os.environ.get("DHARMA_COMPOSER_BACKGROUND_MAX_RETRIES", "2")))
    parser.add_argument("--context-files", type=int, default=12)
    parser.add_argument("--excerpt-chars", type=int, default=4500)
    parser.add_argument("--codex-model", default=os.environ.get("DHARMA_COMPOSER_CODEX_MODEL", ""))
    parser.add_argument("--opus-model", default=os.environ.get("DHARMA_COMPOSER_OPUS_MODEL", "opus"))
    parser.add_argument("--opus-max-budget-usd", default=os.environ.get("DHARMA_COMPOSER_OPUS_MAX_BUDGET_USD", "0.75"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).expanduser()
    paths = ensure_paths(Path(args.bus_root).expanduser())
    run_dir = paths.run_root / utc_stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    paths.latest_run.write_text(str(run_dir), encoding="utf-8")

    cycle = 0
    while True:
        cycle += 1
        events: list[dict[str, Any]] = []
        for agent in args.agents:
            decision = decide_agent(
                paths=paths,
                agent=agent,
                max_retries=args.max_retries,
                dry_run=args.dry_run,
            )
            event: dict[str, Any] = {
                "agent": agent,
                "pending": decision.pending,
                "reason": decision.reason,
                "trigger_key": decision.trigger_key,
                "newest_trigger": str(decision.newest_trigger) if decision.newest_trigger else "",
                "newest_own": str(decision.newest_own) if decision.newest_own else "",
                "attempts": decision.attempts,
                "running": agent_running(agent),
            }
            if decision.pending and event["running"]:
                event["skipped"] = "agent already running"
            elif decision.pending:
                event.update(
                    run_agent(
                        paths=paths,
                        repo_root=repo_root,
                        run_dir=run_dir,
                        decision=decision,
                        timeout=args.cycle_timeout,
                        dry_run=args.dry_run,
                        context_limit=args.context_files,
                        excerpt_chars=args.excerpt_chars,
                        codex_model=args.codex_model,
                        opus_model=args.opus_model,
                        opus_max_budget_usd=args.opus_max_budget_usd,
                    )
                )
            events.append(event)

        write_heartbeat(
            paths,
            {
                "status": "idle",
                "cycle": cycle,
                "run_dir": str(run_dir),
                "agents": args.agents,
                "dry_run": args.dry_run,
                "events": events,
                "poll_seconds": args.poll_seconds,
            },
        )
        print(
            f"composer_background_loop cycle={cycle} "
            f"pending={sum(1 for event in events if event.get('pending'))} "
            f"run_dir={run_dir}",
            flush=True,
        )
        if args.once:
            return 0
        if args.max_cycles and cycle >= args.max_cycles:
            return 0
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
