"""vector_store.py — Bi-temporal vector store for DHARMA SWARM.

Architecture:
    TFIDFEmbedder (scikit-learn) → sqlite-vec (vec0 virtual table) + FTS5
    Bi-temporal design: event_time (when it happened) + ingestion_time (when we learned it)
    Hybrid retrieval: vector similarity + full-text search fusion
    Confidence decay: age-based decay, soft-delete via valid_until

Design borrowed from:
    - OpenClaw's hybrid memory (vec + FTS5 combination)
    - Zep's bi-temporal model (event_time vs ingestion_time)
    - Mem0's layer design (access tracking, confidence decay)
    - CogniLayer (confidence decay formula)

Protocol: Embedder interface allows drop-in replacement with sentence-transformers.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from dharma_swarm import vector_store_dedupe
from dharma_swarm.embedders import (
    Embedder,
    SentenceTransformerEmbedder as SentenceTransformerEmbedder,
    TFIDFEmbedder,
)
from dharma_swarm.vector_fallback_guard import (
    fallback_vector_scan_allowed,
    fts_search_allowed,
)
from dharma_swarm.vector_store_query_support import (
    candidate_has_query_lexical_signal as _candidate_has_query_lexical_signal,
    candidate_query_signal_count as _candidate_query_signal_count,
    filter_and_rank_vector_results as _filter_and_rank_vector_results,
    fts_match_query as _fts_match_query,
    is_degenerate_query_embedding as _is_degenerate_query_embedding,
    lexical_recovery_search as _lexical_recovery_search,
    memory_retrieval_prefilter_available as _memory_retrieval_prefilter_available,
    query_signal_terms as _query_signal_terms,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """SQLite-vec backed vector store with bi-temporal, hybrid retrieval.

    Storage: SQLite database at state_dir/vectors.db
    Bi-temporal: event_time (when it happened) + ingestion_time (when we stored it)
    Hybrid retrieval: vector similarity (L2) + FTS5 full-text search fusion
    Confidence decay: age-based, capped at min_confidence
    Access tracking: access_count + last_accessed updated on every retrieval
    Edge invalidation: valid_until instead of hard delete

    Thread safety: creates a new connection per call (no shared connection).
    """

    _SCHEMA_VERSION = 1

    def __init__(
        self,
        state_dir: Path,
        embedder: Embedder | None = None,
        dim: int = 128,
    ) -> None:
        self._state_dir = state_dir
        self._db_path = state_dir / "vectors.db"
        self._embedder_path = state_dir / "tfidf_embedder.pkl"
        self._memory_embedder_path = state_dir / "tfidf_embedder_memory_retrieval.pkl"
        self._dim = dim
        self._memory_embedder: TFIDFEmbedder | None = None
        self._memory_embedder_mtime: float | None = None
        self._dedupe_index_ok = False
        self.dedupe_guard_errors = 0

        # Embedder — TFIDFEmbedder by default, swappable
        if embedder is not None:
            self._embedder = embedder
        else:
            self._embedder = TFIDFEmbedder(
                dim=dim,
                state_path=self._embedder_path,
                fit_on_embed=False,
            )

        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            self._init_db()
        except Exception as exc:
            logger.debug("VectorStore init failed (non-fatal): %s", exc)

    def _get_memory_retrieval_embedder(self) -> TFIDFEmbedder:
        try:
            mtime = self._memory_embedder_path.stat().st_mtime
        except OSError:
            mtime = None
        if self._memory_embedder is None or self._memory_embedder_mtime != mtime:
            self._memory_embedder = TFIDFEmbedder(
                dim=self._dim,
                state_path=self._memory_embedder_path,
                fit_on_embed=False,
            )
            self._memory_embedder_mtime = mtime
        return self._memory_embedder

    # ------------------------------------------------------------------
    # DB init
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh SQLite connection with sqlite-vec loaded."""
        try:
            import sqlite_vec
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
            finally:
                conn.enable_load_extension(False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            return conn
        except ImportError:
            # sqlite_vec not installed — fall back to plain sqlite
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except Exception as exc:
            logger.debug("VectorStore _connect error: %s", exc)
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            return conn

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vec_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    layer TEXT DEFAULT 'working',
                    metadata_json TEXT DEFAULT '{}',
                    event_time TEXT,
                    ingestion_time TEXT NOT NULL,
                    valid_until TEXT,
                    confidence REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT
                )
            """)
            # FTS5 table for lexical search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_fts
                USING fts5(
                    content,
                    source,
                    content='vec_documents',
                    content_rowid='id'
                )
            """)
            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS vec_fts_insert
                AFTER INSERT ON vec_documents BEGIN
                    INSERT INTO vec_fts(rowid, content, source)
                    VALUES (new.id, new.content, new.source);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS vec_fts_delete
                AFTER DELETE ON vec_documents BEGIN
                    INSERT INTO vec_fts(vec_fts, rowid, content, source)
                    VALUES ('delete', old.id, old.content, old.source);
                END
            """)
            # Try to create vec0 virtual table (requires sqlite-vec)
            try:
                conn.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings
                    USING vec0(
                        embedding float[{self._dim}]
                    )
                """)
            except Exception as vec_exc:
                logger.debug("vec0 table creation failed (sqlite-vec may not support this syntax): %s", vec_exc)
                # Fallback: store embeddings in a plain table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vec_embeddings_fallback (
                        rowid INTEGER PRIMARY KEY,
                        embedding BLOB
                    )
                """)
            conn.commit()
        except Exception as exc:
            logger.debug("VectorStore _init_db error: %s", exc)
        finally:
            conn.close()

    def _has_vec0(self, conn: sqlite3.Connection) -> bool:
        """Check if vec_embeddings (vec0) virtual table is available."""
        try:
            conn.execute("SELECT * FROM vec_embeddings LIMIT 0")
            return True
        except Exception:
            return False

    def _fallback_vector_scan_allowed(self, conn: sqlite3.Connection) -> bool:
        """Compatibility door used by governed retrieval diagnostics."""
        return fallback_vector_scan_allowed(self._db_path, conn)

    def _fts_search_allowed(self, conn: sqlite3.Connection) -> bool:
        """Compatibility door used by retrieval diagnostics and FTS callers."""
        return fts_search_allowed(self._db_path, conn)

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def upsert(
        self,
        content: str,
        source: str = "",
        layer: str = "working",
        metadata: dict[str, Any] | None = None,
        event_time: datetime | None = None,
        dedupe_digest: str | None = None,
    ) -> int:
        """Insert (or update) a document. Returns the doc_id.

        When ``dedupe_digest`` is provided (sha256 of the source content), the
        insert short-circuits if an active row already carries the same
        source + digest, and prior active rows for the same source with a
        different digest are expired (valid_until) before insert — the
        uid→digest pattern from scripts/vector_store_backfill_memory_sources.
        Default None keeps the historical INSERT-only behavior for all
        existing callers.
        """
        doc_id, _status = self.upsert_with_status(
            content,
            source=source,
            layer=layer,
            metadata=metadata,
            event_time=event_time,
            dedupe_digest=dedupe_digest,
        )
        return doc_id

    def upsert_with_status(
        self,
        content: str,
        source: str = "",
        layer: str = "working",
        metadata: dict[str, Any] | None = None,
        event_time: datetime | None = None,
        dedupe_digest: str | None = None,
    ) -> tuple[int, str]:
        """Like :meth:`upsert`, but also returns what actually happened.

        Status is one of:
          - ``"inserted"``     — a new row was written
          - ``"unchanged"``    — dedupe short-circuit; existing active row id returned
          - ``"guard_error"``  — dedupe guard could not run; insert skipped (fail-closed)
          - ``"rejected"``     — empty content
          - ``"error"``        — insert failed
        """
        if not content or not content.strip():
            return -1, "rejected"
        conn = self._connect()
        try:
            now_iso = _utc_now_iso()
            event_iso = event_time.isoformat() if event_time else now_iso
            if dedupe_digest:
                # Fail-closed: if the guard cannot run (index uncreatable,
                # json1 missing, DB locked) we must NOT fall back to blind
                # INSERT — that silently restores the unbounded-growth
                # behavior this guard exists to stop.
                try:
                    self._ensure_dedupe_index(conn)
                    existing = self._active_row_for_digest(conn, source, dedupe_digest)
                    if existing is not None:
                        return existing, "unchanged"
                    self._expire_active_source_rows(conn, source, dedupe_digest, now_iso)
                except Exception as exc:
                    self.dedupe_guard_errors += 1
                    logger.warning(
                        "VectorStore dedupe guard failed for source=%s "
                        "(guard_errors=%d); skipping insert fail-closed: %s",
                        source, self.dedupe_guard_errors, exc,
                    )
                    return -1, "guard_error"
                metadata = {**(metadata or {}), "source_digest": dedupe_digest}
            meta_json = json.dumps(metadata or {})

            # Fit embedder on new content (incremental vocabulary expansion)
            try:
                self._embedder.fit_add([content])
            except Exception:
                pass

            cursor = conn.execute("""
                INSERT INTO vec_documents
                    (content, source, layer, metadata_json, event_time, ingestion_time, confidence)
                VALUES (?, ?, ?, ?, ?, ?, 1.0)
            """, (content, source, layer, meta_json, event_iso, now_iso))
            doc_id = cursor.lastrowid

            # Store vector embedding
            try:
                vecs = self._embedder.embed([content])
                if vecs and vecs[0]:
                    vec = vecs[0]
                    packed = struct.pack(f"{self._dim}f", *vec)
                    if self._has_vec0(conn):
                        conn.execute("""
                            INSERT INTO vec_embeddings(rowid, embedding) VALUES (?, ?)
                        """, (doc_id, packed))
                    else:
                        conn.execute("""
                            INSERT INTO vec_embeddings_fallback(rowid, embedding) VALUES (?, ?)
                        """, (doc_id, packed))
            except Exception as vec_exc:
                logger.debug("VectorStore: embedding storage failed (non-fatal): %s", vec_exc)

            conn.commit()
            if doc_id:
                return doc_id, "inserted"
            return -1, "error"
        except Exception as exc:
            logger.debug("VectorStore.upsert failed: %s", exc)
            return -1, "error"
        finally:
            conn.close()

    def _ensure_dedupe_index(self, conn: sqlite3.Connection) -> None:
        """Partial index over active rows — required by the dedupe guard.

        See vector_store_dedupe.ensure_dedupe_index. Errors propagate to the
        fail-closed guard handler in upsert_with_status. Event-loop callers
        pre-build via :meth:`ensure_dedupe_index_built` (asyncio.to_thread)
        so the minutes-long one-time build on a large DB never blocks the
        loop inside an upsert.
        """
        if self._dedupe_index_ok:
            return
        vector_store_dedupe.ensure_dedupe_index(conn)
        self._dedupe_index_ok = True

    def _active_row_for_digest(
        self,
        conn: sqlite3.Connection,
        source: str,
        digest: str,
    ) -> int | None:
        return vector_store_dedupe.active_row_for_digest(conn, source, digest)

    def _expire_active_source_rows(
        self,
        conn: sqlite3.Connection,
        source: str,
        replacement_digest: str,
        now_iso: str,
    ) -> int:
        return vector_store_dedupe.expire_active_source_rows(
            conn, source, replacement_digest, now_iso, has_vec0=self._has_vec0(conn)
        )

    def ensure_dedupe_index_built(self) -> bool:
        """Build the dedupe partial index on a dedicated connection.

        The one-time build on a large existing DB takes minutes and holds
        the write lock; event-loop callers run this via asyncio.to_thread
        BEFORE ingestion so the lazy in-upsert path never blocks the loop.
        Returns True when the index is present; on failure the per-upsert
        guard stays fail-closed (guard_error, no blind inserts).
        """
        conn = self._connect()
        try:
            self._ensure_dedupe_index(conn)
            return True
        except Exception as exc:
            logger.warning(
                "VectorStore dedupe index build failed (guard stays fail-closed): %s",
                exc,
            )
            return False
        finally:
            conn.close()

    def db_generation(self) -> int | None:
        """Generation nonce for resume cursors; None when unreadable."""
        conn = self._connect()
        try:
            return vector_store_dedupe.db_generation(conn)
        except Exception as exc:
            logger.debug("VectorStore.db_generation failed: %s", exc)
            return None
        finally:
            conn.close()

    def expire_active_source(self, source: str, reason: str = "key_migrated") -> int:
        """Expire ALL active rows for a source key (one-time key migrations).

        Returns the number of rows expired, or -1 on error.
        """
        conn = self._connect()
        try:
            self._ensure_dedupe_index(conn)
            expired = self._expire_active_source_rows(conn, source, reason, _utc_now_iso())
            conn.commit()
            return expired
        except Exception as exc:
            logger.debug("VectorStore.expire_active_source failed for %s: %s", source, exc)
            return -1
        finally:
            conn.close()

    def invalidate(self, doc_id: int, reason: str = "") -> bool:
        """Soft-delete: set valid_until = now. Does NOT remove the record."""
        conn = self._connect()
        try:
            now_iso = _utc_now_iso()
            meta_note = json.dumps({"invalidated_reason": reason, "invalidated_at": now_iso})
            conn.execute("""
                UPDATE vec_documents
                SET valid_until = ?,
                    metadata_json = json_patch(metadata_json, ?)
                WHERE id = ?
            """, (now_iso, meta_note, doc_id))
            conn.commit()
            return True
        except Exception as exc:
            logger.debug("VectorStore.invalidate failed: %s", exc)
            return False
        finally:
            conn.close()

    def decay_confidence(
        self,
        max_age_days: float = 30.0,
        decay_rate: float = 0.95,
    ) -> int:
        """Apply age-based confidence decay. Returns number of rows updated."""
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT id, confidence, ingestion_time
                FROM vec_documents
                WHERE valid_until IS NULL
            """).fetchall()

            now = _utc_now().timestamp()
            updated = 0
            for row in rows:
                try:
                    ingestion_ts = datetime.fromisoformat(row["ingestion_time"]).timestamp()
                    age_days = (now - ingestion_ts) / 86400.0
                    if age_days > 0:
                        # decay^(age_days): exponential decay
                        decayed = row["confidence"] * (decay_rate ** age_days)
                        decayed = max(0.0, min(1.0, decayed))
                        if abs(decayed - row["confidence"]) > 1e-6:
                            conn.execute(
                                "UPDATE vec_documents SET confidence = ? WHERE id = ?",
                                (decayed, row["id"]),
                            )
                            updated += 1
                except Exception:
                    pass

            conn.commit()
            return updated
        except Exception as exc:
            logger.debug("VectorStore.decay_confidence failed: %s", exc)
            return 0
        finally:
            conn.close()

    def gc(self, min_confidence: float = 0.01) -> int:
        """Remove documents below confidence threshold. Returns removed count."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id FROM vec_documents WHERE confidence < ?",
                (min_confidence,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            if not ids:
                return 0

            placeholders = ",".join("?" * len(ids))

            # Drop the FTS delete trigger temporarily so the trigger doesn't
            # conflict with the FTS sync we do manually below.
            try:
                conn.execute("DROP TRIGGER IF EXISTS vec_fts_delete")
            except Exception:
                pass

            # Remove from FTS manually
            try:
                for doc_id in ids:
                    conn.execute("""
                        INSERT INTO vec_fts(vec_fts, rowid, content, source)
                        SELECT 'delete', id, content, source FROM vec_documents WHERE id = ?
                    """, (doc_id,))
            except Exception:
                pass

            # Remove embeddings
            try:
                if self._has_vec0(conn):
                    conn.execute(
                        f"DELETE FROM vec_embeddings WHERE rowid IN ({placeholders})", ids
                    )
                else:
                    conn.execute(
                        f"DELETE FROM vec_embeddings_fallback WHERE rowid IN ({placeholders})", ids
                    )
            except Exception:
                pass

            conn.execute(
                f"DELETE FROM vec_documents WHERE id IN ({placeholders})", ids
            )

            # Recreate the FTS delete trigger
            try:
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS vec_fts_delete
                    AFTER DELETE ON vec_documents BEGIN
                        INSERT INTO vec_fts(vec_fts, rowid, content, source)
                        VALUES ('delete', old.id, old.content, old.source);
                    END
                """)
            except Exception:
                pass

            conn.commit()
            return len(ids)
        except Exception as exc:
            logger.debug("VectorStore.gc failed: %s", exc)
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def search_vector(
        self,
        query_text: str,
        top_k: int = 10,
        include_invalid: bool = False,
    ) -> list[dict[str, Any]]:
        """Vector similarity search. Returns list of result dicts."""
        if not query_text.strip():
            return []
        conn = self._connect()
        try:
            has_vec0 = self._has_vec0(conn)
            memory_prefilter = has_vec0 and _memory_retrieval_prefilter_available(conn)
            memory_embedder_available = (
                memory_prefilter and self._memory_embedder_path.exists()
            )
            embedder = (
                self._get_memory_retrieval_embedder()
                if memory_embedder_available
                else self._embedder
            )
            # Embed the query
            try:
                vecs = embedder.embed([query_text])
            except Exception:
                vecs = [[0.0] * self._dim]
            if not vecs or not vecs[0]:
                return []
            query_vec = vecs[0]
            packed_query = struct.pack(f"{self._dim}f", *query_vec)
            degenerate_query = _is_degenerate_query_embedding(query_text, query_vec)

            results: list[dict[str, Any]] = []

            if has_vec0:
                try:
                    candidate_k = max(top_k * 20, 100) if memory_prefilter else top_k * 2
                    # vec0 KNN search
                    if memory_prefilter:
                        rows = conn.execute("""
                            SELECT d.id, d.content, d.source, d.layer,
                                   d.metadata_json, d.event_time, d.ingestion_time,
                                   d.valid_until, d.confidence, d.access_count,
                                   d.last_accessed,
                                   e.distance
                            FROM vec_embeddings e
                            JOIN vec_documents d ON d.id = e.rowid
                            WHERE e.embedding MATCH ?
                              AND k = ?
                              AND e.rowid IN (
                                  SELECT vec_doc_id FROM memory_retrieval_docs
                              )
                        """, (packed_query, candidate_k)).fetchall()
                    else:
                        rows = conn.execute("""
                            SELECT d.id, d.content, d.source, d.layer,
                                   d.metadata_json, d.event_time, d.ingestion_time,
                                   d.valid_until, d.confidence, d.access_count,
                                   d.last_accessed,
                                   e.distance
                            FROM vec_embeddings e
                            JOIN vec_documents d ON d.id = e.rowid
                            WHERE e.embedding MATCH ?
                              AND k = ?
                        """, (packed_query, candidate_k)).fetchall()

                    for row in rows:
                        if not include_invalid and row["valid_until"] is not None:
                            continue
                        results.append(self._row_to_dict(row, distance=row["distance"]))
                except Exception as vec_exc:
                    logger.debug("vec0 search failed, falling back: %s", vec_exc)
                    if not fallback_vector_scan_allowed(self._db_path, conn):
                        return []
                    results = self._fallback_vector_search(conn, query_vec, top_k, include_invalid)
            else:
                if not fallback_vector_scan_allowed(self._db_path, conn):
                    return []
                results = self._fallback_vector_search(conn, query_vec, top_k, include_invalid)

            results = _filter_and_rank_vector_results(
                query_text,
                results,
                degenerate_query=degenerate_query,
                memory_prefilter=memory_prefilter,
            )
            if not results:
                results = _lexical_recovery_search(
                    conn,
                    self._db_path,
                    query_text,
                    top_k,
                    include_invalid,
                    memory_prefilter=memory_prefilter,
                )

            # Update access tracking
            for r in results[:top_k]:
                self._touch(conn, r["id"])

            conn.commit()
            return results[:top_k]

        except Exception as exc:
            logger.debug("VectorStore.search_vector failed: %s", exc)
            return []
        finally:
            conn.close()

    def _fallback_vector_search(
        self,
        conn: sqlite3.Connection,
        query_vec: list[float],
        top_k: int,
        include_invalid: bool,
    ) -> list[dict[str, Any]]:
        """Manual cosine similarity when vec0 is unavailable."""
        try:
            # Try the fallback embeddings table first
            try:
                rows = conn.execute("""
                    SELECT d.id, d.content, d.source, d.layer,
                           d.metadata_json, d.event_time, d.ingestion_time,
                           d.valid_until, d.confidence, d.access_count,
                           d.last_accessed,
                           f.embedding
                    FROM vec_embeddings_fallback f
                    JOIN vec_documents d ON d.id = f.rowid
                """).fetchall()
            except Exception:
                # Neither vec table exists — return empty
                return []

            query_arr = np.array(query_vec, dtype=np.float32)
            scored: list[tuple[float, dict[str, Any]]] = []

            for row in rows:
                if not include_invalid and row["valid_until"] is not None:
                    continue
                try:
                    blob = row["embedding"]
                    n = len(blob) // 4
                    vec_vals = list(struct.unpack(f"{n}f", blob))
                    # Pad/trim to query dim
                    if len(vec_vals) < self._dim:
                        vec_vals += [0.0] * (self._dim - len(vec_vals))
                    vec_arr = np.array(vec_vals[:self._dim], dtype=np.float32)
                    # Cosine similarity → distance = 1 - sim
                    dot = float(np.dot(query_arr, vec_arr))
                    norm_q = float(np.linalg.norm(query_arr)) or 1.0
                    norm_v = float(np.linalg.norm(vec_arr)) or 1.0
                    sim = dot / (norm_q * norm_v)
                    distance = 1.0 - sim
                    scored.append((distance, self._row_to_dict(row, distance=distance)))
                except Exception:
                    pass

            scored.sort(key=lambda x: x[0])
            return [r for _, r in scored[:top_k]]
        except Exception as exc:
            logger.debug("_fallback_vector_search failed: %s", exc)
            return []

    def search_fts(
        self,
        query_text: str,
        top_k: int = 10,
        include_invalid: bool = False,
    ) -> list[dict[str, Any]]:
        """Full-text search using FTS5."""
        if not query_text.strip():
            return []
        conn = self._connect()
        try:
            if not self._fts_search_allowed(conn):
                return []

            fts_query = _fts_match_query(query_text)
            if not fts_query:
                return []

            rows = conn.execute("""
                SELECT d.id, d.content, d.source, d.layer,
                       d.metadata_json, d.event_time, d.ingestion_time,
                       d.valid_until, d.confidence, d.access_count,
                       d.last_accessed,
                       bm25(vec_fts) AS bm25_score
                FROM vec_fts
                JOIN vec_documents d ON d.id = vec_fts.rowid
                WHERE vec_fts MATCH ?
                ORDER BY bm25_score
                LIMIT ?
            """, (fts_query, top_k * 2)).fetchall()

            results = []
            for row in rows:
                if not include_invalid and row["valid_until"] is not None:
                    continue
                # bm25() returns negative values (lower = better match)
                bm25 = float(row["bm25_score"] or 0.0)
                # Normalize to [0,1] where 1 = best match
                distance = max(0.0, min(1.0, 1.0 + bm25 / 20.0))
                results.append(self._row_to_dict(row, distance=distance))

            # Update access tracking
            for r in results[:top_k]:
                self._touch(conn, r["id"])

            conn.commit()
            return results[:top_k]

        except Exception as exc:
            logger.debug("VectorStore.search_fts failed: %s", exc)
            return []
        finally:
            conn.close()

    def search_hybrid(
        self,
        query_text: str,
        top_k: int = 10,
        vector_weight: float = 0.6,
        fts_weight: float = 0.4,
    ) -> list[dict[str, Any]]:
        """Hybrid retrieval: combine vector + FTS5 results using RRF-style fusion.

        Returns ranked list of result dicts with fused 'score' field.
        score is similarity (higher = more relevant), not distance.
        """
        if not query_text.strip():
            return []

        try:
            vec_results = self.search_vector(query_text, top_k=top_k * 2)
            fts_results = self.search_fts(query_text, top_k=top_k * 2)

            # Build score map: doc_id → (vec_score, fts_score)
            scores: dict[int, dict[str, Any]] = {}

            # Vector results: distance [0, ∞) → similarity score [0, 1]
            for rank, r in enumerate(vec_results):
                doc_id = r["id"]
                # Convert distance to similarity (closer = higher score)
                dist = r.get("distance", 1.0)
                vec_sim = max(0.0, 1.0 - dist)
                if doc_id not in scores:
                    scores[doc_id] = {**r, "vec_score": 0.0, "fts_score": 0.0}
                scores[doc_id]["vec_score"] = vec_sim

            # FTS results: distance already normalized [0, 1]
            for rank, r in enumerate(fts_results):
                doc_id = r["id"]
                fts_sim = max(0.0, 1.0 - r.get("distance", 1.0))
                if doc_id not in scores:
                    scores[doc_id] = {**r, "vec_score": 0.0, "fts_score": 0.0}
                scores[doc_id]["fts_score"] = fts_sim

            # Fuse
            fused: list[tuple[float, dict[str, Any]]] = []
            for doc_id, r in scores.items():
                fused_score = (
                    vector_weight * r.get("vec_score", 0.0) +
                    fts_weight * r.get("fts_score", 0.0)
                )
                result = dict(r)
                result["score"] = round(fused_score, 4)
                fused.append((fused_score, result))

            fused.sort(key=lambda x: x[0], reverse=True)
            return [r for _, r in fused[:top_k]]

        except Exception as exc:
            logger.debug("VectorStore.search_hybrid failed: %s", exc)
            return []

    def get_document(self, doc_id: int) -> dict[str, Any] | None:
        """Fetch a single document by ID."""
        conn = self._connect()
        try:
            row = conn.execute("""
                SELECT id, content, source, layer, metadata_json,
                       event_time, ingestion_time, valid_until,
                       confidence, access_count, last_accessed
                FROM vec_documents WHERE id = ?
            """, (doc_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)
        except Exception as exc:
            logger.debug("VectorStore.get_document failed: %s", exc)
            return None
        finally:
            conn.close()

    def stats(self) -> dict[str, Any]:
        """Return store statistics."""
        conn = self._connect()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM vec_documents"
            ).fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM vec_documents WHERE valid_until IS NULL"
            ).fetchone()[0]
            avg_conf_row = conn.execute(
                "SELECT AVG(confidence) FROM vec_documents WHERE valid_until IS NULL"
            ).fetchone()
            avg_conf = float(avg_conf_row[0] or 0.0)
            by_layer = {}
            for row in conn.execute(
                "SELECT layer, COUNT(*) as cnt FROM vec_documents GROUP BY layer"
            ).fetchall():
                by_layer[row[0]] = row[1]
            return {
                "total_documents": total,
                "valid_documents": valid,
                "invalidated_documents": total - valid,
                "avg_confidence": round(avg_conf, 3),
                "by_layer": by_layer,
                "db_path": str(self._db_path),
                "embedder_dim": self._embedder.dim,
                "embedder_fitted": getattr(self._embedder, "_fitted", False),
            }
        except Exception as exc:
            logger.debug("VectorStore.stats failed: %s", exc)
            return {"total_documents": 0, "error": str(exc)}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_dict(
        self,
        row: sqlite3.Row,
        distance: float | None = None,
    ) -> dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict."""
        return self._row_to_dict_static(row, distance=distance)

    @staticmethod
    def _row_to_dict_static(
        row: sqlite3.Row,
        distance: float | None = None,
    ) -> dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict."""
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except Exception:
            meta = {}
        result: dict[str, Any] = {
            "id": row["id"],
            "content": row["content"],
            "source": row["source"] or "",
            "layer": row["layer"] or "working",
            "metadata": meta,
            "event_time": row["event_time"],
            "ingestion_time": row["ingestion_time"],
            "valid_until": row["valid_until"],
            "confidence": float(row["confidence"] or 1.0),
            "access_count": int(row["access_count"] or 0),
            "last_accessed": row["last_accessed"],
        }
        if distance is not None:
            result["distance"] = distance
            # Derived similarity score
            result["score"] = max(0.0, round(1.0 - distance, 4))
        return result

    def _touch(self, conn: sqlite3.Connection, doc_id: int) -> None:
        """Update access tracking for a retrieved document."""
        try:
            now_iso = _utc_now_iso()
            conn.execute("""
                UPDATE vec_documents
                SET access_count = access_count + 1,
                    last_accessed = ?
                WHERE id = ?
            """, (now_iso, doc_id))
        except Exception:
            pass


__all__ = [
    "Embedder",
    "TFIDFEmbedder",
    "VectorStore",
]
