from __future__ import annotations

import json

from dharma_swarm.vector_store import VectorStore
from scripts.vector_store_reembed_vec0 import reembed_queries


def _delete_embedding_for_doc(store: VectorStore, doc_id: int) -> None:
    conn = store._connect()
    try:
        table = "vec_embeddings" if store._has_vec0(conn) else "vec_embeddings_fallback"
        conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


def test_reembed_queries_updates_vec0_for_matching_rows(tmp_path):
    store = VectorStore(state_dir=tmp_path, dim=32)
    doc_id = store.upsert(
        "MemoryKernel governed retrieval admission preview",
        source="doc:memory-kernel",
    )
    store.upsert("Unrelated GAIA restoration packet", source="doc:gaia")

    _delete_embedding_for_doc(store, doc_id)

    receipt = reembed_queries(
        state_dir=tmp_path,
        queries=("memory kernel retrieval admission",),
        limit_per_query=5,
        dim=32,
        dry_run=False,
    )

    assert receipt.selected_rows >= 1
    assert receipt.upserted_rows >= 1
    repaired = VectorStore(state_dir=tmp_path, dim=32)
    results = repaired.search_vector("memory kernel retrieval", top_k=3)
    assert any(row["id"] == doc_id for row in results)


def test_reembed_queries_can_replace_corpus_from_memory_retrieval_docs(tmp_path):
    store = VectorStore(state_dir=tmp_path, dim=32)
    doc_id = store.upsert(
        "MemoryKernel governed retrieval admission preview",
        source="doc:memory-kernel",
    )
    other_id = store.upsert(
        "GAIA restoration packet for browser state recovery",
        source="doc:gaia",
    )
    general_state_path = tmp_path / "tfidf_embedder.pkl"
    memory_state_path = tmp_path / "tfidf_embedder_memory_retrieval.pkl"
    memory_state_path.write_text(
        json.dumps(
            {
                "corpus": ["poisoned query corpus lunar cheese invoice"],
                "corpus_hash": "poison",
                "dim": 32,
                "fitted": False,
            }
        ),
        encoding="utf-8",
    )
    conn = store._connect()
    try:
        conn.execute(
            """
            CREATE TABLE memory_retrieval_docs (
                vec_doc_id INTEGER PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                valid_until TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO memory_retrieval_docs
                (vec_doc_id, content, source, valid_until)
            VALUES (?, ?, ?, NULL)
            """,
            [
                (
                    doc_id,
                    "MemoryKernel governed retrieval admission preview",
                    "doc:memory-kernel",
                ),
                (
                    other_id,
                    "GAIA restoration packet for browser state recovery",
                    "doc:gaia",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    receipt = reembed_queries(
        state_dir=tmp_path,
        queries=(),
        limit_per_query=5,
        include_memory_retrieval_docs=True,
        memory_doc_limit=10,
        replace_embedder_corpus=True,
        dim=32,
        dry_run=False,
    )

    assert receipt.selected_rows == 2
    assert receipt.upserted_rows == 2
    assert general_state_path.exists()
    state = json.loads(memory_state_path.read_text(encoding="utf-8"))
    assert "poisoned query corpus lunar cheese invoice" not in state["corpus"]
    assert "MemoryKernel governed retrieval admission preview" in state["corpus"]
