"""Read-only MemoryKernel evidence intake for KnowledgeOps.

This module turns MemoryKernel atoms into review artifacts. It does not write
to Chetana, wiki, ontology, vectors, runtime state, or MemoryKernel surfaces.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel import (
    MemoryAtom,
    MemoryKernel,
    MemoryQuery,
    RiskLevel,
    TruthState,
)
from dharma_swarm.memory_kernel.context_admission import redact_context_text


_HIGH_RISKS = {RiskLevel.HIGH, RiskLevel.CRITICAL}
_NO_CONTENT_NOTE = "atom_content_not_serialized"


@dataclass(frozen=True)
class MemoryKernelIntakeConfig:
    surface_ids: tuple[str, ...] = ()
    limit_total: int | None = 100
    limit_per_surface: int | None = 25


@dataclass(frozen=True)
class MemoryKnowledgeNode:
    node_id: str
    node_type: str
    status: str
    surface_id: str
    memory_atom_id: str | None = None
    atom_type: str | None = None
    content_ref: str | None = None
    authority_level: str | None = None
    provenance_quality: str | None = None
    projection_of: tuple[str, ...] = ()
    canon_risk: str | None = None
    pii_risk: str | None = None
    adapter_name: str | None = None
    read_mode: str | None = None
    surface_category: str | None = None
    surface_role: str | None = None
    memory_lane: str | None = None
    scope: str | None = None
    truth_state: str | None = None
    freshness: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    source_refs: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    promotion_allowed: bool = False
    context_admissible: bool = False
    has_content: bool = False

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKnowledgeEdge:
    edge_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    surface_id: str
    memory_atom_id: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKnowledgeSnapshot:
    nodes: tuple[MemoryKnowledgeNode, ...]
    edges: tuple[MemoryKnowledgeEdge, ...]
    warnings: tuple[str, ...] = ()

    @property
    def evidence_nodes(self) -> tuple[MemoryKnowledgeNode, ...]:
        return tuple(node for node in self.nodes if node.node_type == "memory_atom")

    @property
    def surface_nodes(self) -> tuple[MemoryKnowledgeNode, ...]:
        return tuple(node for node in self.nodes if node.node_type == "memory_surface")

    def to_json(self) -> dict[str, object]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "warnings": self.warnings,
            "nodes": [node.to_json() for node in self.nodes],
            "edges": [edge.to_json() for edge in self.edges],
        }


@dataclass(frozen=True)
class MemoryEvidenceReview:
    snapshot: MemoryKnowledgeSnapshot
    total_atoms: int
    evidence_node_count: int
    surface_node_count: int
    derived_from_edge_count: int
    content_bearing_count: int
    projection_atom_count: int
    high_canon_risk_count: int
    high_pii_risk_count: int
    context_admissible_count: int
    promotion_allowed_count: int
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "total_atoms": self.total_atoms,
            "evidence_node_count": self.evidence_node_count,
            "surface_node_count": self.surface_node_count,
            "derived_from_edge_count": self.derived_from_edge_count,
            "content_bearing_count": self.content_bearing_count,
            "projection_atom_count": self.projection_atom_count,
            "high_canon_risk_count": self.high_canon_risk_count,
            "high_pii_risk_count": self.high_pii_risk_count,
            "context_admissible_count": self.context_admissible_count,
            "promotion_allowed_count": self.promotion_allowed_count,
            "warnings": self.warnings,
            "snapshot": self.snapshot.to_json(),
        }


class MemoryKernelIntake:
    """Collect a bounded MemoryKernel atom review for KnowledgeOps."""

    def __init__(
        self,
        memory_kernel: MemoryKernel,
        config: MemoryKernelIntakeConfig | None = None,
    ) -> None:
        self.memory_kernel = memory_kernel
        self.config = config or MemoryKernelIntakeConfig()

    def review(self) -> MemoryEvidenceReview:
        query = MemoryQuery(
            limit_total=self.config.limit_total,
            limit_per_surface=self.config.limit_per_surface,
            include_content=False,
            include_metadata_payloads=False,
        )
        atoms = tuple(
            self.memory_kernel.iter_memory_atoms(
                surface_ids=self.config.surface_ids or None,
                query=query,
            )
        )
        return review_memory_atoms(atoms)


def memory_atoms_to_snapshot(atoms: Iterable[MemoryAtom]) -> MemoryKnowledgeSnapshot:
    materialized = tuple(atoms)
    surface_nodes: dict[str, MemoryKnowledgeNode] = {}
    evidence_nodes: list[MemoryKnowledgeNode] = []
    edges: list[MemoryKnowledgeEdge] = []
    warnings = {_NO_CONTENT_NOTE, "read_only_no_knowledge_mutation"}

    for atom in materialized:
        surface_node_id = f"memory_surface:{atom.surface_id}"
        if surface_node_id not in surface_nodes:
            surface_nodes[surface_node_id] = MemoryKnowledgeNode(
                node_id=surface_node_id,
                node_type="memory_surface",
                status="surface_reference",
                surface_id=atom.surface_id,
                authority_level=atom.authority_level.value,
                provenance_quality=atom.provenance_quality,
                projection_of=_safe_refs(atom.projection_of),
                canon_risk=atom.canon_risk.value,
                pii_risk=atom.pii_risk.value,
                surface_category=atom.surface_category.value,
                surface_role=atom.surface_role.value,
            )

        evidence_node = _atom_to_node(atom)
        evidence_nodes.append(evidence_node)
        edges.append(
            MemoryKnowledgeEdge(
                edge_id=_stable_id(
                    "derived_from",
                    evidence_node.node_id,
                    surface_node_id,
                ),
                edge_type="DERIVED_FROM",
                from_node_id=evidence_node.node_id,
                to_node_id=surface_node_id,
                surface_id=atom.surface_id,
                memory_atom_id=atom.atom_id,
            )
        )
        if atom.content:
            warnings.add("content_bearing_atoms_seen_content_omitted")
        if atom.projection_of:
            warnings.add("projection_atoms_are_evidence_not_authority")
        if atom.canon_risk in _HIGH_RISKS or atom.pii_risk in _HIGH_RISKS:
            warnings.add("high_risk_atoms_require_review")

    return MemoryKnowledgeSnapshot(
        nodes=tuple(surface_nodes.values()) + tuple(evidence_nodes),
        edges=tuple(edges),
        warnings=tuple(sorted(warnings)),
    )


def review_memory_atoms(atoms: Iterable[MemoryAtom]) -> MemoryEvidenceReview:
    materialized = tuple(atoms)
    snapshot = memory_atoms_to_snapshot(materialized)
    return MemoryEvidenceReview(
        snapshot=snapshot,
        total_atoms=len(materialized),
        evidence_node_count=len(snapshot.evidence_nodes),
        surface_node_count=len(snapshot.surface_nodes),
        derived_from_edge_count=len(snapshot.edges),
        content_bearing_count=sum(1 for atom in materialized if atom.content),
        projection_atom_count=sum(1 for atom in materialized if atom.projection_of),
        high_canon_risk_count=sum(1 for atom in materialized if atom.canon_risk in _HIGH_RISKS),
        high_pii_risk_count=sum(1 for atom in materialized if atom.pii_risk in _HIGH_RISKS),
        context_admissible_count=sum(1 for atom in materialized if atom.context_admissible),
        promotion_allowed_count=sum(1 for atom in materialized if atom.promotion_allowed),
        warnings=snapshot.warnings,
    )


def merge_snapshots(*snapshots: MemoryKnowledgeSnapshot) -> MemoryKnowledgeSnapshot:
    nodes: dict[str, MemoryKnowledgeNode] = {}
    edges: dict[str, MemoryKnowledgeEdge] = {}
    warnings: set[str] = set()
    for snapshot in snapshots:
        nodes.update({node.node_id: node for node in snapshot.nodes})
        edges.update({edge.edge_id: edge for edge in snapshot.edges})
        warnings.update(snapshot.warnings)
    return MemoryKnowledgeSnapshot(
        nodes=tuple(nodes.values()),
        edges=tuple(edges.values()),
        warnings=tuple(sorted(warnings)),
    )


def render_memory_evidence_review_markdown(review: MemoryEvidenceReview) -> str:
    lines = [
        "# MemoryKernel KnowledgeOps Evidence Review",
        "",
        "Read-only evidence projection. No canon, Chetana, wiki, ontology, vector, runtime, or MemoryKernel writes are performed.",
        "",
        "## Summary",
        "",
        f"- Total atoms: `{review.total_atoms}`",
        f"- Evidence nodes: `{review.evidence_node_count}`",
        f"- Surface nodes: `{review.surface_node_count}`",
        f"- DERIVED_FROM edges: `{review.derived_from_edge_count}`",
        f"- Content-bearing atoms: `{review.content_bearing_count}`",
        f"- Projection atoms: `{review.projection_atom_count}`",
        f"- High/critical canon-risk atoms: `{review.high_canon_risk_count}`",
        f"- High/critical PII-risk atoms: `{review.high_pii_risk_count}`",
        f"- Context-admissible atoms: `{review.context_admissible_count}`",
        f"- Promotion-allowed atoms: `{review.promotion_allowed_count}`",
        "",
    ]
    if review.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in review.warnings)
        lines.append("")
    return "\n".join(lines)


def _atom_to_node(atom: MemoryAtom) -> MemoryKnowledgeNode:
    return MemoryKnowledgeNode(
        node_id=f"memory_atom:{atom.atom_id.removeprefix('memory_atom:')}",
        node_type="memory_atom",
        status=_status_for(atom),
        surface_id=atom.surface_id,
        memory_atom_id=atom.atom_id,
        atom_type=atom.atom_type.value,
        content_ref=_safe_ref(atom.content_ref),
        authority_level=atom.authority_level.value,
        provenance_quality=atom.provenance_quality,
        projection_of=_safe_refs(atom.projection_of),
        canon_risk=atom.canon_risk.value,
        pii_risk=atom.pii_risk.value,
        adapter_name=atom.adapter_name,
        read_mode=atom.read_mode.value,
        surface_category=atom.surface_category.value,
        surface_role=atom.surface_role.value,
        memory_lane=atom.memory_lane.value,
        scope=atom.scope.value,
        truth_state=atom.truth_state.value,
        freshness=atom.freshness,
        valid_from=atom.valid_from,
        valid_until=atom.valid_until,
        source_refs=_safe_refs(atom.source_refs),
        supersedes=_safe_refs(atom.supersedes),
        promotion_allowed=atom.promotion_allowed,
        context_admissible=atom.context_admissible,
        has_content=bool(atom.content),
    )


def _status_for(atom: MemoryAtom) -> str:
    if atom.truth_state == TruthState.SUPERSEDED:
        return "superseded"
    if atom.truth_state == TruthState.REJECTED:
        return "contested"
    return "staged"


def _safe_refs(refs: Iterable[str]) -> tuple[str, ...]:
    return tuple(_safe_ref(ref) for ref in refs)


def _safe_ref(ref: str) -> str:
    value = str(ref)
    redacted = redact_context_text(value)
    if redacted != value:
        return "redacted_ref:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    if _looks_like_path(value) or len(value) > 160:
        return "redacted_ref:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return value


def _looks_like_path(value: str) -> bool:
    if value.startswith(("/", "~")):
        return True
    if value.startswith("file:"):
        return True
    parts = Path(value).parts
    return len(parts) > 2 and any(part.startswith(".") for part in parts)


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"knowledge_edge:{digest[:24]}"
