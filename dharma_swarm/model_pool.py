"""The ONE model-grain source: a frozen pool of logical models, each with an
ordered (best-route-first) tuple of provider routes.

This module is the cure for routing drift. Models were defined in 10+ parallel
files (model_hierarchy.DEFAULT_MODELS, tui/model_routing.MODEL_TARGETS,
provider_matrix blueprints, provider_smoke catalogs, ollama_config frontier,
free_fleet tier rules, evolution_roster, runtime_provider DEFAULT_*) — the same
logical model under different provider-ids and tiers, with no single source.

The pool collapses that: one :class:`ModelEntry` per *logical* model. The same
weights served by several providers (e.g. kimi-k2.5 via ollama AND openrouter)
become ONE entry with a tuple of :class:`Route` rows ordered best-route-first.

THE ONE WAY: this module holds **no key strings** and never reads key material.
Routability is *derived* at call time via :func:`live_routes`, which is handed a
``key_oracle`` (the live-provider set, or ``None`` for "unknown"). Keys live only
in ``~/.dharma/agent_keys.env`` (via ``dkeys``), read only through ``api_keys.py``.

FAIL-OPEN: when the oracle says "unknown" (``None``), :func:`live_routes` returns
*all* routes — the pool must never strand the fleet by going blind.

Seeded from ``evolution_roster.EVOLUTION_ROSTER`` (the richest legacy source).
STEP 2 of the consolidation: no call sites are switched yet. Later steps project
``DEFAULT_MODELS`` / ``MODEL_TARGETS`` / provider_matrix from this pool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from dharma_swarm.evolution_roster import (
    EVOLUTION_ROSTER,
    ModelSlot,
    ModelTier,
)
from dharma_swarm.models import ProviderType

# ---------------------------------------------------------------------------
# Floor: never route / recommend a model below this grade (GOAL doctrine).
# K2.6 is the operator's floor; K2.5 entries seeded from the legacy roster are
# the live frontier-equivalent today. The floor is a marker the pool exposes so
# downstream projections (DEFAULT_MODELS, MODEL_TARGETS) can refuse sub-floor
# recommendations. STEP 2 records it; it does not yet prune call sites.
# ---------------------------------------------------------------------------
K2_FLOOR_ID = "kimi-k2.6"


# ---------------------------------------------------------------------------
# Route + ModelEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Route:
    """One way to reach a logical model: (provider, provider-specific id).

    ``model_id`` is the EXACT string a given provider expects (e.g.
    ``"moonshotai/kimi-k2.5"`` on OpenRouter vs ``"kimi-k2.5:cloud"`` on Ollama).
    No key strings here — routability is derived from the live-provider oracle.
    """

    provider: ProviderType
    model_id: str


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """A single logical model and every provider route that serves it.

    ``routes`` is ordered best-route-first: the first live route wins.
    ``aliases`` are operator-facing handles (for ``/model set <alias>``).
    """

    id: str
    display: str
    tier: ModelTier
    caps: tuple[str, ...]
    context: int
    routes: tuple[Route, ...]
    aliases: tuple[str, ...] = ()

    @property
    def model_ids(self) -> tuple[str, ...]:
        """Every provider-specific model-id this entry can serve under."""
        return tuple(r.model_id for r in self.routes)

    @property
    def providers(self) -> tuple[ProviderType, ...]:
        return tuple(r.provider for r in self.routes)


# ---------------------------------------------------------------------------
# Seeding from the evolution roster
# ---------------------------------------------------------------------------

# Provider preference for ordering routes within one logical model
# (best-route-first). Lower number == preferred. Direct first-party providers
# beat aggregators; free/local keyless routes beat paid aggregators that may be
# dead. OpenRouter is deprioritised because it is the flappy/dead aggregator the
# consolidation goal is fixing.
_PROVIDER_RANK: dict[ProviderType, int] = {
    ProviderType.ANTHROPIC: 0,
    ProviderType.CLAUDE_CODE: 0,
    ProviderType.OPENAI: 1,
    ProviderType.CODEX: 1,
    ProviderType.OLLAMA: 2,
    ProviderType.NVIDIA_NIM: 3,
    ProviderType.GROQ: 4,
    ProviderType.CEREBRAS: 4,
    ProviderType.OPENROUTER: 8,
    ProviderType.OPENROUTER_FREE: 9,
}
_DEFAULT_RANK = 5


def _logical_id(slot: ModelSlot) -> str:
    """Collapse a provider-specific model_id to a stable logical model id.

    Strips the provider prefix (``anthropic/``, ``moonshotai/`` …), the
    ``:free`` / ``:cloud`` serving suffixes, and the trailing ``-YYYYMMDD`` date
    pin — so all routes for the same weights group into one entry.

    Examples::

        "anthropic/claude-opus-4"     -> "claude-opus-4"
        "claude-opus-4-20250514"      -> "claude-opus-4"
        "moonshotai/kimi-k2.5"        -> "kimi-k2.5"
        "kimi-k2.5:cloud"             -> "kimi-k2.5"
        "meta-llama/llama-3.3-70b-instruct:free" -> "llama-3.3-70b-instruct"
        "qwen2.5-coder:14b"           -> "qwen2.5-coder:14b"   (size tag kept)
    """
    mid = slot.model_id
    # Drop a leading provider namespace (only the first "<vendor>/").
    base = mid.split("/")[-1]
    # Drop serving-grade suffixes that mark the SAME weights on a route.
    base = base.removesuffix(":free")
    base = base.removesuffix(":cloud")
    # Drop a trailing date pin (Anthropic/OpenAI dated ids).
    base = re.sub(r"-\d{8}$", "", base)
    return base


# Tier ordering: lower index == stronger grade (for picking the entry's
# canonical tier when routes disagree, e.g. NIM 'fast' vs OpenRouter 'strong').
_TIER_ORDER: tuple[ModelTier, ...] = (
    ModelTier.FRONTIER,
    ModelTier.STRONG,
    ModelTier.FAST,
    ModelTier.FREE,
    ModelTier.LOCAL,
)


def _best_tier(tiers: Iterable[ModelTier]) -> ModelTier:
    return min(tiers, key=lambda t: _TIER_ORDER.index(t))


def _route_sort_key(slot: ModelSlot) -> tuple[int, str]:
    return (_PROVIDER_RANK.get(slot.provider, _DEFAULT_RANK), slot.model_id)


def _display_for(slots: list[ModelSlot]) -> str:
    """Prefer the cleanest display name (the one without a parenthetical
    provider qualifier like "(direct)" / "(Ollama Cloud)" / "(free)")."""
    clean = [s for s in slots if "(" not in s.display_name]
    chosen = clean[0] if clean else slots[0]
    return re.sub(r"\s*\([^)]*\)\s*$", "", chosen.display_name).strip()


def _build_pool(roster: tuple[ModelSlot, ...]) -> tuple[ModelEntry, ...]:
    grouped: dict[str, list[ModelSlot]] = {}
    order: list[str] = []
    for slot in roster:
        key = _logical_id(slot)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(slot)

    entries: list[ModelEntry] = []
    for key in order:
        slots = grouped[key]
        ordered = sorted(slots, key=_route_sort_key)
        routes = tuple(Route(s.provider, s.model_id) for s in ordered)
        # caps: union of strengths across routes, in first-seen order.
        caps: list[str] = []
        for s in ordered:
            for cap in s.strengths:
                if cap not in caps:
                    caps.append(cap)
        # context: the largest context any route guarantees.
        context = max(s.max_context for s in slots)
        tier = _best_tier(s.tier for s in slots)
        display = _display_for(slots)
        entries.append(
            ModelEntry(
                id=key,
                display=display,
                tier=tier,
                caps=tuple(caps),
                context=context,
                routes=routes,
            )
        )
    return tuple(entries)


# The ONE pool. Frozen, deterministic, seeded from the legacy roster.
MODEL_POOL: tuple[ModelEntry, ...] = _build_pool(EVOLUTION_ROSTER)

_BY_ID: dict[str, ModelEntry] = {e.id: e for e in MODEL_POOL}
_BY_ALIAS: dict[str, ModelEntry] = {}
for _e in MODEL_POOL:
    for _a in (_e.id, *_e.aliases):
        _BY_ALIAS.setdefault(_a.lower(), _e)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def all_entries() -> tuple[ModelEntry, ...]:
    return MODEL_POOL


def get_entry(name: str) -> ModelEntry | None:
    """Resolve an entry by id or alias (case-insensitive)."""
    entry = _BY_ID.get(name)
    if entry is not None:
        return entry
    return _BY_ALIAS.get(name.lower())


def entry_for_model_id(model_id: str) -> ModelEntry | None:
    """Find the pool entry that serves an exact provider-specific model_id."""
    for entry in MODEL_POOL:
        if model_id in entry.model_ids:
            return entry
    return None


def live_routes(
    entry: ModelEntry,
    key_oracle: set[str] | None,
) -> tuple[Route, ...]:
    """Return the entry's routes whose provider currently has a live key.

    ``key_oracle`` is the set of live provider-value strings (from
    ``key_oracle.live_providers()``), or ``None`` meaning "unknown".

    FAIL-OPEN: when ``key_oracle is None`` (status missing/stale/unparseable),
    EVERY route is returned — the pool never strands the fleet by going blind.
    A real-but-empty oracle set (all keys dead) is a valid answer: routes whose
    provider is not live are pruned, possibly to an empty tuple. Order is
    preserved (best-route-first), so the first element is the route to try.
    """
    if key_oracle is None:
        return entry.routes
    return tuple(
        r for r in entry.routes if r.provider.value in key_oracle
    )


def best_live_route(
    entry: ModelEntry,
    key_oracle: set[str] | None,
) -> Route | None:
    """The single best (first) live route, or ``None`` if no route is live."""
    routes = live_routes(entry, key_oracle)
    return routes[0] if routes else None


__all__ = [
    "Route",
    "ModelEntry",
    "MODEL_POOL",
    "K2_FLOOR_ID",
    "all_entries",
    "get_entry",
    "entry_for_model_id",
    "live_routes",
    "best_live_route",
]
