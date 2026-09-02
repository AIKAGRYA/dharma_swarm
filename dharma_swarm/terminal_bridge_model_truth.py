"""Truth-preserving helpers for terminal model policy projections."""

from __future__ import annotations

from typing import Any

from dharma_swarm import key_oracle, model_status
from dharma_swarm.model_hierarchy import CANONICAL_SEED_ORDER, intelligence_order
from dharma_swarm.tui import model_routing

_EXTERNAL_PREVIEW_ORACLE_PROVIDERS: dict[str, tuple[str, ...]] = {
    "claude": ("claude_code",),
    "codex_text": ("codex",),
    "grok_oauth": ("xai",),
    "kimi_code": ("kimi_code",),
}
_CANONICAL_PROVIDER_RANK = {
    provider.value: index
    for index, provider in enumerate(
        intelligence_order(CANONICAL_SEED_ORDER, respect_cost_tiers=False)
    )
}


def strict_verified_identities(bridge) -> set[tuple[str, str]]:
    """Return only identities admitted by the seven-seat evaluator.

    Generic liveness and model-status receipts are deliberately ignored here:
    neither is authority to claim that a provider served the requested model.
    """

    projection = getattr(bridge, "_helm_on_call_projection", None)
    identities: set[tuple[str, str]] = set()
    for row in getattr(projection, "seats", ()):
        if getattr(row, "verdict", None) is not model_status.RouteVerdict.ON_CALL:
            continue
        evidence = getattr(row, "evidence", None)
        provider = str(getattr(evidence, "served_provider", "") or "").strip().lower()
        model = str(getattr(evidence, "served_model", "") or "").strip()
        if provider and model:
            identities.add((provider, model))
    return identities


def identity_verified(
    *,
    route_statuses: list[Any],
    oracle_providers: list[str],
    model_id: str,
    strict_identities: set[tuple[str, str]],
) -> bool:
    candidate_identities = {
        (
            str(getattr(route_status, "provider", "")).strip().lower(),
            str(getattr(route_status, "model_id", "")).strip(),
        )
        for route_status in route_statuses
        if str(getattr(route_status, "provider", "")).strip()
        and str(getattr(route_status, "model_id", "")).strip()
    }
    candidate_identities.update((provider, model_id) for provider in oracle_providers)
    return bool(candidate_identities & strict_identities)


def target_hierarchy_rank(
    target: dict[str, Any], strategy: str | None = "responsive"
) -> tuple[int, int, int]:
    """Power-first rank: canonical before preview, strategy order, then power.

    A preview-only lane never outranks a canonical floor lane, and within the
    canonical set the strategy's fallback order wins before the provider's
    raw intelligence seed. The historical cheap-first seed is not consulted.
    """

    order = model_routing.strategy_fallback_order(strategy)
    alias = str(target.get("alias", ""))
    strategy_rank = order.index(alias) if alias in order else len(order)
    provider_ranks = [
        _CANONICAL_PROVIDER_RANK[provider]
        for provider in target.get("oracle_providers", [])
        if provider in _CANONICAL_PROVIDER_RANK
    ]
    # Providers outside the canonical registry remain deterministically last.
    return (
        1 if bool(target.get("preview_only")) else 0,
        strategy_rank,
        min(provider_ranks, default=len(_CANONICAL_PROVIDER_RANK)),
    )


def fallback_notice(
    *, configured_route: str, selected_route: str | None
) -> dict[str, Any]:
    if selected_route is None:
        return {
            "kind": "no_usable_lane",
            "configured_route": configured_route,
            "selected_route": None,
            "message": (
                f"No usable model lane for {configured_route} "
                "(no dispatchable terminal route)"
            ),
        }
    return {
        "kind": "live_fallback",
        "configured_route": configured_route,
        "selected_route": selected_route,
        "message": (
            f"Live fallback: {configured_route} -> {selected_route} "
            "(configured route not usable now)"
        ),
    }


def external_preview_oracle_providers(provider_id: str) -> list[str]:
    """Return the oracle provider IDs that can back a preview transport."""

    return list(_EXTERNAL_PREVIEW_ORACLE_PROVIDERS.get(provider_id, ()))


def preview_provider_dispatchable(provider_id: str) -> bool:
    oracle_providers = set(external_preview_oracle_providers(provider_id))
    return bool(oracle_providers & key_oracle.dispatchable_cached())


__all__ = [
    "external_preview_oracle_providers",
    "fallback_notice",
    "identity_verified",
    "preview_provider_dispatchable",
    "strict_verified_identities",
    "target_hierarchy_rank",
]
