"""KaizenReview — room-scoped learning loop (SECI cycle).

Implements Law 4: Knowledge Compounding. Every work packet outcome
gets reviewed, producing either a playbook update or a process
recommendation. This is the SECI cycle (Nonaka 1994) applied at the
room level:

  Socialization   → agents share tacit observations via WorkPacket outcomes
  Externalization → KaizenReview crystallizes observations into findings
  Combination     → findings update playbooks (explicit → explicit)
  Internalization → agents use updated playbooks in next packets

A KaizenReview is always scoped to a room_id — there is no global
review. Each room learns independently, and its playbooks stay
within its memory namespace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_review_id() -> str:
    return f"kr_{uuid4().hex[:12]}"


# -----------------------------------------------------------------------
# Review types
# -----------------------------------------------------------------------

class ReviewVerdict:
    """Named constants for review outcomes."""
    WORKING = "working"
    NEEDS_IMPROVEMENT = "needs_improvement"
    BROKEN = "broken"
    OBSOLETE = "obsolete"


@dataclass
class KaizenFinding:
    """A single observation from reviewing a work packet outcome."""
    id: str = field(default_factory=lambda: f"kf_{uuid4().hex[:12]}")
    category: str = ""  # process, tooling, quality, scope, communication
    observation: str = ""
    recommendation: str = ""
    severity: str = "info"  # info, warning, critical
    created_at: str = field(default_factory=_now_iso)

    VALID_CATEGORIES: frozenset[str] = frozenset({
        "process", "tooling", "quality", "scope", "communication",
        "budget", "governance", "integration",
    })

    VALID_SEVERITIES: frozenset[str] = frozenset({
        "info", "warning", "critical",
    })


@dataclass
class PlaybookEntry:
    """A playbook recommendation derived from kaizen findings."""
    id: str = field(default_factory=lambda: f"pb_{uuid4().hex[:12]}")
    room_id: str = ""
    title: str = ""
    description: str = ""
    source_review_id: str = ""
    source_findings: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    supersedes: str | None = None
    created_at: str = field(default_factory=_now_iso)


@dataclass
class KaizenReview:
    """A review of work packet outcomes for a room.

    The review examines completed work packets since the last review,
    extracts findings, and produces playbook entries.
    """
    id: str = field(default_factory=_new_review_id)
    room_id: str = ""
    reviewer: str = ""  # human operator or system
    reviewed_packet_ids: list[str] = field(default_factory=list)
    verdict: str = ReviewVerdict.WORKING
    findings: list[KaizenFinding] = field(default_factory=list)
    playbook_entries: list[PlaybookEntry] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "reviewer": self.reviewer,
            "reviewed_packet_ids": list(self.reviewed_packet_ids),
            "verdict": self.verdict,
            "findings": [
                {
                    "id": f.id, "category": f.category,
                    "observation": f.observation,
                    "recommendation": f.recommendation,
                    "severity": f.severity,
                }
                for f in self.findings
            ],
            "playbook_entries": [
                {
                    "id": p.id, "title": p.title,
                    "description": p.description,
                    "tags": p.tags,
                }
                for p in self.playbook_entries
            ],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# -----------------------------------------------------------------------
# Review engine
# -----------------------------------------------------------------------

class KaizenReviewValidationError(Exception):
    pass


def validate_finding(finding: KaizenFinding) -> None:
    if not finding.observation:
        raise KaizenReviewValidationError("Finding requires observation")
    if finding.category and finding.category not in KaizenFinding.VALID_CATEGORIES:
        raise KaizenReviewValidationError(
            f"Invalid category '{finding.category}'. "
            f"Valid: {sorted(KaizenFinding.VALID_CATEGORIES)}"
        )
    if finding.severity not in KaizenFinding.VALID_SEVERITIES:
        raise KaizenReviewValidationError(
            f"Invalid severity '{finding.severity}'. "
            f"Valid: {sorted(KaizenFinding.VALID_SEVERITIES)}"
        )


def validate_review(review: KaizenReview) -> None:
    if not review.room_id:
        raise KaizenReviewValidationError("Review requires room_id")
    if not review.reviewer:
        raise KaizenReviewValidationError("Review requires reviewer")
    if not review.reviewed_packet_ids:
        raise KaizenReviewValidationError(
            "Review must reference at least one work packet"
        )
    for finding in review.findings:
        validate_finding(finding)


class KaizenReviewStore:
    """In-memory store for kaizen reviews and playbook entries.

    Scoped per room: reviews only reference packets from their room.
    Integrates with KaizenOpsLocal via ingest_event for telemetry.
    """

    def __init__(self) -> None:
        self._reviews: dict[str, KaizenReview] = {}
        self._playbooks: dict[str, list[PlaybookEntry]] = {}  # room_id → entries

    def submit_review(self, review: KaizenReview) -> KaizenReview:
        """Submit a validated kaizen review."""
        validate_review(review)
        self._reviews[review.id] = review

        # Index playbook entries by room
        if review.playbook_entries:
            room_playbooks = self._playbooks.setdefault(review.room_id, [])
            for entry in review.playbook_entries:
                entry.room_id = review.room_id
                entry.source_review_id = review.id
                room_playbooks.append(entry)

        return review

    def reviews_for_room(self, room_id: str) -> list[KaizenReview]:
        return [
            r for r in self._reviews.values()
            if r.room_id == room_id
        ]

    def playbook_for_room(self, room_id: str) -> list[PlaybookEntry]:
        return list(self._playbooks.get(room_id, []))

    def latest_review(self, room_id: str) -> KaizenReview | None:
        reviews = self.reviews_for_room(room_id)
        if not reviews:
            return None
        return max(reviews, key=lambda r: r.created_at)

    def review_count(self, room_id: str) -> int:
        return len(self.reviews_for_room(room_id))

    def playbook_count(self, room_id: str) -> int:
        return len(self.playbook_for_room(room_id))

    def all_findings(
        self, room_id: str, *, severity: str | None = None,
    ) -> list[KaizenFinding]:
        """Get all findings for a room, optionally filtered by severity."""
        findings: list[KaizenFinding] = []
        for review in self.reviews_for_room(room_id):
            for f in review.findings:
                if severity is None or f.severity == severity:
                    findings.append(f)
        return findings

    def render_playbook_markdown(self, room_id: str) -> str:
        """Render the room's playbook as markdown."""
        entries = self.playbook_for_room(room_id)
        if not entries:
            return f"# Playbook: {room_id}\n\n_No entries yet._\n"

        lines: list[str] = [
            f"# Playbook: {room_id}\n",
            f"_{len(entries)} entries from {self.review_count(room_id)} reviews_\n",
        ]
        for entry in entries:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            lines.append(f"## {entry.title}{tags}\n")
            lines.append(f"{entry.description}\n")
            if entry.supersedes:
                lines.append(f"_Supersedes: {entry.supersedes}_\n")
        return "\n".join(lines)


