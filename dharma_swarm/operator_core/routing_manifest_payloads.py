"""Shared routing manifest payloads for terminal and dashboard surfaces."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

ROUTING_MANIFEST_VERSION = "v1"
ROUTING_MANIFEST_DOMAIN = "routing_manifest"


def _route_key(provider: str, model: str) -> str:
    provider = provider.strip()
    model = model.strip()
    return f"{provider}:{model}" if provider and model else ""


def _string(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _target_route_keys(targets: Iterable[Mapping[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for target in targets:
        key = _route_key(_string(target.get("provider")), _string(target.get("model")))
        if key:
            keys.add(key)
    return keys


def normalize_adapter_catalog(
    providers: Iterable[Mapping[str, Any]],
    *,
    policy_targets: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Normalize provider handshake/catalog entries and annotate route-policy coverage."""

    route_keys = _target_route_keys(policy_targets)
    catalog: list[dict[str, Any]] = []
    seen: set[str] = set()
    for provider_entry in providers:
        provider_id = _string(provider_entry.get("provider_id"))
        if not provider_id:
            continue
        default_model = _string(provider_entry.get("default_model"))
        models = provider_entry.get("models", [])
        if not isinstance(models, list):
            models = []
        for model_entry in models:
            model_record = _as_mapping(model_entry)
            model_id = _string(model_record.get("id") or model_record.get("model_id"))
            if not model_id:
                continue
            route_id = _route_key(provider_id, model_id)
            if route_id in seen:
                continue
            seen.add(route_id)
            catalog.append(
                {
                    "route_id": route_id,
                    "provider": provider_id,
                    "model": model_id,
                    "display_name": _string(model_record.get("display_name"), model_id),
                    "capabilities": [str(item) for item in model_record.get("capabilities", [])]
                    if isinstance(model_record.get("capabilities"), list)
                    else [],
                    "default_for_provider": bool(default_model and model_id == default_model),
                    "policy_selectable": route_id in route_keys,
                }
            )
    return catalog


def normalize_legacy_targets(
    *,
    hard_targets: Iterable[Any],
    soft_targets: Iterable[Any],
    policy_targets: Iterable[Mapping[str, Any]] = (),
    adapter_catalog: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Normalize legacy model aliases without making them authoritative routes."""

    route_keys = _target_route_keys(policy_targets)
    catalog_keys = _target_route_keys(
        {
            "provider": item.get("provider"),
            "model": item.get("model"),
        }
        for item in adapter_catalog
    )
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source, targets in (("legacy_hard_target", hard_targets), ("legacy_soft_alias", soft_targets)):
        for target in targets:
            provider = _string(getattr(target, "provider_id", ""))
            model = _string(getattr(target, "model_id", ""))
            alias = _string(getattr(target, "alias", ""))
            if not provider or not model or not alias:
                continue
            key = (source, provider, model)
            if key in seen:
                continue
            seen.add(key)
            route_id = _route_key(provider, model)
            rows.append(
                {
                    "source": source,
                    "route_id": route_id,
                    "provider": provider,
                    "model": model,
                    "alias": alias,
                    "label": _string(getattr(target, "label", ""), alias),
                    "aliases": [str(item) for item in getattr(target, "aliases", ())],
                    "policy_selectable": route_id in route_keys,
                    "adapter_catalog": route_id in catalog_keys,
                }
            )
    return rows


def normalize_agent_assignments(agents: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize persistent/live agent model assignments for UI reconciliation."""

    assignments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for agent in agents:
        agent_id = _string(agent.get("id") or agent.get("agent_id") or agent.get("name"))
        provider = _string(agent.get("provider"))
        model = _string(agent.get("model"))
        route_id = _route_key(provider, model)
        if not agent_id or agent_id in seen:
            continue
        seen.add(agent_id)
        assignments.append(
            {
                "agent_id": agent_id,
                "name": _string(agent.get("name"), agent_id),
                "display_name": _string(agent.get("display_name") or agent.get("name"), agent_id),
                "role": _string(agent.get("role"), "general"),
                "status": _string(agent.get("status"), "unknown"),
                "provider": provider,
                "model": model,
                "route_id": route_id,
                "model_key": _string(agent.get("model_key"), route_id.replace(":", "::", 1) if route_id else ""),
            }
        )
    return assignments


def build_routing_manifest_payload(
    *,
    model_policy: Mapping[str, Any],
    routing_decision_payload: Mapping[str, Any],
    agent_routes_payload: Mapping[str, Any],
    adapter_catalog: Iterable[Mapping[str, Any]],
    legacy_targets: Iterable[Mapping[str, Any]],
    agent_assignments: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the shared model/agent routing manifest used by dashboard and terminal."""

    targets = list(model_policy.get("targets", [])) if isinstance(model_policy.get("targets"), list) else []
    catalog = list(adapter_catalog)
    legacy_rows = list(legacy_targets)
    assignments = list(agent_assignments)
    selectable_route_ids = _target_route_keys(_as_mapping(item) for item in targets)
    catalog_route_ids = _target_route_keys(_as_mapping(item) for item in catalog)
    assigned_route_ids = _target_route_keys(_as_mapping(item) for item in assignments)
    drift: list[dict[str, Any]] = []
    for route_id in sorted(selectable_route_ids - catalog_route_ids):
        drift.append({"kind": "policy_target_missing_from_adapter_catalog", "route_id": route_id})
    for route_id in sorted(assigned_route_ids - selectable_route_ids):
        drift.append({"kind": "agent_assignment_not_policy_selectable", "route_id": route_id})

    return {
        "version": ROUTING_MANIFEST_VERSION,
        "domain": ROUTING_MANIFEST_DOMAIN,
        "selected_route": _string(model_policy.get("selected_route")),
        "strategy": _string(model_policy.get("strategy"), "responsive"),
        "model_policy": dict(model_policy),
        "routing_decision": dict(routing_decision_payload),
        "agent_routes": dict(agent_routes_payload),
        "selectable_routes": targets,
        "adapter_catalog": catalog,
        "legacy_targets": legacy_rows,
        "agent_assignments": assignments,
        "counts": {
            "selectable_routes": len(targets),
            "adapter_catalog": len(catalog),
            "legacy_targets": len(legacy_rows),
            "agent_assignments": len(assignments),
            "drift": len(drift),
        },
        "drift": drift,
    }
