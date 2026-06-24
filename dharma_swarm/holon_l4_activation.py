"""Reviewed activation receipts for L4 HOLON supervisor artifacts.

This module is the governed handoff after ``holon_l4_supervisor`` renders a
review plan. It records hash-reviewed installs and launch reviews in an
append-only ledger. It does not call launchctl, start tmux, or spawn the service
unless the caller explicitly passes ``live=True``.
"""
from __future__ import annotations

import fcntl
import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.holon_service_liveness import assess_service_liveness
from dharma_swarm.holon_l4_service import SERVICE_ID
from dharma_swarm.holon_l4_supervisor import HolonL4SupervisorPlan
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

HolonL4ActivationStatus = Literal["reviewed", "installed", "activated", "denied", "failed"]
HolonL4ActivationTarget = Literal["supervisor_service", "launch_artifact", "launch_start"]
HolonL4LaunchStatus = Literal["launched", "completed", "failed"]
HolonL4LaunchArtifactState = Literal["missing", "installed", "changed", "started", "unknown"]
HolonL4Launcher = Callable[[list[str], Path], "HolonL4ProcessLaunch"]


class HolonL4ProcessLaunch(BaseModel):
    schema_version: str = "dharma.holon_l4_process_launch.v1"
    status: HolonL4LaunchStatus
    pid: int | None = None
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    message: str = ""


class HolonL4ActivationReceipt(BaseModel):
    schema_version: str = "dharma.holon_l4_activation_receipt.v1"
    target_kind: HolonL4ActivationTarget
    status: HolonL4ActivationStatus
    activation_dir: str
    holon: str = ""
    command: list[str] = Field(default_factory=list)
    command_hash: str = ""
    approved_ref: dict[str, Any] = Field(default_factory=dict)
    install_ref: dict[str, Any] = Field(default_factory=dict)
    process_ref: dict[str, Any] = Field(default_factory=dict)
    service_state_ref: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    message: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""


class HolonL4LaunchArtifactStatus(BaseModel):
    schema_version: str = "dharma.holon_l4_launch_artifact_status.v1"
    status: HolonL4LaunchArtifactState
    activation_dir: str
    install_receipt_hash: str
    install_ref: dict[str, Any] = Field(default_factory=dict)
    latest_start_ref: dict[str, Any] = Field(default_factory=dict)
    observed_at: str = Field(default_factory=utc_now)
    message: str = ""


class HolonL4ActivationStore:
    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.activation_path = self.base_dir / "activation_receipts.jsonl"

    def activations(self) -> list[HolonL4ActivationReceipt]:
        return [HolonL4ActivationReceipt.model_validate(row) for row in _jsonl_rows(self.activation_path)]

    def activation_by_hash(self, record_hash: str) -> HolonL4ActivationReceipt | None:
        target = record_hash.strip()
        for receipt in self.activations():
            if receipt.record_hash == target:
                return receipt
        return None

    def append_activation(self, receipt: HolonL4ActivationReceipt) -> HolonL4ActivationReceipt:
        return _append_hashed(self.activation_path, receipt, HolonL4ActivationReceipt)

    def verify_activation_ledger(self) -> tuple[bool, list[str]]:
        if not self.activation_path.exists():
            return (True, [])
        return _verify_hash_ledger(self.activation_path)


def activation_dir_for_plan(plan: HolonL4SupervisorPlan) -> Path:
    plan_ref = str(plan.artifact_refs.get("supervisor_plan") or "").strip()
    if plan_ref:
        return Path(plan_ref).expanduser().resolve().parent
    return Path(plan.agents_root).expanduser().resolve() / plan.holon / "supervisor"


def command_hash(command: list[str], *, cwd: Path | str) -> str:
    return stable_payload_hash({"command": list(command), "cwd": str(Path(cwd).expanduser().resolve())})


