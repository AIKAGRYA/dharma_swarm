"""World-radar analysis: evidence thresholds, board rendering, and promotion."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROMOTION_MIN_SCORE = 0.62
INCUBATION_MIN_SCORE = 0.42
DEFAULT_SOURCE_WEIGHTS = {
    "operator_drop": 1.0,
    "company_docs": 0.92,
    "github": 0.86,
    "arxiv": 0.84,
    "news": 0.78,
    "hacker_news": 0.68,
    "reddit": 0.58,
    "llm_scan": 0.5,
}


def build_world_signal_board(
    rows: Iterable[dict[str, Any]],
    *,
    source_weights: dict[str, float] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Group raw world signals into movement rows with promotion status."""
    weights = {**DEFAULT_SOURCE_WEIGHTS, **(source_weights or {})}
    timestamp = now or datetime.now(timezone.utc).isoformat()
    clusters: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        normalized = _normalize_signal(row)
        if normalized is None:
            continue
        clusters.setdefault(_movement_key(normalized), []).append(normalized)

    movements = [
        _movement_from_rows(key, values, weights=weights, timestamp=timestamp)
        for key, values in clusters.items()
    ]
    movements.sort(key=lambda movement: movement["weighted_score"], reverse=True)
    return {
        "generated_at": timestamp,
        "promotion_rule": (
            "score>=0.62 and either two independent public sources or "
            "operator_drop plus concrete evidence URL/source"
        ),
        "health": {
            "raw_signals": sum(len(values) for values in clusters.values()),
            "movements": len(movements),
            "promotion_ready": sum(1 for item in movements if item["status"] == "promotion_ready"),
            "incubating": sum(1 for item in movements if item["status"] == "incubating"),
            "watchlist": sum(1 for item in movements if item["status"] == "watchlist"),
        },
        "movements": movements,
    }


