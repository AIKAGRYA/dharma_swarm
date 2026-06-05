"""Tests for scripts/consume_review_marks.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import consume_review_marks as crm


class TestParseFrontmatter:
    def test_valid_atomic(self) -> None:
        text = "---\ntitle: Test\ntype: atomic\nconfidence: 0.8\nconcepts: a, b\nreviewed: true\n---\nBody."
        meta = crm.parse_frontmatter(text)
        assert meta is not None
        assert meta.atom_type == "atomic"
        assert meta.confidence == 0.8
        assert meta.title == "Test"
        assert meta.concepts == ["a", "b"]
        assert meta.reviewed is True

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
        meta = crm.AtomMeta("atomic", 0.8, "T", [], "", reviewed=True)
        ok, reason = crm.should_promote(meta, 0.5, has_independent_review=True)
        assert ok is True

    def test_atomic_low_confidence(self) -> None:
        meta = crm.AtomMeta("atomic", 0.3, "T", [], "", reviewed=True)
        ok, reason = crm.should_promote(meta, 0.5, has_independent_review=True)
        assert ok is False
        assert "confidence" in reason

    def test_compound_type_rejected(self) -> None:
        meta = crm.AtomMeta("compound", 0.9, "T", [], "", reviewed=True)
        ok, reason = crm.should_promote(meta, 0.5, has_independent_review=True)
        assert ok is False
        assert "type" in reason

    def test_concept_type_rejected(self) -> None:
        meta = crm.AtomMeta("concept", 0.6, "T", [], "", reviewed=True)
        ok, reason = crm.should_promote(meta, 0.5, has_independent_review=True)
        assert ok is False
        assert "type" in reason

    def test_atomic_without_review_mark_rejected(self) -> None:
        meta = crm.AtomMeta("atomic", 0.8, "T", [], "", reviewed=True)
        ok, reason = crm.should_promote(meta, 0.5)
        assert ok is False
        assert "external review" in reason


class TestExternalReviewMarks:
    def test_external_review_mark_approves_atom(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        review_marks = tmp_path / "review_marks"
        staging.mkdir()
        review_marks.mkdir()
        atom = staging / "test.md"
        atom.write_text(
            "---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "REVIEW_MARK_DIR", review_marks)
        crm.review_mark_path(atom).write_text(
            json.dumps(
                {
                    "schema": crm.REVIEW_MARK_SCHEMA,
                    "path": "test.md",
                    "decision": "approved",
                    "reviewer": "operator",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                    "atom_sha256": crm._file_sha256(atom),
                }
            ),
            encoding="utf-8",
        )

        assert crm.has_external_review_mark(atom) is True

    def test_atom_local_reviewed_flag_is_not_authority(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        review_marks = tmp_path / "review_marks"
        staging.mkdir()
        review_marks.mkdir()
        atom = staging / "test.md"
        atom.write_text(
            "---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "REVIEW_MARK_DIR", review_marks)

        assert crm.has_external_review_mark(atom) is False

    def test_external_review_mark_rejects_missing_hash(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        review_marks = tmp_path / "review_marks"
        staging.mkdir()
        review_marks.mkdir()
        atom = staging / "test.md"
        atom.write_text(
            "---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "REVIEW_MARK_DIR", review_marks)
        crm.review_mark_path(atom).write_text(
            json.dumps(
                {
                    "schema": crm.REVIEW_MARK_SCHEMA,
                    "path": "test.md",
                    "decision": "approved",
                    "reviewer": "operator",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        assert crm.has_external_review_mark(atom) is False

    def test_external_review_mark_rejects_automation_reviewer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        review_marks = tmp_path / "review_marks"
        staging.mkdir()
        review_marks.mkdir()
        atom = staging / "test.md"
        atom.write_text(
            "---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "REVIEW_MARK_DIR", review_marks)
        crm.review_mark_path(atom).write_text(
            json.dumps(
                {
                    "schema": crm.REVIEW_MARK_SCHEMA,
                    "path": "test.md",
                    "decision": "approved",
                    "reviewer": "devin",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                    "atom_sha256": crm._file_sha256(atom),
                }
            ),
            encoding="utf-8",
        )

        assert crm.has_external_review_mark(atom) is False

    def test_external_review_mark_rejects_hash_mismatch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        review_marks = tmp_path / "review_marks"
        staging.mkdir()
        review_marks.mkdir()
        atom = staging / "test.md"
        atom.write_text(
            "---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "REVIEW_MARK_DIR", review_marks)
        crm.review_mark_path(atom).write_text(
            json.dumps(
                {
                    "schema": crm.REVIEW_MARK_SCHEMA,
                    "path": "test.md",
                    "decision": "approved",
                    "reviewer": "operator",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                    "atom_sha256": "not-the-current-hash",
                }
            ),
            encoding="utf-8",
        )

        assert crm.has_external_review_mark(atom) is False

    def test_scan_staging_counts_external_review_marks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        review_marks = tmp_path / "review_marks"
        staging.mkdir()
        review_marks.mkdir()
        approved = staging / "approved.md"
        unreviewed = staging / "unreviewed.md"
        approved.write_text(
            "---\ntitle: Approved\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )
        unreviewed.write_text(
            "---\ntitle: Unreviewed\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "REVIEW_MARK_DIR", review_marks)
        crm.review_mark_path(approved).write_text(
            json.dumps(
                {
                    "schema": crm.REVIEW_MARK_SCHEMA,
                    "path": "approved.md",
                    "decision": "approved",
                    "reviewer": "operator",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                    "atom_sha256": crm._file_sha256(approved),
                }
            ),
            encoding="utf-8",
        )

        stats = crm.scan_staging(min_confidence=0.5)

        assert stats["total"] == 2
        assert stats["promotable"] == 1
        assert stats["missing_review"] == 1
        assert stats["wrong_type"] == 0


class TestPromoteAtom:
    def test_promote_moves_file(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        trusted = tmp_path / "trusted"
        staging.mkdir()
        trusted.mkdir()

        atom = staging / "test.md"
        atom.write_text("---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.")

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

    def test_dry_run_does_not_create_destination_parent(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        trusted = tmp_path / "trusted"
        nested = staging / "nested"
        nested.mkdir(parents=True)

        atom = nested / "test.md"
        atom.write_text("content")

        original_staging = crm.STAGING_DIR
        crm.STAGING_DIR = staging
        try:
            result = crm.promote_atom(atom, trusted, dry_run=True)
        finally:
            crm.STAGING_DIR = original_staging

        assert result is True
        assert atom.exists()
        assert not trusted.exists()

    def test_main_dry_run_does_not_create_trusted_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        staging = tmp_path / "staging"
        trusted = tmp_path / "trusted"
        log_path = tmp_path / "logs" / "consume_review_marks.jsonl"
        staging.mkdir()

        atom = staging / "test.md"
        atom.write_text(
            "---\ntitle: X\ntype: atomic\nconfidence: 0.9\nreviewed: true\n---\nBody.",
            encoding="utf-8",
        )

        monkeypatch.setattr(crm, "STAGING_DIR", staging)
        monkeypatch.setattr(crm, "TRUSTED_DIR", trusted)
        monkeypatch.setattr(crm, "LOG_PATH", log_path)
        monkeypatch.setattr(sys, "argv", ["consume_review_marks.py", "--dry-run"])

        assert crm.main() == 0
        assert atom.exists()
        assert not trusted.exists()
