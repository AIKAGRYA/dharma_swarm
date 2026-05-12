"""Schema primitives for the KnowledgeOps semantic metabolism.

The schema separates containers (docs), claims, concepts, evidence, decisions,
code surfaces, runtime facts, broken-register items, and pre-canonical idea
candidates.  These records are designed for JSONL projection and later graph
storage, not as a new source of authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class NodeKind(StrEnum):
    DOC = "doc"
    CONCEPT = "concept"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    DECISION = "decision"
    CODE_SURFACE = "code_surface"
    RUNTIME_FACT = "runtime_fact"
    BROKEN_REGISTER_ITEM = "broken_register_item"
    IDEA_CANDIDATE = "idea_candidate"
    SYNTHESIS_CANDIDATE = "synthesis_candidate"


class EdgeKind(StrEnum):
    REFERENCES = "references"
    EXTRACTS_CONCEPT = "extracts_concept"
    ASSERTS = "asserts"
    SUPPORTS = "supports"
    REFUTES = "refutes"
    CONTEXTUALIZES = "contextualizes"
    DECIDES = "decides"
    IMPLEMENTS = "implements"
    OBSERVES = "observes"
    TRACKS_BROKENNESS_OF = "tracks_brokenness_of"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    SYNTHESIZES = "synthesizes"
    PROMOTES = "promotes"
    DEMOTES = "demotes"
    ARCHIVES = "archives"
    GOVERNS = "governs"


class LifecycleStatus(StrEnum):
    STAGED = "staged"
    TRUSTED = "trusted"
    CANONICAL = "canonical"
    STALE = "stale"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class KnowledgeOpsMode(StrEnum):
    WAKE = "wake"
    SENSE = "sense"
    WORK = "work"
    LEARNING = "learning"
    REFLECTION = "reflection"
    SLEEP = "sleep"
    DREAM = "dream"
    IMMUNE = "immune"
    PROMOTION = "promotion"
    FORGETTING = "forgetting"


def stable_hash(parts: list[str]) -> str:
    payload = "\n".join(part.strip() for part in parts if part is not None)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_id(kind: str, *parts: str) -> str:
    return f"{kind}:{stable_hash([kind, *parts])[:24]}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SourceRef:
    path: str
    role: str = "evidence"
    lines: str | None = None
    checksum: str | None = None

    @classmethod
    def for_path(
        cls,
        path: Path,
        repo_root: Path | None = None,
        *,
        role: str = "evidence",
        lines: str | None = None,
    ) -> SourceRef:
        resolved = path.resolve()
        rendered = (
            resolved.relative_to(repo_root.resolve()).as_posix()
            if repo_root is not None
            and resolved.is_relative_to(repo_root.resolve())
            else resolved.as_posix()
        )
        checksum = file_sha256(resolved) if resolved.is_file() else None
        return cls(path=rendered, role=role, lines=lines, checksum=checksum)


@dataclass(frozen=True)
class KnowledgeNode:
    node_id: str
    kind: NodeKind
    title: str
    status: LifecycleStatus = LifecycleStatus.STAGED
    confidence: float = 0.5
    owner: str = ""
    authority_tier: str = ""
    stale_after: str | None = None
    source_refs: tuple[SourceRef, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        kind: NodeKind,
        title: str,
        *,
        id_parts: list[str],
        status: LifecycleStatus = LifecycleStatus.STAGED,
        confidence: float = 0.5,
        owner: str = "",
        authority_tier: str = "",
        stale_after: str | None = None,
        source_refs: tuple[SourceRef, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        return cls(
            node_id=stable_id(kind.value, *id_parts),
            kind=kind,
            title=title,
            status=status,
            confidence=confidence,
            owner=owner,
            authority_tier=authority_tier,
            stale_after=stale_after,
            source_refs=source_refs,
            metadata=metadata or {},
        )

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class KnowledgeEdge:
    edge_id: str
    kind: EdgeKind
    source_id: str
    target_id: str
    confidence: float = 0.5
    source_refs: tuple[SourceRef, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        kind: EdgeKind,
        source_id: str,
        target_id: str,
        *,
        confidence: float = 0.5,
        source_refs: tuple[SourceRef, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEdge:
        return cls(
            edge_id=stable_id("edge", kind.value, source_id, target_id),
            kind=kind,
            source_id=source_id,
            target_id=target_id,
            confidence=confidence,
            source_refs=source_refs,
            metadata=metadata or {},
        )

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass(frozen=True)
class KnowledgeOpsSnapshot:
    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]

    def node_count_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self.nodes:
            counts[node.kind.value] = counts.get(node.kind.value, 0) + 1
        return counts

    def edge_count_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for edge in self.edges:
            counts[edge.kind.value] = counts.get(edge.kind.value, 0) + 1
        return counts

    def write_jsonl(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(output_dir / "nodes.jsonl", [node.to_json() for node in self.nodes])
        _write_jsonl(output_dir / "edges.jsonl", [edge.to_json() for edge in self.edges])
        summary = {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_count_by_kind": self.node_count_by_kind(),
            "edge_count_by_kind": self.edge_count_by_kind(),
        }
        (output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")
