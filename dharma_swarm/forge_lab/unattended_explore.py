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
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from dharma_swarm.forge_lab.operator_views import doctor
from dharma_swarm.forge_lab.provider_selftest import (
    UNATTENDED_MAX_INPUT_TOKEN_LIABILITY,
    UNATTENDED_MAX_OUTPUT_TOKEN_LIABILITY,
    validate_provider_receipt,
)
from dharma_swarm.forge_lab.safety_control import halt_status, latch_halt
from dharma_swarm.forge_lab.source_guard import require_execution_source
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    safe_json,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.unattended_budget import (
    BudgetPolicy,
    LEDGER_SCHEMA,
    budget_status,
    reserve_budget,
    settle_budget,
)
from dharma_swarm.forge_lab.unattended_lease import (
    LEASE_SCHEMA,
    LeaseHeartbeat,
    acquire_lease,
    lease_status,
    release_lease,
)
from dharma_swarm.forge_lab.unattended_receipts import (
    UnattendedError,
    _chain_digest,
    append_chain,
    read_chain,
)

RUNNER_SCHEMA = "rsi_lab.unattended_explore.v2"
RECEIPT_SCHEMA = "rsi_lab.unattended_receipt_chain.v1"
CHILD_SCHEMA = "rsi_lab.unattended_child_result.v2"

# Fixed live shape and hard policy maxima.  Reservations alone are never
# treated as provider billing telemetry: admission additionally requires a
# pinned route tariff whose maximum call liability fits the reservation, and a
# successful child reports exact coherent usage priced without cache discounts.
GENERATIONS = 1
CHILDREN = 1
TASKS = 1
LOGICAL_PROVIDER_CALL_SLOTS = 4
MAX_TRANSPORT_REQUESTS = 8
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
MAX_CHILD_LOG_BYTES = 64 * 1024 * 1024
PROVIDER_TTL_SECONDS = 3_600
MIN_FREE_DISK_BYTES = 2 * 1024 * 1024 * 1024
MIN_FREE_DISK_FRACTION = 0.05

TERMINAL_SUCCESS_STATES = {"inconclusive_low_power", "measured_negative"}


