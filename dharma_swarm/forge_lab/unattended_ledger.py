"""Durable append-only chains and spend reservations for unattended runs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from dharma_swarm.forge_lab.state_io import canonical_json, content_digest


class LedgerError(RuntimeError):
    """Internal typed refusal translated by the unattended runner."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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
    try:
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LedgerError("LEDGER_TIME_INVALID", f"invalid UTC time: {at}") from exc
    if instant.tzinfo is None:
        raise LedgerError("LEDGER_TIME_INVALID", "ledger time must carry a UTC offset")
    instant = instant.astimezone(timezone.utc)
    return instant.strftime("%Y-%m-%d"), instant.strftime("%Y-%m")


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
    if any(row.get("run_id") == run_id for row in rows):
        raise LedgerError("BUDGET_DUPLICATE_RUN", f"reservation already exists: {run_id}")
    for row in rows:
        try:
            row_usd = float(row.get("reserved_usd"))
            row_calls = int(row.get("reserved_logical_calls"))
        except (TypeError, ValueError) as exc:
            raise LedgerError("BUDGET_LEDGER_SEMANTICS", "invalid reservation row") from exc
        if (
            row.get("kind") != "reservation"
            or row_usd < 0
            or row_usd > ceilings.run_usd
            or row_calls < 0
            or row_calls > ceilings.run_calls
        ):
            raise LedgerError(
                "BUDGET_LEDGER_SEMANTICS",
                "reservation row outside policy",
            )
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
                "conservative reservation ceiling; provider billing telemetry unavailable; "
                "transport-level retries are not independently metered"
            ),
        },
        schema=ledger_schema,
        digest_field="ledger_digest",
    )


__all__ = [
    "BudgetCeilings",
    "LedgerError",
    "append_chain",
    "chain_digest",
    "read_chain",
    "reserve_budget",
]
