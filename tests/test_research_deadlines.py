"""Operator-owned research deadlines (the post-COLM stopped-clock fix).

The contract under test: a dead or absent deadline NEVER renders a countdown —
active_deadline() returns None and callers omit the line entirely.
"""

from __future__ import annotations

import json
from datetime import date

from dharma_swarm.research_deadlines import (
    active_deadline,
    deadline_line,
)

TODAY = date(2026, 7, 3)


def _write(tmp_path, payload):
    p = tmp_path / "research_deadlines.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_absent_file_means_no_deadline(tmp_path):
    p = tmp_path / "missing.json"
    assert active_deadline(today=TODAY, path=p) is None
    assert "no active research deadline" in deadline_line(today=TODAY, path=p)


def test_past_deadline_never_returns_a_countdown(tmp_path):
    # The COLM bug: the venue died 2026-03-31 but the clock kept broadcasting.
    p = _write(tmp_path, {"deadlines": [
        {"venue": "COLM 2026", "abstract": "2026-03-26", "paper": "2026-03-31"},
    ]})
    assert active_deadline(today=TODAY, path=p) is None
    assert "no active research deadline" in deadline_line(today=TODAY, path=p)


def test_future_deadline_counts_down(tmp_path):
    p = _write(tmp_path, {"deadlines": [
        {"venue": "TestVenue 2027", "abstract": "2026-07-10", "paper": "2026-07-13"},
    ]})
    dl = active_deadline(today=TODAY, path=p)
    assert dl is not None and dl.venue == "TestVenue 2027"
    assert dl.days_to_abstract(TODAY) == 7
    assert dl.days_to_paper(TODAY) == 10
    assert deadline_line(today=TODAY, path=p) == (
        "TestVenue 2027 — abstract in 7d, paper in 10d"
    )


def test_nearest_future_entry_wins_and_past_entries_are_skipped(tmp_path):
    p = _write(tmp_path, [
        {"venue": "Dead", "paper": "2026-01-01"},
        {"venue": "Far", "paper": "2027-01-01"},
        {"venue": "Near", "paper": "2026-08-01"},
    ])
    dl = active_deadline(today=TODAY, path=p)
    assert dl is not None and dl.venue == "Near"


def test_malformed_file_means_no_deadline(tmp_path):
    p = tmp_path / "research_deadlines.json"
    p.write_text("{not json", encoding="utf-8")
    assert active_deadline(today=TODAY, path=p) is None
    p.write_text(json.dumps({"deadlines": [{"venue": "NoDates"}]}), encoding="utf-8")
    assert active_deadline(today=TODAY, path=p) is None
