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
    MODEL_POWER_FLOOR,
    ModelSlot,
    ModelTier,
)
from dharma_swarm.model_defaults import (
    _PROVIDER_DEFAULTS,
    default_for_provider,
)
from dharma_swarm.models import ProviderType

# THE POWER FLOOR: the documented Kimi K2.6-class line. Roster slots carry
# ``below_floor`` and the pool propagates it. ``floor_entries`` feeds real paths;
# ``grunt_entries`` is the explicit opt-in for old/weak/local weights.
K2_FLOOR_ID = MODEL_POWER_FLOOR  # "kimi-k2.6" — single documented source

# Provider defaults live in :mod:`model_defaults` to avoid import cycles; the
# pool re-exports :func:`default_for_provider` and validates those defaults below.


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
    # The UNMISTAKABLE demarcation: True == sub-floor (below MODEL_POWER_FLOOR),
    # grunt-work-only. Carried from the roster's ModelSlot.below_floor. The
    # default / frontier / picker projections use :func:`floor_entries` (this
    # flag False); sub-floor entries are reachable only via :func:`grunt_entries`.
    below_floor: bool = False

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
    ProviderType.KIMI_CODE: 2,
    ProviderType.MOONSHOT: 2,
    ProviderType.OLLAMA: 2,
    ProviderType.NVIDIA_NIM: 3,
    ProviderType.GROQ: 4,
    ProviderType.CEREBRAS: 4,
    ProviderType.OPENROUTER: 8,
    ProviderType.OPENROUTER_FREE: 9,
}
_DEFAULT_RANK = 5

