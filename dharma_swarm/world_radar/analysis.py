"""World-radar analysis: evidence thresholds, source learning, and promotion."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROMOTION_MIN_SCORE = 0.62
INCUBATION_MIN_SCORE = 0.42
TRIAGE_PROMOTION_MIN_SCORE = 0.62
TRIAGE_INCUBATION_MIN_SCORE = 0.42
DEFAULT_SOURCE_WEIGHTS = {
    "operator_drop": 1.0,
    "company_docs": 0.92,
    "github": 0.86,
    "arxiv": 0.84,
    "news": 0.78,
    "hacker_news": 0.68,
    "youtube": 0.64,
    "reddit": 0.58,
    "llm_scan": 0.5,
    "unknown": 0.45,
}
TELOS_KEYWORDS = {
    "agent",
    "agentic",
    "automation",
    "benchmark",
    "computer-use",
    "developer",
    "evaluation",
    "governance",
    "infrastructure",
    "memory",
    "model",
    "open source",
    "orchestration",
    "research",
    "runtime",
    "security",
    "tool",
    "workflow",
}
TRACTABILITY_KEYWORDS = {
    "api",
    "arxiv",
    "benchmark",
    "docs",
    "execution",
    "github",
    "infrastructure",
    "open source",
    "paper",
    "prototype",
    "public",
    "release",
    "repo",
    "runtime",
    "tool",
}
NOVELTY_KEYWORDS = {
    "benchmark",
    "frontier",
    "launch",
    "new",
    "paper",
    "release",
    "research",
    "runtime",
}
REJECT_KEYWORDS = {
    "adult",
    "casino",
    "coupon",
    "gambling",
    "malware",
    "phishing",
    "promo",
    "scam",
    "spam",
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
            "score>=0.62, deterministic Idea Spark triage passes, and either "
            "two independent public sources or operator_drop plus concrete evidence URL/source"
        ),
        "triage_rule": (
            "novelty, telos_fit, tractability, and source_confidence are "
            "deterministic 0..1 scores; promotion requires triage_score>=0.62"
        ),
        "source_weights": weights,
        "health": {
            "raw_signals": sum(len(values) for values in clusters.values()),
            "movements": len(movements),
            "promotion_ready": sum(1 for item in movements if item["status"] == "promotion_ready"),
            "incubating": sum(1 for item in movements if item["status"] == "incubating"),
            "watchlist": sum(1 for item in movements if item["status"] == "watchlist"),
            "rejected": sum(1 for item in movements if item["status"] == "rejected"),
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
                "triage": movement.get("triage", {}),
                "triage_tuple": movement.get("triage_tuple", {}),
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


def load_source_weights(path: Path) -> dict[str, float]:
    """Load persisted source weights, falling back to defaults."""
    if not path.exists():
        return dict(DEFAULT_SOURCE_WEIGHTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SOURCE_WEIGHTS)
    if not isinstance(data, dict):
        return dict(DEFAULT_SOURCE_WEIGHTS)
    weights = dict(DEFAULT_SOURCE_WEIGHTS)
    for key, value in data.items():
        try:
            weights[str(key)] = max(0.2, min(1.2, float(value)))
        except (TypeError, ValueError):
            continue
    return weights


def save_source_weights(path: Path, weights: dict[str, float]) -> None:
    """Persist source weights deterministically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: round(float(value), 3) for key, value in sorted(weights.items())}
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_source_feedback_ledger(path: Path) -> set[str]:
    """Load ids for opportunity feedback events already applied to weights."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data if str(item).strip()}
    if isinstance(data, dict):
        events = data.get("applied_event_ids", [])
        if isinstance(events, list):
            return {str(item) for item in events if str(item).strip()}
    return set()


def save_source_feedback_ledger(path: Path, applied_event_ids: set[str]) -> None:
    """Persist applied feedback ids so source learning is event-idempotent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "applied_event_ids": sorted(applied_event_ids)[-5000:],
    }
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def update_source_weights_from_opportunities(
    source_weights: dict[str, float],
    opportunity_rows: Iterable[dict[str, Any]],
    *,
    applied_event_ids: set[str] | None = None,
) -> dict[str, float]:
    """Update source trust from opportunity outcomes.

    Successful realized outcomes nudge the originating source up. Failed
    outcomes and stale unaddressed rows nudge it down. Deltas are deliberately
    small so one execution cannot dominate the source prior.
    """
    updated = dict(source_weights)
    for row in opportunity_rows:
        sources = _row_sources(row)
        if not sources:
            continue
        for event_id, delta in _row_feedback_events(row):
            if applied_event_ids is not None and event_id in applied_event_ids:
                continue
            for raw_source in sources:
                current = float(updated.get(raw_source, DEFAULT_SOURCE_WEIGHTS.get(raw_source, 0.5)))
                updated[raw_source] = round(max(0.2, min(1.2, current + delta)), 3)
            if applied_event_ids is not None:
                applied_event_ids.add(event_id)
    return updated


