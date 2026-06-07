from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.revenue.action_gateway import CashClawActionGateway
from dharma_swarm.revenue.action_gateway_models import ActionCategory, CashClawActionRequest


def _request(category: ActionCategory, **kwargs) -> CashClawActionRequest:
    payload = {
        "action_id": "act-test",
        "agent_uid": "signal-scout",
        "employee_role": "cashclaw_signal_scout",
        "category": category,
        "intent": "test action",
        "payload": {"message": "draft only"},
        "evidence_refs": ["receipt://source"],
    }
    payload.update(kwargs)
    return CashClawActionRequest(**payload)


def test_observe_action_allowed_without_token() -> None:
    decision = CashClawActionGateway().evaluate(_request(ActionCategory.OBSERVE))

    assert decision.decision == "allow"
    assert decision.token_required is False
    assert "internal_no_side_effect_action" in decision.reasons


def test_internal_artifact_path_allowed_under_revenue_reports() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(
            ActionCategory.WRITE_INTERNAL_ARTIFACT,
            target_path="reports/revenue_wedge/cashclaw/packet.md",
        )
    )

    assert decision.decision == "allow"
    assert "internal_artifact_path_allowed" in decision.reasons


def test_sensitive_internal_artifact_path_blocked() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(
            ActionCategory.WRITE_INTERNAL_ARTIFACT,
            target_path="/Users/dhyana/.ssh/id_rsa",
        )
    )

    assert decision.decision == "block"
    assert "target_path_sensitive" in decision.reasons


@pytest.mark.parametrize(
    ("target_path", "reason"),
    [
        ("reports/revenue_wedge/../../.ssh/id_rsa", "target_path_traversal"),
        ("/reports/revenue_wedge/cashclaw/packet.md", "target_path_absolute"),
    ],
)
def test_internal_artifact_path_traversal_and_absolute_paths_blocked(target_path, reason) -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.WRITE_INTERNAL_ARTIFACT, target_path=target_path)
    )

    assert decision.decision == "block"
    assert decision.allowed_scope == []
    assert reason in decision.reasons


def test_human_approval_request_requires_passing_gauntlet() -> None:
    gateway = CashClawActionGateway()

    blocked = gateway.evaluate(
        _request(ActionCategory.REQUEST_HUMAN_APPROVAL, gauntlet_refs={"decision": "HOLD"})
    )
    review = gateway.evaluate(
        _request(ActionCategory.REQUEST_HUMAN_APPROVAL, gauntlet_refs={"decision": "PASS_TO_HUMAN"})
    )

    assert blocked.decision == "block"
    assert "gauntlet_not_pass_to_human" in blocked.reasons
    assert review.decision == "review"
    assert "operator_approval" in review.required_receipts


def test_payload_only_pass_to_human_does_not_spoof_gauntlet() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.REQUEST_HUMAN_APPROVAL, payload={"verdict": "PASS_TO_HUMAN"})
    )

    assert decision.decision == "block"
    assert "gauntlet_not_pass_to_human" in decision.reasons


@pytest.mark.parametrize(
    "risk_flag",
    [
        "payment_or_wallet_action",
        "auth_or_sensitive_security",
        "ai_disallowed_or_human_only",
        "security_or_bug_bounty",
        "non_cash_or_token_reward",
    ],
)
def test_human_approval_request_with_hard_risk_blocks(risk_flag: str) -> None:
    decision = CashClawActionGateway().evaluate(
        _request(
            ActionCategory.REQUEST_HUMAN_APPROVAL,
            gauntlet_refs={"decision": "PASS_TO_HUMAN"},
            risk_flags=[risk_flag],
        )
    )

    assert decision.decision == "block"
    assert decision.allowed_scope == []
    assert f"hard_risk:{risk_flag}" in decision.reasons
    assert "clean_risk_review" in decision.required_receipts


