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

from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecisionKind,
    load_memory_promotion_decisions,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionGate,
    MemoryPromotionProposal,
    MemoryPromotionProposalQueue,
    MemoryPromotionQueueStatus,
    render_memory_promotion_queue_markdown,
)

# External zeitgeist signals cross a trust boundary and are public web content,
# so they require the FULL structural gate battery before any promotion —
# including privacy_review (PII) and canon_policy_review, which the KnowledgeOps
# battery (memory_conflict_review) mandates for promotable candidates. Since
# build_memory_decision_ledger validates an ACCEPT only against
# proposal.required_gates, omitting these would let an operator validly promote
# external content without a privacy/canon check. We list the full set.
_ZEITGEIST_REQUIRED_GATES: tuple[str, ...] = (
    MemoryPromotionGate.HUMAN_REVIEW.value,
    MemoryPromotionGate.PROVENANCE_REVIEW.value,
    MemoryPromotionGate.CONFLICT_REVIEW.value,
    MemoryPromotionGate.PRIVACY_REVIEW.value,
    MemoryPromotionGate.CANON_POLICY_REVIEW.value,
    MemoryPromotionGate.KNOWLEDGEOPS_LINKING.value,
)

_SURFACE_ID = "world_zeitgeist"
# TruthState.OBSERVED: we observed the signal in the world feed but have not
# verified/curated it. This is the honest state for an external observation AND
# the state the promotion executor requires to be promotable
# (_PROMOTABLE_TRUTH_STATES = {"observed", "curated"}); "unverified" is not a
# valid TruthState and would make every proposal silently non-promotable.
_TRUTH_STATE = "observed"
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


def load_settled_atom_ids(decisions_path: Path) -> frozenset[str]:
    """atom_ids an operator has already ACCEPTed or REJECTed — never re-propose.

    ACCEPT means the signal is already in (or on its way into) memory; REJECT
    means the operator refused it. Either way, resurfacing it every cycle wastes
    review time and buries the prior decision. DEFER is intentionally NOT settled:
    a deferred signal is meant to come back. Missing/garbled ledger -> empty set
    (degrade to prior behaviour, never crash the scout).
    """
    if not decisions_path.exists():
        return frozenset()
    try:
        decisions = load_memory_promotion_decisions(decisions_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return frozenset()
    return frozenset(
        d.atom_id
        for d in decisions
        if d.decision
        in (MemoryPromotionDecisionKind.ACCEPT, MemoryPromotionDecisionKind.REJECT)
    )


def build_zeitgeist_promotion_queue(
    rows: list[dict[str, Any]],
    settled_atom_ids: frozenset[str] = frozenset(),
) -> MemoryPromotionProposalQueue:
    """Convert zeitgeist inbox rows into a read-only promotion proposal queue.

    Accounting invariant (holds exactly):
      total_atoms_reviewed == promotion_proposal_count + blocker_occurrence_count
    where blocker_occurrence_count = rows-with-no-id + already-settled + duplicates.
    Rows with no usable id are blocked. Signals the operator already decided
    (settled_atom_ids) are skipped so a REJECT is not re-proposed next cycle.
    Duplicate signal ids within one batch collapse to a single proposal.
    """
    proposals: dict[str, MemoryPromotionProposal] = {}
    blocked = 0
    settled = 0
    duplicates = 0
    for row in rows:
        proposal = _proposal_from_signal(row)
        if proposal is None:
            blocked += 1
            continue
        if proposal.atom_id in settled_atom_ids:
            settled += 1
            continue
        if proposal.atom_id in proposals:
            duplicates += 1
        proposals[proposal.atom_id] = proposal
    ordered = tuple(proposals.values())
    warnings = [
        "read_only_queue_not_authority",
        "no_canon_or_memory_writes",
        "external_unverified_signals_need_human_review",
    ]
    if settled:
        warnings.append("prior_operator_decisions_honored")
    return MemoryPromotionProposalQueue(
        total_atoms_reviewed=len(rows),
        promotion_proposal_count=len(ordered),
        blocked_atom_count=blocked + settled,
        blocker_occurrence_count=blocked + settled + duplicates,
        proposals=ordered,
        warnings=tuple(warnings),
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
    # resolve() canonicalizes any '..' segments so a misconfigured state_dir
    # cannot traverse outside its own tree.
    meta = state_dir.expanduser().resolve() / "meta"
    inbox_path = meta / "world_zeitgeist_inbox.jsonl"
    out_dir = meta / "knowledge_ops"
    decisions_path = out_dir / "zeitgeist_promotion_decisions.json"

    rows = load_zeitgeist_inbox(inbox_path)
    settled = load_settled_atom_ids(decisions_path)
    queue = build_zeitgeist_promotion_queue(rows, settled_atom_ids=settled)

    json_path = out_dir / "zeitgeist_promotion_proposals.json"
    md_path = out_dir / "zeitgeist_promotion_proposals.md"
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        proposals_json = json.dumps(queue.to_json(), indent=2, sort_keys=True)
        proposals_markdown = render_memory_promotion_queue_markdown(queue)
        json_path.write_text(proposals_json, encoding="utf-8")
        md_path.write_text(proposals_markdown, encoding="utf-8")
    return {
        "inbox_path": str(inbox_path),
        "rows_read": len(rows),
        "proposal_count": queue.promotion_proposal_count,
        "blocked_count": queue.blocked_atom_count,
        # Count of THIS batch's rows actually suppressed by a settled decision —
        # not len(settled), which is every accept/reject ever recorded in the
        # ledger and inflates once old settled ids scroll out of the inbox
        # (Greptile finding, zeitgeist_promotion.py:191).
        "settled_skipped": _count_settled_in_batch(rows, settled),
        "review_json": str(json_path) if write else "",
        "review_md": str(md_path) if write else "",
    }


def _count_settled_in_batch(
    rows: list[dict[str, Any]], settled_atom_ids: frozenset[str]
) -> int:
    """How many rows in THIS batch carry an id already settled by the operator.

    Mirrors build_zeitgeist_promotion_queue's own per-row settled check so the
    reported count matches what the queue actually suppressed this cycle.
    """
    if not settled_atom_ids:
        return 0
    return sum(
        1
        for row in rows
        if str(row.get("id") or "").strip() in settled_atom_ids
    )


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
        # These rows reference public external content for review; they are
        # not themselves content-bearing MemoryKernel atoms.
        has_content=False,
    )


def _proposal_id(signal_id: str, content_ref: str, title: str) -> str:
    # Use the shared "memory_promotion_proposal:" prefix (not a bespoke
    # "zeitgeist_promotion_proposal:" one) so that, if a reviewed proposal is
    # ever bridged, the MemoryKernel control-surface receipt check recognizes
    # its source_proposal_id and links the canonical receipt. The "zg" segment
    # keeps zeitgeist ids distinguishable within the shared namespace.
    digest = hashlib.sha256(
        "\n".join((signal_id, content_ref, title)).encode("utf-8")
    ).hexdigest()
    return f"memory_promotion_proposal:zg-{digest[:24]}"
