"""Dedicated RuntimeState schema for the governed repository-effect fence."""

from __future__ import annotations

import re
import sqlite3
from typing import Final

import aiosqlite

EFFECT_FENCE_TABLE: Final[str] = "mission_control_effect_fences"
EFFECT_KEY_PREFIX: Final[str] = "governed_patch_effect:"
EFFECT_RECEIPT_TYPE: Final[str] = "governed_patch_effect_terminal"
EFFECT_RECEIPT_ID_PREFIX: Final[str] = "rr_governed_patch_effect_"
EFFECT_IDEMPOTENCY_KEY_PREFIX: Final[str] = "idem_" + EFFECT_RECEIPT_ID_PREFIX

_RUNTIME_RECEIPTS_DDL: Final[str] = """
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

_IDEMPOTENCY_RECORDS_DDL: Final[str] = """
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

_SINK_INDEX_DDLS: Final[tuple[str, ...]] = (
    "CREATE INDEX idx_runtime_receipts_run_created ON runtime_receipts(run_id, created_at)",
    "CREATE INDEX idx_runtime_receipts_trace_created ON runtime_receipts(trace_id, created_at)",
    "CREATE INDEX idx_runtime_receipts_idempotency ON runtime_receipts(idempotency_key)",
    "CREATE INDEX idx_idempotency_run ON idempotency_records(run_id)",
)

