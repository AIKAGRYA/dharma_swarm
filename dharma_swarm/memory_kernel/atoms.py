"""Schema atoms for the MemoryKernel surface census.

These records classify memory-like surfaces.  They are not canonical memories
themselves; they describe where memories live, how much authority they carry,
and how future adapters should treat them.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class MemorySurfaceRole(StrEnum):
    SESSION_MEMORY = "session_memory"
    RAW_EPISODIC_LOG = "raw_episodic_log"
    MEMORY_PLANE = "memory_plane"
    RUNTIME_STATE = "runtime_state"
    WITNESS = "witness"
    PROJECTION_INDEX = "projection_index"
    KNOWLEDGE_LIFECYCLE = "knowledge_lifecycle"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    INTENT_GRAPH = "intent_graph"
    COORDINATION = "coordination"
    TELEMETRY = "telemetry"
    EXTERNAL_EXOCORTEX = "external_exocortex"
    REPO_LOCAL_STATE = "repo_local_state"
    SNAPSHOT = "snapshot"
    UNSAFE_FIXTURE = "unsafe_fixture"


class SurfaceCategory(StrEnum):
    RAW_EVIDENCE = "raw_evidence"
    RUNTIME_CONTROL = "runtime_control"
    PROVENANCE = "provenance"
    PROJECTION = "projection"
    KNOWLEDGE_METABOLISM = "knowledge_metabolism"
    KNOWLEDGE_AUTHORITY = "knowledge_authority"
    INTENT = "intent"
    COORDINATION = "coordination"
    TELEMETRY = "telemetry"
    EXTERNAL = "external"
    REPO_LOCAL = "repo_local"
    DORMANT = "dormant"
    UNSAFE = "unsafe"


class AuthorityLevel(StrEnum):
    """Surface authority classification.

    CANONICAL is reserved for future promoted/gated surfaces.  M0 default
    surfaces should not use it; M0 observes and classifies, it does not promote.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CANONICAL = "canonical"


class WriteMode(StrEnum):
    READ_ONLY = "read_only"
    APPEND_ONLY = "append_only"
    READ_WRITE = "read_write"
    PROJECTION_WRITE = "projection_write"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class AdapterMode(StrEnum):
    READ_ONLY = "read_only"
    STREAMING = "streaming"
    METADATA_ONLY = "metadata_only"
    DISABLED = "disabled"
    FUTURE = "future"


class SurfaceStatus(StrEnum):
    ACTIVE = "active"
    MISSING = "missing"
    DORMANT = "dormant"
    SNAPSHOT = "snapshot"
    EXTERNAL = "external"
    UNSAFE = "unsafe"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MigrationStatus(StrEnum):
    REGISTER_ONLY = "register_only"
    ADAPTER_NEEDED = "adapter_needed"
    ADAPTER_READY = "adapter_ready"
    DO_NOT_MIGRATE = "do_not_migrate"
    LEGACY_TOLERATED = "legacy_tolerated"
    RETIRE_LATER = "retire_later"


class MemoryAtomType(StrEnum):
    EPISODE = "episode"
    FACT = "fact"
    EDGE = "edge"
    SOURCE_CHUNK = "source_chunk"
    RETRIEVAL_FEEDBACK = "retrieval_feedback"
    WITNESS_EVENT = "witness_event"
    EXTERNAL_MEMORY = "external_memory"
    KNOWLEDGE_CARD = "knowledge_card"
    RUNTIME_EVENT = "runtime_event"
    CONTEXT_BUNDLE = "context_bundle"
    METADATA = "metadata"


class ReadMode(StrEnum):
    IMMUTABLE_SNAPSHOT = "immutable_snapshot"
    READ_ONLY = "read_only"
    STREAMING = "streaming"
    METADATA_ONLY = "metadata_only"


class MemoryOrder(StrEnum):
    STABLE_ID = "stable_id"
    NEWEST = "newest"
    OLDEST = "oldest"


