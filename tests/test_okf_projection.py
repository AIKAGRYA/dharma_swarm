"""Tests for the Slice B OKF projector (export / import / project ontology)."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.fs_substrate.okf import (
    OKFConcept,
    project_semantic_objects,
    read_bundle,
    write_bundle,
)

SEMANTIC_OBJECTS = (
    Path(__file__).resolve().parents[1] / "docs" / "ontology" / "semantic_objects.yaml"
)


def _sample() -> list[OKFConcept]:
    return [
        OKFConcept(rel_path="objects/Alpha.md", type="runtime_object",
                   title="Alpha", description="the first", links=["objects/Beta.md"]),
        OKFConcept(rel_path="objects/Beta.md", type="identifier", title="Beta",
                   description="the second"),
    ]


def test_write_bundle_emits_required_type_and_reserved_files(tmp_path):
    root = write_bundle(_sample(), tmp_path / "bundle", today="2026-06-24")
    alpha = (root / "objects" / "Alpha.md").read_text()
    # The one required OKF field, first in frontmatter.
    assert alpha.startswith("---\ntype: runtime_object")
    # Reserved filenames exist.
    assert (root / "index.md").is_file()
    assert (root / "log.md").is_file()
    # index lists concepts with relative links; declares the version.
    index = (root / "index.md").read_text()
    assert 'okf_version: "0.1"' in index
    assert "(objects/Alpha.md)" in index
    # log carries the injected date (module never calls the clock itself).
    assert "## 2026-06-24" in (root / "log.md").read_text()


def test_write_bundle_rejects_escaping_or_absolute_paths(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        write_bundle([OKFConcept(rel_path="../escape.md", type="x")], tmp_path / "b")
    with pytest.raises(ValueError):
        write_bundle([OKFConcept(rel_path="/etc/passwd", type="x")], tmp_path / "b2")


def test_reexport_removes_stale_concepts(tmp_path):
    root = tmp_path / "bundle"
    write_bundle(_sample(), root, today="2026-06-24")  # Alpha + Beta
    assert (root / "objects" / "Alpha.md").is_file()
    # Re-export with Beta renamed away -> Alpha must not be resurrected.
    write_bundle(
        [OKFConcept(rel_path="objects/Beta.md", type="identifier", title="Beta")],
        root, today="2026-06-25",
    )
    assert not (root / "objects" / "Alpha.md").exists()
    assert {c.rel_path for c in read_bundle(root)} == {"objects/Beta.md"}


def test_roundtrip_preserves_identity_and_type(tmp_path):
    root = write_bundle(_sample(), tmp_path / "bundle", today="2026-06-24")
    back = {c.rel_path: c for c in read_bundle(root)}
    assert set(back) == {"objects/Alpha.md", "objects/Beta.md"}
    assert back["objects/Alpha.md"].type == "runtime_object"
    assert back["objects/Beta.md"].type == "identifier"
    # The path IS the identifier; the cross-link survives the round trip.
    assert "objects/Beta.md" in back["objects/Alpha.md"].links


def test_consumer_tolerates_unknown_type_and_broken_links(tmp_path):
    root = tmp_path / "foreign"
    root.mkdir()
    (root / "weird.md").write_text(
        "---\ntype: SomeVendorType\n---\n# Weird\nsee [x](objects/does-not-exist.md)\n"
    )
    # Must not raise on unknown type or broken link (OKF tolerant-consumer rule).
    concepts = read_bundle(root)
    assert len(concepts) == 1
    assert concepts[0].type == "SomeVendorType"
    assert "objects/does-not-exist.md" in concepts[0].links


def test_missing_type_defaults_not_fatal(tmp_path):
    root = tmp_path / "b"
    root.mkdir()
    (root / "c.md").write_text("---\ntitle: No Type Here\n---\nbody\n")
    concepts = read_bundle(root)
    assert concepts and concepts[0].type == "unknown"


def test_project_semantic_objects_uses_kind_as_type():
    if not SEMANTIC_OBJECTS.is_file():
        return  # manifest is the owner; skip cleanly if absent on this branch
    concepts = project_semantic_objects(SEMANTIC_OBJECTS)
    assert concepts, "expected at least one projected concept"
    by_title = {c.title: c for c in concepts}
    # A2ACard is a runtime_object in the manifest -> that is its OKF type.
    if "A2ACard" in by_title:
        assert by_title["A2ACard"].type == "runtime_object"
        assert by_title["A2ACard"].rel_path == "objects/A2ACard.md"


def test_project_then_write_then_read_full_cycle(tmp_path):
    if not SEMANTIC_OBJECTS.is_file():
        return
    concepts = project_semantic_objects(SEMANTIC_OBJECTS)
    root = write_bundle(concepts, tmp_path / "commons", title="Semantic Commons",
                        today="2026-06-24")
    back = read_bundle(root)
    assert {c.rel_path for c in back} == {c.rel_path for c in concepts}
