"""Tests for the free-model army: budget cap, selection, escalation ratio."""

from __future__ import annotations

import pytest

from dharma_swarm.foundry.army import (
    CONFIG_A_ROSTER,
    ROLE_HARD,
    ROLE_MASS,
    ArmyModel,
    BudgetExceeded,
    MutationBudget,
    escalation_ratio,
    frontier_within_budget,
    select_mutators,
)


def test_free_model_call_cost_is_zero():
    free = ArmyModel("f", ROLE_MASS, "openrouter_free", free=True)
    assert free.call_cost(1000) == 0.0


def test_metered_model_call_cost_positive():
    m = ArmyModel("m", ROLE_HARD, "openrouter", cost_in_per_m=1.0, cost_out_per_m=2.0)
    # (6000/1e6)*1 + (1500/1e6)*2 = 0.006 + 0.003 = 0.009
    assert round(m.call_cost(1), 6) == 0.009


def test_budget_blocks_when_exceeded():
    budget = MutationBudget(cap_usd=0.01)
    expensive = ArmyModel("x", ROLE_HARD, "openrouter", cost_in_per_m=10.0, cost_out_per_m=10.0)
    assert not budget.can_afford(expensive)
    with pytest.raises(BudgetExceeded):
        budget.charge(expensive)


def test_free_models_always_affordable():
    budget = MutationBudget(cap_usd=0.0)
    free = ArmyModel("f", ROLE_MASS, "openrouter_free", free=True)
    assert budget.can_afford(free)
    assert budget.charge(free) == 0.0
    assert budget.free_calls == 1


def test_selection_is_deterministic():
    a = select_mutators("balanced", 20, seed=42)
    b = select_mutators("balanced", 20, seed=42)
    assert [m.id for m in a] == [m.id for m in b]


def test_explore_favors_mass_over_exploit():
    explore = select_mutators("explore", 200, seed=1)
    exploit = select_mutators("exploit", 200, seed=1)
    explore_mass = sum(1 for m in explore if m.role == ROLE_MASS)
    exploit_mass = sum(1 for m in exploit if m.role == ROLE_MASS)
    assert explore_mass > exploit_mass


def test_exploit_escalates_more_than_explore():
    explore = select_mutators("explore", 200, seed=3)
    exploit = select_mutators("exploit", 200, seed=3)
    assert escalation_ratio(exploit) > escalation_ratio(explore)


def test_explore_frontier_within_budget():
    # Explore keeps hard/frontier escalation modest.
    explore = select_mutators("explore", 500, seed=7)
    assert frontier_within_budget(explore, max_ratio=0.20)


def test_roster_has_decorrelated_sources():
    sources = {m.source for m in CONFIG_A_ROSTER}
    # Multiple decorrelated lineages/providers = the ensemble asset.
    assert len(sources) >= 4
    assert any(m.free for m in CONFIG_A_ROSTER)
    assert any(m.frontier for m in CONFIG_A_ROSTER)
