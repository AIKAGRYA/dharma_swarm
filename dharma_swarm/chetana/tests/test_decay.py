"""Tests for chetana.decay — stale_after scanning + quarantine."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from dharma_swarm.chetana.decay import scan_decay
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import approve_atom, promote


def _seed_promoted_atom_with_stale(
    chetana_sandbox: Path, *, body: str, title: str, stale_after: str
) -> Path:
    ingested = ingest(source=body, source_kind="note", title=title, confidence=0.5)
    staged = ingested.atoms[0]
    pr = promote(staged_path=staged, promoted_by="seeder")
    assert pr.trusted_path is not None
    approved = approve_atom(path=pr.trusted_path, reviewer="seeder")
    assert approved.decision == "APPROVED"
    trusted = approved.trusted_path
    # Re-write the trusted file with an overridden stale_after for the test.
    text = trusted.read_text(encoding="utf-8")
    text = text.replace(_extract_stale(text), stale_after, 1)
    trusted.write_text(text, encoding="utf-8")
    return trusted


def _extract_stale(text: str) -> str:
    # crude extraction: find "stale_after: <iso>" line in frontmatter
    for line in text.splitlines():
        if line.startswith("stale_after:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("no stale_after field found")


def test_scan_decay_finds_no_stale_when_none_overdue(chetana_sandbox: Path):
    future = (date.today() + timedelta(days=30)).isoformat()
    _seed_promoted_atom_with_stale(
        chetana_sandbox, body="fresh atom", title="Fresh", stale_after=future
    )
    report = scan_decay()
    assert report.scanned >= 1
    assert report.stale_count == 0


def test_scan_decay_finds_overdue(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=10)).isoformat()
    _seed_promoted_atom_with_stale(
        chetana_sandbox, body="stale atom", title="Stale", stale_after=past
    )
    report = scan_decay()
    assert report.stale_count == 1
    assert report.stale[0].days_overdue >= 10


def test_quarantine_moves_stale_atoms(chetana_sandbox: Path):
    past = (date.today() - timedelta(days=5)).isoformat()
    path = _seed_promoted_atom_with_stale(
        chetana_sandbox, body="stale", title="Stale2", stale_after=past
    )
    assert path.exists()
    report = scan_decay(quarantine=True)
    assert len(report.quarantined) == 1
    assert not path.exists()
    assert report.quarantined[0].exists()
