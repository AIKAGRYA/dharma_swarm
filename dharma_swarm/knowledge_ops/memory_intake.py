"""Read-only KnowledgeOps intake from MemoryKernel atoms.

This bridge turns MemoryKernel atoms into KnowledgeOps evidence nodes.  It does
not promote, archive, dedupe canon, mutate Chetana surfaces, or write to any
memory store.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Iterable

from dharma_swarm.knowledge_ops.schema import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeOpsSnapshot,
    LifecycleStatus,
    NodeKind,
    SourceRef,
)
from dharma_swarm.memory_kernel import MemoryAtom, MemoryAtomType, MemoryKernel, MemoryQuery
from dharma_swarm.memory_kernel.atoms import TruthState


@dataclass(frozen=True)
class MemoryKernelIntakeConfig:
    """Read budget for KnowledgeOps memory intake."""

    surface_ids: tuple[str, ...] = ()
    limit_total: int | None = 100
    limit_per_surface: int | None = 25
    include_content: bool = False
    include_metadata_payloads: bool = False
    atom_types: tuple[MemoryAtomType, ...] = ()
    include_surface_nodes: bool = True
    review_sample_limit: int = 10

    def to_query(self) -> MemoryQuery:
        return MemoryQuery(
            limit_total=self.limit_total,
            limit_per_surface=self.limit_per_surface,
            include_content=self.include_content,
            include_metadata_payloads=self.include_metadata_payloads,
            atom_types=self.atom_types,
        )


@dataclass(frozen=True)
class MemoryKernelIntake:
    """Build a KnowledgeOps projection from MemoryKernel atom streams."""

    kernel: MemoryKernel
    config: MemoryKernelIntakeConfig = field(default_factory=MemoryKernelIntakeConfig)

    def collect_atoms(self) -> tuple[MemoryAtom, ...]:
        return tuple(
            self.kernel.iter_memory_atoms(
                surface_ids=self.config.surface_ids or None,
                query=self.config.to_query(),
            )
        )

    def extract(self) -> KnowledgeOpsSnapshot:
        snapshot, _review = self.extract_with_review()
        return snapshot

    def extract_with_review(self) -> tuple[KnowledgeOpsSnapshot, "MemoryEvidenceReview"]:
        atoms = self.collect_atoms()
        snapshot = memory_atoms_to_snapshot(
            atoms,
            include_surface_nodes=self.config.include_surface_nodes,
        )
        review = review_memory_atoms(
            atoms,
            snapshot=snapshot,
            query=self.config.to_query(),
            surface_ids=self.config.surface_ids or None,
            sample_limit=self.config.review_sample_limit,
        )
        return snapshot, review


@dataclass(frozen=True)
class MemoryEvidenceReview:
    """Bounded review summary for MemoryKernel evidence entering KnowledgeOps."""

    total_atoms: int
    node_count: int
    edge_count: int
    query: dict[str, object]
    by_surface: dict[str, int]
    by_atom_type: dict[str, int]
    by_authority: dict[str, int]
    by_truth_state: dict[str, int]
    by_memory_lane: dict[str, int]
    by_scope: dict[str, int]
    by_canon_risk: dict[str, int]
    by_pii_risk: dict[str, int]
    by_read_mode: dict[str, int]
    projection_atom_count: int
    context_admissible_count: int
    promotion_allowed_count: int
    redacted_count: int
    content_bearing_count: int
    stale_or_snapshot_count: int
    superseded_or_rejected_count: int
    warnings: tuple[str, ...]
    top_risky_surfaces: tuple[dict[str, object], ...]
    sample_evidence: tuple[dict[str, object], ...]

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def memory_atoms_to_snapshot(
    atoms: Iterable[MemoryAtom],
    *,
    include_surface_nodes: bool = True,
) -> KnowledgeOpsSnapshot:
    """Convert MemoryKernel atoms into staged KnowledgeOps evidence.

    The conversion intentionally preserves MemoryKernel authority, truth, scope,
    and projection labels in metadata.  It does not turn memory atoms into
    canonical KnowledgeOps nodes.
    """

    nodes: dict[str, KnowledgeNode] = {}
    edges: dict[str, KnowledgeEdge] = {}
    surface_nodes: dict[str, KnowledgeNode] = {}

    for atom in atoms:
        atom_node = _node_for_atom(atom)
        nodes[atom_node.node_id] = atom_node
        if not include_surface_nodes:
            continue
        surface_node = surface_nodes.get(atom.surface_id)
        if surface_node is None:
            surface_node = _surface_node_for_atom(atom)
            surface_nodes[atom.surface_id] = surface_node
            nodes[surface_node.node_id] = surface_node
        edge = KnowledgeEdge.build(
            EdgeKind.DERIVED_FROM,
            atom_node.node_id,
            surface_node.node_id,
            confidence=min(atom.confidence, 0.7),
            source_refs=atom_node.source_refs,
            metadata={
                "memory_atom_id": atom.atom_id,
                "surface_id": atom.surface_id,
                "adapter_name": atom.adapter_name,
            },
        )
        edges[edge.edge_id] = edge

    return KnowledgeOpsSnapshot(
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
        edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
    )


def review_memory_atoms(
    atoms: Iterable[MemoryAtom],
    *,
    snapshot: KnowledgeOpsSnapshot | None = None,
    query: MemoryQuery | None = None,
    surface_ids: tuple[str, ...] | None = None,
    sample_limit: int = 10,
) -> MemoryEvidenceReview:
    """Summarize MemoryKernel atoms before later KnowledgeOps metabolism."""

    rows = tuple(atoms)
    surface_counts = Counter(atom.surface_id for atom in rows)
    canon_risk_counts = Counter(atom.canon_risk.value for atom in rows)
    pii_risk_counts = Counter(atom.pii_risk.value for atom in rows)
    projection_count = sum(1 for atom in rows if _is_projection_atom(atom))
    context_admissible_count = sum(1 for atom in rows if atom.context_admissible)
    promotion_allowed_count = sum(1 for atom in rows if atom.promotion_allowed)
    redacted_count = sum(1 for atom in rows if atom.metadata.get("redaction_status") == "redacted")
    content_bearing_count = sum(1 for atom in rows if atom.content is not None)
    stale_or_snapshot_count = sum(1 for atom in rows if _is_stale_or_snapshot(atom))
    superseded_or_rejected_count = sum(
        1
        for atom in rows
        if atom.truth_state in {TruthState.SUPERSEDED, TruthState.REJECTED}
    )
    return MemoryEvidenceReview(
        total_atoms=len(rows),
        node_count=len(snapshot.nodes) if snapshot is not None else 0,
        edge_count=len(snapshot.edges) if snapshot is not None else 0,
        query=_query_metadata(query, surface_ids),
        by_surface=_sorted_counts(surface_counts),
        by_atom_type=_sorted_counts(Counter(atom.atom_type.value for atom in rows)),
        by_authority=_sorted_counts(Counter(atom.authority_level.value for atom in rows)),
        by_truth_state=_sorted_counts(Counter(atom.truth_state.value for atom in rows)),
        by_memory_lane=_sorted_counts(Counter(atom.memory_lane.value for atom in rows)),
        by_scope=_sorted_counts(Counter(atom.scope.value for atom in rows)),
        by_canon_risk=_sorted_counts(canon_risk_counts),
        by_pii_risk=_sorted_counts(pii_risk_counts),
        by_read_mode=_sorted_counts(Counter(atom.read_mode.value for atom in rows)),
        projection_atom_count=projection_count,
        context_admissible_count=context_admissible_count,
        promotion_allowed_count=promotion_allowed_count,
        redacted_count=redacted_count,
        content_bearing_count=content_bearing_count,
        stale_or_snapshot_count=stale_or_snapshot_count,
        superseded_or_rejected_count=superseded_or_rejected_count,
        warnings=_review_warnings(
            total_atoms=len(rows),
            canon_risk_counts=canon_risk_counts,
            pii_risk_counts=pii_risk_counts,
            projection_count=projection_count,
            context_admissible_count=context_admissible_count,
            promotion_allowed_count=promotion_allowed_count,
            redacted_count=redacted_count,
            content_bearing_count=content_bearing_count,
            stale_or_snapshot_count=stale_or_snapshot_count,
            superseded_or_rejected_count=superseded_or_rejected_count,
        ),
        top_risky_surfaces=_top_risky_surfaces(rows),
        sample_evidence=tuple(_sample_for_atom(atom) for atom in rows[: max(0, sample_limit)]),
    )


def render_memory_evidence_review_markdown(report: MemoryEvidenceReview) -> str:
    """Render a bounded human review artifact without raw atom content."""

    lines = [
        "# MemoryKernel Evidence Review",
        "",
        "This is a read-only KnowledgeOps review artifact. It does not promote, archive, or write memory.",
        "",
        "## Summary",
        "",
        f"- Total atoms: `{report.total_atoms}`",
        f"- KnowledgeOps nodes: `{report.node_count}`",
        f"- KnowledgeOps edges: `{report.edge_count}`",
        f"- Projection atoms: `{report.projection_atom_count}`",
        f"- Context-admissible atoms: `{report.context_admissible_count}`",
        f"- Promotion-allowed atoms: `{report.promotion_allowed_count}`",
        f"- Redacted atoms: `{report.redacted_count}`",
        f"- Content-bearing atoms: `{report.content_bearing_count}`",
        f"- Stale or snapshot atoms: `{report.stale_or_snapshot_count}`",
        f"- Superseded or rejected atoms: `{report.superseded_or_rejected_count}`",
        "",
        "## Query",
        "",
    ]
    for key, value in report.query.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Warnings", ""])
    if report.warnings:
        for warning in report.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No review warnings.")
    _append_counts(lines, "By Surface", report.by_surface)
    _append_counts(lines, "By Truth State", report.by_truth_state)
    _append_counts(lines, "By Canon Risk", report.by_canon_risk)
    _append_counts(lines, "By PII Risk", report.by_pii_risk)
    lines.extend(["", "## Top Risky Surfaces", ""])
    if report.top_risky_surfaces:
        for row in report.top_risky_surfaces:
            lines.append(
                f"- `{row['surface_id']}`: total `{row['total']}`, risky `{row['risky']}`"
            )
    else:
        lines.append("- No high or critical risk surfaces in this bounded sample.")
    lines.extend(["", "## Sample Evidence", ""])
    if report.sample_evidence:
        for row in report.sample_evidence:
            lines.append(
                f"- `{row['atom_id']}` `{row['atom_type']}` from `{row['surface_id']}` "
                f"truth=`{row['truth_state']}` canon_risk=`{row['canon_risk']}` "
                f"pii_risk=`{row['pii_risk']}`"
            )
    else:
        lines.append("- No atoms selected by the query.")
    lines.append("")
    return "\n".join(lines)


def merge_snapshots(*snapshots: KnowledgeOpsSnapshot) -> KnowledgeOpsSnapshot:
    """Merge projection snapshots by stable node/edge ID."""

    nodes: dict[str, KnowledgeNode] = {}
    edges: dict[str, KnowledgeEdge] = {}
    for snapshot in snapshots:
        nodes.update((node.node_id, node) for node in snapshot.nodes)
        edges.update((edge.edge_id, edge) for edge in snapshot.edges)
    return KnowledgeOpsSnapshot(
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
        edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
    )


def _node_for_atom(atom: MemoryAtom) -> KnowledgeNode:
    node_kind = _node_kind_for_atom(atom)
    return KnowledgeNode.build(
        node_kind,
        _title_for_atom(atom),
        id_parts=["memory_atom", atom.atom_id],
        status=_status_for_atom(atom),
        confidence=min(atom.confidence, 0.7),
        owner="memory-kernel",
        authority_tier=atom.authority_level.value,
        stale_after=atom.valid_until,
        source_refs=tuple(
            SourceRef(path=_safe_ref(ref), role="memory_atom") for ref in atom.source_refs
        ),
        metadata=_metadata_for_atom(atom),
    )


def _surface_node_for_atom(atom: MemoryAtom) -> KnowledgeNode:
    return KnowledgeNode.build(
        NodeKind.EVIDENCE,
        f"Memory surface: {atom.surface_id}",
        id_parts=["memory_surface", atom.surface_id],
        status=LifecycleStatus.STAGED,
        confidence=0.5,
        owner="memory-kernel",
        authority_tier=atom.authority_level.value,
        source_refs=(SourceRef(path=_safe_ref(atom.source_path), role="memory_surface"),),
        metadata={
            "surface_id": atom.surface_id,
            "surface_category": atom.surface_category.value,
            "surface_role": atom.surface_role.value,
            "authority_level": atom.authority_level.value,
            "canon_risk": atom.canon_risk.value,
            "pii_risk": atom.pii_risk.value,
            "projection_of": list(atom.projection_of),
        },
    )


def _node_kind_for_atom(atom: MemoryAtom) -> NodeKind:
    if atom.atom_type in {
        MemoryAtomType.FACT,
        MemoryAtomType.EDGE,
        MemoryAtomType.RUNTIME_EVENT,
        MemoryAtomType.CONTEXT_BUNDLE,
    }:
        return NodeKind.RUNTIME_FACT
    if atom.atom_type == MemoryAtomType.KNOWLEDGE_CARD:
        return NodeKind.IDEA_CANDIDATE
    return NodeKind.EVIDENCE


def _status_for_atom(atom: MemoryAtom) -> LifecycleStatus:
    if atom.truth_state == TruthState.SUPERSEDED:
        return LifecycleStatus.SUPERSEDED
    if atom.truth_state == TruthState.REJECTED:
        return LifecycleStatus.CONTESTED
    return LifecycleStatus.STAGED


def _title_for_atom(atom: MemoryAtom) -> str:
    timestamp = f" @ {atom.timestamp}" if atom.timestamp else ""
    return f"{atom.atom_type.value} from {atom.surface_id}{timestamp}"


def _metadata_for_atom(atom: MemoryAtom) -> dict[str, object]:
    metadata: dict[str, object] = {
        "memory_atom_id": atom.atom_id,
        "surface_id": atom.surface_id,
        "atom_type": atom.atom_type.value,
        "content_ref": _safe_ref(atom.content_ref),
        "content_ref_redacted": _needs_ref_redaction(atom.content_ref),
        "has_content": atom.content is not None,
        "timestamp": atom.timestamp,
        "source_path": _safe_ref(atom.source_path),
        "source_path_redacted": _needs_ref_redaction(atom.source_path),
        "authority_level": atom.authority_level.value,
        "provenance_quality": atom.provenance_quality,
        "projection_of": list(atom.projection_of),
        "canon_risk": atom.canon_risk.value,
        "pii_risk": atom.pii_risk.value,
        "adapter_name": atom.adapter_name,
        "read_mode": atom.read_mode.value,
        "surface_category": atom.surface_category.value,
        "surface_role": atom.surface_role.value,
        "memory_lane": atom.memory_lane.value,
        "scope": atom.scope.value,
        "truth_state": atom.truth_state.value,
        "freshness": atom.freshness,
        "valid_from": atom.valid_from,
        "valid_until": atom.valid_until,
        "source_refs": [_safe_ref(ref) for ref in atom.source_refs],
        "supersedes": list(atom.supersedes),
        "promotion_allowed": atom.promotion_allowed,
        "context_admissible": atom.context_admissible,
    }
    for key in ("redaction_status", "ordering_warning", "snapshot_warning"):
        if key in atom.metadata:
            metadata[key] = atom.metadata[key]
    if "snapshot_warnings" in atom.metadata:
        metadata["snapshot_warnings"] = atom.metadata["snapshot_warnings"]
    return metadata


def _query_metadata(
    query: MemoryQuery | None,
    surface_ids: tuple[str, ...] | None,
) -> dict[str, object]:
    resolved = query or MemoryQuery()
    return {
        "limit_total": resolved.limit_total,
        "limit_per_surface": resolved.limit_per_surface,
        "surface_ids": list(surface_ids or ()),
        "include_content": resolved.include_content,
        "include_metadata_payloads": resolved.include_metadata_payloads,
        "atom_types": [atom_type.value for atom_type in resolved.atom_types],
    }


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _safe_ref(ref: str) -> str:
    if not _needs_ref_redaction(ref):
        return ref
    digest = hashlib.sha256(ref.encode("utf-8")).hexdigest()[:16]
    return f"redacted_ref:{digest}"


def _needs_ref_redaction(ref: str) -> bool:
    return (
        ref.startswith("/")
        or ref.startswith("~")
        or "/" in ref
        or "\\" in ref
        or len(ref) > 96
    )


def _is_projection_atom(atom: MemoryAtom) -> bool:
    return (
        bool(atom.projection_of)
        or atom.surface_category.value == "projection"
        or atom.memory_lane.value == "projection"
    )


def _is_stale_or_snapshot(atom: MemoryAtom) -> bool:
    return (
        atom.freshness in {"snapshot", "stale", "dormant"}
        or bool(atom.metadata.get("snapshot_warnings"))
    )


def _review_warnings(
    *,
    total_atoms: int,
    canon_risk_counts: Counter[str],
    pii_risk_counts: Counter[str],
    projection_count: int,
    context_admissible_count: int,
    promotion_allowed_count: int,
    redacted_count: int,
    content_bearing_count: int,
    stale_or_snapshot_count: int,
    superseded_or_rejected_count: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if total_atoms == 0:
        warnings.append("No MemoryKernel atoms matched this review query.")
    high_canon = canon_risk_counts.get("high", 0) + canon_risk_counts.get("critical", 0)
    if high_canon:
        warnings.append(f"{high_canon} atoms have high or critical canon risk.")
    high_pii = pii_risk_counts.get("high", 0) + pii_risk_counts.get("critical", 0)
    if high_pii:
        warnings.append(f"{high_pii} atoms have high or critical PII/secrets risk.")
    if projection_count:
        warnings.append(f"{projection_count} atoms are projections and must not be treated as authority.")
    if context_admissible_count:
        warnings.append(f"{context_admissible_count} atoms are marked context-admissible; review admission policy.")
    if promotion_allowed_count:
        warnings.append(f"{promotion_allowed_count} atoms are marked promotion-allowed; verify gates before promotion.")
    if redacted_count:
        warnings.append(f"{redacted_count} atoms had metadata redactions.")
    if content_bearing_count:
        warnings.append(f"{content_bearing_count} atoms carried bounded content; do not publish without review.")
    if stale_or_snapshot_count:
        warnings.append(f"{stale_or_snapshot_count} atoms are stale, dormant, or immutable snapshots.")
    if superseded_or_rejected_count:
        warnings.append(f"{superseded_or_rejected_count} atoms are superseded or rejected.")
    return tuple(warnings)


def _top_risky_surfaces(atoms: tuple[MemoryAtom, ...]) -> tuple[dict[str, object], ...]:
    totals: Counter[str] = Counter()
    risky: Counter[str] = Counter()
    for atom in atoms:
        totals[atom.surface_id] += 1
        if atom.canon_risk.value in {"high", "critical"} or atom.pii_risk.value in {"high", "critical"}:
            risky[atom.surface_id] += 1
    rows = [
        {
            "surface_id": surface_id,
            "total": totals[surface_id],
            "risky": risky[surface_id],
        }
        for surface_id in totals
        if risky[surface_id]
    ]
    return tuple(sorted(rows, key=lambda row: (-int(row["risky"]), str(row["surface_id"])))[:10])


def _sample_for_atom(atom: MemoryAtom) -> dict[str, object]:
    sample = {
        "atom_id": atom.atom_id,
        "surface_id": atom.surface_id,
        "atom_type": atom.atom_type.value,
        "content_ref": _safe_ref(atom.content_ref),
        "content_ref_redacted": _needs_ref_redaction(atom.content_ref),
        "timestamp": atom.timestamp,
        "authority_level": atom.authority_level.value,
        "truth_state": atom.truth_state.value,
        "memory_lane": atom.memory_lane.value,
        "scope": atom.scope.value,
        "canon_risk": atom.canon_risk.value,
        "pii_risk": atom.pii_risk.value,
        "read_mode": atom.read_mode.value,
        "has_content": atom.content is not None,
    }
    for key in ("redaction_status", "content_status", "ordering_warning", "snapshot_warnings"):
        if key in atom.metadata:
            sample[key] = atom.metadata[key]
    return sample


def _append_counts(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines.extend(["", f"## {title}", ""])
    if counts:
        for key, count in counts.items():
            lines.append(f"- `{key}`: `{count}`")
    else:
        lines.append("- None.")
