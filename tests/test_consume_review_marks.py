"""Tests for scripts/consume_review_marks.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import consume_review_marks as crm


class TestParseFrontmatter:
    def test_valid_atomic(self) -> None:
        text = "---\ntitle: Test\ntype: atomic\nconfidence: 0.8\nconcepts: a, b\n---\nBody."
        meta = crm.parse_frontmatter(text)
        assert meta is not None
        assert meta.atom_type == "atomic"
        assert meta.confidence == 0.8
        assert meta.title == "Test"
        assert meta.concepts == ["a", "b"]

    def test_missing_frontmatter(self) -> None:
        text = "No frontmatter here."
        assert crm.parse_frontmatter(text) is None

    def test_defaults_for_missing_fields(self) -> None:
        text = "---\ntitle: Minimal\n---\nContent."
        meta = crm.parse_frontmatter(text)
        assert meta is not None
        assert meta.atom_type == "unknown"
        assert meta.confidence == 0.0


class TestShouldPromote:
    def test_atomic_high_confidence(self) -> None:
        meta = crm.AtomMeta("atomic", 0.8, "T", [], "")
        ok, reason = crm.should_promote(meta, 0.5)
        assert ok is True

    def test_atomic_low_confidence(self) -> None:
        meta = crm.AtomMeta("atomic", 0.3, "T", [], "")
        ok, reason = crm.should_promote(meta, 0.5)
        assert ok is False
        assert "confidence" in reason

    def test_compound_type_rejected(self) -> None:
        meta = crm.AtomMeta("compound", 0.9, "T", [], "")
        ok, reason = crm.should_promote(meta, 0.5)
        assert ok is False
        assert "type" in reason

    def test_concept_type_allowed(self) -> None:
        meta = crm.AtomMeta("concept", 0.6, "T", [], "")
        ok, reason = crm.should_promote(meta, 0.5)
        assert ok is True


class TestPromoteAtom:
    def test_promote_moves_file(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        trusted = tmp_path / "trusted"
        staging.mkdir()
        trusted.mkdir()

        atom = staging / "test.md"
        atom.write_text("---\ntitle: X\ntype: atomic\nconfidence: 0.9\n---\nBody.")

        # Monkey-patch STAGING_DIR for the test
        original_staging = crm.STAGING_DIR
        crm.STAGING_DIR = staging
        try:
            result = crm.promote_atom(atom, trusted, dry_run=False)
        finally:
            crm.STAGING_DIR = original_staging

        assert result is True
        assert not atom.exists()
        assert (trusted / "test.md").exists()

    def test_dry_run_does_not_move(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        trusted = tmp_path / "trusted"
        staging.mkdir()
        trusted.mkdir()

        atom = staging / "test.md"
        atom.write_text("content")

        original_staging = crm.STAGING_DIR
        crm.STAGING_DIR = staging
        try:
            result = crm.promote_atom(atom, trusted, dry_run=True)
        finally:
            crm.STAGING_DIR = original_staging

        assert result is True
        assert atom.exists()  # Not moved
        assert not (trusted / "test.md").exists()
