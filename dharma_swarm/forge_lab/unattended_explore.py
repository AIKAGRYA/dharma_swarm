"""Fail-closed, tightly bounded unattended Forge Lab EXPLORE runner.

This module is deliberately narrower than :mod:`dharma_swarm.forge_lab.cli`.
It admits exactly one generation, one child, and one task after proving a clean
immutable release, an anchored state root, a fresh two-provider receipt, and a
reachable hardened Docker grader.  It never emits a positive RSI claim.

The parent process owns admission, the host lock, UTC day/month reservations,
an external child timeout, and append-only hash chains.  The child owns the
single EXPLORE run.  A crash leaves the reservation consumed, which is the
conservative failure mode for spend governance.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import stat
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from dharma_swarm.forge_lab.operator_views import doctor
from dharma_swarm.forge_lab.model_onboarding import activation_status
from dharma_swarm.forge_lab.provider_selftest import validate_provider_receipt
from dharma_swarm.forge_lab.reconciliation_view import (
    composite_reconciliation_status as reconciliation_status,
)
from dharma_swarm.forge_lab.source_guard import require_execution_source
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    safe_json,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.unattended_call_shape import (
    EXPECTED_PROVIDER_CALLS,
    CallShapeError,
    build_bounded_child_seams,
    execution_shape_matches,
    validate_child_spec,
    validated_child_result,
)
from dharma_swarm.forge_lab.unattended_accounting import (
    reconcile_budget,
    reconcile_run_budget,
    unavailable_usage_accounting,
)
from dharma_swarm.forge_lab.unattended_child_support import (
    child_scratch_identity as _child_scratch_identity,
    child_scratch_marker_digest as _child_scratch_marker_digest,
    clone_scratch as _clone_scratch,
    lexists as _lexists,
    redact_secret_values as _redact_secret_values,
    remove_clone_scratch as _remove_clone_scratch,
    run_child_process as _run_child_process,
    run_with_scratch_custody as _run_with_scratch_custody,
)
from dharma_swarm.forge_lab.unattended_ledger import (
    BudgetCeilings,
    LedgerError,
    append_chain as _ledger_append_chain,
    chain_digest as _ledger_chain_digest,
    read_chain as _ledger_read_chain,
    reserve_budget as _ledger_reserve_budget,
)
from dharma_swarm.forge_lab.unattended_context import (
    UnattendedContextError,
    load_admitted_task_context,
    sanitize_unattended_docker_env,
)
from dharma_swarm.forge_lab.unattended_model_evidence import (
    ModelEvidenceError,
    selected_model_evidence,
)
from dharma_swarm.forge_lab.unattended_policy import (
    CHILDREN,
    CHILD_SCHEMA,
    DAILY_CALL_CAP,
    DAILY_USD_CAP,
    DEFAULT_TIMEOUT_SECONDS,
    GENERATIONS,
    LEDGER_SCHEMA,
    LOGICAL_PROVIDER_CALL_SLOTS,
    MAX_EXPERIMENT_TOKENS,
    MAX_TIMEOUT_SECONDS,
    MODEL_ROLES,
    MONTHLY_CALL_CAP,
    MONTHLY_USD_CAP,
    PER_CALL_TOKENS,
    PER_CANDIDATE_TOKENS,
    PER_CANDIDATE_USD,
    PROVIDER_TTL_SECONDS,
    RECEIPT_SCHEMA,
    RUNNER_POLICY,
    RUNNER_SCHEMA,
    RUN_USD_RESERVATION,
    TASKS,
    TERMINAL_SUCCESS_STATES,
    BudgetPolicy,
    LogicalCallBudget,
    UnattendedError,
)
from dharma_swarm.forge_lab.unattended_recovery import recover_stale_scratch
from dharma_swarm.forge_lab.unattended_scratch import (
    ScratchCustodyError,
    acquire_run_scratch_lease,
    cleanup_run_scratch,
    create_run_scratch,
    run_root as unattended_scratch_root,
    validate_parent_scratch_proofs,
)

def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _chain_digest(payload: dict[str, Any], digest_field: str) -> str:
    return _ledger_chain_digest(payload, digest_field)


def read_chain(
    path: Path,
    *,
    schema: str,
    digest_field: str,
) -> list[dict[str, Any]]:
    try:
        return _ledger_read_chain(path, schema=schema, digest_field=digest_field)
    except LedgerError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


def append_chain(
    path: Path,
    payload: dict[str, Any],
    *,
    schema: str,
    digest_field: str,
) -> dict[str, Any]:
    try:
        return _ledger_append_chain(
            path,
            payload,
            schema=schema,
            digest_field=digest_field,
        )
    except LedgerError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


def reserve_budget(
    ledger_path: Path,
    *,
    run_id: str,
    at: str,
    policy: BudgetPolicy = BudgetPolicy(),
) -> dict[str, Any]:
    """Reserve the full run ceiling against UTC daily and monthly caps."""
    try:
        return _ledger_reserve_budget(
            ledger_path,
            run_id=run_id,
            at=at,
            policy=policy,
            ceilings=BudgetCeilings(
                run_usd=RUN_USD_RESERVATION,
                run_calls=LOGICAL_PROVIDER_CALL_SLOTS,
                daily_usd=DAILY_USD_CAP,
                monthly_usd=MONTHLY_USD_CAP,
                daily_calls=DAILY_CALL_CAP,
                monthly_calls=MONTHLY_CALL_CAP,
            ),
            ledger_schema=LEDGER_SCHEMA,
        )
    except LedgerError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


@contextmanager
def host_lock(path: Path) -> Iterator[None]:
    """Acquire the one nonblocking host runner lock without following symlinks."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise UnattendedError("LOCK_PATH_UNSAFE", str(exc)) from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UnattendedError("LOCK_HELD", "another unattended run owns the host lock") from exc
        yield
    finally:
        os.close(descriptor)


