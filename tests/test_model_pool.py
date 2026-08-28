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
    required_provider_model_id,
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
    """The roster has 48 slots that collapse to 31 logical pool entries.
    Guards against silent regroup drift.

    K3 replaces two active K2.7 logical entries with one provider-typed entry:
    Kimi Code ``k3``, Moonshot ``kimi-k3``, and OpenRouter
    ``moonshotai/kimi-k3`` are three routes for the same model. The roster gains
    one route overall (46 -> 47) while the pool loses one duplicate logical
    entry (32 -> 31). The additional Ollama GLM 5.2 route raises the roster to
    48 without creating another logical entry."""
    assert len(EVOLUTION_ROSTER) == 48
    assert len(MODEL_POOL) == 31


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


def test_kimi_k3_provider_ids_collapse_only_by_explicit_promotion_rule():
    """Provider-specific K3 ids form one logical model without string guessing."""
    kimi = get_entry("kimi-k3")
    assert kimi is not None and not kimi.below_floor
    assert kimi.context == 1_048_576
    assert kimi.routes[0] == Route(ProviderType.KIMI_CODE, "k3")
    assert set(kimi.routes) == {
        Route(ProviderType.KIMI_CODE, "k3"),
        Route(ProviderType.MOONSHOT, "kimi-k3"),
        Route(ProviderType.OPENROUTER, "moonshotai/kimi-k3"),
    }
    assert entry_for_model_id("k3") is kimi
    assert entry_for_model_id("kimi-k3") is kimi
    assert entry_for_model_id("moonshotai/kimi-k3") is kimi


def test_glm52_is_one_entry_with_exact_zhipu_and_ollama_routes():
    """The governed authoring route is one logical model with two providers."""
    logical_id = model_pool.default_for_provider(ProviderType.ZHIPU)
    glm = get_entry(logical_id)

    assert glm is not None and not glm.below_floor
    assert set(glm.routes) == {
        Route(ProviderType.ZHIPU, "glm-5.2"),
        Route(ProviderType.OLLAMA, "glm-5.2:cloud"),
    }
    assert glm.routes[0] == Route(ProviderType.OLLAMA, "glm-5.2:cloud")
    assert required_provider_model_id(logical_id, ProviderType.ZHIPU) == "glm-5.2"
    assert required_provider_model_id(logical_id, ProviderType.OLLAMA) == "glm-5.2:cloud"
    assert "glm-5.2:cloud" in model_pool.ollama_cloud_model_ids()
    assert entry_for_model_id("glm-5.2:cloud") is glm
    assert len([entry for entry in MODEL_POOL if entry.id == logical_id]) == 1


def test_required_provider_model_id_fails_closed():
    logical_id = model_pool.default_for_provider(ProviderType.ZHIPU)
    with pytest.raises(AssertionError, match="missing model-pool entry"):
        required_provider_model_id("missing-logical-model", ProviderType.OLLAMA)
    with pytest.raises(AssertionError, match="missing 'codex' route"):
        required_provider_model_id(logical_id, ProviderType.CODEX)


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
    # Re-exported, single documented source.
    assert model_pool.MODEL_POWER_FLOOR == "kimi-k2.6"
    assert model_pool.K2_FLOOR_ID == model_pool.MODEL_POWER_FLOOR


# --------------------------------------------------------------------------
# Floor demarcation: below_floor carried from roster -> entry, floor/grunt API
# --------------------------------------------------------------------------


def test_below_floor_marker_carried_from_roster_into_entries():
    """Every entry's below_floor reflects its grouped roster slots (the
    demarcation lives in the DATA, not in prose)."""
    for entry in MODEL_POOL:
        slots = [s for s in EVOLUTION_ROSTER if model_pool._logical_id(s) == entry.id]
        assert slots, f"entry {entry.id} has no backing roster slots"
        expected = any(s.below_floor for s in slots)
        assert entry.below_floor is expected, entry.id


