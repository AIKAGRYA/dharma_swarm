from __future__ import annotations

from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts
from scripts.wiki_vector_live_gate import run_gate


def test_wiki_vector_live_gate_verifies_current_concept_digest(tmp_path):
    wiki_dir = tmp_path / "wiki" / "concepts"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "orchestrator.md").write_text(
        "---\n"
        "title: Orchestrator\n"
        "---\n"
        "Orchestrator async task routing engine with live wiki content.\n",
        encoding="utf-8",
    )
    (wiki_dir / "jagat-kalyan.md").write_text(
        "---\n"
        "title: Jagat Kalyan\n"
        "---\n"
        "Jagat Kalyan universal welfare north star telos.\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"

    ingest_wiki_concepts(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        max_files=10,
    )
    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=2,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert receipt.passed
    assert receipt.score == 100.0
    assert receipt.indexed_current_count == 2
    assert receipt.retrieval_passed == 2


def test_wiki_vector_live_gate_fails_on_stale_concept_digest(tmp_path):
    wiki_dir = tmp_path / "wiki" / "concepts"
    wiki_dir.mkdir(parents=True)
    concept = wiki_dir / "orchestrator.md"
    concept.write_text(
        "---\n"
        "title: Orchestrator\n"
        "---\n"
        "Orchestrator async task routing engine.\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        max_files=10,
    )
    concept.write_text(
        "---\n"
        "title: Orchestrator\n"
        "---\n"
        "Orchestrator async task routing engine enriched after ingestion.\n",
        encoding="utf-8",
    )

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert not receipt.passed
    assert receipt.indexed_current_count == 0
    assert str(concept.resolve()) in receipt.missing_or_stale
