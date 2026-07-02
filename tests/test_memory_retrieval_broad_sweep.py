from __future__ import annotations

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine
from dharma_swarm.vector_store import VectorStore
from scripts.memory_retrieval_broad_sweep import (
    IndexedRow,
    build_cases,
    load_indexed_rows,
    query_for_row,
    run_case,
)
from scripts.memory_retrieval_sync_index import sync_memory_retrieval_index


def test_broad_sweep_query_splits_relation_sources():
    row = IndexedRow(
        vec_doc_id=1,
        source="memory_relation:alpha_beta:relates_to:gamma_delta:123456789abc",
        layer="memory_graph",
        content="Memory graph relation: alpha_beta --relates_to--> gamma_delta",
    )

    query = query_for_row(row)

    assert "alpha" in query
    assert "beta" in query
    assert "relat" in query
    assert "gamma" in query
    assert "delta" in query


def test_broad_sweep_query_prefers_relation_target_terms():
    row = IndexedRow(
        vec_doc_id=1,
        source="memory_relation:memorykernel-query-relevance-gap-open-dual-audit-worthy-:is-the-open-keystone-of:wiki-read-path:f0a2b52efc13",
        layer="memory_graph",
        content=(
            "Memory graph relation: MemoryKernel query-relevance gap "
            "(open, dual-audit-worthy) --is the open keystone of--> "
            "Wiki Read-Path Architecture (verified 2026-06-08)"
        ),
    )

    query = query_for_row(row)

    assert query.index("architecture") < query.index("memorykernel")
    assert "verifi" in query


def test_broad_sweep_source_file_query_prefers_filename_terms():
    row = IndexedRow(
        vec_doc_id=1,
        source="text_file:users-dhyana-dharma_swarm-scripts-runtime-cwt_report.py:123456789abc",
        layer="source_file",
        content=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        ),
    )

    query = query_for_row(row)

    assert query.split()[:3] == ["runtime", "cwt", "report"]
    assert "python3" not in query


def test_broad_sweep_source_file_query_keeps_short_filename_signals():
    row = IndexedRow(
        vec_doc_id=1,
        source="text_file:users-dhyana-.dharma-knowledge-wiki-concepts-rv-py.md:123456789abc",
        layer="source_file",
        content="# rv.py\n\nMetric implementation for participation ratio contraction.",
    )

    query = query_for_row(row)

    assert "rv" in query
    assert "py" in query


def test_broad_sweep_runs_against_compact_index(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    store.upsert(
        "Claude memory context observation: 1 Observation: Bronze CLI dedupe receipts closed cleanly.",
        source="agents_context:bronze-cli-dedupe",
        layer="memory_context",
    )
    store.upsert(
        "Memory graph relation: alpha_beta --relates_to--> gamma_delta",
        source="memory_relation:alpha_beta:relates_to:gamma_delta:123456789abc",
        layer="memory_graph",
    )
    store.upsert(
        "MCP Python SDK transport documentation covers stdio, SSE, WebSocket, and memory queues.",
        source="text_file:mcp-python-sdk-transport-doc",
        layer="source_file",
    )
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)
    sync_memory_retrieval_index(state_dir=tmp_path, dim=32)
    rows = load_indexed_rows(tmp_path)
    cases = build_cases(rows, case_count=5, negative_count=2)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    results = [run_case(engine, case, top_k=5, timeout_s=8) for case in cases]

    assert len(results) == 5
    assert all(row["passed"] for row in results)
