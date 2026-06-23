"""DPI tests (spec §4, §5, §6): bounds, correctness gate (wrong outcome =>
decorrelation_bonus <= 0), trust as multiplier, LearningValue logged-not-active."""

from __future__ import annotations

from dharma_swarm.coordination.dpi import (
    DPIInputs,
    compute_dpi,
    decorrelation_bonus,
    trust_multiplier,
    verified_capability_delta,
)


def _inputs(**overrides) -> DPIInputs:
    base = dict(
        candidate_score=0.9,
        best_single_score=0.6,
        final_correct=True,
        loo_marginal_contributions={"a": 0.2, "b": 0.1},
        nonredundancy={"a": 1.0, "b": 0.5},
        receipt_coverage=1.0,
        replay_pass_rate=1.0,
        corroboration_strength=1.0,
        reuse_or_learning_value=3.0,
        cost=1200.0,
        latency=1.0,
        fragility=1.0,
        complexity=12.0,
    )
    base.update(overrides)
    return DPIInputs(**base)


def test_decorrelation_bonus_correctness_gate_wrong_outcome():
    """The load-bearing §4 invariant: a wrong final outcome => bonus <= 0."""
    wrong = _inputs(final_correct=False)
    assert decorrelation_bonus(wrong) <= 0
    # even with large disagreement contributions, a wrong outcome earns nothing
    wrong_big = _inputs(
        final_correct=False,
        loo_marginal_contributions={"a": 5.0},
        nonredundancy={"a": 5.0},
    )
    assert decorrelation_bonus(wrong_big) <= 0


def test_decorrelation_bonus_positive_when_correct():
    bonus = decorrelation_bonus(_inputs())  # 0.2*1.0 + 0.1*0.5 = 0.25
    assert abs(bonus - 0.25) < 1e-9


def test_capability_is_in_the_numerator():
    vcd = verified_capability_delta(_inputs())
    # (0.9 - 0.6) + 0.25 = 0.55
    assert abs(vcd - 0.55) < 1e-9


def test_wrong_outcome_cannot_launder_capability_via_disagreement():
    """A wrong outcome zeroes the decorrelation bonus, so capability cannot be
    inflated by disagreement alone (spec §4, §6.5)."""
    wrong = _inputs(
        final_correct=False,
        candidate_score=0.6,
        best_single_score=0.6,
        loo_marginal_contributions={"a": 10.0},
        nonredundancy={"a": 10.0},
    )
    # base = 0, bonus = 0 -> vcd = 0 (no laundering)
    assert verified_capability_delta(wrong) == 0.0


def test_trust_is_a_multiplier_in_unit_interval():
    assert trust_multiplier(_inputs()) == 1.0
    half = _inputs(receipt_coverage=1.0, replay_pass_rate=0.5, corroboration_strength=1.0)
    assert abs(trust_multiplier(half) - 0.5) < 1e-9
    # clamped to [0,1]
    over = _inputs(receipt_coverage=2.0, replay_pass_rate=2.0, corroboration_strength=2.0)
    assert trust_multiplier(over) == 1.0
    neg = _inputs(corroboration_strength=-1.0)
    assert trust_multiplier(neg) == 0.0


def test_trust_scales_dpi_but_is_never_the_numerator():
    full = compute_dpi(_inputs())
    half = compute_dpi(_inputs(replay_pass_rate=0.5))
    assert abs(half["dpi"] - full["dpi"] * 0.5) < 1e-12
    # zero trust kills the score entirely (it is a multiplier)
    zero = compute_dpi(_inputs(corroboration_strength=0.0))
    assert zero["dpi"] == 0.0


def test_reuse_or_learning_value_logged_not_active():
    """Retroactive-only: logged but neutral (1.0) in ranking by default (§5, §6.9)."""
    out = compute_dpi(_inputs(reuse_or_learning_value=3.0))
    assert out["reuse_or_learning_value_logged"] == 3.0
    assert out["reuse_or_learning_value_active"] == 1.0
    assert out["learning_active"] is False
    # activating it (future) would change the score; proving it is currently inert
    active = compute_dpi(_inputs(reuse_or_learning_value=3.0), activate_learning=True)
    assert active["reuse_or_learning_value_active"] == 3.0
    assert abs(active["dpi"] - out["dpi"] * 3.0) < 1e-12


def test_dpi_bounds_finite_and_signs():
    pos = compute_dpi(_inputs())
    assert pos["dpi"] > 0  # positive capability, full trust
    # negative capability -> negative DPI
    neg = compute_dpi(_inputs(candidate_score=0.3, best_single_score=0.6))
    assert neg["verified_capability_delta"] < 0
    assert neg["dpi"] < 0
    # all components finite
    for v in (pos["dpi"], neg["dpi"]):
        assert v == v and abs(v) != float("inf")
