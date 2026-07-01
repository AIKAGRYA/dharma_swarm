"""Durable taskbed ledger for RSI Lab EXPLORE/CONFIRM allocation.

Promotion needs a full paired CONFIRM corpus that is not a split of the same
campaign and was never exposed through EXPLORE.  This module is the allocation
authority for that invariant.  It records task provenance and split allocation
decisions in SQLite; it does not grade tasks or decide promotion.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable, Literal

from dharma_swarm.daemon_config import dharma_state_dir

DEFAULT_DB = dharma_state_dir() / "forge_v1" / "taskbed.db"
MIN_CONFIRM_TASKS = 500
CLEAN_CONFIRM_STATES = frozenset({"fresh_heldout", "self_mod_clean", "clean"})
SplitName = Literal["explore", "confirm"]


class TaskbedLedgerError(RuntimeError):
    """Raised when the taskbed ledger cannot satisfy a safe allocation."""


def utc_seconds() -> float:
    return time.time()


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
    conn.commit()


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


def _eligible_rows(
    conn: sqlite3.Connection,
    *,
    split: SplitName,
    epoch_id: str,
    limit: int,
) -> list[sqlite3.Row]:
    opposite = "confirm" if split == "explore" else "explore"
    clean_filter = ""
    params: list[Any] = []
    if split == "confirm":
        clean_filter = (
            "AND t.contamination_state IN ({})".format(
                ",".join("?" for _ in sorted(CLEAN_CONFIRM_STATES))
            )
        )
        params.extend(sorted(CLEAN_CONFIRM_STATES))
    params.extend([opposite, epoch_id])
    params.append(limit)
    return conn.execute(
        f"""
        SELECT t.*
          FROM taskbed_tasks t
         WHERE t.active=1
           {clean_filter}
           AND NOT EXISTS (
             SELECT 1
               FROM taskbed_allocations prior
              WHERE prior.task_id=t.task_id
                AND prior.split=?
           )
           AND (
             SELECT COUNT(*)
               FROM taskbed_allocations used
              WHERE used.task_id=t.task_id
                AND used.epoch_id=?
                AND used.status='allocated'
           ) < t.max_uses_per_epoch
         ORDER BY t.created_at ASC, t.first_seen_at ASC, t.task_id ASC
         LIMIT ?
        """,
        params,
    ).fetchall()


def allocate_tasks(
    *,
    split: SplitName,
    count: int,
    epoch_id: str,
    lane_id: str,
    db_path: Path | str = DEFAULT_DB,
    allocation_id: str | None = None,
    candidate_id: str = "",
    min_count: int | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if split not in {"explore", "confirm"}:
        raise ValueError("split must be explore or confirm")
    if count <= 0:
        raise ValueError("count must be positive")
    if not epoch_id:
        raise ValueError("epoch_id is required")
    if split == "confirm" and min_count is None:
        min_count = MIN_CONFIRM_TASKS
    required = max(count, min_count or 0)
    allocation_id = allocation_id or f"{split}_{epoch_id}_{uuid.uuid4().hex[:12]}"
    ts = utc_seconds() if now is None else now

    with closing(connect(db_path)) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = _eligible_rows(conn, split=split, epoch_id=epoch_id, limit=count)
            if len(rows) < required:
                conn.execute("ROLLBACK")
                raise TaskbedLedgerError(
                    f"insufficient_{split}_tasks: requested={count} required={required} available={len(rows)}"
                )
            conn.executemany(
                """
                INSERT INTO taskbed_allocations (
                  allocation_id, task_id, split, epoch_id, lane_id,
                  candidate_id, allocated_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'allocated')
                """,
                [
                    (
                        allocation_id,
                        row["task_id"],
                        split,
                        epoch_id,
                        lane_id,
                        candidate_id,
                        ts,
                    )
                    for row in rows
                ],
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise

    return allocation_receipt(allocation_id, db_path=db_path, min_confirm_count=min_count or MIN_CONFIRM_TASKS)


def allocate_explore(
    *,
    count: int,
    epoch_id: str,
    lane_id: str,
    db_path: Path | str = DEFAULT_DB,
    allocation_id: str | None = None,
    candidate_id: str = "",
) -> dict[str, Any]:
    return allocate_tasks(
        split="explore",
        count=count,
        epoch_id=epoch_id,
        lane_id=lane_id,
        db_path=db_path,
        allocation_id=allocation_id,
        candidate_id=candidate_id,
        min_count=count,
    )


def allocate_confirm(
    *,
    count: int = MIN_CONFIRM_TASKS,
    epoch_id: str,
    lane_id: str,
    db_path: Path | str = DEFAULT_DB,
    allocation_id: str | None = None,
    candidate_id: str = "",
    min_count: int = MIN_CONFIRM_TASKS,
) -> dict[str, Any]:
    return allocate_tasks(
        split="confirm",
        count=count,
        epoch_id=epoch_id,
        lane_id=lane_id,
        db_path=db_path,
        allocation_id=allocation_id,
        candidate_id=candidate_id,
        min_count=min_count,
    )


def allocation_rows(allocation_id: str, *, db_path: Path | str = DEFAULT_DB) -> list[dict[str, Any]]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT a.*, t.task_json, t.contamination_state, t.source, t.taskbed, t.created_at
              FROM taskbed_allocations a
              JOIN taskbed_tasks t ON t.task_id=a.task_id
             WHERE a.allocation_id=?
             ORDER BY a.allocated_at ASC, a.task_id ASC
            """,
            (allocation_id,),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["task"] = json.loads(item.pop("task_json"))
        result.append(item)
    return result


