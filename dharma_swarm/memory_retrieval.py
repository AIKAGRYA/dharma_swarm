"""Governed retrieval engine over vector projections and MemoryKernel policy.

This module is intentionally small: it does not create a new source of truth.
It ranks candidates from the retrieval projection, records degradation signals,
and optionally attaches a read-only MemoryKernel admission preview.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.vector_store import VectorStore, _fts_match_query


_SECRETISH_RE = re.compile(
    r"(?is)(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{8,}|\bBearer\s+[A-Za-z0-9._~+/=-]{16,})"
)
_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9]+", re.UNICODE)
_FTS_STOPWORDS = {
    "and",
    "are",
    "did",
    "does",
    "entity",
    "file",
    "for",
    "from",
    "graph",
    "has",
    "into",
    "in",
    "memory",
    "not",
    "relation",
    "source",
    "stop",
    "what",
    "which",
    "why",
    "was",
    "were",
    "the",
    "this",
    "that",
    "with",
}
_BOUNDED_GENERAL_FTS_MAX_DB_BYTES = 512 * 1024 * 1024
_BOUNDED_GENERAL_FTS_MAX_ROWS = 250_000
_CURATED_MEMORY_LAYERS = ("memory_context", "memory_graph", "source_file")
_SOURCE_IDENTITY_STOPWORDS = _FTS_STOPWORDS | {
    "concept",
    "concepts",
    "dharma",
    "dhyana",
    "docs",
    "file",
    "knowledge",
    "md",
    "reports",
    "script",
    "scripts",
    "source",
    "swarm",
    "text",
    "users",
    "wiki",
}


@dataclass(frozen=True)
class RetrievalQuery:
    """One bounded retrieval request."""

    text: str
    top_k: int = 10
    candidate_multiplier: int = 3
    include_content: bool = True
    min_score: float = 0.01
    enable_memory_kernel: bool = True
    kernel_candidate_limit: int = 24
    kernel_admitted_limit: int = 8
    record_telemetry: bool = True


@dataclass(frozen=True)
class RetrievalCandidate:
    """A ranked retrieval projection candidate."""

    doc_id: str
    rank: int
    score: float
    source: str
    layer: str
    channels: tuple[str, ...]
    content: str
    event_time: str | None = None
    ingestion_time: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Health and degradation signals for one retrieval run."""

    vector_db_path: str
    vector_db_bytes: int
    row_estimate: int | None
    fts_allowed: bool
    vector_scan_allowed: bool
    sqlite_vec_table_available: bool
    sqlite_vec_has_rows: bool | None
    fallback_embedding_has_rows: bool | None
    optional_dependencies: dict[str, bool]
    degraded_reasons: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKernelAdmissionSummary:
    """Honest summary of the MemoryKernel context gate for this run."""

    available: bool
    text_query_supported: bool
    candidate_count: int = 0
    admitted_count: int = 0
    omitted_count: int = 0
    pack_id: str = ""
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    """Full governed retrieval response."""

    query: str
    candidates: tuple[RetrievalCandidate, ...]
    timings_ms: dict[str, float]
    diagnostics: RetrievalDiagnostics
    memory_kernel: MemoryKernelAdmissionSummary

    def to_json(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidates": tuple(candidate.to_json() for candidate in self.candidates),
            "timings_ms": self.timings_ms,
            "diagnostics": self.diagnostics.to_json(),
            "memory_kernel": self.memory_kernel.to_json(),
        }


