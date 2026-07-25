"""Governed retrieval engine over vector projections and MemoryKernel policy.

This module is intentionally small: it does not create a new source of truth.
It ranks candidates from the retrieval projection, records degradation signals,
and optionally attaches a read-only MemoryKernel admission preview.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from dharma_swarm.memory_kernel_retrieval.engine_search import _SearchMixin
from dharma_swarm.memory_kernel_retrieval.fusion import fuse_candidates
from dharma_swarm.memory_kernel_retrieval.scoring_terms import (
    _elapsed_ms,
    _ensure_retrieval_telemetry_table,
    _module_available,
    _path_size,
    _query_preview,
    _sha256,
    _sqlite_sequence,
    _table_has_sample,
    _utc_now_iso,
)
from dharma_swarm.memory_kernel_retrieval.types import (
    MemoryKernelAdmissionSummary,
    RetrievalAbstentionConfig,
    RetrievalCandidate,
    RetrievalDiagnostics,
    RetrievalQuery,
    RetrievalResult,
)
from dharma_swarm.vector_store import VectorStore

# Shadow-scoring threshold used until an operator-set calibrated value lands.
# From the 2026-07-25 scripts/memory_retrieval_calibrate_abstention.py run over
# 31,591 live telemetry rows (27 days): 0.37 newly abstains 25/31,380 served
# queries (0.08%, within the 0.1% loss budget) while zero served queries ever
# scored below 0.25; nonsense queries score ~0.0-0.21. Receipt:
# ~/.dharma/witness/audit_impl_20260725/abstention_calibration_20260725T145824Z.json
# NOT a serving-path threshold while RetrievalAbstentionConfig.enabled is False.
_DEFAULT_CALIBRATED_MIN_SCORE = 0.37

# Curated memory layers considered for the default retrieval scope. Currently
# unreferenced within this module (kept for the public retrieval-layer
# vocabulary this door documents); left in place rather than moved so a
# decomposition PR does not silently drop a public-shaped constant.
_CURATED_MEMORY_LAYERS = ("memory_context", "memory_graph", "source_file")


class GovernedRetrievalEngine(_SearchMixin):
    """Rank retrieval projection candidates with explicit guardrail signals."""

    def __init__(
        self,
        *,
        state_dir: Path,
        vector_store: VectorStore | None = None,
        memory_kernel: Any | None = None,
        dim: int = 128,
        abstention: RetrievalAbstentionConfig | None = None,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.vector_store = vector_store or VectorStore(state_dir=self.state_dir, dim=dim)
        self.memory_kernel = memory_kernel
        self.abstention = abstention if abstention is not None else RetrievalAbstentionConfig.from_env()
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
                abstained=self.abstention.enabled,
                abstained_reason="empty_query" if self.abstention.enabled else "",
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

        min_score = query.min_score
        if self.abstention.enabled and self.abstention.min_score is not None:
            min_score = self.abstention.min_score

        fuse_t0 = time.perf_counter()
        candidates = self._fuse_candidates(
            query_text=query.text,
            vector_results=vector_results,
            fts_results=fts_results,
            top_k=query.top_k,
            min_score=min_score,
            include_content=query.include_content,
        )
        timings["fusion"] = _elapsed_ms(fuse_t0)

        abstained = False
        abstained_reason = ""
        if self.abstention.enabled and not candidates:
            abstained = True
            abstained_reason = (
                "no_candidates_above_min_score"
                if (fts_results or vector_results)
                else "no_matching_documents"
            )

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
            abstained=abstained,
            abstained_reason=abstained_reason,
        )
        if query.record_telemetry:
            self._record_retrieval_telemetry(result)
        return result

    def _shadow_abstention(self, result: RetrievalResult) -> tuple[int, float]:
        """What the calibrated config would decide for this result.

        Recorded on every telemetry row so the DEFAULT-ON flip can be judged
        from >=1 week of shadow receipts instead of guessed. Limitation: this
        re-scores the served candidates only — it does not re-run the search
        with floors removed, so it is an upper bound on served quality.
        """

        shadow_min = (
            self.abstention.min_score
            if self.abstention.min_score is not None
            else _DEFAULT_CALIBRATED_MIN_SCORE
        )
        if not result.candidates:
            return 1, shadow_min
        return int(float(result.candidates[0].score) < shadow_min), shadow_min

    def _record_retrieval_telemetry(self, result: RetrievalResult) -> None:
        """Best-effort runtime telemetry for retrieval quality and drift audits."""

        try:
            top = result.candidates[0] if result.candidates else None
            shadow_abstained, shadow_min_score = self._shadow_abstention(result)
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
                        top_channels_json, abstained, abstained_reason,
                        shadow_abstained, shadow_min_score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        int(result.abstained),
                        result.abstained_reason,
                        shadow_abstained,
                        shadow_min_score,
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
        return fuse_candidates(
            query_text=query_text,
            vector_results=vector_results,
            fts_results=fts_results,
            top_k=top_k,
            min_score=min_score,
            include_content=include_content,
        )


__all__ = [
    "GovernedRetrievalEngine",
    "MemoryKernelAdmissionSummary",
    "RetrievalAbstentionConfig",
    "RetrievalCandidate",
    "RetrievalDiagnostics",
    "RetrievalQuery",
    "RetrievalResult",
]
