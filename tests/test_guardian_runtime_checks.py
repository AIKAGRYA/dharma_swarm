"""Tests for dharma_swarm.guardian_runtime_checks — runtime warning probes.

Validates:
- run_guardian_warning_checks: stale report detection, unregistered state dirs
- runtime_context_bundle_injection_findings: context bundle security scanning
- runtime_rows_missing_context: missing context bundle counts
- runtime_context_status_counts: unhealthy status aggregation
- Helper functions: _runtime_table_names, _runtime_table_columns, _json_load
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from dharma_swarm.guardian_runtime_checks import (
    GuardianRuntimeFinding,
    run_guardian_warning_checks,
    runtime_context_bundle_injection_findings,
    runtime_rows_missing_context,
    runtime_context_status_counts,
    _REGISTERED_DHARMA_TOP_LEVEL_DIRS,
)


# ---------------------------------------------------------------------------
# GuardianRuntimeFinding model
# ---------------------------------------------------------------------------


class TestGuardianRuntimeFinding:
    def test_construction(self):
        f = GuardianRuntimeFinding(
            severity="WARNING",
            check="test_check",
            title="Test",
            detail="Details here",
        )
        assert f.severity == "WARNING"
        assert f.file == ""
        assert f.line == 0

    def test_with_file_and_line(self):
        f = GuardianRuntimeFinding(
            severity="BLOCKER",
            check="mm02",
            title="Enum coercion",
            detail="Bare string",
            file="orchestrate_live.py",
            line=1247,
            fix_hint="Use AgentRole()",
        )
        assert f.file == "orchestrate_live.py"
        assert f.line == 1247


# ---------------------------------------------------------------------------
# run_guardian_warning_checks
# ---------------------------------------------------------------------------


class TestGuardianWarningChecks:
    async def test_no_findings_on_clean_state(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        findings = await run_guardian_warning_checks(src_root, state_dir)
        assert findings == []

    async def test_stale_report_detected(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        report = tmp_path / "GUARDIAN_REPORT.md"
        report.write_text("# Old report")
        old_time = time.time() - 48 * 3600
        import os
        os.utime(str(report), (old_time, old_time))

        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()

        findings = await run_guardian_warning_checks(src_root, state_dir)
        stale = [f for f in findings if "stale" in f.title.lower()]
        assert len(stale) == 1
        assert stale[0].severity == "WARNING"

    async def test_fresh_report_no_finding(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        report = tmp_path / "GUARDIAN_REPORT.md"
        report.write_text("# Fresh report")

        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()

        findings = await run_guardian_warning_checks(src_root, state_dir)
        stale = [f for f in findings if "stale" in f.title.lower()]
        assert len(stale) == 0

    async def test_unregistered_state_dir_detected(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "unknown_dir").mkdir()

        findings = await run_guardian_warning_checks(src_root, state_dir)
        unreg = [f for f in findings if "unregistered" in f.title.lower()]
        assert len(unreg) == 1
        assert "unknown_dir" in unreg[0].detail

    async def test_registered_dirs_not_flagged(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        for name in ["evolution", "memory", "witness"]:
            (state_dir / name).mkdir()

        findings = await run_guardian_warning_checks(src_root, state_dir)
        unreg = [f for f in findings if "unregistered" in f.title.lower()]
        assert len(unreg) == 0

    async def test_hidden_dirs_ignored(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / ".hidden").mkdir()

        findings = await run_guardian_warning_checks(src_root, state_dir)
        unreg = [f for f in findings if "unregistered" in f.title.lower()]
        assert len(unreg) == 0

    async def test_nonexistent_state_dir_no_crash(self, tmp_path):
        src_root = tmp_path / "dharma_swarm"
        src_root.mkdir()
        (src_root / "__init__.py").write_text("")
        state_dir = tmp_path / "nonexistent"

        findings = await run_guardian_warning_checks(src_root, state_dir)
        assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# Registered dirs completeness
# ---------------------------------------------------------------------------


class TestRegisteredDirs:
    def test_known_dirs_present(self):
        expected = {"evolution", "memory", "witness", "stigmergy", "guardian", "tasks"}
        assert expected <= _REGISTERED_DHARMA_TOP_LEVEL_DIRS

    def test_all_entries_lowercase(self):
        for d in _REGISTERED_DHARMA_TOP_LEVEL_DIRS:
            assert d == d.lower(), f"Entry {d!r} not lowercase"


# ---------------------------------------------------------------------------
# runtime_context_bundle_injection_findings
# ---------------------------------------------------------------------------


class TestContextBundleInjectionFindings:
    def _create_db_with_context_bundles(self, db: sqlite3.Connection) -> None:
        db.execute("""
            CREATE TABLE context_bundles (
                bundle_id TEXT PRIMARY KEY,
                rendered_text TEXT,
                metadata_json TEXT,
                created_at TEXT,
                run_id TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                task_id TEXT DEFAULT ''
            )
        """)
        db.commit()

    def test_no_table_returns_empty(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        result = runtime_context_bundle_injection_findings(
            db, datetime.now(timezone.utc).isoformat()
        )
        assert result == []
        db.close()

    def test_empty_table_returns_empty(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        self._create_db_with_context_bundles(db)
        result = runtime_context_bundle_injection_findings(
            db, "2020-01-01T00:00:00"
        )
        assert result == []
        db.close()

    def test_blocked_metadata_detected(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        self._create_db_with_context_bundles(db)
        metadata = json.dumps({
            "context_scan": {"status": "blocked", "findings": ["injection detected"]}
        })
        db.execute(
            "INSERT INTO context_bundles (bundle_id, rendered_text, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("b1", "some text", metadata, "2026-01-01T00:00:00"),
        )
        db.commit()
        result = runtime_context_bundle_injection_findings(db, "2020-01-01T00:00:00")
        assert len(result) == 1
        assert result[0][0] == "b1"
        db.close()


# ---------------------------------------------------------------------------
# runtime_rows_missing_context
# ---------------------------------------------------------------------------


class TestRuntimeRowsMissingContext:
    def test_no_tables_returns_zero(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        count = runtime_rows_missing_context(
            db, "task_claims", "claimed_at", "2020-01-01"
        )
        assert count == 0
        db.close()

    def test_unsupported_table_returns_zero(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE some_other (id TEXT)")
        db.execute("CREATE TABLE context_bundles (bundle_id TEXT)")
        db.commit()
        count = runtime_rows_missing_context(
            db, "some_other", "created_at", "2020-01-01"
        )
        assert count == 0
        db.close()


# ---------------------------------------------------------------------------
# runtime_context_status_counts
# ---------------------------------------------------------------------------


class TestRuntimeContextStatusCounts:
    def test_no_tables_returns_empty(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        counts = runtime_context_status_counts(db, "2020-01-01")
        assert counts == {}
        db.close()

    def test_counts_unhealthy_statuses(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / "test.db"))
        db.execute("""
            CREATE TABLE task_claims (
                claim_id TEXT,
                claimed_at TEXT,
                metadata_json TEXT,
                status TEXT DEFAULT 'claimed',
                session_id TEXT DEFAULT '',
                task_id TEXT DEFAULT ''
            )
        """)
        for i, status in enumerate(["failed", "failed", "missing_runtime_state"]):
            metadata = json.dumps({"context_bundle_status": status})
            db.execute(
                "INSERT INTO task_claims (claim_id, claimed_at, metadata_json) VALUES (?, ?, ?)",
                (f"c{i}", "2026-01-01T00:00:00", metadata),
            )
        db.commit()
        counts = runtime_context_status_counts(db, "2020-01-01")
        assert counts.get("failed", 0) == 2
        assert counts.get("missing_runtime_state", 0) == 1
        db.close()
