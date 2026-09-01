from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.forge_lab import unattended_explore as unattended


def test_ac_02_usage_and_price(tmp_path: Path) -> None:
    """AC-02: cost/calls/retries reconcile once, including unknown usage."""

    ledger = tmp_path / "budget.jsonl"
    complete_reservation = unattended.reserve_budget(
        ledger,
        run_id="complete-run",
        at="2026-08-25T00:00:00Z",
    )
    complete = unattended.reconcile_budget(
        ledger,
        run_id="complete-run",
        at="2026-08-25T00:01:00Z",
        actual_cost_usd=0.83,
        cost_completeness="complete",
        observed_logical_calls=unattended.LOGICAL_PROVIDER_CALL_SLOTS,
        logical_calls_complete=True,
        transport_retry_count=2,
        transport_retries_complete=True,
        cost_includes_transport_retries=True,
        evidence_digest="sha256:" + "a" * 64,
    )
    replay = unattended.reconcile_budget(
        ledger,
        run_id="complete-run",
        at="2026-08-25T00:01:00Z",
        actual_cost_usd=0.83,
        cost_completeness="complete",
        observed_logical_calls=unattended.LOGICAL_PROVIDER_CALL_SLOTS,
        logical_calls_complete=True,
        transport_retry_count=2,
        transport_retries_complete=True,
        cost_includes_transport_retries=True,
        evidence_digest="sha256:" + "a" * 64,
    )
    assert replay["ledger_digest"] == complete["ledger_digest"]
    assert complete["reservation_digest"] == complete_reservation["ledger_digest"]
    assert complete["actual_cost_usd"] == 0.83
    assert complete["transport_retry_count"] == 2
    assert complete["cost_includes_transport_retries"] is True
    assert complete["effective_governed_cost_usd"] == unattended.RUN_USD_RESERVATION
    assert complete["incremental_charge_usd"] == 0.0
    assert complete["reservation_refunded"] is False

    ambiguous_reservation = unattended.reserve_budget(
        ledger,
        run_id="ambiguous-run",
        at="2026-08-26T00:00:00Z",
    )
    ambiguous = unattended.reconcile_budget(
        ledger,
        run_id="ambiguous-run",
        at="2026-08-26T00:01:00Z",
        actual_cost_usd=None,
        cost_completeness="ambiguous",
        observed_logical_calls=3,
        logical_calls_complete=False,
        transport_retry_count=None,
        transport_retries_complete=False,
        cost_includes_transport_retries=False,
        evidence_digest="sha256:" + "b" * 64,
    )
    assert ambiguous["reservation_digest"] == ambiguous_reservation["ledger_digest"]
    assert ambiguous["actual_cost_usd"] is None
    assert ambiguous["cost_completeness"] == "ambiguous"
    assert ambiguous["logical_calls_complete"] is False
    assert ambiguous["transport_retries_complete"] is False
    assert ambiguous["effective_governed_cost_usd"] == unattended.RUN_USD_RESERVATION
    assert ambiguous["incremental_charge_usd"] == 0.0

    rows = unattended.read_chain(
        ledger,
        schema=unattended.LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )
    assert [row["kind"] for row in rows] == [
        "reservation",
        "reconciliation",
        "reservation",
        "reconciliation",
    ]

    overshoot_ledger = tmp_path / "overshoot.jsonl"
    unattended.reserve_budget(
        overshoot_ledger,
        run_id="overshoot-run",
        at="2026-08-25T00:00:00Z",
    )
    with pytest.raises(unattended.UnattendedError) as overshoot:
        unattended.reconcile_budget(
            overshoot_ledger,
            run_id="overshoot-run",
            at="2026-08-25T00:01:00Z",
            actual_cost_usd=unattended.RUN_USD_RESERVATION + 0.01,
            cost_completeness="complete",
            observed_logical_calls=unattended.LOGICAL_PROVIDER_CALL_SLOTS,
            logical_calls_complete=True,
            transport_retry_count=0,
            transport_retries_complete=True,
            cost_includes_transport_retries=True,
            evidence_digest="sha256:" + "c" * 64,
        )
    assert overshoot.value.code == "BUDGET_ACTUAL_OVERSHOOT"
    assert overshoot.value.receipt["decision"] == "rejected_overshoot"
    assert overshoot.value.receipt["incremental_charge_usd"] == 0.0
