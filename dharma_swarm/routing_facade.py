"""Routing Facade — single entry point for model routing decisions.

This module consolidates the routing pipeline into a single API surface.
The internal pipeline is:

    1. ``router_v1``      — language detection + complexity classification (deterministic)
    2. ``smart_router``    — cost-tier mapping (wraps router_v1 signals)
    3. ``provider_policy`` — candidate selection + fallback chains
    4. ``swarm_router``    — multi-agent role assignment (wraps decision_router)
    5. ``model_routing``   — organism-level OrganismRouter (wraps provider_policy)

Callers that only need "give me a provider for this request" should use
this facade instead of reaching into the layers directly.

See MODEL_ROUTING_MAP.md for the full architecture.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from dharma_swarm.models import LLMRequest, ProviderType

if TYPE_CHECKING:
    from dharma_swarm.smart_router import SmartRouteDecision

logger = logging.getLogger(__name__)


def classify_and_route(request: LLMRequest) -> SmartRouteDecision:
    """Classify a request and return a cost-aware routing decision.

    This is the primary facade entry point.  It delegates to
    ``SmartRouter.route()`` which internally calls ``router_v1`` for
    complexity classification and maps to cost tiers.
    """
    from dharma_swarm.smart_router import SmartRouter

    router = SmartRouter()
    return router.route(request)


def detect_language(messages: list[dict[str, Any]]) -> str:
    """Return ISO language code for the dominant language in *messages*.

    Delegates to ``router_v1.detect_language_profile``.
    """
    from dharma_swarm.router_v1 import detect_language_profile

    profile = detect_language_profile(messages)
    return str(profile.primary_language) if profile else "en"


def select_provider(
    request: LLMRequest,
    *,
    allowed_providers: list[ProviderType] | None = None,
) -> ProviderType:
    """Select the best provider for *request*, respecting cost tiers.

    Returns the ``ProviderType`` that should handle this request.
    Raises ``RuntimeError`` if no provider is available.
    """
    decision = classify_and_route(request)
    provider = decision.provider
    if allowed_providers and provider not in allowed_providers:
        for fallback in allowed_providers:
            return fallback
    return provider


__all__ = [
    "classify_and_route",
    "detect_language",
    "select_provider",
]
