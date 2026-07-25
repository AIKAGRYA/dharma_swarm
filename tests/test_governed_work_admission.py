from __future__ import annotations

from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkRequest,
    WorkKind,
    evaluate_governed_work_admission,
)


def test_read_only_q1_allows_clean_scope():
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            request_id="read-only-q1",
            agent_uid="codex",
            work_kind=WorkKind.READ_ONLY,
            intent="inspect state",
            risk_tier="Q1",
        )
    )

    assert admission.decision == "allow"
    assert admission.request_id == "read-only-q1"
    assert admission.reasons == []


def test_code_write_without_contract_reviews():
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            agent_uid="codex",
            work_kind=WorkKind.CODE_WRITE,
            intent="patch file",
            risk_tier="Q2",
        )
    )

    assert admission.decision == "review"
    assert "mission_contract_missing" in admission.reasons
    assert "workspace_lease_missing" in admission.reasons
    assert "mission_contract_receipt" in admission.required_receipts


def test_q3_missing_context_quorum_blocks():
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            agent_uid="codex",
            work_kind=WorkKind.READ_ONLY,
            intent="inspect protected state",
            risk_tier="Q3",
            context_quorum_ok=False,
        )
    )

    assert admission.decision == "block"
    assert "context_quorum_missing_or_failed" in admission.reasons
    assert "context_quorum_receipt" in admission.required_receipts


def test_self_evolution_without_mutation_budget_blocks_even_with_contract():
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            agent_uid="codex",
            work_kind=WorkKind.SELF_EVOLUTION,
            intent="edit self",
            risk_tier="Q3",
            context_quorum_ok=True,
            mission_contract_present=True,
            workspace_lease_present=True,
            mutation_budget_remaining=0,
        )
    )

    assert admission.decision == "block"
    assert "mutation_budget_exhausted" in admission.reasons


def test_protected_file_hit_blocks():
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            agent_uid="codex",
            work_kind=WorkKind.CODE_WRITE,
            intent="patch protected file",
            risk_tier="Q3",
            context_quorum_ok=True,
            mission_contract_present=True,
            workspace_lease_present=True,
            protected_file_hits=["docs/governance/ACTIVE_TRACK.yaml"],
        )
    )

    assert admission.decision == "block"
    assert "protected_file_hits" in admission.reasons
    assert "protected_file_receipt" in admission.required_receipts


def test_promotion_always_requires_holdout_review():
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            agent_uid="forge_dgm",
            work_kind=WorkKind.PROMOTION,
            intent="promote scaffold",
            risk_tier="Q4",
            mission_contract_present=True,
            workspace_lease_present=True,
            mutation_budget_remaining=1,
        )
    )

    assert admission.decision == "review"
    assert "promotion_requires_holdout_receipt" in admission.reasons
    assert "holdout_eval_receipt" in admission.required_receipts


def test_promotion_caller_metadata_cannot_skip_review():
    for metadata in (
        {"holdout_eval_receipt": {"verified": True}},
        {"holdout_eval_receipt_verified": True},
        {"holdout_eval_receipt": {"verified": True}, "holdout_eval_receipt_verified": True},
    ):
        admission = evaluate_governed_work_admission(
            GovernedWorkRequest(
                agent_uid="forge_dgm",
                work_kind=WorkKind.PROMOTION,
                intent="promote scaffold",
                risk_tier="Q4",
                mission_contract_present=True,
                workspace_lease_present=True,
                mutation_budget_remaining=1,
                metadata=metadata,
            )
        )

        assert admission.decision == "review", (
            "caller-supplied metadata must never satisfy the promotion review gate"
        )
        assert "promotion_requires_holdout_receipt" in admission.reasons
