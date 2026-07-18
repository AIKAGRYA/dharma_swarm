"""Model routing helpers for TUI model switching, strategy, and fallback.

STEP 5 of the model-pool consolidation. ``MODEL_TARGETS`` is now a *projection*
of the ONE :mod:`dharma_swarm.model_pool` rather than a free-standing literal
table. Each :class:`ModelTarget` declares the ``ProviderType`` routes that serve
it (``pool_providers``); where the pool holds the logical model, the provider
set and the exact provider-specific ``model_id`` are SOURCED FROM the pool at
import time (drift-killer), and an import-time guard asserts the projection is
faithful.

FLOOR-ONLY DEMARCATION (operator word 2026-06-17): the picker's main list and
the default chat brain project ONLY ``model_pool.floor_entries()`` — models at
or above :data:`~dharma_swarm.model_pool.MODEL_POWER_FLOOR` (Kimi K2.6). The
default target (index 1) is a FLOOR Claude on the Claude-Max oauth lane. Sub-floor
(grunt-only) models are DELIBERATELY ABSENT here; ``_validate_targets`` fails the
import if any target projects a ``below_floor`` pool entry. The grunt path is an
explicit opt-in elsewhere, NEVER the picker or a fallback.

UNROUTABLE = a target whose providers have ZERO live keys per the key oracle.
Such a target is non-selectable: ``resolve_model_target`` / ``target_by_index``
return ``None`` for it once a real oracle is supplied, so ``/model set`` errors
instead of flapping onto a dead provider. THE ONE WAY: no key strings live here;
liveness comes only from :func:`dharma_swarm.key_oracle.live_providers`.
FAIL-OPEN is load-bearing: oracle ``None`` (missing/stale/unparseable status, or
no oracle passed) => every target is selectable, exactly today's behaviour — the
TUI is never stranded by a blind oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time

from dharma_swarm import key_oracle as _key_oracle
from dharma_swarm import model_pool as _model_pool
from dharma_swarm.models import ProviderType

INDIGO = "#9C7444"
VERDIGRIS = "#62725D"
OCHRE = "#A17A47"
BENGARA = "#8C5448"
WISTERIA = "#74677D"


@dataclass(frozen=True, slots=True)
class ModelTarget:
    alias: str
    provider_id: str
    model_id: str
    label: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    # ProviderType routes that can serve this target. Routability is derived
    # from this against the live-key oracle — NO key strings here (THE ONE WAY).
    pool_providers: tuple[ProviderType, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Pool projection helpers
# ---------------------------------------------------------------------------
#
# A TUI target's operator-facing ``provider_id`` (claude/codex/openrouter/
# ollama) is a bridge-adapter id, not a ProviderType. These maps translate so a
# target can declare which ProviderType routes serve it.

# Bridge provider_id -> the ProviderType routes it can ride, best-first. Claude
# rides the Max-plan oauth lane (CLAUDE_CODE) first, then the metered API.
_BRIDGE_PROVIDER_ROUTES: dict[str, tuple[ProviderType, ...]] = {
    "claude": (ProviderType.CLAUDE_CODE, ProviderType.ANTHROPIC),
    "codex": (ProviderType.CODEX,),
    "ollama": (ProviderType.OLLAMA,),
    "openrouter": (ProviderType.OPENROUTER,),
    "kimi_code": (
        ProviderType.KIMI_CODE,
        ProviderType.MOONSHOT,
        ProviderType.OPENROUTER,
    ),
    "openai": (ProviderType.OPENAI,),
}


def _pool_providers_for(pool_id: str, provider_id: str) -> tuple[ProviderType, ...]:
    """Provider routes that serve ``pool_id``, restricted to the ones reachable
    through the target's bridge ``provider_id``.

    When the pool knows ``pool_id``, intersect its real routes with the bridge
    provider's reachable ProviderTypes (so an ``ollama`` target only claims the
    OLLAMA route even though the same weights also ride OpenRouter in the pool).
    When the pool does NOT know it (operator-pinned lane the roster predates),
    fall back to the bridge provider's full route set.
    """
    bridge_routes = _BRIDGE_PROVIDER_ROUTES.get(provider_id, ())
    entry = _model_pool.get_entry(pool_id)
    if entry is None:
        return bridge_routes
    pool_route_providers = {r.provider for r in entry.routes}
    matched = tuple(p for p in bridge_routes if p in pool_route_providers)
    return matched or bridge_routes


def _pool_model_id(pool_id: str, provider: ProviderType) -> str | None:
    """The exact provider-specific model_id the pool holds for ``pool_id`` under
    ``provider`` (drift-killer source), or ``None`` if the pool has no such route."""
    entry = _model_pool.get_entry(pool_id)
    if entry is None:
        return None
    for route in entry.routes:
        if route.provider is provider:
            return route.model_id
    return None


def _projected(
    *,
    alias: str,
    provider_id: str,
    label: str,
    aliases: tuple[str, ...],
    pool_id: str | None,
    pinned_model_id: str | None = None,
) -> ModelTarget:
    """Build a ModelTarget as a pool projection.

    ``pool_id`` names the logical pool entry; the provider-specific ``model_id``
    is sourced FROM the pool for the target's primary provider (no literal here).
    ``pinned_model_id`` is for operator-pinned lanes the pool does not know
    (Claude-Max/Codex oauth, Sonnet/Haiku, the Gemini aggregator) — the string
    is the deliberate operator pin, not roster drift.
    """
    routes = _pool_providers_for(pool_id or "", provider_id) if pool_id else (
        _BRIDGE_PROVIDER_ROUTES.get(provider_id, ())
    )
    model_id: str | None = None
    if pool_id is not None and routes:
        model_id = _pool_model_id(pool_id, routes[0])
    if model_id is None:
        model_id = pinned_model_id
    if model_id is None:  # pragma: no cover - guarded by _validate_targets
        raise AssertionError(
            f"model_routing target {alias!r} has no pool route for {pool_id!r} "
            f"and no pinned model id"
        )
    return ModelTarget(
        alias=alias,
        provider_id=provider_id,
        model_id=model_id,
        label=label,
        aliases=aliases,
        pool_providers=routes,
    )


# ───────────────────────────────────────────────────────────────────────────
# THE PICKER'S MAIN LIST — FLOOR MODELS ONLY (>= MODEL_POWER_FLOOR / K2.6).
#
# Every target here projects a ``model_pool.floor_entries()`` entry (or is a
# floor-class operator-pinned Claude/Codex lane). Sub-floor (grunt) models are
# DELIBERATELY ABSENT — they were glm-5 / deepseek-v3.2 / kimi-k2.5 / minimax-m2.7
# in the old list and are now reachable ONLY via an explicit grunt opt-in, NEVER
# the picker's main list or the default chat brain (operator demarcation).
#
# An import-time guard (:func:`_validate_targets`) asserts NO target projects a
# sub-floor pool entry, so the demarcation can never silently regress here.
# ───────────────────────────────────────────────────────────────────────────
MODEL_TARGETS: tuple[ModelTarget, ...] = (
    # DEFAULT chat brain (index 1): a FLOOR Claude on the Max-plan oauth lane.
    _projected(
        alias="opus-4.8",
        provider_id="claude",
        label="Claude Opus 4.8 [floor default]",
        aliases=("opus", "opus 4.8", "claude opus 4.8", "default"),
        pool_id="claude-opus-4.8",
    ),
    _projected(
        alias="sonnet-4.6",
        provider_id="claude",
        label="Claude Sonnet 4.6",
        aliases=("sonnet", "sonnet 4.6", "claude sonnet 4.6"),
        pool_id="claude-sonnet-4.6",
    ),
    # GPT-5.5 floor lane via the codex oauth subscription (THE ONE WAY).
    _projected(
        alias="gpt-5.5",
        provider_id="codex",
        label="GPT-5.5 (Codex)",
        aliases=("gpt", "gpt 5.5", "codex", "gpt-5.5"),
        pool_id="gpt-5.5",
    ),
    # Kimi K2.6 remains an explicit floor fallback; unqualified Kimi aliases
    # promote to K3 below.
    _projected(
        alias="kimi-k2.6",
        provider_id="ollama",
        label="Kimi K2.6 [FREE] (floor)",
        aliases=("kimi k2.6", "k2.6", "floor"),
        pool_id="kimi-k2.6",
    ),
    _projected(
        alias="kimi-k3",
        provider_id="kimi_code",
        label="Kimi K3 (first-party Kimi; Moonshot/OpenRouter fallback)",
        aliases=("kimi", "moonshot", "kimi 3", "kimi k3", "k3"),
        pool_id="kimi-k3",
    ),
    _projected(
        alias="deepseek-v4-pro",
        provider_id="ollama",
        label="DeepSeek V4 Pro [FREE]",
        aliases=("deepseek", "ds", "deepseek v4", "v4 pro"),
        pool_id="deepseek-v4-pro",
    ),
    _projected(
        alias="glm-5.1",
        provider_id="ollama",
        label="GLM-5.1 [FREE]",
        aliases=("glm", "glm5.1", "glm 5.1", "zhipu"),
        pool_id="glm-5.1",
    ),
    _projected(
        alias="minimax-m3",
        provider_id="ollama",
        label="MiniMax M3 [FREE]",
        aliases=("minimax", "m3", "minimax m3"),
        pool_id="minimax-m3",
    ),
    _projected(
        alias="qwen3-coder-480b",
        provider_id="ollama",
        label="Qwen3 Coder 480B [FREE]",
        aliases=("qwen", "qwen3 coder", "qwen3-coder", "480b"),
        pool_id="qwen3-coder:480b-cloud",
    ),
    # Gemini 3 class rides a real FLOOR pool entry (gemini-3-pro); its OpenRouter
    # model_id is SOURCED FROM the pool — no pinned literal.
    _projected(
        alias="gemini-3",
        provider_id="openrouter",
        label="Gemini 3 class (via OpenRouter)",
        aliases=("gemini", "gemini 3", "google gemini 3"),
        pool_id="gemini-3-pro",
    ),
)


def _validate_targets() -> None:
    """Import-time guard: every target declares at least one provider route,
    every pool-backed target's ``model_id`` matches the pool route it projects,
    and NO target projects a sub-floor (grunt-only) pool entry.

    This is the projection-faithfulness gate plus the FLOOR demarcation gate: it
    makes ``MODEL_TARGETS`` provably a view of the pool's ``floor_entries()`` (for
    the models the pool knows) rather than a parallel literal table that can
    silently drift OR leak a sub-floor model onto the picker's main list.
    """
    for t in MODEL_TARGETS:
        if not t.pool_providers:
            raise AssertionError(
                f"model_routing target {t.alias!r} declares no provider routes"
            )
        entry = _model_pool.entry_for_model_id(t.model_id)
        if entry is not None and entry.below_floor:
            raise AssertionError(
                f"model_routing target {t.alias!r} projects SUB-FLOOR pool entry "
                f"{entry.id!r}; the picker's main list is FLOOR-ONLY — sub-floor "
                f"models are reachable only via the explicit grunt opt-in"
            )
        pool_id = _pool_id_for_model(t.model_id)
        if pool_id is None:
            continue  # operator-pinned lane the pool does not know
        primary_provider = t.pool_providers[0]
        primary_expected = _pool_model_id(pool_id, primary_provider)
        if primary_expected is not None and primary_expected != t.model_id:
            raise AssertionError(
                f"model_routing target {t.alias!r} model_id {t.model_id!r} "
                f"does not match primary pool route {primary_expected!r} "
                f"for {primary_provider.value}"
            )
        for provider in t.pool_providers[1:]:
            if _pool_model_id(pool_id, provider) is None:
                raise AssertionError(
                    f"model_routing target {t.alias!r} declares fallback "
                    f"provider {provider.value!r}, but pool entry {pool_id!r} "
                    "has no such route"
                )


def _pool_id_for_model(model_id: str) -> str | None:
    entry = _model_pool.entry_for_model_id(model_id)
    return entry.id if entry is not None else None


_validate_targets()


# _DEFAULT_TARGET is the default chat brain: MODEL_TARGETS[0] == a FLOOR Claude
# (claude-opus-4.8 on the Max-plan oauth lane). NEVER a sub-floor model.
_DEFAULT_TARGET = MODEL_TARGETS[0]
ROUTING_STRATEGIES: tuple[str, ...] = ("responsive", "cost", "genius")
# Fallback orders reference FLOOR aliases only (the picker's main list). No
# sub-floor alias can appear here — the grunt path is opt-in, never a fallback.
_FALLBACK_ORDER_BY_STRATEGY: dict[str, tuple[str, ...]] = {
    "responsive": (
        "sonnet-4.6",
        "kimi-k2.6",
        "gpt-5.5",
        "gemini-3",
        "opus-4.8",
    ),
    "cost": (
        "kimi-k2.6",
        "glm-5.1",
        "deepseek-v4-pro",
        "minimax-m3",
        "gemini-3",
    ),
    "genius": (
        "opus-4.8",
        "sonnet-4.6",
        "gpt-5.5",
        "kimi-k3",
        "gemini-3",
    ),
}


def _norm(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9.\-/ ]+", " ", text)
    return " ".join(text.split())


def all_targets() -> list[ModelTarget]:
    return list(MODEL_TARGETS)


def route_key(provider_id: str, model_id: str) -> str:
    return f"{provider_id}:{model_id}"


def default_target() -> ModelTarget:
    return _DEFAULT_TARGET


# ---------------------------------------------------------------------------
# Routability — unroutable targets become non-selectable (STEP 5 core ask)
# ---------------------------------------------------------------------------

# Sentinel distinguishing "no oracle argument passed" (read the live oracle now)
# from an explicit ``None`` (FAIL-OPEN, do not filter). Both differ from an
# explicit ``set`` (the live-provider set, used as-is for test injection).
_UNSET: object = object()


def _resolve_oracle(key_oracle: set[str] | None | object) -> set[str] | None:
    """Coerce the ``key_oracle`` argument into a live-provider set or ``None``.

    - explicit ``set``  -> use as-is (caller override / test injection)
    - explicit ``None`` -> FAIL-OPEN, do not filter
    - ``_UNSET`` (default for the read-the-world helpers) -> read the live oracle.
    Any oracle read error degrades to ``None`` (fail-open) — the oracle can never
    raise into model selection or strand the TUI.
    """
    if isinstance(key_oracle, set):
        return key_oracle
    if key_oracle is None:
        return None
    try:
        return _key_oracle.live_providers()
    except Exception:  # pragma: no cover - oracle must never raise into routing
        return None


def is_routable(target: ModelTarget, key_oracle: set[str] | None | object = _UNSET) -> bool:
    """Does ``target`` have at least one provider route with a live key?

    FAIL-OPEN: when the oracle is unknown/stale/missing (``None`` after
    resolution, or no oracle passed and the status file is blind), every target
    is routable — today's behaviour, never a self-inflicted outage. A target with
    no declared provider routes is unroutable (it could never reach a provider).
    """
    live = _resolve_oracle(key_oracle)
    if live is None:
        return True
    return any(p.value in live for p in target.pool_providers)


def live_targets(key_oracle: set[str] | None | object = _UNSET) -> list[ModelTarget]:
    """The targets that are routable right now (>=1 live route). FAIL-OPEN: a
    blind oracle returns every target."""
    live = _resolve_oracle(key_oracle)
    if live is None:
        return list(MODEL_TARGETS)
    return [t for t in MODEL_TARGETS if any(p.value in live for p in t.pool_providers)]


def resolve_routable_target(
    text: str,
    key_oracle: set[str] | None | object = _UNSET,
) -> ModelTarget | None:
    """Resolve a target by alias/index/model-id, rejecting UNROUTABLE ones.

    This is the selection gate for ``/model set``: a resolvable-but-dead target
    returns ``None`` so the caller errors ("unroutable") instead of flapping onto
    a provider with no live key. FAIL-OPEN: a blind oracle never rejects.
    """
    cleaned = text.strip().lstrip("#")
    if cleaned.isdigit():
        target = target_by_index(int(cleaned))
    else:
        target = resolve_model_target(text)
    if target is None:
        return None
    if not is_routable(target, key_oracle):
        return None
    return target


def resolve_strategy(text: str | None) -> str | None:
    if not text:
        return None
    q = _norm(text)
    aliases = {
        "responsive": "responsive",
        "fast": "responsive",
        "speed": "responsive",
        "balanced": "responsive",
        "cost": "cost",
        "cheap": "cost",
        "budget": "cost",
        "frugal": "cost",
        "genius": "genius",
        "quality": "genius",
        "max": "genius",
        "best": "genius",
    }
    return aliases.get(q)


def resolve_model_target(text: str) -> ModelTarget | None:
    q = _norm(text)
    if not q:
        return None
    for t in MODEL_TARGETS:
        if q == _norm(t.alias):
            return t
        if q == _norm(t.model_id):
            return t
        for a in t.aliases:
            if q == _norm(a):
                return t
    # relaxed match: "switch to opus 4.6"
    for t in MODEL_TARGETS:
        keys = (_norm(t.alias), _norm(t.model_id), *(_norm(a) for a in t.aliases))
        if any(k and k in q for k in keys):
            return t
    return None


def target_for_route(provider_id: str, model_id: str) -> ModelTarget | None:
    for target in MODEL_TARGETS:
        if target.provider_id == provider_id and target.model_id == model_id:
            return target
    return None


def target_by_index(index: int) -> ModelTarget | None:
    if index < 1 or index > len(MODEL_TARGETS):
        return None
    return MODEL_TARGETS[index - 1]


def _cooldown_remaining_seconds(
    *,
    alias: str,
    cooldown_until: dict[str, float] | None,
    now_ts: float,
) -> int:
    if not cooldown_until:
        return 0
    until = cooldown_until.get(alias, 0.0)
    if until <= 0.0:
        return 0
    remain = int(until - now_ts)
    return remain if remain > 0 else 0


def format_model_list(
    current_provider: str,
    current_model: str,
    *,
    auto_fallback: bool = True,
    strategy: str = "responsive",
    preferred_key: str | None = None,
    available_keys: set[str] | None = None,
    cooldown_until: dict[str, float] | None = None,
    model_stats_by_alias: dict[str, dict[str, float | int | str]] | None = None,
    now_ts: float | None = None,
    key_oracle: set[str] | None | object = _UNSET,
) -> str:
    strategy = resolve_strategy(strategy) or "responsive"
    now = now_ts if now_ts is not None else time.time()
    live = _resolve_oracle(key_oracle)
    lines = ["Available models:", ""]
    for idx, t in enumerate(MODEL_TARGETS, start=1):
        active = (
            t.provider_id == current_provider and t.model_id == current_model
        )
        key = route_key(t.provider_id, t.model_id)
        preferred = preferred_key == key
        mark = f"[{VERDIGRIS}]*[/{VERDIGRIS}]" if active else " "
        remain = _cooldown_remaining_seconds(
            alias=t.alias,
            cooldown_until=cooldown_until,
            now_ts=now,
        )
        # Unroutable (zero live provider keys) takes precedence — it is the
        # non-selectable state. FAIL-OPEN: a blind oracle never marks unroutable.
        routable = live is None or any(p.value in live for p in t.pool_providers)
        if not routable:
            readiness = f"[{BENGARA}]unroutable[/{BENGARA}]"
        elif remain > 0:
            readiness = f"[{OCHRE}]cooldown {remain}s[/{OCHRE}]"
        elif available_keys is not None and key not in available_keys:
            readiness = f"[{BENGARA}]blocked[/{BENGARA}]"
        else:
            readiness = f"[{VERDIGRIS}]ready[/{VERDIGRIS}]"
        stats_suffix = ""
        if model_stats_by_alias:
            stats = model_stats_by_alias.get(t.alias, {})
            ok = int(stats.get("successes", 0) or 0)
            bad = int(stats.get("failures", 0) or 0)
            latency = float(stats.get("ema_latency_ms", 0.0) or 0.0)
            if ok or bad:
                if latency > 0.0:
                    stats_suffix = f" [dim]ok:{ok} fail:{bad} ~{latency:.0f}ms[/dim]"
                else:
                    stats_suffix = f" [dim]ok:{ok} fail:{bad}[/dim]"
        pref = f" [{WISTERIA}](preferred)[/{WISTERIA}]" if preferred else ""
        lines.append(
            f"{mark} [bold]{idx:02d}[/bold] [{INDIGO}]{t.alias}[/{INDIGO}] -> {t.label}"
            f"{pref} {readiness} [dim]({key})[/dim]{stats_suffix}"
        )
    lines.append("")
    lines.append(
        f"Auto-fallback: {'ON' if auto_fallback else 'OFF'} | "
        f"Strategy: {strategy}"
    )
    lines.append(
        "Usage: /model list | /model status | /model set <alias|index> | "
        "/model auto <on|off|status|responsive|cost|genius>"
    )
    lines.append("Natural language: 'switch to opus 4.6' or 'switch to codex 5.4'")
    return "\n".join(lines)


def format_model_status(
    current_provider: str,
    current_model: str,
    auto_fallback: bool,
    *,
    strategy: str = "responsive",
    preferred: ModelTarget | None = None,
    cooldown_count: int = 0,
) -> str:
    t = resolve_model_target(current_model) or resolve_model_target(
        f"{current_provider} {current_model}"
    )
    label = t.label if t else current_model
    state = "ON" if auto_fallback else "OFF"
    resolved_strategy = resolve_strategy(strategy) or "responsive"
    preferred_label = preferred.label if preferred else "unset"
    return (
        f"Current model: [{INDIGO}]{label}[/{INDIGO}]\n"
        f"Provider/model: [dim]{current_provider}:{current_model}[/dim]\n"
        f"Auto-fallback: [{OCHRE}]{state}[/{OCHRE}]\n"
        f"Strategy: [{OCHRE}]{resolved_strategy}[/{OCHRE}]\n"
        f"Preferred model: [{INDIGO}]{preferred_label}[/{INDIGO}]\n"
        f"Cooling models: [{OCHRE}]{cooldown_count}[/{OCHRE}]"
    )


def fallback_chain(
    current_provider: str,
    current_model: str,
    *,
    strategy: str = "responsive",
    allowed_aliases: set[str] | None = None,
    cooldown_until: dict[str, float] | None = None,
    now_ts: float | None = None,
) -> list[ModelTarget]:
    current = target_for_route(current_provider, current_model)
    resolved_strategy = resolve_strategy(strategy) or "responsive"
    order = _FALLBACK_ORDER_BY_STRATEGY.get(
        resolved_strategy,
        _FALLBACK_ORDER_BY_STRATEGY["responsive"],
    )
    ordered: list[ModelTarget] = []
    by_alias = {t.alias: t for t in MODEL_TARGETS}
    now = now_ts if now_ts is not None else time.time()
    for alias in order:
        t = by_alias.get(alias)
        if t is None:
            continue
        if allowed_aliases is not None and t.alias not in allowed_aliases:
            continue
        if _cooldown_remaining_seconds(
            alias=t.alias,
            cooldown_until=cooldown_until,
            now_ts=now,
        ) > 0:
            continue
        if current and t.alias == current.alias:
            continue
        ordered.append(t)
    return ordered


def detect_inline_switch_intent(text: str) -> ModelTarget | None:
    q = _norm(text)
    if not q:
        return None
    patterns = (
        "switch to ",
        "change to ",
        "use ",
        "set model to ",
        "move to ",
        "switch model to ",
        "go to ",
    )
    if any(p in q for p in patterns):
        return resolve_model_target(q)
    return None
