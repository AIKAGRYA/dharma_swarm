"""Compare ACTIVE_SURFACE_MANIFEST declarations with registered health checks.

The fixed registry prevents manifest-defined arbitrary shell execution."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from dharma_swarm import manifest_health_autocatalytic

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"


# ── Manifest loader ──────────────────────────────────────────────


def load_manifest() -> dict[str, Any]:
    """Parse ACTIVE_SURFACE_MANIFEST.yaml and return the full dict."""
    try:
        text = _MANIFEST_PATH.read_text(encoding="utf-8")
        return yaml.safe_load(text) or {}
    except Exception as exc:
        logger.error("Failed to load manifest: %s", exc)
        return {}


# ── Health check registry ────────────────────────────────────────
#
# Every check function receives the entity dict and the full manifest,
# and returns (passed: bool, evidence: str).


def _check_dashboard_route_exists(
    entity: dict[str, Any],
    _manifest: dict[str, Any],
) -> tuple[bool, str]:
    route = entity.get("route", "")
    if not route:
        return False, "no route declared"
    # /dashboard/foo → dashboard/src/app/dashboard/foo
    rel = route.lstrip("/")
    page_dir = _REPO_ROOT / "dashboard" / "src" / "app" / rel
    exists = page_dir.is_dir()
    return (
        exists,
        f"{'found' if exists else 'missing'}: {page_dir.relative_to(_REPO_ROOT)}",
    )


def _check_api_router_registered(
    entity: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    deps = entity.get("api_dependencies", [])
    if not deps:
        return True, "no API dependencies declared"
    registered_prefixes = {r["prefix"] for r in manifest.get("api_routers", [])}
    missing = []
    for dep in deps:
        prefix = "/" + "/".join(dep.strip("/").split("/")[:2])
        if prefix not in registered_prefixes:
            missing.append(dep)
    if missing:
        return False, f"unregistered API deps: {missing}"
    return True, f"all {len(deps)} API dep(s) have registered routers"


def _route_matches(dep: str, route_path: str) -> bool:
    """Match a declared endpoint against a real route path.

    Segment counts must agree; a route segment wrapped in ``{...}`` (a path
    parameter) matches any single dep segment.
    """
    dep_parts = dep.strip("/").split("/")
    route_parts = route_path.strip("/").split("/")
    if len(dep_parts) != len(route_parts):
        return False
    for d, r in zip(dep_parts, route_parts):
        if r.startswith("{") and r.endswith("}"):
            continue
        if d != r:
            return False
    return True


def _mounted_api_route_paths() -> list[str]:
    """Return route paths mounted on the actual FastAPI app.

    FastAPI >=0.116 no longer flattens ``include_router`` calls into
    ``app.routes`` eagerly — included routers appear as lazy
    ``_IncludedRouter`` wrappers with no ``path`` attribute, so walking
    ``app.routes`` for ``.path`` sees only the handful of default routes
    (``/openapi.json``, ``/docs``, ...) and reports every mounted endpoint
    as missing. The generated OpenAPI schema is the stable public surface
    that resolves the lazy wrappers, so use it as the source of truth and
    union in any directly-attached route paths (non-schema/websocket routes
    and older FastAPI versions).

    A failure to build the OpenAPI schema propagates to the caller, which
    records it as inspection failure rather than masking it here."""
    api_main = importlib.import_module("api.main")
    app = api_main.app
    paths: set[str] = set(app.openapi().get("paths", {}).keys())
    for route in getattr(app, "routes", []):
        path = str(getattr(route, "path", ""))
        if path:
            paths.add(path)
    return sorted(paths)


def _check_api_endpoint_registered(
    entity: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    """Endpoint-level validation: each api_dependency must resolve to a real
    registered route path, not merely a registered router prefix.

    This catches typo'd or stale endpoints under an otherwise-valid prefix
    (the gap left by :func:`_check_api_router_registered`).
    """
    deps = entity.get("api_dependencies", [])
    if not deps:
        return True, "no API dependencies declared"
    registered_prefixes = {r["prefix"] for r in manifest.get("api_routers", [])}
    try:
        route_paths = _mounted_api_route_paths()
    except Exception as exc:
        return False, f"mounted API route inspection failed: {exc}"
    missing: list[str] = []
    for dep in deps:
        prefix = "/" + "/".join(dep.strip("/").split("/")[:2])
        if prefix not in registered_prefixes:
            missing.append(f"{dep} (no registered router prefix)")
            continue
        if not any(_route_matches(dep, rp) for rp in route_paths if rp):
            missing.append(f"{dep} (no matching mounted app route)")
    if missing:
        return False, f"unregistered API endpoints: {missing}"
    return True, f"all {len(deps)} API endpoint(s) resolve to mounted app routes"


def _check_module_file_exists(
    entity: dict[str, Any],
    _manifest: dict[str, Any],
) -> tuple[bool, str]:
    module_path = entity.get("module", "")
    if not module_path:
        return False, "no module declared"
    full = _REPO_ROOT / module_path
    exists = full.is_file()
    return exists, f"{'found' if exists else 'missing'}: {module_path}"


def _check_test_file_exists(
    entity: dict[str, Any],
    _manifest: dict[str, Any],
) -> tuple[bool, str]:
    module_path = entity.get("module", "")
    if not module_path:
        return False, "no module declared"
    module_name = Path(module_path).stem
    test_file = _REPO_ROOT / "tests" / f"test_{module_name}.py"
    exists = test_file.is_file()
    return exists, f"{'found' if exists else 'missing'}: tests/test_{module_name}.py"


def _check_runtime_db_present(
    _entity: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    from dharma_swarm.daemon_config import dharma_state_dir

    state = dharma_state_dir()
    db_path = state / "state" / "runtime.db"
    exists = db_path.is_file()
    return exists, f"{'found' if exists else 'missing'}: {db_path}"


def _check_ontology_db_present(
    _entity: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    from dharma_swarm.daemon_config import dharma_state_dir

    state = dharma_state_dir()
    db_path = state / "ontology.db"
    exists = db_path.is_file()
    return exists, f"{'found' if exists else 'missing'}: {db_path}"


def _check_api_health_responds(
    _entity: dict[str, Any],
    _manifest: dict[str, Any],
) -> tuple[bool, str]:
    # This is a lightweight check — just verify the health module is importable.
    # A real HTTP probe would need the server running; we check wiring instead.
    try:
        importlib.import_module("api.routers.health")
        return True, "api.routers.health importable"
    except Exception as exc:
        return False, f"api.routers.health import failed: {exc}"


_AUTOCATALYTIC_HEALTH_CHECKS = manifest_health_autocatalytic.build_health_checks(
    lambda: _REPO_ROOT
)
_check_autocatalytic_contract_complete = _AUTOCATALYTIC_HEALTH_CHECKS[
    "autocatalytic_contract_complete"
]
_check_autocatalytic_proof_refs_exist = _AUTOCATALYTIC_HEALTH_CHECKS[
    "autocatalytic_proof_refs_exist"
]
_check_autocatalytic_node_page_exists = _AUTOCATALYTIC_HEALTH_CHECKS[
    "autocatalytic_node_page_exists"
]


# The registry: check_id → function
_HEALTH_CHECK_REGISTRY: dict[
    str,
    type[Any] | Any,
] = {
    "dashboard_route_exists": _check_dashboard_route_exists,
    "api_router_registered": _check_api_router_registered,
    "api_endpoint_registered": _check_api_endpoint_registered,
    "module_file_exists": _check_module_file_exists,
    "test_file_exists": _check_test_file_exists,
    "runtime_db_present": _check_runtime_db_present,
    "ontology_db_present": _check_ontology_db_present,
    "api_health_responds": _check_api_health_responds,
    **_AUTOCATALYTIC_HEALTH_CHECKS,
}


# ── Check runner ─────────────────────────────────────────────────


def run_checks_for_entity(
    entity: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run all health_check_ids for an entity. Returns list of results."""
    check_ids = entity.get("health_check_ids", [])
    results: list[dict[str, Any]] = []
    for check_id in check_ids:
        fn = _HEALTH_CHECK_REGISTRY.get(check_id)
        if fn is None:
            results.append(
                {
                    "check_id": check_id,
                    "passed": False,
                    "evidence": f"unknown check_id: {check_id}",
                }
            )
            continue
        try:
            passed, evidence = fn(entity, manifest)
        except Exception as exc:
            passed, evidence = False, f"check raised: {exc}"
        results.append(
            {
                "check_id": check_id,
                "passed": passed,
                "evidence": evidence,
            }
        )
    return results