@dataclass
class LogicalCallBudget:
    """Count admitted logical provider invocations before dispatch."""

    limit: int = LOGICAL_PROVIDER_CALL_SLOTS
    used: int = 0
    transport_requests: int = 0
    provider_tokens: int = 0
    provider_usd: float = 0.0
    telemetry_valid: bool = True
    pricing_valid: bool = True
    attempts: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit <= 0:
            raise UnattendedError("LOGICAL_PROVIDER_CALL_CAP", "invalid call limit")
        self.attempts = []

    def consume(self, label: str) -> None:
        if self.used >= self.limit:
            raise UnattendedError(
                "LOGICAL_PROVIDER_CALL_CAP",
                f"provider call slot refused before {label}: {self.used}/{self.limit}",
            )
        self.used += 1

    def transport_attempt(
        self,
        label: str,
        *,
        provider: str,
        model_id: str,
        pricing: dict[str, Any],
    ) -> None:
        if self.transport_requests >= MAX_TRANSPORT_REQUESTS:
            raise UnattendedError(
                "TRANSPORT_REQUEST_CAP",
                f"transport request refused before {label}",
            )
        input_rate = pricing.get("input_usd_per_token")
        output_rate = pricing.get("output_usd_per_token")
        max_liability = pricing.get("unattended_max_call_liability_usd")
        if (
            not isinstance(pricing.get("pricing_id"), str)
            or not pricing["pricing_id"]
            or pricing.get("unattended_budget_eligible") is not True
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
                for value in (input_rate, output_rate, max_liability)
            )
            or float(max_liability) > PER_CANDIDATE_USD
        ):
            self.pricing_valid = False
            self.telemetry_valid = False
            raise UnattendedError("PROVIDER_PRICING_UNVERIFIED", str(model_id))
        self.transport_requests += 1
        assert self.attempts is not None
        self.attempts.append(
            {
                "label": str(label)[:96],
                "provider": str(provider)[:64],
                "requested_model": str(model_id)[:128],
                "request_sequence": self.transport_requests,
                "pricing_id": pricing["pricing_id"],
                "input_usd_per_token": float(input_rate),
                "output_usd_per_token": float(output_rate),
                "max_call_liability_usd": float(max_liability),
                "usage_verified": False,
            }
        )

    def record_response(
        self,
        *,
        served_model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> None:
        valid = bool(
            type(input_tokens) is int
            and input_tokens > 0
            and input_tokens <= UNATTENDED_MAX_INPUT_TOKEN_LIABILITY
            and type(output_tokens) is int
            and output_tokens >= 0
            and output_tokens <= UNATTENDED_MAX_OUTPUT_TOKEN_LIABILITY
            and type(total_tokens) is int
            and total_tokens > 0
            and total_tokens == input_tokens + output_tokens
        )
        if not valid or not self.attempts:
            self.telemetry_valid = False
            return
        attempt = self.attempts[-1]
        observed_usd = (
            input_tokens * float(attempt["input_usd_per_token"])
            + output_tokens * float(attempt["output_usd_per_token"])
        )
        if observed_usd > float(attempt["max_call_liability_usd"]) + 1e-12:
            self.pricing_valid = False
            self.telemetry_valid = False
            return
        self.provider_tokens += total_tokens
        self.provider_usd += observed_usd
        self.attempts[-1].update(
            {
                "served_model": str(served_model)[:128],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "provider_usd_verified": round(observed_usd, 9),
                "usage_verified": True,
            }
        )

    def record_unverifiable(self, error_category: str) -> None:
        self.telemetry_valid = False
        if self.attempts:
            self.attempts[-1]["error_category"] = str(error_category)[:96]

    def accounting(self) -> dict[str, Any]:
        return {
            "transport_requests_verified": (
                self.transport_requests if self.telemetry_valid else None
            ),
            "provider_tokens_verified": self.provider_tokens if self.telemetry_valid else None,
            # The USD reservation is an internal admission/accounting control.
            # Without a pinned tariff or account-level vendor cap it is not
            # truthful to report it as observed provider spend.
            "provider_usd_verified": (
                round(self.provider_usd, 9)
                if self.telemetry_valid and self.pricing_valid
                else None
            ),
            "telemetry_valid": self.telemetry_valid,
            "usd_accounting_verified": self.telemetry_valid and self.pricing_valid,
            "usd_accounting_mode": "pinned_tariff_exact_usage_conservative_no_cache_discount",
            "attempts": list(self.attempts or []),
        }


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def disk_readiness(state_root: Path) -> dict[str, Any]:
    """Fail closed before writes when the state filesystem is near exhaustion."""

    try:
        usage = shutil.disk_usage(state_root)
    except OSError as exc:
        return {
            "ready": False,
            "error": f"{type(exc).__name__}:{exc}"[:500],
            "reasons": ["state_filesystem_unreadable"],
        }
    free_fraction = usage.free / usage.total if usage.total else 0.0
    reasons: list[str] = []
    if usage.free < MIN_FREE_DISK_BYTES:
        reasons.append("free_bytes_below_2GiB")
    if free_fraction < MIN_FREE_DISK_FRACTION:
        reasons.append("free_fraction_below_5_percent")
    return {
        "ready": not reasons,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_fraction": round(free_fraction, 6),
        "reasons": reasons,
    }


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
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise UnattendedError("LOCK_PATH_UNSAFE", str(path))
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UnattendedError("LOCK_HELD", "another unattended run owns the host lock") from exc
        yield
    finally:
        os.close(descriptor)


def _selected_routes(provider_check: dict[str, Any]) -> list[dict[str, Any]]:
    receipt_path = provider_check.get("receipt")
    path = Path(str(receipt_path)) if receipt_path else None
    payload = safe_json(path) if path is not None else None
    if payload is None or path is None:
        raise UnattendedError("PROVIDER_RECEIPT_MISSING", "fresh provider receipt is unreadable")
    failures = validate_provider_receipt(payload, path=path)
    if failures:
        raise UnattendedError("PROVIDER_RECEIPT_INVALID", ",".join(failures))
    routes: list[dict[str, Any]] = []
    providers: set[str] = set()
    transports: set[str] = set()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not row.get("admission_eligible"):
            continue
        provider = str(row.get("provider") or "").strip().casefold()
        transport = str(row.get("transport_id") or "").strip().casefold()
        route_id = str(row.get("model_id") or "").strip()
        model = str(row.get("requested_model") or "").strip()
        pricing = row.get("pricing")
        if (
            provider
            and transport
            and model
            and isinstance(pricing, dict)
            and pricing.get("unattended_budget_eligible") is True
            and provider not in providers
            and transport not in transports
        ):
            providers.add(provider)
            transports.add(transport)
            routes.append(
                {
                    "provider": provider,
                    "transport_id": transport,
                    "route_id": route_id or model,
                    "model_id": model,
                    "endpoint_policy_id": str(row.get("endpoint_policy_id") or ""),
                    "pricing": pricing,
                }
            )
        if len(routes) == 2:
            break
    if len(routes) != 2:
        raise UnattendedError("TWO_PROVIDER_POLICY", f"callable independent routes: {len(routes)}/2")
    return routes


def admission_status(state_root: Path) -> dict[str, Any]:
    """Evaluate all pre-spend gates and return selected redacted route IDs."""

    reasons: list[str] = []
    safety_root = state_root / ".dharma" / "forge_lab"
    halt = safety_root / "HALT"
    try:
        status = halt_status(safety_root)
        if status.get("active"):
            reasons.append(f"HALT_present:{status.get('halt_digest') or halt}")
    except UnattendedError as exc:
        reasons.append(f"HALT_present_invalid:{exc.code}")
    if os.environ.get("RSI_LAB_DEV_SOURCE") == "1":
        reasons.append("development_source_forbidden")
    configured_state = os.environ.get("RSI_LAB_STATE", "").strip()
    if not configured_state or Path(configured_state).expanduser().resolve(strict=False) != state_root:
        reasons.append("explicit_state_root_not_anchored")
    disk = disk_readiness(state_root)
    if not disk["ready"]:
        reasons.extend(f"disk:{reason}" for reason in disk["reasons"])
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
    task_binding = taskbed.get("next_explore_task_binding")
    if (
        not taskbed.get("ready")
        or not task_id
        or not isinstance(task_binding, dict)
        or task_binding.get("task_id") != task_id
    ):
        reasons.append("state_anchored_isolated_task_unavailable")
    return {
        "ready": not reasons and len(routes) == 2,
        "reasons": reasons,
        "halt_path": str(halt),
        "source": source,
        "doctor": report,
        "disk": disk,
        "routes": routes,
        "task_id": task_id or None,
        "task_binding": task_binding if isinstance(task_binding, dict) else None,
    }


def _run_child_process(
    spec_path: Path,
    *,
    run_id: str,
    timeout_seconds: int,
    log_path: Path,
    halt_path: Path,
) -> tuple[int, bool, bool, int, str | None, bool]:
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
    halt_observation: str | None = None

    def observe_halt() -> bool:
        nonlocal halt_observation
        try:
            status = halt_status(halt_path.parent)
        except UnattendedError as exc:
            halt_observation = f"halt_control_invalid:{exc.code}"
            return True
        if status.get("active"):
            halt_observation = f"halt_active:{status.get('halt_digest')}"
            return True
        return False

    with os.fdopen(descriptor, "wb") as log_handle:
        process = subprocess.Popen(
            [
                "/usr/bin/prlimit",
                f"--fsize={MAX_CHILD_LOG_BYTES}:{MAX_CHILD_LOG_BYTES}",
                "--",
                sys.executable,
                "-m",
                __name__,
                "--child-spec",
                str(spec_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        returncode: int | None = None
        while returncode is None:
            if observe_halt():
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
        if observe_halt():
            halted = True
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
    log_limited = log_path.stat().st_size >= MAX_CHILD_LOG_BYTES
    return (
        returncode,
        timed_out,
        halted,
        round(time.monotonic() - started),
        halt_observation,
        log_limited,
    )


def _append_receipt(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return append_chain(
        root / "receipts.jsonl",
        payload,
        schema=RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )


def _validated_child_result(
    path: Path, *, run_id: str, spec: dict[str, Any]
) -> dict[str, Any] | None:
    if path.is_symlink():
        return None
    payload = safe_json(path)
    if payload is None or payload.get("schema") != CHILD_SCHEMA:
        return None
    expected_keys = {
        "schema",
        "run_id",
        "spec_digest",
        "reservation_digest",
        "lease",
        "task_id",
        "task_binding",
        "source_commit",
        "routes",
        "experiment_id",
        "closeout_state",
        "logical_provider_calls_used",
        "logical_provider_call_limit",
        "transport_requests_verified",
        "provider_tokens_verified",
        "provider_usd_verified",
        "telemetry_valid",
        "usd_accounting_verified",
        "usd_accounting_mode",
        "attempts",
        "grader_proofs",
        "experiment_closeout",
        "epistemic_modality",
        "positive_rsi_claim",
        "billing_telemetry",
        "result_digest",
    }
    if set(payload) != expected_keys:
        return None
    if (
        payload.get("run_id") != run_id
        or payload.get("positive_rsi_claim") is not False
        or payload.get("telemetry_valid") is not True
        or payload.get("usd_accounting_verified") is not True
        or payload.get("epistemic_modality") != "EXPLORE_ONLY"
        or payload.get("billing_telemetry")
        != "exact_requests_tokens_and_pinned_tariff_usd"
        or payload.get("usd_accounting_mode")
        != "pinned_tariff_exact_usage_conservative_no_cache_discount"
    ):
        return None
    if payload.get("result_digest") != _chain_digest(payload, "result_digest"):
        return None
    for result_field, spec_field in (
        ("spec_digest", "spec_digest"),
        ("reservation_digest", "reservation_digest"),
        ("lease", "lease"),
        ("task_id", "task_id"),
        ("task_binding", "task_binding"),
        ("source_commit", "source_commit"),
        ("routes", "routes"),
    ):
        if payload.get(result_field) != spec.get(spec_field):
            return None
    used = payload.get("logical_provider_calls_used")
    limit = payload.get("logical_provider_call_limit")
    requests = payload.get("transport_requests_verified")
    tokens = payload.get("provider_tokens_verified")
    usd = payload.get("provider_usd_verified")
    if (
        type(used) is not int
        or type(limit) is not int
        or type(requests) is not int
        or type(tokens) is not int
        or isinstance(usd, bool)
        or not isinstance(usd, (int, float))
        or not math.isfinite(float(usd))
    ):
        return None
    if (
        used <= 0
        or used > LOGICAL_PROVIDER_CALL_SLOTS
        or limit != LOGICAL_PROVIDER_CALL_SLOTS
        or requests != used
        or requests > MAX_TRANSPORT_REQUESTS
        or tokens <= 0
        or tokens > PER_CALL_TOKENS * LOGICAL_PROVIDER_CALL_SLOTS
        or float(usd) < 0
        or float(usd) > RUN_USD_RESERVATION
    ):
        return None
    attempts = payload.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != requests:
        return None
    total_tokens = 0
    total_usd = 0.0
    route_by_identity = {
        (str(route.get("provider") or ""), str(route.get("model_id") or "")): route
        for route in (spec.get("routes") or [])
        if isinstance(route, dict)
    }
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict) or set(attempt) != {
            "label",
            "provider",
            "requested_model",
            "request_sequence",
            "pricing_id",
            "input_usd_per_token",
            "output_usd_per_token",
            "max_call_liability_usd",
            "served_model",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "provider_usd_verified",
            "usage_verified",
        }:
            return None
        inp = attempt.get("input_tokens")
        out = attempt.get("output_tokens")
        total = attempt.get("total_tokens")
        attempt_usd = attempt.get("provider_usd_verified")
        input_rate = attempt.get("input_usd_per_token")
        output_rate = attempt.get("output_usd_per_token")
        max_liability = attempt.get("max_call_liability_usd")
        route = route_by_identity.get(
            (str(attempt.get("provider") or ""), str(attempt.get("requested_model") or ""))
        )
        pricing = route.get("pricing") if isinstance(route, dict) else None
        if (
            attempt.get("request_sequence") != index
            or type(inp) is not int
            or inp <= 0
            or inp > UNATTENDED_MAX_INPUT_TOKEN_LIABILITY
            or type(out) is not int
            or out < 0
            or out > UNATTENDED_MAX_OUTPUT_TOKEN_LIABILITY
            or type(total) is not int
            or total != inp + out
            or attempt.get("usage_verified") is not True
            or not isinstance(pricing, dict)
            or attempt.get("pricing_id") != pricing.get("pricing_id")
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
                for value in (attempt_usd, input_rate, output_rate, max_liability)
            )
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
                for value in (
                    pricing.get("input_usd_per_token"),
                    pricing.get("output_usd_per_token"),
                    pricing.get("unattended_max_call_liability_usd"),
                )
            )
            or float(input_rate) != float(pricing.get("input_usd_per_token", -1))
            or float(output_rate) != float(pricing.get("output_usd_per_token", -1))
            or float(max_liability)
            != float(pricing.get("unattended_max_call_liability_usd", -1))
            or abs(float(attempt_usd) - (inp * float(input_rate) + out * float(output_rate)))
            > 1e-9
            or float(attempt_usd) > float(max_liability) + 1e-12
            or _probe_identity(str(attempt.get("requested_model") or ""))
            != _probe_identity(str(attempt.get("served_model") or ""))
        ):
            return None
        total_tokens += total
        total_usd += float(attempt_usd)
    if total_tokens != tokens or abs(total_usd - float(usd)) > 1e-8:
        return None
    closeout = payload.get("experiment_closeout")
    if (
        not isinstance(closeout, dict)
        or closeout.get("experiment_id") != payload.get("experiment_id")
        or closeout.get("closeout_state") != payload.get("closeout_state")
        or payload.get("closeout_state") not in TERMINAL_SUCCESS_STATES
    ):
        return None
    proofs = payload.get("grader_proofs")
    task_binding = spec.get("task_binding") or {}
    if not isinstance(proofs, list) or not proofs:
        return None
    for proof in proofs:
        identity = proof.get("image_identity") if isinstance(proof, dict) else None
        if (
            not isinstance(proof, dict)
            or proof.get("schema") != "rsi_lab.grader_isolation_proof.v1"
            or proof.get("promotion_eligible") is not True
            or not isinstance(identity, dict)
            or identity.get("image_key") != task_binding.get("image_key")
            or identity.get("expected_local_image_id")
            != task_binding.get("local_image_id")
            or identity.get("observed_local_image_id")
            != task_binding.get("local_image_id")
            or sorted(identity.get("repo_digests") or [])
            != sorted(task_binding.get("local_image_repo_digests") or [])
            or identity.get("immutable_repo_digest")
            not in (task_binding.get("local_image_repo_digests") or [])
        ):
            return None
    return payload


def _probe_identity(model_id: str) -> str:
    return str(model_id or "").strip().casefold()


def _validate_child_spec(
    spec: dict[str, Any],
    spec_path: Path,
    *,
    admission: dict[str, Any],
) -> None:
    """Bind the hidden child to the parent's reservation and canonical paths."""

    if set(spec) != {
        "schema",
        "run_id",
        "created_at",
        "source_repo",
        "source_commit",
        "state_root",
        "archive_root",
        "scratch_root",
        "result_path",
        "routes",
        "task_id",
        "task_binding",
        "shape",
        "limits",
        "lease",
        "reservation_digest",
        "positive_rsi_claim",
        "spec_digest",
    } or spec.get("positive_rsi_claim") is not False:
        raise UnattendedError("CHILD_SPEC_SHAPE", "child spec keys or authority flag invalid")
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
    if (
        not isinstance(spec.get("task_binding"), dict)
        or spec.get("task_binding") != admission.get("task_binding")
    ):
        raise UnattendedError("CHILD_TASK_BINDING", "taskpack identity changed after admission")
    expected_shape = {"generations": GENERATIONS, "children": CHILDREN, "tasks": TASKS}
    if spec.get("shape") != expected_shape:
        raise UnattendedError("CHILD_SHAPE", "child shape is not fixed 1x1x1")
    limits = spec.get("limits") if isinstance(spec.get("limits"), dict) else {}
    expected_limits = {
        "logical_provider_call_slots": LOGICAL_PROVIDER_CALL_SLOTS,
        "max_transport_requests": MAX_TRANSPORT_REQUESTS,
        "per_call_tokens": PER_CALL_TOKENS,
        "per_candidate_tokens": PER_CANDIDATE_TOKENS,
        "per_candidate_usd": PER_CANDIDATE_USD,
        "max_experiment_tokens": MAX_EXPERIMENT_TOKENS,
        "external_timeout_seconds": limits.get("external_timeout_seconds"),
    }
    if limits != expected_limits:
        raise UnattendedError("CHILD_LIMITS", "child limits differ from fixed policy")
    timeout = limits.get("external_timeout_seconds")
    if type(timeout) is not int or timeout < 60 or timeout > MAX_TIMEOUT_SECONDS:
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
        or not isinstance(reservation.get("reserved"), dict)
        or reservation["reserved"].get("requests") != MAX_TRANSPORT_REQUESTS
        or reservation["reserved"].get("tokens") != PER_CALL_TOKENS * LOGICAL_PROVIDER_CALL_SLOTS
    ):
        raise UnattendedError("CHILD_RESERVATION", "exact parent reservation is absent")
    lease = spec.get("lease") if isinstance(spec.get("lease"), dict) else {}
    current = lease_status(control_root).get("lease") or {}
    fence = lease.get("fence")
    current_fence = current.get("fence")
    if type(fence) is not int or type(current_fence) is not int:
        raise UnattendedError("CHILD_LEASE", "lease fence is not an exact integer")
    lease_identity = (
        lease.get("lease_id"),
        lease.get("holder_id"),
        fence,
        lease.get("run_id"),
    )
    current_identity = (
        current.get("lease_id"),
        current.get("holder_id"),
        current_fence,
        current.get("run_id"),
    )
    if lease_identity != current_identity or lease_identity[3] != run_id:
        raise UnattendedError("CHILD_LEASE", "child does not hold the current fenced lease")


def _reconcile_crash_closeouts(
    control_root: Path,
    *,
    current_run_id: str,
    recovery_fence: int,
) -> list[dict[str, Any]]:
    """Close every abandoned reservation once after a newer fence takes over."""

    receipts = read_chain(
        control_root / "receipts.jsonl",
        schema=RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    terminal_kinds = {
        "admission_refusal",
        "run_closeout",
        "run_launch_failed",
        "run_crash_reconciled",
        "control_reconciliation",
    }
    terminal_runs = {
        str(row.get("run_id"))
        for row in receipts
        if row.get("kind") in terminal_kinds
    }
    admissions = {
        str(row.get("run_id")): row
        for row in receipts
        if row.get("kind") == "run_admitted"
    }
    ledger_path = control_root / "budget_ledger.jsonl"
    ledger = read_chain(ledger_path, schema=LEDGER_SCHEMA, digest_field="ledger_digest")
    settlements = {
        str(row.get("reservation_digest")): row
        for row in ledger
        if row.get("kind") == "settlement"
    }
    reservations = {
        str(row.get("run_id")): row
        for row in ledger
        if row.get("kind") == "reservation"
    }
    lease_events = read_chain(
        control_root / "lease_events.jsonl",
        schema=LEASE_SCHEMA,
        digest_field="lease_event_digest",
    )
    acquisitions = {
        str(row.get("run_id")): row
        for row in lease_events
        if row.get("kind") == "acquired"
        and int(row.get("fence") or 0) < int(recovery_fence)
    }
    reconciled: list[dict[str, Any]] = []
    abandoned_run_ids = sorted(set(reservations) | set(acquisitions))
    for run_id in abandoned_run_ids:
        if run_id == current_run_id or run_id in terminal_runs:
            continue
        reservation = reservations.get(run_id)
        digest = str((reservation or {}).get("ledger_digest") or "")
        settlement = settlements.get(digest) if digest else None
        if reservation is not None and settlement is None:
            settlement = settle_budget(
                ledger_path,
                run_id=run_id,
                reservation_digest=digest,
                at=_now(),
                observed=None,
                terminal_kind="crash_reconciled",
            )
        admission = admissions.get(run_id)
        acquisition = acquisitions.get(run_id)
        receipt = _append_receipt(
            control_root,
            {
                "kind": "run_crash_reconciled",
                "at": _now(),
                "run_id": run_id,
                "admission_receipt_digest": (admission or {}).get("receipt_digest"),
                "acquisition_event_digest": (acquisition or {}).get("lease_event_digest"),
                "reservation_digest": digest or None,
                "settlement_digest": (settlement or {}).get("ledger_digest"),
                "prior_settlement_reused": bool(digest and digest in settlements),
                "zero_spend_pre_reservation": reservation is None,
                "provider_calls_authorized": 0 if reservation is None else None,
                "recovery_fence": int(recovery_fence),
                "unknown_effects": reservation is not None,
                "epistemic_modality": "InconclusiveCrashRecovery",
                "positive_rsi_claim": False,
            },
        )
        reconciled.append(receipt)
    return reconciled


def run_once(state_root: Path, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Acquire a fence, execute one bounded run, and terminally close all authority."""

    state_root = state_root.expanduser().resolve(strict=False)
    if not state_root.is_absolute() or state_root == Path("/"):
        raise UnattendedError("STATE_ROOT_UNSAFE", "state root must be a non-root absolute path")
    if (
        type(timeout_seconds) is not int
        or timeout_seconds < 60
        or timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        raise UnattendedError("TIMEOUT_POLICY", f"timeout must be 60..{MAX_TIMEOUT_SECONDS} seconds")
    control_root = state_root / ".dharma" / "forge_lab" / "unattended_explore"
    run_id = "unattended-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
    holder_id = f"pid-{os.getpid()}-{uuid4().hex[:12]}"
    at = _now()
    with host_lock(control_root / "runner.lock"):
        lease = acquire_lease(
            control_root,
            run_id=run_id,
            holder_id=holder_id,
            at=at,
        )
        reservation: dict[str, Any] | None = None
        settlement: dict[str, Any] | None = None
        terminal_receipt: dict[str, Any] | None = None
        released = False
        try:
            recovered = _reconcile_crash_closeouts(
                control_root,
                current_run_id=run_id,
                recovery_fence=int(lease["fence"]),
            )
            admission = admission_status(state_root)
            if not admission["ready"]:
                terminal_receipt = _append_receipt(
                    control_root,
                    {
                        "kind": "admission_refusal",
                        "at": at,
                        "run_id": run_id,
                        "lease_id": lease["lease_id"],
                        "fence": lease["fence"],
                        "recovered_run_count": len(recovered),
                        "reasons": admission["reasons"],
                        "provider_calls": 0,
                        "usd_reserved": 0.0,
                        "positive_rsi_claim": False,
                    },
                )
                release_lease(
                    control_root,
                    lease_id=str(lease["lease_id"]),
                    holder_id=holder_id,
                    fence=int(lease["fence"]),
                    terminal_receipt_digest=str(terminal_receipt["receipt_digest"]),
                )
                released = True
                raise UnattendedError(
                    "ADMISSION_REFUSED", str(terminal_receipt["receipt_digest"])
                )

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
                "task_binding": admission["task_binding"],
                "shape": {"generations": GENERATIONS, "children": CHILDREN, "tasks": TASKS},
                "limits": {
                    "logical_provider_call_slots": LOGICAL_PROVIDER_CALL_SLOTS,
                    "max_transport_requests": MAX_TRANSPORT_REQUESTS,
                    "per_call_tokens": PER_CALL_TOKENS,
                    "per_candidate_tokens": PER_CANDIDATE_TOKENS,
                    "per_candidate_usd": PER_CANDIDATE_USD,
                    "max_experiment_tokens": MAX_EXPERIMENT_TOKENS,
                    "external_timeout_seconds": timeout_seconds,
                },
                "lease": {
                    "lease_id": lease["lease_id"],
                    "holder_id": holder_id,
                    "fence": lease["fence"],
                    "run_id": run_id,
                    "acquisition_event_digest": lease["lease_event_digest"],
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
                    "lease_id": lease["lease_id"],
                    "fence": lease["fence"],
                    "source_commit": source["commit"],
                    "provider_families": [route["provider"] for route in routes],
                    "task_id": spec["task_id"],
                    "shape": spec["shape"],
                    "limits": spec["limits"],
                    "spec": str(spec_path),
                    "spec_digest": spec["spec_digest"],
                    "reservation_digest": reservation["ledger_digest"],
                    "recovered_run_count": len(recovered),
                    "positive_rsi_claim": False,
                },
            )

            def heartbeat_failure(exc: UnattendedError) -> None:
                latch_halt(
                    state_root / ".dharma" / "forge_lab",
                    at=_now(),
                    code=exc.code,
                    reason=str(exc),
                    source="lease_heartbeat",
                    run_id=run_id,
                )

            try:
                with LeaseHeartbeat(control_root, lease, on_failure=heartbeat_failure) as heartbeat:
                    heartbeat.progress("child_started")
                    (
                        returncode,
                        timed_out,
                        halted,
                        wall_seconds,
                        halt_observation,
                        log_limited,
                    ) = _run_child_process(
                        spec_path,
                        run_id=run_id,
                        timeout_seconds=timeout_seconds,
                        log_path=log_path,
                        halt_path=Path(admission["halt_path"]),
                    )
                    heartbeat.progress("child_terminal")
                heartbeat_error = heartbeat.error
            except Exception as exc:
                settlement = settle_budget(
                    control_root / "budget_ledger.jsonl",
                    run_id=run_id,
                    reservation_digest=str(reservation["ledger_digest"]),
                    at=_now(),
                    observed=None,
                    terminal_kind="launch_failed",
                )
                latch_halt(
                    state_root / ".dharma" / "forge_lab",
                    at=_now(),
                    code="CHILD_LAUNCH_FAILED",
                    reason=f"{type(exc).__name__}:{exc}"[:500],
                    source="unattended_supervisor",
                    run_id=run_id,
                )
                terminal_receipt = _append_receipt(
                    control_root,
                    {
                        "kind": "run_launch_failed",
                        "at": _now(),
                        "run_id": run_id,
                        "lease_id": lease["lease_id"],
                        "fence": lease["fence"],
                        "admission_receipt_digest": preflight["receipt_digest"],
                        "reservation_digest": reservation["ledger_digest"],
                        "settlement_digest": settlement["ledger_digest"],
                        "error_class": type(exc).__name__,
                        "epistemic_modality": "InconclusiveInfrastructure",
                        "positive_rsi_claim": False,
                    },
                )
                raise UnattendedError(
                    "CHILD_LAUNCH_FAILED", str(terminal_receipt["receipt_digest"])
                ) from exc

            child = _validated_child_result(result_path, run_id=run_id, spec=spec)
            observed = {
                "logical_calls": (child or {}).get("logical_provider_calls_used"),
                "requests": (child or {}).get("transport_requests_verified"),
                "tokens": (child or {}).get("provider_tokens_verified"),
                "usd": (child or {}).get("provider_usd_verified"),
                "wall_seconds": wall_seconds,
            }
            settlement = settle_budget(
                control_root / "budget_ledger.jsonl",
                run_id=run_id,
                reservation_digest=str(reservation["ledger_digest"]),
                at=_now(),
                observed=observed,
                terminal_kind="run_closeout",
            )
            if (
                timed_out
                or heartbeat_error
                or child is None
                or log_limited
                or not settlement["accounting_valid"]
            ):
                code = (
                    "RUN_WALL_TIMEOUT" if timed_out else
                    heartbeat_error.code if heartbeat_error else
                    "CHILD_RESULT_INVALID" if child is None else
                    "CHILD_LOG_LIMIT" if log_limited else
                    "BUDGET_OVERRUN" if settlement["overrun_dimensions"] else
                    "BUDGET_USAGE_UNVERIFIABLE"
                )
                latch_halt(
                    state_root / ".dharma" / "forge_lab",
                    at=_now(),
                    code=code,
                    reason="bounded unattended closeout tripped a safety fuse",
                    source="unattended_supervisor",
                    run_id=run_id,
                )
            log_digest = "sha256:" + hashlib.sha256(log_path.read_bytes()).hexdigest()
            terminal_receipt = _append_receipt(
                control_root,
                {
                    "kind": "run_closeout",
                    "at": _now(),
                    "run_id": run_id,
                    "lease_id": lease["lease_id"],
                    "fence": lease["fence"],
                    "admission_receipt_digest": preflight["receipt_digest"],
                    "reservation_digest": reservation["ledger_digest"],
                    "settlement_digest": settlement["ledger_digest"],
                    "returncode": returncode,
                    "timed_out": timed_out,
                    "halted": halted,
                    "halt_observation": halt_observation,
                    "child_log_limit_bytes": MAX_CHILD_LOG_BYTES,
                    "child_log_limit_reached": log_limited,
                    "heartbeat_error": heartbeat_error.code if heartbeat_error else None,
                    "wall_seconds": wall_seconds,
                    "child_result": str(result_path) if child else None,
                    "child_result_digest": content_digest(child) if child else None,
                    "experiment_id": (child or {}).get("experiment_id"),
                    "explore_closeout_state": (child or {}).get("closeout_state"),
                    "logical_provider_calls_used": (child or {}).get("logical_provider_calls_used"),
                    "accounting_valid": settlement["accounting_valid"],
                    "unverifiable_dimensions_charged_in_full": settlement["unverifiable_dimensions"],
                    "log": str(log_path),
                    "log_digest": log_digest,
                    "epistemic_modality": (
                        "InconclusiveOperatorHalt" if halted else
                        "InconclusiveAccounting" if not settlement["accounting_valid"] else
                        "EXPLORE_ONLY"
                    ),
                    "positive_rsi_claim": False,
                    "billing_telemetry": "conservative_full_reservation_for_unverifiable_dimensions",
                },
            )
            release_lease(
                control_root,
                lease_id=str(lease["lease_id"]),
                holder_id=holder_id,
                fence=int(lease["fence"]),
                terminal_receipt_digest=str(terminal_receipt["receipt_digest"]),
            )
            released = True
            successful = bool(
                not timed_out
                and not halted
                and heartbeat_error is None
                and returncode == 0
                and child
                and not log_limited
                and child.get("closeout_state") in TERMINAL_SUCCESS_STATES
                and settlement["accounting_valid"]
            )
            return {
                "schema": RUNNER_SCHEMA,
                "ok": successful,
                "run_id": run_id,
                "fence": lease["fence"],
                "receipt_digest": terminal_receipt["receipt_digest"],
                "settlement_digest": settlement["ledger_digest"],
                "closeout_state": (child or {}).get("closeout_state"),
                "timed_out": timed_out,
                "halted": halted,
                "returncode": returncode,
                "positive_rsi_claim": False,
            }
        except Exception as exc:
            if reservation is not None and settlement is None:
                settlement = settle_budget(
                    control_root / "budget_ledger.jsonl",
                    run_id=run_id,
                    reservation_digest=str(reservation["ledger_digest"]),
                    at=_now(),
                    observed=None,
                    terminal_kind="supervisor_exception",
                )
            if terminal_receipt is None:
                terminal_receipt = _append_receipt(
                    control_root,
                    {
                        "kind": "run_launch_failed",
                        "at": _now(),
                        "run_id": run_id,
                        "lease_id": lease["lease_id"],
                        "fence": lease["fence"],
                        "reservation_digest": (reservation or {}).get("ledger_digest"),
                        "settlement_digest": (settlement or {}).get("ledger_digest"),
                        "error_class": type(exc).__name__,
                        "error_code": getattr(exc, "code", "SUPERVISOR_EXCEPTION"),
                        "epistemic_modality": "InconclusiveInfrastructure",
                        "positive_rsi_claim": False,
                    },
                )
            if not released:
                release_lease(
                    control_root,
                    lease_id=str(lease["lease_id"]),
                    holder_id=holder_id,
                    fence=int(lease["fence"]),
                    terminal_receipt_digest=str(terminal_receipt["receipt_digest"]),
                )
            raise


def _bounded_child_seams(spec: dict[str, Any], counter: LogicalCallBudget):
    from dharma_swarm.forge_lab.unattended_child import bounded_child_seams

    return bounded_child_seams(spec, counter)


def _isolation_proofs(payload: Any) -> list[dict[str, Any]]:
    proofs: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        value = payload.get("isolation_proofs")
        if isinstance(value, list):
            proofs.extend(dict(item) for item in value if isinstance(item, dict))
        for key, nested in payload.items():
            if key != "isolation_proofs":
                proofs.extend(_isolation_proofs(nested))
    elif isinstance(payload, list):
        for nested in payload:
            proofs.extend(_isolation_proofs(nested))
    return proofs


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
    accounting = counter.accounting()
    grader_proofs = _isolation_proofs(closeout)
    result = {
        "schema": CHILD_SCHEMA,
        "run_id": run_id,
        "spec_digest": spec["spec_digest"],
        "reservation_digest": spec["reservation_digest"],
        "lease": spec["lease"],
        "task_id": spec["task_id"],
        "task_binding": spec["task_binding"],
        "source_commit": spec["source_commit"],
        "routes": spec["routes"],
        "experiment_id": closeout.get("experiment_id"),
        "closeout_state": closeout.get("closeout_state"),
        "logical_provider_calls_used": counter.used,
        "logical_provider_call_limit": counter.limit,
        **accounting,
        "grader_proofs": grader_proofs,
        "experiment_closeout": closeout,
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
        "billing_telemetry": "exact_requests_tokens_and_pinned_tariff_usd",
    }
    result["result_digest"] = content_digest(result)
    write_json_exclusive(Path(spec["result_path"]), result)
    return 0 if (
        closeout.get("closeout_state") in TERMINAL_SUCCESS_STATES
        and accounting["telemetry_valid"]
        and accounting["usd_accounting_verified"]
        and bool(grader_proofs)
    ) else 1


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
    parser.add_argument("--systemd-condition", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    args = build_parser().parse_args(argv)
    if args.systemd_condition:
        if args.state_root is None or args.child_spec is not None:
            print("rsi systemd condition: invalid invocation", file=sys.stderr)
            return 255
        try:
            status = halt_status(args.state_root / ".dharma" / "forge_lab")
        except UnattendedError as exc:
            print(f"rsi systemd condition refused [{exc.code}]", file=sys.stderr)
            return 255
        # ExecCondition exit 1 is a clean skip, not a failed activation.  The
        # authoritative receipt chain therefore stays quiescent until resume,
        # even when an operator deletes the HALT marker projection.
        return 1 if status.get("active") else 0
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
