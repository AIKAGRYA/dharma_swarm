"""Durable append-only chains and spend reservations for unattended runs."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from dharma_swarm.forge_lab.state_io import (
    canonical_json,
    content_digest,
    validate_digest,
)


class LedgerError(RuntimeError):
    """Internal typed refusal translated by the unattended runner."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        receipt: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.receipt = receipt


class ReservationPolicy(Protocol):
    run_usd: float
    run_calls: int
    daily_usd: float
    monthly_usd: float
    daily_calls: int
    monthly_calls: int


@dataclass(frozen=True)
class BudgetCeilings:
    run_usd: float
    run_calls: int
    daily_usd: float
    monthly_usd: float
    daily_calls: int
    monthly_calls: int


def chain_digest(payload: dict[str, Any], digest_field: str) -> str:
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
        raise LedgerError("CHAIN_PATH_UNSAFE", f"unsafe chain path: {path}")
    if path.stat().st_mode & 0o077:
        raise LedgerError("CHAIN_MODE_UNSAFE", f"chain must be owner-only: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LedgerError("CHAIN_UNREADABLE", f"cannot read {path}: {exc}") from exc
    if len(raw) > 16 * 1024 * 1024:
        raise LedgerError("CHAIN_TOO_LARGE", f"chain exceeds 16 MiB: {path}")
    if raw and not raw.endswith(b"\n"):
        raise LedgerError("CHAIN_TRUNCATED", f"chain lacks final newline: {path}")
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    for index, line in enumerate(raw.splitlines(), start=1):
        try:
            row = json.loads(line)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise LedgerError(
                "CHAIN_MALFORMED",
                f"invalid JSON at {path}:{index}",
            ) from exc
        if not isinstance(row, dict):
            raise LedgerError("CHAIN_MALFORMED", f"non-object at {path}:{index}")
        if row.get("schema") != schema or row.get("sequence") != index:
            raise LedgerError(
                "CHAIN_SEQUENCE",
                f"schema/sequence mismatch at {path}:{index}",
            )
        if row.get("previous_digest") != previous:
            raise LedgerError(
                "CHAIN_PREVIOUS",
                f"previous digest mismatch at {path}:{index}",
            )
        if row.get(digest_field) != chain_digest(row, digest_field):
            raise LedgerError("CHAIN_DIGEST", f"digest mismatch at {path}:{index}")
        previous = str(row[digest_field])
        rows.append(row)
    return rows


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def append_chain(
    path: Path,
    payload: dict[str, Any],
    *,
    schema: str,
    digest_field: str,
) -> dict[str, Any]:
    """Verify, append, and durably commit one chain row and its directory entry."""

    rows = read_chain(path, schema=schema, digest_field=digest_field)
    row = {
        **payload,
        "schema": schema,
        "sequence": len(rows) + 1,
        "previous_digest": rows[-1][digest_field] if rows else None,
    }
    row[digest_field] = chain_digest(row, digest_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "ab", closefd=True) as handle:
            handle.write(canonical_json(row) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except OSError as exc:
        raise LedgerError("CHAIN_DURABILITY", f"cannot durably append {path}: {exc}") from exc
    return row


def _utc_periods(at: str) -> tuple[str, str]:
    instant = _utc_instant(at)
    return instant.strftime("%Y-%m-%d"), instant.strftime("%Y-%m")


def _utc_instant(at: str) -> datetime:
    try:
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise LedgerError("LEDGER_TIME_INVALID", f"invalid UTC time: {at}") from exc
    if instant.tzinfo is None:
        raise LedgerError("LEDGER_TIME_INVALID", "ledger time must carry a UTC offset")
    return instant.astimezone(timezone.utc)


def _reservation_rows(
    rows: list[dict[str, Any]],
    *,
    ceilings: BudgetCeilings,
) -> list[dict[str, Any]]:
    reservations: list[dict[str, Any]] = []
    for row in rows:
        kind = row.get("kind")
        if kind == "reconciliation":
            if (
                not isinstance(row.get("reconciliation_key"), str)
                or row.get("decision") not in {"accepted", "rejected_overshoot"}
                or row.get("incremental_charge_usd") != 0.0
            ):
                raise LedgerError(
                    "BUDGET_LEDGER_SEMANTICS",
                    "invalid reconciliation row",
                )
            continue
        if kind != "reservation":
            raise LedgerError(
                "BUDGET_LEDGER_SEMANTICS",
                f"unknown budget row kind: {kind!r}",
            )
        try:
            row_usd = float(row.get("reserved_usd"))
            row_calls = int(row.get("reserved_logical_calls"))
        except (TypeError, ValueError) as exc:
            raise LedgerError(
                "BUDGET_LEDGER_SEMANTICS",
                "invalid reservation row",
            ) from exc
        if (
            isinstance(row.get("reserved_usd"), bool)
            or isinstance(row.get("reserved_logical_calls"), bool)
            or not math.isfinite(row_usd)
            or row_usd < 0
            or row_usd > ceilings.run_usd
            or row_calls < 0
            or row_calls > ceilings.run_calls
        ):
            raise LedgerError(
                "BUDGET_LEDGER_SEMANTICS",
                "reservation row outside policy",
            )
        reservations.append(row)
    return reservations


def reserve_budget(
    ledger_path: Path,
    *,
    run_id: str,
    at: str,
    policy: ReservationPolicy,
    ceilings: BudgetCeilings,
    ledger_schema: str,
) -> dict[str, Any]:
    """Reserve the full run ceiling against UTC daily and monthly caps."""

    rows = read_chain(
        ledger_path,
        schema=ledger_schema,
        digest_field="ledger_digest",
    )
    if not (
        0 < policy.run_usd <= ceilings.run_usd
        and 0 < policy.run_calls <= ceilings.run_calls
        and 0 < policy.daily_usd <= ceilings.daily_usd
        and 0 < policy.monthly_usd <= ceilings.monthly_usd
        and 0 < policy.daily_calls <= ceilings.daily_calls
        and 0 < policy.monthly_calls <= ceilings.monthly_calls
    ):
        raise LedgerError("BUDGET_POLICY_INVALID", "policy exceeds hard-coded maxima")
    reservations = _reservation_rows(rows, ceilings=ceilings)
    if any(row.get("run_id") == run_id for row in reservations):
        raise LedgerError("BUDGET_DUPLICATE_RUN", f"reservation already exists: {run_id}")
    day, month = _utc_periods(at)
    daily = [row for row in reservations if row.get("day") == day]
    monthly = [row for row in reservations if row.get("month") == month]
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
        raise LedgerError("BUDGET_CAP", ",".join(refusals))
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
                "conservative reservation ceiling; billing telemetry unavailable "
                "until a later reconciliation row; reconciliation never refunds or "
                "adds a second charge and records actual provider cost and retry "
                "completeness explicitly"
            ),
        },
        schema=ledger_schema,
        digest_field="ledger_digest",
    )


