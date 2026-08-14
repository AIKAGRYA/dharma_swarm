"""Model policy and governed lane selection for terminal bridge chat."""

from __future__ import annotations

import os
from typing import Any

from dharma_swarm import model_status
from dharma_swarm.terminal_bridge_external_preview import (
    explicit_external_preview_lane,
    external_preview_route,
    external_preview_targets,
)
from dharma_swarm.tui import model_routing

_SLICE1_CHAT_PROVIDER_IDS = frozenset(
    {"claude", "codex_text", "grok_oauth", "kimi_code", "ollama", "openrouter"}
)
_DEDICATED_PREVIEW_PROVIDER_IDS = frozenset({"codex_text", "grok_oauth", "kimi_code"})


def _build_model_policy_summary(
    bridge, *, selected_provider: str, selected_model: str, strategy: str
) -> dict[str, Any]:
    strategy = model_routing.resolve_strategy(strategy) or "responsive"
    projection = model_status.floor_model_status()
    status_by_model_id: dict[str, Any] = {}
    for projected in projection.models:
        status_by_model_id[projected.id] = projected
        for route_status in projected.route_statuses:
            status_by_model_id[route_status.model_id] = projected

    terminal_providers = bridge._available_provider_ids()
    local_attempt_cache: dict[str, bool] = {}
    seen_routes: set[tuple[str, str]] = set()
    targets: list[dict[str, Any]] = []
    for target in model_routing.all_targets():
        provider_id = target.provider_id
        route = (provider_id, target.model_id)
        if route in seen_routes:
            continue
        seen_routes.add(route)
        projected = status_by_model_id.get(target.model_id)
        provider_values = {provider.value for provider in target.pool_providers}
        route_statuses = (
            [
                route_status
                for route_status in projected.route_statuses
                if route_status.provider in provider_values
            ]
            if projected is not None
            else []
        )
        model_available = any(
            route_status.status == "live_routable" for route_status in route_statuses
        )
        exact_model_proven = bool(
            projected is not None
            and getattr(projected.verification, "status", None) == "verified"
        )
        adapter_available = provider_id in terminal_providers
        oracle_unverified = bool(route_statuses) and all(
            route_status.status == "unverified"
            and route_status.reason == "key_status_unknown"
            for route_status in route_statuses
        )
        local_attempt_authorized = False
        if adapter_available and oracle_unverified:
            if provider_id not in local_attempt_cache:
                local_attempt_cache[provider_id] = bridge._local_cli_attempt_authorized(
                    provider_id
                )
            local_attempt_authorized = local_attempt_cache[provider_id]
        chat_executable = provider_id in {"claude", "openrouter"}
        selectable = (
            adapter_available
            and chat_executable
            and (model_available or local_attempt_authorized)
        )
        if (
            adapter_available
            and not chat_executable
            and (model_available or local_attempt_authorized)
        ):
            route_state = "unavailable"
            availability_reason = "terminal_chat_transport_unsupported"
        elif model_available and adapter_available:
            route_state = "ready" if exact_model_proven else "unverified"
            availability_reason = None if exact_model_proven else "exact_model_unproven"
        elif local_attempt_authorized:
            route_state = "unverified"
            availability_reason = "local_cli_auth_unverified"
        elif model_available and not adapter_available:
            route_state = "unavailable"
            availability_reason = "terminal_adapter_missing"
        else:
            route_state = "unavailable"
            availability_reason = (
                getattr(projected, "unavailable_reason", None) or "no_live_route"
                if projected is not None
                else "model_status_missing"
            )
        targets.append(
            {
                "alias": target.alias,
                "provider": provider_id,
                "model": target.model_id,
                "label": target.label,
                "route_id": f"{provider_id}:{target.model_id}",
                "route_state": route_state,
                "picker_visible": selectable,
                "selectable": selectable,
                "chat_executable": chat_executable,
                "exact_model_proven": exact_model_proven,
                "available": model_available,
                "availability_reason": availability_reason,
                "pool_id": getattr(projected, "id", None),
                "tier": getattr(projected, "tier", "unknown"),
                "lane": getattr(projected, "lane", "floor"),
                "status": getattr(projected, "status", "unavailable"),
                "available_routes": list(getattr(projected, "available_routes", [])),
            }
        )

    preview_model = bridge._local_preview_model()
    preview_selectable = bool(preview_model and "ollama" in terminal_providers)
    if preview_model:
        targets.append(
            {
                "alias": "local-preview",
                "provider": "ollama",
                "model": preview_model,
                "label": (f"{preview_model} (local preview; not a Helm OnCall seat)"),
                "route_id": f"ollama:{preview_model}",
                "route_state": "unverified",
                "picker_visible": preview_selectable,
                "selectable": preview_selectable,
                "chat_executable": preview_selectable,
                "exact_model_proven": False,
                "preview_only": True,
                "helm_on_call_eligible": False,
                "available": False,
                "availability_reason": (
                    "local_preview_exact_model_unproven"
                    if preview_selectable
                    else "terminal_adapter_missing"
                ),
                "pool_id": None,
                "tier": "preview",
                "lane": "local_preview",
                "status": "unverified",
                "available_routes": [],
            }
        )

    preview_targets = external_preview_targets(terminal_providers)
    preview_route_ids = {str(target["route_id"]) for target in preview_targets}
    # A preview route can intentionally reuse a canonical provider/model
    # identity (Kimi K3 does).  Its narrower authority must win instead of
    # leaving two contradictory picker rows where the first silently
    # regains fallback or Helm-promotion semantics.
    targets = [
        target
        for target in targets
        if str(target.get("route_id", "")) not in preview_route_ids
    ]
    targets.extend(preview_targets)

    selected_available = any(
        target["provider"] == selected_provider
        and target["model"] == selected_model
        and bool(target.get("selectable"))
        for target in targets
    )
    if not selected_available and targets:
        selectable_targets = [
            target for target in targets if bool(target.get("selectable"))
        ]
        fallback_target = selectable_targets[0] if selectable_targets else targets[0]
        selected_provider = str(fallback_target["provider"])
        selected_model = str(fallback_target["model"])

    active_target = next(
        (
            target
            for target in targets
            if target["provider"] == selected_provider
            and target["model"] == selected_model
        ),
        None,
    )
    selected_is_preview = bool(active_target and active_target.get("preview_only"))
    fallback_chain = (
        []
        if selected_is_preview
        else [
            {
                "alias": str(target["alias"]),
                "provider": str(target["provider"]),
                "model": str(target["model"]),
                "label": str(target["label"]),
                "route_id": str(target["route_id"]),
                "route_state": str(target["route_state"]),
                "availability_reason": target.get("availability_reason"),
            }
            for target in targets
            if not (
                target["provider"] == selected_provider
                and target["model"] == selected_model
            )
            and bool(target.get("selectable"))
        ][:6]
    )
    provider_counts: dict[str, int] = {}
    attemptable_provider_counts: dict[str, int] = {}
    for target in targets:
        provider = str(target["provider"])
        if bool(target.get("available")):
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        if bool(target.get("selectable")):
            attemptable_provider_counts[provider] = (
                attemptable_provider_counts.get(provider, 0) + 1
            )
    default_provider, default_model = bridge._terminal_default_route()
    return {
        "schema_version": model_status.MODEL_STATUS_SCHEMA_VERSION,
        "oracle_state": projection.oracle_state,
        "live_providers": projection.live_providers,
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "selected_route": f"{selected_provider}:{selected_model}",
        "strategy": strategy,
        "strategies": list(model_routing.ROUTING_STRATEGIES),
        "default_route": f"{default_provider}:{default_model}",
        "active_label": str(active_target["label"])
        if active_target
        else selected_model,
        "fallback_chain": fallback_chain,
        "targets": targets,
        "available_providers": [
            {"id": provider, "model_count": count}
            for provider, count in sorted(provider_counts.items())
        ],
        "attemptable_providers": [
            {"id": provider, "model_count": count}
            for provider, count in sorted(attemptable_provider_counts.items())
        ],
    }


