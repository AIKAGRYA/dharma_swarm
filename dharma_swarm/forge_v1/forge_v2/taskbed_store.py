"""SQLite taskbed storage and registration primitives."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable, Literal

from dharma_swarm.daemon_config import dharma_state_dir

DEFAULT_DB = dharma_state_dir() / "forge_v1" / "taskbed.db"
DEFAULT_QUALITY_ROOT = dharma_state_dir() / "forge_v1" / "taskbed_quality"
DEFAULT_GRADE_RECEIPT_ROOTS = (
    dharma_state_dir() / "forge_v1" / "task_harvests" / "pr_suite_grade_receipts",
    dharma_state_dir() / "forge_v1" / "native_runner" / "synced_receipts",
)
MIN_CONFIRM_TASKS = 500
LEGACY_CONTAMINATION_STATE_MAP = {
    "fresh_heldout": "fresh_post_cutoff",
    "self_mod_clean": "fresh_private_local_generated",
}
CLEAN_CONFIRM_STATES = frozenset({"fresh_post_cutoff", "fresh_private_local_generated"})
SplitName = Literal["explore", "confirm"]


class TaskbedLedgerError(RuntimeError):
    """Raised when the taskbed ledger cannot satisfy a safe allocation."""


def utc_seconds() -> float:
    return time.time()


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS taskbed_tasks (
          task_id TEXT PRIMARY KEY,
          task_json TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT '',
          taskbed TEXT NOT NULL DEFAULT '',
          contamination_state TEXT NOT NULL,
          provenance_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT '',
          first_seen_at REAL NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          max_uses_per_epoch INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS taskbed_allocations (
          allocation_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          split TEXT NOT NULL CHECK(split IN ('explore', 'confirm')),
          epoch_id TEXT NOT NULL,
          lane_id TEXT NOT NULL DEFAULT '',
          candidate_id TEXT NOT NULL DEFAULT '',
          allocated_at REAL NOT NULL,
          status TEXT NOT NULL DEFAULT 'allocated',
          PRIMARY KEY (allocation_id, task_id),
          FOREIGN KEY(task_id) REFERENCES taskbed_tasks(task_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_taskbed_alloc_task_split "
        "ON taskbed_allocations(task_id, split)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_taskbed_alloc_epoch_task "
        "ON taskbed_allocations(epoch_id, task_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_taskbed_tasks_active_state "
        "ON taskbed_tasks(active, contamination_state, task_id)"
    )
    conn.execute(
        "UPDATE taskbed_tasks SET contamination_state = ? WHERE contamination_state = ?",
        ("fresh_post_cutoff", "fresh_heldout"),
    )
    conn.execute(
        "UPDATE taskbed_tasks SET contamination_state = ? WHERE contamination_state = ?",
        ("fresh_private_local_generated", "self_mod_clean"),
    )
    conn.commit()


def normalize_contamination_state(contamination_state: str) -> str:
    state = str(contamination_state or "possible_pretrain").strip() or "possible_pretrain"
    if state == "clean":
        raise TaskbedLedgerError("contamination_state 'clean' is caller-asserted and not accepted")
    return LEGACY_CONTAMINATION_STATE_MAP.get(state, state)


def register_task(
    task: dict[str, Any],
    *,
    db_path: Path | str = DEFAULT_DB,
    task_id: str | None = None,
    source: str = "",
    taskbed: str = "",
    contamination_state: str = "possible_pretrain",
    provenance: dict[str, Any] | None = None,
    created_at: str = "",
    active: bool = True,
    max_uses_per_epoch: int = 1,
    now: float | None = None,
) -> str:
    task_id = str(task_id or task.get("task_id") or task.get("instance_id") or "").strip()
    if not task_id:
        raise ValueError("task must include task_id or instance_id")
    contamination_state = normalize_contamination_state(contamination_state)
    ts = utc_seconds() if now is None else now
    payload = dict(task)
    payload.setdefault("task_id", task_id)
    with closing(connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO taskbed_tasks (
                  task_id, task_json, source, taskbed, contamination_state,
                  provenance_json, created_at, first_seen_at, active,
                  max_uses_per_epoch
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  task_json=excluded.task_json,
                  source=excluded.source,
                  taskbed=excluded.taskbed,
                  contamination_state=excluded.contamination_state,
                  provenance_json=excluded.provenance_json,
                  created_at=excluded.created_at,
                  active=excluded.active,
                  max_uses_per_epoch=excluded.max_uses_per_epoch
                """,
                (
                    task_id,
                    json.dumps(payload, sort_keys=True),
                    source,
                    taskbed,
                    contamination_state,
                    json.dumps(provenance or {}, sort_keys=True),
                    created_at,
                    ts,
                    int(active),
                    max(1, int(max_uses_per_epoch)),
                ),
            )
    return task_id


def register_tasks(
    tasks: Iterable[dict[str, Any]],
    *,
    db_path: Path | str = DEFAULT_DB,
    source: str = "",
    taskbed: str = "",
    contamination_state: str = "possible_pretrain",
    max_uses_per_epoch: int = 1,
    now: float | None = None,
) -> list[str]:
    return [
        register_task(
            task,
            db_path=db_path,
            source=source,
            taskbed=taskbed,
            contamination_state=str(task.get("contamination_state") or contamination_state),
            provenance=dict(task.get("provenance") or {}),
            created_at=str(task.get("created_at") or ""),
            max_uses_per_epoch=int(task.get("max_uses_per_epoch") or max_uses_per_epoch),
            now=now,
        )
        for task in tasks
    ]
