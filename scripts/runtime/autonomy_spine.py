#!/usr/bin/env python3
"""Receipt-backed autonomy spine for goal -> leases -> proof loops.

This is a small control surface, not a transport daemon. It creates a durable
mission ledger that can be promoted to tmux/A2A/NATS execution once those
substrates have live proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.runtime_truth import (
    RuntimeTruthState,
    file_ref,
    reconcile_tasks_from_receipts,
)


SCHEMA_MISSION = "dharma.autonomy_mission.v1"
SCHEMA_TASK = "dharma.autonomy_task.v1"
SCHEMA_RECEIPT = "dharma.autonomy_receipt.v1"
SCHEMA_RECONCILED_SUMMARY = "dharma.autonomy_reconciled_task_summary.v1"
DEFAULT_STATE_ROOT = Path("~/.dharma/autonomy_spine")
REPO_ROOT = Path(__file__).resolve().parents[2]
CLOSED_STATUSES = {"completed", "failed", "blocked"}
RUNNER_SCHEMA = "dharma.autonomy_runner.v1"
RECEIPT_NONCLOSING_STATUSES = {"dispatched", "heartbeat", "lease_reopened", "verified", "verifier_failed"}
AGENT_ALIASES = {
    "codex": "codex_composer",
    "opus": "opus_composer",
    "claude": "opus_composer",
    "hermes": "hermes-m5",
    "gemini": "gemini-flash-worker",
    "devin": "devin-roaming",
}


DEFAULT_TASK_SPECS = [
    {
        "role": "planner",
        "agent_uid": "opus_composer",
        "title": "Define acceptance contract, risks, and smallest proof loop",
        "allowed_writes": ["reports/", "docs/"],
        "verifier_command": "python3 scripts/runtime/autonomy_spine.py verify --mission-id {mission_id} --phase ready",
    },
    {
        "role": "builder",
        "agent_uid": "codex_composer",
        "title": "Implement the scoped change under the mission lease",
        "allowed_writes": ["dharma_swarm/", "scripts/", "tests/", "docs/"],
        "verifier_command": "python3 -m pytest tests -q --tb=short",
    },
    {
        "role": "adversary",
        "agent_uid": "hermes-m5",
        "title": "Attack assumptions, false-liveness claims, and missing receipts",
        "allowed_writes": ["reports/audit/", "docs/governance/"],
        "verifier_command": "python3 scripts/runtime/autonomy_spine.py verify --mission-id {mission_id} --phase ready",
    },
    {
        "role": "verifier",
        "agent_uid": "gemini-flash-worker",
        "title": "Run evidence checks and record pass/fail proof",
        "allowed_writes": ["reports/", "tests/"],
        "verifier_command": "python3 scripts/runtime/autonomy_spine.py verify --mission-id {mission_id} --phase complete",
    },
    {
        "role": "reporter",
        "agent_uid": "opus_composer",
        "title": "Write operator brief and next-action handoff",
        "allowed_writes": ["reports/", "docs/ops/"],
        "verifier_command": "python3 scripts/runtime/autonomy_spine.py brief --mission-id {mission_id}",
    },
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def expand(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "mission"


def short_hash(payload: str, length: int = 10) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def mission_id_from_goal(goal: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{slugify(goal)}-{short_hash(goal, 6)}"


def mission_path(state_root: Path, mission_id: str) -> Path:
    return expand(state_root) / mission_id


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL row") from exc
    return rows


def task_path(root: Path) -> Path:
    return root / "tasks.jsonl"


def receipts_path(root: Path) -> Path:
    return root / "receipts.jsonl"


def runner_path(root: Path) -> Path:
    return root / "runner.json"


def reconciled_summary_path(root: Path) -> Path:
    return root / "reconciled_summary.json"


def load_tasks(root: Path) -> list[dict[str, Any]]:
    return read_jsonl(task_path(root))


def write_tasks(root: Path, tasks: list[dict[str, Any]]) -> None:
    path = task_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in tasks),
        encoding="utf-8",
    )
    tmp.replace(path)


def load_mission(state_root: Path, mission_id: str) -> tuple[Path, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    root = mission_path(state_root, mission_id)
    mission_file = root / "mission.json"
    if not mission_file.exists():
        raise FileNotFoundError(f"mission not found: {mission_id} ({mission_file})")
    return root, read_json(mission_file), load_tasks(root), read_jsonl(receipts_path(root))


def update_mission_status(mission: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    statuses = {task.get("status", "open") for task in tasks}
    if tasks and statuses <= {"completed"}:
        status = "complete"
    elif tasks and statuses <= CLOSED_STATUSES:
        status = "review"
    elif "claimed" in statuses:
        status = "active"
    else:
        status = "open"
    mission["status"] = status
    mission["updated_at"] = utc_now()
    return status


def make_task(mission_id: str, index: int, spec: dict[str, Any], created_at: str) -> dict[str, Any]:
    role = spec["role"]
    task_id = f"{mission_id}-t{index:02d}-{role}"
    return {
        "schema": SCHEMA_TASK,
        "task_id": task_id,
        "mission_id": mission_id,
        "role": role,
        "agent_uid": spec["agent_uid"],
        "title": spec["title"],
        "status": "open",
        "created_at": created_at,
        "updated_at": created_at,
        "allowed_writes": spec["allowed_writes"],
        "verifier_command": spec["verifier_command"].format(mission_id=mission_id),
        "tmux_session": f"ds-{role}",
        "lease": {
            "claimed_by": None,
            "claimed_at": None,
            "expires_at": None,
        },
        "return_address": f"autonomy://{mission_id}/{task_id}",
        "receipt_required": True,
    }


def make_initial_receipt(mission_id: str, goal: str, created_at: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA_RECEIPT,
        "receipt_id": f"r-{short_hash(mission_id + goal + created_at)}",
        "mission_id": mission_id,
        "task_id": None,
        "agent_uid": "autonomy_spine",
        "status": "initialized",
        "evidence": "mission ledger, task leases, and proof commands created",
        "artifact_path": "mission.json",
        "notes": "This is a control ledger only; NATS/A2A live authority still requires ack proof.",
        "test_command": None,
        "created_at": created_at,
    }


def make_runtime_receipt(
    mission_id: str,
    status: str,
    *,
    task_id: str | None = None,
    agent_uid: str = "autonomy_runner",
    role: str | None = None,
    evidence: str | None = None,
    artifact_path: str | None = None,
    notes: str | None = None,
    test_command: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    seed = "|".join([
        mission_id,
        task_id or "mission",
        agent_uid,
        status,
        evidence or "",
        now,
    ])
    return {
        "schema": SCHEMA_RECEIPT,
        "receipt_id": f"r-{short_hash(seed, 16)}",
        "mission_id": mission_id,
        "task_id": task_id,
        "agent_uid": agent_uid,
        "role": role,
        "status": status,
        "evidence": evidence,
        "artifact_path": artifact_path,
        "notes": notes,
        "test_command": test_command,
        "created_at": now,
    }


def create_mission(args: argparse.Namespace) -> dict[str, Any]:
    state_root = expand(args.state_root)
    mission_id = args.mission_id or mission_id_from_goal(args.goal)
    root = mission_path(state_root, mission_id)
    if root.exists() and not args.force:
        raise FileExistsError(f"mission already exists: {mission_id}; use --force to overwrite")

    created_at = utc_now()
    tasks = [make_task(mission_id, index, spec, created_at) for index, spec in enumerate(DEFAULT_TASK_SPECS, start=1)]
    mission = {
        "schema": SCHEMA_MISSION,
        "mission_id": mission_id,
        "goal": args.goal,
        "owner": args.owner,
        "risk": args.risk,
        "mode": args.mode,
        "status": "open",
        "created_at": created_at,
        "updated_at": created_at,
        "repo_root": str(REPO_ROOT),
        "state_root": str(state_root),
        "nats_authority": "blocked_until_ack_proof",
        "a2a_authority": "filesystem_receipts_only_until_live_contact",
        "tmux_authority": "persistent terminal lanes are allowed execution surfaces",
        "command_plan": {
            "status": f"python3 scripts/runtime/autonomy_spine.py --state-root {state_root} status --mission-id {mission_id}",
            "brief": f"python3 scripts/runtime/autonomy_spine.py --state-root {state_root} brief --mission-id {mission_id}",
            "run": f"python3 scripts/runtime/autonomy_spine.py --state-root {state_root} run --mission-id {mission_id} --duration-hours 6",
            "verify_ready": f"python3 scripts/runtime/autonomy_spine.py --state-root {state_root} verify --mission-id {mission_id} --phase ready",
            "verify_complete": f"python3 scripts/runtime/autonomy_spine.py --state-root {state_root} verify --mission-id {mission_id} --phase complete",
        },
    }
    update_mission_status(mission, tasks)

    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "mission.json", mission)
    write_tasks(root, tasks)
    append_jsonl(receipts_path(root), make_initial_receipt(mission_id, args.goal, created_at))
    write_reconciled_task_summary(root, mission, tasks, read_jsonl(receipts_path(root)))
    write_brief(root, mission, tasks, read_jsonl(receipts_path(root)))
    return mission


def find_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    for task in tasks:
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"task not found: {task_id}")


def claim_task(args: argparse.Namespace) -> dict[str, Any]:
    state_root = expand(args.state_root)
    root, mission, tasks, _receipts = load_mission(state_root, args.mission_id)
    task = find_task(tasks, args.task_id)
    if task["status"] in CLOSED_STATUSES:
        raise RuntimeError(f"task is already closed: {args.task_id} status={task['status']}")
    claimed_by = task["lease"].get("claimed_by")
    if task["status"] == "claimed" and claimed_by != args.agent:
        raise RuntimeError(f"task already claimed by {claimed_by}: {args.task_id}")

    now = utc_now()
    expires_at = (
        datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=args.lease_minutes)
    ).isoformat().replace("+00:00", "Z")
    task["status"] = "claimed"
    task["updated_at"] = now
    task["lease"] = {
        "claimed_by": args.agent,
        "claimed_at": now,
        "expires_at": expires_at,
    }
    update_mission_status(mission, tasks)
    write_json(root / "mission.json", mission)
    write_tasks(root, tasks)
    return task


def make_receipt(args: argparse.Namespace, task: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    seed = "|".join([
        args.mission_id,
        args.task_id,
        args.status,
        args.agent,
        args.evidence or "",
        now,
    ])
    return {
        "schema": SCHEMA_RECEIPT,
        "receipt_id": f"r-{short_hash(seed, 16)}",
        "mission_id": args.mission_id,
        "task_id": args.task_id,
        "agent_uid": args.agent,
        "role": task.get("role"),
        "status": args.status,
        "evidence": args.evidence,
        "artifact_path": args.artifact,
        "notes": args.notes,
        "test_command": args.test_command,
        "created_at": now,
    }


def record_receipt(args: argparse.Namespace) -> dict[str, Any]:
    if args.status == "completed" and not args.evidence:
        raise ValueError("--evidence is required when recording a completed task")
    if args.status in {"failed", "blocked"} and not (args.evidence or args.notes):
        raise ValueError("--evidence or --notes is required when recording failed/blocked")

    state_root = expand(args.state_root)
    root, mission, tasks, _receipts = load_mission(state_root, args.mission_id)
    task = find_task(tasks, args.task_id)
    task["status"] = args.status
    task["updated_at"] = utc_now()
    task["closed_by_receipt"] = True
    receipt = make_receipt(args, task)
    task["receipt_id"] = receipt["receipt_id"]
    update_mission_status(mission, tasks)
    write_json(root / "mission.json", mission)
    write_tasks(root, tasks)
    append_jsonl(receipts_path(root), receipt)
    receipts = read_jsonl(receipts_path(root))
    write_reconciled_task_summary(root, mission, tasks, receipts)
    write_brief(root, mission, tasks, receipts)
    return receipt


def record_progress_receipt(args: argparse.Namespace) -> dict[str, Any]:
    """Append a non-closing progress receipt without mutating task status."""

    if not (args.evidence or args.notes):
        raise ValueError("--evidence or --notes is required when recording progress")

    state_root = expand(args.state_root)
    root, mission, tasks, _receipts = load_mission(state_root, args.mission_id)
    role = None
    if args.task_id:
        task = find_task(tasks, args.task_id)
        role = task.get("role")
    receipt = make_runtime_receipt(
        args.mission_id,
        args.status,
        task_id=args.task_id,
        agent_uid=args.agent,
        role=role,
        evidence=args.evidence,
        artifact_path=args.artifact,
        notes=args.notes,
        test_command=args.test_command,
    )
    append_jsonl(receipts_path(root), receipt)
    receipts = read_jsonl(receipts_path(root))
    write_reconciled_task_summary(root, mission, tasks, receipts)
    write_brief(root, mission, tasks, receipts)
    return receipt


def task_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"open": 0, "claimed": 0, "completed": 0, "failed": 0, "blocked": 0}
    for task in tasks:
        status = task.get("status", "open")
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = len(tasks)
    return counts


def build_reconciled_task_summary(
    root: Path,
    mission: dict[str, Any],
    tasks: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    result = reconcile_tasks_from_receipts(
        tasks,
        receipts,
        closing_statuses=CLOSED_STATUSES,
        nonclosing_statuses=RECEIPT_NONCLOSING_STATUSES,
    )
    summary = result["summary"]
    summary["schema_version"] = SCHEMA_RECONCILED_SUMMARY
    summary["mission_id"] = mission["mission_id"]
    summary["mission_status"] = mission.get("status", "")
    summary["summary_path"] = str(reconciled_summary_path(root))
    summary["source_refs"] = [
        file_ref(root / "mission.json", kind="mission"),
        file_ref(task_path(root), kind="tasks_jsonl"),
        file_ref(receipts_path(root), kind="receipts_jsonl"),
    ]
    if runner_path(root).exists():
        summary["source_refs"].append(file_ref(runner_path(root), kind="runner_state"))
    summary["artifact_progress_status"] = list(summary.get("progress_states") or [])
    if stale_claims(tasks):
        summary["artifact_progress_status"].append(RuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS.value)
    return summary


def write_reconciled_task_summary(
    root: Path,
    mission: dict[str, Any],
    tasks: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = build_reconciled_task_summary(root, mission, tasks, receipts)
    write_json(reconciled_summary_path(root), summary)
    return summary


def stale_claims(tasks: list[dict[str, Any]], now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    stale: list[str] = []
    for task in tasks:
        if task.get("status") != "claimed":
            continue
        expires_at = task.get("lease", {}).get("expires_at")
        if expires_at and parse_utc(expires_at) < now:
            stale.append(task["task_id"])
    return stale


def normalize_agent(value: str) -> str:
    token = value.strip()
    return AGENT_ALIASES.get(token, token)


def parse_agents(value: str | None) -> set[str] | None:
    if not value:
        return None
    agents = {normalize_agent(part) for part in value.split(",") if part.strip()}
    return agents or None


def parse_agent_commands(values: list[str]) -> dict[str, str]:
    commands: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--agent-command must use agent=command")
        agent, command = value.split("=", 1)
        commands[normalize_agent(agent)] = command.strip()
    return commands


def task_is_dispatchable(task: dict[str, Any], allowed_agents: set[str] | None) -> bool:
    if task.get("status") != "open":
        return False
    return allowed_agents is None or task.get("agent_uid") in allowed_agents


def make_task_prompt(root: Path, mission: dict[str, Any], task: dict[str, Any], cycle: int) -> Path:
    prompt_dir = root / "artifacts" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{task['task_id']}.prompt.md"
    allowed = "\n".join(f"- {item}" for item in task.get("allowed_writes", []))
    content = f"""# Dharma Swarm Autonomy Lease

