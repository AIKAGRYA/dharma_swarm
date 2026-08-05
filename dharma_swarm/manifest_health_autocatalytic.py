"""Autocatalytic projections for :mod:`dharma_swarm.manifest_health`.

The parent module injects filesystem and report-building dependencies so this
module stays independent of the manifest-health registry and avoids an import
cycle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

HealthCheck = Callable[
    [dict[str, Any], dict[str, Any]],
    tuple[bool, str],
]
CheckRunner = Callable[
    [dict[str, Any], dict[str, Any]],
    list[dict[str, Any]],
]
GapComputer = Callable[
    [str, str, dict[str, Any], list[dict[str, Any]]],
    str,
]


def _check_autocatalytic_contract_complete(
    entity: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    """Check the local one-in/one-out metabolic node contract."""
    required = (
        "id",
        "ordinal",
        "label",
        "role",
        "authority",
        "input_signal",
        "output_signal",
        "transform",
        "next_node",
        "page",
        "doc",
    )
    missing = [name for name in required if not entity.get(name)]
    if missing:
        return False, f"missing contract fields: {missing}"
    nodes = manifest.get("autocatalytic_portfolio", {}).get("nodes", [])
    ids = {node.get("id") for node in nodes if isinstance(node, dict)}
    if entity.get("next_node") not in ids:
        return False, f"next_node is not declared: {entity.get('next_node')}"
    obligations = entity.get("proof_obligations")
    if not isinstance(obligations, list) or not obligations:
        return False, "no proof obligations declared"
    return True, (
        f"{entity['input_signal']} -> {entity['output_signal']} -> "
        f"{entity['next_node']} ({entity['authority']})"
    )


def _check_autocatalytic_proof_refs_exist(
    entity: dict[str, Any],
    _manifest: dict[str, Any],
    *,
    repo_root: Path,
) -> tuple[bool, str]:
    refs = entity.get("proof_refs")
    if not isinstance(refs, list) or not refs:
        return False, "no proof_refs declared"
    missing = [str(ref) for ref in refs if not (repo_root / str(ref)).is_file()]
    if missing:
        return False, f"missing proof refs: {missing}"
    return True, f"all {len(refs)} proof ref(s) exist"


def _check_autocatalytic_node_page_exists(
    entity: dict[str, Any],
    _manifest: dict[str, Any],
    *,
    repo_root: Path,
) -> tuple[bool, str]:
    doc = repo_root / str(entity.get("doc") or "")
    dynamic_page = (
        repo_root
        / "dashboard"
        / "src"
        / "app"
        / "dashboard"
        / "organism"
        / "[nodeId]"
        / "page.tsx"
    )
    missing = []
    expected_route = f"/dashboard/organism/{entity.get('id') or ''}"
    if entity.get("page") != expected_route:
        missing.append(
            f"manifest page must be {expected_route}, got {entity.get('page')!r}"
        )
    if not doc.is_file():
        missing.append(str(entity.get("doc") or "no doc declared"))
    if not dynamic_page.is_file():
        missing.append("dashboard/src/app/dashboard/organism/[nodeId]/page.tsx")
    if missing:
        return False, f"missing node page(s): {missing}"
    return True, f"canonical doc + dynamic operator page found for {entity.get('id')}"


def build_health_checks(repo_root: Callable[[], Path]) -> dict[str, HealthCheck]:
    """Bind autocatalytic checks to the parent's dynamic repository root."""

    def proof_refs_exist(
        entity: dict[str, Any],
        manifest: dict[str, Any],
    ) -> tuple[bool, str]:
        return _check_autocatalytic_proof_refs_exist(
            entity,
            manifest,
            repo_root=repo_root(),
        )

    def node_page_exists(
        entity: dict[str, Any],
        manifest: dict[str, Any],
    ) -> tuple[bool, str]:
        return _check_autocatalytic_node_page_exists(
            entity,
            manifest,
            repo_root=repo_root(),
        )

    return {
        "autocatalytic_contract_complete": _check_autocatalytic_contract_complete,
        "autocatalytic_proof_refs_exist": proof_refs_exist,
        "autocatalytic_node_page_exists": node_page_exists,
    }


def project_autocatalytic_section(
    manifest: dict[str, Any],
    *,
    run_checks: CheckRunner,
    compute_gap: GapComputer,
) -> dict[str, Any] | None:
    """Project the ten-node portfolio into its manifest-health section."""
    portfolio = manifest.get("autocatalytic_portfolio", {})
    records = []
    for node in portfolio.get("nodes", []) if isinstance(portfolio, dict) else []:
        checks = run_checks(node, manifest)
        declared = "degraded" if node.get("authority") == "local_evidence" else "stub"
        if checks and all(check["passed"] for check in checks):
            observed = declared
        elif checks and any(check["passed"] for check in checks):
            observed = "degraded"
        elif checks:
            observed = "broken"
        else:
            observed = "unknown"
        records.append(
            {
                "id": node["id"],
                "label": node.get("label", node["id"]),
                "entity_type": "autocatalytic_node",
                "declared_status": declared,
                "observed_status": observed,
                "gap": compute_gap(declared, observed, node, checks),
                "priority": "p0",
                "next_action": "",
                "health_checks": checks,
                "ordinal": node.get("ordinal"),
                "role": node.get("role", ""),
                "authority": node.get("authority", ""),
                "input_signal": node.get("input_signal", ""),
                "output_signal": node.get("output_signal", ""),
                "next_node": node.get("next_node", ""),
                "page": node.get("page", ""),
                "proof_refs": node.get("proof_refs", []),
                "proof_obligations": node.get("proof_obligations", []),
                "promotion_checks": node.get("promotion_checks", []),
                "project_bindings": node.get("project_bindings", []),
            }
        )
    if not records:
        return None
    return {
        "section": "Autocatalytic Portfolio",
        "entity_type": "autocatalytic_node",
        "entities": records,
    }
