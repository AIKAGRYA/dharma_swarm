#!/usr/bin/env python3
"""Targeted live VectorStore re-embedding into sqlite-vec vec0.

Use this after dependency activation when old fallback embeddings are zero or
stale.  Candidate selection is bounded by FTS LIMITs; writes only update the
retrieval projection table.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.vector_store import TFIDFEmbedder, VectorStore, _fts_match_query


@dataclass(frozen=True)
class ReembedReceipt:
    state_dir: str
    db_path: str
    started_at: str
    finished_at: str
    dim: int
    query_count: int
    selected_rows: int
    upserted_rows: int
    elapsed_ms: float
    queries: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=str(dharma_state_dir()))
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--limit-per-query", type=int, default=100)
    parser.add_argument("--memory-retrieval-docs", action="store_true")
    parser.add_argument("--memory-doc-limit", type=int, default=1000)
    parser.add_argument("--replace-embedder-corpus", action="store_true")
    parser.add_argument("--dim", type=int, default=128)
    parser.add_argument("--rank-bm25", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.query and not args.memory_retrieval_docs:
        raise SystemExit("at least one --query or --memory-retrieval-docs is required")
    receipt = reembed_queries(
        state_dir=Path(args.state_dir).expanduser(),
        queries=tuple(args.query),
        limit_per_query=max(1, args.limit_per_query),
        include_memory_retrieval_docs=bool(args.memory_retrieval_docs),
        memory_doc_limit=max(1, args.memory_doc_limit),
        replace_embedder_corpus=bool(args.replace_embedder_corpus),
        dim=max(1, args.dim),
        dry_run=bool(args.dry_run),
        rank_bm25=bool(args.rank_bm25),
    )
    if args.receipt_path:
        path = Path(args.receipt_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(receipt.to_json(), indent=2, sort_keys=True))
    else:
        print(render_receipt(receipt))
    return 0


def reembed_queries(
    *,
    state_dir: Path,
    queries: tuple[str, ...],
    limit_per_query: int,
    dim: int,
    include_memory_retrieval_docs: bool = False,
    memory_doc_limit: int = 1000,
    replace_embedder_corpus: bool = False,
    dry_run: bool = False,
    rank_bm25: bool = False,
) -> ReembedReceipt:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    store = VectorStore(state_dir=state_dir, dim=dim)
    embedder_state_path = state_dir / (
        "tfidf_embedder_memory_retrieval.pkl"
        if include_memory_retrieval_docs
        else "tfidf_embedder.pkl"
    )
    embedder = TFIDFEmbedder(dim=dim, state_path=embedder_state_path)
    selected: dict[int, tuple[str, str]] = {}
    query_receipts: list[dict[str, Any]] = []
    warnings: list[str] = []
    conn = store._connect()
    try:
        has_vec0 = store._has_vec0(conn)
        if not has_vec0:
            warnings.append("vec0_unavailable")
        for query in queries:
            fts_query = _fts_match_query(query)
            rows = []
            if fts_query:
                if rank_bm25:
                    rows = conn.execute(
                        """
                        SELECT d.id, d.content, d.source, bm25(vec_fts) AS bm25_score
                        FROM vec_fts
                        JOIN vec_documents d ON d.id = vec_fts.rowid
                        WHERE vec_fts MATCH ?
                          AND d.valid_until IS NULL
                        ORDER BY bm25_score
                        LIMIT ?
                        """,
                        (fts_query, limit_per_query),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT d.id, d.content, d.source
                        FROM vec_fts
                        JOIN vec_documents d ON d.id = vec_fts.rowid
                        WHERE vec_fts MATCH ?
                          AND d.valid_until IS NULL
                        LIMIT ?
                        """,
                        (fts_query, limit_per_query),
                    ).fetchall()
            for row in rows:
                selected[int(row["id"])] = (str(row["content"]), str(row["source"] or ""))
            query_receipts.append(
                {
                    "query": query,
                    "fts_query": fts_query,
                    "selected_rows": len(rows),
                    "sample_ids": [int(row["id"]) for row in rows[:5]],
                }
            )
        if include_memory_retrieval_docs:
            try:
                rows = conn.execute(
                    """
                    SELECT vec_doc_id AS id, content, source
                    FROM memory_retrieval_docs
                    WHERE valid_until IS NULL
                    ORDER BY vec_doc_id
                    LIMIT ?
                    """,
                    (memory_doc_limit,),
                ).fetchall()
            except Exception as exc:
                rows = []
                warnings.append(f"memory_retrieval_docs_unavailable:{type(exc).__name__}")
            for row in rows:
                selected[int(row["id"])] = (
                    str(row["content"]),
                    str(row["source"] or ""),
                )
            query_receipts.append(
                {
                    "query": "memory_retrieval_docs",
                    "fts_query": "",
                    "selected_rows": len(rows),
                    "sample_ids": [int(row["id"]) for row in rows[:5]],
                }
            )
        texts = [content for content, _source in selected.values()]
        upserted = 0
        if texts and not dry_run:
            if replace_embedder_corpus:
                embedder.fit_replace(texts)
            else:
                embedder.fit_add(texts)
            vectors = embedder.embed(texts)
            if not has_vec0:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vec_embeddings_fallback (
                        rowid INTEGER PRIMARY KEY,
                        embedding BLOB
                    )
                    """
                )
            for (doc_id, (_content, _source)), vector in zip(selected.items(), vectors):
                if not vector or len(vector) != dim:
                    warnings.append(f"bad_vector_dim:{doc_id}")
                    continue
                packed = struct.pack(f"{dim}f", *vector)
                if has_vec0:
                    conn.execute("DELETE FROM vec_embeddings WHERE rowid = ?", (doc_id,))
                    conn.execute(
                        "INSERT INTO vec_embeddings(rowid, embedding) VALUES (?, ?)",
                        (doc_id, packed),
                    )
                else:
                    conn.execute(
                        "DELETE FROM vec_embeddings_fallback WHERE rowid = ?",
                        (doc_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO vec_embeddings_fallback(rowid, embedding)
                        VALUES (?, ?)
                        """,
                        (doc_id, packed),
                    )
                upserted += 1
            conn.commit()
        return _receipt(
            state_dir=state_dir,
            store=store,
            started=started,
            t0=t0,
            dim=dim,
            queries=query_receipts,
            selected_rows=len(selected),
            upserted_rows=upserted,
            warnings=warnings,
        )
    finally:
        conn.close()


