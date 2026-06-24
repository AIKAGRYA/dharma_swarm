"""Review-only supervisor plans for the L4 HOLON service runner.

This module renders launchd/tmux artifacts for ``scripts/holon_l4_service.py``.
It intentionally does not install plist files, call launchctl, start tmux, or
spawn the service. The output is a review artifact for a later governed launch
step.
"""
from __future__ import annotations

import json
import plistlib
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.holon_bridge import AGENTS_ROOT
from dharma_swarm.holon_l4_service import default_service_lock_path
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

SUPERVISOR_PLAN_SCHEMA_VERSION = "dharma.holon_l4_supervisor_plan.v1"
HolonL4SupervisorMode = Literal["launchd", "tmux"]
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class HolonL4SupervisorPlan(BaseModel):
    schema_version: str = SUPERVISOR_PLAN_SCHEMA_VERSION
    mode: HolonL4SupervisorMode
    holon: str
    label: str
    repo_root: str
    agents_root: str
    memory_receipt_path: str
    service_command: list[str] = Field(default_factory=list)
    launchd_plist: str = ""
    tmux_session: str = ""
    tmux_command: str = ""
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True
    generated_at: str = Field(default_factory=utc_now)
    receipt_hash: str = ""


def _safe_segment(value: str, *, fallback: str = "holon") -> str:
    raw = str(value or "").strip().lower()
    safe = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip(".-")
    return safe or fallback


def _validate_safe_name(value: str, *, field: str) -> str:
    raw = str(value or "").strip()
    if not _SAFE_NAME_RE.fullmatch(raw):
        raise ValueError(f"{field} must be a simple alphanumeric/dot/dash/underscore name")
    return raw


def default_supervisor_label(name: str) -> str:
    return f"com.dharma.holon-l4.{_safe_segment(name)}"


def default_tmux_session(name: str) -> str:
    return f"dharma_holon_l4_{_safe_segment(name).replace('-', '_').replace('.', '_')}"


def _append_optional_path_arg(command: list[str], flag: str, value: Path | str | None) -> None:
    if value is not None:
        command.extend([flag, str(Path(value).expanduser().resolve())])


def _build_service_command(
    *,
    name: str,
    repo_root: Path,
    agents_root: Path,
    memory_receipt_path: Path,
    lease_seconds: int,
    cycles: int,
    forever: bool,
    interval_seconds: float,
    lock_path: Path,
    session_id: str,
    live_model_probe: bool,
    model_probe_first_cycle_only: bool,
    model_probe_timeout_seconds: int,
    model_probe_message: str,
    allow_subprocess_model_probe: bool,
    safe_subprocess_model_probe: bool,
    safe_subprocess_probe_cwd: Path | None,
    model_probe_lease_id: str,
    model_probe_lease_path: Path | None,
    transport_agent_uid: str,
    transport_heartbeat_path: Path | None,
    transport_fresh_after_seconds: int,
    require_transport_reachable: bool,
    enable_orchestration_probe: bool,
    require_orchestration: bool,
    orchestration_execution_mode: str,
    orchestration_timeout_seconds: float,
    orchestration_min_subtasks: int,
    orchestration_min_model_tiers: int,
    deterministic_orchestration_plan: bool,
    use_readonly_swarm_manager_orchestrator: bool,
    orchestration_state_dir: Path | None,
    python_executable: str | None,
) -> list[str]:
    script = repo_root / "scripts" / "holon_l4_service.py"
    command = [
        python_executable or sys.executable,
        str(script),
        name,
        "--agents-root",
        str(agents_root),
        "--memory-receipt-path",
        str(memory_receipt_path),
        "--lease-seconds",
        str(max(1, int(lease_seconds))),
        "--interval-seconds",
        str(max(0.0, float(interval_seconds))),
        "--lock-path",
        str(lock_path),
        "--json",
    ]
    if session_id:
        command.extend(["--session-id", session_id])
    if forever:
        command.append("--forever")
    else:
        command.extend(["--cycles", str(max(0, int(cycles)))])
    if live_model_probe:
        command.extend(
            [
                "--live-model-probe",
                "--model-probe-timeout-seconds",
                str(max(1, int(model_probe_timeout_seconds))),
                "--model-probe-message",
                model_probe_message,
            ]
        )
    if model_probe_first_cycle_only:
        command.append("--model-probe-first-cycle-only")
    if allow_subprocess_model_probe:
        command.append("--allow-subprocess-model-probe")
    if safe_subprocess_model_probe:
        command.append("--safe-subprocess-model-probe")
    _append_optional_path_arg(command, "--safe-subprocess-probe-cwd", safe_subprocess_probe_cwd)
    if model_probe_lease_id:
        command.extend(["--model-probe-lease-id", model_probe_lease_id])
    _append_optional_path_arg(command, "--model-probe-lease-path", model_probe_lease_path)
    if transport_agent_uid:
        command.extend(["--transport-agent-uid", transport_agent_uid])
    _append_optional_path_arg(command, "--transport-heartbeat-path", transport_heartbeat_path)
    command.extend(
        [
            "--transport-fresh-after-seconds",
            str(max(1, int(transport_fresh_after_seconds))),
        ]
    )
    if require_transport_reachable:
        command.append("--require-transport-reachable")
    orchestration_configured = (
        enable_orchestration_probe
        or require_orchestration
        or use_readonly_swarm_manager_orchestrator
    )
    if orchestration_configured:
        if enable_orchestration_probe:
            command.append("--enable-orchestration-probe")
        if require_orchestration:
            command.append("--require-orchestration")
        command.extend(
            [
                "--orchestration-execution-mode",
                orchestration_execution_mode,
                "--orchestration-timeout-seconds",
                str(max(0.1, float(orchestration_timeout_seconds))),
                "--orchestration-min-subtasks",
                str(max(1, int(orchestration_min_subtasks))),
                "--orchestration-min-model-tiers",
                str(max(1, int(orchestration_min_model_tiers))),
            ]
        )
        if not deterministic_orchestration_plan:
            command.append("--no-deterministic-orchestration-plan")
        if use_readonly_swarm_manager_orchestrator:
            command.append("--use-readonly-swarm-manager-orchestrator")
        _append_optional_path_arg(command, "--orchestration-state-dir", orchestration_state_dir)
    return command