def activate_holon_l4_supervisor_plan(
    plan: HolonL4SupervisorPlan,
    *,
    approved_receipt_hash: str,
    live: bool = False,
    require_service_heartbeat: bool = False,
    service_heartbeat_fresh_after_seconds: int = 3600,
    service_heartbeat_timeout_seconds: float = 0.0,
    service_heartbeat_poll_seconds: float = 0.5,
    launcher: HolonL4Launcher | None = None,
    now: str | None = None,
) -> HolonL4ActivationReceipt:
    activation_dir = activation_dir_for_plan(plan)
    store = HolonL4ActivationStore(activation_dir)
    command = list(plan.service_command)
    expected_hash = plan.receipt_hash
    actual_hash = approved_receipt_hash.strip()
    cmd_hash = command_hash(command, cwd=plan.repo_root)
    approved_ref = _plan_approved_ref(plan, approved_receipt_hash=actual_hash)
    baseline_record_hash = ""
    if require_service_heartbeat:
        baseline_record_hash = str(
            assess_service_liveness(plan.holon, agents_root=Path(plan.agents_root)).get("latest_record_hash") or ""
        )
    if actual_hash != expected_hash:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="supervisor_service",
                status="denied",
                activation_dir=str(activation_dir),
                holon=plan.holon,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="L4 supervisor activation denied because the approved plan hash does not match.",
            )
        )
    if not live:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="supervisor_service",
                status="reviewed",
                activation_dir=str(activation_dir),
                holon=plan.holon,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="L4 supervisor plan hash reviewed; live process launch was not requested.",
            )
        )
    try:
        launch = (launcher or _popen_launcher)(command, Path(plan.repo_root))
    except Exception as exc:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="supervisor_service",
                status="failed",
                activation_dir=str(activation_dir),
                holon=plan.holon,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message=f"L4 supervisor activation failed: {type(exc).__name__}: {exc}",
            )
        )
    service_state_ref: dict[str, Any] = {}
    status: HolonL4ActivationStatus = "activated" if launch.status in {"launched", "completed"} else "failed"
    message = "L4 supervisor service command launched under reviewed plan hash."
    if require_service_heartbeat:
        service_state_ref = _await_service_liveness(
            plan.holon,
            agents_root=Path(plan.agents_root),
            fresh_after_seconds=max(1, int(service_heartbeat_fresh_after_seconds)),
            timeout_seconds=service_heartbeat_timeout_seconds,
            poll_seconds=service_heartbeat_poll_seconds,
            previous_record_hash=baseline_record_hash,
            expected_session_id=_command_flag_value(command, "--session-id"),
            expected_service_id=SERVICE_ID,
        )
        if not bool(service_state_ref.get("service_alive")):
            status = "failed"
            message = "L4 supervisor service command ran but no fresh service heartbeat was observed."
    return store.append_activation(
        HolonL4ActivationReceipt(
            target_kind="supervisor_service",
            status=status,
            activation_dir=str(activation_dir),
            holon=plan.holon,
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            process_ref=launch.model_dump(mode="json"),
            service_state_ref=service_state_ref,
            created_at=now or utc_now(),
            message=message,
        )
    )


def install_holon_l4_supervisor_plan(
    plan: HolonL4SupervisorPlan,
    *,
    approved_receipt_hash: str,
    install_dir: Path | str,
    now: str | None = None,
) -> HolonL4ActivationReceipt:
    activation_dir = activation_dir_for_plan(plan)
    store = HolonL4ActivationStore(activation_dir)
    expected_hash = plan.receipt_hash
    actual_hash = approved_receipt_hash.strip()
    destination_dir = Path(install_dir).expanduser().resolve()
    command = ["install_holon_l4_supervisor_plan", plan.mode, str(destination_dir)]
    cmd_hash = command_hash(command, cwd=plan.repo_root)
    approved_ref = _plan_approved_ref(plan, approved_receipt_hash=actual_hash)
    if actual_hash != expected_hash:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="launch_artifact",
                status="denied",
                activation_dir=str(activation_dir),
                holon=plan.holon,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                created_at=now or utc_now(),
                message="L4 launch artifact install denied because the approved plan hash does not match.",
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
        "holon": plan.holon,
        "agents_root": plan.agents_root,
        "expected_service_id": SERVICE_ID,
        "expected_session_id": _command_flag_value(plan.service_command, "--session-id"),
        "launch_started": False,
    }
    return store.append_activation(
        HolonL4ActivationReceipt(
            target_kind="launch_artifact",
            status="installed",
            activation_dir=str(activation_dir),
            holon=plan.holon,
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            install_ref=install_ref,
            created_at=now or utc_now(),
            message="Reviewed L4 launch artifact installed without starting a service.",
        )
    )


