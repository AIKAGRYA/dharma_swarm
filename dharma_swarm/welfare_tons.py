"""Auditable welfare-ton scoring and small-portfolio allocation helpers.

This module restores the missing local welfare-ton authority described in the
Jagat Kalyan grant packet. The current implementation is intentionally narrow:
it scores one project with an explicit factor decomposition and plans an exact
subset allocation for bounded pilot portfolios.
"""

from __future__ import annotations

from itertools import combinations
from math import prod
from typing import Sequence

from pydantic import BaseModel, Field


FORMULA = "W = C x E x A x B x V x P"

_FACTOR_LABELS = {
    "carbon_tons": "carbon_tons",
    "employment_factor": "employment_factor",
    "agency_factor": "agency_factor",
    "biodiversity_factor": "biodiversity_factor",
    "verification_factor": "verification_factor",
    "permanence_factor": "permanence_factor",
}


class WelfareTonFactors(BaseModel):
    """Explicit decomposition of the welfare-ton formula."""

    carbon_tons: float = Field(ge=0.0)
    employment_factor: float = Field(ge=0.0)
    agency_factor: float = Field(ge=0.0)
    biodiversity_factor: float = Field(ge=0.0)
    verification_factor: float = Field(ge=0.0)
    permanence_factor: float = Field(ge=0.0)

    def as_dict(self) -> dict[str, float]:
        return {
            "carbon_tons": self.carbon_tons,
            "employment_factor": self.employment_factor,
            "agency_factor": self.agency_factor,
            "biodiversity_factor": self.biodiversity_factor,
            "verification_factor": self.verification_factor,
            "permanence_factor": self.permanence_factor,
        }


class WelfareTonScorecard(BaseModel):
    """Scored welfare-ton output with explicit limiting-factor trace."""

    formula: str = FORMULA
    factors: WelfareTonFactors
    welfare_tons: float = Field(ge=0.0)
    limiting_factor: str
    zero_kill_factors: tuple[str, ...] = Field(default_factory=tuple)
    assumptions: tuple[str, ...] = Field(default_factory=tuple)


class WelfareTonPortfolioCandidate(BaseModel):
    """One restoration option eligible for welfare-ton allocation."""

    project_id: str
    project_name: str
    cost_usd: float = Field(gt=0.0)
    worker_count: int = Field(ge=0)
    geography: str = ""
    project_type: str = ""
    verified: bool = True
    scorecard: WelfareTonScorecard

    @property
    def welfare_tons(self) -> float:
        return self.scorecard.welfare_tons

    @property
    def welfare_per_usd(self) -> float:
        if self.cost_usd <= 0:
            return 0.0
        return self.scorecard.welfare_tons / self.cost_usd


class WelfareTonPortfolioPlan(BaseModel):
    """Exact-subset welfare allocation for a bounded pilot portfolio."""

    objective: str = "maximize_aggregate_welfare_tons_exact_subset"
    budget_usd: float = Field(ge=0.0)
    total_cost_usd: float = Field(ge=0.0)
    total_welfare_tons: float = Field(ge=0.0)
    total_workers: int = Field(ge=0)
    remaining_budget_usd: float = Field(ge=0.0)
    compared_portfolios: int = Field(ge=0)
    selected_projects: tuple[WelfareTonPortfolioCandidate, ...] = Field(
        default_factory=tuple
    )
    excluded_project_ids: tuple[str, ...] = Field(default_factory=tuple)


def score_welfare_tons(
    factors: WelfareTonFactors,
    *,
    assumptions: Sequence[str] | None = None,
) -> WelfareTonScorecard:
    """Evaluate the multiplicative welfare-ton formula with zero-kill tracing."""

    factor_values = factors.as_dict()
    zero_kill_factors = tuple(
        label for label, value in factor_values.items() if value == 0.0
    )
    non_zero = {
        label: value for label, value in factor_values.items() if value > 0.0
    }
    welfare_tons = prod(factor_values.values()) if factor_values else 0.0
    limiting_factor = (
        zero_kill_factors[0]
        if zero_kill_factors
        else min(non_zero, key=non_zero.get, default="carbon_tons")
    )
    return WelfareTonScorecard(
        factors=factors,
        welfare_tons=round(float(welfare_tons), 6),
        limiting_factor=_FACTOR_LABELS.get(limiting_factor, limiting_factor),
        zero_kill_factors=tuple(
            _FACTOR_LABELS.get(label, label) for label in zero_kill_factors
        ),
        assumptions=tuple(item.strip() for item in assumptions or () if item.strip()),
    )


def plan_welfare_portfolio(
    candidates: Sequence[WelfareTonPortfolioCandidate],
    *,
    budget_usd: float,
    max_projects: int | None = None,
    require_verified: bool = True,
) -> WelfareTonPortfolioPlan:
    """Choose the best bounded subset for the current pilot-scale portfolio.

    This uses exact subset search because the shipped GAIA surface currently
    works with a small candidate set. When the ecological portfolio grows
    materially, the same interface can be backed by a linear solver.
    """

    eligible = [
        candidate
        for candidate in candidates
        if candidate.cost_usd <= budget_usd and (candidate.verified or not require_verified)
    ]
    compared = 0
    best_subset: tuple[WelfareTonPortfolioCandidate, ...] = ()
    best_key = (0.0, 0, 0.0)
    limit = min(max_projects or len(eligible), len(eligible))
    for subset_size in range(1, limit + 1):
        for subset in combinations(eligible, subset_size):
            compared += 1
            total_cost = round(sum(item.cost_usd for item in subset), 2)
            if total_cost > budget_usd:
                continue
            total_welfare = round(sum(item.welfare_tons for item in subset), 6)
            total_workers = sum(item.worker_count for item in subset)
            key = (total_welfare, total_workers, -total_cost)
            if key > best_key:
                best_key = key
                best_subset = subset

    total_cost = round(sum(item.cost_usd for item in best_subset), 2)
    total_welfare = round(sum(item.welfare_tons for item in best_subset), 6)
    total_workers = sum(item.worker_count for item in best_subset)
    selected_ids = {item.project_id for item in best_subset}
    excluded = tuple(
        candidate.project_id for candidate in candidates if candidate.project_id not in selected_ids
    )
    return WelfareTonPortfolioPlan(
        budget_usd=budget_usd,
        total_cost_usd=total_cost,
        total_welfare_tons=total_welfare,
        total_workers=total_workers,
        remaining_budget_usd=round(max(budget_usd - total_cost, 0.0), 2),
        compared_portfolios=compared,
        selected_projects=tuple(best_subset),
        excluded_project_ids=excluded,
    )
