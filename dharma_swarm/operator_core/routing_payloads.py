"""JSON-ready routing payload builders for the shared operator core."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict
from typing import Any

from .adapters import routing_decision_from_policy

ROUTING_PAYLOAD_VERSION = "v1"
ROUTING_DECISION_DOMAIN = "routing_decision"
AGENT_ROUTES_DOMAIN = "agent_routes"


def build_routing_decision_payload(
    policy: dict[str, Any],
    *,
    reason: str = "selected by current routing policy",
) -> dict[str, Any]:
    """Build a canonical routing payload from bridge model-policy state."""

    decision = routing_decision_from_policy(policy, reason=reason)
    return {
        "version": ROUTING_PAYLOAD_VERSION,
        "domain": ROUTING_DECISION_DOMAIN,
        "decision": asdict(decision),
        "strategies": list(policy.get("strategies", [])),
        "targets": list(policy.get("targets", [])),
        "fallback_targets": list(policy.get("fallback_chain", [])),
    }


def build_agent_routes_payload(routes: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Build a versioned agent-routes payload from bridge route summaries."""

    route_items = routes if isinstance(routes, list) else routes.get("routes", [])
    openclaw = {} if isinstance(routes, list) else routes.get("openclaw", {})
    subagent_capabilities = [] if isinstance(routes, list) else routes.get("subagent_capabilities", [])
    return {
        "version": ROUTING_PAYLOAD_VERSION,
        "domain": AGENT_ROUTES_DOMAIN,
        "routes": list(route_items),
        "openclaw": dict(openclaw),
        "subagent_capabilities": list(subagent_capabilities),
    }


def build_model_policy_summary(
    *,
    raw_targets: Iterable[Any],
    selected_provider: str,
    selected_model: str,
    strategy: str,
    strategies: Iterable[str],
    default_provider_id: str,
    default_model_id: str,
    provider_id_for_target: Callable[[Any], str | None],
    alias_for_model: Callable[[str], str],
) -> dict[str, Any]:
    """Build the canonical terminal model-policy summary from matrix targets."""

    seen_routes: set[tuple[str, str]] = set()
    targets: list[dict[str, Any]] = []
    for target in raw_targets:
        provider_id = provider_id_for_target(target)
        if provider_id is None:
            continue
        model = str(getattr(target, "model", ""))
        route = (provider_id, model)
        if route in seen_routes:
            continue
        seen_routes.add(route)
        lane_role_value = getattr(getattr(target, "lane_role", ""), "value", str(getattr(target, "lane_role", "")))
        tier = str(getattr(target, "tier", ""))
        availability = "ready" if bool(getattr(target, "available", False)) else "unavailable"
        targets.append(
            {
                "alias": alias_for_model(model),
                "provider": provider_id,
                "model": model,
                "label": f"{model} [{provider_id} | {lane_role_value.replace('_', ' ')} | {tier} | {availability}]",
                "lane_role": lane_role_value,
                "tier": tier,
                "available": bool(getattr(target, "available", False)),
                "availability_reason": getattr(target, "availability_reason", ""),
                "config_source": getattr(target, "config_source", ""),
            }
        )

    selected_available = any(
        target["provider"] == selected_provider and target["model"] == selected_model
        for target in targets
    )
    if not selected_available and targets:
        fallback_target = next((target for target in targets if target["provider"] == "codex"), targets[0])
        selected_provider = str(fallback_target["provider"])
        selected_model = str(fallback_target["model"])

    active_target = next(
        (
            target
            for target in targets
            if target["provider"] == selected_provider and target["model"] == selected_model
        ),
        None,
    )
    fallback_chain = [
        {
            "alias": str(target["alias"]),
            "provider": str(target["provider"]),
            "model": str(target["model"]),
            "label": str(target["label"]),
        }
        for target in targets
        if not (target["provider"] == selected_provider and target["model"] == selected_model)
    ][:6]
    return {
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "selected_route": f"{selected_provider}:{selected_model}",
        "strategy": strategy,
        "strategies": list(strategies),
        "default_route": (
            f"{targets[0]['provider']}:{targets[0]['model']}"
            if targets
            else f"{default_provider_id}:{default_model_id}"
        ),
        "active_label": str(active_target["label"]) if active_target else selected_model,
        "fallback_chain": fallback_chain,
        "targets": targets,
    }