def test_floor_and_grunt_partition_the_pool():
    floor = model_pool.floor_entries()
    grunt = model_pool.grunt_entries()
    # Disjoint and exhaustive.
    assert set(floor).isdisjoint(set(grunt))
    assert len(floor) + len(grunt) == len(MODEL_POOL)
    assert all(not e.below_floor for e in floor)
    assert all(e.below_floor for e in grunt)
    assert len(floor) == 13
    assert len(grunt) == 18


def test_floor_path_has_a_claude_chat_brain():
    """The REAL path must carry a floor Claude for the default chat brain."""
    floor_ids = {e.id for e in model_pool.floor_entries()}
    assert "claude-opus-4.8" in floor_ids
    opus = get_entry("claude-opus-4.8")
    assert opus is not None and not opus.below_floor
    # Routes via the Claude-Max oauth lane (THE ONE WAY), not the metered API.
    assert ProviderType.CLAUDE_CODE in {r.provider for r in opus.routes}


def test_named_subfloor_models_are_grunt_only():
    """The operator's BELOW-FLOOR / grunt list must all be marked below_floor."""
    grunt_ids = {e.id for e in model_pool.grunt_entries()}
    for sub in (
        "kimi-k2.5",
        "glm-5",
        "deepseek-v3.2",
        "deepseek-r1",
        "deepseek-chat-v3-0324",
        "minimax-m2.7",
        "gpt-4o",
        "claude-opus-4",
        "claude-sonnet-4",
        "qwen-2.5-coder-32b-instruct",
        "mistral-large-2411",
        "mistral-small-3.1-24b-instruct",
        "llama-3.3-70b-instruct",
        "llama-3.1-nemotron-ultra-253b-v1",
        "gemma-3-27b-it",
        "qwen2.5-coder:14b",
        "deepseek-coder-v2:16b",
        "llama3.2",
    ):
        assert sub in grunt_ids, f"{sub} must be marked below_floor (grunt-only)"


def test_floor_frontier_models_present_and_above_floor():
    """The K2.6-floor frontier the roster must SERVE — all floor (real path)."""
    floor_ids = {e.id for e in model_pool.floor_entries()}
    for use in (
        "claude-opus-4.8",
        "claude-sonnet-4.6",
        "gpt-5.5",
        "kimi-k2.6",
        "kimi-k3",
        "deepseek-v4-pro",
        "glm-5.1",
        "minimax-m3",
        "qwen3-coder:480b-cloud",
        "gemini-3-pro",
    ):
        assert use in floor_ids, f"{use} must be a FLOOR (real-path) entry"


def test_deepseek_v4_pro_is_one_entry_live_provider_first():
    """deepseek-v4-pro collapses Ollama, NIM, SambaNova, and Fireworks into ONE
    entry, with the live keyless Ollama route first."""
    dv4 = get_entry("deepseek-v4-pro")
    assert dv4 is not None and not dv4.below_floor
    providers = {r.provider for r in dv4.routes}
    assert providers == {
        ProviderType.OLLAMA,
        ProviderType.NVIDIA_NIM,
        ProviderType.SAMBANOVA,
        ProviderType.FIREWORKS,
    }
    # Live provider (Ollama Cloud) ranked first, dead/secondary after.
    assert dv4.routes[0].provider is ProviderType.OLLAMA
    assert entry_for_model_id("deepseek-ai/deepseek-v4-pro") is dv4


def test_floor_nim_routes_cover_kimi_deepseek_and_minimax():
    expected = {
        "kimi-k2.6": "moonshotai/kimi-k2.6",
        "deepseek-v4-pro": "deepseek-ai/deepseek-v4-pro",
        "minimax-m3": "minimaxai/minimax-m3",
    }
    for logical_id, model_id in expected.items():
        entry = get_entry(logical_id)
        assert entry is not None and not entry.below_floor
        assert any(
            route.provider is ProviderType.NVIDIA_NIM and route.model_id == model_id
            for route in entry.routes
        )
