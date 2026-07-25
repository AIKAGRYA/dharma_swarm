# spine: reads EvidenceReceipt (read-only view over delegation_runs.receipt_json)
"""Live EvidenceReceipt tail + cockpit pulse — the operator's felt view of the spine.

This module OWNS NOTHING. It reads the ``receipt_json`` column that the spine
dispatch writes on ``delegation_runs`` (owner: ``runtime_state``), exactly the
access pattern ``orientation_graph.build_loop1_closure`` uses. No new store.

Two read surfaces sit on the one query:
  - ``read_recent_receipts`` / ``cmd_spine_tail`` — ``dgc spine tail`` one line
    per receipt (started_at, trace_id, provider, model, status), optional --follow.
  - ``compute_spine_pulse`` — the read-only cockpit pulse (receipts_last_hour,
    last_receipt_age_seconds, dispatch_dropoff_count).

Graceful absence is a first-class outcome: when the runtime DB or the
``delegation_runs`` table is missing, callers get ``present=False`` and a
"spine not live on this host" message rather than an exception.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ABSENT_HINT = "spine not live on this host — see make orient"


def _runtime_db_path() -> Path:
    """Resolve the canonical runtime DB path (runtime_state owns it)."""
    try:
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

        return DEFAULT_RUNTIME_DB
    except Exception:  # pragma: no cover - defensive
        return Path.home() / ".dharma" / "state" / "runtime.db"


def _connect_ro(path: Path) -> sqlite3.Connection:
    """Open the runtime DB read-only (never mutate the truth surface)."""
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except Exception:  # pragma: no cover - older sqlite / odd fs
        return sqlite3.connect(str(path))


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class ReceiptRow:
    """One projected EvidenceReceipt line (read-only, no ownership)."""

    started_at: str = ""
    trace_id: str = ""
    provider: str = ""
    model: str = ""
    status: str = ""

    def one_line(self) -> str:
        trace_short = (self.trace_id or "-")[:12]
        started = self.started_at or "-"
        provider = self.provider or "-"
        model = self.model or "-"
        status = self.status or "-"
        return f"{started:<20}  {trace_short:<12}  {provider:<14}  {model:<28}  {status}"


@dataclass
class ReceiptQuery:
    """Result of a read: whether the surface is present + the projected rows."""

    present: bool
    detail: str = ""
    db_path: str = ""
    rows: list[ReceiptRow] = field(default_factory=list)


def _rows_from_receipts(records: list[tuple[str, str]]) -> list[ReceiptRow]:
    rows: list[ReceiptRow] = []
    for col_started_at, receipt_json in records:
        try:
            blob = json.loads(receipt_json)
        except Exception:
            blob = {}
        started = str(blob.get("started_at", "") or col_started_at or "")
        rows.append(
            ReceiptRow(
                started_at=started,
                trace_id=str(blob.get("trace_id", "") or ""),
                provider=str(blob.get("provider", "") or ""),
                model=str(blob.get("model", "") or ""),
                status=str(blob.get("status", "") or ""),
            )
        )
    return rows


def read_recent_receipts(
    db_path: Any = None,
    limit: int = 20,
    *,
    newest_first: bool = True,
) -> ReceiptQuery:
    """Read the most recent persisted EvidenceReceipts (read-only).

    Ordered by ``started_at DESC, rowid DESC`` (the same ordering
    ``build_loop1_closure`` uses). Returns ``present=False`` with a graceful
    message when the DB or the ``delegation_runs`` table is absent.
    """
    path = Path(db_path) if db_path is not None else _runtime_db_path()
    if not Path(path).exists():
        return ReceiptQuery(present=False, detail=ABSENT_HINT, db_path=str(path))
    try:
        conn = _connect_ro(Path(path))
    except Exception as exc:  # pragma: no cover - defensive
        return ReceiptQuery(present=False, detail=f"db unreadable: {exc}", db_path=str(path))
    try:
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='delegation_runs'"
        ).fetchone()
        if not has_table:
            return ReceiptQuery(present=False, detail=ABSENT_HINT, db_path=str(path))
        records = conn.execute(
            "SELECT started_at, receipt_json FROM delegation_runs "
            "WHERE receipt_json IS NOT NULL AND receipt_json != '' "
            "ORDER BY started_at DESC, rowid DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
    except Exception as exc:
        return ReceiptQuery(present=False, detail=f"delegation_runs query failed: {exc}", db_path=str(path))
    finally:
        conn.close()

    rows = _rows_from_receipts([(str(a or ""), str(b or "")) for a, b in records])
    if not newest_first:
        rows = list(reversed(rows))
    detail = "no persisted EvidenceReceipt yet" if not rows else f"{len(rows)} receipt(s)"
    return ReceiptQuery(present=True, detail=detail, db_path=str(path), rows=rows)


def compute_spine_pulse(db_path: Any = None, *, window_seconds: int = 3600) -> dict[str, Any]:
    """Read-only cockpit pulse over the receipt stream.

    Returns a JSON-safe dict with:
      - ``present``            — False when the spine isn't live on this host
      - ``receipts_last_hour`` — receipts started within ``window_seconds``
      - ``last_receipt_age_seconds`` — age of the newest receipt (None if none)
      - ``dispatch_dropoff_count``    — receipts with status ``dropped``
    """
    # Pull a generous slice so counts are meaningful without scanning the table.
    q = read_recent_receipts(db_path, limit=500)
    base: dict[str, Any] = {
        "present": q.present,
        "detail": q.detail,
        "db_path": q.db_path,
        "receipts_last_hour": 0,
        "last_receipt_age_seconds": None,
        "dispatch_dropoff_count": 0,
    }
    if not q.present:
        return base

    now = datetime.now(timezone.utc)
    last_hour = 0
    dropoffs = 0
    newest: datetime | None = None
    for row in q.rows:
        if row.status == "dropped":
            dropoffs += 1
        dt = _parse_dt(row.started_at)
        if dt is None:
            continue
        if newest is None or dt > newest:
            newest = dt
        if (now - dt).total_seconds() <= window_seconds:
            last_hour += 1

    base["receipts_last_hour"] = last_hour
    base["dispatch_dropoff_count"] = dropoffs
    if newest is not None:
        base["last_receipt_age_seconds"] = max(0, int((now - newest).total_seconds()))
    return base


_TAIL_HEADER = (
    f"{'started_at':<20}  {'trace_id':<12}  {'provider':<14}  {'model':<28}  status"
)


def cmd_spine_tail(limit: int = 20, follow: bool = False, db_path: Any = None) -> int:
    """`dgc spine tail` — one line per EvidenceReceipt; --follow polls every 2s."""
    q = read_recent_receipts(db_path, limit=limit, newest_first=False)
    if not q.present:
        print(q.detail)
        return 0

    print(_TAIL_HEADER)
    print("-" * len(_TAIL_HEADER))
    if not q.rows:
        print("(no persisted EvidenceReceipt yet)")
    for row in q.rows:
        print(row.one_line())

    if not follow:
        return 0

    seen: set[tuple[str, str, str]] = {
        (r.started_at, r.trace_id, r.status) for r in q.rows
    }
    print("... following (Ctrl-C to stop) ...", flush=True)
    try:
        while True:
            time.sleep(2)
            fresh = read_recent_receipts(db_path, limit=limit, newest_first=False)
            if not fresh.present:
                print(fresh.detail)
                return 0
            for row in fresh.rows:
                key = (row.started_at, row.trace_id, row.status)
                if key not in seen:
                    seen.add(key)
                    print(row.one_line(), flush=True)
    except KeyboardInterrupt:
        print()
        return 0
