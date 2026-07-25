"""Graph helpers for formal telos provenance analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from dharma_swarm.telos_formal_models import ProvenanceClaim

__all__ = ["ProvenanceGraphAnalysis", "analyze_provenance_claims"]


@dataclass(frozen=True)
class ProvenanceGraphAnalysis:
    claim_ids: tuple[str, ...]
    cycle_components: tuple[tuple[str, ...], ...]
    cycle_claim_ids: tuple[str, ...]
    grounded_claim_ids: tuple[str, ...]
    ungrounded_claim_ids: tuple[str, ...]


def _build_graphs(
    claims: Sequence[ProvenanceClaim],
) -> tuple[dict[str, list[str]], dict[str, list[str]], set[str]]:
    claim_ids = {claim.claim_id for claim in claims}
    claim_edges = {
        claim.claim_id: [evidence for evidence in claim.evidence_ids if evidence in claim_ids]
        for claim in claims
    }
    evidence_map = {claim.claim_id: list(claim.evidence_ids) for claim in claims}
    return claim_edges, evidence_map, claim_ids


def _strongly_connected_components(
    adjacency: Mapping[str, Sequence[str]],
) -> list[list[str]]:
    nodes = set(adjacency)
    for neighbors in adjacency.values():
        nodes.update(neighbors)

    visited: set[str] = set()
    order: list[str] = []

    for start in sorted(nodes):
        if start in visited:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            for neighbor in sorted(adjacency.get(node, ()), reverse=True):
                if neighbor not in visited:
                    stack.append((neighbor, False))

    reverse_adjacency = {node: [] for node in nodes}
    for node, neighbors in adjacency.items():
        for neighbor in neighbors:
            reverse_adjacency.setdefault(neighbor, []).append(node)

    components: list[list[str]] = []
    visited.clear()
    for start in reversed(order):
        if start in visited:
            continue
        component: list[str] = []
        stack = [start]
        visited.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in reverse_adjacency.get(node, ()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))

    return components


def _has_cycle(component: Sequence[str], adjacency: Mapping[str, Sequence[str]]) -> bool:
    if len(component) > 1:
        return True
    node = component[0]
    return node in adjacency.get(node, ())


def _grounded_nodes(
    evidence_map: Mapping[str, Sequence[str]], claim_ids: set[str]
) -> set[str]:
    grounded: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node, evidence_ids in evidence_map.items():
            if node in grounded:
                continue
            if any(
                evidence_id not in claim_ids or evidence_id in grounded
                for evidence_id in evidence_ids
            ):
                grounded.add(node)
                changed = True
    return grounded


def analyze_provenance_claims(claims: Sequence[ProvenanceClaim]) -> ProvenanceGraphAnalysis:
    claim_edges, evidence_map, claim_ids = _build_graphs(claims)
    components = _strongly_connected_components(claim_edges)
    cycle_components = tuple(
        tuple(component)
        for component in sorted(
            (component for component in components if _has_cycle(component, claim_edges)),
            key=lambda item: item[0],
        )
    )
    cycle_claim_ids = tuple(sorted({claim_id for component in cycle_components for claim_id in component}))
    grounded = _grounded_nodes(evidence_map, claim_ids)
    ungrounded_claim_ids = tuple(sorted(claim_ids - grounded))
    return ProvenanceGraphAnalysis(
        claim_ids=tuple(sorted(claim_ids)),
        cycle_components=cycle_components,
        cycle_claim_ids=cycle_claim_ids,
        grounded_claim_ids=tuple(sorted(grounded)),
        ungrounded_claim_ids=ungrounded_claim_ids,
    )
