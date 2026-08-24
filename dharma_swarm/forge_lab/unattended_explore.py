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
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from dharma_swarm.forge_lab.operator_views import doctor
from dharma_swarm.forge_lab.provider_selftest import validate_provider_receipt
from dharma_swarm.forge_lab.source_guard import require_execution_source
from dharma_swarm.forge_lab.state_io import (
    canonical_json,
    content_digest,
    safe_json,
    write_json_exclusive,
)

RUNNER_SCHEMA = "rsi_lab.unattended_explore.v1"
LEDGER_SCHEMA = "rsi_lab.unattended_budget_ledger.v1"
RECEIPT_SCHEMA = "rsi_lab.unattended_receipt_chain.v1"
CHILD_SCHEMA = "rsi_lab.unattended_child_result.v1"

# Fixed live shape and hard policy maxima.  Dollar reservations are accounting
# ceilings, not vendor billing telemetry; that distinction is repeated in every
# ledger entry and closeout.
GENERATIONS = 1
CHILDREN = 1
TASKS = 1
LOGICAL_PROVIDER_CALL_SLOTS = 4
PER_CALL_TOKENS = 8_000
PER_CANDIDATE_TOKENS = 8_000
PER_CANDIDATE_USD = 0.25
MAX_EXPERIMENT_TOKENS = 24_000
RUN_USD_RESERVATION = PER_CANDIDATE_USD * LOGICAL_PROVIDER_CALL_SLOTS
DAILY_USD_CAP = 3.0
MONTHLY_USD_CAP = 30.0
DAILY_CALL_CAP = 12
MONTHLY_CALL_CAP = 120
DEFAULT_TIMEOUT_SECONDS = 2_700
MAX_TIMEOUT_SECONDS = 3_000
PROVIDER_TTL_SECONDS = 3_600

TERMINAL_SUCCESS_STATES = {"inconclusive_low_power", "measured_negative"}


