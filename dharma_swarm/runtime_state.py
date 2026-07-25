"""Canonical SQLite runtime state spine for DGC vNext.

This module provides the structured source-of-truth layer for single-host
orchestration. It complements the append-only JSONL ledgers and the derived
memory/retrieval indexes by keeping live control-plane state explicit,
transactional, and inspectable.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from dharma_swarm.correlation_context import get_correlation
from dharma_swarm.engine.event_memory import (
    ensure_memory_plane_schema_async,
    ensure_memory_plane_schema_sync,
)
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

DEFAULT_RUNTIME_DB = Path.home() / ".dharma" / "state" / "runtime.db"

_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    current_task_id TEXT NOT NULL DEFAULT '',
    active_bundle_id TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)"""

_TASK_CLAIMS_DDL = """
CREATE TABLE IF NOT EXISTS task_claims (
    claim_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    acked_at TEXT,
    heartbeat_at TEXT,
    stale_after TEXT,
    recovered_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    trace_id TEXT NOT NULL DEFAULT ''
)"""

_DELEGATION_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS delegation_runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL,
    claim_id TEXT NOT NULL DEFAULT '',
    parent_run_id TEXT NOT NULL DEFAULT '',
    assigned_by TEXT NOT NULL DEFAULT '',
    assigned_to TEXT NOT NULL,
    requested_output_json TEXT NOT NULL DEFAULT '[]',
    current_artifact_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    failure_code TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    trace_id TEXT NOT NULL DEFAULT '',
    receipt_json TEXT
)"""

_TOPOLOGY_STATES_DDL = """
CREATE TABLE IF NOT EXISTS topology_states (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL,
    topology TEXT NOT NULL,
    active_agent TEXT NOT NULL DEFAULT '',
    current_node TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL DEFAULT '',
    parent_run_id TEXT NOT NULL DEFAULT '',
    child_run_ids_json TEXT NOT NULL DEFAULT '[]',
    allowed_handoffs_json TEXT NOT NULL DEFAULT '{}',
    handoff_receipts_json TEXT NOT NULL DEFAULT '[]',
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)"""

_WORKSPACE_LEASES_DDL = """
CREATE TABLE IF NOT EXISTS workspace_leases (
    lease_id TEXT PRIMARY KEY,
    zone_path TEXT NOT NULL,
    holder_run_id TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL,
    base_hash TEXT NOT NULL DEFAULT '',
    acquired_at TEXT NOT NULL,
    expires_at TEXT,
    released_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
)"""

_ARTIFACT_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS artifact_records (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    artifact_kind TEXT NOT NULL,
    manifest_path TEXT NOT NULL DEFAULT '',
    payload_path TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL DEFAULT '',
    parent_artifact_id TEXT NOT NULL DEFAULT '',
    promotion_state TEXT NOT NULL DEFAULT 'ephemeral',
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
)"""

_ARTIFACT_LINKS_DDL = """
CREATE TABLE IF NOT EXISTS artifact_links (
    link_id TEXT PRIMARY KEY,
    from_artifact_id TEXT NOT NULL,
    to_artifact_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
)"""

_MEMORY_FACTS_DDL = """
CREATE TABLE IF NOT EXISTS memory_facts (
    fact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    fact_kind TEXT NOT NULL,
    truth_state TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    valid_from TEXT,
    valid_to TEXT,
    source_event_id TEXT NOT NULL DEFAULT '',
    source_artifact_id TEXT NOT NULL DEFAULT '',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)"""

_MEMORY_EDGES_DDL = """
CREATE TABLE IF NOT EXISTS memory_edges (
    edge_id TEXT PRIMARY KEY,
    from_fact_id TEXT NOT NULL,
    to_fact_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 0.0,
    source_event_id TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
)"""

_CONTEXT_BUNDLES_DDL = """
CREATE TABLE IF NOT EXISTS context_bundles (
    bundle_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    token_budget INTEGER NOT NULL,
    rendered_text TEXT NOT NULL,
    sections_json TEXT NOT NULL DEFAULT '[]',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    checksum TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
)"""

_OPERATOR_ACTIONS_DDL = """
CREATE TABLE IF NOT EXISTS operator_actions (
    action_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    action_name TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
)"""

_SESSION_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS session_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    ledger_kind TEXT NOT NULL,
    event_name TEXT NOT NULL,
    task_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    event_text TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
)"""

_SESSION_EVENTS_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS session_events_fts USING fts5(
    event_id UNINDEXED,
    session_id UNINDEXED,
    ledger_kind UNINDEXED,
    event_name,
    task_id,
    run_id,
    agent_id,
    summary,
    event_text,
    created_at UNINDEXED,
    tokenize='porter unicode61'
)"""

_EXECUTION_IDENTITIES_DDL = """
CREATE TABLE IF NOT EXISTS execution_identities (
    run_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    claim_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    causation_id TEXT NOT NULL DEFAULT '',
    parent_run_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    external_a2a_task_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    event_id TEXT NOT NULL DEFAULT '',
    artifact_id TEXT NOT NULL DEFAULT '',
    proposal_id TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)"""

_RUNTIME_RECEIPTS_DDL = """
CREATE TABLE IF NOT EXISTS runtime_receipts (
    receipt_id TEXT PRIMARY KEY,
    receipt_type TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    causation_id TEXT NOT NULL DEFAULT '',
    parent_run_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    side_effect_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
)"""

_IDEMPOTENCY_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT NOT NULL,
    side_effect_key TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    result_receipt_id TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (idempotency_key, side_effect_key)
)"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sessions_status_updated ON sessions(status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_claims_task_status ON task_claims(task_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_claims_agent_status ON task_claims(agent_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_runs_task_status ON delegation_runs(task_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_runs_session_started ON delegation_runs(session_id, started_at)",
    "CREATE INDEX IF NOT EXISTS idx_topology_states_session_updated ON topology_states(session_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_topology_states_task_updated ON topology_states(task_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_topology_states_topology_updated ON topology_states(topology, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_leases_zone_released ON workspace_leases(zone_path, released_at)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_task_created ON artifact_records(task_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_run_created ON artifact_records(run_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_trace_created ON artifact_records(trace_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_memory_truth_updated ON memory_facts(truth_state, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_memory_task_truth ON memory_facts(task_id, truth_state)",
    "CREATE INDEX IF NOT EXISTS idx_context_session_created ON context_bundles(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_context_task_created ON context_bundles(task_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_operator_actions_session_created ON operator_actions(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_session_events_session_created ON session_events(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_session_events_kind_created ON session_events(ledger_kind, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_exec_identity_trace ON execution_identities(trace_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_identity_correlation ON execution_identities(correlation_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_identity_task ON execution_identities(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_identity_external_a2a ON execution_identities(external_a2a_task_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_identity_parent ON execution_identities(parent_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_runtime_receipts_run_created ON runtime_receipts(run_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_runtime_receipts_trace_created ON runtime_receipts(trace_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_runtime_receipts_idempotency ON runtime_receipts(idempotency_key)",
    "CREATE INDEX IF NOT EXISTS idx_idempotency_run ON idempotency_records(run_id)",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _next_idempotency_token(
    observed: datetime | None, floor: datetime | None = None,
) -> str:
    candidates = [_utc_now()]
    if observed is not None:
        observed = observed.replace(tzinfo=observed.tzinfo or timezone.utc)
        candidates.append(observed + timedelta(microseconds=1))
    if floor is not None:
        candidates.append(floor.replace(tzinfo=floor.tzinfo or timezone.utc))
    return max(candidates).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


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


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


# Wait up to this long for a competing writer to release the write lock before
# raising "database is locked". WAL lets readers and a writer coexist, but two
# writers still serialize; without a busy timeout the loser fails instantly.
_BUSY_TIMEOUT_MS = 5_000


def _apply_connection_pragmas_sync(db: sqlite3.Connection) -> None:
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")


async def _apply_connection_pragmas_async(db: aiosqlite.Connection) -> None:
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")


def ensure_runtime_state_schema_sync(
    db: sqlite3.Connection,
    *,
    include_memory_plane: bool = True,
) -> None:
    """Create runtime-state tables on a sync SQLite connection."""
    _apply_connection_pragmas_sync(db)
    for ddl in (
        _SESSIONS_DDL,
        _TASK_CLAIMS_DDL,
        _DELEGATION_RUNS_DDL,
        _TOPOLOGY_STATES_DDL,
        _WORKSPACE_LEASES_DDL,
        _ARTIFACT_RECORDS_DDL,
        _ARTIFACT_LINKS_DDL,
        _MEMORY_FACTS_DDL,
        _MEMORY_EDGES_DDL,
        _CONTEXT_BUNDLES_DDL,
        _OPERATOR_ACTIONS_DDL,
        _SESSION_EVENTS_DDL,
        _SESSION_EVENTS_FTS_DDL,
        _EXECUTION_IDENTITIES_DDL,
        _RUNTIME_RECEIPTS_DDL,
        _IDEMPOTENCY_RECORDS_DDL,
    ):
        db.execute(ddl)
    for tbl, column_sql in (
        ("task_claims", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "receipt_json TEXT"),
        ("artifact_records", "trace_id TEXT NOT NULL DEFAULT ''"),
    ):
        try:
            db.execute(f"ALTER TABLE {tbl} ADD COLUMN {column_sql}")
        except sqlite3.Error:
            pass
    for idx in _INDEXES:
        db.execute(idx)
    if include_memory_plane:
        ensure_memory_plane_schema_sync(db)
    db.commit()


async def ensure_runtime_state_schema_async(
    db: aiosqlite.Connection,
    *,
    include_memory_plane: bool = True,
) -> None:
    """Create runtime-state tables on an async SQLite connection."""
    await _apply_connection_pragmas_async(db)
    for ddl in (
        _SESSIONS_DDL,
        _TASK_CLAIMS_DDL,
        _DELEGATION_RUNS_DDL,
        _TOPOLOGY_STATES_DDL,
        _WORKSPACE_LEASES_DDL,
        _ARTIFACT_RECORDS_DDL,
        _ARTIFACT_LINKS_DDL,
        _MEMORY_FACTS_DDL,
        _MEMORY_EDGES_DDL,
        _CONTEXT_BUNDLES_DDL,
        _OPERATOR_ACTIONS_DDL,
        _SESSION_EVENTS_DDL,
        _SESSION_EVENTS_FTS_DDL,
        _EXECUTION_IDENTITIES_DDL,
        _RUNTIME_RECEIPTS_DDL,
        _IDEMPOTENCY_RECORDS_DDL,
    ):
        await db.execute(ddl)
    # Migrate old runtime DBs without changing existing rows destructively.
    for tbl, column_sql in (
        ("task_claims", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "receipt_json TEXT"),
        ("artifact_records", "trace_id TEXT NOT NULL DEFAULT ''"),
    ):
        try:
            await db.execute(f"ALTER TABLE {tbl} ADD COLUMN {column_sql}")
        except Exception:
            pass  # column already exists
    for idx in _INDEXES:
        await db.execute(idx)
    if include_memory_plane:
        await ensure_memory_plane_schema_async(db)
    await db.commit()


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


_IDENTITY_REQUIRED_RECEIPT_TYPES = {"task_claim", "delegation_run"}
_PROVIDER_ACCOUNTED_RECEIPT_TYPES = {"task_claim", "delegation_run"}
_RUNTIME_PROVIDER_ACTUAL_SERVED_TRUTH_SOURCE = "runtime_provider.actual_served"


def _payload_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _payload_falseish(value: Any) -> bool:
    return value is False or str(value or "").strip().lower() in {"false", "0", "no"}


def _payload_trueish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"true", "1", "yes"}


def _runtime_receipt_provider_model_accounted(receipt: RuntimeReceipt) -> bool:
    payload = dict(receipt.payload or {})
    truth_source = _payload_text(
        payload,
        "provider_model_truth_source",
        "route_truth_source",
    )
    if not truth_source:
        return False

    served_provider = _payload_text(
        payload,
        "actual_served_provider",
        "served_provider",
        "actual_provider",
        "provider_served",
    )
    served_model = _payload_text(
        payload,
        "actual_served_model",
        "served_model",
        "actual_model",
        "model_served",
    )
    if served_provider and served_model:
        return truth_source == _RUNTIME_PROVIDER_ACTUAL_SERVED_TRUTH_SOURCE

    provider_execution = payload.get("provider_execution")
    applicability = _payload_text(payload, "provider_model_applicability")
    if _payload_falseish(provider_execution):
        return bool(
            applicability == "not_applicable"
            and _payload_text(payload, "no_provider_model_reason")
        )
    if str(provider_execution or "").strip().lower() == "pending":
        return applicability == "pending_execution"
    if _payload_trueish(provider_execution):
        return bool(
            applicability
            and _payload_text(payload, "provider_model_missing_reason")
        )
    return False


def _validate_runtime_receipt_identity(receipt: RuntimeReceipt) -> None:
    if receipt.receipt_type not in _IDENTITY_REQUIRED_RECEIPT_TYPES:
        return
    if not str(receipt.idempotency_key or "").strip():
        raise ValueError(
            f"{receipt.receipt_type} runtime receipts require a non-empty idempotency_key"
        )
    if not str(receipt.side_effect_key or "").strip():
        raise ValueError(
            f"{receipt.receipt_type} runtime receipts require a non-empty side_effect_key"
        )
    if (
        receipt.receipt_type in _PROVIDER_ACCOUNTED_RECEIPT_TYPES
        and not _runtime_receipt_provider_model_accounted(receipt)
    ):
        raise ValueError(
            f"{receipt.receipt_type} runtime receipts require provider/model truth "
            "or explicit no-provider/pending applicability"
        )


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


