"""Deterministic analysis for external world signals."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_world_signal_board(
    signals: list[dict[str, Any]],
    *,
    opportunity_board: Path | None = None,
    scout_health: Path | None = None,
    source_weights: Path | None = None,
    source_feed: Path | None = None,
) -> dict[str, Any]:
    """Build a compact board from ranked world-feed signals."""
    opportunities = _opportunity_lookup(opportunity_board) if opportunity_board else {}
    health = _read_json(scout_health) if scout_health else {}
    weights = _read_json(source_weights) if source_weights else {}
    source_scores = weights.get("sources", {}) if isinstance(weights, dict) else {}
    movements = _cluster_movements(signals)

    ranked = sorted(signals, key=lambda row: _float(row.get("relevance_score")), reverse=True)[:12]
    rows: list[dict[str, Any]] = []
    for row in ranked:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        title = str(row.get("title") or "").strip()
        source_url = str(row.get("source_url") or metadata.get("source_url") or "").strip()
        source = str(row.get("source") or "").strip()
        movement = _movement_for(row, movements)
        corroboration = _corroboration_count(movement)
        rows.append(
            {
                "id": row.get("id"),
                "opportunity_id": opportunities.get(_signal_lookup_key(title, source_url), ""),
                "title": title,
                "category": row.get("category", "opportunity"),
                "source": source,
                "source_url": source_url,
                "score": _float(row.get("relevance_score")),
                "source_weight": _source_weight(source_scores, source),
                "uncertainty": _uncertainty(row, corroboration),
                "corroboration_count": corroboration,
                "movement_id": movement["movement_id"],
                "movement": movement["title"],
                "why_it_matters": metadata.get("advancement_pressure") or _why_it_matters(row),
                "adjacent_search_queries": metadata.get("adjacent_search_queries", []),
                "strategic_moves": metadata.get("strategic_moves", []),
                "recommended_move": _recommended_move(row, corroboration),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_feed": str(source_feed or ""),
        "scout_health": _health_summary(health),
        "movements": list(movements.values())[:8],
        "signals": rows,
    }


def render_world_signal_brief(board: dict[str, Any]) -> str:
    """Render the morning operator/orchestrator brief."""
    lines = [
        "# World Signal Brief",
        "",
        f"Generated: {board.get('generated_at', '')}",
        "",
    ]
    health = board.get("scout_health") if isinstance(board.get("scout_health"), dict) else {}
    if health:
        lines.extend([
            "## Scout Health",
            "",
            (
                f"- Sources: {health.get('source_count', 0)}; "
                f"reachable: {health.get('reachable_count', 0)}; "
                f"items: {health.get('item_count', 0)}; "
                f"fetch_enabled: {health.get('fetch_enabled', False)}"
            ),
            "",
        ])

    movements = board.get("movements") if isinstance(board.get("movements"), list) else []
    if movements:
        lines.extend(["## Movements", ""])
        for movement in movements[:5]:
            lines.append(
                f"- {movement.get('title', '')}: {movement.get('signal_count', 0)} signal(s), "
                f"sources={movement.get('source_count', 0)}, top_score={movement.get('top_score', 0)}"
            )
        lines.append("")

    signals = board.get("signals") if isinstance(board.get("signals"), list) else []
    lines.extend(["## Top Signals", ""])
    if not signals:
        lines.append("No world signals detected.")
    for idx, row in enumerate(signals[:10], start=1):
        title = row.get("title", "")
        lines.append(f"{idx}. {title}")
        lines.append(
            f"   - score={row.get('score', 0)} uncertainty={row.get('uncertainty', '')} "
            f"move={row.get('recommended_move', '')}"
        )
        source_url = row.get("source_url", "")
        if source_url:
            lines.append(f"   - source={source_url}")
        why = row.get("why_it_matters", "")
        if why:
            lines.append(f"   - so what: {why}")
    lines.append("")
    return "\n".join(lines)


def update_source_weights_from_opportunities(
    *,
    opportunity_board: Path,
    weights_path: Path,
) -> dict[str, Any]:
    """Update source weights from realized outcomes on ecosystem opportunities."""
    rows = _read_json(opportunity_board)
    if not isinstance(rows, list):
        return _write_weights(weights_path, {})

    stats: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if not isinstance(row, dict) or row.get("domain") != "ecosystem_scan":
            continue
        outcomes = row.get("realized_outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            continue
        sources = row.get("source_inputs")
        if not isinstance(sources, list):
            continue
        for source_row in sources:
            if not isinstance(source_row, dict):
                continue
            source = str(source_row.get("raw_source") or source_row.get("source") or "").strip()
            if not source:
                continue
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                if outcome.get("success"):
                    stats[source]["success"] += 1
                else:
                    stats[source]["failure"] += 1

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
    }
    for source, counter in stats.items():
        success = counter["success"]
        failure = counter["failure"]
        total = success + failure
        weight = 1.0 + min(0.4, success * 0.05) - min(0.4, failure * 0.08)
        payload["sources"][source] = {
            "success": success,
            "failure": failure,
            "total": total,
            "weight": round(max(0.4, min(1.4, weight)), 3),
        }
    return _write_weights(weights_path, payload)


def _cluster_movements(signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in signals:
        key = _movement_key(row)
        grouped[key].append(row)

    out: dict[str, dict[str, Any]] = {}
    for key, rows in grouped.items():
        sources = {str(row.get("source") or "") for row in rows if row.get("source")}
        top = max((_float(row.get("relevance_score")) for row in rows), default=0.0)
        title = _movement_title(key, rows)
        out[key] = {
            "movement_id": key,
            "title": title,
            "signal_count": len(rows),
            "source_count": len(sources),
            "top_score": round(top, 3),
        }
    return dict(sorted(out.items(), key=lambda item: item[1]["top_score"], reverse=True))


def _movement_for(row: dict[str, Any], movements: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = _movement_key(row)
    return movements.get(key) or {
        "movement_id": key,
        "title": _movement_title(key, [row]),
        "signal_count": 1,
        "source_count": 1,
        "top_score": _float(row.get("relevance_score")),
    }


def _movement_key(row: dict[str, Any]) -> str:
    category = str(row.get("category") or "opportunity").lower()
    keywords = [str(k).lower() for k in row.get("keywords") or [] if str(k).strip()]
    for preferred in ("subquadratic", "long context", "coding agents", "agents", "mcp", "funding", "github", "paper"):
        if preferred in keywords or preferred in str(row.get("title") or "").lower():
            return f"{category}:{preferred.replace(' ', '_')}"
    return f"{category}:{(keywords[0] if keywords else 'general').replace(' ', '_')}"


def _movement_title(key: str, rows: list[dict[str, Any]]) -> str:
    category, _, topic = key.partition(":")
    if topic and topic != "general":
        return f"{topic.replace('_', ' ')} / {category.replace('_', ' ')}"
    title = str(rows[0].get("title") or "external signal") if rows else "external signal"
    return f"{category.replace('_', ' ')}: {title[:80]}"


def _corroboration_count(movement: dict[str, Any]) -> int:
    return int(movement.get("source_count") or movement.get("signal_count") or 1)


def _uncertainty(row: dict[str, Any], corroboration: int) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if corroboration >= 2:
        return "corroborated"
    if metadata.get("claims_self_reported") or metadata.get("raw_signal_not_final_judgment"):
        return "self_reported"
    source = str(row.get("source_url") or "").lower()
    if "arxiv.org" in source or "github.com" in source:
        return "source_documented"
    return "unverified"


def _recommended_move(row: dict[str, Any], corroboration: int) -> str:
    category = str(row.get("category") or "")
    score = _float(row.get("relevance_score"))
    if score >= 0.85 and corroboration >= 2:
        return "prototype"
    if score >= 0.75:
        return "teardown"
    if category in {"funding", "company", "social_signal"}:
        return "landscape_map"
    return "verify"


def _source_weight(source_scores: dict[str, Any], source: str) -> float:
    row = source_scores.get(source)
    if isinstance(row, dict):
        return _float(row.get("weight")) or 1.0
    return 1.0


def _health_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        "observed_at": payload.get("observed_at", ""),
        "fetch_enabled": bool(payload.get("fetch_enabled", False)),
        "source_count": int(_float(payload.get("source_count"))),
        "reachable_count": int(_float(payload.get("reachable_count"))),
        "item_count": int(_float(payload.get("item_count"))),
    }


def _opportunity_lookup(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    rows = _read_json(path)
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        vision = row.get("strategic_vision") if isinstance(row.get("strategic_vision"), dict) else {}
        source_url = str(vision.get("source_url") or "").strip()
        opp_id = str(row.get("opportunity_id") or "").strip()
        if title and opp_id:
            out[_signal_lookup_key(title, source_url)] = opp_id
            out[_signal_lookup_key(title, "")] = opp_id
    return out


def _read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_weights(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _signal_lookup_key(title: str, source_url: str) -> str:
    return "\0".join((title.strip().lower(), source_url.strip().lower()))


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _why_it_matters(row: dict[str, Any]) -> str:
    category = str(row.get("category") or "opportunity").replace("_", " ")
    title = str(row.get("title") or "external signal").strip()
    return f"{category} pressure: verify, map adjacency, and decide the next move for {title}."


__all__ = [
    "build_world_signal_board",
    "render_world_signal_brief",
    "update_source_weights_from_opportunities",
]
