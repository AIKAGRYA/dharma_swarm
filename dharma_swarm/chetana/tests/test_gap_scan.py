"""Tests for chetana.gap_scan."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.chetana.gap_scan import gap_scan
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import approve_atom, promote


def _promote_and_approve(staged_path: Path) -> None:
    pr = promote(staged_path=staged_path, promoted_by="t")
    approved = approve_atom(path=pr.trusted_path, reviewer="t")
    assert approved.decision == "APPROVED"


def test_gap_scan_finds_dangling_wikilinks(chetana_sandbox: Path):
    # Atom A references [[strange-loop]] but no atom titled "strange-loop" exists.
    body = "I love [[strange-loop]] and [[strange-loop]] is everywhere"
    ingested = ingest(source=body, source_kind="note", title="A1", confidence=0.5)
    _promote_and_approve(ingested.atoms[0])

    body2 = "and again [[strange-loop]] keeps coming up"
    ing2 = ingest(source=body2, source_kind="note", title="A2", confidence=0.5)
    _promote_and_approve(ing2.atoms[0])

    report = gap_scan(min_occurrences=2)
    assert report.scanned >= 2
    targets = {g.topic_or_question for g in report.topic_gaps}
    assert "strange-loop" in targets


def test_gap_scan_finds_open_questions(chetana_sandbox: Path):
    body = (
        "Why do strange loops emerge in transformers? "
        "Can we measure this with R_V? "
        "Why do strange loops emerge in transformers?"
    )
    ing = ingest(source=body, source_kind="note", title="Open questions", confidence=0.5)
    _promote_and_approve(ing.atoms[0])

    report = gap_scan(min_occurrences=2)
    assert any(
        "why do strange loops emerge" in q.topic_or_question for q in report.open_questions
    )
