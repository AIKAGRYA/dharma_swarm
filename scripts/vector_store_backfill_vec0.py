#!/usr/bin/env python3
"""Backfill VectorStore fallback embeddings into sqlite-vec vec0.

This is a bounded, resumable projection repair tool.  It does not rebuild
content, rewrite source documents, or touch MemoryKernel authority surfaces.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.vector_store import VectorStore


@dataclass(frozen=True)
class BackfillReceipt:
    state_dir: str
    db_path: str
    started_at: str
    finished_at: str
    dry_run: bool
    batch_size: int
    max_rows: int
    start_rowid: int
    last_rowid: int
    selected_rows: int
    inserted_rows: int
    batch_count: int
    elapsed_ms: float
    vec0_has_rows: bool | None
    fallback_has_rows: bool | None
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=str(Path.home() / ".dharma"))
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-rows", type=int, default=1000)
    parser.add_argument("--start-rowid", type=int, default=-1)
    parser.add_argument("--cursor-path", default="")
    parser.add_argument("--reset-cursor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repair-empty-vec0-dim", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_dir = Path(args.state_dir).expanduser()
    cursor_path = Path(args.cursor_path).expanduser() if args.cursor_path else (
        state_dir / "vector_backfill_vec0_cursor.json"
    )
    receipt = backfill_vec0(
        state_dir=state_dir,
        batch_size=max(1, args.batch_size),
        max_rows=max(0, args.max_rows),
        start_rowid=args.start_rowid,
        cursor_path=cursor_path,
        reset_cursor=bool(args.reset_cursor),
        dry_run=bool(args.dry_run),
        repair_empty_vec0_dim=bool(args.repair_empty_vec0_dim),
    )
    if args.receipt_path:
        receipt_path = Path(args.receipt_path).expanduser()
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(receipt.to_json(), indent=2, sort_keys=True))
    else:
        print(render_receipt(receipt))
    return 0


def backfill_vec0(
    *,
    state_dir: Path,
    batch_size: int,
    max_rows: int,
    start_rowid: int = -1,
    cursor_path: Path | None = None,
    reset_cursor: bool = False,
    dry_run: bool = False,
    repair_empty_vec0_dim: bool = False,
) -> BackfillReceipt:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    store = VectorStore(state_dir=state_dir)
    selected_rows = 0
    inserted_rows = 0
    batch_count = 0
    warnings: list[str] = []
    conn = store._connect()
    try:
        if not store._has_vec0(conn):
            warnings.append("vec0_unavailable")
            last_rowid = max(0, start_rowid)
            return _receipt(
                state_dir=state_dir,
                store=store,
                started=started,
                t0=t0,
                dry_run=dry_run,
                batch_size=batch_size,
                max_rows=max_rows,
                start_rowid=last_rowid,
                last_rowid=last_rowid,
                selected_rows=0,
                inserted_rows=0,
                batch_count=0,
                warnings=warnings,
                conn=conn,
            )
        if not _table_exists(conn, "vec_embeddings_fallback"):
            warnings.append("fallback_table_unavailable")
            last_rowid = max(0, start_rowid)
            return _receipt(
                state_dir=state_dir,
                store=store,
                started=started,
                t0=t0,
                dry_run=dry_run,
                batch_size=batch_size,
                max_rows=max_rows,
                start_rowid=last_rowid,
                last_rowid=last_rowid,
                selected_rows=0,
                inserted_rows=0,
                batch_count=0,
                warnings=warnings,
                conn=conn,
            )
        if _table_has_sample(conn, "vec_embeddings_fallback") is False:
            warnings.append("fallback_embeddings_empty")
        elif repair_empty_vec0_dim and _table_has_sample(conn, "vec_embeddings") is False:
            repaired_dim = repair_empty_vec0_dimension(conn)
            if repaired_dim:
                warnings.append(f"repaired_empty_vec0_dimension:{repaired_dim}")

        resolved_start = resolve_start_rowid(
            requested_start=start_rowid,
            cursor_path=cursor_path,
            reset_cursor=reset_cursor,
        )
        last_rowid = resolved_start
        remaining = max_rows
        while remaining > 0:
            limit = min(batch_size, remaining)
            rows = conn.execute(
                """
                SELECT f.rowid, f.embedding
                FROM vec_embeddings_fallback f
                WHERE f.rowid > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM vec_embeddings e WHERE e.rowid = f.rowid
                  )
                ORDER BY f.rowid
                LIMIT ?
                """,
                (last_rowid, limit),
            ).fetchall()
            if not rows:
                break
            batch_count += 1
            selected_rows += len(rows)
            last_rowid = int(rows[-1]["rowid"])
            if not dry_run:
                conn.executemany(
                    "INSERT INTO vec_embeddings(rowid, embedding) VALUES (?, ?)",
                    [(int(row["rowid"]), row["embedding"]) for row in rows],
                )
                conn.commit()
                inserted_rows += len(rows)
                write_cursor(cursor_path, state_dir=state_dir, last_rowid=last_rowid)
            remaining -= len(rows)
            if dry_run:
                break

        return _receipt(
            state_dir=state_dir,
            store=store,
            started=started,
            t0=t0,
            dry_run=dry_run,
            batch_size=batch_size,
            max_rows=max_rows,
            start_rowid=resolved_start,
            last_rowid=last_rowid,
            selected_rows=selected_rows,
            inserted_rows=inserted_rows,
            batch_count=batch_count,
            warnings=warnings,
            conn=conn,
        )
    finally:
        conn.close()


def resolve_start_rowid(
    *,
    requested_start: int,
    cursor_path: Path | None,
    reset_cursor: bool,
) -> int:
    if requested_start >= 0:
        return requested_start
    if reset_cursor or cursor_path is None or not cursor_path.exists():
        return 0
    try:
        payload = json.loads(cursor_path.read_text(encoding="utf-8"))
        return max(0, int(payload.get("last_rowid", 0)))
    except Exception:
        return 0


def write_cursor(cursor_path: Path | None, *, state_dir: Path, last_rowid: int) -> None:
    if cursor_path is None:
        return
    payload = {
        "schema_version": 1,
        "state_dir": str(state_dir),
        "last_rowid": int(last_rowid),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def repair_empty_vec0_dimension(conn: Any) -> int | None:
    sample = conn.execute(
        "SELECT embedding FROM vec_embeddings_fallback ORDER BY rowid LIMIT 1"
    ).fetchone()
    if sample is None:
        return None
    embedding = sample["embedding"] if hasattr(sample, "keys") else sample[0]
    dim = int(len(embedding) // 4)
    if dim <= 0:
        return None
    try:
        conn.execute("SAVEPOINT vec0_dim_probe")
        conn.execute(
            "INSERT INTO vec_embeddings(rowid, embedding) VALUES (?, ?)",
            (0, embedding),
        )
        conn.execute("ROLLBACK TO vec0_dim_probe")
        conn.execute("RELEASE vec0_dim_probe")
        return None
    except Exception as exc:
        try:
            conn.execute("ROLLBACK TO vec0_dim_probe")
            conn.execute("RELEASE vec0_dim_probe")
        except Exception:
            pass
        if "dimension mismatch" not in str(exc).lower():
            raise

    conn.execute("DROP TABLE IF EXISTS vec_embeddings")
    conn.execute(f"""
        CREATE VIRTUAL TABLE vec_embeddings
        USING vec0(
            embedding float[{dim}]
        )
    """)
    conn.commit()
    return dim


def _receipt(
    *,
    state_dir: Path,
    store: VectorStore,
    started: datetime,
    t0: float,
    dry_run: bool,
    batch_size: int,
    max_rows: int,
    start_rowid: int,
    last_rowid: int,
    selected_rows: int,
    inserted_rows: int,
    batch_count: int,
    warnings: list[str],
    conn: Any,
) -> BackfillReceipt:
    return BackfillReceipt(
        state_dir=str(state_dir),
        db_path=str(store._db_path),
        started_at=started.isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        dry_run=dry_run,
        batch_size=batch_size,
        max_rows=max_rows,
        start_rowid=start_rowid,
        last_rowid=last_rowid,
        selected_rows=selected_rows,
        inserted_rows=inserted_rows,
        batch_count=batch_count,
        elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        vec0_has_rows=_table_has_sample(conn, "vec_embeddings"),
        fallback_has_rows=_table_has_sample(conn, "vec_embeddings_fallback"),
        warnings=tuple(warnings),
    )


def _table_has_sample(conn: Any, table: str) -> bool | None:
    try:
        return conn.execute(f"SELECT rowid FROM {table} LIMIT 1").fetchone() is not None
    except Exception:
        return None


def _table_exists(conn: Any, table: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_schema WHERE name = ? LIMIT 1",
            (table,),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def render_receipt(receipt: BackfillReceipt) -> str:
    lines = [
        "# VectorStore vec0 Backfill",
        "",
        f"- State dir: `{receipt.state_dir}`",
        f"- DB path: `{receipt.db_path}`",
        f"- Dry run: `{str(receipt.dry_run).lower()}`",
        f"- Batch size: `{receipt.batch_size}`",
        f"- Max rows: `{receipt.max_rows}`",
        f"- Start rowid: `{receipt.start_rowid}`",
        f"- Last rowid: `{receipt.last_rowid}`",
        f"- Selected rows: `{receipt.selected_rows}`",
        f"- Inserted rows: `{receipt.inserted_rows}`",
        f"- Batch count: `{receipt.batch_count}`",
        f"- Elapsed ms: `{receipt.elapsed_ms}`",
        f"- vec0 has rows: `{receipt.vec0_has_rows}`",
        f"- fallback has rows: `{receipt.fallback_has_rows}`",
    ]
    if receipt.warnings:
        lines.append(f"- Warnings: `{', '.join(receipt.warnings)}`")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
