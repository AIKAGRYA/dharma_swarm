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
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    RunnerPolicy,
    build_bounded_child_seams,
    execution_shape_matches,
    validate_child_spec,
    validated_child_result,
)
from dharma_swarm.forge_lab.unattended_ledger import (
    BudgetCeilings,
    LedgerError,
    append_chain as _ledger_append_chain,
    chain_digest as _ledger_chain_digest,
    read_chain as _ledger_read_chain,
    reserve_budget as _ledger_reserve_budget,
)
from dharma_swarm.forge_lab.unattended_model_evidence import (
    ModelEvidenceError,
    selected_model_evidence,
)

RUNNER_SCHEMA = "rsi_lab.unattended_explore.v1"
LEDGER_SCHEMA = "rsi_lab.unattended_budget_ledger.v1"
RECEIPT_SCHEMA = "rsi_lab.unattended_receipt_chain.v1"
CHILD_SCHEMA = "rsi_lab.unattended_child_result.v1"
CHILD_MODULE = "dharma_swarm.forge_lab.unattended_explore"

# Fixed live shape and hard policy maxima.  Dollar reservations are accounting
# ceilings, not vendor billing telemetry; that distinction is repeated in every
# ledger entry and closeout.
GENERATIONS = 1
CHILDREN = 1
TASKS = 1
LOGICAL_PROVIDER_CALL_SLOTS = 5
PER_CALL_TOKENS = 8_000
PER_CALL_USD = 0.25
PER_CANDIDATE_TOKENS = 16_000
PER_CANDIDATE_USD = 0.50
MAX_EXPERIMENT_TOKENS = 40_000
RUN_USD_RESERVATION = PER_CALL_USD * LOGICAL_PROVIDER_CALL_SLOTS
DAILY_USD_CAP = 3.0
MONTHLY_USD_CAP = 40.0
DAILY_CALL_CAP = 12
MONTHLY_CALL_CAP = 120
DEFAULT_TIMEOUT_SECONDS = 2_700
MAX_TIMEOUT_SECONDS = 3_000
PROVIDER_TTL_SECONDS = 3_600
MODEL_ROLES = ("mutator", "solver", "verifier")

TERMINAL_SUCCESS_STATES = {"inconclusive_low_power", "measured_negative"}
RUNNER_POLICY = RunnerPolicy(
    runner_schema=RUNNER_SCHEMA,
    ledger_schema=LEDGER_SCHEMA,
    child_schema=CHILD_SCHEMA,
    generations=GENERATIONS,
    children=CHILDREN,
    tasks=TASKS,
    logical_provider_call_slots=LOGICAL_PROVIDER_CALL_SLOTS,
    per_call_tokens=PER_CALL_TOKENS,
    per_candidate_tokens=PER_CANDIDATE_TOKENS,
    per_candidate_usd=PER_CANDIDATE_USD,
    max_experiment_tokens=MAX_EXPERIMENT_TOKENS,
    max_timeout_seconds=MAX_TIMEOUT_SECONDS,
    run_usd_reservation=RUN_USD_RESERVATION,
)


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
    by_label: dict[str, int] = field(default_factory=dict)

    def consume(self, label: str) -> None:
        if self.used >= self.limit:
            raise UnattendedError(
                "LOGICAL_PROVIDER_CALL_CAP",
                f"provider call slot refused before {label}: {self.used}/{self.limit}",
            )
        self.used += 1
        self.by_label[label] = self.by_label.get(label, 0) + 1


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
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise UnattendedError(
                "STATE_ROOT_UNSAFE", f"{label} must be a real directory: {path}"
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
        }
    halt = state_root / ".dharma" / "forge_lab" / "HALT"
    if halt.exists():
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
            [sys.executable, "-m", CHILD_MODULE, "--child-spec", str(spec_path)],
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
    return validated_child_result(
        path,
        run_id=run_id,
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
            "role_bindings": role_bindings,
            "model_profile_digest": admission["model_profile_digest"],
            "provider_receipt_digest": admission["provider_receipt_digest"],
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
                "model_profile_digest": spec["model_profile_digest"],
                "role_bindings": role_bindings,
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

    return build_bounded_child_seams(
        spec,
        counter,
        per_call_tokens=PER_CALL_TOKENS,
        error_factory=UnattendedError,
        clone_scratch=_clone_scratch,
        remove_clone_scratch=_remove_clone_scratch,
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
    if admission["role_bindings"] != spec.get("role_bindings"):
        raise UnattendedError("MODEL_PROFILE_CHANGED", "model roles changed after admission")
    if admission["model_profile_digest"] != spec.get("model_profile_digest"):
        raise UnattendedError("MODEL_PROFILE_CHANGED", "model profile changed after admission")
    if admission["provider_receipt_digest"] != spec.get("provider_receipt_digest"):
        raise UnattendedError("PROVIDER_RECEIPT_CHANGED", "provider receipt changed after admission")
    _validate_child_spec(spec, spec_path, admission=admission)

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
    closeout = asyncio.run(run_experiment(cfg, seams=_bounded_child_seams(spec, counter)))
    closeout = _redact_secret_values(closeout)
    stats = closeout.get("stats") if isinstance(closeout.get("stats"), dict) else {}
    counters = stats.get("counters") if isinstance(stats.get("counters"), dict) else {}
    execution_shape_ok = execution_shape_matches(
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
        "experiment_closeout": closeout,
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
        "billing_telemetry": "unavailable_reservation_only",
    }
    result["result_digest"] = content_digest(result)
    write_json_exclusive(Path(spec["result_path"]), result)
    return 0 if effective_state in TERMINAL_SUCCESS_STATES else 1


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
