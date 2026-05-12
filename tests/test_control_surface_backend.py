from __future__ import annotations

import sqlite3
from pathlib import Path

from dharma_swarm.operator_core.control_surface import (
    ControlSurfaceQuery,
    build_control_surface_page,
    build_control_surface_rows,
    build_control_surface_summary,
    find_control_surface_row,
    find_evidence_ref,
)


def _seed_runtime_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE sessions (session_id TEXT PRIMARY KEY, operator_id TEXT,"
            " status TEXT, current_task_id TEXT, active_bundle_id TEXT,"
            " metadata_json TEXT, created_at TEXT, updated_at TEXT)"
        )
        db.execute(
            "INSERT INTO sessions VALUES"
            " ('s1', 'dhyana', 'active', 'task-1', '', '{}',"
            " '2026-05-12T00:00:00+00:00', '2026-05-12T00:01:00+00:00')"
        )
        db.execute(
            "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, session_id TEXT,"
            " task_id TEXT, claim_id TEXT, parent_run_id TEXT, assigned_by TEXT,"
            " assigned_to TEXT, requested_output_json TEXT, current_artifact_id TEXT,"
            " status TEXT, started_at TEXT, completed_at TEXT, failure_code TEXT,"
            " metadata_json TEXT)"
        )
        db.execute(
            "INSERT INTO delegation_runs VALUES"
            " ('run-fail', 's1', 'task-1', '', '', 'operator', 'agent', '[]', '',"
            " 'failed', '2026-05-12T00:02:00+00:00',"
            " '2026-05-12T00:03:00+00:00', 'boom', '{}')"
        )
        db.execute(
            "CREATE TABLE routing_decisions (decision_id TEXT PRIMARY KEY,"
            " action_name TEXT, route_path TEXT, selected_provider TEXT,"
            " selected_model_hint TEXT, confidence REAL, requires_human INTEGER,"
            " session_id TEXT, task_id TEXT, run_id TEXT, reasons_json TEXT,"
            " metadata_json TEXT, created_at TEXT, outcome TEXT)"
        )
        db.execute(
            "INSERT INTO routing_decisions VALUES"
            " ('rd1', 'delegate', 'operator->agent', 'codex', 'gpt', 0.8, 1,"
            " 's1', 'task-1', 'run-fail', '[]', '{}',"
            " '2026-05-12T00:04:00+00:00', 'all_failed')"
        )
        db.execute(
            "CREATE TABLE provider_attempts (decision_id TEXT, attempt_idx INTEGER,"
            " provider TEXT, model TEXT, tier TEXT, success INTEGER, outcome TEXT,"
            " error_class TEXT, error_detail TEXT, duration_ms REAL, stop_reason TEXT,"
            " usage_json TEXT, cost_estimate_usd REAL, circuit_state TEXT,"
            " schema_version TEXT, created_at TEXT)"
        )
        db.execute(
            "INSERT INTO provider_attempts VALUES"
            " ('rd1', 0, 'codex', 'gpt', 'paid', 0, 'api_error',"
            " 'timeout', 'secret detail', 12.0, '', '{}', 0.1, 'closed',"
            " 'v1', '2026-05-12T00:05:00+00:00')"
        )
        db.commit()


def test_control_surface_reads_runtime_and_telemetry_without_memory_or_writers(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_runtime_db(db_path)

    rows = build_control_surface_rows(
        repo_root=tmp_path,
        runtime_db=db_path,
        include_memory=False,
        include_writers=False,
    )

    ids = {row.id for row in rows}
    assert "runtime_session.s1" in ids
    assert "delegation_run.run-fail" in ids
    assert "routing_decision.rd1" in ids
    assert "provider_attempt.rd1.0" in ids
    failed_run = find_control_surface_row("delegation_run.run-fail", rows=rows)
    assert failed_run is not None
    assert failed_run.priority == "p0"
    assert failed_run.human_decision_required is True
    assert "run_failed" in failed_run.gap_codes


def test_control_surface_summary_counts_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_runtime_db(db_path)
    rows = build_control_surface_rows(
        repo_root=tmp_path,
        runtime_db=db_path,
        include_memory=False,
        include_writers=False,
    )

    summary = build_control_surface_summary(rows)

    assert summary["total"] == len(rows)
    assert summary["by_coherence"]["drifted"] >= 2
    assert summary["human_decision_required_count"] >= 2


def test_control_surface_page_filters_and_cursors(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_runtime_db(db_path)
    rows = build_control_surface_rows(
        repo_root=tmp_path,
        runtime_db=db_path,
        include_memory=False,
        include_writers=False,
    )

    page = build_control_surface_page(
        rows=rows,
        query=ControlSurfaceQuery(priority="p0", limit=1),
    )

    assert len(page.items) == 1
    assert page.next_cursor is not None
    next_page = build_control_surface_page(
        rows=rows,
        query=ControlSurfaceQuery(priority="p0", limit=10, cursor=page.next_cursor),
    )
    assert all(item.priority == "p0" for item in next_page.items)


def test_control_surface_evidence_lookup_is_metadata_pointer(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_runtime_db(db_path)
    rows = build_control_surface_rows(
        repo_root=tmp_path,
        runtime_db=db_path,
        include_memory=False,
        include_writers=False,
    )
    evidence_id = rows[0].evidence_refs[0].evidence_id

    evidence = find_evidence_ref(evidence_id, rows=rows)

    assert evidence is not None
    assert evidence.kind in {"db_row", "governance"}
    assert evidence.ref


def test_missing_runtime_db_becomes_source_failure_row(tmp_path: Path) -> None:
    rows = build_control_surface_rows(
        repo_root=tmp_path,
        runtime_db=tmp_path / "missing.db",
        include_memory=False,
        include_writers=False,
    )

    assert any(row.kind == "source_failure" for row in rows)
    assert any("runtime_store_missing" in row.gap_codes for row in rows)
