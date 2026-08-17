"""Manifest loading and topology validation for the autocatalytic portfolio."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from dharma_swarm.autocatalytic_contract_primitives import (
    PORTFOLIO_SCHEMA,
    PROMOTION_CHECKS_BY_NODE,
    REQUIRED_NODE_COUNT,
    SEMANTIC_HOP_SCHEMA,
    PortfolioContractError,
)
from dharma_swarm.catalytic_graph import CatalyticGraph

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"


def load_portfolio_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical autocatalytic portfolio declaration."""

    manifest_path = path or _MANIFEST_PATH
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    portfolio = data.get("autocatalytic_portfolio")
    if not isinstance(portfolio, dict):
        raise PortfolioContractError("autocatalytic_portfolio is not declared")
    return portfolio


def _ordered_nodes(portfolio: Mapping[str, Any]) -> list[dict[str, Any]]:
    nodes = portfolio.get("nodes")
    if not isinstance(nodes, list) or not all(isinstance(row, dict) for row in nodes):
        raise PortfolioContractError("portfolio nodes must be a list of objects")
    return sorted(
        (dict(row) for row in nodes), key=lambda row: int(row.get("ordinal", 0))
    )


def _active_track_ids(repo_root: Path) -> set[str]:
    path = repo_root / "docs" / "governance" / "ACTIVE_TRACK.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("active_tracks") or []
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") and row.get("status") == "ACTIVE"
    }


def _build_catalytic_graph(portfolio: Mapping[str, Any]) -> CatalyticGraph:
    graph = CatalyticGraph(persist_path=Path(os.devnull))
    for node in _ordered_nodes(portfolio):
        graph.add_node(
            str(node.get("id", "")),
            label=str(node.get("label", "")),
            authority=str(node.get("authority", "")),
        )
    for edge in portfolio.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        graph.add_edge(
            str(edge.get("source", "")),
            str(edge.get("target", "")),
            edge_type=str(edge.get("kind") or "enables"),
            strength=1.0,
            evidence=str(edge.get("signal") or ""),
        )
    return graph


