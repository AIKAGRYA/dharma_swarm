"""Analysis helpers for external world signals."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_WEIGHT = 1.0

PREFERRED_TERMS = (
    "subquadratic",
    "long context",
    "coding agent",
    "agent infra",
    "governance",
    "safety",
    "eval",
    "inference",
    "memory",
    "workflow",
)


def build_world_signal_board(
    signals: list[dict[str, Any]],
    *,
    opportunity_board: list[dict[str, Any]] | None = None,
    scout_health: dict[str, Any] | None = None,
    source_weights: dict[str, float] | None = None,
    source_feed: str | None = None,
) -> dict[str, Any]:
    """Cluster normalized signals into a strategic board."""
    weights = source_weights or {}
    rows = [_normalize_signal(row, weights) for row in signals if isinstance(row, dict)]
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[_movement_key(row)].append(row)

    movements: list[dict[str, Any]] = []
    for movement_id, cluster in clusters.items():
        cluster.sort(key=lambda row: row["weighted_score"], reverse=True)
        top = cluster[0]
        corroboration = len({row["source"] for row in cluster})
        uncertainty = _uncertainty(cluster, corroboration)
        movements.append(
            {
                "movement_id": movement_id,
                "title": top["title"],
                "category": top["category"],
                "top_signal_id": top["id"],
                "weighted_score": round(top["weighted_score"], 3),
                "corroboration_count": corroboration,
                "signal_count": len(cluster),
                "uncertainty": uncertainty,
                "recommended_move": _recommended_move(top, corroboration, uncertainty),
                "questions": _metadata_list(top, "first_principles_questions"),
                "iteration_steps": _metadata_list(top, "iteration_steps"),
                "adjacent_searches": _metadata_list(top, "adjacent_searches"),
                "strategic_moves": _metadata_list(top, "strategic_moves"),
                "signals": cluster[:5],
            }
        )

    movements.sort(key=lambda row: row["weighted_score"], reverse=True)
    health_summary = _health_summary(scout_health or {})
    return {
        "source_feed": source_feed,
        "signal_count": len(rows),
        "movement_count": len(movements),
        "movements": movements[:40],
        "source_health": health_summary,
        "learning": {
            "opportunity_rows_seen": len(opportunity_board or []),
            "source_weights": weights,
        },
    }


def render_world_signal_brief(board: dict[str, Any]) -> str:
    """Render a compact operator brief from a board."""
    lines = [
        "# World Signal Brief",
        "",
        f"Signals: {board.get('signal_count', 0)}",
        f"Movements: {board.get('movement_count', 0)}",
    ]
    health = dict(board.get("source_health") or {})
    if health:
        lines.append(
            "Scout health: "
            f"{health.get('reachable_sources', 0)}/{health.get('source_count', 0)} "
            f"sources reachable, {health.get('item_count', 0)} items."
        )
    lines.append("")
    for movement in list(board.get("movements") or [])[:10]:
        lines.append(f"## {movement.get('title', 'Untitled signal')}")
        lines.append(
            f"- Score: {movement.get('weighted_score', 0)} | "
            f"Corroboration: {movement.get('corroboration_count', 0)} | "
            f"Uncertainty: {movement.get('uncertainty', 'unknown')}"
        )
        lines.append(f"- Move: {movement.get('recommended_move', 'Review manually.')}")
        questions = list(movement.get("questions") or [])[:3]
        if questions:
            lines.append("- First questions:")
            lines.extend(f"  - {question}" for question in questions)
        steps = list(movement.get("iteration_steps") or [])[:3]
        if steps:
            lines.append("- First steps:")
            lines.extend(f"  - {step}" for step in steps)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_source_weights_from_opportunities(
    opportunity_board: list[dict[str, Any]],
    weights_path: Path,
) -> dict[str, float]:
    """Nudge source weights using realized ecosystem opportunity outcomes."""
    weights = _load_weights(weights_path)
    changed = False
    for row in opportunity_board:
        if not isinstance(row, dict) or row.get("domain") != "ecosystem_scan":
            continue
        score = _realized_score(row)
        if score is None:
            continue
        for source in _raw_sources(row):
            old = weights.get(source, DEFAULT_SOURCE_WEIGHT)
            delta = 0.05 if score >= 0.6 else -0.04
            weights[source] = round(max(0.4, min(1.8, old + delta)), 3)
            changed = True
    if changed:
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        weights_path.write_text(json.dumps(weights, indent=2, sort_keys=True), encoding="utf-8")
    return weights


def _normalize_signal(row: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    source = str(row.get("source") or row.get("publisher") or "unknown")
    metadata = dict(row.get("metadata") or {})
    raw_source = str(metadata.get("raw_source") or row.get("raw_source") or source)
    score = _float(row.get("relevance_score"), _float(row.get("score"), 0.0))
    source_weight = weights.get(raw_source, weights.get(source, DEFAULT_SOURCE_WEIGHT))
    normalized = {
        "id": str(row.get("id") or f"{source}:{row.get('title', '')}"),
        "source": source,
        "raw_source": raw_source,
        "title": str(row.get("title") or "Untitled signal"),
        "category": str(row.get("category") or "world_signal"),
        "description": str(row.get("description") or row.get("body") or ""),
        "keywords": [str(k) for k in list(row.get("keywords") or [])[:12]],
        "relevance_score": round(max(0.0, min(1.0, score)), 3),
        "weighted_score": round(max(0.0, min(1.0, score * source_weight)), 3),
        "metadata": metadata,
    }
    for key in ("url", "source_url", "publisher"):
        if row.get(key) is not None:
            normalized[key] = row[key]
    return normalized


def _movement_key(row: dict[str, Any]) -> str:
    haystack = " ".join(
        [row.get("title", ""), row.get("description", ""), " ".join(row.get("keywords") or [])]
    ).lower()
    for term in PREFERRED_TERMS:
        if term in haystack:
            return f"{row.get('category', 'world_signal')}:{term.replace(' ', '_')}"
    words = [
        token
        for token in re_split(haystack)
        if len(token) > 4 and token not in {"about", "using", "their", "there"}
    ]
    return f"{row.get('category', 'world_signal')}:{words[0] if words else 'general'}"


def re_split(text: str) -> list[str]:
    return [part.strip(".,:;!?()[]{}\"'") for part in text.split()]


def _uncertainty(cluster: list[dict[str, Any]], corroboration: int) -> str:
    if corroboration >= 3:
        return "low"
    if corroboration == 2:
        return "medium"
    score = max(row.get("relevance_score", 0.0) for row in cluster)
    return "medium" if score >= 0.82 else "high"


def _recommended_move(signal: dict[str, Any], corroboration: int, uncertainty: str) -> str:
    if corroboration <= 1 and uncertainty == "high":
        return "Verify source, find two adjacent witnesses, then decide whether to research."
    if signal.get("category") in {"product_company", "agent_infra", "tool_release"}:
        return "Reverse engineer the pattern, map adjacent companies, and draft a prototype wedge."
    if signal.get("category") in {"security_regulatory", "threat"}:
        return "Assess risk, capture evidence, and route governance implications to Shakti."
    return "Research first principles, derive local leverage, and create the next experiment."


def _metadata_list(row: dict[str, Any], key: str) -> list[str]:
    value = dict(row.get("metadata") or {}).get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _health_summary(health: dict[str, Any]) -> dict[str, Any]:
    sources = list(health.get("sources") or [])
    if not sources:
        return {}
    return {
        "source_count": len(sources),
        "reachable_sources": sum(1 for source in sources if source.get("reachable")),
        "item_count": sum(int(_float(source.get("item_count"), 0.0)) for source in sources),
        "errors": [
            {"source_id": source.get("source_id"), "error": source.get("error")}
            for source in sources
            if source.get("error")
        ][:10],
    }


def _load_weights(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): _float(value, DEFAULT_SOURCE_WEIGHT) for key, value in raw.items()}


def _realized_score(row: dict[str, Any]) -> float | None:
    realized = row.get("realized_outcomes")
    if not isinstance(realized, list) or not realized:
        return None
    scores = [_float(item.get("value"), -1.0) for item in realized if isinstance(item, dict)]
    scores = [score for score in scores if score >= 0.0]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _raw_sources(row: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for source in list(row.get("source_inputs") or []):
        if not isinstance(source, dict):
            continue
        raw_source = str(source.get("raw_source") or "").strip()
        if raw_source:
            sources.append(raw_source)
    return sources


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
