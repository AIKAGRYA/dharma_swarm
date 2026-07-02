from __future__ import annotations

import json

import pytest

from dharma_swarm.venture_cell import DomainCEOContractError, VentureCellRuntime
from dharma_swarm.venture_cell.external_actions import (
    ExternalActionKind,
    ExternalActionRequest,
    ExternalActionStatus,
)
from dharma_swarm.venture_cell.livelihood_loom import load_livelihood_loom_contract


def test_external_action_requires_idempotency_and_approval(tmp_path):
    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, tmp_path / "external_actions.jsonl")

    with pytest.raises(DomainCEOContractError, match="idempotency"):
        runtime.draft_external_action(
            ExternalActionRequest(
                cell_id=contract.cell_id,
                kind=ExternalActionKind.OUTREACH,
                title="Contact partner",
                requested_by="livelihood_loom_ceo",
            )
        )

    request = runtime.draft_external_action(
        ExternalActionRequest(
            cell_id=contract.cell_id,
            kind=ExternalActionKind.OUTREACH,
            title="Contact partner",
            requested_by="livelihood_loom_ceo",
            idempotency_key="contact-partner-1",
        )
    )
    assert request.status == ExternalActionStatus.DRAFTED
    with pytest.raises(DomainCEOContractError, match="before approval"):
        runtime.external_actions.execute(
            request.request_id,
            executor="agent",
            execution_receipt_id="rr_exec",
        )

    runtime.external_actions.risk_review(
        request.request_id,
        reviewer="worker_advocate",
        notes=["public partner contact only"],
    )
    runtime.external_actions.decide(
        request.request_id,
        decision="approved",
        decided_by=contract.human_governor,
        reason="safe partner outreach",
    )
    executed = runtime.external_actions.execute(
        request.request_id,
        executor="human_operator",
        execution_receipt_id="rr_exec",
    )
    assert executed.status == ExternalActionStatus.EXECUTED

    rows = [
        json.loads(line)
        for line in (tmp_path / "external_actions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event_type"] for row in rows] == [
        "drafted",
        "risk_reviewed",
        "approved",
        "executed",
    ]


def test_publication_payload_rejects_sensitive_fields(tmp_path):
    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, tmp_path / "external_actions.jsonl")
    with pytest.raises(DomainCEOContractError, match="sensitive"):
        runtime.draft_external_action(
            ExternalActionRequest(
                cell_id=contract.cell_id,
                kind=ExternalActionKind.PUBLICATION,
                title="Publish outcome",
                requested_by="livelihood_loom_ceo",
                idempotency_key="publish-1",
                payload={
                    "claim_id": "proof_1",
                    "cell_id": contract.cell_id,
                    "claim_type": "aggregate_outcome",
                    "aggregate_count": 4,
                    "sector": "food",
                    "region_level": "district",
                    "evidence_refs": [],
                    "audit_status": "audited",
                    "outcome_metric": "buyer_access",
                    "outcome_value": "3 new buyers",
                    "time_period": "2026-06",
                    "exact_location": "stall 12",
                },
            )
        )


def test_only_human_governor_can_approve(tmp_path):
    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, tmp_path / "external_actions.jsonl")
    request = runtime.draft_external_action(
        ExternalActionRequest(
            cell_id=contract.cell_id,
            kind=ExternalActionKind.PAYMENT,
            title="Draft stipend payout",
            requested_by="treasury_payout_guard",
            idempotency_key="payment-1",
        )
    )
    runtime.external_actions.risk_review(
        request.request_id,
        reviewer="worker_advocate",
        notes=["requires multisig"],
    )
    with pytest.raises(DomainCEOContractError, match="human_governor"):
        runtime.external_actions.decide(
            request.request_id,
            decision="approved",
            decided_by="agent",
            reason="agent cannot approve",
        )
