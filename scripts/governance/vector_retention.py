#!/usr/bin/env python3
"""Vector store retention CLI — inspection + gc dry-run for ~/.dharma/vectors.db.

NOTE ON VACUUM: this script NEVER runs VACUUM. On a 56+ GiB SQLite db VACUUM
is offline-only operator maintenance (it rewrites the entire file and can take
hours while holding an exclusive lock). Reclaiming freed pages from gc is a
separate, operator-scheduled, offline task. This tool only reports size and
deletion candidates and, with --execute, runs gc() which issues DELETEs but
does not VACUUM.

Usage:
    python scripts/governance/vector_retention.py            # dry-run (default)
    python scripts/governance/vector_retention.py --execute  # actually gc()
    python scripts/governance/vector_retention.py --min-confidence 0.05
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Resolve repo root so `dharma_swarm` is importable when run from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.vector_store import VectorStore  # noqa: E402


def _db_path() -> Path:
    return Path(os.path.expanduser(os.environ.get("DHARMA_VECTORS_DB", "~/.dharma/vectors.db")))


def _db_size_bytes(db_path: Path) -> int:
    try:
        return os.path.getsize(db_path)
    except OSError:
        return -1


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return -1


def _sqlite_sequence(conn: sqlite3.Connection, table: str) -> int | None:
    """Return the autoincrement seq value for `table` from sqlite_sequence, or None."""
    try:
        row = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)
        ).fetchone()
        return int(row[0]) if row else None
    except sqlite3.Error:
        return None


def _guard_env_vars() -> list[tuple[str, str]]:
    """Report the guard env-var names the VectorStore reads, if present.

    Scans the vector_store module source for os.environ.get(...) calls whose
    names mention FTS/FALLBACK/VECTOR/VDB thresholds, so the operator can pick
    values. Returns (env_name, current_value) pairs.
    """
    import inspect
    import re

    found: list[tuple[str, str]] = []
    # Known retrieval-guard threshold env-vars the VectorStore reads via
    # _env_int(). These are part of the VectorStore contract; listing them
    # explicitly is more robust than source-scanning, because _env_int wraps
    # os.environ.get so the literal name does not appear next to the call.
    known = [
        "DHARMA_VECTOR_FTS_MAX_DB_BYTES",
        "DHARMA_VECTOR_FTS_MAX_ROWS",
        "DHARMA_VECTOR_FALLBACK_MAX_DB_BYTES",
        "DHARMA_VECTOR_FALLBACK_MAX_ROWS",
    ]
    seen = set()
    for name in known:
        found.append((name, os.environ.get(name, "<unset>")))
        seen.add(name)
    # Also scan the source for any os.environ.get("...") calls with these
    # keywords, to pick up future guard vars without a CLI edit.
    try:
        mod = sys.modules.get(VectorStore.__module__)
        src = inspect.getsource(mod) if mod else ""
    except Exception:
        src = ""
    for m in re.finditer(r"os\.environ\.get\(\s*['\"]([^'\"]+)['\"]", src):
        env_name = m.group(1)
        if env_name in seen:
            continue
        if any(k in env_name.upper() for k in ("FTS", "FALLBACK", "VECTOR", "VDB")):
            found.append((env_name, os.environ.get(env_name, "<unset>")))
            seen.add(env_name)
    return found


def _format_bytes(n: int) -> str:
    if n < 0:
        return "n/a"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} TiB"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vector store retention: inspect + gc dry-run (no VACUUM)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run gc() (deletes rows). Default is dry-run (deletes nothing).",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.01,
        help="Confidence threshold for gc() (default 0.01).",
    )
    args = parser.parse_args()

    db_path = _db_path()
    size = _db_size_bytes(db_path)

    print("=" * 70)
    print("vector store retention — " + ("EXECUTE" if args.execute else "DRY-RUN"))
    print("=" * 70)
    print(f"db path        : {db_path}")
    print(f"db size        : {_format_bytes(size)}  ({size} bytes)")
    if not db_path.exists():
        print(f"\n[warn] db not found at {db_path}; nothing to do.")
        return 0

    # Row counts (read-only; uses a separate connection so gc's connection is untouched).
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total = _row_count(conn, "vec_documents")
        seq = _sqlite_sequence(conn, "vec_documents")
        fts_rows = _row_count(conn, "vec_fts")
    finally:
        conn.close()

    print(f"vec_documents  : {total} rows")
    if seq is not None:
        print(f"sqlite_sequence: seq={seq} for vec_documents")
    print(f"vec_fts        : {fts_rows} rows")

    # Guard env-var report (if the guards exist in this build).
    env_vars = _guard_env_vars()
    if env_vars:
        print("\nretrieval guard env-vars:")
        for name, val in env_vars:
            print(f"  {name} = {val}")
    else:
        print("\nretrieval guard env-vars: none detected in this build "
              "(no _fts_search_allowed / _fallback_vector_scan_allowed).")

    # gc — VectorStore requires state_dir; db_path = state_dir / "vectors.db".
    state_dir = db_path.parent
    store = VectorStore(state_dir=state_dir)
    if args.execute:
        print(f"\ngc(execute) min_confidence={args.min_confidence} ...")
        rc = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        before = _row_count(rc, "vec_documents")
        rc.close()
        removed = store.gc(min_confidence=args.min_confidence, dry_run=False)
        print(f"removed: {removed} rows")
        rc = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        after = _row_count(rc, "vec_documents")
        rc.close()
        print(f"vec_documents before={before} after={after} delta={before - after}")
        print("\n[NOTE] VACUUM was NOT run. Reclaiming disk space is a separate "
              "offline operator task on a 56+ GiB db.")
    else:
        print(f"\ngc(dry-run) min_confidence={args.min_confidence} ...")
        result = store.gc(min_confidence=args.min_confidence, dry_run=True)
        print(f"would_remove: {result.get('would_remove', 0)}")
        by_layer = result.get("by_layer", {})
        if by_layer:
            print("by_layer:")
            for layer, cnt in sorted(by_layer.items()):
                print(f"  {layer}: {cnt}")
        print("\n[NOTE] dry-run deleted NOTHING. Re-run with --execute to apply.")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())