def allocation_receipt(
    allocation_id: str,
    *,
    db_path: Path | str = DEFAULT_DB,
    min_confirm_count: int = MIN_CONFIRM_TASKS,
) -> dict[str, Any]:
    rows = allocation_rows(allocation_id, db_path=db_path)
    splits = {str(row["split"]) for row in rows}
    split = next(iter(splits)) if len(splits) == 1 else "mixed"
    task_ids = [str(row["task_id"]) for row in rows]
    clean = all(str(row["contamination_state"]) in CLEAN_CONFIRM_STATES for row in rows)
    with closing(connect(db_path)) as conn:
        prior_explore = conn.execute(
            """
            SELECT COUNT(*) AS n
              FROM taskbed_allocations a
             WHERE a.task_id IN ({})
               AND a.split='explore'
               AND a.allocation_id != ?
            """.format(",".join("?" for _ in task_ids) or "''"),
            [*task_ids, allocation_id],
        ).fetchone()
    no_prior_explore = int(prior_explore["n"] if prior_explore else 0) == 0
    blockers: list[str] = []
    if split == "confirm":
        if len(rows) < min_confirm_count:
            blockers.append(f"confirm_n<{min_confirm_count}")
        if not clean:
            blockers.append("confirm_contamination_not_clean")
        if not no_prior_explore:
            blockers.append("confirm_task_previously_explored")
    elif split != "explore":
        blockers.append("allocation_mixed_split")
    return {
        "schema": "forge_v2.taskbed_allocation_receipt.v1",
        "allocation_id": allocation_id,
        "split": split,
        "task_count": len(rows),
        "task_ids": task_ids,
        "full_confirm_min_n": min_confirm_count if split == "confirm" else None,
        "paired_same_task": split == "confirm" and len(rows) >= min_confirm_count,
        "explore_separate_from_confirm": no_prior_explore,
        "contamination_clean": clean if split == "confirm" else None,
        "promotion_eligible_taskbed": split == "confirm" and not blockers,
        "blockers": blockers,
    }


def task_counts(*, db_path: Path | str = DEFAULT_DB) -> dict[str, int]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT contamination_state, COUNT(*) AS n FROM taskbed_tasks GROUP BY contamination_state"
        ).fetchall()
    return {str(row["contamination_state"]): int(row["n"]) for row in rows}


__all__ = [
    "CLEAN_CONFIRM_STATES",
    "DEFAULT_DB",
    "MIN_CONFIRM_TASKS",
    "TaskbedLedgerError",
    "allocate_confirm",
    "allocate_explore",
    "allocate_tasks",
    "allocation_receipt",
    "allocation_rows",
    "connect",
    "register_task",
    "register_tasks",
    "task_counts",
]