def reconcile_budget(
    ledger_path: Path,
    *,
    run_id: str,
    at: str,
    actual_cost_usd: float | None,
    cost_completeness: str,
    observed_logical_calls: int,
    logical_calls_complete: bool,
    transport_retry_count: int | None,
    transport_retries_complete: bool,
    cost_includes_transport_retries: bool,
    evidence_digest: str,
    ceilings: BudgetCeilings,
    ledger_schema: str,
) -> dict[str, Any]:
    """Reconcile one reservation without charging or refunding it again.

    Replaying byte-equivalent evidence returns the existing row. A conflicting
    replay fails closed. Overshoot is durably receipted before rejection so the
    invalid result cannot disappear behind an exception.
    """

    rows = read_chain(
        ledger_path,
        schema=ledger_schema,
        digest_field="ledger_digest",
    )
    reservations = _reservation_rows(rows, ceilings=ceilings)
    matches = [row for row in reservations if row.get("run_id") == run_id]
    if len(matches) != 1:
        raise LedgerError(
            "BUDGET_RESERVATION_MISSING",
            f"exactly one reservation is required: {run_id}",
        )
    reservation = matches[0]
    reconcile_at = _utc_instant(at)
    reservation_at = _utc_instant(str(reservation.get("at") or ""))
    if reconcile_at < reservation_at:
        raise LedgerError(
            "BUDGET_RECONCILIATION_TIME",
            "reconciliation precedes reservation",
        )
    if cost_completeness not in {"complete", "unavailable", "ambiguous"}:
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            f"unknown cost completeness: {cost_completeness!r}",
        )
    if type(logical_calls_complete) is not bool:
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "logical_calls_complete must be boolean",
        )
    if (
        type(observed_logical_calls) is not int
        or observed_logical_calls < 0
    ):
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "observed_logical_calls must be a nonnegative integer",
        )
    if type(transport_retries_complete) is not bool:
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "transport_retries_complete must be boolean",
        )
    if (
        transport_retry_count is not None
        and (
            type(transport_retry_count) is not int
            or transport_retry_count < 0
        )
    ):
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "transport_retry_count must be null or a nonnegative integer",
        )
    if transport_retries_complete and transport_retry_count is None:
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "complete retry accounting requires transport_retry_count",
        )
    if type(cost_includes_transport_retries) is not bool:
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "cost_includes_transport_retries must be boolean",
        )
    if cost_completeness == "complete":
        if (
            actual_cost_usd is None
            or isinstance(actual_cost_usd, bool)
            or not isinstance(actual_cost_usd, (int, float))
            or not math.isfinite(float(actual_cost_usd))
            or float(actual_cost_usd) < 0
        ):
            raise LedgerError(
                "BUDGET_RECONCILIATION_INVALID",
                "complete cost must be finite and nonnegative",
            )
        if not cost_includes_transport_retries:
            raise LedgerError(
                "BUDGET_RECONCILIATION_INVALID",
                "complete cost must include transport retries",
            )
        normalized_cost: float | None = round(float(actual_cost_usd), 9)
    else:
        if actual_cost_usd is not None:
            raise LedgerError(
                "BUDGET_RECONCILIATION_INVALID",
                "incomplete cost must be null",
            )
        normalized_cost = None
    try:
        evidence_digest = validate_digest(evidence_digest)
    except ValueError as exc:
        raise LedgerError(
            "BUDGET_RECONCILIATION_INVALID",
            "evidence_digest must be a sha256 digest",
        ) from exc

    reserved_usd = float(reservation["reserved_usd"])
    reserved_calls = int(reservation["reserved_logical_calls"])
    overshoot_reasons: list[str] = []
    if normalized_cost is not None and normalized_cost > reserved_usd + 1e-9:
        overshoot_reasons.append("actual_cost_exceeds_reservation")
    if observed_logical_calls > reserved_calls:
        overshoot_reasons.append("logical_calls_exceed_reservation")
    decision = "rejected_overshoot" if overshoot_reasons else "accepted"
    semantic = {
        "run_id": run_id,
        "reservation_digest": reservation["ledger_digest"],
        "actual_cost_usd": normalized_cost,
        "cost_completeness": cost_completeness,
        "observed_logical_calls": observed_logical_calls,
        "logical_calls_complete": logical_calls_complete,
        "transport_retry_count": transport_retry_count,
        "transport_retries_complete": transport_retries_complete,
        "cost_includes_transport_retries": cost_includes_transport_retries,
        "evidence_digest": evidence_digest,
        "decision": decision,
        "overshoot_reasons": overshoot_reasons,
    }
    reconciliation_key = content_digest(semantic)
    existing = [
        row
        for row in rows
        if row.get("kind") == "reconciliation"
        and row.get("run_id") == run_id
    ]
    if existing:
        if len(existing) != 1 or existing[0].get("reconciliation_key") != reconciliation_key:
            raise LedgerError(
                "BUDGET_RECONCILIATION_CONFLICT",
                f"conflicting reconciliation already exists: {run_id}",
            )
        row = existing[0]
        if row.get("decision") == "rejected_overshoot":
            raise LedgerError(
                "BUDGET_ACTUAL_OVERSHOOT",
                ",".join(row.get("overshoot_reasons") or []),
                receipt=row,
            )
        return row

    row = append_chain(
        ledger_path,
        {
            "kind": "reconciliation",
            "at": at,
            **semantic,
            "reconciliation_key": reconciliation_key,
            "reserved_usd": reserved_usd,
            "reserved_logical_calls": reserved_calls,
            "effective_governed_cost_usd": reserved_usd,
            "incremental_charge_usd": 0.0,
            "reservation_refunded": False,
            "accounting_semantics": (
                "the reservation remains consumed; reconciliation records actual "
                "usage and completeness without charging or refunding again"
            ),
        },
        schema=ledger_schema,
        digest_field="ledger_digest",
    )
    if overshoot_reasons:
        raise LedgerError(
            "BUDGET_ACTUAL_OVERSHOOT",
            ",".join(overshoot_reasons),
            receipt=row,
        )
    return row


__all__ = [
    "BudgetCeilings",
    "LedgerError",
    "append_chain",
    "chain_digest",
    "read_chain",
    "reconcile_budget",
    "reserve_budget",
]