def _selected_model_evidence(provider_check: dict[str, Any]) -> dict[str, Any]:
    """Bind active role assignments to one fresh, exact provider receipt."""

    try:
        return selected_model_evidence(
            provider_check,
            model_roles=MODEL_ROLES,
            activation_status_fn=activation_status,
            validate_provider_receipt_fn=validate_provider_receipt,
            safe_json_fn=safe_json,
        )
    except ModelEvidenceError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


def _validated_state_root(value: Path) -> Path:
    raw = value.expanduser()
    if not raw.is_absolute() or raw == Path("/"):
        raise UnattendedError(
            "STATE_ROOT_UNSAFE", "state root must be a non-root absolute path"
        )
    for label, path in (
        ("state_root", raw),
        ("dharma_home", raw / ".dharma"),
        ("forge_root", raw / ".dharma" / "forge_lab"),
    ):
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            if label == "state_root":
                raise UnattendedError("STATE_ROOT_UNSAFE", f"state root is missing: {raw}")
            continue
        except OSError as exc:
            raise UnattendedError("STATE_ROOT_UNSAFE", f"cannot inspect {path}") from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise UnattendedError(
                "STATE_ROOT_UNSAFE",
                f"{label} must be an owner-controlled real directory: {path}",
            )
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise UnattendedError("STATE_ROOT_UNSAFE", f"cannot resolve {raw}") from exc
    if resolved != raw:
        raise UnattendedError("STATE_ROOT_UNSAFE", f"state root is not canonical: {raw}")
    forge_root = (resolved / ".dharma" / "forge_lab").resolve(strict=False)
    if forge_root != resolved and not forge_root.is_relative_to(resolved):
        raise UnattendedError("STATE_ROOT_UNSAFE", "forge root escaped state root")
    return resolved


