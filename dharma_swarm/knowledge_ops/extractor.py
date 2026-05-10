"""Read-only KnowledgeOps graph extractor.

The extractor inventories existing authority docs, state docs, code surfaces,
runtime projections, and wiki atoms.  It emits a projection graph that can be
reviewed by humans or downstream agents.  It does not promote, archive, move,
or mutate any source surface.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
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


AUTHORITY_TERMS = ("canonical", "source of truth", "authoritative", "ground truth")
CODE_REF_RE = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|md|yaml|yml|json|toml|sh|ts|tsx|js|jsx)(?::\d+)?)`"
)
BROKEN_ID_RE = re.compile(r"\b(BR-\d{3})\b")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SLOT_RE = re.compile(r"^###\s+Slot\s+(\d+)\s+[-—]\s+(.+?)\s*$")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


DEFAULT_DOC_PATHS = (
    "CLAUDE.md",
    "docs/MEGAFILE_INDEX.md",
    "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
    "docs/governance/CANONICAL_DOC_STACK.md",
    "docs/governance/SOVEREIGN_MANIFEST.md",
    "docs/governance/REPO_GOVERNANCE_AUDIT.md",
    "docs/architecture/NAVIGATION.md",
    "docs/architecture/WIRING_AND_LOOPS.md",
    "docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md",
    "docs/state/BROKEN_REGISTER.md",
    "docs/state/LIVE_OPS_DASHBOARD.md",
    "reports/system_map/latest.json",
)

DEFAULT_CODE_SURFACES = (
    "dharma_swarm/context_compiler.py",
    "dharma_swarm/engine/event_memory.py",
    "dharma_swarm/graph_store.py",
    "dharma_swarm/knowledge_units.py",
    "dharma_swarm/memory_lattice.py",
    "dharma_swarm/ontology.py",
    "dharma_swarm/semantic_gravity.py",
    "dharma_swarm/semantic_memory_bridge.py",
    "dharma_swarm/temporal_graph.py",
    "dharma_swarm/operator_core/operating_facts.py",
)


@dataclass(frozen=True)
class ExtractorConfig:
    repo_root: Path
    wiki_root: Path | None = None
    doc_paths: tuple[str, ...] = DEFAULT_DOC_PATHS
    code_surfaces: tuple[str, ...] = DEFAULT_CODE_SURFACES
    wiki_limit: int = 250


class KnowledgeOpsExtractor:
    """Build a KnowledgeOps projection graph from existing local surfaces."""

    def __init__(self, config: ExtractorConfig | Path | str) -> None:
        if isinstance(config, ExtractorConfig):
            self.config = config
        else:
            self.config = ExtractorConfig(repo_root=Path(config))
        self.repo_root = self.config.repo_root.resolve()

    def extract(self) -> KnowledgeOpsSnapshot:
        nodes: dict[str, KnowledgeNode] = {}
        edges: dict[str, KnowledgeEdge] = {}

        def add_node(node: KnowledgeNode) -> KnowledgeNode:
            nodes[node.node_id] = node
            return node

        def add_edge(edge: KnowledgeEdge) -> None:
            edges[edge.edge_id] = edge

        doc_nodes: dict[str, KnowledgeNode] = {}
        for rel_path in self.config.doc_paths:
            path = self.repo_root / rel_path
            if not path.exists() or not path.is_file():
                continue
            doc_node = add_node(self._doc_node(path, rel_path))
            doc_nodes[rel_path] = doc_node
            for concept in self._concepts_from_doc(path, doc_node):
                add_node(concept)
                add_edge(
                    KnowledgeEdge.build(
                        EdgeKind.EXTRACTS_CONCEPT,
                        doc_node.node_id,
                        concept.node_id,
                        confidence=0.65,
                        source_refs=concept.source_refs,
                    )
                )
            for broken_item in self._broken_items_from_doc(path, doc_node):
                add_node(broken_item)
                add_edge(
                    KnowledgeEdge.build(
                        EdgeKind.TRACKS_BROKENNESS_OF,
                        doc_node.node_id,
                        broken_item.node_id,
                        confidence=0.8,
                        source_refs=broken_item.source_refs,
                    )
                )
            for target in self._code_refs_from_doc(path):
                target_node = self._node_for_path(target, nodes)
                if target_node:
                    add_edge(
                        KnowledgeEdge.build(
                            EdgeKind.REFERENCES,
                            doc_node.node_id,
                            target_node.node_id,
                            confidence=0.75,
                            source_refs=doc_node.source_refs,
                            metadata={"target": target},
                        )
                    )

        for rel_path in self.config.code_surfaces:
            path = self.repo_root / rel_path
            if path.exists() and path.is_file():
                add_node(self._code_surface_node(path, rel_path))

        system_map = self.repo_root / "reports/system_map/latest.json"
        if system_map.exists():
            for fact in self._runtime_facts_from_system_map(system_map):
                add_node(fact)
                source = doc_nodes.get("reports/system_map/latest.json")
                if source:
                    add_edge(
                        KnowledgeEdge.build(
                            EdgeKind.OBSERVES,
                            source.node_id,
                            fact.node_id,
                            confidence=0.7,
                            source_refs=fact.source_refs,
                        )
                    )

        if self.config.wiki_root and self.config.wiki_root.exists():
            for wiki_node in self._wiki_concepts(self.config.wiki_root):
                add_node(wiki_node)
                for doc_node in doc_nodes.values():
                    if self._title_mentions_doc(wiki_node.title, doc_node.title):
                        add_edge(
                            KnowledgeEdge.build(
                                EdgeKind.CONTEXTUALIZES,
                                wiki_node.node_id,
                                doc_node.node_id,
                                confidence=0.35,
                                source_refs=wiki_node.source_refs,
                            )
                        )

        return KnowledgeOpsSnapshot(
            nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
            edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
        )

    def _doc_node(self, path: Path, rel_path: str) -> KnowledgeNode:
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = _first_heading(text) or Path(rel_path).name
        status = _status_for_doc(rel_path, text)
        authority_tier = _authority_tier(rel_path)
        return KnowledgeNode.build(
            NodeKind.DOC,
            title,
            id_parts=[rel_path],
            status=status,
            confidence=0.8 if status == LifecycleStatus.CANONICAL else 0.6,
            authority_tier=authority_tier,
            owner="repo-docops" if rel_path.startswith("docs/") else "",
            source_refs=(SourceRef.for_path(path, self.repo_root, role="source"),),
            metadata={
                "path": rel_path,
                "authority_terms": [
                    term for term in AUTHORITY_TERMS if term in text.lower()
                ],
                "line_count": len(text.splitlines()),
            },
        )

    def _code_surface_node(self, path: Path, rel_path: str) -> KnowledgeNode:
        return KnowledgeNode.build(
            NodeKind.CODE_SURFACE,
            rel_path,
            id_parts=[rel_path],
            status=LifecycleStatus.TRUSTED,
            confidence=0.75,
            owner="runtime",
            source_refs=(SourceRef.for_path(path, self.repo_root, role="code"),),
            metadata={"path": rel_path, "suffix": path.suffix},
        )

    def _concepts_from_doc(
        self, path: Path, doc_node: KnowledgeNode
    ) -> Iterable[KnowledgeNode]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel_path = doc_node.metadata["path"]
        for index, line in enumerate(text.splitlines(), start=1):
            slot = SLOT_RE.match(line)
            if slot:
                title = f"MEGAFILE Slot {slot.group(1)}: {slot.group(2).strip()}"
                yield KnowledgeNode.build(
                    NodeKind.CONCEPT,
                    title,
                    id_parts=[rel_path, title],
                    status=LifecycleStatus.TRUSTED,
                    confidence=0.8,
                    owner="megafile-index",
                    source_refs=(
                        SourceRef.for_path(
                            path, self.repo_root, role="slot", lines=str(index)
                        ),
                    ),
                    metadata={"slot": int(slot.group(1)), "source_doc": rel_path},
                )
                continue
            heading = HEADING_RE.match(line)
            if heading and len(heading.group(1)) <= 3:
                title = heading.group(2).strip().strip("#")
                if title and not title.lower().startswith("table of contents"):
                    yield KnowledgeNode.build(
                        NodeKind.CONCEPT,
                        title,
                        id_parts=[rel_path, title],
                        status=LifecycleStatus.STAGED,
                        confidence=0.55,
                        source_refs=(
                            SourceRef.for_path(
                                path,
                                self.repo_root,
                                role="heading",
                                lines=str(index),
                            ),
                        ),
                        metadata={"source_doc": rel_path, "heading_level": len(heading.group(1))},
                    )

    def _broken_items_from_doc(
        self, path: Path, doc_node: KnowledgeNode
    ) -> Iterable[KnowledgeNode]:
        if not doc_node.metadata["path"].endswith("BROKEN_REGISTER.md"):
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
        seen: set[str] = set()
        for index, line in enumerate(text.splitlines(), start=1):
            for match in BROKEN_ID_RE.finditer(line):
                br_id = match.group(1)
                if br_id in seen:
                    continue
                seen.add(br_id)
                title = line.strip().lstrip("-# ").strip() or br_id
                yield KnowledgeNode.build(
                    NodeKind.BROKEN_REGISTER_ITEM,
                    title,
                    id_parts=[br_id],
                    status=LifecycleStatus.TRUSTED,
                    confidence=0.85,
                    owner="broken-register",
                    source_refs=(
                        SourceRef.for_path(
                            path, self.repo_root, role="register", lines=str(index)
                        ),
                    ),
                    metadata={"br_id": br_id},
                )

    def _runtime_facts_from_system_map(self, path: Path) -> Iterable[KnowledgeNode]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        organs = payload.get("organs", [])
        if isinstance(organs, dict):
            organs = [{"name": key, **value} for key, value in organs.items()]
        if not isinstance(organs, list):
            return
        for organ in organs:
            if not isinstance(organ, dict):
                continue
            name = str(organ.get("name") or organ.get("organ") or "")
            if not name:
                continue
            coherence = str(organ.get("coherence_state") or organ.get("status") or "unknown")
            yield KnowledgeNode.build(
                NodeKind.RUNTIME_FACT,
                f"{name}: {coherence}",
                id_parts=["system_map", name, coherence],
                status=LifecycleStatus.STAGED,
                confidence=0.7,
                owner="system-map",
                source_refs=(SourceRef.for_path(path, self.repo_root, role="projection"),),
                metadata={"organ": name, "coherence_state": coherence},
            )

    def _wiki_concepts(self, wiki_root: Path) -> Iterable[KnowledgeNode]:
        concept_root = wiki_root / "concepts"
        if not concept_root.exists():
            concept_root = wiki_root
        for index, path in enumerate(sorted(concept_root.glob("*.md"))):
            if index >= self.config.wiki_limit:
                break
            text = path.read_text(encoding="utf-8", errors="ignore")
            title = _first_heading(text) or path.stem.replace("-", " ").title()
            status = _status_from_frontmatter(text)
            links = sorted(set(WIKI_LINK_RE.findall(text)))
            yield KnowledgeNode.build(
                NodeKind.CONCEPT,
                title,
                id_parts=["wiki", path.name],
                status=status,
                confidence=0.65,
                owner="wiki",
                source_refs=(SourceRef.for_path(path, None, role="wiki"),),
                metadata={
                    "path": path.as_posix(),
                    "wiki_links": links[:25],
                    "line_count": len(text.splitlines()),
                },
            )

    def _code_refs_from_doc(self, path: Path) -> Iterable[str]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in CODE_REF_RE.finditer(text):
            target = match.group(1).split(":", 1)[0]
            if (self.repo_root / target).exists():
                yield target

    def _node_for_path(
        self, rel_path: str, nodes: dict[str, KnowledgeNode]
    ) -> KnowledgeNode | None:
        expected_id = KnowledgeNode.build(
            NodeKind.CODE_SURFACE,
            rel_path,
            id_parts=[rel_path],
        ).node_id
        if expected_id in nodes:
            return nodes[expected_id]
        path = self.repo_root / rel_path
        if path.exists() and path.is_file():
            node = self._code_surface_node(path, rel_path)
            nodes[node.node_id] = node
            return node
        return None

    @staticmethod
    def _title_mentions_doc(title: str, doc_title: str) -> bool:
        title_words = set(_words(title))
        doc_words = set(_words(doc_title))
        return bool(title_words and doc_words and len(title_words & doc_words) >= 2)


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            return match.group(2).strip()
    return None


def _status_for_doc(rel_path: str, text: str) -> LifecycleStatus:
    lowered = f"{rel_path}\n{text[:2000]}".lower()
    if "/archive/" in rel_path or rel_path.startswith("docs/archive/"):
        return LifecycleStatus.ARCHIVED
    if "contested" in lowered:
        return LifecycleStatus.CONTESTED
    if "stale" in lowered:
        return LifecycleStatus.STALE
    if "canonical" in lowered:
        return LifecycleStatus.CANONICAL
    if "seeded" in lowered:
        return LifecycleStatus.TRUSTED
    return LifecycleStatus.STAGED


def _status_from_frontmatter(text: str) -> LifecycleStatus:
    match = re.search(r"(?m)^status:\s*([A-Za-z_-]+)\s*$", text[:2000])
    if not match:
        return LifecycleStatus.STAGED
    raw = match.group(1).lower().replace("-", "_")
    aliases = {
        "draft": LifecycleStatus.STAGED,
        "seed": LifecycleStatus.STAGED,
        "trusted": LifecycleStatus.TRUSTED,
        "canonical": LifecycleStatus.CANONICAL,
        "stale": LifecycleStatus.STALE,
        "contested": LifecycleStatus.CONTESTED,
        "superseded": LifecycleStatus.SUPERSEDED,
        "archived": LifecycleStatus.ARCHIVED,
    }
    return aliases.get(raw, LifecycleStatus.STAGED)


def _authority_tier(rel_path: str) -> str:
    if rel_path == "CLAUDE.md":
        return "tier-1"
    if rel_path.startswith("docs/governance/"):
        return "tier-1"
    if rel_path.startswith("docs/architecture/"):
        return "tier-2"
    if rel_path.startswith("docs/state/"):
        return "state"
    if rel_path.startswith("reports/"):
        return "projection"
    return ""


def _words(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]{4,}", text.lower())]
