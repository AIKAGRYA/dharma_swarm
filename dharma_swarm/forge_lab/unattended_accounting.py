"""Budget reconciliation bridge for the bounded unattended runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_lab.unattended_ledger import (
    BudgetCeilings,
    LedgerError,
    reconcile_budget as _reconcile_budget,
)
from dharma_swarm.forge_lab.unattended_policy import (
    DAILY_CALL_CAP,
    DAILY_USD_CAP,
    LEDGER_SCHEMA,
    LOGICAL_PROVIDER_CALL_SLOTS,
    MONTHLY_CALL_CAP,
    MONTHLY_USD_CAP,
    RUN_USD_RESERVATION,
    UnattendedError,
)


@dataclass(frozen=True)
class RunBudgetReconciliation:
    row: dict[str, Any]
    error_code: str | None


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
) -> dict[str, Any]:
    """Record actual usage without refunding or charging the reservation twice."""

    try:
        return _reconcile_budget(
            ledger_path,
            run_id=run_id,
            at=at,
            actual_cost_usd=actual_cost_usd,
            cost_completeness=cost_completeness,
            observed_logical_calls=observed_logical_calls,
            logical_calls_complete=logical_calls_complete,
            transport_retry_count=transport_retry_count,
            transport_retries_complete=transport_retries_complete,
            cost_includes_transport_retries=cost_includes_transport_retries,
            evidence_digest=evidence_digest,
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
        raise UnattendedError(
            exc.code,
            str(exc),
            receipt=exc.receipt,
        ) from exc


def unavailable_usage_accounting(
    observed_logical_calls: int,
    *,
    logical_calls_complete: bool,
) -> dict[str, Any]:
    return {
        "schema": "rsi_lab.usage_accounting.v1",
        "actual_cost_usd": None,
        "cost_completeness": "unavailable",
        "observed_logical_calls": observed_logical_calls,
        "logical_calls_complete": logical_calls_complete,
        "transport_retry_count": None,
        "transport_retries_complete": False,
        "cost_includes_transport_retries": False,
    }


def reconcile_run_budget(
    ledger_path: Path,
    *,
    run_id: str,
    at: str,
    child: dict[str, Any] | None,
    log_digest: str,
) -> RunBudgetReconciliation:
    usage = (
        child.get("usage_accounting")
        if isinstance((child or {}).get("usage_accounting"), dict)
        else {}
    )
    try:
        row = reconcile_budget(
            ledger_path,
            run_id=run_id,
            at=at,
            actual_cost_usd=usage.get("actual_cost_usd"),
            cost_completeness=str(
                usage.get("cost_completeness")
                or ("unavailable" if child else "ambiguous")
            ),
            observed_logical_calls=int(
                usage.get("observed_logical_calls") if child else 0
            ),
            logical_calls_complete=bool(
                usage.get("logical_calls_complete") if child else False
            ),
            transport_retry_count=usage.get("transport_retry_count"),
            transport_retries_complete=bool(
                usage.get("transport_retries_complete") if child else False
            ),
            cost_includes_transport_retries=bool(
                usage.get("cost_includes_transport_retries") if child else False
            ),
            evidence_digest=content_digest(child) if child else log_digest,
        )
    except UnattendedError as exc:
        return RunBudgetReconciliation(
            row=dict(exc.receipt or {}),
            error_code=exc.code,
        )
    return RunBudgetReconciliation(row=row, error_code=None)


__all__ = [
    "RunBudgetReconciliation",
    "reconcile_budget",
    "reconcile_run_budget",
    "unavailable_usage_accounting",
]
