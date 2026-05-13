"""Data contracts for the Shakti executive opportunity bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutiveSignal:
    """A normalized signal from scouts, zeitgeist, recognition, or operator input."""

    source: str
    title: str
    category: str
    description: str = ""
    relevance_score: float = 0.0
    confidence: float = 0.5
    domain_hint: str = ""
    evidence_ref: str = ""
    keywords: tuple[str, ...] = ()
    suggested_action: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def evidence_line(self) -> str:
        """Return the compact evidence string used by opportunity_board.json."""
        prefix = f"{self.source}:{self.category}"
        if self.evidence_ref:
            prefix = f"{prefix}:{self.evidence_ref}"
        return f"{prefix} - {self.title}"


@dataclass(frozen=True)
class OpportunityCandidate:
    """Canonical opportunity_board entry produced by the executive."""

    opportunity_id: str
    title: str
    domain: str
    thesis: str
    factor_scores: dict[str, float]
    final_score: float
    evidence_signals: list[str]
    why_now: str
    timestamp: str
    source_inputs: list[dict[str, Any]] = field(default_factory=list)
    strategic_vision: dict[str, Any] | None = None

    def to_board_entry(self) -> dict[str, Any]:
        """Return JSON-serializable opportunity_board shape."""
        entry = {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "domain": self.domain,
            "thesis": self.thesis,
            "factor_scores": self.factor_scores,
            "final_score": self.final_score,
            "evidence_signals": self.evidence_signals,
            "why_now": self.why_now,
            "timestamp": self.timestamp,
            "source_inputs": self.source_inputs,
        }
        if self.strategic_vision:
            entry["strategic_vision"] = self.strategic_vision
        return entry


@dataclass(frozen=True)
class ExecutiveResult:
    """Summary returned by a ShaktiExecutive run."""

    dry_run: bool
    scanned_signals: int
    generated_candidates: int
    selected_candidates: int
    board_count_before: int
    board_count_after: int
    board_path: str
    report_path: str | None
    errors: tuple[str, ...] = ()