class MemoryLane(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    REFLECTION = "reflection"
    PROVENANCE = "provenance"
    PROJECTION = "projection"


class MemoryScope(StrEnum):
    USER = "user"
    PROJECT = "project"
    REPO = "repo"
    WORKTREE = "worktree"
    SESSION = "session"
    AGENT = "agent"
    SWARM = "swarm"


class TruthState(StrEnum):
    RAW = "raw"
    CLAIMED = "claimed"
    OBSERVED = "observed"
    DERIVED = "derived"
    CURATED = "curated"
    CANONICAL = "canonical"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


@dataclass(frozen=True)
class MemoryQuery:
    limit_total: int | None = 100
    limit_per_surface: int | None = 25
    order_by: MemoryOrder = MemoryOrder.STABLE_ID
    since: str | None = None
    cursor: str | None = None
    include_content: bool = False
    include_metadata_payloads: bool = False
    atom_types: tuple[MemoryAtomType, ...] = ()

    def per_surface_limit(self, default_limit: int) -> int | None:
        if self.limit_per_surface is None:
            return default_limit
        return max(0, self.limit_per_surface)

    def total_limit(self) -> int | None:
        if self.limit_total is None:
            return None
        return max(0, self.limit_total)

    def allows_atom_type(self, atom_type: MemoryAtomType) -> bool:
        return not self.atom_types or atom_type in self.atom_types


@dataclass(frozen=True)
class MemorySurfaceHealth:
    exists: bool
    path_type: str = "missing"
    size_bytes: int | None = None
    last_modified: str | None = None
    record_count: int | None = None
    schema: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    probe_truncated: bool = False
    probe_error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemorySurface:
    surface_id: str
    path: str
    owner_module: str
    role: MemorySurfaceRole
    category: SurfaceCategory
    authority_level: AuthorityLevel
    write_mode: WriteMode
    adapter_mode: AdapterMode
    active_status: SurfaceStatus
    health: MemorySurfaceHealth
    provenance_quality: str = "unknown"
    promotion_path: str = ""
    canon_risk: RiskLevel = RiskLevel.UNKNOWN
    pii_secrets_risk: RiskLevel = RiskLevel.UNKNOWN
    latency_risk: RiskLevel = RiskLevel.UNKNOWN
    known_writers: tuple[str, ...] = ()
    known_readers: tuple[str, ...] = ()
    feeds: tuple[str, ...] = ()
    source_of_truth_for: tuple[str, ...] = ()
    projection_of: tuple[str, ...] = ()
    migration_status: MigrationStatus = MigrationStatus.REGISTER_ONLY
    do_not_migrate_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["role"] = self.role.value
        payload["category"] = self.category.value
        payload["authority_level"] = self.authority_level.value
        payload["write_mode"] = self.write_mode.value
        payload["adapter_mode"] = self.adapter_mode.value
        payload["active_status"] = self.active_status.value
        payload["canon_risk"] = self.canon_risk.value
        payload["pii_secrets_risk"] = self.pii_secrets_risk.value
        payload["latency_risk"] = self.latency_risk.value
        payload["migration_status"] = self.migration_status.value
        return payload


@dataclass(frozen=True)
class MemoryAtom:
    atom_id: str
    surface_id: str
    atom_type: MemoryAtomType
    content_ref: str
    content: str | None
    timestamp: str | None
    source_path: str
    authority_level: AuthorityLevel
    provenance_quality: str
    projection_of: tuple[str, ...]
    canon_risk: RiskLevel
    pii_risk: RiskLevel
    adapter_name: str
    read_mode: ReadMode
    surface_category: SurfaceCategory
    surface_role: MemorySurfaceRole
    memory_lane: MemoryLane
    scope: MemoryScope
    truth_state: TruthState
    confidence: float
    freshness: str
    valid_from: str | None
    valid_until: str | None
    source_refs: tuple[str, ...]
    supersedes: tuple[str, ...]
    promotion_allowed: bool
    context_admissible: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        surface: MemorySurface,
        atom_type: MemoryAtomType,
        content_ref: str,
        adapter_name: str,
        read_mode: ReadMode,
        content: str | None = None,
        timestamp: str | None = None,
        source_path: str | None = None,
        metadata: dict[str, Any] | None = None,
        memory_lane: MemoryLane | None = None,
        scope: MemoryScope | None = None,
        truth_state: TruthState | None = None,
        confidence: float | None = None,
        freshness: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        source_refs: tuple[str, ...] | None = None,
        supersedes: tuple[str, ...] = (),
        promotion_allowed: bool = False,
        context_admissible: bool = False,
    ) -> "MemoryAtom":
        resolved_truth_state = truth_state or infer_truth_state(surface, atom_type)
        return cls(
            atom_id=stable_atom_id(surface.surface_id, atom_type.value, content_ref),
            surface_id=surface.surface_id,
            atom_type=atom_type,
            content_ref=content_ref,
            content=content,
            timestamp=timestamp,
            source_path=source_path or surface.path,
            authority_level=surface.authority_level,
            provenance_quality=surface.provenance_quality,
            projection_of=surface.projection_of,
            canon_risk=surface.canon_risk,
            pii_risk=surface.pii_secrets_risk,
            adapter_name=adapter_name,
            read_mode=read_mode,
            surface_category=surface.category,
            surface_role=surface.role,
            memory_lane=memory_lane or infer_memory_lane(surface, atom_type),
            scope=scope or infer_scope(surface),
            truth_state=resolved_truth_state,
            confidence=confidence if confidence is not None else infer_confidence(resolved_truth_state),
            freshness=freshness or infer_freshness(surface),
            valid_from=valid_from or timestamp,
            valid_until=valid_until,
            source_refs=source_refs or (source_path or surface.path,),
            supersedes=supersedes,
            promotion_allowed=promotion_allowed,
            context_admissible=context_admissible,
            metadata=metadata or {},
        )

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["atom_type"] = self.atom_type.value
        payload["authority_level"] = self.authority_level.value
        payload["canon_risk"] = self.canon_risk.value
        payload["pii_risk"] = self.pii_risk.value
        payload["read_mode"] = self.read_mode.value
        payload["surface_category"] = self.surface_category.value
        payload["surface_role"] = self.surface_role.value
        payload["memory_lane"] = self.memory_lane.value
        payload["scope"] = self.scope.value
        payload["truth_state"] = self.truth_state.value
        return payload


