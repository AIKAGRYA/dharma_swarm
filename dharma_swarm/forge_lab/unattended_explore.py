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
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.forge_lab.state_io import (
    content_digest,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.unattended_admission import (
    _selected_model_evidence as _selected_model_evidence,
    _validated_state_root,
    admission_status,
)
from dharma_swarm.forge_lab.unattended_chain import (
    _now,
    append_chain,
    host_lock,
    read_chain,
    reserve_budget,
)
from dharma_swarm.forge_lab.unattended_child import (
    _append_receipt,
    _recover_stale_scratch,
    _validated_child_result,
    run_child,
)
from dharma_swarm.forge_lab.unattended_child_support import (
    clone_scratch as _clone_scratch,  # noqa: F401  # re-export seam (tests patch via this module)
    lexists as _lexists,  # noqa: F401  # re-export seam
    run_child_process as _run_child_process,
    run_with_scratch_custody as _run_with_scratch_custody,  # noqa: F401  # re-export seam
)
from dharma_swarm.forge_lab.unattended_context import (
    UnattendedContextError as UnattendedContextError,
)
from dharma_swarm.forge_lab.unattended_policy import (
    CHILDREN,
    CHILD_SCHEMA as CHILD_SCHEMA,
    DEFAULT_TIMEOUT_SECONDS,
    GENERATIONS,
    LEDGER_SCHEMA as LEDGER_SCHEMA,
    LOGICAL_PROVIDER_CALL_SLOTS,
    MAX_EXPERIMENT_TOKENS,
    MAX_TIMEOUT_SECONDS,
    PER_CALL_TOKENS,
    PER_CANDIDATE_TOKENS,
    PER_CANDIDATE_USD,
    PROVIDER_TTL_SECONDS as PROVIDER_TTL_SECONDS,
    RECEIPT_SCHEMA as RECEIPT_SCHEMA,
    RUNNER_POLICY as RUNNER_POLICY,
    RUNNER_SCHEMA,
    RUN_USD_RESERVATION as RUN_USD_RESERVATION,
    TASKS,
    TERMINAL_SUCCESS_STATES as TERMINAL_SUCCESS_STATES,
    BudgetPolicy,
    LogicalCallBudget,
    UnattendedError,
)
from dharma_swarm.forge_lab.unattended_scratch import (
    ScratchCustodyError,
    acquire_run_scratch_lease as acquire_run_scratch_lease,
    cleanup_run_scratch,
    create_run_scratch,
    run_root as unattended_scratch_root,
    validate_parent_scratch_proofs,
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
                        else "EXPLORE_ONLY"
                    )
                ),
                "positive_rsi_claim": False,
                "billing_telemetry": "unavailable_reservation_only",
            },
        )
        successful = bool(
            not timed_out
            and not halted
            and returncode == 0
            and scratch_parent_cleanup_ok
            and child
            and child.get("closeout_state") in TERMINAL_SUCCESS_STATES
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
            "positive_rsi_claim": False,
        }


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
    "reserve_budget",
    "run_child",
    "run_once",
]
