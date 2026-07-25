from __future__ import annotations

import sys
import types

import dharma_swarm.chetana
from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts
from scripts.wiki_vector_live_gate import run_gate


def _install_manifest_stub(monkeypatch, entries) -> None:
    stub = types.SimpleNamespace(load_verified_manifest=lambda path: entries)
    monkeypatch.setitem(sys.modules, "dharma_swarm.chetana.manifest", stub)
    monkeypatch.setattr(dharma_swarm.chetana, "manifest", stub, raising=False)


def _write_concepts(tmp_path):
    wiki_dir = tmp_path / "wiki" / "concepts"
    wiki_dir.mkdir(parents=True)
    concept = wiki_dir / "orchestrator.md"
    concept.write_text(
        "---\n"
        "title: Orchestrator\n"
        "---\n"
        "Orchestrator async task routing engine with live wiki content.\n",
        encoding="utf-8",
    )
    return wiki_dir, concept


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


def test_wiki_vector_live_gate_provenance_degrades_to_warning_without_module(tmp_path):
    wiki_dir, _concept = _write_concepts(tmp_path)
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(state_dir=state_dir, wiki_concepts_dir=wiki_dir, max_files=10)

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    # dharma_swarm/chetana/manifest.py does not exist pre-PR-08
    assert receipt.provenance_status == "unavailable"
    assert receipt.provenance_score == 10.0
    assert "pre-PR-08" in receipt.provenance_warning
    assert receipt.passed
    assert receipt.score == 100.0


def test_wiki_vector_live_gate_provenance_subset_passes(monkeypatch, tmp_path):
    wiki_dir, concept = _write_concepts(tmp_path)
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(state_dir=state_dir, wiki_concepts_dir=wiki_dir, max_files=10)
    _install_manifest_stub(
        monkeypatch, [{"path": str(concept.resolve()), "tier": "gold"}]
    )

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert receipt.provenance_status == "ok"
    assert receipt.provenance_violations == ()
    assert receipt.indexed_wiki_file_count == 1
    assert receipt.passed
    assert receipt.score == 100.0


def test_wiki_vector_live_gate_provenance_fails_on_unaccepted_tier(monkeypatch, tmp_path):
    wiki_dir, concept = _write_concepts(tmp_path)
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(state_dir=state_dir, wiki_concepts_dir=wiki_dir, max_files=10)
    _install_manifest_stub(
        monkeypatch, [{"path": str(concept.resolve()), "tier": "quarantine"}]
    )

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert receipt.provenance_status == "violations"
    assert str(concept.resolve()) in receipt.provenance_violations
    assert receipt.provenance_score == 0.0
    assert not receipt.passed


def test_wiki_vector_live_gate_provenance_rejects_basename_collision(monkeypatch, tmp_path):
    wiki_dir, concept = _write_concepts(tmp_path)
    rogue_dir = wiki_dir / "evil"
    rogue_dir.mkdir()
    rogue = rogue_dir / "orchestrator.md"
    rogue.write_text(
        "---\n"
        "title: Orchestrator\n"
        "---\n"
        "Poisoned twin sharing the accepted basename.\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(state_dir=state_dir, wiki_concepts_dir=wiki_dir, max_files=10)
    # Manifest blesses only the real concept; the rogue file shares its
    # basename but lives in another directory and must NOT pass.
    _install_manifest_stub(
        monkeypatch, [{"path": str(concept.resolve()), "tier": "gold"}]
    )

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert receipt.provenance_status == "violations"
    assert str(rogue.resolve()) in receipt.provenance_violations
    assert str(concept.resolve()) not in receipt.provenance_violations
    assert not receipt.passed


def test_wiki_vector_live_gate_provenance_fails_closed_on_unrecognized_loader(
    monkeypatch, tmp_path
):
    wiki_dir, _concept = _write_concepts(tmp_path)
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(state_dir=state_dir, wiki_concepts_dir=wiki_dir, max_files=10)
    # Module landed but under an unexpected loader name: must go red, not
    # silently keep the full-score "unavailable" warning.
    stub = types.SimpleNamespace(verify_manifest=lambda path: [])
    monkeypatch.setitem(sys.modules, "dharma_swarm.chetana.manifest", stub)
    monkeypatch.setattr(dharma_swarm.chetana, "manifest", stub, raising=False)

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert receipt.provenance_status == "error"
    assert "fail-closed" in receipt.provenance_warning
    assert receipt.provenance_score == 0.0
    assert not receipt.passed


def test_wiki_vector_live_gate_provenance_fails_closed_on_loader_error(monkeypatch, tmp_path):
    wiki_dir, _concept = _write_concepts(tmp_path)
    state_dir = tmp_path / "state"
    ingest_wiki_concepts(state_dir=state_dir, wiki_concepts_dir=wiki_dir, max_files=10)

    def _boom(path):
        raise ValueError("signature verification failed")

    stub = types.SimpleNamespace(load_verified_manifest=_boom)
    monkeypatch.setitem(sys.modules, "dharma_swarm.chetana.manifest", stub)
    monkeypatch.setattr(dharma_swarm.chetana, "manifest", stub, raising=False)

    receipt = run_gate(
        state_dir=state_dir,
        wiki_concepts_dir=wiki_dir,
        min_concepts=1,
        top_k=5,
        max_p95_ms=5000.0,
    )

    assert receipt.provenance_status == "error"
    assert "fail-closed" in receipt.provenance_warning
    assert not receipt.passed
