"""Dataclasses for the governed retrieval engine's public contract.

Split out of ``memory_retrieval.py`` (Rule 10 module-line-budget
decomposition) so both ``memory_retrieval.py`` (the public door) and
``fusion.py`` (the candidate-ranking helper) can share these types without
a circular import. ``memory_retrieval.py`` re-exports these names; import
from there, not from here, outside this package.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

_TRUTHY = {"1", "true", "yes", "on"}

# Calibrated threshold used whenever an enabled config carries no explicit
# min_score (and as the shadow-scoring threshold while enabled=False). From
# the 2026-07-25 scripts/memory_retrieval_calibrate_abstention.py run over
# 31,593 live telemetry rows (27 days, 31,380 served-scored): 0.37 newly
# abstains 25/31,380 served queries (0.08%, within the 0.1% loss budget)
# while zero served queries ever scored below 0.25; nonsense queries score
# ~0.0-0.21. Receipt:
# ~/.dharma/witness/audit_impl_20260725/abstention_calibration_20260725T145824Z.json
DEFAULT_CALIBRATED_MIN_SCORE = 0.37


@dataclass(frozen=True)
class RetrievalAbstentionConfig:
    """Rollout switches for calibrated abstention (audit 2026-07-25 P0-5).

    Defaults preserve legacy behavior exactly: below-threshold sidecar
    fallback stays on, the 0.5 score/distance floors stay in place, and
    results never carry ``abstained=True``. The calibrated path is enabled
    per-engine (or fleet-wide via env) only after shadow telemetry justifies
    the flip — the live fallback path IS the serving path (fts_guard_blocked
    on 100% of live queries), so an un-shadowed flip would silently zero
    recall fleet-wide.

    Fail-closed: an enabled config never serves at the permissive per-query
    floor. ``calibrated()`` resolves a missing/invalid ``min_score`` to
    ``DEFAULT_CALIBRATED_MIN_SCORE`` — the measured threshold the shadow
    telemetry was scored at — so the env flip cannot silently deploy an
    unmeasured configuration.

    ``effective_min_score()`` doubles as the shadow-scoring threshold while
    ``enabled=False``: every telemetry row records whether the calibrated
    config *would* have abstained, without changing what is served.
    """

    enabled: bool = False
    include_below_threshold: bool = True
    apply_score_floors: bool = True
    min_score: float | None = None

    def effective_min_score(self) -> float:
        if self.min_score is not None:
            return self.min_score
        return DEFAULT_CALIBRATED_MIN_SCORE

    @classmethod
    def calibrated(cls, min_score: float | None = None) -> "RetrievalAbstentionConfig":
        return cls(
            enabled=True,
            include_below_threshold=False,
            apply_score_floors=False,
            min_score=min_score if min_score is not None else DEFAULT_CALIBRATED_MIN_SCORE,
        )

    @classmethod
    def from_env(cls) -> "RetrievalAbstentionConfig":
        enabled = (
            str(os.environ.get("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_ABSTENTION", "")).strip().lower()
            in _TRUTHY
        )
        min_score: float | None = None
        raw = str(os.environ.get("DHARMA_MEMORY_RETRIEVAL_CALIBRATED_MIN_SCORE", "")).strip()
        if raw:
            try:
                min_score = float(raw)
            except ValueError:
                # Fail-closed: a typo'd threshold must not enable the config
                # at the permissive per-query floor; calibrated() resolves
                # None to the measured default instead.
                min_score = None
        if enabled:
            return cls.calibrated(min_score=min_score)
        return cls(min_score=min_score)


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
    abstained: bool = False
    abstained_reason: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidates": tuple(candidate.to_json() for candidate in self.candidates),
            "timings_ms": self.timings_ms,
            "diagnostics": self.diagnostics.to_json(),
            "memory_kernel": self.memory_kernel.to_json(),
            "abstained": self.abstained,
            "abstained_reason": self.abstained_reason,
        }
