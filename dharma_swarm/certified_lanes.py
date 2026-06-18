"""Canonical certified operator lanes.

These are the lanes we have verified as real working peers and want to keep
stable across chat surfaces, live-agent registration, and KaizenOps sync.
"""

from __future__ import annotations

from dataclasses import dataclass

from dharma_swarm import model_pool as _model_pool
from dharma_swarm.models import ProviderType


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip().lower()


# ---------------------------------------------------------------------------
# Pool projection (STEP of the model-pool consolidation)
# ---------------------------------------------------------------------------
#
# A certified lane's ``default_models`` / ``model_aliases`` are RECOGNITION sets:
# when a live agent registers with ``(provider, model)``, ``matches_provider_model``
# checks the incoming model string against these. They used to be hand-typed
# provider-specific id literals — exactly the drift the consolidation kills. They
# are now DERIVED from a ``dharma_swarm.model_pool`` entry at the FLOOR model, so
# the model-id strings live in exactly ONE place (the roster -> pool). The Kimi
# lane rides the K2.6 floor entry (never the sub-floor K2.5 literal); the GLM lane
# rides the pool's GLM entry.


def _pool_default_model(pool_id: str, provider: ProviderType) -> str:
    """The exact provider-specific model_id the pool serves for ``pool_id`` under
    ``provider`` — the certified lane's default for that provider (drift-killer
    source, never a literal). Raises at import if the pool has no such route, so a
    lane can never silently point at a provider the floor entry does not serve."""
    entry = _model_pool.get_entry(pool_id)
    if entry is None:  # pragma: no cover - guarded by import-time construction
        raise AssertionError(f"certified lane references unknown pool id {pool_id!r}")
    for route in entry.routes:
        if route.provider is provider:
            return route.model_id
    raise AssertionError(
        f"pool entry {pool_id!r} has no {provider.value!r} route for a certified lane"
    )


def _pool_model_aliases(pool_id: str) -> dict[ProviderType, tuple[str, ...]]:
    """Every (provider, model_id) the pool serves for ``pool_id``, grouped by
    provider — the lane's recognition set, sourced FROM the pool at the floor."""
    entry = _model_pool.get_entry(pool_id)
    if entry is None:  # pragma: no cover - guarded by import-time construction
        raise AssertionError(f"certified lane references unknown pool id {pool_id!r}")
    grouped: dict[ProviderType, list[str]] = {}
    for route in entry.routes:
        grouped.setdefault(route.provider, [])
        if route.model_id not in grouped[route.provider]:
            grouped[route.provider].append(route.model_id)
    return {provider: tuple(ids) for provider, ids in grouped.items()}


@dataclass(frozen=True, slots=True)
class CertifiedLane:
    profile_id: str
    label: str
    accent: str
    summary: str
    registration_id: str
    codename: str
    display_name: str
    provider_order_env: str
    default_provider_order: tuple[ProviderType, ...]
    default_models: dict[ProviderType, str]
    model_envs: dict[ProviderType, str]
    aliases: tuple[str, ...] = ()
    model_aliases: dict[ProviderType, tuple[str, ...]] | None = None

    def matches_profile_id(self, profile_id: str | None) -> bool:
        normalized = _normalize_text(profile_id)
        if not normalized:
            return False
        if normalized == _normalize_text(self.profile_id):
            return True
        return normalized in {_normalize_text(alias) for alias in self.aliases}

    def matches_alias(self, alias: str | None) -> bool:
        normalized = _normalize_text(alias)
        if not normalized:
            return False
        values = {
            _normalize_text(self.profile_id),
            _normalize_text(self.codename),
            _normalize_text(self.display_name),
            _normalize_text(self.label),
            *(_normalize_text(item) for item in self.aliases),
        }
        return normalized in values

    def matches_provider_model(
        self,
        provider: ProviderType | str | None,
        model: str | None,
    ) -> bool:
        provider_name = _normalize_text(
            provider.value if isinstance(provider, ProviderType) else provider
        )
        model_name = _normalize_text(model)
        if not provider_name or not model_name:
            return False
        try:
            provider_type = ProviderType(provider_name)
        except ValueError:
            return False

        allowed = {_normalize_text(self.default_models.get(provider_type))}
        if self.model_aliases:
            allowed.update(
                _normalize_text(item)
                for item in self.model_aliases.get(provider_type, ())
            )
        allowed.discard("")
        return model_name in allowed


