"""Read-only bridge: world_zeitgeist inbox signals -> MemoryKernel promotion proposals.

The world_scout radar (dharma_swarm/world_radar/) promotes independently
verified external signals into ``{state_dir}/meta/world_zeitgeist_inbox.jsonl``.
Those rows are NOT memory: they are unverified external observations. This
module turns each inbox row into a ``MemoryPromotionProposal`` in the
``READY_FOR_REVIEW`` state so an operator can decide, one signal at a time,
whether it earns a place in durable memory.

Governance floor (never weakened here):
  * READ-ONLY. This module never writes to MemoryKernel, canon, or any
    authority store. It only emits a review artifact.
  * Every proposal carries the HUMAN_REVIEW gate (plus provenance/conflict
    gates for external content). Nothing is auto-accepted; "auto" means the
    PROPOSAL is generated automatically, not that promotion happens
    automatically.
  * Reuses the shipped MemoryPromotionProposal/Queue types — no new proposal
    schema, no new receipt store.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionGate,
    MemoryPromotionProposal,
    MemoryPromotionProposalQueue,
    MemoryPromotionQueueStatus,
    render_memory_promotion_queue_markdown,
)

# External zeitgeist signals are unverified and cross a trust boundary, so they
# require the full external-content gate battery before any promotion.
_ZEITGEIST_REQUIRED_GATES: tuple[str, ...] = (
    MemoryPromotionGate.HUMAN_REVIEW.value,
    MemoryPromotionGate.PROVENANCE_REVIEW.value,
    MemoryPromotionGate.CONFLICT_REVIEW.value,
    MemoryPromotionGate.KNOWLEDGEOPS_LINKING.value,
)

_SURFACE_ID = "world_zeitgeist"
_TRUTH_STATE = "unverified"
_AUTHORITY_LEVEL = "external_signal"


def load_zeitgeist_inbox(inbox_path: Path) -> list[dict[str, Any]]:
    """Read the JSONL zeitgeist inbox defensively. Missing/garbled -> []."""
    rows: list[dict[str, Any]] = []
    if not inbox_path.exists():
        return rows
    try:
        text = inbox_path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def build_zeitgeist_promotion_queue(
    rows: list[dict[str, Any]],
) -> MemoryPromotionProposalQueue:
    """Convert zeitgeist inbox rows into a read-only promotion proposal queue.

    Rows with no usable id are skipped (counted as blocked). Duplicate signal
    ids collapse to a single proposal (last write wins) so a signal that
    reappears across cycles does not stack duplicate proposals.
    """
    proposals: dict[str, MemoryPromotionProposal] = {}
    blocked = 0
    for row in rows:
        proposal = _proposal_from_signal(row)
        if proposal is None:
            blocked += 1
            continue
        proposals[proposal.atom_id] = proposal
    ordered = tuple(proposals.values())
    warnings = (
        "read_only_queue_not_authority",
        "no_canon_or_memory_writes",
        "external_unverified_signals_need_human_review",
    )
    return MemoryPromotionProposalQueue(
        total_atoms_reviewed=len(rows),
        promotion_proposal_count=len(ordered),
        blocked_atom_count=blocked,
        blocker_occurrence_count=blocked,
        proposals=ordered,
        warnings=warnings,
    )


def run_zeitgeist_promotion(
    state_dir: Path,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """End-to-end: read the inbox, build proposals, optionally write the review.

    Returns a small summary dict suitable for a cron result. Never raises on
    ordinary IO problems — a broken inbox yields an empty queue, not a crash.
    """
    meta = state_dir.expanduser() / "meta"
    inbox_path = meta / "world_zeitgeist_inbox.jsonl"
    rows = load_zeitgeist_inbox(inbox_path)
    queue = build_zeitgeist_promotion_queue(rows)

    out_dir = meta / "knowledge_ops"
    json_path = out_dir / "zeitgeist_promotion_proposals.json"
    md_path = out_dir / "zeitgeist_promotion_proposals.md"
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(queue.to_json(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        md_path.write_text(
            render_memory_promotion_queue_markdown(queue),
            encoding="utf-8",
        )
    return {
        "inbox_path": str(inbox_path),
        "rows_read": len(rows),
        "proposal_count": queue.promotion_proposal_count,
        "blocked_count": queue.blocked_atom_count,
        "review_json": str(json_path) if write else "",
        "review_md": str(md_path) if write else "",
    }


def _proposal_from_signal(row: dict[str, Any]) -> MemoryPromotionProposal | None:
    signal_id = str(row.get("id") or "").strip()
    if not signal_id:
        return None
    title = str(row.get("title") or "").strip()
    description = str(row.get("description") or "").strip()
    url = str(row.get("url") or "").strip()
    content_ref = url or signal_id
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    try:
        score = float(row.get("relevance_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0

    reasons: list[str] = [f"relevance_score={round(score, 3)}"]
    promotion_reason = str(metadata.get("promotion_reason") or "").strip()
    if promotion_reason:
        reasons.append(promotion_reason)
    source_count = metadata.get("source_count")
    if isinstance(source_count, int):
        reasons.append(f"independent_sources={source_count}")
    keywords = row.get("keywords")
    if isinstance(keywords, list) and keywords:
        reasons.append("keywords=" + ",".join(str(k) for k in keywords[:6]))

    return MemoryPromotionProposal(
        proposal_id=_proposal_id(signal_id, content_ref, title),
        atom_id=signal_id,
        surface_id=_SURFACE_ID,
        content_ref=content_ref,
        truth_state=_TRUTH_STATE,
        authority_level=_AUTHORITY_LEVEL,
        status=MemoryPromotionQueueStatus.READY_FOR_REVIEW,
        required_gates=_ZEITGEIST_REQUIRED_GATES,
        reasons=tuple(reasons),
        source_review_status=str(metadata.get("promotion_status") or "promotion_ready"),
        canon_risk="unknown",
        pii_risk="unknown",
        projection_of=(),
        has_content=bool(description or title),
    )


def _proposal_id(signal_id: str, content_ref: str, title: str) -> str:
    digest = hashlib.sha256(
        "\n".join((signal_id, content_ref, title)).encode("utf-8")
    ).hexdigest()
    return f"zeitgeist_promotion_proposal:{digest[:24]}"
