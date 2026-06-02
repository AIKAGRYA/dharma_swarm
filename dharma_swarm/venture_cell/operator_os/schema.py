"""Schema for the VentureCell Operator OS projection.

The projection is a read-only company-OS view. It does not create a new
dispatcher, grant external authority, or promote memory into trusted Chetana.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "dharma.venture_cell_operator_os.v0"


@dataclass(frozen=True)
class OperatorDepartment:
    """One Cofounder/Polsia-style department mapped onto Dharma surfaces."""

    department_id: str
    label: str
    role_pattern: str
    ds_surface: str
    authority_mode: str
    status: str = "declared"
    evidence_refs: tuple[str, ...] = ()
    borrowed_from: tuple[str, ...] = ()
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanvasItem:
    """One item visible in the VentureCell canvas/attention queue."""

    item_id: str
    lane: str
    title: str
    status: str
    source_surface: str
    owner_department: str = ""
    evidence_refs: tuple[str, ...] = ()
    blocked_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateSummary:
    """Governance gate state for the projection."""

    gate_id: str
    label: str
    observed_state: str
    coherence_state: str
    decision: str
    evidence_refs: tuple[str, ...] = ()
    gap_codes: tuple[str, ...] = ()
    next_action: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKernelSnapshot:
    """Chetana/wiki status as an agent-readable memory substrate snapshot."""

    status: str
    staged_count: int = 0
    trusted_count: int = 0
    quarantine_count: int = 0
    truncated: bool = False
    index_status: str = ""
    indexed_count: int = 0
    index_entries: tuple[dict[str, Any], ...] = ()
    index_query_terms: tuple[str, ...] = ()
    query_eval_results: tuple[dict[str, Any], ...] = ()
    query_eval_passed: int = 0
    query_eval_total: int = 0
    query_eval_status: str = "not_run"
    source_roots: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    gap_codes: tuple[str, ...] = ()
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperatorNextActionPacket:
    """One read-only packet that can be handed to an operator or ds-goal lane."""

    packet_id: str
    status: str
    autonomy_level: str
    owner_department: str
    decision: str
    next_governed_action: str
    blockers: tuple[str, ...] = ()
    blocked_departments: tuple[str, ...] = ()
    required_unblock_artifact: str = ""
    memory_query_eval_status: str = "not_run"
    memory_query_eval_passed: int = 0
    memory_query_eval_total: int = 0
    gate_decisions: tuple[dict[str, Any], ...] = ()
    evidence_refs: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DarshanGoGatePacket:
    """Read-only Darshan external-reader GO gate handoff."""

    packet_id: str
    gate_id: str
    decision: str
    observed_state: str
    coherence_state: str
    authority_boundary: str
    why_external_reader_required: str
    required_receipt_source: str
    required_receipt_schema: str
    required_receipt_fields: tuple[str, ...] = ()
    countable_event_types: tuple[str, ...] = ()
    blocked_departments: tuple[str, ...] = ()
    blocked_actions: tuple[str, ...] = ()
    accepted_receipts: tuple[str, ...] = ()
    rejected_receipts: tuple[str, ...] = ()
    missing_receipts: tuple[str, ...] = ()
    event_uids: tuple[str, ...] = ()
    expected_local_artifacts: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    next_governed_action: str = ""
    gap_codes: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VentureCellOperatorProjection:
    """The fused Operator OS projection for one VentureCell."""

    venture_cell_id: str
    title: str
    artifact_id: str
    status: str
    autonomy_level: str
    company_profile: dict[str, Any]
    departments: tuple[OperatorDepartment, ...] = ()
    canvas: tuple[CanvasItem, ...] = ()
    gates: tuple[GateSummary, ...] = ()
    memory_kernel: MemoryKernelSnapshot = field(
        default_factory=lambda: MemoryKernelSnapshot(status="unknown")
    )
    next_action_packet: OperatorNextActionPacket = field(
        default_factory=lambda: OperatorNextActionPacket(
            packet_id="operator.next_action",
            status="unknown",
            autonomy_level="unknown",
            owner_department="operations",
            decision="inspect_projection",
            next_governed_action="Inspect the current Operator OS projection.",
        )
    )
    darshan_go_gate_packet: DarshanGoGatePacket = field(
        default_factory=lambda: DarshanGoGatePacket(
            packet_id="darshan.go_gate",
            gate_id="darshan.external_reader_go_receipts",
            decision="inspect_gate",
            observed_state="unknown",
            coherence_state="unknown",
            authority_boundary="read_only_projection",
            why_external_reader_required="Inspect the Darshan external-reader gate.",
            required_receipt_source="darshan_external_reader",
            required_receipt_schema="go_evidence_receipt.v0",
        )
    )
    daily_cycle: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    gap_codes: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
