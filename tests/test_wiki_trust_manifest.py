"""PR-08: signed wiki trust manifest gates every READ seam (audit WS-D.1/2).

Contract under test:
  - manifest module: signature verify, fail-closed on missing / unsigned /
    tampered / malformed / duplicate rows / placeholder kernel
  - tier gate: only {gold, trusted} admitted; contested tiers excluded (D-3)
  - content binding: sha256 drift since signing un-trusts a file
  - seam 1: scripts/wiki_vector_live_gate._concept_files
  - seam 2: dharma_swarm/wiki_vector_ingest.ingest_wiki_concepts
  - seam 3: memory_kernel KnowledgeWikiAdapter (filter BEFORE max_files cut)
  - seam 4: chetana/staging.list_trusted
A file absent from the manifest must never be admitted through any seam.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.chetana import manifest as manifest_mod
from dharma_swarm.chetana.manifest import (
    load_manifest,
    manifest_entry_for_file,
    signature_path_for,
    write_manifest,
)

FAKE_KERNEL_SIG = "f" * 64


@pytest.fixture(autouse=True)
def _fixed_kernel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(manifest_mod, "_resolve_kernel_signature", lambda: FAKE_KERNEL_SIG)
    manifest_mod.clear_manifest_cache()
    yield
    manifest_mod.clear_manifest_cache()


def _write_page(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _wiki_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """wiki root with one gold concept, one untrusted scratch file."""
    wiki_root = tmp_path / "wiki"
    concepts = wiki_root / "concepts"
    gold = _write_page(
        concepts / "orchestrator.md",
        "---\ntitle: Orchestrator\n---\nOrchestrator async task routing engine.\n",
    )
    scratch = _write_page(
        concepts / "aaa-scratch-note.md",
        "---\ntitle: Scratch\n---\nUnadjudicated scratch content.\n",
    )
    write_manifest(
        [manifest_entry_for_file(gold, root=wiki_root, tier="gold")],
        manifest_file=wiki_root / "MANIFEST.jsonl",
    )
    return wiki_root, concepts, gold, scratch


# ---------------------------------------------------------------------------
# manifest module
# ---------------------------------------------------------------------------


def test_load_verify_roundtrip_and_tier_gate(tmp_path: Path):
    wiki_root, _, gold, scratch = _wiki_fixture(tmp_path)
    contested = _write_page(wiki_root / "concepts" / "contested.md", "needs review\n")
    entries = [
        manifest_entry_for_file(gold, root=wiki_root, tier="gold"),
        manifest_entry_for_file(contested, root=wiki_root, tier="needs_review"),
    ]
    write_manifest(entries, manifest_file=wiki_root / "MANIFEST.jsonl")

    manifest = load_manifest(wiki_root / "concepts")
    assert manifest.valid
    assert manifest.is_trusted(gold)
    assert not manifest.is_trusted(contested), "contested tier must stay excluded (D-3)"
    assert not manifest.is_trusted(scratch), "unlisted file must never be trusted"
    assert manifest.trusted_relpaths() == ("concepts/orchestrator.md",)


def test_missing_manifest_fails_closed(tmp_path: Path):
    root = tmp_path / "wiki" / "concepts"
    root.mkdir(parents=True)
    page = _write_page(root / "page.md", "content\n")
    manifest = load_manifest(root)
    assert not manifest.valid
    assert manifest.warning == "manifest-or-signature-missing"
    assert not manifest.is_trusted(page)


def test_missing_signature_fails_closed(tmp_path: Path):
    wiki_root, concepts, gold, _ = _wiki_fixture(tmp_path)
    signature_path_for(wiki_root / "MANIFEST.jsonl").unlink()
    manifest_mod.clear_manifest_cache()
    assert not load_manifest(concepts).is_trusted(gold)


def test_tampered_manifest_fails_closed(tmp_path: Path):
    wiki_root, concepts, gold, scratch = _wiki_fixture(tmp_path)
    manifest_file = wiki_root / "MANIFEST.jsonl"
    forged = manifest_entry_for_file(scratch, root=wiki_root, tier="gold")
    with manifest_file.open("a", encoding="utf-8") as handle:
        handle.write(
            '{"path": "%s", "sha256": "%s", "tier": "gold", "reasons": []}\n'
            % (forged.path, forged.sha256)
        )
    manifest_mod.clear_manifest_cache()
    manifest = load_manifest(concepts)
    assert not manifest.valid
    assert manifest.warning == "signature-mismatch"
    assert not manifest.is_trusted(gold)
    assert not manifest.is_trusted(scratch)


def test_placeholder_kernel_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wiki_root, concepts, gold, _ = _wiki_fixture(tmp_path)
    monkeypatch.setattr(manifest_mod, "_resolve_kernel_signature", lambda: "0" * 64)
    manifest_mod.clear_manifest_cache()
    manifest = load_manifest(concepts)
    assert not manifest.valid
    assert manifest.warning == "kernel-unavailable"
    assert not manifest.is_trusted(gold)


def test_content_drift_untrusts_file(tmp_path: Path):
    _, concepts, gold, _ = _wiki_fixture(tmp_path)
    assert load_manifest(concepts).is_trusted(gold)
    gold.write_text("mutated after signing\n", encoding="utf-8")
    assert not load_manifest(concepts).is_trusted(gold)
    assert load_manifest(concepts).is_trusted(gold, verify_content=False)


def test_malformed_and_duplicate_rows_fail_closed(tmp_path: Path):
    wiki_root = tmp_path / "wiki"
    gold = _write_page(wiki_root / "concepts" / "a.md", "a\n")
    entry = manifest_entry_for_file(gold, root=wiki_root, tier="gold")
    manifest_file = wiki_root / "MANIFEST.jsonl"
    write_manifest([entry], manifest_file=manifest_file)

    # duplicate rows, re-signed so only the row check can reject
    text = manifest_file.read_text(encoding="utf-8")
    manifest_file.write_text(text + text, encoding="utf-8")
    manifest_mod.sign_manifest(manifest_file, kernel_signature=FAKE_KERNEL_SIG)
    manifest = load_manifest(wiki_root / "concepts")
    assert not manifest.valid and manifest.warning.startswith("duplicate-entry")

    # malformed row, re-signed
    manifest_file.write_text("not-json\n", encoding="utf-8")
    manifest_mod.sign_manifest(manifest_file, kernel_signature=FAKE_KERNEL_SIG)
    manifest = load_manifest(wiki_root / "concepts")
    assert not manifest.valid and manifest.warning.startswith("malformed-row")


def test_env_override_selects_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wiki_root, concepts, gold, scratch = _wiki_fixture(tmp_path)
    alt = tmp_path / "alt" / "MANIFEST.jsonl"
    monkeypatch.setenv(manifest_mod.MANIFEST_ENV, str(alt))
    manifest_mod.clear_manifest_cache()
    assert not load_manifest(concepts).valid, "env-pointed manifest missing → fail closed"
    # env manifest root is its parent dir, so entries resolve against alt/
    alt_gold = _write_page(tmp_path / "alt" / "concepts" / "g.md", "alt gold\n")
    write_manifest(
        [manifest_entry_for_file(alt_gold, root=tmp_path / "alt", tier="trusted")],
        manifest_file=alt,
    )
    manifest = load_manifest(concepts)
    assert manifest.valid
    assert manifest.is_trusted(alt_gold)
    assert not manifest.is_trusted(gold), "paths outside the manifest root are untrusted"
    assert not manifest.is_trusted(scratch)


def test_write_manifest_refuses_placeholder_kernel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(manifest_mod, "_resolve_kernel_signature", lambda: "0" * 64)
    with pytest.raises(ValueError):
        write_manifest([], manifest_file=tmp_path / "MANIFEST.jsonl")


# ---------------------------------------------------------------------------
# seam 1: wiki_vector_live_gate._concept_files
# ---------------------------------------------------------------------------


def test_gate_concept_files_exclude_non_manifest(tmp_path: Path):
    from scripts.wiki_vector_live_gate import _concept_files

    _, concepts, gold, scratch = _wiki_fixture(tmp_path)
    files = _concept_files(concepts)
    assert gold.resolve() in files
    assert scratch.resolve() not in files


def test_gate_concept_files_empty_without_manifest(tmp_path: Path):
    from scripts.wiki_vector_live_gate import _concept_files

    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    _write_page(concepts / "page.md", "content\n")
    assert _concept_files(concepts) == ()


# ---------------------------------------------------------------------------
# seam 2: wiki_vector_ingest
# ---------------------------------------------------------------------------


def test_ingest_excludes_non_manifest_files(tmp_path: Path):
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

    _, concepts, gold, scratch = _wiki_fixture(tmp_path)
    receipt = ingest_wiki_concepts(
        state_dir=tmp_path / "state",
        wiki_concepts_dir=concepts,
        max_files=10,
    )
    assert receipt.discovered_files == 1
    assert receipt.manifest_excluded_files == 1
    ingested = {Path(p).name for p in receipt.backfill["text_file_paths"]}
    assert ingested == {gold.name}
    assert scratch.name not in ingested


def test_ingest_empty_without_manifest(tmp_path: Path):
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    _write_page(concepts / "page.md", "content\n")
    receipt = ingest_wiki_concepts(
        state_dir=tmp_path / "state",
        wiki_concepts_dir=concepts,
        max_files=10,
    )
    assert receipt.discovered_files == 0
    assert receipt.manifest_excluded_files == 1


# ---------------------------------------------------------------------------
# seam 3: KnowledgeWikiAdapter (filter before max_files truncation)
# ---------------------------------------------------------------------------


def _wiki_kernel_atoms(home: Path, repo: Path, max_files: int = 100):
    from dharma_swarm.memory_kernel import (
        CensusConfig,
        MemoryKernel,
        MemoryKernelConfig,
    )
    from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig

    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=50, max_files=max_files),
        )
    )
    return list(
        kernel.iter_memory_atoms(surface_ids=("home.knowledge_wiki",), limit_per_surface=50)
    )


def test_adapter_excludes_non_manifest_files(tmp_path: Path):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    wiki_root = home / ".dharma" / "knowledge" / "wiki"
    gold = _write_page(wiki_root / "concepts" / "zzz-gold.md", "# Gold\n\nCurated note.\n")
    _write_page(wiki_root / "aaa-scratch.md", "# Scratch\n\nRaw session dump.\n")
    write_manifest(
        [manifest_entry_for_file(gold, root=wiki_root, tier="gold")],
        manifest_file=wiki_root / "MANIFEST.jsonl",
    )
    atoms = _wiki_kernel_atoms(home, repo, max_files=1)
    refs = {atom.content_ref for atom in atoms}
    # scratch is alphabetically first: without pre-truncation filtering,
    # max_files=1 would admit it and evict the gold page
    assert refs == {gold.as_posix()}


def test_adapter_yields_nothing_without_manifest(tmp_path: Path):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    wiki_root = home / ".dharma" / "knowledge" / "wiki"
    _write_page(wiki_root / "concepts" / "page.md", "# Page\n\nContent.\n")
    assert _wiki_kernel_atoms(home, repo) == []


# ---------------------------------------------------------------------------
# seam 4: chetana staging.list_trusted
# ---------------------------------------------------------------------------


def test_list_trusted_excludes_non_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from dharma_swarm.chetana import staging as staging_mod

    wiki_root, concepts, gold, scratch = _wiki_fixture(tmp_path)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", concepts, raising=True)

    trusted = staging_mod.list_trusted()
    assert trusted == [gold]
    raw = staging_mod.list_trusted(apply_manifest=False)
    assert scratch in raw and gold in raw


def test_list_trusted_empty_without_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from dharma_swarm.chetana import staging as staging_mod

    wiki_root = tmp_path / "wiki"
    concepts = wiki_root / "concepts"
    page = _write_page(concepts / "page.md", "content\n")
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", concepts, raising=True)

    assert staging_mod.list_trusted() == []
    assert staging_mod.list_trusted(apply_manifest=False) == [page]


# ---------------------------------------------------------------------------
# adversarial-review fixes (2026-07-26)
# ---------------------------------------------------------------------------


def test_single_file_root_resolves_wiki_manifest(tmp_path: Path):
    # promote._auto_ingest_file passes the approved FILE as the root; the
    # resolver must climb from <wiki>/concepts/<file> to <wiki>/MANIFEST.jsonl
    _, _, gold, scratch = _wiki_fixture(tmp_path)
    manifest = load_manifest(gold)
    assert manifest.valid
    assert manifest.is_trusted(gold)
    assert not load_manifest(scratch).is_trusted(scratch)


def test_promote_seam_single_file_ingest(tmp_path: Path):
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

    _, _, gold, scratch = _wiki_fixture(tmp_path)
    receipt = ingest_wiki_concepts(state_dir=tmp_path / "state", wiki_concepts_dir=gold)
    assert receipt.discovered_files == 1
    ingested = {Path(p).name for p in receipt.backfill["text_file_paths"]}
    assert ingested == {gold.name}
    # unmanifested single file still refuses
    refuse = ingest_wiki_concepts(state_dir=tmp_path / "state2", wiki_concepts_dir=scratch)
    assert refuse.discovered_files == 0


def test_op3_signature_artifact_format_accepted(tmp_path: Path):
    # the already-produced OP-3 deliverable ships MANIFEST.sig.json with the
    # signature under "axiom_signature" — must be deployable without re-signing
    import json as json_mod

    wiki_root, concepts, gold, _ = _wiki_fixture(tmp_path)
    manifest_file = wiki_root / "MANIFEST.jsonl"
    canonical_sig = signature_path_for(manifest_file)
    payload = json_mod.loads(canonical_sig.read_text(encoding="utf-8"))
    canonical_sig.unlink()
    (wiki_root / "MANIFEST.sig.json").write_text(
        json_mod.dumps(
            {
                "artifact": "MANIFEST.jsonl",
                "axiom_signature": payload["signature"],
                "kernel_signature": FAKE_KERNEL_SIG,
            }
        ),
        encoding="utf-8",
    )
    manifest_mod.clear_manifest_cache()
    manifest = load_manifest(concepts)
    assert manifest.valid
    assert manifest.is_trusted(gold)


def test_env_override_outside_tree_warns_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    import logging
    import shutil

    wiki_root, concepts, gold, _ = _wiki_fixture(tmp_path)
    git_copy = tmp_path / "gitcopy" / "MANIFEST.jsonl"
    git_copy.parent.mkdir(parents=True)
    shutil.copy(wiki_root / "MANIFEST.jsonl", git_copy)
    shutil.copy(signature_path_for(wiki_root / "MANIFEST.jsonl"), signature_path_for(git_copy))
    monkeypatch.setenv(manifest_mod.MANIFEST_ENV, str(git_copy))
    manifest_mod.clear_manifest_cache()
    with caplog.at_level(logging.WARNING, logger="dharma_swarm.chetana.manifest"):
        manifest = load_manifest(concepts)
        again = load_manifest(concepts)
    assert manifest.valid and again.valid
    assert not manifest.is_trusted(gold), "fail-closed direction unchanged"
    hits = [r for r in caplog.records if "does not govern" in r.getMessage()]
    assert len(hits) == 1, "must warn exactly once (diagnosable, not noisy)"


def test_ingest_filter_runs_before_max_files_cut(tmp_path: Path):
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

    wiki_root = tmp_path / "wiki"
    concepts = wiki_root / "concepts"
    gold = _write_page(concepts / "zzz-gold.md", "curated content that matters\n")
    for i in range(5):
        _write_page(concepts / f"aa{i}.md", "scratch\n")
    write_manifest(
        [manifest_entry_for_file(gold, root=wiki_root, tier="gold")],
        manifest_file=wiki_root / "MANIFEST.jsonl",
    )
    # without pre-truncation filtering, max_files=1 admits an alphabetically
    # earlier scratch file and evicts the gold page from the discover window
    receipt = ingest_wiki_concepts(
        state_dir=tmp_path / "state", wiki_concepts_dir=concepts, max_files=1
    )
    assert receipt.discovered_files == 1
    ingested = {Path(p).name for p in receipt.backfill["text_file_paths"]}
    assert ingested == {gold.name}
    assert receipt.manifest_excluded_files == 5


def test_gate_default_min_concepts_satisfiable():
    from scripts.wiki_vector_live_gate import DEFAULT_MIN_CONCEPTS

    # 2026-07-25 signed manifest: 204 gold+trusted top-level concepts/*.md
    # rows, all on disk. A default above that is arithmetically unsatisfiable
    # and the gate would be permanently red.
    assert DEFAULT_MIN_CONCEPTS <= 204
