from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.runtime.provider_starvation_alert import evaluate_and_emit


def _runtime_db(state_dir: Path) -> Path:
    db_path = state_dir / "state" / "runtime.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(str(db_path)) as db:
        db.execute(
            "CREATE TABLE delegation_runs (started_at TEXT, receipt_json TEXT)"
        )
    return db_path


def _insert_run(db_path: Path, *, started_at: str, receipt_json: str) -> None:
    with sqlite3.connect(str(db_path)) as db:
        db.execute(
            "INSERT INTO delegation_runs (started_at, receipt_json) VALUES (?, ?)",
            (started_at, receipt_json),
        )


def test_provider_starvation_alert_emits_critical_algedonic_signal(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    db_path = _runtime_db(state_dir)
    _insert_run(
        db_path,
        started_at="2026-07-02T00:01:00Z",
        receipt_json='{"error":"ProviderChainExecutionError"}',
    )
    _insert_run(
        db_path,
        started_at="2026-07-02T00:02:00Z",
        receipt_json='{"error":"429 rate limit"}',
    )
    _insert_run(
        db_path,
        started_at="2026-07-02T00:03:00Z",
        receipt_json='{"status":"ok"}',
    )

    status = evaluate_and_emit(
        state_dir=state_dir,
        since_date="2026-07-02",
        threshold=0.5,
        min_count=3,
    )

    assert status["alert"] is True
    assert status["emitted"] is True
    assert status["window"]["total"] == 3
    assert status["window"]["failures"] == 2
    stream = state_dir / "algedonic_signals.jsonl"
    records = [
        json.loads(line)
        for line in stream.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    assert records[0]["kind"] == "provider_starvation"
    assert records[0]["severity"] == "critical"
    assert records[0]["action"] == "restore_live_provider_routing"


def test_provider_starvation_alert_suppresses_unchanged_repeated_signal(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    db_path = _runtime_db(state_dir)
    for idx in range(3):
        _insert_run(
            db_path,
            started_at=f"2026-07-02T00:0{idx}:00Z",
            receipt_json='{"error":"ProviderChainExecutionError"}',
        )

    first = evaluate_and_emit(
        state_dir=state_dir,
        since_date="2026-07-02",
        threshold=0.5,
        min_count=3,
    )
    second = evaluate_and_emit(
        state_dir=state_dir,
        since_date="2026-07-02",
        threshold=0.5,
        min_count=3,
    )

    assert first["emitted"] is True
    assert second["alert"] is True
    assert second["emitted"] is False
    stream = state_dir / "algedonic_signals.jsonl"
    assert len(stream.read_text(encoding="utf-8").splitlines()) == 1
