"""Dataclasses for the governed retrieval engine's public contract.

Split out of ``memory_retrieval.py`` (Rule 10 module-line-budget
decomposition) so both ``memory_retrieval.py`` (the public door) and
``fusion.py`` (the candidate-ranking helper) can share these types without
a circular import. ``memory_retrieval.py`` re-exports these names; import
from there, not from here, outside this package.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
