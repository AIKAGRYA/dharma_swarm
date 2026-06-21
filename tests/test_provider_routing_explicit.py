"""Stage 1 keystone: explicit provider/model requests win (pin + safe fallback).

Track: provider-routing-consolidation-2026-06. These tests lock the behavior
that a caller-named provider/model is honored as the SELECTION (not merely a
constraint), while an unavailable pin degrades gracefully to the ranked chain.
"""
from __future__ import annotations

from dharma_swarm.models import ProviderType
from dharma_swarm.provider_policy import ProviderPolicyRouter, ProviderRouteRequest


def _reflex_request(**context: object) -> ProviderRouteRequest:
    # Low risk/uncertainty -> REFLEX path, whose default candidates would
    # otherwise pick a free-tier provider. The explicit pin must override that.
    return ProviderRouteRequest(
        action_name="summarize_logs",
        risk_score=0.08,
        uncertainty=0.10,
        novelty=0.12,
        urgency=0.4,
        expected_impact=0.2,
        estimated_latency_ms=200,
        estimated_tokens=300,
        preferred_low_cost=True,
        context=dict(context),
    )


def test_explicit_provider_is_selected() -> None:
    """A named provider becomes selected_provider even when the path/cost
    heuristics would otherwise choose a different (cheaper) provider."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _reflex_request(preferred_provider="claude_code"),
        available_providers=[
            ProviderType.OPENROUTER_FREE,
            ProviderType.CLAUDE_CODE,
            ProviderType.OLLAMA,
        ],
    )
    assert decision.selected_provider == ProviderType.CLAUDE_CODE
    assert any("explicit_provider_pinned=claude_code" in r for r in decision.reasons)


def test_explicit_model_sets_selected_hint() -> None:
    """A named model rides along as the selected model hint."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _reflex_request(
            preferred_provider="openrouter",
            preferred_model="z-ai/glm-4.6",
        ),
        available_providers=[ProviderType.OPENROUTER, ProviderType.OLLAMA],
    )
    assert decision.selected_provider == ProviderType.OPENROUTER
    assert decision.selected_model_hint == "z-ai/glm-4.6"


def test_unavailable_pin_falls_back_to_ranked_chain() -> None:
    """Safe fallback: a pin for a provider that is not registered/available
    does NOT force-select it; the normal ranked chain stands."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _reflex_request(preferred_provider="mistral"),
        available_providers=[ProviderType.OPENROUTER_FREE, ProviderType.CODEX],
    )
    assert decision.selected_provider != ProviderType.MISTRAL
    assert decision.selected_provider in {
        ProviderType.OPENROUTER_FREE,
        ProviderType.CODEX,
    }


def test_pinned_provider_keeps_chain_as_fallback() -> None:
    """Pin + safe fallback: the rest of the available chain remains as
    ordered fallbacks behind the pinned provider."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _reflex_request(preferred_provider="ollama"),
        available_providers=[
            ProviderType.OPENROUTER_FREE,
            ProviderType.OLLAMA,
            ProviderType.CODEX,
        ],
    )
    assert decision.selected_provider == ProviderType.OLLAMA
    # the other available providers survive as fallbacks (graceful degradation)
    assert ProviderType.OPENROUTER_FREE in decision.fallback_providers
    assert ProviderType.CODEX in decision.fallback_providers


def test_garbage_pin_is_ignored() -> None:
    """An unrecognized provider string must not crash; it degrades to ranked."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _reflex_request(preferred_provider="not_a_real_provider"),
        available_providers=[ProviderType.OPENROUTER_FREE, ProviderType.CODEX],
    )
    assert decision.selected_provider in {
        ProviderType.OPENROUTER_FREE,
        ProviderType.CODEX,
    }


def _plain_request(**over: object) -> ProviderRouteRequest:
    # Context-only keys (not request fields) get routed into context.
    context = {k: over.pop(k) for k in ("preferred_provider", "preferred_model") if k in over}
    base = dict(
        action_name="general_task",
        risk_score=0.10,
        uncertainty=0.10,
        novelty=0.10,
        urgency=0.3,
        expected_impact=0.2,
        context=context,
    )
    base.update(over)
    return ProviderRouteRequest(**base)  # type: ignore[arg-type]


def test_power_first_default_selects_most_capable() -> None:
    """Stage 2: with NO explicit cost preference, the default reaches for the
    most capable provider (Anthropic, intelligence 72) — not the cheapest."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _plain_request(),  # preferred_low_cost defaults False -> power-first
        available_providers=[
            ProviderType.OPENROUTER_FREE,
            ProviderType.OLLAMA,
            ProviderType.ANTHROPIC,
        ],
    )
    assert decision.selected_provider == ProviderType.ANTHROPIC


def test_cost_opt_in_reverts_to_cheap() -> None:
    """Cost is the opt-in nudge: preferred_low_cost=True flips back to
    free-tier-first, away from the most capable provider."""
    router = ProviderPolicyRouter()
    decision = router.route(
        _plain_request(preferred_low_cost=True),
        available_providers=[
            ProviderType.OPENROUTER_FREE,
            ProviderType.OLLAMA,
            ProviderType.ANTHROPIC,
        ],
    )
    assert decision.selected_provider != ProviderType.ANTHROPIC


def test_precedence_explicit_beats_power_beats_cost() -> None:
    """Stage 4 invariant: the one precedence holds end to end.

    explicit  >  capability/power  >  cost
    An explicit pin wins even with a cost preference set (cost would otherwise
    pick the cheap provider, power would pick Anthropic) — proving explicit is
    the top of the order and is never demoted by a lower pass.
    """
    router = ProviderPolicyRouter()
    avail = [
        ProviderType.OPENROUTER_FREE,  # cheapest
        ProviderType.OLLAMA,
        ProviderType.ANTHROPIC,        # most capable
        ProviderType.ZHIPU,
    ]
    # explicit pin for the mid provider + a cost preference: explicit still wins
    explicit = router.route(
        _plain_request(preferred_low_cost=True, preferred_provider="zhipu"),
        available_providers=avail,
    )
    assert explicit.selected_provider == ProviderType.ZHIPU

    # no explicit, no cost -> power wins (Anthropic)
    power = router.route(_plain_request(), available_providers=avail)
    assert power.selected_provider == ProviderType.ANTHROPIC

    # no explicit, cost opt-in -> cheap wins (not Anthropic)
    cost = router.route(_plain_request(preferred_low_cost=True), available_providers=avail)
    assert cost.selected_provider != ProviderType.ANTHROPIC
