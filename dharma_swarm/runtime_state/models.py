"""Frozen dataclass records + receipt/identity vocab constants.

Mechanical split from the former dharma_swarm/runtime_state.py (item 6a).
Zero logic change: definitions are verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ._util import _utc_now


RUNTIME_RECEIPT_TYPES = frozenset(
    {
        "task_claim",
        "delegation_run",
        "side_effect_intent",
        "side_effect_complete",
        "artifact",
        "artifact_written",
        "message_consumed",
        "identity_mapping",
        "idempotency_consumed",
        "runtime_warrant",
        "topology_state",
        "topology_handoff",
        "ontology_action_requested",
        "ontology_action_applied",
        "child_spawned",
        "child_completed",
        "self_mod_proposal",
        "self_mod_gate",
        "self_mod_apply",
        "self_mod_verify",
        "self_mod_promote",
        "self_mod_revert",
    }
)

MAPPING_ID_KINDS = frozenset(
    {
        "workflow_id",
        "proposal_id",
        "event_id",
        "message_id",
        "ontology_action_id",
        "engine_artifact_id",
    }
)

MAPPING_IDENTITY_FIELDS = {
    "proposal_id": "proposal_id",
    "event_id": "event_id",
    "message_id": "message_id",
    "engine_artifact_id": "artifact_id",
}

SELF_MOD_RECEIPT_TYPES = frozenset(
    {
        "self_mod_proposal",
        "self_mod_gate",
        "self_mod_apply",
        "self_mod_verify",
        "self_mod_promote",
        "self_mod_revert",
    }
)

_EXECUTION_IDENTITY_CONFLICT_FIELDS = (
    "trace_id",
    "correlation_id",
    "task_id",
    "claim_id",
    "idempotency_key",
    "causation_id",
    "parent_run_id",
    "agent_id",
    "session_id",
    "external_a2a_task_id",
    "message_id",
    "event_id",
    "artifact_id",
    "proposal_id",
)


@dataclass(frozen=True)
class SessionState:
    session_id: str
    operator_id: str = ""
    status: str = "active"
    current_task_id: str = ""
    active_bundle_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class TaskClaim:
    claim_id: str
    task_id: str
    agent_id: str
    status: str = "claimed"
    session_id: str = ""
    claimed_at: datetime = field(default_factory=_utc_now)
    acked_at: datetime | None = None
    heartbeat_at: datetime | None = None
    stale_after: datetime | None = None
    recovered_at: datetime | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DelegationRun:
    run_id: str
    task_id: str
    assigned_to: str
    status: str = "queued"
    session_id: str = ""
    claim_id: str = ""
    parent_run_id: str = ""
    assigned_by: str = ""
    requested_output: list[str] = field(default_factory=list)
    current_artifact_id: str = ""
    started_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = None
    failure_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TopologyStateRecord:
    run_id: str
    task_id: str
    topology: str
    schema_version: str = "topology_state_record.v1"
    session_id: str = ""
    active_agent: str = ""
    current_node: str = ""
    checkpoint_id: str = ""
    parent_run_id: str = ""
    child_run_ids: list[str] = field(default_factory=list)
    allowed_handoffs: dict[str, list[str]] = field(default_factory=dict)
    handoff_receipts: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class WorkspaceLease:
    lease_id: str
    zone_path: str
    mode: str
    holder_run_id: str = ""
    base_hash: str = ""
    acquired_at: datetime = field(default_factory=_utc_now)
    expires_at: datetime | None = None
    released_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    artifact_kind: str
    session_id: str = ""
    task_id: str = ""
    run_id: str = ""
    trace_id: str = ""
    manifest_path: str = ""
    payload_path: str = ""
    checksum: str = ""
    parent_artifact_id: str = ""
    promotion_state: str = "ephemeral"
    created_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryFact:
    fact_id: str
    fact_kind: str
    truth_state: str
    text: str
    confidence: float = 0.0
    session_id: str = ""
    task_id: str = ""
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source_event_id: str = ""
    source_artifact_id: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class MemoryEdge:
    edge_id: str
    from_fact_id: str
    to_fact_id: str
    relation: str
    weight: float = 0.0
    source_event_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class ContextBundleRecord:
    bundle_id: str
    session_id: str
    task_id: str = ""
    run_id: str = ""
    token_budget: int = 0
    rendered_text: str = ""
    sections: list[dict[str, Any]] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    checksum: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatorAction:
    action_id: str
    action_name: str
    actor: str
    session_id: str = ""
    task_id: str = ""
    run_id: str = ""
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class SessionEventRecord:
    event_id: str
    session_id: str
    ledger_kind: str
    event_name: str
    task_id: str = ""
    run_id: str = ""
    agent_id: str = ""
    summary: str = ""
    event_text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class RuntimeReceipt:
    receipt_id: str
    receipt_type: str
    status: str
    run_id: str = ""
    task_id: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    parent_run_id: str = ""
    agent_id: str = ""
    idempotency_key: str = ""
    side_effect_key: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class IdempotencyRecord:
    idempotency_key: str
    side_effect_key: str
    status: str
    run_id: str = ""
    task_id: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    result_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