def holon_l4_launch_artifact_status(
    *,
    activation_dir: Path | str,
    install_receipt_hash: str,
    now: str | None = None,
) -> HolonL4LaunchArtifactStatus:
    store = HolonL4ActivationStore(activation_dir)
    observed_at = now or utc_now()
    install_receipt = store.activation_by_hash(install_receipt_hash)
    if install_receipt is None or install_receipt.target_kind != "launch_artifact":
        return HolonL4LaunchArtifactStatus(
            status="unknown",
            activation_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            observed_at=observed_at,
            message="Install receipt was not found.",
        )
    install_ref = dict(install_receipt.install_ref)
    artifact_path = Path(str(install_ref.get("path") or ""))
    if not artifact_path.exists():
        return HolonL4LaunchArtifactStatus(
            status="missing",
            activation_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            install_ref=install_ref,
            observed_at=observed_at,
            message="Installed launch artifact is missing.",
        )
    content_hash = stable_payload_hash({"content": artifact_path.read_text(encoding="utf-8")})
    if content_hash != str(install_ref.get("content_hash") or ""):
        return HolonL4LaunchArtifactStatus(
            status="changed",
            activation_dir=str(store.base_dir),
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
        return HolonL4LaunchArtifactStatus(
            status="started",
            activation_dir=str(store.base_dir),
            install_receipt_hash=install_receipt_hash,
            install_ref=install_ref,
            latest_start_ref={
                "kind": "holon_l4_launch_start",
                "record_hash": latest.record_hash,
                "command_hash": latest.command_hash,
                "process_ref": dict(latest.process_ref),
                "service_state_ref": dict(latest.service_state_ref),
            },
            observed_at=observed_at,
            message="L4 launch artifact has an activated start receipt.",
        )
    return HolonL4LaunchArtifactStatus(
        status="installed",
        activation_dir=str(store.base_dir),
        install_receipt_hash=install_receipt_hash,
        install_ref=install_ref,
        observed_at=observed_at,
        message="L4 launch artifact is installed and content hash matches.",
    )


def start_installed_holon_l4_supervisor_artifact(
    *,
    activation_dir: Path | str,
    install_receipt_hash: str,
    live: bool = False,
    launchd_domain: str = "gui/current",
    require_service_heartbeat: bool = False,
    service_heartbeat_fresh_after_seconds: int = 3600,
    service_heartbeat_timeout_seconds: float = 0.0,
    service_heartbeat_poll_seconds: float = 0.5,
    launcher: HolonL4Launcher | None = None,
    now: str | None = None,
) -> HolonL4ActivationReceipt:
    store = HolonL4ActivationStore(activation_dir)
    install_receipt = store.activation_by_hash(install_receipt_hash)
    if (
        install_receipt is None
        or install_receipt.target_kind != "launch_artifact"
        or install_receipt.status != "installed"
    ):
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="launch_start",
                status="denied",
                activation_dir=str(store.base_dir),
                approved_ref={"kind": "holon_l4_launch_artifact", "install_receipt_hash": install_receipt_hash},
                created_at=now or utc_now(),
                message="L4 launch start denied because an installed launch artifact receipt was not found.",
            )
        )
    status = holon_l4_launch_artifact_status(
        activation_dir=store.base_dir,
        install_receipt_hash=install_receipt_hash,
        now=now,
    )
    install_ref = dict(install_receipt.install_ref)
    if status.status in {"missing", "changed", "unknown"}:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="launch_start",
                status="failed",
                activation_dir=str(store.base_dir),
                holon=install_receipt.holon,
                approved_ref={"kind": "holon_l4_launch_artifact", "install_receipt_hash": install_receipt_hash},
                install_ref=install_ref,
                created_at=now or utc_now(),
                message=f"L4 launch start failed preflight: {status.message}",
            )
        )
    command = _launch_start_command(install_ref, launchd_domain=launchd_domain)
    cmd_hash = command_hash(command, cwd=store.base_dir)
    baseline_record_hash = ""
    if require_service_heartbeat:
        agents_root = str(install_ref.get("agents_root") or "").strip()
        if agents_root:
            baseline_record_hash = str(
                assess_service_liveness(
                    install_receipt.holon,
                    agents_root=Path(agents_root),
                ).get("latest_record_hash")
                or ""
            )
    approved_ref = {
        "kind": "holon_l4_launch_artifact",
        "install_receipt_hash": install_receipt_hash,
        "install_command_hash": install_receipt.command_hash,
        "launchd_domain": launchd_domain,
    }
    if not live:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="launch_start",
                status="reviewed",
                activation_dir=str(store.base_dir),
                holon=install_receipt.holon,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                install_ref=install_ref,
                created_at=now or utc_now(),
                message="L4 launch start command reviewed; live launch was not requested.",
            )
        )
    try:
        launch = (launcher or _run_launcher)(command, store.base_dir)
    except Exception as exc:
        return store.append_activation(
            HolonL4ActivationReceipt(
                target_kind="launch_start",
                status="failed",
                activation_dir=str(store.base_dir),
                holon=install_receipt.holon,
                command=command,
                command_hash=cmd_hash,
                approved_ref=approved_ref,
                install_ref=install_ref,
                created_at=now or utc_now(),
                message=f"L4 launch start failed: {type(exc).__name__}: {exc}",
            )
        )
    service_state_ref: dict[str, Any] = {}
    started = launch.status in {"completed", "launched"}
    receipt_status: HolonL4ActivationStatus = "activated" if started else "failed"
    message = "L4 launch start command executed from reviewed install receipt."
    if require_service_heartbeat:
        agents_root = str(install_ref.get("agents_root") or "").strip()
        if agents_root:
            service_state_ref = _await_service_liveness(
                install_receipt.holon,
                agents_root=Path(agents_root),
                fresh_after_seconds=max(1, int(service_heartbeat_fresh_after_seconds)),
                timeout_seconds=service_heartbeat_timeout_seconds,
                poll_seconds=service_heartbeat_poll_seconds,
                previous_record_hash=baseline_record_hash,
                expected_session_id=str(install_ref.get("expected_session_id") or ""),
                expected_service_id=str(install_ref.get("expected_service_id") or SERVICE_ID),
            )
            if not bool(service_state_ref.get("service_alive")):
                receipt_status = "failed"
                message = "L4 launch start command ran but no fresh service heartbeat was observed."
        else:
            receipt_status = "failed"
            message = "L4 launch start cannot verify service heartbeat because install receipt lacks agents_root."
    return store.append_activation(
        HolonL4ActivationReceipt(
            target_kind="launch_start",
            status=receipt_status,
            activation_dir=str(store.base_dir),
            holon=install_receipt.holon,
            command=command,
            command_hash=cmd_hash,
            approved_ref=approved_ref,
            install_ref={**install_ref, "launch_started": started},
            process_ref=launch.model_dump(mode="json"),
            service_state_ref=service_state_ref,
            created_at=now or utc_now(),
            message=message,
        )
    )


