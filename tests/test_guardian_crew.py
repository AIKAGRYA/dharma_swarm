from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.guardian_crew import run_guardian_warning_checks, run_ledger_watcher
from dharma_swarm.runtime_state import RuntimeStateStore


def _runtime_db(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / ".dharma"
    db_path = state_dir / "state" / "runtime.db"
    RuntimeStateStore(db_path).init_db_sync()
    return state_dir, db_path


def _seed_session_events(
    db_path: Path,
    count: int,
    *,
    created_at: datetime | None = None,
) -> None:
    now = (created_at or datetime.now(timezone.utc)).isoformat()
    rows = [
        (
            f"sevt_guardian_{idx}",
            "sess_guardian",
            "progress",
            "task_progress",
            f"task_{idx}",
            "",
            "agent_guardian",
            "guardian seed",
            "guardian seed event",
            "{}",
            now,
        )
        for idx in range(count)
    ]
    with sqlite3.connect(db_path) as db:
        db.executemany(
            "INSERT INTO session_events (event_id, session_id, ledger_kind,"
            " event_name, task_id, run_id, agent_id, summary, event_text,"
            " payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        db.commit()


def _seed_structured_rows(db_path: Path, *, with_context: bool = True) -> None:
    now = datetime.now(timezone.utc).isoformat()
    metadata_json = '{"context_bundle_id": "bundle_guardian"}' if with_context else "{}"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id,"
            " status, claimed_at, retry_count, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "claim_guardian",
                "task_guardian",
                "sess_guardian",
                "agent_guardian",
                "completed",
                now,
                0,
                metadata_json,
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs (run_id, session_id, task_id, claim_id,"
            " assigned_to, status, started_at, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run_guardian",
                "sess_guardian",
                "task_guardian",
                "claim_guardian",
                "agent_guardian",
                "completed",
                now,
                metadata_json,
            ),
        )
        if with_context:
            db.execute(
                "INSERT INTO context_bundles (bundle_id, session_id, task_id,"
                " run_id, token_budget, rendered_text, sections_json,"
                " source_refs_json, checksum, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "bundle_guardian",
                    "sess_guardian",
                    "task_guardian",
                    "run_guardian",
                    200,
                    "guardian context",
                    "[]",
                    "[]",
                    "checksum",
                    now,
                    "{}",
                ),
            )
        db.execute(
            "INSERT INTO artifact_records (artifact_id, session_id, task_id,"
            " run_id, artifact_kind, payload_path, checksum, created_at, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "artifact_guardian",
                "sess_guardian",
                "task_guardian",
                "run_guardian",
                "task_result",
                "/tmp/guardian-artifact.md",
                "sha256",
                now,
                "{}",
            ),
        )
        db.commit()


def _repo_src_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    src_root = repo_root / "dharma_swarm"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    return src_root


