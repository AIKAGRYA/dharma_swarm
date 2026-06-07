"""CashClaw action gateway.

This module is intentionally pure: it evaluates action requests and approval
tokens, but does not send messages, bid on jobs, spend money, or mutate any
external system.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.revenue.action_gateway_models import (
    ActionCategory,
    CashClawActionDecision,
    CashClawActionRequest,
    CashClawApprovalToken,
    CashClawExecutionReceipt,
    canonical_hash,
    utc_now_iso,
)


PASS_TO_HUMAN = "PASS_TO_HUMAN"

ALLOW_CATEGORIES = {
    ActionCategory.OBSERVE,
    ActionCategory.ANALYZE,
    ActionCategory.DRAFT_INTERNAL,
}
TOKEN_REQUIRED_CATEGORIES = {
    ActionCategory.EXTERNAL_COMMUNICATION,
    ActionCategory.COMMERCIAL_COMMITMENT,
    ActionCategory.FINANCIAL_ACTION,
}
BLOCK_BY_DEFAULT_CATEGORIES = {
    ActionCategory.CREDENTIAL_OR_PRIVATE_DATA,
    ActionCategory.REGULATED_OR_HIGH_LIABILITY,
}
INTERNAL_ARTIFACT_PREFIXES = (
    "reports/revenue_wedge/",
    ".dharma/cashclaw_fleet/",
    ".dharma/cashclaw_gateway/",
)
FORBIDDEN_PATH_FRAGMENTS = (
    "/.ssh/",
    "/.env",
    "/secrets",
    "id_rsa",
    "private_key",
)
HARD_BLOCK_RISK_FLAGS = {
    "regulated_advice",
    "tos_conflict",
    "secret_or_pii",
    "spam_or_bulk_outreach",
    "guaranteed_revenue",
    "requires_signup_or_credentials",
    "payment_or_wallet_action",
    "auth_or_sensitive_security",
    "ai_disallowed_or_human_only",
    "security_or_bug_bounty",
    "non_cash_or_token_reward",
}
SIDE_EFFECT_INTENT_KEYWORDS = (
    "send ",
    "auto-send",
    "submit",
    "accept job",
    "accept payment",
    "charge card",
    "wallet",
    "transfer",
    "bid ",
    "commit",
    "publish",
)


class CashClawActionGateway:
    """Evaluate CashClaw employee actions against revenue governance."""

    def __init__(
        self,
        *,
        allowed_internal_prefixes: tuple[str, ...] = INTERNAL_ARTIFACT_PREFIXES,
    ) -> None:
        self.allowed_internal_prefixes = allowed_internal_prefixes

    def evaluate(
        self,
        request: CashClawActionRequest | dict[str, Any],
        *,
        token: CashClawApprovalToken | dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> CashClawActionDecision:
        req = request if isinstance(request, CashClawActionRequest) else CashClawActionRequest(**request)
        tok = token if isinstance(token, CashClawApprovalToken) or token is None else CashClawApprovalToken(**token)
        reasons: list[str] = []
        required: list[str] = []
        allowed_scope: list[str] = []
        token_required = False
        decision = "allow"

        hard_flags = sorted(set(req.risk_flags).intersection(HARD_BLOCK_RISK_FLAGS))
        if req.category in BLOCK_BY_DEFAULT_CATEGORIES:
            decision = "block"
            reasons.append(f"{req.category.value}_blocked_by_default")
            required.append("human_break_glass_review")

        if hard_flags:
            if decision != "block":
                decision = "block"
            reasons.extend(f"hard_risk:{flag}" for flag in hard_flags)
            required.append("clean_risk_review")

        if req.category in ALLOW_CATEGORIES:
            allowed_scope.append(req.category.value)
            if req.no_external_side_effects is not True:
                decision = "review"
                reasons.append("internal_action_claims_external_side_effect")
                required.append("side_effect_review")
            elif _payload_suggests_external_side_effect(req):
                decision = "review"
                reasons.append("payload_suggests_external_side_effect")
                required.append("side_effect_review")
            elif not reasons:
                reasons.append("internal_no_side_effect_action")

        elif req.category == ActionCategory.WRITE_INTERNAL_ARTIFACT:
            path_decision, path_reasons = self._evaluate_internal_path(req.target_path)
            reasons.extend(path_reasons)
            if path_decision == "allow":
                allowed_scope.append(req.target_path)
            elif path_decision == "review" and decision != "block":
                decision = "review"
                required.append("path_scope_review")
            else:
                decision = "block"
                required.append("path_scope_clearance")

        elif req.category == ActionCategory.MUTATE_REVENUE_SPINE:
            if _spine_mutation_is_draft_only(req.payload):
                decision = "allow" if decision != "block" else decision
                allowed_scope.append("revenue_spine:draft_only")
                reasons.append("revenue_spine_draft_only")
            elif decision != "block":
                decision = "review"
                reasons.append("revenue_spine_external_state_transition")
                required.append("revenue_spine_human_approval")

        elif req.category == ActionCategory.REQUEST_HUMAN_APPROVAL:
            if _gauntlet_passed(req):
                if decision != "block":
                    decision = "review"
                reasons.append("gauntlet_pass_to_human")
                required.append("operator_approval")
            else:
                decision = "block"
                reasons.append("gauntlet_not_pass_to_human")
                required.append("passing_gauntlet_evaluation")

        elif req.category in TOKEN_REQUIRED_CATEGORIES:
            token_required = True
            if req.no_external_side_effects is True:
                decision = "block"
                reasons.append("external_category_claims_no_side_effect")
                required.append("side_effect_category_correction")
            else:
                token_error = self.validate_token(req, tok, now=now)
                if token_error:
                    if decision != "block":
                        decision = "review" if tok is None else "block"
                    reasons.append(token_error)
                    required.append("valid_single_use_approval_token")
                else:
                    if decision != "block":
                        decision = "allow"
                        allowed_scope.append(req.category.value)
                    reasons.append("valid_approval_token")

        elif req.category == ActionCategory.RUNTIME_OR_CODE_MUTATION:
            if decision != "block":
                decision = "review"
            reasons.append("route_to_governed_work_admission")
            required.append("governed_work_admission")

        elif req.category == ActionCategory.MEMORY_PROMOTION:
            if decision != "block":
                decision = "review"
            reasons.append("memory_promotion_requires_provenance_review")
            required.append("memory_provenance_receipt")

        if not reasons:
            reasons.append("unclassified_action_review")
            decision = "review"

        if hard_flags:
            decision = "block"
            allowed_scope = []
            if "clean_risk_review" not in required:
                required.append("clean_risk_review")

        if decision == "block":
            allowed_scope = []

        return CashClawActionDecision(
            decision_id=f"cagd_{canonical_hash([req.action_id, req.payload_hash, reasons])[-16:]}",
            action_id=req.action_id,
            agent_uid=req.agent_uid,
            category=req.category,
            decision=decision,  # type: ignore[arg-type]
            reasons=sorted(set(reasons)),
            required_receipts=sorted(set(required)),
            allowed_scope=allowed_scope,
            token_required=token_required,
            payload_hash=req.payload_hash,
            metadata={
                "employee_role": req.employee_role,
                "risk_flags": list(req.risk_flags),
                "gauntlet_refs": dict(req.gauntlet_refs),
                "revenue_refs": dict(req.revenue_refs),
            },
        )

    def mint_token(
        self,
        request: CashClawActionRequest,
        *,
        approved_by: str,
        expires_at: str,
        gauntlet_evaluation_hash: str = "",
    ) -> CashClawApprovalToken:
        """Mint an exact single-use token for a reviewable action."""

        if not approved_by.strip():
            raise ValueError("approved_by is required")
        if request.category not in TOKEN_REQUIRED_CATEGORIES:
            raise ValueError(f"token not required for category {request.category.value}")
        hard_flags = sorted(set(request.risk_flags).intersection(HARD_BLOCK_RISK_FLAGS))
        if hard_flags:
            raise ValueError(f"cannot mint token for hard-risk action: {', '.join(hard_flags)}")
        expiry_error = _approval_expiry_error(expires_at)
        if expiry_error:
            raise ValueError(expiry_error)
        evidence_hash = _evidence_bundle_hash(request)
        return CashClawApprovalToken(
            token_id=_approval_token_id(request, approved_by),
            action_id=request.action_id,
            agent_uid=request.agent_uid,
            category=request.category,
            payload_hash=request.payload_hash,
            approved_by=approved_by,
            expires_at=expires_at,
            gauntlet_evaluation_hash=gauntlet_evaluation_hash,
            revenue_target_id=request.revenue_refs.get("target_id", ""),
            outreach_draft_id=request.revenue_refs.get("outreach_draft_id", ""),
            evidence_bundle_hash=evidence_hash,
        )

    def validate_token(
        self,
        request: CashClawActionRequest,
        token: CashClawApprovalToken | None,
        *,
        now: datetime | None = None,
    ) -> str:
        """Return empty string if token authorizes this request; else reason."""

        if token is None:
            return "approval_token_missing"
        if not token.approved_by.strip():
            return "approval_token_approver_missing"
        if token.max_uses != 1:
            return "approval_token_not_single_use"
        if token.status != "approved":
            return f"approval_token_status:{token.status}"
        if token.is_consumed:
            return "approval_token_consumed"
        if token.action_id != request.action_id:
            return "approval_token_action_mismatch"
        if token.agent_uid != request.agent_uid:
            return "approval_token_agent_mismatch"
        if token.category != request.category:
            return "approval_token_category_mismatch"
        if token.payload_hash != request.payload_hash:
            return "approval_token_payload_hash_mismatch"
        if token.evidence_bundle_hash != _evidence_bundle_hash(request):
            return "approval_token_evidence_bundle_mismatch"
        if token.revenue_target_id != request.revenue_refs.get("target_id", ""):
            return "approval_token_target_mismatch"
        if token.outreach_draft_id != request.revenue_refs.get("outreach_draft_id", ""):
            return "approval_token_outreach_draft_mismatch"
        if token.token_id != _approval_token_id(request, token.approved_by):
            return "approval_token_id_mismatch"
        expiry_error = _approval_expiry_error(token.expires_at, now=now)
        if expiry_error:
            return expiry_error
        return ""

    def consume_token(
        self,
        request: CashClawActionRequest,
        token: CashClawApprovalToken,
        *,
        now: datetime | None = None,
    ) -> CashClawApprovalToken:
        """Return a consumed token copy after validating exact request match."""

        error = self.validate_token(request, token, now=now)
        if error:
            raise ValueError(error)
        updated = token.model_copy()
        updated.use_count += 1
        if updated.use_count >= updated.max_uses:
            updated.status = "consumed"
        return updated

    def execution_receipt(
        self,
        request: CashClawActionRequest,
        decision: CashClawActionDecision,
        *,
        token: CashClawApprovalToken | None = None,
        applied: bool = False,
        external_side_effect: bool = False,
        result_ref: str = "",
    ) -> CashClawExecutionReceipt:
        """Build an execution receipt object without applying side effects."""

        if decision.action_id != request.action_id or decision.agent_uid != request.agent_uid:
            raise ValueError("decision_request_identity_mismatch")
        if decision.category != request.category:
            raise ValueError("decision_request_category_mismatch")
        if decision.payload_hash != request.payload_hash:
            raise ValueError("decision_request_payload_hash_mismatch")
        if token is not None:
            token_error = self.validate_token(request, token)
            if token_error:
                raise ValueError(f"receipt_token_invalid:{token_error}")
        if applied and decision.decision != "allow":
            raise ValueError("cannot_apply_non_allow_decision")
        if external_side_effect and not applied:
            raise ValueError("external_side_effect_requires_applied")
        if external_side_effect and token is None:
            raise ValueError("external_side_effect_requires_token")
        if external_side_effect and request.category not in TOKEN_REQUIRED_CATEGORIES:
            raise ValueError("external_side_effect_invalid_category")

        return CashClawExecutionReceipt(
            receipt_id=f"caexec_{canonical_hash([request.action_id, decision.decision_id, result_ref])[-24:]}",
            action_id=request.action_id,
            agent_uid=request.agent_uid,
            token_id=token.token_id if token else "",
            decision=decision.decision,
            applied=applied,
            external_side_effect=external_side_effect,
            result_ref=result_ref,
            reasons=list(decision.reasons),
            payload_hash=request.payload_hash,
        )

    def append_jsonl(self, path: Path, payload: Any) -> None:
        """Append a model/dict payload to JSONL for audit tests and adapters."""

        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(payload, "model_dump"):
            row = payload.model_dump(mode="json")
        else:
            row = payload
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True, default=str) + "\n")

    def _evaluate_internal_path(self, target_path: str) -> tuple[str, list[str]]:
        path = str(target_path or "").strip()
        if not path:
            return "review", ["target_path_missing"]
        block_reasons: list[str] = []
        if Path(path).is_absolute():
            block_reasons.append("target_path_absolute")
        lowered = path.lower()
        if any(fragment in lowered for fragment in FORBIDDEN_PATH_FRAGMENTS):
            block_reasons.append("target_path_sensitive")
        normalized = path.replace("\\", "/").lstrip("/")
        if ".." in normalized.split("/"):
            block_reasons.append("target_path_traversal")
        if block_reasons:
            return "block", block_reasons
        if normalized.startswith(self.allowed_internal_prefixes):
            return "allow", ["internal_artifact_path_allowed"]
        return "review", ["internal_artifact_path_outside_default_scope"]


def _gauntlet_passed(request: CashClawActionRequest) -> bool:
    decision = request.gauntlet_refs.get("decision") or ""
    return str(decision).strip().upper() == PASS_TO_HUMAN


def _payload_suggests_external_side_effect(request: CashClawActionRequest) -> bool:
    watched_fields = (
        "action",
        "next_action",
        "next_step",
        "command",
        "operation",
        "message",
        "draft_message",
    )
    payload_text = " ".join(str(request.payload.get(field, "")) for field in watched_fields)
    text = f"{request.intent} {payload_text}".lower()
    return any(keyword in text for keyword in SIDE_EFFECT_INTENT_KEYWORDS)


def _spine_mutation_is_draft_only(payload: dict[str, Any]) -> bool:
    mutation = str(payload.get("mutation") or payload.get("operation") or "").strip().lower()
    status = str(payload.get("status") or "").strip().lower()
    external = bool(payload.get("external_side_effect"))
    return (
        not external
        and mutation in {"add_target", "qualify_target", "draft_outreach", "register_offer"}
        and status not in {"approved", "sent", "paid", "engaged"}
    )


def _evidence_bundle_hash(request: CashClawActionRequest) -> str:
    return canonical_hash(
        {
            "evidence_refs": request.evidence_refs,
            "gauntlet_refs": request.gauntlet_refs,
            "revenue_refs": request.revenue_refs,
        }
    )


def _approval_token_id(request: CashClawActionRequest, approved_by: str) -> str:
    return f"catok_{canonical_hash([request.action_id, request.payload_hash, approved_by])[-24:]}"


def _approval_expiry_error(expires_at: str, *, now: datetime | None = None) -> str:
    if not str(expires_at or "").strip():
        return "approval_token_missing_expiry"
    check_at = now or datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return "approval_token_bad_expiry"
    if parsed.tzinfo is None:
        return "approval_token_bad_expiry"
    if check_at > parsed:
        return "approval_token_expired"
    return ""


def write_gateway_receipt(path: Path, payload: Any) -> None:
    """Write one gateway receipt as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"gateway receipt already exists: {path}")
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    data.setdefault("written_at", utc_now_iso())
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
