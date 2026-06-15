"""Reviewed activation receipts for LivingAgentKernel processes.

This module records operator-reviewed service and worker-process launches. It
does not install launchd/tmux jobs, call providers, or create another queue.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import DEFAULT_KERNEL_RUN_DIR
from dharma_swarm.operator_core.living_agent_kernel_supervisor import KernelSupervisorPlan
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

KernelActivationStatus = Literal["reviewed", "installed", "activated", "denied", "failed"]
KernelActivationTarget = Literal["supervisor_service", "worker_process", "launch_artifact", "launch_start"]
KernelLaunchStatus = Literal["launched", "completed", "failed"]
KernelLaunchArtifactState = Literal["missing", "installed", "changed", "started", "unknown"]
KernelLauncher = Callable[[list[str], Path], "KernelProcessLaunch"]


class KernelProcessLaunch(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_process_launch.v1"
    status: KernelLaunchStatus
    pid: int | None = None
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    message: str = ""


class KernelActivationReceipt(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_activation_receipt.v1"
    target_kind: KernelActivationTarget
    status: KernelActivationStatus
    store_dir: str
    command: list[str] = Field(default_factory=list)
    command_hash: str = ""
    approved_ref: dict[str, Any] = Field(default_factory=dict)
    install_ref: dict[str, Any] = Field(default_factory=dict)
    process_ref: dict[str, Any] = Field(default_factory=dict)
    worker_state_ref: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    message: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelLaunchArtifactStatus(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_launch_artifact_status.v1"
    status: KernelLaunchArtifactState
    store_dir: str
    install_receipt_hash: str
    install_ref: dict[str, Any] = Field(default_factory=dict)
    latest_start_ref: dict[str, Any] = Field(default_factory=dict)
    observed_at: str = Field(default_factory=utc_now)
    message: str = ""


class KernelActivationStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.activation_path = self.base_dir / "activation_receipts.jsonl"

    def activations(self) -> list[KernelActivationReceipt]:
        return [KernelActivationReceipt.model_validate(row) for row in _jsonl_rows(self.activation_path)]

    def activation_by_hash(self, record_hash: str) -> KernelActivationReceipt | None:
        target = record_hash.strip()
        for receipt in self.activations():
            if receipt.record_hash == target:
                return receipt
        return None

    def append_activation(self, receipt: KernelActivationReceipt) -> KernelActivationReceipt:
        return _append_hashed(self.activation_path, receipt, KernelActivationReceipt)

    def verify_activation_ledger(self) -> tuple[bool, list[str]]:
        if not self.activation_path.exists():
            return (True, [])
        return _verify_hash_ledger(self.activation_path)


def command_hash(command: list[str], *, cwd: Path | str) -> str:
    return stable_payload_hash({"command": list(command), "cwd": str(Path(cwd).expanduser().resolve())})


def activate_supervisor_plan(
    plan: KernelSupervisorPlan,
    *,
    approved_receipt_hash: str,
    live: bool = False,
    launcher: KernelLauncher | None = None,
    now: str | None = None,
) -> KernelActivationReceipt:
    store = KernelActivationStore(plan.store_dir)
    command = list(plan.service_command)
    expected_hash = plan.receipt_hash
    actual_hash = approved_receipt_hash.strip()
    cmd_hash = command_hash(command, cwd=plan.repo_root)
    approved_ref = {
        "kind": "kernel_supervisor_plan",
        "mode": plan.mode,
        "plan_receipt_hash": expected_hash,
        "approved_receipt_hash": actual_hash,
        "artifact_refs": dict(plan.artifact_refs),
    }
    if actual_hash != expected_hash:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="supervisor_service",
                status="denied",
                store_dir=plan.store_dir,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="Supervisor activation denied because the approved plan hash does not match.",
            )
        )
    if not live:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="supervisor_service",
                status="reviewed",
                store_dir=plan.store_dir,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="Supervisor plan hash reviewed; live process launch was not requested.",
            )
        )
    try:
        launch = (launcher or _popen_launcher)(command, Path(plan.repo_root))
    except Exception as exc:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="supervisor_service",
                status="failed",
                store_dir=plan.store_dir,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message=f"Supervisor activation failed: {type(exc).__name__}: {exc}",
            )
        )
    return store.append_activation(
        KernelActivationReceipt(
            target_kind="supervisor_service",
            status="activated" if launch.status in {"launched", "completed"} else "failed",
            store_dir=plan.store_dir,
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            process_ref=launch.model_dump(mode="json"),
            created_at=now or utc_now(),
            message="Supervisor service command launched under reviewed plan hash.",
        )
    )


def install_supervisor_plan(
    plan: KernelSupervisorPlan,
    *,
    approved_receipt_hash: str,
    install_dir: Path | str,
    now: str | None = None,
) -> KernelActivationReceipt:
    store = KernelActivationStore(plan.store_dir)
    expected_hash = plan.receipt_hash
    actual_hash = approved_receipt_hash.strip()
    destination_dir = Path(install_dir).expanduser().resolve()
    command = ["install_supervisor_plan", plan.mode, str(destination_dir)]
    cmd_hash = command_hash(command, cwd=plan.repo_root)
    approved_ref = {
        "kind": "kernel_supervisor_plan",
        "mode": plan.mode,
        "plan_receipt_hash": expected_hash,
        "approved_receipt_hash": actual_hash,
        "artifact_refs": dict(plan.artifact_refs),
    }
    if actual_hash != expected_hash:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="launch_artifact",
                status="denied",
                store_dir=plan.store_dir,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="Launch artifact install denied because the approved plan hash does not match.",
            )
        )
    destination_dir.mkdir(parents=True, exist_ok=True)
    if plan.mode == "launchd":
        destination = destination_dir / f"{plan.label}.plist"
        content = plan.launchd_plist
        artifact_kind = "launchd_plist"
    else:
        destination = destination_dir / f"{plan.tmux_session}.sh"
        content = f"#!/usr/bin/env bash\nset -euo pipefail\n{plan.tmux_command}\n"
        artifact_kind = "tmux_script"
    destination.write_text(content, encoding="utf-8")
    if plan.mode == "tmux":
        destination.chmod(0o700)
    install_ref = {
        "kind": artifact_kind,
        "path": str(destination),
        "content_hash": stable_payload_hash({"content": content}),
        "mode": plan.mode,
        "launch_started": False,
    }
    return store.append_activation(
        KernelActivationReceipt(
            target_kind="launch_artifact",
            status="installed",
            store_dir=plan.store_dir,
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            install_ref=install_ref,
            created_at=now or utc_now(),
            message="Reviewed launch artifact installed without starting a service.",
        )
    )


def launch_artifact_status(
    *,
    store_dir: Path | str | None = None,
    install_receipt_hash: str,
    now: str | None = None,
) -> KernelLaunchArtifactStatus:
    store = KernelActivationStore(store_dir)
    observed_at = now or utc_now()
    install_receipt = store.activation_by_hash(install_receipt_hash)
    if install_receipt is None or install_receipt.target_kind != "launch_artifact":
        return KernelLaunchArtifactStatus(
            status="unknown",
            store_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            observed_at=observed_at,
            message="Install receipt was not found.",
        )
    install_ref = dict(install_receipt.install_ref)
    artifact_path = Path(str(install_ref.get("path") or ""))
    if not artifact_path.exists():
        return KernelLaunchArtifactStatus(
            status="missing",
            store_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            install_ref=install_ref,
            observed_at=observed_at,
            message="Installed launch artifact is missing.",
        )
    content_hash = stable_payload_hash({"content": artifact_path.read_text(encoding="utf-8")})
    if content_hash != str(install_ref.get("content_hash") or ""):
        return KernelLaunchArtifactStatus(
            status="changed",
            store_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            install_ref=install_ref,
            observed_at=observed_at,
            message="Installed launch artifact content hash changed.",
        )
    starts = [
        receipt
        for receipt in store.activations()
        if receipt.target_kind == "launch_start"
        and receipt.status == "activated"
        and receipt.approved_ref.get("install_receipt_hash") == install_receipt_hash
    ]
    if starts:
        latest = starts[-1]
        return KernelLaunchArtifactStatus(
            status="started",
            store_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            install_ref=install_ref,
            latest_start_ref={
                "kind": "kernel_launch_start",
                "record_hash": latest.record_hash,
                "command_hash": latest.command_hash,
                "process_ref": dict(latest.process_ref),
            },
            observed_at=observed_at,
            message="Launch artifact has an activated start receipt.",
        )
    return KernelLaunchArtifactStatus(
        status="installed",
        store_dir=str(store.base_dir),
        install_receipt_hash=install_receipt_hash,
        install_ref=install_ref,
        observed_at=observed_at,
        message="Launch artifact is installed and content hash matches.",
    )


def start_installed_supervisor_artifact(
    *,
    store_dir: Path | str | None = None,
    install_receipt_hash: str,
    live: bool = False,
    launchd_domain: str = "gui/current",
    launcher: KernelLauncher | None = None,
    now: str | None = None,
) -> KernelActivationReceipt:
    store = KernelActivationStore(store_dir)
    install_receipt = store.activation_by_hash(install_receipt_hash)
    if install_receipt is None or install_receipt.target_kind != "launch_artifact" or install_receipt.status != "installed":
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="launch_start",
                status="denied",
                store_dir=str(store.base_dir),
                approved_ref={"kind": "kernel_launch_artifact", "install_receipt_hash": install_receipt_hash},
                created_at=now or utc_now(),
                message="Launch start denied because an installed launch artifact receipt was not found.",
            )
        )
    status = launch_artifact_status(store_dir=store.base_dir, install_receipt_hash=install_receipt_hash, now=now)
    install_ref = dict(install_receipt.install_ref)
    if status.status in {"missing", "changed", "unknown"}:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="launch_start",
                status="failed",
                store_dir=str(store.base_dir),
                approved_ref={"kind": "kernel_launch_artifact", "install_receipt_hash": install_receipt_hash},
                install_ref=install_ref,
                created_at=now or utc_now(),
                message=f"Launch start failed preflight: {status.message}",
            )
        )
    command = _launch_start_command(install_ref, launchd_domain=launchd_domain)
    cmd_hash = command_hash(command, cwd=store.base_dir)
    approved_ref = {
        "kind": "kernel_launch_artifact",
        "install_receipt_hash": install_receipt_hash,
        "install_command_hash": install_receipt.command_hash,
        "launchd_domain": launchd_domain,
    }
    if not live:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="launch_start",
                status="reviewed",
                store_dir=str(store.base_dir),
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                install_ref=install_ref,
                created_at=now or utc_now(),
                message="Launch start command reviewed; live launch was not requested.",
            )
        )
    try:
        launch = (launcher or _run_launcher)(command, store.base_dir)
    except Exception as exc:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="launch_start",
                status="failed",
                store_dir=str(store.base_dir),
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                install_ref=install_ref,
                created_at=now or utc_now(),
                message=f"Launch start failed: {type(exc).__name__}: {exc}",
            )
        )
    return store.append_activation(
        KernelActivationReceipt(
            target_kind="launch_start",
            status="activated" if launch.status in {"completed", "launched"} else "failed",
            store_dir=str(store.base_dir),
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            install_ref={**install_ref, "launch_started": launch.status in {"completed", "launched"}},
            process_ref=launch.model_dump(mode="json"),
            created_at=now or utc_now(),
            message="Launch start command executed from reviewed install receipt.",
        )
    )


def build_worker_process_command(
    *,
    repo_root: Path | str,
    store_dir: Path | str | None = None,
    workspace_root: Path | str | None = None,
    worker_id: str,
    role: str = "worker",
    allowed_sources: list[str] | tuple[str, ...] | None = None,
    max_lease_seconds: int = 300,
    heartbeat_interval_seconds: int = 60,
    cycles: int | None = 1,
    lease: bool = False,
    execute: bool = False,
    now: str | None = None,
    python_executable: str | None = None,
) -> list[str]:
    repo = Path(repo_root).expanduser().resolve()
    store = Path(store_dir or DEFAULT_KERNEL_RUN_DIR).expanduser().resolve()
    workspace = Path(workspace_root or repo).expanduser().resolve()
    command = [
        python_executable or sys.executable,
        str(repo / "scripts" / "runtime" / "living_agent_kernel_worker_process.py"),
        "--store-dir",
        str(store),
        "--workspace-root",
        str(workspace),
        "--worker-id",
        worker_id,
        "--role",
        role,
        "--max-lease-seconds",
        str(max(1, int(max_lease_seconds))),
        "--heartbeat-interval-seconds",
        str(max(0, int(heartbeat_interval_seconds))),
        "--json",
    ]
    if cycles is None:
        command.append("--forever")
    else:
        command.extend(["--cycles", str(max(0, int(cycles)))])
    for source in sorted(set(allowed_sources or [])):
        command.extend(["--allowed-source", source])
    if lease:
        command.append("--lease")
    if execute:
        command.append("--execute")
    if now:
        command.extend(["--now", now])
    return command


def activate_worker_process(
    *,
    repo_root: Path | str,
    store_dir: Path | str | None = None,
    workspace_root: Path | str | None = None,
    worker_id: str,
    approved_command_hash: str,
    role: str = "worker",
    allowed_sources: list[str] | tuple[str, ...] | None = None,
    max_lease_seconds: int = 300,
    heartbeat_interval_seconds: int = 60,
    cycles: int | None = 1,
    lease: bool = False,
    execute: bool = False,
    now: str | None = None,
    live: bool = False,
    require_heartbeat: bool = False,
    launcher: KernelLauncher | None = None,
) -> KernelActivationReceipt:
    repo = Path(repo_root).expanduser().resolve()
    store_dir_path = Path(store_dir or DEFAULT_KERNEL_RUN_DIR).expanduser().resolve()
    command = build_worker_process_command(
        repo_root=repo,
        store_dir=store_dir_path,
        workspace_root=workspace_root or repo,
        worker_id=worker_id,
        role=role,
        allowed_sources=allowed_sources,
        max_lease_seconds=max_lease_seconds,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        cycles=cycles,
        lease=lease,
        execute=execute,
        now=now,
    )
    store = KernelActivationStore(store_dir_path)
    cmd_hash = command_hash(command, cwd=repo)
    approved_ref = {
        "kind": "kernel_worker_process_command",
        "worker_id": worker_id,
        "command_hash": cmd_hash,
        "approved_command_hash": approved_command_hash.strip(),
    }
    if approved_command_hash.strip() != cmd_hash:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="worker_process",
                status="denied",
                store_dir=str(store_dir_path),
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="Worker process activation denied because the approved command hash does not match.",
            )
        )
    if not live:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="worker_process",
                status="reviewed",
                store_dir=str(store_dir_path),
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="Worker process command hash reviewed; live process launch was not requested.",
            )
        )
    try:
        launch = (launcher or _popen_launcher)(command, repo)
    except Exception as exc:
        return store.append_activation(
            KernelActivationReceipt(
                target_kind="worker_process",
                status="failed",
                store_dir=str(store_dir_path),
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message=f"Worker process activation failed: {type(exc).__name__}: {exc}",
            )
        )
    worker_state_ref: dict[str, Any] = {}
    status: KernelActivationStatus = "activated" if launch.status in {"launched", "completed"} else "failed"
    message = "Worker process command launched under reviewed command hash."
    if require_heartbeat:
        states = KernelExternalWorkerStore(store_dir_path).worker_states(now=now)
        worker_state = next((state for state in states if state.worker_id == worker_id), None)
        worker_state_ref = worker_state.model_dump(mode="json") if worker_state is not None else {}
        if worker_state is None or worker_state.status != "online":
            status = "failed"
            message = "Worker process launched but no fresh online heartbeat was observed."
    return store.append_activation(
        KernelActivationReceipt(
            target_kind="worker_process",
            status=status,
            store_dir=str(store_dir_path),
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            process_ref=launch.model_dump(mode="json"),
            worker_state_ref=worker_state_ref,
            created_at=now or utc_now(),
            message=message,
        )
    )


def _popen_launcher(command: list[str], cwd: Path) -> KernelProcessLaunch:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return KernelProcessLaunch(status="launched", pid=process.pid, message="Process launched.")


def _run_launcher(command: list[str], cwd: Path) -> KernelProcessLaunch:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, check=False)
    return KernelProcessLaunch(
        status="completed" if completed.returncode == 0 else "failed",
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        message="Launch command completed." if completed.returncode == 0 else "Launch command failed.",
    )


def _launch_start_command(install_ref: dict[str, Any], *, launchd_domain: str) -> list[str]:
    mode = str(install_ref.get("mode") or "")
    path = str(install_ref.get("path") or "")
    if mode == "launchd":
        return ["launchctl", "bootstrap", launchd_domain, path]
    if mode == "tmux":
        return [path]
    raise ValueError(f"unsupported launch artifact mode: {mode}")


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _append_hashed(path: Path, model: BaseModel, model_type: type[Any]) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    with lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        try:
            row = model.model_dump(mode="json")
            rows = _jsonl_rows(path)
            row["previous_record_hash"] = str(rows[-1].get("record_hash") or "") if rows else ""
            row["record_hash"] = ""
            row["record_hash"] = stable_payload_hash(row)
            _append_jsonl(path, row)
        finally:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
    return model_type.model_validate(row)


def _verify_hash_ledger(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    previous = ""
    for index, row in enumerate(_jsonl_rows(path), start=1):
        expected_previous = str(row.get("previous_record_hash") or "")
        if expected_previous != previous:
            errors.append(f"row {index}: previous_record_hash mismatch")
        observed_hash = str(row.get("record_hash") or "")
        payload = dict(row)
        payload["record_hash"] = ""
        expected_hash = stable_payload_hash(payload)
        if observed_hash != expected_hash:
            errors.append(f"row {index}: record_hash mismatch")
        previous = observed_hash
    return (len(errors) == 0, errors)


__all__ = [
    "KernelActivationReceipt",
    "KernelActivationStatus",
    "KernelActivationStore",
    "KernelActivationTarget",
    "KernelLaunchArtifactStatus",
    "KernelLaunchArtifactState",
    "KernelLaunchStatus",
    "KernelProcessLaunch",
    "activate_supervisor_plan",
    "activate_worker_process",
    "build_worker_process_command",
    "command_hash",
    "install_supervisor_plan",
    "launch_artifact_status",
    "start_installed_supervisor_artifact",
]
