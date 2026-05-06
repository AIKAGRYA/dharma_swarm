"""Tests for dharma_swarm.kaizen_ops_local — SQLite-backed operational telemetry.

Validates:
- KaizenOpsLocal construction and schema creation
- ingest_event: generic event recording
- ingest_cron_result: new job + upsert + failure tracking
- stale_cron_jobs: age-based detection
- failing_cron_jobs: consecutive failure detection
- cron_health_summary: aggregation
- ingest_scout_report: new + upsert
- system_health: composite score and grading
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.kaizen_ops_local import KaizenOpsLocal


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_creates_db(self, tmp_path):
        db = tmp_path / "test.db"
        ops = KaizenOpsLocal(db_path=db)
        assert db.exists()
        ops.close()

    def test_schema_tables(self, tmp_path):
        db = tmp_path / "test.db"
        ops = KaizenOpsLocal(db_path=db)
        conn = ops._get_conn()
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "events" in tables
        assert "cron_health" in tables
        assert "scout_health" in tables
        ops.close()


# ---------------------------------------------------------------------------
# ingest_event
# ---------------------------------------------------------------------------


class TestIngestEvent:
    def test_basic_event(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_event("test", "unit_test", status="ok", duration_sec=1.5)
        conn = ops._get_conn()
        count = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
        assert count == 1
        ops.close()

    def test_with_metadata(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_event("deploy", "ci", metadata={"branch": "main"})
        conn = ops._get_conn()
        row = conn.execute("SELECT metadata FROM events").fetchone()
        import json
        data = json.loads(row["metadata"])
        assert data["branch"] == "main"
        ops.close()


# ---------------------------------------------------------------------------
# ingest_cron_result
# ---------------------------------------------------------------------------


class TestIngestCronResult:
    def test_new_job(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_cron_result("pulse", "completed", job_name="Pulse Check")
        conn = ops._get_conn()
        row = conn.execute("SELECT * FROM cron_health WHERE job_id='pulse'").fetchone()
        assert row["last_status"] == "completed"
        assert row["consecutive_failures"] == 0
        assert row["total_runs"] == 1
        ops.close()

    def test_failure_tracking(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_cron_result("pulse", "completed", job_name="Pulse")
        ops.ingest_cron_result("pulse", "failed", job_name="Pulse", error="timeout")
        ops.ingest_cron_result("pulse", "failed", job_name="Pulse", error="timeout again")
        conn = ops._get_conn()
        row = conn.execute("SELECT * FROM cron_health WHERE job_id='pulse'").fetchone()
        assert row["consecutive_failures"] == 2
        assert row["total_runs"] == 3
        assert row["total_failures"] == 2
        ops.close()

    def test_failure_reset_on_success(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_cron_result("pulse", "failed", job_name="Pulse")
        ops.ingest_cron_result("pulse", "failed", job_name="Pulse")
        ops.ingest_cron_result("pulse", "completed", job_name="Pulse")
        conn = ops._get_conn()
        row = conn.execute("SELECT * FROM cron_health WHERE job_id='pulse'").fetchone()
        assert row["consecutive_failures"] == 0
        ops.close()


# ---------------------------------------------------------------------------
# stale_cron_jobs / failing_cron_jobs
# ---------------------------------------------------------------------------


class TestCronQueries:
    def test_stale_detection(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_cron_result("fresh", "completed")
        # All jobs just ran, so none should be stale with a large window
        stale = ops.stale_cron_jobs(max_age_hours=24)
        assert len(stale) == 0
        ops.close()

    def test_failing_detection(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_cron_result("bad", "failed", job_name="Bad")
        ops.ingest_cron_result("bad", "failed", job_name="Bad")
        ops.ingest_cron_result("good", "completed", job_name="Good")
        failing = ops.failing_cron_jobs(min_consecutive=2)
        assert len(failing) == 1
        assert failing[0]["job_id"] == "bad"
        ops.close()


# ---------------------------------------------------------------------------
# cron_health_summary
# ---------------------------------------------------------------------------


class TestCronHealthSummary:
    def test_empty(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        summary = ops.cron_health_summary()
        assert summary["total_jobs"] == 0
        assert summary["health_pct"] == 0.0
        ops.close()

    def test_mixed(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_cron_result("a", "completed", job_name="A")
        ops.ingest_cron_result("b", "failed", job_name="B")
        ops.ingest_cron_result("b", "failed", job_name="B")
        summary = ops.cron_health_summary()
        assert summary["total_jobs"] == 2
        assert summary["healthy"] == 1
        assert summary["failing"] == 1
        ops.close()


# ---------------------------------------------------------------------------
# ingest_scout_report
# ---------------------------------------------------------------------------


class TestIngestScoutReport:
    def test_new_domain(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_scout_report("architecture", 5, 1, 3)
        conn = ops._get_conn()
        row = conn.execute("SELECT * FROM scout_health WHERE domain='architecture'").fetchone()
        assert row["last_finding_count"] == 5
        assert row["last_critical_count"] == 1
        assert row["total_runs"] == 1
        ops.close()

    def test_upsert(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_scout_report("tests", 3, 0, 2)
        ops.ingest_scout_report("tests", 7, 2, 5)
        conn = ops._get_conn()
        row = conn.execute("SELECT * FROM scout_health WHERE domain='tests'").fetchone()
        assert row["last_finding_count"] == 7
        assert row["total_runs"] == 2
        ops.close()


# ---------------------------------------------------------------------------
# system_health
# ---------------------------------------------------------------------------


class TestSystemHealth:
    def test_perfect_score(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        health = ops.system_health()
        assert health["score"] == 100.0
        assert health["grade"] == "A"
        ops.close()

    def test_degraded_score(self, tmp_path):
        ops = KaizenOpsLocal(db_path=tmp_path / "test.db")
        ops.ingest_scout_report("security", 3, 2, 1)
        health = ops.system_health()
        assert health["score"] < 100.0
        assert health["scouts"]["with_criticals"] == 1
        ops.close()