def admission_status(state_root: Path) -> dict[str, Any]:
    """Evaluate all pre-spend gates and return selected redacted route IDs."""

    reasons: list[str] = []
    try:
        state_root = _validated_state_root(state_root)
    except UnattendedError as exc:
        return {
            "ready": False,
            "reasons": [f"{exc.code}:{exc}"],
            "halt_path": None,
            "source": {},
            "doctor": {},
            "reconciliation": {},
            "routes": [],
            "role_bindings": {},
            "model_profile_digest": None,
            "provider_receipt_digest": None,
            "task_id": None,
            "task_context_binding": None,
        }
    sanitize_unattended_docker_env()
    halt = state_root / ".dharma" / "forge_lab" / "HALT"
    if _lexists(halt):
        reasons.append(f"HALT_present:{halt}")
    if os.environ.get("RSI_LAB_DEV_SOURCE") == "1":
        reasons.append("development_source_forbidden")
    configured_state = os.environ.get("RSI_LAB_STATE", "").strip()
    try:
        configured_state_root = (
            Path(configured_state).expanduser().resolve(strict=True)
            if configured_state
            else None
        )
    except OSError:
        configured_state_root = None
    if configured_state_root != state_root:
        reasons.append("explicit_state_root_not_anchored")
    try:
        source = require_execution_source()
    except RuntimeError as exc:
        source = {"ready": False, "reasons": [str(exc)]}
        reasons.append("immutable_source_gate_failed")
    try:
        report = doctor()
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}:{exc}"[:500]}
        reasons.append("doctor_unavailable")
    if not report.get("ok"):
        reasons.append("doctor_not_ready")
    try:
        reconciliation = reconciliation_status()
    except Exception as exc:
        reconciliation = {
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}"[:500],
        }
        reasons.append("reconciliation_unavailable")
    if not reconciliation.get("ok"):
        reasons.append("control_plane_reconciliation_required")
    provider_check = ((report.get("checks") or {}).get("providers") or {})
    if int(provider_check.get("ttl_seconds") or 0) > PROVIDER_TTL_SECONDS:
        reasons.append("provider_ttl_policy_too_weak")
    try:
        model_evidence = (
            _selected_model_evidence(provider_check) if provider_check.get("ready") else {}
        )
    except UnattendedError as exc:
        reasons.append(f"{exc.code}:{exc}")
        model_evidence = {}
    routes = model_evidence.get("routes") or []
    role_bindings = model_evidence.get("role_bindings") or {}
    grader = ((report.get("checks") or {}).get("grader") or {})
    if not grader.get("ready") or not grader.get("docker_daemon_reachable"):
        reasons.append("isolated_docker_grader_not_ready")
    taskbed = ((report.get("checks") or {}).get("taskbed") or {})
    task_id = str(taskbed.get("next_explore_task_id") or "").strip()
    if not taskbed.get("ready") or not task_id:
        reasons.append("state_anchored_isolated_task_unavailable")
    task_context_binding: dict[str, Any] | None = None
    if task_id:
        try:
            _task, _context, task_context_binding = load_admitted_task_context(
                task_id,
                state_root=state_root,
            )
        except UnattendedContextError as exc:
            reasons.append(f"{exc.code}:{exc}")
    return {
        "ready": not reasons and set(role_bindings) == set(MODEL_ROLES) and len(routes) >= 2,
        "reasons": reasons,
        "halt_path": str(halt),
        "source": source,
        "doctor": report,
        "reconciliation": reconciliation,
        "routes": routes,
        "role_bindings": role_bindings,
        "model_profile_digest": model_evidence.get("model_profile_digest"),
        "provider_receipt_digest": model_evidence.get("provider_receipt_digest"),
        "task_id": task_id or None,
        "task_context_binding": task_context_binding,
    }


