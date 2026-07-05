"""Tests for dharma_swarm.graph.reconciler -- orphaned dispatch reconciliation.

Fixture-DB style: rows are fabricated directly in a temp runtime.db, then the
reconciler runs against it and the resulting rows are asserted.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.graph.reconciler import (
    FAILURE_CODE_DIED_MID_DISPATCH,
    FAILURE_CODE_NEVER_STARTED,
    QUARANTINE_REASON,
    GraphReconciler,
    ReconcileReport,
)
from dharma_swarm.runtime_state import RuntimeStateStore

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def runtime(tmp_path: Path) -> RuntimeStateStore:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    store.init_db_sync()
    return store


def _insert_run(
    store: RuntimeStateStore,
    run_id: str,
    *,
    status: str = "running",
    claim_id: str = "",
    task_id: str = "task-1",
    receipt_json: str | None = None,
    metadata: dict | None = None,
    quarantined_at: str | None = None,
) -> None:
    with sqlite3.connect(store.db_path) as db:
        try:
            db.execute("ALTER TABLE delegation_runs ADD COLUMN quarantined_at TEXT")
            db.execute("ALTER TABLE delegation_runs ADD COLUMN quarantine_reason TEXT")
        except sqlite3.Error:
            pass
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, claim_id, assigned_to,"
            " status, started_at, metadata_json, receipt_json, quarantined_at)"
            " VALUES (?, ?, ?, 'agent-1', ?, ?, ?, ?, ?)",
            (
                run_id,
                task_id,
                claim_id,
                status,
                (NOW - timedelta(minutes=10)).isoformat(),
                json.dumps(metadata or {}),
                receipt_json,
                quarantined_at,
            ),
        )
        db.commit()


def _insert_claim(
    store: RuntimeStateStore,
    claim_id: str,
    *,
    status: str = "running",
    task_id: str = "task-1",
    acked_at: str | None = None,
    heartbeat_at: str | None = None,
    stale_after: str | None = None,
    recovered_at: str | None = None,
    retry_count: int = 0,
) -> None:
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO task_claims (claim_id, task_id, agent_id, status,"
            " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
            " retry_count) VALUES (?, ?, 'agent-1', ?, ?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                task_id,
                status,
                (NOW - timedelta(minutes=10)).isoformat(),
                acked_at,
                heartbeat_at,
                stale_after,
                recovered_at,
                retry_count,
            ),
        )
        db.commit()


def _get_run(store: RuntimeStateStore, run_id: str) -> sqlite3.Row:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT * FROM delegation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()


def _get_claim(store: RuntimeStateStore, claim_id: str) -> sqlite3.Row:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT * FROM task_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


async def test_never_started_orphan_requeued_as_claim_timeout(runtime):
    _insert_run(runtime, "run-ns", status="claimed", claim_id="claim-ns")
    _insert_claim(runtime, "claim-ns", status="claimed")

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.requeued_runs == ["run-ns"]
    run = _get_run(runtime, "run-ns")
    assert run["status"] == "failed"
    assert run["failure_code"] == FAILURE_CODE_NEVER_STARTED
    claim = _get_claim(runtime, "claim-ns")
    assert claim["status"] == "recovered"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_started_and_died_with_retries_left_requeued(runtime):
    _insert_run(runtime, "run-died", status="running", claim_id="claim-died")
    _insert_claim(
        runtime,
        "claim-died",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
        heartbeat_at=(NOW - timedelta(minutes=5)).isoformat(),
        retry_count=1,
    )

    report = await GraphReconciler(runtime, max_retries=3).reconcile(now=NOW)

    assert report.requeued_runs == ["run-died"]
    run = _get_run(runtime, "run-died")
    assert run["status"] == "failed"
    assert run["failure_code"] == FAILURE_CODE_DIED_MID_DISPATCH
    assert json.loads(run["metadata_json"])["retry_count"] == 2
    claim = _get_claim(runtime, "claim-died")
    assert claim["retry_count"] == 2
    assert claim["recovered_at"] == NOW.isoformat()


async def test_retry_exhausted_orphan_quarantined(runtime):
    _insert_run(runtime, "run-exh", status="running", claim_id="claim-exh")
    _insert_claim(
        runtime,
        "claim-exh",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
        retry_count=3,
    )

    report = await GraphReconciler(runtime, max_retries=3).reconcile(now=NOW)

    assert report.quarantined_runs == ["run-exh"]
    assert report.summary()["quarantined_runs"] == 1
    run = _get_run(runtime, "run-exh")
    assert run["status"] == "failed"
    assert run["quarantined_at"] == NOW.isoformat()
    assert run["quarantine_reason"] == QUARANTINE_REASON
    claim = _get_claim(runtime, "claim-exh")
    assert claim["recovered_at"] == NOW.isoformat()


# ---------------------------------------------------------------------------
# Torn window: receipt is ground truth
# ---------------------------------------------------------------------------


async def test_torn_window_completes_run_and_claim_from_receipt(runtime):
    receipt = json.dumps({"status": "ok", "task_id": "task-1"})
    _insert_run(
        runtime, "run-torn", status="running", claim_id="claim-torn", receipt_json=receipt
    )
    _insert_claim(
        runtime,
        "claim-torn",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == ["run-torn"]
    assert report.requeued_runs == []
    run = _get_run(runtime, "run-torn")
    assert run["status"] == "completed"
    assert run["failure_code"] == ""
    claim = _get_claim(runtime, "claim-torn")
    assert claim["status"] == "completed"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_torn_window_failed_receipt_marks_failed(runtime):
    receipt = json.dumps({"status": "error", "error_source": "provider"})
    _insert_run(
        runtime, "run-tf", status="running", claim_id="claim-tf", receipt_json=receipt
    )
    _insert_claim(
        runtime,
        "claim-tf",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == ["run-tf"]
    run = _get_run(runtime, "run-tf")
    assert run["status"] == "failed"
    assert run["failure_code"] == "provider"
    claim = _get_claim(runtime, "claim-tf")
    assert claim["status"] == "failed"
    assert claim["recovered_at"] == NOW.isoformat()


# ---------------------------------------------------------------------------
# Stale claims scan (tz-aware compare, 'Z' drift trap)
# ---------------------------------------------------------------------------


async def test_stale_claim_with_z_suffix_recovered(runtime):
    stale = (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _insert_claim(runtime, "claim-z", status="claimed", stale_after=stale)

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert "claim-z" in report.recovered_claims
    claim = _get_claim(runtime, "claim-z")
    assert claim["status"] == "recovered"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_unexpired_claim_not_recovered(runtime):
    stale = (NOW + timedelta(minutes=30)).isoformat()
    _insert_claim(runtime, "claim-fresh", status="claimed", stale_after=stale)

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.recovered_claims == []
    claim = _get_claim(runtime, "claim-fresh")
    assert claim["status"] == "claimed"
    assert claim["recovered_at"] is None


# ---------------------------------------------------------------------------
# Idempotency and live-row predicate
# ---------------------------------------------------------------------------


async def test_second_pass_is_noop(runtime):
    _insert_run(runtime, "run-once", status="claimed", claim_id="claim-once")
    _insert_claim(runtime, "claim-once", status="claimed")

    first = await GraphReconciler(runtime).reconcile(now=NOW)
    second = await GraphReconciler(runtime).reconcile(now=NOW + timedelta(minutes=1))

    assert first.total_reconciled == 1
    assert second.total_reconciled == 0
    assert second.recovered_claims == []


async def test_quarantined_and_terminal_rows_skipped(runtime):
    _insert_run(
        runtime,
        "run-q",
        status="running",
        quarantined_at=(NOW - timedelta(days=1)).isoformat(),
    )
    _insert_run(runtime, "run-done", status="completed")

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.total_reconciled == 0
    assert _get_run(runtime, "run-q")["status"] == "running"
    assert _get_run(runtime, "run-done")["status"] == "completed"


# ---------------------------------------------------------------------------
# Task board requeue wiring
# ---------------------------------------------------------------------------


class _StubBoard:
    def __init__(self) -> None:
        self.requeued: list[str] = []

    async def requeue(self, task_id: str, reason: str = "", metadata=None):
        self.requeued.append(task_id)


async def test_requeued_run_requeues_task_on_board(runtime):
    board = _StubBoard()
    _insert_run(
        runtime, "run-board", status="claimed", claim_id="claim-board", task_id="task-b"
    )
    _insert_claim(runtime, "claim-board", status="claimed", task_id="task-b")

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.requeued_runs == ["run-board"]
    assert board.requeued == ["task-b"]


# ---------------------------------------------------------------------------
# Heartbeat wiring
# ---------------------------------------------------------------------------


def test_heartbeat_live_claims_beats_due_claims(runtime):
    claimed = NOW - timedelta(minutes=10)
    stale = NOW + timedelta(minutes=20)  # window = 10 min
    _insert_claim(
        runtime,
        "claim-due",
        status="running",
        stale_after=stale.isoformat(),
        heartbeat_at=(NOW - timedelta(minutes=11)).isoformat(),
    )
    _insert_claim(
        runtime,
        "claim-recent",
        status="running",
        stale_after=stale.isoformat(),
        heartbeat_at=(NOW - timedelta(seconds=10)).isoformat(),
    )
    _insert_claim(
        runtime,
        "claim-recovered",
        status="running",
        stale_after=stale.isoformat(),
        recovered_at=NOW.isoformat(),
    )

    beaten = GraphReconciler(runtime).heartbeat_live_claims(now=NOW)

    assert beaten == 1
    due = _get_claim(runtime, "claim-due")
    assert due["heartbeat_at"] != (NOW - timedelta(minutes=11)).isoformat()
    recent = _get_claim(runtime, "claim-recent")
    assert recent["heartbeat_at"] == (NOW - timedelta(seconds=10)).isoformat()


def test_reconcile_report_summary_shape():
    report = ReconcileReport(requeued_runs=["a"], quarantined_runs=["b", "c"])
    assert report.total_reconciled == 3
    assert report.summary() == {
        "requeued_runs": 1,
        "quarantined_runs": 2,
        "completed_from_receipt": 0,
        "recovered_claims": 0,
        "errors": 0,
    }
