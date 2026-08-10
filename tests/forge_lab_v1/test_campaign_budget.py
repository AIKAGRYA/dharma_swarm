from __future__ import annotations

import json
from decimal import Decimal

import pytest

from dharma_swarm.forge_lab.campaign_budget import (
    CampaignBudgetConflict,
    CampaignBudgetError,
    CampaignBudgetExceeded,
    CampaignBudgetLedger,
    CampaignBudgetSettlementError,
    INVALID,
    SETTLED,
)


def test_reservation_refuses_dispatch_before_provider_call() -> None:
    budget = CampaignBudgetLedger(cap_tokens=100, cap_usd="1.00")
    budget.reserve("mutation", max_tokens=80, max_usd="0.50", operation_id="mut-1")
    provider_calls = 0

    with pytest.raises(CampaignBudgetExceeded, match="remaining=20"):
        budget.reserve("candidate_eval", max_tokens=21, operation_id="eval-1")
        provider_calls += 1

    assert provider_calls == 0
    assert budget.reserved_tokens == 80
    assert budget.spent_tokens == 0


def test_settlement_releases_capacity_and_accounts_mutation_component() -> None:
    budget = CampaignBudgetLedger(cap_tokens=100, cap_usd="2")
    first = budget.reserve("mutation", max_tokens=60, max_usd="1", operation_id="mut-1")
    assert budget.reserve("mutation", max_tokens=60, max_usd="1", operation_id="mut-1") == first
    settled = budget.settle("mut-1", actual_tokens=25, actual_usd="0.20")

    assert settled.status == SETTLED
    assert budget.spent_tokens == 25
    assert budget.remaining_tokens == 75
    budget.reserve("candidate_eval", max_tokens=75, max_usd="1.80", operation_id="eval-1")
    budget.settle("eval-1", actual_tokens=70, actual_usd="1.25")
    totals = budget.component_totals()
    assert totals["mutation"]["spent_tokens"] == 25
    assert totals["candidate_eval"]["spent_tokens"] == 70
    assert sum(row["spent_tokens"] for row in totals.values()) == budget.spent_tokens == 95
    assert budget.spent_usd == Decimal("1.45")
    assert budget.valid is True


def test_usage_above_reserved_ceiling_invalidates_campaign() -> None:
    budget = CampaignBudgetLedger(cap_tokens=100)
    budget.reserve("baseline_eval", max_tokens=20, operation_id="base-1")

    with pytest.raises(CampaignBudgetSettlementError, match="tokens:21>20"):
        budget.settle("base-1", actual_tokens=21)

    assert budget.reservation("base-1").status == INVALID
    assert budget.valid is False
    with pytest.raises(CampaignBudgetError, match="new dispatches are forbidden"):
        budget.reserve("candidate_eval", max_tokens=1)


def test_budget_round_trip_reconstructs_and_detects_tampering(tmp_path) -> None:
    path = tmp_path / "campaign_budget.json"
    budget = CampaignBudgetLedger(cap_tokens=100, cap_usd="1.5")
    budget.reserve("mutation", max_tokens=30, max_usd="0.4", operation_id="mut-1")
    budget.settle("mut-1", actual_tokens=12, actual_usd="0.1")
    budget.reserve("confirm_eval", max_tokens=50, max_usd="0.8", operation_id="confirm-1")
    budget.save(path)

    loaded = CampaignBudgetLedger.load(path)
    assert loaded.to_dict() == budget.to_dict()
    assert loaded.remaining_tokens == 38

    tampered = json.loads(path.read_text())
    tampered["spent_tokens"] = 0
    path.write_text(json.dumps(tampered))
    with pytest.raises(CampaignBudgetError, match="digest mismatch"):
        CampaignBudgetLedger.load(path)


def test_operation_id_cannot_be_reused_with_changed_terms() -> None:
    budget = CampaignBudgetLedger(cap_tokens=100)
    budget.reserve("mutation", max_tokens=10, operation_id="same")
    with pytest.raises(CampaignBudgetError, match="different reservation terms"):
        budget.reserve("candidate_eval", max_tokens=10, operation_id="same")


def test_persisted_budget_uses_file_lock_and_compare_and_swap(tmp_path) -> None:
    path = tmp_path / "campaign_budget.json"
    initial = CampaignBudgetLedger(cap_tokens=100)
    initial.save(path)
    first = CampaignBudgetLedger.load(path)
    stale = CampaignBudgetLedger.load(path)

    first.reserve("mutation", max_tokens=60, operation_id="first")
    first.save(path)
    stale.reserve("candidate_eval", max_tokens=60, operation_id="stale")
    with pytest.raises(CampaignBudgetConflict, match="changed since"):
        stale.save(path)

    persisted = CampaignBudgetLedger.load(path)
    assert persisted.reserved_tokens == 60
    assert persisted.reservation("first") is not None
    assert persisted.reservation("stale") is None
