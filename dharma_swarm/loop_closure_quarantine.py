# spine: quarantine marker over delegation_runs (owner: runtime_state) — no new store
"""Quarantine marker for historical dispatch_dropoff rows (loop-closure-2026-06).

A dispatch_dropoff row is a ``delegation_runs`` row with ``status='failed'``
and ``failure_code='dispatch_dropoff'`` (written by
``orchestrator._fail_task(source="dispatch_dropoff")``; counted full-history by
``cybernetics_codex.read_runtime_summary``). Thousands of such rows predate the
spine-dispatch fixes; they block any standing all-history daemon-clean claim
even though the current harness is green.

Doctrine (track loop-closure-2026-06):
  - NO new truth store. The marker is two nullable columns on the existing
    ``delegation_runs`` table, added by the same idempotent-ALTER pattern
    ``spine/persistence.ensure_receipt_column`` used for ``receipt_json``.
  - Quarantine != delete. Rows stay in the table, fully auditable; a
    quarantined row carries ``quarantined_at`` + ``quarantine_reason`` and is
    excluded from LIVE failure counts while being reported SEPARATELY
    (dropoff_live=N, dropoff_quarantined_historical=M — never hidden).
  - Timestamp comparison happens in Python (parsed, timezone-aware), never by
    SQL string compare, so 'Z' vs '+00:00' suffix drift cannot misclassify.

Consumers: ``cybernetics_codex.read_runtime_summary`` (audit exclusion +
separate reporting) and ``scripts/runtime/dispatch_dropoff_quarantine.py``
(the operator tool that marks rows and writes the quarantine receipt).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# NULL/'' means LIVE; any non-empty quarantined_at means quarantined.
QUARANTINE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("quarantined_at", "TEXT"),
    ("quarantine_reason", "TEXT"),
)
LIVE_ROW_PREDICATE = "(quarantined_at is null or quarantined_at = '')"
DROPOFF_PREDICATE = "status='failed' and failure_code='dispatch_dropoff'"
SQLITE_IN_CHUNK_SIZE = 500


def parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp; naive values are assumed UTC."""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def has_quarantine_columns(conn: sqlite3.Connection) -> bool:
    try:
        columns = {row[1] for row in conn.execute("pragma table_info(delegation_runs)")}
    except sqlite3.Error:
        return False
    return all(name in columns for name, _ in QUARANTINE_COLUMNS)


def ensure_quarantine_columns(conn: sqlite3.Connection) -> None:
    """Idempotent migration mirroring spine.persistence.ensure_receipt_column."""
    for name, sql_type in QUARANTINE_COLUMNS:
        try:
            conn.execute(f"SELECT {name} FROM delegation_runs LIMIT 0")
        except sqlite3.Error:
            try:
                conn.execute(f"ALTER TABLE delegation_runs ADD COLUMN {name} {sql_type}")
                conn.commit()
                logger.info("quarantine: added %s column to delegation_runs", name)
            except sqlite3.Error:
                logger.debug("quarantine: %s column already exists or table missing", name)


