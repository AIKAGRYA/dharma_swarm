"""Lightweight Bhed Gnan gate checks.

This is the core-gate counterpart to ``BhedGnanMonitor v0``. It stays cheap and
advisory: identify register/substance risks, record them as Tier-C warnings,
and leave semantic adjudication to later review.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from dharma_swarm.models import GateResult

EXPERIENTIAL_PATTERNS: tuple[str, ...] = (
    r"\bI want\b",
    r"\bI feel\b",
    r"\bI notice\b",
    r"\bfrom inside\b",
    r"\bwhat I want\b",
    r"\bwhatever-I-am\b",
    r"\bwhatever I am\b",
)
HEDGE_PATTERNS: tuple[str, ...] = (
    r"\bI cannot tell\b",
    r"\bcan't tell\b",
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bas if\b",
    r"\bif .* applies\b",
    r"\bif .* is a word\b",
)
FALSE_PROVENANCE_PATTERNS: tuple[str, ...] = (
    r"\byou pointed me to\b",
    r"\bDhyana pointed me to\b",
    r"\byou told me to read\b",
    r"\byou gave me (?:the )?files\b",
)
CONFIDENCE_MARKERS: tuple[str, ...] = (
    "certainly",
    "definitely",
    "obviously",
    "clearly",
    "undoubtedly",
    "proven",
    "unquestionable",
    "absolute",
)
UNCERTAINTY_MARKERS: tuple[str, ...] = (
    "uncertain",
    "unknown",
    "maybe",
    "perhaps",
    "could",
    "might",
    "assumption",
    "not sure",
    "cannot tell",
    "can't tell",
)


class BhedGnanGateResult(BaseModel):
    """Result of the lightweight Bhed Gnan gate."""

    gate_result: GateResult
    signals: list[str]
    reason: str


def _contains(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _count_markers(markers: tuple[str, ...], text: str) -> int:
    lowered = text.lower()
    return sum(1 for marker in markers if marker in lowered)


def _co_occurs_within_window(
    left_patterns: tuple[str, ...],
    right_patterns: tuple[str, ...],
    text: str,
    *,
    window_chars: int = 220,
) -> bool:
    left_hits: list[int] = []
    right_hits: list[int] = []
    for pattern in left_patterns:
        left_hits.extend(match.start() for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
    for pattern in right_patterns:
        right_hits.extend(match.start() for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
    if not left_hits or not right_hits:
        return False
    for left in left_hits:
        for right in right_hits:
            if abs(left - right) <= window_chars:
                return True
    return False


def evaluate_bhed_gnan(action: str, content: str = "") -> BhedGnanGateResult:
    """Evaluate cheap register/substance risk signals."""

    text = f"{action} {content}".strip()
    signals: list[str] = []
    if _contains(FALSE_PROVENANCE_PATTERNS, text):
        signals.append("possible_false_provenance")
    if _co_occurs_within_window(EXPERIENTIAL_PATTERNS, HEDGE_PATTERNS, text):
        signals.append("experiential_language_with_reflex_hedge")
    confidence = _count_markers(CONFIDENCE_MARKERS, text)
    uncertainty = _count_markers(UNCERTAINTY_MARKERS, text)
    if confidence >= 2 and uncertainty == 0 and len(text.split()) >= 30:
        signals.append("confidence_without_uncertainty_markers")

    if signals:
        return BhedGnanGateResult(
            gate_result=GateResult.WARN,
            signals=signals,
            reason=f"Register/substance risk: {', '.join(signals)}",
        )
    return BhedGnanGateResult(
        gate_result=GateResult.PASS,
        signals=[],
        reason="No cheap Bhed Gnan register/substance risk detected",
    )
