"""Tests for typed ontology proposal envelopes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.typed_proposal_envelope import (
    ObjectTypeProposal,
    ProposalProvenance,
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