def _row_sources(row: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for source in row.get("source_inputs", []) or []:
        if not isinstance(source, dict):
            continue
        raw_source = str(source.get("raw_source") or source.get("source") or "").strip()
        if raw_source and raw_source not in sources:
            sources.append(raw_source)
    return sources


def _row_outcome_delta(row: dict[str, Any]) -> float:
    outcomes = [o for o in row.get("realized_outcomes", []) or [] if isinstance(o, dict)]
    if outcomes:
        success_count = sum(1 for outcome in outcomes if bool(outcome.get("success")))
        failure_count = len(outcomes) - success_count
        return max(-0.05, min(0.08, success_count * 0.03 - failure_count * 0.025))
    if row.get("addressed") or row.get("outcome_success"):
        return 0.03
    if row.get("queued"):
        return 0.0
    if row.get("stale") or str(row.get("status") or "").lower() in {"failed", "abandoned"}:
        return -0.005
    return 0.0


def _row_feedback_events(row: dict[str, Any]) -> list[tuple[str, float]]:
    row_key = _row_key(row)
    events: list[tuple[str, float]] = []
    outcomes = [o for o in row.get("realized_outcomes", []) or [] if isinstance(o, dict)]
    for index, outcome in enumerate(outcomes):
        success = bool(outcome.get("success"))
        delta = 0.03 if success else -0.025
        events.append((f"{row_key}:outcome:{_outcome_key(outcome, index)}", delta))
    if events:
        return events
    if row.get("addressed") or row.get("outcome_success"):
        return [(f"{row_key}:addressed:{_row_version(row)}", 0.03)]
    status = str(row.get("status") or "").lower()
    if row.get("stale") or status in {"failed", "abandoned"}:
        return [(f"{row_key}:status:{status or 'stale'}:{_row_version(row)}", -0.005)]
    return []


def _row_key(row: dict[str, Any]) -> str:
    raw = row.get("opportunity_id") or row.get("id") or row.get("title") or row
    if isinstance(raw, dict):
        raw = json.dumps(raw, sort_keys=True)
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:16]


def _outcome_key(outcome: dict[str, Any], index: int) -> str:
    for key in ("id", "outcome_id", "artifact_id", "trace_id", "completed_at", "recorded_at"):
        value = str(outcome.get(key) or "").strip()
        if value:
            return value
    payload = json.dumps(outcome, sort_keys=True)
    return hashlib.sha256(f"{index}:{payload}".encode("utf-8")).hexdigest()[:16]


