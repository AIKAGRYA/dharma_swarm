from __future__ import annotations

from dharma_swarm.vector_store import VectorStore
from scripts.memory_retrieval_sync_index import sync_memory_retrieval_index
from scripts.memory_retrieval_system_gate import run_system_gate


def test_memory_retrieval_system_gate_scores_health_and_coverage(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    store.upsert(
        "Claude memory context observation: Bronze dedupe receipts closed.",
        source="agents_context:bronze",
        layer="memory_context",
    )
    store.upsert(
        "Memory graph relation: alpha_beta --relates_to--> gamma_delta",
        source="memory_relation:alpha_beta:relates_to:gamma_delta:123456789abc",
        layer="memory_graph",
    )
    store.upsert(
        "MCP transport source file covers stdio, SSE, WebSocket, and memory queues.",
        source="text_file:mcp-transport-doc",
        layer="source_file",
    )
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)

    sync_memory_retrieval_index(state_dir=tmp_path, dim=32)
    payload = run_system_gate(
        state_dir=tmp_path,
        negative_count=1,
        source_file_target=1,
        memory_context_target=1,
        memory_graph_target=1,
        run_live=False,
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["compact_sidecar_exhaustive_recall"]["passed"]
    assert checks["index_health_and_freshness"]["passed"]
    assert checks["curated_source_coverage"]["passed"]
    assert checks["retrieval_telemetry"]["passed"]
    assert payload["telemetry"]["new_rows"] == payload["broad"]["case_count"]