def _receipt(
    *,
    state_dir: Path,
    store: VectorStore,
    started: datetime,
    t0: float,
    dim: int,
    queries: list[dict[str, Any]],
    selected_rows: int,
    upserted_rows: int,
    warnings: list[str],
) -> ReembedReceipt:
    return ReembedReceipt(
        state_dir=str(state_dir),
        db_path=str(store._db_path),
        started_at=started.isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        dim=dim,
        query_count=len(queries),
        selected_rows=selected_rows,
        upserted_rows=upserted_rows,
        elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        queries=tuple(queries),
        warnings=tuple(warnings),
    )


def render_receipt(receipt: ReembedReceipt) -> str:
    lines = [
        "# VectorStore Targeted vec0 Re-embed",
        "",
        f"- State dir: `{receipt.state_dir}`",
        f"- DB path: `{receipt.db_path}`",
        f"- Dim: `{receipt.dim}`",
        f"- Query count: `{receipt.query_count}`",
        f"- Selected rows: `{receipt.selected_rows}`",
        f"- Upserted rows: `{receipt.upserted_rows}`",
        f"- Elapsed ms: `{receipt.elapsed_ms}`",
    ]
    for query in receipt.queries:
        lines.append(
            f"- Query `{query['query']}` selected `{query['selected_rows']}` rows; "
            f"sample ids `{query['sample_ids']}`"
        )
    if receipt.warnings:
        lines.append(f"- Warnings: `{', '.join(receipt.warnings)}`")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
