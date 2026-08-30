"""Last-attempt readiness projection for the bounded daily RSI Lab lane.

Split out of ``daily_status`` to keep both modules under the repo's 500-line
budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent module
re-exports every name defined here.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest, forge_state_root, safe_json
from dharma_swarm.forge_lab.unattended_explore import (
    RECEIPT_SCHEMA,
    RUNNER_POLICY,
    TERMINAL_SUCCESS_STATES,
    UnattendedError,
    _validated_child_result,
    read_chain,
)
from dharma_swarm.forge_lab.unattended_scratch import (
    validate_parent_scratch_proofs,
)

MAX_LAST_ATTEMPT_AGE_SECONDS = 36 * 60 * 60
MAX_CONDITION_TRIGGER_SKEW_SECONDS = 5 * 60


def _sha256(path: Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


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
    timer_systemd = (
        scheduler.get("systemd")
        if isinstance(scheduler.get("systemd"), dict)
        else {}
    )
    last_trigger_present = "LastTriggerUSec" in timer_systemd
    last_trigger_text = str(timer_systemd.get("LastTriggerUSec") or "").strip()
    timer_never_triggered = bool(
        last_trigger_present and last_trigger_text.casefold() in {"", "n/a"}
    )
    last_trigger = _parse_utc(last_trigger_text)
    last_trigger_timestamp_valid = bool(
        last_trigger_present
        and (timer_never_triggered or last_trigger is not None)
    )
    covers_last_trigger = bool(
        attempt_at is not None
        and last_trigger_timestamp_valid
        and (last_trigger is None or attempt_at >= last_trigger)
    )
    service_systemd = (
        scheduler.get("service_systemd")
        if isinstance(scheduler.get("service_systemd"), dict)
        else {}
    )
    service_start_present = "ExecMainStartTimestamp" in service_systemd
    service_start_text = str(
        service_systemd.get("ExecMainStartTimestamp") or ""
    ).strip()
    service_never_executed = bool(
        service_start_present and service_start_text.casefold() in {"", "n/a"}
    )
    last_service_execution = _parse_utc(service_start_text)
    service_execution_timestamp_valid = bool(
        service_start_present
        and (service_never_executed or last_service_execution is not None)
    )
    covers_last_service_execution = bool(
        attempt_at is not None
        and service_execution_timestamp_valid
        and (
            last_service_execution is None
            or attempt_at >= last_service_execution
        )
    )
    condition_result = service_systemd.get("ConditionResult")
    condition_timestamp = _parse_utc(service_systemd.get("ConditionTimestamp"))
    condition_trigger_skew_seconds = (
        (condition_timestamp - last_trigger).total_seconds()
        if condition_timestamp is not None and last_trigger is not None
        else None
    )
    newer_trigger_condition_skip_valid = bool(
        attempt_at is not None
        and last_trigger is not None
        and last_trigger > attempt_at
        and condition_result == "no"
        and condition_trigger_skew_seconds is not None
        and 0 <= condition_trigger_skew_seconds <= MAX_CONDITION_TRIGGER_SKEW_SECONDS
    )
    latest_trigger_accounted_for = bool(
        covers_last_trigger or newer_trigger_condition_skip_valid
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
        "last_trigger_timestamp_valid": last_trigger_timestamp_valid,
        "covers_last_service_execution": covers_last_service_execution,
        "last_service_execution": (
            last_service_execution.isoformat() if last_service_execution else None
        ),
        "service_execution_timestamp_valid": service_execution_timestamp_valid,
        "condition_result": condition_result,
        "condition_timestamp": (
            condition_timestamp.isoformat() if condition_timestamp else None
        ),
        "condition_trigger_skew_seconds": condition_trigger_skew_seconds,
        "newer_trigger_condition_skip_valid": newer_trigger_condition_skip_valid,
        "latest_trigger_accounted_for": latest_trigger_accounted_for,
        "child_artifact_valid": child_artifact_valid,
        "attempt_child_binding_valid": attempt_child_binding_valid,
        "log_artifact_valid": log_artifact_valid,
        "scratch_custody_valid": scratch_custody_valid,
        "admission_authority_valid": admission_authority_valid,
    }
    return bool(
        projection.get("valid_chain")
        and terminal_success
        and fresh
        and covers_last_service_execution
        and latest_trigger_accounted_for
    ), details