def _observed_status(
    declared: str,
    check_results: list[dict[str, Any]],
) -> str:
    """Derive observed status from check results.

    The observed status is capped by the declared status: an entity
    declared as ``stub`` cannot be observed as ``live`` — it stays
    ``stub`` until the builder upgrades its declaration.  This
    prevents stubs with existing page directories from inflating
    the "live" count.
    """
    if not check_results:
        return "unknown"
    all_passed = all(c["passed"] for c in check_results)
    any_passed = any(c["passed"] for c in check_results)

    # If declared stub/frozen, cap at that level even if checks pass.
    if declared in ("stub", "frozen"):
        if all_passed:
            return declared
        if any_passed:
            return "degraded"
        return "broken"

    if all_passed:
        return "live"
    if any_passed:
        return "degraded"
    return "broken"


def _compute_gap(
    declared: str,
    observed: str,
    entity: dict[str, Any],
    check_results: list[dict[str, Any]],
) -> str:
    """Compute a human-readable gap description."""
    if declared == observed:
        return ""
    failed = [c for c in check_results if not c["passed"]]
    parts = [c["evidence"] for c in failed]
    if entity.get("next_action"):
        parts.append(f"next: {entity['next_action']}")
    return "; ".join(parts) if parts else f"declared={declared}, observed={observed}"


# ── Full report ──────────────────────────────────────────────────


