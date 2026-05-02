"""Small, hot-path-safe contradiction heuristics for retrieved facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_NEGATION_RE = re.compile(r"\b(not|no|never|isn't|aren't|won't|cannot|can't)\b", re.I)
_NUMBER_RE = re.compile(r"(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>%|ms|s|sec|seconds|kg|gb|mb|usd|\$)?", re.I)
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_'-]+")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "is",
    "are",
    "was",
    "were",
    "for",
    "with",
    "this",
    "that",
}


@dataclass(frozen=True)
class Contradiction:
    left_id: str
    right_id: str
    reason: str
    confidence: float


def detect_contradictions(records: list[dict[str, Any]]) -> list[Contradiction]:
    contradictions: list[Contradiction] = []
    for i, left in enumerate(records):
        for right in records[i + 1:]:
            reason = _contradiction_reason(str(left.get("text", "")), str(right.get("text", "")))
            if reason is None:
                continue
            contradictions.append(
                Contradiction(
                    left_id=str(left.get("id", f"left-{i}")),
                    right_id=str(right.get("id", "right")),
                    reason=reason,
                    confidence=0.7 if reason == "numeric_disagreement" else 0.6,
                )
            )
    return contradictions


def _contradiction_reason(left: str, right: str) -> str | None:
    if _content_overlap(left, right) < 0.55:
        return None
    if bool(_NEGATION_RE.search(left)) != bool(_NEGATION_RE.search(right)):
        return "negation_flip"
    if _numeric_disagreement(left, right):
        return "numeric_disagreement"
    return None


def _content_overlap(left: str, right: str) -> float:
    left_words = _content_words(left)
    right_words = _content_words(right)
    if not left_words or not right_words:
        return 0.0
    overlap = len(left_words & right_words)
    return overlap / max(1, min(len(left_words), len(right_words)))


def _content_words(text: str) -> set[str]:
    return {
        word.lower()
        for word in _WORD_RE.findall(text)
        if len(word) > 2 and word.lower() not in _STOPWORDS
    }


def _numeric_disagreement(left: str, right: str) -> bool:
    left_numbers = _numbers(left)
    right_numbers = _numbers(right)
    for left_value, left_unit in left_numbers:
        for right_value, right_unit in right_numbers:
            if left_unit != right_unit:
                continue
            denom = max(abs(left_value), abs(right_value), 1.0)
            if abs(left_value - right_value) / denom > 0.2:
                return True
    return False


def _numbers(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for match in _NUMBER_RE.finditer(text):
        try:
            out.append((float(match.group("num")), (match.group("unit") or "").lower()))
        except ValueError:
            continue
    return out
