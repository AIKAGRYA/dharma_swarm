"""Seed local Goodworks MRV ledger evidence.

The seed is deliberately modest. It records a pilot/readiness slice with
measured evidence and audit metadata, not an externally certified ecological
claim. That gives the dashboard and goal loop real ledger rows without
greenwashing the outcome.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from dharma_swarm.ai_reciprocity_ledger import (
    AIActor,
    AIReciprocityLedger,
    ActivityRecord,
    ActorType,
    AuditRecord,
    AuditScope,
    AuditStatus,
    ConfidenceLevel,
    ConsentStatus,
    DisclosureLevel,
    EvidenceRecord,
    EvidenceSubjectType,
    EvidenceType,
    ExposureClass,
    IntegrityClass,
    LivelihoodMode,
    LivelihoodRecord,
    ObligationBasis,
    ObligationRecord,
    ObligationStatus,
    ObligationType,
    OutcomeRecord,
    OutcomeStatus,
    OutcomeType,
    ProjectRecord,
    ProjectType,
    QuantityUnit,
    RoutingRecord,
)
from dharma_swarm.daemon_config import dharma_state_dir

SEED_ID = "goodworks_dgm_mrv_pilot_2026_05_21"


def seed_goodworks_mrv_pilot(ledger_root: Path | None = None) -> dict[str, Any]:
    root = ledger_root or dharma_state_dir()
    reciprocity = AIReciprocityLedger(data_dir=root / "ai_reciprocity_ledger")
    reciprocity.load()

    for project in reciprocity._projects.values():
        if project.metadata.get("seed_id") == SEED_ID:
            gaia, warnings = reciprocity.to_gaia_ledger(data_dir=root / "gaia_ledger")
            gaia.save()
            return {
                "created": False,
                "seed_id": SEED_ID,
                "reciprocity_entries": reciprocity.entry_count,
                "gaia_entries": gaia.entry_count,
                "warnings": warnings,
            }

    actor = AIActor(
        actor_name="Dharma Swarm Local Operator",
        actor_type=ActorType.RESEARCH_ORG,
        jurisdiction="US",
        disclosure_level=DisclosureLevel.FULL,
        metadata={"seed_id": SEED_ID, "source": "local_goodworks_dgm_seed"},
    )
    activity = ActivityRecord(
        actor_id=actor.actor_id,
        workload_label="goodworks-dgm-api-and-dashboard-wiring",
        period_start=date(2026, 5, 21),
        period_end=date(2026, 5, 21),
        exposure_class=ExposureClass.AUTOMATION_PROGRAM,
        energy_mwh=0.0,
        emissions_tco2e=0.0,
        methodology_ref="local-operator-time-and-repo-evidence-v1",
        confidence=ConfidenceLevel.MEDIUM,
        metadata={"seed_id": SEED_ID},
    )
    project = ProjectRecord(
        project_name="Goodworks DGM MRV Pilot Ledger",
        project_type=ProjectType.MIXED,
        location="local development environment",
        operator_name="Dharma Swarm",
        integrity_class=IntegrityClass.EMERGING,
        indigenous_or_local_consent=ConsentStatus.UNKNOWN,
        methodology_ref="pilot-readiness-v1",
        metadata={
            "seed_id": SEED_ID,
            "claim_boundary": "readiness evidence only; not an external carbon credit claim",
        },
    )
    obligation = ObligationRecord(
        activity_id=activity.activity_id,
        obligation_type=ObligationType.MIXED,
        obligation_basis=ObligationBasis.PILOT_RULE,
        obligation_quantity=1.0,
        obligation_unit=QuantityUnit.USD,
        status=ObligationStatus.ACTIVE,
        metadata={"seed_id": SEED_ID, "purpose": "bootstrap verifiable Goodworks loop"},
    )
    routing = RoutingRecord(
        obligation_id=obligation.obligation_id,
        project_id=project.project_id,
        routed_value=1.0,
        routed_unit=QuantityUnit.USD,
        restrictions="local pilot evidence only",
        metadata={"seed_id": SEED_ID},
    )
    livelihood = LivelihoodRecord(
        project_id=project.project_id,
        participant_count=1,
        livelihood_mode=LivelihoodMode.TRAINING,
        transition_target_group="operator-agent collaboration",
        person_hours=1.0,
        median_compensation_local=0.0,
        local_ownership_share=1.0,
        metadata={"seed_id": SEED_ID},
    )
    outcome = OutcomeRecord(
        project_id=project.project_id,
        outcome_type=OutcomeType.TRAINING,
        quantity=1.0,
        unit="readiness_receipt",
        status=OutcomeStatus.MEASURED,
        metadata={
            "seed_id": SEED_ID,
            "claim_boundary": "measured local system-readiness outcome",
        },
    )
    evidence = EvidenceRecord(
        subject_type=EvidenceSubjectType.OUTCOME,
        subject_id=outcome.outcome_id,
        evidence_type=EvidenceType.POLICY,
        source_ref="dharma_swarm/goodworks_dgm + api/routers/goodworks_dgm.py",
        verifier="local filesystem + tests",
        confidence=ConfidenceLevel.HIGH,
        metadata={"seed_id": SEED_ID},
    )
    audit = AuditRecord(
        scope=AuditScope.OUTCOME,
        scope_id=outcome.outcome_id,
        audit_status=AuditStatus.QUALIFIED,
        auditor="Dharma Swarm local test gate",
        notes_ref="tests/test_goodworks_dgm.py",
        metadata={
            "seed_id": SEED_ID,
            "qualification": "qualified because the seed is local readiness evidence, not third-party MRV",
        },
    )

    reciprocity.record_actor(actor)
    reciprocity.record_activity(activity)
    reciprocity.record_project(project)
    reciprocity.record_obligation(obligation)
    reciprocity.record_routing(routing)
    reciprocity.record_livelihood(livelihood)
    reciprocity.record_outcome(outcome)
    reciprocity.record_evidence(evidence)
    reciprocity.record_audit(audit)
    reciprocity.save()

    gaia, warnings = reciprocity.to_gaia_ledger(data_dir=root / "gaia_ledger")
    gaia.save()

    return {
        "created": True,
        "seed_id": SEED_ID,
        "reciprocity_entries": reciprocity.entry_count,
        "gaia_entries": gaia.entry_count,
        "warnings": warnings,
    }