def build_health_report() -> dict[str, Any]:
    """Build the complete manifest health report.

    Returns a dict with sections for each entity type, each containing
    a list of entity health records with declared/observed/gap/evidence.
    """
    manifest = load_manifest()
    if not manifest:
        return {"error": "manifest not loaded", "sections": []}

    sections: list[dict[str, Any]] = []

    # Dashboard surfaces
    surfaces = manifest.get("dashboard_surfaces", [])
    surface_records = []
    for s in surfaces:
        checks = run_checks_for_entity(s, manifest)
        declared = s.get("status", "unknown")
        observed = _observed_status(declared, checks)
        surface_records.append(
            {
                "id": s["id"],
                "label": s.get("label", s["id"]),
                "entity_type": "dashboard_surface",
                "declared_status": declared,
                "observed_status": observed,
                "gap": _compute_gap(declared, observed, s, checks),
                "priority": s.get("priority", ""),
                "next_action": s.get("next_action") or "",
                "health_checks": checks,
                "route": s.get("route", ""),
                "api_dependencies": s.get("api_dependencies", []),
            }
        )
    if surface_records:
        sections.append(
            {
                "section": "Dashboard Surfaces",
                "entity_type": "dashboard_surface",
                "entities": surface_records,
            }
        )

    # Agents / subsystems
    agents = manifest.get("agents", [])
    agent_records = []
    for a in agents:
        checks = run_checks_for_entity(a, manifest)
        declared = a.get("status", "unknown")
        observed = _observed_status(declared, checks)
        agent_records.append(
            {
                "id": a["id"],
                "label": a.get("label", a["id"]),
                "entity_type": "agent",
                "declared_status": declared,
                "observed_status": observed,
                "gap": _compute_gap(declared, observed, a, checks),
                "priority": a.get("priority", ""),
                "next_action": a.get("next_action") or "",
                "health_checks": checks,
                "module": a.get("module", ""),
                "wired_to": a.get("wired_to", []),
            }
        )
    if agent_records:
        sections.append(
            {
                "section": "Agents & Subsystems",
                "entity_type": "agent",
                "entities": agent_records,
            }
        )

    # Integrations
    integrations = manifest.get("integrations", [])
    integration_records = []
    for i in integrations:
        checks = run_checks_for_entity(i, manifest)
        declared = i.get("status", "unknown")
        observed = _observed_status(declared, checks)
        integration_records.append(
            {
                "id": i["id"],
                "label": i.get("label", i["id"]),
                "entity_type": "integration",
                "declared_status": declared,
                "observed_status": observed,
                "gap": _compute_gap(declared, observed, i, checks),
                "priority": "",
                "next_action": "",
                "health_checks": checks,
                "integration_type": i.get("type", ""),
                "used_by": i.get("used_by", []),
            }
        )
    if integration_records:
        sections.append(
            {
                "section": "Integrations",
                "entity_type": "integration",
                "entities": integration_records,
            }
        )

    # Feedback loops
    loops = manifest.get("loops", [])
    loop_records = []
    for loop in loops:
        checks = run_checks_for_entity(loop, manifest)
        declared = loop.get("status", "unknown")
        observed = _observed_status(declared, checks)
        loop_records.append(
            {
                "id": loop["id"],
                "label": loop.get("label", loop["id"]),
                "entity_type": "loop",
                "declared_status": declared,
                "observed_status": observed,
                "gap": _compute_gap(declared, observed, loop, checks),
                "priority": loop.get("priority", ""),
                "next_action": loop.get("next_action") or "",
                "health_checks": checks,
                "module": loop.get("module", ""),
                "sense": loop.get("sense", ""),
                "act": loop.get("act", ""),
                "evaluate": loop.get("evaluate", ""),
                "adapt": loop.get("adapt", ""),
            }
        )
    if loop_records:
        sections.append(
            {
                "section": "Feedback Loops",
                "entity_type": "loop",
                "entities": loop_records,
            }
        )

    autocatalytic_section = manifest_health_autocatalytic.project_autocatalytic_section(
        manifest,
        run_checks=run_checks_for_entity,
        compute_gap=_compute_gap,
    )
    if autocatalytic_section:
        sections.append(autocatalytic_section)

    # Summary counts — all buckets are by observed_status.
    all_entities = [e for s in sections for e in s["entities"]]
    total = len(all_entities)
    live_count = sum(1 for e in all_entities if e["observed_status"] == "live")
    degraded_count = sum(1 for e in all_entities if e["observed_status"] == "degraded")
    broken_count = sum(1 for e in all_entities if e["observed_status"] == "broken")
    stub_count = sum(1 for e in all_entities if e["observed_status"] == "stub")
    frozen_count = sum(1 for e in all_entities if e["observed_status"] == "frozen")
    unknown_count = sum(1 for e in all_entities if e["observed_status"] == "unknown")

    return {
        "manifest_version": manifest.get("schema_version", 0),
        "last_updated": manifest.get("last_updated", ""),
        "summary": {
            "total": total,
            "live": live_count,
            "degraded": degraded_count,
            "broken": broken_count,
            "stub": stub_count,
            "frozen": frozen_count,
            "unknown": unknown_count,
        },
        "sections": sections,
    }