class GovernedRetrievalEngine:
    """Rank retrieval projection candidates with explicit guardrail signals."""

    def __init__(
        self,
        *,
        state_dir: Path,
        vector_store: VectorStore | None = None,
        memory_kernel: Any | None = None,
        dim: int = 128,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.vector_store = vector_store or VectorStore(state_dir=self.state_dir, dim=dim)
        self.memory_kernel = memory_kernel
        self._retrieve_diagnostics_cache: RetrievalDiagnostics | None = None
        self._sidecar_scan_cache: tuple[tuple[sqlite3.Row, set[str]], ...] | None = None

    def retrieve(self, request: str | RetrievalQuery) -> RetrievalResult:
        query = request if isinstance(request, RetrievalQuery) else RetrievalQuery(text=request)
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        diagnostics = self._diagnostics_for_retrieve()
        timings["diagnostics"] = _elapsed_ms(t0)

        if not query.text.strip():
            result = RetrievalResult(
                query=query.text,
                candidates=(),
                timings_ms=timings,
                diagnostics=diagnostics,
                memory_kernel=self._memory_kernel_admission(query),
            )
            if query.record_telemetry:
                self._record_retrieval_telemetry(result)
            return result

        fetch_k = max(query.top_k, query.top_k * max(1, query.candidate_multiplier))
        fts_t0 = time.perf_counter()
        fts_results = self._safe_search_fts(query.text, fetch_k)
        timings["fts_search"] = _elapsed_ms(fts_t0)

        vector_results: list[dict[str, Any]] = []
        if fts_results:
            timings["vector_search"] = 0.0
        else:
            vec_t0 = time.perf_counter()
            vector_results = self._safe_search_vector(query.text, fetch_k)
            timings["vector_search"] = _elapsed_ms(vec_t0)

        fuse_t0 = time.perf_counter()
        candidates = self._fuse_candidates(
            query_text=query.text,
            vector_results=vector_results,
            fts_results=fts_results,
            top_k=query.top_k,
            min_score=query.min_score,
            include_content=query.include_content,
        )
        timings["fusion"] = _elapsed_ms(fuse_t0)

        kernel_t0 = time.perf_counter()
        memory_kernel = self._memory_kernel_admission(query)
        timings["memory_kernel_admission"] = _elapsed_ms(kernel_t0)
        timings["total"] = _elapsed_ms(t0)
        result = RetrievalResult(
            query=query.text,
            candidates=tuple(candidates),
            timings_ms=timings,
            diagnostics=diagnostics,
            memory_kernel=memory_kernel,
        )
        if query.record_telemetry:
            self._record_retrieval_telemetry(result)
        return result

    def _record_retrieval_telemetry(self, result: RetrievalResult) -> None:
        """Best-effort runtime telemetry for retrieval quality and drift audits."""

        try:
            top = result.candidates[0] if result.candidates else None
            conn = self.vector_store._connect()
            try:
                _ensure_retrieval_telemetry_table(conn)
                conn.execute(
                    """
                    INSERT INTO memory_retrieval_query_log (
                        query_time, query_hash, query_preview,
                        top_doc_id, top_source, top_layer, top_score,
                        result_count, total_ms, vector_search_ms, fts_search_ms,
                        fusion_ms, memory_kernel_available,
                        memory_kernel_text_query_supported,
                        memory_kernel_admitted_count, degraded_reasons_json,
                        top_channels_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _utc_now_iso(),
                        _sha256(result.query),
                        _query_preview(result.query),
                        top.doc_id if top else "",
                        top.source if top else "",
                        top.layer if top else "",
                        top.score if top else None,
                        len(result.candidates),
                        result.timings_ms.get("total"),
                        result.timings_ms.get("vector_search"),
                        result.timings_ms.get("fts_search"),
                        result.timings_ms.get("fusion"),
                        int(result.memory_kernel.available),
                        int(result.memory_kernel.text_query_supported),
                        int(result.memory_kernel.admitted_count),
                        json.dumps(tuple(result.diagnostics.degraded_reasons), sort_keys=True),
                        json.dumps(top.channels if top else (), sort_keys=True),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            return

    def diagnostics(self) -> RetrievalDiagnostics:
        db_path = self.state_dir / "vectors.db"
        db_bytes = _path_size(db_path)
        deps = {
            "numpy": _module_available("numpy"),
            "sklearn": _module_available("sklearn"),
            "sqlite_vec": _module_available("sqlite_vec"),
            "lancedb": _module_available("lancedb"),
            "qdrant_client": _module_available("qdrant_client"),
            "sentence_transformers": _module_available("sentence_transformers"),
        }
        row_estimate: int | None = None
        fts_allowed = False
        vector_scan_allowed = False
        sqlite_vec_table_available = False
        sqlite_vec_has_rows: bool | None = None
        fallback_embedding_has_rows: bool | None = None
        degraded: list[str] = []
        conn: sqlite3.Connection | None = None
        try:
            conn = self.vector_store._connect()
            row_estimate = _sqlite_sequence(conn)
            fts_allowed = self.vector_store._fts_search_allowed(conn)
            vector_scan_allowed = self.vector_store._fallback_vector_scan_allowed(conn)
            sqlite_vec_table_available = self.vector_store._has_vec0(conn)
            sqlite_vec_has_rows = _table_has_sample(conn, "vec_embeddings")
            fallback_embedding_has_rows = _table_has_sample(conn, "vec_embeddings_fallback")
        except Exception as exc:
            degraded.append(f"diagnostics_failed:{type(exc).__name__}")
        finally:
            if conn is not None:
                conn.close()

        if db_bytes == 0:
            degraded.append("vector_db_missing")
        if not fts_allowed:
            degraded.append("fts_guard_blocked")
        if not sqlite_vec_table_available and not vector_scan_allowed:
            degraded.append("vector_guard_blocked_without_sqlite_vec")
        if (
            sqlite_vec_table_available
            and sqlite_vec_has_rows is False
            and fallback_embedding_has_rows is True
        ):
            degraded.append("vec0_empty_fallback_embeddings_present")
        if not deps["sklearn"]:
            degraded.append("tfidf_embedder_dependency_missing")
        if not deps["sqlite_vec"]:
            degraded.append("ann_sqlite_vec_dependency_missing")

        return RetrievalDiagnostics(
            vector_db_path=str(db_path),
            vector_db_bytes=db_bytes,
            row_estimate=row_estimate,
            fts_allowed=fts_allowed,
            vector_scan_allowed=vector_scan_allowed,
            sqlite_vec_table_available=sqlite_vec_table_available,
            sqlite_vec_has_rows=sqlite_vec_has_rows,
            fallback_embedding_has_rows=fallback_embedding_has_rows,
            optional_dependencies=deps,
            degraded_reasons=tuple(dict.fromkeys(degraded)),
        )

    def _diagnostics_for_retrieve(self) -> RetrievalDiagnostics:
        if self._retrieve_diagnostics_cache is None:
            self._retrieve_diagnostics_cache = self.diagnostics()
        return self._retrieve_diagnostics_cache

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

    def _memory_kernel_admission(self, query: RetrievalQuery) -> MemoryKernelAdmissionSummary:
        if not query.enable_memory_kernel:
            return MemoryKernelAdmissionSummary(
                available=False,
                text_query_supported=False,
                warnings=("memory_kernel_disabled_for_query",),
            )
        if self.memory_kernel is None:
            return MemoryKernelAdmissionSummary(
                available=False,
                text_query_supported=False,
                warnings=("memory_kernel_not_attached",),
            )
        try:
            from dharma_swarm.memory_kernel import MemoryContextBudget, MemoryQuery, TruthState

            pack = self.memory_kernel.preview_memory_pack(
                query=MemoryQuery(
                    limit_total=max(1, query.kernel_candidate_limit),
                    limit_per_surface=max(1, query.kernel_candidate_limit),
                    include_content=query.include_content,
                    include_high_risk=False,
                    include_projections=False,
                    include_unsafe=False,
                    require_source_digest=True,
                    require_source_row_key=True,
                ),
                budget=MemoryContextBudget(
                    max_candidate_atoms=max(1, query.kernel_candidate_limit),
                    max_admitted_atoms=max(1, query.kernel_admitted_limit),
                    max_total_chars=4000,
                    max_atom_chars=600,
                    include_content=query.include_content,
                    require_context_admissible=False,
                    allow_projections=False,
                    allow_high_risk=False,
                    allowed_truth_states=(
                        TruthState.OBSERVED,
                        TruthState.CLAIMED,
                        TruthState.CURATED,
                        TruthState.CANONICAL,
                    ),
                ),
            )
            text_query_supported = callable(
                getattr(self.memory_kernel, "query", None)
            ) or callable(getattr(self.memory_kernel, "search", None))
            warnings = tuple(pack.warnings)
            if not text_query_supported:
                warnings = (*warnings, "memory_kernel_text_query_not_yet_supported")
            return MemoryKernelAdmissionSummary(
                available=True,
                text_query_supported=text_query_supported,
                candidate_count=pack.candidate_count,
                admitted_count=pack.admitted_count,
                omitted_count=pack.omitted_count,
                pack_id=pack.pack_id,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        except Exception as exc:
            return MemoryKernelAdmissionSummary(
                available=True,
                text_query_supported=False,
                warnings=(f"memory_kernel_admission_failed:{type(exc).__name__}",),
            )

    def _fuse_candidates(
        self,
        *,
        query_text: str,
        vector_results: list[dict[str, Any]],
        fts_results: list[dict[str, Any]],
        top_k: int,
        min_score: float,
        include_content: bool,
    ) -> list[RetrievalCandidate]:
        slots: dict[str, dict[str, Any]] = {}
        rrf_k = 60.0
        channel_weights = {"vector": 0.45, "fts": 0.55}
        ideal_score = sum(weight / (rrf_k + 1.0) for weight in channel_weights.values())
        exact_needle = query_text.strip().lower()
        query_terms = _scoring_terms(query_text)
        anchor_terms = _explicit_anchor_terms(query_text)
        tail_terms = _tail_intent_terms(query_text)

        for channel, rows in (("vector", vector_results), ("fts", fts_results)):
            for rank, row in enumerate(rows, start=1):
                doc_id = str(row.get("id", ""))
                if not doc_id:
                    continue
                channel_similarity = _row_similarity(row)
                if channel == "vector" and channel_similarity <= 0.0:
                    continue
                slot = slots.setdefault(
                    doc_id,
                    {
                        "row": row,
                        "rrf": 0.0,
                        "channels": [],
                        "channel_scores": {},
                        "exact_match": False,
                        "token_overlap": 0.0,
                        "weighted_token_overlap": 0.0,
                        "rare_query_term_coverage": 0.0,
                        "discriminator_coverage": 0.0,
                        "identity_match": 0.0,
                        "source_match": 0.0,
                        "title_match": 0.0,
                        "candidate_terms": set(),
                    },
                )
                slot["rrf"] += channel_weights[channel] / (rrf_k + float(rank))
                slot["channels"].append(channel)
                slot["channel_scores"][channel] = round(channel_similarity, 4)
                candidate_terms = _scoring_terms(f"{row.get('content', '')} {row.get('source', '')}")
                slot["candidate_terms"].update(candidate_terms)
                overlap = _token_overlap_from_terms(query_terms, candidate_terms)
                slot["token_overlap"] = max(float(slot["token_overlap"]), overlap)
                identity_match = _identity_match_score(query_terms, row)
                slot["identity_match"] = max(float(slot["identity_match"]), identity_match)
                source_match = _source_match_score(query_terms, row)
                slot["source_match"] = max(float(slot["source_match"]), source_match)
                title_match = _title_match_score(query_terms, row)
                slot["title_match"] = max(float(slot["title_match"]), title_match)
                if exact_needle and (
                    exact_needle in str(row.get("content", "")).lower()
                    or exact_needle in str(row.get("source", "")).lower()
                ):
                    slot["exact_match"] = True
                if channel == "fts":
                    slot["row"] = row

        term_stat_slots = _term_stat_slots(slots.values())
        term_doc_freq = _query_term_doc_freq(query_terms, term_stat_slots)
        rare_query_terms = _rare_query_terms(term_doc_freq)
        candidate_count = len(term_stat_slots)

        ranked: list[tuple[float, str, dict[str, Any]]] = []
        for doc_id, slot in slots.items():
            channels = tuple(dict.fromkeys(slot.get("channels", [])))
            overlap_score = float(slot.get("token_overlap", 0.0))
            weighted_overlap = _weighted_token_overlap_from_terms(
                query_terms,
                slot.get("candidate_terms", set()),
                term_doc_freq,
                candidate_count,
            )
            slot["weighted_token_overlap"] = weighted_overlap
            rare_coverage = _token_overlap_from_terms(
                rare_query_terms,
                slot.get("candidate_terms", set()),
            )
            slot["rare_query_term_coverage"] = rare_coverage
            discriminator_terms = anchor_terms or tail_terms
            discriminator_coverage = max(
                rare_coverage,
                _token_overlap_from_terms(
                    discriminator_terms,
                    slot.get("candidate_terms", set()),
                ),
            )
            slot["discriminator_coverage"] = discriminator_coverage
            identity_match = float(slot.get("identity_match", 0.0))
            source_match = float(slot.get("source_match", 0.0))
            title_match = float(slot.get("title_match", 0.0))
            if channels == ("vector",) and overlap_score <= 0.0:
                continue
            if channels == ("fts",) and _identifier_like_query(query_text) and not slot.get("exact_match"):
                identifier_support = max(identity_match, source_match, title_match)
                if identifier_support < 0.5:
                    continue
            required_fts_overlap = 0.5 if len(query_terms) >= 5 and not anchor_terms else 0.3
            if channels == ("fts",) and not slot.get("exact_match") and overlap_score < required_fts_overlap:
                continue
            if channels == ("vector",) and _is_noisy_vector_only_candidate(
                slot["row"],
                query_text=query_text,
                token_overlap=overlap_score,
                exact_match=bool(slot.get("exact_match")),
            ):
                continue
            rrf_score = min(1.0, float(slot["rrf"]) / ideal_score) if ideal_score else 0.0
            score = (
                (rrf_score * 0.38)
                + (weighted_overlap * 0.30)
                + (discriminator_coverage * 0.17)
                + (identity_match * 0.18)
                + (source_match * 0.12)
                + (title_match * 0.12)
            )
            if slot.get("exact_match"):
                score = min(1.0, score + 0.5)
            if score >= min_score:
                ranked.append((score, doc_id, slot))
        ranked.sort(key=lambda item: item[0], reverse=True)

        out: list[RetrievalCandidate] = []
        for rank, (score, doc_id, slot) in enumerate(ranked[: max(0, top_k)], start=1):
            row = slot["row"]
            content, warnings = _content_for_candidate(str(row.get("content", "")), include_content)
            metadata = dict(row.get("metadata") or {})
            metadata["retrieval_channel_scores"] = dict(slot["channel_scores"])
            metadata["retrieval_token_overlap"] = round(float(slot.get("token_overlap", 0.0)), 4)
            metadata["retrieval_weighted_token_overlap"] = round(
                float(slot.get("weighted_token_overlap", 0.0)),
                4,
            )
            metadata["retrieval_rare_query_term_coverage"] = round(
                float(slot.get("rare_query_term_coverage", 0.0)),
                4,
            )
            metadata["retrieval_discriminator_coverage"] = round(
                float(slot.get("discriminator_coverage", 0.0)),
                4,
            )
            metadata["retrieval_identity_match"] = round(
                float(slot.get("identity_match", 0.0)),
                4,
            )
            metadata["retrieval_source_match"] = round(
                float(slot.get("source_match", 0.0)),
                4,
            )
            metadata["retrieval_title_match"] = round(
                float(slot.get("title_match", 0.0)),
                4,
            )
            out.append(
                RetrievalCandidate(
                    doc_id=doc_id,
                    rank=rank,
                    score=round(score, 4),
                    source=str(row.get("source", "")),
                    layer=str(row.get("layer", "")),
                    channels=tuple(dict.fromkeys(slot["channels"])),
                    content=content,
                    event_time=row.get("event_time"),
                    ingestion_time=row.get("ingestion_time"),
                    metadata=metadata,
                    warnings=warnings,
                )
            )
        return out


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _sqlite_sequence(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'vec_documents'"
        ).fetchone()
        if row is not None:
            return int(row[0] or 0)
    except Exception:
        return None
    return None


def _table_has_sample(conn: sqlite3.Connection, table: str) -> bool | None:
    try:
        return conn.execute(f"SELECT rowid FROM {table} LIMIT 1").fetchone() is not None
    except Exception:
        return None


def _row_similarity(row: dict[str, Any]) -> float:
    try:
        if "distance" in row:
            return max(0.0, min(1.0, 1.0 - float(row.get("distance", 1.0))))
        return max(0.0, min(1.0, float(row.get("score", 0.0))))
    except (TypeError, ValueError):
        return 0.0


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


def _sidecar_rows_to_results(
    vector_store: VectorStore,
    rows: list[tuple[sqlite3.Row, float]],
) -> list[dict[str, Any]]:
    return [
        vector_store._row_to_dict(
            row,
            distance=max(0.0, min(1.0, 1.0 - float(score))),
        )
        for row, score in rows
    ]


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


def _source_identity_terms(source: str) -> set[str]:
    terms: set[str] = set()
    for term in re.findall(r"[A-Za-z0-9]+", source.lower(), flags=re.UNICODE):
        if len(term) <= 1:
            continue
        normalized = _normalized_scoring_term(term)
        if normalized in _SOURCE_IDENTITY_STOPWORDS:
            continue
        terms.add(normalized)
    return terms


def _identity_text(row: dict[str, Any]) -> str:
    source = str(row.get("source", ""))
    titles = _title_text(row)
    return f"{source} {titles}"


def _title_text(row: dict[str, Any]) -> str:
    content = str(row.get("content", ""))
    markdown_title = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    if markdown_title:
        return markdown_title.group(1)
    frontmatter_title = re.search(r'^title:\s*"?([^"\n]+)"?', content, flags=re.MULTILINE)
    if frontmatter_title:
        return frontmatter_title.group(1)
    title_patterns = (
        r"Observation:\s*(.+?)(?:\nSource file:|\n|$)",
        r"Memory graph entity:\s*(.+?)(?:\n|$)",
        r"Memory graph relation:\s*(.+?)(?:\n|$)",
        r'"goal"\s*:\s*"([^"]+)"',
    )
    titles: list[str] = []
    for pattern in title_patterns:
        match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL)
        if match:
            titles.append(match.group(1))
    return " ".join(titles)


def _token_overlap_score(query_text: str, candidate_text: str) -> float:
    query_terms = _scoring_terms(query_text)
    candidate_terms = _scoring_terms(candidate_text)
    return _token_overlap_from_terms(query_terms, candidate_terms)


def _token_overlap_from_terms(query_terms: set[str], candidate_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    if not candidate_terms:
        return 0.0
    return len(query_terms & candidate_terms) / len(query_terms)


def _query_term_doc_freq(
    query_terms: set[str],
    slots: Any,
) -> dict[str, int]:
    counts = {term: 0 for term in query_terms}
    for slot in slots:
        candidate_terms = slot.get("candidate_terms", set())
        for term in query_terms & candidate_terms:
            counts[term] += 1
    return counts


def _term_stat_slots(slots: Any) -> list[dict[str, Any]]:
    all_slots = list(slots)
    fts_slots = [slot for slot in all_slots if "fts" in slot.get("channels", ())]
    return fts_slots or all_slots


def _rare_query_terms(term_doc_freq: dict[str, int]) -> set[str]:
    return {term for term, doc_freq in term_doc_freq.items() if doc_freq == 1}


def _weighted_token_overlap_from_terms(
    query_terms: set[str],
    candidate_terms: set[str],
    term_doc_freq: dict[str, int],
    candidate_count: int,
) -> float:
    if not query_terms or not candidate_terms:
        return 0.0
    denominator = 0.0
    numerator = 0.0
    for term in query_terms:
        doc_freq = max(1, int(term_doc_freq.get(term, 0)))
        weight = 1.0 / math.sqrt(doc_freq)
        denominator += weight
        if term in candidate_terms:
            numerator += weight
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _scoring_terms(text: str) -> set[str]:
    return set(_ordered_scoring_terms(text))


def _ordered_scoring_terms(text: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in re.findall(r"[A-Za-z0-9]+", text.lower(), flags=re.UNICODE):
        if len(term) <= 1 or term in _FTS_STOPWORDS:
            continue
        normalized = _normalized_scoring_term(term)
        if normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    return terms


def _explicit_anchor_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for term in re.findall(r"[A-Za-z0-9]+", text, flags=re.UNICODE):
        if len(term) < 3 or not any(char.isalpha() for char in term):
            continue
        if term.upper() == term:
            normalized = _normalized_scoring_term(term.lower())
            if normalized not in _FTS_STOPWORDS:
                terms.add(normalized)
    return terms


def _tail_intent_terms(text: str) -> set[str]:
    terms = _ordered_scoring_terms(text)
    if len(terms) <= 3:
        return set(terms)
    return set(terms[-3:])


def _normalized_scoring_term(term: str) -> str:
    if term.endswith("ing") and len(term) > 5:
        return term[:-3]
    if term.endswith("ed") and len(term) > 4:
        return term[:-2]
    if term.endswith("es") and len(term) > 4:
        return term[:-2]
    if term.endswith("s") and len(term) > 4:
        return term[:-1]
    return term


def _bounded_fts_match_queries(query_text: str) -> tuple[str, ...]:
    terms = [term for term in _FTS_TOKEN_RE.findall(query_text) if len(term) > 1]
    if not terms:
        return ()

    queries: list[str] = []
    important = [
        term
        for term in terms
        if len(term) > 2 and term.lower() not in _FTS_STOPWORDS
    ]
    for width in (3, 4):
        if len(important) >= width:
            queries.append(_fts_and_query(important[:width]))

    if len(terms) > 1:
        queries.append(_fts_and_query(terms))

    if 1 < len(important) < len(terms):
        queries.append(_fts_and_query(important))
    return tuple(dict.fromkeys(query for query in queries if query))


def _sidecar_fts_match_queries(query_text: str) -> tuple[str, ...]:
    terms = [term for term in _FTS_TOKEN_RE.findall(query_text) if len(term) > 1]
    if not terms:
        return ()
    important = [
        term
        for term in terms
        if len(term) > 2 and term.lower() not in _FTS_STOPWORDS
    ]
    normalized = _normalized_fts_terms(important)
    queries: list[str] = []
    if len(terms) > 1:
        queries.append(_fts_and_query(terms))
    if len(important) > 1:
        queries.append(_fts_and_query(important))
    for width in (4, 3):
        if len(important) >= width:
            window = important[:width]
            queries.append(_fts_and_query(window))
            queries.append(_fts_prefix_and_query(window))
        if len(normalized) >= width:
            window = normalized[:width]
            queries.append(_fts_and_query(window))
            queries.append(_fts_prefix_and_query(window))
    for width in (4, 3, 2):
        if len(important) < width:
            continue
        for index in range(0, len(important) - width + 1):
            window = important[index : index + width]
            queries.append(_fts_and_query(window))
            queries.append(_fts_prefix_and_query(window))
        if len(normalized) >= width:
            for index in range(0, len(normalized) - width + 1):
                window = normalized[index : index + width]
                queries.append(_fts_and_query(window))
                queries.append(_fts_prefix_and_query(window))
    queries.append(_fts_match_query(query_text))
    return tuple(dict.fromkeys(query for query in queries if query))


def _normalized_fts_terms(terms: list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        lowered = term.lower()
        candidate = term
        if lowered.endswith("ing") and len(term) > 5:
            candidate = term[:-3]
        elif lowered.endswith("ed") and len(term) > 4:
            candidate = term[:-2]
        elif lowered.endswith("es") and len(term) > 4:
            candidate = term[:-2]
        elif lowered.endswith("s") and len(term) > 4:
            candidate = term[:-1]
        out.append(candidate)
    return out


def _fts_and_query(terms: list[str]) -> str:
    return " AND ".join(f'"{term}"' for term in terms)


def _fts_prefix_and_query(terms: list[str]) -> str:
    parts = []
    for term in terms:
        if len(term) >= 4:
            parts.append(f"{term}*")
        else:
            parts.append(f'"{term}"')
    return " AND ".join(parts)


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


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _ensure_retrieval_telemetry_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_retrieval_query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_time TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            query_preview TEXT NOT NULL,
            top_doc_id TEXT DEFAULT '',
            top_source TEXT DEFAULT '',
            top_layer TEXT DEFAULT '',
            top_score REAL,
            result_count INTEGER NOT NULL,
            total_ms REAL,
            vector_search_ms REAL,
            fts_search_ms REAL,
            fusion_ms REAL,
            memory_kernel_available INTEGER NOT NULL DEFAULT 0,
            memory_kernel_text_query_supported INTEGER NOT NULL DEFAULT 0,
            memory_kernel_admitted_count INTEGER NOT NULL DEFAULT 0,
            degraded_reasons_json TEXT NOT NULL DEFAULT '[]',
            top_channels_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS memory_retrieval_query_log_time_idx
        ON memory_retrieval_query_log(query_time)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS memory_retrieval_query_log_hash_idx
        ON memory_retrieval_query_log(query_hash)
        """
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _query_preview(text: str, *, max_chars: int = 240) -> str:
    preview = _SECRETISH_RE.sub("[redacted]", text)
    preview = " ".join(preview.split())
    if len(preview) <= max_chars:
        return preview
    return preview[: max(0, max_chars - 3)].rstrip() + "..."


def _is_noisy_vector_only_candidate(
    row: dict[str, Any],
    *,
    query_text: str,
    token_overlap: float,
    exact_match: bool,
) -> bool:
    """Reject common live-store vector noise when lexical evidence is absent."""

    if exact_match:
        return False
    source = str(row.get("source", ""))
    layer = str(row.get("layer", ""))
    if not (source.startswith("evolution_archive:") or layer == "development"):
        return False
    if _identifier_like_query(query_text):
        return True
    return token_overlap < 0.5


def _identifier_like_query(query_text: str) -> bool:
    stripped = query_text.strip()
    if re.search(r"[A-Za-z]+-\d{4}-\d{2}-[A-Za-z0-9-]+", stripped):
        return True
    if re.search(r"\b[A-Za-z0-9]+-[A-Za-z0-9-]+-[A-Za-z0-9-]+\b", stripped):
        return True
    return False


def _content_for_candidate(content: str, include_content: bool) -> tuple[str, tuple[str, ...]]:
    if not include_content:
        return "", ()
    if _SECRETISH_RE.search(content):
        return "[redacted: secret-like content omitted]", ("secret_like_content_redacted",)
    return content[:2000], ()


__all__ = [
    "GovernedRetrievalEngine",
    "MemoryKernelAdmissionSummary",
    "RetrievalCandidate",
    "RetrievalDiagnostics",
    "RetrievalQuery",
    "RetrievalResult",
]
