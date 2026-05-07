"""Tests for ``dharma_swarm.shakti_executive.feedback_writer``.

Covers the BR-002 next-step writer: outcome appended to opportunity's
realized_outcomes, learned_score_delta updated, atomic write, idempotency,
and the no-op paths (missing board, missing opportunity).
"""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.shakti_executive.feedback_writer import (
    OutcomeRecord,
    update_opportunity_outcome,
)


def _board(tmp_path: Path, *opps: dict) -> Path:
    path = tmp_path / "opportunity_board.json"
    path.write_text(json.dumps(list(opps)), encoding="utf-8")
    return path


def _outcome(**kwargs) -> OutcomeRecord:
    defaults = {
        "outcome_id": "out-1",
        "proposal_id": "prop-1",
        "success": True,
        "fitness_score": 0.8,
        "duration_ms": 1500.0,
        "result_summary": "ok",
        "recorded_at": 1_700_000_000.0,
    }
    defaults.update(kwargs)
    return OutcomeRecord(**defaults)


def test_appends_outcome_to_matching_opportunity(tmp_path: Path):
    board = _board(
        tmp_path,
        {"opportunity_id": "opp-A", "title": "Reforest"},
        {"opportunity_id": "opp-B", "title": "Compost"},
    )
    out = _outcome(outcome_id="out-1", success=True, fitness_score=0.9)

    ok = update_opportunity_outcome("opp-A", out, board_path=board)
    assert ok is True

    rows = json.loads(board.read_text())
    a = next(r for r in rows if r["opportunity_id"] == "opp-A")
    b = next(r for r in rows if r["opportunity_id"] == "opp-B")

    assert len(a["realized_outcomes"]) == 1
    assert a["realized_outcomes"][0]["outcome_id"] == "out-1"
    assert a["realized_outcomes"][0]["success"] is True
    assert a["learned_score_delta"] == 0.9
    assert "realized_outcomes" not in b
    assert "learned_score_delta" not in b


def test_failure_outcome_decreases_score(tmp_path: Path):
    board = _board(tmp_path, {"opportunity_id": "opp-A"})
    out = _outcome(outcome_id="out-fail", success=False, fitness_score=0.0)

    ok = update_opportunity_outcome("opp-A", out, board_path=board)
    assert ok is True

    rows = json.loads(board.read_text())
    assert rows[0]["learned_score_delta"] == -0.5
    assert rows[0]["realized_outcomes"][0]["success"] is False


def test_idempotent_on_duplicate_outcome_id(tmp_path: Path):
    board = _board(tmp_path, {"opportunity_id": "opp-A"})
    out = _outcome(outcome_id="out-dup", success=True, fitness_score=0.5)

    first = update_opportunity_outcome("opp-A", out, board_path=board)
    second = update_opportunity_outcome("opp-A", out, board_path=board)

    assert first is True
    assert second is False  # idempotent

    rows = json.loads(board.read_text())
    assert len(rows[0]["realized_outcomes"]) == 1
    # delta applied exactly once
    assert rows[0]["learned_score_delta"] == 0.5


def test_no_match_returns_false_and_does_not_write(tmp_path: Path):
    board = _board(tmp_path, {"opportunity_id": "opp-A"})
    before = board.read_text()

    ok = update_opportunity_outcome("opp-MISSING", _outcome(), board_path=board)
    assert ok is False
    assert board.read_text() == before


def test_missing_board_returns_false(tmp_path: Path):
    missing = tmp_path / "does_not_exist.json"
    ok = update_opportunity_outcome("opp-A", _outcome(), board_path=missing)
    assert ok is False
    assert not missing.exists()


def test_atomic_write_preserves_other_rows(tmp_path: Path):
    board = _board(
        tmp_path,
        {"opportunity_id": "opp-A", "title": "A", "score": 1.0},
        {"opportunity_id": "opp-B", "title": "B", "score": 2.0},
        {"opportunity_id": "opp-C", "title": "C", "score": 3.0},
    )
    update_opportunity_outcome("opp-B", _outcome(outcome_id="x"), board_path=board)

    rows = json.loads(board.read_text())
    assert len(rows) == 3
    assert {r["opportunity_id"] for r in rows} == {"opp-A", "opp-B", "opp-C"}
    a = next(r for r in rows if r["opportunity_id"] == "opp-A")
    c = next(r for r in rows if r["opportunity_id"] == "opp-C")
    assert a == {"opportunity_id": "opp-A", "title": "A", "score": 1.0}
    assert c == {"opportunity_id": "opp-C", "title": "C", "score": 3.0}


def test_backup_file_written_on_update(tmp_path: Path):
    board = _board(tmp_path, {"opportunity_id": "opp-A"})
    update_opportunity_outcome("opp-A", _outcome(), board_path=board)
    backups = list(tmp_path.glob("opportunity_board.json.bak.*"))
    assert len(backups) == 1


def test_score_delta_capped_per_outcome(tmp_path: Path):
    """A single oversized fitness_score does not blow past the cap."""
    board = _board(tmp_path, {"opportunity_id": "opp-A"})
    out = _outcome(outcome_id="big", success=True, fitness_score=999.0)
    update_opportunity_outcome("opp-A", out, board_path=board)
    rows = json.loads(board.read_text())
    assert rows[0]["learned_score_delta"] == 1.0
