"""Shell-neutral canonical contracts for the DGC operator brain.

The current repo has multiple shells and multiple partial truth models.
These dataclasses define the smallest shared contract surface that both the
terminal and dashboard can build against while the internals converge.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class RuntimeHealth(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RuntimeTruthState(StrEnum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"
    MISSING = "missing"
    SOURCE_OWNED = "source_owned"
    PROJECTION_ONLY = "projection_only"
    CACHE_ONLY = "cache_only"
    READY_BY_PROBE = "ready_by_probe"
    NOT_READY_BY_PROBE = "not_ready_by_probe"
    UNKNOWN_BY_PROBE_ERROR = "unknown_by_probe_error"
    DEGRADED_BY_PROBE_TIMEOUT = "degraded_by_probe_timeout"
    RUNNING_BY_HEARTBEAT = "running_by_heartbeat"
    PROGRESSING_BY_ARTIFACT = "progressing_by_artifact"
    STALLED_BY_ARTIFACT_PROGRESS = "stalled_by_artifact_progress"
    BLOCKED_BY_RECEIPT = "blocked_by_receipt"
    COMPLETED_BY_RECEIPT = "completed_by_receipt"
    EXTERNAL_GATED = "external_gated"
    NO_MUTATION_OBSERVED = "no_mutation_observed"
    MUTATION_OBSERVED = "mutation_observed"
    DRY_RUN_ONLY = "dry_run_only"
    RETRY_EQUIVALENT = "retry_equivalent"
    RETRY_PARAMETER_MISMATCH = "retry_parameter_mismatch"
    EVALUATOR_PASS = "evaluator_pass"
    EVALUATOR_RETRY = "evaluator_retry"
    EVALUATOR_BLOCKED = "evaluator_blocked"


class PermissionRisk(StrEnum):
    SAFE_READ = "safe_read"
    WORKSPACE_MUTATION = "workspace_mutation"
    CROSS_BOUNDARY_MUTATION = "cross_boundary_mutation"
    SHELL_OR_NETWORK = "shell_or_network"
    DESTRUCTIVE = "destructive"


class PermissionDecisionKind(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class PermissionResolutionKind(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class PermissionOutcomeKind(StrEnum):
    RUNTIME_RECORDED = "runtime_recorded"
    RUNTIME_RECORD_FAILED = "runtime_record_failed"
    RUNTIME_APPLIED = "runtime_applied"
    RUNTIME_REJECTED = "runtime_rejected"
    RUNTIME_EXPIRED = "runtime_expired"


class EventTransport(StrEnum):
    LOCAL = "local"
    STDIO = "stdio"
    WS = "ws"
    HTTP = "http"
    FILE = "file"


class EventSource(StrEnum):
    OPERATOR = "operator"
    PROVIDER = "provider"
    RUNTIME = "runtime"
    GOVERNANCE = "governance"
    WORKFLOW = "workflow"
    SYSTEM = "system"


class EventAudience(StrEnum):
    CORE = "core"
    TUI = "tui"
    DASHBOARD = "dashboard"
    AUDIT = "audit"
    ALL = "all"


class WorkflowExecutionMode(StrEnum):
    IDLE = "idle"
    READ_PARALLEL = "read_parallel"
    SERIAL_WRITE = "serial_write"
    MIXED = "mixed"


@dataclass(slots=True, frozen=True)
class EntityRef:
    kind: str
    id: str


@dataclass(slots=True, frozen=True)
class EntityBadge:
    label: str
    tone: RuntimeHealth = RuntimeHealth.UNKNOWN


@dataclass(slots=True, frozen=True)
class RuntimeTruthPacket:
    """Read-only reconciliation packet projected from existing truth owners."""

    surface_id: str
    kind: str
    observed_at: str
    owner_surface: str
    source_kind: str
    run_id: str | None = None
    mission_id: str | None = None
    mission_id_missing: bool = False
    correlation_id: str | None = None
    correlation_id_inferred: bool = False
    task_id: str | None = None
    claim_id: str | None = None
    runner_id: str | None = None
    receipt_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    startup_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    heartbeat_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    readiness_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    progress_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    completion_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    authority_state: RuntimeTruthState = RuntimeTruthState.PROJECTION_ONLY
    mutation_state: RuntimeTruthState = RuntimeTruthState.NO_MUTATION_OBSERVED
    source_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    projection_state: RuntimeTruthState = RuntimeTruthState.PROJECTION_ONLY
    external_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    retry_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    evaluator_state: RuntimeTruthState = RuntimeTruthState.UNKNOWN
    probe_ok: bool | None = None
    probe_error: str | None = None
    stale_after: str | None = None
    stale_reason: str | None = None
    last_heartbeat_at: str | None = None
    last_progress_at: str | None = None
    last_receipt_at: str | None = None
    loop_iteration: int | None = None
    retry_intent_key: str | None = None
    eval_refs: list[str] = field(default_factory=list)
    stop_reason: str | None = None
    missing_machine_fields: list[str] = field(default_factory=list)
    proof_grade: str = "MISSING"
    is_authoritative: bool = False
    is_projection: bool = True
    projection_lag: str | None = None
    projection_source_refs: list[str] = field(default_factory=list)
    projection_rebuildable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_authoritative:
            raise ValueError(
                "RuntimeTruthPacket is a read model; authority lives in owner surfaces"
            )
        for name in (
            "receipt_refs",
            "artifact_refs",
            "source_refs",
            "eval_refs",
            "missing_machine_fields",
            "projection_source_refs",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "metadata", _freeze_runtime_truth_value(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready machine row without making this packet authority."""

        def encode(value: Any) -> Any:
            if isinstance(value, StrEnum):
                return value.value
            if isinstance(value, tuple | list):
                return [encode(item) for item in value]
            if isinstance(value, Mapping):
                return {str(key): encode(item) for key, item in value.items()}
            return value

        return {item.name: encode(getattr(self, item.name)) for item in fields(self)}


