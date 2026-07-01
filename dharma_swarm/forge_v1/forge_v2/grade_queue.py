"""SQLite grade queue for batching official SWE-bench evaluations.

The RSI Lab throughput path needs many independent Forge grades to drain through
one official SWE-bench harness invocation with ``max_workers > 1``.  This module
is deliberately small: durable enqueue, atomic batch claim, and completion
receipts.  It does not infer promotion or mutate archive fitness.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.forge_v1.swebench_real import DEFAULT_NAMESPACE, verify_predictions

DEFAULT_DB = dharma_state_dir() / "forge_v1" / "grade_queue.db"
DEFAULT_BATCH_SIZE = 6
DEFAULT_STALE_AFTER_S = 6 * 3600

GradeVerifier = Callable[..., dict[str, bool]]


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
        CREATE TABLE IF NOT EXISTS grade_jobs (
          id TEXT PRIMARY KEY,
          instance_id TEXT NOT NULL,
          instance_json TEXT NOT NULL,
          patch TEXT NOT NULL,
          status TEXT NOT NULL,
          priority INTEGER NOT NULL DEFAULT 0,
          split TEXT NOT NULL DEFAULT '',
          arm TEXT NOT NULL DEFAULT '',
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          claimed_at REAL,
          finished_at REAL,
          run_id TEXT,
          resolved INTEGER,
          error TEXT,
          attempts INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grade_jobs_status_priority "
        "ON grade_jobs(status, priority DESC, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grade_jobs_instance_status "
        "ON grade_jobs(instance_id, status)"
    )
    conn.commit()


def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
    job = dict(row)
    job["instance"] = json.loads(job.pop("instance_json"))
    job["metadata"] = json.loads(job.pop("metadata_json") or "{}")
    job["resolved"] = None if job["resolved"] is None else bool(job["resolved"])
    return job


def enqueue_grade(
    instance: dict[str, Any],
    patch: str,
    *,
    db_path: Path | str = DEFAULT_DB,
    job_id: str | None = None,
    priority: int = 0,
    split: str = "",
    arm: str = "",
    metadata: dict[str, Any] | None = None,
    now: float | None = None,
) -> str:
    instance_id = str(instance.get("instance_id") or "").strip()
    if not instance_id:
        raise ValueError("instance must include instance_id")
    job_id = job_id or uuid.uuid4().hex
    ts = utc_seconds() if now is None else now
    with closing(connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO grade_jobs (
                  id, instance_id, instance_json, patch, status, priority, split,
                  arm, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    instance_id,
                    json.dumps(instance, sort_keys=True),
                    patch,
                    int(priority),
                    split,
                    arm,
                    json.dumps(metadata or {}, sort_keys=True),
                    ts,
                    ts,
                ),
            )
    return job_id


def enqueue_many(
    jobs: list[dict[str, Any]],
    *,
    db_path: Path | str = DEFAULT_DB,
    now: float | None = None,
) -> list[str]:
    return [
        enqueue_grade(
            job["instance"],
            job["patch"],
            db_path=db_path,
            job_id=job.get("job_id"),
            priority=int(job.get("priority", 0)),
            split=str(job.get("split", "")),
            arm=str(job.get("arm", "")),
            metadata=job.get("metadata"),
            now=now,
        )
        for job in jobs
    ]


def claim_batch(
    *,
    db_path: Path | str = DEFAULT_DB,
    batch_size: int = DEFAULT_BATCH_SIZE,
    run_id: str | None = None,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Atomically claim up to ``batch_size`` queued jobs.

    A single batch contains at most one job per ``instance_id`` because the
    official SWE-bench predictions file is keyed by instance id.
    """
    run_id = run_id or f"grade_batch_{int(utc_seconds())}_{uuid.uuid4().hex[:8]}"
    ts = utc_seconds() if now is None else now
    with closing(connect(db_path)) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                UPDATE grade_jobs
                   SET status='queued', run_id=NULL, claimed_at=NULL, updated_at=?
                 WHERE status='in_flight'
                   AND claimed_at IS NOT NULL
                   AND claimed_at < ?
                """,
                (ts, ts - stale_after_s),
            )
            candidates = conn.execute(
                """
                SELECT *
                  FROM grade_jobs
                 WHERE status='queued'
                 ORDER BY priority DESC, created_at ASC, id ASC
                 LIMIT ?
                """,
                (max(batch_size * 4, batch_size),),
            ).fetchall()
            selected: list[sqlite3.Row] = []
            seen_instances: set[str] = set()
            for row in candidates:
                instance_id = str(row["instance_id"])
                if instance_id in seen_instances:
                    continue
                seen_instances.add(instance_id)
                selected.append(row)
                if len(selected) >= batch_size:
                    break
            ids = [str(row["id"]) for row in selected]
            if ids:
                conn.executemany(
                    """
                    UPDATE grade_jobs
                       SET status='in_flight',
                           run_id=?,
                           claimed_at=?,
                           updated_at=?,
                           attempts=attempts+1
                     WHERE id=?
                    """,
                    [(run_id, ts, ts, job_id) for job_id in ids],
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT * FROM grade_jobs WHERE run_id=? AND status='in_flight' ORDER BY claimed_at, id",
            (run_id,),
        ).fetchall()
    return [_row_to_job(row) for row in rows]


def complete_job(
    job_id: str,
    *,
    resolved: bool | None = None,
    error: str | None = None,
    db_path: Path | str = DEFAULT_DB,
    now: float | None = None,
) -> None:
    status = "done" if error is None else "error"
    ts = utc_seconds() if now is None else now
    with closing(connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                UPDATE grade_jobs
                   SET status=?,
                       resolved=?,
                       error=?,
                       finished_at=?,
                       updated_at=?
                 WHERE id=?
                """,
                (
                    status,
                    None if resolved is None else int(bool(resolved)),
                    error,
                    ts,
                    ts,
                    job_id,
                ),
            )


