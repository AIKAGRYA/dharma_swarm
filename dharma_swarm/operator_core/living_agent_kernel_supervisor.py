"""Supervisor planning/status for LivingAgentKernel service runners.

This module renders reviewable launchd/tmux supervisor plans and status
receipts. It intentionally does not call launchctl, tmux, or spawn processes.
"""

from __future__ import annotations

import json
import plistlib
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import DEFAULT_KERNEL_RUN_DIR, KernelRunStore
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

KernelSupervisorMode = Literal["launchd", "tmux"]
KernelSupervisorStatusValue = Literal["never_ran", "recent", "stale"]


class KernelSupervisorPlan(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_supervisor_plan.v1"
    mode: KernelSupervisorMode
    daemon_id: str = "living-agent-kernel"
    label: str = "com.dharma.living-agent-kernel"
    repo_root: str
    store_dir: str
    workspace_root: str
    service_command: list[str] = Field(default_factory=list)
    launchd_plist: str = ""
    tmux_session: str = ""
    tmux_command: str = ""
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = True
    generated_at: str = Field(default_factory=utc_now)
    receipt_hash: str = ""


class KernelSupervisorStatus(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_supervisor_status.v1"
    status: KernelSupervisorStatusValue
    daemon_id: str = "living-agent-kernel"
    store_dir: str
    observed_at: str = Field(default_factory=utc_now)
    latest_cycle_ref: dict[str, Any] = Field(default_factory=dict)
    latest_cycle_age_seconds: float | None = None
    cycle_count: int = 0
    message: str = ""


def build_supervisor_plan(
    *,
    mode: KernelSupervisorMode,
    repo_root: Path | str,
    store_dir: Path | str | None = None,
    workspace_root: Path | str | None = None,
    daemon_id: str = "living-agent-kernel",
    label: str = "com.dharma.living-agent-kernel",
    interval_seconds: int = 60,
    max_wakes: int = 1,
    lease_seconds: int = 300,
    latest_limit: int = 20,
    python_executable: str | None = None,
    tmux_session: str = "dharma_living_agent_kernel",
) -> KernelSupervisorPlan:
    repo = Path(repo_root).expanduser().resolve()
    store = Path(store_dir or DEFAULT_KERNEL_RUN_DIR).expanduser().resolve()
    workspace = Path(workspace_root or repo).expanduser().resolve()
    script = repo / "scripts" / "runtime" / "living_agent_kernel_service.py"
    python = python_executable or sys.executable
    command = [
        python,
        str(script),
        "--store-dir",
        str(store),
        "--workspace-root",
        str(workspace),
        "--daemon-id",
        daemon_id,
        "--forever",
        "--interval-seconds",
        str(max(1, int(interval_seconds))),
        "--max-wakes",
        str(max(0, int(max_wakes))),
        "--lease-seconds",
        str(max(1, int(lease_seconds))),
        "--latest-limit",
        str(max(1, int(latest_limit))),
        "--json",
    ]
    logs_dir = store / "logs"
    artifact_refs: dict[str, str] = {}
    launchd_plist = ""
    tmux_command = ""
    if mode == "launchd":
        plist_payload = {
            "Label": label,
            "ProgramArguments": command,
            "WorkingDirectory": str(repo),
            "RunAtLoad": False,
            "KeepAlive": True,
            "StandardOutPath": str(logs_dir / "living-agent-kernel.stdout.log"),
            "StandardErrorPath": str(logs_dir / "living-agent-kernel.stderr.log"),
            "EnvironmentVariables": {
                "PYTHONUNBUFFERED": "1",
            },
        }
        launchd_plist = plistlib.dumps(plist_payload, sort_keys=True).decode("utf-8")
        artifact_refs["planned_launchd_plist"] = str(store / "supervisor" / f"{label}.plist")
    else:
        quoted_command = " ".join(shlex.quote(part) for part in command)
        tmux_command = (
            f"tmux new-session -d -s {shlex.quote(tmux_session)} "
            f"{shlex.quote(f'cd {shlex.quote(str(repo))} && {quoted_command}')}"
        )
        artifact_refs["planned_tmux_command"] = str(store / "supervisor" / f"{tmux_session}.sh")
    artifact_refs["supervisor_plan"] = str(store / "supervisor" / f"{mode}_supervisor_plan.json")
    plan = KernelSupervisorPlan(
        mode=mode,
        daemon_id=daemon_id,
        label=label,
        repo_root=str(repo),
        store_dir=str(store),
        workspace_root=str(workspace),
        service_command=command,
        launchd_plist=launchd_plist,
        tmux_session=tmux_session if mode == "tmux" else "",
        tmux_command=tmux_command,
        artifact_refs=artifact_refs,
    )
    plan.receipt_hash = stable_payload_hash(plan.model_dump(mode="json", exclude={"receipt_hash"}))
    return plan


def write_supervisor_plan(plan: KernelSupervisorPlan) -> KernelSupervisorPlan:
    refs = dict(plan.artifact_refs)
    plan_path = Path(refs["supervisor_plan"])
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if plan.mode == "launchd":
        Path(refs["planned_launchd_plist"]).write_text(plan.launchd_plist, encoding="utf-8")
    elif plan.mode == "tmux":
        script_path = Path(refs["planned_tmux_command"])
        script_path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{plan.tmux_command}\n", encoding="utf-8")
        script_path.chmod(0o700)
    plan_path.write_text(json.dumps(plan.model_dump(mode="json"), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return plan


def supervisor_status(
    *,
    store_dir: Path | str | None = None,
    daemon_id: str = "living-agent-kernel",
    stale_after_seconds: int = 180,
    now: str | None = None,
) -> KernelSupervisorStatus:
    store = KernelRunStore(store_dir or DEFAULT_KERNEL_RUN_DIR)
    observed_at = now or utc_now()
    cycles = [cycle for cycle in store.daemon_cycles() if cycle.daemon_id == daemon_id]
    if not cycles:
        return KernelSupervisorStatus(
            status="never_ran",
            daemon_id=daemon_id,
            store_dir=str(store.base_dir),
            observed_at=observed_at,
            message="No daemon cycle receipts found for this daemon id.",
        )
    latest = cycles[-1]
    age = (_parse_utc(observed_at) - _parse_utc(latest.finished_at or latest.started_at)).total_seconds()
    status: KernelSupervisorStatusValue = "recent" if age <= max(1, int(stale_after_seconds)) else "stale"
    return KernelSupervisorStatus(
        status=status,
        daemon_id=daemon_id,
        store_dir=str(store.base_dir),
        observed_at=observed_at,
        latest_cycle_ref={
            "kind": "kernel_daemon_cycle",
            "cycle_id": latest.cycle_id,
            "status": latest.status,
            "record_hash": latest.record_hash,
            "path": str(store.daemon_cycles_path),
        },
        latest_cycle_age_seconds=age,
        cycle_count=len(cycles),
        message=(
            f"Latest daemon cycle is {age:.0f}s old."
            if status == "recent"
            else f"Latest daemon cycle is stale at {age:.0f}s old."
        ),
    )


def _parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


__all__ = [
    "KernelSupervisorMode",
    "KernelSupervisorPlan",
    "KernelSupervisorStatus",
    "build_supervisor_plan",
    "supervisor_status",
    "write_supervisor_plan",
]