def test_human_approval_execution_receipt_preserves_review_hash() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.REQUEST_HUMAN_APPROVAL, gauntlet_refs={"decision": "PASS_TO_HUMAN"})

    decision = gateway.evaluate(req)
    receipt = gateway.execution_receipt(decision=decision, request=req)

    assert decision.decision == "review"
    assert receipt.decision == "review"
    assert receipt.applied is False
    assert receipt.external_side_effect is False
    assert receipt.payload_hash == req.payload_hash


def test_internal_action_claiming_external_side_effect_requires_review() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.ANALYZE, no_external_side_effects=False)
    )

    assert decision.decision == "review"
    assert "internal_action_claims_external_side_effect" in decision.reasons
    assert "side_effect_review" in decision.required_receipts


def test_internal_action_payload_suggesting_external_side_effect_requires_review() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.ANALYZE, payload={"next_step": "send the bid and accept payment"})
    )

    assert decision.decision == "review"
    assert "payload_suggests_external_side_effect" in decision.reasons
    assert "side_effect_review" in decision.required_receipts


def test_revenue_spine_mutation_decisions_separate_draft_from_external_state() -> None:
    gateway = CashClawActionGateway()

    draft = gateway.evaluate(
        _request(
            ActionCategory.MUTATE_REVENUE_SPINE,
            payload={"mutation": "draft_outreach", "status": "draft"},
        )
    )
    sent = gateway.evaluate(
        _request(
            ActionCategory.MUTATE_REVENUE_SPINE,
            payload={"mutation": "draft_outreach", "status": "sent", "external_side_effect": True},
        )
    )

    assert draft.decision == "allow"
    assert "revenue_spine_draft_only" in draft.reasons
    assert sent.decision == "review"
    assert "revenue_spine_human_approval" in sent.required_receipts


def test_external_communication_requires_exact_token() -> None:
    gateway = CashClawActionGateway()
    req = _request(
        ActionCategory.EXTERNAL_COMMUNICATION,
        no_external_side_effects=False,
        revenue_refs={"target_id": "tgt-1", "outreach_draft_id": "out-1"},
    )

    without_token = gateway.evaluate(req)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    with_token = gateway.evaluate(req, token=token)

    assert without_token.decision == "review"
    assert without_token.token_required is True
    assert "approval_token_missing" in without_token.reasons
    assert with_token.decision == "allow"
    assert "valid_approval_token" in with_token.reasons


def test_external_category_claiming_no_side_effect_blocks() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=True)
    )

    assert decision.decision == "block"
    assert "external_category_claims_no_side_effect" in decision.reasons
    assert "side_effect_category_correction" in decision.required_receipts


def test_hard_risk_external_communication_blocks_even_without_token() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(
            ActionCategory.EXTERNAL_COMMUNICATION,
            no_external_side_effects=False,
            risk_flags=["spam_or_bulk_outreach"],
        )
    )

    assert decision.decision == "block"
    assert decision.allowed_scope == []
    assert "hard_risk:spam_or_bulk_outreach" in decision.reasons
    assert "clean_risk_review" in decision.required_receipts


def test_hard_risk_external_token_mint_is_rejected() -> None:
    gateway = CashClawActionGateway()
    req = _request(
        ActionCategory.EXTERNAL_COMMUNICATION,
        no_external_side_effects=False,
        risk_flags=["payment_or_wallet_action"],
    )

    with pytest.raises(ValueError, match="cannot mint token for hard-risk action"):
        gateway.mint_token(
            req,
            approved_by="dhyana",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )


def test_token_payload_hash_mismatch_blocks_action() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    edited = _request(
        ActionCategory.EXTERNAL_COMMUNICATION,
        no_external_side_effects=False,
        payload={"message": "edited after approval"},
    )

    decision = gateway.evaluate(edited, token=token)

    assert decision.decision == "block"
    assert "approval_token_payload_hash_mismatch" in decision.reasons


