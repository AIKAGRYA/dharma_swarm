"""Tests for chetana.ingest + chetana.promote — the staged → trusted path."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.chetana import cross_update as cross_update_module
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.cross_update import _upsert_index_entry, cross_update_trusted
from dharma_swarm.chetana.governance import current_kernel_signature
from dharma_swarm.chetana.promote import approve_atom, promote
from dharma_swarm.chetana.provenance import parse_frontmatter, signature_matches


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
        "\n".join(
            [
                '{"type":"user","content":"explain self-reference"}',
                '{"type":"assistant","content":"'
                + ("Self-reference is when " * 10)
                + '"}',
                '{"type":"user","content":"more"}',
                '{"type":"assistant","content":"yes"}',  # too short, should skip
                '{"type":"user","content":"more"}',
                '{"type":"assistant","content":"'
                + ("Hofstadter calls these strange loops " * 6)
                + '"}',
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


def test_promote_writes_pending_atom_with_provenance(chetana_sandbox: Path):
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
    # Non-approved atoms land in pending, NEVER in the trusted projection.
    assert pr.trusted_path.parent == chetana_sandbox / "wiki" / "pending"
    assert list((chetana_sandbox / "wiki" / "concepts").glob("*.md")) == []

    parsed, body = parse_frontmatter(pr.trusted_path.read_text(encoding="utf-8"))
    assert parsed is not None
    assert parsed.provenance is not None
    assert parsed.provenance.gate_check.result == pr.decision
    assert parsed.provenance.review_status in {"staged", "auto_promoted"}
    assert parsed.provenance.axiom_signature.startswith("v2:")
    assert "atom body for promotion" in body
    log_text = (chetana_sandbox / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "promote | Promotion test" in log_text

    # Staged file should be removed after successful promote
    assert not staged.exists()


def test_approve_moves_pending_atom_into_trusted_and_runs_cross_update(
    chetana_sandbox: Path,
):
    related = ingest(
        source="Bridge hypothesis background",
        source_kind="note",
        title="Bridge Hypothesis",
        confidence=0.8,
    )
    related_promoted = promote(staged_path=related.atoms[0], promoted_by="tester")
    related_approved = approve_atom(
        path=related_promoted.trusted_path, reviewer="tester"
    )
    assert related_approved.decision == "APPROVED"

    main = ingest(
        source="This contradicts older synthesis and relates to the bridge hypothesis.",
        source_kind="note",
        title="Main Cross Update",
        confidence=0.8,
        related=["Bridge Hypothesis"],
    )
    promoted = promote(staged_path=main.atoms[0], promoted_by="tester")
    # Pending: nothing in the trusted projection yet, no index entry.
    index_path = chetana_sandbox / "wiki" / "index.md"
    if index_path.exists():
        assert "Main Cross Update" not in index_path.read_text(encoding="utf-8")
    approved = approve_atom(path=promoted.trusted_path, reviewer="tester")
    assert approved.decision == "APPROVED"
    assert approved.trusted_path.parent == chetana_sandbox / "wiki" / "concepts"
    assert not promoted.trusted_path.exists()  # pending copy removed

    assert index_path.exists(), approved.notes
    index_text = index_path.read_text(encoding="utf-8")
    assert "Main Cross Update" in index_text
    assert str(approved.trusted_path.name).removesuffix(".md") in index_text

    related_text = related_approved.trusted_path.read_text(encoding="utf-8")
    assert "## Backlinks" in related_text
    assert "[[main-cross-update]]" in related_text
    for trusted_path in (related_approved.trusted_path, approved.trusted_path):
        trusted_schema, trusted_body = parse_frontmatter(
            trusted_path.read_text(encoding="utf-8"), source_path=str(trusted_path)
        )
        assert trusted_schema is not None and trusted_schema.provenance is not None
        assert signature_matches(
            trusted_schema.provenance.axiom_signature,
            trusted_schema,
            trusted_body,
            current_kernel_signature(),
        )

    # A keyword is not evidence. Cross-update must not manufacture a
    # contradiction fact without a typed claim ID and authoritative source.
    assert not (chetana_sandbox / "wiki" / "contradictions.md").exists()


def test_approval_refuses_manifest_governed_partial_publish(
    chetana_sandbox: Path,
) -> None:
    pending = promote(
        staged_path=ingest(
            source="manifest-governed approval",
            source_kind="note",
            title="Manifest Governed",
            confidence=0.8,
        ).atoms[0],
        promoted_by="tester",
    ).trusted_path
    assert pending is not None
    original = pending.read_text(encoding="utf-8")
    wiki = chetana_sandbox / "wiki"
    (wiki / "MANIFEST.jsonl").write_text("{}\n", encoding="utf-8")

    approved = approve_atom(path=pending, reviewer="tester")

    assert approved.decision == "INTEGRATION_BLOCKED"
    assert pending.read_text(encoding="utf-8") == original
    assert not (wiki / "concepts" / pending.name).exists()
    assert "approve-integrate" not in (wiki / "log.md").read_text(encoding="utf-8")


def test_approval_transaction_rolls_back_page_move_and_projections(
    chetana_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pending = promote(
        staged_path=ingest(
            source="rollback approval",
            source_kind="note",
            title="Rollback Approval",
            confidence=0.8,
        ).atoms[0],
        promoted_by="tester",
    ).trusted_path
    assert pending is not None
    original = pending.read_text(encoding="utf-8")
    wiki = chetana_sandbox / "wiki"

    def refuse_final_projection(*_args, **_kwargs):
        raise ValueError("injected final projection refusal")

    monkeypatch.setattr(
        cross_update_module,
        "_validate_cross_update_projection",
        refuse_final_projection,
    )
    approved = approve_atom(path=pending, reviewer="tester")

    assert approved.decision == "INTEGRATION_BLOCKED"
    assert pending.read_text(encoding="utf-8") == original
    assert not (wiki / "concepts" / pending.name).exists()
    assert not (wiki / "index.md").exists()
    assert "approve-integrate" not in (wiki / "log.md").read_text(encoding="utf-8")


def test_approval_reconciles_backlink_invalidated_by_new_alias(
    chetana_sandbox: Path,
) -> None:
    wiki = chetana_sandbox / "wiki"
    concepts = wiki / "concepts"
    connections = wiki / "connections"
    concepts.mkdir(parents=True, exist_ok=True)
    connections.mkdir(parents=True, exist_ok=True)
    (concepts / "source.md").write_text("# Source\n\nSee [[foo]].\n", encoding="utf-8")
    old_target = connections / "foo.md"
    old_target.write_text(
        "# Old Foo\n\n"
        "## Backlinks\n\n"
        "<!-- BACKLINKS_BEGIN -->\n"
        "- [[source]]\n"
        "<!-- BACKLINKS_END -->\n",
        encoding="utf-8",
    )
    pending = promote(
        staged_path=ingest(
            source="A new curated concept that collides with the old short alias.",
            source_kind="note",
            title="Foo",
            confidence=0.8,
        ).atoms[0],
        promoted_by="tester",
    ).trusted_path
    assert pending is not None

    approved = approve_atom(path=pending, reviewer="tester")

    assert approved.decision == "APPROVED", approved.error
    assert "[[source]]" not in old_target.read_text(encoding="utf-8")
    assert approved.trusted_path == concepts / "foo.md"


def test_index_upsert_does_not_overwrite_a_prefix_collision(
    chetana_sandbox: Path,
) -> None:
    wiki = chetana_sandbox / "wiki"
    index = wiki / "index.md"
    index.write_text(
        "# Index\n\n## Concepts\n- [[concepts/foo-bar|Foo Bar]] — atom_id=bar\n",
        encoding="utf-8",
    )
    atom = wiki / "concepts" / "foo.md"
    atom.write_text("# Foo\n", encoding="utf-8")

    _upsert_index_entry(index, atom, "Foo", "foo-id")

    text = index.read_text(encoding="utf-8")
    assert "[[concepts/foo-bar|Foo Bar]] — atom_id=bar" in text
    assert "[[concepts/foo|Foo]] — atom_id=foo-id" in text


def test_index_upsert_preserves_curated_prose_and_sanitizes_title(
    chetana_sandbox: Path,
) -> None:
    wiki = chetana_sandbox / "wiki"
    index = wiki / "index.md"
    index.write_text(
        "# Index\n\n## Concepts\nSee [[concepts/foo|Foo]] in the curated guide.\n",
        encoding="utf-8",
    )
    atom = wiki / "concepts" / "foo.md"
    atom.write_text("# Foo\n", encoding="utf-8")

    _upsert_index_entry(
        index,
        atom,
        "Safe]]\n- [[evil|Forged",
        "00000000-0000-4000-8000-000000000000",
    )

    text = index.read_text(encoding="utf-8")
    assert "See [[concepts/foo|Foo]] in the curated guide." in text
    assert text.count("\n- [[") == 1
    assert "[[evil|Forged" not in text


def test_cross_update_rejects_unsigned_or_unapproved_concept(
    chetana_sandbox: Path,
) -> None:
    staged = ingest(
        source="unreviewed atom",
        source_kind="note",
        title="Unreviewed",
        confidence=0.8,
    ).atoms[0]
    concept = chetana_sandbox / "wiki" / "concepts" / "unreviewed.md"
    concept.write_text(staged.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="approved provenance"):
        cross_update_trusted(concept)

    assert not (chetana_sandbox / "wiki" / "index.md").exists()


def test_double_promote_raises(chetana_sandbox: Path):
    ingested = ingest(source="x", source_kind="note", title="t", confidence=0.5)
    staged = ingested.atoms[0]
    promote(staged_path=staged, promoted_by="t")
    with pytest.raises(FileNotFoundError):
        promote(staged_path=staged, promoted_by="t")  # already moved/deleted


def test_promote_refuses_path_outside_staging_root(chetana_sandbox: Path):
    ingested = ingest(
        source="valid staged body",
        source_kind="note",
        title="outside copy",
        confidence=0.5,
    )
    outside = chetana_sandbox / "outside.md"
    outside.write_text(ingested.atoms[0].read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="outside chetana staging root"):
        promote(staged_path=outside, promoted_by="test")
