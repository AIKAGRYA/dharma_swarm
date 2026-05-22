"""Tests for chetana.ingest + chetana.promote — the staged → trusted path."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import promote
from dharma_swarm.chetana.provenance import parse_frontmatter


def test_ingest_simple_note_creates_staged_atom(chetana_sandbox: Path):
    result = ingest(
        source="this is a research note about strange loops",
        source_kind="note",
        title="Strange Loops Note",
        confidence=0.6,
        captured_by="test_ingest",
    )
    assert result.staged_count == 1
    atom_path = result.atoms[0]
    assert atom_path.exists()
    parsed, body = parse_frontmatter(atom_path.read_text(encoding="utf-8"))
    assert parsed is not None
    assert parsed.title == "Strange Loops Note"
    assert parsed.provenance is None  # staged atoms have NO provenance
    assert "strange loops" in body
    log_text = (chetana_sandbox / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "ingest | Strange Loops Note" in log_text


def test_ingest_session_jsonl_creates_atom_per_substantive_turn(
    chetana_sandbox: Path, tmp_path: Path
):
    jsonl = tmp_path / "session.jsonl"
    jsonl.write_text(
        '\n'.join(
            [
                '{"type":"user","content":"explain self-reference"}',
                '{"type":"assistant","content":"' + ("Self-reference is when " * 10) + '"}',
                '{"type":"user","content":"more"}',
                '{"type":"assistant","content":"yes"}',  # too short, should skip
                '{"type":"user","content":"more"}',
                '{"type":"assistant","content":"' + ("Hofstadter calls these strange loops " * 6) + '"}',
            ]
        )
    )
    result = ingest(
        source=jsonl, source_kind="session", title="Session test", captured_by="test"
    )
    assert result.staged_count == 2  # the third short turn was skipped
    for atom in result.atoms:
        assert atom.exists()


def test_ingest_webclip_uses_existing_extractor(chetana_sandbox: Path, tmp_path: Path):
    clip = tmp_path / "clip.md"
    clip.write_text(
        "---\n"
        "title: Clipped Source Title\n"
        "url: https://example.test/source\n"
        "tags: [clip, source]\n"
        "---\n"
        "Clipped body only.\n",
        encoding="utf-8",
    )

    result = ingest(
        source=clip,
        source_kind="webclip",
        title="fallback title",
        confidence=0.6,
        tags=["manual"],
    )
    parsed, body = parse_frontmatter(result.atoms[0].read_text(encoding="utf-8"))
    assert parsed.title == "Clipped Source Title"
    assert parsed.source[0].path == "https://example.test/source"
    assert parsed.tags == ["manual", "clip", "source"]
    assert body == "Clipped body only.\n"


def test_promote_writes_trusted_atom_with_provenance(chetana_sandbox: Path):
    ingested = ingest(
        source="atom body for promotion",
        source_kind="note",
        title="Promotion test",
        confidence=0.8,
    )
    staged = ingested.atoms[0]

    pr = promote(staged_path=staged, promoted_by="tester")
    assert pr.decision in {"ALLOW", "WARN"}  # not BLOCK
    assert pr.trusted_path is not None and pr.trusted_path.exists()

    parsed, body = parse_frontmatter(pr.trusted_path.read_text(encoding="utf-8"))
    assert parsed is not None
    assert parsed.provenance is not None
    assert parsed.provenance.gate_check.result == pr.decision
    assert len(parsed.provenance.axiom_signature) == 64
    assert "atom body for promotion" in body
    log_text = (chetana_sandbox / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "promote | Promotion test" in log_text

    # Staged file should be removed after successful promote
    assert not staged.exists()


def test_promote_runs_cross_update_index_backlinks_and_contradiction_ledger(
    chetana_sandbox: Path,
):
    related = ingest(
        source="Bridge hypothesis background",
        source_kind="note",
        title="Bridge Hypothesis",
        confidence=0.8,
    )
    related_promoted = promote(staged_path=related.atoms[0], promoted_by="tester")

    main = ingest(
        source="This contradicts older synthesis and relates to the bridge hypothesis.",
        source_kind="note",
        title="Main Cross Update",
        confidence=0.8,
        related=["Bridge Hypothesis"],
    )
    promoted = promote(staged_path=main.atoms[0], promoted_by="tester")

    index_text = (chetana_sandbox / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "Main Cross Update" in index_text
    assert str(promoted.trusted_path.name).removesuffix(".md") in index_text

    related_text = related_promoted.trusted_path.read_text(encoding="utf-8")
    assert "## Backlinks" in related_text
    assert "Main Cross Update" in related_text

    contradictions = (chetana_sandbox / "wiki" / "contradictions.md").read_text(
        encoding="utf-8"
    )
    assert "Main Cross Update" in contradictions


def test_double_promote_raises(chetana_sandbox: Path):
    ingested = ingest(source="x", source_kind="note", title="t", confidence=0.5)
    staged = ingested.atoms[0]
    promote(staged_path=staged, promoted_by="t")
    with pytest.raises(FileNotFoundError):
        promote(staged_path=staged, promoted_by="t")  # already moved/deleted


def test_promote_refuses_path_outside_staging_root(chetana_sandbox: Path):
    ingested = ingest(
        source="valid staged body", source_kind="note", title="outside copy", confidence=0.5
    )
    outside = chetana_sandbox / "outside.md"
    outside.write_text(ingested.atoms[0].read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="outside chetana staging root"):
        promote(staged_path=outside, promoted_by="test")
