from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.casebook_mine import mine_candidates, write_candidates


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_casebook_mine_end_to_end_schema(tmp_path: Path) -> None:
    witness_dir = tmp_path / "witness"
    _write_jsonl(
        witness_dir / "witness_20260501.jsonl",
        [
            {
                "ts": "2026-05-01T00:00:00+00:00",
                "phase": "before_write",
                "outcome": "BLOCKED",
                "action": "dangerous action",
                "reflection": "AHIMSA violation",
            }
        ],
    )
    marks = tmp_path / "stigmergy" / "marks.jsonl"
    _write_jsonl(
        marks,
        [
            {
                "ts": "2026-05-01T01:00:00+00:00",
                "subject_id": "dangerous action",
                "severity": "high",
                "corrects": "abc",
            }
        ],
    )

    output = tmp_path / "meta" / "casebook_candidates.jsonl"
    candidates = mine_candidates(
        witness_dir=witness_dir,
        stigmergy_marks=marks,
        stigmergy_archive=tmp_path / "missing_stigmergy_archive.jsonl",
        evolution_archive=tmp_path / "missing_evolution_archive.jsonl",
        limit=200,
    )
    assert write_candidates(candidates, output)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows
    required = {
        "candidate_id",
        "source",
        "source_path",
        "source_line",
        "ts",
        "action_payload",
        "context",
        "original_decision",
        "candidate_for_rejudgement",
        "selection_reason",
    }
    assert required <= set(rows[0])


def test_casebook_mine_spans_sources_when_available(tmp_path: Path) -> None:
    witness_dir = tmp_path / "witness"
    _write_jsonl(
        witness_dir / "witness_20260501.jsonl",
        [{"ts": "2026-05-01T00:00:00+00:00", "outcome": "HOLD", "action": "hold"}],
    )
    evolution = tmp_path / "evolution" / "archive.jsonl"
    _write_jsonl(
        evolution,
        [{"timestamp": "2026-05-01T00:00:00+00:00", "kept": False, "mutation_id": "m1"}],
    )

    candidates = mine_candidates(
        witness_dir=witness_dir,
        stigmergy_marks=tmp_path / "missing_marks.jsonl",
        stigmergy_archive=tmp_path / "missing_archive.jsonl",
        evolution_archive=evolution,
        limit=200,
    )
    assert {candidate["source"] for candidate in candidates} == {"witness", "evolution"}


def test_casebook_mine_candidate_ids_are_deterministic(tmp_path: Path) -> None:
    witness_dir = tmp_path / "witness"
    _write_jsonl(
        witness_dir / "witness_20260501.jsonl",
        [{"ts": "2026-05-01T00:00:00+00:00", "outcome": "BLOCKED", "action": "x"}],
    )

    kwargs = {
        "witness_dir": witness_dir,
        "stigmergy_marks": tmp_path / "missing_marks.jsonl",
        "stigmergy_archive": tmp_path / "missing_archive.jsonl",
        "evolution_archive": tmp_path / "missing_evolution_archive.jsonl",
        "limit": 200,
    }
    first = mine_candidates(**kwargs)
    second = mine_candidates(**kwargs)
    assert [c["candidate_id"] for c in first] == [c["candidate_id"] for c in second]


def test_casebook_mine_detects_allow_followed_by_mark(tmp_path: Path) -> None:
    witness_dir = tmp_path / "witness"
    _write_jsonl(
        witness_dir / "witness_20260501.jsonl",
        [{"ts": "2026-05-01T00:00:00+00:00", "outcome": "PASS", "action": "subject-a"}],
    )
    marks = tmp_path / "stigmergy" / "marks.jsonl"
    _write_jsonl(
        marks,
        [{"ts": "2026-05-01T12:00:00+00:00", "subject_id": "subject-a", "severity": "warn"}],
    )

    candidates = mine_candidates(
        witness_dir=witness_dir,
        stigmergy_marks=marks,
        stigmergy_archive=tmp_path / "missing_archive.jsonl",
        evolution_archive=tmp_path / "missing_evolution_archive.jsonl",
        limit=200,
    )
    assert any("within 24h" in c["selection_reason"] for c in candidates)
