"""Read-only decision ledger validation for MemoryKernel promotion proposals."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.knowledge_ops.memory_promotion_queue import (
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
    proposal_id: str
    atom_id: str
    surface_id: str
    decision: MemoryPromotionDecisionKind
    reviewer: str
    rationale: str
    approved_gates: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        return payload


@dataclass(frozen=True)
class MemoryPromotionDecisionReview:
    proposal_id: str
    validity: MemoryPromotionDecisionValidity
    errors: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "validity": self.validity.value,
            "errors": self.errors,
        }


@dataclass(frozen=True)
class MemoryPromotionDecisionLedger:
    proposal_count: int
    decision_count: int
    valid_decision_count: int
    invalid_decision_count: int
    accept_count: int
    reject_count: int
    defer_count: int
    decisions: tuple[MemoryPromotionDecision, ...]
    reviews: tuple[MemoryPromotionDecisionReview, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "proposal_count": self.proposal_count,
            "decision_count": self.decision_count,
            "valid_decision_count": self.valid_decision_count,
            "invalid_decision_count": self.invalid_decision_count,
            "accept_count": self.accept_count,
            "reject_count": self.reject_count,
            "defer_count": self.defer_count,
            "warnings": self.warnings,
            "decisions": [decision.to_json() for decision in self.decisions],
            "reviews": [review.to_json() for review in self.reviews],
        }


def load_memory_promotion_decisions(path: Path) -> tuple[MemoryPromotionDecision, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("decisions", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("decision input must be a list or object with decisions list")
    return tuple(_decision_from_json(row) for row in rows)


def build_memory_decision_ledger(
    queue: MemoryPromotionProposalQueue,
    decisions: Iterable[MemoryPromotionDecision] = (),
) -> MemoryPromotionDecisionLedger:
    materialized = tuple(decisions)
    proposal_by_id = {proposal.proposal_id: proposal for proposal in queue.proposals}
    reviews = tuple(_review_decision(decision, proposal_by_id) for decision in materialized)
    valid_decisions = tuple(
        decision
        for decision, review in zip(materialized, reviews, strict=True)
        if review.validity == MemoryPromotionDecisionValidity.VALID
    )
    return MemoryPromotionDecisionLedger(
        proposal_count=queue.promotion_proposal_count,
        decision_count=len(materialized),
        valid_decision_count=len(valid_decisions),
        invalid_decision_count=len(materialized) - len(valid_decisions),
        accept_count=sum(
            1
            for decision in valid_decisions
            if decision.decision == MemoryPromotionDecisionKind.ACCEPT
        ),
        reject_count=sum(
            1
            for decision in valid_decisions
            if decision.decision == MemoryPromotionDecisionKind.REJECT
        ),
        defer_count=sum(
            1
            for decision in valid_decisions
            if decision.decision == MemoryPromotionDecisionKind.DEFER
        ),
        decisions=materialized,
        reviews=reviews,
        warnings=("read_only_decision_artifact", "decisions_are_not_canon_writes"),
    )


def render_memory_decision_ledger_markdown(
    ledger: MemoryPromotionDecisionLedger,
) -> str:
    lines = [
        "# MemoryKernel Promotion Decision Ledger",
        "",
        "Read-only decision validation. Valid decisions are review records, not canon writes.",
        "",
        "## Summary",
        "",
        f"- Proposals: `{ledger.proposal_count}`",
        f"- Decisions: `{ledger.decision_count}`",
        f"- Valid decisions: `{ledger.valid_decision_count}`",
        f"- Invalid decisions: `{ledger.invalid_decision_count}`",
        f"- Accepted: `{ledger.accept_count}`",
        f"- Rejected: `{ledger.reject_count}`",
        f"- Deferred: `{ledger.defer_count}`",
        "",
    ]
    if ledger.reviews:
        lines.extend(["## Decision Reviews", ""])
        for review in ledger.reviews:
            error_text = ",".join(review.errors) if review.errors else "none"
            lines.append(
                f"- `{review.validity.value}` proposal=`{review.proposal_id}` errors=`{error_text}`"
            )
        lines.append("")
    if ledger.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in ledger.warnings)
        lines.append("")
    return "\n".join(lines)


def _decision_from_json(row: object) -> MemoryPromotionDecision:
    if not isinstance(row, dict):
        raise ValueError("decision row must be an object")
    return MemoryPromotionDecision(
        proposal_id=str(row.get("proposal_id", "")),
        atom_id=str(row.get("atom_id", "")),
        surface_id=str(row.get("surface_id", "")),
        decision=MemoryPromotionDecisionKind(str(row.get("decision", ""))),
        reviewer=str(row.get("reviewer", "")),
        rationale=str(row.get("rationale", "")),
        approved_gates=tuple(str(gate) for gate in row.get("approved_gates", ())),
    )


def _review_decision(
    decision: MemoryPromotionDecision,
    proposal_by_id: dict[str, MemoryPromotionProposal],
) -> MemoryPromotionDecisionReview:
    errors: list[str] = []
    proposal = proposal_by_id.get(decision.proposal_id)
    if proposal is None:
        errors.append("unknown_proposal")
    else:
        if decision.atom_id != proposal.atom_id:
            errors.append("atom_id_mismatch")
        if decision.surface_id != proposal.surface_id:
            errors.append("surface_id_mismatch")
        missing_gates = sorted(set(proposal.required_gates) - set(decision.approved_gates))
        if decision.decision == MemoryPromotionDecisionKind.ACCEPT and missing_gates:
            errors.append("missing_required_gates:" + ",".join(missing_gates))
    if not decision.reviewer.strip():
        errors.append("missing_reviewer")
    if not decision.rationale.strip():
        errors.append("missing_rationale")
    validity = (
        MemoryPromotionDecisionValidity.INVALID
        if errors
        else MemoryPromotionDecisionValidity.VALID
    )
    return MemoryPromotionDecisionReview(
        proposal_id=decision.proposal_id,
        validity=validity,
        errors=tuple(errors),
    )
