from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import unattended_explore as unattended

EVIDENCE = "sha256:" + "e" * 64


def _reserve(path: Path, *, run_id: str = "run-one", at: str = "2026-08-25T00:00:00Z"):
    return unattended.reserve_budget(path, run_id=run_id, at=at)


def _reconcile(path: Path, **overrides):
    values = {
        "run_id": "run-one",
        "at": "2026-08-25T00:01:00Z",
        "actual_cost_usd": 0.75,
        "cost_completeness": "complete",
        "observed_logical_calls": unattended.LOGICAL_PROVIDER_CALL_SLOTS,
        "logical_calls_complete": True,
        "transport_retry_count": 1,
        "transport_retries_complete": True,
        "cost_includes_transport_retries": True,
        "evidence_digest": EVIDENCE,
    }
    values.update(overrides)
    return unattended.reconcile_budget(path, **values)


def _rows(path: Path) -> list[dict]:
    return unattended.read_chain(
        path,
        schema=unattended.LEDGER_SCHEMA,
        digest_field="ledger_digest",
    )


def test_complete_actual_cost_reconciles_without_second_charge_or_refund(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "budget.jsonl"
    reservation = _reserve(ledger)

    reconciliation = _reconcile(ledger)
    replay = _reconcile(ledger)

    assert reconciliation == replay
    assert reconciliation["reservation_digest"] == reservation["ledger_digest"]
    assert reconciliation["actual_cost_usd"] == 0.75
    assert reconciliation["cost_completeness"] == "complete"
    assert reconciliation["observed_logical_calls"] == 5
    assert reconciliation["transport_retry_count"] == 1
    assert reconciliation["decision"] == "accepted"
    assert reconciliation["effective_governed_cost_usd"] == 1.25
    assert reconciliation["incremental_charge_usd"] == 0.0
    assert reconciliation["reservation_refunded"] is False
    assert [row["kind"] for row in _rows(ledger)] == [
        "reservation",
        "reconciliation",
    ]


def test_unavailable_cost_is_typed_null_and_keeps_conservative_reservation(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "budget.jsonl"
    _reserve(ledger)

    row = _reconcile(
        ledger,
        actual_cost_usd=None,
        cost_completeness="unavailable",
        observed_logical_calls=3,
        logical_calls_complete=False,
        transport_retry_count=None,
        transport_retries_complete=False,
        cost_includes_transport_retries=False,
    )

    assert row["actual_cost_usd"] is None
    assert row["cost_completeness"] == "unavailable"
    assert row["logical_calls_complete"] is False
    assert row["effective_governed_cost_usd"] == 1.25
    assert row["incremental_charge_usd"] == 0.0


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"actual_cost_usd": 1.25000001}, "actual_cost_exceeds_reservation"),
        ({"observed_logical_calls": 6}, "logical_calls_exceed_reservation"),
    ],
)
def test_actual_overshoot_is_durably_receipted_then_rejected_idempotently(
    tmp_path: Path,
    overrides: dict,
    reason: str,
) -> None:
    ledger = tmp_path / "budget.jsonl"
    _reserve(ledger)

    with pytest.raises(unattended.UnattendedError) as first:
        _reconcile(ledger, **overrides)
    assert first.value.code == "BUDGET_ACTUAL_OVERSHOOT"
    assert first.value.receipt is not None
    assert first.value.receipt["decision"] == "rejected_overshoot"
    assert reason in first.value.receipt["overshoot_reasons"]

    with pytest.raises(unattended.UnattendedError) as replay:
        _reconcile(ledger, **overrides)
    assert replay.value.code == "BUDGET_ACTUAL_OVERSHOOT"
    assert replay.value.receipt["ledger_digest"] == first.value.receipt["ledger_digest"]
    assert len(_rows(ledger)) == 2


def test_conflicting_reconciliation_cannot_rebind_one_run(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.jsonl"
    _reserve(ledger)
    _reconcile(ledger, actual_cost_usd=0.50)

    with pytest.raises(unattended.UnattendedError) as error:
        _reconcile(ledger, actual_cost_usd=0.51)

    assert error.value.code == "BUDGET_RECONCILIATION_CONFLICT"
    assert len(_rows(ledger)) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_cost_usd": -0.01},
        {"actual_cost_usd": math.inf},
        {"actual_cost_usd": True},
        {"actual_cost_usd": 0.1, "cost_completeness": "unavailable"},
        {"actual_cost_usd": None, "cost_completeness": "complete"},
        {"cost_includes_transport_retries": False},
        {"observed_logical_calls": True},
        {"observed_logical_calls": -1},
        {"logical_calls_complete": 1},
        {"transport_retry_count": -1},
        {"transport_retries_complete": True, "transport_retry_count": None},
        {"evidence_digest": "not-a-digest"},
    ],
)
def test_invalid_reconciliation_is_non_mutating(
    tmp_path: Path,
    overrides: dict,
) -> None:
    ledger = tmp_path / "budget.jsonl"
    _reserve(ledger)

    with pytest.raises(unattended.UnattendedError) as error:
        _reconcile(ledger, **overrides)

    assert error.value.code == "BUDGET_RECONCILIATION_INVALID"
    assert len(_rows(ledger)) == 1


def test_reconciliation_requires_reservation_and_cannot_precede_it(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "budget.jsonl"
    with pytest.raises(unattended.UnattendedError) as missing:
        _reconcile(ledger)
    assert missing.value.code == "BUDGET_RESERVATION_MISSING"

    _reserve(ledger, at="2026-08-25T00:02:00Z")
    with pytest.raises(unattended.UnattendedError) as early:
        _reconcile(ledger, at="2026-08-25T00:01:00Z")
    assert early.value.code == "BUDGET_RECONCILIATION_TIME"
    assert len(_rows(ledger)) == 1


def test_reconciliation_rows_do_not_count_against_later_reservations(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "budget.jsonl"
    _reserve(ledger)
    _reconcile(ledger)

    second = _reserve(
        ledger,
        run_id="run-two",
        at="2026-08-25T00:02:00Z",
    )

    assert second["sequence"] == 3
    assert [row["kind"] for row in _rows(ledger)] == [
        "reservation",
        "reconciliation",
        "reservation",
    ]


def test_reconciliation_chain_tampering_is_detected(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.jsonl"
    _reserve(ledger)
    _reconcile(ledger)
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    rows[1]["actual_cost_usd"] = 0.01
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(unattended.UnattendedError) as error:
        unattended.read_chain(
            ledger,
            schema=unattended.LEDGER_SCHEMA,
            digest_field="ledger_digest",
        )

    assert error.value.code == "CHAIN_DIGEST"
