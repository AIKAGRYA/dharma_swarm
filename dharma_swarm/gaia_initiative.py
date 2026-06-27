"""Standards-aligned GAIA initiative packets.

This module fills the gap between the conceptual GAIA-ECO architecture and the
already-shipped pilot/claim-card surface in ``gaia_platform.py``.

It models a restoration initiative in a FERM-aligned shape with explicit:

- area and ecosystem metadata
- partner diligence and consent records
- monitoring indicators
- observation-source protocols (SensorThings, STAC, Darwin Core, manual)

The packet can be converted into the narrower ``GaiaPilotIntake`` used by the
current GAIA runtime without inventing a parallel stack.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class GaiaInitiativeMeasurementMode(str, Enum):
    """Measurement source status for the pilot activity."""

    MEASURED = "measured"
    ESTIMATED = "estimated"
    DISCLOSED = "disclosed"


class GaiaInitiativePartnerCredibility(str, Enum):
    """Qualification state for the named community partner."""

    CREDIBLE = "credible"
    PROVISIONAL = "provisional"
    UNKNOWN = "unknown"


class GaiaInitiativeIntegrityClass(str, Enum):
    """Public integrity vocabulary for initiative intake."""

    HIGH_INTEGRITY = "high_integrity"
    EMERGING = "emerging"
    EXPERIMENTAL = "experimental"


class GaiaConsentStatus(str, Enum):
    """Consent readiness for public-facing pilot packets."""

    DOCUMENTED = "documented"
    PENDING = "pending"
    UNKNOWN = "unknown"


class GaiaObservationProtocol(str, Enum):
    """Observation or evidence source profile attached to the initiative."""

    FERM = "ferm"
    SENSORTHINGS = "sensorthings"
    STAC = "stac"
    DARWIN_CORE = "darwin_core"
    MANUAL = "manual"


class GaiaIndicatorCategory(str, Enum):
    """Monitoring indicator category."""

    BIOPHYSICAL = "biophysical"
    SOCIOECONOMIC = "socioeconomic"
    GOVERNANCE = "governance"


class GaiaInitiativeArea(BaseModel):
    """Core site metadata for a restoration initiative."""

    country: str
    region: str
    hectares: float = Field(gt=0.0)
    ecosystem_type: str
    boundary_ref: str

    @field_validator("country", "region", "ecosystem_type", "boundary_ref")
    @classmethod
    def non_blank_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required area fields must not be blank")
        return cleaned


class GaiaInitiativePartner(BaseModel):
    """Named operator and community-partner diligence surface."""

    project_operator: str
    community_partner: str
    partner_credibility: GaiaInitiativePartnerCredibility
    due_diligence_ref: str

    @field_validator("project_operator", "community_partner", "due_diligence_ref")
    @classmethod
    def non_blank_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required partner fields must not be blank")
        return cleaned


class GaiaInitiativeConsent(BaseModel):
    """Consent, benefit-sharing, and grievance references."""

    consent_status: GaiaConsentStatus = GaiaConsentStatus.UNKNOWN
    consent_ref: str = ""
    benefit_sharing_ref: str = ""
    grievance_process_ref: str = ""

    @field_validator("consent_ref", "benefit_sharing_ref", "grievance_process_ref")
    @classmethod
    def strip_optional_refs(cls, value: str) -> str:
        return value.strip()


class GaiaMonitoringIndicator(BaseModel):
    """FERM-style indicator spanning biophysical, socioeconomic, or governance lanes."""

    indicator_id: str
    label: str
    category: GaiaIndicatorCategory
    unit: str
    baseline_value: float
    target_value: float
    cadence: str
    source_ref: str

    @field_validator("indicator_id", "label", "unit", "cadence", "source_ref")
    @classmethod
    def non_blank_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required indicator fields must not be blank")
        return cleaned


class GaiaObservationSource(BaseModel):
    """Attached observation or evidence source."""

    protocol: GaiaObservationProtocol
    source_ref: str
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_ref")
    @classmethod
    def non_blank_source_ref(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source_ref must not be blank")
        return cleaned

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()


class GaiaPilotMeasurementContract(BaseModel):
    """Canonical exposure-to-obligation contract for one reporting period."""

    model_id: str
    sponsor_name: str
    reporting_period: str
    measurement_mode: GaiaInitiativeMeasurementMode
    energy_mwh: float = Field(gt=0.0)
    carbon_intensity: float = Field(ge=0.0)
    measurement_ref: str
    obligation_rule: str
    challenge_contact: str
    measurement_verifier: str = ""
    measurement_boundary_ref: str = ""
    metering_evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    metering_audit_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator(
        "model_id",
        "sponsor_name",
        "reporting_period",
        "measurement_ref",
        "obligation_rule",
        "challenge_contact",
    )
    @classmethod
    def non_blank_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required contract fields must not be blank")
        return cleaned

    @field_validator("measurement_verifier", "measurement_boundary_ref")
    @classmethod
    def strip_optional_refs(cls, value: str) -> str:
        return value.strip()

    @field_validator("metering_evidence_refs", "metering_audit_refs")
    @classmethod
    def strip_ref_tuples(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.strip() for value in values if value.strip())


class GaiaRestorationInitiative(BaseModel):
    """Standards-aligned restoration initiative that can feed the GAIA pilot loop."""

    initiative_id: str
    initiative_name: str
    project_type: str
    description: str
    area: GaiaInitiativeArea
    carbon_potential_tons_yr: float = Field(gt=0.0)
    labor_needed: int = Field(ge=0)
    funding_gap_usd: float = Field(gt=0.0)
    verification_status: str = "verified"
    integrity_class: GaiaInitiativeIntegrityClass
    methodology_ref: str
    livelihood_target_group: str
    partners: GaiaInitiativePartner
    consent: GaiaInitiativeConsent
    planned_activities: tuple[str, ...] = Field(default_factory=tuple)
    verification_channels: tuple[str, ...] = Field(default_factory=tuple)
    monitoring_indicators: tuple[GaiaMonitoringIndicator, ...]
    observation_sources: tuple[GaiaObservationSource, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    audit_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator(
        "initiative_id",
        "initiative_name",
        "project_type",
        "description",
        "verification_status",
        "methodology_ref",
        "livelihood_target_group",
    )
    @classmethod
    def non_blank_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required initiative fields must not be blank")
        return cleaned

    @field_validator("planned_activities", "verification_channels", "evidence_refs", "audit_refs")
    @classmethod
    def strip_string_tuples(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.strip() for value in values if value.strip())

    @field_validator("monitoring_indicators")
    @classmethod
    def require_monitoring_indicators(
        cls,
        indicators: tuple[GaiaMonitoringIndicator, ...],
    ) -> tuple[GaiaMonitoringIndicator, ...]:
        if not indicators:
            raise ValueError("at least one monitoring indicator is required")
        return indicators

    @property
    def observation_protocols(self) -> tuple[str, ...]:
        protocols = {source.protocol.value for source in self.observation_sources}
        return tuple(sorted(protocols))


class GaiaInitiativePilotPacket(BaseModel):
    """Combined standards-aligned initiative plus pilot measurement contract."""

    contract: GaiaPilotMeasurementContract
    initiative: GaiaRestorationInitiative
    standards_profile: tuple[str, ...] = (
        "FERM",
        "SensorThings",
        "STAC",
        "Darwin Core",
    )

    @field_validator("standards_profile")
    @classmethod
    def strip_standards_profile(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(value.strip() for value in values if value.strip())
        if not cleaned:
            raise ValueError("standards_profile must not be empty")
        return cleaned

    def initiative_summary(self) -> dict[str, Any]:
        """Return the auditable standards-oriented summary used in reports."""

        return {
            "initiative_id": self.initiative.initiative_id,
            "initiative_name": self.initiative.initiative_name,
            "ecosystem_type": self.initiative.area.ecosystem_type,
            "boundary_ref": self.initiative.area.boundary_ref,
            "planned_activity_count": len(self.initiative.planned_activities),
            "monitoring_indicator_count": len(self.initiative.monitoring_indicators),
            "observation_protocols": list(self.initiative.observation_protocols),
            "standards_profile": list(self.standards_profile),
        }

    def to_pilot_intake(self) -> Any:
        """Convert the standards-aligned packet into the shipped GAIA intake surface."""

        from dharma_swarm.gaia_platform import (
            GaiaMeasurementMode,
            GaiaPartnerCredibility,
            GaiaPilotIntake,
            GaiaProject,
        )

        project = GaiaProject(
            project_id=self.initiative.initiative_id,
            name=self.initiative.initiative_name,
            project_type=self.initiative.project_type,
            country=self.initiative.area.country,
            region=self.initiative.area.region,
            hectares=self.initiative.area.hectares,
            carbon_potential_tons_yr=self.initiative.carbon_potential_tons_yr,
            labor_needed=self.initiative.labor_needed,
            funding_gap_usd=self.initiative.funding_gap_usd,
            verification_status=self.initiative.verification_status,
            community_partner=self.initiative.partners.community_partner,
            description=self.initiative.description,
            verification_channels=self.initiative.verification_channels,
        )
        return GaiaPilotIntake(
            model_id=self.contract.model_id,
            sponsor_name=self.contract.sponsor_name,
            reporting_period=self.contract.reporting_period,
            project=project,
            measurement_mode=GaiaMeasurementMode(self.contract.measurement_mode.value),
            energy_mwh=self.contract.energy_mwh,
            carbon_intensity=self.contract.carbon_intensity,
            methodology_ref=self.initiative.methodology_ref,
            measurement_ref=self.contract.measurement_ref,
            obligation_rule=self.contract.obligation_rule,
            project_operator=self.initiative.partners.project_operator,
            integrity_class=self.initiative.integrity_class.value,
            partner_credibility=GaiaPartnerCredibility(
                self.initiative.partners.partner_credibility.value
            ),
            due_diligence_ref=self.initiative.partners.due_diligence_ref,
            consent_status=self.initiative.consent.consent_status.value,
            consent_ref=self.initiative.consent.consent_ref,
            benefit_sharing_ref=self.initiative.consent.benefit_sharing_ref,
            grievance_process_ref=self.initiative.consent.grievance_process_ref,
            challenge_contact=self.contract.challenge_contact,
            measurement_verifier=self.contract.measurement_verifier,
            measurement_boundary_ref=self.contract.measurement_boundary_ref,
            ecosystem_type=self.initiative.area.ecosystem_type,
            boundary_ref=self.initiative.area.boundary_ref,
            planned_activities=self.initiative.planned_activities,
            standards_profile=self.standards_profile,
            monitoring_indicators=tuple(
                indicator.model_dump(mode="json")
                for indicator in self.initiative.monitoring_indicators
            ),
            observation_protocols=self.initiative.observation_protocols,
            metering_evidence_refs=self.contract.metering_evidence_refs,
            metering_audit_refs=self.contract.metering_audit_refs,
            livelihood_target_group=self.initiative.livelihood_target_group,
            evidence_refs=self.initiative.evidence_refs,
            audit_refs=self.initiative.audit_refs,
            verification_channels=self.initiative.verification_channels,
        )


__all__ = [
    "GaiaConsentStatus",
    "GaiaIndicatorCategory",
    "GaiaInitiativeArea",
    "GaiaInitiativeConsent",
    "GaiaInitiativeIntegrityClass",
    "GaiaInitiativeMeasurementMode",
    "GaiaInitiativePartner",
    "GaiaInitiativePartnerCredibility",
    "GaiaInitiativePilotPacket",
    "GaiaMonitoringIndicator",
    "GaiaObservationProtocol",
    "GaiaObservationSource",
    "GaiaPilotMeasurementContract",
    "GaiaRestorationInitiative",
]