@pytest.mark.asyncio
async def test_ledger_watcher_degraded_threshold(tmp_path: Path) -> None:
    state_dir, db_path = _runtime_db(tmp_path)
    _seed_session_events(db_path, 101)

    findings = await run_ledger_watcher(state_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "DEGRADED"
    assert finding.check == "LEDGER_WATCHER:structured_runtime_counts"
    assert "session_events=101" in finding.detail
    assert "task_claims=0" in finding.detail
    assert "delegation_runs=0" in finding.detail
    assert "artifact_records=0" in finding.detail
    assert "do not create a new ledger" in finding.fix_hint


@pytest.mark.asyncio
async def test_ledger_watcher_blocker_threshold(tmp_path: Path) -> None:
    state_dir, db_path = _runtime_db(tmp_path)
    _seed_session_events(db_path, 1001)

    findings = await run_ledger_watcher(state_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "BLOCKER"
    assert "session_events=1001" in finding.detail
    assert "Threshold > 1000" in finding.detail


@pytest.mark.asyncio
async def test_ledger_watcher_ok_when_structured_rows_exist(tmp_path: Path) -> None:
    state_dir, db_path = _runtime_db(tmp_path)
    _seed_session_events(db_path, 1001)
    _seed_structured_rows(db_path)

    findings = await run_ledger_watcher(state_dir)

    assert findings == []


@pytest.mark.asyncio
async def test_ledger_watcher_warns_on_recent_rows_without_context_bundle(tmp_path: Path) -> None:
    state_dir, db_path = _runtime_db(tmp_path)
    _seed_session_events(db_path, 3)
    _seed_structured_rows(db_path, with_context=False)

    findings = await run_ledger_watcher(state_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "WARNING"
    assert finding.check == "LEDGER_WATCHER:missing_context_bundle"
    assert "task_claims=1" in finding.detail
    assert "delegation_runs=1" in finding.detail


@pytest.mark.asyncio
async def test_ledger_watcher_warning_on_24h_delta_without_structured_rows(tmp_path: Path) -> None:
    state_dir, db_path = _runtime_db(tmp_path)
    _seed_session_events(db_path, 3)

    findings = await run_ledger_watcher(state_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "WARNING"
    assert finding.check == "LEDGER_WATCHER:delta_window"
    assert "24h deltas" in finding.detail
    assert "session_events=3" in finding.detail
    assert "task_claims=0" in finding.detail
    assert "delegation_runs=0" in finding.detail
    assert "artifact_records=0" in finding.detail


@pytest.mark.asyncio
async def test_guardian_warning_stale_repo_root_report(tmp_path: Path) -> None:
    src_root = _repo_src_root(tmp_path)
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir()
    report_path = src_root.parent / "GUARDIAN_REPORT.md"
    report_path.write_text("# old report\n", encoding="utf-8")
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
    os.utime(report_path, (old, old))

    findings = await run_guardian_warning_checks(src_root, state_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "WARNING"
    assert finding.check == "GUARDIAN_WARNINGS:stale_repo_report"
    assert "GUARDIAN_REPORT.md is stale" in finding.title
    assert "threshold: 24h" in finding.detail


@pytest.mark.asyncio
async def test_guardian_warning_unregistered_state_dir(tmp_path: Path) -> None:
    src_root = _repo_src_root(tmp_path)
    (src_root.parent / "GUARDIAN_REPORT.md").write_text("# fresh\n", encoding="utf-8")
    state_dir = tmp_path / ".dharma"
    (state_dir / "state").mkdir(parents=True)
    (state_dir / "guardian").mkdir()
    (state_dir / "novel_feature").mkdir()

    findings = await run_guardian_warning_checks(src_root, state_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "WARNING"
    assert finding.check == "GUARDIAN_WARNINGS:unregistered_state_dir"
    assert "novel_feature" in finding.detail
    assert "directories: novel_feature" in finding.detail


@pytest.mark.asyncio
async def test_guardian_warning_checks_ok_on_healthy_temp_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_root = _repo_src_root(tmp_path)
    (src_root.parent / "GUARDIAN_REPORT.md").write_text("# fresh\n", encoding="utf-8")
    state_dir = tmp_path / ".dharma"
    for name in ("state", "guardian", "logs"):
        (state_dir / name).mkdir(parents=True)

    def _fail_home(cls: type[Path]) -> Path:
        raise AssertionError("warning checks must not read live ~/.dharma")

    monkeypatch.setattr(Path, "home", classmethod(_fail_home))

    findings = await run_guardian_warning_checks(src_root, state_dir)

    assert findings == []


@pytest.mark.asyncio
async def test_ledger_watcher_does_not_consult_live_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_dir, db_path = _runtime_db(tmp_path)
    _seed_session_events(db_path, 101)

    def _fail_home(cls: type[Path]) -> Path:
        raise AssertionError("LEDGER_WATCHER must not read live ~/.dharma")

    monkeypatch.setattr(Path, "home", classmethod(_fail_home))

    findings = await run_ledger_watcher(state_dir)

    assert len(findings) == 1
    assert findings[0].severity == "DEGRADED"
