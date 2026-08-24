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
from typing import Any, Iterable
from uuid import uuid4

import aiosqlite

from dharma_swarm.correlation_context import get_correlation
from dharma_swarm.engine.event_memory import (
    ensure_memory_plane_schema_async,
    ensure_memory_plane_schema_sync,
)
from dharma_swarm.mission_control_operator_state import (
    OPERATOR_CONTROL_RECEIPT_REF_PREFIX,
    OPERATOR_CONTROL_RECEIPT_SCHEMA,
    OPERATOR_CONTROL_RECEIPT_TYPE,
    canonical_utc_timestamp,
    runtime_receipt_content_digest,
    validate_operator_control_state,
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
        "runtime_warrant", "sarathi_turn",
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

_IMMUTABLE_EXECUTION_METADATA_KEYS = frozenset(
    {
        "schema_version",
        "mission_id",
        "dispatch_key",
        "operation_id",
        "operation_digest",
        "context_id",
        "authority_ref",
        "authority_digest",
        "authenticated_principal",
        "subject",
        "nats_operation_hash",
        "capability",
    }
)

_RENEWABLE_TASK_CLAIM_STATUSES = frozenset(
    {"active", "claimed", "acknowledged", "running", "leased"}
)
_ABSORBING_RUNTIME_STATUSES = frozenset({"completed", "failed"})
_MISSION_CONTROL_RUNTIME_SCHEMA = "dharma.mission_control.v1"
_CLAIM_EVIDENCE_METADATA_KEY = "mission_control_evidence"
_IMMUTABLE_RUNTIME_RECEIPT_TYPES = frozenset(
    {
        "child_completed",
        "delegation_run",
        "mission_attempt_recovery",
        "mission_attempt_terminal",
        "mission_evidence_delta",
        "mission_independent_acceptance",
        "mission_campaign_cycle",
        "mission_campaign_control",
        "mission_verifier_result",
        OPERATOR_CONTROL_RECEIPT_TYPE,
        "task_claim",
        "mission_dispatch_indeterminate",
        "mission_observed_input",
    }
)
_IMMUTABLE_SESSION_SCHEMA_VALUES = frozenset(
    {"dharma.mission_control.campaign.v1"}
)

_CAMPAIGN_INDETERMINATE_SCHEMA = "dharma.sadhana.runtime_indeterminate.v1"
_PROVIDER_EVIDENCE_KEYS = frozenset(
    {
        "actual_served_provider",
        "actual_served_model",
        "served_provider",
        "served_model",
        "provider_served",
        "model_served",
    }
)


def _campaign_indeterminate_payload(
    *, mission_id: str, task_id: str, run_id: str, claim_id: str,
    agent_id: str, attempt_generation: int,
) -> dict[str, Any]:
    return {
        "schema_version": _CAMPAIGN_INDETERMINATE_SCHEMA,
        "mission_id": mission_id,
        "task_id": task_id,
        "run_id": run_id,
        "claim_id": claim_id,
        "agent_id": agent_id,
        "attempt_generation": attempt_generation,
        "provider_task_scheduled": False,
    }


def _pre_effect_payload_is_exact(
    payload: dict[str, Any], *, mission_id: str, attempt_generation: int,
) -> bool:
    return bool(
        payload.get("mission_id") == mission_id
        and payload.get("attempt_generation") == attempt_generation
        and not any(payload.get(key) for key in _PROVIDER_EVIDENCE_KEYS)
        and payload.get("provider_execution") is not True
    )


def _pre_effect_receipt_is_exact(
    receipt: RuntimeReceipt,
    identity: ExecutionIdentity,
    *,
    mission_id: str,
    claim_id: str,
    attempt_generation: int,
    indeterminate_receipt_id: str,
    indeterminate_payload: dict[str, Any],
) -> bool:
    carrier = (
        receipt.run_id,
        receipt.task_id,
        receipt.trace_id,
        receipt.correlation_id,
        receipt.causation_id,
        receipt.parent_run_id,
        receipt.agent_id,
        receipt.idempotency_key,
    )
    expected_carrier = (
        identity.run_id,
        identity.task_id,
        identity.trace_id,
        identity.correlation_id,
        identity.causation_id,
        identity.parent_run_id,
        identity.agent_id,
        identity.idempotency_key,
    )
    if carrier != expected_carrier:
        return False
    if receipt.receipt_id == indeterminate_receipt_id:
        return bool(
            receipt.receipt_type == "mission_dispatch_indeterminate"
            and receipt.status == "failed"
            and receipt.side_effect_key
            == f"campaign_dispatch_indeterminate:{identity.run_id}"
            and receipt.payload == indeterminate_payload
        )
    prefix = "task_claim" if receipt.side_effect_key.startswith("task_claim:") else (
        "delegation_run"
        if receipt.side_effect_key.startswith("delegation_run:")
        else ""
    )
    status = receipt.side_effect_key.rsplit(":", 1)[-1]
    target = claim_id if prefix == "task_claim" else identity.run_id
    if (
        prefix not in {"task_claim", "delegation_run"}
        or status not in {"claimed", "running"}
        or receipt.side_effect_key != f"{prefix}:{target}:{status}"
        or not _pre_effect_payload_is_exact(
            receipt.payload,
            mission_id=mission_id,
            attempt_generation=attempt_generation,
        )
    ):
        return False
    allowed = {
        prefix: {status},
        "idempotency_consumed": {"accepted"},
        "side_effect_intent": {"started"},
        "side_effect_complete": {"completed"},
    }
    if receipt.status not in allowed.get(receipt.receipt_type, set()):
        return False
    if prefix == "task_claim" and receipt.payload.get("claim_id") != claim_id:
        return False
    if receipt.receipt_type == "side_effect_complete":
        expected = f"rr_{identity.run_id}_{status}_{'claim' if prefix == 'task_claim' else 'run'}"
        return receipt.payload.get("result_receipt_id") == expected
    return True


def _stable_bound_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _validate_campaign_cycle_receipt(receipt: RuntimeReceipt) -> None:
    if receipt.receipt_type == OPERATOR_CONTROL_RECEIPT_TYPE:
        _validate_campaign_operator_control_receipt(receipt)
        return
    if receipt.receipt_type != "mission_campaign_cycle":
        return
    payload = receipt.payload
    mission_id = payload.get("mission_id")
    generation = payload.get("generation")
    sequence = payload.get("sequence")
    if (
        not isinstance(mission_id, str)
        or not mission_id
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence < 1
    ):
        raise ValueError("campaign cycle receipt coordinates are invalid")
    expected_id = _stable_bound_id(
        "mission_campaign_cycle", mission_id, str(generation), str(sequence)
    )
    if (
        payload.get("schema_version") != "dharma.mission_control.campaign.v1"
        or receipt.receipt_id != expected_id
        or receipt.correlation_id != f"mission_campaign:{mission_id}"
        or receipt.run_id
        != _stable_bound_id("mission_campaign_run", mission_id, str(generation))
        or receipt.agent_id != "mission-control-supervisor"
        or receipt.idempotency_key != expected_id
        or receipt.side_effect_key != f"mission_campaign_cycle:{generation}:{sequence}"
        or receipt.status not in {"completed", "partial"}
    ):
        raise ValueError("campaign cycle receipt carrier is invalid")


def _validate_campaign_operator_control_receipt(receipt: RuntimeReceipt) -> None:
    payload = receipt.payload
    mission_id = payload.get("mission_id")
    generation = payload.get("campaign_generation")
    sequence = payload.get("transition_sequence")
    idempotency_key = payload.get("idempotency_key")
    status = payload.get("application_status")
    expected_fields = {
        "schema_version",
        "campaign_schema_version",
        "mission_id",
        "config_digest",
        "campaign_generation",
        "transition_sequence",
        "request_id",
        "idempotency_key",
        "action",
        "issued_at",
        "expires_at",
        "reason",
        "operator_login",
        "source_envelope_sha256",
        "prior_control_state",
        "next_control_state",
        "application_status",
        "rejection_reason",
        "authority_applied_at",
        "preserves_queued_work",
        "external_effect_performed",
    }
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != OPERATOR_CONTROL_RECEIPT_SCHEMA
        or payload.get("campaign_schema_version")
        != "dharma.mission_control.campaign.v1"
        or not isinstance(mission_id, str)
        or not mission_id
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence < 0
        or not isinstance(idempotency_key, str)
        or not idempotency_key
        or status not in {"applied", "rejected"}
        or receipt.status != status
        or receipt.receipt_id
        != _stable_bound_id(
            "mission_campaign_operator_control", mission_id, idempotency_key
        )
        or receipt.run_id
        != _stable_bound_id("mission_campaign_run", mission_id, str(generation))
        or receipt.correlation_id != f"mission_campaign:{mission_id}"
        or receipt.agent_id != "mission-control-supervisor"
        or receipt.idempotency_key != idempotency_key
        or receipt.side_effect_key
        != f"mission_campaign_operator_control:{idempotency_key}"
        or payload.get("authority_applied_at")
        != canonical_utc_timestamp(receipt.created_at)
        or payload.get("preserves_queued_work") is not True
        or payload.get("external_effect_performed") is not False
    ):
        raise ValueError("campaign operator control receipt carrier is invalid")


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
        _EPISODE_EVENT_OUTBOX_DDL, _EXECUTION_IDENTITIES_DDL,
        _RUNTIME_RECEIPTS_DDL,
        _IDEMPOTENCY_RECORDS_DDL,
    ):
        db.execute(ddl)
    for tbl, column_sql in (
        ("task_claims", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "receipt_json TEXT"),
        ("artifact_records", "trace_id TEXT NOT NULL DEFAULT ''"), *_EPISODE_OUTBOX_MIGRATIONS,
    ):
        try:
            db.execute(f"ALTER TABLE {tbl} ADD COLUMN {column_sql}")
        except sqlite3.Error:
            pass
    for idx in _INDEXES:
        db.execute(idx)
    if include_memory_plane:
        ensure_memory_plane_schema_sync(db)
    _backfill_episode_outbox_keys_and_commit_sync(db)


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
        _EPISODE_EVENT_OUTBOX_DDL, _EXECUTION_IDENTITIES_DDL,
        _RUNTIME_RECEIPTS_DDL,
        _IDEMPOTENCY_RECORDS_DDL,
    ):
        await db.execute(ddl)
    # Migrate old runtime DBs without changing existing rows destructively.
    for tbl, column_sql in (
        ("task_claims", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "trace_id TEXT NOT NULL DEFAULT ''"),
        ("delegation_runs", "receipt_json TEXT"),
        ("artifact_records", "trace_id TEXT NOT NULL DEFAULT ''"), *_EPISODE_OUTBOX_MIGRATIONS,
    ):
        try:
            await db.execute(f"ALTER TABLE {tbl} ADD COLUMN {column_sql}")
        except Exception:
            pass  # column already exists
    for idx in _INDEXES:
        await db.execute(idx)
    if include_memory_plane:
        await ensure_memory_plane_schema_async(db)
    await _backfill_episode_outbox_keys_and_commit_async(db)


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


def _absorbing_claim_replay(existing: TaskClaim, candidate: TaskClaim) -> bool:
    """Make terminal claim custody first-writer-wins."""
    if not _is_absorbing_runtime_row(existing.status, existing.metadata):
        return False
    if candidate.status.lower() != existing.status.lower():
        raise ValueError("terminal claim cannot be replaced by conflicting replay")
    return True


def _absorbing_run_replay(
    existing: DelegationRun,
    candidate: DelegationRun,
) -> bool:
    """Make terminal run custody first-writer-wins."""
    if not _is_absorbing_runtime_row(existing.status, existing.metadata):
        return False
    if candidate.status.lower() != existing.status.lower():
        raise ValueError("terminal run cannot be replaced by conflicting replay")
    return True


