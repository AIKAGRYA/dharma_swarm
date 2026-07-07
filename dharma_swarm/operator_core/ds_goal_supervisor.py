"""Real ds-goal supervisor loop with scoped local actuation.

The Autonomy Spine CLI is the mission ledger front door. This module is the
runtime worker layer for that ledger: it leases ds-goal tasks, creates bounded
artifacts inside declared write roots, runs the task verifier, and only marks a
task done when terminal proof exists.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import uuid4

from dharma_swarm.operator_core.runtime_truth import sha256_file, stable_payload_hash, utc_now

DS_GOAL_SUPERVISOR_SCHEMA = "dharma.ds_goal_supervisor.v1"
DS_GOAL_TASK_SCHEMA = "dharma.autonomy_task.v1"
MISSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
TERMINAL_TASK_STATUSES = {"done", "completed", "closed", "cancelled", "canceled"}
OPEN_TASK_STATUSES = {"", "claimable", "claimed", "running", "review"}


def compile_mission_tasks(
    *,
    mission: dict[str, Any],
    mission_dir: Path,
    role: str,
    agent_uid: str,
    allowed_writes: list[str],
    verifier_command: str,
) -> list[dict[str, Any]]:
    """Compile the initial mission task graph.

    This emits a builder task plus a dependent verifier task. The important
    change from the old bridge is that neither task is a session-status-only
    projection: the graph declares artifact generation, verifier execution, and
    terminal proof requirements.
    """
    mission_id = str(mission.get("mission_id") or mission_dir.name)
    task_id = f"{mission_id}-t01"
    required_artifacts = _infer_required_artifacts(
        verifier_command=verifier_command,
        allowed_writes=allowed_writes,
        mission_dir=mission_dir,
        task_id=task_id,
    )
    resolved_verifier = verifier_command.strip() or _default_verifier(required_artifacts)
    builder = {
        "schema": DS_GOAL_TASK_SCHEMA,
        "mission_id": mission_id,
        "task_id": task_id,
        "role": role or "builder",
        "agent_uid": agent_uid or "codex_composer",
        "title": str(mission.get("title") or mission.get("goal") or task_id),
        "status": "claimable",
        "allowed_writes": list(allowed_writes),
        "verifier_command": resolved_verifier,
        "required_artifacts": required_artifacts,
        "actuation_mode": "write_and_verify",
        "depends_on": [],
        "lease": {
            "claimed_by": "",
            "claimed_at": "",
            "expires_at": "",
        },
        "return_address": f"autonomy://{mission_id}/{task_id}",
        "requested_tools": [
            "session_status",
            "ds_goal_write_artifact",
            "ds_goal_run_verifier",
        ],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
        "requested_output": [
            "artifact_refs",
            "verifier_result",
            "ds_goal_supervisor_receipt",
        ],
        "stop_conditions": [
            "required_artifacts_exist",
            "verifier_command_exit_0",
        ],
        "receipt_required": True,
    }
    verifier_task_id = f"{mission_id}-t02-verifier"
    verifier = {
        **builder,
        "task_id": verifier_task_id,
        "role": "verifier",
        "title": f"Verify {builder['title']}",
        "allowed_writes": [],
        "actuation_mode": "verify_only",
        "depends_on": [task_id],
        "return_address": f"autonomy://{mission_id}/{verifier_task_id}",
        "requested_tools": [
            "session_status",
            "ds_goal_run_verifier",
        ],
        "requested_output": [
            "verifier_result",
            "ds_goal_supervisor_receipt",
        ],
    }
    return [builder, verifier]


def run_supervisor_loop(
    *,
    state_root: Path,
    mission_id: str,
    kernel_store: Path,
    workspace_root: Path,
    duration_hours: float,
    lease_seconds: int = 300,
    interval_seconds: float = 5.0,
    max_tasks_per_cycle: int = 1,
    worker_id: str = "ds-goal-supervisor",
    tmux_session: str = "",
    live_provider_requested: bool = False,
    provider: str = "",
    model: str = "",
    verifier_timeout_seconds: int = 120,
    max_cycles: int = 0,
) -> dict[str, Any]:
    mission_dir = mission_directory(state_root, mission_id)
    mission = _read_json(mission_dir / "mission.json")
    deadline = _deadline_from_duration(duration_hours)
    started_at = utc_now()
    cycle_count = 0
    latest_cycle: dict[str, Any] = {}
    _write_supervisor_state(
        mission_dir,
        {
            "status": "running",
            "mission_id": mission_id,
            "worker_id": worker_id,
            "pid": os.getpid(),
            "tmux_session": tmux_session,
            "started_at": started_at,
            "heartbeat_at": started_at,
            "deadline_at": _format_dt(deadline),
            "message": "ds-goal supervisor loop started",
            "cycle_count": 0,
        },
    )
    while True:
        cycle_count += 1
        latest_cycle = run_supervisor_cycle(
            state_root=state_root,
            mission_id=mission_id,
            kernel_store=kernel_store,
            workspace_root=workspace_root,
            lease_seconds=lease_seconds,
            max_tasks=max_tasks_per_cycle,
            worker_id=worker_id,
            live_provider_requested=live_provider_requested,
            provider=provider,
            model=model,
            verifier_timeout_seconds=verifier_timeout_seconds,
        )
        tasks = load_tasks(mission_dir)
        aggregate = mission_task_status(tasks)
        state_status = "completed" if aggregate == "completed" else latest_cycle["status"]
        _write_supervisor_state(
            mission_dir,
            {
                "status": state_status,
                "mission_id": mission_id,
                "worker_id": worker_id,
                "pid": os.getpid(),
                "tmux_session": tmux_session,
                "started_at": started_at,
                "heartbeat_at": utc_now(),
                "deadline_at": _format_dt(deadline),
                "latest_cycle": latest_cycle,
                "cycle_count": cycle_count,
                "open_task_count": open_task_count(tasks),
                "terminal_task_count": terminal_task_count(tasks),
                "message": latest_cycle.get("message", ""),
            },
        )
        if aggregate == "completed":
            break
        if latest_cycle["status"] in {"blocked", "failed"} and not has_runnable_task(tasks):
            break
        if max_cycles and cycle_count >= max(1, int(max_cycles)):
            break
        if datetime.now(UTC) >= deadline:
            break
        time.sleep(max(0.1, float(interval_seconds)))
    finished = {
        "schema_version": DS_GOAL_SUPERVISOR_SCHEMA,
        "status": "completed" if mission_task_status(load_tasks(mission_dir)) == "completed" else latest_cycle.get("status", "idle"),
        "mission_id": mission_id,
        "mission_title": str(mission.get("title") or ""),
        "worker_id": worker_id,
        "started_at": started_at,
        "finished_at": utc_now(),
        "deadline_at": _format_dt(deadline),
        "cycle_count": cycle_count,
        "latest_cycle": latest_cycle,
        "mission_dir": str(mission_dir),
        "kernel_store": str(kernel_store),
    }
    append_mission_receipt(mission_dir, {**finished, "event": "ds_goal_supervisor_loop"})
    _write_supervisor_state(
        mission_dir,
        {
            **finished,
            "pid": os.getpid(),
            "tmux_session": tmux_session,
            "heartbeat_at": utc_now(),
        },
    )
    return finished


def run_supervisor_cycle(
    *,
    state_root: Path,
    mission_id: str,
    kernel_store: Path,
    workspace_root: Path,
    lease_seconds: int = 300,
    max_tasks: int = 1,
    worker_id: str = "ds-goal-supervisor",
    live_provider_requested: bool = False,
    provider: str = "",
    model: str = "",
    verifier_timeout_seconds: int = 120,
) -> dict[str, Any]:
    mission_dir = mission_directory(state_root, mission_id)
    mission = _read_json(mission_dir / "mission.json")
    tasks = load_tasks(mission_dir)
    ran: list[dict[str, Any]] = []
    for _ in range(max(1, int(max_tasks))):
        task = first_runnable_task(tasks)
        if task is None:
            break
        lease = {
            "claimed_by": worker_id,
            "claimed_at": utc_now(),
            "expires_at": _utc_after(utc_now(), lease_seconds),
        }
        task = {
            **task,
            "status": "running",
            "lease": lease,
            "supervisor_worker_id": worker_id,
        }
        replace_task(mission_dir, task)
        result = execute_task(
            mission=mission,
            mission_dir=mission_dir,
            task=task,
            kernel_store=kernel_store,
            workspace_root=workspace_root,
            worker_id=worker_id,
            live_provider_requested=live_provider_requested,
            provider=provider,
            model=model,
            verifier_timeout_seconds=verifier_timeout_seconds,
        )
        replace_task(mission_dir, result["task"])
        ran.append(result)
        tasks = load_tasks(mission_dir)
    aggregate = mission_task_status(tasks)
    status: Literal["idle", "completed", "blocked", "failed", "running"]
    if ran:
        if any(item["status"] == "failed" for item in ran):
            status = "failed"
        elif any(item["status"] == "blocked" for item in ran):
            status = "blocked"
        elif aggregate == "completed":
            status = "completed"
        else:
            status = "running"
    else:
        status = "completed" if aggregate == "completed" else "idle"
    cycle = {
        "schema_version": "dharma.ds_goal_supervisor_cycle.v1",
        "status": status,
        "mission_id": mission_id,
        "worker_id": worker_id,
        "ran_task_count": len(ran),
        "task_results": [_task_result_summary(item) for item in ran],
        "open_task_count": open_task_count(tasks),
        "terminal_task_count": terminal_task_count(tasks),
        "created_at": utc_now(),
        "message": (
            f"Supervisor executed {len(ran)} ds-goal task(s)."
            if ran
            else "Supervisor found no runnable ds-goal task."
        ),
    }
    append_mission_receipt(mission_dir, {**cycle, "event": "ds_goal_supervisor_cycle"})
    return cycle


def execute_task(
    *,
    mission: dict[str, Any],
    mission_dir: Path,
    task: dict[str, Any],
    kernel_store: Path,
    workspace_root: Path,
    worker_id: str,
    live_provider_requested: bool,
    provider: str,
    model: str,
    verifier_timeout_seconds: int,
) -> dict[str, Any]:
    task_id = str(task.get("task_id") or task.get("id") or "")
    run_id = f"ds_goal_supervisor_{uuid4().hex[:16]}"
    provider_truth = {
        "provider_execution_requested": bool(live_provider_requested),
        "provider_execution": False,
        "provider": provider,
        "model": model,
        "provider_execution_truth_source": "ds_goal_supervisor.local_worker",
        "provider_note": (
            "live provider was requested; local supervisor actuation remains verifier-gated"
            if live_provider_requested
            else "local supervisor actuation without provider"
        ),
    }
    write_result = write_required_artifacts(
        mission=mission,
        mission_dir=mission_dir,
        task=task,
        workspace_root=workspace_root,
        run_id=run_id,
        worker_id=worker_id,
    )
    artifact_refs = write_result["artifact_refs"]
    artifacts_ok = write_result["status"] == "completed" and _all_required_artifacts_exist(task, artifact_refs)
    verifier_result = run_verifier_command(
        str(task.get("verifier_command") or ""),
        workspace_root=workspace_root,
        timeout_seconds=verifier_timeout_seconds,
    )
    verifier_ok = verifier_result["status"] == "passed"
    if not artifacts_ok:
        status = "blocked"
        reason = write_result.get("reason") or "required_artifact_write_failed"
    elif not verifier_ok:
        status = "blocked"
        reason = "verifier_command_failed"
    else:
        status = "completed"
        reason = "required_artifacts_and_verifier_passed"
    result_payload = {
        "schema_version": "dharma.ds_goal_supervisor_task_result.v1",
        "status": status,
        "reason": reason,
        "mission_id": str(mission.get("mission_id") or mission_dir.name),
        "task_id": task_id,
        "run_id": run_id,
        "worker_id": worker_id,
        "kernel_store": str(kernel_store),
        "artifact_refs": artifact_refs,
        "verifier_result": verifier_result,
        "provider_truth": provider_truth,
        "created_at": utc_now(),
    }
    result_hash = stable_payload_hash(result_payload)
    receipt = append_mission_receipt(
        mission_dir,
        {
            **result_payload,
            "event": "ds_goal_supervisor_task",
            "result_hash": result_hash,
        },
    )
    terminal_task = {
        **task,
        "status": "done" if status == "completed" else status,
        "kernel_result_status": status,
        "kernel_result_ref": {
            "kind": "ds_goal_supervisor_result",
            "run_id": run_id,
            "status": status,
            "proof_entry_hash": result_hash,
            "artifact_refs": artifact_refs,
            "verifier_result_ref": verifier_result.get("result_ref", {}),
            "receipt_hash": receipt["record_hash"],
            **provider_truth,
        },
        "kernel_closeback_at": utc_now(),
        "kernel_closeback_via": "operator_core.ds_goal_supervisor",
        "worker_result_ref": {
            "kind": "ds_goal_supervisor_task_result",
            "run_id": run_id,
            "receipt_hash": receipt["record_hash"],
            "path": str(receipt_path(mission_dir)),
        },
        "artifact_refs": artifact_refs,
        "verifier_result": verifier_result,
        "failure_reason": "" if status == "completed" else reason,
    }
    return {"status": status, "task": terminal_task, "receipt": receipt, "result": result_payload}


def write_required_artifacts(
    *,
    mission: dict[str, Any],
    mission_dir: Path,
    task: dict[str, Any],
    workspace_root: Path,
    run_id: str,
    worker_id: str,
) -> dict[str, Any]:
    required = _string_list(task.get("required_artifacts"))
    if not required:
        required = _infer_required_artifacts(
            verifier_command=str(task.get("verifier_command") or ""),
            allowed_writes=_string_list(task.get("allowed_writes")),
            mission_dir=mission_dir,
            task_id=str(task.get("task_id") or "task"),
        )
    if str(task.get("actuation_mode") or "") == "verify_only":
        refs: list[dict[str, Any]] = []
        for raw_path in required:
            target = _resolve_artifact_path(raw_path, workspace_root=workspace_root, mission_dir=mission_dir)
            if not target.exists():
                return {
                    "status": "blocked",
                    "reason": f"required_artifact_missing:{raw_path}",
                    "artifact_refs": refs,
                }
            refs.append(
                {
                    "kind": "ds_goal_existing_artifact",
                    "path": str(target),
                    "sha256": sha256_file(target),
                    "allowed_by": "verify_only_existing_artifact",
                }
            )
        return {"status": "completed", "artifact_refs": refs}
    refs: list[dict[str, Any]] = []
    for raw_path in required:
        target = _resolve_artifact_path(raw_path, workspace_root=workspace_root, mission_dir=mission_dir)
        allowed_reason = _artifact_allowed(
            target,
            allowed_writes=_string_list(task.get("allowed_writes")),
            workspace_root=workspace_root,
            mission_dir=mission_dir,
        )
        if not allowed_reason:
            return {
                "status": "blocked",
                "reason": f"artifact_target_outside_allowed_writes:{raw_path}",
                "artifact_refs": refs,
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "dharma.ds_goal_worker_artifact.v1",
            "mission_id": str(mission.get("mission_id") or mission_dir.name),
            "task_id": str(task.get("task_id") or task.get("id") or ""),
            "run_id": run_id,
            "worker_id": worker_id,
            "goal": str(mission.get("goal") or ""),
            "title": str(task.get("title") or mission.get("title") or ""),
            "allowed_writes": _string_list(task.get("allowed_writes")),
            "created_at": utc_now(),
        }
        payload["payload_hash"] = stable_payload_hash(payload)
        if target.suffix.lower() == ".json":
            target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            target.write_text(_artifact_markdown(payload), encoding="utf-8")
        refs.append(
            {
                "kind": "ds_goal_worker_artifact",
                "path": str(target),
                "sha256": sha256_file(target),
                "allowed_by": allowed_reason,
            }
        )
    return {"status": "completed", "artifact_refs": refs}


def _record_verifier_command_receipt(*, command: str, workspace_root: Path) -> None:
    """Append an audit-trail receipt before executing a shell verifier command.

    run_verifier_command executes an operator-supplied shell string with
    shell=True; this leaves a forensic trail (who/what ran, when, where) so an
    unexpected or injected command is at least detectable after the fact, even
    though it does not sanitize or restrict the command itself.
    """
    try:
        receipts_dir = Path.home() / ".dharma" / "witness"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema_version": "dharma.ds_goal_verifier_command_receipt.v1",
            "command": command,
            "workspace_root": str(workspace_root),
            "pid": os.getpid(),
            "recorded_at": utc_now(),
        }
        with (receipts_dir / "verifier_command_receipts.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True) + "\n")
    except OSError:
        pass


def run_verifier_command(
    verifier_command: str,
    *,
    workspace_root: Path,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    command = _normalize_verifier_command(str(verifier_command or "").strip())
    started_at = utc_now()
    if not command:
        return {
            "status": "failed",
            "exit_code": None,
            "command": "",
            "started_at": started_at,
            "completed_at": utc_now(),
            "reason": "verifier_command_missing",
        }
    workspace_root.mkdir(parents=True, exist_ok=True)
    _record_verifier_command_receipt(command=command, workspace_root=workspace_root)
    try:
        completed = subprocess.run(
            command,
            cwd=workspace_root,
            shell=True,
            executable="/bin/bash",
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "exit_code": None,
            "command": command,
            "started_at": started_at,
            "completed_at": utc_now(),
            "reason": "verifier_command_timeout",
            "stdout": _truncate(exc.stdout or ""),
            "stderr": _truncate(exc.stderr or ""),
        }
    status = "passed" if completed.returncode == 0 else "failed"
    payload = {
        "schema_version": "dharma.ds_goal_verifier_result.v1",
        "status": status,
        "exit_code": completed.returncode,
        "command": command,
        "cwd": str(workspace_root),
        "started_at": started_at,
        "completed_at": utc_now(),
        "stdout": _truncate(completed.stdout),
        "stderr": _truncate(completed.stderr),
    }
    payload["result_ref"] = {
        "kind": "ds_goal_verifier_result",
        "status": status,
        "payload_hash": stable_payload_hash(payload),
    }
    return payload


def start_tmux_supervisor(
    *,
    repo_root: Path,
    state_root: Path,
    mission_id: str,
    kernel_store: Path,
    runtime_db: Path | None = None,
    duration_hours: float = 0.0,
    lease_seconds: int = 300,
    interval_seconds: float = 5.0,
    max_tasks_per_cycle: int = 1,
    live_provider_requested: bool = False,
    provider: str = "",
    model: str = "",
    session_name: str = "",
) -> dict[str, Any]:
    mission_dir = mission_directory(state_root, mission_id)
    tmux = shutil.which("tmux")
    if not tmux:
        return {
            "status": "blocked",
            "mission_id": mission_id,
            "reason": "tmux_not_found",
            "tmux_session_created": False,
        }
    session = session_name or default_tmux_session(mission_id)
    if tmux_session_running(session):
        return {
            "status": "running",
            "mission_id": mission_id,
            "tmux_session": session,
            "tmux_session_created": False,
            "reason": "tmux_session_already_running",
        }
    logs_dir = mission_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "ds_goal_supervisor.log"
    script = repo_root / "scripts" / "runtime" / "ds_goal_supervisor.py"
    command = [
        sys.executable,
        str(script),
        "run",
        "--mission-id",
        mission_id,
        "--state-root",
        str(state_root),
        "--kernel-store",
        str(kernel_store),
        "--workspace-root",
        str(repo_root),
        "--duration-hours",
        str(float(duration_hours)),
        "--lease-seconds",
        str(int(lease_seconds)),
        "--interval-seconds",
        str(float(interval_seconds)),
        "--max-tasks-per-cycle",
        str(int(max_tasks_per_cycle)),
        "--tmux-session",
        session,
        "--json",
    ]
    if runtime_db is not None:
        command.extend(["--runtime-db", str(runtime_db)])
    if live_provider_requested:
        command.append("--live-provider-requested")
    if provider:
        command.extend(["--provider", provider])
    if model:
        command.extend(["--model", model])
    shell_command = f"cd {shlex.quote(str(repo_root))} && {shlex.join(command)} >> {shlex.quote(str(log_path))} 2>&1"
    plan_path = mission_dir / "supervisor" / "tmux_command.sh"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{shell_command}\n", encoding="utf-8")
    plan_path.chmod(0o700)
    started = subprocess.run(
        [tmux, "new-session", "-d", "-s", session, shell_command],
        check=False,
        capture_output=True,
        text=True,
    )
    status = "running" if started.returncode == 0 else "blocked"
    payload = {
        "schema_version": "dharma.ds_goal_tmux_supervisor_start.v1",
        "status": status,
        "mission_id": mission_id,
        "tmux_session": session,
        "tmux_session_created": started.returncode == 0,
        "tmux_command_path": str(plan_path),
        "log_path": str(log_path),
        "returncode": started.returncode,
        "stdout": _truncate(started.stdout),
        "stderr": _truncate(started.stderr),
        "created_at": utc_now(),
    }
    append_mission_receipt(mission_dir, {**payload, "event": "ds_goal_tmux_supervisor_start"})
    if started.returncode == 0:
        _write_supervisor_state(
            mission_dir,
            {
                "status": "running",
                "mission_id": mission_id,
                "tmux_session": session,
                "tmux_session_live": True,
                "log_path": str(log_path),
                "tmux_command_path": str(plan_path),
                "heartbeat_at": utc_now(),
                "message": "tmux supervisor session started",
            },
        )
    return payload


def stop_tmux_supervisor(*, state_root: Path, mission_id: str, session_name: str = "") -> dict[str, Any]:
    mission_dir = mission_directory(state_root, mission_id)
    tmux = shutil.which("tmux")
    session = session_name or default_tmux_session(mission_id)
    if not tmux:
        return {"status": "blocked", "mission_id": mission_id, "reason": "tmux_not_found"}
    if not tmux_session_running(session):
        payload = {
            "status": "stopped",
            "mission_id": mission_id,
            "tmux_session": session,
            "tmux_session_was_running": False,
        }
        append_mission_receipt(mission_dir, {**payload, "event": "ds_goal_tmux_supervisor_stop"})
        return payload
    stopped = subprocess.run([tmux, "kill-session", "-t", session], check=False, capture_output=True, text=True)
    payload = {
        "status": "stopped" if stopped.returncode == 0 else "failed",
        "mission_id": mission_id,
        "tmux_session": session,
        "tmux_session_was_running": True,
        "returncode": stopped.returncode,
        "stdout": _truncate(stopped.stdout),
        "stderr": _truncate(stopped.stderr),
    }
    append_mission_receipt(mission_dir, {**payload, "event": "ds_goal_tmux_supervisor_stop"})
    return payload


def supervisor_status_payload(
    *,
    state_root: Path,
    mission_id: str,
    session_name: str = "",
    stale_after_seconds: int = 180,
) -> dict[str, Any]:
    mission_dir = mission_directory(state_root, mission_id)
    state = _read_json(supervisor_state_path(mission_dir))
    session = session_name or str(state.get("tmux_session") or default_tmux_session(mission_id))
    live = tmux_session_running(session)
    heartbeat = str(state.get("heartbeat_at") or "")
    age = _age_seconds(heartbeat)
    tasks = load_tasks(mission_dir)
    if not state:
        status = "never_started"
    elif live:
        status = "running"
    elif state.get("status") == "completed":
        status = "completed"
    elif age is not None and age > max(1, int(stale_after_seconds)):
        status = "stale"
    else:
        status = str(state.get("status") or "stopped")
    return {
        "schema_version": "dharma.ds_goal_supervisor_status.v1",
        "status": status,
        "mission_id": mission_id,
        "mission_dir": str(mission_dir),
        "tmux_session": session,
        "tmux_session_live": live,
        "supervisor_state_path": str(supervisor_state_path(mission_dir)),
        "heartbeat_age_seconds": age,
        "open_task_count": open_task_count(tasks),
        "terminal_task_count": terminal_task_count(tasks),
        "state": state,
        "observed_at": utc_now(),
    }


def mission_directory(state_root: Path, mission_id: str) -> Path:
    clean = _validate_mission_id(mission_id)
    root = state_root.expanduser().resolve()
    mission_dir = root / clean
    resolved = mission_dir.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError("mission_id resolves outside state root")
    return mission_dir


def receipt_path(mission_dir: Path) -> Path:
    return mission_dir / "receipts.jsonl"


def tasks_path(mission_dir: Path) -> Path:
    return mission_dir / "tasks.jsonl"


def supervisor_state_path(mission_dir: Path) -> Path:
    return mission_dir / "supervisor" / "state.json"


def load_tasks(mission_dir: Path) -> list[dict[str, Any]]:
    return _jsonl_rows(tasks_path(mission_dir))


def replace_task(mission_dir: Path, task: dict[str, Any]) -> None:
    task_id = str(task.get("task_id") or task.get("id") or "")
    rows = load_tasks(mission_dir)
    for index, row in enumerate(rows):
        if str(row.get("task_id") or row.get("id") or "") == task_id:
            rows[index] = task
            _write_jsonl_rows(tasks_path(mission_dir), rows)
            return
    raise ValueError(f"task not found: {task_id}")


def append_mission_receipt(mission_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    rows = _jsonl_rows(receipt_path(mission_dir))
    row = {
        "schema_version": "dharma.ds_goal_spine.v1",
        "created_at": utc_now(),
        **receipt,
        "previous_record_hash": str(rows[-1].get("record_hash") or "") if rows else "",
        "record_hash": "",
    }
    row["record_hash"] = stable_payload_hash(row)
    _append_jsonl(receipt_path(mission_dir), row)
    return row


def first_runnable_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed_ids = {
        str(task.get("task_id") or task.get("id") or "")
        for task in tasks
        if str(task.get("kernel_result_status") or task.get("status") or "").strip().lower()
        in {"completed", "done"}
    }
    for task in tasks:
        status = str(task.get("status") or "").strip().lower()
        if status in TERMINAL_TASK_STATUSES:
            continue
        if status not in OPEN_TASK_STATUSES:
            continue
        depends_on = _string_list(task.get("depends_on"))
        if any(dep not in completed_ids for dep in depends_on):
            continue
        return dict(task)
    return None


def has_runnable_task(tasks: list[dict[str, Any]]) -> bool:
    return first_runnable_task(tasks) is not None


def open_task_count(tasks: list[dict[str, Any]]) -> int:
    return sum(1 for task in tasks if str(task.get("status") or "").strip().lower() not in TERMINAL_TASK_STATUSES)


def terminal_task_count(tasks: list[dict[str, Any]]) -> int:
    return len(tasks) - open_task_count(tasks)


def mission_task_status(tasks: list[dict[str, Any]]) -> str:
    if tasks and open_task_count(tasks) == 0:
        if all(str(task.get("kernel_result_status") or task.get("status") or "").lower() in {"completed", "done"} for task in tasks):
            return "completed"
        return "closed"
    if any(str(task.get("status") or "").lower() == "failed" for task in tasks):
        return "failed"
    if any(str(task.get("status") or "").lower() == "blocked" for task in tasks):
        return "blocked"
    return "running" if tasks else "idle"


def default_tmux_session(mission_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in mission_id)
    return f"ds_goal_{safe}"[:80]


def tmux_session_running(session_name: str) -> bool:
    tmux = shutil.which("tmux")
    if not tmux:
        return False
    result = subprocess.run([tmux, "has-session", "-t", session_name], check=False, capture_output=True, text=True)
    return result.returncode == 0


def _infer_required_artifacts(
    *,
    verifier_command: str,
    allowed_writes: list[str],
    mission_dir: Path,
    task_id: str,
) -> list[str]:
    candidates: list[str] = []
    if verifier_command.strip():
        try:
            tokens = shlex.split(verifier_command)
        except ValueError:
            tokens = verifier_command.split()
        for index, token in enumerate(tokens):
            previous = tokens[index - 1] if index else ""
            if previous in {"-f", "json.tool"} or _looks_like_artifact_path(token):
                cleaned = token.strip()
                if cleaned and cleaned not in {"&&", "||"}:
                    candidates.append(cleaned)
    if not candidates and allowed_writes:
        first = Path(allowed_writes[0])
        candidates.append(str(first if first.suffix else first / "receipt.json"))
    if not candidates:
        candidates.append(str(mission_dir / "artifacts" / task_id / "receipt.json"))
    return _dedupe(candidates)


def _default_verifier(required_artifacts: list[str]) -> str:
    if not required_artifacts:
        return ""
    return " && ".join(f"test -f {shlex.quote(path)}" for path in required_artifacts)


def _looks_like_artifact_path(token: str) -> bool:
    raw = str(token or "").strip()
    if not raw or raw.startswith("-") or raw in {"test", "python", "python3", "json.tool"}:
        return False
    suffix = Path(raw).suffix.lower()
    return suffix in {".json", ".md", ".txt", ".yaml", ".yml"}


def _resolve_artifact_path(raw_path: str, *, workspace_root: Path, mission_dir: Path) -> Path:
    target = Path(str(raw_path)).expanduser()
    if target.is_absolute():
        return target.resolve()
    mission_root = mission_dir.resolve()
    if str(raw_path).startswith("artifacts/") or str(raw_path).startswith("supervisor/"):
        return (mission_root / target).resolve()
    return (workspace_root.expanduser().resolve() / target).resolve()


def _artifact_allowed(
    target: Path,
    *,
    allowed_writes: list[str],
    workspace_root: Path,
    mission_dir: Path,
) -> str:
    resolved = target.resolve()
    mission_root = mission_dir.expanduser().resolve()
    if resolved == mission_root or mission_root in resolved.parents:
        return "mission_state_root"
    workspace = workspace_root.expanduser().resolve()
    try:
        relative = resolved.relative_to(workspace).as_posix()
    except ValueError:
        relative = ""
    for raw in allowed_writes:
        pattern = str(raw or "").strip().replace("\\", "/")
        if not pattern:
            continue
        allowed = Path(pattern).expanduser()
        if allowed.is_absolute():
            allowed_resolved = allowed.resolve()
            if resolved == allowed_resolved or allowed_resolved in resolved.parents:
                return pattern
            continue
        if not relative:
            continue
        if _relative_path_matches(relative, pattern, workspace_root=workspace):
            return pattern
    return ""


def _relative_path_matches(relative_path: str, pattern: str, *, workspace_root: Path) -> bool:
    normalized = pattern.strip().replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        candidate = Path(normalized).expanduser()
        try:
            normalized = candidate.resolve().relative_to(workspace_root).as_posix()
        except Exception:
            return False
    posix = PurePosixPath(normalized)
    if any(part == ".." for part in posix.parts):
        return False
    if fnmatch.fnmatchcase(relative_path, normalized):
        return True
    if normalized.endswith("/"):
        return relative_path.startswith(normalized)
    return relative_path.startswith(normalized.rstrip("/") + "/")


def _all_required_artifacts_exist(task: dict[str, Any], artifact_refs: list[dict[str, Any]]) -> bool:
    required = set(_string_list(task.get("required_artifacts")))
    observed = {str(ref.get("path") or "") for ref in artifact_refs}
    if not required:
        return bool(artifact_refs)
    for raw in required:
        if not any(path.endswith(raw) or Path(path).name == Path(raw).name for path in observed):
            return False
    return all(Path(path).exists() for path in observed)


def _write_supervisor_state(mission_dir: Path, payload: dict[str, Any]) -> None:
    material = {
        "schema_version": "dharma.ds_goal_supervisor_state.v1",
        **payload,
    }
    material["state_hash"] = stable_payload_hash({key: value for key, value in material.items() if key != "state_hash"})
    path = supervisor_state_path(mission_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(material, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def _validate_mission_id(mission_id: str) -> str:
    clean = str(mission_id or "").strip()
    if not MISSION_ID_RE.fullmatch(clean):
        raise ValueError("mission_id must be 1-96 chars of letters, numbers, dash, underscore, or dot")
    return clean


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _deadline_from_duration(duration_hours: float) -> datetime:
    duration = max(0.0, float(duration_hours or 0.0))
    seconds = max(1.0, duration * 3600.0) if duration else 1.0
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _utc_after(value: str, seconds: int) -> str:
    return (_parse_utc(value) + timedelta(seconds=max(1, int(seconds)))).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_dt(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _age_seconds(value: str) -> float | None:
    if not value:
        return None
    try:
        return (datetime.now(UTC) - _parse_utc(value)).total_seconds()
    except Exception:
        return None


def _truncate(value: str, limit: int = 8000) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def _normalize_verifier_command(command: str) -> str:
    if "python -m " not in command:
        return command
    return command.replace("python -m ", f"{shlex.quote(sys.executable)} -m ")


def _artifact_markdown(payload: dict[str, Any]) -> str:
    return (
        "# ds-goal Worker Artifact\n\n"
        f"- mission_id: `{payload['mission_id']}`\n"
        f"- task_id: `{payload['task_id']}`\n"
        f"- run_id: `{payload['run_id']}`\n"
        f"- worker_id: `{payload['worker_id']}`\n"
        f"- created_at: `{payload['created_at']}`\n"
        f"- payload_hash: `{payload['payload_hash']}`\n"
    )


def _task_result_summary(item: dict[str, Any]) -> dict[str, Any]:
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    return {
        "status": item.get("status"),
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "artifact_count": len(result.get("artifact_refs") or []),
        "verifier_status": (result.get("verifier_result") or {}).get("status"),
    }


__all__ = [
    "compile_mission_tasks",
    "default_tmux_session",
    "execute_task",
    "mission_directory",
    "run_supervisor_cycle",
    "run_supervisor_loop",
    "start_tmux_supervisor",
    "stop_tmux_supervisor",
    "supervisor_status_payload",
    "tmux_session_running",
]
