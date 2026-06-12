"""Shared governed-work admission for risky autonomous work.

The service is intentionally deterministic and dependency-light. It reduces
requested work to allow/review/block plus explicit reasons and receipts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkKind(str, Enum):
    READ_ONLY = "read_only"
    CODE_WRITE = "code_write"
    LONG_RUNNING = "long_running"
    A2A_CLAIM = "a2a_claim"
    SELF_EVOLUTION = "self_evolution"
    PROMOTION = "promotion"


class GovernedWorkRequest(BaseModel):
    request_id: str = ""
    agent_uid: str
    work_kind: WorkKind = WorkKind.READ_ONLY
    intent: str = ""
    risk_tier: str = "Q1"
    autonomy_level: str = "manual"
    mutation_budget_remaining: int | None = None
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    protected_file_hits: list[str] = Field(default_factory=list)
    telos_decision: str = "allow"
    telos_reasons: list[str] = Field(default_factory=list)
    context_quorum_ok: bool = True
    context_quorum_ref: str = ""
    scanner_available: bool = True
    scanner_verdict: str = "clean"
    mission_contract_present: bool = False
    workspace_lease_present: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernedWorkAdmission(BaseModel):
    request_id: str = ""
    decision: Literal["allow", "review", "block"]
    reasons: list[str] = Field(default_factory=list)
    required_receipts: list[str] = Field(default_factory=list)
    reduced_authority: dict[str, Any] = Field(default_factory=dict)


def _risk_number(risk_tier: str) -> int:
    digits = "".join(ch for ch in str(risk_tier).upper() if ch.isdigit())
    return int(digits or "1")


def evaluate_governed_work_admission(request: GovernedWorkRequest) -> GovernedWorkAdmission:
    reasons: list[str] = []
    receipts: list[str] = []
    decision: Literal["allow", "review", "block"] = "allow"
    risk = _risk_number(request.risk_tier)

    def review(reason: str, receipt: str = "") -> None:
        nonlocal decision
        if decision != "block":
            decision = "review"
        reasons.append(reason)
        if receipt:
            receipts.append(receipt)

    def block(reason: str, receipt: str = "") -> None:
        nonlocal decision
        decision = "block"
        reasons.append(reason)
        if receipt:
            receipts.append(receipt)

    if request.telos_decision in {"block", "deny", "reject"}:
        block("telos_decision_block")
        reasons.extend(request.telos_reasons)

    if not request.scanner_available:
        review("scanner_unavailable", "scanner_receipt")
    elif request.scanner_verdict not in {"clean", "pass", "ok"}:
        block("scanner_verdict_not_clean", "scanner_receipt")

    if request.protected_file_hits:
        block("protected_file_hits", "protected_file_receipt")

    if risk >= 3 and not request.context_quorum_ok:
        block("context_quorum_missing_or_failed", "context_quorum_receipt")

    if request.work_kind in {WorkKind.CODE_WRITE, WorkKind.LONG_RUNNING, WorkKind.SELF_EVOLUTION, WorkKind.PROMOTION}:
        if not request.mission_contract_present:
            review("mission_contract_missing", "mission_contract_receipt")
        if not request.workspace_lease_present:
            review("workspace_lease_missing", "workspace_lease_receipt")

    if request.work_kind == WorkKind.SELF_EVOLUTION:
        if request.mutation_budget_remaining is None:
            review("mutation_budget_missing", "mutation_budget_receipt")
        elif request.mutation_budget_remaining <= 0:
            block("mutation_budget_exhausted", "mutation_budget_receipt")

    if request.work_kind == WorkKind.PROMOTION:
        review("promotion_requires_holdout_receipt", "holdout_eval_receipt")

    return GovernedWorkAdmission(
        request_id=request.request_id,
        decision=decision,
        reasons=sorted(set(reasons)),
        required_receipts=sorted(set(receipts)),
        reduced_authority={
            "work_kind": request.work_kind.value,
            "risk_tier": request.risk_tier,
            "allowed_files": list(request.allowed_files),
            "forbidden_files": list(request.forbidden_files),
            "autonomy_level": request.autonomy_level,
        },
    )


__all__ = [
    "GovernedWorkAdmission",
    "GovernedWorkRequest",
    "WorkKind",
    "evaluate_governed_work_admission",
]
