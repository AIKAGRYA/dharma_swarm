from __future__ import annotations

import json

from dharma_swarm.vector_store import VectorStore
from scripts.vector_store_backfill_memory_sources import (
    backfill_memory_sources,
    discover_text_files,
    load_agents_context,
    load_memory_jsonl,
    load_text_file,
)


def test_load_memory_jsonl_entities_and_relations(tmp_path):
    memory = tmp_path / "memory.jsonl"
    memory.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "entity",
                        "name": "Bronze supply-chain intake",
                        "entityType": "feature",
                        "observations": ["MinHash dedupe works", "Boundary receipts inspected"],
                    }
                ),
                json.dumps(
                    {
                        "type": "relation",
                        "from": "Bronze supply-chain intake",
                        "to": "World radar",
                        "relationType": "feeds",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    docs = load_memory_jsonl(memory)

    assert len(docs) == 2
    assert "Memory graph entity: Bronze supply-chain intake" in docs[0].content
    assert "Memory graph relation:" in docs[1].content


def test_load_agents_context_observations(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """<claude-mem-context>
# Memory Context
# [dhyana] recent context, 2026-06-20 7:28pm GMT+9
### Jun 20, 2026
42195 6:03p Blue Bronze dedupe uses MinHash LSH with 32-element signature and 8 buckets
42196 " Blue PR #648 (Bronze supply-chain intake) has all 26 CI checks passing
</claude-mem-context>
""",
        encoding="utf-8",
    )

    docs = load_agents_context(agents)

    assert len(docs) == 2
    assert docs[0].metadata["observation_id"] == "42195"
    assert "Bronze dedupe uses MinHash" in docs[0].content


def test_backfill_memory_sources_is_resumable_and_searchable(tmp_path):
    memory = tmp_path / "memory.jsonl"
    memory.write_text(
        json.dumps(
            {
                "type": "entity",
                "name": "MemoryKernel query relevance gap",
                "entityType": "finding",
                "observations": ["MemoryKernel lacks text query relevance over admitted atoms"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """# [dhyana] recent context, 2026-06-20 7:28pm GMT+9
### Jun 20, 2026
42195 6:03p Blue Bronze dedupe uses MinHash LSH with 32-element signature and 8 buckets
""",
        encoding="utf-8",
    )

    receipt = backfill_memory_sources(
        state_dir=tmp_path,
        memory_jsonl_paths=(memory,),
        agents_context_paths=(agents,),
        text_file_paths=(),
        dim=32,
    )

    assert receipt.candidate_rows == 2
    assert receipt.inserted_rows == 2
    store = VectorStore(state_dir=tmp_path, dim=32)
    results = store.search_vector("bronze minhash dedupe", top_k=5)
    assert any("Bronze dedupe" in row["content"] for row in results)

    second = backfill_memory_sources(
        state_dir=tmp_path,
        memory_jsonl_paths=(memory,),
        agents_context_paths=(agents,),
        text_file_paths=(),
        dim=32,
    )

    assert second.inserted_rows == 0
    assert second.skipped_rows == 2


def test_backfill_memory_sources_dry_run_does_not_write(tmp_path):
    memory = tmp_path / "memory.jsonl"
    memory.write_text(
        json.dumps(
            {
                "type": "entity",
                "name": "Dry run memory",
                "entityType": "test",
                "observations": ["Should not be inserted"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    receipt = backfill_memory_sources(
        state_dir=tmp_path,
        memory_jsonl_paths=(memory,),
        agents_context_paths=(),
        text_file_paths=(),
        dim=32,
        dry_run=True,
    )

    assert receipt.selected_rows == 1
    assert receipt.inserted_rows == 0
    assert not (tmp_path / "vectors.db").exists()


def test_load_text_file_and_backfill_source_file(tmp_path):
    doc = tmp_path / "mcp_transport.md"
    doc.write_text(
        "MCP Python SDK communication transports include stdio, SSE, WebSocket, and memory queues.",
        encoding="utf-8",
    )

    docs = load_text_file(doc)

    assert len(docs) == 1
    assert docs[0].layer == "source_file"
    assert docs[0].metadata["source_kind"] == "text_file"

    receipt = backfill_memory_sources(
        state_dir=tmp_path,
        memory_jsonl_paths=(),
        agents_context_paths=(),
        text_file_paths=(doc,),
        dim=32,
    )

    assert receipt.inserted_rows == 1
    store = VectorStore(state_dir=tmp_path, dim=32)
    results = store.search_vector("MCP Python SDK stdio websocket memory", top_k=3)
    assert any("communication transports" in row["content"] for row in results)


def test_backfill_memory_sources_invalidates_replaced_source_file_rows(tmp_path):
    doc = tmp_path / "concept.md"
    doc.write_text("Obsolete amber concept text for source uid replacement.", encoding="utf-8")

    first = backfill_memory_sources(
        state_dir=tmp_path,
        memory_jsonl_paths=(),
        agents_context_paths=(),
        text_file_paths=(doc,),
        dim=32,
    )

    assert first.inserted_rows == 1
    assert first.invalidated_rows == 0

    doc.write_text("Fresh cyan concept text for source uid replacement.", encoding="utf-8")
    second = backfill_memory_sources(
        state_dir=tmp_path,
        memory_jsonl_paths=(),
        agents_context_paths=(),
        text_file_paths=(doc,),
        dim=32,
    )

    assert second.inserted_rows == 1
    assert second.invalidated_rows == 1

    source_uid = load_text_file(doc)[0].uid
    store = VectorStore(state_dir=tmp_path, dim=32)
    conn = store._connect()
    try:
        rows = conn.execute(
            """
            SELECT content, valid_until, metadata_json
            FROM vec_documents
            WHERE layer = 'source_file'
            ORDER BY id
            """
        ).fetchall()
    finally:
        conn.close()

    source_rows = [
        row
        for row in rows
        if json.loads(row["metadata_json"]).get("source_uid") == source_uid
    ]
    active_rows = [row for row in source_rows if row["valid_until"] is None]
    invalid_rows = [row for row in source_rows if row["valid_until"] is not None]

    assert len(source_rows) == 2
    assert len(active_rows) == 1
    assert len(invalid_rows) == 1
    assert "Fresh cyan concept" in active_rows[0]["content"]
    assert "Obsolete amber concept" in invalid_rows[0]["content"]

    stale_results = store.search_fts("Obsolete amber concept", top_k=5)
    assert all("Obsolete amber concept" not in row["content"] for row in stale_results)


def test_discover_text_files_prioritizes_docs_and_skips_noisy_dirs(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text("Important operator documentation", encoding="utf-8")
    package = tmp_path / "dharma_swarm"
    package.mkdir()
    module = package / "module.py"
    module.write_text("print('source code')", encoding="utf-8")
    noisy = tmp_path / ".venv"
    noisy.mkdir()
    skipped = noisy / "README.md"
    skipped.write_text("noise", encoding="utf-8")

    found = discover_text_files((tmp_path,), max_files=2, max_bytes=1024)

    assert readme in found
    assert module in found
    assert skipped not in found
