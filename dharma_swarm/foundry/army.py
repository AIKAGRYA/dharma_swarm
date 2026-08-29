"""The free-model army — the mutation operator, sized to a hard budget.

AlphaEvolve uses a Flash+Pro ensemble as its mutation operator; the Foundry
uses a decorrelated army of cheap open-weight models for breadth and escalates
to a strong/frontier model only for archive elites. This module holds the
Config-A roster, the budget ledger that enforces the $300/mo model cap (free
routes cost $0), and the strategy-weighted selection that mixes tiers per
generation. It composes ``dharma_swarm.evolution_roster`` when available (a
guarded import) but stays pure and testable on its own.

Cost unit (from the army scouting report): one mutation call is ~6K tokens in
+ ~1.5K out. These logical roster estimates never authorize a provider call;
the live pool separately requires current account/model tariff evidence and
charges actual or full-liability usage.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# roles
ROLE_MASS = "mass"      # high-volume cheap/free breadth generators
ROLE_MID = "mid"        # mid-cost multi-file / harder diffs
ROLE_HARD = "hard"      # strong models for archive elites
ROLE_JUDGE = "judge"    # fast decorrelated verifier/synth lane

CALL_TOKENS_IN = 6000
CALL_TOKENS_OUT = 1500
DEFAULT_MONTHLY_CAP_USD = 300.0


@dataclass(frozen=True)
class ArmyModel:
    id: str
    role: str
    source: str            # openrouter_free | openrouter | nim | groq | cerebras | subscription
    cost_in_per_m: float = 0.0
    cost_out_per_m: float = 0.0
    free: bool = False
    frontier: bool = False
    notes: str = ""

    def call_cost(self, n_calls: int = 1) -> float:
        if self.free:
            return 0.0
        per = (CALL_TOKENS_IN / 1_000_000) * self.cost_in_per_m + (
            CALL_TOKENS_OUT / 1_000_000
        ) * self.cost_out_per_m
        return per * n_calls


# Config A — all-API roster (army scouting report, 2026-08-18). Costs are the
# metered fallbacks; ``free`` is only a logical selection estimate. IDs are
# logical and do not select or price the actual live provider route.
CONFIG_A_ROSTER: tuple[ArmyModel, ...] = (
    ArmyModel("qwen3-coder-480b:free", ROLE_MASS, "openrouter_free", free=True,
              notes="OpenRouter free tier, 1000 req/day after $10 unlock"),
    ArmyModel("deepseek-v4-flash", ROLE_MASS, "openrouter", 0.0786, 0.1572,
              notes="cheapest capable diff generator"),
    ArmyModel("nemotron-3.5-lightning", ROLE_MASS, "nim", free=True,
              notes="OpenMDW open weights; NIM credits / local; un-banished 2026-08-18"),
    ArmyModel("gpt-oss-120b", ROLE_JUDGE, "groq", free=True,
              notes="Groq/Cerebras free; decorrelated US-lab lineage"),
    ArmyModel("qwen3-coder-next-80b", ROLE_MID, "openrouter", 0.11, 0.80),
    ArmyModel("glm-5", ROLE_HARD, "openrouter", 0.60, 1.92,
              notes="long-horizon / multi-file"),
    ArmyModel("kimi-k2.5", ROLE_MID, "openrouter", 0.45, 2.25),
    ArmyModel("deepseek-v4-pro", ROLE_HARD, "openrouter", 0.27, 1.10),
    ArmyModel("kimi-k3", ROLE_HARD, "openrouter", 2.60, 13.0, frontier=True,
              notes="frontier; near-$0 marginal on Kimi Code membership"),
    ArmyModel("claude-max-oauth", ROLE_JUDGE, "subscription", free=True,
              notes="Claude Max subscription; $0 marginal; synthesis/judge"),
)

# Role weights per selection strategy (mirrors evolution_roster _STRATEGY_PROFILES:
# explore leans free/mass; exploit leans hard/frontier).
_STRATEGY_ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "explore": {ROLE_MASS: 0.55, ROLE_MID: 0.22, ROLE_JUDGE: 0.15, ROLE_HARD: 0.08},
    "balanced": {ROLE_MASS: 0.40, ROLE_MID: 0.28, ROLE_HARD: 0.22, ROLE_JUDGE: 0.10},
    "exploit": {ROLE_MASS: 0.15, ROLE_MID: 0.25, ROLE_HARD: 0.50, ROLE_JUDGE: 0.10},
}


@dataclass
class MutationBudget:
    """Enforce logical roster estimates; live spend has a separate hard gate."""

    cap_usd: float = DEFAULT_MONTHLY_CAP_USD
    spent_usd: float = 0.0
    calls: int = 0
    free_calls: int = 0

    def can_afford(self, model: ArmyModel, n_calls: int = 1) -> bool:
        return model.free or (self.spent_usd + model.call_cost(n_calls)) <= self.cap_usd

    def charge(self, model: ArmyModel, n_calls: int = 1) -> float:
        cost = model.call_cost(n_calls)
        if not model.free and (self.spent_usd + cost) > self.cap_usd:
            raise BudgetExceeded(
                f"charging {model.id} (${cost:.4f}) would exceed cap ${self.cap_usd}"
            )
        self.spent_usd += cost
        self.calls += n_calls
        if model.free:
            self.free_calls += n_calls
        return cost

    def remaining(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def exhausted(self) -> bool:
        return self.remaining() <= 0.0


class BudgetExceeded(RuntimeError):
    """Raised when a metered charge would break the monthly cap."""


def select_mutators(
    strategy: str,
    n: int,
    *,
    roster: tuple[ArmyModel, ...] = CONFIG_A_ROSTER,
    seed: int = 0,
    available_ids: set[str] | None = None,
) -> list[ArmyModel]:
    """Weighted sample of ``n`` mutator models for one generation.

    Deterministic under ``seed``. ``available_ids`` restricts to models whose
    keys/routes are live (fail-open: if None, the whole roster is eligible).
    """
    if strategy not in _STRATEGY_ROLE_WEIGHTS:
        strategy = "balanced"
    weights = _STRATEGY_ROLE_WEIGHTS[strategy]
    pool = [m for m in roster if available_ids is None or m.id in available_ids]
    if not pool:
        return []
    rng = random.Random(seed)
    role_weights = [max(1e-6, weights.get(m.role, 0.02)) for m in pool]
    return rng.choices(pool, weights=role_weights, k=n)


def escalation_ratio(selection: list[ArmyModel]) -> float:
    """Fraction of a selection that are hard/frontier (the escalation lane)."""
    if not selection:
        return 0.0
    strong = sum(1 for m in selection if m.role == ROLE_HARD or m.frontier)
    return strong / len(selection)


def frontier_within_budget(selection: list[ArmyModel], *, max_ratio: float = 0.10) -> bool:
    """True if hard/frontier escalation stays within the target ratio (<=10%)."""
    return escalation_ratio(selection) <= max_ratio


def live_available_ids() -> set[str] | None:
    """Best-effort liveness set from the model pool (guarded; None = fail-open).

    Composes the organism's model pool when importable; otherwise returns None
    so selection falls back to the full roster (never strands the army).
    """
    try:  # pragma: no cover - exercised only with the full stack installed
        from dharma_swarm.model_pool import provider_model_ids  # noqa: PLC0415
        from dharma_swarm.models import ProviderType  # noqa: PLC0415

        ids: set[str] = set()
        for provider in (ProviderType.OPENROUTER_FREE, ProviderType.OPENROUTER):
            for mid in provider_model_ids(provider):
                ids.add(mid)
        return ids or None
    except Exception:
        return None
