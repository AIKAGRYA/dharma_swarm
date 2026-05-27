"""Schemas for the Darshan artifact transaction."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class DarshanBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimKind(str, Enum):
    FACT = "fact"
    INTERPRETATION = "interpretation"
    FORECAST = "forecast"
    CAUSAL = "causal_claim"
    NORMATIVE = "normative_claim"
    QUOTATION = "quotation"
    SYNTHESIS = "synthesis"


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    PUBLISHED = "published"
    CORRECTED = "corrected"
    WITHDRAWN = "withdrawn"
    CHALLENGED = "challenged"


class EvidenceLane(str, Enum):
    DIRECT = "direct"
    OBSERVED = "observed"
    PROXY = "proxy"
    INFERENCE = "inference"
    SPECULATIVE = "speculative"


class SourceTrustStatus(str, Enum):
    UNEVALUATED = "unevaluated"
    WEAK = "weak"
    USABLE = "usable"
    STRONG = "strong"


class SourceType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPERT = "expert"
    PUBLIC_RECORD = "public_record"
    DATASET = "dataset"
    MODEL_OUTPUT = "model_output"
    OPERATOR_NOTE = "operator_note"


class PolsiaTrack(str, Enum):
    COLLABORATOR = "collaborator"
    OBSERVATORY = "observatory"


class ExternalOperator(str, Enum):
    COFOUNDER = "cofounder"
    POLSIA = "polsia"
    COMPANY_CO = "company_co"
    OPENCLAW = "openclaw"
    CUSTOM = "custom"


class ExternalOperatorTrack(str, Enum):
    COLLABORATOR = "collaborator"
    OBSERVATORY = "observatory"
    BENCHMARK = "benchmark"


class SourceRecord(DarshanBaseModel):
    source_id: str = Field(default_factory=lambda: new_id("src"))
    canonical_url: str = ""
    final_url: str = ""
    archive_url: str = ""
    capture_timestamp: str = Field(default_factory=utc_now_iso)
    content_hash: str = ""
    receipt_path: str = ""
    source_type: SourceType = SourceType.SECONDARY
    source_independence_family: str = ""
    license_or_reuse_status: str = ""
    accessed_at: str = Field(default_factory=utc_now_iso)
    excerpt_locations: list[str] = Field(default_factory=list)
    extracted_claims: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trust_status: SourceTrustStatus = SourceTrustStatus.UNEVALUATED
    safety_privacy_notes: list[str] = Field(default_factory=list)
    consent_status: str = ""


class SourcePack(DarshanBaseModel):
    artifact_id: str
    sources: list[SourceRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ClaimRecord(DarshanBaseModel):
    claim_id: str = Field(default_factory=lambda: new_id("claim"))
    artifact_id: str
    claim_text: str
    claim_kind: ClaimKind = ClaimKind.FACT
    scope: str = ""
    status: ClaimStatus = ClaimStatus.PROPOSED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_lane: EvidenceLane = EvidenceLane.INFERENCE
    evidence_refs: list[str] = Field(default_factory=list)
    counterclaims: list[str] = Field(default_factory=list)
    what_would_change_this: str = ""
    interpretation_boundary: str = ""
    public_wording_limit: str = ""
    last_reviewed_at: str = Field(default_factory=utc_now_iso)
    correction_parent_id: str = ""

    @field_validator("claim_text")
    @classmethod
    def _claim_text_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim_text is required")
        return value


class ClaimLedger(DarshanBaseModel):
    artifact_id: str
    claims: list[ClaimRecord] = Field(default_factory=list)


class CounterframeRecord(DarshanBaseModel):
    frame_id: str = Field(default_factory=lambda: new_id("frame"))
    artifact_id: str
    frame_summary: str
    strongest_case: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    response: str = ""


class CounterframeLedger(DarshanBaseModel):
    artifact_id: str
    counterframes: list[CounterframeRecord] = Field(default_factory=list)


class AttentionLedger(DarshanBaseModel):
    artifact_id: str
    starting_confusion: str = ""
    intended_attentional_movement: str = ""
    reading_modes_supported: list[str] = Field(default_factory=list)
    anti_feed_design_choices: list[str] = Field(default_factory=list)
    pause_or_reflection_points: list[str] = Field(default_factory=list)
    evidence_access_pattern: str = ""
    expected_clarity_signal: str = ""
    expected_calm_focus_signal: str = ""
    manipulation_risks: list[str] = Field(default_factory=list)
    reader_feedback_observed: list[str] = Field(default_factory=list)


class GateDecisionRecord(DarshanBaseModel):
    gate: str
    verdict: Literal["pass", "warn", "fail", "not_run"] = "not_run"
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    reviewed_by: str = ""
    reviewed_at: str = Field(default_factory=utc_now_iso)


class GateDecisionLedger(DarshanBaseModel):
    artifact_id: str
    gates: list[GateDecisionRecord] = Field(default_factory=list)


class DecisionDelta(DarshanBaseModel):
    artifact_id: str
    delta_summary: str = ""
    changed_swarm_belief: str = ""
    changed_routing: str = ""
    new_task_ids: list[str] = Field(default_factory=list)
    affected_cells: list[str] = Field(default_factory=lambda: ["DARSHAN"])
    followup_owner: str = ""
    review_by: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class PolsiaHandoff(DarshanBaseModel):
    artifact_id: str
    handoff_summary: str = ""
    allowed_scope: list[str] = Field(default_factory=list)
    forbidden_scope: list[str] = Field(default_factory=list)
    requested_outputs: list[str] = Field(default_factory=list)
    logging_required: bool = True


class BundleManifest(DarshanBaseModel):
    artifact_id: str
    title: str
    slug: str
    season: str = "After the Feed"
    bundle_path: str
    created_at: str = Field(default_factory=utc_now_iso)
    required_files: list[str] = Field(default_factory=list)
    content_hashes: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolsiaObservation(DarshanBaseModel):
    interaction_id: str = Field(default_factory=lambda: new_id("polsia"))
    timestamp: str = Field(default_factory=utc_now_iso)
    track: PolsiaTrack
    prompt_given: str
    expected_output: str = ""
    polsia_actions_observed: list[str] = Field(default_factory=list)
    agents_or_roles_visible: list[str] = Field(default_factory=list)
    latency_minutes: float = Field(default=0.0, ge=0.0)
    output_paths_or_links: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    human_intervention_required: bool = False
    missing_receipts: list[str] = Field(default_factory=list)
    reusable_operator_pattern: str = ""
    dharma_swarm_followup_task: str = ""

    @field_validator("prompt_given")
    @classmethod
    def _prompt_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt_given is required")
        return value


class ExternalOperatorObservation(DarshanBaseModel):
    interaction_id: str = Field(default_factory=lambda: new_id("operator"))
    timestamp: str = Field(default_factory=utc_now_iso)
    operator: ExternalOperator = ExternalOperator.COFOUNDER
    track: ExternalOperatorTrack = ExternalOperatorTrack.COLLABORATOR
    venture_cell: str = "DARSHAN"
    surface: str = ""
    session_phase: str = ""
    prompt_given: str
    expected_output: str = ""
    operator_response_summary: str = ""
    actions_observed: list[str] = Field(default_factory=list)
    agents_or_roles_visible: list[str] = Field(default_factory=list)
    artifacts_or_urls: list[str] = Field(default_factory=list)
    screenshot_refs: list[str] = Field(default_factory=list)
    capabilities_observed: list[str] = Field(default_factory=list)
    limitations_observed: list[str] = Field(default_factory=list)
    allowed_scope_boundary: list[str] = Field(default_factory=list)
    forbidden_scope_boundary: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    autonomy_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    human_intervention_required: bool = False
    missing_receipts: list[str] = Field(default_factory=list)
    reusable_operator_pattern: str = ""
    dharma_swarm_design_implication: str = ""
    followup_task: str = ""

    @field_validator("prompt_given")
    @classmethod
    def _external_prompt_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt_given is required")
        return value
