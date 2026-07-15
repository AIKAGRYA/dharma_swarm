"""Physical-provider transport policy for :mod:`dharma_swarm.providers`.

Logical provider names are useful routing labels, but two labels can resolve to
the same endpoint.  This module keeps that physical-lane policy separate from
provider implementations: it filters unavailable/dead-key lanes, deduplicates
shared transports, and records which logical aliases were removed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
import logging
import random
from typing import Any

from dharma_swarm.key_oracle import live_providers
from dharma_swarm.models import LLMResponse, ProviderType
from dharma_swarm.provider_policy import (
    ProviderPolicyRouter,
    ProviderRouteDecision,
    ProviderRouteRequest,
)
from dharma_swarm.runtime_provider import runtime_provider_transport_identity

logger = logging.getLogger(__name__)

KeyLivenessProvider = Callable[[], set[str] | None]
TransportAlias = tuple[ProviderType, ProviderType, str]


def provider_instance_available(
    providers: Mapping[ProviderType, Any],
    provider_type: ProviderType,
) -> bool:
    """Return whether a logical provider has an enabled runtime instance."""
    provider = providers.get(provider_type)
    return provider is not None and bool(getattr(provider, "available", True))


def response_indicates_failure(response: LLMResponse) -> str | None:
    """Classify a provider's error-shaped response without trusting its label."""
    body = response.content.strip().lower()
    if not body:
        return "empty_response"
    if body.startswith("timeout:"):
        return "provider_timeout"
    if body.startswith(("error:", "error (rc=", "error(rc=")):
        return "provider_error"

    rate_limit_markers = (
        "rate_limit_exceeded",
        "rate limit",
        "too many requests",
        "429",
    )
    quota_markers = (
        "insufficient_quota",
        "you exceeded your current quota",
    )
    billing_markers = (
        "credit balance is too low",
        "credit balance",
        "billing hard limit",
        "your api key has been disabled",
    )
    access_denied_markers = (
        "access denied",
        "please check your network settings",
        "403",
        "forbidden",
        "unauthorized",
    )
    is_structured_error = (
        body.startswith(("{", "["))
        or '"error"' in body[:1200]
        or "'error'" in body[:1200]
        or "error code" in body[:1200]
    )
    if len(body) < 300 or is_structured_error:
        for markers, failure in (
            (rate_limit_markers, "rate_limited"),
            (quota_markers, "quota_exhausted"),
            (billing_markers, "billing_exhausted"),
            (access_denied_markers, "access_denied"),
        ):
            if any(marker in body for marker in markers):
                return failure
    return None


def provider_transport_identity(
    providers: Mapping[ProviderType, Any],
    provider_type: ProviderType,
) -> str:
    """Resolve a secret-free physical identity for one logical provider."""
    provider_instance = providers[provider_type]
    return runtime_provider_transport_identity(
        getattr(provider_instance, "runtime_config", None),
        logical_provider=provider_type,
        provider_instance=provider_instance,
    )


def deduplicate_physical_provider_chain(
    chain: list[ProviderType],
    *,
    providers: Mapping[ProviderType, Any],
    preferred_logical_lanes: list[ProviderType] | None = None,
) -> tuple[list[ProviderType], list[TransportAlias]]:
    """Keep one logical lane per physical transport, with provenance."""
    preferred_by_identity: dict[str, ProviderType] = {}
    for provider in preferred_logical_lanes or []:
        preferred_by_identity.setdefault(
            provider_transport_identity(providers, provider),
            provider,
        )

    deduplicated: list[ProviderType] = []
    retained_by_identity: dict[str, ProviderType] = {}
    aliases: list[TransportAlias] = []
    for provider in chain:
        identity = provider_transport_identity(providers, provider)
        preferred = preferred_by_identity.get(identity)
        if preferred is not None and provider != preferred:
            aliases.append((provider, preferred, identity))
            continue
        retained = retained_by_identity.get(identity)
        if retained is not None:
            aliases.append((provider, retained, identity))
            continue
        retained_by_identity[identity] = provider
        deduplicated.append(provider)
    return deduplicated, aliases


def prune_dead_key_providers(
    chain: list[ProviderType],
    *,
    live_provider: KeyLivenessProvider | None = None,
) -> list[ProviderType]:
    """Drop verifiably dead keys, while failing open on uncertain evidence."""
    if not chain:
        return chain
    try:
        oracle = live_provider or live_providers
        live = oracle()
    except Exception:  # never let the oracle take down routing
        logger.warning("key_oracle raised; keeping unfiltered chain", exc_info=True)
        return chain
    if live is None:
        return chain
    filtered = [provider for provider in chain if provider.value in live]
    if not filtered:
        logger.warning(
            "key_oracle: all routed providers have dead keys (%s); "
            "keeping UNFILTERED chain to avoid a self-inflicted outage "
            "(run `dkeys test`).",
            [provider.value for provider in chain],
        )
        return chain
    if len(filtered) != len(chain):
        pruned = [provider.value for provider in chain if provider.value not in live]
        logger.info("key_oracle: pruned dead-key providers from chain: %s", pruned)
    return filtered


