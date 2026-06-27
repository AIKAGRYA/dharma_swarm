"""Proof slice: a REAL operator spark is elevated into the Semantic Evolution
Engine via the A->B adapter. Asserts OBSERVED reality (including the honest
degraded behavior the adversarial pass surfaced), not a cherry-picked toy."""

import asyncio
import tempfile
from pathlib import Path

from dharma_swarm.idea_spark.see_adapter import (
    RESEARCH_GATE_THRESHOLD,
    elevate_spark,
    elevate_to_graph,
    inject_spark,
    spark_to_node,
)
from dharma_swarm.semantic_gravity import ConceptGraph

# A genuine operator spark (the 2026-06-20 morning briefing's "single most
# important move") — realistic, vocabulary-free; NOT reverse-engineered to hit
# the researcher's frozen citation table.
REAL_SPARK = (
    "Fix the chetana gap-scan to cross-validate reference counts against the "
    "actual concepts/ directory before declaring gaps, so the gap queue stops "
    "chasing phantom gaps for articles that already exist."
)
CORR = "corr_realspark_gapscan"


def test_real_spark_is_starved_by_quality_but_eligible_by_provenance():
    node = spark_to_node(REAL_SPARK, CORR, authority_level="observation")
    # HONEST: the spark's computed semantic salience is BELOW the research gate
    # (real operator sparks are vocabulary-free; they score ~0.13, not >=0.4).
    assert node.metadata["computed_salience"] < RESEARCH_GATE_THRESHOLD
    assert node.formal_structures == []  # no frozen-table keys; the realistic case
    # ...yet operator PROVENANCE floors it to elevation-eligible — and says so,
    # rather than forging a quality score.
    assert node.salience >= RESEARCH_GATE_THRESHOLD
    assert node.salience >= node.metadata["computed_salience"]  # floor never lowers
    assert node.metadata["elevation_floor_reason"] == "operator_origin_provenance_not_quality"
    assert node.source_file == f"idea_spark://{CORR}"
    assert node.metadata["source"] == "idea_spark"


def test_consent_gate_withholds_observation_body_but_passes_authorized():
    obs = spark_to_node(REAL_SPARK, CORR, authority_level="observation")
    assert "withheld" in obs.definition
    assert "chetana gap-scan" not in obs.definition  # raw body not leaked
    assert obs.metadata["body_redacted"] is True

    authorized = spark_to_node(REAL_SPARK, CORR, authority_level="proposal")
    assert authorized.definition.startswith(REAL_SPARK[:40])
    assert authorized.metadata["body_redacted"] is False


def test_injection_is_idempotent():
    graph = ConceptGraph()
    node = spark_to_node(REAL_SPARK, CORR)
    inject_spark(graph, node)
    inject_spark(graph, node)  # second injection must NOT duplicate
    assert graph.node_count == 1
    assert len(graph._by_name[node.name.lower()]) == 1  # not a silent dupe list


def test_deepen_leg_consumes_spark_and_persists_round_trip():
    node, annotations = elevate_spark(REAL_SPARK, CORR)
    # the (currently CANNED) research leg consumes the spark node and returns
    # annotations — proving the deepen-leg accepts spark-origin input at all.
    assert isinstance(annotations, list)

    graph = ConceptGraph()
    inject_spark(graph, node)

    # Round-trip through the REAL async persistence (isolated temp graph — the
    # production 26MB concept_graph.json is never touched by this slice).
    path = Path(tempfile.mkdtemp()) / "spark_graph.json"
    asyncio.run(graph.save(path))
    reloaded = asyncio.run(ConceptGraph.load(path))
    assert reloaded.get_node(node.id) is not None


def test_elevate_to_graph_persists_isolated_receipt():
    path = Path(tempfile.mkdtemp()) / "elevated" / "g.json"
    result = elevate_to_graph(REAL_SPARK, CORR, path, authority_level="observation")
    assert result.salience >= RESEARCH_GATE_THRESHOLD  # provenance-floored
    assert result.computed_salience <= result.salience
    assert result.research_is_live is False  # honest: canned research leg
    assert result.body_redacted is True
    assert Path(result.graph_path).exists()
    # reload proves the elevated node persisted to its own isolated graph
    reloaded = asyncio.run(ConceptGraph.load(path))
    assert reloaded.get_node(result.node_id) is not None


def test_live_research_attaches_grounded_annotations(monkeypatch):
    """Deterministic (mocked) proof that live_research wires real external
    sources into the elevated graph as ResearchAnnotations."""
    import dharma_swarm.web_search as ws

    class _FakeResult:
        title = "Gap detection over concept graphs"
        url = "http://arxiv.org/abs/2406.00001"
        snippet = "A method for validating reference counts before declaring gaps."
        source = "arxiv"
        score = 0.91

    async def _fake_search_web(query, max_results=5, backend=None, domain=None, format_output=True):
        assert query  # the spark text is passed through to research
        return [_FakeResult(), _FakeResult()]

    monkeypatch.setattr(ws, "search_web", _fake_search_web)

    path = Path(tempfile.mkdtemp()) / "elevated" / "live.json"
    result = elevate_to_graph(
        REAL_SPARK, CORR, path, authority_level="proposal", live_research=True
    )
    assert result.research_is_live is True
    assert result.annotation_count >= 2  # canned + 2 live
    # the grounded annotations persist into the isolated receipt
    reloaded = asyncio.run(ConceptGraph.load(path))
    assert reloaded.annotation_count >= 2
