"""One read-only status projection for the bounded daily RSI Lab lane."""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.forge_lab.model_onboarding import activation_status
from dharma_swarm.forge_lab.operator_views import doctor
from dharma_swarm.forge_lab.reconciliation_view import (
    composite_reconciliation_status,
)
from dharma_swarm.forge_lab.state_io import content_digest, forge_state_root, safe_json
from dharma_swarm.forge_lab.taskpack_ops import taskpack_status
from dharma_swarm.forge_lab.unattended_explore import (
    RECEIPT_SCHEMA,
    RUNNER_POLICY,
    TERMINAL_SUCCESS_STATES,
    UnattendedError,
    _validated_child_result,
    admission_status,
    read_chain,
)
from dharma_swarm.forge_lab.unattended_scratch import (
    validate_parent_scratch_proofs,
)

STATUS_SCHEMA = "rsi_lab.daily_status.v1"
SCHEDULER_SCHEMA = "rsi_lab.scheduler_status.v1"
TIMER_UNIT = "rsi-lab-explore.timer"
SERVICE_UNIT = "rsi-lab-explore.service"
MAX_LAST_ATTEMPT_AGE_SECONDS = 36 * 60 * 60


def _sha256(path: Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _unit_sources(repo_root: Path | None = None) -> dict[str, Path]:
    repo = (repo_root or Path(__file__).resolve().parents[2]).resolve(strict=False)
    root = repo / "scripts" / "forge_lab" / "systemd"
    return {TIMER_UNIT: root / TIMER_UNIT, SERVICE_UNIT: root / SERVICE_UNIT}


def _show_fields(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator and key:
            result[key] = value
    return result


def scheduler_status(
    *,
    repo_root: Path | None = None,
    unit_root: Path = Path("/etc/systemd/system"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Verify installed unit bytes, enablement, activity, and next trigger."""

    sources = _unit_sources(repo_root)
    units: dict[str, Any] = {}
    for name, source in sources.items():
        installed = unit_root / name
        source_digest = _sha256(source)
        installed_digest = _sha256(installed) if not installed.is_symlink() else None
        units[name] = {
            "source": str(source),
            "installed": str(installed),
            "source_digest": source_digest,
            "installed_digest": installed_digest,
            "bytes_match": bool(source_digest and source_digest == installed_digest),
        }

    timer_fields: dict[str, str] = {}
    service_fields: dict[str, str] = {}
    error: str | None = None
    try:
        timer_result = runner(
            [
                "systemctl",
                "show",
                TIMER_UNIT,
                "--no-pager",
                "--property=LoadState,ActiveState,UnitFileState,FragmentPath,DropInPaths,"
                "TimersCalendar,NextElapseUSecRealtime,LastTriggerUSec",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        service_result = runner(
            [
                "systemctl",
                "show",
                SERVICE_UNIT,
                "--no-pager",
                "--property=LoadState,ActiveState,FragmentPath,DropInPaths,ExecStart,"
                "Result,ExecMainCode,ExecMainStatus",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        if timer_result.returncode == 0 and service_result.returncode == 0:
            timer_fields = _show_fields(timer_result.stdout)
            service_fields = _show_fields(service_result.stdout)
        else:
            error = (
                f"systemctl_exit_timer_{timer_result.returncode}_"
                f"service_{service_result.returncode}"
            )
    except (OSError, subprocess.SubprocessError) as exc:
        error = type(exc).__name__

    timer_text = ""
    try:
        timer_text = sources[TIMER_UNIT].read_text(encoding="utf-8")
    except OSError:
        pass
    persistent = any(
        line.strip().casefold() == "persistent=true"
        for line in timer_text.splitlines()
    )
    calendar = next(
        (
            line.split("=", 1)[1].strip()
            for line in timer_text.splitlines()
            if line.strip().startswith("OnCalendar=")
        ),
        None,
    )
    expected_timer_fragment = str((unit_root / TIMER_UNIT).resolve(strict=False))
    expected_service_fragment = str((unit_root / SERVICE_UNIT).resolve(strict=False))
    timer_effective = bool(
        timer_fields.get("LoadState") == "loaded"
        and timer_fields.get("ActiveState") == "active"
        and timer_fields.get("UnitFileState") == "enabled"
        and timer_fields.get("FragmentPath") == expected_timer_fragment
        and not timer_fields.get("DropInPaths")
        and calendar
        and calendar in timer_fields.get("TimersCalendar", "")
        and timer_fields.get("NextElapseUSecRealtime", "").strip().casefold()
        not in {"", "n/a"}
    )
    service_effective = bool(
        service_fields.get("LoadState") == "loaded"
        and service_fields.get("FragmentPath") == expected_service_fragment
        and not service_fields.get("DropInPaths")
        and "/root/rsi-lab/bin/rsi-unattended-explore --timeout-seconds 2700"
        in service_fields.get("ExecStart", "")
        and service_fields.get("Result") in {"", "success"}
        and service_fields.get("ExecMainStatus") in {"", "0"}
    )
    ready = bool(
        all(row["bytes_match"] for row in units.values())
        and persistent
        and timer_effective
        and service_effective
    )
    return {
        "schema": SCHEDULER_SCHEMA,
        "ready": ready,
        "read_only": True,
        "unit": TIMER_UNIT,
        "calendar": calendar,
        "persistent": persistent,
        "systemd": timer_fields,
        "service_systemd": service_fields,
        "effective_timer_ok": timer_effective,
        "effective_service_ok": service_effective,
        "units": units,
        "error": error,
    }


def _last_unattended_attempt() -> dict[str, Any]:
    path = forge_state_root() / "unattended_explore" / "receipts.jsonl"
    if not path.is_file() or path.is_symlink():
        return {
            "present": False,
            "path": str(path),
            "valid_chain": True,
            "attempt": None,
            "admission": None,
        }
    try:
        rows = read_chain(path, schema=RECEIPT_SCHEMA, digest_field="receipt_digest")
    except (OSError, UnattendedError) as exc:
        return {
            "present": True,
            "path": str(path),
            "valid_chain": False,
            "error": f"{type(exc).__name__}:{exc}"[:500],
            "attempt": None,
            "admission": None,
        }
    attempt = rows[-1] if rows else None
    admission = None
    if isinstance(attempt, dict) and attempt.get("kind") == "run_closeout":
        referenced_digest = attempt.get("admission_receipt_digest")
        admission = next(
            (
                row
                for row in reversed(rows[:-1])
                if row.get("receipt_digest") == referenced_digest
                and row.get("kind") == "run_admitted"
            ),
            None,
        )
    return {
        "present": bool(rows),
        "path": str(path),
        "valid_chain": True,
        "receipt_count": len(rows),
        "attempt": attempt,
        "admission": admission,
    }


def _parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text or text.casefold() == "n/a":
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1] + "+00:00").astimezone(timezone.utc)
        return datetime.strptime(text, "%a %Y-%m-%d %H:%M:%S UTC").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _last_attempt_ready(
    projection: dict[str, Any],
    scheduler: dict[str, Any],
    *,
    now: datetime | None = None,
    forge_root: Path | None = None,
) -> tuple[bool, dict[str, Any]]:
    attempt = projection.get("attempt") if isinstance(projection, dict) else None
    attempt = attempt if isinstance(attempt, dict) else {}
    attempt_at = _parse_utc(attempt.get("at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = (current - attempt_at).total_seconds() if attempt_at else None
    last_trigger = _parse_utc((scheduler.get("systemd") or {}).get("LastTriggerUSec"))
    covers_last_trigger = bool(
        attempt_at is not None and (last_trigger is None or attempt_at >= last_trigger)
    )
    run_id = str(attempt.get("run_id") or "")
    artifact_root = (forge_root or forge_state_root()) / "unattended_explore" / "runs"
    run_dir = artifact_root / run_id
    expected_child = artifact_root / run_id / "child_result.json"
    expected_log = artifact_root / run_id / "child.log"
    expected_spec = artifact_root / run_id / "child_spec.json"
    child_path = Path(str(attempt.get("child_result") or ""))
    log_path = Path(str(attempt.get("log") or ""))
    scratch_custody = (
        attempt.get("scratch_custody")
        if isinstance(attempt.get("scratch_custody"), dict)
        else {}
    )
    scratch_create = (
        scratch_custody.get("create")
        if isinstance(scratch_custody.get("create"), dict)
        else {}
    )
    scratch_cleanup = (
        scratch_custody.get("cleanup")
        if isinstance(scratch_custody.get("cleanup"), dict)
        else {}
    )
    state_root = artifact_root.parents[3]
    expected_scratch_root = (
        state_root / ".dharma" / "evolution_worktrees" / "unattended" / run_id
    )
    marker_digest = scratch_create.get("marker_digest")
    admission = (
        projection.get("admission")
        if isinstance(projection.get("admission"), dict)
        else {}
    )
    admission_create = admission.get("scratch_custody_create")
    spec_path = Path(str(admission.get("spec") or ""))
    run_artifact_dir_safe = bool(
        artifact_root.is_dir()
        and not artifact_root.is_symlink()
        and run_dir.is_dir()
        and not run_dir.is_symlink()
    )
    admitted_spec = None
    if (
        run_artifact_dir_safe
        and spec_path == expected_spec
        and not spec_path.is_symlink()
        and spec_path.is_file()
    ):
        admitted_spec = safe_json(spec_path)
    admitted_spec_digest = (
        content_digest(
            {
                key: value
                for key, value in admitted_spec.items()
                if key != "spec_digest"
            }
        )
        if isinstance(admitted_spec, dict)
        else None
    )
    admission_authority_valid = bool(
        run_id
        and admission.get("kind") == "run_admitted"
        and attempt.get("admission_receipt_digest")
        == admission.get("receipt_digest")
        and admission.get("run_id") == run_id
        and admission.get("positive_rsi_claim") is False
        and attempt.get("reservation_digest")
        == admission.get("reservation_digest")
        and admission_create == scratch_create
        and isinstance(admitted_spec, dict)
        and admitted_spec.get("schema") == RUNNER_POLICY.runner_schema
        and admitted_spec.get("run_id") == run_id
        and admitted_spec.get("positive_rsi_claim") is False
        and admitted_spec.get("spec_digest")
        == admitted_spec_digest
        == admission.get("spec_digest")
        and admitted_spec.get("reservation_digest")
        == admission.get("reservation_digest")
        and admitted_spec.get("source_commit") == admission.get("source_commit")
        and admitted_spec.get("state_root") == str(state_root)
        and admitted_spec.get("scratch_root") == str(expected_scratch_root)
        and admitted_spec.get("result_path") == str(expected_child)
        and admitted_spec.get("model_profile_digest")
        == admission.get("model_profile_digest")
        and admitted_spec.get("role_bindings") == admission.get("role_bindings")
        and admitted_spec.get("task_id") == admission.get("task_id")
        and admitted_spec.get("task_context_binding_digest")
        == admission.get("task_context_binding_digest")
        and admitted_spec.get("shape") == admission.get("shape")
        and admitted_spec.get("limits") == admission.get("limits")
    )
    scratch_custody_valid = bool(
        admission_authority_valid
        and attempt.get("scratch_cleanup_ok") is True
        and validate_parent_scratch_proofs(
            scratch_create,
            scratch_cleanup,
            state_root=state_root,
            run_id=run_id,
        )
    )
    child = None
    if (
        run_id
        and child_path == expected_child
        and not child_path.is_symlink()
        and child_path.is_file()
        and scratch_custody_valid
    ):
        child = _validated_child_result(
            child_path,
            run_id=run_id,
            scratch_root=expected_scratch_root,
            scratch_marker_digest=str(marker_digest),
            scratch_root_identity=scratch_create["root_identity"],
        )
    child_artifact_valid = bool(
        child is not None
        and content_digest(child) == attempt.get("child_result_digest")
    )
    attempt_child_binding_valid = bool(
        child_artifact_valid
        and isinstance(child, dict)
        and attempt.get("experiment_id") == child.get("experiment_id")
        and attempt.get("explore_closeout_state") == child.get("closeout_state")
        and type(attempt.get("logical_provider_calls_used")) is int
        and attempt.get("logical_provider_calls_used")
        == child.get("logical_provider_calls_used")
        == RUNNER_POLICY.logical_provider_call_slots
    )
    log_artifact_valid = bool(
        run_id
        and log_path == expected_log
        and not log_path.is_symlink()
        and log_path.is_file()
        and _sha256(log_path) == attempt.get("log_digest")
    )
    terminal_success = bool(
        attempt.get("kind") == "run_closeout"
        and attempt.get("returncode") == 0
        and attempt.get("timed_out") is False
        and attempt.get("halted") is False
        and attempt_child_binding_valid
        and log_artifact_valid
        and attempt.get("explore_closeout_state") in TERMINAL_SUCCESS_STATES
        and attempt.get("epistemic_modality") == "EXPLORE_ONLY"
        and attempt.get("positive_rsi_claim") is False
    )
    fresh = bool(
        age_seconds is not None
        and 0 <= age_seconds <= MAX_LAST_ATTEMPT_AGE_SECONDS
    )
    details = {
        "terminal_success": terminal_success,
        "fresh": fresh,
        "age_seconds": age_seconds,
        "covers_last_systemd_trigger": covers_last_trigger,
        "last_systemd_trigger": last_trigger.isoformat() if last_trigger else None,
        "child_artifact_valid": child_artifact_valid,
        "attempt_child_binding_valid": attempt_child_binding_valid,
        "log_artifact_valid": log_artifact_valid,
        "scratch_custody_valid": scratch_custody_valid,
        "admission_authority_valid": admission_authority_valid,
    }
    return bool(
        projection.get("valid_chain") and terminal_success and fresh and covers_last_trigger
    ), details


def daily_status() -> dict[str, Any]:
    """Compose existing authorities without creating a new state substrate."""

    forge_root = forge_state_root()
    state_root = forge_root.parent.parent
    scheduler = scheduler_status()
    last_unattended = _last_unattended_attempt()
    last_run_ok, last_run_details = _last_attempt_ready(last_unattended, scheduler)
    halt_path = forge_root / "HALT"
    checks = {
        "doctor": doctor(),
        "reconciliation": composite_reconciliation_status(),
        "models": activation_status(),
        "taskpack": taskpack_status(),
        "admission": admission_status(state_root),
        "scheduler": scheduler,
        "last_unattended": {**last_unattended, "readiness": last_run_details},
        "halt": {"absent": not os.path.lexists(halt_path), "path": str(halt_path)},
    }
    ready_for_next_run = bool(
        checks["doctor"].get("ok")
        and checks["reconciliation"].get("ok")
        and checks["models"].get("active")
        and checks["taskpack"].get("ready")
        and checks["admission"].get("ready")
        and checks["scheduler"].get("ready")
        and checks["halt"].get("absent")
    )
    awaiting_first_run = not bool(last_unattended.get("present"))
    last_cycle_healthy = bool(last_run_ok)
    return {
        "schema": STATUS_SCHEMA,
        "ok": bool(ready_for_next_run and last_cycle_healthy),
        "ready_for_next_run": ready_for_next_run,
        "last_cycle_healthy": last_cycle_healthy,
        "awaiting_first_run": awaiting_first_run,
        "read_only": True,
        "checks": checks,
        "claim_boundary": {
            "lane": "bounded_configuration_search",
            "epistemic_modality": "EXPLORE_ONLY",
            "positive_rsi_claim": False,
            "promotion_authority": False,
        },
    }


__all__ = [
    "SCHEDULER_SCHEMA",
    "SERVICE_UNIT",
    "STATUS_SCHEMA",
    "TIMER_UNIT",
    "daily_status",
    "scheduler_status",
]
