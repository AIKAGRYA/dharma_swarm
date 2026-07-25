from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from dharma_swarm.memory_retrieval import (
    GovernedRetrievalEngine,
    RetrievalAbstentionConfig,
    RetrievalQuery,
)
from dharma_swarm.vector_store import VectorStore


def _seed_vector_store(tmp_path):
    store = VectorStore(state_dir=tmp_path, dim=32)
    store.upsert(
        "Fresh A2A consumer liveness projection: semantic inbox drains require a verified reply receipt.",
        source="receipt:a2a-consumer-liveness",
        layer="working",
        metadata={"expected": "a2a"},
        event_time=datetime.now(timezone.utc),
    )
    store.upsert(
        "Bronze supply-chain intake closed MinHash dedupe and raw boundary receipts.",
        source="receipt:bronze-supply-chain",
        layer="consolidated",
        metadata={"expected": "bronze"},
        event_time=datetime.now(timezone.utc) - timedelta(days=90),
    )
    store.upsert(
        "Correlation handle corr-2026-06-a2a-liveness maps the launchd drill to the domain reply.",
        source="receipt:correlation-edge",
        layer="working",
        metadata={"expected": "edge"},
        event_time=datetime.now(timezone.utc),
    )
    return store


def test_governed_retrieval_ranks_lexical_candidate(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    result = engine.retrieve("consumer liveness reply receipt")

    assert result.candidates
    assert result.candidates[0].metadata["expected"] == "a2a"
    assert "fts" in result.candidates[0].channels
    assert result.diagnostics.vector_db_bytes > 0


def test_governed_retrieval_handles_punctuation_heavy_identifiers(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    result = engine.retrieve("corr-2026-06-a2a-liveness")

    assert result.candidates
    assert result.candidates[0].metadata["expected"] == "edge"


def test_governed_retrieval_allows_hyphenated_wiki_titles_with_identity_match(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    neighbor = {
        "id": 40,
        "content": (
            "---\n"
            "title: Multi Latent Attention\n"
            "---\n"
            "Related notes mention Mixture-of-Experts, MoE, mixture, and experts."
        ),
        "source": "text_file:users-dhyana-.dharma-knowledge-wiki-concepts-multi-latent-attention.md",
        "layer": "source_file",
        "metadata": {"expected": "neighbor"},
        "distance": 0.5,
    }
    target = {
        "id": 41,
        "content": (
            "---\n"
            "title: \"Mixture-of-Experts (MoE)\"\n"
            "---\n"
            "# Mixture-of-Experts\n"
            "A routed expert model architecture."
        ),
        "source": "text_file:users-dhyana-.dharma-knowledge-wiki-concepts-mixture-of-experts.md",
        "layer": "source_file",
        "metadata": {"expected": "target"},
        "distance": 0.5,
    }

    result = engine._fuse_candidates(
        query_text="Mixture-of-Experts (MoE) mixture of experts",
        vector_results=[],
        fts_results=[neighbor, target],
        top_k=2,
        min_score=0.01,
        include_content=True,
    )

    assert result
    assert result[0].metadata["expected"] == "target"
    assert result[0].metadata["retrieval_title_match"] == 1.0


def test_governed_retrieval_rejects_degraded_vector_only_noise(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    result = engine.retrieve("zxqwbblplk fnord qqqnotindexed")

    assert result.candidates == ()


def test_governed_retrieval_records_query_telemetry(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    engine.retrieve("consumer liveness reply receipt")
    engine.retrieve(
        RetrievalQuery(
            text="bronze supply-chain dedupe receipts",
            record_telemetry=False,
        )
    )

    conn = sqlite3.connect(tmp_path / "vectors.db")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT query_hash, query_preview, top_source, result_count, total_ms
            FROM memory_retrieval_query_log
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["query_hash"]
    assert rows[0]["query_preview"] == "consumer liveness reply receipt"
    assert "a2a-consumer-liveness" in rows[0]["top_source"]
    assert rows[0]["result_count"] > 0
    assert rows[0]["total_ms"] is not None


@dataclass
class _FakePack:
    candidate_count: int = 3
    admitted_count: int = 2
    omitted_count: int = 1
    pack_id: str = "pack_fake"
    warnings: tuple[str, ...] = ("preview_only_no_runtime_prompt_injection",)


class _FakeKernel:
    def preview_memory_pack(self, **_kwargs):
        return _FakePack()


def test_memory_kernel_admission_summary_is_attached_and_honest(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(
        state_dir=tmp_path,
        vector_store=store,
        memory_kernel=_FakeKernel(),
    )

    result = engine.retrieve(
        RetrievalQuery(
            text="bronze supply-chain dedupe receipts",
            top_k=2,
            kernel_candidate_limit=3,
            kernel_admitted_limit=2,
        )
    )

    assert result.memory_kernel.available is True
    assert result.memory_kernel.text_query_supported is False
    assert result.memory_kernel.admitted_count == 2
    assert "memory_kernel_text_query_not_yet_supported" in result.memory_kernel.warnings


def test_retrieval_diagnostics_surface_guarded_projection(tmp_path, monkeypatch):
    store = _seed_vector_store(tmp_path)
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    diagnostics = engine.diagnostics()

    assert "fts_guard_blocked" in diagnostics.degraded_reasons
    assert "vector_guard_blocked_without_sqlite_vec" in diagnostics.degraded_reasons


def test_governed_retrieval_uses_bounded_fts_when_full_fts_guarded(
    tmp_path,
    monkeypatch,
):
    store = _seed_vector_store(tmp_path)
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    result = engine.retrieve("consumer liveness reply receipt")

    assert result.candidates
    assert result.candidates[0].metadata["expected"] == "a2a"
    assert "fts_guard_blocked" in result.diagnostics.degraded_reasons


def test_bounded_fts_prefers_backfilled_memory_layer(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    for index in range(20):
        store.upsert(
            f"Evolution archive loop noise entry {index}: generic April loop status.",
            source=f"evolution_archive:{index}",
            layer="development",
            metadata={"expected": "noise"},
        )
    store.upsert(
        "Claude memory context observation: 42219 Observation: Dharma Capital Holon: Loop Never Closes - 87 Cycles, Zero Tier Changes Applied",
        source="agents_context:42219",
        layer="memory_context",
        metadata={"expected": "memory_context"},
    )
    monkeypatch.setenv("DHARMA_VECTOR_FTS_MAX_ROWS", "1")
    monkeypatch.setenv("DHARMA_VECTOR_FALLBACK_MAX_ROWS", "1")
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    result = engine.retrieve(
        RetrievalQuery(
            text="Dharma Capital Holon loop never closes",
            top_k=1,
        )
    )

    assert result.candidates
    assert result.candidates[0].metadata["expected"] == "memory_context"


def test_governed_retrieval_rejects_vector_only_evolution_archive_handle_noise(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    noise = {
        "id": 999,
        "content": "Evolution archive entry with generic 2026 timestamp and A2A routing noise.",
        "source": "evolution_archive:noisy",
        "layer": "development",
        "metadata": {"expected": "noise"},
        "distance": 0.01,
    }

    result = engine._fuse_candidates(
        query_text="corr-2026-06-a2a-liveness",
        vector_results=[noise],
        fts_results=[],
        top_k=3,
        min_score=0.01,
        include_content=True,
    )

    assert result == []


def test_governed_retrieval_weights_discriminating_query_terms(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    generic_rows = [
        {
            "id": index + 10,
            "content": f"Adjacent carbon offset restoration note {index} without platform implementation evidence.",
            "source": f"agents_context:generic-carbon-offset-{index}",
            "layer": "memory_context",
            "metadata": {"expected": "generic"},
            "distance": 0.5,
        }
        for index in range(5)
    ]
    specific_row = {
        "id": 99,
        "content": "GAIA Platform: Full Ecological Restoration Coordination System Already Implemented.",
        "source": "agents_context:41706:gaia-platform-full-ecological-restoration-coordination-system-already-implemented",
        "layer": "memory_context",
        "metadata": {"expected": "gaia"},
        "distance": 0.5,
    }

    result = engine._fuse_candidates(
        query_text="AI carbon offset restoration platform already implemented",
        vector_results=[],
        fts_results=[*generic_rows, specific_row],
        top_k=3,
        min_score=0.01,
        include_content=True,
    )

    assert result
    assert result[0].metadata["expected"] == "gaia"
    assert result[0].metadata["retrieval_weighted_token_overlap"] > result[0].metadata["retrieval_token_overlap"]


def test_governed_retrieval_prefers_relation_title_when_query_names_target(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    entity_row = {
        "id": 20,
        "content": (
            "Memory graph entity: MemoryKernel query-relevance gap "
            "(open, dual-audit-worthy)\nObservations:\n"
            "- The keystone wiki read path architecture issue is tracked."
        ),
        "source": "memory_graph:memorykernel-query-relevance-gap-open-dual-audit-worthy",
        "layer": "memory_graph",
        "metadata": {"expected": "entity"},
        "distance": 0.5,
    }
    relation_row = {
        "id": 21,
        "content": (
            "Memory graph relation: MemoryKernel query-relevance gap "
            "(open, dual-audit-worthy) --is the open keystone of--> "
            "Wiki Read-Path Architecture (verified 2026-06-08)"
        ),
        "source": "memory_relation:memorykernel-query-relevance-gap-open-dual-audit-worthy-:is-the-open-keystone-of:wiki-read-path",
        "layer": "memory_graph",
        "metadata": {"expected": "relation"},
        "distance": 0.5,
    }

    result = engine._fuse_candidates(
        query_text=(
            "open keystone wiki read path architecture verified "
            "memorykernel query relevance gap"
        ),
        vector_results=[],
        fts_results=[entity_row, relation_row],
        top_k=2,
        min_score=0.01,
        include_content=True,
    )

    assert result
    assert result[0].metadata["expected"] == "relation"


def test_governed_retrieval_prefers_source_identity_for_source_files(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)
    neighboring_file = {
        "id": 30,
        "content": "Organism council live daemon config state directory runtime notes.",
        "source": "text_file:users-dhyana-dharma_swarm-scripts-organism_council.py",
        "layer": "source_file",
        "metadata": {"expected": "neighbor"},
        "distance": 0.5,
    }
    target_file = {
        "id": 31,
        "content": "Run the OrganismRuntime against live daemon state.",
        "source": "text_file:users-dhyana-dharma_swarm-scripts-organism_live.py",
        "layer": "source_file",
        "metadata": {"expected": "target"},
        "distance": 0.5,
    }

    result = engine._fuse_candidates(
        query_text="organism live daemon config state dir run organismruntime",
        vector_results=[],
        fts_results=[neighboring_file, target_file],
        top_k=2,
        min_score=0.01,
        include_content=True,
    )

    assert result
    assert result[0].metadata["expected"] == "target"
    assert result[0].metadata["retrieval_source_match"] > 0


def test_nonsense_query_abstains_when_calibrated_config_enabled(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(
        state_dir=tmp_path,
        vector_store=store,
        abstention=RetrievalAbstentionConfig.calibrated(min_score=0.37),
    )

    result = engine.retrieve("nonexistent zxqwbblplk fnord")

    assert result.candidates == ()
    assert result.abstained is True
    assert result.abstained_reason in {
        "no_candidates_above_min_score",
        "no_matching_documents",
    }


def test_legacy_default_never_marks_abstained(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    assert engine.abstention == RetrievalAbstentionConfig()
    nonsense = engine.retrieve("nonexistent zxqwbblplk fnord")
    served = engine.retrieve("consumer liveness reply receipt")

    assert nonsense.abstained is False
    assert nonsense.abstained_reason == ""
    assert served.abstained is False
    assert served.candidates
    assert served.candidates[0].metadata["expected"] == "a2a"


def test_calibrated_min_score_overrides_query_min_score(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(
        state_dir=tmp_path,
        vector_store=store,
        abstention=RetrievalAbstentionConfig.calibrated(min_score=0.99),
    )

    result = engine.retrieve("consumer liveness reply receipt")

    assert result.candidates == ()
    assert result.abstained is True
    assert result.abstained_reason == "no_candidates_above_min_score"


def test_calibrated_empty_query_abstains_with_reason(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(
        state_dir=tmp_path,
        vector_store=store,
        abstention=RetrievalAbstentionConfig.calibrated(),
    )

    result = engine.retrieve("   ")

    assert result.candidates == ()
    assert result.abstained is True
    assert result.abstained_reason == "empty_query"


def test_telemetry_records_shadow_abstention_columns(tmp_path):
    store = _seed_vector_store(tmp_path)
    engine = GovernedRetrievalEngine(state_dir=tmp_path, vector_store=store)

    engine.retrieve("consumer liveness reply receipt")
    engine.retrieve("nonexistent zxqwbblplk fnord")

    conn = sqlite3.connect(tmp_path / "vectors.db")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT query_preview, abstained, abstained_reason,
                   shadow_abstained, shadow_min_score
            FROM memory_retrieval_query_log
            ORDER BY id
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    served, nonsense = rows
    assert served["abstained"] == 0
    assert served["abstained_reason"] == ""
    assert served["shadow_min_score"] == 0.37
    assert nonsense["abstained"] == 0
    assert nonsense["shadow_abstained"] == 1


def test_telemetry_schema_upgrade_is_additive(tmp_path):
    from dharma_swarm.memory_kernel_retrieval.scoring_terms import (
        _ensure_retrieval_telemetry_table,
    )

    db = tmp_path / "vectors.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE memory_retrieval_query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_time TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            query_preview TEXT NOT NULL,
            top_doc_id TEXT DEFAULT '',
            top_source TEXT DEFAULT '',
            top_layer TEXT DEFAULT '',
            top_score REAL,
            result_count INTEGER NOT NULL,
            total_ms REAL,
            vector_search_ms REAL,
            fts_search_ms REAL,
            fusion_ms REAL,
            memory_kernel_available INTEGER NOT NULL DEFAULT 0,
            memory_kernel_text_query_supported INTEGER NOT NULL DEFAULT 0,
            memory_kernel_admitted_count INTEGER NOT NULL DEFAULT 0,
            degraded_reasons_json TEXT NOT NULL DEFAULT '[]',
            top_channels_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO memory_retrieval_query_log (query_time, query_hash, query_preview, result_count)
        VALUES ('2026-07-01T00:00:00+00:00', 'h', 'legacy row', 3)
        """
    )
    conn.commit()

    _ensure_retrieval_telemetry_table(conn)
    _ensure_retrieval_telemetry_table(conn)

    row = conn.execute(
        "SELECT abstained, abstained_reason, shadow_abstained, shadow_min_score "
        "FROM memory_retrieval_query_log"
    ).fetchone()
    conn.close()
    assert row == (0, "", None, None)


def test_abstention_config_from_env(monkeypatch):
    monkeypatch.delenv("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_ABSTENTION", raising=False)
    monkeypatch.delenv("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_MIN_SCORE", raising=False)
    assert RetrievalAbstentionConfig.from_env() == RetrievalAbstentionConfig()

    monkeypatch.setenv("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_ABSTENTION", "1")
    monkeypatch.setenv("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_MIN_SCORE", "0.37")
    config = RetrievalAbstentionConfig.from_env()
    assert config.enabled is True
    assert config.include_below_threshold is False
    assert config.apply_score_floors is False
    assert config.min_score == 0.37

    monkeypatch.setenv("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_MIN_SCORE", "not-a-float")
    assert RetrievalAbstentionConfig.from_env().min_score is None
