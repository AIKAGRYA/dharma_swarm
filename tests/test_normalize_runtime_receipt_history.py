from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from dharma_swarm.runtime_state import RuntimeStateStore


def _load_normalizer_module():
    spec = importlib.util.spec_from_file_location(
        "normalize_runtime_receipt_history",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "normalize_runtime_receipt_history.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_history_gap_db(db_path: Path) -> None:
    RuntimeStateStore(db_path, include_memory_plane=False).init_db_sync()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs ("
            " run_id, session_id, task_id, claim_id, assigned_to, status,"
            " started_at, failure_code, metadata_json, trace_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-gap",
                "session-gap",
                "task-gap",
                "claim-gap",
                "agent-gap",
                "failed",
                "2026-06-11T00:00:00+00:00",
                "dispatch_dropoff",
                "{}",
                "trace-gap",
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs ("
            " run_id, session_id, task_id, claim_id, assigned_to, status,"
            " started_at, metadata_json, trace_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-preserved",
                "session-preserved",
                "task-preserved",
                "claim-preserved",
                "agent-preserved",
                "completed",
                "2026-06-11T00:00:00+00:00",
                "{}",
                "trace-preserved",
            ),
        )
        db.executemany(
            "INSERT INTO runtime_receipts ("
            " receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, agent_id, idempotency_key, side_effect_key,"
            " status, payload_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "rr-gap-run",
                    "delegation_run",
                    "run-gap",
                    "task-gap",
                    "trace-gap",
                    "corr-gap",
                    "agent-gap",
                    "idem-gap",
                    "",
                    "failed",
                    "{}",
                    "2026-06-11T00:01:00+00:00",
                ),
                (
                    "rr-gap-claim",
                    "task_claim",
                    "run-gap",
                    "task-gap",
                    "trace-gap",
                    "corr-gap",
                    "agent-gap",
                    "idem-gap",
                    "",
                    "failed",
                    "{}",
                    "2026-06-11T00:01:01+00:00",
                ),
                (
                    "rr-preserved",
                    "delegation_run",
                    "run-preserved",
                    "task-preserved",
                    "trace-preserved",
                    "corr-preserved",
                    "agent-preserved",
                    "idem-preserved",
                    "delegation_run:run-preserved:completed",
                    "completed",
                    json.dumps(
                        {
                            "mission_id": "explicit-mission",
                            "artifact_refs": ["artifact_records:artifact-existing"],
                        }
                    ),
                    "2026-06-11T00:02:00+00:00",
                ),
            ],
        )
        db.commit()


def _runtime_receipt(db_path: Path, receipt_id: str) -> sqlite3.Row:
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM runtime_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
    assert row is not None
    return row


def test_normalizer_dry_run_reports_candidates_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_history_gap_db(db_path)
    mod = _load_normalizer_module()

    result = mod.normalize_runtime_receipt_history(db_path, apply=False)

    assert result["mode"] == "dry_run"
    assert result["counts"]["side_effect_key_candidates"] == 2
    assert result["counts"]["payload_candidates"] == 2
    assert result["counts"]["idempotency_record_candidates"] == 3
    assert result["updated_side_effect_key_count"] == 0
    assert result["updated_payload_count"] == 0
    assert result["inserted_idempotency_record_count"] == 0
    assert _runtime_receipt(db_path, "rr-gap-run")["side_effect_key"] == ""


def test_normalizer_apply_marks_payload_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_history_gap_db(db_path)
    mod = _load_normalizer_module()

    result = mod.normalize_runtime_receipt_history(db_path, apply=True)

    assert result["mode"] == "apply"
    assert result["updated_side_effect_key_count"] == 2
    assert result["updated_payload_count"] == 2
    assert result["inserted_idempotency_record_count"] == 3

    run_receipt = _runtime_receipt(db_path, "rr-gap-run")
    assert run_receipt["side_effect_key"] == "delegation_run:run-gap:failed"
    payload = json.loads(run_receipt["payload_json"])
    assert payload["mission_id"] == "session-gap"
    assert payload["mission"] == "session-gap"
    assert payload["mission_id_source"] == "historical_runtime_lifecycle_fallback"
    assert (
        payload["no_artifact_refs_reason"]
        == "historical_dispatch_dropoff_receipt_no_artifact_recorded"
    )
    assert payload["side_effect_key_was_reconstructed"] is True
    assert payload["historical_runtime_receipt_normalization"]["schema_version"] == (
        "runtime_receipt_history_normalization.v1"
    )

    claim_receipt = _runtime_receipt(db_path, "rr-gap-claim")
    assert claim_receipt["side_effect_key"] == "task_claim:claim-gap:failed"

    preserved = json.loads(_runtime_receipt(db_path, "rr-preserved")["payload_json"])
    assert preserved["mission_id"] == "explicit-mission"
    assert preserved["artifact_refs"] == ["artifact_records:artifact-existing"]
    assert "historical_runtime_receipt_normalization" not in preserved

    with sqlite3.connect(db_path) as db:
        records = db.execute(
            "SELECT idempotency_key, side_effect_key, metadata_json"
            " FROM idempotency_records ORDER BY side_effect_key"
        ).fetchall()
    assert len(records) == 3
    metadata_by_side_effect = {row[1]: json.loads(row[2]) for row in records}
    assert all(
        item["source"] == "runtime_receipt_history_normalization"
        for item in metadata_by_side_effect.values()
    )
    assert (
        metadata_by_side_effect["delegation_run:run-gap:failed"][
            "side_effect_key_was_derived"
        ]
        is True
    )
    assert (
        metadata_by_side_effect["task_claim:claim-gap:failed"][
            "side_effect_key_was_derived"
        ]
        is True
    )
    assert (
        metadata_by_side_effect["delegation_run:run-preserved:completed"][
            "side_effect_key_was_derived"
        ]
        is False
    )

    second = mod.normalize_runtime_receipt_history(db_path, apply=True)
    assert second["counts"]["side_effect_key_candidates"] == 0
    assert second["counts"]["payload_candidates"] == 0
    assert second["counts"]["idempotency_record_candidates"] == 0
    assert second["updated_side_effect_key_count"] == 0
    assert second["updated_payload_count"] == 0
    assert second["inserted_idempotency_record_count"] == 0
