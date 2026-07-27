from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.chetana import manifest as manifest_mod
from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts
from scripts.wiki_vector_live_gate import run_gate

_KERNEL_SIG = "e" * 64


@pytest.fixture(autouse=True)
def _fixed_kernel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(manifest_mod, "_resolve_kernel_signature", lambda: _KERNEL_SIG)
    manifest_mod.clear_manifest_cache()
    yield
    manifest_mod.clear_manifest_cache()


def _sign_manifest_for(wiki_root: Path) -> None:
    # PR-08: ingest/gate refuse files outside the signed trust manifest
    entries = [
        manifest_mod.manifest_entry_for_file(p, root=wiki_root, tier="gold")
        for p in sorted((wiki_root / "concepts").glob("*.md"))
    ]
    manifest_mod.write_manifest(entries, manifest_file=wiki_root / "MANIFEST.jsonl")


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
    _sign_manifest_for(tmp_path / "wiki")

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
    _sign_manifest_for(tmp_path / "wiki")
    ingest_wiki_concepts(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        max_files=10,
    )
    # post-ingest drift: membership keeps the file gate-visible so the gate's
    # digest comparison reports it stale (manifest content check lives at ingest)
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
