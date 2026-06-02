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
    source_roots: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    gap_codes: tuple[str, ...] = ()
    next_action: str = ""

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
    daily_cycle: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    gap_codes: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
