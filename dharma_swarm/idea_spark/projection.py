"""Project every source lane into one ``idea_spark_candidate.v0`` object.

Operator receipts, conversation idea shards, and world-radar movements/rows all
normalize into ``IdeaSparkCandidate`` so downstream routing speaks one object.
Candidates are content-addressed (idempotent by ``candidate_id``) and embed the
``idea_spark_triage.v0`` tuple verbatim — world-radar movements reuse the triage
they already carry (no re-scoring drift).
"""

from __future__ import annotations

from typing import Any

from .schemas import (
    AuthorityLevel,
    IdeaSparkCandidate,
    OperatorInputReceipt,
    PromotionStatus,
    content_hash,
    derive_candidate_id,
    derive_correlation_id,
    utc_now_iso,
)
from .triage import build_signal_row, triage_movement

_PROMOTION_STATUSES = {"rejected", "watchlist", "incubating", "promotion_ready"}

# Conversation idea-shard kinds that indicate an actionable / experimental claim.
_TASK_SHARD_KINDS = frozenset({"proposal", "todo"})
_EXPERIMENT_SHARD_KINDS = frozenset({"hypothesis"})


def _title_from(text: str, limit: int = 120) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return first_line[:limit].strip() or text.strip()[:limit]


def coerce_promotion_status(status: str) -> PromotionStatus:
    return status if status in _PROMOTION_STATUSES else "watchlist"  # type: ignore[return-value]


def default_authority_level(triage: dict[str, Any]) -> AuthorityLevel:
    decision = str(triage.get("decision") or "")
    if decision == "promote":
        return "proposal"
    return "observation"


def _attr(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def candidate_from_operator_receipt(
    receipt: OperatorInputReceipt,
    *,
    claim: str,
    title: str | None = None,
    why_now: str = "",
    domain: str = "",
    url: str = "",
    keywords: list[str] | None = None,
    relevance_score: float = 0.7,
    authority_level: AuthorityLevel | None = None,
    now: str | None = None,
) -> IdeaSparkCandidate:
    """Normalize an operator/transcript/url/go_receipt receipt into a candidate."""
    resolved_title = title or _title_from(claim)
    candidate_id = derive_candidate_id(receipt.input_id, claim)
    row = build_signal_row(
        signal_id=candidate_id,
        title=resolved_title,
        claim=claim,
        domain=domain,
        source_kind=receipt.source_kind,
        url=url or receipt.source_ref if receipt.source_kind in {"url", "youtube_transcript"} else url,
        keywords=keywords,
        relevance_score=relevance_score,
    )
    movement = triage_movement(row, now=now)
    triage = movement.get("triage", {})
    status = coerce_promotion_status(str(movement.get("status") or "watchlist"))
    evidence: list[str] = [receipt.content_hash]
    if url:
        evidence.append(url)
    return IdeaSparkCandidate(
        candidate_id=candidate_id,
        correlation_id=receipt.correlation_id,
        title=resolved_title,
        claim=claim,
        why_now=why_now,
        domain=domain,
        source_refs=[receipt.input_id, receipt.source_ref],
        evidence_refs=evidence,
        triage=triage,
        promotion_status=status,
        authority_level=authority_level or default_authority_level(triage),
        created_at=now or utc_now_iso(),
    )


def candidate_from_idea_shard(
    shard: Any,
    *,
    correlation_id: str | None = None,
    domain: str = "conversation",
    authority_level: AuthorityLevel | None = None,
    now: str | None = None,
) -> IdeaSparkCandidate:
    """Project a ``ConversationMemoryStore`` idea shard into a candidate.

    Accepts an ``IdeaShard`` dataclass or a plain dict. The stable shard id is
    preserved verbatim in ``source_refs`` (candidate_id is a separate content
    hash, since shard ids are random at harvest time).
    """
    text = str(_attr(shard, "text") or "")
    shard_id = str(_attr(shard, "shard_id") or "")
    turn_id = str(_attr(shard, "turn_id") or "")
    session_id = str(_attr(shard, "session_id") or "")
    task_id = str(_attr(shard, "task_id") or "")
    shard_kind = str(_attr(shard, "shard_kind") or "")
    salience = _attr(shard, "salience", 0.0)
    novelty = _attr(shard, "novelty", 0.0)

    claim = text
    resolved_title = _title_from(text)
    corr = correlation_id or derive_correlation_id(shard_id or resolved_title, content_hash(claim))
    candidate_id = derive_candidate_id(shard_id or resolved_title, claim)
    row = build_signal_row(
        signal_id=candidate_id,
        title=resolved_title,
        claim=claim,
        domain=domain,
        source_kind="idea_shard",
        keywords=[shard_kind] if shard_kind else None,
    )
    movement = triage_movement(row, now=now)
    triage = movement.get("triage", {})
    status = coerce_promotion_status(str(movement.get("status") or "watchlist"))

    if authority_level is not None:
        authority = authority_level
    elif shard_kind in _EXPERIMENT_SHARD_KINDS:
        authority = "experiment_candidate"
    elif shard_kind in _TASK_SHARD_KINDS:
        authority = "task_candidate"
    else:
        authority = default_authority_level(triage)

    source_refs = [ref for ref in (shard_id, turn_id, session_id, task_id) if ref]
    return IdeaSparkCandidate(
        candidate_id=candidate_id,
        correlation_id=corr,
        title=resolved_title,
        claim=claim,
        domain=domain,
        source_refs=source_refs,
        evidence_refs=[f"shard_kind:{shard_kind}", f"salience:{salience}", f"novelty:{novelty}"],
        triage=triage,
        promotion_status=status,
        authority_level=authority,
        created_at=now or utc_now_iso(),
    )


def candidate_from_world_movement(
    movement: dict[str, Any],
    *,
    correlation_id: str | None = None,
    authority_level: AuthorityLevel | None = None,
    now: str | None = None,
) -> IdeaSparkCandidate:
    """Project a world-radar board movement (already triaged) into a candidate."""
    title = str(movement.get("title") or "")
    claim = str(movement.get("summary") or title)
    triage = movement.get("triage", {}) or {}
    status = coerce_promotion_status(str(movement.get("status") or "watchlist"))
    movement_id = str(movement.get("movement_id") or movement.get("movement_key") or title)
    domain = str(movement.get("category") or "")
    corr = correlation_id or derive_correlation_id(movement_id, content_hash(claim))
    candidate_id = derive_candidate_id(movement_id, claim)

    signal_ids = [
        str(sig.get("id") or "")
        for sig in (movement.get("signals") or [])
        if isinstance(sig, dict) and sig.get("id")
    ]
    evidence: list[str] = []
    if movement.get("primary_url"):
        evidence.append(str(movement["primary_url"]))
    return IdeaSparkCandidate(
        candidate_id=candidate_id,
        correlation_id=corr,
        title=title,
        claim=claim,
        domain=domain,
        source_refs=[movement_id, *signal_ids[:3]],
        evidence_refs=evidence,
        triage=triage,
        promotion_status=status,
        authority_level=authority_level or default_authority_level(triage),
        created_at=now or utc_now_iso(),
    )


def candidates_from_world_rows(
    rows: list[dict[str, Any]],
    *,
    now: str | None = None,
) -> list[IdeaSparkCandidate]:
    """Triage raw world-radar signal rows and project each movement."""
    from dharma_swarm.world_radar.analysis import build_world_signal_board

    board = build_world_signal_board(rows, now=now)
    return [
        candidate_from_world_movement(movement, now=now)
        for movement in board.get("movements", [])
    ]