class UnattendedError(RuntimeError):
    """Typed fail-closed runner refusal."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BudgetPolicy:
    run_usd: float = RUN_USD_RESERVATION
    run_calls: int = LOGICAL_PROVIDER_CALL_SLOTS
    daily_usd: float = DAILY_USD_CAP
    monthly_usd: float = MONTHLY_USD_CAP
    daily_calls: int = DAILY_CALL_CAP
    monthly_calls: int = MONTHLY_CALL_CAP


@dataclass
class LogicalCallBudget:
    """Count admitted logical provider invocations before dispatch."""

    limit: int = LOGICAL_PROVIDER_CALL_SLOTS
    used: int = 0

    def consume(self, label: str) -> None:
        if self.used >= self.limit:
            raise UnattendedError(
                "LOGICAL_PROVIDER_CALL_CAP",
                f"provider call slot refused before {label}: {self.used}/{self.limit}",
            )
        self.used += 1


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _utc_periods(at: str) -> tuple[str, str]:
    try:
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UnattendedError("LEDGER_TIME_INVALID", f"invalid UTC time: {at}") from exc
    if instant.tzinfo is None:
        raise UnattendedError("LEDGER_TIME_INVALID", "ledger time must carry a UTC offset")
    instant = instant.astimezone(timezone.utc)
    return instant.strftime("%Y-%m-%d"), instant.strftime("%Y-%m")


def _chain_digest(payload: dict[str, Any], digest_field: str) -> str:
    return content_digest({key: value for key, value in payload.items() if key != digest_field})


def read_chain(
    path: Path,
    *,
    schema: str,
    digest_field: str,
) -> list[dict[str, Any]]:
    """Read and verify one strict newline-terminated JSONL hash chain."""

    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise UnattendedError("CHAIN_PATH_UNSAFE", f"unsafe chain path: {path}")
    if path.stat().st_mode & 0o077:
        raise UnattendedError("CHAIN_MODE_UNSAFE", f"chain must be owner-only: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise UnattendedError("CHAIN_UNREADABLE", f"cannot read {path}: {exc}") from exc
    if len(raw) > 16 * 1024 * 1024:
        raise UnattendedError("CHAIN_TOO_LARGE", f"chain exceeds 16 MiB: {path}")
    if raw and not raw.endswith(b"\n"):
        raise UnattendedError("CHAIN_TRUNCATED", f"chain lacks final newline: {path}")
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    for index, line in enumerate(raw.splitlines(), start=1):
        try:
            row = json.loads(line)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise UnattendedError(
                "CHAIN_MALFORMED", f"invalid JSON at {path}:{index}"
            ) from exc
        if not isinstance(row, dict):
            raise UnattendedError("CHAIN_MALFORMED", f"non-object at {path}:{index}")
        if row.get("schema") != schema or row.get("sequence") != index:
            raise UnattendedError("CHAIN_SEQUENCE", f"schema/sequence mismatch at {path}:{index}")
        if row.get("previous_digest") != previous:
            raise UnattendedError("CHAIN_PREVIOUS", f"previous digest mismatch at {path}:{index}")
        if row.get(digest_field) != _chain_digest(row, digest_field):
            raise UnattendedError("CHAIN_DIGEST", f"digest mismatch at {path}:{index}")
        previous = str(row[digest_field])
        rows.append(row)
    return rows


def append_chain(
    path: Path,
    payload: dict[str, Any],
    *,
    schema: str,
    digest_field: str,
) -> dict[str, Any]:
    """Verify then append one fsync-backed chain row while the host lock is held."""

    rows = read_chain(path, schema=schema, digest_field=digest_field)
    row = {
        **payload,
        "schema": schema,
        "sequence": len(rows) + 1,
        "previous_digest": rows[-1][digest_field] if rows else None,
    }
    row[digest_field] = _chain_digest(row, digest_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "ab", closefd=True) as handle:
        handle.write(canonical_json(row) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return row


def reserve_budget(
    ledger_path: Path,
    *,
    run_id: str,
    at: str,
    policy: BudgetPolicy = BudgetPolicy(),
) -> dict[str, Any]:
    """Reserve the full run ceiling against UTC daily and monthly caps."""

    rows = read_chain(
        ledger_path,
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )
    if not (
        0 < policy.run_usd <= RUN_USD_RESERVATION
        and 0 < policy.run_calls <= LOGICAL_PROVIDER_CALL_SLOTS
        and 0 < policy.daily_usd <= DAILY_USD_CAP
        and 0 < policy.monthly_usd <= MONTHLY_USD_CAP
        and 0 < policy.daily_calls <= DAILY_CALL_CAP
        and 0 < policy.monthly_calls <= MONTHLY_CALL_CAP
    ):
        raise UnattendedError("BUDGET_POLICY_INVALID", "policy exceeds hard-coded maxima")
    if any(row.get("run_id") == run_id for row in rows):
        raise UnattendedError("BUDGET_DUPLICATE_RUN", f"reservation already exists: {run_id}")
    for row in rows:
        try:
            row_usd = float(row.get("reserved_usd"))
            row_calls = int(row.get("reserved_logical_calls"))
        except (TypeError, ValueError) as exc:
            raise UnattendedError("BUDGET_LEDGER_SEMANTICS", "invalid reservation row") from exc
        if (
            row.get("kind") != "reservation"
            or row_usd < 0
            or row_usd > RUN_USD_RESERVATION
            or row_calls < 0
            or row_calls > LOGICAL_PROVIDER_CALL_SLOTS
        ):
            raise UnattendedError("BUDGET_LEDGER_SEMANTICS", "reservation row outside policy")
    day, month = _utc_periods(at)
    daily = [row for row in rows if row.get("day") == day]
    monthly = [row for row in rows if row.get("month") == month]
    daily_usd = sum(float(row.get("reserved_usd") or 0.0) for row in daily)
    monthly_usd = sum(float(row.get("reserved_usd") or 0.0) for row in monthly)
    daily_calls = sum(int(row.get("reserved_logical_calls") or 0) for row in daily)
    monthly_calls = sum(int(row.get("reserved_logical_calls") or 0) for row in monthly)
    refusals: list[str] = []
    if daily_usd + policy.run_usd > policy.daily_usd + 1e-9:
        refusals.append("daily_usd_reservation_cap")
    if monthly_usd + policy.run_usd > policy.monthly_usd + 1e-9:
        refusals.append("monthly_usd_reservation_cap")
    if daily_calls + policy.run_calls > policy.daily_calls:
        refusals.append("daily_logical_call_cap")
    if monthly_calls + policy.run_calls > policy.monthly_calls:
        refusals.append("monthly_logical_call_cap")
    if refusals:
        raise UnattendedError("BUDGET_CAP", ",".join(refusals))
    return append_chain(
        ledger_path,
        {
            "kind": "reservation",
            "at": at,
            "run_id": run_id,
            "day": day,
            "month": month,
            "reserved_usd": policy.run_usd,
            "reserved_logical_calls": policy.run_calls,
            "caps": {
                "daily_usd": policy.daily_usd,
                "monthly_usd": policy.monthly_usd,
                "daily_logical_calls": policy.daily_calls,
                "monthly_logical_calls": policy.monthly_calls,
            },
            "accounting_semantics": (
                "conservative reservation ceiling; provider billing telemetry unavailable; "
                "transport-level retries are not independently metered"
            ),
        },
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )


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


def _selected_routes(provider_check: dict[str, Any]) -> list[dict[str, str]]:
    receipt_path = provider_check.get("receipt")
    path = Path(str(receipt_path)) if receipt_path else None
    payload = safe_json(path) if path is not None else None
    if payload is None or path is None:
        raise UnattendedError("PROVIDER_RECEIPT_MISSING", "fresh provider receipt is unreadable")
    failures = validate_provider_receipt(payload, path=path)
    if failures:
        raise UnattendedError("PROVIDER_RECEIPT_INVALID", ",".join(failures))
    routes: list[dict[str, str]] = []
    providers: set[str] = set()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not row.get("callable"):
            continue
        provider = str(row.get("provider") or "").strip().casefold()
        model = str(row.get("model_id") or row.get("requested_model") or "").strip()
        if provider and model and provider not in providers:
            providers.add(provider)
            routes.append({"provider": provider, "model_id": model})
        if len(routes) == 2:
            break
    if len(routes) != 2:
        raise UnattendedError("TWO_PROVIDER_POLICY", f"callable independent routes: {len(routes)}/2")
    return routes


def admission_status(state_root: Path) -> dict[str, Any]:
    """Evaluate all pre-spend gates and return selected redacted route IDs."""

    reasons: list[str] = []
    halt = state_root / ".dharma" / "forge_lab" / "HALT"
    if halt.exists():
        reasons.append(f"HALT_present:{halt}")
    if os.environ.get("RSI_LAB_DEV_SOURCE") == "1":
        reasons.append("development_source_forbidden")
    configured_state = os.environ.get("RSI_LAB_STATE", "").strip()
    if not configured_state or Path(configured_state).expanduser().resolve(strict=False) != state_root:
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
    provider_check = ((report.get("checks") or {}).get("providers") or {})
    if int(provider_check.get("ttl_seconds") or 0) > PROVIDER_TTL_SECONDS:
        reasons.append("provider_ttl_policy_too_weak")
    try:
        routes = _selected_routes(provider_check) if provider_check.get("ready") else []
    except UnattendedError as exc:
        reasons.append(f"{exc.code}:{exc}")
        routes = []
    grader = ((report.get("checks") or {}).get("grader") or {})
    if not grader.get("ready") or not grader.get("docker_daemon_reachable"):
        reasons.append("isolated_docker_grader_not_ready")
    taskbed = ((report.get("checks") or {}).get("taskbed") or {})
    task_id = str(taskbed.get("next_explore_task_id") or "").strip()
    if not taskbed.get("ready") or not task_id:
        reasons.append("state_anchored_isolated_task_unavailable")
    return {
        "ready": not reasons and len(routes) == 2,
        "reasons": reasons,
        "halt_path": str(halt),
        "source": source,
        "doctor": report,
        "routes": routes,
        "task_id": task_id or None,
    }


def _run_child_process(
    spec_path: Path,
    *,
    run_id: str,
    timeout_seconds: int,
    log_path: Path,
    halt_path: Path,
) -> tuple[int, bool, bool, int]:
    """Run the experiment in a child process with an external wall-clock fuse."""

    env = os.environ.copy()
    env.update(
        {
            "RSI_LAB_UNATTENDED_CHILD_RUN_ID": run_id,
            "DHARMA_MODEL_BUDGET_USD": str(RUN_USD_RESERVATION),
            "DHARMA_EVOLUTION_SHADOW": "1",
            "DHARMA_SELF_IMPROVE": "0",
            "DHARMA_ALLOW_LIVE_MUTATION": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    started = time.monotonic()
    deadline = started + timeout_seconds
    timed_out = False
    halted = False
    with os.fdopen(descriptor, "wb") as log_handle:
        process = subprocess.Popen(
            [sys.executable, "-m", __name__, "--child-spec", str(spec_path)],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        returncode: int | None = None
        while returncode is None:
            if halt_path.exists():
                halted = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                returncode = process.wait(timeout=min(2.0, remaining))
            except subprocess.TimeoutExpired:
                continue
        if returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                returncode = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                returncode = process.wait(timeout=10)
        log_handle.flush()
        os.fsync(log_handle.fileno())
    return returncode, timed_out, halted, round(time.monotonic() - started)


def _append_receipt(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return append_chain(
        root / "receipts.jsonl",
        payload,
        schema=RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )


def _validated_child_result(path: Path, *, run_id: str) -> dict[str, Any] | None:
    if path.is_symlink():
        return None
    payload = safe_json(path)
    if payload is None or payload.get("schema") != CHILD_SCHEMA:
        return None
    if payload.get("run_id") != run_id or payload.get("positive_rsi_claim") is not False:
        return None
    if payload.get("result_digest") != _chain_digest(payload, "result_digest"):
        return None
    try:
        used = int(payload.get("logical_provider_calls_used"))
        limit = int(payload.get("logical_provider_call_limit"))
    except (TypeError, ValueError):
        return None
    if used < 0 or used > LOGICAL_PROVIDER_CALL_SLOTS or limit != LOGICAL_PROVIDER_CALL_SLOTS:
        return None
    return payload


def _validate_child_spec(
    spec: dict[str, Any],
    spec_path: Path,
    *,
    admission: dict[str, Any],
) -> None:
    """Bind the hidden child to the parent's reservation and canonical paths."""

    run_id = str(spec.get("run_id") or "")
    state_root = Path(str(spec.get("state_root") or "")).resolve(strict=False)
    control_root = state_root / ".dharma" / "forge_lab" / "unattended_explore"
    expected_run_dir = control_root / "runs" / run_id
    expected_spec = expected_run_dir / "child_spec.json"
    expected_result = expected_run_dir / "child_result.json"
    expected_archive = state_root / ".dharma" / "evolution_archive"
    expected_scratch = state_root / ".dharma" / "evolution_worktrees"
    if spec_path.resolve(strict=False) != expected_spec.resolve(strict=False):
        raise UnattendedError("CHILD_SPEC_PATH", "child spec is outside its run directory")
    if Path(str(spec.get("result_path") or "")).resolve(strict=False) != expected_result.resolve(
        strict=False
    ):
        raise UnattendedError("CHILD_RESULT_PATH", "child result path is not canonical")
    if Path(str(spec.get("archive_root") or "")).resolve(strict=False) != expected_archive.resolve(
        strict=False
    ):
        raise UnattendedError("CHILD_ARCHIVE_PATH", "archive root is not state-anchored")
    if Path(str(spec.get("scratch_root") or "")).resolve(strict=False) != expected_scratch.resolve(
        strict=False
    ):
        raise UnattendedError("CHILD_SCRATCH_PATH", "scratch root is not state-anchored")
    source = admission["source"]
    if Path(str(spec.get("source_repo") or "")).resolve(strict=False) != Path(
        source["repo"]
    ).resolve(strict=False):
        raise UnattendedError("CHILD_SOURCE_PATH", "source path changed after admission")
    if not spec.get("task_id") or spec.get("task_id") != admission.get("task_id"):
        raise UnattendedError("CHILD_TASK", "isolated task changed after admission")
    expected_shape = {"generations": GENERATIONS, "children": CHILDREN, "tasks": TASKS}
    if spec.get("shape") != expected_shape:
        raise UnattendedError("CHILD_SHAPE", "child shape is not fixed 1x1x1")
    limits = spec.get("limits") if isinstance(spec.get("limits"), dict) else {}
    expected_limits = {
        "logical_provider_call_slots": LOGICAL_PROVIDER_CALL_SLOTS,
        "per_call_tokens": PER_CALL_TOKENS,
        "per_candidate_tokens": PER_CANDIDATE_TOKENS,
        "per_candidate_usd": PER_CANDIDATE_USD,
        "max_experiment_tokens": MAX_EXPERIMENT_TOKENS,
        "external_timeout_seconds": limits.get("external_timeout_seconds"),
    }
    if limits != expected_limits:
        raise UnattendedError("CHILD_LIMITS", "child limits differ from fixed policy")
    timeout = int(limits.get("external_timeout_seconds") or 0)
    if timeout < 60 or timeout > MAX_TIMEOUT_SECONDS:
        raise UnattendedError("CHILD_TIMEOUT", "child timeout is outside fixed policy")
    ledger = read_chain(
        control_root / "budget_ledger.jsonl",
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )
    reservation = next(
        (row for row in ledger if row.get("ledger_digest") == spec.get("reservation_digest")),
        None,
    )
    if (
        reservation is None
        or reservation.get("run_id") != run_id
        or reservation.get("reserved_usd") != RUN_USD_RESERVATION
        or reservation.get("reserved_logical_calls") != LOGICAL_PROVIDER_CALL_SLOTS
    ):
        raise UnattendedError("CHILD_RESERVATION", "exact parent reservation is absent")