def _chat_lanes(
    bridge, requested_provider: str, requested_model: str
) -> list[tuple[str, str, dict[str, Any], str]]:
    lanes: list[tuple[str, str, dict[str, Any], str]] = []
    seen: set[tuple[str, str]] = set()

    preview_model = bridge._local_preview_model()
    if requested_provider == "ollama":
        if (
            preview_model
            and requested_model == preview_model
            and "ollama" in bridge._adapters
        ):
            return [
                (
                    "ollama",
                    preview_model,
                    {},
                    "explicit local preview; no external fallback",
                )
            ]
        # An Ollama request is never rewritten onto a metered or unrelated
        # external provider. A missing/mismatched opt-in fails closed.
        return []

    preview_route = external_preview_route(requested_provider, requested_model)
    if preview_route is not None:
        explicit_lane = explicit_external_preview_lane(
            requested_provider,
            requested_model,
            bridge._adapters,
        )
        return [explicit_lane] if explicit_lane is not None else []
    if requested_provider in _DEDICATED_PREVIEW_PROVIDER_IDS:
        # These namespaces have exactly one governed route each. A typo,
        # stale served alias, or forged picker value must never fall back
        # onto a different account/provider.
        return []

    def add(
        provider_id: str, model_id: str, options: dict[str, Any], note: str
    ) -> None:
        if (
            provider_id not in _SLICE1_CHAT_PROVIDER_IDS
            or provider_id not in bridge._adapters
            or not model_id
        ):
            return
        key = (provider_id, model_id)
        if key in seen:
            return
        seen.add(key)
        lanes.append((provider_id, model_id, options, note))

    requested_target = model_routing.target_for_route(
        requested_provider, requested_model
    )
    if requested_target is None:
        requested_target = model_routing.default_target()
    policy = bridge._build_model_policy_summary(
        selected_provider=requested_target.provider_id,
        selected_model=requested_target.model_id,
        strategy="responsive",
    )
    policy_targets = {
        (str(target.get("provider", "")), str(target.get("model", ""))): target
        for target in policy.get("targets", [])
        if isinstance(target, dict)
    }
    ordered_routes = [
        (
            str(policy.get("selected_provider", "")),
            str(policy.get("selected_model", "")),
        )
    ]
    ordered_routes.extend(
        (str(target.get("provider", "")), str(target.get("model", "")))
        for target in policy.get("fallback_chain", [])
        if isinstance(target, dict)
    )
    for provider_id, model_id in ordered_routes:
        projected = policy_targets.get((provider_id, model_id))
        target = model_routing.target_for_route(provider_id, model_id)
        if (
            projected is None
            or not bool(projected.get("selectable"))
            or target is None
            or not model_routing.is_routable(target)
        ):
            continue
        options = bridge._chat_claude_options() if provider_id == "claude" else {}
        note = (
            "configured canonical route"
            if provider_id == requested_provider and model_id == requested_model
            else "canonical live fallback"
        )
        add(provider_id, model_id, options, note)
    return lanes


