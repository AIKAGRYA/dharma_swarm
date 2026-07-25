"""Search/fetch mixin for the governed retrieval engine.

Split out of ``memory_retrieval.py`` (Rule 10 module-line-budget
decomposition) along the search/fetch seam: these methods only touch
``self.vector_store`` and ``self._sidecar_scan_cache`` (both set by
``GovernedRetrievalEngine.__init__``), so they compose cleanly as a mixin.
``GovernedRetrievalEngine`` in ``memory_retrieval.py`` inherits from
``_SearchMixin``; nothing outside that class should use this mixin directly.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from dharma_swarm.memory_kernel_retrieval.scoring_terms import (
    _bounded_fts_match_queries,
    _sidecar_fts_match_queries,
    _sidecar_rows_to_results,
)
from dharma_swarm.memory_kernel_retrieval.sidecar_matching import (
    _bounded_general_fts_allowed,
    _load_sidecar_scan_rows,
    _sidecar_direct_scan_preferred,
    _sidecar_normalized_scan,
    _sidecar_scan_score,
)
from dharma_swarm.vector_store import _fts_match_query


class _SearchMixin:
    """Vector/FTS/sidecar search methods for ``GovernedRetrievalEngine``.

    Relies on ``self.vector_store`` and ``self._sidecar_scan_cache`` being
    set by the composing class's ``__init__``.
    """

    def _safe_search_vector(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        try:
            return self.vector_store.search_vector(query_text, top_k=top_k)
        except Exception:
            return []

    def _safe_search_fts(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        try:
            results = self.vector_store.search_fts(query_text, top_k=top_k)
            if results:
                return results
            return self._safe_search_fts_bounded(query_text, top_k)
        except Exception:
            return []

    def _safe_search_fts_bounded(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        """Bounded lexical fallback for large FTS stores.

        VectorStore.search_fts intentionally refuses very large projections
        because BM25 ordering can block.  This fallback does not compute BM25 or
        scan the whole projection; it uses FTS only as a limited candidate
        generator, then the governed engine's token-overlap fusion ranks the
        returned rows.  Source-of-truth memory layers are searched first because
        the live projection is dominated by repeated evolution-archive rows.
        """

        fts_queries = _bounded_fts_match_queries(query_text)
        if not fts_queries:
            return []
        conn = self.vector_store._connect()
        try:
            sidecar_results = self._safe_search_memory_sidecar_fts(conn, query_text, top_k)
            if sidecar_results:
                return sidecar_results

            rows_by_id: dict[int, sqlite3.Row] = {}
            memory_limit = max(20, min(200, top_k * 12))
            general_limit = max(1, min(50, top_k * 2))
            for fts_query in fts_queries:
                rows = conn.execute(
                    """
                    SELECT d.id, d.content, d.source, d.layer,
                           d.metadata_json, d.event_time, d.ingestion_time,
                           d.valid_until, d.confidence, d.access_count,
                           d.last_accessed
                    FROM vec_fts
                    JOIN vec_documents d ON d.id = vec_fts.rowid
                    WHERE vec_fts MATCH ?
                      AND d.valid_until IS NULL
                      AND d.layer IN ('memory_context', 'memory_graph', 'source_file')
                    ORDER BY vec_fts.rowid DESC
                    LIMIT ?
                    """,
                    (fts_query, memory_limit),
                ).fetchall()
                for row in rows:
                    rows_by_id.setdefault(int(row["id"]), row)
                if rows_by_id:
                    break
            if rows_by_id:
                return [self.vector_store._row_to_dict(row, distance=0.5) for row in rows_by_id.values()]

            general_query = _fts_match_query(query_text)
            if general_query and _bounded_general_fts_allowed(conn, self.vector_store._db_path):
                rows = conn.execute(
                    """
                    SELECT d.id, d.content, d.source, d.layer,
                           d.metadata_json, d.event_time, d.ingestion_time,
                           d.valid_until, d.confidence, d.access_count,
                           d.last_accessed
                    FROM vec_fts
                    JOIN vec_documents d ON d.id = vec_fts.rowid
                    WHERE vec_fts MATCH ?
                      AND d.valid_until IS NULL
                    LIMIT ?
                    """,
                    (general_query, general_limit),
                ).fetchall()
                for row in rows:
                    rows_by_id.setdefault(int(row["id"]), row)
            return [self.vector_store._row_to_dict(row, distance=0.5) for row in rows_by_id.values()]
        except Exception:
            return []
        finally:
            conn.close()

    def _safe_search_memory_sidecar_fts(
        self,
        conn: sqlite3.Connection,
        query_text: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search the compact curated-memory FTS projection when available."""

        try:
            conn.execute("SELECT rowid FROM memory_retrieval_fts LIMIT 0")
        except Exception:
            return []

        rows_by_id: dict[int, sqlite3.Row] = {}
        scores_by_id: dict[int, float] = {}
        limit = max(20, min(200, top_k * 12))

        if _sidecar_direct_scan_preferred(conn):
            scanned = _sidecar_normalized_scan(
                conn,
                query_text,
                limit,
                include_below_threshold=True,
                row_terms=self._cached_sidecar_scan_rows(conn),
            )
            if scanned:
                return _sidecar_rows_to_results(self.vector_store, scanned)

        for fts_query in _sidecar_fts_match_queries(query_text):
            try:
                rows = conn.execute(
                    """
                    SELECT d.vec_doc_id AS id, d.content, d.source, d.layer,
                           d.metadata_json, d.event_time, d.ingestion_time,
                           d.valid_until, d.confidence, d.access_count,
                           d.last_accessed
                    FROM memory_retrieval_fts
                    JOIN memory_retrieval_docs d
                      ON d.vec_doc_id = memory_retrieval_fts.rowid
                    WHERE memory_retrieval_fts MATCH ?
                      AND d.valid_until IS NULL
                    ORDER BY bm25(memory_retrieval_fts)
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
            except Exception:
                continue
            for row in rows:
                row_id = int(row["id"])
                score = max(0.5, _sidecar_scan_score(query_text, row))
                rows_by_id.setdefault(row_id, row)
                scores_by_id[row_id] = max(float(scores_by_id.get(row_id, 0.0)), score)
            if len(rows_by_id) >= limit:
                break

        for row, score in _sidecar_normalized_scan(
            conn,
            query_text,
            limit,
            row_terms=self._cached_sidecar_scan_rows(conn),
        ):
            row_id = int(row["id"])
            if row_id not in rows_by_id:
                rows_by_id[row_id] = row
            scores_by_id[row_id] = max(float(scores_by_id.get(row_id, 0.0)), score)

        ranked_rows = sorted(
            rows_by_id.values(),
            key=lambda row: (float(scores_by_id.get(int(row["id"]), 0.0)), int(row["id"])),
            reverse=True,
        )
        return [
            self.vector_store._row_to_dict(
                row,
                distance=max(0.0, min(1.0, 1.0 - float(scores_by_id.get(int(row["id"]), 0.5)))),
            )
            for row in ranked_rows[:limit]
        ]

    def _cached_sidecar_scan_rows(
        self,
        conn: sqlite3.Connection,
    ) -> tuple[tuple[sqlite3.Row, set[str]], ...]:
        if self._sidecar_scan_cache is None:
            self._sidecar_scan_cache = _load_sidecar_scan_rows(conn)
        return self._sidecar_scan_cache
