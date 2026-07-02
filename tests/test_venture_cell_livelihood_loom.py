from __future__ import annotations

import pytest

from dharma_swarm.venture_cell.livelihood_loom.adapters.eas_attestation_adapter import (
    build_eas_attestation_payload,
)
from dharma_swarm.venture_cell.livelihood_loom.adapters.enabler_csv_import import (
    load_enabler_csv,
)
from dharma_swarm.venture_cell.livelihood_loom.adapters.gaia_outcome_adapter import (
    outcome_to_gaia_record,
)
from dharma_swarm.venture_cell.livelihood_loom.adapters.safe_treasury_adapter import (
    build_safe_treasury_request,
)
from dharma_swarm.venture_cell.livelihood_loom.consent import (
    ConsentViolation,
    require_contact_consent,
    require_publish_consent,
)
from dharma_swarm.venture_cell.livelihood_loom.ontology import (
    ConsentLevel,
    ConsentReceipt,
    EnablerCompany,
    OutcomeClaim,
    PublicProofClaim,
    RiskClass,
    validate_public_payload,
)
from dharma_swarm.venture_cell.livelihood_loom.scoring import score_enabler
from dharma_swarm.venture_cell.workflow_plan import livelihood_pilot_workflow_spec


def test_consent_guards_contact_and_publish():
    internal = ConsentReceipt(
        subject_ref="business_1",
        level=ConsentLevel.INTERNAL_USE,
        source_ref="interview_note",
    )
    with pytest.raises(ConsentViolation):
        require_contact_consent(internal)
    publish = ConsentReceipt(
        subject_ref="business_1",
        level=ConsentLevel.PUBLISH_APPROVED,
        source_ref="signed_form",
    )
    require_publish_consent(publish)


def test_public_proof_claim_is_aggregate_and_non_sensitive():
    claim = PublicProofClaim(
        cell_id="livelihood_loom",
        claim_type="aggregate_outcome",
        aggregate_count=12,
        sector="food",
        region_level="district",
        evidence_refs=("rr_audit",),
        audit_status="audited",
        outcome_metric="buyer_access",
        outcome_value="5 buyer intros completed",
        time_period="2026-06",
    )
    payload = claim.to_public_payload()
    assert payload["aggregate_count"] == 12
    with pytest.raises(ValueError, match="aggregate"):
        validate_public_payload({**payload, "aggregate_count": 1})
    with pytest.raises(ValueError, match="sensitive"):
        validate_public_payload({**payload, "income": "$30/day"})


def test_scoring_flags_vulnerable_risk_for_review():
    company = EnablerCompany(
        name="Example Cooperative",
        sector="food",
        geography="Kenya",
        enablement_levers=("market_access",),
        source_refs=("public-directory",),
        risk_class=RiskClass.VULNERABLE_PERSON_RISK,
    )
    score = score_enabler(company)
    assert score.blocked is True
    assert "requires_human_safety_review" in score.reasons


def test_gaia_eas_and_safe_adapters_are_draft_or_public_safe():
    outcome = OutcomeClaim(
        subject_ref="cohort_1",
        outcome_metric="income_delta",
        outcome_value="positive",
        evidence_refs=("rr_measurement",),
        audit_status="audited",
    )
    gaia = outcome_to_gaia_record(outcome)
    assert gaia["schema"] == "gaia.livelihood_outcome.v1"

    proof = PublicProofClaim(
        cell_id="livelihood_loom",
        claim_type="aggregate_outcome",
        aggregate_count=9,
        sector="repair",
        region_level="city",
        evidence_refs=("rr_audit",),
        audit_status="audited",
        outcome_metric="time_saved",
        outcome_value="18 hours/week aggregate",
        time_period="2026-06",
    )
    eas = build_eas_attestation_payload(proof)
    assert eas["schema"] == "livelihood_loom.public_outcome.v1"
    assert eas["revocable"] is True

    treasury = build_safe_treasury_request(
        cell_id="livelihood_loom",
        token="USDC",
        amount="100.00",
        recipient_label="cohort_stipend_batch_1",
        purpose="approved pilot stipend",
        external_action_request_id="ext_1",
    )
    assert treasury["execution_mode"] == "draft_only_human_multisig_required"


def test_livelihood_workflow_side_effects_require_approval_and_idempotency():
    spec = livelihood_pilot_workflow_spec(
        mission_id="livelihood_loom_pilot_001",
        trace_id="trace_loom_1",
    )
    side_effecting = [activity for activity in spec.activities if activity.side_effecting]
    assert side_effecting
    assert all(activity.requires_approval for activity in side_effecting)
    assert all(activity.requires_idempotency_key for activity in side_effecting)


def test_enabler_csv_import_maps_public_rows(tmp_path):
    csv_path = tmp_path / "enablers.csv"
    csv_path.write_text(
        "name,sector,geography,enablement_levers,source_refs\n"
        "Example Pay,finance,Kenya,payments;credit,public-dir;report\n",
        encoding="utf-8",
    )
    rows = load_enabler_csv(csv_path)
    assert len(rows) == 1
    assert rows[0].name == "Example Pay"
    assert rows[0].enablement_levers == ("payments", "credit")
    assert rows[0].source_refs == ("public-dir", "report")