def quarantined_failure_counts(
    conn: sqlite3.Connection,
    where_sql: str = "",
    where_args: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Group-by failure_code over QUARANTINED failed rows (the separate report).

    ``where_sql``/``where_args`` compose with the audit's time-scope clause the
    same way ``cybernetics_codex._and_where`` does for the live count.
    """
    if not has_quarantine_columns(conn):
        return []
    predicate = f"status='failed' and not {LIVE_ROW_PREDICATE}"
    scoped = f"{where_sql} and {predicate}" if where_sql.strip() else f"where {predicate}"
    rows = conn.execute(
        f"""
        select
          failure_code,
          count(*) as count,
          max(coalesce(completed_at, started_at)) as last_seen
        from delegation_runs
        {scoped}
        group by failure_code
        order by count desc
        limit 12
        """,
        where_args,
    ).fetchall()
    return [
        {"failure_code": row[0], "count": row[1], "last_seen": row[2]}
        for row in rows
    ]


def scan_dropoffs(conn: sqlite3.Connection, *, before: datetime) -> dict[str, Any]:
    """Classify live dispatch_dropoff rows against the cutoff (read-only).

    Returns rowid lists so the caller can act (or just report on --dry-run):
      - ``candidates``  — live dropoff rows strictly older than ``before``
      - ``fresh_live``  — live dropoff rows at/after the cutoff (NEVER touched)
      - ``undated``     — live dropoff rows with no parseable timestamp
                          (never quarantine what cannot be dated)
    """
    quarantined = 0
    if has_quarantine_columns(conn):
        quarantined = int(
            conn.execute(
                "select count(*) from delegation_runs "
                f"where {DROPOFF_PREDICATE} and not {LIVE_ROW_PREDICATE}"
            ).fetchone()[0]
        )
        live_clause = f"{DROPOFF_PREDICATE} and {LIVE_ROW_PREDICATE}"
    else:
        live_clause = DROPOFF_PREDICATE

    candidates: list[int] = []
    fresh_live: list[int] = []
    undated: list[int] = []
    for rowid, ts in conn.execute(
        "select rowid, coalesce(completed_at, started_at) from delegation_runs "
        f"where {live_clause}"
    ):
        parsed = parse_ts(ts)
        if parsed is None:
            undated.append(int(rowid))
        elif parsed < before:
            candidates.append(int(rowid))
        else:
            fresh_live.append(int(rowid))
    return {
        "candidates": sorted(candidates),
        "fresh_live": sorted(fresh_live),
        "undated": sorted(undated),
        "already_quarantined": quarantined,
    }


def rowids_sha256(rowids: list[int]) -> str:
    return hashlib.sha256(json.dumps(sorted(rowids)).encode("utf-8")).hexdigest()


def quarantine_historical_dropoffs(
    conn: sqlite3.Connection,
    *,
    before: datetime,
    reason: str,
    execute: bool = False,
) -> dict[str, Any]:
    """Mark pre-cutoff live dispatch_dropoff rows quarantined (or plan to).

    Dry-run (``execute=False``) mutates NOTHING — not even the schema. On
    execute the columns are ensured, then only the pre-cutoff candidates are
    stamped with ``quarantined_at`` + ``quarantine_reason``. Idempotent: a
    stamped row leaves the live predicate, so re-runs find zero candidates.
    """
    scan = scan_dropoffs(conn, before=before)
    candidates: list[int] = scan["candidates"]
    live_before = len(candidates) + len(scan["fresh_live"]) + len(scan["undated"])
    result: dict[str, Any] = {
        "cutoff": before.isoformat().replace("+00:00", "Z"),
        "reason": reason,
        "executed": bool(execute),
        "dropoff_live_before": live_before,
        "dropoff_fresh_live_kept": len(scan["fresh_live"]),
        "dropoff_undated_kept": len(scan["undated"]),
        "dropoff_quarantined_prior": scan["already_quarantined"],
        "candidates": len(candidates),
        "quarantined_rowids_sha256": rowids_sha256(candidates),
    }
    if not execute:
        result["dropoff_live_after"] = live_before
        result["dropoff_quarantined_total_after"] = scan["already_quarantined"]
        result["quarantined_now"] = 0
        return result

    ensure_quarantine_columns(conn)
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    quarantined_now = 0
    for start in range(0, len(candidates), SQLITE_IN_CHUNK_SIZE):
        chunk = candidates[start : start + SQLITE_IN_CHUNK_SIZE]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(
            "update delegation_runs set quarantined_at = ?, quarantine_reason = ? "
            f"where rowid in ({placeholders}) and {LIVE_ROW_PREDICATE}",
            (stamp, reason, *chunk),
        )
        quarantined_now += int(cur.rowcount or 0)
    conn.commit()
    result["quarantined_at"] = stamp
    result["quarantined_now"] = quarantined_now
    result["dropoff_live_after"] = live_before - quarantined_now
    result["dropoff_quarantined_total_after"] = scan["already_quarantined"] + quarantined_now
    return result