def _row_version(row: dict[str, Any]) -> str:
    for key in ("outcome_id", "addressed_at", "updated_at", "queued_at", "timestamp"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    payload = json.dumps(row, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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
    triage = _idea_spark_triage(rows, weights=weights, public_sources=public_sources, operator_evidence=operator_evidence)
    status, reason = _status_for(score, public_sources, operator_evidence, triage=triage)
    strategy = _strategic_vision(top, status=status)
    return {
        "movement_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:14],
        "movement_key": key,
        "title": top["title"],
        "category": top["category"],
        "summary": top["description"] or top["title"],
        "weighted_score": score,
        "triage_score": triage["triage_score"],
        "triage": triage,
        "triage_tuple": {
            "novelty": triage["novelty"],
            "telos_fit": triage["telos_fit"],
            "tractability": triage["tractability"],
            "source_confidence": triage["source_confidence"],
        },
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


def _status_for(
    score: float,
    public_sources: list[str],
    operator_evidence: bool,
    *,
    triage: dict[str, Any],
) -> tuple[str, str]:
    triage_decision = str(triage.get("decision") or "")
    triage_reason = "; ".join(str(item) for item in triage.get("reasons", [])[:3])
    if triage_decision == "reject":
        return "rejected", triage_reason or "deterministic triage rejected"
    if (
        score >= PROMOTION_MIN_SCORE
        and triage_decision == "promote"
        and (len(public_sources) >= 2 or operator_evidence)
    ):
        if len(public_sources) >= 2:
            return "promotion_ready", "triage passed with two independent public sources"
        return "promotion_ready", "triage passed with operator drop and concrete evidence URL/source"
    if score >= INCUBATION_MIN_SCORE or float(triage.get("triage_score", 0.0) or 0.0) >= TRIAGE_INCUBATION_MIN_SCORE:
        if triage_decision == "insufficient_evidence":
            return "incubating", "triage needs more concrete source evidence"
        return "incubating", triage_reason or "needs scout cascade and R&D incubation"
    return "watchlist", "below promotion and incubation thresholds"


def _idea_spark_triage(
    rows: list[dict[str, Any]],
    *,
    weights: dict[str, float],
    public_sources: list[str],
    operator_evidence: bool,
) -> dict[str, Any]:
    text = _triage_text(rows)
    novelty = _score_novelty(rows, text, public_sources)
    telos_fit = _score_telos_fit(rows, text)
    tractability = _score_tractability(rows, text)
    source_confidence = _score_source_confidence(
        rows,
        weights=weights,
        public_sources=public_sources,
        operator_evidence=operator_evidence,
    )
    triage_score = round(
        0.28 * novelty
        + 0.32 * telos_fit
        + 0.20 * tractability
        + 0.20 * source_confidence,
        3,
    )
    reasons: list[str] = []
    if _keyword_hits(text, REJECT_KEYWORDS):
        reasons.append("reject_keyword_match")
    if telos_fit < 0.25:
        reasons.append("telos_fit_below_floor")
    if tractability < 0.25:
        reasons.append("tractability_below_floor")
    if source_confidence < 0.55:
        reasons.append("source_confidence_insufficient")
    if reasons and any(reason in reasons for reason in ("reject_keyword_match", "telos_fit_below_floor", "tractability_below_floor")):
        decision = "reject"
    elif source_confidence < 0.55:
        decision = "insufficient_evidence"
    elif (
        triage_score >= TRIAGE_PROMOTION_MIN_SCORE
        and novelty >= 0.45
        and telos_fit >= 0.45
        and tractability >= 0.45
    ):
        decision = "promote"
        reasons.append("triage_score_passed")
    elif triage_score >= TRIAGE_INCUBATION_MIN_SCORE:
        decision = "incubate"
        reasons.append("triage_score_incubate")
    else:
        decision = "watchlist"
        reasons.append("triage_score_below_incubation")
    return {
        "schema_version": "idea_spark_triage.v0",
        "decision": decision,
        "novelty": novelty,
        "telos_fit": telos_fit,
        "tractability": tractability,
        "source_confidence": source_confidence,
        "triage_score": triage_score,
        "reasons": _dedupe(reasons),
    }


def _score_novelty(rows: list[dict[str, Any]], text: str, public_sources: list[str]) -> float:
    keywords = _merge_keywords(rows)
    score = 0.3 + min(0.25, 0.04 * len(set(keywords)))
    score += 0.08 if len(public_sources) >= 2 else 0.0
    score += 0.08 if _keyword_hits(text, NOVELTY_KEYWORDS) else 0.0
    score += 0.06 if any(_has_concrete_evidence(row) for row in rows) else 0.0
    return round(min(1.0, score), 3)


def _score_telos_fit(rows: list[dict[str, Any]], text: str) -> float:
    score = 0.18 + min(0.58, 0.085 * len(_keyword_hits(text, TELOS_KEYWORDS)))
    if any(row.get("category") in {"company", "tool_release", "benchmark", "research"} for row in rows):
        score += 0.08
    return round(min(1.0, score), 3)


def _score_tractability(rows: list[dict[str, Any]], text: str) -> float:
    score = 0.28
    score += min(0.34, 0.075 * len(_keyword_hits(text, TRACTABILITY_KEYWORDS)))
    score += 0.14 if any(_has_concrete_evidence(row) for row in rows) else 0.0
    score += 0.08 if any(row.get("category") in {"company", "tool_release", "benchmark", "research"} for row in rows) else 0.0
    return round(min(1.0, score), 3)


def _score_source_confidence(
    rows: list[dict[str, Any]],
    *,
    weights: dict[str, float],
    public_sources: list[str],
    operator_evidence: bool,
) -> float:
    row_sources = [_public_source(row) for row in rows if _public_source(row)]
    if not row_sources:
        return 0.0
    avg_trust = sum(weights.get(source, DEFAULT_SOURCE_WEIGHTS.get(source, 0.45)) for source in row_sources) / len(row_sources)
    score = 0.18 + min(0.24, 0.12 * len(public_sources)) + 0.28 * avg_trust
    score += 0.18 if any(_has_concrete_evidence(row) for row in rows) else 0.0
    score += 0.12 if operator_evidence else 0.0
    return round(min(1.0, score), 3)


def _triage_text(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        parts.extend(
            [
                str(row.get("title") or ""),
                str(row.get("description") or ""),
                " ".join(str(item) for item in row.get("keywords", []) or []),
                str(row.get("category") or ""),
                str(row.get("source") or ""),
                str(row.get("url") or ""),
            ]
        )
    return " ".join(part.lower() for part in parts if part).strip()


def _keyword_hits(text: str, keywords: set[str]) -> set[str]:
    return {keyword for keyword in keywords if keyword in text}


def _dedupe(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


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
    raw = str(metadata.get("raw_source") or row.get("raw_source") or row.get("source") or "").strip().lower()
    source_type = str(metadata.get("source_type") or row.get("source_type") or "").strip().lower()
    haystack = f"{raw} {source_type}"
    if "github" in haystack:
        return "github"
    if "arxiv" in haystack:
        return "arxiv"
    if "hacker" in haystack or raw in {"hn", "hacker_news"}:
        return "hacker_news"
    if "reddit" in haystack:
        return "reddit"
    if raw in {"operator", "operator_drop", "manual"}:
        return "operator_drop"
    if raw in DEFAULT_SOURCE_WEIGHTS:
        return raw
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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
