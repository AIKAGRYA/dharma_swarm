"""Livelihood Loom ontology records and public-proof guards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from uuid import uuid4


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class ConsentLevel(StrEnum):
    PUBLIC_ONLY = "public_only"
    INTERNAL_USE = "internal_use"
    DIRECT_CONTACT_APPROVED = "direct_contact_approved"
    PUBLISH_APPROVED = "publish_approved"
    OPT_OUT = "opt_out"
    BLOCKED = "blocked"


class EvidenceLevel(StrEnum):
    PUBLIC_SOURCE = "public_source"
    SOURCE_VERIFIED = "source_verified"
    OPERATOR_CONTACTED = "operator_contacted"
    CONSENTED = "consented"
    MEASURED = "measured"
    AUDITED = "audited"


class RiskClass(StrEnum):
    LOW = "low"
    PRIVACY_SENSITIVE = "privacy_sensitive"
    WORKER_HARM_SENSITIVE = "worker_harm_sensitive"
    FINANCIAL_RISK = "financial_risk"
    VULNERABLE_PERSON_RISK = "vulnerable_person_risk"
    REGULATORY_RISK = "regulatory_risk"
    ECOLOGICAL_RISK = "ecological_risk"


SENSITIVE_PUBLIC_FIELDS = frozenset({
    "person_name",
    "phone",
    "email",
    "exact_location",
    "income",
    "debt",
    "migration_status",
    "caste",
    "religion",
    "health",
    "household",
    "case_notes",
    "consent_record",
})


@dataclass(frozen=True)
class EnablerCompany:
    name: str
    sector: str
    geography: str
    enablement_levers: tuple[str, ...]
    source_refs: tuple[str, ...]
    evidence_level: EvidenceLevel = EvidenceLevel.PUBLIC_SOURCE
    risk_class: RiskClass = RiskClass.LOW
    company_id: str = field(default_factory=lambda: _id("enabler"))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence_level"] = self.evidence_level.value
        payload["risk_class"] = self.risk_class.value
        return payload


@dataclass(frozen=True)
class ConsentReceipt:
    subject_ref: str
    level: ConsentLevel
    source_ref: str
    receipt_id: str = field(default_factory=lambda: _id("consent"))

    def allows_contact(self) -> bool:
        return self.level == ConsentLevel.DIRECT_CONTACT_APPROVED

    def allows_publish(self) -> bool:
        return self.level == ConsentLevel.PUBLISH_APPROVED


@dataclass(frozen=True)
class NeedSignal:
    subject_ref: str
    friction: str
    evidence_refs: tuple[str, ...]
    consent_level: ConsentLevel = ConsentLevel.PUBLIC_ONLY
    signal_id: str = field(default_factory=lambda: _id("need"))


@dataclass(frozen=True)
class EnablementPacket:
    subject_ref: str
    action: str
    expected_value: str
    risk_class: RiskClass
    consent_receipt_id: str
    packet_id: str = field(default_factory=lambda: _id("packet"))


@dataclass(frozen=True)
class OutcomeClaim:
    subject_ref: str
    outcome_metric: str
    outcome_value: str
    evidence_refs: tuple[str, ...]
    audit_status: str = "unaudited"
    claim_id: str = field(default_factory=lambda: _id("outcome"))


@dataclass(frozen=True)
class PublicProofClaim:
    cell_id: str
    claim_type: str
    aggregate_count: int
    sector: str
    region_level: str
    evidence_refs: tuple[str, ...]
    audit_status: str
    outcome_metric: str
    outcome_value: str
    time_period: str
    claim_id: str = field(default_factory=lambda: _id("proof"))

    def to_public_payload(self) -> dict[str, object]:
        payload = asdict(self)
        validate_public_payload(payload)
        return payload


def validate_public_payload(payload: dict[str, object]) -> None:
    leaked = SENSITIVE_PUBLIC_FIELDS.intersection(payload)
    if leaked:
        raise ValueError("public livelihood proof includes sensitive field(s): " + ", ".join(sorted(leaked)))
    if payload.get("aggregate_count") == 1:
        raise ValueError("public livelihood proof must aggregate more than one person/business")
    if "region_level" in payload and payload["region_level"] == "exact":
        raise ValueError("public livelihood proof cannot expose exact location")


def enabler_from_csv_row(row: dict[str, str]) -> EnablerCompany:
    source_value = (
        row.get("source_refs")
        or row.get("source")
        or row.get("source_url")
        or row.get("website")
        or ""
    )
    lever_value = (
        row.get("enablement_levers")
        or row.get("lever")
        or row.get("informal_economy_role")
        or row.get("subdomain")
        or row.get("source_tag")
        or ""
    )
    levers = tuple(
        item.strip()
        for item in lever_value.split(";")
        if item.strip()
    )
    refs = tuple(
        item.strip()
        for item in source_value.split(";")
        if item.strip()
    )
    return EnablerCompany(
        name=row.get("name", "").strip(),
        sector=(row.get("sector") or row.get("domain") or "").strip() or "unknown",
        geography=(row.get("geography") or row.get("country") or "").strip() or "unknown",
        enablement_levers=levers,
        source_refs=refs,
    )
