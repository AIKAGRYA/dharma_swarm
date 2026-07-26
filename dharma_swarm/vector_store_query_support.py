"""Query-side ranking/filtering helpers for VectorStore.

Extracted verbatim from vector_store.py (which re-imports them under their
original underscore names, so existing monkeypatch targets keep working):
low-signal query detection, candidate lexical-overlap ranking, the
memory-retrieval prefilter probe, and the small-store lexical recovery
search. Pure functions over a connection/rows — no VectorStore state.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from dharma_swarm.vector_fallback_guard import fallback_vector_scan_allowed

_FTS_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_LOW_SIGNAL_QUERY_TERMS = {
    "about",
    "document",
    "documents",
    "entry",
    "memory",
    "query",
    "retrieval",
    "search",
    "system",
    "topic",
}


def fts_match_query(query_text: str) -> str:
    """Return a conservative FTS5 MATCH expression for arbitrary operator text."""

    terms = [term for term in _FTS_TOKEN_RE.findall(query_text) if len(term) > 1]
    return " OR ".join(f'"{term}"' for term in terms)


def is_degenerate_query_embedding(query_text: str, query_vec: list[float]) -> bool:
    """Detect low-information query vectors that cause false-positive ANN hits."""

    query_terms = [term for term in _FTS_TOKEN_RE.findall(query_text) if len(term) > 1]
    if len(query_terms) <= 1:
        return False
    active_dims = sum(1 for value in query_vec if abs(float(value)) > 1e-9)
    return active_dims <= 1


def candidate_has_query_lexical_signal(query_text: str, row: dict[str, Any]) -> bool:
    query_terms = query_signal_terms(query_text)
    if not query_terms:
        return False
    return candidate_query_signal_count(query_terms, row) > 0


def query_signal_terms(query_text: str) -> set[str]:
    return {
        term.lower()
        for term in _FTS_TOKEN_RE.findall(query_text)
        if len(term) > 1 and term.lower() not in _LOW_SIGNAL_QUERY_TERMS
    }


def candidate_query_signal_count(
    query_terms: set[str],
    row: dict[str, Any],
    *,
    field: str = "all",
) -> int:
    if not query_terms:
        return 0
    if field == "prefix":
        candidate_text = str(row.get("content", ""))[:360]
    elif field == "source":
        candidate_text = str(row.get("source", ""))
    else:
        candidate_text = f"{row.get('content', '')} {row.get('source', '')}"
    candidate_terms = {
        term.lower()
        for term in _FTS_TOKEN_RE.findall(candidate_text)
        if len(term) > 1
    }
    return len(query_terms & candidate_terms)


def filter_and_rank_vector_results(
    query_text: str,
    results: list[dict[str, Any]],
    *,
    degenerate_query: bool,
    memory_prefilter: bool,
) -> list[dict[str, Any]]:
    query_terms = query_signal_terms(query_text)
    ranked: list[tuple[tuple[int, int, int, float], dict[str, Any]]] = []
    min_overlap = 2 if len(query_terms) >= 3 else 1
    for row in results:
        distance = float(row.get("distance", 1.0) or 1.0)
        overlap = candidate_query_signal_count(query_terms, row)
        if degenerate_query or memory_prefilter:
            if overlap < min_overlap:
                continue
        prefix_overlap = candidate_query_signal_count(query_terms, row, field="prefix")
        source_overlap = candidate_query_signal_count(query_terms, row, field="source")
        ranked.append(((-prefix_overlap, -source_overlap, -overlap, distance), row))
    if not ranked and not (degenerate_query or memory_prefilter):
        return results
    ranked.sort(key=lambda item: item[0])
    return [row for _rank, row in ranked]


def memory_retrieval_prefilter_available(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute("SELECT vec_doc_id FROM memory_retrieval_docs LIMIT 1").fetchone()
        return row is not None
    except Exception:
        return False


def lexical_recovery_search(
    conn: sqlite3.Connection,
    db_path: Path,
    query_text: str,
    top_k: int,
    include_invalid: bool,
    *,
    memory_prefilter: bool,
) -> list[dict[str, Any]]:
    """Recover small-store vector searches when embeddings are unavailable."""

    if not fallback_vector_scan_allowed(db_path, conn):
        return []
    query_terms = query_signal_terms(query_text)
    if not query_terms:
        return []
    fts_query = " OR ".join(f'"{term}"' for term in sorted(query_terms))
    validity_clause = "" if include_invalid else "AND d.valid_until IS NULL"
    memory_clause = (
        "AND d.id IN (SELECT vec_doc_id FROM memory_retrieval_docs)"
        if memory_prefilter
        else ""
    )
    try:
        rows = conn.execute(f"""
            SELECT d.id, d.content, d.source, d.layer,
                   d.metadata_json, d.event_time, d.ingestion_time,
                   d.valid_until, d.confidence, d.access_count,
                   d.last_accessed,
                   bm25(vec_fts) AS bm25_score
            FROM vec_fts
            JOIN vec_documents d ON d.id = vec_fts.rowid
            WHERE vec_fts MATCH ?
              {validity_clause}
              {memory_clause}
            ORDER BY bm25_score
            LIMIT ?
        """, (fts_query, max(top_k * 10, 50))).fetchall()
    except Exception:
        return []

    from dharma_swarm.vector_store import VectorStore  # circular at import time only

    results: list[dict[str, Any]] = []
    for row in rows:
        bm25 = float(row["bm25_score"] or 0.0)
        distance = max(0.0, min(1.0, 1.0 + bm25 / 20.0))
        results.append(VectorStore._row_to_dict_static(row, distance=distance))
    return filter_and_rank_vector_results(
        query_text,
        results,
        degenerate_query=True,
        memory_prefilter=memory_prefilter,
    )[:top_k]
