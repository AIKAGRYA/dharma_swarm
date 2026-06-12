"""Manifest Health — declared-vs-observed comparison engine.

Reads ACTIVE_SURFACE_MANIFEST.yaml and runs safe, registered health
checks against live runtime state.  Returns a structured report of
every entity with its declared status, observed status, and gap.

Health checks are a hardcoded registry of safe operations — no
arbitrary shell commands.  The manifest declares *which* check IDs
to run; this module maps them to Python functions.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"
CANONICAL_RUNTIME_WORKTREE = Path.home() / "dharma_swarm_main"
_DEPLOY_RECEIPT_PATH = Path.home() / ".dharma" / "ops" / "deploy_receipt.json"


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
    return exists, f"{'found' if exists else 'missing'}: {page_dir.relative_to(_REPO_ROOT)}"


def _check_api_router_registered(
    entity: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    deps = entity.get("api_dependencies", [])
    if not deps:
        return True, "no API dependencies declared"
    registered_prefixes = {
        r["prefix"] for r in manifest.get("api_routers", [])
    }
    missing = []
    for dep in deps:
        prefix = "/" + "/".join(dep.strip("/").split("/")[:2])
        if prefix not in registered_prefixes:
            missing.append(dep)
    if missing:
        return False, f"unregistered API deps: {missing}"
    return True, f"all {len(deps)} API dep(s) have registered routers"


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


# The registry: check_id → function
_HEALTH_CHECK_REGISTRY: dict[
    str,
    type[Any] | Any,
] = {
    "dashboard_route_exists": _check_dashboard_route_exists,
    "api_router_registered": _check_api_router_registered,
    "module_file_exists": _check_module_file_exists,
    "test_file_exists": _check_test_file_exists,
    "runtime_db_present": _check_runtime_db_present,
    "ontology_db_present": _check_ontology_db_present,
    "api_health_responds": _check_api_health_responds,
}


# ── Running package provenance ───────────────────────────────────


def _git_field(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _repo_root_from_spec_origin(origin: str) -> Path | None:
    path = Path(origin).resolve()
    if path.name == "__init__.py" and path.parent.name == "dharma_swarm":
        return path.parent.parent
    if path.name.endswith(".py") and path.parent.name == "dharma_swarm":
        return path.parent.parent
    return None


def _resolve_package_init() -> Path | None:
    """Resolve the served dharma_swarm package root file."""
    spec = importlib.util.find_spec("dharma_swarm")
    if spec is not None and spec.origin and spec.origin.endswith("__init__.py"):
        return Path(spec.origin).resolve()

    try:
        import dharma_swarm as pkg

        if pkg.__file__:
            return Path(pkg.__file__).resolve()
    except ImportError:
        pass

    # Namespace / editable edge cases: anchor on a core submodule file.
    for submodule in ("manifest_health", "orchestrator", "status"):
        try:
            mod = importlib.import_module(f"dharma_swarm.{submodule}")
            mod_file = getattr(mod, "__file__", None)
            if not mod_file:
                continue
            pkg_dir = Path(mod_file).resolve().parent
            if pkg_dir.name == "dharma_swarm":
                init = pkg_dir / "__init__.py"
                if init.is_file():
                    return init
        except ImportError:
            continue
    return None


def _read_deploy_receipt() -> dict[str, Any] | None:
    if not _DEPLOY_RECEIPT_PATH.is_file():
        return None
    try:
        return json.loads(_DEPLOY_RECEIPT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def running_package_provenance(
    *,
    canonical_worktree: Path | None = None,
) -> dict[str, Any]:
    """Resolve the interpreter's dharma_swarm package to git + deploy truth."""
    canonical = (canonical_worktree or CANONICAL_RUNTIME_WORKTREE).resolve()
    init_path = _resolve_package_init()
    if init_path is None:
        return {
            "ok": False,
            "issues": ["dharma_swarm not importable"],
            "canonical_worktree": str(canonical),
        }

    origin = str(init_path)
    repo_root = _repo_root_from_spec_origin(origin)
    if repo_root is None:
        return {
            "ok": False,
            "issues": [f"could not derive repo root from {origin}"],
            "package_origin": origin,
            "canonical_worktree": str(canonical),
        }

    repo_root = repo_root.resolve()
    head = _git_field(repo_root, "rev-parse", "--short=10", "HEAD")
    branch = _git_field(repo_root, "symbolic-ref", "--short", "HEAD")
    dirty = _git_field(repo_root, "status", "--porcelain")
    ahead_behind = _git_field(
        repo_root, "rev-list", "--left-right", "--count", "HEAD...origin/main",
    )
    behind = ahead = None
    if ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    receipt = _read_deploy_receipt() or {}
    deploy_status = receipt.get("status")
    deploy_note = receipt.get("note", "")

    issues: list[str] = []
    if repo_root != canonical:
        issues.append(
            f"running repo {repo_root} != canonical {canonical}",
        )
    if dirty:
        issues.append(f"running worktree dirty ({len(dirty.splitlines())} files)")
    if behind and behind > 0:
        issues.append(f"{behind} commit(s) behind origin/main")
    if deploy_status in {"blocked", "error"}:
        issues.append(f"deploy receipt status={deploy_status}")
    if deploy_status == "paused":
        issues.append("deploy paused (kill switch)")

    return {
        "ok": not issues,
        "issues": issues,
        "package_origin": origin,
        "repo_root": str(repo_root),
        "canonical_worktree": str(canonical),
        "canonical_match": repo_root == canonical,
        "git_head": head,
        "git_branch": branch or "(detached)",
        "dirty_file_count": len(dirty.splitlines()) if dirty else 0,
        "ahead_of_main": ahead,
        "behind_main": behind,
        "deploy_status": deploy_status,
        "deploy_note": deploy_note,
    }


