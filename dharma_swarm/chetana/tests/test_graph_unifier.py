"""Tests for chetana.graph_unifier — unified query interface across 4 graphs."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.chetana import graph_unifier as gu_mod
from dharma_swarm.chetana.graph_unifier import coverage_summary, query


def test_query_against_empty_catalytic_returns_no_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(gu_mod, "CATALYTIC_GRAPH_PATH", tmp_path / "missing.json", raising=True)
    result = query("strange loop", sources=["catalytic"])
    assert result.coverage["catalytic"] == 0
    assert any("missing" in n for n in result.notes)


def test_query_finds_node_in_catalytic_graph(tmp_path, monkeypatch):
    cat_file = tmp_path / "catalytic_graph.json"
    cat_file.write_text(
        json.dumps(
            {
                "nodes": {
                    "strange-loop": {"label": "Strange Loop (Hofstadter)", "weight": 0.9},
                    "telos-gradient": {"label": "Telos Gradient", "weight": 0.7},
                    "rv-paper": {"label": "R_V Paper", "weight": 1.0},
                },
                "edges": [],
            }
        )
    )
    monkeypatch.setattr(gu_mod, "CATALYTIC_GRAPH_PATH", cat_file, raising=True)
    result = query("strange loop", sources=["catalytic"])
    assert result.coverage["catalytic"] >= 1
    hits = result.by_source("catalytic")
    assert any("Strange Loop" in h.label for h in hits)


def test_query_missing_backends_dont_break(tmp_path, monkeypatch):
    """Memory + contextplus require an MCP client; graph_unifier should not crash."""
    monkeypatch.setattr(gu_mod, "CATALYTIC_GRAPH_PATH", tmp_path / "missing.json", raising=True)
    result = query("anything", sources=["memory", "contextplus", "gitnexus"])
    # All three either produce 0 hits with notes, or some hits — no exceptions.
    assert isinstance(result.coverage, dict)
    assert all(v >= 0 for v in result.coverage.values())


def test_coverage_summary_renders():
    from dharma_swarm.chetana.graph_unifier import UnifiedQueryResult, GraphHit

    result = UnifiedQueryResult(query="x")
    result.coverage = {"catalytic": 2, "memory": 0}
    result.hits = [
        GraphHit(source="catalytic", kind="node", id="a", label="A"),
        GraphHit(source="catalytic", kind="node", id="b", label="B"),
    ]
    text = coverage_summary(result)
    assert "Unified graph query" in text
    assert "catalytic: 2" in text
