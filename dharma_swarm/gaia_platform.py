"""GAIA platform surface for recommendation, pilot staging, and CLI rendering.

This module composes the tracked GAIA core into a small shipped operator surface:
- assess ecological restoration projects against Aptavani-aligned gates
- rank approved projects for a given model/operator profile
- stage an auditable pilot ledger using the existing GAIA runtime
- render a terminal dashboard that can be documented and run directly
"""

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from dharma_swarm.ai_reciprocity_ledger import (
    AIActor,
    AIReciprocityLedger,
    ActivityRecord,
    ActorType as ReciprocityActorType,
    AuditRecord,
    AuditScope,
    AuditStatus as ReciprocityAuditStatus,
    ConfidenceLevel as ReciprocityConfidenceLevel,
    ConsentStatus as ReciprocityConsentStatus,
    DisclosureLevel as ReciprocityDisclosureLevel,
    EvidenceRecord,
    EvidenceSubjectType,
    EvidenceType,
    ExposureClass as ReciprocityExposureClass,
    IntegrityClass as ReciprocityIntegrityClass,
    LivelihoodMode as ReciprocityLivelihoodMode,
    LivelihoodRecord,
    ObligationBasis as ReciprocityObligationBasis,
    ObligationRecord,
    ObligationStatus as ReciprocityObligationStatus,
    ObligationType as ReciprocityObligationType,
    OutcomeRecord,
    OutcomeStatus as ReciprocityOutcomeStatus,
    OutcomeType as ReciprocityOutcomeType,
    ProjectRecord,
    ProjectType as ReciprocityProjectType,
    QuantityUnit as ReciprocityQuantityUnit,
    RoutingRecord,
)
from dharma_swarm.archive import FitnessScore
from dharma_swarm.gaia_fitness import ECOLOGICAL_HARM_WORDS, EcologicalFitness
from dharma_swarm.gaia_ledger import (
    ComputeUnit,
    FundingUnit,
    GaiaLedger,
    LaborUnit,
    OffsetUnit,
)
from dharma_swarm.gaia_verification import ORACLE_TYPES, OracleVerdict, verify_offset

if TYPE_CHECKING:
    from dharma_swarm.gaia_initiative import GaiaInitiativePilotPacket


GAIA_PRINCIPLES: tuple[str, ...] = (
    "anekanta",
    "ahimsa",
    "satya",
    "jagat_kalyan",
)


class GaiaProject(BaseModel):
    """A concrete restoration project candidate for GAIA matching."""

    project_id: str
    name: str
    project_type: str
    country: str
    region: str
    hectares: float
    carbon_potential_tons_yr: float
    labor_needed: int
    funding_gap_usd: float
    verification_status: str
    community_partner: str
    description: str
    verification_channels: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def is_verified(self) -> bool:
        return self.verification_status.lower() == "verified"


class GaiaStrategy(BaseModel):
    """Assessment output grounded in GAIA's dharmic/ecological gates."""

    approved: bool
    principles: tuple[str, ...] = GAIA_PRINCIPLES
    warnings: list[str] = Field(default_factory=list)
    rationale: str = ""


class GaiaRecommendation(BaseModel):
    """Ranked recommendation for one operator/model profile."""

    project: GaiaProject
    strategy: GaiaStrategy
    welfare_tons: float
    match_score: float
    verification_bonus: float
    community_bonus: float


class GaiaMonitoringSnapshot(BaseModel):
    """One auditable checkpoint in a staged restoration pilot."""

    label: str
    day: int
    vegetation_cover_pct: float
    soil_carbon_index: float
    steward_hours: float
    community_participants: int
    survival_rate_pct: float
    notes: str


class GaiaUserFeedback(BaseModel):
    """Structured user feedback captured during pilot review."""

    actor_id: str
    role: str
    satisfaction: float = Field(ge=0.0, le=5.0)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    requested_follow_up: str = ""


class GaiaMeasurementMode(str, Enum):
    """How the compute activity was sourced for the pilot packet."""

    MEASURED = "measured"
    ESTIMATED = "estimated"
    DISCLOSED = "disclosed"


class GaiaPartnerCredibility(str, Enum):
    """Qualification state for the named community partner."""

    CREDIBLE = "credible"
    PROVISIONAL = "provisional"
    UNKNOWN = "unknown"


class GaiaClaimVisibility(str, Enum):
    """How far a pilot claim is allowed to travel."""

    PUBLIC_READY = "public_ready"
    PROVISIONAL = "provisional"
    INTERNAL_ONLY = "internal_only"


class GaiaClaimType(str, Enum):
    """Public claim-card classification."""

    ACTIVITY = "activity"
    OUTPUT = "output"
    OUTCOME = "outcome"
    LIVELIHOOD = "livelihood"
    MIXED = "mixed"


class GaiaChallengeGround(str, Enum):
    """Valid grounds for challenging a public claim."""

    FACTUAL_ERROR = "factual_error"
    MISLEADING_SCOPE_OR_WORDING = "misleading_scope_or_wording"
    MISSING_EVIDENCE_PATH = "missing_evidence_path"
    AUDIT_CONFLICT_OF_INTEREST = "audit_conflict_of_interest"
    CONSENT_DISPUTE = "consent_dispute"
    GRIEVANCE_OR_HARM = "grievance_or_harm"
    CONSERVATION_VIOLATION = "conservation_violation"
    ECOLOGICAL_REVERSAL = "ecological_reversal"
    FABRICATED_OR_UNVERIFIABLE_EVIDENCE = "fabricated_or_unverifiable_evidence"


class GaiaChallengeState(str, Enum):
    """Workflow states for a public claim challenge."""

    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    NEEDS_EVIDENCE = "needs_evidence"
    OPEN_REVIEW = "open_review"
    MATERIAL_CHALLENGE = "material_challenge"
    DISMISSED = "dismissed"
    UPHELD = "upheld"
    RESOLVED = "resolved"
    APPEAL_OPEN = "appeal_open"


class GaiaRemediationOutcome(str, Enum):
    """Explicit remediation outcomes for upheld or material challenges."""

    CLARIFICATION = "clarification"
    NUMERICAL_CORRECTION = "numerical_correction"
    METHODOLOGY_CORRECTION = "methodology_correction"
    INTEGRITY_DOWNGRADE = "integrity_downgrade"
    CLAIM_FREEZE = "claim_freeze"
    CLAIM_WITHDRAWAL = "claim_withdrawal"
    CLAIM_REISSUE = "claim_reissue"


class GaiaRemediationStep(str, Enum):
    """Current step of a remediation case."""

    CASE_OPENED = "case_opened"
    OWNER_ASSIGNED = "owner_assigned"
    CONTAINMENT = "containment"
    REPAIR_PLAN = "repair_plan"
    VERIFICATION = "verification"
    DECISION = "decision"
    HISTORICAL_APPEND = "historical_append"


class GaiaGrievanceStatus(str, Enum):
    """Public grievance state shown on a claim card."""

    NONE = "none"
    OPEN = "open"
    MATERIAL = "material"
    RESOLVED = "resolved"


class GaiaReversalStatus(str, Enum):
    """Public reversal state shown on a claim card."""

    NONE = "none"
    WATCH = "watch"
    PARTIAL_REVERSAL = "partial_reversal"
    FULL_REVERSAL = "full_reversal"


class GaiaPilotIntake(BaseModel):
    """Structured intake packet for one bounded GAIA pilot."""

    model_id: str
    sponsor_name: str
    sponsor_jurisdiction: str = "unknown"
    sponsor_actor_type: ReciprocityActorType = ReciprocityActorType.LAB
    sponsor_disclosure_level: ReciprocityDisclosureLevel = (
        ReciprocityDisclosureLevel.PARTIAL
    )
    reporting_period: str
    project: GaiaProject
    measurement_mode: GaiaMeasurementMode
    energy_mwh: float = Field(gt=0.0)
    carbon_intensity: float = Field(ge=0.0)
    methodology_ref: str
    measurement_ref: str
    obligation_rule: str
    project_operator: str
    integrity_class: str
    partner_credibility: GaiaPartnerCredibility = GaiaPartnerCredibility.UNKNOWN
    due_diligence_ref: str = ""
    consent_status: str = "unknown"
    consent_ref: str = ""
    benefit_sharing_ref: str = ""
    grievance_process_ref: str = ""
    challenge_contact: str = ""
    measurement_verifier: str = ""
    measurement_boundary_ref: str = ""
    ecosystem_type: str = ""
    boundary_ref: str = ""
    planned_activities: tuple[str, ...] = Field(default_factory=tuple)
    standards_profile: tuple[str, ...] = Field(default_factory=tuple)
    monitoring_indicators: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    observation_protocols: tuple[str, ...] = Field(default_factory=tuple)
    metering_evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    metering_audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    livelihood_target_group: str
    livelihood_mode: ReciprocityLivelihoodMode = ReciprocityLivelihoodMode.MIXED
    livelihood_participant_count: int | None = Field(default=None, ge=0)
    livelihood_person_hours: float | None = Field(default=None, ge=0.0)
    median_compensation_local: float | None = Field(default=None, ge=0.0)
    local_ownership_share: float | None = Field(default=None, ge=0.0, le=1.0)
    outcome_type: ReciprocityOutcomeType = ReciprocityOutcomeType.CARBON
    outcome_unit: str = "tco2e"
    auditor_name: str = "Independent Audit Lane"
    audit_status: ReciprocityAuditStatus = ReciprocityAuditStatus.PASSED
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    verification_channels: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator(
        "model_id",
        "sponsor_name",
        "sponsor_jurisdiction",
        "reporting_period",
        "methodology_ref",
        "measurement_ref",
        "obligation_rule",
        "project_operator",
        "integrity_class",
        "livelihood_target_group",
        "outcome_unit",
        "auditor_name",
    )
    @classmethod
    def non_blank_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required intake fields must not be blank")
        return cleaned

    @field_validator(
        "due_diligence_ref",
        "consent_status",
        "consent_ref",
        "benefit_sharing_ref",
        "grievance_process_ref",
        "challenge_contact",
        "measurement_verifier",
        "measurement_boundary_ref",
        "ecosystem_type",
        "boundary_ref",
    )
    @classmethod
    def strip_optional_text_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "evidence_refs",
        "audit_refs",
        "verification_channels",
        "planned_activities",
        "standards_profile",
        "observation_protocols",
        "metering_evidence_refs",
        "metering_audit_refs",
    )
    @classmethod
    def strip_string_tuples(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.strip() for value in values if value.strip())

    @property
    def declared_verification_channels(self) -> tuple[str, ...]:
        return (
            self.verification_channels
            if self.verification_channels
            else self.project.verification_channels
        )


class GaiaQualificationDecision(BaseModel):
    """Explicit approval state for a pilot intake packet."""

    approved: bool
    visibility: GaiaClaimVisibility
    integrity_class: str
    challenge_status: str
    verification_channels: tuple[str, ...]
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    public_claim_ready: bool = False
    measurement_claim_ready: bool = False
    rationale: str = ""


class GaiaClaimCard(BaseModel):
    """Challengeable public claim surface for a qualified pilot."""

    claim_id: str
    visibility: GaiaClaimVisibility
    claim_statement: str
    claim_type: GaiaClaimType = GaiaClaimType.MIXED
    claim_scope: str
    challenge_status: str
    challenge_contact: str
    sponsor_name: str
    model_id: str
    reporting_period: str
    project_id: str
    project_name: str
    project_operator: str
    community_partner: str
    integrity_class: str
    methodology_ref: str
    audit_status: ReciprocityAuditStatus
    measurement_mode: GaiaMeasurementMode
    measurement_ref: str
    measurement_verifier: str = ""
    measurement_boundary_ref: str = ""
    metering_evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    metering_audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    measurement_claim_ready: bool = False
    measurement_packet_path: str
    obligation_rule: str
    benefit_sharing_ref: str
    grievance_process_ref: str
    consent_status: str
    consent_ref: str
    due_diligence_ref: str
    grievance_status: GaiaGrievanceStatus = GaiaGrievanceStatus.NONE
    reversal_status: GaiaReversalStatus = GaiaReversalStatus.NONE
    ecosystem_type: str = ""
    boundary_ref: str = ""
    standards_profile: tuple[str, ...] = Field(default_factory=tuple)
    observation_protocols: tuple[str, ...] = Field(default_factory=tuple)
    planned_activity_count: int = 0
    monitoring_indicator_count: int = 0
    livelihood_target_group: str
    evidence_refs: tuple[str, ...]
    audit_refs: tuple[str, ...]
    verification_channels: tuple[str, ...]
    final_confidence: float = Field(ge=0.0, le=1.0)
    agreeing_oracles: tuple[str, ...] = Field(default_factory=tuple)
    dissenting_oracles: tuple[str, ...] = Field(default_factory=tuple)
    total_verified_offset: float
    net_carbon_position: float
    ledger_path: str
    reciprocity_ledger_path: str
    report_path: str
    obligation_quantity_usd: float
    routed_value_usd: float
    livelihood_participant_count: int
    livelihood_mode: ReciprocityLivelihoodMode
    livelihood_person_hours: float
    median_compensation_local: float | None = Field(default=None, ge=0.0)
    local_ownership_share: float | None = Field(default=None, ge=0.0, le=1.0)
    livelihood_feedback_count: int = 0
    livelihood_feedback_roles: tuple[str, ...] = Field(default_factory=tuple)
    livelihood_packet_path: str
    challenge_packet_path: str
    promotional_use_frozen: bool = False
    challenge_count: int = 0
    unresolved_challenge_count: int = 0
    material_challenge_count: int = 0
    remediation_case_count: int = 0
    reciprocity_invariant_issues: int = 0
    reciprocity_projection_warnings: tuple[str, ...] = Field(default_factory=tuple)
    public_notes: tuple[str, ...] = Field(default_factory=tuple)
    last_reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    monitoring_status: str
    remediation_status: str
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class GaiaMeasurementPacket(BaseModel):
    """Sponsor-side compute measurement packet for one GAIA claim."""

    sponsor_name: str
    model_id: str
    reporting_period: str
    measurement_mode: GaiaMeasurementMode
    measurement_ref: str
    measurement_verifier: str = ""
    measurement_boundary_ref: str = ""
    energy_mwh: float = Field(gt=0.0)
    carbon_intensity: float = Field(ge=0.0)
    emissions_tco2e: float = Field(ge=0.0)
    metering_evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    metering_audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    public_claim_ready: bool = False
    warnings: list[str] = Field(default_factory=list)


class GaiaLivelihoodPacket(BaseModel):
    """Auditable worker-transition packet bound to one GAIA claim."""

    sponsor_name: str
    model_id: str
    reporting_period: str
    visibility: GaiaClaimVisibility
    challenge_status: str
    project_id: str
    project_name: str
    project_operator: str
    community_partner: str
    livelihood_target_group: str
    livelihood_mode: ReciprocityLivelihoodMode
    participant_count: int = Field(ge=0)
    person_hours: float = Field(ge=0.0)
    median_compensation_local: float | None = Field(default=None, ge=0.0)
    local_ownership_share: float | None = Field(default=None, ge=0.0, le=1.0)
    partner_credibility: GaiaPartnerCredibility
    due_diligence_ref: str
    consent_status: str
    consent_ref: str
    benefit_sharing_ref: str
    grievance_process_ref: str
    challenge_contact: str
    feedback_response_count: int = Field(default=0, ge=0)
    feedback_roles: tuple[str, ...] = Field(default_factory=tuple)
    feedback_average_satisfaction: float = Field(default=0.0, ge=0.0, le=5.0)
    feedback_average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    top_follow_up: str = ""
    linked_evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    linked_audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    verification_channels: tuple[str, ...] = Field(default_factory=tuple)
    reciprocity_ledger_path: str
    report_path: str


class GaiaChallengeRecord(BaseModel):
    """A typed public challenge against one claim card."""

    challenge_id: str = Field(default_factory=lambda: _new_record_id("challenge"))
    raised_by: str
    role: str
    summary: str
    ground: GaiaChallengeGround
    state: GaiaChallengeState = GaiaChallengeState.SUBMITTED
    evidence_ref: str = ""
    requested_action: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("raised_by", "role", "summary", "evidence_ref", "requested_action")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        return value.strip()


class GaiaRemediationCase(BaseModel):
    """A typed remediation case linked to one or more challenges."""

    case_id: str = Field(default_factory=lambda: _new_record_id("remediation"))
    owner: str
    summary: str
    outcome: GaiaRemediationOutcome
    step: GaiaRemediationStep = GaiaRemediationStep.CASE_OPENED
    linked_challenge_ids: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    decision_ref: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("owner", "summary", "decision_ref")
    @classmethod
    def strip_case_text_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("linked_challenge_ids", "evidence_refs")
    @classmethod
    def strip_case_tuple_fields(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.strip() for value in values if value.strip())