def provider_chain_with_transport_provenance(
    decision: ProviderRouteDecision,
    *,
    providers: Mapping[ProviderType, Any],
    available_provider_types: list[ProviderType] | None = None,
    live_provider: KeyLivenessProvider | None = None,
) -> tuple[list[ProviderType], list[TransportAlias]]:
    """Build an authorized, live, physically distinct execution chain."""
    available = (
        set(providers)
        if available_provider_types is None
        else set(available_provider_types)
    )
    chain: list[ProviderType] = []
    for provider in [decision.selected_provider, *decision.fallback_providers]:
        if (
            provider in available
            and provider_instance_available(providers, provider)
            and provider not in chain
        ):
            chain.append(provider)
    live_chain = prune_dead_key_providers(chain, live_provider=live_provider)
    return deduplicate_physical_provider_chain(live_chain, providers=providers)


def route_request_with_transport_provenance(
    route_request: ProviderRouteRequest,
    *,
    providers: Mapping[ProviderType, Any],
    policy_router: ProviderPolicyRouter,
    available_provider_types: list[ProviderType] | None = None,
) -> ProviderRouteDecision:
    """Route across enabled physical lanes and retain alias provenance."""
    if available_provider_types is not None and not available_provider_types:
        raise RuntimeError("No available providers after routing filter")
    authorized = (
        list(providers)
        if available_provider_types is None
        else available_provider_types
    )
    available = [
        provider
        for provider in authorized
        if provider_instance_available(providers, provider)
    ]
    available, aliases = deduplicate_physical_provider_chain(
        available,
        providers=providers,
    )
    decision = policy_router.route(route_request, available_providers=available)
    return decision_with_transport_provenance(decision, aliases)


def decision_with_transport_provenance(
    decision: ProviderRouteDecision,
    aliases: list[TransportAlias],
) -> ProviderRouteDecision:
    """Remove aliased fallbacks and attach secret-free dedup reasons."""
    if not aliases:
        return decision

    dropped = {alias for alias, _retained, _identity in aliases}
    fallbacks: list[ProviderType] = []
    fallback_hints: list[str] = []
    for index, provider in enumerate(decision.fallback_providers):
        if provider in dropped:
            continue
        fallbacks.append(provider)
        if index < len(decision.fallback_model_hints):
            fallback_hints.append(decision.fallback_model_hints[index])

    reasons = list(decision.reasons)
    for alias, retained, identity in aliases:
        reason = f"physical_transport_dedup={alias.value}->{retained.value}@{identity}"
        if reason not in reasons:
            reasons.append(reason)
    return replace(
        decision,
        fallback_providers=fallbacks,
        fallback_model_hints=fallback_hints,
        reasons=reasons,
    )


def provider_key_is_verifiably_dead(
    provider: ProviderType,
    *,
    live_provider: KeyLivenessProvider | None = None,
) -> bool:
    """Return true only when the configured oracle positively excludes a key."""
    try:
        live = (live_provider or live_providers)()
    except Exception:
        logger.warning(
            "key_oracle raised while checking canary; skipping dead-key proof",
            exc_info=True,
        )
        return False
    return live is not None and provider.value not in live


def apply_canary(
    chain: list[ProviderType],
    *,
    providers: Mapping[ProviderType, Any],
    canary_percent: float,
    canary_provider: ProviderType | None,
    canary_model_hint: str | None,
    model_hints: dict[ProviderType, str | None],
    available_provider_types: list[ProviderType] | None = None,
    live_provider: KeyLivenessProvider | None = None,
) -> tuple[list[ProviderType], bool]:
    """Optionally front-load a live, authorized canary provider."""
    authorized = (
        set(providers)
        if available_provider_types is None
        else set(available_provider_types)
    )
    if (
        canary_percent <= 0
        or canary_provider is None
        or canary_provider not in authorized
        or not provider_instance_available(providers, canary_provider)
        or provider_key_is_verifiably_dead(
            canary_provider,
            live_provider=live_provider,
        )
    ):
        return (chain, False)
    if random.random() * 100.0 >= canary_percent:
        return (chain, False)
    reordered = [canary_provider] + [item for item in chain if item != canary_provider]
    if canary_model_hint:
        model_hints[canary_provider] = canary_model_hint
    return (reordered, True)


__all__ = [
    "KeyLivenessProvider",
    "TransportAlias",
    "apply_canary",
    "decision_with_transport_provenance",
    "deduplicate_physical_provider_chain",
    "provider_chain_with_transport_provenance",
    "provider_instance_available",
    "provider_key_is_verifiably_dead",
    "provider_transport_identity",
    "prune_dead_key_providers",
    "response_indicates_failure",
    "route_request_with_transport_provenance",
]
