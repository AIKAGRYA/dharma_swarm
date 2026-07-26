"""Safety guard for Python-side vector fallback scans."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_FALLBACK_MAX_DB_BYTES = 256 * 1024 * 1024
DEFAULT_FALLBACK_MAX_ROWS = 50_000
DEFAULT_FTS_MAX_DB_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_FTS_MAX_ROWS = 250_000


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def fallback_vector_scan_allowed(db_path: Path, conn: sqlite3.Connection) -> bool:
    """Return whether Python-side vector fallback may scan all embeddings.

    Without sqlite-vec, fallback similarity is O(n): it loads every fallback
    embedding row and computes cosine similarity in Python. That is fine for
    small local fixtures, but unsafe for live stores; large stores should
    degrade to text search instead of blocking daemon dispatch.
    """
    max_bytes = _env_int(
        "DHARMA_VECTOR_FALLBACK_MAX_DB_BYTES",
        DEFAULT_FALLBACK_MAX_DB_BYTES,
    )
    if max_bytes > 0:
        try:
            if db_path.exists() and db_path.stat().st_size > max_bytes:
                return False
        except OSError:
            return False

    max_rows = _env_int(
        "DHARMA_VECTOR_FALLBACK_MAX_ROWS",
        DEFAULT_FALLBACK_MAX_ROWS,
    )
    if max_rows > 0:
        try:
            row = conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'vec_documents'"
            ).fetchone()
            if row is not None and int(row[0] or 0) > max_rows:
                return False
        except Exception:
            return False

    return True


def fts_search_allowed(db_path: Path, conn: sqlite3.Connection) -> bool:
    """Return whether globally ranked FTS5 retrieval is safe for this store.

    ``LIMIT`` does not bound the work required by ``ORDER BY bm25(...)``.
    SQLite can scan a large FTS projection and its docsize table before it can
    return even one row. Live callers must degrade to the bounded retrieval
    path instead of blocking the daemon's event loop on multi-gigabyte stores.
    """
    max_bytes = _env_int(
        "DHARMA_VECTOR_FTS_MAX_DB_BYTES",
        DEFAULT_FTS_MAX_DB_BYTES,
    )
    if max_bytes > 0:
        try:
            if db_path.exists() and db_path.stat().st_size > max_bytes:
                return False
        except OSError:
            return False

    max_rows = _env_int(
        "DHARMA_VECTOR_FTS_MAX_ROWS",
        DEFAULT_FTS_MAX_ROWS,
    )
    if max_rows > 0:
        try:
            row = conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'vec_documents'"
            ).fetchone()
            if row is not None and int(row[0] or 0) > max_rows:
                return False
        except Exception:
            return False

    return True