def run_once(state_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Admit and execute one bounded run.  No retry occurs inside this function."""

    state_root = state_root.expanduser().resolve(strict=False)
    if not state_root.is_absolute() or state_root == Path("/"):
        raise UnattendedError("STATE_ROOT_UNSAFE", "state root must be a non-root absolute path")
    timeout_seconds = int(timeout_seconds)
    if timeout_seconds < 60 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise UnattendedError("TIMEOUT_POLICY", f"timeout must be 60..{MAX_TIMEOUT_SECONDS} seconds")
    control_root = state_root / ".dharma" / "forge_lab" / "unattended_explore"
    run_id = "unattended-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
    at = _now()
    with host_lock(control_root / "runner.lock"):
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
        run_dir = control_root / "runs" / run_id
        result_path = run_dir / "child_result.json"
        spec_path = run_dir / "child_spec.json"
        log_path = run_dir / "child.log"
        spec = {
            "schema": RUNNER_SCHEMA,
            "run_id": run_id,
            "created_at": at,
            "source_repo": source["repo"],
            "source_commit": source["commit"],
            "state_root": str(state_root),
            "archive_root": str(state_root / ".dharma" / "evolution_archive"),
            "scratch_root": str(state_root / ".dharma" / "evolution_worktrees"),
            "result_path": str(result_path),
            "routes": routes,
            "task_id": admission["task_id"],
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
        preflight = _append_receipt(
            control_root,
            {
                "kind": "run_admitted",
                "at": at,
                "run_id": run_id,
                "source_commit": source["commit"],
                "provider_families": [route["provider"] for route in routes],
                "task_id": spec["task_id"],
                "shape": spec["shape"],
                "limits": spec["limits"],
                "spec": str(spec_path),
                "spec_digest": spec["spec_digest"],
                "reservation_digest": reservation["ledger_digest"],
                "positive_rsi_claim": False,
            },
        )
        try:
            returncode, timed_out, halted, wall_seconds = _run_child_process(
                spec_path,
                run_id=run_id,
                timeout_seconds=timeout_seconds,
                log_path=log_path,
                halt_path=Path(admission["halt_path"]),
            )
        except Exception as exc:
            failed = _append_receipt(
                control_root,
                {
                    "kind": "run_launch_failed",
                    "at": _now(),
                    "run_id": run_id,
                    "admission_receipt_digest": preflight["receipt_digest"],
                    "reservation_digest": reservation["ledger_digest"],
                    "error_class": type(exc).__name__,
                    "epistemic_modality": "InconclusiveInfrastructure",
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError(
                "CHILD_LAUNCH_FAILED", str(failed["receipt_digest"])
            ) from exc
        child = _validated_child_result(result_path, run_id=run_id)
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
                "log": str(log_path),
                "log_digest": log_digest,
                "epistemic_modality": (
                    "InconclusiveOperatorHalt" if halted else "EXPLORE_ONLY"
                ),
                "positive_rsi_claim": False,
                "billing_telemetry": "unavailable_reservation_only",
            },
        )
        successful = bool(
            not timed_out
            and not halted
            and returncode == 0
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
            "positive_rsi_claim": False,
        }


def _bounded_child_seams(spec: dict[str, Any], counter: LogicalCallBudget):
    """Build seams with exactly one provider dispatch per logical slot."""

    from dharma_swarm.api_keys import bootstrap_runtime_env
    from dharma_swarm.forge_lab import grade_explore
    from dharma_swarm.forge_lab.experiment import Seams
    from dharma_swarm.forge_v1.providers import PoolCompletion
    from dharma_swarm.forge_v1.forge_v2.runner import _pull_task_context
    from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_task_ids

    bootstrap_runtime_env()
    base = grade_explore.production_seams()
    original_propose = base.propose_slot

    def propose_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
        counter.consume("candidate_generation")
        kwargs["continue_rounds"] = 0
        return original_propose(*args, **kwargs)

    def forbidden_arm(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise UnattendedError("UNBOUNDED_ARM_REFUSED", "unattended lane admits freeform_single only")

    grade = replace(
        base,
        propose_slot=propose_once,
        self_moa_arm=forbidden_arm,
        verify_chain_arm=forbidden_arm,
        mixed_moa_arm=forbidden_arm,
    )
    routes = spec["routes"]
    mutation_completion = PoolCompletion(routes[1]["model_id"])
    taskbed_db = Path(spec["state_root"]) / ".dharma" / "forge_v1" / "taskbed.db"

    def state_anchored_allocate(**kwargs: Any) -> dict[str, Any]:
        if kwargs.pop("count", None) != 1:
            raise UnattendedError("TASK_SHAPE", "unattended allocation requires one task")
        return allocate_task_ids(
            task_ids=[spec["task_id"]], db_path=taskbed_db, **kwargs
        )

    def bounded_mutation(prompt: str) -> tuple[str, int]:
        counter.consume("mutation")
        text, tokens = mutation_completion.complete(prompt)
        child = {
            "arm_kind": "freeform_single",
            "generator_model": routes[0]["model_id"],
            "verifier_model": routes[1]["model_id"],
            "per_call_tokens": PER_CALL_TOKENS,
            "window_chars": 24_000,
            "extra_instruction": str(text or "")[:4_000],
            "notes": "bounded_unattended_mutation_projection",
        }
        return json.dumps(child, sort_keys=True), int(tokens)

    return Seams(
        grade=grade,
        pull_task_context=_pull_task_context,
        allocate_explore=state_anchored_allocate,
        mutate_complete=bounded_mutation,
        make_worktree=_clone_scratch,
        remove_worktree=_remove_clone_scratch,
    )


def _run_git(argv: list[str], *, cwd: Path | None = None, timeout: int = 300) -> None:
    result = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
        env={
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": os.environ.get("HOME", "/nonexistent"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        },
    )
    if result.returncode != 0:
        raise UnattendedError("SCRATCH_GIT_FAILED", result.stderr.strip()[:500])


def _clone_scratch(
    *,
    source_repo: Path,
    experiment_id: str,
    archive_path: Path,
    category: str,
) -> Path:
    """Clone exact release bytes without writing the immutable source Git dir."""

    from dharma_swarm.evolution_safety import EVOLUTION_MARKER, is_scratch_worktree

    scratch_root = Path(os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"]).resolve()
    repo = (scratch_root / experiment_id / "repo").resolve()
    if scratch_root not in repo.parents or repo.exists():
        raise UnattendedError("SCRATCH_PATH_UNSAFE", str(repo))
    commit = str(require_execution_source(source_repo)["commit"])
    repo.parent.mkdir(parents=True, exist_ok=False)
    try:
        _run_git(["git", "clone", "--no-hardlinks", "--no-checkout", "--quiet", str(source_repo), str(repo)])
        _run_git(["git", "checkout", "--detach", "--quiet", commit], cwd=repo)
    except Exception:
        if scratch_root in repo.parent.parents:
            shutil.rmtree(repo.parent)
        raise
    marker = {
        "experiment_id": experiment_id,
        "git_base_sha": commit,
        "created_at": _now(),
        "archive_path": str(archive_path),
        "category": category,
        "standalone_clone": True,
    }
    marker_path = repo / EVOLUTION_MARKER
    write_json_exclusive(marker_path, marker)
    ok, _payload, reason = is_scratch_worktree(repo)
    if not ok:
        raise UnattendedError("SCRATCH_MARKER_REFUSED", str(reason))
    return repo


def _remove_clone_scratch(*, source_repo: Path, repo: Path, experiment_id: str) -> None:
    del source_repo, experiment_id
    from dharma_swarm.evolution_safety import EVOLUTION_MARKER, is_scratch_worktree

    scratch_root = Path(os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"]).resolve()
    resolved = repo.resolve()
    ok, _payload, _reason = is_scratch_worktree(resolved)
    if scratch_root not in resolved.parents or not ok or not (resolved / EVOLUTION_MARKER).is_file():
        raise UnattendedError("SCRATCH_REMOVE_REFUSED", str(resolved))
    shutil.rmtree(resolved.parent)


def run_child(spec_path: Path) -> int:
    """Execute the admitted child spec and persist one exclusive result."""

    from dharma_swarm.forge_lab.experiment import ExperimentConfig, run_experiment

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
    _validate_child_spec(spec, spec_path, admission=admission)

    os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"] = spec["scratch_root"]
    counter = LogicalCallBudget()
    routes = spec["routes"]
    cfg = ExperimentConfig(
        generations=GENERATIONS,
        children=CHILDREN,
        tasks_per_generation=TASKS,
        solver_model=routes[0]["model_id"],
        verifier_model=routes[1]["model_id"],
        mutator_model=routes[1]["model_id"],
        seed_genome={
            "arm_kind": "freeform_single",
            "generator_model": routes[0]["model_id"],
            "verifier_model": routes[1]["model_id"],
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
    closeout = asyncio.run(run_experiment(cfg, seams=_bounded_child_seams(spec, counter)))
    closeout = _redact_secret_values(closeout)
    result = {
        "schema": CHILD_SCHEMA,
        "run_id": run_id,
        "experiment_id": closeout.get("experiment_id"),
        "closeout_state": closeout.get("closeout_state"),
        "logical_provider_calls_used": counter.used,
        "logical_provider_call_limit": counter.limit,
        "experiment_closeout": closeout,
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
        "billing_telemetry": "unavailable_reservation_only",
    }
    result["result_digest"] = content_digest(result)
    write_json_exclusive(Path(spec["result_path"]), result)
    return 0 if closeout.get("closeout_state") in TERMINAL_SUCCESS_STATES else 1


def _redact_secret_values(payload: Any) -> Any:
    """Keep provider credential values out of child evidence recursively."""

    from dharma_swarm.api_keys import ALL_API_KEY_ENV_KEYS

    secrets = {
        value
        for name in ALL_API_KEY_ENV_KEYS
        if len(value := os.environ.get(name, "")) >= 8
    }
    if isinstance(payload, str):
        redacted = payload
        for secret in secrets:
            redacted = redacted.replace(secret, "[REDACTED_PROVIDER_CREDENTIAL]")
        return redacted
    if isinstance(payload, list):
        return [_redact_secret_values(value) for value in payload]
    if isinstance(payload, tuple):
        return tuple(_redact_secret_values(value) for value in payload)
    if isinstance(payload, dict):
        return {key: _redact_secret_values(value) for key, value in payload.items()}
    return payload


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