def build_review_from_packets(
    room_id: str,
    reviewer: str,
    packets: list[dict[str, Any]],
) -> KaizenReview:
    """Build a review from completed work packet data.

    This is the "externalization" step of the SECI cycle: tacit
    observations from packet outcomes become explicit findings.

    Args:
        room_id: The room being reviewed.
        reviewer: Human operator performing the review.
        packets: List of packet dicts with 'id', 'outcome', 'cost_tokens', etc.

    Returns:
        A KaizenReview with auto-generated findings (still needs human review).
    """
    findings: list[KaizenFinding] = []
    packet_ids: list[str] = []

    for p in packets:
        packet_ids.append(p.get("id", ""))

        outcome = p.get("outcome", "")
        cost = p.get("cost_tokens", 0)
        ceiling = p.get("cost_ceiling", 0)

        if outcome and "fail" in outcome.lower():
            findings.append(KaizenFinding(
                category="quality",
                observation=f"Packet {p.get('id', '?')} failed: {outcome}",
                recommendation="Investigate failure cause and update process",
                severity="warning",
            ))

        if ceiling > 0 and cost > ceiling * 0.9:
            findings.append(KaizenFinding(
                category="budget",
                observation=f"Packet {p.get('id', '?')} used {cost}/{ceiling} tokens (>90% of ceiling)",
                recommendation="Consider increasing cost ceiling or breaking into smaller packets",
                severity="info",
            ))

    # Determine overall verdict
    failure_count = sum(
        1 for p in packets
        if "fail" in p.get("outcome", "").lower()
    )
    total = len(packets)

    if total == 0:
        verdict = ReviewVerdict.WORKING
    elif failure_count > total * 0.5:
        verdict = ReviewVerdict.BROKEN
    elif failure_count > 0:
        verdict = ReviewVerdict.NEEDS_IMPROVEMENT
    else:
        verdict = ReviewVerdict.WORKING

    return KaizenReview(
        room_id=room_id,
        reviewer=reviewer,
        reviewed_packet_ids=packet_ids,
        verdict=verdict,
        findings=findings,
        summary=f"Reviewed {total} packets: {total - failure_count} succeeded, {failure_count} failed",
    )
