"""Tests for the consolidated model pool (STEP 2 of routing consolidation).

The pool is seeded from ``evolution_roster.EVOLUTION_ROSTER``. These tests
protect two load-bearing invariants the consolidation goal names explicitly:

  * every legacy roster literal (provider model_id) has a matching pool entry;
  * the kimi multi-route dedup — ONE entry, ollama + openrouter routes.

Plus the FAIL-OPEN oracle contract (never strand the fleet) and the K2.6 floor.
"""

from __future__ import annotations

import pytest

from dharma_swarm.evolution_roster import EVOLUTION_ROSTER, ModelTier
from dharma_swarm.models import ProviderType
from dharma_swarm import model_pool
from dharma_swarm.model_pool import (
    MODEL_POOL,
    ModelEntry,
    Route,
    best_live_route,
    entry_for_model_id,
    get_entry,
    live_routes,
)


# --------------------------------------------------------------------------
# Coverage: every legacy literal maps to a pool entry / route
# --------------------------------------------------------------------------


def test_every_legacy_literal_has_a_matching_pool_entry():
    """Each provider-specific model_id in the roster is reachable from a pool
    entry's routes, under the matching ProviderType."""
    missing = []
    for slot in EVOLUTION_ROSTER:
        entry = entry_for_model_id(slot.model_id)
        if entry is None:
            missing.append(slot.model_id)
            continue
        # The route must carry the SAME provider, not just the same id.
        providers = {r.provider for r in entry.routes if r.model_id == slot.model_id}
        assert slot.provider in providers, (
            f"{slot.model_id} found but not under provider {slot.provider}"
        )
    assert not missing, f"legacy literals with no pool entry: {missing}"


def test_pool_routes_are_exactly_the_roster_literals():
    """No route invents a model_id that wasn't in the legacy roster, and no
    roster literal is dropped — the pool is a faithful regroup, not a rewrite."""
    roster_pairs = {(s.provider, s.model_id) for s in EVOLUTION_ROSTER}
    pool_pairs = {
        (r.provider, r.model_id) for e in MODEL_POOL for r in e.routes
    }
    assert pool_pairs == roster_pairs


def test_pool_collapses_roster_slots_to_logical_entries():
    """The roster has 31 slots that collapse to 23 logical pool entries.
    Guards against silent regroup drift.

    Step 4 added 6 slots the provider matrix projects (the K2.6 floor model via
    BOTH Ollama Cloud and OpenRouter, plus deepseek-v3.2 / qwen3-coder:480b /
    minimax-m2.7 Ollama-cloud lanes). That is 4 new logical ids — kimi-k2.6
    (2 routes -> 1 entry) + 3 single-route entries — taking 18 -> 22.

    The misc-surfaces consolidation (2026-06) added 1 slot: gemini-3-pro via
    OpenRouter (google/gemini-3-pro), the FLOOR the TUI/openrouter Gemini lane
    now projects instead of the sub-floor google/gemini-2.5-pro literal. One new
    single-route logical id -> 30 -> 31 slots, 22 -> 23 entries."""
    assert len(EVOLUTION_ROSTER) == 31
    assert len(MODEL_POOL) == 23


# --------------------------------------------------------------------------
# The named case: kimi multi-route dedup
# --------------------------------------------------------------------------


def test_kimi_is_one_entry_with_ollama_and_openrouter_routes():
    """The operator's flap bug: kimi-k2.5 lived as BOTH ollama:kimi-k2.5:cloud
    and openrouter:moonshotai/kimi-k2.5. The pool must hold ONE kimi entry whose
    routes include both providers (de-duplicated, not flapping)."""
    kimi = get_entry("kimi-k2.5")
    assert kimi is not None
    assert isinstance(kimi, ModelEntry)
    assert kimi.id == "kimi-k2.5"

    providers = {r.provider for r in kimi.routes}
    assert ProviderType.OLLAMA in providers
    assert ProviderType.OPENROUTER in providers

    # Exactly the two legacy literals, under their real providers.
    pairs = {(r.provider, r.model_id) for r in kimi.routes}
    assert pairs == {
        (ProviderType.OPENROUTER, "moonshotai/kimi-k2.5"),
        (ProviderType.OLLAMA, "kimi-k2.5:cloud"),
    }

    # Both literals resolve back to the SAME single entry (no duplicate entry).
    assert entry_for_model_id("kimi-k2.5:cloud") is kimi
    assert entry_for_model_id("moonshotai/kimi-k2.5") is kimi
    kimi_entries = [e for e in MODEL_POOL if e.id == "kimi-k2.5"]
    assert len(kimi_entries) == 1