# Explicit proof obligation: only this map authorizes Kimi Code ``k3`` to
# collapse with provider-qualified ``kimi-k3``; name similarity is not authority.
_NESTED_ROUTE_LOGICAL_IDS: dict[str, str] = {"k3": "kimi-k3"}


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
        "DeepSeek-V4-Pro"             -> "deepseek-v4-pro"      (casefolded)
    """
    mid = slot.model_id
    nested_id = _NESTED_ROUTE_LOGICAL_IDS.get(mid.casefold())
    if nested_id is not None:
        return nested_id
    # Drop a leading provider namespace (only the first "<vendor>/").
    base = mid.split("/")[-1]
    # Drop serving-grade suffixes that mark the SAME weights on a route.
    base = base.removesuffix(":free")
    base = base.removesuffix(":cloud")
    # Drop a trailing date pin (Anthropic/OpenAI dated ids).
    base = re.sub(r"-\d{8}$", "", base)
    # Casefold so the SAME weights group regardless of a provider's id casing
    # (e.g. SambaNova ``DeepSeek-V4-Pro`` joins the Ollama/Fireworks lowercase
    # routes for one logical model, not a duplicate entry).
    return base.lower()


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
        # Demarcation: an entry is sub-floor if ANY grouped slot is sub-floor.
        # ``any`` (not ``all``) is the safe direction — if a single route is
        # below the floor we keep the whole logical model out of the real path
        # rather than risk leaking it onto the frontier. In a coherent roster a
        # logical model's slots are uniform, so this is exact in practice.
        below_floor = any(s.below_floor for s in slots)
        entries.append(
            ModelEntry(
                id=key,
                display=display,
                tier=tier,
                caps=tuple(caps),
                context=context,
                routes=routes,
                below_floor=below_floor,
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


def floor_entries() -> tuple[ModelEntry, ...]:
    """REAL-path entries: at or above :data:`MODEL_POWER_FLOOR` (Kimi K2.6).

    This is the ONLY set the default chat brain, the frontier, and the model
    picker's main list project from. Sub-floor (grunt) models are excluded by
    construction, so no surface can route below the floor by accident.
    """
    return tuple(e for e in MODEL_POOL if not e.below_floor)


def grunt_entries() -> tuple[ModelEntry, ...]:
    """GRUNT-path entries: sub-floor models, reachable ONLY by explicit opt-in.

    These are the demarcated old / weak / genuinely-local weights the K2.6 floor
    banishes from the real path. They exist for real grunt work only and are
    NEVER part of the default/frontier path or the picker's main list.
    """
    return tuple(e for e in MODEL_POOL if e.below_floor)


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


def required_provider_model_id(logical_id: str, provider: ProviderType) -> str:
    """Return one exact provider route, failing closed when it is absent."""
    entry = get_entry(logical_id)
    if entry is None:
        raise AssertionError(f"missing model-pool entry for {logical_id!r}")
    for route in entry.routes:
        if route.provider is provider:
            return route.model_id
    raise AssertionError(f"missing {provider.value!r} route for {logical_id!r}")


FORGE_KIMI_CODE_MODEL_ID = default_for_provider(ProviderType.KIMI_CODE)
FORGE_KIMI_K3_LOGICAL_ID = "kimi-k3"
FORGE_KIMI_K3_OPENROUTER_MODEL_ID = required_provider_model_id(FORGE_KIMI_K3_LOGICAL_ID, ProviderType.OPENROUTER)
FORGE_NVIDIA_KIMI_MODEL_ID = required_provider_model_id(K2_FLOOR_ID, ProviderType.NVIDIA_NIM)
FORGE_NVIDIA_LLAMA_VERIFIER_MODEL_ID = required_provider_model_id(
    "llama-3.3-70b-instruct",
    ProviderType.NVIDIA_NIM,
)


# Providers whose default is a deliberate operator pin that supersedes the
# legacy roster (the roster predates gpt-5 / opus-4.6 / codex gpt-5.4). These are
# still owned by _PROVIDER_DEFAULTS; the coherence guard below only exempts them
# from the "must match a roster route" check — it does NOT exempt them from being
# present here.
_OPERATOR_PINNED_DEFAULTS: frozenset[ProviderType] = frozenset(
    {
        ProviderType.OPENAI,        # gpt-5  (roster: gpt-4o / gpt-5.5)
        ProviderType.ANTHROPIC,     # claude-opus-4-6  (roster: claude-opus-4-20250514)
        ProviderType.CLAUDE_CODE,   # claude-opus-4-6 via Claude-Max (roster: claude-opus-4.8)
        ProviderType.CODEX,         # gpt-5.4 via codex oauth (roster: gpt-5.5)
        # Secondary floor routes (DeepSeek-V4-Pro / MiniMax-M3 fan-out) gave
        # these providers a roster entry, but their per-provider *default* is a
        # deliberate constant (Llama-3.3-70B / qwen3-coder-480b), not that
        # secondary route — exempt them from the "default must be a roster route"
        # check exactly like the other operator-pinned defaults.
        ProviderType.SAMBANOVA,     # Meta-Llama-3.3-70B-Instruct (roster: DeepSeek-V4-Pro route)
        ProviderType.FIREWORKS,     # qwen3-coder-480b (roster: deepseek-v4-pro route)
    }
)


def _validate_provider_defaults() -> None:
    """Import-time coherence guard for the per-provider default map.

    Drift-killer: where the roster already serves a provider's default id (and
    the provider is not an operator-pinned exception), the default MUST be one of
    that provider's known pool routes — so the default string and the route table
    can never silently disagree.
    """
    known: dict[ProviderType, set[str]] = {}
    for entry in MODEL_POOL:
        for route in entry.routes:
            known.setdefault(route.provider, set()).add(route.model_id)
    for provider, model_id in _PROVIDER_DEFAULTS.items():
        if provider in _OPERATOR_PINNED_DEFAULTS:
            continue
        provider_ids = known.get(provider)
        if provider_ids and model_id not in provider_ids:
            # The roster knows this provider but not this id: a real disagreement
            # between the default and the routes. Surface it loudly at import.
            raise AssertionError(
                f"model_pool default for {provider.value!r} ({model_id!r}) is "
                f"not among that provider's roster routes {sorted(provider_ids)!r}"
            )


_validate_provider_defaults()


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


# ---------------------------------------------------------------------------
# Provider model-id generators (STEP 6 of the consolidation)
# ---------------------------------------------------------------------------
# These replace the hand-typed frontier tuples that used to live in
# ollama_config (OLLAMA_CLOUD_FRONTIER_MODELS), provider_smoke (NIM hosted /
# self-hosted / OpenRouter frontier catalogs) and elsewhere. Each returns the
# provider-specific model-id strings the pool already owns — so the model-id
# literals live in exactly ONE place (the roster -> pool), and downstream
# catalogs become projections. Ordering callers care about (e.g. the smoke
# probe sequence) is applied by the caller; these return pool order, deduped.


def provider_model_ids(
    provider: ProviderType,
    *,
    tiers: tuple[ModelTier, ...] | None = None,
) -> tuple[str, ...]:
    """Every provider-specific model-id the pool serves for ``provider``.

    Pool order (best-route-first across entries), deduped. ``tiers`` optionally
    restricts to entries of those logical tiers (e.g. only STRONG models for a
    smoke catalog). No key strings, no liveness — pure model-grain projection.
    """
    out: list[str] = []
    for entry in MODEL_POOL:
        if tiers is not None and entry.tier not in tiers:
            continue
        for route in entry.routes:
            if route.provider is provider and route.model_id not in out:
                out.append(route.model_id)
    return tuple(out)


def ollama_cloud_model_ids() -> tuple[str, ...]:
    """Ollama routes served over the cloud endpoint (``:cloud`` / ``-cloud``).

    Source for ``ollama_config.OLLAMA_CLOUD_FRONTIER_MODELS``. Pool order,
    deduped, K2.6 floor included (the pool carries it as an Ollama-Cloud route).
    """
    out: list[str] = []
    for mid in provider_model_ids(ProviderType.OLLAMA):
        if (mid.endswith(":cloud") or mid.endswith("-cloud")) and mid not in out:
            out.append(mid)
    return tuple(out)


def strong_vendor_model_ids() -> tuple[str, ...]:
    """Vendor-namespaced ids for STRONG-tier logical models, pool order.

    Used to project the NVIDIA-NIM self-hosted smoke catalog: a self-hosted NIM
    OpenAI-compatible endpoint can serve the same open weights under their
    vendor namespace (e.g. ``moonshotai/kimi-k2.5``, ``z-ai/glm-5``). Each STRONG
    entry contributes its first vendor-namespaced route id (an OpenRouter or NIM
    route carries the ``vendor/model`` form); bare-name local/Ollama-only ids are
    skipped (no vendor namespace to serve self-hosted under).
    """
    out: list[str] = []
    for entry in MODEL_POOL:
        if entry.tier is not ModelTier.STRONG:
            continue
        for route in entry.routes:
            if "/" in route.model_id and route.model_id not in out:
                out.append(route.model_id)
                break
    return tuple(out)


def forge_high_slot_model_ids() -> tuple[str, ...]:
    ids = [default_for_provider(ProviderType.ZHIPU)]
    for entry_id in ("kimi-k3", "deepseek-v4-pro", "minimax-m3", "qwen3-coder:480b-cloud"):
        entry = get_entry(entry_id)
        if entry is not None and not entry.below_floor:
            ids.extend(route.model_id for route in entry.routes)
    return tuple(dict.fromkeys(model_id for model_id in ids if model_id))

def forge_default_high_slot_verifier_id() -> str:
    entry = get_entry("kimi-k3")
    return entry.routes[0].model_id if entry is not None and entry.routes else default_for_provider(ProviderType.KIMI_CODE)


__all__ = [
    "Route",
    "ModelEntry",
    "MODEL_POOL",
    "K2_FLOOR_ID",
    "MODEL_POWER_FLOOR",
    "all_entries",
    "floor_entries",
    "grunt_entries",
    "get_entry",
    "entry_for_model_id",
    "default_for_provider",
    "required_provider_model_id",
    "FORGE_KIMI_CODE_MODEL_ID",
    "FORGE_KIMI_K3_LOGICAL_ID",
    "FORGE_KIMI_K3_OPENROUTER_MODEL_ID",
    "FORGE_NVIDIA_KIMI_MODEL_ID",
    "FORGE_NVIDIA_LLAMA_VERIFIER_MODEL_ID",
    "live_routes",
    "forge_default_high_slot_verifier_id",
    "forge_high_slot_model_ids",
    "best_live_route",
    "provider_model_ids",
    "ollama_cloud_model_ids",
    "strong_vendor_model_ids",
]
