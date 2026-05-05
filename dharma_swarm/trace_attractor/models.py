"""Data models for the Trace Attractor Ledger.

Defines ``AttractorPacket`` (the read-model projection) and
``AttractorEvent`` (the normalized event row used inside the projection).

Aligned with:
  - CloudEvents 1.0 (event envelope)
  - W3C PROV-O (entity/activity/agent provenance)
  - W3C Trace Context (trace_id as causal identity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class AttractorEvent:
    """Normalized event row inside a projection.

    CloudEvents mapping:
      id      -> event_id
      source  -> dharma://{source_store}/{source_table_or_type}
      type    -> dev.dharma.{event_type}
      subject -> source_object_id
      time    -> occurred_at
      data    -> attributes
    """

    event_id: str
    trace_id: str
    proposal_id: str = ""
    session_id: str = ""
    source_store: str = ""
    source_table_or_type: str = ""
    source_object_id: str = ""
    event_type: str = ""
    subject: str = ""
    occurred_at: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_cloudevent(self) -> dict[str, Any]:
        """Serialize to CloudEvents 1.0 JSON shape."""
        return {
            "specversion": "1.0",
            "id": self.event_id,
            "source": f"dharma://{self.source_store}/{self.source_table_or_type}",
            "type": f"dev.dharma.{self.event_type}",
            "subject": self.subject or self.source_object_id,
            "time": self.occurred_at,
            "data": self.attributes,
        }


@dataclass(frozen=True, slots=True)
class LifecycleFinding:
    """A lifecycle integrity finding within the packet."""

    finding_type: str
    severity: str  # INFO | DEGRADED | BLOCKER
    detail: str = ""
    source_object_id: str = ""


@dataclass(frozen=True, slots=True)
class ProvenanceNode:
    """A node in the provenance graph (PROV-O entity/activity/agent)."""

    node_id: str
    node_type: str  # entity | activity | agent
    label: str = ""
    source_store: str = ""


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    """An edge in the provenance graph (PROV-O relation)."""

    source_id: str
    target_id: str
    relation: str  # wasGeneratedBy | wasDerivedFrom | wasAttributedTo | used
    label: str = ""


@dataclass(frozen=True, slots=True)
class FourfoldWarrantSummary:
    """Summary of Fourfold Action Warrant status for the trace."""

    status: str = "unknown"
    maheshwari: str = "unknown"
    mahakali: str = "unknown"
    mahalakshmi: str = "unknown"
    mahasaraswati: str = "unknown"
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ValueSummary:
    """Aggregate value metrics for the trace."""

    composite_value: float = 0.0
    economic_amount: float = 0.0
    currency: str = "USD"
    agent_count: int = 0
    artifact_count: int = 0
    task_count: int = 0


@dataclass(slots=True)
class AttractorPacket:
    """Read-model projection assembled from existing stores.

    This is NOT a new source of truth — it can always be deleted and
    rebuilt from the existing ontology, runtime, telemetry, and signal
    capture data.
    """

    schema_version: int = 1
    trace_id: str = ""
    generated_at: str = field(default_factory=_utcnow)

    # ID collections from stores
    session_ids: list[str] = field(default_factory=list)
    proposal_ids: list[str] = field(default_factory=list)
    gate_decision_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    delegation_run_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    outcome_ids: list[str] = field(default_factory=list)
    value_event_ids: list[str] = field(default_factory=list)
    contribution_ids: list[str] = field(default_factory=list)
    economic_event_ids: list[str] = field(default_factory=list)
    signal_event_ids: list[str] = field(default_factory=list)
    witness_log_ids: list[str] = field(default_factory=list)
    lineage_edge_ids: list[str] = field(default_factory=list)

    # Structured summaries
    fourfold_warrant: FourfoldWarrantSummary = field(
        default_factory=FourfoldWarrantSummary
    )
    value_summary: ValueSummary = field(default_factory=ValueSummary)

    # Findings and graph
    lifecycle_findings: list[LifecycleFinding] = field(default_factory=list)
    provenance_graph: dict[str, list[Any]] = field(
        default_factory=lambda: {"nodes": [], "edges": []}
    )

    # Raw events (for detailed inspection)
    events: list[AttractorEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "generated_at": self.generated_at,
            "session_ids": self.session_ids,
            "proposal_ids": self.proposal_ids,
            "gate_decision_ids": self.gate_decision_ids,
            "task_ids": self.task_ids,
            "claim_ids": self.claim_ids,
            "delegation_run_ids": self.delegation_run_ids,
            "artifact_ids": self.artifact_ids,
            "outcome_ids": self.outcome_ids,
            "value_event_ids": self.value_event_ids,
            "contribution_ids": self.contribution_ids,
            "economic_event_ids": self.economic_event_ids,
            "signal_event_ids": self.signal_event_ids,
            "witness_log_ids": self.witness_log_ids,
            "lineage_edge_ids": self.lineage_edge_ids,
            "fourfold_warrant": {
                "status": self.fourfold_warrant.status,
                "maheshwari": self.fourfold_warrant.maheshwari,
                "mahakali": self.fourfold_warrant.mahakali,
                "mahalakshmi": self.fourfold_warrant.mahalakshmi,
                "mahasaraswati": self.fourfold_warrant.mahasaraswati,
                "evidence_refs": self.fourfold_warrant.evidence_refs,
            },
            "value_summary": {
                "composite_value": self.value_summary.composite_value,
                "economic_amount": self.value_summary.economic_amount,
                "currency": self.value_summary.currency,
                "agent_count": self.value_summary.agent_count,
                "artifact_count": self.value_summary.artifact_count,
                "task_count": self.value_summary.task_count,
            },
            "lifecycle_findings": [
                {
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "detail": f.detail,
                    "source_object_id": f.source_object_id,
                }
                for f in self.lifecycle_findings
            ],
            "provenance_graph": self.provenance_graph,
        }

    def human_summary(self) -> str:
        """Compact human-readable summary."""
        findings_by_sev = {"BLOCKER": 0, "DEGRADED": 0, "INFO": 0}
        for f in self.lifecycle_findings:
            findings_by_sev[f.severity] = findings_by_sev.get(f.severity, 0) + 1
        return (
            f"Trace {self.trace_id}\n"
            f"  proposals: {len(self.proposal_ids)}  "
            f"gates: {len(self.gate_decision_ids)}  "
            f"tasks: {len(self.task_ids)}  "
            f"artifacts: {len(self.artifact_ids)}\n"
            f"  outcomes: {len(self.outcome_ids)}   "
            f"value_events: {len(self.value_event_ids)}  "
            f"contributions: {len(self.contribution_ids)}\n"
            f"  economic: {self.value_summary.currency} "
            f"{self.value_summary.economic_amount:.2f}  "
            f"warrant: {self.fourfold_warrant.status}\n"
            f"  findings: {findings_by_sev.get('BLOCKER', 0)} blocker, "
            f"{findings_by_sev.get('DEGRADED', 0)} degraded"
        )
