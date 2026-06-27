"""Promote live world/Shakti insights into Darwin proposal candidates.

The bridge is intentionally append-only and non-dispatching: it turns repeated
external/intuitive signal scans into Darwin's existing pending proposal queue,
then records a receipt so the promotion itself can be checked later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.pending_proposals import append_pending_proposals


DEFAULT_MIN_WORLD_SCORE = 0.45
DEFAULT_MIN_OPPORTUNITY_SCORE = 55.0

DOMAIN_COMPONENTS: dict[str, str] = {
    "artifact_publication": "dharma_swarm/daily_operating_brief.py",
    "ecosystem_scan": "dharma_swarm/world_radar/analysis.py",
    "internal_maintenance": "dharma_swarm/orchestrate_live.py",
    "productization": "dharma_swarm/opportunity_dispatcher.py",
    "reliability": "dharma_swarm/orchestrate_live.py",
    "research": "dharma_swarm/zeitgeist.py",
    "revenue_exploration": "dharma_swarm/opportunity_refill.py",
    "strategic_infrastructure": "dharma_swarm/evolution.py",
}

EVALUATOR_PLAN: tuple[dict[str, str], ...] = (
    {
        "role": "primary_source_checker",
        "verdict": "pending",
        "question": "Can the load-bearing claim be reopened against public or local primary evidence?",
    },
    {
        "role": "applicability_mapper",
        "verdict": "pending",
        "question": "Which Dharma module, loop, or artifact would actually change if the claim is true?",
    },
    {
        "role": "sandbox_designer",
        "verdict": "pending",
        "question": "What is the smallest sandboxed experiment that could beat the current baseline?",
    },
    {
        "role": "governance_risk",
        "verdict": "pending",
        "question": "What consent, autonomy, policy, or trust gate blocks direct action?",
    },
    {
        "role": "fitness_judge",
        "verdict": "pending",
        "question": "What receipt would prove this idea improved the swarm rather than narrated progress?",
    },
)


@dataclass(frozen=True)
class InsightPromotionResult:
    """Summary of one bridge pass."""

    candidates_seen: int = 0
    queued: int = 0
    skipped_duplicate: int = 0
    skipped_low_score: int = 0
    proposals_path: str = ""
    ledger_path: str = ""
    receipt_path: str = ""
    proposal_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Candidate:
    key: str
    title: str
    description: str
    score: float
    domain: str
    source: str
    source_id: str
    raw: dict[str, Any]


def promote_insights_to_pending_proposals(
    *,
    state_dir: Path | str | None = None,
    proposals_path: Path | str | None = None,
    ledger_path: Path | str | None = None,
    receipt_dir: Path | str | None = None,
    max_items: int = 8,
    min_world_score: float = DEFAULT_MIN_WORLD_SCORE,
    min_opportunity_score: float = DEFAULT_MIN_OPPORTUNITY_SCORE,
) -> InsightPromotionResult:
    """Append live insight candidates to Darwin's pending proposal queue.

    The function reads two already-existing artifacts:
    ``meta/world_zeitgeist_inbox.jsonl`` and
    ``meta/shakti_zeitgeist_state.json``. Rows are deduped by stable content
    key, so running the bridge every daemon pass does not spam Darwin.
    """

    state = Path(state_dir).expanduser() if state_dir is not None else dharma_state_dir()
    meta = state / "meta"
    evolution = state / "evolution"
    resolved_proposals = (
        Path(proposals_path).expanduser()
        if proposals_path is not None
        else evolution / "pending_proposals.jsonl"
    )
    resolved_ledger = (
        Path(ledger_path).expanduser()
        if ledger_path is not None
        else evolution / "insight_promotion_ledger.jsonl"
    )
    resolved_receipt_dir = (
        Path(receipt_dir).expanduser()
        if receipt_dir is not None
        else evolution / "insight_promotion_receipts"
    )

    candidates = _coalesce_candidates(
        [
            *_world_candidates(meta / "world_zeitgeist_inbox.jsonl", min_score=min_world_score),
            *_shakti_candidates(
                meta / "shakti_zeitgeist_state.json",
                min_score=min_opportunity_score,
            ),
        ]
    )
    candidates = candidates[: max(0, int(max_items))]
    seen_keys = _read_ledger_keys(resolved_ledger)

    proposals: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    skipped_duplicate = 0
    skipped_low_score = 0
    now = _utc_now()
    for candidate in candidates:
        if candidate.key in seen_keys:
            skipped_duplicate += 1
            continue
        if candidate.score <= 0:
            skipped_low_score += 1
            continue
        proposal = _candidate_to_proposal(candidate, promoted_at=now)
        proposals.append(proposal)
        ledger_rows.append(
            {
                "key": candidate.key,
                "proposal_id": proposal["id"],
                "title": candidate.title,
                "source": candidate.source,
                "source_id": candidate.source_id,
                "score": candidate.score,
                "promoted_at": now,
            }
        )
        seen_keys.add(candidate.key)

    queued = append_pending_proposals(proposals, path=resolved_proposals)
    if ledger_rows:
        _append_jsonl(resolved_ledger, ledger_rows)

    receipt = {
        "schema_version": "dharma.insight_evolution_promotion.v1",
        "created_at": now,
        "state_dir": str(state),
        "source_paths": {
            "world_zeitgeist_inbox": str(meta / "world_zeitgeist_inbox.jsonl"),
            "shakti_zeitgeist_state": str(meta / "shakti_zeitgeist_state.json"),
        },
        "proposals_path": str(resolved_proposals),
        "ledger_path": str(resolved_ledger),
        "candidates_seen": len(candidates),
        "queued": queued,
        "skipped_duplicate": skipped_duplicate,
        "skipped_low_score": skipped_low_score,
        "proposal_ids": [proposal["id"] for proposal in proposals],
        "proposal_keys": [row["key"] for row in ledger_rows],
    }
    resolved_receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = resolved_receipt_dir / f"{now.replace(':', '').replace('-', '')}.json"
    _write_json(receipt_path, receipt)

    return InsightPromotionResult(
        candidates_seen=len(candidates),
        queued=queued,
        skipped_duplicate=skipped_duplicate,
        skipped_low_score=skipped_low_score,
        proposals_path=str(resolved_proposals),
        ledger_path=str(resolved_ledger),
        receipt_path=str(receipt_path),
        proposal_ids=[proposal["id"] for proposal in proposals],
    )


def _world_candidates(path: Path, *, min_score: float) -> list[_Candidate]:
    out: list[_Candidate] = []
    for row in _read_jsonl(path):
        title = _text(row.get("title"))
        if not title:
            continue
        score = _float(row.get("relevance_score", row.get("score", 0.0)))
        if score < min_score:
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        source_id = _text(row.get("id") or row.get("signal_id") or metadata.get("movement_id"))
        domain = _domain_from_row(row, metadata)
        key = _stable_key("world", source_id or title, _text(row.get("url") or metadata.get("url")))
        out.append(
            _Candidate(
                key=key,
                title=title,
                description=_text(row.get("description") or row.get("summary")),
                score=score,
                domain=domain,
                source="world_zeitgeist_inbox",
                source_id=source_id,
                raw=dict(row),
            )
        )
    return out


def _shakti_candidates(path: Path, *, min_score: float) -> list[_Candidate]:
    state = _read_json(path)
    opportunities = state.get("opportunities") if isinstance(state, dict) else None
    if not isinstance(opportunities, list):
        return []
    out: list[_Candidate] = []
    for row in opportunities:
        if not isinstance(row, dict):
            continue
        title = _text(row.get("title"))
        if not title:
            continue
        score = _float(row.get("final_score"))
        if score < min_score:
            continue
        source_id = _text(row.get("opportunity_id"))
        key = _stable_key("shakti", source_id or title, _text(row.get("domain")))
        out.append(
            _Candidate(
                key=key,
                title=title,
                description=_text(row.get("thesis") or row.get("why_now")),
                score=score / 100.0 if score > 1.0 else score,
                domain=_text(row.get("domain")) or "internal_maintenance",
                source="shakti_zeitgeist_state",
                source_id=source_id,
                raw=dict(row),
            )
        )
    return out


def _coalesce_candidates(candidates: list[_Candidate]) -> list[_Candidate]:
    by_title: dict[str, _Candidate] = {}
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        title_key = " ".join(candidate.title.lower().split())
        if title_key not in by_title:
            by_title[title_key] = candidate
    return sorted(by_title.values(), key=lambda item: item.score, reverse=True)


def _candidate_to_proposal(candidate: _Candidate, *, promoted_at: str) -> dict[str, Any]:
    first_move = _first_non_empty(
        candidate.raw.get("first_move"),
        _nested(candidate.raw, "metadata", "first_move"),
        _first(_nested(candidate.raw, "metadata", "iteration_steps")),
    )
    source_refs = _source_refs(candidate.raw)
    proposal_id = "insight-" + hashlib.sha256(candidate.key.encode("utf-8")).hexdigest()[:16]
    return {
        "id": proposal_id,
        "component": DOMAIN_COMPONENTS.get(candidate.domain, "dharma_swarm/evolution.py"),
        "change_type": "zeitgeist_insight",
        "description": _proposal_description(candidate, first_move),
        "diff": "",
        "spec_ref": f"insight_evolution_bridge:{candidate.source}:{candidate.source_id or candidate.key}",
        "metadata": {
            "source": "insight_evolution_bridge",
            "candidate_key": candidate.key,
            "candidate_source": candidate.source,
            "candidate_source_id": candidate.source_id,
            "title": candidate.title,
            "domain": candidate.domain,
            "score": candidate.score,
            "promoted_at": promoted_at,
            "source_refs": source_refs,
            "dispatch_authority": False,
            "apply_authority": "darwin_sandbox_only",
            "cross_test_status": "pending",
            "evaluator_plan": list(EVALUATOR_PLAN),
            "required_receipts": [
                "primary_source_or_local_artifact",
                "applicability_mapping",
                "sandbox_verifier",
                "fitness_delta",
            ],
            "world_radar_iteration_steps": _nested(candidate.raw, "metadata", "iteration_steps") or [],
            "world_radar_first_principles": _nested(candidate.raw, "metadata", "first_principles_questions") or [],
            "raw_candidate": candidate.raw,
        },
    }


def _proposal_description(candidate: _Candidate, first_move: str) -> str:
    parts = [f"[insight:{candidate.domain}] {candidate.title}"]
    if candidate.description:
        parts.append(candidate.description)
    if first_move:
        parts.append(f"first move: {first_move}")
    return " -- ".join(parts)[:1200]


def _domain_from_row(row: dict[str, Any], metadata: dict[str, Any]) -> str:
    explicit = _text(metadata.get("domain") or row.get("domain"))
    if explicit:
        return explicit
    category = _text(row.get("category")).lower()
    if category in {"company", "startup", "market", "opportunity"}:
        return "ecosystem_scan"
    if category in {"paper", "research", "benchmark"}:
        return "research"
    if category in {"threat", "release"}:
        return "strategic_infrastructure"
    return "ecosystem_scan"


def _source_refs(row: dict[str, Any]) -> list[dict[str, str]]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    refs: list[dict[str, str]] = []
    for key in ("url", "source_url", "feed_path", "incubation_path"):
        value = _text(row.get(key) or metadata.get(key))
        if value:
            refs.append({"kind": key, "ref": value})
    for query in _nested(row, "metadata", "adjacent_searches") or []:
        if _text(query):
            refs.append({"kind": "adjacent_search", "ref": _text(query)})
    return refs[:16]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return rows
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_ledger_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for row in _read_jsonl(path):
        key = _text(row.get("key"))
        if key:
            keys.add(key)
    return keys


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_key(*parts: str) -> str:
    material = "\n".join(part.strip().lower() for part in parts if part.strip())
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"insight:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _nested(row: dict[str, Any], *keys: str) -> Any:
    current: Any = row
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = _text(item)
            if text:
                return text
    return ""


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


__all__ = [
    "DOMAIN_COMPONENTS",
    "EVALUATOR_PLAN",
    "InsightPromotionResult",
    "promote_insights_to_pending_proposals",
]
