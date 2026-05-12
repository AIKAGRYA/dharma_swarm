"""Read-only promotion proposal queue for MemoryKernel atoms."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable

from dharma_swarm.knowledge_ops.memory_conflict_review import (
    MemoryConflictProjectionReview,
    MemoryPromotionCandidate,
    review_memory_conflicts,
)
from dharma_swarm.memory_kernel import MemoryAtom


class MemoryPromotionQueueStatus(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"


class MemoryPromotionGate(StrEnum):
    HUMAN_REVIEW = "human_review"
    PROVENANCE_REVIEW = "provenance_review"
    CONFLICT_REVIEW = "conflict_review"
    PRIVACY_REVIEW = "privacy_review"
    CANON_POLICY_REVIEW = "canon_policy_review"
    KNOWLEDGEOPS_LINKING = "knowledgeops_linking"


@dataclass(frozen=True)
class MemoryPromotionProposal:
    proposal_id: str
    atom_id: str
    surface_id: str
    atom_type: str
    content_ref: str
    current_truth_state: str
    current_authority_level: str
    confidence: float
    proposed_target: str
    status: MemoryPromotionQueueStatus
    required_gates: tuple[MemoryPromotionGate, ...]
    reason: str

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["required_gates"] = [gate.value for gate in self.required_gates]
        return payload


@dataclass(frozen=True)
class MemoryPromotionProposalQueue:
    total_atoms: int
    proposal_count: int
    displayed_proposal_count: int
    proposal_truncated: bool
    blocked_atom_count: int
    blocker_count: int
    blockers_by_reason: dict[str, int]
    required_gates_by_gate: dict[str, int]
    warnings: tuple[str, ...]
    proposals: tuple[MemoryPromotionProposal, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["proposals"] = [proposal.to_json() for proposal in self.proposals]
        return payload


def build_memory_promotion_queue(
    atoms: Iterable[MemoryAtom],
    *,
    conflict_review: MemoryConflictProjectionReview | None = None,
    proposal_limit: int = 50,
) -> MemoryPromotionProposalQueue:
    rows = tuple(atoms)
    review = conflict_review or review_memory_conflicts(
        rows,
        promotion_candidate_limit=proposal_limit,
    )
    proposals = tuple(
        _proposal_for_candidate(candidate)
        for candidate in review.promotion_candidates[: max(0, proposal_limit)]
    )
    gate_counts: Counter[str] = Counter()
    for proposal in proposals:
        for gate in proposal.required_gates:
            gate_counts[gate.value] += 1
    return MemoryPromotionProposalQueue(
        total_atoms=len(rows),
        proposal_count=review.promotion_candidate_count,
        displayed_proposal_count=len(proposals),
        proposal_truncated=review.promotion_candidate_count > len(proposals),
        blocked_atom_count=review.promotion_blocked_atom_count,
        blocker_count=review.promotion_blocker_count,
        blockers_by_reason=review.promotion_blockers_by_reason,
        required_gates_by_gate=_sorted_counts(gate_counts),
        warnings=_queue_warnings(
            proposal_count=review.promotion_candidate_count,
            displayed_proposal_count=len(proposals),
            blocked_atom_count=review.promotion_blocked_atom_count,
        ),
        proposals=proposals,
    )


def render_memory_promotion_queue_markdown(
    queue: MemoryPromotionProposalQueue,
) -> str:
    lines = [
        "# MemoryKernel Promotion Proposal Queue",
        "",
        "This is a read-only proposal queue. It does not promote, archive, or write memory.",
        "",
        "## Summary",
        "",
        f"- Total atoms reviewed: `{queue.total_atoms}`",
        f"- Promotion proposals: `{queue.proposal_count}`",
        f"- Displayed proposals: `{queue.displayed_proposal_count}`",
        f"- Proposals truncated: `{str(queue.proposal_truncated).lower()}`",
        f"- Blocked atoms: `{queue.blocked_atom_count}`",
        f"- Blocker occurrences: `{queue.blocker_count}`",
        "",
    ]
    _append_counts(lines, "Required Gates", queue.required_gates_by_gate)
    _append_counts(lines, "Blockers", queue.blockers_by_reason)
    lines.extend(["", "## Warnings", ""])
    if queue.warnings:
        for warning in queue.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Proposals", ""])
    if queue.proposals:
        for proposal in queue.proposals:
            gates = ", ".join(gate.value for gate in proposal.required_gates)
            lines.append(
                f"- `{proposal.proposal_id}` atom=`{proposal.atom_id}` "
                f"surface=`{proposal.surface_id}` truth=`{proposal.current_truth_state}` "
                f"authority=`{proposal.current_authority_level}` gates=`{gates}`"
            )
    else:
        lines.append("- No atoms passed structural promotion proposal gates.")
    lines.append("")
    return "\n".join(lines)


def _proposal_for_candidate(
    candidate: MemoryPromotionCandidate,
) -> MemoryPromotionProposal:
    gates = (
        MemoryPromotionGate.HUMAN_REVIEW,
        MemoryPromotionGate.PROVENANCE_REVIEW,
        MemoryPromotionGate.CONFLICT_REVIEW,
        MemoryPromotionGate.PRIVACY_REVIEW,
        MemoryPromotionGate.CANON_POLICY_REVIEW,
        MemoryPromotionGate.KNOWLEDGEOPS_LINKING,
    )
    return MemoryPromotionProposal(
        proposal_id=_stable_proposal_id(candidate.atom_id),
        atom_id=candidate.atom_id,
        surface_id=candidate.surface_id,
        atom_type=candidate.atom_type,
        content_ref=candidate.content_ref,
        current_truth_state=candidate.truth_state,
        current_authority_level=candidate.authority_level,
        confidence=candidate.confidence,
        proposed_target="knowledgeops.promotion_candidate",
        status=MemoryPromotionQueueStatus.READY_FOR_REVIEW,
        required_gates=gates,
        reason="MemoryKernel atom passed structural gates; canon promotion still requires review.",
    )


def _stable_proposal_id(atom_id: str) -> str:
    digest = hashlib.sha256(f"memory_promotion:{atom_id}".encode("utf-8")).hexdigest()
    return f"memory_promotion:{digest[:32]}"


def _queue_warnings(
    *,
    proposal_count: int,
    displayed_proposal_count: int,
    blocked_atom_count: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if proposal_count == 0:
        warnings.append("No atoms passed structural promotion proposal gates.")
    if proposal_count > displayed_proposal_count:
        warnings.append(
            f"{proposal_count - displayed_proposal_count} promotion proposals omitted by the bounded proposal limit."
        )
    if proposal_count:
        warnings.append(
            f"{proposal_count} atoms are ready for review, not canon; human or gated approval is required."
        )
    if blocked_atom_count:
        warnings.append(
            f"{blocked_atom_count} atoms were blocked from promotion proposal generation."
        )
    return tuple(warnings)


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _append_counts(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines.extend(["", f"## {title}", ""])
    if counts:
        for key, count in counts.items():
            lines.append(f"- `{key}`: `{count}`")
    else:
        lines.append("- None.")
