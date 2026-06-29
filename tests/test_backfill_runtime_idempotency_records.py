from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from dharma_swarm.runtime_state import RuntimeStateStore


def _load_backfill_module():
    spec = importlib.util.spec_from_file_location(
        "backfill_runtime_idempotency_records",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "backfill_runtime_idempotency_records.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _idempotency_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT COUNT(*) FROM idempotency_records").fetchone()
    return int(row[0] if row else 0)


def _seed_runtime_receipts(db_path: Path) -> None:
    RuntimeStateStore(db_path, include_memory_plane=False).init_db_sync()
    with sqlite3.connect(db_path) as db:
        db.executemany(
            "INSERT INTO runtime_receipts ("
            " receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "rr-candidate",
                    "delegation_run",
                    "run-candidate",
                    "task-candidate",
                    "trace-candidate",
                    "corr-candidate",
                    "agent-candidate",
                    "idem-candidate",
                    "delegation_run:run-candidate:completed",
                    "completed",
                    '{"mission_id":"mission-candidate"}',
                    "2026-06-11T00:00:00+00:00",
                ),
                (
                    "rr-missing-side",
                    "delegation_run",
                    "run-missing-side",
                    "task-missing-side",
                    "trace-missing-side",
                    "corr-missing-side",
                    "agent-missing-side",
                    "idem-missing-side",
                    "",
                    "failed",
                    '{"mission_id":"mission-missing-side"}',
                    "2026-06-11T00:01:00+00:00",
                ),
                (
                    "rr-existing",
                    "delegation_run",
                    "run-existing",
                    "task-existing",
                    "trace-existing",
                    "corr-existing",
                    "agent-existing",
                    "idem-existing",
                    "delegation_run:run-existing:completed",
                    "completed",
                    '{"mission_id":"mission-existing"}',
                    "2026-06-11T00:02:00+00:00",
                ),
            ],
        )
        db.execute(
            "INSERT INTO idempotency_records ("
            " idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, metadata_json,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-existing",
                "delegation_run:run-existing:completed",
                "run-existing",
                "task-existing",
                "trace-existing",
                "corr-existing",
                "completed",
                "rr-existing",
                "{}",
                "2026-06-11T00:02:00+00:00",
                "2026-06-11T00:02:00+00:00",
            ),
        )
        db.commit()


def test_backfill_dry_run_does_not_mutate_runtime_db(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_runtime_receipts(db_path)
    mod = _load_backfill_module()

    result = mod.backfill_missing_idempotency_records(db_path, apply=False)

    assert result["mode"] == "dry_run"
    assert result["candidate_count"] == 1
    assert result["inserted_count"] == 0
    assert result["sample_candidates"][0]["receipt_id"] == "rr-candidate"
    assert result["safety"] == {
        "updates_runtime_receipts": False,
        "derives_missing_side_effect_keys": False,
        "requires_existing_idempotency_key": True,
        "requires_existing_side_effect_key": True,
    }
    assert _idempotency_count(db_path) == 1


def test_backfill_apply_inserts_only_already_keyed_receipts(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_runtime_receipts(db_path)
    mod = _load_backfill_module()

    result = mod.backfill_missing_idempotency_records(db_path, apply=True)

    assert result["mode"] == "apply"
    assert result["candidate_count"] == 1
    assert result["inserted_count"] == 1
    assert _idempotency_count(db_path) == 2

    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM idempotency_records"
            " WHERE idempotency_key = ? AND side_effect_key = ?",
            ("idem-candidate", "delegation_run:run-candidate:completed"),
        ).fetchone()
        assert row is not None
        assert row["status"] == "completed"
        assert row["result_receipt_id"] == "rr-candidate"
        metadata = json.loads(row["metadata_json"])
        assert metadata["source"] == "runtime_receipt_historical_idempotency_backfill"
        assert metadata["created_from_existing_runtime_receipt"] is True
        assert metadata["side_effect_key_was_derived"] is False
        assert metadata["runtime_receipt_was_rewritten"] is False

        missing_side = db.execute(
            "SELECT COUNT(*) FROM idempotency_records"
            " WHERE idempotency_key = 'idem-missing-side'",
        ).fetchone()[0]
        assert missing_side == 0

    second_result = mod.backfill_missing_idempotency_records(db_path, apply=True)
    assert second_result["candidate_count"] == 0
    assert second_result["inserted_count"] == 0
    assert _idempotency_count(db_path) == 2