def test_other_known_multiroute_models_also_dedup():
    """glm-5, gpt-4o, claude-opus-4, claude-sonnet-4, llama-3.3-70b-instruct
    are all multi-route in the roster and must each collapse to one entry."""
    expected_routes = {
        "glm-5": {ProviderType.OPENROUTER, ProviderType.OLLAMA},
        "gpt-4o": {ProviderType.OPENAI, ProviderType.OPENROUTER},
        "claude-opus-4": {ProviderType.ANTHROPIC, ProviderType.OPENROUTER},
        "claude-sonnet-4": {ProviderType.ANTHROPIC, ProviderType.OPENROUTER},
        "llama-3.3-70b-instruct": {
            ProviderType.OPENROUTER,
            ProviderType.NVIDIA_NIM,
            ProviderType.OPENROUTER_FREE,
        },
    }
    for entry_id, providers in expected_routes.items():
        entry = get_entry(entry_id)
        assert entry is not None, f"missing entry {entry_id}"
        assert {r.provider for r in entry.routes} == providers, entry_id
        # Single entry per logical id.
        assert len([e for e in MODEL_POOL if e.id == entry_id]) == 1


# --------------------------------------------------------------------------
# Structure: frozen, best-route-first, no key strings
# --------------------------------------------------------------------------


def test_entries_are_frozen_and_carry_no_key_strings():
    for entry in MODEL_POOL:
        with pytest.raises((AttributeError, Exception)):
            entry.id = "mutated"  # type: ignore[misc]
        for route in entry.routes:
            assert isinstance(route, Route)
            # routes carry only provider + model_id; no key/secret field exists.
            field_names = set(Route.__dataclass_fields__)
            assert field_names == {"provider", "model_id"}


def test_routes_are_best_route_first_openrouter_not_first_when_alternative_exists():
    """OpenRouter is the flappy/dead aggregator; when a logical model has a
    non-openrouter route, openrouter must NOT be the first (best) route."""
    for entry in MODEL_POOL:
        provs = [r.provider for r in entry.routes]
        non_openrouter = [
            p
            for p in provs
            if p not in (ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE)
        ]
        if non_openrouter:
            first = entry.routes[0].provider
            assert first not in (
                ProviderType.OPENROUTER,
                ProviderType.OPENROUTER_FREE,
            ), f"{entry.id} ordered openrouter first despite {non_openrouter}"


def test_entry_metadata_is_populated():
    for entry in MODEL_POOL:
        assert entry.id
        assert entry.display
        assert isinstance(entry.tier, ModelTier)
        assert entry.context > 0
        assert len(entry.routes) >= 1


# --------------------------------------------------------------------------
# FAIL-OPEN oracle contract: never strand the fleet
# --------------------------------------------------------------------------


def test_live_routes_fail_open_returns_all_routes_when_oracle_unknown():
    kimi = get_entry("kimi-k2.5")
    assert kimi is not None
    # None == "I don't know" => return every route, untouched (fail-open).
    assert live_routes(kimi, None) == kimi.routes
    assert best_live_route(kimi, None) == kimi.routes[0]


def test_live_routes_prunes_dead_provider_but_keeps_live_one():
    kimi = get_entry("kimi-k2.5")
    assert kimi is not None
    # openrouter dead, ollama live (the operator's exact bug scenario).
    live = live_routes(kimi, {"ollama"})
    assert len(live) == 1
    assert live[0].provider == ProviderType.OLLAMA
    assert live[0].model_id == "kimi-k2.5:cloud"
    # best_live_route picks the live one, not the dead openrouter.
    assert best_live_route(kimi, {"ollama"}).provider == ProviderType.OLLAMA


def test_live_routes_empty_when_all_providers_dead_is_valid_not_failopen():
    kimi = get_entry("kimi-k2.5")
    assert kimi is not None
    # A real-but-empty oracle (all keys dead) is NOT None; it prunes to empty.
    assert live_routes(kimi, set()) == ()
    assert best_live_route(kimi, set()) is None


# --------------------------------------------------------------------------
# K2.6 floor: the pool exposes the operator's floor marker
# --------------------------------------------------------------------------


def test_k2_floor_marker_present():
    assert model_pool.K2_FLOOR_ID == "kimi-k2.6"
