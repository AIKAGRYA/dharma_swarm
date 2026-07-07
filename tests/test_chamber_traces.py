"""chamber_gym_trace.v1 — schema freeze, digest determinism, corpus pinning."""

from __future__ import annotations

import pytest

from dharma_swarm.chamber.traces import (
    CHAMBER_GYM_TRACE_SCHEMA,
    GymTraceRow,
    SeatAnswer,
    corpus_sha256,
    read_corpus,
    render_corpus_jsonl,
    verify_row_digest,
    write_corpus,
)


def _row(task_id: str = "t1", correct: bool = True) -> GymTraceRow:
    return GymTraceRow(
        env_id="g1_git_history",
        task_id=task_id,
        taskpack_sha="a" * 64,
        scorer_hash="b" * 64,
        seed=7,
        answers=(
            SeatAnswer(seat_id="s1", answer="diff-1", model="m1", provider="p1",
                       correct=True),
            SeatAnswer(seat_id="s2", answer="diff-2", model="m2", provider="p2",
                       correct=False),
        ),
        aggregated_answer="diff-1",
        correct=correct,
    )


def test_schema_is_frozen():
    assert CHAMBER_GYM_TRACE_SCHEMA == "chamber_gym_trace.v1"
    assert _row().to_dict()["schema"] == "chamber_gym_trace.v1"


def test_digest_is_deterministic_and_verifiable():
    d1, d2 = _row().to_dict(), _row().to_dict()
    assert d1["digest"] == d2["digest"]
    assert verify_row_digest(d1)
    d1["correct"] = False  # tamper
    assert not verify_row_digest(d1)


def test_corpus_bytes_and_sha_are_deterministic():
    rows = [_row("t1").to_dict(), _row("t2", correct=False).to_dict()]
    assert render_corpus_jsonl(rows) == render_corpus_jsonl(
        [_row("t1").to_dict(), _row("t2", correct=False).to_dict()]
    )
    assert len(corpus_sha256(rows)) == 64


def test_write_corpus_pins_sha_and_read_roundtrips(tmp_path):
    rows = [_row("t1").to_dict(), _row("t2").to_dict()]
    path = tmp_path / "corpus.jsonl"
    sha = write_corpus(rows, path)
    assert sha == corpus_sha256(rows)
    assert read_corpus(path) == rows


def test_write_corpus_refuses_undigested_rows(tmp_path):
    bad = _row().to_dict()
    bad.pop("digest")
    with pytest.raises(ValueError, match="digest"):
        write_corpus([bad], tmp_path / "c.jsonl")


def test_read_corpus_refuses_tampered_rows(tmp_path):
    rows = [_row().to_dict()]
    path = tmp_path / "corpus.jsonl"
    write_corpus(rows, path)
    text = path.read_text(encoding="utf-8").replace('"correct": true',
                                                    '"correct": false')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        read_corpus(path)