def _is_enabled_external_preview_route(
    bridge,
    provider_id: str,
    model_id: str,
) -> bool:
    return (
        explicit_external_preview_lane(
            provider_id,
            model_id,
            bridge._adapters,
        )
        is not None
    )


def _sealed_chat_options(
    bridge,
    provider_id: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    """Return provider options that caller input cannot weaken."""

    if provider_id == "claude":
        return bridge._chat_claude_options()
    if provider_id == "openrouter":
        timeout = options.get("timeout_sec")
        sealed: dict[str, Any] = {"require_served_identity": True}
        if timeout is not None:
            sealed["timeout_sec"] = timeout
        return sealed
    return dict(options)


def _chat_claude_model(bridge) -> str:
    # Genius strategy => Claude Opus 4.8 leads (the master lane). On the Max
    # plan every Claude tier costs the same, so cost-ranking to the cheapest
    # (Haiku, sub-floor) was pure downside — it picked a banished model.
    for target in model_routing.fallback_chain("", "", strategy="genius"):
        if target.provider_id == "claude":
            return target.model_id
    adapter = bridge._adapters.get("claude")
    if adapter is None:
        return ""
    return str(adapter.get_profile(None).model_id)


def _chat_claude_options(bridge) -> dict[str, Any]:
    try:
        budget = float(os.environ.get("DHARMA_CHAT_MAX_BUDGET_USD", "") or 0.25)
    except ValueError:
        budget = 0.25
    return {
        "permission_mode": "plan",
        "tools": "",
        "max_budget_usd": budget,
        "strict_mcp_config": True,
        "max_turns": 1,
        "raw_single_user_prompt": True,
        "scrub_metered_keys": True,
        "subscription_auth_only": True,
        "strict_preview_protocol": True,
        "setting_sources": "",
    }


__all__ = [
    "_build_model_policy_summary",
    "_chat_claude_model",
    "_chat_claude_options",
    "_chat_lanes",
    "_is_enabled_external_preview_route",
    "_sealed_chat_options",
]
