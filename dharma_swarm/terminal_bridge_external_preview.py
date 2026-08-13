"""Typed, preview-only chat routes that cannot promote Helm OnCall truth.

These identities are deliberately separate from the canonical model roster.  A
preview route grants bounded attempt authority only; it never asserts that the
provider served the requested model or that a locked Helm seat is OnCall.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from dharma_swarm.model_catalog import (
    HELM_PREVIEW_CLAUDE_FABLE_5_MODEL_ID,
    HELM_PREVIEW_GPT_5_6_SOL_MODEL_ID,
    HELM_PREVIEW_GROK_4_6_MODEL_ID,
)
from dharma_swarm.model_pool import FORGE_KIMI_CODE_MODEL_ID
from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    RateLimitEvent,
    SessionStart,
    UsageReport,
)

GPT_5_6_SOL_MODEL_ID = HELM_PREVIEW_GPT_5_6_SOL_MODEL_ID
CLAUDE_FABLE_5_MODEL_ID = HELM_PREVIEW_CLAUDE_FABLE_5_MODEL_ID
KIMI_K3_MODEL_ID = FORGE_KIMI_CODE_MODEL_ID
GROK_4_6_MODEL_ID = HELM_PREVIEW_GROK_4_6_MODEL_ID


@dataclass(frozen=True, slots=True)
class ExternalPreviewRoute:
    alias: str
    provider_id: str
    model_id: str
    label: str
    account_lane: str
    enabled: bool = True
    attempt_authorized: bool = True
    exact_model_proven: bool = False
    preview_only: bool = True
    helm_on_call_eligible: bool = False
    availability_reason: str = "exact_model_unproven"

    @property
    def route_id(self) -> str:
        return f"{self.provider_id}:{self.model_id}"


EXTERNAL_PREVIEW_ROUTES: tuple[ExternalPreviewRoute, ...] = (
    ExternalPreviewRoute(
        alias="gpt-5.6-sol",
        provider_id="codex_text",
        model_id=GPT_5_6_SOL_MODEL_ID,
        label="GPT-5.6 Sol · ChatGPT account · text-only preview",
        account_lane="chatgpt_subscription",
    ),
    ExternalPreviewRoute(
        alias="claude-fable-5",
        provider_id="claude",
        model_id=CLAUDE_FABLE_5_MODEL_ID,
        label="Claude Fable 5 · Anthropic account · no-tools",
        account_lane="claude_subscription",
    ),
    ExternalPreviewRoute(
        alias="kimi-k3",
        provider_id="kimi_code",
        model_id=KIMI_K3_MODEL_ID,
        label="Kimi K3 · first-party account · no-tools preview",
        account_lane="kimi_code_api",
    ),
    ExternalPreviewRoute(
        alias="grok-4.6",
        provider_id="grok_oauth",
        model_id=GROK_4_6_MODEL_ID,
        label="Grok 4.6 · Grok account · no-tools preview",
        account_lane="grok_oauth",
    ),
)

_ROUTES_BY_ID = {route.route_id: route for route in EXTERNAL_PREVIEW_ROUTES}
_SAFE_SESSION_INFO_KEYS = frozenset(
    {
        "exact_model_proven",
        "requested_model",
        "served_identity_source",
        "served_model",
        "tool_authority",
        "tools_disabled",
    }
)


def sanitize_external_preview_event(event: CanonicalEventType) -> CanonicalEventType:
    """Drop provider-private metadata after the no-tools scan has consumed it."""

    event.raw = None
    if isinstance(event, RateLimitEvent):
        raise ValueError("preview rate-limit metadata is not admissible")
    if isinstance(event, SessionStart):
        event.system_info = {
            key: value
            for key, value in event.system_info.items()
            if key in _SAFE_SESSION_INFO_KEYS
        }
    elif isinstance(event, UsageReport):
        token_values = (
            event.input_tokens,
            event.output_tokens,
            event.cache_read_tokens,
            event.cache_write_tokens,
            event.thinking_tokens,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in token_values
        ):
            raise ValueError("preview usage metadata is invalid")
        cost = event.total_cost_usd
        if cost is not None:
            if isinstance(cost, bool) or not isinstance(cost, (int, float)):
                raise ValueError("preview usage metadata is invalid")
            cost = float(cost)
            if not math.isfinite(cost) or cost < 0:
                raise ValueError("preview usage metadata is invalid")
            event.total_cost_usd = cost
        event.model_breakdown = {}
    return event


def external_preview_route(
    provider_id: str,
    model_id: str,
) -> ExternalPreviewRoute | None:
    """Return an exact preview route; aliases and partial identities never match."""

    return _ROUTES_BY_ID.get(
        f"{str(provider_id or '').strip().lower()}:{str(model_id or '').strip()}"
    )


def external_preview_targets(
    available_provider_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Project attempt authority without turning it into proof."""

    providers = {str(item).strip().lower() for item in available_provider_ids}
    targets: list[dict[str, Any]] = []
    for route in EXTERNAL_PREVIEW_ROUTES:
        adapter_available = route.provider_id in providers
        selectable = (
            adapter_available and route.enabled and route.attempt_authorized
        )
        reason = route.availability_reason
        if not adapter_available:
            reason = "terminal_adapter_missing"
        targets.append(
            {
                "alias": route.alias,
                "provider": route.provider_id,
                "model": route.model_id,
                "label": route.label,
                "route_id": route.route_id,
                "route_state": "unverified" if selectable else "unavailable",
                "picker_visible": True,
                "selectable": selectable,
                "chat_executable": selectable,
                "attempt_authorized": selectable,
                "exact_model_proven": False,
                "preview_only": route.preview_only,
                "helm_on_call_eligible": route.helm_on_call_eligible,
                "available": False,
                "availability_reason": reason,
                "account_lane": route.account_lane,
                "pool_id": None,
                "tier": "preview",
                "lane": "account_preview",
                "status": "unverified" if selectable else "unavailable",
                "available_routes": [],
            }
        )
    return targets


def explicit_external_preview_lane(
    provider_id: str,
    model_id: str,
    available_provider_ids: Iterable[str],
) -> tuple[str, str, dict[str, Any], str] | None:
    """Resolve a singleton preview lane, never a cross-provider fallback."""

    route = external_preview_route(provider_id, model_id)
    providers = {str(item).strip().lower() for item in available_provider_ids}
    if (
        route is None
        or not route.enabled
        or not route.attempt_authorized
        or route.provider_id not in providers
    ):
        return None
    return (
        route.provider_id,
        route.model_id,
        {},
        "explicit account preview; exact route; no fallback",
    )


def default_external_preview_route(
    available_provider_ids: Iterable[str],
) -> tuple[str, str] | None:
    """Choose the first enabled account preview without implying proof."""

    providers = {str(item).strip().lower() for item in available_provider_ids}
    for route in EXTERNAL_PREVIEW_ROUTES:
        if (
            route.enabled
            and route.attempt_authorized
            and route.provider_id in providers
        ):
            return route.provider_id, route.model_id
    return None
