"""Tests for typed ontology proposal envelopes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.typed_proposal_envelope import (
    ActionProposal,
    LinkProposal,
    ObjectTypeProposal,
    OntologyProposalEnvelope,
    ProposalProvenance,
    PromoteStatusProposal,
    TypeStatus,
)


def _provenance() -> ProposalProvenance:
    return ProposalProvenance(
        agent="perplexity-computer",
        callsign="perplexity",
        branch="test/schema-proposal",
        rationale="test proposal",
    )


def test_object_type_proposal_accepts_no_version_api_name() -> None:
    proposal = ObjectTypeProposal(
        name="AuditFinding",
        api_name="dharma.findings.AuditFinding",
        description="Finding emitted by an audit pass",
        provenance=_provenance(),
    )

    assert proposal.api_name == "dharma.findings.AuditFinding"
    assert proposal.status == TypeStatus.EXPERIMENTAL


def test_object_type_proposal_rejects_version_suffix() -> None:
    with pytest.raises(ValidationError, match="must match dharma"):
        ObjectTypeProposal(
            name="AuditFinding",
            api_name="dharma.findings.AuditFinding.v1",
            description="Finding emitted by an audit pass",
            provenance=_provenance(),
        )


def test_object_type_proposal_rejects_type_name_mismatch() -> None:
    with pytest.raises(ValidationError, match="must match name"):
        ObjectTypeProposal(
            name="AuditFinding",
            api_name="dharma.findings.OtherFinding",
            description="Finding emitted by an audit pass",
            provenance=_provenance(),
        )


def test_object_type_proposal_rejects_promoted_status() -> None:
    with pytest.raises(ValidationError, match="cannot propose PROMOTED"):
        ObjectTypeProposal(
            name="AuditFinding",
            api_name="dharma.findings.AuditFinding",
            status=TypeStatus.PROMOTED,
            description="Finding emitted by an audit pass",
            provenance=_provenance(),
        )


def test_promote_status_proposal_requires_operator_blessing() -> None:
    with pytest.raises(ValidationError, match="Only operator"):
        PromoteStatusProposal(
            target_api_name="dharma.findings.AuditFinding",
            new_status=TypeStatus.PROMOTED,
            blessed_by="perplexity-computer",
            provenance=_provenance(),
        )


def test_envelope_round_trips_proposal_union() -> None:
    envelope = OntologyProposalEnvelope(
        envelope_id="test-envelope",
        proposal=LinkProposal(
            name="findings",
            source_type="AuditRun",
            target_type="AuditFinding",
            provenance=_provenance(),
        ),
    )

    loaded = OntologyProposalEnvelope.model_validate_json(envelope.model_dump_json())

    assert isinstance(loaded.proposal, LinkProposal)


def test_action_proposal_union_accepts_effect_summary() -> None:
    envelope = OntologyProposalEnvelope(
        envelope_id="test-action-envelope",
        proposal=ActionProposal(
            name="Approve",
            object_type="ActionProposal",
            effect_summary="Moves a proposal to approved.",
            provenance=_provenance(),
        ),
    )

    assert isinstance(envelope.proposal, ActionProposal)