class GaiaChallengePacket(BaseModel):
    """Public challenge/remediation packet bound to one claim card."""

    claim_id: str
    visibility: GaiaClaimVisibility
    challenge_status: str
    audit_status: ReciprocityAuditStatus
    challenge_contact: str
    grievance_process_ref: str
    consent_status: str
    grievance_status: GaiaGrievanceStatus
    reversal_status: GaiaReversalStatus
    freeze_promotional_use: bool = False
    challenge_count: int = 0
    unresolved_challenge_count: int = 0
    material_challenge_count: int = 0
    resolved_challenge_count: int = 0
    remediation_case_count: int = 0
    public_notes: tuple[str, ...] = Field(default_factory=tuple)
    challenge_records: tuple[GaiaChallengeRecord, ...] = Field(default_factory=tuple)
    remediation_cases: tuple[GaiaRemediationCase, ...] = Field(default_factory=tuple)
    next_acknowledge_due_at: datetime | None = None
    next_triage_due_at: datetime | None = None
    next_initial_finding_due_at: datetime | None = None
    service_level_notes: tuple[str, ...] = Field(default_factory=tuple)
    report_path: str
    claim_card_path: str
    last_reviewed_at: datetime = Field(default_factory=datetime.utcnow)


class GaiaClaimExplorerEntry(BaseModel):
    """One row in the static public-claim explorer index."""

    claim_id: str
    visibility: GaiaClaimVisibility
    sponsor_name: str
    project_name: str
    claim_statement: str
    integrity_class: str
    challenge_status: str
    promotional_use_frozen: bool = False
    challenge_count: int = 0
    material_challenge_count: int = 0
    audit_status: ReciprocityAuditStatus
    grievance_status: GaiaGrievanceStatus
    reversal_status: GaiaReversalStatus
    total_verified_offset: float
    final_confidence: float = Field(ge=0.0, le=1.0)
    last_reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    claim_card_path: str
    challenge_packet_path: str


