from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.memory_retrieval_system_gate import (
    load_isolation_proof,
    load_telemetry_health,
    score_isolation_proof,
    score_telemetry,
    split_degraded_reasons,
)


def _seed_query_log(state_dir: Path, degraded_reasons: list[str]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_dir / "vectors.db")
    try:
        conn.execute(
            """
            CREATE TABLE memory_retrieval_query_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_time TEXT,
                query_hash TEXT,
                query_preview TEXT,
                result_count INTEGER,
                total_ms REAL,
                degraded_reasons_json TEXT
            )
            """
        )
        for index, reasons in enumerate(degraded_reasons):
            conn.execute(
                "INSERT INTO memory_retrieval_query_log"
                " (query_time, query_hash, query_preview, result_count, total_ms,"
                " degraded_reasons_json) VALUES (?, ?, ?, ?, ?, ?)",
                (f"2026-07-26T00:00:0{index}", f"hash{index}", f"query {index}", 1, 12.5, reasons),
            )
        conn.commit()
    finally:
        conn.close()


def _seed_context_bundles(state_dir: Path, bundles: list[tuple[str, dict]]) -> None:
    db_dir = state_dir / "state"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "runtime.db")
    try:
        conn.execute(
            """
            CREATE TABLE context_bundles (
                bundle_id TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        for index, (bundle_id, metadata) in enumerate(bundles):
            conn.execute(
                "INSERT INTO context_bundles (bundle_id, metadata_json, created_at)"
                " VALUES (?, ?, ?)",
                (bundle_id, json.dumps(metadata), f"2026-07-26T00:00:0{index}"),
            )
        conn.commit()
    finally:
        conn.close()


def _healthy_telemetry(reason_counts: dict[str, int]) -> dict:
    return {
        "table_exists": True,
        "new_rows": 4,
        "missing_core_fields": 0,
        "empty_result_rows": 0,
        "degraded_rows": sum(reason_counts.values()),
        "degraded_reason_counts": reason_counts,
        "p95_total_ms": 120.0,
        "max_total_ms": 200.0,
    }


def test_load_telemetry_health_counts_reasons_per_reason(tmp_path: Path) -> None:
    _seed_query_log(
        tmp_path,
        ['["fts_guard_blocked"]', '["fts_guard_blocked", "vector_backend_down"]', "[]"],
    )

    health = load_telemetry_health(tmp_path, after_id=0)

    assert health["degraded_rows"] == 2
    assert health["degraded_reason_counts"] == {
        "fts_guard_blocked": 2,
        "vector_backend_down": 1,
    }


def test_load_telemetry_health_unparseable_reasons_become_new_reason(tmp_path: Path) -> None:
    _seed_query_log(tmp_path, ["{not json"])

    health = load_telemetry_health(tmp_path, after_id=0)

    assert health["degraded_reason_counts"] == {"_unparseable_degraded_reasons": 1}


def test_split_degraded_reasons_ratchets_known_and_fails_new() -> None:
    warnings, hard_fails = split_degraded_reasons(
        {"fts_guard_blocked": 31571, "embedding_timeout": 2},
        today="2026-07-26",
    )

    assert "fts_guard_blocked" in warnings
    assert warnings["fts_guard_blocked"]["count"] == 31571
    assert warnings["fts_guard_blocked"]["declared"] == "2026-07-25"
    assert hard_fails == {"embedding_timeout": 2}


def test_split_degraded_reasons_flip_date_arms_hard_fail(monkeypatch) -> None:
    from scripts import memory_retrieval_system_gate as gate

    monkeypatch.setitem(
        gate.RATCHETED_DEGRADED_REASONS,
        "fts_guard_blocked",
        {"declared": "2026-07-25", "flip_after": "2026-08-01"},
    )

    warnings, hard_fails = split_degraded_reasons({"fts_guard_blocked": 3}, today="2026-08-01")

    assert warnings == {}
    assert hard_fails == {"fts_guard_blocked": 3}


def test_score_telemetry_warns_but_passes_on_ratcheted_reason() -> None:
    check = score_telemetry(
        _healthy_telemetry({"fts_guard_blocked": 4}),
        expected_min_logs=4,
        max_score=10.0,
    )

    assert check.passed
    assert not check.hard_fail
    assert check.score == 10.0
    assert "fts_guard_blocked" in check.details["ratchet_warnings"]
    assert check.details["new_degraded_reasons"] == {}


def test_score_telemetry_hard_fails_on_new_degraded_reason() -> None:
    check = score_telemetry(
        _healthy_telemetry({"vector_backend_down": 1}),
        expected_min_logs=4,
        max_score=10.0,
    )

    assert not check.passed
    assert check.hard_fail
    assert check.score == 0.0
    assert check.details["new_degraded_reasons"] == {"vector_backend_down": 1}
    assert "telemetry_new_degraded_reasons" in check.details["check_ids"]


def test_isolation_proof_warns_when_uninstrumented(tmp_path: Path) -> None:
    _seed_context_bundles(tmp_path, [("b1", {"other": True}), ("b2", {})])

    check = score_isolation_proof(load_isolation_proof(tmp_path))

    assert check.passed
    assert not check.hard_fail
    assert check.details["warning"] is True
    assert check.details["legacy_rows"] == 2
    assert check.details["check_id"] == "isolation_applied_ratchet"


def test_isolation_proof_missing_db_is_warning(tmp_path: Path) -> None:
    check = score_isolation_proof(load_isolation_proof(tmp_path))

    assert check.passed
    assert not check.hard_fail


def test_isolation_proof_hard_fails_on_unisolated_worker_bundle(tmp_path: Path) -> None:
    _seed_context_bundles(
        tmp_path,
        [
            (
                "good",
                {
                    "memory_kernel_default": {
                        "isolation_applied": True,
                        "isolation_topology": "fan_out",
                    }
                },
            ),
            (
                "bad",
                {
                    "memory_kernel_default": {
                        "isolation_applied": False,
                        "isolation_topology": "fan_out",
                    }
                },
            ),
        ],
    )

    check = score_isolation_proof(load_isolation_proof(tmp_path))

    assert not check.passed
    assert check.hard_fail
    assert check.details["violations"] == 1
    assert check.details["violation_bundles"] == ["bad"]


def test_isolation_proof_passes_when_workers_isolated(tmp_path: Path) -> None:
    _seed_context_bundles(
        tmp_path,
        [
            (
                "b1",
                {
                    "memory_kernel_default": {
                        "isolation_applied": True,
                        "isolation_topology": "swarm",
                    }
                },
            ),
            (
                "single",
                {
                    "memory_kernel_default": {
                        "isolation_applied": False,
                        "isolation_topology": "single",
                    }
                },
            ),
        ],
    )

    check = score_isolation_proof(load_isolation_proof(tmp_path))

    assert check.passed
    assert not check.hard_fail
    assert check.details["worker_rows"] == 1
    assert check.details["worker_applied_rows"] == 1
