"""Shared model and agent routing manifest endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query

from api.models import ApiResponse
from dharma_swarm.models import ProviderType
from dharma_swarm.operator_core import (
    build_agent_routes_payload,
    build_model_policy_summary,
    build_routing_decision_payload,
    build_routing_manifest_payload,
    normalize_adapter_catalog,
    normalize_agent_assignments,
    normalize_legacy_targets,
)
from dharma_swarm.provider_matrix import build_default_matrix_targets
from dharma_swarm.tui import model_routing

router = APIRouter(prefix="/api", tags=["routing"])


def _get_swarm():
    from api.main import get_swarm

    return get_swarm()


def _bridge_provider_id(provider: ProviderType) -> str | None:
    return model_routing.ADAPTER_MAP.get(provider)


def _target_alias(model: str) -> str:
    normalized = model.split("/")[-1].split(":")[0].strip().lower()
    normalized = normalized.replace("_", "-").replace(" ", "-")
    return normalized.strip("-") or "model"


def _build_model_policy(*, provider: str, model: str, strategy: str) -> dict[str, Any]:
    selected_provider = provider.strip().lower() or "codex"
    selected_model = model.strip() or model_routing.default_target().model_id
    resolved_strategy = model_routing.resolve_strategy(strategy) or "responsive"
    default_target = model_routing.default_target()
    raw_targets = build_default_matrix_targets(
        profile="live25", include_unavailable=True
    )
    return build_model_policy_summary(
        raw_targets=raw_targets,
        selected_provider=selected_provider,
        selected_model=selected_model,
        strategy=resolved_strategy,
        strategies=model_routing.ROUTING_STRATEGIES,
        default_provider_id=default_target.provider_id,
        default_model_id=default_target.model_id,
        provider_id_for_target=lambda target: _bridge_provider_id(target.provider),
        alias_for_model=_target_alias,
    )


async def _adapter_catalog_entries() -> list[dict[str, Any]]:
    raw_targets = build_default_matrix_targets(
        profile="live25", include_unavailable=True
    )
    providers: dict[str, dict[str, Any]] = {}
    for target in raw_targets:
        provider_id = _bridge_provider_id(target.provider)
        if provider_id is None:
            continue
        entry = providers.setdefault(
            provider_id,
            {
                "provider_id": provider_id,
                "default_model": "",
                "models": [],
            },
        )
        model_id = str(getattr(target, "model", "") or "").strip()
        if not model_id:
            continue
        if not entry["default_model"]:
            entry["default_model"] = model_id
        route_models = entry["models"]
        if any(str(item.get("id", "")).strip() == model_id for item in route_models):
            continue
        route_models.append(
            {
                "id": model_id,
                "display_name": model_id,
                "capabilities": [],
            }
        )
    return list(providers.values())


def _agent_routes() -> dict[str, Any]:
    return {
        "routes": [
            {
                "intent": "fast_repo_scan",
                "provider": "claude",
                "model_alias": "haiku-4.5",
                "reasoning": "low",
                "role": "scanner",
            },
            {
                "intent": "deep_code_work",
                "provider": "codex",
                "model_alias": "codex-5.4",
                "reasoning": "high",
                "role": "builder",
            },
            {
                "intent": "architecture_review",
                "provider": "claude",
                "model_alias": "opus-4.6",
                "reasoning": "max",
                "role": "reviewer",
            },
            {
                "intent": "open_model_bulk",
                "provider": "ollama",
                "model_alias": "glm-5",
                "reasoning": "medium",
                "role": "bulk_builder",
            },
        ],
        "openclaw": {
            "present": False,
            "readable": False,
            "agents_count": 0,
            "providers": [],
        },
        "subagent_capabilities": [
            "route by task type",
            "prefer subscription drivers for deep code work",
            "prefer open/free lanes for bulk research",
            "keep human approval for destructive actions",
        ],
    }


async def _agent_assignments() -> list[dict[str, Any]]:
    try:
        agents = await _get_swarm().list_agents()
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for agent in agents:
        rows.append(
            {
                "id": getattr(agent, "id", ""),
                "name": getattr(agent, "name", ""),
                "display_name": getattr(agent, "name", ""),
                "role": getattr(
                    getattr(agent, "role", ""), "value", getattr(agent, "role", "")
                ),
                "status": getattr(
                    getattr(agent, "status", ""), "value", getattr(agent, "status", "")
                ),
                "provider": getattr(agent, "provider", "") or "",
                "model": getattr(agent, "model", "") or "",
            }
        )
    return normalize_agent_assignments(rows)


@router.get("/routing/manifest")
async def get_routing_manifest(
    provider: str = Query("codex"),
    model: str = Query("gpt-5.4"),
    strategy: str = Query("responsive"),
) -> ApiResponse:
    """Return the canonical model and persistent-agent routing manifest."""

    try:
        policy = await asyncio.to_thread(
            _build_model_policy,
            provider=provider,
            model=model,
            strategy=strategy,
        )
        adapter_entries, assignments = await asyncio.gather(
            _adapter_catalog_entries(),
            _agent_assignments(),
        )
        adapter_catalog = normalize_adapter_catalog(
            adapter_entries, policy_targets=policy.get("targets", [])
        )
        legacy_targets = normalize_legacy_targets(
            hard_targets=model_routing.MODEL_TARGETS,
            soft_targets=model_routing._SOFT_TARGETS,
            policy_targets=policy.get("targets", []),
            adapter_catalog=adapter_catalog,
        )
        routes = _agent_routes()
        return ApiResponse(
            data=build_routing_manifest_payload(
                model_policy=policy,
                routing_decision_payload=build_routing_decision_payload(policy),
                agent_routes_payload=build_agent_routes_payload(routes),
                adapter_catalog=adapter_catalog,
                legacy_targets=legacy_targets,
                agent_assignments=assignments,
            )
        )
    except Exception as exc:
        return ApiResponse(status="error", error=str(exc), data={})
