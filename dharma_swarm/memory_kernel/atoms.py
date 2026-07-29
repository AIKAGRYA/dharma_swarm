"""Schema atoms for the MemoryKernel surface census.

These records classify memory-like surfaces.  They are not canonical memories
themselves; they describe where memories live, how much authority they carry,
and how future adapters should treat them.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


MEMORY_ATOM_SCHEMA_VERSION = "memory_atom.v2"
_AUTHORITY_RANK: dict["AuthorityLevel", int] = {}
_RISK_RANK: dict["RiskLevel", int] = {}


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
    EXPECTED_UNAVAILABLE = "expected_unavailable"
    DORMANT = "dormant"
    SNAPSHOT = "snapshot"
    EXTERNAL = "external"
    RETIRED = "retired"
    DISABLED = "disabled"
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


# Metadata keys that identify an atom's owning agent(s). Shared between the
# adapters' redaction boundary (which must preserve ownership when dropping
# row/payload dicts) and scoped context admission (which enforces it).
AGENT_OWNER_METADATA_KEYS = (
    "agent_id",
    "agent",
    "agent_name",
    "owner_agent_id",
    "assigned_to",
    "assigned_agent_id",
    "worker_agent_id",
)


@dataclass(frozen=True)
class MemoryQuery:
    limit_total: int | None = 100
    limit_per_surface: int | None = 25
    text_query: str | None = None
    order_by: MemoryOrder = MemoryOrder.STABLE_ID
    since: str | None = None
    cursor: str | None = None
    include_content: bool = False
    include_metadata_payloads: bool = False
    atom_types: tuple[MemoryAtomType, ...] = ()
    authority_levels: tuple[AuthorityLevel, ...] = ()
    min_authority: AuthorityLevel | None = None
    provenance_qualities: tuple[str, ...] = ()
    freshness_values: tuple[str, ...] = ()
    surface_categories: tuple[SurfaceCategory, ...] = ()
    max_canon_risk: RiskLevel | None = None
    max_pii_risk: RiskLevel | None = None
    include_high_risk: bool = True
    include_projections: bool = True
    include_unsafe: bool = True
    require_source_digest: bool = False
    require_payload_digest: bool = False
    require_source_row_key: bool = False
    include_degraded_metadata: bool = False

    @classmethod
    def canary_context(
        cls,
        *,
        limit_total: int | None = 50,
        limit_per_surface: int | None = 25,
        include_content: bool = False,
        atom_types: tuple[MemoryAtomType, ...] = (),
    ) -> "MemoryQuery":
        return cls(
            limit_total=limit_total,
            limit_per_surface=limit_per_surface,
            include_content=include_content,
            atom_types=atom_types,
            max_canon_risk=RiskLevel.MEDIUM,
            max_pii_risk=RiskLevel.MEDIUM,
            include_high_risk=False,
            include_projections=False,
            include_unsafe=False,
            require_source_digest=True,
            require_source_row_key=True,
            include_degraded_metadata=True,
        )

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

    def allows_atom(self, atom: "MemoryAtom") -> bool:
        if not self.allows_atom_type(atom.atom_type):
            return False
        if self.authority_levels and atom.authority_level not in self.authority_levels:
            return False
        if self.min_authority and _authority_rank(atom.authority_level) < _authority_rank(
            self.min_authority
        ):
            return False
        if (
            self.provenance_qualities
            and atom.provenance_quality not in self.provenance_qualities
        ):
            return False
        if self.freshness_values and atom.freshness not in self.freshness_values:
            return False
        if self.surface_categories and atom.surface_category not in self.surface_categories:
            return False
        if self.max_canon_risk and _risk_rank(atom.canon_risk) > _risk_rank(
            self.max_canon_risk
        ):
            return False
        if self.max_pii_risk and _risk_rank(atom.pii_risk) > _risk_rank(
            self.max_pii_risk
        ):
            return False
        if not self.include_high_risk and atom.has_high_risk:
            return False
        if not self.include_projections and atom.is_projection:
            return False
        if not self.include_unsafe and atom.is_unsafe:
            return False
        if self.require_source_digest and not atom.source_digest:
            return False
        if self.require_payload_digest and not atom.payload_digest:
            return False
        if self.require_source_row_key and not atom.source_row_key:
            return False
        if self.since and not _timestamp_at_or_after(atom.timestamp, self.since):
            return False
        if self.text_query and not _matches_text_query(atom, self.text_query):
            return False
        return True


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
    schema_version: str
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
    surface_status: SurfaceStatus
    memory_lane: MemoryLane
    scope: MemoryScope
    truth_state: TruthState
    confidence: float
    freshness: str
    source_digest: str | None
    payload_digest: str | None
    source_row_key: str | None
    adapter_version: str
    source_last_modified: str | None
    freshness_lag_seconds: float | None
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
        schema_version: str = MEMORY_ATOM_SCHEMA_VERSION,
        source_digest: str | None = None,
        payload_digest: str | None = None,
        source_row_key: str | None = None,
        adapter_version: str = "unknown",
        source_last_modified: str | None = None,
        freshness_lag_seconds: float | None = None,
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
        resolved_source_path = source_path or surface.path
        resolved_source_last_modified = source_last_modified or surface.health.last_modified
        resolved_payload_digest = payload_digest
        if resolved_payload_digest is None and content is not None:
            resolved_payload_digest = stable_digest(content)
        resolved_source_row_key = source_row_key or content_ref
        resolved_source_digest = source_digest or stable_digest(
            {
                "surface_id": surface.surface_id,
                "atom_type": atom_type.value,
                "content_ref": content_ref,
                "source_path": resolved_source_path,
                "timestamp": timestamp,
                "source_last_modified": resolved_source_last_modified,
            }
        )
        return cls(
            schema_version=schema_version,
            atom_id=stable_atom_id(surface.surface_id, atom_type.value, content_ref),
            surface_id=surface.surface_id,
            atom_type=atom_type,
            content_ref=content_ref,
            content=content,
            timestamp=timestamp,
            source_path=resolved_source_path,
            authority_level=surface.authority_level,
            provenance_quality=surface.provenance_quality,
            projection_of=surface.projection_of,
            canon_risk=surface.canon_risk,
            pii_risk=surface.pii_secrets_risk,
            adapter_name=adapter_name,
            read_mode=read_mode,
            surface_category=surface.category,
            surface_role=surface.role,
            surface_status=surface.active_status,
            memory_lane=memory_lane or infer_memory_lane(surface, atom_type),
            scope=scope or infer_scope(surface),
            truth_state=resolved_truth_state,
            confidence=(
                confidence
                if confidence is not None
                else infer_confidence(resolved_truth_state)
            ),
            freshness=freshness or infer_freshness(surface),
            source_digest=resolved_source_digest,
            payload_digest=resolved_payload_digest,
            source_row_key=resolved_source_row_key,
            adapter_version=adapter_version,
            source_last_modified=resolved_source_last_modified,
            freshness_lag_seconds=(
                freshness_lag_seconds
                if freshness_lag_seconds is not None
                else freshness_lag(timestamp, resolved_source_last_modified)
            ),
            valid_from=valid_from or timestamp,
            valid_until=valid_until,
            source_refs=source_refs or (resolved_source_path,),
            supersedes=supersedes,
            promotion_allowed=promotion_allowed,
            context_admissible=context_admissible,
            metadata=metadata or {},
        )

    @property
    def has_high_risk(self) -> bool:
        high_risks = {RiskLevel.HIGH, RiskLevel.CRITICAL}
        return self.canon_risk in high_risks or self.pii_risk in high_risks

    @property
    def is_projection(self) -> bool:
        return (
            self.surface_category == SurfaceCategory.PROJECTION
            or self.memory_lane == MemoryLane.PROJECTION
            or bool(self.projection_of)
        )

    @property
    def is_unsafe(self) -> bool:
        return (
            self.surface_category == SurfaceCategory.UNSAFE
            or self.surface_role == MemorySurfaceRole.UNSAFE_FIXTURE
            or self.surface_status == SurfaceStatus.UNSAFE
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
        payload["surface_status"] = self.surface_status.value
        payload["memory_lane"] = self.memory_lane.value
        payload["scope"] = self.scope.value
        payload["truth_state"] = self.truth_state.value
        return payload


def infer_memory_lane(surface: MemorySurface, atom_type: MemoryAtomType) -> MemoryLane:
    if atom_type == MemoryAtomType.WITNESS_EVENT:
        return MemoryLane.PROVENANCE
    if atom_type in {
        MemoryAtomType.SOURCE_CHUNK,
        MemoryAtomType.RETRIEVAL_FEEDBACK,
        MemoryAtomType.METADATA,
    }:
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
    if (
        surface_id.startswith("home.smriti")
        or surface_id.startswith("home.codex")
        or surface_id.startswith("external.")
    ):
        return MemoryScope.USER
    if surface.category in {SurfaceCategory.COORDINATION, SurfaceCategory.RUNTIME_CONTROL}:
        return MemoryScope.SWARM
    return MemoryScope.PROJECT


def infer_truth_state(surface: MemorySurface, atom_type: MemoryAtomType) -> TruthState:
    if atom_type in {MemoryAtomType.WITNESS_EVENT, MemoryAtomType.RUNTIME_EVENT}:
        return TruthState.OBSERVED
    if atom_type in {
        MemoryAtomType.SOURCE_CHUNK,
        MemoryAtomType.RETRIEVAL_FEEDBACK,
        MemoryAtomType.METADATA,
    }:
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
    if surface.active_status == SurfaceStatus.EXPECTED_UNAVAILABLE:
        return "expected_unavailable"
    if surface.active_status == SurfaceStatus.DORMANT:
        return "dormant"
    if surface.active_status == SurfaceStatus.RETIRED:
        return "retired"
    if surface.active_status == SurfaceStatus.DISABLED:
        return "disabled"
    if surface.active_status == SurfaceStatus.MISSING:
        return "missing"
    return "unknown"


def stable_atom_id(*parts: str) -> str:
    payload = "\n".join(part.strip() for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"memory_atom:{digest[:32]}"


def stable_digest(value: Any) -> str:
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


_TEXT_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "use",
    "with",
}


def _matches_text_query(atom: MemoryAtom, query: str) -> bool:
    terms = _text_query_terms(query)
    if not terms:
        return True
    haystack = _atom_text_haystack(atom)
    hits = sum(1 for term in terms if term in haystack)
    if hits == 0:
        return False
    if len(terms) <= 3:
        return hits == len(terms)
    required = max(1, int((len(terms) * 0.6) + 0.999))
    return hits >= required


def _text_query_terms(query: str) -> tuple[str, ...]:
    terms = []
    for raw in re.findall(r"[a-z0-9][a-z0-9_-]*", query.lower()):
        if len(raw) < 3 or raw in _TEXT_QUERY_STOPWORDS:
            continue
        terms.append(raw)
    return tuple(dict.fromkeys(terms))


def _atom_text_haystack(atom: MemoryAtom) -> str:
    metadata_text = _metadata_text(atom.metadata)
    parts = (
        atom.atom_id,
        atom.surface_id,
        atom.atom_type.value,
        atom.content_ref,
        atom.content or "",
        atom.source_path,
        " ".join(atom.source_refs),
        metadata_text,
    )
    return " ".join(str(part).lower() for part in parts if part)


def _metadata_text(value: Any, *, _depth: int = 0) -> str:
    if _depth > 3:
        return ""
    if isinstance(value, dict):
        return " ".join(
            _metadata_text(item, _depth=_depth + 1)
            for key, item in value.items()
            if not _looks_sensitive_metadata_key(str(key))
        )
    if isinstance(value, (list, tuple, set)):
        return " ".join(_metadata_text(item, _depth=_depth + 1) for item in value)
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


def _looks_sensitive_metadata_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in ("api_key", "apikey", "password", "private_key", "secret", "token")
    )


def freshness_lag(
    timestamp: str | None,
    source_last_modified: str | None,
) -> float | None:
    atom_time = _parse_timestamp(timestamp)
    source_time = _parse_timestamp(source_last_modified)
    if atom_time is None or source_time is None:
        return None
    return max(0.0, source_time.timestamp() - atom_time.timestamp())


def _authority_rank(authority: AuthorityLevel) -> int:
    if not _AUTHORITY_RANK:
        _AUTHORITY_RANK.update(
            {
                AuthorityLevel.NONE: 0,
                AuthorityLevel.LOW: 1,
                AuthorityLevel.MEDIUM: 2,
                AuthorityLevel.HIGH: 3,
                AuthorityLevel.CANONICAL: 4,
            }
        )
    return _AUTHORITY_RANK[authority]


def _risk_rank(risk: RiskLevel) -> int:
    if not _RISK_RANK:
        _RISK_RANK.update(
            {
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 1,
                RiskLevel.HIGH: 2,
                RiskLevel.CRITICAL: 3,
                RiskLevel.UNKNOWN: 4,
            }
        )
    return _RISK_RANK[risk]


def _timestamp_at_or_after(timestamp: str | None, since: str | None) -> bool:
    if not since:
        return True
    if not timestamp:
        return False
    timestamp_dt = _parse_timestamp(timestamp)
    since_dt = _parse_timestamp(since)
    if timestamp_dt and since_dt:
        return timestamp_dt >= since_dt
    return timestamp >= since


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