def check_runtime_package_currency(
    *,
    canonical_worktree: Path | None = None,
) -> tuple[bool, str]:
    """Return (passed, evidence) for dgc health / manifest checks."""
    prov = running_package_provenance(canonical_worktree=canonical_worktree)
    if prov.get("ok"):
        head = prov.get("git_head", "?")
        branch = prov.get("git_branch", "?")
        return True, f"canonical match @ {branch}/{head}"
    issues = prov.get("issues") or ["unknown provenance failure"]
    return False, "; ".join(str(i) for i in issues)


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
            results.append({
                "check_id": check_id,
                "passed": False,
                "evidence": f"unknown check_id: {check_id}",
            })
            continue
        try:
            passed, evidence = fn(entity, manifest)
        except Exception as exc:
            passed, evidence = False, f"check raised: {exc}"
        results.append({
            "check_id": check_id,
            "passed": passed,
            "evidence": evidence,
        })
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
        surface_records.append({
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
        })
    if surface_records:
        sections.append({
            "section": "Dashboard Surfaces",
            "entity_type": "dashboard_surface",
            "entities": surface_records,
        })

    # Agents / subsystems
    agents = manifest.get("agents", [])
    agent_records = []
    for a in agents:
        checks = run_checks_for_entity(a, manifest)
        declared = a.get("status", "unknown")
        observed = _observed_status(declared, checks)
        agent_records.append({
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
        })
    if agent_records:
        sections.append({
            "section": "Agents & Subsystems",
            "entity_type": "agent",
            "entities": agent_records,
        })

    # Integrations
    integrations = manifest.get("integrations", [])
    integration_records = []
    for i in integrations:
        checks = run_checks_for_entity(i, manifest)
        declared = i.get("status", "unknown")
        observed = _observed_status(declared, checks)
        integration_records.append({
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
        })
    if integration_records:
        sections.append({
            "section": "Integrations",
            "entity_type": "integration",
            "entities": integration_records,
        })

    # Feedback loops
    loops = manifest.get("loops", [])
    loop_records = []
    for loop in loops:
        checks = run_checks_for_entity(loop, manifest)
        declared = loop.get("status", "unknown")
        observed = _observed_status(declared, checks)
        loop_records.append({
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
        })
    if loop_records:
        sections.append({
            "section": "Feedback Loops",
            "entity_type": "loop",
            "entities": loop_records,
        })

    # Summary counts — all buckets are by observed_status.
    all_entities = [
        e for s in sections for e in s["entities"]
    ]
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
            "unknown": unknown_count,
        },
        "sections": sections,
    }
