from __future__ import annotations

from dharma_swarm.vector_store import VectorStore
from scripts.vector_store_live_gate import run_gate
from scripts.vector_store_reembed_vec0 import reembed_queries


def test_vector_store_live_gate_passes_against_memory_projection(tmp_path):
    store = VectorStore(state_dir=tmp_path, dim=128)
    doc_id = store.upsert(
        "Orchestrator async task routing engine",
        source="doc:orchestrator",
        layer="source_file",
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
        conn.execute(
            """
            INSERT INTO memory_retrieval_docs
                (vec_doc_id, content, source, valid_until)
            VALUES (?, ?, ?, NULL)
            """,
            (doc_id, "Orchestrator async task routing engine", "doc:orchestrator"),
        )
        conn.commit()
    finally:
        conn.close()

    reembed_queries(
        state_dir=tmp_path,
        queries=(),
        limit_per_query=5,
        include_memory_retrieval_docs=True,
        memory_doc_limit=10,
        replace_embedder_corpus=True,
        dim=128,
        dry_run=False,
    )

    receipt = run_gate(
        state_dir=tmp_path,
        top_k=2,
        min_memory_corpus=1,
        max_p95_ms=5000.0,
        cases=(
            {
                "name": "orchestrator",
                "query": "orchestrator async task routing engine",
                "expected": "doc:orchestrator",
            },
            {
                "name": "negative",
                "query": "xyzzq impossible memory topic lunar cheese invoice",
                "expected": "",
                "expect_empty": True,
            },
        ),
    )

    assert receipt.passed
    assert receipt.score == 100.0