def _row_to_session(row: sqlite3.Row | aiosqlite.Row) -> SessionState:
    return SessionState(
        session_id=str(row["session_id"]),
        operator_id=str(row["operator_id"] or ""),
        status=str(row["status"]),
        current_task_id=str(row["current_task_id"] or ""),
        active_bundle_id=str(row["active_bundle_id"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _row_to_claim(row: sqlite3.Row | aiosqlite.Row) -> TaskClaim:
    return TaskClaim(
        claim_id=str(row["claim_id"]),
        task_id=str(row["task_id"]),
        agent_id=str(row["agent_id"]),
        status=str(row["status"]),
        session_id=str(row["session_id"] or ""),
        claimed_at=_parse_dt(row["claimed_at"]) or _utc_now(),
        acked_at=_parse_dt(row["acked_at"]),
        heartbeat_at=_parse_dt(row["heartbeat_at"]),
        stale_after=_parse_dt(row["stale_after"]),
        recovered_at=_parse_dt(row["recovered_at"]),
        retry_count=int(row["retry_count"] or 0),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_run(row: sqlite3.Row | aiosqlite.Row) -> DelegationRun:
    return DelegationRun(
        run_id=str(row["run_id"]),
        task_id=str(row["task_id"]),
        assigned_to=str(row["assigned_to"]),
        status=str(row["status"]),
        session_id=str(row["session_id"] or ""),
        claim_id=str(row["claim_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        assigned_by=str(row["assigned_by"] or ""),
        requested_output=list(_json_load(row["requested_output_json"], [])),
        current_artifact_id=str(row["current_artifact_id"] or ""),
        started_at=_parse_dt(row["started_at"]) or _utc_now(),
        completed_at=_parse_dt(row["completed_at"]),
        failure_code=str(row["failure_code"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_topology_state(row: sqlite3.Row | aiosqlite.Row) -> TopologyStateRecord:
    child_run_ids = _json_load(row["child_run_ids_json"], [])
    if not isinstance(child_run_ids, list):
        child_run_ids = []
    allowed = _json_load(row["allowed_handoffs_json"], {})
    if not isinstance(allowed, dict):
        allowed = {}
    normalized_allowed: dict[str, list[str]] = {}
    for key, value in allowed.items():
        if isinstance(value, (list, tuple, set)):
            normalized_allowed[str(key)] = [str(item) for item in value]
    handoffs = _json_load(row["handoff_receipts_json"], [])
    if not isinstance(handoffs, list):
        handoffs = []
    return TopologyStateRecord(
        run_id=str(row["run_id"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"]),
        topology=str(row["topology"]),
        active_agent=str(row["active_agent"] or ""),
        current_node=str(row["current_node"] or ""),
        checkpoint_id=str(row["checkpoint_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        child_run_ids=[str(item) for item in child_run_ids],
        allowed_handoffs=normalized_allowed,
        handoff_receipts=[item for item in handoffs if isinstance(item, dict)],
        state=_json_load(row["state_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _row_to_lease(row: sqlite3.Row | aiosqlite.Row) -> WorkspaceLease:
    return WorkspaceLease(
        lease_id=str(row["lease_id"]),
        zone_path=str(row["zone_path"]),
        mode=str(row["mode"]),
        holder_run_id=str(row["holder_run_id"] or ""),
        base_hash=str(row["base_hash"] or ""),
        acquired_at=_parse_dt(row["acquired_at"]) or _utc_now(),
        expires_at=_parse_dt(row["expires_at"]),
        released_at=_parse_dt(row["released_at"]),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_artifact(row: sqlite3.Row | aiosqlite.Row) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=str(row["artifact_id"]),
        artifact_kind=str(row["artifact_kind"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        trace_id=str(row["trace_id"] or "") if "trace_id" in row.keys() else "",
        manifest_path=str(row["manifest_path"] or ""),
        payload_path=str(row["payload_path"] or ""),
        checksum=str(row["checksum"] or ""),
        parent_artifact_id=str(row["parent_artifact_id"] or ""),
        promotion_state=str(row["promotion_state"] or "ephemeral"),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_memory_fact(row: sqlite3.Row | aiosqlite.Row) -> MemoryFact:
    return MemoryFact(
        fact_id=str(row["fact_id"]),
        fact_kind=str(row["fact_kind"]),
        truth_state=str(row["truth_state"]),
        text=str(row["text"]),
        confidence=float(row["confidence"] or 0.0),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        valid_from=_parse_dt(row["valid_from"]),
        valid_to=_parse_dt(row["valid_to"]),
        source_event_id=str(row["source_event_id"] or ""),
        source_artifact_id=str(row["source_artifact_id"] or ""),
        provenance=_json_load(row["provenance_json"], {}),
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _row_to_context_bundle(row: sqlite3.Row | aiosqlite.Row) -> ContextBundleRecord:
    return ContextBundleRecord(
        bundle_id=str(row["bundle_id"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        token_budget=int(row["token_budget"] or 0),
        rendered_text=str(row["rendered_text"] or ""),
        sections=list(_json_load(row["sections_json"], [])),
        source_refs=list(_json_load(row["source_refs_json"], [])),
        checksum=str(row["checksum"] or ""),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_operator_action(row: sqlite3.Row | aiosqlite.Row) -> OperatorAction:
    return OperatorAction(
        action_id=str(row["action_id"]),
        action_name=str(row["action_name"]),
        actor=str(row["actor"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        reason=str(row["reason"] or ""),
        payload=_json_load(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_session_event(row: sqlite3.Row | aiosqlite.Row) -> SessionEventRecord:
    return SessionEventRecord(
        event_id=str(row["event_id"]),
        session_id=str(row["session_id"] or ""),
        ledger_kind=str(row["ledger_kind"]),
        event_name=str(row["event_name"]),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        summary=str(row["summary"] or ""),
        event_text=str(row["event_text"] or ""),
        payload=_json_load(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_execution_identity(row: sqlite3.Row | aiosqlite.Row) -> ExecutionIdentity:
    return ExecutionIdentity(
        trace_id=str(row["trace_id"]),
        correlation_id=str(row["correlation_id"]),
        task_id=str(row["task_id"]),
        run_id=str(row["run_id"]),
        claim_id=str(row["claim_id"] or ""),
        idempotency_key=str(row["idempotency_key"] or ""),
        causation_id=str(row["causation_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        session_id=str(row["session_id"] or ""),
        external_a2a_task_id=str(row["external_a2a_task_id"] or ""),
        message_id=str(row["message_id"] or ""),
        event_id=str(row["event_id"] or ""),
        artifact_id=str(row["artifact_id"] or ""),
        proposal_id=str(row["proposal_id"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_runtime_receipt(row: sqlite3.Row | aiosqlite.Row) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id=str(row["receipt_id"]),
        receipt_type=str(row["receipt_type"]),
        status=str(row["status"]),
        run_id=str(row["run_id"] or ""),
        task_id=str(row["task_id"] or ""),
        trace_id=str(row["trace_id"] or ""),
        correlation_id=str(row["correlation_id"] or ""),
        causation_id=str(row["causation_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        idempotency_key=str(row["idempotency_key"] or ""),
        side_effect_key=str(row["side_effect_key"] or ""),
        payload=_json_load(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_idempotency_record(row: sqlite3.Row | aiosqlite.Row) -> IdempotencyRecord:
    return IdempotencyRecord(
        idempotency_key=str(row["idempotency_key"]),
        side_effect_key=str(row["side_effect_key"]),
        status=str(row["status"]),
        run_id=str(row["run_id"] or ""),
        task_id=str(row["task_id"] or ""),
        trace_id=str(row["trace_id"] or ""),
        correlation_id=str(row["correlation_id"] or ""),
        result_receipt_id=str(row["result_receipt_id"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _operation_hash(metadata: dict[str, Any] | None) -> str:
    return str((metadata or {}).get("operation_hash") or "")


def _merge_idempotency_metadata(
    existing: IdempotencyRecord,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(existing.metadata)
    merged.update(metadata or {})
    return merged


def _execution_identity_conflicts(
    existing: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
) -> dict[str, dict[str, str]]:
    if existing is None:
        return {}
    conflicts: dict[str, dict[str, str]] = {}
    for field_name in _EXECUTION_IDENTITY_CONFLICT_FIELDS:
        existing_value = str(getattr(existing, field_name, "") or "")
        incoming_value = str(getattr(incoming, field_name, "") or "")
        if existing_value and incoming_value and existing_value != incoming_value:
            conflicts[field_name] = {
                "existing": existing_value,
                "incoming": incoming_value,
            }
    return conflicts


def _raise_on_execution_identity_conflict(
    existing: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
) -> None:
    conflicts = _execution_identity_conflicts(existing, incoming)
    if not conflicts:
        return
    details = ", ".join(
        f"{field} existing={values['existing']!r} incoming={values['incoming']!r}"
        for field, values in sorted(conflicts.items())
    )
    raise ValueError(
        f"execution identity conflict for run_id {incoming.run_id!r}: {details}"
    )


def _identity_from_metadata(metadata: dict[str, Any] | None) -> ExecutionIdentity | None:
    return ExecutionIdentity.from_metadata(metadata, require=False)


def _required_identity_from_metadata(
    metadata: dict[str, Any] | None,
    *,
    task_id: str,
    agent_id: str = "",
    session_id: str = "",
) -> ExecutionIdentity:
    identity = ExecutionIdentity.from_metadata(
        metadata,
        task_id=task_id,
        agent_id=agent_id,
        session_id=session_id,
        require=True,
    )
    if identity is None:
        raise MissingExecutionIdentity("ExecutionIdentity is required")
    return identity.require_for_dispatch()


def _legacy_no_identity_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {
        **dict(metadata or {}),
        "legacy_no_identity_allowed": True,
        "runtime_spine_status": "legacy_no_identity",
    }


def _metadata_with_identity(
    metadata: dict[str, Any] | None,
    identity: ExecutionIdentity,
) -> dict[str, Any]:
    return {
        **dict(metadata or {}),
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
    }


_PROVIDER_MODEL_RECEIPT_METADATA_KEYS = (
    "actual_served_provider",
    "served_provider",
    "actual_provider",
    "provider_served",
    "actual_served_model",
    "served_model",
    "actual_model",
    "model_served",
    "selected_provider",
    "provider_selected",
    "provider",
    "selected_model",
    "model_selected",
    "selected_model_hint",
    "model",
    "provider_model_truth_source",
    "route_truth_source",
    "provider_execution",
    "provider_model_applicability",
    "no_provider_model_reason",
    "provider_model_missing_reason",
    "provider_model_pending_reason",
)
_PROVIDER_MODEL_RECEIPT_CONTEXT_KEYS = (
    "actual_served_provider",
    "served_provider",
    "actual_provider",
    "provider_served",
    "actual_served_model",
    "served_model",
    "actual_model",
    "model_served",
    "provider_model_truth_source",
    "route_truth_source",
    "provider_execution",
    "provider_model_applicability",
    "no_provider_model_reason",
    "provider_model_missing_reason",
    "provider_model_pending_reason",
)


def _provider_model_receipt_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    if not any(
        key in metadata and metadata[key] not in ("", None, [], {})
        for key in _PROVIDER_MODEL_RECEIPT_CONTEXT_KEYS
    ):
        return {}
    return {
        key: metadata[key]
        for key in _PROVIDER_MODEL_RECEIPT_METADATA_KEYS
        if key in metadata and metadata[key] not in ("", None, [], {})
    }


def _ds_goal_receipt_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    preflight = metadata.get("ds_goal_longrun_preflight")
    if not isinstance(preflight, dict):
        return {}
    return {
        "ds_goal_longrun_preflight": preflight,
        "ds_goal_longrun_preflight_status": str(preflight.get("status") or ""),
        "ds_goal_longrun_preflight_passed": preflight.get("passed") is True,
        "ds_goal_default_target_repo": str(preflight.get("default_target_repo") or ""),
    }


def _task_claim_receipt_payload(claim: TaskClaim) -> dict[str, Any]:
    metadata = dict(claim.metadata or {})
    mission_id = str(
        metadata.get("mission_id")
        or metadata.get("missionId")
        or metadata.get("mission")
        or ""
    )
    mission = str(
        metadata.get("mission")
        or mission_id
        or claim.session_id
        or claim.task_id
        or ""
    )
    return {
        "claim_id": claim.claim_id,
        "mission_id": mission_id,
        "mission": mission,
        "retry_count": int(claim.retry_count),
        "receipt_status": claim.status,
        **_provider_model_receipt_payload(metadata),
        **_ds_goal_receipt_payload(metadata),
    }


def _delegation_run_receipt_payload(run: DelegationRun) -> dict[str, Any]:
    metadata = dict(run.metadata or {})
    mission_id = str(
        metadata.get("mission_id")
        or metadata.get("missionId")
        or metadata.get("mission")
        or ""
    )
    mission = str(
        metadata.get("mission")
        or mission_id
        or run.session_id
        or run.task_id
        or ""
    )
    artifact_refs = []
    current_artifact_id = str(run.current_artifact_id or "")
    if current_artifact_id:
        artifact_refs.append(f"artifact_records:{current_artifact_id}")
    return {
        "failure_code": run.failure_code,
        "mission_id": mission_id,
        "mission": mission,
        "artifact_refs": artifact_refs,
        "no_artifact_refs_reason": ""
        if artifact_refs
        else "delegation_run has no current_artifact_id",
        "receipt_status": run.status,
        **_provider_model_receipt_payload(metadata),
        **_ds_goal_receipt_payload(metadata),
    }


def _require_identity_match(
    identity: ExecutionIdentity,
    *,
    surface: str,
    task_id: str = "",
    claim_id: str = "",
    run_id: str = "",
    agent_id: str = "",
    session_id: str = "",
) -> None:
    expected = {
        "task_id": task_id,
        "claim_id": claim_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "session_id": session_id,
    }
    mismatches = [
        f"{name}={actual!r} expected {wanted!r}"
        for name, wanted in expected.items()
        if wanted and (actual := str(getattr(identity, name, "") or "")) and actual != wanted
    ]
    if mismatches:
        raise MissingExecutionIdentity(
            f"ExecutionIdentity does not match {surface}: " + ", ".join(mismatches)
        )


def _trace_from_metadata(metadata: dict[str, Any] | None) -> str:
    identity = _identity_from_metadata(metadata)
    if identity is not None and identity.trace_id:
        return identity.trace_id
    meta = dict(metadata or {})
    return str(meta.get("trace_id", "") or "")


def _flatten_search_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts: list[str] = []
        for key, inner in value.items():
            flattened = _flatten_search_text(inner)
            if flattened:
                parts.append(f"{key} {flattened}")
        return " ".join(parts)
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_search_text(item) for item in value if _flatten_search_text(item))
    return str(value)


def _session_event_summary(payload: dict[str, Any], event_text: str) -> str:
    preferred_keys = (
        "summary",
        "reason",
        "failure_signature",
        "error",
        "status",
        "artifact",
        "result",
        "assigned_to",
        "assigned_by",
    )
    parts = [
        str(payload.get(key, "")).strip()
        for key in preferred_keys
        if str(payload.get(key, "")).strip()
    ]
    summary = " | ".join(parts) if parts else event_text.strip()
    return summary[:240]


def _ledger_record_event_id(session_id: str, ledger_kind: str, record: dict[str, Any]) -> str:
    existing = str(record.get("event_id", "")).strip()
    if existing:
        return existing
    canonical = {
        "session_id": session_id,
        "ledger_kind": ledger_kind,
        "record": record,
    }
    digest = hashlib.sha256(_json_dump(canonical).encode("utf-8")).hexdigest()[:24]
    return f"sevt_{digest}"


def build_session_event_from_ledger_record(
    *,
    session_id: str,
    ledger_kind: str,
    record: dict[str, Any],
) -> SessionEventRecord:
    payload = {
        key: value
        for key, value in dict(record).items()
        if key not in {"event_id", "session_id", "ledger_kind", "ts_utc", "event"}
    }
    event_name = str(record.get("event", "")).strip() or "unknown_event"
    task_id = str(payload.get("task_id", "") or "")
    run_id = str(payload.get("run_id", "") or "")
    agent_id = str(payload.get("agent_id", "") or payload.get("claimed_by", "") or "")
    event_text = " ".join(
        part
        for part in [
            event_name,
            task_id,
            run_id,
            agent_id,
            _flatten_search_text(payload),
        ]
        if str(part).strip()
    ).strip()
    created_at = _parse_dt(str(record.get("ts_utc", "")).strip()) or _utc_now()
    return SessionEventRecord(
        event_id=_ledger_record_event_id(session_id, ledger_kind, record),
        session_id=session_id,
        ledger_kind=ledger_kind,
        event_name=event_name,
        task_id=task_id,
        run_id=run_id,
        agent_id=agent_id,
        summary=_session_event_summary(payload, event_text),
        event_text=event_text,
        payload=payload,
        created_at=created_at,
    )


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", query or "")
    return " AND ".join(f"{token}*" for token in tokens if token)


class RuntimeStateStore:
    """WAL-backed SQLite store for live runtime truth."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        include_memory_plane: bool = True,
    ) -> None:
        self.db_path = Path(db_path or DEFAULT_RUNTIME_DB)
        self.include_memory_plane = include_memory_plane

    def init_db_sync(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as db:
            ensure_runtime_state_schema_sync(
                db,
                include_memory_plane=self.include_memory_plane,
            )

    async def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await ensure_runtime_state_schema_async(
                db,
                include_memory_plane=self.include_memory_plane,
            )

    @staticmethod
    def _upsert_session_stub_sync(db: sqlite3.Connection, event: SessionEventRecord) -> None:
        current_task_id = event.task_id or ""
        created_at = event.created_at.isoformat()
        db.execute(
            "INSERT INTO sessions (session_id, operator_id, status, current_task_id,"
            " active_bundle_id, metadata_json, created_at, updated_at)"
            " VALUES (?, '', 'active', ?, '', '{}', ?, ?)"
            " ON CONFLICT(session_id) DO UPDATE SET"
            " current_task_id = CASE"
            "   WHEN excluded.current_task_id != '' THEN excluded.current_task_id"
            "   ELSE sessions.current_task_id"
            " END,"
            " updated_at = excluded.updated_at",
            (
                event.session_id,
                current_task_id,
                created_at,
                created_at,
            ),
        )

    @staticmethod
    async def _upsert_session_stub_async(
        db: aiosqlite.Connection,
        event: SessionEventRecord,
    ) -> None:
        current_task_id = event.task_id or ""
        created_at = event.created_at.isoformat()
        await db.execute(
            "INSERT INTO sessions (session_id, operator_id, status, current_task_id,"
            " active_bundle_id, metadata_json, created_at, updated_at)"
            " VALUES (?, '', 'active', ?, '', '{}', ?, ?)"
            " ON CONFLICT(session_id) DO UPDATE SET"
            " current_task_id = CASE"
            "   WHEN excluded.current_task_id != '' THEN excluded.current_task_id"
            "   ELSE sessions.current_task_id"
            " END,"
            " updated_at = excluded.updated_at",
            (
                event.session_id,
                current_task_id,
                created_at,
                created_at,
            ),
        )

    @classmethod
    def _record_session_event_sync_db(
        cls,
        db: sqlite3.Connection,
        event: SessionEventRecord,
    ) -> None:
        cls._upsert_session_stub_sync(db, event)
        db.execute(
            "INSERT OR REPLACE INTO session_events (event_id, session_id, ledger_kind,"
            " event_name, task_id, run_id, agent_id, summary, event_text, payload_json,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.session_id,
                event.ledger_kind,
                event.event_name,
                event.task_id,
                event.run_id,
                event.agent_id,
                event.summary,
                event.event_text,
                _json_dump(event.payload),
                event.created_at.isoformat(),
            ),
        )
        db.execute("DELETE FROM session_events_fts WHERE event_id = ?", (event.event_id,))
        db.execute(
            "INSERT INTO session_events_fts (event_id, session_id, ledger_kind, event_name,"
            " task_id, run_id, agent_id, summary, event_text, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.session_id,
                event.ledger_kind,
                event.event_name,
                event.task_id,
                event.run_id,
                event.agent_id,
                event.summary,
                event.event_text,
                event.created_at.isoformat(),
            ),
        )

    @classmethod
    async def _record_session_event_async_db(
        cls,
        db: aiosqlite.Connection,
        event: SessionEventRecord,
    ) -> None:
        await cls._upsert_session_stub_async(db, event)
        await db.execute(
            "INSERT OR REPLACE INTO session_events (event_id, session_id, ledger_kind,"
            " event_name, task_id, run_id, agent_id, summary, event_text, payload_json,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.session_id,
                event.ledger_kind,
                event.event_name,
                event.task_id,
                event.run_id,
                event.agent_id,
                event.summary,
                event.event_text,
                _json_dump(event.payload),
                event.created_at.isoformat(),
            ),
        )
        await db.execute("DELETE FROM session_events_fts WHERE event_id = ?", (event.event_id,))
        await db.execute(
            "INSERT INTO session_events_fts (event_id, session_id, ledger_kind, event_name,"
            " task_id, run_id, agent_id, summary, event_text, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.session_id,
                event.ledger_kind,
                event.event_name,
                event.task_id,
                event.run_id,
                event.agent_id,
                event.summary,
                event.event_text,
                event.created_at.isoformat(),
            ),
        )

    async def upsert_session(self, session: SessionState) -> SessionState:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (session_id, operator_id, status, current_task_id,"
                " active_bundle_id, metadata_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(session_id) DO UPDATE SET"
                " operator_id = excluded.operator_id,"
                " status = excluded.status,"
                " current_task_id = excluded.current_task_id,"
                " active_bundle_id = excluded.active_bundle_id,"
                " metadata_json = excluded.metadata_json,"
                " updated_at = excluded.updated_at",
                (
                    session.session_id,
                    session.operator_id,
                    session.status,
                    session.current_task_id,
                    session.active_bundle_id,
                    _json_dump(session.metadata),
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
            await db.commit()
        loaded = await self.get_session(session.session_id)
        assert loaded is not None
        return loaded

    def record_session_event_sync(self, event: SessionEventRecord) -> SessionEventRecord:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            self._record_session_event_sync_db(db, event)
            db.commit()
        return event

    async def record_session_event(self, event: SessionEventRecord) -> SessionEventRecord:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            await self._record_session_event_async_db(db, event)
            await db.commit()
        return event

    async def get_session(self, session_id: str) -> SessionState | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT session_id, operator_id, status, current_task_id,"
                    " active_bundle_id, metadata_json, created_at, updated_at"
                    " FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
            ).fetchone()
        return _row_to_session(row) if row is not None else None

    def list_sessions_sync(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[SessionState]:
        self.init_db_sync()
        query = (
            "SELECT session_id, operator_id, status, current_task_id, active_bundle_id,"
            " metadata_json, created_at, updated_at FROM sessions WHERE 1=1"
        )
        params: list[Any] = []
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, limit))
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(query, params).fetchall()
        return [_row_to_session(row) for row in rows]

    def search_session_events_sync(
        self,
        query: str,
        *,
        session_id: str | None = None,
        ledger_kind: str | None = None,
        limit: int = 20,
    ) -> list[SessionEventRecord]:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            match_query = _fts_query(query)
            base_params: list[Any] = []
            filter_sql = ""
            if session_id is not None:
                filter_sql += " AND se.session_id = ?"
                base_params.append(session_id)
            if ledger_kind is not None:
                filter_sql += " AND se.ledger_kind = ?"
                base_params.append(ledger_kind)

            if match_query:
                try:
                    rows = db.execute(
                        "SELECT se.event_id, se.session_id, se.ledger_kind, se.event_name,"
                        " se.task_id, se.run_id, se.agent_id, se.summary, se.event_text,"
                        " se.payload_json, se.created_at"
                        " FROM session_events_fts"
                        " JOIN session_events se ON se.event_id = session_events_fts.event_id"
                        " WHERE session_events_fts MATCH ?"
                        f"{filter_sql}"
                        " ORDER BY bm25(session_events_fts), se.created_at DESC LIMIT ?",
                        [match_query, *base_params, max(1, limit)],
                    ).fetchall()
                    return [_row_to_session_event(row) for row in rows]
                except sqlite3.Error:
                    pass

            like = f"%{query.strip()}%"
            rows = db.execute(
                "SELECT event_id, session_id, ledger_kind, event_name, task_id, run_id,"
                " agent_id, summary, event_text, payload_json, created_at"
                " FROM session_events se WHERE"
                " (se.event_text LIKE ? OR se.summary LIKE ? OR se.event_name LIKE ?)"
                f"{filter_sql}"
                " ORDER BY se.created_at DESC LIMIT ?",
                [like, like, like, *base_params, max(1, limit)],
            ).fetchall()
        return [_row_to_session_event(row) for row in rows]

    async def list_session_events(
        self,
        *,
        session_id: str | None = None,
        ledger_kind: str | None = None,
        event_name: str | None = None,
        limit: int = 20,
    ) -> list[SessionEventRecord]:
        await self.init_db()
        query = (
            "SELECT event_id, session_id, ledger_kind, event_name, task_id, run_id,"
            " agent_id, summary, event_text, payload_json, created_at"
            " FROM session_events WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if ledger_kind is not None:
            query += " AND ledger_kind = ?"
            params.append(ledger_kind)
        if event_name is not None:
            query += " AND event_name = ?"
            params.append(event_name)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_session_event(row) for row in rows]

    def index_ledger_session_sync(self, session_dir: Path | str) -> int:
        session_path = Path(session_dir)
        if not session_path.exists() or not session_path.is_dir():
            return 0
        session_id = session_path.name
        self.init_db_sync()
        processed = 0
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            for ledger_kind, filename in (("task", "task_ledger.jsonl"), ("progress", "progress_ledger.jsonl")):
                path = session_path / filename
                if not path.exists():
                    continue
                for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if not raw.strip():
                        continue
                    try:
                        record = json.loads(raw)
                    except Exception:
                        continue
                    event = build_session_event_from_ledger_record(
                        session_id=session_id,
                        ledger_kind=ledger_kind,
                        record=record,
                    )
                    self._record_session_event_sync_db(db, event)
                    processed += 1
            db.commit()
        return processed

    def index_ledgers_sync(
        self,
        *,
        ledger_base: Path | str | None = None,
        session_id: str | None = None,
        limit_sessions: int | None = None,
    ) -> tuple[int, int]:
        base = Path(ledger_base or (Path.home() / ".dharma" / "ledgers"))
        if not base.exists():
            return (0, 0)
        if session_id:
            targets = [base / session_id]
        else:
            targets = sorted(
                (path for path in base.iterdir() if path.is_dir()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if limit_sessions is not None:
                targets = targets[: max(1, limit_sessions)]
        sessions_scanned = 0
        events_scanned = 0
        for target in targets:
            if not target.exists() or not target.is_dir():
                continue
            sessions_scanned += 1
            events_scanned += self.index_ledger_session_sync(target)
        return sessions_scanned, events_scanned

    async def record_task_claim(
        self,
        claim: TaskClaim,
        *,
        emit_receipt: bool = True,
    ) -> TaskClaim:
        identity: ExecutionIdentity | None = None
        receipt_id = ""
        side_effect_key = ""
        receipt_payload: dict[str, Any] = {}
        inserted_idempotency = False
        if emit_receipt:
            try:
                identity = _required_identity_from_metadata(
                    claim.metadata,
                    task_id=claim.task_id,
                    agent_id=claim.agent_id,
                    session_id=claim.session_id,
                )
            except MissingExecutionIdentity:
                identity = None
            if identity is not None:
                _require_identity_match(
                    identity,
                    surface="record_task_claim",
                    task_id=claim.task_id,
                    claim_id=claim.claim_id,
                    agent_id=claim.agent_id,
                    session_id=claim.session_id,
                )
                claim = replace(
                    claim,
                    metadata=_metadata_with_identity(claim.metadata, identity),
                )
                await self.record_execution_identity(
                    identity,
                    source="runtime_state.record_task_claim",
                )
                side_effect_key = f"task_claim:{claim.claim_id}:{claim.status}"
                receipt_id = f"rr_{identity.run_id}_{claim.status}_claim"
                receipt_payload = _task_claim_receipt_payload(claim)
                inserted_idempotency = await self.try_begin_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    metadata=receipt_payload,
                )
        await self.init_db()
        corr = get_correlation()
        trace_id = _trace_from_metadata(claim.metadata) or corr.trace_id
        if corr.cell_id:
            claim.metadata.setdefault("cell_id", corr.cell_id)
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            await db.execute(
                "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id, status,"
                " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
                " retry_count, metadata_json, trace_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(claim_id) DO UPDATE SET"
                " task_id = excluded.task_id,"
                " session_id = excluded.session_id,"
                " agent_id = excluded.agent_id,"
                " status = excluded.status,"
                " claimed_at = excluded.claimed_at,"
                " acked_at = excluded.acked_at,"
                " heartbeat_at = excluded.heartbeat_at,"
                " stale_after = excluded.stale_after,"
                " recovered_at = excluded.recovered_at,"
                " retry_count = excluded.retry_count,"
                " metadata_json = excluded.metadata_json,"
                " trace_id = excluded.trace_id",
                (
                    claim.claim_id,
                    claim.task_id,
                    claim.session_id,
                    claim.agent_id,
                    claim.status,
                    claim.claimed_at.isoformat(),
                    claim.acked_at.isoformat() if claim.acked_at else None,
                    claim.heartbeat_at.isoformat() if claim.heartbeat_at else None,
                    claim.stale_after.isoformat() if claim.stale_after else None,
                    claim.recovered_at.isoformat() if claim.recovered_at else None,
                    int(claim.retry_count),
                    _json_dump(claim.metadata),
                    trace_id,
                ),
            )
            await db.commit()
        if identity is not None:
            await self.record_runtime_receipt(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="task_claim",
                    status=claim.status,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=side_effect_key,
                    payload=receipt_payload,
                )
            )
            if inserted_idempotency:
                await self.complete_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt_id,
                    metadata=receipt_payload,
                )
        loaded = await self.get_task_claim(claim.claim_id)
        assert loaded is not None
        return loaded

    async def get_task_claim(self, claim_id: str) -> TaskClaim | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                    " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                    " metadata_json FROM task_claims WHERE claim_id = ?",
                    (claim_id,),
                )
            ).fetchone()
        return _row_to_claim(row) if row is not None else None

    async def list_task_claims(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[TaskClaim]:
        await self.init_db()
        query = (
            "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
            " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
            " metadata_json FROM task_claims WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if agent_id is not None:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY claimed_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_claim(row) for row in rows]

    async def acknowledge_task_claim(
        self,
        claim_id: str,
        *,
        status: str = "acknowledged",
        acknowledged_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskClaim:
        existing = await self.get_task_claim(claim_id)
        if existing is None:
            raise KeyError(f"claim {claim_id} not found")
        merged_metadata = {**existing.metadata, **(metadata or {})}
        acked_at = acknowledged_at or _utc_now()
        updated = TaskClaim(
            claim_id=existing.claim_id,
            task_id=existing.task_id,
            agent_id=existing.agent_id,
            status=status,
            session_id=existing.session_id,
            claimed_at=existing.claimed_at,
            acked_at=acked_at,
            heartbeat_at=existing.heartbeat_at or acked_at,
            stale_after=existing.stale_after,
            recovered_at=existing.recovered_at,
            retry_count=existing.retry_count,
            metadata=merged_metadata,
        )
        return await self.record_task_claim(updated)

    async def heartbeat_task_claim(
        self,
        claim_id: str,
        *,
        heartbeat_at: datetime | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskClaim:
        existing = await self.get_task_claim(claim_id)
        if existing is None:
            raise KeyError(f"claim {claim_id} not found")
        beat_at = heartbeat_at or _utc_now()
        merged_metadata = {**existing.metadata, **(metadata or {})}
        updated = TaskClaim(
            claim_id=existing.claim_id,
            task_id=existing.task_id,
            agent_id=existing.agent_id,
            status=status or existing.status,
            session_id=existing.session_id,
            claimed_at=existing.claimed_at,
            acked_at=existing.acked_at,
            heartbeat_at=beat_at,
            stale_after=existing.stale_after,
            recovered_at=existing.recovered_at,
            retry_count=existing.retry_count,
            metadata=merged_metadata,
        )
        return await self.record_task_claim(updated)

    async def record_delegation_run(
        self,
        run: DelegationRun,
        *,
        emit_receipt: bool = True,
    ) -> DelegationRun:
        identity: ExecutionIdentity | None = None
        receipt_id = ""
        side_effect_key = ""
        receipt_payload: dict[str, Any] = {}
        inserted_idempotency = False
        if emit_receipt:
            try:
                identity = _required_identity_from_metadata(
                    run.metadata,
                    task_id=run.task_id,
                    agent_id=run.assigned_to,
                    session_id=run.session_id,
                )
            except MissingExecutionIdentity:
                identity = None
            if identity is not None:
                _require_identity_match(
                    identity,
                    surface="record_delegation_run",
                    task_id=run.task_id,
                    claim_id=run.claim_id,
                    run_id=run.run_id,
                    agent_id=run.assigned_to,
                    session_id=run.session_id,
                )
                run = replace(
                    run,
                    parent_run_id=run.parent_run_id or identity.parent_run_id,
                    metadata=_metadata_with_identity(run.metadata, identity),
                )
                await self.record_execution_identity(
                    identity,
                    source="runtime_state.record_delegation_run",
                )
                side_effect_key = f"delegation_run:{identity.run_id}:{run.status}"
                receipt_id = f"rr_{identity.run_id}_{run.status}_run"
                receipt_payload = _delegation_run_receipt_payload(run)
                inserted_idempotency = await self.try_begin_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    metadata=receipt_payload,
                )
        await self.init_db()
        corr = get_correlation()
        trace_id = _trace_from_metadata(run.metadata) or corr.trace_id
        if corr.cell_id:
            run.metadata.setdefault("cell_id", corr.cell_id)
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            await db.execute(
                "INSERT INTO delegation_runs (run_id, session_id, task_id, claim_id,"
                " parent_run_id, assigned_by, assigned_to, requested_output_json,"
                " current_artifact_id, status, started_at, completed_at, failure_code,"
                " metadata_json, trace_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(run_id) DO UPDATE SET"
                " session_id = excluded.session_id,"
                " task_id = excluded.task_id,"
                " claim_id = excluded.claim_id,"
                " parent_run_id = excluded.parent_run_id,"
                " assigned_by = excluded.assigned_by,"
                " assigned_to = excluded.assigned_to,"
                " requested_output_json = excluded.requested_output_json,"
                " current_artifact_id = excluded.current_artifact_id,"
                " status = excluded.status,"
                " started_at = excluded.started_at,"
                " completed_at = excluded.completed_at,"
                " failure_code = excluded.failure_code,"
                " metadata_json = excluded.metadata_json,"
                " trace_id = excluded.trace_id",
                (
                    run.run_id,
                    run.session_id,
                    run.task_id,
                    run.claim_id,
                    run.parent_run_id,
                    run.assigned_by,
                    run.assigned_to,
                    _json_dump(run.requested_output),
                    run.current_artifact_id,
                    run.status,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    run.failure_code,
                    _json_dump(run.metadata),
                    trace_id,
                ),
            )
            await db.commit()
        if identity is not None:
            await self.record_runtime_receipt(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="delegation_run",
                    status=run.status,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=side_effect_key,
                    payload=receipt_payload,
                )
            )
            if inserted_idempotency:
                await self.complete_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt_id,
                    metadata=receipt_payload,
                )
            if identity.parent_run_id and run.status in {"queued", "claimed", "running"}:
                await self.record_receipt_for_identity(
                    identity,
                    receipt_id=f"rr_{identity.parent_run_id}_{identity.run_id}_child_spawned",
                    receipt_type="child_spawned",
                    status=run.status,
                    side_effect_key=f"child:{identity.parent_run_id}:{identity.run_id}",
                    payload={
                        "child_run_id": identity.run_id,
                        "parent_run_id": identity.parent_run_id,
                        "assigned_to": identity.agent_id,
                    },
                )
            if identity.parent_run_id and run.status in {"completed", "failed"}:
                await self.record_receipt_for_identity(
                    identity,
                    receipt_id=f"rr_{identity.parent_run_id}_{identity.run_id}_child_completed_{run.status}",
                    receipt_type="child_completed",
                    status=run.status,
                    side_effect_key=f"child:{identity.parent_run_id}:{identity.run_id}",
                    payload={
                        "child_run_id": identity.run_id,
                        "parent_run_id": identity.parent_run_id,
                        "failure_code": run.failure_code,
                    },
                )
        loaded = await self.get_delegation_run(run.run_id)
        assert loaded is not None
        return loaded

    async def get_delegation_run(self, run_id: str) -> DelegationRun | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                    " assigned_by, assigned_to, requested_output_json,"
                    " current_artifact_id, status, started_at, completed_at,"
                    " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                    (run_id,),
                )
            ).fetchone()
        return _row_to_run(row) if row is not None else None

    async def list_delegation_runs(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[DelegationRun]:
        await self.init_db()
        query = (
            "SELECT run_id, session_id, task_id, claim_id, parent_run_id, assigned_by,"
            " assigned_to, requested_output_json, current_artifact_id, status,"
            " started_at, completed_at, failure_code, metadata_json"
            " FROM delegation_runs WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_run(row) for row in rows]

    async def record_topology_state(
        self,
        state: TopologyStateRecord,
    ) -> TopologyStateRecord:
        await self.init_db()
        now = _utc_now()
        created_at = state.created_at or now
        updated_at = state.updated_at or now
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            await db.execute(
                "INSERT INTO topology_states (run_id, session_id, task_id, topology,"
                " active_agent, current_node, checkpoint_id, parent_run_id,"
                " child_run_ids_json, allowed_handoffs_json, handoff_receipts_json,"
                " state_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(run_id) DO UPDATE SET"
                " session_id = excluded.session_id,"
                " task_id = excluded.task_id,"
                " topology = excluded.topology,"
                " active_agent = excluded.active_agent,"
                " current_node = excluded.current_node,"
                " checkpoint_id = excluded.checkpoint_id,"
                " parent_run_id = excluded.parent_run_id,"
                " child_run_ids_json = excluded.child_run_ids_json,"
                " allowed_handoffs_json = excluded.allowed_handoffs_json,"
                " handoff_receipts_json = excluded.handoff_receipts_json,"
                " state_json = excluded.state_json,"
                " updated_at = excluded.updated_at",
                (
                    state.run_id,
                    state.session_id,
                    state.task_id,
                    state.topology,
                    state.active_agent,
                    state.current_node,
                    state.checkpoint_id,
                    state.parent_run_id,
                    _json_dump([str(item) for item in state.child_run_ids]),
                    _json_dump(state.allowed_handoffs),
                    _json_dump(state.handoff_receipts),
                    _json_dump(state.state),
                    created_at.isoformat(),
                    updated_at.isoformat(),
                ),
            )
            await db.commit()
        loaded = await self.get_topology_state(state.run_id)
        assert loaded is not None
        return loaded

    async def get_topology_state(self, run_id: str) -> TopologyStateRecord | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, topology, active_agent,"
                    " current_node, checkpoint_id, parent_run_id, child_run_ids_json,"
                    " allowed_handoffs_json, handoff_receipts_json, state_json,"
                    " created_at, updated_at FROM topology_states WHERE run_id = ?",
                    (run_id,),
                )
            ).fetchone()
        return _row_to_topology_state(row) if row is not None else None

    async def get_latest_topology_state_for_task(
        self,
        task_id: str,
    ) -> TopologyStateRecord | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, topology, active_agent,"
                    " current_node, checkpoint_id, parent_run_id, child_run_ids_json,"
                    " allowed_handoffs_json, handoff_receipts_json, state_json,"
                    " created_at, updated_at FROM topology_states"
                    " WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (task_id,),
                )
            ).fetchone()
        return _row_to_topology_state(row) if row is not None else None

    async def list_topology_states(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        topology: str | None = None,
        limit: int = 20,
    ) -> list[TopologyStateRecord]:
        await self.init_db()
        query = (
            "SELECT run_id, session_id, task_id, topology, active_agent,"
            " current_node, checkpoint_id, parent_run_id, child_run_ids_json,"
            " allowed_handoffs_json, handoff_receipts_json, state_json,"
            " created_at, updated_at FROM topology_states WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if topology is not None:
            query += " AND topology = ?"
            params.append(topology)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_topology_state(row) for row in rows]

    # ── Sync helpers (for non-async callers like OpportunityDispatcher) ──

    def create_task_claim_sync(
        self,
        claim: TaskClaim,
        *,
        legacy_no_identity_allowed: bool = False,
    ) -> TaskClaim:
        """Synchronous version of record_task_claim.

        Canonical callers must provide a full ExecutionIdentity in metadata.
        Legacy callers may opt into the temporary compatibility path explicitly.
        """
        try:
            identity = _required_identity_from_metadata(
                claim.metadata,
                task_id=claim.task_id,
                agent_id=claim.agent_id,
                session_id=claim.session_id,
            )
        except MissingExecutionIdentity:
            if not legacy_no_identity_allowed:
                raise
            identity = None

        if identity is None:
            claim = replace(
                claim,
                metadata=_legacy_no_identity_metadata(claim.metadata),
            )
        else:
            _require_identity_match(
                identity,
                surface="create_task_claim_sync",
                task_id=claim.task_id,
                claim_id=claim.claim_id,
                agent_id=claim.agent_id,
                session_id=claim.session_id,
            )
            claim = replace(
                claim,
                metadata=_metadata_with_identity(claim.metadata, identity),
            )
            self.record_execution_identity_sync(
                identity,
                source="runtime_state.create_task_claim_sync",
            )
        trace_id = identity.trace_id if identity is not None else _trace_from_metadata(claim.metadata)
        side_effect_key = ""
        receipt_id = ""
        receipt_payload: dict[str, Any] = {}
        inserted_idempotency = False
        if identity is not None:
            side_effect_key = f"task_claim:{claim.claim_id}:{claim.status}"
            receipt_id = f"rr_{identity.run_id}_{claim.status}_claim"
            receipt_payload = _task_claim_receipt_payload(claim)
            inserted_idempotency = self.try_begin_idempotent_side_effect_sync(
                identity,
                side_effect_key,
                metadata=receipt_payload,
            )
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id, status,"
                " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
                " retry_count, metadata_json, trace_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(claim_id) DO UPDATE SET"
                " task_id = excluded.task_id,"
                " session_id = excluded.session_id,"
                " agent_id = excluded.agent_id,"
                " status = excluded.status,"
                " claimed_at = excluded.claimed_at,"
                " acked_at = excluded.acked_at,"
                " heartbeat_at = excluded.heartbeat_at,"
                " stale_after = excluded.stale_after,"
                " recovered_at = excluded.recovered_at,"
                " retry_count = excluded.retry_count,"
                " metadata_json = excluded.metadata_json,"
                " trace_id = excluded.trace_id",
                (
                    claim.claim_id,
                    claim.task_id,
                    claim.session_id,
                    claim.agent_id,
                    claim.status,
                    claim.claimed_at.isoformat(),
                    claim.acked_at.isoformat() if claim.acked_at else None,
                    claim.heartbeat_at.isoformat() if claim.heartbeat_at else None,
                    claim.stale_after.isoformat() if claim.stale_after else None,
                    claim.recovered_at.isoformat() if claim.recovered_at else None,
                    int(claim.retry_count),
                    _json_dump(claim.metadata),
                    trace_id,
                ),
            )
            db.commit()
        if identity is not None:
            self.record_runtime_receipt_sync(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="task_claim",
                    status=claim.status,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=side_effect_key,
                    payload=receipt_payload,
                )
            )
            if inserted_idempotency:
                self.complete_idempotent_side_effect_sync(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt_id,
                    metadata=receipt_payload,
                )
        return self.get_task_claim_sync(claim.claim_id) or claim

    def get_task_claim_sync(self, claim_id: str) -> TaskClaim | None:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                " metadata_json FROM task_claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
        return _row_to_claim(row) if row is not None else None

    def heartbeat_claim_sync(self, claim_id: str) -> TaskClaim | None:
        """Update heartbeat_at timestamp for a claim (sync)."""
        existing = self.get_task_claim_sync(claim_id)
        if existing is None:
            return None
        now = _utc_now()
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                "UPDATE task_claims SET heartbeat_at = ? WHERE claim_id = ?",
                (now.isoformat(), claim_id),
            )
            db.commit()
        return self.get_task_claim_sync(claim_id)

    def close_claim_sync(
        self,
        claim_id: str,
        *,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> TaskClaim | None:
        """Close a claim with a terminal status (sync)."""
        existing = self.get_task_claim_sync(claim_id)
        if existing is None:
            return None
        merged = {**existing.metadata, **(metadata or {})}
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                "UPDATE task_claims SET status = ?, metadata_json = ? WHERE claim_id = ?",
                (status, _json_dump(merged), claim_id),
            )
            db.commit()
        return self.get_task_claim_sync(claim_id)

    def create_delegation_run_sync(
        self,
        run: DelegationRun,
        *,
        legacy_no_identity_allowed: bool = False,
    ) -> DelegationRun:
        """Synchronous version of record_delegation_run.

        Canonical callers must provide a full ExecutionIdentity in metadata.
        Legacy callers may opt into the temporary compatibility path explicitly.
        """
        try:
            identity = _required_identity_from_metadata(
                run.metadata,
                task_id=run.task_id,
                agent_id=run.assigned_to,
                session_id=run.session_id,
            )
        except MissingExecutionIdentity:
            if not legacy_no_identity_allowed:
                raise
            identity = None

        if identity is None:
            run = replace(
                run,
                metadata=_legacy_no_identity_metadata(run.metadata),
            )
        else:
            _require_identity_match(
                identity,
                surface="create_delegation_run_sync",
                task_id=run.task_id,
                claim_id=run.claim_id,
                run_id=run.run_id,
                agent_id=run.assigned_to,
                session_id=run.session_id,
            )
            run = replace(
                run,
                parent_run_id=run.parent_run_id or identity.parent_run_id,
                metadata=_metadata_with_identity(run.metadata, identity),
            )
            self.record_execution_identity_sync(
                identity,
                source="runtime_state.create_delegation_run_sync",
            )
        trace_id = identity.trace_id if identity is not None else _trace_from_metadata(run.metadata)
        side_effect_key = ""
        receipt_id = ""
        receipt_payload: dict[str, Any] = {}
        inserted_idempotency = False
        if identity is not None:
            side_effect_key = f"delegation_run:{identity.run_id}:{run.status}"
            receipt_id = f"rr_{identity.run_id}_{run.status}_run"
            receipt_payload = _delegation_run_receipt_payload(run)
            inserted_idempotency = self.try_begin_idempotent_side_effect_sync(
                identity,
                side_effect_key,
                metadata=receipt_payload,
            )
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                "INSERT INTO delegation_runs (run_id, session_id, task_id, claim_id,"
                " parent_run_id, assigned_by, assigned_to, requested_output_json,"
                " current_artifact_id, status, started_at, completed_at, failure_code,"
                " metadata_json, trace_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(run_id) DO UPDATE SET"
                " session_id = excluded.session_id,"
                " task_id = excluded.task_id,"
                " claim_id = excluded.claim_id,"
                " parent_run_id = excluded.parent_run_id,"
                " assigned_by = excluded.assigned_by,"
                " assigned_to = excluded.assigned_to,"
                " requested_output_json = excluded.requested_output_json,"
                " current_artifact_id = excluded.current_artifact_id,"
                " status = excluded.status,"
                " started_at = excluded.started_at,"
                " completed_at = excluded.completed_at,"
                " failure_code = excluded.failure_code,"
                " metadata_json = excluded.metadata_json,"
                " trace_id = excluded.trace_id",
                (
                    run.run_id,
                    run.session_id,
                    run.task_id,
                    run.claim_id,
                    run.parent_run_id,
                    run.assigned_by,
                    run.assigned_to,
                    _json_dump(run.requested_output),
                    run.current_artifact_id,
                    run.status,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    run.failure_code,
                    _json_dump(run.metadata),
                    trace_id,
                ),
            )
            db.commit()
        if identity is not None:
            self.record_runtime_receipt_sync(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="delegation_run",
                    status=run.status,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=side_effect_key,
                    payload=receipt_payload,
                )
            )
            if inserted_idempotency:
                self.complete_idempotent_side_effect_sync(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt_id,
                    metadata=receipt_payload,
                )
            if identity.parent_run_id and run.status in {"queued", "claimed", "running"}:
                self.record_receipt_for_identity_sync(
                    identity,
                    receipt_id=f"rr_{identity.parent_run_id}_{identity.run_id}_child_spawned",
                    receipt_type="child_spawned",
                    status=run.status,
                    side_effect_key=f"child:{identity.parent_run_id}:{identity.run_id}",
                    payload={
                        "child_run_id": identity.run_id,
                        "parent_run_id": identity.parent_run_id,
                        "assigned_to": identity.agent_id,
                    },
                )
            if identity.parent_run_id and run.status in {"completed", "failed"}:
                self.record_receipt_for_identity_sync(
                    identity,
                    receipt_id=f"rr_{identity.parent_run_id}_{identity.run_id}_child_completed_{run.status}",
                    receipt_type="child_completed",
                    status=run.status,
                    side_effect_key=f"child:{identity.parent_run_id}:{identity.run_id}",
                    payload={
                        "child_run_id": identity.run_id,
                        "parent_run_id": identity.parent_run_id,
                        "failure_code": run.failure_code,
                    },
                )
        return self.get_delegation_run_sync(run.run_id) or run

    def get_delegation_run_sync(self, run_id: str) -> DelegationRun | None:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                " assigned_by, assigned_to, requested_output_json,"
                " current_artifact_id, status, started_at, completed_at,"
                " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row_to_run(row) if row is not None else None

    def close_delegation_run_sync(
        self,
        run_id: str,
        *,
        status: str = "completed",
        failure_code: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DelegationRun | None:
        """Close a delegation run (sync)."""
        existing = self.get_delegation_run_sync(run_id)
        if existing is None:
            return None
        merged = {**existing.metadata, **(metadata or {})}
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                "UPDATE delegation_runs SET status = ?, completed_at = ?,"
                " failure_code = ?, metadata_json = ? WHERE run_id = ?",
                (status, _utc_now_iso(), failure_code, _json_dump(merged), run_id),
            )
            db.commit()
        return self.get_delegation_run_sync(run_id)

    async def record_workspace_lease(self, lease: WorkspaceLease) -> WorkspaceLease:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO workspace_leases (lease_id, zone_path, holder_run_id, mode,"
                " base_hash, acquired_at, expires_at, released_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(lease_id) DO UPDATE SET"
                " zone_path = excluded.zone_path,"
                " holder_run_id = excluded.holder_run_id,"
                " mode = excluded.mode,"
                " base_hash = excluded.base_hash,"
                " acquired_at = excluded.acquired_at,"
                " expires_at = excluded.expires_at,"
                " released_at = excluded.released_at,"
                " metadata_json = excluded.metadata_json",
                (
                    lease.lease_id,
                    lease.zone_path,
                    lease.holder_run_id,
                    lease.mode,
                    lease.base_hash,
                    lease.acquired_at.isoformat(),
                    lease.expires_at.isoformat() if lease.expires_at else None,
                    lease.released_at.isoformat() if lease.released_at else None,
                    _json_dump(lease.metadata),
                ),
            )
            await db.commit()
        loaded = await self.get_workspace_lease(lease.lease_id)
        assert loaded is not None
        return loaded

    async def get_workspace_lease(self, lease_id: str) -> WorkspaceLease | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT lease_id, zone_path, holder_run_id, mode, base_hash,"
                    " acquired_at, expires_at, released_at, metadata_json"
                    " FROM workspace_leases WHERE lease_id = ?",
                    (lease_id,),
                )
            ).fetchone()
        return _row_to_lease(row) if row is not None else None

    async def list_workspace_leases(
        self,
        *,
        holder_run_id: str | None = None,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[WorkspaceLease]:
        await self.init_db()
        query = (
            "SELECT lease_id, zone_path, holder_run_id, mode, base_hash, acquired_at,"
            " expires_at, released_at, metadata_json FROM workspace_leases WHERE 1=1"
        )
        params: list[Any] = []
        if holder_run_id is not None:
            query += " AND holder_run_id = ?"
            params.append(holder_run_id)
        if active_only:
            query += " AND released_at IS NULL"
        query += " ORDER BY acquired_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_lease(row) for row in rows]

    async def release_workspace_lease(
        self,
        lease_id: str,
        *,
        released_at: datetime | None = None,
    ) -> WorkspaceLease:
        existing = await self.get_workspace_lease(lease_id)
        if existing is None:
            raise KeyError(f"lease {lease_id} not found")
        released = WorkspaceLease(
            lease_id=existing.lease_id,
            zone_path=existing.zone_path,
            mode=existing.mode,
            holder_run_id=existing.holder_run_id,
            base_hash=existing.base_hash,
            acquired_at=existing.acquired_at,
            expires_at=existing.expires_at,
            released_at=released_at or _utc_now(),
            metadata=existing.metadata,
        )
        return await self.record_workspace_lease(released)

    async def record_artifact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO artifact_records (artifact_id, session_id, task_id, run_id,"
                " trace_id, artifact_kind, manifest_path, payload_path, checksum,"
                " parent_artifact_id, promotion_state, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(artifact_id) DO UPDATE SET"
                " session_id = excluded.session_id,"
                " task_id = excluded.task_id,"
                " run_id = excluded.run_id,"
                " trace_id = excluded.trace_id,"
                " artifact_kind = excluded.artifact_kind,"
                " manifest_path = excluded.manifest_path,"
                " payload_path = excluded.payload_path,"
                " checksum = excluded.checksum,"
                " parent_artifact_id = excluded.parent_artifact_id,"
                " promotion_state = excluded.promotion_state,"
                " created_at = excluded.created_at,"
                " metadata_json = excluded.metadata_json",
                (
                    artifact.artifact_id,
                    artifact.session_id,
                    artifact.task_id,
                    artifact.run_id,
                    artifact.trace_id,
                    artifact.artifact_kind,
                    artifact.manifest_path,
                    artifact.payload_path,
                    artifact.checksum,
                    artifact.parent_artifact_id,
                    artifact.promotion_state,
                    artifact.created_at.isoformat(),
                    _json_dump(artifact.metadata),
                ),
            )
            await db.commit()
        loaded = await self.get_artifact(artifact.artifact_id)
        assert loaded is not None
        return loaded

    async def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT artifact_id, session_id, task_id, run_id, trace_id,"
                    " artifact_kind, manifest_path, payload_path, checksum, parent_artifact_id,"
                    " promotion_state, created_at, metadata_json"
                    " FROM artifact_records WHERE artifact_id = ?",
                    (artifact_id,),
                )
            ).fetchone()
        return _row_to_artifact(row) if row is not None else None

    async def list_artifacts(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
        promotion_state: str | None = None,
        limit: int = 20,
    ) -> list[ArtifactRecord]:
        await self.init_db()
        query = (
            "SELECT artifact_id, session_id, task_id, run_id, trace_id, artifact_kind,"
            " manifest_path, payload_path, checksum, parent_artifact_id,"
            " promotion_state, created_at, metadata_json"
            " FROM artifact_records WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if trace_id is not None:
            query += " AND trace_id = ?"
            params.append(trace_id)
        if promotion_state is not None:
            query += " AND promotion_state = ?"
            params.append(promotion_state)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_artifact(row) for row in rows]

    @staticmethod
    def _identity_params(
        identity: ExecutionIdentity,
        *,
        source: str,
        now: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Any, ...]:
        merged_metadata = {
            **dict(identity.metadata or {}),
            **dict(metadata or {}),
        }
        return (
            identity.run_id,
            identity.trace_id,
            identity.correlation_id,
            identity.task_id,
            identity.claim_id,
            identity.idempotency_key,
            identity.causation_id,
            identity.parent_run_id,
            identity.agent_id,
            identity.session_id,
            identity.external_a2a_task_id,
            identity.message_id,
            identity.event_id,
            identity.artifact_id,
            identity.proposal_id,
            source,
            _json_dump(merged_metadata),
            now.isoformat(),
            now.isoformat(),
        )

    @staticmethod
    def _identity_upsert_sql() -> str:
        return (
            "INSERT INTO execution_identities (run_id, trace_id, correlation_id,"
            " task_id, claim_id, idempotency_key, causation_id, parent_run_id,"
            " agent_id, session_id, external_a2a_task_id, message_id, event_id,"
            " artifact_id, proposal_id, source, metadata_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(run_id) DO UPDATE SET"
            " trace_id = excluded.trace_id,"
            " correlation_id = excluded.correlation_id,"
            " task_id = excluded.task_id,"
            " claim_id = excluded.claim_id,"
            " idempotency_key = excluded.idempotency_key,"
            " causation_id = excluded.causation_id,"
            " parent_run_id = excluded.parent_run_id,"
            " agent_id = excluded.agent_id,"
            " session_id = excluded.session_id,"
            " external_a2a_task_id = CASE"
            "   WHEN excluded.external_a2a_task_id != '' THEN excluded.external_a2a_task_id"
            "   ELSE execution_identities.external_a2a_task_id"
            " END,"
            " message_id = CASE"
            "   WHEN excluded.message_id != '' THEN excluded.message_id"
            "   ELSE execution_identities.message_id"
            " END,"
            " event_id = CASE"
            "   WHEN excluded.event_id != '' THEN excluded.event_id"
            "   ELSE execution_identities.event_id"
            " END,"
            " artifact_id = CASE"
            "   WHEN excluded.artifact_id != '' THEN excluded.artifact_id"
            "   ELSE execution_identities.artifact_id"
            " END,"
            " proposal_id = CASE"
            "   WHEN excluded.proposal_id != '' THEN excluded.proposal_id"
            "   ELSE execution_identities.proposal_id"
            " END,"
            " source = excluded.source,"
            " metadata_json = excluded.metadata_json,"
            " updated_at = excluded.updated_at"
        )

    async def record_execution_identity(
        self,
        identity: ExecutionIdentity,
        *,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionIdentity:
        identity.require_for_dispatch()
        await self.init_db()
        existing = await self.get_execution_identity(identity.run_id)
        _raise_on_execution_identity_conflict(existing, identity)
        now = _utc_now()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            await db.execute(
                self._identity_upsert_sql(),
                self._identity_params(identity, source=source, now=now, metadata=metadata),
            )
            await db.commit()
        loaded = await self.get_execution_identity(identity.run_id)
        assert loaded is not None
        return loaded

    def record_execution_identity_sync(
        self,
        identity: ExecutionIdentity,
        *,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionIdentity:
        identity.require_for_dispatch()
        self.init_db_sync()
        existing = self.get_execution_identity_sync(identity.run_id)
        _raise_on_execution_identity_conflict(existing, identity)
        now = _utc_now()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                self._identity_upsert_sql(),
                self._identity_params(identity, source=source, now=now, metadata=metadata),
            )
            db.commit()
        return self.get_execution_identity_sync(identity.run_id) or identity

    async def get_execution_identity(self, run_id: str) -> ExecutionIdentity | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT run_id, trace_id, correlation_id, task_id, claim_id,"
                    " idempotency_key, causation_id, parent_run_id, agent_id,"
                    " session_id, external_a2a_task_id, message_id, event_id,"
                    " artifact_id, proposal_id, metadata_json"
                    " FROM execution_identities WHERE run_id = ?",
                    (run_id,),
                )
            ).fetchone()
        return _row_to_execution_identity(row) if row is not None else None

    def get_execution_identity_sync(self, run_id: str) -> ExecutionIdentity | None:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT run_id, trace_id, correlation_id, task_id, claim_id,"
                " idempotency_key, causation_id, parent_run_id, agent_id,"
                " session_id, external_a2a_task_id, message_id, event_id,"
                " artifact_id, proposal_id, metadata_json"
                " FROM execution_identities WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row_to_execution_identity(row) if row is not None else None

    async def get_execution_identity_by_external_a2a_task(
        self,
        external_a2a_task_id: str,
    ) -> ExecutionIdentity | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT run_id, trace_id, correlation_id, task_id, claim_id,"
                    " idempotency_key, causation_id, parent_run_id, agent_id,"
                    " session_id, external_a2a_task_id, message_id, event_id,"
                    " artifact_id, proposal_id, metadata_json"
                    " FROM execution_identities WHERE external_a2a_task_id = ?"
                    " ORDER BY updated_at DESC LIMIT 1",
                    (external_a2a_task_id,),
                )
            ).fetchone()
        return _row_to_execution_identity(row) if row is not None else None

    @staticmethod
    def build_runtime_receipt(
        identity: ExecutionIdentity,
        *,
        receipt_type: str,
        status: str,
        side_effect_key: str = "",
        payload: dict[str, Any] | None = None,
        receipt_id: str = "",
        created_at: datetime | None = None,
    ) -> RuntimeReceipt:
        """Build a RuntimeReceipt that preserves the canonical identity fields."""
        identity.require_for_dispatch()
        return RuntimeReceipt(
            receipt_id=receipt_id or _new_id("rr"),
            receipt_type=receipt_type,
            status=status,
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=side_effect_key,
            payload=dict(payload or {}),
            created_at=created_at or _utc_now(),
        )

    async def record_receipt_for_identity(
        self,
        identity: ExecutionIdentity,
        *,
        receipt_type: str,
        status: str,
        side_effect_key: str = "",
        payload: dict[str, Any] | None = None,
        receipt_id: str = "",
    ) -> RuntimeReceipt:
        receipt = self.build_runtime_receipt(
            identity,
            receipt_type=receipt_type,
            status=status,
            side_effect_key=side_effect_key,
            payload=payload,
            receipt_id=receipt_id,
        )
        return await self.record_runtime_receipt(receipt)

    def record_receipt_for_identity_sync(
        self,
        identity: ExecutionIdentity,
        *,
        receipt_type: str,
        status: str,
        side_effect_key: str = "",
        payload: dict[str, Any] | None = None,
        receipt_id: str = "",
    ) -> RuntimeReceipt:
        receipt = self.build_runtime_receipt(
            identity,
            receipt_type=receipt_type,
            status=status,
            side_effect_key=side_effect_key,
            payload=payload,
            receipt_id=receipt_id,
        )
        return self.record_runtime_receipt_sync(receipt)

    async def record_idempotency_consumed(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return await self.record_receipt_for_identity(
            identity,
            receipt_type="idempotency_consumed",
            status=status,
            side_effect_key=side_effect_key,
            payload=payload,
        )

    def record_idempotency_consumed_sync(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return self.record_receipt_for_identity_sync(
            identity,
            receipt_type="idempotency_consumed",
            status=status,
            side_effect_key=side_effect_key,
            payload=payload,
        )

    async def record_side_effect_intent(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return await self.record_receipt_for_identity(
            identity,
            receipt_type="side_effect_intent",
            status="started",
            side_effect_key=side_effect_key,
            payload=payload,
        )

    def record_side_effect_intent_sync(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return self.record_receipt_for_identity_sync(
            identity,
            receipt_type="side_effect_intent",
            status="started",
            side_effect_key=side_effect_key,
            payload=payload,
        )

    async def record_side_effect_complete(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        status: str = "completed",
        result_receipt_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return await self.record_receipt_for_identity(
            identity,
            receipt_type="side_effect_complete",
            status=status,
            side_effect_key=side_effect_key,
            payload={
                "result_receipt_id": result_receipt_id,
                **dict(payload or {}),
            },
        )

    def record_side_effect_complete_sync(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        status: str = "completed",
        result_receipt_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return self.record_receipt_for_identity_sync(
            identity,
            receipt_type="side_effect_complete",
            status=status,
            side_effect_key=side_effect_key,
            payload={
                "result_receipt_id": result_receipt_id,
                **dict(payload or {}),
            },
        )

    async def record_message_consumed(
        self,
        identity: ExecutionIdentity,
        message_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        return await self.record_receipt_for_identity(
            identity.with_updates(message_id=message_id),
            receipt_type="message_consumed",
            status="consumed",
            side_effect_key=f"message:{message_id}",
            payload={"message_id": message_id, **dict(payload or {})},
        )

    async def record_ontology_action_receipt(
        self,
        identity: ExecutionIdentity,
        *,
        action_name: str,
        object_type: str,
        object_id: str = "",
        applied: bool = False,
        status: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        receipt_type = "ontology_action_applied" if applied else "ontology_action_requested"
        return await self.record_receipt_for_identity(
            identity,
            receipt_type=receipt_type,
            status=status or ("applied" if applied else "requested"),
            side_effect_key=f"ontology:{object_type}:{object_id}:{action_name}",
            payload={
                "action_name": action_name,
                "object_type": object_type,
                "object_id": object_id,
                **dict(payload or {}),
            },
        )

    def record_ontology_action_receipt_sync(
        self,
        identity: ExecutionIdentity,
        *,
        action_name: str,
        object_type: str,
        object_id: str = "",
        applied: bool = False,
        status: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        receipt_type = "ontology_action_applied" if applied else "ontology_action_requested"
        return self.record_receipt_for_identity_sync(
            identity,
            receipt_type=receipt_type,
            status=status or ("applied" if applied else "requested"),
            side_effect_key=f"ontology:{object_type}:{object_id}:{action_name}",
            payload={
                "action_name": action_name,
                "object_type": object_type,
                "object_id": object_id,
                **dict(payload or {}),
            },
        )

    async def record_self_mod_receipt(
        self,
        identity: ExecutionIdentity,
        *,
        stage: str,
        status: str,
        proposal_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        stage_key = stage.removeprefix("self_mod_")
        receipt_type = f"self_mod_{stage_key}"
        if receipt_type not in SELF_MOD_RECEIPT_TYPES:
            raise ValueError(f"unknown self-mod receipt stage: {stage}")
        return await self.record_receipt_for_identity(
            identity.with_updates(proposal_id=proposal_id or identity.proposal_id),
            receipt_type=receipt_type,
            status=status,
            side_effect_key=f"self_mod:{proposal_id or identity.proposal_id}:{stage_key}",
            payload={"proposal_id": proposal_id or identity.proposal_id, **dict(payload or {})},
        )

    def record_self_mod_receipt_sync(
        self,
        identity: ExecutionIdentity,
        *,
        stage: str,
        status: str,
        proposal_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        stage_key = stage.removeprefix("self_mod_")
        receipt_type = f"self_mod_{stage_key}"
        if receipt_type not in SELF_MOD_RECEIPT_TYPES:
            raise ValueError(f"unknown self-mod receipt stage: {stage}")
        return self.record_receipt_for_identity_sync(
            identity.with_updates(proposal_id=proposal_id or identity.proposal_id),
            receipt_type=receipt_type,
            status=status,
            side_effect_key=f"self_mod:{proposal_id or identity.proposal_id}:{stage_key}",
            payload={"proposal_id": proposal_id or identity.proposal_id, **dict(payload or {})},
        )

    @staticmethod
    def _normalize_mapping_id_kind(id_kind: str) -> str:
        normalized = str(id_kind or "").strip()
        if normalized not in MAPPING_ID_KINDS:
            raise ValueError(f"unknown runtime identity mapping kind: {id_kind}")
        return normalized

    @staticmethod
    def _mapping_side_effect_key(id_kind: str, external_id: str) -> str:
        return f"mapping:{id_kind}:{external_id}"

    @staticmethod
    def _mapping_receipt_id(
        identity: ExecutionIdentity,
        *,
        id_kind: str,
        external_id: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{identity.run_id}:{id_kind}:{external_id}".encode("utf-8")
        ).hexdigest()[:16]
        return f"rr_{identity.run_id}_mapping_{digest}"

    @staticmethod
    def _identity_with_mapping_field(
        identity: ExecutionIdentity,
        *,
        id_kind: str,
        external_id: str,
    ) -> ExecutionIdentity:
        field_name = MAPPING_IDENTITY_FIELDS.get(id_kind)
        if not field_name:
            return identity
        current = str(getattr(identity, field_name, "") or "").strip()
        if current and current != external_id:
            return identity.with_updates(metadata={f"mapped_{id_kind}": external_id})
        return identity.with_updates(**{field_name: external_id})

    @staticmethod
    def _mapping_payload(
        identity: ExecutionIdentity,
        *,
        id_kind: str,
        external_id: str,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id_kind": id_kind,
            "external_id": external_id,
            "run_id": identity.run_id,
            "task_id": identity.task_id,
            "trace_id": identity.trace_id,
            "correlation_id": identity.correlation_id,
            "source": source,
            **dict(payload or {}),
        }

    async def record_mapping_receipt(
        self,
        identity: ExecutionIdentity,
        *,
        id_kind: str,
        external_id: str,
        source: str = "runtime_state.mapping",
        status: str = "mapped",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        identity.require_for_dispatch()
        normalized_kind = self._normalize_mapping_id_kind(id_kind)
        normalized_external_id = str(external_id or "").strip()
        if not normalized_external_id:
            raise ValueError("external_id is required for runtime identity mapping")
        mapped_identity = self._identity_with_mapping_field(
            identity,
            id_kind=normalized_kind,
            external_id=normalized_external_id,
        )
        mapping_payload = self._mapping_payload(
            identity,
            id_kind=normalized_kind,
            external_id=normalized_external_id,
            source=source,
            payload=payload,
        )
        await self.record_execution_identity(
            mapped_identity,
            source=f"mapping:{normalized_kind}",
            metadata={"runtime_mapping": mapping_payload},
        )
        return await self.record_receipt_for_identity(
            mapped_identity,
            receipt_type="identity_mapping",
            status=status,
            side_effect_key=self._mapping_side_effect_key(
                normalized_kind,
                normalized_external_id,
            ),
            payload=mapping_payload,
            receipt_id=self._mapping_receipt_id(
                mapped_identity,
                id_kind=normalized_kind,
                external_id=normalized_external_id,
            ),
        )

    def record_mapping_receipt_sync(
        self,
        identity: ExecutionIdentity,
        *,
        id_kind: str,
        external_id: str,
        source: str = "runtime_state.mapping",
        status: str = "mapped",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeReceipt:
        identity.require_for_dispatch()
        normalized_kind = self._normalize_mapping_id_kind(id_kind)
        normalized_external_id = str(external_id or "").strip()
        if not normalized_external_id:
            raise ValueError("external_id is required for runtime identity mapping")
        mapped_identity = self._identity_with_mapping_field(
            identity,
            id_kind=normalized_kind,
            external_id=normalized_external_id,
        )
        mapping_payload = self._mapping_payload(
            identity,
            id_kind=normalized_kind,
            external_id=normalized_external_id,
            source=source,
            payload=payload,
        )
        self.record_execution_identity_sync(
            mapped_identity,
            source=f"mapping:{normalized_kind}",
            metadata={"runtime_mapping": mapping_payload},
        )
        return self.record_receipt_for_identity_sync(
            mapped_identity,
            receipt_type="identity_mapping",
            status=status,
            side_effect_key=self._mapping_side_effect_key(
                normalized_kind,
                normalized_external_id,
            ),
            payload=mapping_payload,
            receipt_id=self._mapping_receipt_id(
                mapped_identity,
                id_kind=normalized_kind,
                external_id=normalized_external_id,
            ),
        )

    async def list_mapping_receipts(
        self,
        *,
        run_id: str | None = None,
        id_kind: str | None = None,
        external_id: str | None = None,
        limit: int = 100,
    ) -> list[RuntimeReceipt]:
        normalized_kind = self._normalize_mapping_id_kind(id_kind) if id_kind else None
        normalized_external_id: str | None = None
        if external_id is not None:
            normalized_external_id = str(external_id or "").strip()
            if not normalized_external_id:
                raise ValueError("external_id is required for runtime identity mapping")
            if not normalized_kind:
                raise ValueError("id_kind is required when external_id is provided")
        await self.init_db()
        query = (
            "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, causation_id, parent_run_id, agent_id,"
            " idempotency_key, side_effect_key, status, payload_json, created_at"
            " FROM runtime_receipts WHERE receipt_type = 'identity_mapping'"
        )
        params: list[Any] = []
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if normalized_kind and normalized_external_id:
            query += " AND side_effect_key = ?"
            params.append(
                self._mapping_side_effect_key(normalized_kind, normalized_external_id)
            )
        elif normalized_kind:
            query += " AND side_effect_key LIKE ?"
            params.append(f"mapping:{normalized_kind}:%")
        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        receipts = [_row_to_runtime_receipt(row) for row in rows]
        if normalized_kind and not normalized_external_id:
            receipts = [
                receipt
                for receipt in receipts
                if receipt.payload.get("id_kind") == normalized_kind
            ]
        return receipts

    def list_mapping_receipts_sync(
        self,
        *,
        run_id: str | None = None,
        id_kind: str | None = None,
        external_id: str | None = None,
        limit: int = 100,
    ) -> list[RuntimeReceipt]:
        normalized_kind = self._normalize_mapping_id_kind(id_kind) if id_kind else None
        normalized_external_id: str | None = None
        if external_id is not None:
            normalized_external_id = str(external_id or "").strip()
            if not normalized_external_id:
                raise ValueError("external_id is required for runtime identity mapping")
            if not normalized_kind:
                raise ValueError("id_kind is required when external_id is provided")
        self.init_db_sync()
        query = (
            "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, causation_id, parent_run_id, agent_id,"
            " idempotency_key, side_effect_key, status, payload_json, created_at"
            " FROM runtime_receipts WHERE receipt_type = 'identity_mapping'"
        )
        params: list[Any] = []
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if normalized_kind and normalized_external_id:
            query += " AND side_effect_key = ?"
            params.append(
                self._mapping_side_effect_key(normalized_kind, normalized_external_id)
            )
        elif normalized_kind:
            query += " AND side_effect_key LIKE ?"
            params.append(f"mapping:{normalized_kind}:%")
        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(max(1, limit))
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(query, params).fetchall()
        receipts = [_row_to_runtime_receipt(row) for row in rows]
        if normalized_kind and not normalized_external_id:
            receipts = [
                receipt
                for receipt in receipts
                if receipt.payload.get("id_kind") == normalized_kind
            ]
        return receipts

    async def find_run_id_by_mapping(self, id_kind: str, external_id: str) -> str | None:
        receipts = await self.list_mapping_receipts(
            id_kind=id_kind,
            external_id=external_id,
            limit=1,
        )
        return receipts[0].run_id if receipts else None

    def find_run_id_by_mapping_sync(self, id_kind: str, external_id: str) -> str | None:
        receipts = self.list_mapping_receipts_sync(
            id_kind=id_kind,
            external_id=external_id,
            limit=1,
        )
        return receipts[0].run_id if receipts else None

    async def record_runtime_receipt(self, receipt: RuntimeReceipt) -> RuntimeReceipt:
        _validate_runtime_receipt_identity(receipt)
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO runtime_receipts (receipt_id, receipt_type,"
                " run_id, task_id, trace_id, correlation_id, causation_id,"
                " parent_run_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.receipt_id,
                    receipt.receipt_type,
                    receipt.run_id,
                    receipt.task_id,
                    receipt.trace_id,
                    receipt.correlation_id,
                    receipt.causation_id,
                    receipt.parent_run_id,
                    receipt.agent_id,
                    receipt.idempotency_key,
                    receipt.side_effect_key,
                    receipt.status,
                    _json_dump(receipt.payload),
                    receipt.created_at.isoformat(),
                ),
            )
            await db.commit()
        return receipt

    def record_runtime_receipt_sync(self, receipt: RuntimeReceipt) -> RuntimeReceipt:
        _validate_runtime_receipt_identity(receipt)
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute(
                "INSERT OR REPLACE INTO runtime_receipts (receipt_id, receipt_type,"
                " run_id, task_id, trace_id, correlation_id, causation_id,"
                " parent_run_id, agent_id, idempotency_key, side_effect_key,"
                " status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.receipt_id,
                    receipt.receipt_type,
                    receipt.run_id,
                    receipt.task_id,
                    receipt.trace_id,
                    receipt.correlation_id,
                    receipt.causation_id,
                    receipt.parent_run_id,
                    receipt.agent_id,
                    receipt.idempotency_key,
                    receipt.side_effect_key,
                    receipt.status,
                    _json_dump(receipt.payload),
                    receipt.created_at.isoformat(),
                ),
            )
            db.commit()
        return receipt

    async def list_runtime_receipts(
        self,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        receipt_type: str | None = None,
        limit: int = 50,
    ) -> list[RuntimeReceipt]:
        await self.init_db()
        query = (
            "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
            " correlation_id, causation_id, parent_run_id, agent_id,"
            " idempotency_key, side_effect_key, status, payload_json, created_at"
            " FROM runtime_receipts WHERE 1=1"
        )
        params: list[Any] = []
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if trace_id is not None:
            query += " AND trace_id = ?"
            params.append(trace_id)
        if correlation_id is not None:
            query += " AND correlation_id = ?"
            params.append(correlation_id)
        if receipt_type is not None:
            query += " AND receipt_type = ?"
            params.append(receipt_type)
        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_runtime_receipt(row) for row in rows]

    async def _mark_idempotency_record_stale(
        self,
        existing: IdempotencyRecord,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        now = _next_idempotency_token(existing.updated_at)
        merged_metadata = _merge_idempotency_metadata(
            existing,
            {
                **dict(metadata or {}),
                "stale_quarantined_at": now,
                "previous_status": existing.status,
            },
        )
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE idempotency_records SET status = 'stale',"
                " metadata_json = ?, updated_at = ?"
                " WHERE idempotency_key = ? AND side_effect_key = ?"
                " AND status = 'started' AND updated_at = ?",
                (
                    _json_dump(merged_metadata),
                    now,
                    existing.idempotency_key,
                    existing.side_effect_key,
                    existing.updated_at.isoformat(),
                ),
            )
            await db.commit()
        return int(cur.rowcount or 0) == 1

    def _mark_idempotency_record_stale_sync(
        self,
        existing: IdempotencyRecord,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        now = _next_idempotency_token(existing.updated_at)
        merged_metadata = _merge_idempotency_metadata(
            existing,
            {
                **dict(metadata or {}),
                "stale_quarantined_at": now,
                "previous_status": existing.status,
            },
        )
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            cur = db.execute(
                "UPDATE idempotency_records SET status = 'stale',"
                " metadata_json = ?, updated_at = ?"
                " WHERE idempotency_key = ? AND side_effect_key = ?"
                " AND status = 'started' AND updated_at = ?",
                (
                    _json_dump(merged_metadata),
                    now,
                    existing.idempotency_key,
                    existing.side_effect_key,
                    existing.updated_at.isoformat(),
                ),
            )
            db.commit()
        return int(cur.rowcount or 0) == 1

    async def _handle_existing_idempotency_record(
        self,
        identity: ExecutionIdentity,
        existing: IdempotencyRecord,
        *,
        metadata: dict[str, Any] | None,
        stale_after_seconds: float | None,
    ) -> None:
        existing_hash = _operation_hash(existing.metadata)
        incoming_hash = _operation_hash(metadata)
        if existing_hash and incoming_hash and existing_hash != incoming_hash:
            await self.record_idempotency_consumed(
                identity,
                existing.side_effect_key,
                status="conflict",
                payload={
                    **dict(metadata or {}),
                    "existing_operation_hash": existing_hash,
                    "operation_hash": incoming_hash,
                },
            )
            raise ValueError(
                "idempotency operation_hash conflict for "
                f"{existing.idempotency_key}:{existing.side_effect_key}"
            )
        if (
            existing.status == "started"
            and stale_after_seconds is not None
            and (_utc_now() - existing.updated_at).total_seconds() >= stale_after_seconds
        ):
            marked = await self._mark_idempotency_record_stale(existing, metadata=metadata)
            if marked:
                await self.record_idempotency_consumed(
                    identity,
                    existing.side_effect_key,
                    status="stale",
                    payload={
                        **dict(metadata or {}),
                        "stale_after_seconds": stale_after_seconds,
                    },
                )
                return
        await self.record_idempotency_consumed(
            identity,
            existing.side_effect_key,
            status="duplicate",
            payload=metadata,
        )

    def _handle_existing_idempotency_record_sync(
        self,
        identity: ExecutionIdentity,
        existing: IdempotencyRecord,
        *,
        metadata: dict[str, Any] | None,
        stale_after_seconds: float | None,
    ) -> None:
        existing_hash = _operation_hash(existing.metadata)
        incoming_hash = _operation_hash(metadata)
        if existing_hash and incoming_hash and existing_hash != incoming_hash:
            self.record_idempotency_consumed_sync(
                identity,
                existing.side_effect_key,
                status="conflict",
                payload={
                    **dict(metadata or {}),
                    "existing_operation_hash": existing_hash,
                    "operation_hash": incoming_hash,
                },
            )
            raise ValueError(
                "idempotency operation_hash conflict for "
                f"{existing.idempotency_key}:{existing.side_effect_key}"
            )
        if (
            existing.status == "started"
            and stale_after_seconds is not None
            and (_utc_now() - existing.updated_at).total_seconds() >= stale_after_seconds
        ):
            marked = self._mark_idempotency_record_stale_sync(existing, metadata=metadata)
            if marked:
                self.record_idempotency_consumed_sync(
                    identity,
                    existing.side_effect_key,
                    status="stale",
                    payload={
                        **dict(metadata or {}),
                        "stale_after_seconds": stale_after_seconds,
                    },
                )
                return
        self.record_idempotency_consumed_sync(
            identity,
            existing.side_effect_key,
            status="duplicate",
            payload=metadata,
        )

    async def try_begin_idempotent_side_effect_with_token(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        metadata: dict[str, Any] | None = None,
        stale_after_seconds: float | None = None,
        ownership_time: datetime | None = None,
    ) -> datetime | None:
        identity.require_for_dispatch()
        if not side_effect_key:
            raise ValueError("side_effect_key is required")
        await self.init_db()
        now = _next_idempotency_token(None, ownership_time)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT OR IGNORE INTO idempotency_records (idempotency_key,"
                " side_effect_key, run_id, task_id, trace_id, correlation_id,"
                " status, result_receipt_id, metadata_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'started', '', ?, ?, ?)",
                (
                    identity.idempotency_key,
                    side_effect_key,
                    identity.run_id,
                    identity.task_id,
                    identity.trace_id,
                    identity.correlation_id,
                    _json_dump(metadata or {}),
                    now,
                    now,
                ),
            )
            await db.commit()
            inserted = int(cur.rowcount or 0) == 1
        if not inserted:
            existing = await self.get_idempotency_record(identity.idempotency_key, side_effect_key)
            if existing is None:
                raise KeyError(f"idempotency record {identity.idempotency_key}:{side_effect_key} not found")
            await self._handle_existing_idempotency_record(
                identity,
                existing,
                metadata=metadata,
                stale_after_seconds=stale_after_seconds,
            )
            return None
        await self.record_idempotency_consumed(
            identity,
            side_effect_key,
            status="accepted",
            payload=metadata,
        )
        await self.record_side_effect_intent(identity, side_effect_key, payload=metadata)
        return datetime.fromisoformat(now)

    async def try_begin_idempotent_side_effect(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        metadata: dict[str, Any] | None = None,
        stale_after_seconds: float | None = None,
    ) -> bool:
        """Preserve the public boolean begin API."""
        token = await self.try_begin_idempotent_side_effect_with_token(
            identity, side_effect_key, metadata=metadata,
            stale_after_seconds=stale_after_seconds,
        )
        return token is not None

    def try_begin_idempotent_side_effect_sync(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        metadata: dict[str, Any] | None = None,
        stale_after_seconds: float | None = None,
    ) -> bool:
        identity.require_for_dispatch()
        if not side_effect_key:
            raise ValueError("side_effect_key is required")
        self.init_db_sync()
        now = _utc_now_iso()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            cur = db.execute(
                "INSERT OR IGNORE INTO idempotency_records (idempotency_key,"
                " side_effect_key, run_id, task_id, trace_id, correlation_id,"
                " status, result_receipt_id, metadata_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'started', '', ?, ?, ?)",
                (
                    identity.idempotency_key,
                    side_effect_key,
                    identity.run_id,
                    identity.task_id,
                    identity.trace_id,
                    identity.correlation_id,
                    _json_dump(metadata or {}),
                    now,
                    now,
                ),
            )
            db.commit()
            inserted = int(cur.rowcount or 0) == 1
        if not inserted:
            existing = self.get_idempotency_record_sync(identity.idempotency_key, side_effect_key)
            if existing is None:
                raise KeyError(f"idempotency record {identity.idempotency_key}:{side_effect_key} not found")
            self._handle_existing_idempotency_record_sync(
                identity,
                existing,
                metadata=metadata,
                stale_after_seconds=stale_after_seconds,
            )
            return False
        self.record_idempotency_consumed_sync(
            identity,
            side_effect_key,
            status="accepted",
            payload=metadata,
        )
        if inserted:
            self.record_side_effect_intent_sync(
                identity,
                side_effect_key,
                payload=metadata,
            )
        return inserted

    async def complete_idempotent_side_effect(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        status: str = "completed",
        result_receipt_id: str = "",
        metadata: dict[str, Any] | None = None,
        expected_updated_at: datetime | None = None,
    ) -> IdempotencyRecord:
        identity.require_for_dispatch()
        await self.init_db()
        existing = await self.get_idempotency_record(identity.idempotency_key, side_effect_key)
        if existing is None:
            raise KeyError(f"idempotency record {identity.idempotency_key}:{side_effect_key} not found")
        now = _next_idempotency_token(expected_updated_at or existing.updated_at)
        merged_metadata = _merge_idempotency_metadata(existing, metadata)
        async with aiosqlite.connect(self.db_path) as db:
            sql = (
                "UPDATE idempotency_records SET status = ?, result_receipt_id = ?,"
                " metadata_json = ?, updated_at = ?"
                " WHERE idempotency_key = ? AND side_effect_key = ?"
            )
            params: list[Any] = [status, result_receipt_id, _json_dump(merged_metadata), now,
                                 identity.idempotency_key, side_effect_key]
            if expected_updated_at is not None:
                sql += " AND status = 'started' AND updated_at = ?"
                params.append(expected_updated_at.isoformat())
            cur = await db.execute(sql, tuple(params))
            await db.commit()
        if expected_updated_at is not None and int(cur.rowcount or 0) != 1:
            raise RuntimeError(f"idempotency lease lost for {identity.idempotency_key}:{side_effect_key}")
        record = await self.get_idempotency_record(identity.idempotency_key, side_effect_key)
        await self.record_side_effect_complete(
            identity,
            side_effect_key,
            status=status,
            result_receipt_id=result_receipt_id,
            payload=merged_metadata,
        )
        return record

    def complete_idempotent_side_effect_sync(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        status: str = "completed",
        result_receipt_id: str = "",
        metadata: dict[str, Any] | None = None,
        expected_updated_at: datetime | None = None,
    ) -> IdempotencyRecord:
        identity.require_for_dispatch()
        self.init_db_sync()
        existing = self.get_idempotency_record_sync(identity.idempotency_key, side_effect_key)
        if existing is None:
            raise KeyError(f"idempotency record {identity.idempotency_key}:{side_effect_key} not found")
        now = _next_idempotency_token(expected_updated_at or existing.updated_at)
        merged_metadata = _merge_idempotency_metadata(existing, metadata)
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            sql = (
                "UPDATE idempotency_records SET status = ?, result_receipt_id = ?,"
                " metadata_json = ?, updated_at = ?"
                " WHERE idempotency_key = ? AND side_effect_key = ?"
            )
            params: list[Any] = [status, result_receipt_id, _json_dump(merged_metadata), now,
                                 identity.idempotency_key, side_effect_key]
            if expected_updated_at is not None:
                sql += " AND status = 'started' AND updated_at = ?"
                params.append(expected_updated_at.isoformat())
            cur = db.execute(sql, tuple(params))
            db.commit()
        if expected_updated_at is not None and int(cur.rowcount or 0) != 1:
            raise RuntimeError(f"idempotency lease lost for {identity.idempotency_key}:{side_effect_key}")
        record = self.get_idempotency_record_sync(identity.idempotency_key, side_effect_key)
        self.record_side_effect_complete_sync(
            identity,
            side_effect_key,
            status=status,
            result_receipt_id=result_receipt_id,
            payload=merged_metadata,
        )
        return record

    async def try_reclaim_idempotent_side_effect_with_token(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        expected_status: str,
        expected_updated_at: datetime | None = None,
        ownership_time: datetime | None = None,
    ) -> datetime | None:
        identity.require_for_dispatch()
        if not side_effect_key:
            raise ValueError("side_effect_key is required")
        await self.init_db()
        now = _next_idempotency_token(expected_updated_at, ownership_time)
        sql = (
            "UPDATE idempotency_records SET status = 'started', run_id = ?,"
            " task_id = ?, trace_id = ?, correlation_id = ?, updated_at = ?"
            " WHERE idempotency_key = ? AND side_effect_key = ? AND status = ?"
        )
        params: list[Any] = [
            identity.run_id,
            identity.task_id,
            identity.trace_id,
            identity.correlation_id,
            now,
            identity.idempotency_key,
            side_effect_key,
            expected_status,
        ]
        if expected_updated_at is not None:
            sql += " AND updated_at = ?"
            params.append(expected_updated_at.isoformat())
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(sql, tuple(params))
            await db.commit()
            reclaimed = int(cur.rowcount or 0) == 1
        if reclaimed:
            await self.record_idempotency_consumed(
                identity,
                side_effect_key,
                status="reclaimed",
                payload={"expected_status": expected_status,
                         "ownership_token": now},
            )
        return datetime.fromisoformat(now) if reclaimed else None

    async def try_reclaim_idempotent_side_effect(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        expected_status: str,
        expected_updated_at: datetime | None = None,
    ) -> bool:
        """Preserve the public boolean reclaim API."""
        token = await self.try_reclaim_idempotent_side_effect_with_token(
            identity, side_effect_key, expected_status=expected_status,
            expected_updated_at=expected_updated_at,
        )
        return token is not None

    async def get_idempotency_record(
        self,
        idempotency_key: str,
        side_effect_key: str,
    ) -> IdempotencyRecord | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                    " trace_id, correlation_id, status, result_receipt_id,"
                    " metadata_json, created_at, updated_at FROM idempotency_records"
                    " WHERE idempotency_key = ? AND side_effect_key = ?",
                    (idempotency_key, side_effect_key),
                )
            ).fetchone()
        return _row_to_idempotency_record(row) if row is not None else None

    def get_idempotency_record_sync(
        self,
        idempotency_key: str,
        side_effect_key: str,
    ) -> IdempotencyRecord | None:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                " trace_id, correlation_id, status, result_receipt_id,"
                " metadata_json, created_at, updated_at FROM idempotency_records"
                " WHERE idempotency_key = ? AND side_effect_key = ?",
                (idempotency_key, side_effect_key),
            ).fetchone()
        return _row_to_idempotency_record(row) if row is not None else None

    async def was_side_effect_performed(
        self,
        idempotency_key: str,
        side_effect_key: str,
    ) -> bool:
        record = await self.get_idempotency_record(idempotency_key, side_effect_key)
        return record is not None and record.status in {"completed", "skipped"}

    async def list_child_runs(self, parent_run_id: str) -> list[DelegationRun]:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                    " assigned_by, assigned_to, requested_output_json,"
                    " current_artifact_id, status, started_at, completed_at,"
                    " failure_code, metadata_json FROM delegation_runs"
                    " WHERE parent_run_id = ? ORDER BY started_at ASC",
                    (parent_run_id,),
                )
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    async def describe_run(self, run_id: str) -> dict[str, Any]:
        identity = await self.get_execution_identity(run_id)
        run = await self.get_delegation_run(run_id)
        artifacts = await self.list_artifacts(run_id=run_id, limit=100)
        receipts = await self.list_runtime_receipts(run_id=run_id, limit=200)
        mappings = await self.list_mapping_receipts(run_id=run_id, limit=200)
        children = await self.list_child_runs(run_id)
        topology_state = await self.get_topology_state(run_id)
        idempotency_records: list[IdempotencyRecord] = []
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                    " trace_id, correlation_id, status, result_receipt_id,"
                    " metadata_json, created_at, updated_at"
                    " FROM idempotency_records WHERE run_id = ?"
                    " ORDER BY created_at ASC",
                    (run_id,),
                )
            ).fetchall()
        idempotency_records = [_row_to_idempotency_record(row) for row in rows]
        return {
            "identity": identity,
            "run": run,
            "artifacts": artifacts,
            "receipts": receipts,
            "mappings": mappings,
            "children": children,
            "topology_state": topology_state,
            "idempotency_records": idempotency_records,
        }

    async def get_run_ledger(self, run_id: str) -> dict[str, Any]:
        """Return the durable runtime facts known for one run."""
        return await self.describe_run(run_id)

    async def record_memory_fact(self, fact: MemoryFact) -> MemoryFact:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO memory_facts (fact_id, session_id, task_id, fact_kind,"
                " truth_state, text, confidence, valid_from, valid_to, source_event_id,"
                " source_artifact_id, provenance_json, metadata_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(fact_id) DO UPDATE SET"
                " session_id = excluded.session_id,"
                " task_id = excluded.task_id,"
                " fact_kind = excluded.fact_kind,"
                " truth_state = excluded.truth_state,"
                " text = excluded.text,"
                " confidence = excluded.confidence,"
                " valid_from = excluded.valid_from,"
                " valid_to = excluded.valid_to,"
                " source_event_id = excluded.source_event_id,"
                " source_artifact_id = excluded.source_artifact_id,"
                " provenance_json = excluded.provenance_json,"
                " metadata_json = excluded.metadata_json,"
                " created_at = excluded.created_at,"
                " updated_at = excluded.updated_at",
                (
                    fact.fact_id,
                    fact.session_id,
                    fact.task_id,
                    fact.fact_kind,
                    fact.truth_state,
                    fact.text,
                    float(fact.confidence),
                    fact.valid_from.isoformat() if fact.valid_from else None,
                    fact.valid_to.isoformat() if fact.valid_to else None,
                    fact.source_event_id,
                    fact.source_artifact_id,
                    _json_dump(fact.provenance),
                    _json_dump(fact.metadata),
                    fact.created_at.isoformat(),
                    fact.updated_at.isoformat(),
                ),
            )
            await db.commit()
        loaded = await self.get_memory_fact(fact.fact_id)
        assert loaded is not None
        return loaded

    async def get_memory_fact(self, fact_id: str) -> MemoryFact | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT fact_id, session_id, task_id, fact_kind, truth_state, text,"
                    " confidence, valid_from, valid_to, source_event_id,"
                    " source_artifact_id, provenance_json, metadata_json,"
                    " created_at, updated_at FROM memory_facts WHERE fact_id = ?",
                    (fact_id,),
                )
            ).fetchone()
        return _row_to_memory_fact(row) if row is not None else None

    async def list_memory_facts(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        truth_state: str | None = None,
        limit: int = 20,
    ) -> list[MemoryFact]:
        await self.init_db()
        query = (
            "SELECT fact_id, session_id, task_id, fact_kind, truth_state, text,"
            " confidence, valid_from, valid_to, source_event_id, source_artifact_id,"
            " provenance_json, metadata_json, created_at, updated_at"
            " FROM memory_facts WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if truth_state is not None:
            query += " AND truth_state = ?"
            params.append(truth_state)
        query += " ORDER BY updated_at DESC, confidence DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_memory_fact(row) for row in rows]

    async def update_memory_fact_truth(
        self,
        fact_id: str,
        *,
        truth_state: str,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryFact:
        existing = await self.get_memory_fact(fact_id)
        if existing is None:
            raise KeyError(f"fact {fact_id} not found")
        updated = MemoryFact(
            fact_id=existing.fact_id,
            session_id=existing.session_id,
            task_id=existing.task_id,
            fact_kind=existing.fact_kind,
            truth_state=truth_state,
            text=existing.text,
            confidence=existing.confidence if confidence is None else float(confidence),
            valid_from=existing.valid_from,
            valid_to=existing.valid_to,
            source_event_id=existing.source_event_id,
            source_artifact_id=existing.source_artifact_id,
            provenance=existing.provenance,
            metadata={**existing.metadata, **(metadata or {})},
            created_at=existing.created_at,
            updated_at=_utc_now(),
        )
        return await self.record_memory_fact(updated)

    async def record_memory_edge(self, edge: MemoryEdge) -> MemoryEdge:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO memory_edges (edge_id, from_fact_id, to_fact_id,"
                " relation, weight, source_event_id, metadata_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    edge.edge_id,
                    edge.from_fact_id,
                    edge.to_fact_id,
                    edge.relation,
                    float(edge.weight),
                    edge.source_event_id,
                    _json_dump(edge.metadata),
                    edge.created_at.isoformat(),
                ),
            )
            await db.commit()
        return edge

    async def record_context_bundle(self, bundle: ContextBundleRecord) -> ContextBundleRecord:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO context_bundles (bundle_id, session_id, task_id,"
                " run_id, token_budget, rendered_text, sections_json, source_refs_json,"
                " checksum, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    bundle.bundle_id,
                    bundle.session_id,
                    bundle.task_id,
                    bundle.run_id,
                    int(bundle.token_budget),
                    bundle.rendered_text,
                    _json_dump(bundle.sections),
                    _json_dump(bundle.source_refs),
                    bundle.checksum,
                    bundle.created_at.isoformat(),
                    _json_dump(bundle.metadata),
                ),
            )
            await db.commit()
        loaded = await self.get_context_bundle(bundle.bundle_id)
        assert loaded is not None
        return loaded

    async def get_context_bundle(self, bundle_id: str) -> ContextBundleRecord | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT bundle_id, session_id, task_id, run_id, token_budget,"
                    " rendered_text, sections_json, source_refs_json, checksum,"
                    " created_at, metadata_json FROM context_bundles WHERE bundle_id = ?",
                    (bundle_id,),
                )
            ).fetchone()
        return _row_to_context_bundle(row) if row is not None else None

    def get_context_bundle_sync(self, bundle_id: str) -> ContextBundleRecord | None:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT bundle_id, session_id, task_id, run_id, token_budget,"
                " rendered_text, sections_json, source_refs_json, checksum,"
                " created_at, metadata_json FROM context_bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
        return _row_to_context_bundle(row) if row is not None else None

    async def list_context_bundles(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        limit: int = 20,
    ) -> list[ContextBundleRecord]:
        await self.init_db()
        query = (
            "SELECT bundle_id, session_id, task_id, run_id, token_budget,"
            " rendered_text, sections_json, source_refs_json, checksum,"
            " created_at, metadata_json FROM context_bundles WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_context_bundle(row) for row in rows]

    async def record_operator_action(self, action: OperatorAction) -> OperatorAction:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO operator_actions (action_id, session_id, task_id,"
                " run_id, action_name, actor, reason, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    action.action_id,
                    action.session_id,
                    action.task_id,
                    action.run_id,
                    action.action_name,
                    action.actor,
                    action.reason,
                    _json_dump(action.payload),
                    action.created_at.isoformat(),
                ),
            )
            await db.commit()
        loaded = await self.get_operator_action(action.action_id)
        assert loaded is not None
        return loaded

    async def get_operator_action(self, action_id: str) -> OperatorAction | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT action_id, session_id, task_id, run_id, action_name, actor,"
                    " reason, payload_json, created_at FROM operator_actions"
                    " WHERE action_id = ?",
                    (action_id,),
                )
            ).fetchone()
        return _row_to_operator_action(row) if row is not None else None

    async def list_operator_actions(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        limit: int = 20,
    ) -> list[OperatorAction]:
        await self.init_db()
        query = (
            "SELECT action_id, session_id, task_id, run_id, action_name, actor,"
            " reason, payload_json, created_at FROM operator_actions WHERE 1=1"
        )
        params: list[Any] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, limit))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, params)).fetchall()
        return [_row_to_operator_action(row) for row in rows]

    @staticmethod
    def new_session_id() -> str:
        return _new_id("session")

    @staticmethod
    def new_claim_id() -> str:
        return _new_id("claim")

    @staticmethod
    def new_run_id() -> str:
        return _new_id("run")

    @staticmethod
    def new_lease_id() -> str:
        return _new_id("lease")

    @staticmethod
    def new_artifact_id() -> str:
        return _new_id("art")

    @staticmethod
    def new_fact_id() -> str:
        return _new_id("fact")

    @staticmethod
    def new_edge_id() -> str:
        return _new_id("edge")

    @staticmethod
    def new_bundle_id() -> str:
        return _new_id("ctx")

    @staticmethod
    def new_action_id() -> str:
        return _new_id("act")