def drain_once(
    *,
    db_path: Path | str = DEFAULT_DB,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = DEFAULT_BATCH_SIZE,
    timeout: int = 1800,
    namespace: str | None = DEFAULT_NAMESPACE,
    verifier: GradeVerifier = verify_predictions,
    run_id: str | None = None,
) -> dict[str, Any]:
    run_id = run_id or f"grade_batch_{int(utc_seconds())}_{uuid.uuid4().hex[:8]}"
    jobs = claim_batch(db_path=db_path, batch_size=batch_size, run_id=run_id)
    if not jobs:
        return {"run_id": run_id, "claimed": 0, "completed": 0, "errors": 0}

    try:
        results = verifier(
            [(job["instance"], job["patch"]) for job in jobs],
            max_workers=max_workers,
            timeout=timeout,
            namespace=namespace,
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 - queue must receipt failed batches.
        message = f"{type(exc).__name__}: {exc}"
        for job in jobs:
            complete_job(job["id"], error=message, db_path=db_path)
        return {"run_id": run_id, "claimed": len(jobs), "completed": 0, "errors": len(jobs), "error": message}

    completed = 0
    errors = 0
    for job in jobs:
        instance_id = str(job["instance_id"])
        if instance_id not in results:
            errors += 1
            complete_job(job["id"], error=f"missing verdict for {instance_id}", db_path=db_path)
            continue
        completed += 1
        complete_job(job["id"], resolved=bool(results[instance_id]), db_path=db_path)
    return {"run_id": run_id, "claimed": len(jobs), "completed": completed, "errors": errors}


def queue_counts(*, db_path: Path | str = DEFAULT_DB) -> dict[str, int]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM grade_jobs GROUP BY status"
        ).fetchall()
    return {str(row["status"]): int(row["n"]) for row in rows}