def _plan_approved_ref(
    plan: HolonL4SupervisorPlan,
    *,
    approved_receipt_hash: str,
) -> dict[str, Any]:
    return {
        "kind": "holon_l4_supervisor_plan",
        "mode": plan.mode,
        "holon": plan.holon,
        "plan_receipt_hash": plan.receipt_hash,
        "approved_receipt_hash": approved_receipt_hash,
        "artifact_refs": dict(plan.artifact_refs),
        "safety": dict(plan.safety),
    }


def _command_flag_value(command: list[str], flag: str) -> str:
    try:
        index = list(command).index(flag)
    except ValueError:
        return ""
    if index + 1 >= len(command):
        return ""
    return str(command[index + 1])


def _await_service_liveness(
    holon: str,
    *,
    agents_root: Path,
    fresh_after_seconds: int,
    timeout_seconds: float,
    poll_seconds: float,
    previous_record_hash: str = "",
    expected_session_id: str = "",
    expected_service_id: str = "",
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    poll = max(0.05, float(poll_seconds))
    latest: dict[str, Any] = {}
    while True:
        latest = assess_service_liveness(
            holon,
            agents_root=agents_root,
            fresh_after_seconds=fresh_after_seconds,
        )
        observed_record_hash = str(latest.get("latest_record_hash") or "")
        observed_session_id = str(latest.get("latest_session_id") or "")
        observed_service_id = str(latest.get("latest_service_id") or "")
        new_record_seen = not previous_record_hash or observed_record_hash != previous_record_hash
        session_matched = not expected_session_id or observed_session_id == expected_session_id
        service_id_matched = not expected_service_id or observed_service_id == expected_service_id
        latest["required_new_record_observed"] = new_record_seen
        latest["required_previous_record_hash"] = previous_record_hash
        latest["required_session_id"] = expected_session_id
        latest["required_session_id_matched"] = session_matched
        latest["required_service_id"] = expected_service_id
        latest["required_service_id_matched"] = service_id_matched
        matched = (
            bool(latest.get("service_alive"))
            and new_record_seen
            and session_matched
            and service_id_matched
        )
        if matched:
            return latest
        latest["service_alive"] = False
        if time.monotonic() >= deadline:
            return latest
        time.sleep(min(poll, max(0.0, deadline - time.monotonic())))


def _popen_launcher(command: list[str], cwd: Path) -> HolonL4ProcessLaunch:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return HolonL4ProcessLaunch(status="launched", pid=process.pid, message="Process launched.")


def _run_launcher(command: list[str], cwd: Path) -> HolonL4ProcessLaunch:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return HolonL4ProcessLaunch(status="launched", pid=process.pid, message="Launch command spawned.")


def _launch_start_command(install_ref: dict[str, Any], *, launchd_domain: str) -> list[str]:
    mode = str(install_ref.get("mode") or "")
    path = str(install_ref.get("path") or "")
    if mode == "launchd":
        return ["launchctl", "bootstrap", launchd_domain, path]
    if mode == "tmux":
        return ["/bin/bash", path]
    raise ValueError(f"unsupported L4 launch artifact mode: {mode}")


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
    "HolonL4ActivationReceipt",
    "HolonL4ActivationStatus",
    "HolonL4ActivationStore",
    "HolonL4ActivationTarget",
    "HolonL4LaunchArtifactState",
    "HolonL4LaunchArtifactStatus",
    "HolonL4LaunchStatus",
    "HolonL4ProcessLaunch",
    "activate_holon_l4_supervisor_plan",
    "activation_dir_for_plan",
    "command_hash",
    "holon_l4_launch_artifact_status",
    "install_holon_l4_supervisor_plan",
    "start_installed_holon_l4_supervisor_artifact",
]