def _append_receipt(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return append_chain(
        root / "receipts.jsonl",
        payload,
        schema=RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )


def _validated_child_result(
    path: Path,
    *,
    run_id: str,
    scratch_root: Path,
    scratch_marker_digest: str,
    scratch_root_identity: dict[str, int],
) -> dict[str, Any] | None:
    return validated_child_result(
        path,
        run_id=run_id,
        scratch_root=scratch_root,
        scratch_marker_digest=scratch_marker_digest,
        scratch_root_identity=scratch_root_identity,
        terminal_success_states=frozenset(TERMINAL_SUCCESS_STATES),
        policy=RUNNER_POLICY,
        safe_json_fn=safe_json,
        chain_digest_fn=_chain_digest,
    )


def _validate_child_spec(
    spec: dict[str, Any],
    spec_path: Path,
    *,
    admission: dict[str, Any],
) -> None:
    try:
        validate_child_spec(
            spec,
            spec_path,
            admission=admission,
            policy=RUNNER_POLICY,
            read_chain_fn=read_chain,
        )
    except CallShapeError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


def _recover_stale_scratch(
    state_root: Path,
    control_root: Path,
) -> list[dict[str, Any]]:
    return recover_stale_scratch(
        state_root,
        control_root,
        read_chain_fn=read_chain,
        append_receipt_fn=_append_receipt,
        now_fn=_now,
    )


def run_once(state_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Admit and execute one bounded run.  No retry occurs inside this function."""

    state_root = _validated_state_root(state_root)
    timeout_seconds = int(timeout_seconds)
    if timeout_seconds < 60 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise UnattendedError("TIMEOUT_POLICY", f"timeout must be 60..{MAX_TIMEOUT_SECONDS} seconds")
    control_root = state_root / ".dharma" / "forge_lab" / "unattended_explore"
    run_id = "unattended-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
    at = _now()
    with host_lock(control_root / "runner.lock"):
        _recover_stale_scratch(state_root, control_root)
        admission = admission_status(state_root)
        if not admission["ready"]:
            receipt = _append_receipt(
                control_root,
                {
                    "kind": "admission_refusal",
                    "at": at,
                    "run_id": run_id,
                    "reasons": admission["reasons"],
                    "provider_calls": 0,
                    "usd_reserved": 0.0,
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError("ADMISSION_REFUSED", str(receipt["receipt_digest"]))

        reservation = reserve_budget(
            control_root / "budget_ledger.jsonl",
            run_id=run_id,
            at=at,
        )
        source = admission["source"]
        routes = admission["routes"]
        role_bindings = admission["role_bindings"]
        run_dir = control_root / "runs" / run_id
        result_path = run_dir / "child_result.json"
        spec_path = run_dir / "child_spec.json"
        log_path = run_dir / "child.log"
        scratch_root = unattended_scratch_root(state_root, run_id)
        spec = {
            "schema": RUNNER_SCHEMA,
            "run_id": run_id,
            "created_at": at,
            "source_repo": source["repo"],
            "source_commit": source["commit"],
            "state_root": str(state_root),
            "archive_root": str(state_root / ".dharma" / "evolution_archive"),
            "scratch_root": str(scratch_root),
            "result_path": str(result_path),
            "routes": routes,
            "role_bindings": role_bindings,
            "model_profile_digest": admission["model_profile_digest"],
            "provider_receipt_digest": admission["provider_receipt_digest"],
            "task_id": admission["task_id"],
            "task_context_binding_digest": admission["task_context_binding"][
                "binding_digest"
            ],
            "shape": {"generations": GENERATIONS, "children": CHILDREN, "tasks": TASKS},
            "limits": {
                "logical_provider_call_slots": LOGICAL_PROVIDER_CALL_SLOTS,
                "per_call_tokens": PER_CALL_TOKENS,
                "per_candidate_tokens": PER_CANDIDATE_TOKENS,
                "per_candidate_usd": PER_CANDIDATE_USD,
                "max_experiment_tokens": MAX_EXPERIMENT_TOKENS,
                "external_timeout_seconds": timeout_seconds,
            },
            "reservation_digest": reservation["ledger_digest"],
            "positive_rsi_claim": False,
        }
        spec["spec_digest"] = content_digest(spec)
        write_json_exclusive(spec_path, spec)
        try:
            scratch_create = create_run_scratch(
                state_root,
                run_id,
                source_commit=source["commit"],
                spec_digest=spec["spec_digest"],
                created_at=at,
            )
        except ScratchCustodyError as exc:
            failed = _append_receipt(
                control_root,
                {
                    "kind": "run_launch_failed",
                    "at": _now(),
                    "run_id": run_id,
                    "admission_receipt_digest": None,
                    "reservation_digest": reservation["ledger_digest"],
                    "error_class": type(exc).__name__,
                    "error_code": exc.code,
                    "scratch_custody": {"create": exc.proof, "cleanup": None},
                    "epistemic_modality": "InconclusiveInfrastructure",
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError(exc.code, str(failed["receipt_digest"])) from exc
        try:
            preflight = _append_receipt(
                control_root,
                {
                    "kind": "run_admitted",
                    "at": at,
                    "run_id": run_id,
                    "source_commit": source["commit"],
                    "provider_families": [route["provider"] for route in routes],
                    "model_profile_digest": spec["model_profile_digest"],
                    "role_bindings": role_bindings,
                    "task_id": spec["task_id"],
                    "task_context_binding_digest": spec[
                        "task_context_binding_digest"
                    ],
                    "shape": spec["shape"],
                    "limits": spec["limits"],
                    "spec": str(spec_path),
                    "spec_digest": spec["spec_digest"],
                    "reservation_digest": reservation["ledger_digest"],
                    "scratch_custody_create": scratch_create,
                    "positive_rsi_claim": False,
                },
            )
        except Exception as exc:
            try:
                cleanup_run_scratch(
                    state_root,
                    run_id,
                    source_commit=source["commit"],
                    spec_digest=spec["spec_digest"],
                    expected_root_identity=scratch_create["root_identity"],
                    expected_marker_digest=str(scratch_create["marker_digest"]),
                )
            except ScratchCustodyError as custody_exc:
                raise UnattendedError(
                    custody_exc.code,
                    str(custody_exc.proof["proof_digest"]),
                ) from exc
            raise UnattendedError(
                "ADMISSION_RECEIPT_FAILED",
                f"{type(exc).__name__}:run admission receipt was not durable",
            ) from exc
        try:
            returncode, timed_out, halted, wall_seconds = _run_child_process(
                spec_path,
                run_id=run_id,
                timeout_seconds=timeout_seconds,
                log_path=log_path,
                halt_path=Path(admission["halt_path"]),
                scratch_root_identity=scratch_create["root_identity"],
                scratch_marker_digest=str(scratch_create["marker_digest"]),
            )
        except Exception as exc:
            try:
                scratch_cleanup = cleanup_run_scratch(
                    state_root,
                    run_id,
                    source_commit=source["commit"],
                    spec_digest=spec["spec_digest"],
                    expected_root_identity=scratch_create["root_identity"],
                    expected_marker_digest=str(scratch_create["marker_digest"]),
                )
                cleanup_error: ScratchCustodyError | None = None
            except ScratchCustodyError as custody_exc:
                scratch_cleanup = custody_exc.proof
                cleanup_error = custody_exc
            failed = _append_receipt(
                control_root,
                {
                    "kind": "run_launch_failed",
                    "at": _now(),
                    "run_id": run_id,
                    "admission_receipt_digest": preflight["receipt_digest"],
                    "reservation_digest": reservation["ledger_digest"],
                    "error_class": type(exc).__name__,
                    "error_code": (
                        cleanup_error.code
                        if cleanup_error is not None
                        else "CHILD_LAUNCH_FAILED"
                    ),
                    "scratch_custody": {
                        "create": scratch_create,
                        "cleanup": scratch_cleanup,
                    },
                    "epistemic_modality": "InconclusiveInfrastructure",
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError(
                (
                    cleanup_error.code
                    if cleanup_error is not None
                    else "CHILD_LAUNCH_FAILED"
                ),
                str(failed["receipt_digest"]),
            ) from exc
        try:
            scratch_cleanup = cleanup_run_scratch(
                state_root,
                run_id,
                source_commit=source["commit"],
                spec_digest=spec["spec_digest"],
                expected_root_identity=scratch_create["root_identity"],
                expected_marker_digest=str(scratch_create["marker_digest"]),
            )
            cleanup_error = None
        except ScratchCustodyError as exc:
            scratch_cleanup = exc.proof
            cleanup_error = exc
        scratch_parent_cleanup_ok = bool(
            cleanup_error is None
            and validate_parent_scratch_proofs(
                scratch_create,
                scratch_cleanup,
                state_root=state_root,
                run_id=run_id,
            )
        )
        child = (
            _validated_child_result(
                result_path,
                run_id=run_id,
                scratch_root=scratch_root,
                scratch_marker_digest=str(scratch_create["marker_digest"]),
                scratch_root_identity=scratch_create["root_identity"],
            )
            if scratch_parent_cleanup_ok
            else None
        )
        log_digest = "sha256:" + hashlib.sha256(log_path.read_bytes()).hexdigest()
        accounting = reconcile_run_budget(
            control_root / "budget_ledger.jsonl",
            run_id=run_id,
            at=_now(),
            child=child,
            log_digest=log_digest,
        )
        budget_reconciliation = accounting.row
        closeout = _append_receipt(
            control_root,
            {
                "kind": "run_closeout",
                "at": _now(),
                "run_id": run_id,
                "admission_receipt_digest": preflight["receipt_digest"],
                "reservation_digest": reservation["ledger_digest"],
                "returncode": returncode,
                "timed_out": timed_out,
                "halted": halted,
                "wall_seconds": wall_seconds,
                "child_result": str(result_path) if child else None,
                "child_result_digest": content_digest(child) if child else None,
                "experiment_id": (child or {}).get("experiment_id"),
                "explore_closeout_state": (child or {}).get("closeout_state"),
                "logical_provider_calls_used": (child or {}).get("logical_provider_calls_used"),
                "budget_reconciliation_digest": budget_reconciliation.get(
                    "ledger_digest"
                ),
                "actual_cost_usd": budget_reconciliation.get("actual_cost_usd"),
                "cost_completeness": budget_reconciliation.get(
                    "cost_completeness"
                ),
                "budget_reconciliation_decision": budget_reconciliation.get(
                    "decision"
                ),
                "budget_error_code": accounting.error_code,
                "scratch_custody": {
                    "create": scratch_create,
                    "cleanup": scratch_cleanup,
                },
                "scratch_cleanup_ok": scratch_parent_cleanup_ok,
                "log": str(log_path),
                "log_digest": log_digest,
                "epistemic_modality": (
                    "InconclusiveOperatorHalt"
                    if halted
                    else (
                        "InconclusiveInfrastructure"
                        if (
                            timed_out
                            or returncode != 0
                            or not scratch_parent_cleanup_ok
                            or child is None
                        )
                        else (
                            "InconclusiveBudget"
                            if accounting.error_code is not None
                            else "EXPLORE_ONLY"
                        )
                    )
                ),
                "positive_rsi_claim": False,
                "billing_telemetry": (
                    budget_reconciliation.get("cost_completeness")
                    or "ambiguous"
                ),
            },
        )
        successful = bool(
            not timed_out
            and not halted
            and returncode == 0
            and scratch_parent_cleanup_ok
            and child
            and child.get("closeout_state") in TERMINAL_SUCCESS_STATES
            and accounting.error_code is None
            and budget_reconciliation.get("decision") == "accepted"
        )
        return {
            "schema": RUNNER_SCHEMA,
            "ok": successful,
            "run_id": run_id,
            "receipt_digest": closeout["receipt_digest"],
            "closeout_state": (child or {}).get("closeout_state"),
            "timed_out": timed_out,
            "halted": halted,
            "returncode": returncode,
            "scratch_cleanup_ok": scratch_parent_cleanup_ok,
            "budget_reconciliation_digest": budget_reconciliation.get(
                "ledger_digest"
            ),
            "actual_cost_usd": budget_reconciliation.get("actual_cost_usd"),
            "cost_completeness": budget_reconciliation.get("cost_completeness"),
            "budget_error_code": accounting.error_code,
            "positive_rsi_claim": False,
        }


def _bounded_child_seams(spec: dict[str, Any], counter: LogicalCallBudget):
    """Build seams with exactly one provider dispatch per logical slot."""

    return build_bounded_child_seams(
        spec,
        counter,
        per_call_tokens=PER_CALL_TOKENS,
        error_factory=UnattendedError,
        clone_scratch=_clone_scratch,
        remove_clone_scratch=_remove_clone_scratch,
    )


def _execute_child_experiment(
    spec: dict[str, Any],
    *,
    run_id: str,
    scratch_attestation: dict[str, Any],
) -> int:
    """Execute one already-attested child while its scratch lease is held."""

    from dharma_swarm.forge_lab.experiment import ExperimentConfig, run_experiment

    os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"] = spec["scratch_root"]
    counter = LogicalCallBudget()
    role_bindings = spec["role_bindings"]
    cfg = ExperimentConfig(
        generations=GENERATIONS,
        children=CHILDREN,
        tasks_per_generation=TASKS,
        solver_model=role_bindings["solver"]["model_id"],
        verifier_model=role_bindings["verifier"]["model_id"],
        mutator_model=role_bindings["mutator"]["model_id"],
        seed_genome={
            "arm_kind": "freeform_single",
            "generator_model": role_bindings["solver"]["model_id"],
            "verifier_model": role_bindings["verifier"]["model_id"],
            "per_call_tokens": PER_CALL_TOKENS,
            "window_chars": 24_000,
            "extra_instruction": "bounded unattended EXPLORE control",
            "notes": "bounded_unattended_seed",
        },
        budget_cap_tokens=PER_CANDIDATE_TOKENS,
        budget_cap_usd=PER_CANDIDATE_USD,
        soft_token_cap=False,
        max_experiment_tokens=MAX_EXPERIMENT_TOKENS,
        propose_timeout_s=240,
        grade_timeout_s=600,
        rng_seed=20260825,
        source_repo=Path(spec["source_repo"]),
        state_root=Path(spec["archive_root"]),
        keep_worktree=False,
        force_single_llm_mutation=True,
    )
    closeout = _run_with_scratch_custody(
        _bounded_child_seams(spec, counter),
        lambda seams: asyncio.run(run_experiment(cfg, seams=seams)),
    )
    closeout = _redact_secret_values(closeout)
    stats = closeout.get("stats") if isinstance(closeout.get("stats"), dict) else {}
    counters = stats.get("counters") if isinstance(stats.get("counters"), dict) else {}
    scratch = (
        closeout.get("scratch_worktree")
        if isinstance(closeout.get("scratch_worktree"), dict)
        else {}
    )
    scratch_cleanup_ok = bool(
        scratch.get("state") == "removed" and scratch.get("removed") is True
    )
    execution_shape_ok = scratch_cleanup_ok and execution_shape_matches(
        counter,
        counters,
        slots=LOGICAL_PROVIDER_CALL_SLOTS,
    )
    effective_state = (
        closeout.get("closeout_state")
        if execution_shape_ok
        else "inconclusive_generation"
    )
    result = {
        "schema": CHILD_SCHEMA,
        "run_id": run_id,
        "experiment_id": closeout.get("experiment_id"),
        "closeout_state": effective_state,
        "logical_provider_calls_used": counter.used,
        "logical_provider_call_limit": counter.limit,
        "logical_provider_calls_by_role": counter.by_label,
        "expected_provider_calls_by_role": EXPECTED_PROVIDER_CALLS,
        "execution_shape_ok": execution_shape_ok,
        "scratch_cleanup_ok": scratch_cleanup_ok,
        "scratch_custody_attestation": scratch_attestation,
        "experiment_closeout": closeout,
        "usage_accounting": unavailable_usage_accounting(
            counter.used,
            logical_calls_complete=execution_shape_ok,
        ),
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
        "billing_telemetry": "unavailable",
    }
    result["result_digest"] = content_digest(result)
    write_json_exclusive(Path(spec["result_path"]), result)
    return 0 if effective_state in TERMINAL_SUCCESS_STATES else 1


def run_child(spec_path: Path) -> int:
    """Execute the admitted child spec and persist one exclusive result."""

    spec = safe_json(spec_path)
    if spec is None or spec.get("schema") != RUNNER_SCHEMA:
        raise UnattendedError("CHILD_SPEC_INVALID", str(spec_path))
    expected_digest = spec.get("spec_digest")
    actual_digest = content_digest({key: value for key, value in spec.items() if key != "spec_digest"})
    if expected_digest != actual_digest:
        raise UnattendedError("CHILD_SPEC_DIGEST", "child spec digest mismatch")
    run_id = str(spec.get("run_id") or "")
    if os.environ.get("RSI_LAB_UNATTENDED_CHILD_RUN_ID") != run_id:
        raise UnattendedError("CHILD_CUSTODY", "child run id environment mismatch")
    state_root = Path(spec["state_root"]).resolve()
    admission = admission_status(state_root)
    if not admission["ready"]:
        raise UnattendedError("CHILD_ADMISSION_REFUSED", ",".join(admission["reasons"]))
    if admission["source"].get("commit") != spec.get("source_commit"):
        raise UnattendedError("SOURCE_CHANGED", "source commit changed after parent admission")
    if admission["routes"] != spec.get("routes"):
        raise UnattendedError("PROVIDER_RECEIPT_CHANGED", "provider routes changed after admission")
    if admission["role_bindings"] != spec.get("role_bindings"):
        raise UnattendedError("MODEL_PROFILE_CHANGED", "model roles changed after admission")
    if admission["model_profile_digest"] != spec.get("model_profile_digest"):
        raise UnattendedError("MODEL_PROFILE_CHANGED", "model profile changed after admission")
    if admission["provider_receipt_digest"] != spec.get("provider_receipt_digest"):
        raise UnattendedError("PROVIDER_RECEIPT_CHANGED", "provider receipt changed after admission")
    _validate_child_spec(spec, spec_path, admission=admission)
    root_identity = _child_scratch_identity()
    marker_digest = _child_scratch_marker_digest()
    try:
        scratch_lease = acquire_run_scratch_lease(
            state_root,
            run_id,
            source_commit=str(spec["source_commit"]),
            spec_digest=str(spec["spec_digest"]),
            expected_root_identity=root_identity,
            expected_marker_digest=marker_digest,
        )
    except ScratchCustodyError as exc:
        raise UnattendedError(exc.code, str(exc.proof["proof_digest"])) from exc
    try:
        return _execute_child_experiment(
            spec,
            run_id=run_id,
            scratch_attestation=scratch_lease.proof,
        )
    finally:
        scratch_lease.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rsi-unattended-explore")
    parser.add_argument("--state-root", type=Path, help="explicit host-owned RSI state root")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--child-spec", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    args = build_parser().parse_args(argv)
    try:
        if args.child_spec is not None:
            return run_child(args.child_spec)
        if args.state_root is None:
            raise UnattendedError("STATE_ROOT_REQUIRED", "--state-root is required")
        result = run_once(args.state_root, timeout_seconds=args.timeout_seconds)
    except UnattendedError as exc:
        print(
            json.dumps(
                {
                    "schema": RUNNER_SCHEMA,
                    "ok": False,
                    "error": {"code": exc.code, "message": str(exc)},
                    "positive_rsi_claim": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 9
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 9


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BudgetPolicy",
    "LogicalCallBudget",
    "UnattendedError",
    "admission_status",
    "append_chain",
    "read_chain",
    "reconcile_budget",
    "reserve_budget",
    "run_child",
    "run_once",
]
