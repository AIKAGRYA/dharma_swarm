"""Sidecar-scan and identity/title/source matching helpers.

Split out of ``memory_retrieval.py`` (Rule 10 module-line-budget
decomposition). Depends on ``scoring_terms.py`` for term normalization and
overlap scoring; both are private implementation helpers of the governed
retrieval door in ``memory_retrieval.py``, which imports the names it needs
back for internal use.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any

from dharma_swarm.memory_kernel_retrieval.scoring_terms import (
    _env_int,
    _explicit_anchor_terms,
    _identity_text,
    _path_size,
    _scoring_terms,
    _source_identity_terms,
    _sqlite_sequence,
    _title_text,
    _token_overlap_from_terms,
    _token_overlap_score,
)

_BOUNDED_GENERAL_FTS_MAX_DB_BYTES = 512 * 1024 * 1024
_BOUNDED_GENERAL_FTS_MAX_ROWS = 250_000


def _sidecar_normalized_scan(
    conn: sqlite3.Connection,
    query_text: str,
    limit: int,
    *,
    include_below_threshold: bool = False,
    row_terms: tuple[tuple[sqlite3.Row, set[str]], ...] | None = None,
) -> list[tuple[sqlite3.Row, float]]:
    query_terms = _scoring_terms(query_text)
    if not query_terms:
        return []
    rows = row_terms if row_terms is not None else _load_sidecar_scan_rows(conn)
    scored: list[tuple[sqlite3.Row, float]] = []
    below_threshold: list[tuple[sqlite3.Row, float]] = []
    min_score = 0.4 if len(query_terms) >= 5 and not _explicit_anchor_terms(query_text) else 0.3
    for row, candidate_terms in rows:
        score = _token_overlap_from_terms(query_terms, candidate_terms)
        if score >= min_score:
            scored.append((row, score))
        elif include_below_threshold and score > 0.0:
            below_threshold.append((row, score))
    scored.sort(key=lambda item: (item[1], int(item[0]["id"])), reverse=True)
    if scored or not include_below_threshold:
        return scored[: max(0, limit)]
    below_threshold.sort(key=lambda item: (item[1], int(item[0]["id"])), reverse=True)
    return below_threshold[: max(0, limit)]


def _load_sidecar_scan_rows(conn: sqlite3.Connection) -> tuple[tuple[sqlite3.Row, set[str]], ...]:
    try:
        rows = conn.execute(
            """
            SELECT d.vec_doc_id AS id, d.content, d.source, d.layer,
                   d.metadata_json, d.event_time, d.ingestion_time,
                   d.valid_until, d.confidence, d.access_count,
                   d.last_accessed
            FROM memory_retrieval_docs d
            WHERE d.valid_until IS NULL
            """
        ).fetchall()
    except Exception:
        return ()
    return tuple(
        (
            row,
            _scoring_terms(f"{row['source'] or ''} {row['content'] or ''}"),
        )
        for row in rows
    )


def _sidecar_direct_scan_preferred(conn: sqlite3.Connection) -> bool:
    max_rows = _env_int("DHARMA_MEMORY_SIDECAR_DIRECT_SCAN_MAX_ROWS", 5_000)
    if max_rows <= 0:
        return False
    try:
        row = conn.execute("SELECT COUNT(*) FROM memory_retrieval_docs").fetchone()
        return int(row[0] or 0) <= max_rows
    except Exception:
        return False


def _sidecar_scan_score(query_text: str, row: sqlite3.Row) -> float:
    return _token_overlap_score(
        query_text,
        f"{row['source'] or ''} {row['content'] or ''}",
    )


def _identity_match_score(query_terms: set[str], row: dict[str, Any]) -> float:
    if not query_terms:
        return 0.0
    identity_terms = _scoring_terms(_identity_text(row))
    if not identity_terms:
        return 0.0
    overlap = _token_overlap_from_terms(query_terms, identity_terms)
    compactness = min(1.0, math.sqrt(len(query_terms) / max(1, len(identity_terms))))
    return max(0.0, min(1.0, overlap * compactness))


def _title_match_score(query_terms: set[str], row: dict[str, Any]) -> float:
    if not query_terms:
        return 0.0
    title_terms = _scoring_terms(_title_text(row))
    if not title_terms:
        return 0.0
    return max(
        _token_overlap_from_terms(query_terms, title_terms),
        _token_overlap_from_terms(title_terms, query_terms),
    )


def _source_match_score(query_terms: set[str], row: dict[str, Any]) -> float:
    if not query_terms:
        return 0.0
    source_terms = _source_identity_terms(str(row.get("source", "")))
    if not source_terms:
        return 0.0
    return _token_overlap_from_terms(source_terms, query_terms)


def _bounded_general_fts_allowed(conn: sqlite3.Connection, db_path: Path) -> bool:
    max_bytes = _env_int(
        "DHARMA_VECTOR_BOUNDED_GENERAL_FTS_MAX_DB_BYTES",
        _BOUNDED_GENERAL_FTS_MAX_DB_BYTES,
    )
    if max_bytes > 0 and _path_size(db_path) > max_bytes:
        return False

    max_rows = _env_int(
        "DHARMA_VECTOR_BOUNDED_GENERAL_FTS_MAX_ROWS",
        _BOUNDED_GENERAL_FTS_MAX_ROWS,
    )
    if max_rows > 0:
        row_estimate = _sqlite_sequence(conn)
        if row_estimate is not None and row_estimate > max_rows:
            return False
    return True
