"""Analysis helpers for external world signals."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_WEIGHT = 1.0
PROMOTION_MIN_SCORE = 0.62
HIGH_UPSIDE_SCORE = 0.72

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
    "benchmark",
)


def build_world_signal_board(
    signals: list[dict[str, Any]],
    *,
    opportunity_board: list[dict[str, Any]] | None = None,
    scout_health: dict[str, Any] | None = None,
    source_weights: dict[str, float] | None = None,
    source_feed: str | None = None,
) -> dict[str, Any]:
    """Cluster normalized signals and determine promotion/incubation status."""
    weights = source_weights or {}
    rows = [_normalize_signal(row, weights) for row in signals if isinstance(row, dict)]
    rows = _dedupe_rows(rows)
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[_movement_key(row)].append(row)

    movements: list[dict[str, Any]] = []
    for movement_id, cluster in clusters.items():
        cluster.sort(key=lambda row: row["weighted_score"], reverse=True)
        top = cluster[0]
        independent_sources = len({row["raw_source"] for row in cluster if row["raw_source"]})
        has_operator = any(_is_operator_source(row) for row in cluster)
        has_evidence_url = any(bool(row.get("url")) for row in cluster)
        corroboration = len({row["source"] for row in cluster})
        uncertainty = _uncertainty(cluster, independent_sources)
        promotion_ready = (
            top["weighted_score"] >= PROMOTION_MIN_SCORE
            and (independent_sources >= 2 or (has_operator and has_evidence_url))
        )
        high_upside = top["weighted_score"] >= HIGH_UPSIDE_SCORE
        status = "promotion_ready" if promotion_ready else (
            "incubating" if high_upside else "watchlist"
        )
        movements.append(
            {
                "movement_id": movement_id,
                "title": top["title"],
                "category": top["category"],
                "top_signal_id": top["id"],
                "weighted_score": round(top["weighted_score"], 3),
                "corroboration_count": corroboration,
                "independent_source_count": independent_sources,
                "signal_count": len(cluster),
                "has_operator_drop": has_operator,
                "has_evidence_url": has_evidence_url,
                "uncertainty": uncertainty,
                "promotion_status": status,
                "recommended_move": _recommended_move(top, status, uncertainty),
                "questions": _metadata_list(top, "first_principles_questions"),
                "iteration_steps": _metadata_list(top, "iteration_steps"),
                "adjacent_searches": _metadata_list(top, "adjacent_searches"),
                "strategic_moves": _metadata_list(top, "strategic_moves"),
                "cascade_queries": _cascade_queries(top),
                "signals": cluster[:8],
            }
        )

    movements.sort(key=lambda row: row["weighted_score"], reverse=True)
    return {
        "source_feed": source_feed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_count": len(rows),
        "movement_count": len(movements),
        "promotion_ready_count": sum(
            1 for row in movements if row["promotion_status"] == "promotion_ready"
        ),
        "incubating_count": sum(
            1 for row in movements if row["promotion_status"] == "incubating"
        ),
        "movements": movements[:60],
        "source_health": _health_summary(scout_health or {}),
        "learning": {
            "opportunity_rows_seen": len(opportunity_board or []),
            "source_weights": weights,
        },
    }


def promotion_ready_signals(board: dict[str, Any]) -> list[dict[str, Any]]:
    """Return top signal rows that are allowed to feed Shakti."""
    out: list[dict[str, Any]] = []
    for movement in board.get("movements") or []:
        if movement.get("promotion_status") != "promotion_ready":
            continue
        signals = list(movement.get("signals") or [])
        if not signals:
            continue
        top = dict(signals[0])
        metadata = dict(top.get("metadata") or {})
        metadata.update(
            {
                "promotion_status": "promotion_ready",
                "movement_id": movement.get("movement_id"),
                "uncertainty": movement.get("uncertainty"),
                "corroboration_count": movement.get("corroboration_count"),
                "independent_source_count": movement.get("independent_source_count"),
                "first_principles_questions": movement.get("questions") or [],
                "iteration_steps": movement.get("iteration_steps") or [],
                "adjacent_searches": movement.get("adjacent_searches") or [],
                "strategic_moves": movement.get("strategic_moves") or [],
            }
        )
        top["metadata"] = metadata
        out.append(top)
    return out


def incubating_movements(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(board.get("movements") or [])
        if row.get("promotion_status") == "incubating"
    ]


def render_world_signal_brief(board: dict[str, Any]) -> str:
    """Render a compact operator brief from a board."""
    lines = [
        "# World Signal Brief",
        "",
        f"Signals: {board.get('signal_count', 0)}",
        f"Movements: {board.get('movement_count', 0)}",
        f"Promotion-ready: {board.get('promotion_ready_count', 0)}",
        f"Incubating: {board.get('incubating_count', 0)}",
    ]
    health = dict(board.get("source_health") or {})
    if health:
        lines.append(
            "Scout health: "
            f"{health.get('reachable_sources', 0)}/{health.get('source_count', 0)} "
            f"sources reachable, {health.get('item_count', 0)} items."
        )
    lines.append("")
    for movement in list(board.get("movements") or [])[:12]:
        lines.append(f"## {movement.get('title', 'Untitled signal')}")
        lines.append(
            f"- Status: {movement.get('promotion_status', 'unknown')} | "
            f"Score: {movement.get('weighted_score', 0)} | "
            f"Sources: {movement.get('independent_source_count', 0)} | "
            f"Uncertainty: {movement.get('uncertainty', 'unknown')}"
        )
        lines.append(f"- Move: {movement.get('recommended_move', 'Review manually.')}")
        incubation = movement.get("incubation_markdown_path")
        if incubation:
            lines.append(f"- Incubation: {incubation}")
        questions = list(movement.get("questions") or [])[:3]
        if questions:
            lines.append("- First questions:")
            lines.extend(f"  - {question}" for question in questions)
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
    for key in ("url", "source_url", "publisher", "published_at"):
        if row.get(key) is not None:
            normalized[key] = row[key]
    return normalized


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("url") or row.get("id") or row.get("title") or "")
        key = key.strip().lower()
        if not key:
            continue
        prev = best.get(key)
        if prev is None or row["weighted_score"] > prev["weighted_score"]:
            best[key] = row
    return list(best.values())


def _movement_key(row: dict[str, Any]) -> str:
    haystack = " ".join(
        [row.get("title", ""), row.get("description", ""), " ".join(row.get("keywords") or [])]
    ).lower()
    for term in PREFERRED_TERMS:
        if term in haystack:
            return f"{row.get('category', 'world_signal')}:{term.replace(' ', '_')}"
    words = [
        token.strip(".,:;!?()[]{}\"'")
        for token in haystack.split()
        if len(token) > 4 and token not in {"about", "using", "their", "there"}
    ]
    return f"{row.get('category', 'world_signal')}:{words[0] if words else 'general'}"


def _uncertainty(cluster: list[dict[str, Any]], independent_sources: int) -> str:
    if independent_sources >= 3:
        return "low"
    if independent_sources == 2:
        return "medium"
    score = max(row.get("weighted_score", 0.0) for row in cluster)
    return "medium" if score >= 0.82 and any(_is_operator_source(row) for row in cluster) else "high"


def _recommended_move(signal: dict[str, Any], status: str, uncertainty: str) -> str:
    if status == "promotion_ready":
        return "Promote to Shakti as an ecosystem opportunity with evidence links."
    if status == "incubating":
        return "Run 3-pass R&D incubation: verify, connect adjacent evidence, then evolve prototype angles."
    if uncertainty == "high":
        return "Keep on watchlist and seek independent corroboration."
    return "Monitor until a stronger adjacent witness appears."


def _cascade_queries(row: dict[str, Any]) -> list[str]:
    title = str(row.get("title") or "").strip()
    keywords = [str(k) for k in list(row.get("keywords") or [])[:5]]
    seeds = [title, *keywords]
    out: list[str] = []
    for seed in seeds:
        seed = seed.strip()
        if not seed:
            continue
        out.extend([
            f"{seed} competitors",
            f"{seed} github",
            f"{seed} arxiv paper benchmark",
            f"{seed} funding launch",
        ])
        if len(out) >= 12:
            break
    return out[:12]


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


def _is_operator_source(row: dict[str, Any]) -> bool:
    value = f"{row.get('source', '')} {row.get('raw_source', '')}".lower()
    return "operator" in value or "manual" in value


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
