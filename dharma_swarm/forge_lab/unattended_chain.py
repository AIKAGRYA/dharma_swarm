"""Append-only hash-chain, budget-reservation, and host-lock primitives.

Split out of ``unattended_explore`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.forge_lab.unattended_ledger import (
    BudgetCeilings,
    LedgerError,
    append_chain as _ledger_append_chain,
    chain_digest as _ledger_chain_digest,
    read_chain as _ledger_read_chain,
    reserve_budget as _ledger_reserve_budget,
)
from dharma_swarm.forge_lab.unattended_policy import (
    DAILY_CALL_CAP,
    DAILY_USD_CAP,
    LEDGER_SCHEMA,
    LOGICAL_PROVIDER_CALL_SLOTS,
    MONTHLY_CALL_CAP,
    MONTHLY_USD_CAP,
    RUN_USD_RESERVATION,
    BudgetPolicy,
    UnattendedError,
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