def validate_portfolio(
    portfolio: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    require_files: bool = True,
) -> list[str]:
    """Return every topology, authority, and filesystem contract error."""

    root = repo_root or _REPO_ROOT
    errors: list[str] = []
    if portfolio.get("schema_version") != PORTFOLIO_SCHEMA:
        errors.append(f"schema_version must be {PORTFOLIO_SCHEMA}")
    if portfolio.get("claim_ceiling") != "local_rehearsal":
        errors.append("portfolio claim_ceiling must remain local_rehearsal")
    promotion_rule = portfolio.get("promotion_rule")
    if not isinstance(promotion_rule, dict):
        errors.append("promotion_rule must be a typed object")
    else:
        if promotion_rule.get("schema") != SEMANTIC_HOP_SCHEMA:
            errors.append(f"promotion_rule schema must be {SEMANTIC_HOP_SCHEMA}")
        if promotion_rule.get("transport_ack_promotes") is not False:
            errors.append("promotion_rule must set transport_ack_promotes to false")
        required_hop_evidence = {
            "terminal_completed",
            "typed_semantic_artifact",
            "causal_continuity",
            "hash_continuity",
            "project_adapter_recomputation",
        }
        if not required_hop_evidence.issubset(
            set(map(str, promotion_rule.get("structural_hop_requires") or []))
        ):
            errors.append("promotion_rule omits required StructuralHop evidence")
        required_cycle_evidence = {
            "exactly_ten_ordered_structural_hops",
            "closed_signal_ring",
            "persisted_local_mutable_receipt_consistency",
        }
        if not required_cycle_evidence.issubset(
            set(
                map(
                    str,
                    promotion_rule.get("receipt_consistent_cycle_requires") or [],
                )
            )
        ):
            errors.append(
                "promotion_rule omits required receipt-consistent cycle evidence"
            )
        forbidden = set(map(str, promotion_rule.get("forbidden_promotions") or []))
        if "transport_ack_to_structural_hop" not in forbidden:
            errors.append("promotion_rule must forbid transport ACK promotion")

    try:
        nodes = _ordered_nodes(portfolio)
    except (PortfolioContractError, TypeError, ValueError) as exc:
        return [str(exc)]
    if len(nodes) != REQUIRED_NODE_COUNT:
        errors.append(
            f"expected exactly {REQUIRED_NODE_COUNT} nodes, found {len(nodes)}"
        )

    ids = [str(node.get("id") or "") for node in nodes]
    if not all(ids) or len(set(ids)) != len(ids):
        errors.append("node ids must be non-empty and unique")
    if [int(node.get("ordinal", 0)) for node in nodes] != list(
        range(1, REQUIRED_NODE_COUNT + 1)
    ):
        errors.append("node ordinals must be exactly 1..10")
    if portfolio.get("entry_node") != (ids[0] if ids else None):
        errors.append("entry_node must be the ordinal-1 node")

    track_ids = _active_track_ids(root)
    bound_track_ids: set[str] = set()
    declared_pages: list[str] = []
    cross_outputs: set[tuple[str, str, str]] = set()
    cross_inputs: set[tuple[str, str, str]] = set()
    required_fields = (
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
    allowed_authority = {"local_evidence", "projection_only", "external_gated"}
    for index, node in enumerate(nodes):
        node_id = ids[index]
        missing = [
            name for name in required_fields if not str(node.get(name) or "").strip()
        ]
        if missing:
            errors.append(f"{node_id}: missing fields {missing}")
        if node.get("authority") not in allowed_authority:
            errors.append(f"{node_id}: invalid authority {node.get('authority')!r}")
        expected_checks = PROMOTION_CHECKS_BY_NODE.get(node_id)
        if expected_checks is None:
            errors.append(f"{node_id}: no code-owned promotion-check mapping")
        elif node.get("promotion_checks") != list(expected_checks):
            errors.append(
                f"{node_id}: promotion_checks must exactly match {list(expected_checks)}"
            )
        expected_page = f"/dashboard/organism/{node_id}"
        declared_pages.append(str(node.get("page") or ""))
        if node.get("page") != expected_page:
            errors.append(f"{node_id}: page must be {expected_page}")
        expected_next = ids[(index + 1) % len(ids)] if ids else ""
        if node.get("next_node") != expected_next:
            errors.append(f"{node_id}: next_node must be {expected_next}")
        if ids and node.get("output_signal") != nodes[(index + 1) % len(nodes)].get(
            "input_signal"
        ):
            errors.append(f"{node_id}: output signal does not feed {expected_next}")
        obligations = node.get("proof_obligations")
        if not isinstance(obligations, list) or not obligations:
            errors.append(f"{node_id}: proof_obligations must be non-empty")
        bindings = node.get("project_bindings")
        if not isinstance(bindings, list) or not bindings:
            errors.append(f"{node_id}: project_bindings must be non-empty")
        else:
            normalized_bindings = set(map(str, bindings))
            bound_track_ids.update(normalized_bindings)
            unknown = sorted(normalized_bindings - track_ids)
            if unknown:
                errors.append(f"{node_id}: non-active project bindings {unknown}")
        refs = node.get("proof_refs")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{node_id}: proof_refs must be non-empty")
        elif require_files:
            for ref in refs:
                if not (root / str(ref)).is_file():
                    errors.append(f"{node_id}: missing proof ref {ref}")
        if (
            require_files
            and node.get("doc")
            and not (root / str(node["doc"])).is_file()
        ):
            errors.append(f"{node_id}: missing canonical node page {node['doc']}")
        for row in node.get("cross_outputs") or []:
            if (
                not isinstance(row, dict)
                or not row.get("signal")
                or not row.get("target")
            ):
                errors.append(
                    f"{node_id}: cross_outputs entries require signal and target"
                )
                continue
            cross_outputs.add((node_id, str(row["target"]), str(row["signal"])))
        for row in node.get("cross_inputs") or []:
            if (
                not isinstance(row, dict)
                or not row.get("signal")
                or not row.get("source")
            ):
                errors.append(
                    f"{node_id}: cross_inputs entries require signal and source"
                )
                continue
            cross_inputs.add((str(row["source"]), node_id, str(row["signal"])))

    if len(set(declared_pages)) != len(declared_pages):
        errors.append("node dashboard pages must be unique")
    if bound_track_ids != track_ids:
        missing = sorted(track_ids - bound_track_ids)
        extra = sorted(bound_track_ids - track_ids)
        errors.append(
            f"active project binding closure mismatch: missing={missing}, extra={extra}"
        )
    if cross_outputs != cross_inputs:
        errors.append(
            "cross-feed producer/consumer contracts disagree: "
            f"outputs_only={sorted(cross_outputs - cross_inputs)}, "
            f"inputs_only={sorted(cross_inputs - cross_outputs)}"
        )
    cross_signals = [signal for _source, _target, signal in cross_outputs]
    if len(cross_signals) != len(set(cross_signals)):
        errors.append(
            "cross-feed signal names must be globally unique because the runtime "
            "bus is keyed by signal"
        )

    ring_pairs = (
        {(ids[index], ids[(index + 1) % len(ids)]) for index in range(len(ids))}
        if ids
        else set()
    )
    declared_edges = [
        (str(edge.get("source")), str(edge.get("target")), str(edge.get("signal")))
        for edge in portfolio.get("edges") or []
        if isinstance(edge, dict)
    ]
    declared_pairs = {(source, target) for source, target, _signal in declared_edges}
    missing_ring = sorted(ring_pairs - declared_pairs)
    if missing_ring:
        errors.append(f"missing ring edges: {missing_ring}")
    expected_ring_edges = (
        {
            (
                ids[index],
                ids[(index + 1) % len(ids)],
                str(nodes[index].get("output_signal")),
            )
            for index in range(len(ids))
        }
        if ids
        else set()
    )
    expected_edges = expected_ring_edges | cross_outputs
    if len(declared_edges) != len(set(declared_edges)):
        errors.append("portfolio edges must be unique")
    if set(declared_edges) != expected_edges:
        errors.append(
            "declared edges do not match typed ring/cross-feed contracts: "
            f"missing={sorted(expected_edges - set(declared_edges))}, "
            f"extra={sorted(set(declared_edges) - expected_edges)}"
        )

    try:
        graph = _build_catalytic_graph(portfolio)
        sets = graph.detect_autocatalytic_sets()
        if graph.node_count != REQUIRED_NODE_COUNT:
            errors.append(f"catalytic graph has {graph.node_count} nodes")
        if len(sets) != 1 or set(sets[0]) != set(ids):
            errors.append("all ten nodes must form one autocatalytic set")
    except (TypeError, ValueError) as exc:
        errors.append(f"catalytic graph invalid: {exc}")
    return errors
