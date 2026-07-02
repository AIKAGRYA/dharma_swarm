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
import calendar
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
CLEAN_CONFIRM_STATES = frozenset({"fresh_heldout", "self_mod_clean", "clean"})
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


def task_for_id(task_id: str, *, db_path: Path | str = DEFAULT_DB) -> dict[str, Any]:
    """Return a registered task row by id, including its sealed payload."""
    with closing(connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT task_id, task_json, source, taskbed, contamination_state,
                   provenance_json, created_at, active, max_uses_per_epoch
              FROM taskbed_tasks
             WHERE task_id=?
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        raise TaskbedLedgerError(f"unknown_task_id: {task_id}")
    result = dict(row)
    result["task"] = json.loads(result.pop("task_json"))
    result["provenance"] = json.loads(result.pop("provenance_json") or "{}")
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


def _read_json(path: Path | str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_div(numerator: float, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _parse_stamp_seconds(stamp: Any) -> float | None:
    text = str(stamp or "").strip()
    if not text:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return float(calendar.timegm(time.strptime(text, fmt)))
        except ValueError:
            continue
    return None


def _duration_seconds(started_at: Any, finished_at: Any) -> float | None:
    start = _parse_stamp_seconds(started_at)
    finish = _parse_stamp_seconds(finished_at)
    if start is None or finish is None or finish < start:
        return None
    return round(finish - start, 1)


def _repo_from_task(task_id: str, task: dict[str, Any]) -> str:
    repo = str(task.get("repo") or task.get("repository") or "").strip().strip("/")
    if repo:
        return repo
    text = str(task_id or "")
    if text.startswith("pr::") and "#" in text:
        return text[len("pr::") :].split("#", 1)[0].strip()
    return "(unknown)"


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def _all_task_rows(*, db_path: Path | str = DEFAULT_DB, active_only: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT task_id, task_json, source, taskbed, contamination_state,
               provenance_json, created_at, active, max_uses_per_epoch
          FROM taskbed_tasks
    """
    if active_only:
        query += " WHERE active=1"
    query += " ORDER BY task_id ASC"
    with closing(connect(db_path)) as conn:
        rows = conn.execute(query).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["task"] = json.loads(item.pop("task_json"))
        item["provenance"] = json.loads(item.pop("provenance_json") or "{}")
        result.append(item)
    return result


def _iter_grade_receipts(roots: Iterable[Path | str]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for root_value in roots:
        root = Path(root_value).expanduser()
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            receipt = _read_json(path)
            task_id = str(receipt.get("task_id") or "").strip()
            if not task_id:
                continue
            receipt["_source_path"] = str(path)
            receipts.append(receipt)
    return receipts


def _repo_summary(repo: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "task_count": 0,
        "validated_count": 0,
        "validation_failed_count": 0,
        "validation_missing_receipt_count": 0,
        "validation_runtime_seconds": [],
        "grade_attempt_count": 0,
        "grade_resolved_count": 0,
        "grade_failed_count": 0,
        "grade_runtime_seconds": [],
        "grade_observed_task_ids": set(),
    }


def _finalize_repo_summary(summary: dict[str, Any]) -> dict[str, Any]:
    validation_runtimes = list(summary.pop("validation_runtime_seconds"))
    grade_runtimes = list(summary.pop("grade_runtime_seconds"))
    observed_task_ids = sorted(summary.pop("grade_observed_task_ids"))
    task_count = int(summary["task_count"])
    grade_attempts = int(summary["grade_attempt_count"])
    summary["validation_failure_rate"] = _safe_div(float(summary["validation_failed_count"]), task_count)
    summary["validation_missing_receipt_rate"] = _safe_div(
        float(summary["validation_missing_receipt_count"]), task_count
    )
    summary["validation_runtime"] = {
        "observed_count": len(validation_runtimes),
        "median_seconds": _median(validation_runtimes),
        "min_seconds": round(min(validation_runtimes), 1) if validation_runtimes else None,
        "max_seconds": round(max(validation_runtimes), 1) if validation_runtimes else None,
        "total_seconds": round(sum(validation_runtimes), 1),
        "source": "validation_receipt.started_at/finished_at",
    }
    summary["grade_failure_rate"] = _safe_div(float(summary["grade_failed_count"]), grade_attempts)
    summary["grade_runtime"] = {
        "observed_count": len(grade_runtimes),
        "median_seconds": _median(grade_runtimes),
        "min_seconds": round(min(grade_runtimes), 1) if grade_runtimes else None,
        "max_seconds": round(max(grade_runtimes), 1) if grade_runtimes else None,
        "total_seconds": round(sum(grade_runtimes), 1),
        "source": "grade_receipt.grade_seconds or started_at/finished_at",
    }
    summary["grade_coverage"] = {
        "observed_task_count": len(observed_task_ids),
        "task_count": task_count,
        "observed_task_rate": _safe_div(float(len(observed_task_ids)), task_count),
        "observed_task_ids": observed_task_ids,
    }
    return summary


def taskbed_quality_report(
    *,
    db_path: Path | str = DEFAULT_DB,
    active_only: bool = True,
    grade_receipt_roots: Iterable[Path | str] = DEFAULT_GRADE_RECEIPT_ROOTS,
) -> dict[str, Any]:
    """Return per-repo taskbed validation/grade quality and runtime evidence.

    Workstream 2's done-state requires failure rate and runtime per repo to be
    known.  The ledger already stores validated task payloads and validation
    receipt paths; this report derives per-repo metrics from those receipts plus
    any observed PR-suite/native grade receipts.  It does not infer missing
    timings: unavailable evidence is counted via coverage fields and left as
    ``None`` instead of guessed.
    """
    rows = _all_task_rows(db_path=db_path, active_only=active_only)
    by_repo: dict[str, dict[str, Any]] = {}
    task_to_repo: dict[str, str] = {}
    task_details: list[dict[str, Any]] = []

    for row in rows:
        task_id = str(row["task_id"])
        task = dict(row["task"])
        repo = _repo_from_task(task_id, task)
        task_to_repo[task_id] = repo
        summary = by_repo.setdefault(repo, _repo_summary(repo))
        summary["task_count"] += 1

        validation_path = str(task.get("validation_receipt") or "").strip()
        validation = _read_json(validation_path) if validation_path else {}
        status = str(validation.get("status") or task.get("validation_state") or "").strip()
        blockers = list(validation.get("blockers") or task.get("validator_blockers") or [])
        validated = status == "fail_to_pass_validated" and not blockers
        missing_receipt = bool(validation_path and not validation) or not validation_path
        if validated:
            summary["validated_count"] += 1
        else:
            summary["validation_failed_count"] += 1
        if missing_receipt:
            summary["validation_missing_receipt_count"] += 1
        duration = _duration_seconds(validation.get("started_at"), validation.get("finished_at"))
        if duration is not None:
            summary["validation_runtime_seconds"].append(duration)

        task_details.append(
            {
                "task_id": task_id,
                "repo": repo,
                "validation_status": status,
                "validation_receipt": validation_path,
                "validation_receipt_present": bool(validation),
                "validation_runtime_seconds": duration,
                "validation_blockers": blockers,
            }
        )

    grade_receipts = _iter_grade_receipts(grade_receipt_roots)
    for receipt in grade_receipts:
        task_id = str(receipt.get("task_id") or "").strip()
        repo = task_to_repo.get(task_id) or _repo_from_task(task_id, receipt)
        if repo not in by_repo:
            continue
        summary = by_repo[repo]
        summary["grade_attempt_count"] += 1
        summary["grade_observed_task_ids"].add(task_id)
        resolved = bool(receipt.get("resolved"))
        if resolved:
            summary["grade_resolved_count"] += 1
        else:
            summary["grade_failed_count"] += 1
        seconds_value = receipt.get("grade_seconds")
        runtime = None
        if seconds_value is not None:
            try:
                runtime = round(float(seconds_value), 1)
            except (TypeError, ValueError):
                runtime = None
        if runtime is None:
            runtime = _duration_seconds(receipt.get("started_at"), receipt.get("finished_at"))
        if runtime is not None:
            summary["grade_runtime_seconds"].append(runtime)

    per_repo = [_finalize_repo_summary(by_repo[key]) for key in sorted(by_repo)]
    total_tasks = len(rows)
    total_validated = sum(int(item["validated_count"]) for item in per_repo)
    total_grade_attempts = sum(int(item["grade_attempt_count"]) for item in per_repo)
    total_grade_resolved = sum(int(item["grade_resolved_count"]) for item in per_repo)
    total_grade_failed = sum(int(item["grade_failed_count"]) for item in per_repo)
    return {
        "schema": "forge_v2.taskbed_quality_report.v1",
        "generated_at": now_stamp(),
        "db_path": str(Path(db_path).expanduser()),
        "active_only": active_only,
        "task_count": total_tasks,
        "validated_count": total_validated,
        "validation_failure_rate": _safe_div(float(total_tasks - total_validated), total_tasks),
        "grade_attempt_count": total_grade_attempts,
        "grade_resolved_count": total_grade_resolved,
        "grade_failed_count": total_grade_failed,
        "grade_failure_rate": _safe_div(float(total_grade_failed), total_grade_attempts),
        "repo_count": len(per_repo),
        "per_repo": per_repo,
        "task_details": task_details,
        "grade_receipt_roots": [str(Path(root).expanduser()) for root in grade_receipt_roots],
        "source_of_truth_mutated": False,
        "official_score_claimed": False,
        "promotion_gate": "verify_promotion_only",
    }


def taskbed_quality_markdown(report: dict[str, Any]) -> str:
    def fmt(value: Any) -> str:
        return "n/a" if value is None else str(value)

    lines = [
        "# Taskbed quality report",
        "",
        f"- task_count: {report.get('task_count', 0)}",
        f"- validated_count: {report.get('validated_count', 0)}",
        f"- validation_failure_rate: {fmt(report.get('validation_failure_rate'))}",
        f"- grade_attempt_count: {report.get('grade_attempt_count', 0)}",
        f"- grade_failure_rate: {fmt(report.get('grade_failure_rate'))}",
        f"- repo_count: {report.get('repo_count', 0)}",
        "",
        "| repo | tasks | validated | validation failure | validation median sec | grade attempts | grade failure | grade median sec | grade coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report.get("per_repo", []):
        validation_runtime = item.get("validation_runtime", {})
        grade_runtime = item.get("grade_runtime", {})
        coverage = item.get("grade_coverage", {})
        lines.append(
            "| {repo} | {tasks} | {validated} | {vfail} | {vmed} | {gatt} | {gfail} | {gmed} | {gcov} |".format(
                repo=item.get("repo", ""),
                tasks=item.get("task_count", 0),
                validated=item.get("validated_count", 0),
                vfail=fmt(item.get("validation_failure_rate")),
                vmed=fmt(validation_runtime.get("median_seconds")),
                gatt=item.get("grade_attempt_count", 0),
                gfail=fmt(item.get("grade_failure_rate")),
                gmed=fmt(grade_runtime.get("median_seconds")),
                gcov=fmt(coverage.get("observed_task_rate")),
            )
        )
    lines.extend(
        [
            "",
            "Validation runtime is measured from validation receipt timestamps.",
            "Grade runtime is measured only when grade receipts expose grade_seconds or usable timestamps; coverage is explicit, not guessed.",
            "",
        ]
    )
    return "\n".join(lines)


def write_taskbed_quality_report(
    *,
    output_root: Path | str = DEFAULT_QUALITY_ROOT,
    db_path: Path | str = DEFAULT_DB,
    active_only: bool = True,
    grade_receipt_roots: Iterable[Path | str] = DEFAULT_GRADE_RECEIPT_ROOTS,
    label: str | None = None,
) -> dict[str, Any]:
    report = taskbed_quality_report(
        db_path=db_path,
        active_only=active_only,
        grade_receipt_roots=grade_receipt_roots,
    )
    stem = f"taskbed_quality_{label or now_stamp()}"
    root = Path(output_root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{stem}.json"
    md_path = root / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(taskbed_quality_markdown(report), encoding="utf-8")
    return {"report": report, "json_path": str(json_path), "markdown_path": str(md_path)}


__all__ = [
    "CLEAN_CONFIRM_STATES",
    "DEFAULT_DB",
    "DEFAULT_GRADE_RECEIPT_ROOTS",
    "DEFAULT_QUALITY_ROOT",
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
    "taskbed_quality_markdown",
    "taskbed_quality_report",
    "task_for_id",
    "task_counts",
    "write_taskbed_quality_report",
]
