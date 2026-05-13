"""Read-only decision ledger for MemoryKernel promotion proposals."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionGate,
    MemoryPromotionProposal,
    MemoryPromotionProposalQueue,
)


class MemoryPromotionDecisionKind(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"


class MemoryPromotionDecisionValidity(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class MemoryPromotionDecision:
    decision_id: str
    proposal_id: str
    atom_id: str
    surface_id: str
    decision: MemoryPromotionDecisionKind
    reviewer: str
    rationale: str
    decided_at: str | None
    approved_gates: tuple[MemoryPromotionGate, ...] = ()
    followups: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        proposal: MemoryPromotionProposal,
        *,
        decision: MemoryPromotionDecisionKind,
        reviewer: str,
        rationale: str,
        decided_at: str | None = None,
        approved_gates: Iterable[MemoryPromotionGate] = (),
        followups: Iterable[str] = (),
        metadata: dict[str, object] | None = None,
    ) -> "MemoryPromotionDecision":
        return cls(
            decision_id=stable_decision_id(proposal.proposal_id, reviewer, decision.value),
            proposal_id=proposal.proposal_id,
            atom_id=proposal.atom_id,
            surface_id=proposal.surface_id,
            decision=decision,
            reviewer=reviewer,
            rationale=rationale,
            decided_at=decided_at,
            approved_gates=tuple(approved_gates),
            followups=tuple(followups),
            metadata=metadata or {},
        )

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        payload["approved_gates"] = [gate.value for gate in self.approved_gates]
        return payload


@dataclass(frozen=True)
class MemoryPromotionDecisionReview:
    decision: MemoryPromotionDecision
    validity: MemoryPromotionDecisionValidity
    errors: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "decision": self.decision.to_json(),
            "validity": self.validity.value,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class MemoryPromotionDecisionLedger:
    total_proposals: int
    decision_count: int
    valid_decision_count: int
    invalid_decision_count: int
    accepted_count: int
    rejected_count: int
    deferred_count: int
    undecided_count: int
    unknown_proposal_decision_count: int
    missing_required_gate_count: int
    by_decision: dict[str, int]
    warnings: tuple[str, ...]
    decision_reviews: tuple[MemoryPromotionDecisionReview, ...]
    undecided_proposal_ids: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["decision_reviews"] = [
            review.to_json() for review in self.decision_reviews
        ]
        return payload


def build_memory_decision_ledger(
    queue: MemoryPromotionProposalQueue,
    *,
    decisions: Iterable[MemoryPromotionDecision] = (),
) -> MemoryPromotionDecisionLedger:
    proposal_by_id = {proposal.proposal_id: proposal for proposal in queue.proposals}
    reviews = tuple(_review_decisions(proposal_by_id, tuple(decisions)))
    valid = tuple(
        review
        for review in reviews
        if review.validity == MemoryPromotionDecisionValidity.VALID
    )
    valid_proposal_ids = {review.decision.proposal_id for review in valid}
    undecided = tuple(
        proposal.proposal_id
        for proposal in queue.proposals
        if proposal.proposal_id not in valid_proposal_ids
    )
    by_decision = Counter(review.decision.decision.value for review in valid)
    missing_gate_count = sum(
        1
        for review in reviews
        for error in review.errors
        if error.startswith("missing_required_gate:")
    )
    unknown_count = sum(
        1
        for review in reviews
        if "unknown_proposal_id" in review.errors
    )
    return MemoryPromotionDecisionLedger(
        total_proposals=queue.proposal_count,
        decision_count=len(reviews),
        valid_decision_count=len(valid),
        invalid_decision_count=len(reviews) - len(valid),
        accepted_count=by_decision.get(MemoryPromotionDecisionKind.ACCEPT.value, 0),
        rejected_count=by_decision.get(MemoryPromotionDecisionKind.REJECT.value, 0),
        deferred_count=by_decision.get(MemoryPromotionDecisionKind.DEFER.value, 0),
        undecided_count=len(undecided),
        unknown_proposal_decision_count=unknown_count,
        missing_required_gate_count=missing_gate_count,
        by_decision=_sorted_counts(by_decision),
        warnings=_ledger_warnings(
            total_proposals=queue.proposal_count,
            valid_decision_count=len(valid),
            invalid_decision_count=len(reviews) - len(valid),
            undecided_count=len(undecided),
            unknown_count=unknown_count,
            missing_gate_count=missing_gate_count,
        ),
        decision_reviews=reviews,
        undecided_proposal_ids=undecided,
    )


def load_memory_promotion_decisions(path: Path) -> tuple[MemoryPromotionDecision, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("decisions", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("decision input must be a list or an object with a decisions list")
    return tuple(_decision_from_json(row) for row in rows)


def render_memory_decision_ledger_markdown(
    ledger: MemoryPromotionDecisionLedger,
) -> str:
    lines = [
        "# MemoryKernel Promotion Decision Ledger",
        "",
        "This is a read-only decision review artifact. It does not promote, archive, or write memory.",
        "",
        "## Summary",
        "",
        f"- Total proposals: `{ledger.total_proposals}`",
        f"- Decisions: `{ledger.decision_count}`",
        f"- Valid decisions: `{ledger.valid_decision_count}`",
        f"- Invalid decisions: `{ledger.invalid_decision_count}`",
        f"- Accepted: `{ledger.accepted_count}`",
        f"- Rejected: `{ledger.rejected_count}`",
        f"- Deferred: `{ledger.deferred_count}`",
        f"- Undecided proposals: `{ledger.undecided_count}`",
        f"- Unknown proposal decisions: `{ledger.unknown_proposal_decision_count}`",
        f"- Missing required gates: `{ledger.missing_required_gate_count}`",
        "",
    ]
    _append_counts(lines, "By Decision", ledger.by_decision)
    lines.extend(["", "## Warnings", ""])
    if ledger.warnings:
        for warning in ledger.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Decisions", ""])
    if ledger.decision_reviews:
        for review in ledger.decision_reviews:
            decision = review.decision
            lines.append(
                f"- `{decision.decision_id}` proposal=`{decision.proposal_id}` "
                f"decision=`{decision.decision.value}` validity=`{review.validity.value}`"
            )
            for error in review.errors:
                lines.append(f"  - error: `{error}`")
    else:
        lines.append("- No decisions supplied.")
    lines.extend(["", "## Undecided Proposals", ""])
    if ledger.undecided_proposal_ids:
        for proposal_id in ledger.undecided_proposal_ids:
            lines.append(f"- `{proposal_id}`")
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def _review_decisions(
    proposal_by_id: dict[str, MemoryPromotionProposal],
    decisions: tuple[MemoryPromotionDecision, ...],
) -> tuple[MemoryPromotionDecisionReview, ...]:
    seen: set[str] = set()
    reviews: list[MemoryPromotionDecisionReview] = []
    for decision in decisions:
        errors = list(_decision_errors(proposal_by_id, decision))
        if decision.proposal_id in seen:
            errors.append("duplicate_decision_for_proposal")
        seen.add(decision.proposal_id)
        reviews.append(
            MemoryPromotionDecisionReview(
                decision=decision,
                validity=(
                    MemoryPromotionDecisionValidity.INVALID
                    if errors
                    else MemoryPromotionDecisionValidity.VALID
                ),
                errors=tuple(errors),
            )
        )
    return tuple(reviews)


def _decision_errors(
    proposal_by_id: dict[str, MemoryPromotionProposal],
    decision: MemoryPromotionDecision,
) -> tuple[str, ...]:
    proposal = proposal_by_id.get(decision.proposal_id)
    errors: list[str] = []
    if proposal is None:
        errors.append("unknown_proposal_id")
        return tuple(errors)
    if decision.atom_id != proposal.atom_id:
        errors.append("atom_id_mismatch")
    if decision.surface_id != proposal.surface_id:
        errors.append("surface_id_mismatch")
    if not decision.reviewer.strip():
        errors.append("missing_reviewer")
    if not decision.rationale.strip():
        errors.append("missing_rationale")
    if decision.decision == MemoryPromotionDecisionKind.ACCEPT:
        approved = set(decision.approved_gates)
        for gate in proposal.required_gates:
            if gate not in approved:
                errors.append(f"missing_required_gate:{gate.value}")
    return tuple(errors)


def _decision_from_json(row: object) -> MemoryPromotionDecision:
    if not isinstance(row, dict):
        raise ValueError("decision rows must be objects")
    return MemoryPromotionDecision(
        decision_id=str(row.get("decision_id") or _input_decision_id(row)),
        proposal_id=str(row["proposal_id"]),
        atom_id=str(row["atom_id"]),
        surface_id=str(row["surface_id"]),
        decision=MemoryPromotionDecisionKind(str(row["decision"])),
        reviewer=str(row.get("reviewer", "")),
        rationale=str(row.get("rationale", "")),
        decided_at=str(row["decided_at"]) if row.get("decided_at") else None,
        approved_gates=tuple(
            MemoryPromotionGate(str(gate))
            for gate in row.get("approved_gates", ())
        ),
        followups=tuple(str(item) for item in row.get("followups", ())),
        metadata=dict(row.get("metadata", {})),
    )


def stable_decision_id(proposal_id: str, reviewer: str, decision: str) -> str:
    digest = hashlib.sha256(
        f"memory_decision:{proposal_id}:{reviewer}:{decision}".encode("utf-8")
    ).hexdigest()
    return f"memory_decision:{digest[:32]}"


def _input_decision_id(row: dict[str, object]) -> str:
    return stable_decision_id(
        str(row.get("proposal_id", "")),
        str(row.get("reviewer", "")),
        str(row.get("decision", "")),
    )


def _ledger_warnings(
    *,
    total_proposals: int,
    valid_decision_count: int,
    invalid_decision_count: int,
    undecided_count: int,
    unknown_count: int,
    missing_gate_count: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if total_proposals == 0:
        warnings.append("No promotion proposals were available for decision review.")
    if valid_decision_count:
        warnings.append(
            f"{valid_decision_count} decisions are valid review records, not canon writes."
        )
    if invalid_decision_count:
        warnings.append(f"{invalid_decision_count} decisions failed validation.")
    if undecided_count:
        warnings.append(f"{undecided_count} proposals remain undecided.")
    if unknown_count:
        warnings.append(f"{unknown_count} decisions reference unknown proposal IDs.")
    if missing_gate_count:
        warnings.append(f"{missing_gate_count} required accept gates are missing.")
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