def promotion_ready_signals(board: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized zeitgeist inbox rows for promotion-ready movements."""
    rows: list[dict[str, Any]] = []
    for movement in board.get("movements", []):
        if not isinstance(movement, dict) or movement.get("status") != "promotion_ready":
            continue
        metadata = dict(movement.get("strategic_vision") or {})
        metadata.update(
            {
                "movement_id": movement.get("movement_id"),
                "promotion_status": "promotion_ready",
                "promotion_reason": movement.get("promotion_reason", ""),
                "source_count": movement.get("independent_sources", 0),
                "url": movement.get("primary_url", ""),
                "raw_source": movement.get("primary_source", ""),
            }
        )
        rows.append(
            {
                "id": f"world-{movement.get('movement_id')}",
                "source": "world_zeitgeist",
                "category": movement.get("category", "opportunity"),
                "title": movement.get("title", ""),
                "description": movement.get("summary", ""),
                "relevance_score": movement.get("weighted_score", 0.0),
                "keywords": movement.get("keywords", []),
                "url": movement.get("primary_url", ""),
                "metadata": metadata,
            }
        )
    return rows


def incubating_movements(board: dict[str, Any]) -> list[dict[str, Any]]:
    """Return movement rows that need scout cascade plus R&D incubation."""
    return [
        movement
        for movement in board.get("movements", [])
        if isinstance(movement, dict) and movement.get("status") == "incubating"
    ]


def render_world_signal_brief(board: dict[str, Any]) -> str:
    """Render the board as a morning-readable Markdown brief."""
    health = board.get("health", {})
    lines = [
        "# World Signal Brief",
        "",
        f"Generated: {board.get('generated_at', '')}",
        (
            f"Movements: {health.get('movements', 0)} | "
            f"Promotion-ready: {health.get('promotion_ready', 0)} | "
            f"Incubating: {health.get('incubating', 0)}"
        ),
        "",
    ]
    for movement in board.get("movements", [])[:12]:
        if not isinstance(movement, dict):
            continue
        lines.extend(
            [
                f"## {movement.get('title', 'Untitled')}",
                (
                    f"Status: {movement.get('status')} | "
                    f"Score: {movement.get('weighted_score')} | "
                    f"Sources: {movement.get('independent_sources')}"
                ),
                f"Why it matters: {movement.get('summary', '')}",
                f"Next move: {movement.get('strategic_vision', {}).get('first_move', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def update_source_weights_from_opportunities(
    source_weights: dict[str, float],
    opportunity_rows: Iterable[dict[str, Any]],
) -> dict[str, float]:
    """Tiny deterministic feedback hook from opportunity outcomes to sources."""
    updated = dict(source_weights)
    for row in opportunity_rows:
        for source in row.get("source_inputs", []) or []:
            if not isinstance(source, dict):
                continue
            raw_source = str(source.get("raw_source") or source.get("source") or "").strip()
            if not raw_source:
                continue
            current = float(updated.get(raw_source, DEFAULT_SOURCE_WEIGHTS.get(raw_source, 0.5)))
            addressed = bool(row.get("addressed") or row.get("outcome_success"))
            updated[raw_source] = round(max(0.2, min(1.2, current + (0.03 if addressed else -0.01))), 3)
    return updated


def _movement_from_rows(
    key: str,
    rows: list[dict[str, Any]],
    *,
    weights: dict[str, float],
    timestamp: str,
) -> dict[str, Any]:
    scored = [(_row_score(row, weights), row) for row in rows]
    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top = scored[0]
    sources = sorted({_public_source(row) for row in rows if _public_source(row)})
    operator_evidence = any(_is_operator_drop(row) and _has_concrete_evidence(row) for row in rows)
    public_sources = [source for source in sources if source != "operator_drop"]
    score = round(min(1.0, top_score + min(0.14, 0.04 * max(0, len(public_sources) - 1))), 3)
    status, reason = _status_for(score, public_sources, operator_evidence)
    strategy = _strategic_vision(top, status=status)
    return {
        "movement_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:14],
        "movement_key": key,
        "title": top["title"],
        "category": top["category"],
        "summary": top["description"] or top["title"],
        "weighted_score": score,
        "status": status,
        "promotion_reason": reason,
        "independent_sources": len(public_sources),
        "operator_drop_evidence": operator_evidence,
        "primary_source": _public_source(top),
        "primary_url": top.get("url", ""),
        "keywords": _merge_keywords(rows),
        "cascade_queries": _cascade_queries(top),
        "strategic_vision": strategy,
        "signals": rows,
        "updated_at": timestamp,
    }


def _normalize_signal(row: dict[str, Any]) -> dict[str, Any] | None:
    title = str(row.get("title") or row.get("headline") or "").strip()
    if not title:
        return None
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
    source = str(row.get("source") or metadata.get("raw_source") or "unknown").strip()
    category = str(row.get("category") or row.get("kind") or "opportunity").strip()
    try:
        score = float(row.get("relevance_score", row.get("score", 0.0)) or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return {
        "id": str(row.get("id") or row.get("signal_id") or ""),
        "source": source,
        "category": category,
        "title": title[:180],
        "description": str(row.get("description") or row.get("summary") or "").strip()[:1600],
        "relevance_score": max(0.0, min(1.0, score)),
        "url": str(row.get("url") or row.get("source_url") or metadata.get("url") or "").strip(),
        "keywords": _string_list(row.get("keywords") or row.get("tags") or []),
        "metadata": metadata,
    }


def _status_for(score: float, public_sources: list[str], operator_evidence: bool) -> tuple[str, str]:
    if score >= PROMOTION_MIN_SCORE and (len(public_sources) >= 2 or operator_evidence):
        if len(public_sources) >= 2:
            return "promotion_ready", "two independent public sources"
        return "promotion_ready", "operator drop with concrete evidence URL/source"
    if score >= INCUBATION_MIN_SCORE:
        return "incubating", "needs scout cascade and R&D incubation"
    return "watchlist", "below promotion and incubation thresholds"


def _row_score(row: dict[str, Any], weights: dict[str, float]) -> float:
    source = _public_source(row)
    weight = weights.get(source, DEFAULT_SOURCE_WEIGHTS.get(source, 0.5))
    evidence_bonus = 0.08 if _has_concrete_evidence(row) else 0.0
    category_bonus = 0.05 if row["category"] in {"company", "tool_release", "benchmark"} else 0.0
    return min(1.0, row["relevance_score"] * weight + evidence_bonus + category_bonus)


def _movement_key(row: dict[str, Any]) -> str:
    explicit = row.get("metadata", {}).get("movement_key")
    if explicit:
        return str(explicit).lower().strip()
    title = re.sub(r"https?://\S+", "", row["title"].lower())
    title = re.sub(r"[^a-z0-9 ]+", " ", title)
    tokens = [token for token in title.split() if token not in {"the", "a", "an", "for", "with", "and"}]
    return " ".join(tokens[:8]) or title.strip()


def _public_source(row: dict[str, Any]) -> str:
    metadata = row.get("metadata", {})
    raw = str(metadata.get("raw_source") or row.get("source") or "").strip().lower()
    if "github" in raw:
        return "github"
    if "arxiv" in raw:
        return "arxiv"
    if "hacker" in raw or raw in {"hn", "hacker_news"}:
        return "hacker_news"
    if "reddit" in raw:
        return "reddit"
    if raw in {"operator", "operator_drop", "manual"}:
        return "operator_drop"
    return raw or "unknown"


def _is_operator_drop(row: dict[str, Any]) -> bool:
    return _public_source(row) == "operator_drop"


def _has_concrete_evidence(row: dict[str, Any]) -> bool:
    return bool(row.get("url") or row.get("metadata", {}).get("source_url"))


def _merge_keywords(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        for keyword in row.get("keywords", []):
            if keyword and keyword not in seen:
                seen.append(keyword)
    return seen[:12]


def _cascade_queries(row: dict[str, Any]) -> list[str]:
    title = row["title"]
    return [
        f'"{title}" company funding launch',
        f'"{title}" GitHub docs API',
        f'"{title}" alternatives competitors benchmark',
        f'"{title}" arxiv research agent system',
        f'"{title}" site:news.ycombinator.com OR site:reddit.com',
    ]


def _strategic_vision(row: dict[str, Any], *, status: str) -> dict[str, Any]:
    title = row["title"]
    first_principles = [
        f"What real capability boundary does {title} expose?",
        "Which primitive is underneath the surface: memory, orchestration, eval, UX, distribution, or data?",
        "What can Dharma reproduce as a governed proof without copying branding or private material?",
        "What adjacent markets or research communities are moving for the same reason?",
        "What would change in the opportunity board if this signal is true?",
    ]
    iteration_steps = [
        "Verify the claim against public primary sources.",
        "Map competitor/product primitives into Dharma primitives.",
        "Find 5 adjacent companies, repos, papers, or community threads.",
        "Extract the user/job-to-be-done pattern.",
        "State the smallest 48-hour prototype.",
        "Identify the risk, moat, and governance constraint.",
        "Draft one Shakti opportunity row with concrete artifact outcome.",
        "Route weak evidence to incubation, strong evidence to proposal.",
        "Compare against current internal capabilities.",
        "Re-score after new evidence arrives.",
    ]
    return {
        "first_principles_questions": first_principles,
        "iteration_steps": iteration_steps,
        "adjacent_searches": _cascade_queries(row),
        "strategic_moves": [
            "research",
            "reverse_engineer_public_pattern",
            "prototype_smallest_governed_version",
            "feed_shakti_opportunity_board",
        ],
        "dimensions": ["market", "capability", "technology", "distribution", "governance"],
        "uncertainty": "high until scout cascade verifies independent evidence",
        "first_move": "Run scout cascade, then write one proposal only if evidence clears the promotion rule.",
        "incubation_status": status,
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []
