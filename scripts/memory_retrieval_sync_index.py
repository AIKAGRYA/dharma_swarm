#!/usr/bin/env python3
"""Build a compact FTS index over curated memory/source rows."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.vector_store import VectorStore


CURATED_LAYERS = ("memory_context", "memory_graph", "source_file")


@dataclass(frozen=True)
class MemoryRetrievalIndexReceipt:
    state_dir: str
    indexed_rows: int
    elapsed_ms: float
    min_doc_id: int
    recent_row_window: int
    full_scan: bool
    layers: tuple[str, ...] = CURATED_LAYERS

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def sync_memory_retrieval_index(
    *,
    state_dir: Path,
    dim: int = 128,
    recent_row_window: int = 1_000_000,
    full_scan: bool = False,
) -> MemoryRetrievalIndexReceipt:
    started = time.perf_counter()
    store = VectorStore(state_dir=Path(state_dir).expanduser(), dim=dim)
    conn = store._connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_retrieval_docs (
                vec_doc_id INTEGER PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                layer TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                event_time TEXT,
                ingestion_time TEXT,
                valid_until TEXT,
                confidence REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_retrieval_fts
            USING fts5(
                content,
                source,
                layer,
                content='memory_retrieval_docs',
                content_rowid='vec_doc_id'
            )
            """
        )
        conn.execute("DELETE FROM memory_retrieval_docs")
        placeholders = ",".join("?" for _ in CURATED_LAYERS)
        min_doc_id = 0
        if not full_scan and recent_row_window > 0:
            row = conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'vec_documents'"
            ).fetchone()
            row_estimate = int(row[0] or 0) if row is not None else 0
            min_doc_id = max(0, row_estimate - recent_row_window)
        rows = conn.execute(
            f"""
            SELECT id, content, source, layer, metadata_json, event_time,
                   ingestion_time, valid_until, confidence, access_count,
                   last_accessed
            FROM vec_documents
            WHERE layer IN ({placeholders})
              AND id >= ?
            """,
            (*CURATED_LAYERS, min_doc_id),
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO memory_retrieval_docs (
                vec_doc_id, content, source, layer, metadata_json, event_time,
                ingestion_time, valid_until, confidence, access_count,
                last_accessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["content"],
                    row["source"],
                    row["layer"],
                    row["metadata_json"],
                    row["event_time"],
                    row["ingestion_time"],
                    row["valid_until"],
                    row["confidence"],
                    row["access_count"],
                    row["last_accessed"],
                )
                for row in rows
            ],
        )
        conn.execute("INSERT INTO memory_retrieval_fts(memory_retrieval_fts) VALUES ('rebuild')")
        _install_triggers(conn)
        conn.commit()
        return MemoryRetrievalIndexReceipt(
            state_dir=str(Path(state_dir).expanduser()),
            indexed_rows=len(rows),
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            min_doc_id=min_doc_id,
            recent_row_window=recent_row_window,
            full_scan=full_scan,
        )
    finally:
        conn.close()