CERTIFIED_LANES: tuple[CertifiedLane, ...] = (
    CertifiedLane(
        profile_id="glm5_researcher",
        label="GLM-5 Cartographer",
        accent="botan",
        summary="Certified synthesis lane for repo cartography, pattern extraction, and deep investigation.",
        registration_id="lane:glm-researcher",
        codename="glm-researcher",
        display_name="GLM-5 Cartographer",
        provider_order_env="DASHBOARD_GLM_PROVIDER_ORDER",
        default_provider_order=(ProviderType.OPENROUTER,),
        default_models={
            ProviderType.OPENROUTER: _pool_default_model("glm-5", ProviderType.OPENROUTER),
        },
        model_envs={
            ProviderType.OPENROUTER: "DASHBOARD_GLM_MODEL",
        },
        aliases=(
            "glm5-researcher",
            "glm5_researcher",
            "ecosystem-synthesizer",
            "ecosystem_synthesizer",
        ),
        model_aliases=_pool_model_aliases("glm-5"),
    ),
    CertifiedLane(
        profile_id="kimi_k25_scout",
        label="Kimi K2.6 Scout",
        accent="bengara",
        summary="Certified long-context scout for reconnaissance, evidence gathering, and operator-ready synthesis.",
        registration_id="lane:kimi-scout",
        codename="kimi-scout",
        display_name="Kimi K2.6 Scout",
        provider_order_env="DASHBOARD_KIMI_PROVIDER_ORDER",
        default_provider_order=(ProviderType.OPENROUTER,),
        default_models={
            # K2.6 is the operator FLOOR; the lane rides the floor pool entry,
            # never the sub-floor K2.5 literal.
            ProviderType.OPENROUTER: _pool_default_model("kimi-k2.6", ProviderType.OPENROUTER),
        },
        model_envs={
            ProviderType.OPENROUTER: "DASHBOARD_KIMI_MODEL",
        },
        aliases=(
            "kimi-k25-scout",
            "kimi_k25_scout",
            "kimi-scout",
            "cyber-kimi25",
        ),
        model_aliases=_pool_model_aliases("kimi-k2.6"),
    ),
    CertifiedLane(
        profile_id="sonnet46_operator",
        label="Claude Sonnet 4.6",
        accent="fuji",
        summary="Certified execution peer for strong local tooling, disciplined edits, and reliable operator handoffs.",
        registration_id="lane:sonnet-relay",
        codename="sonnet-relay",
        display_name="Claude Sonnet 4.6",
        provider_order_env="DASHBOARD_SONNET_PROVIDER_ORDER",
        default_provider_order=(ProviderType.CLAUDE_CODE,),
        default_models={
            ProviderType.CLAUDE_CODE: "claude-sonnet-4-6",
        },
        model_envs={},
        aliases=(
            "sonnet46-operator",
            "sonnet46_operator",
            "claude-sonnet-4-6",
            "sonnet-relay",
        ),
        model_aliases={
            ProviderType.CLAUDE_CODE: (
                "claude-sonnet-4-6",
                "sonnet",
                "sonnet 4.6",
                "claude sonnet 4.6",
            ),
            ProviderType.ANTHROPIC: ("claude-sonnet-4-6",),
        },
    ),
)


CERTIFIED_LANE_BY_PROFILE_ID = {
    lane.profile_id: lane for lane in CERTIFIED_LANES
}


def get_certified_lane(profile_id: str | None) -> CertifiedLane | None:
    normalized = _normalize_text(profile_id)
    if not normalized:
        return None
    for lane in CERTIFIED_LANES:
        if lane.matches_profile_id(normalized):
            return lane
    return None


def match_certified_lane(
    *,
    profile_id: str | None = None,
    provider: ProviderType | str | None = None,
    model: str | None = None,
    alias: str | None = None,
) -> CertifiedLane | None:
    direct = get_certified_lane(profile_id)
    if direct is not None:
        return direct
    for lane in CERTIFIED_LANES:
        if alias and lane.matches_alias(alias):
            return lane
        if provider and model and lane.matches_provider_model(provider, model):
            return lane
    return None


__all__ = [
    "CERTIFIED_LANES",
    "CERTIFIED_LANE_BY_PROFILE_ID",
    "CertifiedLane",
    "get_certified_lane",
    "match_certified_lane",
]
