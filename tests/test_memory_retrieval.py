from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery
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


def test_atoms_for_candidates_maps_ranked_candidates_to_projection_atoms(tmp_path):
    from dharma_swarm.memory_kernel import (
        CensusConfig,
        MemoryAtomType,
        MemoryKernel,
        MemoryKernelConfig,
    )
    from dharma_swarm.memory_retrieval import RetrievalCandidate

    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=tmp_path / "repo",
                home=tmp_path / "home",
                include_discovered=False,
            )
        )
    )
    ranked = RetrievalCandidate(
        doc_id="doc-a2a",
        rank=1,
        score=0.91,
        source="receipt:a2a-consumer-liveness",
        layer="working",
        channels=("fts",),
        content="semantic inbox drains require a verified reply receipt",
    )
    unidentified = RetrievalCandidate(
        doc_id="",
        rank=2,
        score=0.4,
        source="receipt:no-doc-id",
        layer="working",
        channels=("vector",),
        content="candidate without a doc id is skipped",
    )

    atoms = kernel.atoms_for_candidates((ranked, unidentified))

    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.surface_id == "home.vectors"
    assert atom.atom_type == MemoryAtomType.SOURCE_CHUNK
    assert atom.content_ref == "retrieval:doc-a2a"
    assert atom.source_row_key == "doc-a2a"
    assert atom.source_refs == ("receipt:a2a-consumer-liveness",)
    assert atom.content == "semantic inbox drains require a verified reply receipt"
    assert atom.metadata["retrieval_rank"] == 1
    assert atom.metadata["retrieval_score"] == 0.91
    assert atom.metadata["retrieval_layer"] == "working"
    assert atom.metadata["retrieval_channels"] == ["fts"]
    assert atom.source_digest
    assert atom.promotion_allowed is False
    assert atom.context_admissible is False


def test_atoms_for_candidates_fails_loud_when_projection_surface_missing(tmp_path):
    import pytest

    from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig
    from dharma_swarm.memory_retrieval import RetrievalCandidate

    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=tmp_path / "repo",
                home=tmp_path / "home",
                include_discovered=False,
            )
        )
    )
    kernel.surfaces_by_id = {
        surface_id: surface
        for surface_id, surface in kernel.surfaces_by_id.items()
        if surface_id != "home.vectors"
    }
    candidate = RetrievalCandidate(
        doc_id="doc-a2a",
        rank=1,
        score=0.9,
        source="receipt:a2a-consumer-liveness",
        layer="working",
        channels=("fts",),
        content="chunk",
    )

    # A silent () would make shadow receipts read admitted=0 with no WHY;
    # the missing-surface anomaly must surface as a stamped shadow_error.
    with pytest.raises(LookupError, match="home.vectors"):
        kernel.atoms_for_candidates((candidate,))


def test_memory_kernel_query_forwards_shadow_flags(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import dharma_swarm.memory_retrieval as memory_retrieval_module
    from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig

    captured: dict[str, object] = {}

    class _CaptureEngine:
        def __init__(self, *, state_dir, memory_kernel):
            captured["state_dir"] = state_dir

        def retrieve(self, query):
            captured["query"] = query
            return SimpleNamespace(candidates=())

    monkeypatch.setattr(
        memory_retrieval_module, "GovernedRetrievalEngine", _CaptureEngine
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=tmp_path / "repo",
                home=tmp_path / "home",
                include_discovered=False,
            )
        )
    )

    kernel.query(
        "governed memory",
        top_k=6,
        enable_memory_kernel=False,
        record_telemetry=False,
    )

    query = captured["query"]
    assert query.text == "governed memory"
    assert query.top_k == 6
    assert query.enable_memory_kernel is False
    assert query.record_telemetry is False
