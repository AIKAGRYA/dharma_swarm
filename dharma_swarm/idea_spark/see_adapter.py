"""Spark -> Semantic Evolution Engine adapter — the A->B wire.

Bridges an operator Idea Spark (``dharma_swarm/idea_spark/``) into the
Semantic Evolution Engine (``dharma_swarm/semantic_*.py``): a raw spark is
digested into a :class:`ConceptNode`, made *elevation-eligible by operator
provenance* (not a faked quality score), research-annotated, and injected
into a concept graph idempotently.

Honesty boundaries (verified 2026-06-28, via the idea-elevation workflow's
adversarial stress pass):
- ``SemanticResearcher`` is currently a CANNED table lookup, not live
  research. This adapter makes a spark *eligible* for that leg; it does not
  make the leg real. Wiring live research is a separate stage.
- Hardening/synthesis operate on FILE CLUSTERS, not single nodes; a lone
  spark is researched but not hardened until it clusters with kin.
- The salience floor is by PROVENANCE (operator-origin), set to the research
  gate threshold, recorded as such in ``metadata``. It is NOT derived from
  triage_score — that would forge a quality signal past the gate.
- Operator privacy: when ``authority_level == 'observation'`` the raw spark
  body is withheld from the persisted node (reference-by-digest), mirroring
  the idea_spark MemoryKernel leak fix.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.semantic_digester import SemanticDigester
from dharma_swarm.semantic_gravity import (
    ConceptGraph,
    ConceptNode,
    ResearchAnnotation,
    ResearchConnectionType,
)
from dharma_swarm.semantic_researcher import SemanticResearcher

# SemanticResearcher's default salience gate (semantic_researcher.py:265).
RESEARCH_GATE_THRESHOLD = 0.4


def _spark_node_id(correlation_id: str) -> str:
    """Deterministic node id so re-injecting the same spark cannot duplicate."""
    return "spark_" + hashlib.sha256(correlation_id.encode()).hexdigest()[:16]


def spark_to_node(
    text: str,
    correlation_id: str,
    *,
    authority_level: str = "observation",
) -> ConceptNode:
    """Digest a raw spark into a provenance-tagged, elevation-eligible node."""
    base = SemanticDigester().digest_text(text, name=correlation_id)

    body_redacted = authority_level == "observation"
    definition = base.definition
    if body_redacted:
        digest = hashlib.sha256(text.encode()).hexdigest()
        definition = f"[operator spark body withheld — sha256:{digest}]"

    floored = max(base.salience, RESEARCH_GATE_THRESHOLD)
    meta = dict(base.metadata)
    meta.update(
        {
            "source": "idea_spark",
            "correlation_id": correlation_id,
            "authority_level": authority_level,
            "computed_salience": base.salience,
            "body_redacted": body_redacted,
            "elevation_floor_reason": "operator_origin_provenance_not_quality",
        }
    )
    return base.model_copy(
        update={
            "id": _spark_node_id(correlation_id),
            "source_file": f"idea_spark://{correlation_id}",
            "definition": definition,
            "salience": floored,
            "metadata": meta,
        }
    )


def inject_spark(graph: ConceptGraph, node: ConceptNode) -> str:
    """Idempotently add a spark node to an in-memory graph. Returns node id."""
    if graph.get_node(node.id) is not None:
        return node.id  # already present -> no duplicate (guards _by_name append)
    return graph.add_node(node)


def elevate_spark(
    text: str,
    correlation_id: str,
    *,
    authority_level: str = "observation",
):
    """Eligibility pass: digest -> provenance floor -> (canned) research-annotate.

    Returns ``(node, annotations)``. The annotations come from the currently
    canned :class:`SemanticResearcher`; their presence proves the deepen-leg
    CONSUMES the spark — not that the research is yet live.
    """
    node = spark_to_node(text, correlation_id, authority_level=authority_level)
    annotations = SemanticResearcher().annotate_concept(node)
    return node, annotations


@dataclass(frozen=True)
class ElevationResult:
    node_id: str
    salience: float
    computed_salience: float
    annotation_count: int
    body_redacted: bool
    graph_path: str
    # HONEST: the SemanticResearcher leg is currently a canned table lookup.
    research_is_live: bool = False


def live_research_annotations(
    concept_id: str,
    query: str,
    *,
    max_results: int = 4,
    backend: str = "arxiv",
) -> list[ResearchAnnotation]:
    """LIVE research: real external sources -> ResearchAnnotations, replacing the
    canned RESEARCH_CONNECTIONS table with grounded citations.

    Opt-in: it transmits ``query`` (the spark text) to an external search
    backend, so callers gate it behind explicit operator consent. Returns ``[]``
    on any failure so elevation still succeeds with the canned annotations.
    ``arxiv`` is the verified key-free backend in the current environment.
    """
    from dharma_swarm.web_search import search_web  # lazy: only when opted in

    try:
        results = asyncio.run(
            search_web(query, max_results=max_results, backend=backend, format_output=False)
        )
    except Exception:
        return []
    annotations: list[ResearchAnnotation] = []
    for r in results or []:
        annotations.append(
            ResearchAnnotation(
                concept_id=concept_id,
                connection_type=ResearchConnectionType.VALIDATION,
                external_source=r.source or backend,
                citation=r.url,
                summary=f"{r.title}: {r.snippet}"[:400],
                confidence=float(r.score or 0.5),
                field=backend,
                metadata={"matched_via": "live_web_search", "backend": backend, "title": r.title},
            )
        )
    return annotations


def elevate_to_graph(
    text: str,
    correlation_id: str,
    graph_path: str | Path,
    *,
    authority_level: str = "observation",
    live_research: bool = False,
    research_backend: str = "arxiv",
) -> ElevationResult:
    """Elevate a spark and persist it as an ISOLATED, idea_spark-scoped concept
    graph receipt — NOT the shared 26MB semantic canon (governance: the
    elevated writer never mutates owned canon). Idempotent per correlation_id.

    With ``live_research=True`` the deepen-leg is REAL: external sources are
    retrieved and attached as grounded ResearchAnnotations (opt-in, transmits
    the spark text). Otherwise the canned researcher is used and
    ``research_is_live`` stays False.
    """
    node, annotations = elevate_spark(text, correlation_id, authority_level=authority_level)
    annotations = list(annotations)
    research_is_live = False
    if live_research:
        live = live_research_annotations(node.id, text, backend=research_backend)
        if live:
            annotations.extend(live)
            research_is_live = True
    graph = ConceptGraph()
    inject_spark(graph, node)
    for ann in annotations:
        graph.add_annotation(ann)
    path = Path(graph_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(graph.save(path))
    return ElevationResult(
        node_id=node.id,
        salience=node.salience,
        computed_salience=float(node.metadata.get("computed_salience", node.salience)),
        annotation_count=len(annotations),
        body_redacted=bool(node.metadata.get("body_redacted", False)),
        graph_path=str(path),
        research_is_live=research_is_live,
    )
