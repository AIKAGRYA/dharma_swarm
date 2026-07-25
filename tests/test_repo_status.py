"""Tests for scripts/governance/repo_status.py helper functions."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Add repo root to path so we can import the script module
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import repo_status  # noqa: E402


# ── _count_broken_register ──────────────────────────────────────────────


class TestCountBrokenRegister:
    """Tests for section-based broken register parsing."""

    def test_empty_file(self, tmp_path: Path):
        br = tmp_path / "BROKEN_REGISTER.md"
        br.write_text("# Empty register\nNo items yet.\n")
        with patch.object(repo_status, "BROKEN_REGISTER", br):
            total, open_like = repo_status._count_broken_register()
        assert total == 0
        assert open_like == 0

    def test_missing_file(self, tmp_path: Path):
        br = tmp_path / "nonexistent.md"
        with patch.object(repo_status, "BROKEN_REGISTER", br):
            total, open_like = repo_status._count_broken_register()
        assert total == 0
        assert open_like == 0

    def test_multi_line_status_detection(self, tmp_path: Path):
        """Status on a different line from the BR-NNN heading."""
        content = """\
# BROKEN REGISTER

## OPEN ITEMS

### BR-003 — Apply gate present but closed
- **first_observed:** 2026-05-07
- **severity:** BLOCKER
- **status:** PARTIAL — partial closure

### BR-005 — Algedonic stream degenerate
- **first_observed:** 2026-05-02
- **severity:** DEGRADED
- **status:** OPEN

### BR-010 — Some fixed item
- **first_observed:** 2026-05-01
- **status:** FIXED — resolved 2026-05-20
"""
        br = tmp_path / "BROKEN_REGISTER.md"
        br.write_text(content)
        with patch.object(repo_status, "BROKEN_REGISTER", br):
            total, open_like = repo_status._count_broken_register()
        assert total == 3
        assert open_like == 2  # BR-003 (PARTIAL) + BR-005 (OPEN)

    def test_closed_section_not_counted_as_open(self, tmp_path: Path):
        content = """\
# BROKEN REGISTER

## OPEN ITEMS

### BR-014 — BHED_GNAN hard-pass
- **status:** OPEN

## CLOSED ITEMS

### BR-001 — Cron daemon plist
- **status:** FIXED — 2026-05-07
"""
        br = tmp_path / "BROKEN_REGISTER.md"
        br.write_text(content)
        with patch.object(repo_status, "BROKEN_REGISTER", br):
            total, open_like = repo_status._count_broken_register()
        assert total == 2
        assert open_like == 1  # only BR-014

    def test_investigating_counted_as_open(self, tmp_path: Path):
        content = """\
## OPEN ITEMS

### BR-020 — New issue
- **status:** INVESTIGATING
"""
        br = tmp_path / "BROKEN_REGISTER.md"
        br.write_text(content)
        with patch.object(repo_status, "BROKEN_REGISTER", br):
            total, open_like = repo_status._count_broken_register()
        assert total == 1
        assert open_like == 1


# ── _parse_active_track ─────────────────────────────────────────────────


class TestParseActiveTrack:
    """Tests for active track YAML parsing."""

    def test_missing_file(self, tmp_path: Path):
        at = tmp_path / "nonexistent.yaml"
        with patch.object(repo_status, "ACTIVE_TRACK", at):
            info = repo_status._parse_active_track()
        assert info == {}

    def test_valid_track(self, tmp_path: Path):
        content = """\
active_track:
  id: trace-identity-coverage-2026-05
  name: Trace Identity Coverage
  status: ACTIVE
  verified_at: "2026-05-21"
  owner: "@AmitabhainArunachala"
"""
        at = tmp_path / "ACTIVE_TRACK.yaml"
        at.write_text(content)
        with patch.object(repo_status, "ACTIVE_TRACK", at):
            info = repo_status._parse_active_track()
        assert info["id"] == "trace-identity-coverage-2026-05"
        assert info["status"] == "ACTIVE"
        assert info["name"] == "Trace Identity Coverage"


# ── _hotlist_summary ────────────────────────────────────────────────────


class TestHotlistSummary:
    """Tests for hotlist table parsing."""

    def test_missing_file(self, tmp_path: Path):
        hl = tmp_path / "nonexistent.md"
        with patch.object(repo_status, "HOTLIST", hl):
            total, done, wip = repo_status._hotlist_summary()
        assert (total, done, wip) == (0, 0, 0)