def build_holon_l4_supervisor_plan(
    *,
    name: str = "codex_composer",
    mode: HolonL4SupervisorMode,
    repo_root: Path | str,
    agents_root: Path | str = AGENTS_ROOT,
    memory_receipt_path: Path | str = Path(
        "reports/sovereign_holons/l4_memory_write_receipts.jsonl"
    ),
    output_dir: Path | str | None = None,
    label: str | None = None,
    tmux_session: str | None = None,
    lease_seconds: int = 900,
    cycles: int = 1,
    forever: bool = True,
    interval_seconds: float = 60.0,
    lock_path: Path | str | None = None,
    session_id: str = "",
    live_model_probe: bool = False,
    model_probe_first_cycle_only: bool = False,
    model_probe_timeout_seconds: int = 120,
    model_probe_message: str = (
        "Reply with one short sentence confirming you are responsive as this holon."
    ),
    allow_subprocess_model_probe: bool = False,
    safe_subprocess_model_probe: bool = False,
    safe_subprocess_probe_cwd: Path | str | None = None,
    model_probe_lease_id: str = "",
    model_probe_lease_path: Path | str | None = None,
    transport_agent_uid: str = "",
    transport_heartbeat_path: Path | str | None = None,
    transport_fresh_after_seconds: int = 3600,
    require_transport_reachable: bool = False,
    enable_orchestration_probe: bool = False,
    require_orchestration: bool = False,
    orchestration_execution_mode: str = "dispatch_aggregation_probe",
    orchestration_timeout_seconds: float = 30.0,
    orchestration_min_subtasks: int = 2,
    orchestration_min_model_tiers: int = 2,
    deterministic_orchestration_plan: bool = True,
    use_readonly_swarm_manager_orchestrator: bool = False,
    orchestration_state_dir: Path | str | None = None,
    python_executable: str | None = None,
) -> HolonL4SupervisorPlan:
    name = _validate_safe_name(name, field="name")
    repo = Path(repo_root).expanduser().resolve()
    agents = Path(agents_root).expanduser().resolve()
    memory_path = Path(memory_receipt_path).expanduser()
    if not memory_path.is_absolute():
        memory_path = repo / memory_path
    memory_path = memory_path.resolve()
    service_lock = Path(lock_path or default_service_lock_path(name, agents)).expanduser().resolve()
    supervisor_dir = Path(output_dir).expanduser().resolve() if output_dir else (
        agents / name / "supervisor"
    )
    rendered_label = _validate_safe_name(label or default_supervisor_label(name), field="label")
    rendered_tmux_session = _validate_safe_name(
        tmux_session or default_tmux_session(name),
        field="tmux_session",
    )

    model_lease_path = (
        Path(model_probe_lease_path).expanduser().resolve()
        if model_probe_lease_path is not None
        else None
    )
    safe_probe_cwd = (
        Path(safe_subprocess_probe_cwd).expanduser().resolve()
        if safe_subprocess_probe_cwd is not None
        else None
    )
    transport_path = (
        Path(transport_heartbeat_path).expanduser().resolve()
        if transport_heartbeat_path is not None
        else None
    )
    orchestration_state_path = (
        Path(orchestration_state_dir).expanduser().resolve()
        if orchestration_state_dir is not None
        else None
    )
    command = _build_service_command(
        name=name,
        repo_root=repo,
        agents_root=agents,
        memory_receipt_path=memory_path,
        lease_seconds=lease_seconds,
        cycles=cycles,
        forever=forever,
        interval_seconds=interval_seconds,
        lock_path=service_lock,
        session_id=session_id,
        live_model_probe=live_model_probe,
        model_probe_first_cycle_only=model_probe_first_cycle_only,
        model_probe_timeout_seconds=model_probe_timeout_seconds,
        model_probe_message=model_probe_message,
        allow_subprocess_model_probe=allow_subprocess_model_probe,
        safe_subprocess_model_probe=safe_subprocess_model_probe,
        safe_subprocess_probe_cwd=safe_probe_cwd,
        model_probe_lease_id=model_probe_lease_id,
        model_probe_lease_path=model_lease_path,
        transport_agent_uid=transport_agent_uid,
        transport_heartbeat_path=transport_path,
        transport_fresh_after_seconds=transport_fresh_after_seconds,
        require_transport_reachable=require_transport_reachable,
        enable_orchestration_probe=enable_orchestration_probe,
        require_orchestration=require_orchestration,
        orchestration_execution_mode=orchestration_execution_mode,
        orchestration_timeout_seconds=orchestration_timeout_seconds,
        orchestration_min_subtasks=orchestration_min_subtasks,
        orchestration_min_model_tiers=orchestration_min_model_tiers,
        deterministic_orchestration_plan=deterministic_orchestration_plan,
        use_readonly_swarm_manager_orchestrator=use_readonly_swarm_manager_orchestrator,
        orchestration_state_dir=orchestration_state_path,
        python_executable=python_executable,
    )

    artifact_refs = {
        "supervisor_plan": str(supervisor_dir / f"{mode}_supervisor_plan.json"),
    }
    launchd_plist = ""
    tmux_command = ""
    if mode == "launchd":
        logs_dir = agents / name / "logs"
        plist_payload = {
            "Label": rendered_label,
            "ProgramArguments": command,
            "WorkingDirectory": str(repo),
            "RunAtLoad": False,
            "KeepAlive": True,
            "StandardOutPath": str(logs_dir / "holon-l4-service.stdout.log"),
            "StandardErrorPath": str(logs_dir / "holon-l4-service.stderr.log"),
            "EnvironmentVariables": {
                "PYTHONUNBUFFERED": "1",
            },
        }
        launchd_plist = plistlib.dumps(plist_payload, sort_keys=True).decode("utf-8")
        artifact_refs["planned_launchd_plist"] = str(
            supervisor_dir / f"{rendered_label}.plist"
        )
    else:
        quoted_command = " ".join(shlex.quote(part) for part in command)
        tmux_command = (
            f"tmux new-session -d -s {shlex.quote(rendered_tmux_session)} "
            f"{shlex.quote(f'cd {shlex.quote(str(repo))} && {quoted_command}')}"
        )
        artifact_refs["planned_tmux_command"] = str(
            supervisor_dir / f"{rendered_tmux_session}.sh"
        )

    safety = {
        "review_only": True,
        "install_performed": False,
        "service_started": False,
        "launchctl_invoked": False,
        "tmux_invoked": False,
        "process_action_performed": False,
        "requires_operator_install": True,
        "writes_only_review_artifacts": True,
    }
    plan = HolonL4SupervisorPlan(
        mode=mode,
        holon=name,
        label=rendered_label,
        repo_root=str(repo),
        agents_root=str(agents),
        memory_receipt_path=str(memory_path),
        service_command=command,
        launchd_plist=launchd_plist,
        tmux_session=rendered_tmux_session if mode == "tmux" else "",
        tmux_command=tmux_command,
        artifact_refs=artifact_refs,
        safety=safety,
    )
    plan.receipt_hash = stable_payload_hash(plan.model_dump(mode="json", exclude={"receipt_hash"}))
    return plan


def write_holon_l4_supervisor_plan(plan: HolonL4SupervisorPlan) -> HolonL4SupervisorPlan:
    refs = dict(plan.artifact_refs)
    plan_path = Path(refs["supervisor_plan"])
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if plan.mode == "launchd":
        Path(refs["planned_launchd_plist"]).write_text(plan.launchd_plist, encoding="utf-8")
    elif plan.mode == "tmux":
        script_path = Path(refs["planned_tmux_command"])
        script_path.write_text(
            f"#!/usr/bin/env bash\nset -euo pipefail\n{plan.tmux_command}\n",
            encoding="utf-8",
        )
        script_path.chmod(0o700)
    plan_path.write_text(
        json.dumps(plan.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return plan


__all__ = [
    "HolonL4SupervisorMode",
    "HolonL4SupervisorPlan",
    "SUPERVISOR_PLAN_SCHEMA_VERSION",
    "build_holon_l4_supervisor_plan",
    "default_supervisor_label",
    "default_tmux_session",
    "write_holon_l4_supervisor_plan",
]