Mission: {mission['mission_id']}
Goal: {mission['goal']}
Cycle: {cycle}

Task: {task['task_id']}
Role: {task['role']}
Agent: {task['agent_uid']}
Title: {task['title']}

Allowed writes:
{allowed or "- none"}

Verifier:
`{task.get('verifier_command') or 'none'}`

Return address:
`{task['return_address']}`

Rules:
- Work only inside the allowed scope.
- Do not claim NATS or A2A live collaboration without live ack evidence.
- Write a receipt using `ds-goal record` before claiming task completion.
- If blocked, record a blocked receipt with the concrete blocker.
"""
    prompt_path.write_text(content, encoding="utf-8")
    return prompt_path


def tmux_has_session(session: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def ensure_tmux_session(session: str, root: Path) -> None:
    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is not installed")
    if not tmux_has_session(session):
        subprocess.run(["tmux", "new-session", "-d", "-s", session, "-c", str(REPO_ROOT)], check=True)
    subprocess.run(
        [
            "tmux",
            "set-option",
            "-t",
            session,
            "@dharma_autonomy_root",
            str(root),
        ],
        check=False,
    )


def dispatch_to_tmux(root: Path, task: dict[str, Any], prompt_path: Path, agent_commands: dict[str, str], dry_run: bool) -> str:
    session = task.get("tmux_session") or f"ds-{task['role']}"
    command_template = agent_commands.get(task["agent_uid"])
    prompt_q = shlex.quote(str(prompt_path))
    if command_template:
        command = command_template.format(
            prompt_path=prompt_q,
            task_id=shlex.quote(task["task_id"]),
            mission_id=shlex.quote(task["mission_id"]),
        )
    else:
        command = (
            f"cd {shlex.quote(str(REPO_ROOT))} && "
            f"printf '\\n[autonomy-spine] Lease prompt ready: {prompt_q}\\n' && "
            f"sed -n '1,220p' {prompt_q}"
        )

    if dry_run:
        return f"tmux://{session} dry_run command={command}"

    ensure_tmux_session(session, root)
    subprocess.run(["tmux", "send-keys", "-t", session, command, "C-m"], check=True)
    return f"tmux://{session}"


def reopen_stale_leases(tasks: list[dict[str, Any]], root: Path, mission_id: str) -> list[dict[str, Any]]:
    reopened: list[dict[str, Any]] = []
    stale_ids = set(stale_claims(tasks))
    for task in tasks:
        if task["task_id"] not in stale_ids:
            continue
        prior_agent = task.get("lease", {}).get("claimed_by")
        task["status"] = "open"
        task["updated_at"] = utc_now()
        task["lease"] = {"claimed_by": None, "claimed_at": None, "expires_at": None}
        reopened.append(
            make_runtime_receipt(
                mission_id,
                "lease_reopened",
                task_id=task["task_id"],
                role=task.get("role"),
                evidence=f"stale lease reopened; prior_agent={prior_agent}",
            )
        )
    for receipt in reopened:
        append_jsonl(receipts_path(root), receipt)
    return reopened


def claim_task_in_memory(task: dict[str, Any], lease_minutes: int) -> None:
    now = utc_now()
    expires_at = (
        datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=lease_minutes)
    ).isoformat().replace("+00:00", "Z")
    task["status"] = "claimed"
    task["updated_at"] = now
    task["lease"] = {
        "claimed_by": task["agent_uid"],
        "claimed_at": now,
        "expires_at": expires_at,
    }


def run_spine_verifier(root: Path, mission: dict[str, Any], tasks: list[dict[str, Any]], receipts: list[dict[str, Any]], phase: str) -> dict[str, Any]:
    payload = verify_payload(mission, tasks, receipts, phase)
    logs_dir = root / "artifacts" / "verifier"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{phase}.json"
    log_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = "verified" if not payload["blockers"] else "verifier_failed"
    append_jsonl(
        receipts_path(root),
        make_runtime_receipt(
            mission["mission_id"],
            status,
            evidence=f"{phase} blockers={len(payload['blockers'])}",
            artifact_path=str(log_path),
            test_command=f"autonomy_spine verify --phase {phase}",
        ),
    )
    return payload


def write_runner_state(root: Path, payload: dict[str, Any]) -> None:
    write_json(runner_path(root), payload)


def run_mission(args: argparse.Namespace) -> dict[str, Any]:
    state_root = expand(args.state_root)
    root, mission, tasks, receipts = load_mission(state_root, args.mission_id)
    allowed_agents = parse_agents(args.agents)
    agent_commands = parse_agent_commands(args.agent_command)
    if args.duration_hours is not None:
        duration_minutes = int(args.duration_hours * 60)
    else:
        duration_minutes = args.duration_minutes
    if duration_minutes < 0:
        raise ValueError("--duration-minutes/--duration-hours must be non-negative")
    deadline = datetime.now(UTC) + timedelta(minutes=duration_minutes)
    verify_every = timedelta(minutes=args.verify_every_minutes)
    next_verify = datetime.now(UTC)
    cycle = 0
    dispatches = 0
    verifier_runs = 0
    last_verify: dict[str, Any] | None = None

    while True:
        now = datetime.now(UTC)
        if args.max_cycles is not None and cycle >= args.max_cycles:
            break
        if cycle > 0 and now >= deadline:
            break

        cycle += 1
        reopened = reopen_stale_leases(tasks, root, mission["mission_id"])
        if reopened:
            receipts = read_jsonl(receipts_path(root))

        cycle_dispatches = 0
        for task in tasks:
            if args.max_dispatch and cycle_dispatches >= args.max_dispatch:
                break
            if not task_is_dispatchable(task, allowed_agents):
                continue
            prompt_path = make_task_prompt(root, mission, task, cycle)
            destination = "ledger"
            notes = "dispatch_mode=ledger; no external process started"
            if args.dispatch_mode == "tmux":
                destination = dispatch_to_tmux(root, task, prompt_path, agent_commands, args.dry_run)
                notes = "dispatch_mode=tmux"
                if args.dry_run:
                    notes += "; dry_run=true"
                if task["agent_uid"] not in agent_commands:
                    notes += "; no agent command configured, prompt displayed only"
            elif args.dispatch_mode == "print":
                destination = str(prompt_path)
                notes = "dispatch_mode=print"

            claim_task_in_memory(task, args.lease_minutes)
            dispatches += 1
            cycle_dispatches += 1
            append_jsonl(
                receipts_path(root),
                make_runtime_receipt(
                    mission["mission_id"],
                    "dispatched",
                    task_id=task["task_id"],
                    agent_uid="autonomy_runner",
                    role=task.get("role"),
                    evidence=f"leased to {task['agent_uid']} via {destination}",
                    artifact_path=str(prompt_path),
                    notes=notes,
                ),
            )

        update_mission_status(mission, tasks)
        mission["runner"] = {
            "schema": RUNNER_SCHEMA,
            "last_started_at": utc_now(),
            "dispatch_mode": args.dispatch_mode,
            "duration_minutes": duration_minutes,
            "verify_every_minutes": args.verify_every_minutes,
            "agents": sorted(allowed_agents) if allowed_agents else "all",
        }
        write_json(root / "mission.json", mission)
        write_tasks(root, tasks)
        receipts = read_jsonl(receipts_path(root))

        if now >= next_verify or args.once:
            phase = "complete" if mission.get("status") in {"complete", "review"} else "ready"
            last_verify = run_spine_verifier(root, mission, tasks, receipts, phase)
            verifier_runs += 1
            receipts = read_jsonl(receipts_path(root))
            next_verify = datetime.now(UTC) + verify_every

        state = {
            "schema": RUNNER_SCHEMA,
            "mission_id": mission["mission_id"],
            "status": mission["status"],
            "cycle": cycle,
            "dispatch_mode": args.dispatch_mode,
            "dispatches": dispatches,
            "verifier_runs": verifier_runs,
            "deadline": deadline.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "next_verify": next_verify.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "counts": task_counts(tasks),
            "reconciled_task_summary": build_reconciled_task_summary(root, mission, tasks, receipts),
            "last_verify": last_verify,
            "updated_at": utc_now(),
        }
        write_runner_state(root, state)
        append_jsonl(
            receipts_path(root),
            make_runtime_receipt(
                mission["mission_id"],
                "heartbeat",
                evidence=f"cycle={cycle} dispatches={dispatches} verifier_runs={verifier_runs}",
                artifact_path=str(runner_path(root)),
            ),
        )
        receipts = read_jsonl(receipts_path(root))
        write_reconciled_task_summary(root, mission, tasks, receipts)
        write_brief(root, mission, tasks, receipts)

        if args.once:
            break
        if all(task.get("status") in CLOSED_STATUSES for task in tasks):
            break
        if datetime.now(UTC) >= deadline:
            break
        time.sleep(args.sleep_seconds)

    final_state = read_json(runner_path(root))
    return final_state


def verify_payload(mission: dict[str, Any], tasks: list[dict[str, Any]], receipts: list[dict[str, Any]], phase: str) -> dict[str, Any]:
    blockers: list[str] = []
    reconciliation = reconcile_tasks_from_receipts(
        tasks,
        receipts,
        closing_statuses=CLOSED_STATUSES,
        nonclosing_statuses=RECEIPT_NONCLOSING_STATUSES,
    )
    effective_tasks = reconciliation["tasks"]
    counts = task_counts(effective_tasks)
    raw_counts = task_counts(tasks)
    receipt_by_task = {receipt.get("task_id"): receipt for receipt in receipts if receipt.get("task_id")}

    if mission.get("schema") != SCHEMA_MISSION:
        blockers.append("mission_schema_invalid")
    if not tasks:
        blockers.append("no_tasks")
    for task in effective_tasks:
        if task.get("schema") != SCHEMA_TASK:
            blockers.append(f"task_schema_invalid:{task.get('task_id')}")
        if task.get("receipt_required") is not True:
            blockers.append(f"receipt_not_required:{task.get('task_id')}")
        if not task.get("verifier_command"):
            blockers.append(f"verifier_missing:{task.get('task_id')}")
        if not task.get("return_address", "").startswith("autonomy://"):
            blockers.append(f"return_address_invalid:{task.get('task_id')}")

    for task_id in stale_claims(tasks):
        blockers.append(f"lease_stale:{task_id}")

    if phase == "complete":
        for task in effective_tasks:
            status = task.get("status")
            if status not in CLOSED_STATUSES:
                blockers.append(f"task_not_closed:{task['task_id']}")
                continue
            receipt = receipt_by_task.get(task["task_id"])
            if not receipt:
                blockers.append(f"receipt_missing:{task['task_id']}")
            elif status == "completed" and not receipt.get("evidence"):
                blockers.append(f"completed_evidence_missing:{task['task_id']}")

    return {
        "mission_id": mission["mission_id"],
        "phase": phase,
        "status": mission["status"],
        "counts": counts,
        "raw_counts": raw_counts,
        "reconciled_counts": counts,
        "raw_reconciled_mismatch": raw_counts != counts,
        "ready_valid": not blockers if phase == "ready" else None,
        "complete_valid": not blockers if phase == "complete" else None,
        "blockers": blockers,
    }


def render_brief(mission: dict[str, Any], tasks: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> str:
    counts = task_counts(tasks)
    root = mission_path(Path(mission.get("state_root") or DEFAULT_STATE_ROOT), mission["mission_id"])
    reconciliation = build_reconciled_task_summary(root, mission, tasks, receipts)
    reconciled_counts = reconciliation["reconciled_counts"]
    latest = receipts[-5:]
    lines = [
        f"# Autonomy Spine Brief: {mission['mission_id']}",
        "",
        f"Goal: {mission['goal']}",
        f"Status: {mission['status']}",
        f"Risk: {mission['risk']}",
        f"Mode: {mission['mode']}",
        "",
        "## Task State",
        "",
        f"open={counts.get('open', 0)} claimed={counts.get('claimed', 0)} completed={counts.get('completed', 0)} failed={counts.get('failed', 0)} blocked={counts.get('blocked', 0)} total={counts.get('total', 0)}",
        "",
        "## Reconciled Task State",
        "",
        f"open={reconciled_counts.get('open', 0)} claimed={reconciled_counts.get('claimed', 0)} completed={reconciled_counts.get('completed', 0)} failed={reconciled_counts.get('failed', 0)} blocked={reconciled_counts.get('blocked', 0)} total={reconciled_counts.get('total', 0)}",
        f"projection_only={reconciliation.get('authority_state')} mismatch={reconciliation.get('raw_reconciled_mismatch')}",
        f"summary={reconciliation.get('summary_path')}",
        "",
        "| Task | Role | Agent | Status | Lease |",
        "| --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        lease = task.get("lease", {})
        lease_text = lease.get("claimed_by") or "-"
        lines.append(
            f"| `{task['task_id']}` | {task['role']} | {task['agent_uid']} | {task['status']} | {lease_text} |"
        )
    lines.extend(["", "## Latest Receipts", ""])
    if latest:
        for receipt in latest:
            task_id = receipt.get("task_id") or "mission"
            evidence = receipt.get("evidence") or receipt.get("notes") or ""
            lines.append(f"- `{receipt['status']}` `{task_id}` by `{receipt['agent_uid']}`: {evidence}")
    else:
        lines.append("- No receipts yet.")
    lines.extend([
        "",
        "## Commands",
        "",
        f"- Status: `{mission['command_plan']['status']}`",
        f"- Run: `{mission['command_plan'].get('run', 'python3 scripts/runtime/autonomy_spine.py run --mission-id ' + mission['mission_id'])}`",
        f"- Ready check: `{mission['command_plan']['verify_ready']}`",
        f"- Complete check: `{mission['command_plan']['verify_complete']}`",
        "",
        "## Authority Boundary",
        "",
        "- NATS remains blocked until ack proof exists.",
        "- A2A filesystem receipts are evidence, not proof of live contact.",
        "- tmux lanes are allowed execution surfaces for long-running agents.",
        "",
    ])
    return "\n".join(lines)


def write_brief(root: Path, mission: dict[str, Any], tasks: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> str:
    brief = render_brief(mission, tasks, receipts)
    (root / "brief.md").write_text(brief, encoding="utf-8")
    return brief


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT), help="Autonomy spine state root")


def add_state_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_global_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create a new goal mission with default task leases")
    add_state_arg(init_p)
    init_p.add_argument("--goal", required=True)
    init_p.add_argument("--mission-id")
    init_p.add_argument("--owner", default="dhyana")
    init_p.add_argument("--risk", default="Q1", choices=["Q0", "Q1", "Q2", "Q3"])
    init_p.add_argument("--mode", default="build", choices=["build", "audit", "research", "repair", "background"])
    init_p.add_argument("--force", action="store_true")

    status_p = sub.add_parser("status", help="Show mission status")
    add_state_arg(status_p)
    status_p.add_argument("--mission-id", required=True)
    status_p.add_argument("--json", action="store_true")

    reconcile_p = sub.add_parser("reconcile", help="Write derived receipt-reconciled task summary")
    add_state_arg(reconcile_p)
    reconcile_p.add_argument("--mission-id", required=True)
    reconcile_p.add_argument("--json", action="store_true")

    claim_p = sub.add_parser("claim", help="Claim a task lease")
    add_state_arg(claim_p)
    claim_p.add_argument("--mission-id", required=True)
    claim_p.add_argument("--task-id", required=True)
    claim_p.add_argument("--agent", required=True)
    claim_p.add_argument("--lease-minutes", type=int, default=180)
    claim_p.add_argument("--json", action="store_true")

    record_p = sub.add_parser("record", help="Close a task with a receipt")
    add_state_arg(record_p)
    record_p.add_argument("--mission-id", required=True)
    record_p.add_argument("--task-id", required=True)
    record_p.add_argument("--agent", required=True)
    record_p.add_argument("--status", required=True, choices=sorted(CLOSED_STATUSES))
    record_p.add_argument("--evidence")
    record_p.add_argument("--artifact")
    record_p.add_argument("--notes")
    record_p.add_argument("--test-command")
    record_p.add_argument("--json", action="store_true")

    progress_p = sub.add_parser("progress", help="Append a non-closing progress receipt")
    add_state_arg(progress_p)
    progress_p.add_argument("--mission-id", required=True)
    progress_p.add_argument("--task-id")
    progress_p.add_argument("--agent", required=True)
    progress_p.add_argument("--status", required=True, choices=sorted(RECEIPT_NONCLOSING_STATUSES))
    progress_p.add_argument("--evidence")
    progress_p.add_argument("--artifact")
    progress_p.add_argument("--notes")
    progress_p.add_argument("--test-command")
    progress_p.add_argument("--json", action="store_true")

    verify_p = sub.add_parser("verify", help="Verify mission ledger integrity")
    add_state_arg(verify_p)
    verify_p.add_argument("--mission-id", required=True)
    verify_p.add_argument("--phase", default="ready", choices=["ready", "complete"])
    verify_p.add_argument("--json", action="store_true")

    brief_p = sub.add_parser("brief", help="Render and refresh operator brief")
    add_state_arg(brief_p)
    brief_p.add_argument("--mission-id", required=True)
    brief_p.add_argument("--json", action="store_true")

    run_p = sub.add_parser("run", help="Run a bounded mission supervisor loop")
    add_state_arg(run_p)
    run_p.add_argument("--mission-id", required=True)
    run_p.add_argument("--duration-hours", type=float)
    run_p.add_argument("--duration-minutes", type=int, default=60)
    run_p.add_argument("--verify-every-minutes", type=int, default=20)
    run_p.add_argument("--lease-minutes", type=int, default=180)
    run_p.add_argument("--sleep-seconds", type=float, default=60)
    run_p.add_argument("--max-cycles", type=int)
    run_p.add_argument("--max-dispatch", type=int, default=0, help="Max dispatches per cycle; 0 means no cap")
    run_p.add_argument("--once", action="store_true", help="Run one cycle and exit")
    run_p.add_argument("--agents", help="Comma-separated allowed agents or aliases: codex,opus,hermes,gemini")
    run_p.add_argument("--dispatch-mode", choices=["ledger", "tmux", "print"], default="ledger")
    run_p.add_argument(
        "--agent-command",
        action="append",
        default=[],
        help="agent=command template. Use {prompt_path}, {task_id}, {mission_id}.",
    )
    run_p.add_argument("--dry-run", action="store_true", help="For tmux mode, write receipts without sending keys")
    run_p.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            mission = create_mission(args)
            root = mission_path(expand(args.state_root), mission["mission_id"])
            print(root)
            return 0

        root, mission, tasks, receipts = load_mission(expand(args.state_root), args.mission_id)

        if args.command == "status":
            reconciliation = build_reconciled_task_summary(root, mission, tasks, receipts)
            payload = {
                "mission_id": mission["mission_id"],
                "goal": mission["goal"],
                "status": mission["status"],
                "counts": task_counts(tasks),
                "raw_counts": task_counts(tasks),
                "reconciled_counts": reconciliation["reconciled_counts"],
                "raw_reconciled_mismatch": reconciliation["raw_reconciled_mismatch"],
                "reconciled_summary": reconciliation,
                "artifact_progress_status": reconciliation["artifact_progress_status"],
                "stale_claims": stale_claims(tasks),
                "brief": str(root / "brief.md"),
                "reconciled_summary_path": str(reconciled_summary_path(root)),
            }
            if args.json:
                print_json(payload)
            else:
                print(f"{payload['mission_id']} status={payload['status']} counts={payload['counts']}")
                print(f"reconciled_counts={payload['reconciled_counts']} mismatch={payload['raw_reconciled_mismatch']}")
                if payload["stale_claims"]:
                    print("stale_claims=" + ",".join(payload["stale_claims"]))
                print(f"brief={payload['brief']}")
                print(f"reconciled_summary={payload['reconciled_summary_path']}")
            return 0

        if args.command == "reconcile":
            summary = write_reconciled_task_summary(root, mission, tasks, receipts)
            if args.json:
                print_json(summary)
            else:
                print(f"reconciled {mission['mission_id']} summary={reconciled_summary_path(root)}")
            return 0

        if args.command == "claim":
            task = claim_task(args)
            if args.json:
                print_json(task)
            else:
                print(f"claimed {task['task_id']} by {args.agent} until {task['lease']['expires_at']}")
            return 0

        if args.command == "record":
            receipt = record_receipt(args)
            if args.json:
                print_json(receipt)
            else:
                print(f"recorded {receipt['status']} receipt {receipt['receipt_id']} for {receipt['task_id']}")
            return 0

        if args.command == "progress":
            receipt = record_progress_receipt(args)
            if args.json:
                print_json(receipt)
            else:
                target = receipt.get("task_id") or "mission"
                print(f"recorded progress {receipt['status']} receipt {receipt['receipt_id']} for {target}")
            return 0

        if args.command == "verify":
            payload = verify_payload(mission, tasks, receipts, args.phase)
            valid = not payload["blockers"]
            if args.json:
                print_json(payload)
            else:
                verdict = "PASS" if valid else "FAIL"
                print(f"{verdict} {args.phase} {mission['mission_id']} blockers={payload['blockers']}")
            return 0 if valid else 3

        if args.command == "brief":
            brief = write_brief(root, mission, tasks, receipts)
            if args.json:
                print_json({"mission_id": mission["mission_id"], "brief": str(root / "brief.md")})
            else:
                print(brief)
            return 0

        if args.command == "run":
            state = run_mission(args)
            if args.json:
                print_json(state)
            else:
                print(
                    f"runner {state['mission_id']} status={state['status']} "
                    f"cycle={state['cycle']} dispatches={state['dispatches']} "
                    f"verifier_runs={state['verifier_runs']}"
                )
                print(f"runner_state={root / 'runner.json'}")
                print(f"brief={root / 'brief.md'}")
            return 0

        parser.error(f"unknown command: {args.command}")
        return 2
    except (FileExistsError, FileNotFoundError, KeyError, RuntimeError, ValueError) as exc:
        print(f"autonomy_spine: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
