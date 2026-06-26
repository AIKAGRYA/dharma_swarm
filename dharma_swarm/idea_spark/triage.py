"""Reusable adapter over the world-radar ``idea_spark_triage.v0`` scorer.

The deterministic four-dimension triage scorer lives in
``dharma_swarm.world_radar.analysis`` and is the seed triage contract. Rather
than re-implementing (or copying) the weighting, this adapter funnels a single
normalized claim through the PUBLIC, pure, no-network entry point
``build_world_signal_board`` and returns the embedded movement so the ingest
lifecycle and the world signal board speak one triage vocabulary.
"""

from __future__ import annotations

from typing import Any, Iterable

from dharma_swarm.world_radar.analysis import build_world_signal_board

# Map an OperatorInputReceipt source_kind onto a world-radar source label so the
# triage scorer applies the right source-confidence weight. Operator-originated
# inputs map to ``operator_drop`` (the operator-evidence promotion lane).
_OPERATOR_DROP_KINDS = frozenset({"note", "transcript", "idea_shard", "session", "file"})
_PUBLIC_WEB_KINDS = frozenset({"url", "youtube_transcript"})


def source_label_for_kind(source_kind: str, *, fallback: str = "github") -> str:
    if source_kind in _OPERATOR_DROP_KINDS:
        return "operator_drop"
    if source_kind in _PUBLIC_WEB_KINDS:
        return "news"
    return fallback


def build_signal_row(
    *,
    signal_id: str,
    title: str,
    claim: str,
    domain: str = "",
    source_kind: str = "note",
    source_label: str | None = None,
    url: str = "",
    keywords: Iterable[str] | None = None,
    relevance_score: float = 0.7,
) -> dict[str, Any]:
    """Build a world-radar signal row from a normalized candidate claim."""
    return {
        "id": signal_id,
        "source": source_label or source_label_for_kind(source_kind),
        "category": domain or "opportunity",
        "title": title,
        "description": claim,
        "relevance_score": relevance_score,
        "keywords": list(keywords or []),
        "url": url,
        "metadata": {},
    }


def triage_movement(
    row: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Return the single board movement (triage + status) for one signal row."""
    board = build_world_signal_board([row], now=now)
    movements = board.get("movements") or []
    return movements[0] if movements else {}
