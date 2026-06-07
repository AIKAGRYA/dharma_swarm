"""Models for CashClaw action gating.

The gateway separates an employee's ability to prepare work from authority to
touch the outside world. External effects require exact, single-use tokens.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ActionCategory(str, Enum):
    OBSERVE = "observe"
    ANALYZE = "analyze"
    DRAFT_INTERNAL = "draft_internal"
    WRITE_INTERNAL_ARTIFACT = "write_internal_artifact"
    MUTATE_REVENUE_SPINE = "mutate_revenue_spine"
    REQUEST_HUMAN_APPROVAL = "request_human_approval"
    EXTERNAL_COMMUNICATION = "external_communication"
    COMMERCIAL_COMMITMENT = "commercial_commitment"
    FINANCIAL_ACTION = "financial_action"
    CREDENTIAL_OR_PRIVATE_DATA = "credential_or_private_data"
    REGULATED_OR_HIGH_LIABILITY = "regulated_or_high_liability"
    RUNTIME_OR_CODE_MUTATION = "runtime_or_code_mutation"
    MEMORY_PROMOTION = "memory_promotion"


GatewayDecision = Literal["allow", "review", "block"]
TokenStatus = Literal["approved", "consumed", "denied", "expired", "revoked"]


class CashClawActionRequest(BaseModel):
    """One proposed action from a CashClaw employee."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cashclaw_action_request.v1"
    action_id: str
    agent_uid: str
    employee_role: str = ""
    category: ActionCategory
    intent: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    target_path: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    revenue_refs: dict[str, str] = Field(default_factory=dict)
    gauntlet_refs: dict[str, str] = Field(default_factory=dict)
    no_external_side_effects: bool = True
    created_at: str = Field(default_factory=utc_now_iso)

    @property
    def payload_hash(self) -> str:
        return canonical_hash(
            {
                "action_id": self.action_id,
                "agent_uid": self.agent_uid,
                "category": self.category.value,
                "intent": self.intent,
                "payload": self.payload,
                "target_path": self.target_path,
                "evidence_refs": self.evidence_refs,
                "risk_flags": self.risk_flags,
                "revenue_refs": self.revenue_refs,
                "gauntlet_refs": self.gauntlet_refs,
                "no_external_side_effects": self.no_external_side_effects,
            }
        )


class CashClawActionDecision(BaseModel):
    """Gateway decision for a proposed action."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cashclaw_gateway_decision.v1"
    decision_id: str
    action_id: str
    agent_uid: str
    category: ActionCategory
    decision: GatewayDecision
    reasons: list[str] = Field(default_factory=list)
    required_receipts: list[str] = Field(default_factory=list)
    allowed_scope: list[str] = Field(default_factory=list)
    token_required: bool = False
    payload_hash: str = ""
    created_at: str = Field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CashClawApprovalToken(BaseModel):
    """Exact approval token for one externally meaningful action."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cashclaw_approval_token.v1"
    token_id: str
    action_id: str
    agent_uid: str
    category: ActionCategory
    payload_hash: str
    approved_by: str
    approved_at: str = Field(default_factory=utc_now_iso)
    expires_at: str = ""
    max_uses: int = 1
    use_count: int = 0
    status: TokenStatus = "approved"
    gauntlet_evaluation_hash: str = ""
    revenue_target_id: str = ""
    outreach_draft_id: str = ""
    evidence_bundle_hash: str = ""

    @property
    def is_consumed(self) -> bool:
        return self.status == "consumed" or self.use_count >= self.max_uses

    @model_validator(mode="after")
    def _validate_token_invariants(self) -> "CashClawApprovalToken":
        if self.max_uses != 1:
            raise ValueError("approval token max_uses must be 1")
        if not self.expires_at.strip():
            raise ValueError("approval token expiry is required")
        return self


class CashClawExecutionReceipt(BaseModel):
    """Receipt for an action execution attempt."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = "cashclaw_action_executed.v1"
    receipt_id: str
    action_id: str
    agent_uid: str
    token_id: str = ""
    decision: GatewayDecision
    applied: bool = False
    external_side_effect: bool = False
    result_ref: str = ""
    reasons: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    payload_hash: str = ""

    @model_validator(mode="after")
    def _validate_execution_invariants(self) -> "CashClawExecutionReceipt":
        if self.applied and self.decision != "allow":
            raise ValueError("non-allow execution receipt cannot be applied")
        if self.external_side_effect and not self.applied:
            raise ValueError("external side effect requires applied receipt")
        if self.external_side_effect and not self.token_id:
            raise ValueError("external side effect requires token id")
        return self