def _is_absorbing_runtime_row(status: str, metadata: dict[str, Any]) -> bool:
    normalized = status.lower()
    return normalized in _ABSORBING_RUNTIME_STATUSES or (
        normalized == "stale_recovered"
        and metadata.get("schema_version") == _MISSION_CONTROL_RUNTIME_SCHEMA
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


_IDEMPOTENCY_COMPLETION_STATUSES = frozenset({"completed", "failed"})
_IDEMPOTENCY_OWNER_METADATA_KEY = "idempotency_owner_execution"
_IDEMPOTENCY_OWNER_FIELDS = (
    "trace_id",
    "correlation_id",
    "task_id",
    "run_id",
    "claim_id",
    "idempotency_key",
    "causation_id",
    "parent_run_id",
    "agent_id",
    "session_id",
    "external_a2a_task_id",
)


def _side_effect_complete_receipt_id(
    identity: ExecutionIdentity,
    side_effect_key: str,
    *,
    status: str,
    result_receipt_id: str,
    payload: dict[str, Any],
) -> str:
    """Name exact completion evidence so a post-commit retry can heal it."""
    return _stable_bound_id(
        "rr_side_effect_complete",
        identity.run_id,
        identity.idempotency_key,
        side_effect_key,
        status,
        result_receipt_id,
        _json_dump(payload),
    )


def _execution_identity_replay_matches_owner(
    owner: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
) -> bool:
    if owner is None or owner.run_id != incoming.run_id:
        return False
    try:
        owner.require_for_dispatch()
        _merge_execution_identity_metadata(owner, incoming, None)
    except MissingExecutionIdentity:
        return False
    except ValueError:
        return False
    return all(
        not str(getattr(incoming, field_name, "") or "")
        or getattr(incoming, field_name) == getattr(owner, field_name)
        for field_name in _IDEMPOTENCY_OWNER_FIELDS
    )


def _idempotency_identity_from_canonical(
    canonical: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
) -> ExecutionIdentity:
    """Bind one effect owner without conflating run and effect idempotency."""
    if canonical is None:
        return incoming
    authority_fields = tuple(
        field_name
        for field_name in _IDEMPOTENCY_OWNER_FIELDS
        if field_name != "idempotency_key"
    )
    if any(
        str(getattr(incoming, field_name, "") or "")
        and getattr(incoming, field_name) != getattr(canonical, field_name)
        for field_name in authority_fields
    ):
        raise ValueError("idempotency execution identity conflicts with durable owner")
    _merge_execution_identity_metadata(canonical, incoming, None)
    return replace(
        canonical,
        idempotency_key=incoming.idempotency_key,
        metadata=dict(canonical.metadata),
    )


def _idempotency_owner_payload(identity: ExecutionIdentity) -> dict[str, str]:
    return {
        field_name: str(getattr(identity, field_name, "") or "")
        for field_name in _IDEMPOTENCY_OWNER_FIELDS
    }


def _idempotency_owner_from_metadata(
    metadata: dict[str, Any] | None,
) -> ExecutionIdentity | None:
    raw = dict(metadata or {}).get(_IDEMPOTENCY_OWNER_METADATA_KEY)
    if (
        not isinstance(raw, dict)
        or set(raw) != set(_IDEMPOTENCY_OWNER_FIELDS)
        or any(not isinstance(raw.get(field_name), str) for field_name in raw)
        or any(
            not str(raw.get(field_name) or "").strip()
            for field_name in (
                "trace_id",
                "correlation_id",
                "task_id",
                "run_id",
                "claim_id",
                "idempotency_key",
            )
        )
    ):
        return None
    return ExecutionIdentity(
        **raw,
        message_id="",
        event_id="",
        artifact_id="",
        proposal_id="",
        metadata={},
    )


def _idempotency_owner_identity(
    record: IdempotencyRecord,
    durable: ExecutionIdentity | None,
) -> ExecutionIdentity | None:
    owner = _idempotency_owner_from_metadata(record.metadata)
    if owner is None:
        return (
            replace(durable, idempotency_key=record.idempotency_key)
            if durable is not None
            else None
        )
    if durable is None:
        return None
    try:
        return _idempotency_identity_from_canonical(durable, owner)
    except ValueError:
        return None


def _idempotency_effect_rebind_allowed(
    records: Iterable[IdempotencyRecord],
    durable: ExecutionIdentity,
    incoming: ExecutionIdentity,
) -> bool:
    """Authorize a per-effect alias only from its already-bound memo row."""
    return any(
        _idempotency_identity_matches(
            record,
            incoming,
            _idempotency_owner_identity(record, durable),
        )
        for record in records
    )


def _metadata_with_idempotency_owner(
    metadata: dict[str, Any] | None,
    owner: ExecutionIdentity,
) -> dict[str, Any]:
    values = dict(metadata or {})
    if _IDEMPOTENCY_OWNER_METADATA_KEY in values:
        raise ValueError("idempotency owner metadata is reserved")
    values[_IDEMPOTENCY_OWNER_METADATA_KEY] = _idempotency_owner_payload(owner)
    return values


def _idempotency_identity_matches(
    record: IdempotencyRecord,
    identity: ExecutionIdentity,
    owner: ExecutionIdentity | None,
) -> bool:
    return _execution_identity_replay_matches_owner(owner, identity) and (
        record.run_id,
        record.task_id,
        record.trace_id,
        record.correlation_id,
        record.idempotency_key,
    ) == (
        owner.run_id,
        owner.task_id,
        owner.trace_id,
        owner.correlation_id,
        owner.idempotency_key,
    )


def _replayable_idempotency_terminal(record: IdempotencyRecord) -> bool:
    """A complete memoized provider result is absorbing dispatch authority."""
    metadata = record.metadata
    receipt = metadata.get("receipt") if isinstance(metadata, dict) else None
    attributes = receipt.get("attributes") if isinstance(receipt, dict) else None
    encoded = metadata.get("result_json") if isinstance(metadata, dict) else None
    if not isinstance(encoded, str):
        return False
    try:
        json.loads(encoded)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    return bool(
        record.status == "completed"
        and record.result_receipt_id
        and isinstance(receipt, dict)
        and isinstance(attributes, dict)
        and metadata.get("operation_hash")
        and receipt.get("receipt_id") == record.result_receipt_id
        and receipt.get("status") == "ok"
        and receipt.get("task_id") == record.task_id
        and receipt.get("trace_id") == record.trace_id
        and attributes.get("run_id") == record.run_id
        and attributes.get("idempotency_key") == record.idempotency_key
        and attributes.get("side_effect_key") == record.side_effect_key
        and attributes.get("unprotected_dispatch") is not True
    )


def _merge_idempotency_metadata(
    existing: IdempotencyRecord,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    incoming = dict(metadata or {})
    current_owner = existing.metadata.get(_IDEMPOTENCY_OWNER_METADATA_KEY)
    if (
        _IDEMPOTENCY_OWNER_METADATA_KEY in incoming
        and incoming[_IDEMPOTENCY_OWNER_METADATA_KEY] != current_owner
    ):
        raise ValueError("idempotency owner metadata conflicts with first writer")
    merged = dict(existing.metadata)
    merged.update(incoming)
    if current_owner is not None:
        merged[_IDEMPOTENCY_OWNER_METADATA_KEY] = current_owner
    return merged


def _merge_idempotency_completion_metadata(
    existing: IdempotencyRecord,
    metadata: dict[str, Any] | None,
    *,
    result_receipt_id: str,
) -> dict[str, Any]:
    """Preserve intent-time authority while adding terminal evidence."""
    incoming = dict(metadata or {})
    existing_hash = _operation_hash(existing.metadata)
    if (
        existing_hash
        and "operation_hash" in incoming
        and _operation_hash(incoming) != existing_hash
    ):
        raise ValueError("idempotency completion operation_hash conflicts with intent")
    merged = _merge_idempotency_metadata(existing, incoming)
    if (
        "result_receipt_id" in merged
        and merged["result_receipt_id"] != result_receipt_id
    ):
        raise ValueError("idempotency completion result_receipt_id conflicts with evidence")
    return merged


def _side_effect_completion_payload(
    result_receipt_id: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    values = dict(payload or {})
    if (
        "result_receipt_id" in values
        and values["result_receipt_id"] != result_receipt_id
    ):
        raise ValueError("side-effect completion result_receipt_id conflicts with evidence")
    values["result_receipt_id"] = result_receipt_id
    return values


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


def _merge_execution_identity_metadata(
    existing: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge additive lifecycle metadata without weakening security bindings."""
    additions = {**dict(incoming.metadata or {}), **dict(metadata or {})}
    if existing is None:
        return additions
    merged = dict(existing.metadata or {})
    for key in _IMMUTABLE_EXECUTION_METADATA_KEYS:
        current = merged.get(key)
        proposed = additions.get(key)
        if current not in (None, "") and proposed not in (None, ""):
            if _json_dump(current) != _json_dump(proposed):
                raise ValueError(
                    "execution identity immutable metadata conflict for "
                    f"run_id {incoming.run_id!r}: {key}"
                )
    merged.update(additions)
    for key in _IMMUTABLE_EXECUTION_METADATA_KEYS:
        current = (existing.metadata or {}).get(key)
        if current not in (None, ""):
            merged[key] = current
    return merged


def _merge_execution_identity(
    existing: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
    metadata: dict[str, Any] | None,
) -> ExecutionIdentity:
    """Preserve every already-bound identity coordinate on sparse replay."""
    _raise_on_execution_identity_conflict(existing, incoming)
    coordinates = {
        field_name: getattr(existing, field_name)
        for field_name in _EXECUTION_IDENTITY_CONFLICT_FIELDS
        if existing is not None
        and str(getattr(existing, field_name, "") or "")
        and not str(getattr(incoming, field_name, "") or "")
    }
    return replace(
        incoming,
        **coordinates,
        metadata=_merge_execution_identity_metadata(existing, incoming, metadata),
    )


def _preserve_claim_evidence_metadata(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    *,
    claim_id: str,
) -> dict[str, Any]:
    """Keep the CAS-owned evidence generation immutable to generic writers."""
    current = dict(existing or {})
    additions = dict(incoming or {})
    current_evidence = current.get(_CLAIM_EVIDENCE_METADATA_KEY)
    proposed_evidence = additions.get(_CLAIM_EVIDENCE_METADATA_KEY)
    if current_evidence is not None and proposed_evidence is not None:
        if _json_dump(current_evidence) != _json_dump(proposed_evidence):
            raise ValueError(
                "task claim reserved evidence metadata conflict for "
                f"claim_id {claim_id!r}"
            )
    merged = {**current, **additions}
    if current_evidence is not None:
        merged[_CLAIM_EVIDENCE_METADATA_KEY] = current_evidence
    return merged


_EXECUTION_IDENTITY_ALIASES = (
    ("task_id", "task_id"),
    ("agent_id", "agent_id"),
    ("session_id", "session_id"),
    ("claim_id", "claim_id"),
    ("run_id", "run_id"),
    ("runtime_run_id", "run_id"),
    ("trace_id", "trace_id"),
    ("correlation_id", "correlation_id"),
    ("idempotency_key", "idempotency_key"),
    ("causation_id", "causation_id"),
    ("parent_run_id", "parent_run_id"),
    ("external_a2a_task_id", "external_a2a_task_id"),
    ("message_id", "message_id"),
    ("event_id", "event_id"),
    ("artifact_id", "artifact_id"),
    ("proposal_id", "proposal_id"),
)


def _complete_metadata_identity(
    metadata: dict[str, Any] | None,
    *,
    carrier: str,
) -> ExecutionIdentity | None:
    values = dict(metadata or {})
    nested = values.get("execution_identity")
    if nested is None:
        return None
    if not isinstance(nested, dict):
        raise ValueError(f"{carrier} ExecutionIdentity carrier is malformed")
    try:
        identity = ExecutionIdentity.from_metadata(values, require=True)
    except (MissingExecutionIdentity, ValueError) as exc:
        raise ValueError(f"{carrier} ExecutionIdentity carrier is incomplete") from exc
    if identity is None:
        raise ValueError(f"{carrier} ExecutionIdentity carrier is incomplete")
    _require_identity_aliases(values, identity, carrier=carrier)
    return identity.require_for_dispatch()


def _require_identity_aliases(
    metadata: dict[str, Any] | None,
    identity: ExecutionIdentity,
    *,
    carrier: str,
) -> None:
    values = dict(metadata or {})
    mismatches = [
        alias
        for alias, field in _EXECUTION_IDENTITY_ALIASES
        if alias in values
        and values.get(alias) != getattr(identity, field)
    ]
    if mismatches:
        raise ValueError(
            f"{carrier} ExecutionIdentity aliases conflict: {', '.join(mismatches)}"
        )


def _stable_coordinate(
    current: str,
    proposed: str,
    *,
    carrier: str,
    field: str,
) -> str:
    if current and proposed and current != proposed:
        raise ValueError(f"{carrier} immutable {field} conflicts")
    return current or proposed


def _validate_claim_identity_binding(
    identity: ExecutionIdentity,
    claim: TaskClaim,
    *,
    carrier: str,
) -> None:
    expected = {
        "task_id": claim.task_id,
        "claim_id": claim.claim_id,
        "agent_id": claim.agent_id,
        "session_id": claim.session_id,
    }
    mismatches = [
        field
        for field, value in expected.items()
        if value and str(getattr(identity, field) or "") != value
    ]
    if mismatches:
        raise ValueError(
            f"{carrier} ExecutionIdentity claim binding conflicts: "
            + ", ".join(mismatches)
        )


def _normalize_claim_replay(
    existing: TaskClaim | None,
    candidate: TaskClaim,
) -> tuple[TaskClaim, ExecutionIdentity | None]:
    if existing is not None:
        if existing.task_id != candidate.task_id:
            raise ValueError("task claim immutable task_id conflicts")
        if existing.agent_id != candidate.agent_id:
            raise ValueError("task claim immutable agent_id conflicts")
        candidate = replace(
            candidate,
            session_id=_stable_coordinate(
                existing.session_id,
                candidate.session_id,
                carrier="task claim",
                field="session_id",
            ),
        )
    current_identity = _complete_metadata_identity(
        existing.metadata if existing is not None else None,
        carrier="existing task claim",
    )
    incoming_identity = _complete_metadata_identity(
        candidate.metadata,
        carrier="incoming task claim",
    )
    if (
        existing is not None
        and _is_absorbing_runtime_row(existing.status, existing.metadata)
        and current_identity is None
        and incoming_identity is not None
    ):
        raise ValueError("terminal task claim cannot acquire an ExecutionIdentity")
    if current_identity is not None:
        _validate_claim_identity_binding(
            current_identity,
            existing or candidate,
            carrier="existing task claim",
        )
        _require_identity_aliases(
            candidate.metadata,
            current_identity,
            carrier="incoming task claim",
        )
    if current_identity is not None and incoming_identity is not None:
        if current_identity.run_id != incoming_identity.run_id:
            raise ValueError("task claim ExecutionIdentity cannot be rebound")
        try:
            identity = _merge_execution_identity(
                current_identity, incoming_identity, None
            )
        except ValueError as exc:
            raise ValueError("task claim ExecutionIdentity cannot be rebound") from exc
    else:
        identity = current_identity or incoming_identity
    if incoming_identity is not None:
        _validate_claim_identity_binding(
            identity or incoming_identity,
            candidate,
            carrier="incoming task claim",
        )
    metadata = _preserve_claim_evidence_metadata(
        existing.metadata if existing is not None else None,
        candidate.metadata,
        claim_id=candidate.claim_id,
    )
    if identity is not None:
        metadata = _metadata_with_identity(metadata, identity)
    return replace(candidate, metadata=metadata), identity


def _validate_run_identity_binding(
    identity: ExecutionIdentity,
    run: DelegationRun,
    *,
    carrier: str,
) -> None:
    expected = {
        "task_id": run.task_id,
        "run_id": run.run_id,
        "claim_id": run.claim_id,
        "agent_id": run.assigned_to,
        "session_id": run.session_id,
        "parent_run_id": run.parent_run_id,
    }
    mismatches = [
        field
        for field, value in expected.items()
        if str(getattr(identity, field) or "") != value
    ]
    if mismatches:
        raise ValueError(
            f"{carrier} ExecutionIdentity run binding conflicts: "
            + ", ".join(mismatches)
        )


def _normalize_run_replay(
    existing: DelegationRun | None,
    candidate: DelegationRun,
) -> tuple[DelegationRun, ExecutionIdentity | None]:
    if existing is not None:
        if existing.task_id != candidate.task_id:
            raise ValueError("delegation run immutable task_id conflicts")
        if existing.assigned_to != candidate.assigned_to:
            raise ValueError("delegation run immutable assigned_to conflicts")
        candidate = replace(
            candidate,
            session_id=_stable_coordinate(
                existing.session_id,
                candidate.session_id,
                carrier="delegation run",
                field="session_id",
            ),
            claim_id=_stable_coordinate(
                existing.claim_id,
                candidate.claim_id,
                carrier="delegation run",
                field="claim_id",
            ),
            parent_run_id=_stable_coordinate(
                existing.parent_run_id,
                candidate.parent_run_id,
                carrier="delegation run",
                field="parent_run_id",
            ),
        )
    current_identity = _complete_metadata_identity(
        existing.metadata if existing is not None else None,
        carrier="existing delegation run",
    )
    incoming_identity = _complete_metadata_identity(
        candidate.metadata,
        carrier="incoming delegation run",
    )
    if (
        existing is not None
        and _is_absorbing_runtime_row(existing.status, existing.metadata)
        and current_identity is None
        and incoming_identity is not None
    ):
        raise ValueError("terminal delegation run cannot acquire an ExecutionIdentity")
    if current_identity is not None:
        _validate_run_identity_binding(
            current_identity,
            existing or candidate,
            carrier="existing delegation run",
        )
        _require_identity_aliases(
            candidate.metadata,
            current_identity,
            carrier="incoming delegation run",
        )
    if current_identity is not None and incoming_identity is not None:
        if current_identity.run_id != incoming_identity.run_id:
            raise ValueError("delegation run ExecutionIdentity cannot be rebound")
        try:
            identity = _merge_execution_identity(
                current_identity, incoming_identity, None
            )
        except ValueError as exc:
            raise ValueError("delegation run ExecutionIdentity cannot be rebound") from exc
    else:
        identity = current_identity or incoming_identity
    if incoming_identity is not None:
        _validate_run_identity_binding(
            identity or incoming_identity,
            candidate,
            carrier="incoming delegation run",
        )
    metadata = {
        **(existing.metadata if existing is not None else {}),
        **candidate.metadata,
    }
    if identity is not None:
        metadata = _metadata_with_identity(metadata, identity)
    return replace(candidate, metadata=metadata), identity


def _later_timestamp(
    current: datetime | None,
    proposed: datetime | None,
) -> datetime | None:
    if current is None:
        return proposed
    if proposed is None or proposed < current:
        return current
    return proposed


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
        row = db.execute(
            "SELECT metadata_json FROM sessions WHERE session_id = ?",
            (event.session_id,),
        ).fetchone()
        if row is not None and _json_load(row[0], {}).get(
            "schema_version"
        ) in _IMMUTABLE_SESSION_SCHEMA_VALUES:
            return
        if row is None and event.session_id.startswith("mission_campaign:"):
            raise ValueError("session event cannot reserve a campaign session")
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
        row = await (
            await db.execute(
                "SELECT metadata_json FROM sessions WHERE session_id = ?",
                (event.session_id,),
            )
        ).fetchone()
        if row is not None and _json_load(row[0], {}).get(
            "schema_version"
        ) in _IMMUTABLE_SESSION_SCHEMA_VALUES:
            return
        if row is None and event.session_id.startswith("mission_campaign:"):
            raise ValueError("session event cannot reserve a campaign session")
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
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT session_id, operator_id, status, current_task_id,"
                    " active_bundle_id, metadata_json, created_at, updated_at"
                    " FROM sessions WHERE session_id = ?",
                    (session.session_id,),
                )
            ).fetchone()
            existing = _row_to_session(row) if row is not None else None
            existing_schema = (
                existing.metadata.get("schema_version") if existing is not None else None
            )
            incoming_schema = session.metadata.get("schema_version")
            if (
                session.session_id.startswith("mission_campaign:")
                or (
                    existing_schema in _IMMUTABLE_SESSION_SCHEMA_VALUES
                    or incoming_schema in _IMMUTABLE_SESSION_SCHEMA_VALUES
                )
            ):
                if existing == session:
                    await db.commit()
                    return existing
                await db.rollback()
                raise ValueError(
                    "reserved campaign session requires exact create-or-CAS mutation"
                )
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
            row = await (
                await db.execute(
                    "SELECT session_id, operator_id, status, current_task_id,"
                    " active_bundle_id, metadata_json, created_at, updated_at"
                    " FROM sessions WHERE session_id = ?",
                    (session.session_id,),
                )
            ).fetchone()
            await db.commit()
        assert row is not None
        return _row_to_session(row)

    async def insert_session_if_absent(
        self,
        session: SessionState,
        *,
        atomic_receipt: RuntimeReceipt,
    ) -> SessionState | None:
        """Create one session and its immutable receipt in the same transaction."""
        _validate_campaign_cycle_receipt(atomic_receipt)
        if (
            atomic_receipt.correlation_id != session.session_id
            or atomic_receipt.created_at != session.updated_at
        ):
            raise ValueError("atomic session receipt does not bind the new session")
        session_schema = session.metadata.get("schema_version")
        if session.session_id.startswith("mission_campaign:") and (
            session_schema not in _IMMUTABLE_SESSION_SCHEMA_VALUES
        ):
            raise ValueError("reserved campaign session requires campaign schema")
        if session_schema in _IMMUTABLE_SESSION_SCHEMA_VALUES:
            mission_id = session.metadata.get("mission_id")
            generation = session.metadata.get("generation")
            expected_receipt_id = _stable_bound_id(
                "mission_campaign_control", str(mission_id), "start", str(generation)
            )
            if (
                not isinstance(mission_id, str)
                or not mission_id
                or session.session_id != f"mission_campaign:{mission_id}"
                or generation != 1
                or session.status != "active"
                or session.metadata.get("stop_requested") is not False
                or session.metadata.get("last_cycle_sequence") != 0
                or session.metadata.get("last_cycle_receipt_id") != ""
                or atomic_receipt.receipt_type != "mission_campaign_control"
                or atomic_receipt.status != "start"
                or atomic_receipt.receipt_id != expected_receipt_id
                or atomic_receipt.agent_id != session.operator_id
                or atomic_receipt.payload.get("schema_version")
                != session.metadata.get("schema_version")
                or atomic_receipt.payload.get("mission_id") != mission_id
                or atomic_receipt.payload.get("generation") != generation
                or atomic_receipt.payload.get("action") != "start"
            ):
                raise ValueError("campaign start receipt does not bind initial session")
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            inserted = await db.execute(
                "INSERT INTO sessions (session_id, operator_id, status, current_task_id,"
                " active_bundle_id, metadata_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(session_id) DO NOTHING",
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
            if inserted.rowcount != 1:
                await db.rollback()
                return None
            receipt_row = await (
                await db.execute(
                    "SELECT receipt_id FROM runtime_receipts WHERE receipt_id = ?",
                    (atomic_receipt.receipt_id,),
                )
            ).fetchone()
            if receipt_row is not None:
                await db.rollback()
                raise ValueError("atomic session receipt identity already exists")
            await db.execute(
                "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id, task_id,"
                " trace_id, correlation_id, causation_id, parent_run_id, agent_id,"
                " idempotency_key, side_effect_key, status, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    atomic_receipt.receipt_id,
                    atomic_receipt.receipt_type,
                    atomic_receipt.run_id,
                    atomic_receipt.task_id,
                    atomic_receipt.trace_id,
                    atomic_receipt.correlation_id,
                    atomic_receipt.causation_id,
                    atomic_receipt.parent_run_id,
                    atomic_receipt.agent_id,
                    atomic_receipt.idempotency_key,
                    atomic_receipt.side_effect_key,
                    atomic_receipt.status,
                    _json_dump(atomic_receipt.payload),
                    atomic_receipt.created_at.isoformat(),
                ),
            )
            row = await (
                await db.execute(
                    "SELECT session_id, operator_id, status, current_task_id,"
                    " active_bundle_id, metadata_json, created_at, updated_at"
                    " FROM sessions WHERE session_id = ?",
                    (session.session_id,),
                )
            ).fetchone()
            await db.commit()
        assert row is not None
        return _row_to_session(row)

    async def compare_and_swap_session(
        self,
        expected: SessionState,
        replacement: SessionState,
        *,
        atomic_receipt: RuntimeReceipt | None = None,
    ) -> SessionState | None:
        """Replace one exact session generation, optionally with one receipt."""
        if atomic_receipt is not None:
            _validate_campaign_cycle_receipt(atomic_receipt)
        if (
            replacement.session_id != expected.session_id
            or replacement.created_at != expected.created_at
            or replacement.updated_at <= expected.updated_at
        ):
            raise ValueError("session CAS replacement changes its fenced identity")
        expected_schema = expected.metadata.get("schema_version")
        replacement_schema = replacement.metadata.get("schema_version")
        if (
            expected.session_id.startswith("mission_campaign:")
            or expected_schema in _IMMUTABLE_SESSION_SCHEMA_VALUES
            or replacement_schema in _IMMUTABLE_SESSION_SCHEMA_VALUES
        ):
            if expected_schema != replacement_schema:
                raise ValueError("reserved campaign session schema is immutable")
            if atomic_receipt is None:
                raise ValueError("reserved campaign session CAS requires a receipt")
            expected_generation = expected.metadata.get("generation")
            replacement_generation = replacement.metadata.get("generation")
            mission_id = replacement.metadata.get("mission_id")
            if (
                isinstance(expected_generation, bool)
                or not isinstance(expected_generation, int)
                or isinstance(replacement_generation, bool)
                or not isinstance(replacement_generation, int)
                or not isinstance(mission_id, str)
                or not mission_id
                or replacement.session_id != f"mission_campaign:{mission_id}"
            ):
                raise ValueError("campaign session generation binding is invalid")
            operator_receipt = (
                atomic_receipt.receipt_type == OPERATOR_CONTROL_RECEIPT_TYPE
            )
            receipt_schema = atomic_receipt.payload.get(
                "campaign_schema_version" if operator_receipt else "schema_version"
            )
            receipt_generation = atomic_receipt.payload.get(
                "campaign_generation" if operator_receipt else "generation"
            )
            if (
                atomic_receipt.receipt_type
                not in {
                    "mission_campaign_control",
                    "mission_campaign_cycle",
                    OPERATOR_CONTROL_RECEIPT_TYPE,
                }
                or atomic_receipt.correlation_id != replacement.session_id
                or atomic_receipt.created_at != replacement.updated_at
                or receipt_schema not in _IMMUTABLE_SESSION_SCHEMA_VALUES
                or atomic_receipt.payload.get("mission_id")
                != mission_id
                or receipt_generation != replacement_generation
                or expected.metadata.get("mission_id") != mission_id
                or expected.metadata.get("config_digest")
                != replacement.metadata.get("config_digest")
                or expected.metadata.get("config") != replacement.metadata.get("config")
                or replacement.operator_id != expected.operator_id
                or replacement.current_task_id != expected.current_task_id
                or replacement.active_bundle_id != expected.active_bundle_id
            ):
                raise ValueError("campaign session receipt does not bind its replacement")
            if atomic_receipt.receipt_type == "mission_campaign_control":
                action = atomic_receipt.payload.get("action")
                valid_start = (
                    action == atomic_receipt.status == "start"
                    and replacement_generation == expected_generation + 1
                    and replacement.status == "active"
                    and replacement.metadata.get("stop_requested") is False
                    and replacement.metadata.get("last_cycle_sequence") == 0
                    and replacement.metadata.get("last_cycle_receipt_id") == ""
                )
                valid_stop = (
                    action == atomic_receipt.status == "stop"
                    and replacement_generation == expected_generation
                    and replacement.status == "stopped"
                    and replacement.metadata.get("stop_requested") is True
                    and replacement.metadata.get("last_cycle_sequence")
                    == expected.metadata.get("last_cycle_sequence")
                    and replacement.metadata.get("last_cycle_receipt_id")
                    == expected.metadata.get("last_cycle_receipt_id")
                )
                expected_receipt_id = _stable_bound_id(
                    "mission_campaign_control",
                    str(mission_id),
                    str(action),
                    str(replacement_generation),
                )
                if (
                    not (valid_start or valid_stop)
                    or atomic_receipt.receipt_id != expected_receipt_id
                    or atomic_receipt.agent_id != replacement.operator_id
                ):
                    raise ValueError("campaign control receipt transition is invalid")
            elif atomic_receipt.receipt_type == OPERATOR_CONTROL_RECEIPT_TYPE:
                action = atomic_receipt.payload.get("action")
                expected_raw_state = expected.metadata.get("operator_control_state")
                if expected_raw_state is None:
                    if expected.status != "active":
                        raise ValueError(
                            "campaign operator control state is missing"
                        )
                    expected_state = {
                        "schema_version": "dharma.sadhana.operator_control_state.v1",
                        "control_state": "RUNNING",
                        "campaign_generation": expected_generation,
                        "transition_sequence": 0,
                        "request_id": "",
                        "idempotency_key": "",
                        "action": "",
                        "source_envelope_sha256": "",
                        "authority_receipt_ref": "",
                        "authority_receipt_sha256": "",
                        "authority_applied_at": None,
                        "effect_state": "unobserved",
                        "effect_receipt_ref": "",
                        "effect_receipt_sha256": "",
                        "effect_observed_at": None,
                    }
                else:
                    expected_state = validate_operator_control_state(
                        expected_raw_state,
                        expected_generation=expected_generation,
                    )
                replacement_state = validate_operator_control_state(
                    replacement.metadata.get("operator_control_state"),
                    expected_generation=replacement_generation,
                )
                expected_without_state = dict(expected.metadata)
                replacement_without_state = dict(replacement.metadata)
                expected_without_state.pop("operator_control_state", None)
                replacement_without_state.pop("operator_control_state", None)
                expected_status = {"active": "RUNNING", "paused": "PAUSED"}.get(
                    expected.status
                )
                target_status = {"pause": ("paused", "PAUSED"), "resume": ("active", "RUNNING")}.get(
                    action
                )
                if (
                    target_status is None
                    or expected_status != expected_state["control_state"]
                    or replacement.status != target_status[0]
                    or replacement_state["control_state"] != target_status[1]
                    or replacement_generation != expected_generation
                    or replacement.metadata.get("stop_requested") is not False
                    or expected.metadata.get("stop_requested") is not False
                    or replacement_without_state != expected_without_state
                    or replacement_state["campaign_generation"]
                    != replacement_generation
                    or replacement_state["transition_sequence"]
                    != expected_state["transition_sequence"] + 1
                    or replacement_state["request_id"]
                    != atomic_receipt.payload.get("request_id")
                    or replacement_state["idempotency_key"]
                    != atomic_receipt.payload.get("idempotency_key")
                    or replacement_state["action"] != action
                    or replacement_state["source_envelope_sha256"]
                    != atomic_receipt.payload.get("source_envelope_sha256")
                    or replacement_state["authority_receipt_ref"]
                    != OPERATOR_CONTROL_RECEIPT_REF_PREFIX
                    + atomic_receipt.receipt_id
                    or replacement_state["authority_receipt_sha256"]
                    != runtime_receipt_content_digest(atomic_receipt)
                    or replacement_state["authority_applied_at"]
                    != canonical_utc_timestamp(atomic_receipt.created_at)
                    or replacement_state["effect_state"] != "unobserved"
                    or atomic_receipt.status != "applied"
                    or atomic_receipt.payload.get("prior_control_state")
                    != expected_state["control_state"]
                    or atomic_receipt.payload.get("next_control_state")
                    != replacement_state["control_state"]
                    or atomic_receipt.payload.get("transition_sequence")
                    != replacement_state["transition_sequence"]
                    or atomic_receipt.payload.get("config_digest")
                    != replacement.metadata.get("config_digest")
                ):
                    raise ValueError(
                        "campaign operator control receipt transition is invalid"
                    )
            else:
                sequence = replacement.metadata.get("last_cycle_sequence")
                expected_sequence = expected.metadata.get("last_cycle_sequence")
                if (
                    isinstance(sequence, bool)
                    or not isinstance(sequence, int)
                    or isinstance(expected_sequence, bool)
                    or not isinstance(expected_sequence, int)
                ):
                    raise ValueError("campaign cycle sequence binding is invalid")
                expected_receipt_id = _stable_bound_id(
                    "mission_campaign_cycle",
                    str(mission_id),
                    str(replacement_generation),
                    str(sequence),
                )
                if (
                    replacement_generation != expected_generation
                    or replacement.status != expected.status
                    or expected.status not in {"active", "paused"}
                    or (
                        expected.status == "paused"
                        and atomic_receipt.payload.get("dispatched") != 0
                    )
                    or replacement.metadata.get("stop_requested") is not False
                    or sequence != expected_sequence + 1
                    or atomic_receipt.payload.get("sequence") != sequence
                    or atomic_receipt.receipt_id != expected_receipt_id
                    or atomic_receipt.receipt_id
                    != replacement.metadata.get("last_cycle_receipt_id")
                    or atomic_receipt.idempotency_key != expected_receipt_id
                    or atomic_receipt.agent_id != "mission-control-supervisor"
                ):
                    raise ValueError("campaign cycle receipt transition is invalid")
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "UPDATE sessions SET operator_id = ?, status = ?, current_task_id = ?,"
                " active_bundle_id = ?, metadata_json = ?, updated_at = ?"
                " WHERE session_id = ? AND operator_id = ? AND status = ?"
                " AND current_task_id = ? AND active_bundle_id = ?"
                " AND metadata_json = ? AND created_at = ? AND updated_at = ?",
                (
                    replacement.operator_id,
                    replacement.status,
                    replacement.current_task_id,
                    replacement.active_bundle_id,
                    _json_dump(replacement.metadata),
                    replacement.updated_at.isoformat(),
                    expected.session_id,
                    expected.operator_id,
                    expected.status,
                    expected.current_task_id,
                    expected.active_bundle_id,
                    _json_dump(expected.metadata),
                    expected.created_at.isoformat(),
                    expected.updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return None
            if atomic_receipt is not None:
                receipt_row = await (
                    await db.execute(
                        "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                        " correlation_id, causation_id, parent_run_id, agent_id,"
                        " idempotency_key, side_effect_key, status, payload_json, created_at"
                        " FROM runtime_receipts WHERE receipt_id = ?",
                        (atomic_receipt.receipt_id,),
                    )
                ).fetchone()
                if receipt_row is not None:
                    if _row_to_runtime_receipt(receipt_row) != atomic_receipt:
                        raise ValueError("atomic session receipt identity conflicts")
                else:
                    await db.execute(
                        "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id,"
                        " task_id, trace_id, correlation_id, causation_id, parent_run_id,"
                        " agent_id, idempotency_key, side_effect_key, status, payload_json,"
                        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            atomic_receipt.receipt_id,
                            atomic_receipt.receipt_type,
                            atomic_receipt.run_id,
                            atomic_receipt.task_id,
                            atomic_receipt.trace_id,
                            atomic_receipt.correlation_id,
                            atomic_receipt.causation_id,
                            atomic_receipt.parent_run_id,
                            atomic_receipt.agent_id,
                            atomic_receipt.idempotency_key,
                            atomic_receipt.side_effect_key,
                            atomic_receipt.status,
                            _json_dump(atomic_receipt.payload),
                            atomic_receipt.created_at.isoformat(),
                        ),
                    )
            row = await (
                await db.execute(
                    "SELECT session_id, operator_id, status, current_task_id,"
                    " active_bundle_id, metadata_json, created_at, updated_at"
                    " FROM sessions WHERE session_id = ?",
                    (expected.session_id,),
                )
            ).fetchone()
            await db.commit()
        assert row is not None
        return _row_to_session(row)

    def _run_sync_transaction(self, operation: Any, *, immediate: bool = False) -> Any:
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            if immediate:
                db.execute("BEGIN IMMEDIATE")
            return operation(db)

    async def record_session_event(self, event: SessionEventRecord, receipt: RuntimeReceipt | None = None) -> SessionEventRecord:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            await self._record_session_event_and_optional_receipt_async_db(db, event, receipt)
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

    async def _record_execution_identity_in_transaction(
        self,
        db: aiosqlite.Connection,
        identity: ExecutionIdentity,
        *,
        source: str,
    ) -> ExecutionIdentity:
        """Validate and persist identity inside its async owner transaction."""
        identity.require_for_dispatch()
        row = await (
            await db.execute(
                self._identity_select_sql() + " WHERE run_id = ?",
                (identity.run_id,),
            )
        ).fetchone()
        existing = _row_to_execution_identity(row) if row is not None else None
        identity = _merge_execution_identity(existing, identity, None)
        await db.execute(
            self._identity_upsert_sql(),
            self._identity_params(
                identity,
                source=source,
                now=_utc_now(),
            ),
        )
        return identity

    async def record_task_claim(self, claim: TaskClaim) -> TaskClaim:
        await self.init_db()
        corr = get_correlation()
        if corr.cell_id:
            claim.metadata.setdefault("cell_id", corr.cell_id)
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            await db.execute("BEGIN IMMEDIATE")
            db.row_factory = aiosqlite.Row
            existing_row = await (
                await db.execute(
                    "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                    " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                    " metadata_json FROM task_claims WHERE claim_id = ?",
                    (claim.claim_id,),
                )
            ).fetchone()
            existing = _row_to_claim(existing_row) if existing_row is not None else None
            claim, bound_identity = _normalize_claim_replay(existing, claim)
            if bound_identity is not None:
                bound_identity = await self._record_execution_identity_in_transaction(
                    db,
                    bound_identity,
                    source="runtime_state.record_task_claim",
                )
                claim = replace(
                    claim,
                    metadata=_metadata_with_identity(claim.metadata, bound_identity),
                )
            existing_terminal_replay = bool(
                existing is not None and _absorbing_claim_replay(existing, claim)
            )
            metadata = claim.metadata
            if existing_terminal_replay:
                assert existing is not None
                await db.commit()
                return existing
            heartbeat_at = _later_timestamp(
                existing.heartbeat_at if existing is not None else None,
                claim.heartbeat_at,
            )
            stale_after = claim.stale_after
            trace_id = _trace_from_metadata(metadata) or corr.trace_id
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
                    heartbeat_at.isoformat() if heartbeat_at else None,
                    stale_after.isoformat() if stale_after else None,
                    claim.recovered_at.isoformat() if claim.recovered_at else None,
                    int(claim.retry_count),
                    _json_dump(metadata),
                    trace_id,
                ),
            )
            loaded_row = await (
                await db.execute(
                    "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                    " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                    " metadata_json FROM task_claims WHERE claim_id = ?",
                    (claim.claim_id,),
                )
            ).fetchone()
            await db.commit()
        assert loaded_row is not None
        return _row_to_claim(loaded_row)

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
        for _attempt in range(3):
            existing = await self.get_task_claim(claim_id)
            if existing is None:
                raise KeyError(f"claim {claim_id} not found")
            if (
                existing.status.lower() not in _RENEWABLE_TASK_CLAIM_STATUSES
                or status.lower() not in _RENEWABLE_TASK_CLAIM_STATUSES
            ):
                raise ValueError("acknowledgement cannot update a terminal claim")
            merged_metadata = _preserve_claim_evidence_metadata(
                existing.metadata,
                {**existing.metadata, **(metadata or {})},
                claim_id=claim_id,
            )
            normalized, _identity = _normalize_claim_replay(
                existing,
                replace(existing, status=status, metadata=merged_metadata),
            )
            merged_metadata = normalized.metadata
            acked_at = acknowledged_at or _utc_now()
            heartbeat_at = existing.heartbeat_at or acked_at
            async with aiosqlite.connect(self.db_path) as db:
                await _apply_connection_pragmas_async(db)
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "UPDATE task_claims SET status = ?, acked_at = ?, heartbeat_at = ?,"
                    " metadata_json = ?, trace_id = ?"
                    " WHERE claim_id = ? AND task_id = ? AND agent_id = ?"
                    " AND session_id = ? AND status = ? AND claimed_at = ?"
                    " AND acked_at IS ? AND heartbeat_at IS ? AND stale_after IS ?"
                    " AND recovered_at IS ? AND retry_count = ? AND metadata_json = ?",
                    (
                        status,
                        acked_at.isoformat(),
                        heartbeat_at.isoformat(),
                        _json_dump(merged_metadata),
                        _trace_from_metadata(merged_metadata),
                        existing.claim_id,
                        existing.task_id,
                        existing.agent_id,
                        existing.session_id,
                        existing.status,
                        existing.claimed_at.isoformat(),
                        existing.acked_at.isoformat() if existing.acked_at else None,
                        (
                            existing.heartbeat_at.isoformat()
                            if existing.heartbeat_at
                            else None
                        ),
                        existing.stale_after.isoformat() if existing.stale_after else None,
                        (
                            existing.recovered_at.isoformat()
                            if existing.recovered_at
                            else None
                        ),
                        int(existing.retry_count),
                        _json_dump(existing.metadata),
                    ),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    continue
                row = await (
                    await db.execute(
                        "SELECT claim_id, task_id, session_id, agent_id, status,"
                        " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
                        " retry_count, metadata_json FROM task_claims WHERE claim_id = ?",
                        (claim_id,),
                    )
                ).fetchone()
                await db.commit()
            assert row is not None
            return _row_to_claim(row)
        raise RuntimeError("task claim acknowledgement lost its fence repeatedly")

    async def heartbeat_task_claim(
        self,
        claim_id: str,
        *,
        heartbeat_at: datetime | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskClaim:
        for _attempt in range(3):
            existing = await self.get_task_claim(claim_id)
            if existing is None:
                raise KeyError(f"claim {claim_id} not found")
            target_status = status or existing.status
            if (
                existing.status.lower() not in _RENEWABLE_TASK_CLAIM_STATUSES
                or target_status.lower() not in _RENEWABLE_TASK_CLAIM_STATUSES
            ):
                raise ValueError("heartbeat cannot update a terminal claim")
            beat_at = heartbeat_at or _utc_now()
            if beat_at.tzinfo is None:
                raise ValueError("heartbeat_at must be timezone-aware")
            if existing.heartbeat_at is not None and beat_at <= existing.heartbeat_at:
                raise ValueError("heartbeat_at must advance monotonically")
            merged_metadata = {**existing.metadata, **(metadata or {})}
            if "mission_control_evidence" in existing.metadata:
                merged_metadata["mission_control_evidence"] = existing.metadata[
                    "mission_control_evidence"
                ]
            normalized, _identity = _normalize_claim_replay(
                existing,
                replace(
                    existing,
                    status=target_status,
                    heartbeat_at=beat_at,
                    metadata=merged_metadata,
                ),
            )
            merged_metadata = normalized.metadata
            async with aiosqlite.connect(self.db_path) as db:
                await _apply_connection_pragmas_async(db)
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "UPDATE task_claims SET status = ?, heartbeat_at = ?,"
                    " metadata_json = ?, trace_id = ?"
                    " WHERE claim_id = ? AND task_id = ? AND agent_id = ?"
                    " AND session_id = ? AND status = ? AND claimed_at = ?"
                    " AND acked_at IS ? AND heartbeat_at IS ? AND stale_after IS ?"
                    " AND recovered_at IS ? AND retry_count = ? AND metadata_json = ?",
                    (
                        target_status,
                        beat_at.isoformat(),
                        _json_dump(merged_metadata),
                        _trace_from_metadata(merged_metadata),
                        existing.claim_id,
                        existing.task_id,
                        existing.agent_id,
                        existing.session_id,
                        existing.status,
                        existing.claimed_at.isoformat(),
                        existing.acked_at.isoformat() if existing.acked_at else None,
                        (
                            existing.heartbeat_at.isoformat()
                            if existing.heartbeat_at
                            else None
                        ),
                        existing.stale_after.isoformat() if existing.stale_after else None,
                        (
                            existing.recovered_at.isoformat()
                            if existing.recovered_at
                            else None
                        ),
                        int(existing.retry_count),
                        _json_dump(existing.metadata),
                    ),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    continue
                row = await (
                    await db.execute(
                        "SELECT claim_id, task_id, session_id, agent_id, status,"
                        " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
                        " retry_count, metadata_json FROM task_claims WHERE claim_id = ?",
                        (claim_id,),
                    )
                ).fetchone()
                await db.commit()
            assert row is not None
            return _row_to_claim(row)
        raise RuntimeError("task claim heartbeat lost its fence repeatedly")

    async def compare_and_swap_task_claim(
        self,
        expected: TaskClaim,
        replacement: TaskClaim,
        *,
        require_unexpired_at: datetime,
        require_open_run_id: str = "",
        atomic_receipt: RuntimeReceipt | None = None,
    ) -> TaskClaim | None:
        """Atomically replace one exact, still-unexpired claim generation.

        ``None`` means the fence was lost.  Identity, status, timestamps, retry
        generation, and metadata are all compared so a concurrent heartbeat or
        evidence delta cannot be overwritten by a read-then-write renewal.  An
        optional owner run fence makes a terminal run fail in the same update.
        """
        if require_unexpired_at.tzinfo is None:
            raise ValueError("require_unexpired_at must be timezone-aware")
        if require_open_run_id != str(require_open_run_id or "").strip():
            raise ValueError("require_open_run_id must be canonical")
        replacement, _identity = _normalize_claim_replay(expected, replacement)
        if atomic_receipt is not None:
            if replacement.heartbeat_at is None:
                raise ValueError("atomic receipt requires a replacement heartbeat")
            evidence = replacement.metadata.get(_CLAIM_EVIDENCE_METADATA_KEY)
            if not isinstance(evidence, dict):
                raise ValueError("atomic receipt requires reserved claim evidence")
            payload = atomic_receipt.payload
            expected_carrier = (
                "mission_evidence_delta",
                "recorded",
                require_open_run_id,
                expected.task_id,
                expected.agent_id,
                replacement.heartbeat_at,
            )
            observed_carrier = (
                atomic_receipt.receipt_type,
                atomic_receipt.status,
                atomic_receipt.run_id,
                atomic_receipt.task_id,
                atomic_receipt.agent_id,
                atomic_receipt.created_at,
            )
            delta_id = payload.get("delta_id")
            expected_receipt_id = (
                "evidence_delta_receipt_"
                + hashlib.sha256(str(delta_id).encode()).hexdigest()[:24]
            )
            digest_payload = dict(payload)
            supplied_digest = digest_payload.pop("evidence_digest", "")
            encoded_payload = json.dumps(
                digest_payload,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
                default=str,
            ).encode()
            expected_digest = "sha256:" + hashlib.sha256(encoded_payload).hexdigest()
            if observed_carrier != expected_carrier:
                raise ValueError("atomic receipt carrier conflicts with claim renewal")
            if (
                not require_open_run_id
                or atomic_receipt.receipt_id != expected_receipt_id
                or payload.get("mission_id") != expected.metadata.get("mission_id")
                or payload.get("task_id") != expected.task_id
                or payload.get("run_id") != require_open_run_id
                or payload.get("claim_id") != expected.claim_id
                or payload.get("agent_id") != expected.agent_id
                or payload.get("delta_id") != evidence.get("last_delta_id")
                or payload.get("sequence") != evidence.get("last_sequence")
                or payload.get("observed_at")
                != replacement.heartbeat_at.isoformat()
                or payload.get("artifact_ids") != evidence.get("artifact_ids")
                or payload.get("receipt_ids") != evidence.get("receipt_ids")
                or supplied_digest != expected_digest
                or atomic_receipt.side_effect_key
                != f"mission_evidence:{payload.get('delta_id')}"
            ):
                raise ValueError("atomic receipt payload conflicts with claim evidence")
        immutable_fields = (
            "claim_id",
            "task_id",
            "agent_id",
            "session_id",
            "status",
            "claimed_at",
            "acked_at",
            "recovered_at",
            "retry_count",
        )
        if any(
            getattr(expected, field_name) != getattr(replacement, field_name)
            for field_name in immutable_fields
        ):
            raise ValueError("claim CAS replacement changes its fenced identity")
        status = expected.status.lower()
        if status not in _RENEWABLE_TASK_CLAIM_STATUSES:
            raise ValueError("claim CAS cannot renew a terminal claim")
        if expected.stale_after is None or replacement.stale_after is None:
            raise ValueError("claim CAS requires an explicit expiry fence")
        if expected.stale_after.tzinfo is None:
            raise ValueError("claim CAS expected expiry must be timezone-aware")
        if expected.heartbeat_at is not None and expected.heartbeat_at.tzinfo is None:
            raise ValueError("claim CAS expected heartbeat must be timezone-aware")
        if replacement.heartbeat_at is None:
            raise ValueError("claim CAS replacement requires a heartbeat")
        if replacement.heartbeat_at.tzinfo is None or replacement.stale_after.tzinfo is None:
            raise ValueError("claim CAS timestamps must be timezone-aware")
        if replacement.stale_after <= replacement.heartbeat_at:
            raise ValueError("claim CAS expiry must follow its heartbeat")
        if expected.heartbeat_at is not None and replacement.heartbeat_at <= expected.heartbeat_at:
            raise ValueError("claim CAS heartbeat must advance monotonically")

        await self.init_db()
        query = (
            "UPDATE task_claims SET heartbeat_at = ?, stale_after = ?,"
            " metadata_json = ?, trace_id = ?"
            " WHERE claim_id = ? AND task_id = ? AND agent_id = ?"
            " AND session_id = ? AND status = ? AND claimed_at = ?"
            " AND acked_at IS ? AND heartbeat_at IS ? AND stale_after = ?"
            " AND recovered_at IS ? AND retry_count = ? AND metadata_json = ?"
            " AND julianday(stale_after) > julianday(?)"
        )
        params: list[Any] = [
            replacement.heartbeat_at.isoformat(),
            replacement.stale_after.isoformat(),
            _json_dump(replacement.metadata),
            _trace_from_metadata(replacement.metadata),
            expected.claim_id,
            expected.task_id,
            expected.agent_id,
            expected.session_id,
            expected.status,
            expected.claimed_at.isoformat(),
            expected.acked_at.isoformat() if expected.acked_at else None,
            expected.heartbeat_at.isoformat() if expected.heartbeat_at else None,
            expected.stale_after.isoformat(),
            expected.recovered_at.isoformat() if expected.recovered_at else None,
            int(expected.retry_count),
            _json_dump(expected.metadata),
            require_unexpired_at.isoformat(),
        ]
        if require_open_run_id:
            query += (
                " AND EXISTS (SELECT 1 FROM delegation_runs"
                " WHERE run_id = ? AND claim_id = task_claims.claim_id"
                " AND task_id = task_claims.task_id"
                " AND status IN ('claimed', 'running'))"
            )
            params.append(require_open_run_id)
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            if cursor.rowcount != 1:
                await db.rollback()
                return None
            if atomic_receipt is not None:
                identity_row = await (
                    await db.execute(
                        self._identity_select_sql() + " WHERE run_id = ?",
                        (require_open_run_id,),
                    )
                ).fetchone()
                identity = (
                    _row_to_execution_identity(identity_row)
                    if identity_row is not None
                    else None
                )
                if identity is None or (
                    identity.task_id != expected.task_id
                    or identity.claim_id != expected.claim_id
                    or identity.agent_id != expected.agent_id
                    or identity.session_id != expected.session_id
                    or atomic_receipt.trace_id != identity.trace_id
                    or atomic_receipt.correlation_id != identity.correlation_id
                    or atomic_receipt.causation_id != identity.causation_id
                    or atomic_receipt.parent_run_id != identity.parent_run_id
                    or atomic_receipt.idempotency_key != identity.idempotency_key
                ):
                    raise ValueError("atomic receipt identity conflicts with owner run")
                receipt_row = await (
                    await db.execute(
                        "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                        " correlation_id, causation_id, parent_run_id, agent_id,"
                        " idempotency_key, side_effect_key, status, payload_json, created_at"
                        " FROM runtime_receipts WHERE receipt_id = ?",
                        (atomic_receipt.receipt_id,),
                    )
                ).fetchone()
                if receipt_row is not None:
                    if _row_to_runtime_receipt(receipt_row) != atomic_receipt:
                        raise ValueError("atomic receipt identity conflicts")
                else:
                    await db.execute(
                        "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id,"
                        " task_id, trace_id, correlation_id, causation_id, parent_run_id,"
                        " agent_id, idempotency_key, side_effect_key, status, payload_json,"
                        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            atomic_receipt.receipt_id,
                            atomic_receipt.receipt_type,
                            atomic_receipt.run_id,
                            atomic_receipt.task_id,
                            atomic_receipt.trace_id,
                            atomic_receipt.correlation_id,
                            atomic_receipt.causation_id,
                            atomic_receipt.parent_run_id,
                            atomic_receipt.agent_id,
                            atomic_receipt.idempotency_key,
                            atomic_receipt.side_effect_key,
                            atomic_receipt.status,
                            _json_dump(atomic_receipt.payload),
                            atomic_receipt.created_at.isoformat(),
                        ),
                    )
            row = await (
                await db.execute(
                    "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                    " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                    " metadata_json FROM task_claims WHERE claim_id = ?",
                    (expected.claim_id,),
                )
            ).fetchone()
            await db.commit()
        assert row is not None
        return _row_to_claim(row)

    async def record_delegation_run(self, run: DelegationRun) -> DelegationRun:
        await self.init_db()
        corr = get_correlation()
        trace_id = _trace_from_metadata(run.metadata) or corr.trace_id
        if corr.cell_id:
            run.metadata.setdefault("cell_id", corr.cell_id)
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            existing_row = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                    " assigned_by, assigned_to, requested_output_json,"
                    " current_artifact_id, status, started_at, completed_at,"
                    " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                    (run.run_id,),
                )
            ).fetchone()
            existing = _row_to_run(existing_row) if existing_row is not None else None
            run, bound_identity = _normalize_run_replay(existing, run)
            if bound_identity is not None:
                bound_identity = await self._record_execution_identity_in_transaction(
                    db,
                    bound_identity,
                    source="runtime_state.record_delegation_run",
                )
                run = replace(
                    run,
                    parent_run_id=bound_identity.parent_run_id,
                    metadata=_metadata_with_identity(run.metadata, bound_identity),
                )
            if existing is not None and (
                existing == run or _absorbing_run_replay(existing, run)
            ):
                await db.commit()
                return existing
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
            if (
                run.status in {"completed", "failed"}
                and "task_board_projection" in run.metadata
            ):
                # The projection authority is prepared in the SAME SQLite
                # transaction that terminalizes the run.  A crash can expose
                # neither a terminal row without its outbox proof nor a proof
                # for a nonterminal row.
                from dharma_swarm.graph.reconcile_board import (
                    prepare_task_board_projection_snapshot,
                )

                if not await prepare_task_board_projection_snapshot(
                    db, run_id=run.run_id
                ):
                    raise RuntimeError(
                        "terminal delegation run projection prepare failed"
                    )
            await db.commit()
        loaded = await self.get_delegation_run(run.run_id)
        assert loaded is not None
        return loaded

    async def finalize_delegation_run_evidence_exact(
        self,
        *,
        expected_running: DelegationRun,
        completed: DelegationRun,
        receipts: tuple[RuntimeReceipt, ...],
        artifacts: tuple[ArtifactRecord, ...] = (),
    ) -> DelegationRun:
        """Atomically seal immutable evidence and one exact running run.

        Exact existing carriers are replay-safe.  Conflicting, failed, or otherwise
        foreign lifecycle rows fail closed; this method never resurrects a terminal
        run.
        """
        if (
            expected_running.status.lower() != "running"
            or expected_running.completed_at is not None
            or completed.status.lower() != "completed"
            or completed.completed_at is None
            or completed.failure_code
            or replace(
                completed,
                status=expected_running.status,
                completed_at=expected_running.completed_at,
                failure_code=expected_running.failure_code,
            )
            != expected_running
            or completed.completed_at < completed.started_at
            or not receipts
            or len({item.receipt_id for item in receipts}) != len(receipts)
            or len({item.artifact_id for item in artifacts}) != len(artifacts)
        ):
            raise ValueError("delegation evidence finalization coordinates are invalid")
        for receipt in receipts:
            _validate_campaign_cycle_receipt(receipt)
            if (
                receipt.run_id != completed.run_id
                or receipt.task_id != completed.task_id
                or receipt.created_at > completed.completed_at
            ):
                raise ValueError("runtime receipt is foreign to delegation finalization")
        for artifact in artifacts:
            if (
                artifact.run_id != completed.run_id
                or artifact.task_id != completed.task_id
                or artifact.created_at > completed.completed_at
            ):
                raise ValueError("artifact is foreign to delegation finalization")

        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                        " assigned_by, assigned_to, requested_output_json,"
                        " current_artifact_id, status, started_at, completed_at,"
                        " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                        (completed.run_id,),
                    )
                ).fetchone()
                current = _row_to_run(row) if row is not None else None
                if current != expected_running and current != completed:
                    raise ValueError("delegation run does not match exact finalization state")

                identity_row = await (
                    await db.execute(
                        self._identity_select_sql() + " WHERE run_id = ?",
                        (completed.run_id,),
                    )
                ).fetchone()
                identity = (
                    _row_to_execution_identity(identity_row)
                    if identity_row is not None
                    else None
                )
                if identity is None or (
                    identity.task_id != completed.task_id
                    or identity.claim_id != completed.claim_id
                    or identity.agent_id != completed.assigned_to
                    or identity.session_id != completed.session_id
                    or identity.parent_run_id != completed.parent_run_id
                ):
                    raise ValueError(
                        "delegation finalization execution identity conflicts"
                    )

                for receipt in receipts:
                    if (
                        receipt.trace_id != identity.trace_id
                        or receipt.correlation_id != identity.correlation_id
                        or receipt.causation_id != identity.causation_id
                        or receipt.parent_run_id != identity.parent_run_id
                        or receipt.agent_id != identity.agent_id
                        or receipt.idempotency_key != identity.idempotency_key
                    ):
                        raise ValueError(
                            "delegation finalization receipt carrier is foreign"
                        )
                for artifact in artifacts:
                    if (
                        artifact.trace_id != identity.trace_id
                        or artifact.session_id != identity.session_id
                    ):
                        raise ValueError(
                            "delegation finalization artifact carrier is foreign"
                        )

                for receipt in receipts:
                    row = await (
                        await db.execute(
                            "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                            " correlation_id, causation_id, parent_run_id, agent_id,"
                            " idempotency_key, side_effect_key, status, payload_json,"
                            " created_at FROM runtime_receipts WHERE receipt_id = ?",
                            (receipt.receipt_id,),
                        )
                    ).fetchone()
                    if row is not None:
                        if _row_to_runtime_receipt(row) != receipt:
                            raise ValueError("runtime receipt finalization evidence conflicts")
                        continue
                    await db.execute(
                        "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id,"
                        " task_id, trace_id, correlation_id, causation_id, parent_run_id,"
                        " agent_id, idempotency_key, side_effect_key, status, payload_json,"
                        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

                for artifact in artifacts:
                    row = await (
                        await db.execute(
                            "SELECT artifact_id, session_id, task_id, run_id, trace_id,"
                            " artifact_kind, manifest_path, payload_path, checksum,"
                            " parent_artifact_id, promotion_state, created_at, metadata_json"
                            " FROM artifact_records WHERE artifact_id = ?",
                            (artifact.artifact_id,),
                        )
                    ).fetchone()
                    if row is not None:
                        if _row_to_artifact(row) != artifact:
                            raise ValueError("artifact finalization evidence conflicts")
                        continue
                    await db.execute(
                        "INSERT INTO artifact_records (artifact_id, session_id, task_id,"
                        " run_id, trace_id, artifact_kind, manifest_path, payload_path,"
                        " checksum, parent_artifact_id, promotion_state, created_at,"
                        " metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

                if current == expected_running:
                    cursor = await db.execute(
                        "UPDATE delegation_runs SET status = ?, completed_at = ?,"
                        " failure_code = ? WHERE run_id = ? AND status = ?"
                        " AND completed_at IS NULL",
                        (
                            completed.status,
                            completed.completed_at.isoformat(),
                            completed.failure_code,
                            completed.run_id,
                            expected_running.status,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("delegation run finalization CAS lost")
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
        return completed

    async def compare_and_swap_delegation_run_exact(
        self,
        expected: DelegationRun,
        replacement: DelegationRun,
    ) -> bool:
        """Replace only lifecycle fields of one byte-equivalent delegation row."""
        if (
            expected.run_id != replacement.run_id
            or replace(
                replacement,
                status=expected.status,
                completed_at=expected.completed_at,
                failure_code=expected.failure_code,
            )
            != expected
        ):
            raise ValueError("delegation run CAS changes immutable coordinates")
        expected_terminal = _is_absorbing_runtime_row(
            expected.status, expected.metadata
        )
        replacement_terminal = _is_absorbing_runtime_row(
            replacement.status, replacement.metadata
        )
        if expected_terminal and replacement != expected:
            raise ValueError("terminal delegation run cannot be mutated")
        if not expected_terminal and not replacement_terminal:
            raise ValueError("delegation run CAS requires a terminal replacement")
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                        " assigned_by, assigned_to, requested_output_json,"
                        " current_artifact_id, status, started_at, completed_at,"
                        " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                        (expected.run_id,),
                    )
                ).fetchone()
                if row is None or _row_to_run(row) != expected:
                    await db.commit()
                    return False
                if replacement == expected:
                    await db.commit()
                    return True
                cursor = await db.execute(
                    "UPDATE delegation_runs SET status = ?, completed_at = ?,"
                    " failure_code = ? WHERE run_id = ?",
                    (
                        replacement.status,
                        replacement.completed_at.isoformat()
                        if replacement.completed_at
                        else None,
                        replacement.failure_code,
                        replacement.run_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("delegation run CAS lost")
                await db.commit()
                return True
            except BaseException:
                await db.rollback()
                raise

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

    async def inspect_campaign_dispatch_indeterminate(
        self,
        *,
        mission_id: str,
        task_id: str,
        run_id: str,
        claim_id: str,
        agent_id: str,
        idempotency_key: str,
        attempt_generation: int,
    ) -> str:
        """Classify one attempt without changing its durable runtime rows."""
        return await self._campaign_dispatch_indeterminate(
            mission_id=mission_id,
            task_id=task_id,
            run_id=run_id,
            claim_id=claim_id,
            agent_id=agent_id,
            idempotency_key=idempotency_key,
            attempt_generation=attempt_generation,
            apply=False,
        )

    async def resolve_campaign_dispatch_indeterminate(
        self,
        *,
        mission_id: str,
        task_id: str,
        run_id: str,
        claim_id: str,
        agent_id: str,
        idempotency_key: str,
        attempt_generation: int,
    ) -> str:
        """Atomically terminalize one exactly classified pre-provider attempt."""
        return await self._campaign_dispatch_indeterminate(
            mission_id=mission_id,
            task_id=task_id,
            run_id=run_id,
            claim_id=claim_id,
            agent_id=agent_id,
            idempotency_key=idempotency_key,
            attempt_generation=attempt_generation,
            apply=True,
        )

    async def _campaign_dispatch_indeterminate(
        self,
        *,
        mission_id: str,
        task_id: str,
        run_id: str,
        claim_id: str,
        agent_id: str,
        idempotency_key: str,
        attempt_generation: int,
        apply: bool,
    ) -> str:
        """Terminalize only exact pre-provider runtime evidence for one attempt.

        Returns ``absent``, ``terminalized``, ``already_terminal``,
        ``effect_observed``, or ``conflict``.  The transaction fails closed on
        any provider/invoker idempotency or receipt evidence.
        """
        identifiers = (mission_id, task_id, run_id, claim_id, agent_id, idempotency_key)
        if any(not value or value != value.strip() for value in identifiers):
            raise ValueError("campaign indeterminate identity is invalid")
        if (
            isinstance(attempt_generation, bool)
            or not isinstance(attempt_generation, int)
            or attempt_generation < 0
        ):
            raise ValueError("campaign indeterminate generation is invalid")
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            identity_row = await (
                await db.execute(
                    self._identity_select_sql() + " WHERE run_id = ?", (run_id,)
                )
            ).fetchone()
            run_row = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                    " assigned_by, assigned_to, requested_output_json,"
                    " current_artifact_id, status, started_at, completed_at,"
                    " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                    (run_id,),
                )
            ).fetchone()
            claim_row = await (
                await db.execute(
                    "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                    " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                    " metadata_json FROM task_claims WHERE claim_id = ?", (claim_id,),
                )
            ).fetchone()
            receipt_rows = await (
                await db.execute(
                    "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                    " correlation_id, causation_id, parent_run_id, agent_id,"
                    " idempotency_key, side_effect_key, status, payload_json, created_at"
                    " FROM runtime_receipts WHERE run_id = ?", (run_id,),
                )
            ).fetchall()
            idempotency_rows = await (
                await db.execute(
                    "SELECT idempotency_key, side_effect_key, run_id, task_id, trace_id,"
                    " correlation_id, status, result_receipt_id, metadata_json,"
                    " created_at, updated_at FROM idempotency_records WHERE run_id = ?",
                    (run_id,),
                )
            ).fetchall()
            identity = (
                _row_to_execution_identity(identity_row)
                if identity_row is not None else None
            )
            run = _row_to_run(run_row) if run_row is not None else None
            claim = _row_to_claim(claim_row) if claim_row is not None else None
            if identity is None and run is None and claim is None and not receipt_rows:
                await db.commit()
                return "absent"
            if identity is None or (
                identity.task_id != task_id
                or identity.run_id != run_id
                or identity.claim_id != claim_id
                or identity.agent_id != agent_id
                or identity.idempotency_key != idempotency_key
                or identity.metadata.get("attempt_generation") != attempt_generation
            ):
                await db.rollback()
                return "conflict"
            receipt_id = "rr_" + hashlib.sha256(
                f"campaign_dispatch_indeterminate:{run_id}".encode()
            ).hexdigest()[:32]
            payload = _campaign_indeterminate_payload(
                mission_id=mission_id,
                task_id=task_id,
                run_id=run_id,
                claim_id=claim_id,
                agent_id=agent_id,
                attempt_generation=attempt_generation,
            )
            receipts = [_row_to_runtime_receipt(row) for row in receipt_rows]
            if any(
                not _pre_effect_receipt_is_exact(
                    receipt,
                    identity,
                    mission_id=mission_id,
                    claim_id=claim_id,
                    attempt_generation=attempt_generation,
                    indeterminate_receipt_id=receipt_id,
                    indeterminate_payload=payload,
                )
                for receipt in receipts
            ):
                await db.rollback()
                return "effect_observed"
            idempotencies = [
                _row_to_idempotency_record(row) for row in idempotency_rows
            ]
            for record in idempotencies:
                prefix = (
                    "task_claim"
                    if record.side_effect_key.startswith("task_claim:")
                    else "delegation_run"
                    if record.side_effect_key.startswith("delegation_run:")
                    else ""
                )
                status = record.side_effect_key.rsplit(":", 1)[-1]
                target = claim_id if prefix == "task_claim" else run_id
                expected_receipt = (
                    f"rr_{run_id}_{status}_{'claim' if prefix == 'task_claim' else 'run'}"
                )
                if (
                    prefix not in {"task_claim", "delegation_run"}
                    or status not in {"claimed", "running"}
                    or record.side_effect_key != f"{prefix}:{target}:{status}"
                    or record.idempotency_key != idempotency_key
                    or record.run_id != run_id
                    or record.task_id != task_id
                    or record.trace_id != identity.trace_id
                    or record.correlation_id != identity.correlation_id
                    or record.status not in {"started", "completed"}
                    or (
                        record.result_receipt_id
                        not in {"", expected_receipt}
                    )
                    or not _pre_effect_payload_is_exact(
                        record.metadata,
                        mission_id=mission_id,
                        attempt_generation=attempt_generation,
                    )
                ):
                    await db.rollback()
                    return "effect_observed"
            if run is not None and (
                run.task_id != task_id
                or run.claim_id != claim_id
                or run.assigned_to != agent_id
                or run.assigned_by != "orchestrator"
                or run.metadata.get("mission_id") != mission_id
                or run.metadata.get("attempt_generation") != attempt_generation
            ):
                await db.rollback()
                return "conflict"
            if claim is not None and (
                claim.task_id != task_id
                or claim.agent_id != agent_id
                or claim.session_id != identity.session_id
                or claim.metadata.get("mission_id") != mission_id
                or claim.metadata.get("attempt_generation") != attempt_generation
            ):
                await db.rollback()
                return "conflict"
            if run is not None and run.status.lower() not in {
                "claimed", "running", "failed"
            }:
                await db.rollback()
                return "effect_observed"
            if claim is not None and claim.status.lower() not in {
                "claimed", "running", "failed"
            }:
                await db.rollback()
                return "effect_observed"
            if (
                run is not None and run.status.lower() == "failed"
                and run.failure_code != "dispatch_indeterminate"
            ):
                await db.rollback()
                return "effect_observed"
            already = bool(
                (run is None or run.status.lower() == "failed")
                and (claim is None or claim.status.lower() == "failed")
            )
            now = _utc_now().isoformat()
            terminal = {
                "attempt_generation": attempt_generation,
                "failure_code": "dispatch_indeterminate",
                "provider_task_scheduled": False,
            }
            if run is not None and run.status.lower() == "failed" and any(
                run.metadata.get(key) != value for key, value in terminal.items()
            ):
                await db.rollback()
                return "effect_observed"
            if claim is not None and claim.status.lower() == "failed" and any(
                claim.metadata.get(key) != value for key, value in terminal.items()
            ):
                await db.rollback()
                return "effect_observed"
            if not apply:
                await db.rollback()
                return "already_terminal" if already else "recoverable"
            if run is not None and run.status.lower() != "failed":
                cursor = await db.execute(
                    "UPDATE delegation_runs SET status = 'failed', completed_at = ?,"
                    " failure_code = 'dispatch_indeterminate', metadata_json = ?"
                    " WHERE run_id = ? AND status = ? AND metadata_json = ?",
                    (now, _json_dump({**run.metadata, **terminal}), run_id,
                     run.status, _json_dump(run.metadata)),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    return "conflict"
            if claim is not None and claim.status.lower() != "failed":
                cursor = await db.execute(
                    "UPDATE task_claims SET status = 'failed', heartbeat_at = ?,"
                    " recovered_at = ?, metadata_json = ? WHERE claim_id = ?"
                    " AND status = ? AND metadata_json = ?",
                    (now, now, _json_dump({**claim.metadata, **terminal}), claim_id,
                     claim.status, _json_dump(claim.metadata)),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    return "conflict"
            existing_receipt = next(
                (row for row in receipt_rows if row["receipt_id"] == receipt_id), None
            )
            if existing_receipt is None:
                await db.execute(
                    "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id,"
                    " task_id, trace_id, correlation_id, causation_id, parent_run_id,"
                    " agent_id, idempotency_key, side_effect_key, status, payload_json,"
                    " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (receipt_id, "mission_dispatch_indeterminate", run_id, task_id,
                     identity.trace_id, identity.correlation_id, identity.causation_id,
                     identity.parent_run_id, agent_id, idempotency_key,
                     f"campaign_dispatch_indeterminate:{run_id}", "failed",
                     _json_dump(payload), now),
                )
            elif not _pre_effect_receipt_is_exact(
                _row_to_runtime_receipt(existing_receipt),
                identity,
                mission_id=mission_id,
                claim_id=claim_id,
                attempt_generation=attempt_generation,
                indeterminate_receipt_id=receipt_id,
                indeterminate_payload=payload,
            ):
                await db.rollback()
                return "conflict"
            await db.commit()
            return "already_terminal" if already else "terminalized"

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

    def _record_execution_identity_in_transaction_sync(
        self,
        db: sqlite3.Connection,
        identity: ExecutionIdentity,
        *,
        source: str,
    ) -> ExecutionIdentity:
        """Validate and persist identity inside its owner-row transaction."""
        identity.require_for_dispatch()
        row = db.execute(
            self._identity_select_sql() + " WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()
        existing = _row_to_execution_identity(row) if row is not None else None
        identity = _merge_execution_identity(existing, identity, None)
        db.execute(
            self._identity_upsert_sql(),
            self._identity_params(
                identity,
                source=source,
                now=_utc_now(),
            ),
        )
        return identity

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
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.execute("BEGIN IMMEDIATE")
            db.row_factory = sqlite3.Row
            existing_row = db.execute(
                "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                " metadata_json FROM task_claims WHERE claim_id = ?",
                (claim.claim_id,),
            ).fetchone()
            existing = _row_to_claim(existing_row) if existing_row is not None else None
            claim, bound_identity = _normalize_claim_replay(existing, claim)
            identity = bound_identity or identity
            if identity is not None:
                identity = self._record_execution_identity_in_transaction_sync(
                    db,
                    identity,
                    source="runtime_state.create_task_claim_sync",
                )
                claim = replace(
                    claim,
                    metadata=_metadata_with_identity(claim.metadata, identity),
                )
            existing_terminal_replay = bool(
                existing is not None
                and _absorbing_claim_replay(existing, claim)
            )
            metadata = claim.metadata
            if existing_terminal_replay:
                assert existing is not None
                claim = existing
                metadata = existing.metadata
            heartbeat_at = _later_timestamp(
                existing.heartbeat_at if existing is not None else None,
                claim.heartbeat_at,
            )
            stale_after = claim.stale_after
            trace_id = (
                identity.trace_id
                if identity is not None
                else _trace_from_metadata(metadata)
            )
            if not existing_terminal_replay:
                db.execute(
                    "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id,"
                    " status, claimed_at, acked_at, heartbeat_at, stale_after,"
                    " recovered_at, retry_count, metadata_json, trace_id)"
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
                        heartbeat_at.isoformat() if heartbeat_at else None,
                        stale_after.isoformat() if stale_after else None,
                        claim.recovered_at.isoformat()
                        if claim.recovered_at
                        else None,
                        int(claim.retry_count),
                        _json_dump(metadata),
                        trace_id,
                    ),
                )
            db.commit()
        if identity is not None:
            self.record_receipt_for_identity_sync(
                identity,
                receipt_id=f"rr_{identity.run_id}_{claim.status}_claim",
                receipt_type="task_claim",
                status=claim.status,
                payload={"claim_id": claim.claim_id},
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

    def get_task_claim_snapshot_sync(self, claim_id: str) -> TaskClaim | None:
        """Read a committed claim without schema writes or a writer lock.

        RuntimeLifecycle invokes this synchronous boundary from async execution.
        Schema initialization here could wait on an async writer while blocking
        the event loop that must release it. The runtime database is WAL-backed,
        so a read-only connection can observe the last committed custody carrier
        while a different connection owns the writer lock.
        """
        if not self.db_path.is_file():
            return None
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=1.0) as db:
                db.execute("PRAGMA query_only=ON")
                db.row_factory = sqlite3.Row
                row = db.execute(
                    "SELECT claim_id, task_id, session_id, agent_id, status,"
                    " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
                    " retry_count, metadata_json FROM task_claims WHERE claim_id = ?",
                    (claim_id,),
                ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table: task_claims" in str(exc):
                return None
            raise
        return _row_to_claim(row) if row is not None else None

    def heartbeat_claim_sync(self, claim_id: str) -> TaskClaim | None:
        """Update heartbeat_at timestamp for a claim (sync)."""
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                " metadata_json FROM task_claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            existing = _row_to_claim(row)
            if existing.status.lower() not in _RENEWABLE_TASK_CLAIM_STATUSES:
                db.rollback()
                raise ValueError("heartbeat cannot update a terminal claim")
            now = _utc_now()
            if existing.heartbeat_at is not None and now <= existing.heartbeat_at:
                db.rollback()
                raise ValueError("heartbeat_at must advance monotonically")
            cursor = db.execute(
                "UPDATE task_claims SET heartbeat_at = ? WHERE claim_id = ?"
                " AND status = ? AND metadata_json = ?",
                (
                    now.isoformat(),
                    claim_id,
                    existing.status,
                    _json_dump(existing.metadata),
                ),
            )
            if cursor.rowcount != 1:
                db.rollback()
                raise RuntimeError("claim heartbeat lost its exact fence")
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
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT claim_id, task_id, session_id, agent_id, status, claimed_at,"
                " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                " metadata_json FROM task_claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            existing = _row_to_claim(row)
            merged = _preserve_claim_evidence_metadata(
                existing.metadata,
                {**existing.metadata, **(metadata or {})},
                claim_id=claim_id,
            )
            candidate, _identity = _normalize_claim_replay(
                existing,
                replace(existing, status=status, metadata=merged),
            )
            if _is_absorbing_runtime_row(existing.status, existing.metadata):
                if candidate != existing:
                    db.rollback()
                    raise ValueError("terminal claim replay must be exact")
                db.commit()
                return existing
            if not _is_absorbing_runtime_row(candidate.status, candidate.metadata):
                db.rollback()
                raise ValueError("close_claim_sync requires a terminal status")
            cursor = db.execute(
                "UPDATE task_claims SET status = ?, metadata_json = ?"
                " WHERE claim_id = ? AND status = ? AND metadata_json = ?",
                (
                    candidate.status,
                    _json_dump(candidate.metadata),
                    claim_id,
                    existing.status,
                    _json_dump(existing.metadata),
                ),
            )
            if cursor.rowcount != 1:
                db.rollback()
                raise RuntimeError("claim close lost its exact fence")
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
            if run.parent_run_id != identity.parent_run_id:
                if run.parent_run_id:
                    raise MissingExecutionIdentity(
                        "ExecutionIdentity parent_run_id does not match "
                        "create_delegation_run_sync"
                    )
            run = replace(
                run,
                parent_run_id=identity.parent_run_id,
                metadata=_metadata_with_identity(run.metadata, identity),
            )
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            existing_row = db.execute(
                "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                " assigned_by, assigned_to, requested_output_json,"
                " current_artifact_id, status, started_at, completed_at,"
                " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                (run.run_id,),
            ).fetchone()
            existing = _row_to_run(existing_row) if existing_row is not None else None
            run, bound_identity = _normalize_run_replay(existing, run)
            identity = bound_identity or identity
            if identity is not None:
                identity = self._record_execution_identity_in_transaction_sync(
                    db,
                    identity,
                    source="runtime_state.create_delegation_run_sync",
                )
                run = replace(
                    run,
                    parent_run_id=identity.parent_run_id,
                    metadata=_metadata_with_identity(run.metadata, identity),
                )
            trace_id = (
                identity.trace_id
                if identity is not None
                else _trace_from_metadata(run.metadata)
            )
            if existing is not None and (
                existing == run or _absorbing_run_replay(existing, run)
            ):
                run = existing
            else:
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
            self.record_receipt_for_identity_sync(
                identity,
                receipt_id=f"rr_{identity.run_id}_{run.status}_run",
                receipt_type="delegation_run",
                status=run.status,
                payload={"failure_code": run.failure_code},
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
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                " assigned_by, assigned_to, requested_output_json,"
                " current_artifact_id, status, started_at, completed_at,"
                " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                db.commit()
                return None
            existing = _row_to_run(row)
            merged = {**existing.metadata, **(metadata or {})}
            existing_terminal = _is_absorbing_runtime_row(
                existing.status, existing.metadata
            )
            candidate, _identity = _normalize_run_replay(
                existing,
                replace(
                    existing,
                    status=status,
                    completed_at=(
                        existing.completed_at if existing_terminal else _utc_now()
                    ),
                    failure_code=failure_code,
                    metadata=merged,
                ),
            )
            if existing_terminal:
                if candidate != existing:
                    db.rollback()
                    raise ValueError("terminal delegation run replay must be exact")
                db.commit()
                return existing
            if not _is_absorbing_runtime_row(candidate.status, candidate.metadata):
                db.rollback()
                raise ValueError(
                    "close_delegation_run_sync requires a terminal status"
                )
            cursor = db.execute(
                "UPDATE delegation_runs SET status = ?, completed_at = ?,"
                " failure_code = ?, metadata_json = ? WHERE run_id = ?"
                " AND status = ? AND metadata_json = ?",
                (
                    candidate.status,
                    candidate.completed_at.isoformat(),
                    candidate.failure_code,
                    _json_dump(candidate.metadata),
                    run_id,
                    existing.status,
                    _json_dump(existing.metadata),
                ),
            )
            if cursor.rowcount != 1:
                db.rollback()
                raise RuntimeError("delegation run close lost its exact fence")
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

    async def insert_artifact_exact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        """Insert an immutable artifact carrier or return its exact existing row."""
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT artifact_id, session_id, task_id, run_id, trace_id,"
                    " artifact_kind, manifest_path, payload_path, checksum,"
                    " parent_artifact_id, promotion_state, created_at, metadata_json"
                    " FROM artifact_records WHERE artifact_id = ?",
                    (artifact.artifact_id,),
                )
            ).fetchone()
            if row is not None:
                existing = _row_to_artifact(row)
                if existing != artifact:
                    await db.rollback()
                    raise ValueError("artifact identity already has conflicting evidence")
                await db.commit()
                return existing
            await db.execute(
                "INSERT INTO artifact_records (artifact_id, session_id, task_id, run_id,"
                " trace_id, artifact_kind, manifest_path, payload_path, checksum,"
                " parent_artifact_id, promotion_state, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        return artifact

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

    @staticmethod
    def _identity_select_sql() -> str:
        return (
            "SELECT run_id, trace_id, correlation_id, task_id, claim_id,"
            " idempotency_key, causation_id, parent_run_id, agent_id,"
            " session_id, external_a2a_task_id, message_id, event_id,"
            " artifact_id, proposal_id, metadata_json"
            " FROM execution_identities"
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
        now = _utc_now()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        self._identity_select_sql() + " WHERE run_id = ?",
                        (identity.run_id,),
                    )
                ).fetchone()
                existing = _row_to_execution_identity(row) if row is not None else None
                try:
                    identity = _merge_execution_identity(existing, identity, metadata)
                except ValueError:
                    if existing is None:
                        raise
                    effect_rows = await (
                        await db.execute(
                            "SELECT idempotency_key, side_effect_key, run_id,"
                            " task_id, trace_id, correlation_id, status,"
                            " result_receipt_id, metadata_json, created_at, updated_at"
                            " FROM idempotency_records WHERE idempotency_key = ?"
                            " AND run_id = ?",
                            (identity.idempotency_key, identity.run_id),
                        )
                    ).fetchall()
                    if not _idempotency_effect_rebind_allowed(
                        (_row_to_idempotency_record(effect_row) for effect_row in effect_rows),
                        existing,
                        identity,
                    ):
                        raise
                    identity = replace(
                        existing,
                        metadata=_merge_execution_identity_metadata(
                            existing,
                            identity,
                            metadata,
                        ),
                    )
                await db.execute(
                    self._identity_upsert_sql(),
                    self._identity_params(
                        identity,
                        source=source,
                        now=now,
                    ),
                )
                loaded_row = await (
                    await db.execute(
                        self._identity_select_sql() + " WHERE run_id = ?",
                        (identity.run_id,),
                    )
                ).fetchone()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        assert loaded_row is not None
        return _row_to_execution_identity(loaded_row)

    def record_execution_identity_sync(
        self,
        identity: ExecutionIdentity,
        *,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionIdentity:
        identity.require_for_dispatch()
        self.init_db_sync()
        now = _utc_now()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                self._identity_select_sql() + " WHERE run_id = ?",
                (identity.run_id,),
            ).fetchone()
            existing = _row_to_execution_identity(row) if row is not None else None
            try:
                identity = _merge_execution_identity(existing, identity, metadata)
            except ValueError:
                if existing is None:
                    raise
                effect_rows = db.execute(
                    "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                    " trace_id, correlation_id, status, result_receipt_id,"
                    " metadata_json, created_at, updated_at FROM idempotency_records"
                    " WHERE idempotency_key = ? AND run_id = ?",
                    (identity.idempotency_key, identity.run_id),
                ).fetchall()
                if not _idempotency_effect_rebind_allowed(
                    (_row_to_idempotency_record(effect_row) for effect_row in effect_rows),
                    existing,
                    identity,
                ):
                    raise
                identity = replace(
                    existing,
                    metadata=_merge_execution_identity_metadata(
                        existing,
                        identity,
                        metadata,
                    ),
                )
            db.execute(
                self._identity_upsert_sql(),
                self._identity_params(
                    identity,
                    source=source,
                    now=now,
                ),
            )
            loaded_row = db.execute(
                self._identity_select_sql() + " WHERE run_id = ?",
                (identity.run_id,),
            ).fetchone()
            db.commit()
        assert loaded_row is not None
        return _row_to_execution_identity(loaded_row)

    async def get_execution_identity(self, run_id: str) -> ExecutionIdentity | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    self._identity_select_sql() + " WHERE run_id = ?",
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
                self._identity_select_sql() + " WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row_to_execution_identity(row) if row is not None else None

    def get_execution_identity_snapshot_sync(
        self,
        run_id: str,
    ) -> ExecutionIdentity | None:
        """Read a committed identity without schema writes or a writer lock."""
        if not self.db_path.is_file():
            return None
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=1.0) as db:
                db.execute("PRAGMA query_only=ON")
                db.row_factory = sqlite3.Row
                row = db.execute(
                    self._identity_select_sql() + " WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table: execution_identities" in str(exc):
                return None
            raise
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
                    self._identity_select_sql()
                    + " WHERE external_a2a_task_id = ?"
                    " ORDER BY updated_at DESC, run_id DESC LIMIT 1",
                    (external_a2a_task_id,),
                )
            ).fetchone()
        return _row_to_execution_identity(row) if row is not None else None

    async def list_execution_identities_by_external_a2a_task(
        self,
        external_a2a_task_id: str,
        *,
        limit: int = 2,
    ) -> list[ExecutionIdentity]:
        """Return a bounded deterministic ambiguity view for one external ID."""
        external_a2a_task_id = str(external_a2a_task_id or "").strip()
        if not external_a2a_task_id:
            raise ValueError("external_a2a_task_id is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer from 1 to 100")
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    self._identity_select_sql()
                    + " WHERE external_a2a_task_id = ?"
                    " ORDER BY updated_at DESC, run_id DESC LIMIT ?",
                    (external_a2a_task_id, limit),
                )
            ).fetchall()
        return [_row_to_execution_identity(row) for row in rows]

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
        completion_payload = _side_effect_completion_payload(result_receipt_id, payload)
        durable = await self.get_execution_identity(identity.run_id)
        try:
            owner = _idempotency_identity_from_canonical(durable, identity)
        except ValueError as exc:
            raise ValueError("side-effect completion identity conflicts with owner") from exc
        if durable is None:
            raise ValueError("side-effect completion identity conflicts with owner")
        identity = owner
        return await self.record_receipt_for_identity(
            identity,
            receipt_type="side_effect_complete",
            status=status,
            side_effect_key=side_effect_key,
            payload=completion_payload,
            receipt_id=_side_effect_complete_receipt_id(
                identity,
                side_effect_key,
                status=status,
                result_receipt_id=result_receipt_id,
                payload=completion_payload,
            ),
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
        completion_payload = _side_effect_completion_payload(result_receipt_id, payload)
        durable = self.get_execution_identity_sync(identity.run_id)
        try:
            owner = _idempotency_identity_from_canonical(durable, identity)
        except ValueError as exc:
            raise ValueError("side-effect completion identity conflicts with owner") from exc
        if durable is None:
            raise ValueError("side-effect completion identity conflicts with owner")
        identity = owner
        return self.record_receipt_for_identity_sync(
            identity,
            receipt_type="side_effect_complete",
            status=status,
            side_effect_key=side_effect_key,
            payload=completion_payload,
            receipt_id=_side_effect_complete_receipt_id(
                identity,
                side_effect_key,
                status=status,
                result_receipt_id=result_receipt_id,
                payload=completion_payload,
            ),
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
        _validate_campaign_cycle_receipt(receipt)
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                    " correlation_id, causation_id, parent_run_id, agent_id,"
                    " idempotency_key, side_effect_key, status, payload_json, created_at"
                    " FROM runtime_receipts WHERE receipt_id = ?",
                    (receipt.receipt_id,),
                )
            ).fetchone()
            existing = _row_to_runtime_receipt(row) if row is not None else None
            if (
                existing is not None
                and replace(receipt, created_at=existing.created_at) == existing
            ):
                await db.commit()
                return existing
            if (
                receipt.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES
                or existing is not None
                and existing.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES
            ):
                if existing is not None:
                    if existing != receipt:
                        await db.rollback()
                        raise ValueError("immutable runtime receipt identity conflicts")
                    await db.commit()
                    return existing
                verb = "INSERT"
            else:
                verb = "INSERT OR REPLACE"
            await db.execute(
                f"{verb} INTO runtime_receipts (receipt_id, receipt_type,"
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

    async def get_runtime_receipt(
        self,
        receipt_id: str,
    ) -> RuntimeReceipt | None:
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                    " correlation_id, causation_id, parent_run_id, agent_id,"
                    " idempotency_key, side_effect_key, status, payload_json, created_at"
                    " FROM runtime_receipts WHERE receipt_id = ?",
                    (receipt_id,),
                )
            ).fetchone()
        return _row_to_runtime_receipt(row) if row is not None else None

    async def insert_runtime_receipt_exact(
        self,
        receipt: RuntimeReceipt,
    ) -> RuntimeReceipt:
        """Insert one immutable carrier or return its byte-equivalent record."""
        _validate_campaign_cycle_receipt(receipt)
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute(
                    "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                    " correlation_id, causation_id, parent_run_id, agent_id,"
                    " idempotency_key, side_effect_key, status, payload_json, created_at"
                    " FROM runtime_receipts WHERE receipt_id = ?",
                    (receipt.receipt_id,),
                )
            ).fetchone()
            if row is not None:
                existing = _row_to_runtime_receipt(row)
                if existing != receipt:
                    raise ValueError("runtime receipt identity already has conflicting evidence")
                await db.commit()
                return existing
            await db.execute(
                "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id, task_id,"
                " trace_id, correlation_id, causation_id, parent_run_id, agent_id,"
                " idempotency_key, side_effect_key, status, payload_json, created_at)"
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
        _validate_campaign_cycle_receipt(receipt)
        self.init_db_sync()
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, causation_id, parent_run_id, agent_id,"
                " idempotency_key, side_effect_key, status, payload_json, created_at"
                " FROM runtime_receipts WHERE receipt_id = ?",
                (receipt.receipt_id,),
            ).fetchone()
            existing = _row_to_runtime_receipt(row) if row is not None else None
            if (
                existing is not None
                and replace(receipt, created_at=existing.created_at) == existing
            ):
                db.commit()
                return existing
            if (
                receipt.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES
                or existing is not None
                and existing.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES
            ):
                if existing is not None:
                    if existing != receipt:
                        db.rollback()
                        raise ValueError("immutable runtime receipt identity conflicts")
                    db.commit()
                    return existing
                verb = "INSERT"
            else:
                verb = "INSERT OR REPLACE"
            db.execute(
                f"{verb} INTO runtime_receipts (receipt_id, receipt_type,"
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
        durable = await self.get_execution_identity(existing.run_id)
        owner = _idempotency_owner_identity(existing, durable)
        if not _idempotency_identity_matches(existing, identity, owner):
            raise ValueError("idempotency duplicate identity conflicts with owner")
        assert owner is not None
        identity = owner
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
        durable = self.get_execution_identity_sync(existing.run_id)
        owner = _idempotency_owner_identity(existing, durable)
        if not _idempotency_identity_matches(existing, identity, owner):
            raise ValueError("idempotency duplicate identity conflicts with owner")
        assert owner is not None
        identity = owner
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
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
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
                inserted = int(cur.rowcount or 0) == 1
                if inserted:
                    identity_row = await (
                        await db.execute(
                            self._identity_select_sql() + " WHERE run_id = ?",
                            (identity.run_id,),
                        )
                    ).fetchone()
                    canonical = (
                        _row_to_execution_identity(identity_row)
                        if identity_row is not None
                        else await self._record_execution_identity_in_transaction(
                            db,
                            identity,
                            source="idempotency_begin",
                        )
                    )
                    identity = _idempotency_identity_from_canonical(
                        canonical,
                        identity,
                    )
                    owner_metadata = _metadata_with_idempotency_owner(
                        metadata,
                        identity,
                    )
                    await db.execute(
                        "UPDATE idempotency_records SET metadata_json = ?"
                        " WHERE idempotency_key = ? AND side_effect_key = ?"
                        " AND status = 'started'",
                        (
                            _json_dump(owner_metadata),
                            identity.idempotency_key,
                            side_effect_key,
                        ),
                    )
                    await db.commit()
                else:
                    await db.rollback()
            except BaseException:
                await db.rollback()
                raise
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
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            try:
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
                inserted = int(cur.rowcount or 0) == 1
                if inserted:
                    identity_row = db.execute(
                        self._identity_select_sql() + " WHERE run_id = ?",
                        (identity.run_id,),
                    ).fetchone()
                    canonical = (
                        _row_to_execution_identity(identity_row)
                        if identity_row is not None
                        else self._record_execution_identity_in_transaction_sync(
                            db,
                            identity,
                            source="idempotency_begin",
                        )
                    )
                    identity = _idempotency_identity_from_canonical(
                        canonical,
                        identity,
                    )
                    owner_metadata = _metadata_with_idempotency_owner(
                        metadata,
                        identity,
                    )
                    db.execute(
                        "UPDATE idempotency_records SET metadata_json = ?"
                        " WHERE idempotency_key = ? AND side_effect_key = ?"
                        " AND status = 'started'",
                        (
                            _json_dump(owner_metadata),
                            identity.idempotency_key,
                            side_effect_key,
                        ),
                    )
                    db.commit()
                else:
                    db.rollback()
            except BaseException:
                db.rollback()
                raise
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
        if status not in _IDEMPOTENCY_COMPLETION_STATUSES:
            raise ValueError("idempotency completion requires a terminal status")
        await self.init_db()
        existing = await self.get_idempotency_record(identity.idempotency_key, side_effect_key)
        if existing is None:
            raise KeyError(f"idempotency record {identity.idempotency_key}:{side_effect_key} not found")
        durable = await self.get_execution_identity(existing.run_id)
        owner = _idempotency_owner_identity(existing, durable)
        if not _idempotency_identity_matches(existing, identity, owner):
            raise ValueError("idempotency completion identity conflicts with owner")
        assert owner is not None
        identity = owner
        merged_metadata = _merge_idempotency_completion_metadata(
            existing,
            metadata,
            result_receipt_id=result_receipt_id,
        )
        if existing.status != "started":
            if (
                existing.status == status
                and existing.result_receipt_id == result_receipt_id
                and existing.metadata == merged_metadata
            ):
                await self.record_side_effect_complete(
                    identity,
                    side_effect_key,
                    status=status,
                    result_receipt_id=result_receipt_id,
                    payload=merged_metadata,
                )
                return existing
            raise ValueError("terminal idempotency evidence is immutable")
        if expected_updated_at is not None and expected_updated_at != existing.updated_at:
            raise RuntimeError(
                f"idempotency lease lost for {identity.idempotency_key}:{side_effect_key}"
            )
        ownership_token = expected_updated_at or existing.updated_at
        now = _next_idempotency_token(ownership_token)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE idempotency_records SET status = ?, result_receipt_id = ?,"
                " metadata_json = ?, updated_at = ?"
                " WHERE idempotency_key = ? AND side_effect_key = ?"
                " AND status = 'started' AND run_id = ? AND task_id = ?"
                " AND trace_id = ? AND correlation_id = ? AND updated_at = ?",
                (
                    status,
                    result_receipt_id,
                    _json_dump(merged_metadata),
                    now,
                    identity.idempotency_key,
                    side_effect_key,
                    identity.run_id,
                    identity.task_id,
                    identity.trace_id,
                    identity.correlation_id,
                    ownership_token.isoformat(),
                ),
            )
            await db.commit()
        if int(cur.rowcount or 0) != 1:
            raise RuntimeError(f"idempotency lease lost for {identity.idempotency_key}:{side_effect_key}")
        record = await self.get_idempotency_record(identity.idempotency_key, side_effect_key)
        assert record is not None
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
        if status not in _IDEMPOTENCY_COMPLETION_STATUSES:
            raise ValueError("idempotency completion requires a terminal status")
        self.init_db_sync()
        existing = self.get_idempotency_record_sync(identity.idempotency_key, side_effect_key)
        if existing is None:
            raise KeyError(f"idempotency record {identity.idempotency_key}:{side_effect_key} not found")
        durable = self.get_execution_identity_sync(existing.run_id)
        owner = _idempotency_owner_identity(existing, durable)
        if not _idempotency_identity_matches(existing, identity, owner):
            raise ValueError("idempotency completion identity conflicts with owner")
        assert owner is not None
        identity = owner
        merged_metadata = _merge_idempotency_completion_metadata(
            existing,
            metadata,
            result_receipt_id=result_receipt_id,
        )
        if existing.status != "started":
            if (
                existing.status == status
                and existing.result_receipt_id == result_receipt_id
                and existing.metadata == merged_metadata
            ):
                self.record_side_effect_complete_sync(
                    identity,
                    side_effect_key,
                    status=status,
                    result_receipt_id=result_receipt_id,
                    payload=merged_metadata,
                )
                return existing
            raise ValueError("terminal idempotency evidence is immutable")
        if expected_updated_at is not None and expected_updated_at != existing.updated_at:
            raise RuntimeError(
                f"idempotency lease lost for {identity.idempotency_key}:{side_effect_key}"
            )
        ownership_token = expected_updated_at or existing.updated_at
        now = _next_idempotency_token(ownership_token)
        with sqlite3.connect(self.db_path) as db:
            _apply_connection_pragmas_sync(db)
            cur = db.execute(
                "UPDATE idempotency_records SET status = ?, result_receipt_id = ?,"
                " metadata_json = ?, updated_at = ?"
                " WHERE idempotency_key = ? AND side_effect_key = ?"
                " AND status = 'started' AND run_id = ? AND task_id = ?"
                " AND trace_id = ? AND correlation_id = ? AND updated_at = ?",
                (
                    status,
                    result_receipt_id,
                    _json_dump(merged_metadata),
                    now,
                    identity.idempotency_key,
                    side_effect_key,
                    identity.run_id,
                    identity.task_id,
                    identity.trace_id,
                    identity.correlation_id,
                    ownership_token.isoformat(),
                ),
            )
            db.commit()
        if int(cur.rowcount or 0) != 1:
            raise RuntimeError(f"idempotency lease lost for {identity.idempotency_key}:{side_effect_key}")
        record = self.get_idempotency_record_sync(identity.idempotency_key, side_effect_key)
        assert record is not None
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
        async with aiosqlite.connect(self.db_path) as db:
            await _apply_connection_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                row = await (
                    await db.execute(
                        "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                        " trace_id, correlation_id, status, result_receipt_id,"
                        " metadata_json, created_at, updated_at"
                        " FROM idempotency_records WHERE idempotency_key = ?"
                        " AND side_effect_key = ?",
                        (identity.idempotency_key, side_effect_key),
                    )
                ).fetchone()
                existing = (
                    _row_to_idempotency_record(row) if row is not None else None
                )
                owner_row = (
                    await (
                        await db.execute(
                            self._identity_select_sql() + " WHERE run_id = ?",
                            (existing.run_id,),
                        )
                    ).fetchone()
                    if existing is not None
                    else None
                )
                durable_owner = (
                    _row_to_execution_identity(owner_row)
                    if owner_row is not None
                    else None
                )
                owner = (
                    _idempotency_owner_identity(existing, durable_owner)
                    if existing is not None
                    else None
                )
                if existing is not None and not _idempotency_identity_matches(
                    existing,
                    owner or identity,
                    owner,
                ):
                    await db.rollback()
                    raise ValueError("idempotency reclaim owner evidence conflicts")
                if existing is not None and existing.task_id != identity.task_id:
                    await db.rollback()
                    raise ValueError("idempotency reclaim task identity conflicts")
                if (
                    existing is None
                    or existing.status != expected_status
                    or expected_updated_at is not None
                    and existing.updated_at != expected_updated_at
                    or expected_status == "completed"
                    and _replayable_idempotency_terminal(existing)
                ):
                    await db.rollback()
                    return None
                assert owner is not None
                if identity.run_id == existing.run_id:
                    if not _idempotency_identity_matches(existing, identity, owner):
                        await db.rollback()
                        raise ValueError("idempotency reclaim identity conflicts with owner")
                    identity = owner
                else:
                    authority_owner = replace(
                        owner,
                        metadata={
                            key: value
                            for key, value in owner.metadata.items()
                            if key in _IMMUTABLE_EXECUTION_METADATA_KEYS
                            and value not in (None, "")
                        },
                    )
                    try:
                        identity = replace(
                            identity,
                            metadata=_merge_execution_identity_metadata(
                                authority_owner,
                                identity,
                                None,
                            ),
                        )
                    except ValueError as exc:
                        raise ValueError(
                            "idempotency reclaim authority conflicts with owner"
                        ) from exc
                    canonical = await self._record_execution_identity_in_transaction(
                        db,
                        identity,
                        source="idempotency_reclaim",
                    )
                    identity = _idempotency_identity_from_canonical(
                        canonical,
                        identity,
                    )
                    if (
                        identity.task_id != existing.task_id
                        or identity.idempotency_key != existing.idempotency_key
                    ):
                        await db.rollback()
                        raise ValueError("idempotency reclaim identity conflicts with record")
                reclaimed_metadata = dict(existing.metadata)
                reclaimed_metadata[_IDEMPOTENCY_OWNER_METADATA_KEY] = (
                    _idempotency_owner_payload(identity)
                )
                now = _next_idempotency_token(existing.updated_at, ownership_time)
                cur = await db.execute(
                    "UPDATE idempotency_records SET status = 'started', run_id = ?,"
                    " task_id = ?, trace_id = ?, correlation_id = ?,"
                    " metadata_json = ?, updated_at = ?"
                    " WHERE idempotency_key = ? AND side_effect_key = ?"
                    " AND status = ? AND updated_at = ?",
                    (
                        identity.run_id,
                        identity.task_id,
                        identity.trace_id,
                        identity.correlation_id,
                        _json_dump(reclaimed_metadata),
                        now,
                        identity.idempotency_key,
                        side_effect_key,
                        expected_status,
                        existing.updated_at.isoformat(),
                    ),
                )
                reclaimed = int(cur.rowcount or 0) == 1
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
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

    def record_session_event_sync(self, event: SessionEventRecord) -> SessionEventRecord:
        def operation(db: sqlite3.Connection) -> SessionEventRecord:
            self._record_session_event_sync_db(db, event)
            return event

        return self._run_sync_transaction(operation)

    @staticmethod
    def _enqueue_episode_outbox_sync_db(
        db: sqlite3.Connection,
        *,
        delivery_key: str,
        destination_id: str,
        episode_id: str,
        attempt_id: str,
        event_type: str,
        payload: dict[str, Any],
        session_event_id: str,
    ) -> EpisodeOutboxRecord:
        delivery_key = str(delivery_key).strip()
        destination_id = str(destination_id).strip()
        episode_id = str(episode_id).strip()
        attempt_id = str(attempt_id)
        event_type = str(event_type).strip()
        if not delivery_key or not episode_id or not event_type:
            raise ValueError("delivery_key, episode_id, and event_type are required")
        # The outbox is durable episode-ledger state, so validate and
        # recursively redact before SQLite sees the payload. The ledger
        # allocates the durable sequence while holding its append lock.
        payload = _normalize_episode_outbox_payload(
            event_type=event_type,
            payload=payload,
        )
        storage_key = _episode_outbox_storage_key(delivery_key, destination_id)
        created_at = _utc_now_iso()
        db.execute(
            "INSERT INTO episode_event_outbox"
            " (delivery_key, logical_delivery_key, destination_id, episode_id,"
            " attempt_id, event_type, payload_json, session_event_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(delivery_key) DO NOTHING",
            (
                storage_key,
                delivery_key,
                destination_id,
                episode_id,
                attempt_id,
                event_type,
                _episode_outbox_json_dump(payload),
                str(session_event_id),
                created_at,
            ),
        )
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
            " episode_id, attempt_id, event_type, payload_json, session_event_id,"
            " created_at, acked_at, episode_event_id"
            " FROM episode_event_outbox WHERE delivery_key = ?",
            (storage_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError("episode outbox enqueue did not persist a row")
        stored = _row_to_episode_outbox(row)
        if (
            stored.episode_id != episode_id
            or stored.attempt_id != attempt_id
            or stored.event_type != event_type
            or _episode_outbox_json_dump(stored.payload)
            != _episode_outbox_json_dump(payload)
            or stored.session_event_id != str(session_event_id)
            or stored.destination_id != destination_id
        ):
            raise ValueError(
                f"episode outbox delivery_key {delivery_key!r} was reused with "
                "different content"
            )
        return stored

    def enqueue_episode_event_sync(
        self,
        *,
        delivery_key: str,
        episode_id: str,
        attempt_id: str,
        event_type: str,
        payload: dict[str, Any],
        destination_id: str = "",
    ) -> EpisodeOutboxRecord:
        def operation(db: sqlite3.Connection) -> EpisodeOutboxRecord:
            return self._enqueue_episode_outbox_sync_db(
                db,
                delivery_key=delivery_key,
                destination_id=destination_id,
                episode_id=episode_id,
                attempt_id=attempt_id,
                event_type=event_type,
                payload=payload,
                session_event_id="",
            )

        return self._run_sync_transaction(operation, immediate=True)

    def record_session_event_with_episode_outbox_sync(
        self,
        event: SessionEventRecord,
        *,
        delivery_key: str,
        episode_id: str,
        attempt_id: str,
        event_type: str,
        payload: dict[str, Any],
        destination_id: str = "",
    ) -> tuple[SessionEventRecord, EpisodeOutboxRecord]:
        def operation(
            db: sqlite3.Connection,
        ) -> tuple[SessionEventRecord, EpisodeOutboxRecord]:
            self._record_session_event_sync_db(db, event)
            outbox = self._enqueue_episode_outbox_sync_db(
                db,
                delivery_key=delivery_key,
                destination_id=destination_id,
                episode_id=episode_id,
                attempt_id=attempt_id,
                event_type=event_type,
                payload=payload,
                session_event_id=event.event_id,
            )
            return event, outbox

        return self._run_sync_transaction(operation, immediate=True)

    def list_pending_episode_events_sync(
        self,
        *,
        episode_id: str | None = None,
        destination_id: str | None = None,
        limit: int = 1000,
    ) -> list[EpisodeOutboxRecord]:
        clauses = ["acked_at IS NULL"]
        params: list[Any] = []
        if episode_id is not None:
            clauses.append("episode_id = ?")
            params.append(str(episode_id))
        if destination_id is not None:
            clauses.append("destination_id = ?")
            params.append(str(destination_id).strip())
        params.append(max(1, min(int(limit), 10_000)))

        def operation(db: sqlite3.Connection) -> list[EpisodeOutboxRecord]:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
                " episode_id, attempt_id, event_type, payload_json, session_event_id,"
                " created_at, acked_at, episode_event_id"
                f" FROM episode_event_outbox WHERE {' AND '.join(clauses)}"
                " ORDER BY outbox_id LIMIT ?",
                params,
            ).fetchall()
            return [_row_to_episode_outbox(row) for row in rows]

        return self._run_sync_transaction(operation)

    def list_episode_destination_history_sync(
        self,
        *,
        episode_id: str,
        destination_id: str,
    ) -> list[EpisodeOutboxRecord]:
        """Return every retained delivery for one episode destination in order."""
        episode_id = str(episode_id).strip()
        destination_id = str(destination_id).strip()
        if not episode_id or not destination_id:
            raise ValueError("episode_id and destination_id are required")

        def operation(db: sqlite3.Connection) -> list[EpisodeOutboxRecord]:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
                " episode_id, attempt_id, event_type, payload_json, session_event_id,"
                " created_at, acked_at, episode_event_id"
                " FROM episode_event_outbox"
                " WHERE episode_id = ? AND destination_id = ? ORDER BY outbox_id",
                (episode_id, destination_id),
            ).fetchall()
            return [_row_to_episode_outbox(row) for row in rows]

        return self._run_sync_transaction(operation)

    def get_episode_outbox_sync(
        self,
        delivery_key: str,
        *,
        destination_id: str | None = None,
    ) -> EpisodeOutboxRecord | None:
        def operation(db: sqlite3.Connection) -> EpisodeOutboxRecord | None:
            db.row_factory = sqlite3.Row
            select_sql = (
                "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
                " episode_id, attempt_id, event_type, payload_json, session_event_id,"
                " created_at, acked_at, episode_event_id"
                " FROM episode_event_outbox"
            )
            if destination_id is not None:
                storage_key = _episode_outbox_storage_key(
                    delivery_key,
                    destination_id,
                )
                row = db.execute(
                    select_sql + " WHERE delivery_key = ?",
                    (storage_key,),
                ).fetchone()
                return _row_to_episode_outbox(row) if row is not None else None
            rows = db.execute(
                select_sql
                + " WHERE logical_delivery_key = ? ORDER BY outbox_id DESC LIMIT 2",
                (str(delivery_key).strip(),),
            ).fetchall()
            if len(rows) > 1:
                raise ValueError(
                    f"destination_id is required for ambiguous delivery_key "
                    f"{delivery_key!r}"
                )
            return _row_to_episode_outbox(rows[0]) if rows else None

        return self._run_sync_transaction(operation)

    def ack_episode_event_sync(
        self,
        delivery_key: str,
        *,
        episode_event_id: str,
        destination_id: str = "",
    ) -> EpisodeOutboxRecord:
        delivery_key = str(delivery_key).strip()
        episode_event_id = str(episode_event_id).strip()
        if not delivery_key or not episode_event_id:
            raise ValueError("delivery_key and episode_event_id are required")
        storage_key = _episode_outbox_storage_key(delivery_key, destination_id)

        def operation(db: sqlite3.Connection) -> EpisodeOutboxRecord:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
                " episode_id, attempt_id, event_type, payload_json, session_event_id,"
                " created_at, acked_at, episode_event_id"
                " FROM episode_event_outbox WHERE delivery_key = ?",
                (storage_key,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown episode outbox delivery_key {delivery_key!r}")
            current = _row_to_episode_outbox(row)
            if current.acked_at is not None:
                if current.episode_event_id != episode_event_id:
                    raise ValueError(
                        f"episode outbox delivery_key {delivery_key!r} was acked "
                        "with a different event_id"
                    )
                return current
            db.execute(
                "UPDATE episode_event_outbox SET acked_at = ?, episode_event_id = ?"
                " WHERE delivery_key = ? AND acked_at IS NULL",
                (_utc_now_iso(), episode_event_id, storage_key),
            )
            row = db.execute(
                "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
                " episode_id, attempt_id, event_type, payload_json, session_event_id,"
                " created_at, acked_at, episode_event_id"
                " FROM episode_event_outbox WHERE delivery_key = ?",
                (storage_key,),
            ).fetchone()
            assert row is not None
            return _row_to_episode_outbox(row)

        return self._run_sync_transaction(operation, immediate=True)

    def requeue_episode_event_sync(
        self,
        delivery_key: str,
        *,
        destination_id: str = "",
    ) -> EpisodeOutboxRecord:
        """Clear one destination-scoped ack so a missing file event replays."""
        delivery_key = str(delivery_key).strip()
        if not delivery_key:
            raise ValueError("delivery_key is required")
        storage_key = _episode_outbox_storage_key(delivery_key, destination_id)

        def operation(db: sqlite3.Connection) -> EpisodeOutboxRecord:
            db.row_factory = sqlite3.Row
            current = db.execute(
                "SELECT outbox_id FROM episode_event_outbox WHERE delivery_key = ?",
                (storage_key,),
            ).fetchone()
            if current is None:
                raise KeyError(f"unknown episode outbox delivery_key {delivery_key!r}")
            db.execute(
                "UPDATE episode_event_outbox SET acked_at = NULL, episode_event_id = ''"
                " WHERE delivery_key = ?",
                (storage_key,),
            )
            row = db.execute(
                "SELECT outbox_id, delivery_key, logical_delivery_key, destination_id,"
                " episode_id, attempt_id, event_type, payload_json, session_event_id,"
                " created_at, acked_at, episode_event_id"
                " FROM episode_event_outbox WHERE delivery_key = ?",
                (storage_key,),
            ).fetchone()
            assert row is not None
            return _row_to_episode_outbox(row)

        return self._run_sync_transaction(operation, immediate=True)

    def requeue_episode_destination_history_sync(
        self,
        *,
        episode_id: str,
        destination_id: str,
    ) -> int:
        """Requeue the retained causal history for one recreated destination."""
        episode_id = str(episode_id).strip()
        destination_id = str(destination_id).strip()
        if not episode_id or not destination_id:
            raise ValueError("episode_id and destination_id are required")

        def operation(db: sqlite3.Connection) -> int:
            cursor = db.execute(
                "UPDATE episode_event_outbox"
                " SET acked_at = NULL, episode_event_id = ''"
                " WHERE episode_id = ? AND destination_id = ?",
                (episode_id, destination_id),
            )
            return max(0, int(cursor.rowcount))

        return self._run_sync_transaction(operation, immediate=True)

    async def _record_session_event_and_optional_receipt_async_db(
        self,
        db: aiosqlite.Connection,
        event: SessionEventRecord,
        receipt: RuntimeReceipt | None,
    ) -> None:
        """Write a session event and optional receipt on one owned connection."""
        await self._record_session_event_async_db(db, event)
        if receipt is not None:
            _validate_campaign_cycle_receipt(receipt)
            row = await (
                await db.execute(
                    "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                    " correlation_id, causation_id, parent_run_id, agent_id,"
                    " idempotency_key, side_effect_key, status, payload_json, created_at"
                    " FROM runtime_receipts WHERE receipt_id = ?",
                    (receipt.receipt_id,),
                )
            ).fetchone()
            existing = _row_to_runtime_receipt(row) if row is not None else None
            immutable = receipt.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES or (
                existing is not None
                and existing.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES
            )
            if immutable and existing is not None:
                if existing != receipt:
                    raise ValueError("immutable runtime receipt identity conflicts")
                return
            await db.execute(*_runtime_receipt_insert(receipt))

    async def record_session_event_with_runtime_receipt(
        self,
        event: SessionEventRecord,
        receipt: RuntimeReceipt,
    ) -> tuple[SessionEventRecord, RuntimeReceipt]:
        """Persist one session event and runtime receipt in one transaction."""
        await self.record_session_event(event, receipt)
        return event, receipt

    def record_session_event_with_runtime_receipt_sync(
        self,
        event: SessionEventRecord,
        receipt: RuntimeReceipt,
    ) -> tuple[SessionEventRecord, RuntimeReceipt]:
        """Synchronously persist an event and receipt in one transaction."""

        def operation(
            db: sqlite3.Connection,
        ) -> tuple[SessionEventRecord, RuntimeReceipt]:
            self._record_session_event_sync_db(db, event)
            _validate_campaign_cycle_receipt(receipt)
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
                " correlation_id, causation_id, parent_run_id, agent_id,"
                " idempotency_key, side_effect_key, status, payload_json, created_at"
                " FROM runtime_receipts WHERE receipt_id = ?",
                (receipt.receipt_id,),
            ).fetchone()
            existing = _row_to_runtime_receipt(row) if row is not None else None
            immutable = receipt.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES or (
                existing is not None
                and existing.receipt_type in _IMMUTABLE_RUNTIME_RECEIPT_TYPES
            )
            if immutable and existing is not None:
                if existing != receipt:
                    raise ValueError("immutable runtime receipt identity conflicts")
                return event, existing
            db.execute(*_runtime_receipt_insert(receipt))
            return event, receipt

        return self._run_sync_transaction(operation, immediate=True)


def _runtime_receipt_insert(
    receipt: RuntimeReceipt,
) -> tuple[str, tuple[Any, ...]]:
    return (
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


_EPISODE_OUTBOX_EVENT_TYPES = (
    "episode_opened",
    "attempt_started",
    "observation_recorded",
    "effect_requested",
    "effect_resolved",
    "review_recorded",
    "episode_closed",
    "post_merge_observation",
)
_EPISODE_OUTBOX_EFFECT_EVENT_TYPES = frozenset(("effect_requested", "effect_resolved"))
_EPISODE_OUTBOX_REDACT_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "api_key",
    "authorization",
    "credential",
)
_EPISODE_OUTBOX_REDACTED = "[REDACTED]"


def _episode_outbox_storage_key(delivery_key: str, destination_id: str) -> str:
    delivery_key = str(delivery_key).strip()
    destination_id = str(destination_id).strip()
    if not delivery_key:
        raise ValueError("delivery_key is required")
    if not destination_id:
        return delivery_key
    digest = hashlib.sha256(
        f"{destination_id}\0{delivery_key}".encode("utf-8")
    ).hexdigest()
    return f"destination:{digest}"


def _redact_episode_outbox_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(marker in key.lower() for marker in _EPISODE_OUTBOX_REDACT_KEY_MARKERS):
                redacted[key] = _EPISODE_OUTBOX_REDACTED
            else:
                redacted[key] = _redact_episode_outbox_value(item)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact_episode_outbox_value(item) for item in value]
    return value


def _reject_episode_outbox_json_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def _episode_outbox_json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def _normalize_episode_outbox_payload(
    *,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply the Episode Event persistence boundary before durable enqueue.

    Runtime state intentionally does not import ``episode_ledger``: doing so
    makes the high-fanout runtime spine depend on the low-level episode schema.
    The parity test in ``test_runtime_state`` locks this vocabulary and
    recursive redaction result to ``EpisodeEvent.new``.
    """
    if event_type not in _EPISODE_OUTBOX_EVENT_TYPES:
        raise ValueError(
            f"unknown event_type {event_type!r}; the lifecycle vocabulary is "
            f"{_EPISODE_OUTBOX_EVENT_TYPES}"
        )
    _episode_outbox_json_dump(payload)
    redacted = _redact_episode_outbox_value(dict(payload))
    if event_type in _EPISODE_OUTBOX_EFFECT_EVENT_TYPES and not str(
        redacted.get("idempotency_key", "")
    ).strip():
        raise ValueError(f"{event_type} requires payload.idempotency_key")
    return redacted


_EPISODE_EVENT_OUTBOX_DDL = """
CREATE TABLE IF NOT EXISTS episode_event_outbox (
    outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_key TEXT NOT NULL UNIQUE,
    logical_delivery_key TEXT NOT NULL DEFAULT '',
    destination_id TEXT NOT NULL DEFAULT '',
    episode_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    session_event_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    acked_at TEXT,
    episode_event_id TEXT NOT NULL DEFAULT ''
)"""

_EPISODE_OUTBOX_MIGRATIONS = (
    (
        "episode_event_outbox",
        "logical_delivery_key TEXT NOT NULL DEFAULT ''",
    ),
    (
        "episode_event_outbox",
        "destination_id TEXT NOT NULL DEFAULT ''",
    ),
)


def _backfill_episode_outbox_keys_and_commit_sync(db: sqlite3.Connection) -> None:
    db.execute(
        "UPDATE episode_event_outbox SET logical_delivery_key = delivery_key"
        " WHERE logical_delivery_key = ''"
    )
    db.commit()


async def _backfill_episode_outbox_keys_and_commit_async(
    db: aiosqlite.Connection,
) -> None:
    await db.execute(
        "UPDATE episode_event_outbox SET logical_delivery_key = delivery_key"
        " WHERE logical_delivery_key = ''"
    )
    await db.commit()


@dataclass(frozen=True)
class EpisodeOutboxRecord:
    delivery_key: str
    episode_id: str
    event_type: str
    schema_version: str = "episode_outbox_record.v1"
    destination_id: str = ""
    storage_key: str = ""
    attempt_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    session_event_id: str = ""
    outbox_id: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    acked_at: datetime | None = None
    episode_event_id: str = ""


def _row_to_episode_outbox(row: sqlite3.Row | aiosqlite.Row) -> EpisodeOutboxRecord:
    storage_key = str(row["delivery_key"])
    event_type = str(row["event_type"])
    try:
        decoded_payload = json.loads(
            row["payload_json"],
            parse_constant=_reject_episode_outbox_json_constant,
        )
        if not isinstance(decoded_payload, dict):
            raise TypeError("payload must decode to an object")
        payload = _normalize_episode_outbox_payload(
            event_type=event_type,
            payload=decoded_payload,
        )
        if _episode_outbox_json_dump(payload) != _episode_outbox_json_dump(
            decoded_payload
        ):
            raise ValueError("payload is not normalized")
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"episode outbox {storage_key!r} has invalid payload_json"
        ) from exc
    return EpisodeOutboxRecord(
        outbox_id=int(row["outbox_id"]),
        delivery_key=str(row["logical_delivery_key"] or storage_key),
        destination_id=str(row["destination_id"] or ""),
        storage_key=storage_key,
        episode_id=str(row["episode_id"]),
        attempt_id=str(row["attempt_id"] or ""),
        event_type=event_type,
        payload=payload,
        session_event_id=str(row["session_event_id"] or ""),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        acked_at=_parse_dt(row["acked_at"]),
        episode_event_id=str(row["episode_event_id"] or ""),
    )


_INDEXES.extend(
    (
        "CREATE INDEX IF NOT EXISTS idx_episode_outbox_pending "
        "ON episode_event_outbox(destination_id, acked_at, outbox_id)",
        "CREATE INDEX IF NOT EXISTS idx_episode_outbox_episode_pending "
        "ON episode_event_outbox(episode_id, destination_id, acked_at, outbox_id)",
    )
)
