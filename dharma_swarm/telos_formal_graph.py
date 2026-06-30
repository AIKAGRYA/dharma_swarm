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


def _tarjan_scc(adjacency: Mapping[str, Sequence[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, ()):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while True:
                popped = stack.pop()
                on_stack.remove(popped)
                component.append(popped)
                if popped == node:
                    break
            components.append(sorted(component))

    for node in adjacency:
        if node not in indices:
            strongconnect(node)

    return components


def _has_cycle(component: Sequence[str], adjacency: Mapping[str, Sequence[str]]) -> bool:
    if len(component) > 1:
        return True
    node = component[0]
    return node in adjacency.get(node, ())


def _grounded_nodes(
    evidence_map: Mapping[str, Sequence[str]], claim_ids: set[str]
) -> set[str]:
    memo: dict[str, bool] = {}
    active: set[str] = set()

    def grounded(node: str) -> bool:
        if node in memo:
            return memo[node]
        if node in active:
            memo[node] = False
            return False
        active.add(node)
        try:
            edges = evidence_map.get(node, ())
            if any(evidence not in claim_ids for evidence in edges):
                memo[node] = True
                return True
            result = any(
                grounded(evidence) for evidence in edges if evidence in claim_ids
            )
            memo[node] = result
            return result
        finally:
            active.remove(node)

    return {node for node in evidence_map if grounded(node)}


def analyze_provenance_claims(claims: Sequence[ProvenanceClaim]) -> ProvenanceGraphAnalysis:
    claim_edges, evidence_map, claim_ids = _build_graphs(claims)
    components = _tarjan_scc(claim_edges)
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
