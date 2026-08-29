"""Conservative multidimensional reservations for unattended RSI runs.

Reservations are the canonical spend authority for this lane.  Missing vendor
telemetry never creates a refund: every unverifiable dimension is charged at
its reserved ceiling, preserving daily and monthly fail-closed caps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest, validate_digest, validate_safe_id
from dharma_swarm.forge_lab.unattended_receipts import (
    UnattendedError,
    _append_chain_locked,
    chain_transaction,
    read_chain,
)

LEDGER_SCHEMA = "rsi_lab.unattended_budget_ledger.v2"

HARD_RUN_LOGICAL_CALLS = 4
HARD_RUN_REQUESTS = 8
HARD_RUN_TOKENS = 32_000
HARD_RUN_USD = 1.0
HARD_RUN_WALL_SECONDS = 3_000
HARD_DAILY_LOGICAL_CALLS = 12
HARD_DAILY_REQUESTS = 24
HARD_DAILY_TOKENS = 96_000
HARD_DAILY_USD = 3.0
HARD_DAILY_WALL_SECONDS = 9_000
HARD_MONTHLY_LOGICAL_CALLS = 120
HARD_MONTHLY_REQUESTS = 240
HARD_MONTHLY_TOKENS = 960_000
HARD_MONTHLY_USD = 30.0
HARD_MONTHLY_WALL_SECONDS = 90_000

PROVIDER_RUN = {
    "logical_calls": 4,
    "requests": 8,
    "tokens": 2_048,
    "usd": 0.04,
    "wall_seconds": 240,
}
PROVIDER_DAILY = {
    "logical_calls": 96,
    "requests": 192,
    "tokens": 49_152,
    "usd": 0.96,
    "wall_seconds": 5_760,
}
PROVIDER_MONTHLY = {
    "logical_calls": 2_976,
    "requests": 5_952,
    "tokens": 1_523_712,
    "usd": 29.76,
    "wall_seconds": 178_560,
}


@dataclass(frozen=True)
class BudgetPolicy:
    """Pinned run, UTC-day, and UTC-month ceilings for every spend dimension."""

    policy_kind: str = "unattended_explore"
    run_usd: float = HARD_RUN_USD
    run_calls: int = HARD_RUN_LOGICAL_CALLS
    run_requests: int = HARD_RUN_REQUESTS
    run_tokens: int = HARD_RUN_TOKENS
    run_wall_seconds: int = HARD_RUN_WALL_SECONDS
    daily_usd: float = HARD_DAILY_USD
    daily_calls: int = HARD_DAILY_LOGICAL_CALLS
    daily_requests: int = HARD_DAILY_REQUESTS
    daily_tokens: int = HARD_DAILY_TOKENS
    daily_wall_seconds: int = HARD_DAILY_WALL_SECONDS
    monthly_usd: float = HARD_MONTHLY_USD
    monthly_calls: int = HARD_MONTHLY_LOGICAL_CALLS
    monthly_requests: int = HARD_MONTHLY_REQUESTS
    monthly_tokens: int = HARD_MONTHLY_TOKENS
    monthly_wall_seconds: int = HARD_MONTHLY_WALL_SECONDS


def _utc_periods(at: str) -> tuple[str, str]:
    from datetime import datetime, timezone

    try:
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UnattendedError("LEDGER_TIME_INVALID", f"invalid UTC time: {at}") from exc
    if instant.tzinfo is None:
        raise UnattendedError("LEDGER_TIME_INVALID", "ledger time must carry a UTC offset")
    instant = instant.astimezone(timezone.utc)
    return instant.strftime("%Y-%m-%d"), instant.strftime("%Y-%m")


def _vector(row: dict[str, Any], field: str) -> dict[str, float | int]:
    value = row.get(field)
    if not isinstance(value, dict):
        raise UnattendedError("BUDGET_LEDGER_SEMANTICS", f"missing {field} vector")
    try:
        integers = {
            name: value[name]
            for name in ("logical_calls", "requests", "tokens", "wall_seconds")
        }
        usd = value["usd"]
    except (KeyError, TypeError) as exc:
        raise UnattendedError("BUDGET_LEDGER_SEMANTICS", f"invalid {field} vector") from exc
    if any(type(amount) is not int for amount in integers.values()):
        raise UnattendedError("BUDGET_LEDGER_SEMANTICS", f"invalid {field} integer")
    if isinstance(usd, bool) or not isinstance(usd, (int, float)) or not math.isfinite(float(usd)):
        raise UnattendedError("BUDGET_LEDGER_SEMANTICS", f"invalid {field} usd")
    vector: dict[str, float | int] = {**integers, "usd": float(usd)}
    if any(amount < 0 for amount in vector.values()):
        raise UnattendedError("BUDGET_LEDGER_SEMANTICS", f"negative {field} vector")
    return vector


def _policy_vectors(policy: BudgetPolicy) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    integer_values = (
        policy.run_calls,
        policy.run_requests,
        policy.run_tokens,
        policy.run_wall_seconds,
        policy.daily_calls,
        policy.daily_requests,
        policy.daily_tokens,
        policy.daily_wall_seconds,
        policy.monthly_calls,
        policy.monthly_requests,
        policy.monthly_tokens,
        policy.monthly_wall_seconds,
    )
    usd_values = (policy.run_usd, policy.daily_usd, policy.monthly_usd)
    if any(type(value) is not int for value in integer_values):
        raise UnattendedError("BUDGET_POLICY_INVALID", "integer caps must be finite integers")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in usd_values
    ):
        raise UnattendedError("BUDGET_POLICY_INVALID", "USD caps must be finite numbers")
    run = {
        "logical_calls": int(policy.run_calls),
        "requests": int(policy.run_requests),
        "tokens": int(policy.run_tokens),
        "usd": float(policy.run_usd),
        "wall_seconds": int(policy.run_wall_seconds),
    }
    daily = {
        "logical_calls": int(policy.daily_calls),
        "requests": int(policy.daily_requests),
        "tokens": int(policy.daily_tokens),
        "usd": float(policy.daily_usd),
        "wall_seconds": int(policy.daily_wall_seconds),
    }
    monthly = {
        "logical_calls": int(policy.monthly_calls),
        "requests": int(policy.monthly_requests),
        "tokens": int(policy.monthly_tokens),
        "usd": float(policy.monthly_usd),
        "wall_seconds": int(policy.monthly_wall_seconds),
    }
    if policy.policy_kind == "provider_selftest_hourly":
        hard_run, hard_daily, hard_monthly = PROVIDER_RUN, PROVIDER_DAILY, PROVIDER_MONTHLY
    elif policy.policy_kind == "unattended_explore":
        hard_run = {
            "logical_calls": HARD_RUN_LOGICAL_CALLS,
            "requests": HARD_RUN_REQUESTS,
            "tokens": HARD_RUN_TOKENS,
            "usd": HARD_RUN_USD,
            "wall_seconds": HARD_RUN_WALL_SECONDS,
        }
        hard_daily = {
            "logical_calls": HARD_DAILY_LOGICAL_CALLS,
            "requests": HARD_DAILY_REQUESTS,
            "tokens": HARD_DAILY_TOKENS,
            "usd": HARD_DAILY_USD,
            "wall_seconds": HARD_DAILY_WALL_SECONDS,
        }
        hard_monthly = {
            "logical_calls": HARD_MONTHLY_LOGICAL_CALLS,
            "requests": HARD_MONTHLY_REQUESTS,
            "tokens": HARD_MONTHLY_TOKENS,
            "usd": HARD_MONTHLY_USD,
            "wall_seconds": HARD_MONTHLY_WALL_SECONDS,
        }
    else:
        raise UnattendedError("BUDGET_POLICY_INVALID", "unknown policy kind")
    if any(run[key] <= 0 or run[key] > hard_run[key] for key in run):
        raise UnattendedError("BUDGET_POLICY_INVALID", "run policy exceeds hard maxima")
    if any(daily[key] <= 0 or daily[key] > hard_daily[key] for key in daily):
        raise UnattendedError("BUDGET_POLICY_INVALID", "daily policy exceeds hard maxima")
    if any(monthly[key] <= 0 or monthly[key] > hard_monthly[key] for key in monthly):
        raise UnattendedError("BUDGET_POLICY_INVALID", "monthly policy exceeds hard maxima")
    if any(run[key] > daily[key] or daily[key] > monthly[key] for key in run):
        raise UnattendedError("BUDGET_POLICY_INVALID", "run/day/month caps are not monotonic")
    return run, daily, monthly


def _reservation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reservations: list[dict[str, Any]] = []
    known: set[str] = set()
    settled: set[str] = set()
    for row in rows:
        kind = row.get("kind")
        if kind == "reservation":
            reserved = _vector(row, "reserved")
            digest = str(row.get("ledger_digest") or "")
            if digest in known:
                raise UnattendedError("BUDGET_LEDGER_SEMANTICS", "duplicate reservation digest")
            known.add(digest)
            reservations.append({**row, "reserved": reserved})
        elif kind == "settlement":
            reservation_digest = str(row.get("reservation_digest") or "")
            _vector(row, "charged")
            if reservation_digest not in known or reservation_digest in settled:
                raise UnattendedError("BUDGET_LEDGER_SEMANTICS", "orphan/duplicate settlement")
            settled.add(reservation_digest)
        elif kind == "reconciliation":
            continue
        else:
            raise UnattendedError("BUDGET_LEDGER_SEMANTICS", f"unsupported ledger row: {kind}")
    return reservations


def reserve_budget(
    ledger_path: Path,
    *,
    run_id: str,
    at: str,
    policy: BudgetPolicy = BudgetPolicy(),
) -> dict[str, Any]:
    """Atomically reserve all dimensions against UTC daily and monthly caps."""

    run_id = validate_safe_id(run_id, field="run_id")
    with chain_transaction(
        ledger_path,
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    ) as rows:
        return _reserve_budget_locked(
            ledger_path,
            rows=rows,
            run_id=run_id,
            at=at,
            policy=policy,
        )


def _reserve_budget_locked(
    ledger_path: Path,
    *,
    rows: list[dict[str, Any]],
    run_id: str,
    at: str,
    policy: BudgetPolicy,
) -> dict[str, Any]:
    """Reserve while the complete read/check/append transaction is locked."""

    reservations = _reservation_rows(rows)
    run, daily_caps, monthly_caps = _policy_vectors(policy)
    if any(row.get("run_id") == run_id for row in reservations):
        raise UnattendedError("BUDGET_DUPLICATE_RUN", f"reservation already exists: {run_id}")
    day, month = _utc_periods(at)
    refusals: list[str] = []
    for period_name, period, caps in (
        ("daily", day, daily_caps),
        ("monthly", month, monthly_caps),
    ):
        selected = [row for row in reservations if row.get("day" if period_name == "daily" else "month") == period]
        for dimension in run:
            observed = sum(row["reserved"][dimension] for row in selected)
            if float(observed) + float(run[dimension]) > float(caps[dimension]) + 1e-9:
                refusals.append(f"{period_name}_{dimension}_reservation_cap")
    if refusals:
        raise UnattendedError("BUDGET_CAP", ",".join(refusals))
    return _append_chain_locked(
        ledger_path,
        {
            "kind": "reservation",
            "at": at,
            "run_id": run_id,
            "day": day,
            "month": month,
            "reserved": run,
            "policy_kind": policy.policy_kind,
            "reserved_usd": run["usd"],
            "reserved_logical_calls": run["logical_calls"],
            "caps": {"daily": daily_caps, "monthly": monthly_caps},
            "accounting_semantics": (
                "conservative multidimensional ceiling; when billing telemetry unavailable, "
                "missing or retry-ambiguous usage is charged at the full reservation"
            ),
        },
        rows=rows,
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )


def settle_budget(
    ledger_path: Path,
    *,
    run_id: str,
    reservation_digest: str,
    at: str,
    observed: dict[str, float | int | None] | None,
    terminal_kind: str,
) -> dict[str, Any]:
    """Settle once; unknown dimensions consume their complete reservation."""

    run_id = validate_safe_id(run_id, field="run_id")
    try:
        reservation_digest = validate_digest(reservation_digest)
    except ValueError as exc:
        raise UnattendedError("BUDGET_RESERVATION_DIGEST_INVALID", reservation_digest) from exc
    if not str(terminal_kind).strip() or len(str(terminal_kind)) > 96:
        raise UnattendedError("BUDGET_TERMINAL_KIND_INVALID", str(terminal_kind))
    with chain_transaction(
        ledger_path,
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    ) as rows:
        return _settle_budget_locked(
            ledger_path,
            rows=rows,
            run_id=run_id,
            reservation_digest=reservation_digest,
            at=at,
            observed=observed,
            terminal_kind=terminal_kind,
        )


def _settle_budget_locked(
    ledger_path: Path,
    *,
    rows: list[dict[str, Any]],
    run_id: str,
    reservation_digest: str,
    at: str,
    observed: dict[str, float | int | None] | None,
    terminal_kind: str,
) -> dict[str, Any]:
    """Idempotently settle under the ledger transaction lock."""

    reservations = _reservation_rows(rows)
    actual = dict(observed or {})
    allowed_dimensions = {"logical_calls", "requests", "tokens", "usd", "wall_seconds"}
    if set(actual) - allowed_dimensions:
        raise UnattendedError("BUDGET_USAGE_INVALID", "unknown usage dimension")
    for dimension, value in actual.items():
        if value is None:
            continue
        if dimension == "usd":
            valid = bool(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and value >= 0
            )
        else:
            valid = type(value) is int and value >= 0
        if not valid:
            raise UnattendedError("BUDGET_USAGE_INVALID", dimension)
    request_digest = content_digest(
        {
            "run_id": run_id,
            "reservation_digest": reservation_digest,
            "terminal_kind": terminal_kind,
            "observed": actual,
        }
    )
    prior = next(
        (row for row in rows if row.get("kind") == "settlement" and row.get("reservation_digest") == reservation_digest),
        None,
    )
    if prior is not None:
        if (
            prior.get("run_id") != run_id
            or prior.get("terminal_kind") != terminal_kind
            or prior.get("settlement_request_digest") != request_digest
        ):
            raise UnattendedError("BUDGET_SETTLEMENT_CONFLICT", run_id)
        return prior
    reservation = next(
        (row for row in reservations if row.get("ledger_digest") == reservation_digest),
        None,
    )
    if reservation is None or reservation.get("run_id") != run_id:
        raise UnattendedError("BUDGET_RESERVATION_MISSING", run_id)
    charged: dict[str, float | int] = {}
    unverifiable: list[str] = []
    overrun: list[str] = []
    for dimension, ceiling in reservation["reserved"].items():
        value = actual.get(dimension)
        if value is None:
            charged[dimension] = ceiling
            unverifiable.append(dimension)
            continue
        if dimension == "usd":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise UnattendedError("BUDGET_USAGE_INVALID", dimension)
            numeric: float | int = float(value)
        else:
            if type(value) is not int:
                raise UnattendedError("BUDGET_USAGE_INVALID", dimension)
            numeric = value
        if numeric < 0:
            raise UnattendedError("BUDGET_USAGE_INVALID", dimension)
        charged[dimension] = min(numeric, ceiling)
        if numeric > ceiling:
            overrun.append(dimension)
    return _append_chain_locked(
        ledger_path,
        {
            "kind": "settlement",
            "at": at,
            "run_id": run_id,
            "reservation_digest": reservation_digest,
            "terminal_kind": terminal_kind,
            "settlement_request_digest": request_digest,
            "observed": actual,
            "charged": charged,
            "unverifiable_dimensions": sorted(unverifiable),
            "overrun_dimensions": sorted(overrun),
            "fail_closed": bool(unverifiable or overrun),
            "accounting_valid": not overrun and not unverifiable,
            "accounting_semantics": "unknown dimensions consume the reserved ceiling; no refund is inferred",
        },
        rows=rows,
        schema=LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )


def budget_status(ledger_path: Path) -> dict[str, Any]:
    rows = read_chain(ledger_path, schema=LEDGER_SCHEMA, digest_field="ledger_digest")
    reservations = _reservation_rows(rows)
    settled = {
        str(row.get("reservation_digest"))
        for row in rows
        if row.get("kind") == "settlement"
    }
    open_rows = [row for row in reservations if row["ledger_digest"] not in settled]
    return {
        "ready": not open_rows,
        "reservation_count": len(reservations),
        "settlement_count": len(settled),
        "open_run_ids": [str(row.get("run_id")) for row in open_rows],
        "last_ledger_digest": rows[-1]["ledger_digest"] if rows else None,
    }


__all__ = [
    "BudgetPolicy",
    "LEDGER_SCHEMA",
    "budget_status",
    "reserve_budget",
    "settle_budget",
]