def infer_memory_lane(surface: MemorySurface, atom_type: MemoryAtomType) -> MemoryLane:
    if atom_type == MemoryAtomType.WITNESS_EVENT:
        return MemoryLane.PROVENANCE
    if atom_type in {MemoryAtomType.SOURCE_CHUNK, MemoryAtomType.RETRIEVAL_FEEDBACK, MemoryAtomType.METADATA}:
        return MemoryLane.PROJECTION
    if atom_type in {MemoryAtomType.FACT, MemoryAtomType.EDGE, MemoryAtomType.KNOWLEDGE_CARD}:
        return MemoryLane.SEMANTIC
    if surface.category == SurfaceCategory.RUNTIME_CONTROL:
        return MemoryLane.WORKING
    if surface.category == SurfaceCategory.PROVENANCE:
        return MemoryLane.PROVENANCE
    if surface.category == SurfaceCategory.PROJECTION:
        return MemoryLane.PROJECTION
    return MemoryLane.EPISODIC


def infer_scope(surface: MemorySurface) -> MemoryScope:
    surface_id = surface.surface_id
    if surface.category == SurfaceCategory.REPO_LOCAL or surface_id.startswith("repo."):
        return MemoryScope.REPO
    if "agent" in surface_id:
        return MemoryScope.AGENT
    if surface_id.startswith("home.smriti") or surface_id.startswith("home.codex") or surface_id.startswith("external."):
        return MemoryScope.USER
    if surface.category in {SurfaceCategory.COORDINATION, SurfaceCategory.RUNTIME_CONTROL}:
        return MemoryScope.SWARM
    return MemoryScope.PROJECT


def infer_truth_state(surface: MemorySurface, atom_type: MemoryAtomType) -> TruthState:
    if atom_type in {MemoryAtomType.WITNESS_EVENT, MemoryAtomType.RUNTIME_EVENT}:
        return TruthState.OBSERVED
    if atom_type in {MemoryAtomType.SOURCE_CHUNK, MemoryAtomType.RETRIEVAL_FEEDBACK, MemoryAtomType.METADATA}:
        return TruthState.DERIVED
    if atom_type in {MemoryAtomType.FACT, MemoryAtomType.EDGE, MemoryAtomType.KNOWLEDGE_CARD}:
        return TruthState.CLAIMED
    if surface.category in {SurfaceCategory.PROJECTION, SurfaceCategory.TELEMETRY}:
        return TruthState.DERIVED
    if surface.category in {SurfaceCategory.PROVENANCE, SurfaceCategory.RUNTIME_CONTROL}:
        return TruthState.OBSERVED
    return TruthState.RAW


def infer_confidence(truth_state: TruthState) -> float:
    if truth_state == TruthState.OBSERVED:
        return 0.7
    if truth_state == TruthState.CLAIMED:
        return 0.5
    if truth_state == TruthState.DERIVED:
        return 0.45
    if truth_state == TruthState.RAW:
        return 0.35
    return 0.0


def infer_freshness(surface: MemorySurface) -> str:
    if surface.active_status == SurfaceStatus.SNAPSHOT:
        return "snapshot"
    if surface.active_status == SurfaceStatus.ACTIVE:
        return "current_or_live_snapshot"
    if surface.active_status == SurfaceStatus.DORMANT:
        return "dormant"
    if surface.active_status == SurfaceStatus.MISSING:
        return "missing"
    return "unknown"


def stable_atom_id(*parts: str) -> str:
    payload = "\n".join(part.strip() for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"memory_atom:{digest[:32]}"
