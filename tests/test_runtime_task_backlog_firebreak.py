from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def _load_firebreak_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "runtime_task_backlog_firebreak.py"
    )
    spec = importlib.util.spec_from_file_location(
        "runtime_task_backlog_firebreak",
        script_path,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_tasks_db(
    state_root: Path,
    rows: list[tuple[str, str, str, str, str, str, dict]],
) -> None:
    db_path = state_root / "db" / "tasks.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT NOT NULL DEFAULT 'normal',
                assigned_to TEXT,
                created_by TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                trace_id TEXT NOT NULL DEFAULT ''
            )
            """
        )
        for row in rows:
            (
                task_id,
                title,
                status,
                priority,
                created_by,
                created_at,
                metadata,
            ) = row
            db.execute(
                """
                INSERT INTO tasks (
                    id, title, status, priority, created_by,
                    created_at, updated_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    title,
                    status,
                    priority,
                    created_by,
                    created_at,
                    created_at,
                    json.dumps(metadata),
                ),
            )


def _task_statuses(state_root: Path) -> dict[str, str]:
    with sqlite3.connect(state_root / "db" / "tasks.db") as db:
        return dict(db.execute("SELECT id, status FROM tasks").fetchall())


def test_firebreak_dry_run_simulates_safe_backlog_without_mutating(
    tmp_path: Path,
) -> None:
    module = _load_firebreak_module()
    state_root = tmp_path / ".dharma"
    old = "2026-06-18T00:00:00+00:00"
    recent = "2026-06-18T18:30:00+00:00"
    rows = [
        (
            f"old-high-{index}",
            "old high",
            "pending",
            "high",
            "system",
            old,
            {},
        )
        for index in range(30)
    ]
    rows.extend(
        [
            ("old-low", "eval_probe_task", "pending", "low", "eval_harness", old, {}),
            (
                "recent-high",
                "recent high",
                "pending",
                "high",
                "system",
                recent,
                {},
            ),
        ]
    )
    _write_tasks_db(state_root, rows)

    report = module.build_firebreak_report(
        state_root=state_root,
        apply=False,
        allow_unpaused_apply=False,
        max_pending_age_hours=4.0,
        max_running_age_hours=6.0,
        max_pending_high=25,
        max_pending_total=100,
        max_running=25,
        limit=0,
        reason="test",
    )

    assert report["status"] == "pass"
    assert report["candidate_count"] == 31
    assert report["simulated_after_safe"] is True
    assert report["simulated_after"]["pending_high_or_urgent"] == 1
    assert _task_statuses(state_root)["old-high-0"] == "pending"


def test_firebreak_apply_requires_pause_file(tmp_path: Path) -> None:
    module = _load_firebreak_module()
    state_root = tmp_path / ".dharma"
    old = "2026-06-18T00:00:00+00:00"
    _write_tasks_db(
        state_root,
        [("old-high", "old high", "pending", "high", "system", old, {})],
    )

    report = module.build_firebreak_report(
        state_root=state_root,
        apply=True,
        allow_unpaused_apply=False,
        max_pending_age_hours=4.0,
        max_running_age_hours=6.0,
        max_pending_high=25,
        max_pending_total=100,
        max_running=25,
        limit=0,
        reason="test",
    )

    assert report["status"] == "fail"
    assert report["apply_error"] == "apply_requires_pause_file_or_allow_unpaused_apply"
    assert _task_statuses(state_root)["old-high"] == "pending"


def test_firebreak_apply_cancels_candidates_and_marks_metadata(
    tmp_path: Path,
) -> None:
    module = _load_firebreak_module()
    state_root = tmp_path / ".dharma"
    (state_root / ".PAUSE").parent.mkdir(parents=True, exist_ok=True)
    (state_root / ".PAUSE").write_text("paused\n", encoding="utf-8")
    old = "2026-06-18T00:00:00+00:00"
    _write_tasks_db(
        state_root,
        [
            (
                "runaway",
                "[internal_maintenance] Repair: High gate block rate (S3->S4 channel)",
                "pending",
                "high",
                "frontier_refill",
                old,
                {"source": "frontier_refill"},
            )
        ],
    )

    report = module.build_firebreak_report(
        state_root=state_root,
        apply=True,
        allow_unpaused_apply=False,
        max_pending_age_hours=4.0,
        max_running_age_hours=6.0,
        max_pending_high=25,
        max_pending_total=100,
        max_running=25,
        limit=0,
        reason="test",
    )

    assert report["status"] == "pass"
    assert report["applied_count"] == 1
    with sqlite3.connect(state_root / "db" / "tasks.db") as db:
        status, metadata_text = db.execute(
            "SELECT status, metadata FROM tasks WHERE id = 'runaway'",
        ).fetchone()
    metadata = json.loads(metadata_text)
    assert status == "cancelled"
    assert metadata["runtime_task_backlog_firebreak"]["receipt_id"] == report["receipt_id"]
    assert (
        metadata["runtime_task_backlog_firebreak"]["selection_reason"]
        == "runaway_frontier_refill_high_gate_loop"
    )