def _freeze_runtime_truth_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze_runtime_truth_value(item)
            for key, item in value.items()
        })
    if isinstance(value, tuple | list):
        return tuple(_freeze_runtime_truth_value(item) for item in value)
    return value


@dataclass(slots=True)
class CanonicalEntity:
    """Cross-shell entity representation.

    Raw route/API objects should map into this before the shell renders cards,
    inspectors, or drilldowns. `raw` is intentionally preserved during the
    convergence period so existing routes can adopt incrementally.
    """

    kind: str
    id: str
    title: str
    source_route: str
    subtitle: str | None = None
    description: str | None = None
    status: RuntimeHealth = RuntimeHealth.UNKNOWN
    timestamp: str | None = None
    href: str | None = None
    score: float | None = None
    badges: list[EntityBadge] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalRelation:
    kind: str
    from_ref: EntityRef
    to_ref: EntityRef
    label: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CanonicalSession:
    session_id: str
    provider_id: str
    model_id: str
    cwd: str
    created_at: str
    updated_at: str
    status: str
    parent_session_id: str | None = None
    branch_label: str | None = None
    worktree_path: str | None = None
    summary: str | None = None
    pinned_context: list[str] = field(default_factory=list)
    compacted_from_session_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalPermissionDecision:
    action_id: str
    tool_name: str
    risk: PermissionRisk
    decision: PermissionDecisionKind
    rationale: str
    policy_source: str
    requires_confirmation: bool
    command_prefix: str | None = None
    workspace_scope: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalPermissionResolution:
    action_id: str
    resolution: PermissionResolutionKind
    resolved_at: str
    actor: str
    summary: str
    note: str | None = None
    enforcement_state: str = "recorded_only"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalPermissionOutcome:
    action_id: str
    outcome: PermissionOutcomeKind
    outcome_at: str
    source: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalRoutingDecision:
    route_id: str
    provider_id: str
    model_id: str
    strategy: str
    reason: str
    fallback_chain: list[str] = field(default_factory=list)
    degraded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalRuntimeSnapshot:
    snapshot_id: str
    created_at: str
    repo_root: str
    runtime_db: str | None
    health: RuntimeHealth
    bridge_status: str
    active_session_count: int
    active_run_count: int
    artifact_count: int
    context_bundle_count: int
    anomaly_count: int
    verification_status: str
    next_task: str | None = None
    active_task: str | None = None
    worktree_count: int | None = None
    summary: str | None = None
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalWorkflowState:
    workflow_id: str
    title: str
    execution_mode: WorkflowExecutionMode
    status: str
    active_lane_ids: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    writable_scopes: list[str] = field(default_factory=list)
    next_action: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalEventEnvelope:
    """Canonical event envelope shared by shells and core services."""

    event_id: str
    event_type: str
    source: EventSource
    audience: EventAudience
    transport: EventTransport
    session_id: str | None
    created_at: str
    payload: dict[str, Any] = field(default_factory=dict)
    entity_refs: list[EntityRef] = field(default_factory=list)
    correlation_id: str | None = None
    raw: dict[str, Any] | None = None
