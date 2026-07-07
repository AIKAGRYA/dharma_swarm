"""EXPLORE/CONFIRM taskbed allocation logic."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

from .taskbed_store import (
    CLEAN_CONFIRM_STATES,
    DEFAULT_DB,
    MIN_CONFIRM_TASKS,
    SplitName,
    TaskbedLedgerError,
    connect,
    utc_seconds,
)


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
        clean_filter = "AND t.contamination_state IN ({})".format(
            ",".join("?" for _ in sorted(CLEAN_CONFIRM_STATES))
        )
        params.extend(sorted(CLEAN_CONFIRM_STATES))
    params.extend([opposite, epoch_id])
    params.append(limit)
    return conn.execute(
        f"""
        SELECT t.* FROM taskbed_tasks t
         WHERE t.active=1
           {clean_filter}
           AND NOT EXISTS (
             SELECT 1 FROM taskbed_allocations prior
              WHERE prior.task_id=t.task_id AND prior.split=?
           )
           AND (
             SELECT COUNT(*) FROM taskbed_allocations used
              WHERE used.task_id=t.task_id AND used.epoch_id=? AND used.status='allocated'
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
            _insert_allocations(conn, rows, allocation_id, split, epoch_id, lane_id, candidate_id, ts)
            conn.execute("COMMIT")
        except Exception:
            _rollback(conn)
            raise
    return allocation_receipt(allocation_id, db_path=db_path, min_confirm_count=min_count or MIN_CONFIRM_TASKS)


def _insert_allocations(conn, rows, allocation_id, split, epoch_id, lane_id, candidate_id, ts) -> None:
    conn.executemany(
        """
        INSERT INTO taskbed_allocations (
          allocation_id, task_id, split, epoch_id, lane_id, candidate_id, allocated_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'allocated')
        """,
        [
            (allocation_id, row["task_id"], split, epoch_id, lane_id, candidate_id, ts)
            for row in rows
        ],
    )


def _rollback(conn) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


def _eligible_rows_for_task_ids(
    conn: sqlite3.Connection,
    *,
    split: SplitName,
    epoch_id: str,
    task_ids: list[str],
) -> list[sqlite3.Row]:
    if not task_ids:
        return []
    opposite = "confirm" if split == "explore" else "explore"
    clean_filter = ""
    params: list[Any] = []
    if split == "confirm":
        clean_filter = "AND t.contamination_state IN ({})".format(
            ",".join("?" for _ in sorted(CLEAN_CONFIRM_STATES))
        )
        params.extend(sorted(CLEAN_CONFIRM_STATES))
    placeholders = ",".join("?" for _ in task_ids)
    params.extend([*task_ids, opposite, epoch_id])
    return conn.execute(
        f"""
        SELECT t.* FROM taskbed_tasks t
         WHERE t.active=1
           {clean_filter}
           AND t.task_id IN ({placeholders})
           AND NOT EXISTS (
             SELECT 1 FROM taskbed_allocations prior
              WHERE prior.task_id=t.task_id AND prior.split=?
           )
           AND (
             SELECT COUNT(*) FROM taskbed_allocations used
              WHERE used.task_id=t.task_id AND used.epoch_id=? AND used.status='allocated'
           ) < t.max_uses_per_epoch
         ORDER BY t.created_at ASC, t.first_seen_at ASC, t.task_id ASC
        """,
        params,
    ).fetchall()


def allocate_task_ids(
    *,
    split: SplitName,
    task_ids: list[str],
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
    task_ids = [str(item) for item in task_ids if str(item).strip()]
    if not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("task_ids must be non-empty and unique")
    if not epoch_id:
        raise ValueError("epoch_id is required")
    if split == "confirm" and min_count is None:
        min_count = MIN_CONFIRM_TASKS
    required = max(len(task_ids), min_count or 0)
    allocation_id = allocation_id or f"{split}_{epoch_id}_{uuid.uuid4().hex[:12]}"
    ts = utc_seconds() if now is None else now
    with closing(connect(db_path)) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = _eligible_rows_for_task_ids(conn, split=split, epoch_id=epoch_id, task_ids=task_ids)
            row_ids = {str(row["task_id"]) for row in rows}
            missing = sorted(set(task_ids) - row_ids)
            if len(rows) < required or missing:
                conn.execute("ROLLBACK")
                detail = f" requested={len(task_ids)} required={required} available={len(rows)} missing_or_ineligible={missing}"
                raise TaskbedLedgerError(f"insufficient_explicit_{split}_tasks:{detail}")
            _insert_allocations(conn, rows, allocation_id, split, epoch_id, lane_id, candidate_id, ts)
            conn.execute("COMMIT")
        except Exception:
            _rollback(conn)
            raise
    return allocation_receipt(allocation_id, db_path=db_path, min_confirm_count=min_count or MIN_CONFIRM_TASKS)


def allocate_explore(*, count: int, epoch_id: str, lane_id: str, db_path: Path | str = DEFAULT_DB,
                     allocation_id: str | None = None, candidate_id: str = "") -> dict[str, Any]:
    return allocate_tasks(split="explore", count=count, epoch_id=epoch_id, lane_id=lane_id,
                          db_path=db_path, allocation_id=allocation_id, candidate_id=candidate_id,
                          min_count=count)


def allocate_confirm(*, count: int = MIN_CONFIRM_TASKS, epoch_id: str, lane_id: str,
                     db_path: Path | str = DEFAULT_DB, allocation_id: str | None = None,
                     candidate_id: str = "", min_count: int = MIN_CONFIRM_TASKS) -> dict[str, Any]:
    return allocate_tasks(split="confirm", count=count, epoch_id=epoch_id, lane_id=lane_id,
                          db_path=db_path, allocation_id=allocation_id, candidate_id=candidate_id,
                          min_count=min_count)


def allocation_rows(allocation_id: str, *, db_path: Path | str = DEFAULT_DB) -> list[dict[str, Any]]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT a.*, t.task_json, t.contamination_state, t.source, t.taskbed, t.created_at
              FROM taskbed_allocations a JOIN taskbed_tasks t ON t.task_id=a.task_id
             WHERE a.allocation_id=? ORDER BY a.allocated_at ASC, a.task_id ASC
            """,
            (allocation_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["task"] = json.loads(item.pop("task_json"))
        result.append(item)
    return result


def task_for_id(task_id: str, *, db_path: Path | str = DEFAULT_DB) -> dict[str, Any]:
    with closing(connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT task_id, task_json, source, taskbed, contamination_state,
                   provenance_json, created_at, active, max_uses_per_epoch
              FROM taskbed_tasks WHERE task_id=?
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        raise TaskbedLedgerError(f"unknown_task_id: {task_id}")
    result = dict(row)
    result["task"] = json.loads(result.pop("task_json"))
    result["provenance"] = json.loads(result.pop("provenance_json") or "{}")
    return result


def allocation_receipt(allocation_id: str, *, db_path: Path | str = DEFAULT_DB,
                       min_confirm_count: int = MIN_CONFIRM_TASKS) -> dict[str, Any]:
    rows = allocation_rows(allocation_id, db_path=db_path)
    splits = {str(row["split"]) for row in rows}
    split = next(iter(splits)) if len(splits) == 1 else "mixed"
    task_ids = [str(row["task_id"]) for row in rows]
    clean = all(str(row["contamination_state"]) in CLEAN_CONFIRM_STATES for row in rows)
    prior_n = _prior_explore_count(task_ids, allocation_id, db_path=db_path)
    no_prior_explore = prior_n == 0
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


def _prior_explore_count(task_ids: list[str], allocation_id: str, *, db_path: Path | str) -> int:
    if not task_ids:
        return 0
    with closing(connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM taskbed_allocations a
             WHERE a.task_id IN ({}) AND a.split='explore' AND a.allocation_id != ?
            """.format(",".join("?" for _ in task_ids)),
            [*task_ids, allocation_id],
        ).fetchone()
    return int(row["n"] if row else 0)


def task_counts(*, db_path: Path | str = DEFAULT_DB) -> dict[str, int]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT contamination_state, COUNT(*) AS n FROM taskbed_tasks GROUP BY contamination_state"
        ).fetchall()
    return {str(row["contamination_state"]): int(row["n"]) for row in rows}