class GaiaClaimExplorer(BaseModel):
    """Static export of the current public-claim surface."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    claim_count: int
    public_ready_count: int
    provisional_count: int
    challenged_count: int
    entries: tuple[GaiaClaimExplorerEntry, ...] = Field(default_factory=tuple)


class GaiaPlatform:
    """High-level GAIA operator surface over the tracked core runtime."""

    def __init__(
        self,
        data_dir: Path | None = None,
        projects: Sequence[GaiaProject] | None = None,
    ) -> None:
        self._data_dir = data_dir or (Path.home() / ".dharma" / "gaia_platform")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._projects = list(projects) if projects is not None else self._default_projects()

    def assess_project(self, project: GaiaProject) -> GaiaStrategy:
        """Run a small Aptavani-aligned gate over one project."""
        warnings: list[str] = []
        corpus = " ".join(
            (
                project.project_type,
                project.description,
                project.name,
                project.region,
                project.community_partner,
            )
        ).lower()

        matched_harm = next(
            (
                phrase
                for phrase in sorted(ECOLOGICAL_HARM_WORDS | {"monoculture"})
                if phrase in corpus
            ),
            None,
        )
        if matched_harm:
            warnings.append(
                "AHIMSA: project indicates ecological harm risk "
                f"through '{matched_harm}'."
            )

        if not project.is_verified:
            warnings.append(
                "SATYA: project is not verified; GAIA will not stage it as an "
                "approved pilot."
            )

        if not self._has_viable_partner(project.community_partner):
            warnings.append(
                "JAGAT_KALYAN: community partner is missing or not yet credible."
            )

        if len({_normalize_channel(channel) for channel in project.verification_channels}) < 3:
            warnings.append(
                "ANEKANTA: fewer than three distinct verification channels are available."
            )

        approved = not any(
            warning.startswith(("AHIMSA", "SATYA", "JAGAT_KALYAN"))
            for warning in warnings
        )
        rationale = (
            "Project clears harm, verification, and community reciprocity checks."
            if approved
            else "Project requires remediation before GAIA can recommend it."
        )
        return GaiaStrategy(approved=approved, warnings=warnings, rationale=rationale)

    def recommend_projects(
        self,
        model_id: str,
        top_n: int = 3,
    ) -> list[GaiaRecommendation]:
        """Return approved projects ordered by model/operator fit."""
        recommendations: list[GaiaRecommendation] = []
        for project in self._projects:
            strategy = self.assess_project(project)
            if not strategy.approved:
                continue

            welfare_tons = round(self._estimate_welfare_tons(project), 2)
            verification_bonus = self._verification_multiplier(project)
            community_bonus = self._community_multiplier(project)
            match_score = round(
                welfare_tons
                * self._model_affinity(model_id, project)
                / max(project.funding_gap_usd / 100_000.0, 1.0),
                2,
            )
            recommendations.append(
                GaiaRecommendation(
                    project=project,
                    strategy=strategy,
                    welfare_tons=welfare_tons,
                    match_score=match_score,
                    verification_bonus=verification_bonus,
                    community_bonus=community_bonus,
                )
            )

        recommendations.sort(
            key=lambda item: (
                item.project.verification_status != "verified",
                -item.match_score,
                -item.welfare_tons,
            )
        )
        return recommendations[: max(top_n, 0)]

    def stage_pilot(
        self,
        model_id: str,
        energy_mwh: float,
        carbon_intensity: float,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a single auditable pilot chain from compute to verified offset."""
        recommendation = self._pick_recommendation(
            model_id=model_id,
            project_id=project_id,
        )
        return self._stage_recommendation(
            recommendation=recommendation,
            model_id=model_id,
            energy_mwh=energy_mwh,
            carbon_intensity=carbon_intensity,
        )

    def build_pilot_report(
        self,
        model_id: str,
        project_id: str | None = None,
        energy_mwh: float = 12.0,
        carbon_intensity: float = 0.35,
        feedback_entries: Sequence[GaiaUserFeedback | dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Stage a pilot and export auditable monitoring plus feedback artifacts."""
        staged = self.stage_pilot(
            model_id=model_id,
            project_id=project_id,
            energy_mwh=energy_mwh,
            carbon_intensity=carbon_intensity,
        )
        report = self._assemble_report_payload(
            staged=staged,
            model_id=model_id,
            feedback_entries=feedback_entries,
        )

        json_path = staged["report_path"]
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path = json_path.with_suffix(".md")
        markdown_path.write_text(
            self._render_pilot_report_markdown(report),
            encoding="utf-8",
        )

        return {
            **staged,
            "json_path": json_path,
            "markdown_path": markdown_path,
            "report": report,
        }

    def qualify_intake(self, intake: GaiaPilotIntake) -> GaiaQualificationDecision:
        """Apply explicit intake gates before a pilot can become a public claim."""
        strategy = self.assess_project(intake.project)
        warnings = list(strategy.warnings)
        blockers: list[str] = []
        channels = tuple(
            sorted(
                {
                    _normalize_channel(channel)
                    for channel in intake.declared_verification_channels
                    if channel.strip()
                }
            )
        )

        if intake.partner_credibility is not GaiaPartnerCredibility.CREDIBLE:
            blockers.append(
                "JAGAT_KALYAN: community partner diligence is not yet credible."
            )
        if not intake.due_diligence_ref.strip():
            blockers.append(
                "JAGAT_KALYAN: partner due diligence reference is missing."
            )
        if intake.consent_status.strip().lower() not in {"documented", "verified", "granted"}:
            blockers.append(
                "CONSENT: local or indigenous consent is not yet documented."
            )
        if not intake.consent_ref.strip():
            blockers.append("CONSENT: consent reference is missing.")
        if not intake.benefit_sharing_ref.strip():
            blockers.append(
                "JAGAT_KALYAN: benefit-sharing reference is missing."
            )
        if not intake.grievance_process_ref.strip():
            blockers.append(
                "SATYA: grievance process reference is missing."
            )
        if len(channels) < 3:
            blockers.append(
                "ANEKANTA: fewer than three distinct verification channels are documented."
            )
        if not intake.challenge_contact.strip():
            blockers.append("SATYA: challenge contact is missing.")
        declared_standards = {
            _normalize_standard_name(standard)
            for standard in intake.standards_profile
            if standard.strip()
        }
        declared_protocols = {
            _normalize_standard_name(protocol)
            for protocol in intake.observation_protocols
            if protocol.strip()
        }
        if declared_standards:
            if "ferm" not in declared_standards:
                warnings.append(
                    "STANDARDS: initiative is standards-backed but does not declare FERM."
                )
            if not intake.boundary_ref:
                blockers.append(
                    "STANDARDS: boundary reference is missing for a standards-aligned initiative."
                )
            if not intake.ecosystem_type:
                blockers.append(
                    "STANDARDS: ecosystem type is missing for a standards-aligned initiative."
                )
            if not intake.monitoring_indicators:
                blockers.append(
                    "STANDARDS: monitoring indicators are missing for a standards-aligned initiative."
                )
            if not declared_protocols:
                blockers.append(
                    "STANDARDS: observation protocols are missing for a standards-aligned initiative."
                )
            missing_declared_protocols = [
                standard
                for standard in sorted(declared_standards)
                if standard in {"sensorthings", "stac", "darwin_core"}
                and standard not in declared_protocols
            ]
            if missing_declared_protocols:
                warnings.append(
                    "STANDARDS: declared protocols lack matching observation sources: "
                    + ", ".join(missing_declared_protocols)
                )

        measurement_claim_ready = False
        if intake.measurement_mode is GaiaMeasurementMode.ESTIMATED:
            warnings.append(
                "MEASUREMENT: compute source is estimated; claim remains provisional."
            )
        elif intake.measurement_mode is GaiaMeasurementMode.DISCLOSED:
            warnings.append(
                "MEASUREMENT: compute source is operator-disclosed; public claims require metered evidence."
            )
        else:
            if not intake.measurement_verifier.strip():
                blockers.append(
                    "MEASUREMENT: measured compute packets require a named measurement verifier."
                )
            if not intake.measurement_boundary_ref.strip():
                blockers.append(
                    "MEASUREMENT: measured compute packets require a measurement boundary reference."
                )
            if not intake.metering_evidence_refs:
                blockers.append(
                    "MEASUREMENT: measured compute packets require metering evidence references."
                )
            if not intake.metering_audit_refs:
                warnings.append(
                    "MEASUREMENT: metered compute lacks audit references; claim remains provisional."
                )
            measurement_claim_ready = (
                bool(intake.measurement_verifier.strip())
                and bool(intake.measurement_boundary_ref.strip())
                and bool(intake.metering_evidence_refs)
                and bool(intake.metering_audit_refs)
            )

        if not intake.evidence_refs:
            warnings.append(
                "SATYA: evidence references are missing; claim cannot be public-ready."
            )
        if not intake.audit_refs:
            warnings.append(
                "SATYA: audit references are missing; claim cannot be public-ready."
            )

        approved = strategy.approved and not blockers
        public_claim_ready = (
            approved
            and intake.project.is_verified
            and bool(intake.evidence_refs)
            and bool(intake.audit_refs)
            and measurement_claim_ready
        )
        visibility = GaiaClaimVisibility.INTERNAL_ONLY
        if public_claim_ready:
            visibility = GaiaClaimVisibility.PUBLIC_READY
        elif approved:
            visibility = GaiaClaimVisibility.PROVISIONAL

        rationale = (
            "Intake clears measurement, partner, consent, and challengeability gates."
            if approved
            else "Intake is blocked until the listed governance or integrity gaps are resolved."
        )
        return GaiaQualificationDecision(
            approved=approved,
            visibility=visibility,
            integrity_class=intake.integrity_class,
            challenge_status=(
                "open" if intake.challenge_contact.strip() else "unavailable"
            ),
            verification_channels=channels,
            warnings=warnings,
            blockers=blockers,
            public_claim_ready=public_claim_ready,
            measurement_claim_ready=measurement_claim_ready,
            rationale=rationale,
        )

    def build_intake_pilot_report(
        self,
        intake: GaiaPilotIntake,
        feedback_entries: Sequence[GaiaUserFeedback | dict[str, Any]] | None = None,
        initiative_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a qualified pilot packet from a structured intake contract."""
        qualification = self.qualify_intake(intake)
        if not qualification.approved:
            raise ValueError(
                "GAIA intake is not approved: "
                + "; ".join(qualification.blockers)
            )

        recommendation = self._recommendation_for_project(
            model_id=intake.model_id,
            project=intake.project,
        )
        staged = self._stage_recommendation(
            recommendation=recommendation,
            model_id=intake.model_id,
            energy_mwh=intake.energy_mwh,
            carbon_intensity=intake.carbon_intensity,
        )
        report = self._assemble_report_payload(
            staged=staged,
            model_id=intake.model_id,
            feedback_entries=feedback_entries,
        )
        reciprocity = self._build_reciprocity_packet(
            intake=intake,
            qualification=qualification,
            staged=staged,
            report=report,
        )
        report["reciprocity"] = {
            "ledger_path": str(reciprocity["ledger_path"]),
            "projection_path": str(reciprocity["projection_path"]),
            "summary": reciprocity["summary"],
            "projection_summary": reciprocity["projection_summary"],
            "projection_warnings": reciprocity["projection_warnings"],
            "activity_id": reciprocity["activity_id"],
            "obligation_id": reciprocity["obligation_id"],
            "routing_id": reciprocity["routing_id"],
            "outcome_id": reciprocity["outcome_id"],
            "outcome_status": reciprocity["outcome_status"],
            "livelihood": reciprocity["livelihood"],
        }
        livelihood_packet = self._build_livelihood_packet(
            intake=intake,
            qualification=qualification,
            report=report,
            reciprocity=reciprocity,
        )
        challenge_packet = self._build_challenge_packet(
            intake=intake,
            qualification=qualification,
            report=report,
        )
        claim_card = self._build_claim_card(
            intake=intake,
            qualification=qualification,
            report=report,
            challenge_packet=challenge_packet,
        )
        measurement_packet = self._build_measurement_packet(
            intake=intake,
            qualification=qualification,
        )
        claim_explorer = self._update_claim_explorer(claim_card)
        report["intake"] = intake.model_dump(mode="json")
        report["qualification"] = qualification.model_dump(mode="json")
        report["livelihood"] = livelihood_packet.model_dump(mode="json")
        report["challenge"] = {
            **challenge_packet.model_dump(mode="json"),
            "packet_path": str(Path(report["ledger_path"]).with_name("challenge_packet.json")),
        }
        report["claim_card"] = claim_card.model_dump(mode="json")
        report["measurement"] = measurement_packet.model_dump(mode="json")
        report["claim_explorer"] = claim_explorer["explorer"].model_dump(mode="json")
        rendered_initiative_summary = (
            initiative_summary
            if initiative_summary is not None
            else self._initiative_summary_from_intake(intake)
        )
        if rendered_initiative_summary is not None:
            report["initiative"] = rendered_initiative_summary

        json_path = staged["report_path"]
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path = json_path.with_suffix(".md")
        markdown_path.write_text(
            self._render_pilot_report_markdown(report),
            encoding="utf-8",
        )

        intake_path = json_path.with_name("pilot_intake.json")
        intake_path.write_text(
            json.dumps(intake.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        qualification_path = json_path.with_name("qualification.json")
        qualification_path.write_text(
            json.dumps(qualification.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        claim_card_path = json_path.with_name("claim_card.json")
        claim_card_path.write_text(
            json.dumps(claim_card.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        claim_card_markdown_path = claim_card_path.with_suffix(".md")
        claim_card_markdown_path.write_text(
            self._render_claim_card_markdown(claim_card),
            encoding="utf-8",
        )
        measurement_path = json_path.with_name("measurement_packet.json")
        measurement_path.write_text(
            json.dumps(measurement_packet.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        measurement_markdown_path = measurement_path.with_suffix(".md")
        measurement_markdown_path.write_text(
            self._render_measurement_packet_markdown(measurement_packet),
            encoding="utf-8",
        )
        livelihood_path = json_path.with_name("livelihood_packet.json")
        livelihood_path.write_text(
            json.dumps(livelihood_packet.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        livelihood_markdown_path = livelihood_path.with_suffix(".md")
        livelihood_markdown_path.write_text(
            self._render_livelihood_packet_markdown(livelihood_packet),
            encoding="utf-8",
        )
        challenge_path = json_path.with_name("challenge_packet.json")
        challenge_path.write_text(
            json.dumps(challenge_packet.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        challenge_markdown_path = challenge_path.with_suffix(".md")
        challenge_markdown_path.write_text(
            self._render_challenge_packet_markdown(challenge_packet),
            encoding="utf-8",
        )

        return {
            **staged,
            "json_path": json_path,
            "markdown_path": markdown_path,
            "report": report,
            "reciprocity_path": reciprocity["ledger_path"],
            "reciprocity_projection_path": reciprocity["projection_path"],
            "intake": intake,
            "intake_path": intake_path,
            "qualification": qualification,
            "qualification_path": qualification_path,
            "claim_card": claim_card,
            "claim_card_path": claim_card_path,
            "claim_card_markdown_path": claim_card_markdown_path,
            "measurement_packet": measurement_packet,
            "measurement_path": measurement_path,
            "measurement_markdown_path": measurement_markdown_path,
            "livelihood_packet": livelihood_packet,
            "livelihood_path": livelihood_path,
            "livelihood_markdown_path": livelihood_markdown_path,
            "challenge_packet": challenge_packet,
            "challenge_path": challenge_path,
            "challenge_markdown_path": challenge_markdown_path,
            "claim_explorer": claim_explorer["explorer"],
            "claim_explorer_path": claim_explorer["json_path"],
            "claim_explorer_markdown_path": claim_explorer["markdown_path"],
        }

    def build_initiative_pilot_report(
        self,
        packet: GaiaInitiativePilotPacket,
        feedback_entries: Sequence[GaiaUserFeedback | dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Promote a standards-aligned initiative packet into the shipped pilot flow."""
        result = self.build_intake_pilot_report(
            intake=packet.to_pilot_intake(),
            feedback_entries=feedback_entries,
            initiative_summary=packet.initiative_summary(),
        )
        initiative_packet_path = result["json_path"].with_name("initiative_packet.json")
        initiative_packet_path.write_text(
            json.dumps(packet.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        result["initiative_packet"] = packet
        result["initiative_packet_path"] = initiative_packet_path
        return result

    def submit_claim_challenge(
        self,
        *,
        claim_card_path: Path,
        challenge: GaiaChallengeRecord | dict[str, Any],
    ) -> dict[str, Any]:
        """Append one typed public challenge and refresh all GAIA governance artifacts."""
        bundle = self._load_claim_governance_bundle(claim_card_path)
        challenge_record = (
            challenge
            if isinstance(challenge, GaiaChallengeRecord)
            else GaiaChallengeRecord.model_validate(challenge)
        )
        challenge_packet = bundle["challenge_packet"].model_copy(
            update={
                "challenge_records": (
                    *bundle["challenge_packet"].challenge_records,
                    challenge_record,
                )
            }
        )
        return self._persist_claim_governance_bundle(
            claim_card_path=claim_card_path,
            claim_card=bundle["claim_card"],
            challenge_packet=challenge_packet,
            livelihood_packet=bundle["livelihood_packet"],
            report=bundle["report"],
        )

    def apply_claim_remediation(
        self,
        *,
        claim_card_path: Path,
        remediation: GaiaRemediationCase | dict[str, Any],
    ) -> dict[str, Any]:
        """Append one typed remediation case and refresh all GAIA governance artifacts."""
        bundle = self._load_claim_governance_bundle(claim_card_path)
        remediation_case = (
            remediation
            if isinstance(remediation, GaiaRemediationCase)
            else GaiaRemediationCase.model_validate(remediation)
        )
        challenge_records = list(bundle["challenge_packet"].challenge_records)
        if remediation_case.linked_challenge_ids:
            for index, record in enumerate(challenge_records):
                if record.challenge_id not in remediation_case.linked_challenge_ids:
                    continue
                if record.state in {
                    GaiaChallengeState.DISMISSED,
                    GaiaChallengeState.RESOLVED,
                }:
                    continue
                if remediation_case.step is GaiaRemediationStep.DECISION:
                    challenge_records[index] = record.model_copy(
                        update={"state": GaiaChallengeState.UPHELD}
                    )
                elif remediation_case.step is GaiaRemediationStep.HISTORICAL_APPEND:
                    challenge_records[index] = record.model_copy(
                        update={"state": GaiaChallengeState.RESOLVED}
                    )
        challenge_packet = bundle["challenge_packet"].model_copy(
            update={
                "challenge_records": tuple(challenge_records),
                "remediation_cases": (
                    *bundle["challenge_packet"].remediation_cases,
                    remediation_case,
                ),
            }
        )
        return self._persist_claim_governance_bundle(
            claim_card_path=claim_card_path,
            claim_card=bundle["claim_card"],
            challenge_packet=challenge_packet,
            livelihood_packet=bundle["livelihood_packet"],
            report=bundle["report"],
        )

    def _load_claim_governance_bundle(
        self,
        claim_card_path: Path,
    ) -> dict[str, Any]:
        claim_card = GaiaClaimCard.model_validate_json(
            claim_card_path.read_text(encoding="utf-8")
        )
        challenge_packet = GaiaChallengePacket.model_validate_json(
            Path(claim_card.challenge_packet_path).read_text(encoding="utf-8")
        )
        livelihood_packet = GaiaLivelihoodPacket.model_validate_json(
            Path(claim_card.livelihood_packet_path).read_text(encoding="utf-8")
        )
        report_path = Path(claim_card.report_path)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return {
            "claim_card": claim_card,
            "challenge_packet": challenge_packet,
            "livelihood_packet": livelihood_packet,
            "report": report,
        }

    def _persist_claim_governance_bundle(
        self,
        *,
        claim_card_path: Path,
        claim_card: GaiaClaimCard,
        challenge_packet: GaiaChallengePacket,
        livelihood_packet: GaiaLivelihoodPacket,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        governance = self._reconcile_claim_governance(
            claim_card=claim_card,
            challenge_packet=challenge_packet,
            livelihood_packet=livelihood_packet,
            report=report,
        )
        claim_card = governance["claim_card"]
        challenge_packet = governance["challenge_packet"]
        livelihood_packet = governance["livelihood_packet"]
        report = governance["report"]

        report["claim_card"] = claim_card.model_dump(mode="json")
        report["challenge"] = {
            **challenge_packet.model_dump(mode="json"),
            "packet_path": str(Path(claim_card.challenge_packet_path)),
        }
        report["livelihood"] = livelihood_packet.model_dump(mode="json")
        claim_explorer = self._update_claim_explorer(claim_card)
        report["claim_explorer"] = claim_explorer["explorer"].model_dump(mode="json")

        report_path = Path(claim_card.report_path)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        report_path.with_suffix(".md").write_text(
            self._render_pilot_report_markdown(report),
            encoding="utf-8",
        )
        claim_card_path.write_text(
            json.dumps(claim_card.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        claim_card_path.with_suffix(".md").write_text(
            self._render_claim_card_markdown(claim_card),
            encoding="utf-8",
        )
        challenge_path = Path(claim_card.challenge_packet_path)
        challenge_path.write_text(
            json.dumps(
                challenge_packet.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        challenge_path.with_suffix(".md").write_text(
            self._render_challenge_packet_markdown(challenge_packet),
            encoding="utf-8",
        )
        livelihood_path = Path(claim_card.livelihood_packet_path)
        livelihood_path.write_text(
            json.dumps(
                livelihood_packet.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        livelihood_path.with_suffix(".md").write_text(
            self._render_livelihood_packet_markdown(livelihood_packet),
            encoding="utf-8",
        )
        return {
            "claim_card": claim_card,
            "claim_card_path": claim_card_path,
            "challenge_packet": challenge_packet,
            "challenge_path": challenge_path,
            "livelihood_packet": livelihood_packet,
            "livelihood_path": livelihood_path,
            "json_path": report_path,
            "markdown_path": report_path.with_suffix(".md"),
            "claim_explorer": claim_explorer["explorer"],
            "claim_explorer_path": claim_explorer["json_path"],
            "claim_explorer_markdown_path": claim_explorer["markdown_path"],
            "report": report,
        }

    def _reconcile_claim_governance(
        self,
        *,
        claim_card: GaiaClaimCard,
        challenge_packet: GaiaChallengePacket,
        livelihood_packet: GaiaLivelihoodPacket,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        challenge_records = tuple(challenge_packet.challenge_records)
        remediation_cases = tuple(challenge_packet.remediation_cases)
        now = datetime.utcnow()
        challenge_status = self._summarize_challenge_status(challenge_records)
        challenge_count = len(challenge_records)
        unresolved_challenge_count = sum(
            1
            for record in challenge_records
            if record.state
            not in {GaiaChallengeState.DISMISSED, GaiaChallengeState.RESOLVED}
        )
        material_challenge_count = sum(
            1
            for record in challenge_records
            if record.state
            in {
                GaiaChallengeState.MATERIAL_CHALLENGE,
                GaiaChallengeState.UPHELD,
                GaiaChallengeState.APPEAL_OPEN,
            }
        )
        resolved_challenge_count = sum(
            1 for record in challenge_records if record.state is GaiaChallengeState.RESOLVED
        )
        grievance_status = self._summarize_grievance_status(challenge_records)
        reversal_status = self._summarize_reversal_status(challenge_records)
        audit_status = self._summarize_audit_status(
            claim_card.audit_status,
            challenge_records,
        )
        freeze_promotional_use = self._should_freeze_promotional_use(
            challenge_records=challenge_records,
            remediation_cases=remediation_cases,
            grievance_status=grievance_status,
            reversal_status=reversal_status,
            audit_status=audit_status,
        )
        visibility = self._governed_claim_visibility(
            claim_card=claim_card,
            audit_status=audit_status,
            freeze_promotional_use=freeze_promotional_use,
        )
        integrity_class = self._governed_integrity_class(
            integrity_class=claim_card.integrity_class,
            challenge_records=challenge_records,
            remediation_cases=remediation_cases,
        )
        service_levels = self._challenge_service_levels(challenge_records, now)
        remediation_status = self._summarize_remediation_status(
            remediation_cases=remediation_cases,
            freeze_promotional_use=freeze_promotional_use,
            existing_status=claim_card.remediation_status,
        )
        public_notes = self._merge_governance_public_notes(
            challenge_packet.public_notes,
            challenge_status=challenge_status,
            freeze_promotional_use=freeze_promotional_use,
            grievance_status=grievance_status,
            reversal_status=reversal_status,
            service_level_notes=service_levels["notes"],
            challenge_count=challenge_count,
            remediation_status=remediation_status,
        )
        last_reviewed_at = max(
            (
                now,
                challenge_packet.last_reviewed_at,
                *(record.created_at for record in challenge_records),
                *(case.created_at for case in remediation_cases),
            ),
        )
        claim_statement = self._compose_governed_claim_statement(
            report=report,
            claim_card=claim_card,
            visibility=visibility,
            freeze_promotional_use=freeze_promotional_use,
            challenge_status=challenge_status,
        )
        challenge_packet = challenge_packet.model_copy(
            update={
                "visibility": visibility,
                "challenge_status": challenge_status,
                "audit_status": audit_status,
                "grievance_status": grievance_status,
                "reversal_status": reversal_status,
                "freeze_promotional_use": freeze_promotional_use,
                "challenge_count": challenge_count,
                "unresolved_challenge_count": unresolved_challenge_count,
                "material_challenge_count": material_challenge_count,
                "resolved_challenge_count": resolved_challenge_count,
                "remediation_case_count": len(remediation_cases),
                "public_notes": public_notes,
                "next_acknowledge_due_at": service_levels["acknowledge_due_at"],
                "next_triage_due_at": service_levels["triage_due_at"],
                "next_initial_finding_due_at": service_levels["initial_finding_due_at"],
                "service_level_notes": service_levels["notes"],
                "last_reviewed_at": last_reviewed_at,
            }
        )
        claim_card = claim_card.model_copy(
            update={
                "visibility": visibility,
                "claim_statement": claim_statement,
                "challenge_status": challenge_status,
                "integrity_class": integrity_class,
                "audit_status": audit_status,
                "grievance_status": grievance_status,
                "reversal_status": reversal_status,
                "promotional_use_frozen": freeze_promotional_use,
                "challenge_count": challenge_count,
                "unresolved_challenge_count": unresolved_challenge_count,
                "material_challenge_count": material_challenge_count,
                "remediation_case_count": len(remediation_cases),
                "public_notes": public_notes,
                "last_reviewed_at": last_reviewed_at,
                "remediation_status": remediation_status,
            }
        )
        livelihood_packet = livelihood_packet.model_copy(
            update={
                "visibility": visibility,
                "challenge_status": challenge_status,
            }
        )
        return {
            "claim_card": claim_card,
            "challenge_packet": challenge_packet,
            "livelihood_packet": livelihood_packet,
            "report": report,
        }

    def _summarize_challenge_status(
        self,
        challenge_records: Sequence[GaiaChallengeRecord],
    ) -> str:
        if not challenge_records:
            return "open"
        priority = (
            GaiaChallengeState.MATERIAL_CHALLENGE,
            GaiaChallengeState.APPEAL_OPEN,
            GaiaChallengeState.UPHELD,
            GaiaChallengeState.OPEN_REVIEW,
            GaiaChallengeState.NEEDS_EVIDENCE,
            GaiaChallengeState.ACKNOWLEDGED,
            GaiaChallengeState.SUBMITTED,
            GaiaChallengeState.RESOLVED,
            GaiaChallengeState.DISMISSED,
        )
        active_states = {record.state for record in challenge_records}
        for state in priority:
            if state in active_states:
                return state.value
        return "open"

    def _summarize_grievance_status(
        self,
        challenge_records: Sequence[GaiaChallengeRecord],
    ) -> GaiaGrievanceStatus:
        grievance_records = [
            record
            for record in challenge_records
            if record.ground is GaiaChallengeGround.GRIEVANCE_OR_HARM
        ]
        if not grievance_records:
            return GaiaGrievanceStatus.NONE
        active_states = {
            record.state
            for record in grievance_records
            if record.state
            not in {GaiaChallengeState.DISMISSED, GaiaChallengeState.RESOLVED}
        }
        if active_states & {
            GaiaChallengeState.MATERIAL_CHALLENGE,
            GaiaChallengeState.UPHELD,
            GaiaChallengeState.APPEAL_OPEN,
        }:
            return GaiaGrievanceStatus.MATERIAL
        if active_states:
            return GaiaGrievanceStatus.OPEN
        return GaiaGrievanceStatus.RESOLVED

    def _summarize_reversal_status(
        self,
        challenge_records: Sequence[GaiaChallengeRecord],
    ) -> GaiaReversalStatus:
        reversal_records = [
            record
            for record in challenge_records
            if record.ground is GaiaChallengeGround.ECOLOGICAL_REVERSAL
        ]
        if not reversal_records:
            return GaiaReversalStatus.NONE
        active_states = {
            record.state
            for record in reversal_records
            if record.state
            not in {GaiaChallengeState.DISMISSED, GaiaChallengeState.RESOLVED}
        }
        if active_states & {
            GaiaChallengeState.MATERIAL_CHALLENGE,
            GaiaChallengeState.UPHELD,
            GaiaChallengeState.APPEAL_OPEN,
        }:
            return GaiaReversalStatus.PARTIAL_REVERSAL
        if active_states:
            return GaiaReversalStatus.WATCH
        return GaiaReversalStatus.NONE

    def _summarize_audit_status(
        self,
        current_status: ReciprocityAuditStatus,
        challenge_records: Sequence[GaiaChallengeRecord],
    ) -> ReciprocityAuditStatus:
        if current_status is ReciprocityAuditStatus.FAILED:
            return current_status
        for record in challenge_records:
            if record.state in {
                GaiaChallengeState.DISMISSED,
                GaiaChallengeState.RESOLVED,
            }:
                continue
            if record.ground in {
                GaiaChallengeGround.AUDIT_CONFLICT_OF_INTEREST,
                GaiaChallengeGround.FABRICATED_OR_UNVERIFIABLE_EVIDENCE,
                GaiaChallengeGround.CONSERVATION_VIOLATION,
            }:
                return ReciprocityAuditStatus.CHALLENGED
        return current_status

    def _should_freeze_promotional_use(
        self,
        *,
        challenge_records: Sequence[GaiaChallengeRecord],
        remediation_cases: Sequence[GaiaRemediationCase],
        grievance_status: GaiaGrievanceStatus,
        reversal_status: GaiaReversalStatus,
        audit_status: ReciprocityAuditStatus,
    ) -> bool:
        active_freeze_states = {
            GaiaChallengeState.ACKNOWLEDGED,
            GaiaChallengeState.NEEDS_EVIDENCE,
            GaiaChallengeState.OPEN_REVIEW,
            GaiaChallengeState.MATERIAL_CHALLENGE,
            GaiaChallengeState.UPHELD,
            GaiaChallengeState.APPEAL_OPEN,
        }
        freeze_grounds = {
            GaiaChallengeGround.FABRICATED_OR_UNVERIFIABLE_EVIDENCE,
            GaiaChallengeGround.CONSENT_DISPUTE,
            GaiaChallengeGround.GRIEVANCE_OR_HARM,
            GaiaChallengeGround.CONSERVATION_VIOLATION,
            GaiaChallengeGround.ECOLOGICAL_REVERSAL,
            GaiaChallengeGround.AUDIT_CONFLICT_OF_INTEREST,
        }
        if audit_status in {
            ReciprocityAuditStatus.FAILED,
            ReciprocityAuditStatus.CHALLENGED,
        }:
            return True
        if grievance_status is GaiaGrievanceStatus.MATERIAL:
            return True
        if reversal_status is not GaiaReversalStatus.NONE:
            return True
        if any(
            record.state in active_freeze_states and record.ground in freeze_grounds
            for record in challenge_records
        ):
            return True
        if any(
            case.outcome
            in {
                GaiaRemediationOutcome.CLAIM_FREEZE,
                GaiaRemediationOutcome.CLAIM_WITHDRAWAL,
                GaiaRemediationOutcome.INTEGRITY_DOWNGRADE,
            }
            and case.step is not GaiaRemediationStep.HISTORICAL_APPEND
            for case in remediation_cases
        ):
            return True
        if any(
            record.state in {
                GaiaChallengeState.MATERIAL_CHALLENGE,
                GaiaChallengeState.UPHELD,
            }
            for record in challenge_records
        ):
            return True
        return False

    def _governed_claim_visibility(
        self,
        *,
        claim_card: GaiaClaimCard,
        audit_status: ReciprocityAuditStatus,
        freeze_promotional_use: bool,
    ) -> GaiaClaimVisibility:
        if not claim_card.challenge_contact.strip():
            return GaiaClaimVisibility.INTERNAL_ONLY
        eligible_public = (
            claim_card.measurement_claim_ready
            and bool(claim_card.evidence_refs)
            and bool(claim_card.audit_refs)
            and audit_status in {
                ReciprocityAuditStatus.PASSED,
                ReciprocityAuditStatus.QUALIFIED,
            }
        )
        if eligible_public and not freeze_promotional_use:
            return GaiaClaimVisibility.PUBLIC_READY
        if claim_card.blockers:
            return GaiaClaimVisibility.INTERNAL_ONLY
        return GaiaClaimVisibility.PROVISIONAL

    def _governed_integrity_class(
        self,
        *,
        integrity_class: str,
        challenge_records: Sequence[GaiaChallengeRecord],
        remediation_cases: Sequence[GaiaRemediationCase],
    ) -> str:
        lowered = integrity_class.strip().lower()
        downgraded = any(
            record.state
            in {
                GaiaChallengeState.MATERIAL_CHALLENGE,
                GaiaChallengeState.UPHELD,
                GaiaChallengeState.APPEAL_OPEN,
            }
            for record in challenge_records
        ) or any(
            case.outcome
            in {
                GaiaRemediationOutcome.INTEGRITY_DOWNGRADE,
                GaiaRemediationOutcome.CLAIM_FREEZE,
                GaiaRemediationOutcome.CLAIM_WITHDRAWAL,
            }
            for case in remediation_cases
        )
        if downgraded and lowered == "high_integrity":
            return "emerging"
        return integrity_class

    def _challenge_service_levels(
        self,
        challenge_records: Sequence[GaiaChallengeRecord],
        now: datetime,
    ) -> dict[str, Any]:
        acknowledge_due: datetime | None = None
        triage_due: datetime | None = None
        initial_finding_due: datetime | None = None
        notes: list[str] = []
        for record in challenge_records:
            if record.state in {
                GaiaChallengeState.DISMISSED,
                GaiaChallengeState.RESOLVED,
            }:
                continue
            if record.state is GaiaChallengeState.SUBMITTED:
                acknowledge_due = _earliest_datetime(
                    acknowledge_due,
                    _add_business_days(record.created_at, 5),
                )
            if record.state in {
                GaiaChallengeState.SUBMITTED,
                GaiaChallengeState.ACKNOWLEDGED,
            }:
                triage_due = _earliest_datetime(
                    triage_due,
                    _add_business_days(record.created_at, 10),
                )
            if record.state in {
                GaiaChallengeState.SUBMITTED,
                GaiaChallengeState.ACKNOWLEDGED,
                GaiaChallengeState.NEEDS_EVIDENCE,
                GaiaChallengeState.OPEN_REVIEW,
            }:
                initial_finding_due = _earliest_datetime(
                    initial_finding_due,
                    record.created_at + timedelta(days=30),
                )
        if acknowledge_due is not None:
            notes.append(
                _format_service_level_note(
                    "acknowledge",
                    acknowledge_due,
                    now,
                )
            )
        if triage_due is not None:
            notes.append(
                _format_service_level_note(
                    "triage",
                    triage_due,
                    now,
                )
            )
        if initial_finding_due is not None:
            notes.append(
                _format_service_level_note(
                    "initial finding",
                    initial_finding_due,
                    now,
                )
            )
        return {
            "acknowledge_due_at": acknowledge_due,
            "triage_due_at": triage_due,
            "initial_finding_due_at": initial_finding_due,
            "notes": tuple(notes),
        }

    def _summarize_remediation_status(
        self,
        *,
        remediation_cases: Sequence[GaiaRemediationCase],
        freeze_promotional_use: bool,
        existing_status: str,
    ) -> str:
        if any(
            case.step is GaiaRemediationStep.HISTORICAL_APPEND
            for case in remediation_cases
        ):
            return "resolved"
        if remediation_cases:
            return "in_progress"
        if freeze_promotional_use:
            return "follow_up_required"
        return existing_status

    def _merge_governance_public_notes(
        self,
        existing_notes: Sequence[str],
        *,
        challenge_status: str,
        freeze_promotional_use: bool,
        grievance_status: GaiaGrievanceStatus,
        reversal_status: GaiaReversalStatus,
        service_level_notes: Sequence[str],
        challenge_count: int,
        remediation_status: str,
    ) -> tuple[str, ...]:
        base_notes = [
            note for note in existing_notes if not note.startswith("GOVERNANCE:")
        ]
        governance_notes: list[str] = []
        if challenge_count:
            governance_notes.append(
                "GOVERNANCE: "
                f"{challenge_count} public challenge(s) recorded; current state is {challenge_status}."
            )
        if freeze_promotional_use:
            governance_notes.append(
                "GOVERNANCE: promotional wording is frozen while challenge or remediation remains active."
            )
        if grievance_status is not GaiaGrievanceStatus.NONE:
            governance_notes.append(
                "GOVERNANCE: grievance surface is "
                f"{grievance_status.value}."
            )
        if reversal_status is not GaiaReversalStatus.NONE:
            governance_notes.append(
                "GOVERNANCE: reversal surface is "
                f"{reversal_status.value}."
            )
        if remediation_status not in {"none_required", "follow_up_required"}:
            governance_notes.append(
                "GOVERNANCE: remediation status is "
                f"{remediation_status}."
            )
        governance_notes.extend(service_level_notes)
        return _unique_strings((*base_notes, *governance_notes))

    def _compose_governed_claim_statement(
        self,
        *,
        report: dict[str, Any],
        claim_card: GaiaClaimCard,
        visibility: GaiaClaimVisibility,
        freeze_promotional_use: bool,
        challenge_status: str,
    ) -> str:
        if freeze_promotional_use:
            return (
                f"Claim under review for {claim_card.project_name} in "
                f"{claim_card.reporting_period}; promotional wording is suspended "
                f"while challenge state is {challenge_status}. See the challenge packet "
                "for evidence, findings, and remediation."
            )
        reciprocity = report.get("reciprocity") or {}
        summary = reciprocity.get("summary") or {}
        ledger_summary = report.get("ledger_summary") or {}
        intake_payload = report.get("intake") or {}
        if visibility is not GaiaClaimVisibility.PUBLIC_READY:
            return (
                f"{claim_card.sponsor_name} staged a provisional GAIA packet for "
                f"{claim_card.project_name} in {claim_card.reporting_period}; public "
                "promotional reuse remains frozen until the missing proof surfaces are complete."
            )
        routed_value = float(summary.get("total_routed_usd", claim_card.routed_value_usd))
        verified_offset = float(
            ledger_summary.get("total_verified_offset", claim_card.total_verified_offset)
        )
        outcome_unit = str(intake_payload.get("outcome_unit", "tco2e"))
        return (
            f"{claim_card.sponsor_name} routed ${routed_value:,.2f} to "
            f"{claim_card.project_name} for {claim_card.livelihood_participant_count} "
            f"{claim_card.livelihood_target_group} and {verified_offset:.2f} "
            f"{outcome_unit} of verified restoration outcomes in "
            f"{claim_card.reporting_period}."
        )

    def render_dashboard(
        self,
        model_id: str,
        top_n: int = 3,
        energy_mwh: float = 12.0,
        carbon_intensity: float = 0.35,
    ) -> str:
        """Render a concise terminal dashboard with a real staged pilot."""
        recommendations = self.recommend_projects(model_id=model_id, top_n=top_n)
        pilot = None
        if recommendations:
            pilot = self._stage_recommendation(
                recommendation=recommendations[0],
                model_id=model_id,
                energy_mwh=energy_mwh,
                carbon_intensity=carbon_intensity,
            )

        lines = [
            "GAIA Platform",
            "Aptavani-aligned ecological restoration dashboard",
            "",
            f"Model Profile: {model_id}",
            f"Data Dir: {self._data_dir}",
            "",
            "Top Recommendations",
        ]
        if not recommendations:
            lines.append("  No approved projects available.")
        else:
            for index, recommendation in enumerate(recommendations, start=1):
                project = recommendation.project
                lines.extend(
                    [
                        (
                            f"  {index}. {project.name} "
                            f"[{project.verification_status}]"
                        ),
                        (
                            "     "
                            f"score={recommendation.match_score:.2f} "
                            f"welfare_tons={recommendation.welfare_tons:.2f} "
                            f"partner={project.community_partner}"
                        ),
                        (
                            "     "
                            f"principles={', '.join(recommendation.strategy.principles)}"
                        ),
                    ]
                )

        if pilot is not None:
            summary = pilot["ledger_summary"]
            lines.extend(
                [
                    "",
                    "Pilot Chain",
                    (
                        "  "
                        f"chain_valid={summary['chain_valid']} "
                        f"compute={summary['compute_units']} "
                        f"funding={summary['funding_units']} "
                        f"labor={summary['labor_units']} "
                        f"offset={summary['offset_units']} "
                        f"verification={summary['verification_units']}"
                    ),
                    (
                        "  "
                        f"verified_offset={summary['total_verified_offset']:.2f} "
                        f"net_position={summary['net_carbon_position']:.2f}"
                    ),
                    (
                        "  "
                        f"fitness={pilot['fitness']['weighted_score']:.3f} "
                        f"audit={pilot['report_path']}"
                    ),
                ]
            )

        return "\n".join(lines)

    def _default_projects(self) -> list[GaiaProject]:
        return [
            GaiaProject(
                project_id="bayou-lafourche-mangroves",
                name="Bayou Lafourche Mangrove Reciprocity Pilot",
                project_type="mangrove_restoration",
                country="USA",
                region="Louisiana Gulf Coast",
                hectares=420,
                carbon_potential_tons_yr=3_800,
                labor_needed=48,
                funding_gap_usd=640_000,
                verification_status="verified",
                community_partner="Bayou Reciprocity Cooperative",
                description=(
                    "Community-led mangrove restoration that combines satellite "
                    "monitoring, field audits, and local stewardship to strengthen "
                    "coastal resilience and worker livelihoods."
                ),
                verification_channels=(
                    "satellite",
                    "iot_sensor",
                    "human_auditor",
                    "community",
                ),
            ),
            GaiaProject(
                project_id="narmada-watershed-commons",
                name="Narmada Watershed Commons Renewal",
                project_type="watershed_restoration",
                country="India",
                region="Madhya Pradesh",
                hectares=610,
                carbon_potential_tons_yr=3_200,
                labor_needed=56,
                funding_gap_usd=520_000,
                verification_status="verified",
                community_partner="Narmada Stewardship Union",
                description=(
                    "Watershed restoration with soil monitoring, community water "
                    "governance, and mixed-species planting designed to improve "
                    "resilience for farming communities."
                ),
                verification_channels=(
                    "satellite",
                    "community",
                    "human_auditor",
                    "statistical_model",
                ),
            ),
            GaiaProject(
                project_id="delta-shelterbelt-corridor",
                name="Delta Shelterbelt Biodiversity Corridor",
                project_type="agroforestry",
                country="Bangladesh",
                region="Khulna Division",
                hectares=300,
                carbon_potential_tons_yr=2_100,
                labor_needed=34,
                funding_gap_usd=410_000,
                verification_status="field_review",
                community_partner="Delta Commons Forum",
                description=(
                    "Agroforestry corridor linking village shelterbelts, soil "
                    "repair, and flood resilience while creating paid restoration "
                    "work for local residents."
                ),
                verification_channels=(
                    "satellite",
                    "community",
                    "ground",
                ),
            ),
        ]

    def _estimate_welfare_tons(self, project: GaiaProject) -> float:
        labor_multiplier = 1.0 + min(project.labor_needed / 80.0, 0.40)
        return (
            project.carbon_potential_tons_yr
            * self._verification_multiplier(project)
            * self._community_multiplier(project)
            * labor_multiplier
        )

    def _verification_multiplier(self, project: GaiaProject) -> float:
        status = project.verification_status.lower()
        if status == "verified":
            return 1.0
        if status in {"field_review", "community_review"}:
            return 0.6
        return 0.35

    def _community_multiplier(self, project: GaiaProject) -> float:
        return 1.15 if self._has_viable_partner(project.community_partner) else 0.80

    def _model_affinity(self, model_id: str, project: GaiaProject) -> float:
        affinity = 1.0
        text = " ".join(
            (
                model_id,
                project.project_type,
                project.region,
                project.description,
            )
        ).lower()

        if "anthropic" in model_id.lower():
            affinity += 0.25
        if "claude" in model_id.lower():
            affinity += 0.10
        if any(term in text for term in ("mangrove", "wetland", "watershed")):
            affinity += 0.20
        if any(term in text for term in ("community", "coastal", "gulf")):
            affinity += 0.15
        if project.is_verified:
            affinity += 0.15
        return affinity

    def _pick_recommendation(
        self,
        model_id: str,
        project_id: str | None = None,
    ) -> GaiaRecommendation:
        recommendations = self.recommend_projects(
            model_id=model_id,
            top_n=len(self._projects),
        )
        if not recommendations:
            raise ValueError("No approved GAIA projects available for pilot staging")
        if project_id is None:
            return recommendations[0]
        for recommendation in recommendations:
            if recommendation.project.project_id == project_id:
                return recommendation
        if any(project.project_id == project_id for project in self._projects):
            raise ValueError(
                f"GAIA project '{project_id}' is present but not approved for pilot staging"
            )
        raise ValueError(f"Unknown GAIA project '{project_id}'")

    def _recommendation_for_project(
        self,
        model_id: str,
        project: GaiaProject,
    ) -> GaiaRecommendation:
        strategy = self.assess_project(project)
        return GaiaRecommendation(
            project=project,
            strategy=strategy,
            welfare_tons=round(self._estimate_welfare_tons(project), 2),
            match_score=round(
                self._estimate_welfare_tons(project)
                * self._model_affinity(model_id, project)
                / max(project.funding_gap_usd / 100_000.0, 1.0),
                2,
            ),
            verification_bonus=self._verification_multiplier(project),
            community_bonus=self._community_multiplier(project),
        )

    def _stage_recommendation(
        self,
        recommendation: GaiaRecommendation,
        model_id: str,
        energy_mwh: float,
        carbon_intensity: float,
    ) -> dict[str, Any]:
        project = recommendation.project
        ledger_dir = self._data_dir / "pilots" / f"{model_id}-{project.project_id}"
        ledger = GaiaLedger(data_dir=ledger_dir)

        compute = ComputeUnit(
            provider=model_id.split("_", 1)[0],
            energy_mwh=energy_mwh,
            carbon_intensity=carbon_intensity,
            workload_type="gaia_pilot",
            metadata={"model_id": model_id, "project_id": project.project_id},
        )
        ledger.record_compute(compute)

        funding = FundingUnit(
            amount_usd=max(25_000.0, min(project.funding_gap_usd, compute.co2e_tons * 7_500.0)),
            source=model_id,
            destination=project.community_partner,
            purpose=project.project_type,
            metadata={"project_id": project.project_id},
        )
        ledger.record_funding(funding)

        labor = LaborUnit(
            worker_id=f"{project.project_id}-lead-steward",
            project_id=project.project_id,
            hours=max(40.0, float(project.labor_needed) * 4.0),
            skill_type="restoration_coordination",
            location=f"{project.region}, {project.country}",
            output_metric=project.hectares,
            output_unit="hectares_scoped",
            wage_rate=32.0,
            metadata={"community_partner": project.community_partner},
        )
        ledger.record_labor(labor)

        offset = OffsetUnit(
            project_id=project.project_id,
            co2e_tons=max(compute.co2e_tons * 1.35, project.carbon_potential_tons_yr * 0.08),
            method=project.project_type,
            metadata={
                "project_name": project.name,
                "welfare_tons": recommendation.welfare_tons,
                "match_score": recommendation.match_score,
            },
        )
        ledger.record_offset(offset)

        session, coordination = verify_offset(
            ledger,
            offset.id,
            self._pilot_verdicts(project=project, offset_id=offset.id),
        )

        ledger_path = ledger.save()
        fitness_engine = EcologicalFitness()
        fitness_score = fitness_engine.score(ledger)
        weighted_score = fitness_engine.weighted_score(ledger)
        summary = ledger.summary()

        report = {
            "model_id": model_id,
            "project": project.model_dump(mode="json"),
            "recommendation": recommendation.model_dump(mode="json"),
            "ledger_summary": summary,
            "fitness": {
                "weighted_score": weighted_score,
                **fitness_score.model_dump(mode="json"),
            },
            "verification": {
                "session_id": session.id,
                "agreement_count": session.agreement_count,
                "agreeing_oracles": session.agreeing_oracles,
                "dissenting_oracles": session.dissenting_oracles,
                "final_confidence": session.final_confidence,
            },
            "coordination": (
                coordination.model_dump(mode="json") if coordination is not None else None
            ),
            "ledger_path": str(ledger_path),
        }
        report_path = ledger_dir / "pilot_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

        return {
            "project": project,
            "recommendation": recommendation,
            "ledger": ledger,
            "ledger_path": ledger_path,
            "ledger_summary": summary,
            "fitness": {
                "weighted_score": weighted_score,
                **fitness_score.model_dump(mode="json"),
            },
            "verification_session": session,
            "report_path": report_path,
        }

    def _assemble_report_payload(
        self,
        *,
        staged: dict[str, Any],
        model_id: str,
        feedback_entries: Sequence[GaiaUserFeedback | dict[str, Any]] | None,
    ) -> dict[str, Any]:
        project = staged["project"]
        monitoring = self._default_monitoring_snapshots(project)
        feedback = self._coerce_feedback_entries(project, feedback_entries)
        feedback_summary = self._summarize_feedback(feedback)
        effectiveness = self._effectiveness_summary(
            staged=staged,
            monitoring=monitoring,
            feedback_summary=feedback_summary,
        )
        return {
            "model_id": model_id,
            "project": project.model_dump(mode="json"),
            "recommendation": staged["recommendation"].model_dump(mode="json"),
            "ledger_summary": staged["ledger_summary"],
            "fitness": staged["fitness"],
            "verification": {
                "session_id": staged["verification_session"].id,
                "agreement_count": staged["verification_session"].agreement_count,
                "agreeing_oracles": staged["verification_session"].agreeing_oracles,
                "dissenting_oracles": staged["verification_session"].dissenting_oracles,
                "final_confidence": staged["verification_session"].final_confidence,
            },
            "monitoring": {
                "snapshot_count": len(monitoring),
                "snapshots": [snapshot.model_dump(mode="json") for snapshot in monitoring],
            },
            "feedback": [entry.model_dump(mode="json") for entry in feedback],
            "feedback_summary": feedback_summary,
            "effectiveness": effectiveness,
            "ledger_path": str(staged["ledger_path"]),
        }

    def _initiative_summary_from_intake(
        self,
        intake: GaiaPilotIntake,
    ) -> dict[str, Any] | None:
        if not any(
            (
                intake.ecosystem_type,
                intake.boundary_ref,
                intake.standards_profile,
                intake.monitoring_indicators,
                intake.observation_protocols,
                intake.planned_activities,
            )
        ):
            return None
        return {
            "initiative_id": intake.project.project_id,
            "initiative_name": intake.project.name,
            "ecosystem_type": intake.ecosystem_type,
            "boundary_ref": intake.boundary_ref,
            "planned_activity_count": len(intake.planned_activities),
            "monitoring_indicator_count": len(intake.monitoring_indicators),
            "observation_protocols": list(intake.observation_protocols),
            "standards_profile": list(intake.standards_profile),
        }

    def _build_reciprocity_packet(
        self,
        *,
        intake: GaiaPilotIntake,
        qualification: GaiaQualificationDecision,
        staged: dict[str, Any],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        ledger_dir = Path(staged["ledger_path"]).parent / "reciprocity"
        reciprocity = AIReciprocityLedger(data_dir=ledger_dir)
        period_start, period_end = _reporting_period_bounds(intake.reporting_period)
        activity_confidence = _confidence_from_measurement_mode(intake.measurement_mode)

        actor = AIActor(
            actor_name=intake.sponsor_name,
            actor_type=intake.sponsor_actor_type,
            jurisdiction=intake.sponsor_jurisdiction,
            disclosure_level=intake.sponsor_disclosure_level,
            metadata={"model_id": intake.model_id},
        )
        reciprocity.record_actor(actor)

        activity = ActivityRecord(
            actor_id=actor.actor_id,
            workload_label=intake.model_id,
            period_start=period_start,
            period_end=period_end,
            exposure_class=_exposure_class_from_model(intake.model_id),
            energy_mwh=intake.energy_mwh,
            emissions_tco2e=round(intake.energy_mwh * intake.carbon_intensity, 6),
            methodology_ref=intake.measurement_ref,
            confidence=activity_confidence,
            metadata={
                "reporting_period": intake.reporting_period,
                "measurement_mode": intake.measurement_mode.value,
                "measurement_verifier": intake.measurement_verifier,
                "measurement_boundary_ref": intake.measurement_boundary_ref,
            },
        )
        reciprocity.record_activity(activity)

        obligation = ObligationRecord(
            activity_id=activity.activity_id,
            obligation_type=ReciprocityObligationType.MIXED,
            obligation_basis=_obligation_basis_from_rule(intake.obligation_rule),
            obligation_quantity=staged["ledger_summary"]["total_funding_usd"],
            obligation_unit=ReciprocityQuantityUnit.USD,
            status=ReciprocityObligationStatus.ACTIVE,
            metadata={
                "rule": intake.obligation_rule,
                "project_id": intake.project.project_id,
            },
        )
        reciprocity.record_obligation(obligation)

        project = ProjectRecord(
            project_id=intake.project.project_id,
            project_name=intake.project.name,
            project_type=_project_type_from_value(intake.project.project_type),
            location=f"{intake.project.region}, {intake.project.country}",
            operator_name=intake.project_operator,
            integrity_class=_integrity_class_from_value(intake.integrity_class),
            indigenous_or_local_consent=_consent_status_from_value(
                intake.consent_status
            ),
            methodology_ref=intake.methodology_ref,
            metadata={
                "community_partner": intake.project.community_partner,
                "challenge_contact": intake.challenge_contact,
                "benefit_sharing_ref": intake.benefit_sharing_ref,
                "grievance_process_ref": intake.grievance_process_ref,
                "due_diligence_ref": intake.due_diligence_ref,
            },
        )
        reciprocity.record_project(project)

        routing = RoutingRecord(
            obligation_id=obligation.obligation_id,
            project_id=project.project_id,
            routed_value=staged["ledger_summary"]["total_funding_usd"],
            routed_unit=ReciprocityQuantityUnit.USD,
            restrictions=intake.obligation_rule,
            metadata={"reporting_period": intake.reporting_period},
        )
        reciprocity.record_routing(routing)

        livelihood = LivelihoodRecord(
            project_id=project.project_id,
            participant_count=(
                intake.livelihood_participant_count or intake.project.labor_needed
            ),
            livelihood_mode=intake.livelihood_mode,
            median_compensation_local=intake.median_compensation_local,
            local_ownership_share=intake.local_ownership_share,
            transition_target_group=intake.livelihood_target_group,
            person_hours=(
                intake.livelihood_person_hours
                or staged["ledger_summary"]["total_labor_hours"]
            ),
            metadata={
                "partner_credibility": intake.partner_credibility.value,
                "community_partner": intake.project.community_partner,
            },
        )
        reciprocity.record_livelihood(livelihood)

        outcome = OutcomeRecord(
            project_id=project.project_id,
            outcome_type=intake.outcome_type,
            quantity=staged["ledger_summary"]["total_verified_offset"],
            unit=intake.outcome_unit,
            status=_outcome_status_for_claim(
                verified_offset=staged["ledger_summary"]["total_verified_offset"],
                integrity_class=project.integrity_class,
                evidence_refs=intake.evidence_refs,
                audit_refs=intake.audit_refs,
                visibility=qualification.visibility,
            ),
            metadata={
                "net_carbon_position_tons": staged["ledger_summary"][
                    "net_carbon_position"
                ],
                "claim_visibility": qualification.visibility.value,
                "monitoring_status": report["effectiveness"]["status"],
            },
        )
        reciprocity.record_outcome(outcome)

        reciprocity.record_evidence(
            EvidenceRecord(
                subject_type=EvidenceSubjectType.ACTIVITY,
                subject_id=activity.activity_id,
                evidence_type=EvidenceType.METERING,
                source_ref=intake.measurement_ref,
                verifier=intake.measurement_verifier or intake.sponsor_name,
                confidence=activity_confidence,
                metadata={
                    "measurement_mode": intake.measurement_mode.value,
                    "measurement_boundary_ref": intake.measurement_boundary_ref,
                },
            )
        )

        for source_ref in intake.metering_evidence_refs:
            reciprocity.record_evidence(
                EvidenceRecord(
                    subject_type=EvidenceSubjectType.ACTIVITY,
                    subject_id=activity.activity_id,
                    evidence_type=EvidenceType.METERING,
                    source_ref=source_ref,
                    verifier=intake.measurement_verifier or intake.sponsor_name,
                    confidence=activity_confidence,
                    metadata={
                        "measurement_mode": intake.measurement_mode.value,
                        "measurement_boundary_ref": intake.measurement_boundary_ref,
                    },
                )
            )

        for source_ref in intake.metering_audit_refs:
            reciprocity.record_audit(
                AuditRecord(
                    scope=AuditScope.ACTIVITY,
                    scope_id=activity.activity_id,
                    audit_status=intake.audit_status,
                    auditor=intake.measurement_verifier or intake.auditor_name,
                    notes_ref=source_ref,
                    metadata={
                        "measurement_boundary_ref": intake.measurement_boundary_ref,
                        "challenge_contact": intake.challenge_contact,
                    },
                )
            )

        for source_ref in intake.evidence_refs:
            evidence_type = _evidence_type_from_ref(source_ref)
            reciprocity.record_evidence(
                EvidenceRecord(
                    subject_type=EvidenceSubjectType.OUTCOME,
                    subject_id=outcome.outcome_id,
                    evidence_type=evidence_type,
                    source_ref=source_ref,
                    verifier=intake.project.community_partner,
                    confidence=_confidence_from_evidence_type(evidence_type),
                )
            )

        for source_ref in intake.audit_refs:
            reciprocity.record_audit(
                AuditRecord(
                    scope=AuditScope.OUTCOME,
                    scope_id=outcome.outcome_id,
                    audit_status=intake.audit_status,
                    auditor=intake.auditor_name,
                    notes_ref=source_ref,
                    metadata={"challenge_contact": intake.challenge_contact},
                )
            )

        ledger_path = reciprocity.save()
        projection, projection_warnings = reciprocity.to_gaia_ledger(
            data_dir=ledger_dir / "projection"
        )
        projection_path = projection.save()

        return {
            "ledger_path": ledger_path,
            "projection_path": projection_path,
            "summary": reciprocity.summary(),
            "projection_summary": projection.summary(),
            "projection_warnings": projection_warnings,
            "activity_id": activity.activity_id,
            "obligation_id": obligation.obligation_id,
            "routing_id": routing.routing_id,
            "outcome_id": outcome.outcome_id,
            "outcome_status": outcome.status.value,
            "livelihood": {
                "participant_count": livelihood.participant_count,
                "person_hours": livelihood.person_hours,
                "mode": livelihood.livelihood_mode.value,
            },
        }

    def _default_monitoring_snapshots(
        self,
        project: GaiaProject,
    ) -> list[GaiaMonitoringSnapshot]:
        climate_bonus = 3.0 if "mangrove" in project.project_type else 2.0
        base_cover = min(22.0 + (project.hectares / 120.0), 36.0)
        base_hours = max(48.0, float(project.labor_needed) * 2.2)
        base_participants = max(12, project.labor_needed // 3)
        return [
            GaiaMonitoringSnapshot(
                label="baseline",
                day=0,
                vegetation_cover_pct=round(base_cover, 1),
                soil_carbon_index=0.41,
                steward_hours=round(base_hours, 1),
                community_participants=base_participants,
                survival_rate_pct=76.0,
                notes=(
                    "Initial stewardship plan loaded with baseline habitat and labor "
                    "commitments."
                ),
            ),
            GaiaMonitoringSnapshot(
                label="day_45_review",
                day=45,
                vegetation_cover_pct=round(base_cover + 6.5 + climate_bonus, 1),
                soil_carbon_index=0.54,
                steward_hours=round(base_hours * 1.45, 1),
                community_participants=base_participants + 5,
                survival_rate_pct=82.0,
                notes=(
                    "Early monitoring shows field engagement increasing while "
                    "verification channels remain active."
                ),
            ),
            GaiaMonitoringSnapshot(
                label="day_90_review",
                day=90,
                vegetation_cover_pct=round(base_cover + 12.0 + climate_bonus, 1),
                soil_carbon_index=0.67,
                steward_hours=round(base_hours * 1.9, 1),
                community_participants=base_participants + 9,
                survival_rate_pct=87.0,
                notes=(
                    "Pilot remains on track with rising cover, stronger soil signal, "
                    "and sustained community participation."
                ),
            ),
        ]

    def _coerce_feedback_entries(
        self,
        project: GaiaProject,
        feedback_entries: Sequence[GaiaUserFeedback | dict[str, Any]] | None,
    ) -> list[GaiaUserFeedback]:
        entries = feedback_entries
        if entries is None:
            entries = self._default_feedback_entries(project)
        return [
            entry if isinstance(entry, GaiaUserFeedback) else GaiaUserFeedback.model_validate(entry)
            for entry in entries
        ]

    def _default_feedback_entries(self, project: GaiaProject) -> list[dict[str, Any]]:
        return [
            {
                "actor_id": f"{project.project_id}-community-steward",
                "role": "community_steward",
                "satisfaction": 4.6,
                "confidence": 0.88,
                "summary": (
                    "GAIA kept the proof burden visible and helped the stewardship "
                    "team explain progress without overclaiming."
                ),
                "requested_follow_up": "Keep the next monitoring checkpoint public.",
            },
            {
                "actor_id": f"{project.project_id}-scientific-reviewer",
                "role": "scientific_reviewer",
                "satisfaction": 4.3,
                "confidence": 0.86,
                "summary": (
                    "The pilot report preserves evidence paths and dissent risk better "
                    "than a simple offset summary."
                ),
                "requested_follow_up": "Add a habitat-survival trendline to the report.",
            },
        ]

    def _summarize_feedback(
        self,
        feedback: Sequence[GaiaUserFeedback],
    ) -> dict[str, Any]:
        if not feedback:
            return {
                "response_count": 0,
                "average_satisfaction": 0.0,
                "average_confidence": 0.0,
                "top_follow_up": "",
            }
        average_satisfaction = round(
            sum(entry.satisfaction for entry in feedback) / len(feedback),
            2,
        )
        average_confidence = round(
            sum(entry.confidence for entry in feedback) / len(feedback),
            2,
        )
        top_follow_up = max(
            feedback,
            key=lambda entry: (entry.satisfaction * entry.confidence, entry.requested_follow_up),
        ).requested_follow_up
        return {
            "response_count": len(feedback),
            "average_satisfaction": average_satisfaction,
            "average_confidence": average_confidence,
            "top_follow_up": top_follow_up,
        }

    def _effectiveness_summary(
        self,
        *,
        staged: dict[str, Any],
        monitoring: Sequence[GaiaMonitoringSnapshot],
        feedback_summary: dict[str, Any],
    ) -> dict[str, Any]:
        latest = monitoring[-1]
        checks = 0
        if staged["ledger_summary"]["chain_valid"]:
            checks += 1
        if staged["ledger_summary"]["total_verified_offset"] > 0:
            checks += 1
        if staged["fitness"]["weighted_score"] >= 0.25:
            checks += 1
        if latest.survival_rate_pct >= 80.0:
            checks += 1
        if feedback_summary["average_satisfaction"] >= 4.0:
            checks += 1

        status = "on_track"
        if checks <= 2:
            status = "at_risk"
        elif checks == 3:
            status = "needs_attention"

        return {
            "status": status,
            "checks_passed": checks,
            "verified_offset_tons": staged["ledger_summary"]["total_verified_offset"],
            "net_carbon_position_tons": staged["ledger_summary"]["net_carbon_position"],
            "latest_survival_rate_pct": latest.survival_rate_pct,
            "latest_community_participants": latest.community_participants,
            "avg_user_satisfaction": feedback_summary["average_satisfaction"],
        }

    def _build_measurement_packet(
        self,
        *,
        intake: GaiaPilotIntake,
        qualification: GaiaQualificationDecision,
    ) -> GaiaMeasurementPacket:
        return GaiaMeasurementPacket(
            sponsor_name=intake.sponsor_name,
            model_id=intake.model_id,
            reporting_period=intake.reporting_period,
            measurement_mode=intake.measurement_mode,
            measurement_ref=intake.measurement_ref,
            measurement_verifier=intake.measurement_verifier,
            measurement_boundary_ref=intake.measurement_boundary_ref,
            energy_mwh=intake.energy_mwh,
            carbon_intensity=intake.carbon_intensity,
            emissions_tco2e=round(intake.energy_mwh * intake.carbon_intensity, 6),
            metering_evidence_refs=intake.metering_evidence_refs,
            metering_audit_refs=intake.metering_audit_refs,
            public_claim_ready=qualification.measurement_claim_ready,
            warnings=[
                warning
                for warning in qualification.warnings
                if warning.startswith("MEASUREMENT:")
            ],
        )

    def _build_livelihood_packet(
        self,
        *,
        intake: GaiaPilotIntake,
        qualification: GaiaQualificationDecision,
        report: dict[str, Any],
        reciprocity: dict[str, Any],
    ) -> GaiaLivelihoodPacket:
        feedback_roles = tuple(
            sorted(
                {
                    str(entry["role"])
                    for entry in report["feedback"]
                    if entry.get("role")
                }
            )
        )
        feedback_summary = report["feedback_summary"]
        livelihood = reciprocity["livelihood"]
        return GaiaLivelihoodPacket(
            sponsor_name=intake.sponsor_name,
            model_id=intake.model_id,
            reporting_period=intake.reporting_period,
            visibility=qualification.visibility,
            challenge_status=qualification.challenge_status,
            project_id=intake.project.project_id,
            project_name=intake.project.name,
            project_operator=intake.project_operator,
            community_partner=intake.project.community_partner,
            livelihood_target_group=intake.livelihood_target_group,
            livelihood_mode=intake.livelihood_mode,
            participant_count=livelihood["participant_count"],
            person_hours=livelihood["person_hours"],
            median_compensation_local=intake.median_compensation_local,
            local_ownership_share=intake.local_ownership_share,
            partner_credibility=intake.partner_credibility,
            due_diligence_ref=intake.due_diligence_ref,
            consent_status=intake.consent_status,
            consent_ref=intake.consent_ref,
            benefit_sharing_ref=intake.benefit_sharing_ref,
            grievance_process_ref=intake.grievance_process_ref,
            challenge_contact=intake.challenge_contact,
            feedback_response_count=feedback_summary["response_count"],
            feedback_roles=feedback_roles,
            feedback_average_satisfaction=feedback_summary["average_satisfaction"],
            feedback_average_confidence=feedback_summary["average_confidence"],
            top_follow_up=feedback_summary["top_follow_up"],
            linked_evidence_refs=intake.evidence_refs,
            linked_audit_refs=intake.audit_refs,
            verification_channels=qualification.verification_channels,
            reciprocity_ledger_path=str(reciprocity["ledger_path"]),
            report_path=str(Path(report["ledger_path"]).with_name("pilot_report.json")),
        )

    def _build_challenge_packet(
        self,
        *,
        intake: GaiaPilotIntake,
        qualification: GaiaQualificationDecision,
        report: dict[str, Any],
    ) -> GaiaChallengePacket:
        freeze_promotional_use = qualification.visibility is not GaiaClaimVisibility.PUBLIC_READY
        public_notes = list(qualification.warnings)
        if qualification.visibility is GaiaClaimVisibility.PUBLIC_READY:
            public_notes.append(
                "Public claim may circulate because measurement, evidence, and audit paths are present."
            )
        else:
            public_notes.append(
                "Promotional reuse stays frozen until the claim becomes public-ready."
            )

        reversal_status = GaiaReversalStatus.NONE
        monitoring_status = report["effectiveness"]["status"]
        if monitoring_status in {"needs_attention", "at_risk"}:
            reversal_status = GaiaReversalStatus.WATCH
            public_notes.append(
                f"Monitoring status is {monitoring_status}; operator review is still active."
            )

        return GaiaChallengePacket(
            claim_id=f"{intake.model_id}:{intake.project.project_id}:{intake.reporting_period}",
            visibility=qualification.visibility,
            challenge_status=qualification.challenge_status,
            audit_status=intake.audit_status,
            challenge_contact=intake.challenge_contact,
            grievance_process_ref=intake.grievance_process_ref,
            consent_status=intake.consent_status,
            grievance_status=GaiaGrievanceStatus.NONE,
            reversal_status=reversal_status,
            freeze_promotional_use=freeze_promotional_use,
            challenge_count=0,
            unresolved_challenge_count=0,
            material_challenge_count=0,
            resolved_challenge_count=0,
            remediation_case_count=0,
            public_notes=tuple(public_notes),
            report_path=str(Path(report["ledger_path"]).with_name("pilot_report.json")),
            claim_card_path=str(Path(report["ledger_path"]).with_name("claim_card.json")),
        )

    def _build_claim_card(
        self,
        *,
        intake: GaiaPilotIntake,
        qualification: GaiaQualificationDecision,
        report: dict[str, Any],
        challenge_packet: GaiaChallengePacket,
    ) -> GaiaClaimCard:
        remediation_status = (
            "none_required"
            if report["effectiveness"]["status"] == "on_track"
            else "follow_up_required"
        )
        reciprocity = report["reciprocity"]
        feedback_roles = tuple(
            sorted(
                {
                    str(entry["role"])
                    for entry in report["feedback"]
                    if entry.get("role")
                }
            )
        )
        livelihood_participant_count = reciprocity["livelihood"]["participant_count"]
        claim_type = GaiaClaimType.OUTCOME
        if livelihood_participant_count > 0 and report["ledger_summary"]["total_verified_offset"] > 0:
            claim_type = GaiaClaimType.MIXED
        elif livelihood_participant_count > 0:
            claim_type = GaiaClaimType.LIVELIHOOD
        elif report["ledger_summary"]["total_verified_offset"] <= 0:
            claim_type = GaiaClaimType.ACTIVITY

        claim_statement = (
            f"{intake.sponsor_name} routed ${reciprocity['summary']['total_routed_usd']:,.2f} "
            f"to {intake.project.name} for {livelihood_participant_count} "
            f"{intake.livelihood_target_group} and "
            f"{report['ledger_summary']['total_verified_offset']:.2f} {intake.outcome_unit} "
            f"of verified restoration outcomes in {intake.reporting_period}."
        )
        if qualification.visibility is not GaiaClaimVisibility.PUBLIC_READY:
            claim_statement = (
                f"{intake.sponsor_name} staged a provisional GAIA packet for "
                f"{intake.project.name} in {intake.reporting_period}; public promotional reuse "
                "remains frozen until the missing proof surfaces are complete."
            )

        claim_scope = (
            f"{intake.reporting_period} | {intake.project.region}, {intake.project.country} | "
            f"measurement={intake.measurement_mode.value} | "
            f"verification={', '.join(qualification.verification_channels)}"
        )
        return GaiaClaimCard(
            claim_id=f"{intake.model_id}:{intake.project.project_id}:{intake.reporting_period}",
            visibility=qualification.visibility,
            claim_statement=claim_statement,
            claim_type=claim_type,
            claim_scope=claim_scope,
            challenge_status=qualification.challenge_status,
            challenge_contact=intake.challenge_contact,
            sponsor_name=intake.sponsor_name,
            model_id=intake.model_id,
            reporting_period=intake.reporting_period,
            project_id=intake.project.project_id,
            project_name=intake.project.name,
            project_operator=intake.project_operator,
            community_partner=intake.project.community_partner,
            integrity_class=qualification.integrity_class,
            methodology_ref=intake.methodology_ref,
            audit_status=intake.audit_status,
            measurement_mode=intake.measurement_mode,
            measurement_ref=intake.measurement_ref,
            measurement_verifier=intake.measurement_verifier,
            measurement_boundary_ref=intake.measurement_boundary_ref,
            metering_evidence_refs=intake.metering_evidence_refs,
            metering_audit_refs=intake.metering_audit_refs,
            measurement_claim_ready=qualification.measurement_claim_ready,
            measurement_packet_path=str(
                Path(report["ledger_path"]).with_name("measurement_packet.json")
            ),
            obligation_rule=intake.obligation_rule,
            benefit_sharing_ref=intake.benefit_sharing_ref,
            grievance_process_ref=intake.grievance_process_ref,
            consent_status=intake.consent_status,
            consent_ref=intake.consent_ref,
            due_diligence_ref=intake.due_diligence_ref,
            grievance_status=challenge_packet.grievance_status,
            reversal_status=challenge_packet.reversal_status,
            ecosystem_type=intake.ecosystem_type,
            boundary_ref=intake.boundary_ref,
            standards_profile=intake.standards_profile,
            observation_protocols=intake.observation_protocols,
            planned_activity_count=len(intake.planned_activities),
            monitoring_indicator_count=len(intake.monitoring_indicators),
            livelihood_target_group=intake.livelihood_target_group,
            evidence_refs=intake.evidence_refs,
            audit_refs=intake.audit_refs,
            verification_channels=qualification.verification_channels,
            final_confidence=report["verification"]["final_confidence"],
            agreeing_oracles=tuple(report["verification"]["agreeing_oracles"]),
            dissenting_oracles=tuple(report["verification"]["dissenting_oracles"]),
            total_verified_offset=report["ledger_summary"]["total_verified_offset"],
            net_carbon_position=report["ledger_summary"]["net_carbon_position"],
            ledger_path=str(report["ledger_path"]),
            reciprocity_ledger_path=str(reciprocity["ledger_path"]),
            report_path=str(Path(report["ledger_path"]).with_name("pilot_report.json")),
            obligation_quantity_usd=reciprocity["summary"]["total_obligation_usd"],
            routed_value_usd=reciprocity["summary"]["total_routed_usd"],
            livelihood_participant_count=livelihood_participant_count,
            livelihood_mode=intake.livelihood_mode,
            livelihood_person_hours=reciprocity["livelihood"]["person_hours"],
            median_compensation_local=intake.median_compensation_local,
            local_ownership_share=intake.local_ownership_share,
            livelihood_feedback_count=report["feedback_summary"]["response_count"],
            livelihood_feedback_roles=feedback_roles,
            livelihood_packet_path=str(
                Path(report["ledger_path"]).with_name("livelihood_packet.json")
            ),
            challenge_packet_path=str(
                Path(report["ledger_path"]).with_name("challenge_packet.json")
            ),
            promotional_use_frozen=challenge_packet.freeze_promotional_use,
            challenge_count=challenge_packet.challenge_count,
            unresolved_challenge_count=challenge_packet.unresolved_challenge_count,
            material_challenge_count=challenge_packet.material_challenge_count,
            remediation_case_count=challenge_packet.remediation_case_count,
            reciprocity_invariant_issues=reciprocity["summary"]["invariant_issues"],
            reciprocity_projection_warnings=tuple(
                reciprocity["projection_warnings"]
            ),
            public_notes=challenge_packet.public_notes,
            last_reviewed_at=challenge_packet.last_reviewed_at,
            monitoring_status=report["effectiveness"]["status"],
            remediation_status=remediation_status,
            warnings=list(qualification.warnings),
            blockers=list(qualification.blockers),
        )

    def _update_claim_explorer(self, claim_card: GaiaClaimCard) -> dict[str, Any]:
        explorer_path = self._data_dir / "claim_explorer.json"
        markdown_path = explorer_path.with_suffix(".md")
        entries_by_id: dict[str, GaiaClaimExplorerEntry] = {}

        if explorer_path.exists():
            try:
                payload = json.loads(explorer_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            for item in payload.get("entries", []):
                try:
                    entry = GaiaClaimExplorerEntry.model_validate(item)
                except Exception:
                    continue
                entries_by_id[entry.claim_id] = entry

        entries_by_id[claim_card.claim_id] = GaiaClaimExplorerEntry(
            claim_id=claim_card.claim_id,
            visibility=claim_card.visibility,
            sponsor_name=claim_card.sponsor_name,
            project_name=claim_card.project_name,
            claim_statement=claim_card.claim_statement,
            integrity_class=claim_card.integrity_class,
            challenge_status=claim_card.challenge_status,
            promotional_use_frozen=claim_card.promotional_use_frozen,
            challenge_count=claim_card.challenge_count,
            material_challenge_count=claim_card.material_challenge_count,
            audit_status=claim_card.audit_status,
            grievance_status=claim_card.grievance_status,
            reversal_status=claim_card.reversal_status,
            total_verified_offset=claim_card.total_verified_offset,
            final_confidence=claim_card.final_confidence,
            last_reviewed_at=claim_card.last_reviewed_at,
            claim_card_path=str(Path(claim_card.report_path).with_name("claim_card.json")),
            challenge_packet_path=claim_card.challenge_packet_path,
        )
        entries = tuple(
            sorted(
                entries_by_id.values(),
                key=lambda entry: entry.last_reviewed_at,
                reverse=True,
            )
        )
        explorer = GaiaClaimExplorer(
            claim_count=len(entries),
            public_ready_count=sum(
                1
                for entry in entries
                if entry.visibility is GaiaClaimVisibility.PUBLIC_READY
            ),
            provisional_count=sum(
                1
                for entry in entries
                if entry.visibility is GaiaClaimVisibility.PROVISIONAL
            ),
            challenged_count=sum(
                1
                for entry in entries
                if entry.challenge_count > 0
                or entry.grievance_status is not GaiaGrievanceStatus.NONE
                or entry.reversal_status is not GaiaReversalStatus.NONE
            ),
            entries=entries,
        )
        explorer_path.write_text(
            json.dumps(explorer.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self._render_claim_explorer_markdown(explorer),
            encoding="utf-8",
        )
        return {
            "explorer": explorer,
            "json_path": explorer_path,
            "markdown_path": markdown_path,
        }

    def _render_pilot_report_markdown(self, report: dict[str, Any]) -> str:
        measurement = report.get("measurement")
        lines = [
            "# GAIA Pilot Report",
            "",
            f"Project: {report['project']['name']}",
            f"Model Profile: {report['model_id']}",
            "",
            "## Outcome Summary",
            (
                "- "
                f"Verified offset: {report['ledger_summary']['total_verified_offset']:.2f} tCO2e"
            ),
            (
                "- "
                f"Net carbon position: {report['ledger_summary']['net_carbon_position']:.2f} tCO2e"
            ),
            (
                "- "
                f"Effectiveness status: {report['effectiveness']['status']}"
            ),
            "",
            "## Monitoring",
        ]
        if measurement is not None:
            lines[9:9] = [
                "",
                "## Measurement",
                f"- Mode: {measurement['measurement_mode']}",
                f"- Ref: {measurement['measurement_ref']}",
                f"- Verifier: {measurement['measurement_verifier'] or 'unspecified'}",
                (
                    "- "
                    "Boundary ref: "
                    f"{measurement['measurement_boundary_ref'] or 'unspecified'}"
                ),
                (
                    "- "
                    f"Metering evidence refs: {len(measurement['metering_evidence_refs'])}"
                ),
                (
                    "- "
                    f"Metering audit refs: {len(measurement['metering_audit_refs'])}"
                ),
                (
                    "- "
                    "Public claim ready: "
                    f"{'yes' if measurement['public_claim_ready'] else 'no'}"
                ),
            ]
        for snapshot in report["monitoring"]["snapshots"]:
            lines.append(
                "- "
                f"{snapshot['label']} (day {snapshot['day']}): "
                f"cover={snapshot['vegetation_cover_pct']:.1f}%, "
                f"soil_index={snapshot['soil_carbon_index']:.2f}, "
                f"participants={snapshot['community_participants']}, "
                f"survival={snapshot['survival_rate_pct']:.1f}%"
            )
        lines.extend(["", "## User Feedback"])
        for entry in report["feedback"]:
            lines.append(
                "- "
                f"{entry['role']} [{entry['actor_id']}]: "
                f"{entry['summary']} "
                f"(satisfaction={entry['satisfaction']:.1f}/5, "
                f"follow_up={entry['requested_follow_up']})"
            )
        lines.extend(
            [
                "",
                "## Audit Trail",
                f"- Ledger path: {report['ledger_path']}",
                f"- Responses captured: {report['feedback_summary']['response_count']}",
                (
                    "- "
                    f"Top follow-up: {report['feedback_summary']['top_follow_up']}"
                ),
            ]
        )
        claim_card = report.get("claim_card")
        if claim_card is not None:
            lines.extend(
                [
                    "",
                    "## Claim Card",
                    f"- Visibility: {claim_card['visibility']}",
                    f"- Challenge status: {claim_card['challenge_status']}",
                    f"- Methodology: {claim_card['methodology_ref']}",
                    (
                        "- "
                        f"Evidence refs: {len(claim_card['evidence_refs'])} | "
                        f"Audit refs: {len(claim_card['audit_refs'])}"
                    ),
                ]
            )
        challenge = report.get("challenge")
        if challenge is not None:
            lines.extend(
                [
                    "",
                    "## Challengeability",
                    f"- Status: {challenge['challenge_status']}",
                    (
                        "- "
                        f"Challenge count: {challenge['challenge_count']} | "
                        f"Material: {challenge['material_challenge_count']} | "
                        f"Remediation cases: {challenge['remediation_case_count']}"
                    ),
                    (
                        "- "
                        "Promotional reuse frozen: "
                        f"{'yes' if challenge['freeze_promotional_use'] else 'no'}"
                    ),
                    f"- Challenge packet: {challenge['packet_path']}",
                    f"- Challenge contact: {challenge['challenge_contact']}",
                    f"- Public notes: {len(challenge['public_notes'])}",
                ]
            )
        initiative = report.get("initiative")
        if initiative is not None:
            lines.extend(
                [
                    "",
                    "## Initiative Context",
                    f"- Ecosystem type: {initiative['ecosystem_type']}",
                    f"- Boundary ref: {initiative['boundary_ref']}",
                    (
                        "- "
                        "Standards profile: "
                        f"{', '.join(initiative['standards_profile'])}"
                    ),
                    (
                        "- "
                        "Observation protocols: "
                        f"{', '.join(initiative['observation_protocols'])}"
                    ),
                    (
                        "- "
                        f"Monitoring indicators: {initiative['monitoring_indicator_count']}"
                    ),
                ]
            )
        livelihood = report.get("livelihood")
        if livelihood is not None:
            lines.extend(
                [
                    "",
                    "## Livelihood Transition",
                    f"- Target group: {livelihood['livelihood_target_group']}",
                    f"- Mode: {livelihood['livelihood_mode']}",
                    (
                        "- "
                        f"Participants: {livelihood['participant_count']} | "
                        f"Person-hours: {livelihood['person_hours']:.1f}"
                    ),
                    (
                        "- "
                        "Median compensation (local): "
                        f"{_format_optional_amount(livelihood['median_compensation_local'])}"
                    ),
                    (
                        "- "
                        "Local ownership share: "
                        f"{_format_optional_share(livelihood['local_ownership_share'])}"
                    ),
                    (
                        "- "
                        f"Feedback roles: {', '.join(livelihood['feedback_roles']) or 'none'}"
                    ),
                    (
                        "- "
                        f"Feedback responses: {livelihood['feedback_response_count']}"
                    ),
                    (
                        "- "
                        f"Top follow-up: {livelihood['top_follow_up'] or 'none'}"
                    ),
                    f"- Livelihood packet: {Path(report['ledger_path']).with_name('livelihood_packet.json')}",
                ]
            )
        reciprocity = report.get("reciprocity")
        if reciprocity is not None:
            lines.extend(
                [
                    "",
                    "## Reciprocity Proof Chain",
                    f"- Reciprocity ledger: {reciprocity['ledger_path']}",
                    (
                        "- "
                        f"Obligation USD: {reciprocity['summary']['total_obligation_usd']:.2f}"
                    ),
                    (
                        "- "
                        f"Routed USD: {reciprocity['summary']['total_routed_usd']:.2f}"
                    ),
                    (
                        "- "
                        f"Invariant issues: {reciprocity['summary']['invariant_issues']}"
                    ),
                    (
                        "- "
                        f"Projection warnings: {len(reciprocity['projection_warnings'])}"
                    ),
                ]
            )
        qualification = report.get("qualification")
        if qualification is not None:
            lines.extend(
                [
                    "",
                    "## Qualification",
                    f"- Approved: {qualification['approved']}",
                    f"- Integrity class: {qualification['integrity_class']}",
                    (
                        "- "
                        "Verification channels: "
                        f"{', '.join(qualification['verification_channels'])}"
                    ),
                ]
            )
        claim_explorer = report.get("claim_explorer")
        if claim_explorer is not None:
            lines.extend(
                [
                    "",
                    "## Claim Explorer",
                    f"- Claim count: {claim_explorer['claim_count']}",
                    f"- Public-ready claims: {claim_explorer['public_ready_count']}",
                    f"- Provisional claims: {claim_explorer['provisional_count']}",
                    f"- Explorer path: {self._data_dir / 'claim_explorer.json'}",
                ]
            )
        return "\n".join(lines)

    def _render_claim_card_markdown(self, claim_card: GaiaClaimCard) -> str:
        lines = [
            "# GAIA Claim Card",
            "",
            f"Claim ID: {claim_card.claim_id}",
            f"Visibility: {claim_card.visibility.value}",
            f"Project: {claim_card.project_name}",
            f"Sponsor: {claim_card.sponsor_name}",
            f"Reporting Period: {claim_card.reporting_period}",
            "",
            "## Claim",
            f"- Type: {claim_card.claim_type.value}",
            f"- Statement: {claim_card.claim_statement}",
            f"- Scope: {claim_card.claim_scope}",
            "",
            "## Integrity",
            f"- Integrity class: {claim_card.integrity_class}",
            f"- Methodology: {claim_card.methodology_ref}",
            f"- Audit status: {claim_card.audit_status.value}",
            f"- Measurement mode: {claim_card.measurement_mode.value}",
            f"- Measurement ref: {claim_card.measurement_ref}",
            (
                "- "
                f"Measurement verifier: {claim_card.measurement_verifier or 'unspecified'}"
            ),
            (
                "- "
                "Measurement boundary ref: "
                f"{claim_card.measurement_boundary_ref or 'unspecified'}"
            ),
            (
                "- "
                "Measurement claim ready: "
                f"{'yes' if claim_card.measurement_claim_ready else 'no'}"
            ),
            f"- Challenge status: {claim_card.challenge_status}",
            (
                "- "
                "Promotional use frozen: "
                f"{'yes' if claim_card.promotional_use_frozen else 'no'}"
            ),
            f"- Challenge contact: {claim_card.challenge_contact}",
            "",
            "## Challengeability",
            f"- Grievance status: {claim_card.grievance_status.value}",
            f"- Reversal status: {claim_card.reversal_status.value}",
            f"- Challenge packet: {claim_card.challenge_packet_path}",
            (
                "- "
                f"Challenge counts: total={claim_card.challenge_count}, "
                f"unresolved={claim_card.unresolved_challenge_count}, "
                f"material={claim_card.material_challenge_count}"
            ),
            f"- Remediation cases: {claim_card.remediation_case_count}",
            "",
            "## Standards",
            (
                "- "
                f"Standards profile: {', '.join(claim_card.standards_profile) or 'not_declared'}"
            ),
            f"- Ecosystem type: {claim_card.ecosystem_type or 'unspecified'}",
            f"- Boundary ref: {claim_card.boundary_ref or 'unspecified'}",
            (
                "- "
                "Observation protocols: "
                f"{', '.join(claim_card.observation_protocols) or 'none'}"
            ),
            (
                "- "
                f"Monitoring indicators: {claim_card.monitoring_indicator_count}"
            ),
            (
                "- "
                f"Planned activities: {claim_card.planned_activity_count}"
            ),
            "",
            "## Evidence",
            f"- Metering evidence refs: {len(claim_card.metering_evidence_refs)}",
            f"- Metering audit refs: {len(claim_card.metering_audit_refs)}",
            f"- Measurement packet: {claim_card.measurement_packet_path}",
            f"- Evidence refs: {len(claim_card.evidence_refs)}",
            f"- Audit refs: {len(claim_card.audit_refs)}",
            (
                "- "
                "Verification channels: "
                f"{', '.join(claim_card.verification_channels)}"
            ),
            "",
            "## Outcome",
            f"- Verified offset: {claim_card.total_verified_offset:.2f} tCO2e",
            f"- Net carbon position: {claim_card.net_carbon_position:.2f} tCO2e",
            (
                "- "
                f"Obligation routed: ${claim_card.routed_value_usd:,.2f} / "
                f"${claim_card.obligation_quantity_usd:,.2f}"
            ),
            f"- Final confidence: {claim_card.final_confidence:.2%}",
            f"- Monitoring status: {claim_card.monitoring_status}",
            f"- Remediation status: {claim_card.remediation_status}",
            "",
            "## Livelihood",
            f"- Target group: {claim_card.livelihood_target_group}",
            f"- Mode: {claim_card.livelihood_mode.value}",
            (
                "- "
                f"Participants: {claim_card.livelihood_participant_count} | "
                f"Person-hours: {claim_card.livelihood_person_hours:.1f}"
            ),
            (
                "- "
                "Median compensation (local): "
                f"{_format_optional_amount(claim_card.median_compensation_local)}"
            ),
            (
                "- "
                "Local ownership share: "
                f"{_format_optional_share(claim_card.local_ownership_share)}"
            ),
            (
                "- "
                f"Feedback responses: {claim_card.livelihood_feedback_count}"
            ),
            (
                "- "
                "Feedback roles: "
                f"{', '.join(claim_card.livelihood_feedback_roles) or 'none'}"
            ),
            f"- Livelihood packet: {claim_card.livelihood_packet_path}",
            "",
            "## Reciprocity",
            f"- Reciprocity ledger: {claim_card.reciprocity_ledger_path}",
            f"- Invariant issues: {claim_card.reciprocity_invariant_issues}",
            (
                "- "
                f"Projection warnings: {len(claim_card.reciprocity_projection_warnings)}"
            ),
        ]
        if claim_card.warnings:
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in claim_card.warnings)
        if claim_card.public_notes:
            lines.extend(["", "## Public Notes"])
            lines.extend(f"- {note}" for note in claim_card.public_notes)
        if claim_card.blockers:
            lines.extend(["", "## Blockers"])
            lines.extend(f"- {blocker}" for blocker in claim_card.blockers)
        return "\n".join(lines)

    def _render_measurement_packet_markdown(
        self,
        packet: GaiaMeasurementPacket,
    ) -> str:
        lines = [
            "# GAIA Measurement Packet",
            "",
            f"Sponsor: {packet.sponsor_name}",
            f"Model Profile: {packet.model_id}",
            f"Reporting Period: {packet.reporting_period}",
            "",
            "## Measurement",
            f"- Mode: {packet.measurement_mode.value}",
            f"- Ref: {packet.measurement_ref}",
            f"- Verifier: {packet.measurement_verifier or 'unspecified'}",
            (
                "- "
                f"Boundary ref: {packet.measurement_boundary_ref or 'unspecified'}"
            ),
            f"- Energy: {packet.energy_mwh:.2f} MWh",
            f"- Carbon intensity: {packet.carbon_intensity:.4f} tCO2e/MWh",
            f"- Emissions: {packet.emissions_tco2e:.6f} tCO2e",
            "",
            "## Evidence",
            f"- Metering evidence refs: {len(packet.metering_evidence_refs)}",
            f"- Metering audit refs: {len(packet.metering_audit_refs)}",
            (
                "- "
                "Public claim ready: "
                f"{'yes' if packet.public_claim_ready else 'no'}"
            ),
        ]
        if packet.warnings:
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in packet.warnings)
        return "\n".join(lines)

    def _render_livelihood_packet_markdown(
        self,
        packet: GaiaLivelihoodPacket,
    ) -> str:
        lines = [
            "# GAIA Livelihood Packet",
            "",
            f"Sponsor: {packet.sponsor_name}",
            f"Model Profile: {packet.model_id}",
            f"Reporting Period: {packet.reporting_period}",
            f"Visibility: {packet.visibility.value}",
            f"Project: {packet.project_name}",
            "",
            "## Transition Surface",
            f"- Target group: {packet.livelihood_target_group}",
            f"- Mode: {packet.livelihood_mode.value}",
            (
                "- "
                f"Participants: {packet.participant_count} | "
                f"Person-hours: {packet.person_hours:.1f}"
            ),
            (
                "- "
                "Median compensation (local): "
                f"{_format_optional_amount(packet.median_compensation_local)}"
            ),
            (
                "- "
                "Local ownership share: "
                f"{_format_optional_share(packet.local_ownership_share)}"
            ),
            "",
            "## Governance",
            f"- Partner credibility: {packet.partner_credibility.value}",
            f"- Due diligence ref: {packet.due_diligence_ref}",
            f"- Consent status: {packet.consent_status}",
            f"- Consent ref: {packet.consent_ref}",
            f"- Benefit sharing ref: {packet.benefit_sharing_ref}",
            f"- Grievance process ref: {packet.grievance_process_ref}",
            f"- Challenge status: {packet.challenge_status}",
            f"- Challenge contact: {packet.challenge_contact}",
            "",
            "## Feedback",
            f"- Responses: {packet.feedback_response_count}",
            (
                "- "
                f"Roles: {', '.join(packet.feedback_roles) or 'none'}"
            ),
            (
                "- "
                f"Average satisfaction: {packet.feedback_average_satisfaction:.2f}/5"
            ),
            (
                "- "
                f"Average confidence: {packet.feedback_average_confidence:.2f}"
            ),
            f"- Top follow-up: {packet.top_follow_up or 'none'}",
            "",
            "## Linked Proof",
            f"- Evidence refs: {len(packet.linked_evidence_refs)}",
            f"- Audit refs: {len(packet.linked_audit_refs)}",
            (
                "- "
                "Verification channels: "
                f"{', '.join(packet.verification_channels)}"
            ),
            f"- Reciprocity ledger: {packet.reciprocity_ledger_path}",
            f"- Pilot report: {packet.report_path}",
        ]
        return "\n".join(lines)

    def _render_challenge_packet_markdown(
        self,
        packet: GaiaChallengePacket,
    ) -> str:
        lines = [
            "# GAIA Challenge Packet",
            "",
            f"Claim ID: {packet.claim_id}",
            f"Visibility: {packet.visibility.value}",
            f"Challenge status: {packet.challenge_status}",
            f"Audit status: {packet.audit_status.value}",
            "",
            "## Challengeability",
            f"- Challenge contact: {packet.challenge_contact}",
            f"- Grievance process ref: {packet.grievance_process_ref}",
            f"- Consent status: {packet.consent_status}",
            f"- Grievance status: {packet.grievance_status.value}",
            f"- Reversal status: {packet.reversal_status.value}",
            (
                "- "
                "Promotional reuse frozen: "
                f"{'yes' if packet.freeze_promotional_use else 'no'}"
            ),
            (
                "- "
                f"Next acknowledge due: {packet.next_acknowledge_due_at.isoformat() if packet.next_acknowledge_due_at else 'none'}"
            ),
            (
                "- "
                f"Next triage due: {packet.next_triage_due_at.isoformat() if packet.next_triage_due_at else 'none'}"
            ),
            (
                "- "
                "Next initial finding due: "
                f"{packet.next_initial_finding_due_at.isoformat() if packet.next_initial_finding_due_at else 'none'}"
            ),
            (
                "- "
                f"Challenges: total={packet.challenge_count}, "
                f"unresolved={packet.unresolved_challenge_count}, "
                f"material={packet.material_challenge_count}, "
                f"resolved={packet.resolved_challenge_count}"
            ),
            f"- Remediation cases: {packet.remediation_case_count}",
            f"- Claim card: {packet.claim_card_path}",
            f"- Report: {packet.report_path}",
        ]
        if packet.public_notes:
            lines.extend(["", "## Public Notes"])
            lines.extend(f"- {note}" for note in packet.public_notes)
        if packet.service_level_notes:
            lines.extend(["", "## Service Levels"])
            lines.extend(f"- {note}" for note in packet.service_level_notes)
        if packet.challenge_records:
            lines.extend(["", "## Challenges"])
            lines.extend(
                f"- {record.challenge_id}: {record.ground.value} [{record.state.value}] {record.summary}"
                for record in packet.challenge_records
            )
        if packet.remediation_cases:
            lines.extend(["", "## Remediation"])
            lines.extend(
                f"- {case.case_id}: {case.outcome.value} [{case.step.value}] {case.summary}"
                for case in packet.remediation_cases
            )
        return "\n".join(lines)

    def _render_claim_explorer_markdown(
        self,
        explorer: GaiaClaimExplorer,
    ) -> str:
        lines = [
            "# GAIA Claim Explorer",
            "",
            f"Generated at: {explorer.generated_at.isoformat()}",
            f"Claims: {explorer.claim_count}",
            f"Public-ready: {explorer.public_ready_count}",
            f"Provisional: {explorer.provisional_count}",
            f"Challenged: {explorer.challenged_count}",
        ]
        if explorer.entries:
            lines.extend(["", "## Entries"])
            for entry in explorer.entries:
                lines.extend(
                    [
                        (
                            "- "
                            f"{entry.claim_id}: {entry.visibility.value} | "
                            f"{entry.project_name} | confidence={entry.final_confidence:.2%} | "
                            f"challenge={entry.challenge_status} | frozen={'yes' if entry.promotional_use_frozen else 'no'}"
                        ),
                        f"Statement: {entry.claim_statement}",
                        f"Claim card: {entry.claim_card_path}",
                        f"Challenge packet: {entry.challenge_packet_path}",
                    ]
                )
        return "\n".join(lines)

    def _pilot_verdicts(
        self,
        project: GaiaProject,
        offset_id: str,
    ) -> list[OracleVerdict]:
        channels = []
        for channel in project.verification_channels:
            normalized = _normalize_channel(channel)
            if normalized in ORACLE_TYPES and normalized not in channels:
                channels.append(normalized)

        for fallback in ORACLE_TYPES:
            if fallback not in channels:
                channels.append(fallback)
            if len(channels) >= 4:
                break

        verdicts: list[OracleVerdict] = []
        base_confidence = 0.79 if project.is_verified else 0.68
        for index, oracle_type in enumerate(channels[:4]):
            confidence = min(base_confidence + (index * 0.04), 0.95)
            verdicts.append(
                OracleVerdict(
                    oracle_type=oracle_type,
                    target_id=offset_id,
                    confidence=confidence,
                    agrees_with_claim=True,
                    evidence_summary=(
                        f"{oracle_type.replace('_', ' ')} confirms staged pilot "
                        f"for {project.name} in {project.region}."
                    ),
                    evidence_hash=f"{project.project_id}-{oracle_type[:8]}-{index}",
                )
            )
        return verdicts

    @staticmethod
    def _has_viable_partner(partner: str) -> bool:
        normalized = partner.strip().lower()
        return normalized not in {"", "absent", "unknown", "none", "tbd"}


def _normalize_channel(channel: str) -> str:
    normalized = channel.strip().lower()
    alias_map = {
        "ground": "iot_sensor",
        "ground_sensor": "iot_sensor",
        "field": "human_auditor",
        "auditor": "human_auditor",
        "human": "human_auditor",
        "stats_model": "statistical_model",
    }
    return alias_map.get(normalized, normalized)


def _normalize_standard_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _format_optional_amount(value: float | None) -> str:
    if value is None:
        return "unspecified"
    return f"{value:,.2f}"


def _format_optional_share(value: float | None) -> str:
    if value is None:
        return "unspecified"
    return f"{value:.0%}"


def _new_record_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _add_business_days(start: datetime, days: int) -> datetime:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _earliest_datetime(
    current: datetime | None,
    candidate: datetime,
) -> datetime:
    if current is None or candidate < current:
        return candidate
    return current


def _format_service_level_note(
    label: str,
    due_at: datetime,
    now: datetime,
) -> str:
    status = "overdue" if now > due_at else "due"
    return f"GOVERNANCE: {label} service level is {status} by {due_at.isoformat()}."


def _unique_strings(values: Sequence[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return tuple(ordered)


def _reporting_period_bounds(reporting_period: str) -> tuple[date, date]:
    cleaned = reporting_period.strip()
    if len(cleaned) == 7 and cleaned[:4].isdigit() and cleaned[4:6] == "-Q":
        year = int(cleaned[:4])
        quarter = int(cleaned[6])
        month_map = {
            1: (1, 3),
            2: (4, 6),
            3: (7, 9),
            4: (10, 12),
        }
        if quarter not in month_map:
            raise ValueError(f"unsupported reporting quarter '{reporting_period}'")
        start_month, end_month = month_map[quarter]
        end_day = calendar.monthrange(year, end_month)[1]
        return date(year, start_month, 1), date(year, end_month, end_day)
    if len(cleaned) == 7 and cleaned[:4].isdigit() and cleaned[4] == "-":
        year = int(cleaned[:4])
        month = int(cleaned[5:7])
        end_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, end_day)
    if len(cleaned) == 4 and cleaned.isdigit():
        year = int(cleaned)
        return date(year, 1, 1), date(year, 12, 31)
    raise ValueError(
        "unsupported reporting_period format; use YYYY-QN, YYYY-MM, or YYYY"
    )


def _confidence_from_measurement_mode(
    measurement_mode: GaiaMeasurementMode,
) -> ReciprocityConfidenceLevel:
    if measurement_mode is GaiaMeasurementMode.MEASURED:
        return ReciprocityConfidenceLevel.HIGH
    if measurement_mode is GaiaMeasurementMode.DISCLOSED:
        return ReciprocityConfidenceLevel.MEDIUM
    return ReciprocityConfidenceLevel.LOW


def _confidence_from_evidence_type(
    evidence_type: EvidenceType,
) -> ReciprocityConfidenceLevel:
    if evidence_type in {
        EvidenceType.SATELLITE,
        EvidenceType.SENSOR,
        EvidenceType.GROUND_AUDIT,
    }:
        return ReciprocityConfidenceLevel.HIGH
    if evidence_type in {EvidenceType.FINANCIAL, EvidenceType.SURVEY}:
        return ReciprocityConfidenceLevel.MEDIUM
    return ReciprocityConfidenceLevel.LOW


def _obligation_basis_from_rule(rule: str) -> ReciprocityObligationBasis:
    lowered = rule.strip().lower()
    if "pilot" in lowered:
        return ReciprocityObligationBasis.PILOT_RULE
    if "policy" in lowered:
        return ReciprocityObligationBasis.POLICY
    if "pledge" in lowered:
        return ReciprocityObligationBasis.PLEDGE
    return ReciprocityObligationBasis.FORMULA


def _project_type_from_value(project_type: str) -> ReciprocityProjectType:
    lowered = project_type.strip().lower()
    if any(token in lowered for token in {"mangrove", "carbon", "removal"}):
        return ReciprocityProjectType.CARBON_REMOVAL
    if "watershed" in lowered:
        return ReciprocityProjectType.WATERSHED
    if "methane" in lowered:
        return ReciprocityProjectType.METHANE
    if any(token in lowered for token in {"biodiversity", "agroforestry", "corridor"}):
        return ReciprocityProjectType.BIODIVERSITY
    if any(token in lowered for token in {"resilience", "coastal"}):
        return ReciprocityProjectType.RESILIENCE
    if any(token in lowered for token in {"livelihood", "training"}):
        return ReciprocityProjectType.LIVELIHOOD_TRANSITION
    return ReciprocityProjectType.MIXED


def _integrity_class_from_value(value: str) -> ReciprocityIntegrityClass:
    lowered = value.strip().lower()
    try:
        return ReciprocityIntegrityClass(lowered)
    except ValueError:
        return ReciprocityIntegrityClass.EMERGING


def _consent_status_from_value(value: str) -> ReciprocityConsentStatus:
    lowered = value.strip().lower()
    if lowered in {"documented", "verified", "granted", "yes"}:
        return ReciprocityConsentStatus.YES
    if lowered in {"no", "denied"}:
        return ReciprocityConsentStatus.NO
    return ReciprocityConsentStatus.UNKNOWN


def _exposure_class_from_model(model_id: str) -> ReciprocityExposureClass:
    lowered = model_id.strip().lower()
    if "train" in lowered:
        return ReciprocityExposureClass.TRAINING
    if "automation" in lowered:
        return ReciprocityExposureClass.AUTOMATION_PROGRAM
    if "enterprise" in lowered:
        return ReciprocityExposureClass.ENTERPRISE_AI
    return ReciprocityExposureClass.INFERENCE


def _evidence_type_from_ref(source_ref: str) -> EvidenceType:
    lowered = source_ref.strip().lower()
    if "satellite" in lowered:
        return EvidenceType.SATELLITE
    if "sensor" in lowered or "iot" in lowered:
        return EvidenceType.SENSOR
    if "audit" in lowered or "ground" in lowered or "field" in lowered:
        return EvidenceType.GROUND_AUDIT
    if "financial" in lowered or "payment" in lowered:
        return EvidenceType.FINANCIAL
    if "survey" in lowered or "community" in lowered:
        return EvidenceType.SURVEY
    return EvidenceType.POLICY


def _outcome_status_for_claim(
    *,
    verified_offset: float,
    integrity_class: ReciprocityIntegrityClass,
    evidence_refs: Sequence[str],
    audit_refs: Sequence[str],
    visibility: GaiaClaimVisibility,
) -> ReciprocityOutcomeStatus:
    if verified_offset <= 0:
        return ReciprocityOutcomeStatus.ESTIMATED
    if (
        integrity_class is not ReciprocityIntegrityClass.EXPERIMENTAL
        and evidence_refs
        and audit_refs
    ):
        return (
            ReciprocityOutcomeStatus.VERIFIED
            if visibility is GaiaClaimVisibility.PUBLIC_READY
            else ReciprocityOutcomeStatus.MEASURED
        )
    return ReciprocityOutcomeStatus.MEASURED


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gaia-platform")
    subparsers = parser.add_subparsers(dest="command")

    dashboard = subparsers.add_parser(
        "dashboard",
        help="Render the shipped GAIA terminal dashboard",
    )
    dashboard.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dharma" / "gaia_platform",
        help="Directory for GAIA pilot artifacts",
    )
    dashboard.add_argument(
        "--model",
        default="anthropic_claude_ops",
        help="Model/operator profile to match against GAIA projects",
    )
    dashboard.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="Number of recommendations to render",
    )
    dashboard.add_argument(
        "--energy-mwh",
        type=float,
        default=12.0,
        help="Pilot compute energy used for the staged chain",
    )
    dashboard.add_argument(
        "--carbon-intensity",
        type=float,
        default=0.35,
        help="Pilot carbon intensity in tons CO2e per MWh",
    )

    pilot_report = subparsers.add_parser(
        "pilot-report",
        help="Stage a GAIA pilot and export monitoring plus feedback artifacts",
    )
    pilot_report.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dharma" / "gaia_platform",
        help="Directory for GAIA pilot artifacts",
    )
    pilot_report.add_argument(
        "--model",
        default="anthropic_claude_ops",
        help="Model/operator profile to match against GAIA projects",
    )
    pilot_report.add_argument(
        "--project-id",
        default=None,
        help="Optional approved GAIA project identifier to stage explicitly",
    )
    pilot_report.add_argument(
        "--energy-mwh",
        type=float,
        default=12.0,
        help="Pilot compute energy used for the staged chain",
    )
    pilot_report.add_argument(
        "--carbon-intensity",
        type=float,
        default=0.35,
        help="Pilot carbon intensity in tons CO2e per MWh",
    )
    pilot_report.add_argument(
        "--feedback-file",
        type=Path,
        default=None,
        help="Optional JSON file containing structured feedback entries",
    )

    pilot_intake_report = subparsers.add_parser(
        "pilot-intake-report",
        help="Build a qualified GAIA pilot packet from a structured intake file",
    )
    pilot_intake_report.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dharma" / "gaia_platform",
        help="Directory for GAIA pilot artifacts",
    )
    pilot_intake_report.add_argument(
        "--intake-file",
        type=Path,
        required=True,
        help="JSON file containing a GaiaPilotIntake payload",
    )
    pilot_intake_report.add_argument(
        "--feedback-file",
        type=Path,
        default=None,
        help="Optional JSON file containing structured feedback entries",
    )

    initiative_pilot_report = subparsers.add_parser(
        "initiative-pilot-report",
        help="Build a qualified GAIA pilot packet from a standards-aligned initiative file",
    )
    initiative_pilot_report.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dharma" / "gaia_platform",
        help="Directory for GAIA pilot artifacts",
    )
    initiative_pilot_report.add_argument(
        "--packet-file",
        type=Path,
        required=True,
        help="JSON file containing a GaiaInitiativePilotPacket payload",
    )
    initiative_pilot_report.add_argument(
        "--feedback-file",
        type=Path,
        default=None,
        help="Optional JSON file containing structured feedback entries",
    )

    challenge_claim = subparsers.add_parser(
        "challenge-claim",
        help="Record a typed public challenge against an existing GAIA claim card",
    )
    challenge_claim.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dharma" / "gaia_platform",
        help="Directory for GAIA pilot artifacts",
    )
    challenge_claim.add_argument(
        "--claim-card-file",
        type=Path,
        required=True,
        help="JSON file containing the existing GaiaClaimCard payload",
    )
    challenge_claim.add_argument(
        "--challenge-file",
        type=Path,
        required=True,
        help="JSON file containing a GaiaChallengeRecord payload",
    )

    remediate_claim = subparsers.add_parser(
        "remediate-claim",
        help="Record a typed remediation case against an existing GAIA claim card",
    )
    remediate_claim.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dharma" / "gaia_platform",
        help="Directory for GAIA pilot artifacts",
    )
    remediate_claim.add_argument(
        "--claim-card-file",
        type=Path,
        required=True,
        help="JSON file containing the existing GaiaClaimCard payload",
    )
    remediate_claim.add_argument(
        "--remediation-file",
        type=Path,
        required=True,
        help="JSON file containing a GaiaRemediationCase payload",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint used by tests and direct module execution."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "dashboard":
        platform = GaiaPlatform(data_dir=args.data_dir)
        print(
            platform.render_dashboard(
                model_id=args.model,
                top_n=args.top_n,
                energy_mwh=args.energy_mwh,
                carbon_intensity=args.carbon_intensity,
            )
        )
        return 0

    if args.command == "pilot-report":
        platform = GaiaPlatform(data_dir=args.data_dir)
        feedback_entries = None
        if args.feedback_file is not None:
            feedback_entries = json.loads(args.feedback_file.read_text(encoding="utf-8"))
        report = platform.build_pilot_report(
            model_id=args.model,
            project_id=args.project_id,
            energy_mwh=args.energy_mwh,
            carbon_intensity=args.carbon_intensity,
            feedback_entries=feedback_entries,
        )
        print(
            "GAIA pilot report written: "
            f"{report['json_path']} | markdown={report['markdown_path']}"
        )
        return 0

    if args.command == "pilot-intake-report":
        platform = GaiaPlatform(data_dir=args.data_dir)
        feedback_entries = None
        if args.feedback_file is not None:
            feedback_entries = json.loads(args.feedback_file.read_text(encoding="utf-8"))
        intake = GaiaPilotIntake.model_validate_json(
            args.intake_file.read_text(encoding="utf-8")
        )
        report = platform.build_intake_pilot_report(
            intake=intake,
            feedback_entries=feedback_entries,
        )
        print(
            "GAIA intake pilot packet written: "
            f"{report['json_path']} | claim_card={report['claim_card_path']}"
        )
        return 0

    if args.command == "initiative-pilot-report":
        from dharma_swarm.gaia_initiative import GaiaInitiativePilotPacket

        platform = GaiaPlatform(data_dir=args.data_dir)
        feedback_entries = None
        if args.feedback_file is not None:
            feedback_entries = json.loads(args.feedback_file.read_text(encoding="utf-8"))
        packet = GaiaInitiativePilotPacket.model_validate_json(
            args.packet_file.read_text(encoding="utf-8")
        )
        report = platform.build_initiative_pilot_report(
            packet=packet,
            feedback_entries=feedback_entries,
        )
        print(
            "GAIA initiative pilot packet written: "
            f"{report['json_path']} | initiative_packet={report['initiative_packet_path']}"
        )
        return 0

    if args.command == "challenge-claim":
        platform = GaiaPlatform(data_dir=args.data_dir)
        result = platform.submit_claim_challenge(
            claim_card_path=args.claim_card_file,
            challenge=json.loads(args.challenge_file.read_text(encoding="utf-8")),
        )
        print(
            "GAIA claim challenge recorded: "
            f"{result['challenge_path']} | claim_card={result['claim_card_path']}"
        )
        return 0

    if args.command == "remediate-claim":
        platform = GaiaPlatform(data_dir=args.data_dir)
        result = platform.apply_claim_remediation(
            claim_card_path=args.claim_card_file,
            remediation=json.loads(args.remediation_file.read_text(encoding="utf-8")),
        )
        print(
            "GAIA claim remediation recorded: "
            f"{result['challenge_path']} | claim_card={result['claim_card_path']}"
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "GaiaChallengeGround",
    "GaiaChallengePacket",
    "GaiaChallengeRecord",
    "GaiaChallengeState",
    "GaiaClaimExplorer",
    "GaiaClaimExplorerEntry",
    "GaiaClaimCard",
    "GaiaClaimVisibility",
    "GaiaGrievanceStatus",
    "GaiaLivelihoodPacket",
    "GaiaMeasurementPacket",
    "GaiaMeasurementMode",
    "GaiaMonitoringSnapshot",
    "GaiaPartnerCredibility",
    "GaiaPilotIntake",
    "GaiaPlatform",
    "GaiaProject",
    "GaiaQualificationDecision",
    "GaiaRecommendation",
    "GaiaRemediationCase",
    "GaiaRemediationOutcome",
    "GaiaRemediationStep",
    "GaiaReversalStatus",
    "GaiaStrategy",
    "GaiaUserFeedback",
    "main",
]
