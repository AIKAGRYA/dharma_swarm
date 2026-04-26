from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.guardian_crew import run_ledger_watcher
from dharma_swarm.runtime_state import RuntimeStateStore


def _runtime_db(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / ".dharma"
    db_path = state_dir / "state" / "runtime.db"
    RuntimeStateStore(db_path).init_db_sync()
    return state_dir, db_path


def _seed_session_events(db_path: Path, count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
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


def _seed_structured_rows(db_path: Path) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id,"
            " status, claimed_at, retry_count, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("claim_guardian", "task_guardian", "sess_guardian", "agent_guardian", "completed", now, 0, "{}"),
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
