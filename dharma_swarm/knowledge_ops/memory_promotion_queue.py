"""Read-only promotion proposal queue for MemoryKernel evidence."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import StrEnum

from dharma_swarm.knowledge_ops.memory_conflict_review import (
    MemoryConflictProjectionReview,
    MemoryPromotionCandidate,
)


class MemoryPromotionGate(StrEnum):
    HUMAN_REVIEW = "human_review"
    PROVENANCE_REVIEW = "provenance_review"
    CONFLICT_REVIEW = "conflict_review"
    PRIVACY_REVIEW = "privacy_review"
    CANON_POLICY_REVIEW = "canon_policy_review"
    KNOWLEDGEOPS_LINKING = "knowledgeops_linking"


class MemoryPromotionQueueStatus(StrEnum):
    EMPTY = "empty"
    READY_FOR_REVIEW = "ready_for_review"


@dataclass(frozen=True)
class MemoryPromotionProposal:
    proposal_id: str
    atom_id: str
    surface_id: str
    content_ref: str
    truth_state: str
    authority_level: str
    status: MemoryPromotionQueueStatus
    required_gates: tuple[str, ...]
    reasons: tuple[str, ...]
    source_review_status: str = ""
    canon_risk: str = "unknown"
    pii_risk: str = "unknown"
    projection_of: tuple[str, ...] = ()
    has_content: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class MemoryPromotionProposalQueue:
    total_atoms_reviewed: int
    promotion_proposal_count: int
    blocked_atom_count: int
    blocker_occurrence_count: int
    proposals: tuple[MemoryPromotionProposal, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "total_atoms_reviewed": self.total_atoms_reviewed,
            "promotion_proposal_count": self.promotion_proposal_count,
            "blocked_atom_count": self.blocked_atom_count,
            "blocker_occurrence_count": self.blocker_occurrence_count,
            "warnings": self.warnings,
            "proposals": [proposal.to_json() for proposal in self.proposals],
        }


def build_memory_promotion_queue(
    review: MemoryConflictProjectionReview,
) -> MemoryPromotionProposalQueue:
    proposals = tuple(_proposal_from_candidate(candidate) for candidate in review.promotion_candidates)
    warnings = [
        "read_only_queue_not_authority",
        "no_canon_or_memory_writes",
    ]
    if review.promotion_candidate_truncated:
        warnings.append("source_promotion_candidates_truncated")
    return MemoryPromotionProposalQueue(
        total_atoms_reviewed=review.total_atoms,
        promotion_proposal_count=review.promotion_candidate_count,
        blocked_atom_count=review.promotion_blocked_atom_count,
        blocker_occurrence_count=review.promotion_blocker_count,
        proposals=proposals,
        warnings=tuple(warnings),
    )


def render_memory_promotion_queue_markdown(
    queue: MemoryPromotionProposalQueue,
) -> str:
    lines = [
        "# MemoryKernel Promotion Proposal Queue",
        "",
        "Read-only review queue. Proposals are not canon and do not mutate memory.",
        "",
        "## Summary",
        "",
        f"- Total atoms reviewed: `{queue.total_atoms_reviewed}`",
        f"- Promotion proposals: `{queue.promotion_proposal_count}`",
        f"- Blocked atoms: `{queue.blocked_atom_count}`",
        f"- Blocker occurrences: `{queue.blocker_occurrence_count}`",
        "",
    ]
    if queue.proposals:
        lines.extend(["## Proposals", ""])
        for proposal in queue.proposals:
            lines.append(
                f"- `{proposal.status.value}` proposal=`{proposal.proposal_id}` "
                f"atom=`{proposal.atom_id}` surface=`{proposal.surface_id}`"
            )
        lines.append("")
    if queue.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in queue.warnings)
        lines.append("")
    return "\n".join(lines)


def _proposal_from_candidate(candidate: MemoryPromotionCandidate) -> MemoryPromotionProposal:
    return MemoryPromotionProposal(
        proposal_id=_proposal_id(candidate),
        atom_id=candidate.atom_id,
        surface_id=candidate.surface_id,
        content_ref=candidate.content_ref,
        truth_state=candidate.truth_state,
        authority_level=candidate.authority_level,
        status=MemoryPromotionQueueStatus.READY_FOR_REVIEW,
        required_gates=candidate.required_gates,
        reasons=candidate.reasons,
        source_review_status=candidate.source_review_status,
        canon_risk=candidate.canon_risk,
        pii_risk=candidate.pii_risk,
        projection_of=candidate.projection_of,
        has_content=candidate.has_content,
    )


def _proposal_id(candidate: MemoryPromotionCandidate) -> str:
    digest = hashlib.sha256(
        "\n".join((candidate.atom_id, candidate.surface_id, candidate.content_ref)).encode("utf-8")
    ).hexdigest()
    return f"memory_promotion_proposal:{digest[:24]}"
