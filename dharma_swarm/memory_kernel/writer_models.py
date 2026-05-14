"""Writer inventory models for MemoryKernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from dharma_swarm.memory_kernel.atoms import RiskLevel, WriteMode


class WriterClassification(StrEnum):
    APPROVED = "approved"
    LEGACY_TOLERATED = "legacy_tolerated"
    REVIEW_REQUIRED = "review_required"
    UNSAFE = "unsafe"
    DORMANT = "dormant"


class WriterStatus(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNREGISTERED_SURFACE = "unregistered_surface"
    ERROR = "error"


class DiscoveredWriteStatus(StrEnum):
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    IGNORED = "ignored"


class DiscoveryTriageCategory(StrEnum):
    REGISTERED_MEMORY_WRITER = "registered_memory_writer"
    MEMORY_WRITER_NEEDS_SPEC = "memory_writer_needs_spec"
    SURFACE_NEEDS_REGISTRY = "surface_needs_registry"
    READ_WRITE_HELPER = "read_write_helper"
    OPERATIONAL_STATE = "operational_state"
    GENERATED_ARTIFACT = "generated_artifact"
    TEST_OR_EXPERIMENT = "test_or_experiment"
    FALSE_POSITIVE = "false_positive"


@dataclass(frozen=True)
class MemoryWriterSpec:
    writer_id: str
    owner_module: str
    symbol: str
    writes_to: tuple[str, ...]
    write_mode: WriteMode
    classification: WriterClassification
    risk: RiskLevel
    notes: str = ""

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["write_mode"] = self.write_mode.value
        payload["classification"] = self.classification.value
        payload["risk"] = self.risk.value
        return payload


@dataclass(frozen=True)
class DiscoveredMemoryWrite:
    source_path: str
    symbol: str
    line: int
    operation: str
    target: str
    mode: str
    reason: str
    status: DiscoveredWriteStatus
    triage_category: DiscoveryTriageCategory
    triage_reason: str
    matched_writer_ids: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["triage_category"] = self.triage_category.value
        return payload


@dataclass(frozen=True)
class MemoryWriterObservation:
    spec: MemoryWriterSpec
    source_path: str
    present: bool
    status: WriterStatus
    unregistered_surfaces: tuple[str, ...] = ()
    error: str | None = None

    def to_json(self) -> dict[str, object]:
        payload = {
            "writer": self.spec.to_json(),
            "source_path": self.source_path,
            "present": self.present,
            "status": self.status.value,
            "unregistered_surfaces": self.unregistered_surfaces,
        }
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class WriterSentinelSummary:
    writer_count: int
    present_count: int
    missing_count: int
    unregistered_surface_count: int
    error_count: int
    by_classification: dict[str, int]
    by_status: dict[str, int]

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class WriterDiscoverySummary:
    scanned_file_count: int
    parse_error_count: int
    discovered_write_count: int
    registered_discovery_count: int
    unregistered_discovery_count: int
    action_required_count: int
    top_unregistered_sources: tuple[dict[str, object], ...]
    by_operation: dict[str, int]
    by_status: dict[str, int]
    by_triage: dict[str, int]

    def to_json(self) -> dict[str, object]:
        return asdict(self)
