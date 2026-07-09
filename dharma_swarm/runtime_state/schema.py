"""SQLite DDL, connection pragmas, and schema-ensure helpers.

Mechanical split from the former dharma_swarm/runtime_state.py (item 6a).
Zero logic change: definitions are verbatim.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite

from dharma_swarm.engine.event_memory import (
    ensure_memory_plane_schema_async,
    ensure_memory_plane_schema_sync,
)


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