EFFECT_FENCE_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS mission_control_effect_fences (
    fence_id TEXT PRIMARY KEY,
    effect_key TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    mission_attempt_id TEXT NOT NULL UNIQUE,
    mission_claim_id TEXT NOT NULL UNIQUE,
    packet_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL UNIQUE,
    delivery_id TEXT NOT NULL UNIQUE,
    proposal_id TEXT NOT NULL UNIQUE,
    candidate_digest TEXT NOT NULL,
    diff_sha256 TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    candidate_bundle_sha256 TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    postimage_sha256 TEXT NOT NULL,
    authorized_source_files_json TEXT NOT NULL,
    executor_agent_uid TEXT NOT NULL,
    executor_run_id TEXT NOT NULL,
    executor_process_boot_id TEXT NOT NULL,
    proposal_receipt_id TEXT NOT NULL,
    proposal_receipt_sha256 TEXT NOT NULL,
    independent_verification_sha256 TEXT NOT NULL,
    foundry_canary_evidence_sha256 TEXT NOT NULL,
    foundry_process_receipt_sha256 TEXT NOT NULL,
    vibe_process_receipt_sha256 TEXT NOT NULL,
    vibe_patch_receipt_sha256 TEXT NOT NULL,
    supervisor_authority_sha256 TEXT NOT NULL,
    binding_sha256 TEXT NOT NULL,
    effect_binding_json TEXT NOT NULL,
    fence_created_at TEXT NOT NULL,
    warrant_issued_at TEXT NOT NULL,
    warrant_expires_at TEXT NOT NULL,
    warrant_token_sha256 TEXT NOT NULL,
    warrant_sha256 TEXT NOT NULL,
    claim_generation INTEGER NOT NULL DEFAULT 0,
    claim_token_sha256 TEXT NOT NULL DEFAULT '',
    claimed_by TEXT NOT NULL DEFAULT '',
    claim_expires_at TEXT,
    scratch_identity TEXT NOT NULL DEFAULT '',
    scratch_binding_json TEXT NOT NULL,
    consuming_at TEXT,
    terminal_record_json TEXT,
    terminal_receipt_id TEXT NOT NULL DEFAULT '',
    consumed_at TEXT,
    recovery_supervisor_id TEXT NOT NULL DEFAULT '',
    recovery_supervisor_process_boot_id TEXT NOT NULL DEFAULT '',
    recovery_supervisor_authority_sha256 TEXT NOT NULL DEFAULT '',
    quarantine_reason TEXT NOT NULL DEFAULT '',
    observed_sha256 TEXT NOT NULL DEFAULT '',
    quarantined_at TEXT,
    UNIQUE (executor_agent_uid, packet_id)
)"""


def ensure_effect_fence_schema_sync(db: sqlite3.Connection) -> None:
    """Create the dedicated table without exposing a generic row writer."""

    db.execute(EFFECT_FENCE_DDL)


async def ensure_effect_fence_schema_async(db: aiosqlite.Connection) -> None:
    """Async schema companion used by ``RuntimeStateStore.init_db``."""

    await db.execute(EFFECT_FENCE_DDL)


def require_effect_fence_schema(db: sqlite3.Connection) -> None:
    """Require the exact column/PK/default shape and non-partial fences."""

    rows = db.execute(
        "SELECT type FROM main.sqlite_schema WHERE name = ? LIMIT 2",
        (EFFECT_FENCE_TABLE,),
    ).fetchall()
    if len(rows) != 1 or str(rows[0][0]) != "table":
        raise sqlite3.DatabaseError("effect fence table is missing or malformed")

    def columns(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (str(row[1]), str(row[2]).upper(), int(row[3]), row[4], int(row[5]))
            for row in connection.execute(
                f"PRAGMA main.table_info({EFFECT_FENCE_TABLE})"
            ).fetchall()
        )

    def unique_indexes(
        connection: sqlite3.Connection,
    ) -> tuple[tuple[str, int, tuple[str, ...]], ...]:
        result: list[tuple[str, int, tuple[str, ...]]] = []
        for row in connection.execute(
            f"PRAGMA main.index_list({EFFECT_FENCE_TABLE})"
        ).fetchall():
            if not bool(row[2]):
                continue
            name = str(row[1]).replace("'", "''")
            info = connection.execute(
                f"PRAGMA main.index_info('{name}')"
            ).fetchall()
            result.append(
                (str(row[3]), int(row[4]), tuple(str(item[2]) for item in info))
            )
        return tuple(sorted(result))

    expected = sqlite3.connect(":memory:")
    try:
        expected.execute(EFFECT_FENCE_DDL)
        expected_columns = columns(expected)
        expected_indexes = unique_indexes(expected)
        expected_sql = expected.execute(
            "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",
            (EFFECT_FENCE_TABLE,),
        ).fetchone()[0]
    finally:
        expected.close()
    if columns(db) != expected_columns:
        raise sqlite3.DatabaseError("effect fence columns are malformed")
    indexes = unique_indexes(db)
    if any(partial for _origin, partial, _columns in indexes):
        raise sqlite3.DatabaseError("effect fence has a partial uniqueness boundary")
    if indexes != expected_indexes:
        raise sqlite3.DatabaseError("effect fence uniqueness constraints are malformed")
    actual_sql = db.execute(
        "SELECT sql FROM main.sqlite_schema WHERE type='table' AND name=?",
        (EFFECT_FENCE_TABLE,),
    ).fetchone()[0]
    def normalize(sql: object) -> str:
        return re.sub(r"\s+", " ", str(sql)).strip().lower()
    if normalize(actual_sql) != normalize(expected_sql):
        raise sqlite3.DatabaseError("effect fence DDL is not exact")

    def sink_shape(
        connection: sqlite3.Connection, table: str,
    ) -> tuple[tuple[tuple[object, ...], ...], str, tuple[tuple[object, ...], ...]]:
        table_rows = tuple(
            (str(row[1]), str(row[2]).upper(), int(row[3]), row[4], int(row[5]))
            for row in connection.execute(f"PRAGMA main.table_info({table})")
        )
        sql_row = connection.execute(
            "SELECT sql FROM main.sqlite_schema WHERE type='table' AND name=?",
            (table,),
        ).fetchall()
        if len(sql_row) != 1:
            raise sqlite3.DatabaseError(f"exact effect sink {table} is missing")
        indexes: list[tuple[object, ...]] = []
        for row in connection.execute(f"PRAGMA main.index_list({table})"):
            name = str(row[1])
            quoted = name.replace("'", "''")
            fields = tuple(
                str(item[2])
                for item in connection.execute(f"PRAGMA main.index_info('{quoted}')")
            )
            indexes.append((
                name if str(row[3]) == "c" else "<automatic>",
                int(row[2]), str(row[3]), int(row[4]), fields,
            ))
        return table_rows, normalize(sql_row[0][0]), tuple(sorted(indexes))

    expected_sinks = sqlite3.connect(":memory:")
    try:
        expected_sinks.execute(_RUNTIME_RECEIPTS_DDL)
        expected_sinks.execute(_IDEMPOTENCY_RECORDS_DDL)
        for ddl in _SINK_INDEX_DDLS:
            expected_sinks.execute(ddl)
        expected_receipts = sink_shape(expected_sinks, "runtime_receipts")
        expected_idempotency = sink_shape(expected_sinks, "idempotency_records")
    finally:
        expected_sinks.close()
    if (
        sink_shape(db, "runtime_receipts") != expected_receipts
        or sink_shape(db, "idempotency_records") != expected_idempotency
        or db.execute("PRAGMA main.foreign_key_list(runtime_receipts)").fetchall()
        or db.execute("PRAGMA main.foreign_key_list(idempotency_records)").fetchall()
    ):
        raise sqlite3.DatabaseError("effect receipt/idempotency sink schema is not exact")
    trigger_rows = db.execute(
        "SELECT 1 FROM main.sqlite_schema WHERE type='trigger'"
        " AND tbl_name IN (?, ?, ?) LIMIT 1",
        (EFFECT_FENCE_TABLE, "runtime_receipts", "idempotency_records"),
    ).fetchall()
    if trigger_rows:
        raise sqlite3.DatabaseError("triggered exact effect sinks are forbidden")


__all__ = [
    "EFFECT_FENCE_DDL",
    "EFFECT_FENCE_TABLE",
    "EFFECT_IDEMPOTENCY_KEY_PREFIX",
    "EFFECT_KEY_PREFIX",
    "EFFECT_RECEIPT_ID_PREFIX",
    "EFFECT_RECEIPT_TYPE",
    "ensure_effect_fence_schema_async",
    "ensure_effect_fence_schema_sync",
    "require_effect_fence_schema",
]
