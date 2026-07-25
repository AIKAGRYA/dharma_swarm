from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory_retrieval_calibrate_abstention.py"

spec = importlib.util.spec_from_file_location("memory_retrieval_calibrate_abstention", SCRIPT)
calibrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibrate)


def _seed_telemetry(db_path: Path, scores: list[float | None], empty_rows: int = 0) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE memory_retrieval_query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_time TEXT NOT NULL,
            top_score REAL,
            result_count INTEGER NOT NULL
        )
        """
    )
    for i, score in enumerate(scores):
        conn.execute(
            "INSERT INTO memory_retrieval_query_log (query_time, top_score, result_count) VALUES (?, ?, 1)",
            (f"2026-07-{(i % 25) + 1:02d}T00:00:00+00:00", score),
        )
    for _ in range(empty_rows):
        conn.execute(
            "INSERT INTO memory_retrieval_query_log (query_time, top_score, result_count) "
            "VALUES ('2026-07-01T00:00:00+00:00', NULL, 0)"
        )
    conn.commit()
    conn.close()


def test_recommends_threshold_within_loss_budget(tmp_path):
    db = tmp_path / "vectors.db"
    # 1000 served rows well above 0.4 plus one weak outlier at 0.1:
    # loss budget 0.1% (=1 row) allows abstaining the outlier only.
    _seed_telemetry(db, [0.9] * 1000 + [0.1], empty_rows=5)

    rc = calibrate.main(
        ["--db", str(db), "--receipt-dir", str(tmp_path / "receipts"), "--max-loss-rate", "0.001"]
    )

    assert rc == 0
    receipts = sorted((tmp_path / "receipts").glob("abstention_calibration_*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    recommended = receipt["recommendation"]["recommended_min_score"]
    assert 0.1 < recommended <= 0.9
    assert receipt["recommendation"]["newly_abstained_count"] == 1
    assert receipt["read_only"] is True
    assert receipt["telemetry"]["empty_result_count"] == 5
    assert receipt["telemetry"]["served_scored_count"] == 1001


def test_does_not_mutate_telemetry_db(tmp_path):
    db = tmp_path / "vectors.db"
    _seed_telemetry(db, [0.8] * 50)
    before = db.read_bytes()

    rc = calibrate.main(["--db", str(db), "--receipt-dir", str(tmp_path / "receipts")])

    assert rc == 0
    assert db.read_bytes() == before


def test_missing_db_fails_closed(tmp_path):
    rc = calibrate.main(
        ["--db", str(tmp_path / "absent.db"), "--receipt-dir", str(tmp_path / "receipts")]
    )
    assert rc == 2
    assert not (tmp_path / "receipts").exists()


def test_empty_telemetry_recommends_none(tmp_path):
    db = tmp_path / "vectors.db"
    _seed_telemetry(db, [])

    rc = calibrate.main(["--db", str(db), "--receipt-dir", str(tmp_path / "receipts")])

    assert rc == 0
    receipts = sorted((tmp_path / "receipts").glob("abstention_calibration_*.json"))
    receipt = json.loads(receipts[0].read_text())
    assert receipt["recommendation"]["recommended_min_score"] is None
    assert receipt["recommendation"]["reason"] == "no_served_scored_rows"
