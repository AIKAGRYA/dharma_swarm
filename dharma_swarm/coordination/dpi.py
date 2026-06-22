"""Dharma Power Index (spec §5) — capability in the numerator, trust as multiplier.

    DPI = VerifiedCapabilityDelta x Trust x ReuseOrLearningValue
          / (Cost x Latency x Fragility x Complexity)

Load-bearing invariants enforced here (spec §4, §5, §6):
  * VerifiedCapabilityDelta is the headline: error-reduction vs best-single-at-
    budget, plus a correctness-GATED decorrelation bonus (§4).
  * The decorrelation bonus is `leave_one_out_marginal_contribution x
    nonredundancy x final_correctness_gate`; if the final outcome is wrong the
    bonus is <= 0 (never rewards debate theater on a wrong answer).
  * Trust is a MULTIPLIER in [0, 1], never the numerator (§5, §6.6).
  * ReuseOrLearningValue is RETROACTIVE-ONLY: logged but NOT active in ranking
    yet (``activate_learning=False`` by default, §5, §6.9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_EPS = 1e-9


@dataclass(frozen=True)
class DPIInputs:
    """Everything the DPI needs, separated by role in the formula."""

    # capability
    candidate_score: float
    best_single_score: float
    final_correct: bool  # did the final outcome pass the oracle? (the gate)
    # decorrelation (§4): per-role contributions, correctness-gated
    loo_marginal_contributions: dict[str, float] = field(default_factory=dict)
    nonredundancy: dict[str, float] = field(default_factory=dict)
    # trust (multiplier, [0,1])
    receipt_coverage: float = 1.0
    replay_pass_rate: float = 1.0
    corroboration_strength: float = 1.0
    # learning (retroactive-only, logged not active)
    reuse_or_learning_value: float = 1.0
    # denominator (each clamped to >= 1 so DPI is a stable relative score)
    cost: float = 1.0
    latency: float = 1.0
    fragility: float = 1.0
    complexity: float = 1.0


def decorrelation_bonus(inputs: DPIInputs) -> float:
    """Correctness-gated decorrelated-correctness bonus (§4).

    Returns <= 0 whenever the final outcome is wrong — debate theater on a wrong
    answer is never rewarded.
    """
    if not inputs.final_correct:
        return 0.0  # final_correctness_gate = 0  =>  bonus <= 0
    bonus = 0.0
    for role, loo in inputs.loo_marginal_contributions.items():
        nonredundancy = inputs.nonredundancy.get(role, 0.0)
        bonus += loo * nonredundancy
    return bonus


def verified_capability_delta(inputs: DPIInputs) -> float:
    """Capability headline: error-reduction vs best-single + decorrelation bonus.

    Correctness-gated: when the final outcome is wrong the decorrelation bonus is
    zeroed, so a wrong run cannot launder a positive capability delta from
    disagreement alone.
    """
    base = inputs.candidate_score - inputs.best_single_score
    return base + decorrelation_bonus(inputs)


def trust_multiplier(inputs: DPIInputs) -> float:
    """Trust as a multiplier in [0, 1] — never the numerator (§5, §6.6)."""
    raw = inputs.receipt_coverage * inputs.replay_pass_rate * inputs.corroboration_strength
    return max(0.0, min(1.0, raw))


def compute_dpi(inputs: DPIInputs, *, activate_learning: bool = False) -> dict[str, Any]:
    """Compute the DPI and return its fully-decomposed, auditable components.

    ``activate_learning`` defaults to False: ReuseOrLearningValue is logged in the
    output but contributes a NEUTRAL 1.0 to the score until it is earned
    retroactively (§5, §6.9).
    """
    vcd = verified_capability_delta(inputs)
    trust = trust_multiplier(inputs)
    learning_logged = inputs.reuse_or_learning_value
    learning_active = learning_logged if activate_learning else 1.0

    denom = (
        max(inputs.cost, 1.0)
        * max(inputs.latency, 1.0)
        * max(inputs.fragility, 1.0)
        * max(inputs.complexity, 1.0)
    )
    dpi = (vcd * trust * learning_active) / max(denom, _EPS)

    return {
        "dpi": dpi,
        "verified_capability_delta": vcd,
        "decorrelation_bonus": decorrelation_bonus(inputs),
        "trust_multiplier": trust,
        "final_correct": inputs.final_correct,
        # logged-not-active: visible for audit, neutral in ranking
        "reuse_or_learning_value_logged": learning_logged,
        "reuse_or_learning_value_active": learning_active,
        "learning_active": activate_learning,
        "denominator": denom,
        "denominator_components": {
            "cost": inputs.cost,
            "latency": inputs.latency,
            "fragility": inputs.fragility,
            "complexity": inputs.complexity,
        },
    }


__all__ = [
    "DPIInputs",
    "compute_dpi",
    "decorrelation_bonus",
    "trust_multiplier",
    "verified_capability_delta",
]