def _install_triggers(conn) -> None:
    conn.execute("DROP TRIGGER IF EXISTS memory_retrieval_vec_ai")
    conn.execute("DROP TRIGGER IF EXISTS memory_retrieval_vec_ad")
    conn.execute("DROP TRIGGER IF EXISTS memory_retrieval_vec_au_refresh")
    conn.execute("DROP TRIGGER IF EXISTS memory_retrieval_vec_au_delete_old")
    conn.execute("DROP TRIGGER IF EXISTS memory_retrieval_vec_au_insert_new")
    conn.execute(
        """
        CREATE TRIGGER memory_retrieval_vec_ai
        AFTER INSERT ON vec_documents
        WHEN new.layer IN ('memory_context', 'memory_graph', 'source_file')
        BEGIN
            INSERT OR REPLACE INTO memory_retrieval_docs (
                vec_doc_id, content, source, layer, metadata_json, event_time,
                ingestion_time, valid_until, confidence, access_count,
                last_accessed
            )
            VALUES (
                new.id, new.content, new.source, new.layer, new.metadata_json,
                new.event_time, new.ingestion_time, new.valid_until,
                new.confidence, new.access_count, new.last_accessed
            );
            INSERT INTO memory_retrieval_fts(rowid, content, source, layer)
            VALUES (new.id, new.content, new.source, new.layer);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER memory_retrieval_vec_ad
        AFTER DELETE ON vec_documents
        WHEN old.layer IN ('memory_context', 'memory_graph', 'source_file')
        BEGIN
            INSERT INTO memory_retrieval_fts(memory_retrieval_fts, rowid, content, source, layer)
            VALUES ('delete', old.id, old.content, old.source, old.layer);
            DELETE FROM memory_retrieval_docs WHERE vec_doc_id = old.id;
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER memory_retrieval_vec_au_refresh
        AFTER UPDATE ON vec_documents
        WHEN old.layer IN ('memory_context', 'memory_graph', 'source_file')
         AND new.layer IN ('memory_context', 'memory_graph', 'source_file')
        BEGIN
            INSERT INTO memory_retrieval_fts(memory_retrieval_fts, rowid, content, source, layer)
            VALUES ('delete', old.id, old.content, old.source, old.layer);
            DELETE FROM memory_retrieval_docs WHERE vec_doc_id = old.id;
            INSERT OR REPLACE INTO memory_retrieval_docs (
                vec_doc_id, content, source, layer, metadata_json, event_time,
                ingestion_time, valid_until, confidence, access_count,
                last_accessed
            )
            VALUES (
                new.id, new.content, new.source, new.layer, new.metadata_json,
                new.event_time, new.ingestion_time, new.valid_until,
                new.confidence, new.access_count, new.last_accessed
            );
            INSERT INTO memory_retrieval_fts(rowid, content, source, layer)
            VALUES (new.id, new.content, new.source, new.layer);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER memory_retrieval_vec_au_delete_old
        AFTER UPDATE ON vec_documents
        WHEN old.layer IN ('memory_context', 'memory_graph', 'source_file')
         AND coalesce(new.layer, '') NOT IN ('memory_context', 'memory_graph', 'source_file')
        BEGIN
            INSERT INTO memory_retrieval_fts(memory_retrieval_fts, rowid, content, source, layer)
            VALUES ('delete', old.id, old.content, old.source, old.layer);
            DELETE FROM memory_retrieval_docs WHERE vec_doc_id = old.id;
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER memory_retrieval_vec_au_insert_new
        AFTER UPDATE ON vec_documents
        WHEN coalesce(old.layer, '') NOT IN ('memory_context', 'memory_graph', 'source_file')
         AND new.layer IN ('memory_context', 'memory_graph', 'source_file')
        BEGIN
            INSERT OR REPLACE INTO memory_retrieval_docs (
                vec_doc_id, content, source, layer, metadata_json, event_time,
                ingestion_time, valid_until, confidence, access_count,
                last_accessed
            )
            VALUES (
                new.id, new.content, new.source, new.layer, new.metadata_json,
                new.event_time, new.ingestion_time, new.valid_until,
                new.confidence, new.access_count, new.last_accessed
            );
            INSERT INTO memory_retrieval_fts(rowid, content, source, layer)
            VALUES (new.id, new.content, new.source, new.layer);
        END
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=dharma_state_dir())
    parser.add_argument("--dim", type=int, default=128)
    parser.add_argument("--recent-row-window", type=int, default=1_000_000)
    parser.add_argument("--full-scan", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-path", type=Path)
    args = parser.parse_args()

    receipt = sync_memory_retrieval_index(
        state_dir=args.state_dir,
        dim=args.dim,
        recent_row_window=args.recent_row_window,
        full_scan=args.full_scan,
    )
    payload = receipt.to_json()
    if args.receipt_path:
        args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"indexed {receipt.indexed_rows} curated memory rows in {receipt.elapsed_ms}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
