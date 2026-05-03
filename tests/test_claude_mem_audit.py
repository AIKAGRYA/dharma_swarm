"""Tests for read-only claude-mem audit utilities."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dharma_swarm.claude_mem_audit import (
    queue_lag,
    render_doctor,
    sample_audit_packet,
    score_packet,
)


def _build_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_session_id TEXT,
            project TEXT NOT NULL,
            text TEXT,
            type TEXT,
            title TEXT,
            subtitle TEXT,
            facts TEXT,
            narrative TEXT,
            concepts TEXT,
            files_read TEXT,
            files_modified TEXT,
            prompt_number INTEGER,
            discovery_tokens INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );
        CREATE TABLE session_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_session_id TEXT,
            project TEXT NOT NULL,
            request TEXT,
            investigated TEXT,
            learned TEXT,
            completed TEXT,
            next_steps TEXT,
            notes TEXT,
            prompt_number INTEGER,
            discovery_tokens INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );
        CREATE TABLE sdk_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_session_id TEXT,
            memory_session_id TEXT,
            project TEXT NOT NULL,
            platform_source TEXT,
            started_at TEXT NOT NULL,
            started_at_epoch INTEGER NOT NULL,
            status TEXT
        );
        CREATE TABLE user_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_session_id TEXT,
            prompt TEXT,
            created_at TEXT,
            created_at_epoch INTEGER
        );
        CREATE TABLE pending_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_db_id INTEGER NOT NULL,
            content_session_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );
        """
    )
    for idx in range(40):
        text = "Architecture correction recorded" if idx % 9 == 0 else "Regular observation"
        conn.execute(
            """
            INSERT INTO observations
            (memory_session_id, project, text, type, title, subtitle, facts, narrative,
             concepts, files_read, files_modified, prompt_number, created_at, created_at_epoch)
            VALUES (?, 'dhyana', ?, 'discovery', ?, '', ?, ?, '', '', '', ?, ?, ?)
            """,
            (
                f"mem-{idx}",
                text,
                f"Observation {idx}",
                text,
                f"Narrative {idx} architecture",
                idx,
                f"2026-05-03T00:{idx:02d}:00Z",
                1_777_800_000_000 + idx,
            ),
        )
    for idx in range(3):
        conn.execute(
            """
            INSERT INTO session_summaries
            (memory_session_id, project, request, investigated, learned, completed,
             next_steps, notes, prompt_number, created_at, created_at_epoch)
            VALUES (?, 'dhyana', ?, 'investigated', 'learned', 'completed',
                    'next', 'notes', ?, ?, ?)
            """,
            (
                f"sum-{idx}",
                f"Request {idx}",
                idx,
                f"2026-05-03T01:{idx:02d}:00Z",
                1_777_800_100_000 + idx,
            ),
        )
    conn.execute(
        """
        INSERT INTO pending_messages
        (session_db_id, content_session_id, message_type, status, created_at_epoch)
        VALUES (1, 's1', 'observation', 'pending', 1777800000000)
        """
    )
    conn.execute(
        """
        INSERT INTO pending_messages
        (session_db_id, content_session_id, message_type, status, created_at_epoch)
        VALUES (1, 's1', 'summarize', 'failed', 1777700000000)
        """
    )
    conn.commit()
    conn.close()
    return path


def test_queue_lag_separates_active_and_failed(tmp_path: Path) -> None:
    db = _build_db(tmp_path / "claude-mem.db")
    lag = queue_lag(db, now_ms=1_777_900_000_000)
    assert lag.total_messages == 2
    assert lag.active_pending == 1
    assert lag.failed == 1
    assert lag.oldest_active_age_hours is not None


def test_sample_audit_packet_has_stratified_unreviewed_samples(tmp_path: Path) -> None:
    db = _build_db(tmp_path / "claude-mem.db")
    packet = sample_audit_packet(db, project="dhyana", seed=1, target=35)
    buckets = {sample["bucket"] for sample in packet["samples"]}
    assert "recent_observations" in buckets
    assert "older_observations" in buckets
    assert "corrections_reversals" in buckets
    assert "session_summaries" in buckets
    assert len(packet["samples"]) >= 35
    assert all(sample["label"] == "unreviewed" for sample in packet["samples"])
    assert packet["queue_lag"]["active_pending"] == 1


def test_score_packet_computes_falsehood_rate() -> None:
    packet = {
        "samples": [
            {"label": "true"},
            {"label": "mostly_true"},
            {"label": "false"},
            {"label": "unreviewed"},
            {"label": "stale_but_once_true"},
        ]
    }
    score = score_packet(packet)
    assert score["reviewed_samples"] == 4
    assert score["falsehood_rate"] == 0.25
    assert score["stale_rate"] == 0.25


def test_doctor_reports_queue_and_summary(tmp_path: Path) -> None:
    db = _build_db(tmp_path / "claude-mem.db")
    text = render_doctor(db, project="dhyana")
    assert "Claude-Mem Doctor" in text
    assert "Active pending/processing: 1" in text
    assert "Latest dhyana summary:" in text


def test_cli_score_outputs_json(tmp_path: Path, capsys) -> None:
    from dharma_swarm.claude_mem_audit import main

    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({"samples": [{"label": "false"}]}), encoding="utf-8")
    rc = main(["score", "--input", str(packet)])
    assert rc == 0
    assert '"falsehood_rate": 1.0' in capsys.readouterr().out