@pytest.mark.parametrize(
    ("edited_kwargs", "reason"),
    [
        ({"action_id": "different-action"}, "approval_token_action_mismatch"),
        ({"agent_uid": "different-agent"}, "approval_token_agent_mismatch"),
        ({"category": ActionCategory.COMMERCIAL_COMMITMENT}, "approval_token_category_mismatch"),
    ],
)
def test_token_identity_mismatches_block_action(edited_kwargs, reason) -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    edited = req.model_copy(update=edited_kwargs)

    decision = gateway.evaluate(edited, token=token)

    assert decision.decision == "block"
    assert reason in decision.reasons


@pytest.mark.parametrize(
    ("token_update", "reason"),
    [
        ({"token_id": "catok_forged"}, "approval_token_id_mismatch"),
        ({"evidence_bundle_hash": "sha256:forged"}, "approval_token_evidence_bundle_mismatch"),
        ({"expires_at": ""}, "approval_token_missing_expiry"),
        ({"max_uses": 2}, "approval_token_not_single_use"),
        ({"approved_by": ""}, "approval_token_approver_missing"),
    ],
)
def test_token_metadata_tampering_blocks_action(token_update, reason) -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )

    decision = gateway.evaluate(req, token=token.model_copy(update=token_update))

    assert decision.decision == "block"
    assert reason in decision.reasons


def test_token_mint_requires_future_expiry() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)

    with pytest.raises(ValueError, match="approval_token_missing_expiry"):
        gateway.mint_token(req, approved_by="dhyana", expires_at="")


def test_token_consumption_prevents_reuse() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.COMMERCIAL_COMMITMENT, no_external_side_effects=False)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )

    consumed = gateway.consume_token(req, token)
    decision = gateway.evaluate(req, token=consumed)

    assert consumed.status == "consumed"
    assert decision.decision == "block"
    assert "approval_token_status:consumed" in decision.reasons


def test_credential_action_blocked_by_default() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.CREDENTIAL_OR_PRIVATE_DATA)
    )

    assert decision.decision == "block"
    assert "credential_or_private_data_blocked_by_default" in decision.reasons


def test_hard_risk_flag_blocks_non_review_action() -> None:
    decision = CashClawActionGateway().evaluate(
        _request(ActionCategory.ANALYZE, risk_flags=["payment_or_wallet_action"])
    )

    assert decision.decision == "block"
    assert "hard_risk:payment_or_wallet_action" in decision.reasons


def test_execution_receipt_defaults_to_no_external_effect_for_review_decision() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    decision = gateway.evaluate(req)

    receipt = gateway.execution_receipt(req, decision)

    assert decision.decision == "review"
    assert receipt.decision == "review"
    assert receipt.applied is False
    assert receipt.external_side_effect is False
    assert receipt.token_id == ""
    assert receipt.payload_hash == req.payload_hash


def test_execution_receipt_cannot_mark_review_or_block_applied() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    decision = gateway.evaluate(req)

    with pytest.raises(ValueError, match="cannot_apply_non_allow_decision"):
        gateway.execution_receipt(req, decision, applied=True)


def test_execution_receipt_rejects_mismatched_decision_payload() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    decision = gateway.evaluate(req)
    edited = _request(
        ActionCategory.EXTERNAL_COMMUNICATION,
        no_external_side_effects=False,
        payload={"message": "edited"},
    )

    with pytest.raises(ValueError, match="decision_request_payload_hash_mismatch"):
        gateway.execution_receipt(edited, decision)


def test_execution_receipt_requires_token_for_external_side_effect() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    decision = gateway.evaluate(req, token=token)

    with pytest.raises(ValueError, match="external_side_effect_requires_token"):
        gateway.execution_receipt(req, decision, applied=True, external_side_effect=True)


def test_consume_invalid_token_raises() -> None:
    gateway = CashClawActionGateway()
    req = _request(ActionCategory.EXTERNAL_COMMUNICATION, no_external_side_effects=False)
    token = gateway.mint_token(
        req,
        approved_by="dhyana",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    ).model_copy(
        update={"expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
    )

    with pytest.raises(ValueError, match="approval_token_expired"):
        gateway.consume_token(req, token, now=datetime.now(timezone.utc))
