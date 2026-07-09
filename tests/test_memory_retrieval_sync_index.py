from __future__ import annotations

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine
from dharma_swarm.vector_store import VectorStore
from scripts.memory_retrieval_sync_index import sync_memory_retrieval_index


def test_compact_memory_retrieval_index_serves_source_file_rows(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    store.upsert(
        "MCP Python SDK communication transports include stdio, SSE, WebSocket, and memory queues.",
        source="text_file:mcp-python-sdk-communication-transports",
        layer="source_file",
        metadata={"expected": "mcp"},
    )
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)

    receipt = sync_memory_retrieval_index(state_dir=tmp_path, dim=32)

    assert receipt.indexed_rows == 1
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    result = engine.retrieve("MCP Python SDK stdio SSE websocket memory")

    assert result.candidates
    assert result.candidates[0].metadata["expected"] == "mcp"
    assert result.candidates[0].layer == "source_file"


def test_compact_memory_retrieval_index_triggers_track_new_curated_rows(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    sync_memory_retrieval_index(state_dir=tmp_path, dim=32)
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)

    store.upsert(
        "Fresh curated source row: Livelihood Loom operator proof queue.",
        source="agents_context:fresh-trigger",
        layer="memory_context",
        metadata={"expected": "trigger"},
    )

    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    result = engine.retrieve("fresh curated source row proof queue")

    assert result.candidates
    assert result.candidates[0].metadata["expected"] == "trigger"


def test_compact_memory_retrieval_update_trigger_preserves_curated_rows(tmp_path):
    store = VectorStore(state_dir=tmp_path, dim=32)
    store.upsert(
        "Curated source row survives access tracking updates.",
        source="text_file:update-trigger-doc",
        layer="source_file",
        metadata={"expected": "update-trigger"},
    )
    sync_memory_retrieval_index(state_dir=tmp_path, dim=32)

    conn = store._connect()
    try:
        conn.execute(
            """
            UPDATE vec_documents
            SET access_count = access_count + 1
            WHERE source = 'text_file:update-trigger-doc'
            """
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT source, access_count
            FROM memory_retrieval_docs
            WHERE source = 'text_file:update-trigger-doc'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["access_count"] == 1
