"""Typed read-model contracts for the Trace Attractor Ledger.

These models do not read or write runtime state.  They define the stable JSON
shape that later store readers, SignalBus capture, CLI commands, and dashboard
routes must target.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


ATTRACTOR_PACKET_SCHEMA_VERSION = 1
DHARMA_JSONLD_CONTEXT = {
    "prov": "http://www.w3.org/ns/prov#",
    "dharma": "https://dharma.local/ns#",
    "trace_id": "dharma:traceId",
    "trace_id_source": "dharma:traceIdSource",
    "value_summary": "dharma:valueSummary",
}


def utc_now_iso() -> str:
    """Return a compact UTC timestamp for packet generation."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


class _TraceAttractorModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class FindingSeverity(str, Enum):
    """Severity for lifecycle findings in an AttractorPacket."""

    INFO = "INFO"
    DEGRADED = "DEGRADED"
    BLOCKER = "BLOCKER"


class WarrantStatus(str, Enum):
    """Evidence status for a Fourfold Action Warrant dimension."""

    PASS = "pass"
    HOLD = "hold"
    BLOCK = "block"
    UNKNOWN = "unknown"


class FourfoldWarrantSummary(_TraceAttractorModel):
    """Fourfold Action Warrant evidence summary attached to a trace."""

    status: WarrantStatus = WarrantStatus.UNKNOWN
    maheshwari: WarrantStatus = WarrantStatus.UNKNOWN
    mahakali: WarrantStatus = WarrantStatus.UNKNOWN
    mahalakshmi: WarrantStatus = WarrantStatus.UNKNOWN
    mahasaraswati: WarrantStatus = WarrantStatus.UNKNOWN
    evidence_refs: list[str] = Field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_refs) or any(
            value != WarrantStatus.UNKNOWN.value
            for value in (
                self.status,
                self.maheshwari,
                self.mahakali,
                self.mahalakshmi,
                self.mahasaraswati,
            )
        )


class ValueSummary(_TraceAttractorModel):
    """Compact value accounting summary for a projected trace."""

    composite_value: float = 0.0
    economic_amount: float = 0.0
    currency: str = "USD"
    agent_count: int = 0
    artifact_count: int = 0
    task_count: int = 0


class LifecycleFinding(_TraceAttractorModel):
    """A deterministic lifecycle or evidence-quality finding."""

    code: str
    severity: FindingSeverity
    message: str
    source_event_id: str = ""
    source_object_id: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class ProvenanceNode(_TraceAttractorModel):
    """A PROV-compatible node in the projected packet graph."""

    id: str
    label: str = ""
    kind: str = "prov:Entity"
    source_event_id: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvenanceEdge(_TraceAttractorModel):
    """A PROV-compatible edge in the projected packet graph."""

    source: str
    target: str
    relation: str
    source_event_id: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvenanceGraph(_TraceAttractorModel):
    """Small graph projection embedded inside an AttractorPacket."""

    nodes: list[ProvenanceNode] = Field(default_factory=list)
    edges: list[ProvenanceEdge] = Field(default_factory=list)


class AttractorEvent(_TraceAttractorModel):
    """Normalized event row used as input to the projection.

    The event shape borrows CloudEvents fields while keeping Dharma-specific
    correlation fields explicit.  Later PRs can derive this object from ontology,
    runtime, telemetry, or SignalBus records.
    """

    event_id: str
    trace_id: str = ""
    proposal_id: str = ""
    session_id: str = ""
    source_store: str
    source_table_or_type: str
    source_object_id: str
    event_type: str
    subject: str = ""
    occurred_at: str
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_object_id(self) -> str:
        return self.source_object_id or self.subject

    def attribute_text(self, key: str) -> str:
        value = self.attributes.get(key)
        if value is None:
            return ""
        return str(value)

    def to_cloudevent(self) -> dict[str, Any]:
        """Render a CloudEvents-inspired envelope for this normalized event."""
        data = dict(self.attributes)
        if self.trace_id:
            data.setdefault("trace_id", self.trace_id)
        if self.proposal_id:
            data.setdefault("proposal_id", self.proposal_id)
        if self.session_id:
            data.setdefault("session_id", self.session_id)
        return {
            "specversion": "1.0",
            "id": self.event_id,
            "source": f"dharma://{self.source_store}/{self.source_table_or_type}",
            "type": f"dev.dharma.{self.event_type}",
            "time": self.occurred_at,
            "subject": self.subject or self.primary_object_id,
            "data": data,
        }


class AttractorPacket(_TraceAttractorModel):
    """Rebuildable trace-level read model assembled from normalized events."""

    schema_version: int = ATTRACTOR_PACKET_SCHEMA_VERSION
    trace_id: str
    trace_id_source: str = "unknown"
    generated_at: str = Field(default_factory=utc_now_iso)
    session_ids: list[str] = Field(default_factory=list)
    proposal_ids: list[str] = Field(default_factory=list)
    gate_decision_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    delegation_run_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    outcome_ids: list[str] = Field(default_factory=list)
    value_event_ids: list[str] = Field(default_factory=list)
    contribution_ids: list[str] = Field(default_factory=list)
    economic_event_ids: list[str] = Field(default_factory=list)
    signal_event_ids: list[str] = Field(default_factory=list)
    witness_log_ids: list[str] = Field(default_factory=list)
    lineage_edge_ids: list[str] = Field(default_factory=list)
    fourfold_warrant: FourfoldWarrantSummary = Field(
        default_factory=FourfoldWarrantSummary
    )
    value_summary: ValueSummary = Field(default_factory=ValueSummary)
    lifecycle_findings: list[LifecycleFinding] = Field(default_factory=list)
    provenance_graph: ProvenanceGraph = Field(default_factory=ProvenanceGraph)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable packet data."""
        return self.model_dump(mode="json")

    def to_stable_json(self) -> str:
        """Return deterministic compact JSON suitable for CLI golden tests."""
        return _canonical_json(self.to_dict())

    def to_jsonld_stub(self) -> dict[str, Any]:
        """Return the minimal JSON-LD wrapper promised by the master spec."""
        data = self.to_dict()
        data["@context"] = dict(DHARMA_JSONLD_CONTEXT)
        data["@id"] = f"dharma:trace/{self.trace_id}"
        data["@type"] = "dharma:AttractorPacket"
        return data
