"""Read-only status probes that must not initialize runtime state."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def read_memory_entry_count(db_path: Path, *, limit: int = 5) -> int:
    """Read a no-write main-database snapshot.

    ``immutable=1`` prevents SQLite from creating ``-shm``/``-wal`` files,
    which even ``mode=ro`` may do. The explicit tradeoff is bounded semantic
    freshness: rows committed only to a live WAL are not reported until a
    checkpoint moves them into the main database. Status prefers a stale
    observation over mutating the system it observes.
    """
    if not db_path.is_file():
        return 0
    uri = f"{db_path.resolve().as_uri()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as db:
        row = db.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM memories ORDER BY timestamp DESC LIMIT ?)",
            (limit,),
        ).fetchone()
    return int(row[0]) if row is not None else 0
