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
from dharma_swarm.helm_route_truth_types import HELM_SLICE1_SEATS, HelmSeat
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
    """The roster has 46 slots that collapse to 32 logical pool entries.
    Guards against silent regroup drift.

    K3 replaces two active K2.7 logical entries with one provider-typed entry:
    Kimi Code ``k3``, Moonshot ``kimi-k3``, and OpenRouter
    ``moonshotai/kimi-k3`` are three routes for the same model. The roster gains
    one route overall (46 -> 47) while the pool loses one duplicate logical
    entry (32 -> 31).

    Ticket #1405 (Helm leg-one pool registration) adds 7 new roster slots for
    6 new logical entries — Fable 5 (1 slot), GPT 5.6 (2 slots collapsing to
    1, mirroring gpt-5.5), Grok 4.5 (1 slot), Grok 4.6 (1 slot, a separate
    logical entry — the pool does not collapse differing version numbers),
    Fugu Ultra (1 slot), Opus 5.0 (1 slot): roster 47 -> 54, pool 31 -> 37."""
    assert len(EVOLUTION_ROSTER) == 54
    assert len(MODEL_POOL) == 37


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
    # Ticket #1405 (Helm leg-one pool registration) adds 6 new floor entries
    # (Fable 5, GPT 5.6, Grok 4.5, Grok 4.6, Fugu Ultra, Opus 5.0), all
    # above the power floor by construction: 13 -> 19. grunt is untouched.
    assert len(floor) == 19
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


# --------------------------------------------------------------------------
# Helm leg-one alive bar: the 7 ratified on-call seats (ticket #1405;
# HELM_LEGONE_SPEC.md §2.1 item 4 "Standing named bench" + §3 obligation 1
# "Pool registration"). Fixed priority order per the spec: Fable 5 -> GPT 5.6
# -> Grok 4.5/4.6 -> Fugu Ultra -> Kimi K3 -> Opus 5.0 -> Opus 4.8.
#
# Canonical logical ids and (provider, model_id) routes are not invented here
# — they are the pool projection of the SAME identities already ratified in
# ``dharma_swarm.helm_route_truth_types.HELM_SLICE1_SEATS`` (the obligation-5
# RouteVerification census), restricted to the admissible identities whose
# provider is a real ``ProviderType`` member. See PR body for the two seats
# (Grok, Fugu Ultra) where that source names a provider string with no
# existing ``ProviderType`` member.
#
# These tests PROJECT from HELM_SLICE1_SEATS instead of re-encoding a
# parallel seat -> pool-id table (ADR-008 naming floor: no parallel naming
# schemes for the same concept) — seat identity, admissible routes, AND
# order all come from that ONE existing canonical source via
# entry_for_model_id (exact route-level model_id match, not a guessed pool
# id). Only HELM_SEVEN_SEAT_DISPLAY_ORDER below is hand-transcribed: it is
# the independent spec ground-truth an order check needs to be
# non-tautological — deriving the expected order FROM HELM_SLICE1_SEATS
# would make "does HELM_SLICE1_SEATS match the spec" vacuously true.
# --------------------------------------------------------------------------

# HELM_LEGONE_SPEC.md §2.1 item 4 "Standing named bench, fixed priority
# order" / §8 Definition of done, transcribed verbatim.
HELM_SEVEN_SEAT_DISPLAY_ORDER: tuple[str, ...] = (
    "Fable 5",
    "GPT 5.6",
    "Grok 4.5/4.6",
    "Fugu Ultra",
    "Kimi K3",
    "Opus 5.0",
    "Opus 4.8",
)


def _seat_pool_entries(seat: HelmSeat) -> list[ModelEntry]:
    """Every pool entry reachable from one of ``seat``'s admissible
    (provider_string, model_id) identities, via the exact route-level
    model_id (``entry_for_model_id``) — never a hand-typed pool-id guess."""
    entries: list[ModelEntry] = []
    for _provider_str, model_id in seat.admissible_served_identities:
        entry = entry_for_model_id(model_id)
        if entry is not None and entry not in entries:
            entries.append(entry)
    return entries


def test_seven_seat_census_order_matches_the_ratified_alive_bar_sequence():
    """The fixed order lives in HELM_SLICE1_SEATS — consumed by
    model_status.py's on-call projection — NOT in the pool/roster. The
    roster's own top-level tuple order is a capability-tier grouping (see
    the "FLOOR FRONTIER" / "Strong tier" / "Fast tier" section banners in
    evolution_roster.py) and is never documented as seat-priority-
    significant; this ticket's new slots were inserted into the existing
    floor-frontier section, matching that pre-existing convention, not the
    alive-bar's seat order. This test proves the surface that actually IS
    order-significant for the alive bar still matches the ratified spec
    sequence."""
    assert tuple(seat.display_label for seat in HELM_SLICE1_SEATS) == HELM_SEVEN_SEAT_DISPLAY_ORDER


def test_seven_seat_order_gate_fails_on_permutation():
    """Negative control for the order check above: swapping two seats must
    make the comparison fail — proves it is not a tautology."""
    permuted = list(seat.display_label for seat in HELM_SLICE1_SEATS)
    permuted[0], permuted[1] = permuted[1], permuted[0]
    assert tuple(permuted) != HELM_SEVEN_SEAT_DISPLAY_ORDER
    # And the real, untampered sequence still matches at this point.
    assert tuple(seat.display_label for seat in HELM_SLICE1_SEATS) == HELM_SEVEN_SEAT_DISPLAY_ORDER


def test_all_seven_ratified_oncall_seats_resolve_to_a_pool_entry():
    """Alive-bar acceptance criterion (#1405): all seven fixed-order named
    seats must resolve to a registered pool entry with a canonical id and
    route. Negative control for this exact check: ticket #1405 body records
    the pre-registration red run — 5 of 7 seats absent, verified 2026-08-19."""
    missing = [seat.display_label for seat in HELM_SLICE1_SEATS if not _seat_pool_entries(seat)]
    assert not missing, f"ratified on-call seats with no pool entry: {missing}"


def test_all_seven_ratified_oncall_seats_are_above_the_power_floor():
    """Catalog honesty (spec §2.1 item 6): a seat may not be satisfied by a
    sub-floor (grunt-only) entry — it must be on the real (floor) path."""
    floor_ids = {e.id for e in model_pool.floor_entries()}
    not_on_floor = [
        seat.display_label
        for seat in HELM_SLICE1_SEATS
        if not any(entry.id in floor_ids for entry in _seat_pool_entries(seat))
    ]
    assert not not_on_floor, f"ratified on-call seats not on the real (floor) path: {not_on_floor}"


def test_seven_seat_gate_fails_if_a_seat_is_missing():
    """Negative control: proves the resolution check above is not a
    tautology — a seat whose admissible identities all miss the pool must
    be reported as missing, and only that seat (the tampered seat keeps a
    REAL display label so a naive "any non-empty string" bug can't hide)."""
    tampered_seat = HelmSeat(
        "not-a-real-seat",
        "Opus 4.8",
        "not-a-real-lineage",
        (("nobody", "definitely-not-a-registered-model-id"),),
    )
    seats = HELM_SLICE1_SEATS[:-1] + (tampered_seat,)
    missing = [seat.display_label for seat in seats if not _seat_pool_entries(seat)]
    assert missing == ["Opus 4.8"]
    # And the real (untampered) census has nothing missing at this point.
    assert [seat.display_label for seat in HELM_SLICE1_SEATS if not _seat_pool_entries(seat)] == []
