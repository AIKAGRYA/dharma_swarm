"""Fail-closed, non-authorizing census for Board-only campaign custody."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.graph.receipt_authority import claim_run_match
from dharma_swarm.mission_control_executor_guard import campaign_principal
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_lifecycle_identity import valid_board_campaign_authority
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.task_board_campaign_guard import (
    campaign_metadata_bound,
    campaign_runtime_recovery_fence,
)
from dharma_swarm.task_board_projection_intent import (
    TASK_BOARD_PROJECTION_INTENT_KEY,
    is_aware_iso8601,
    stable_sha256,
    valid_completion_binding,
)

from .reconcile_board_campaign import (
    canonical_claim_execution,
    canonical_orchestrator_execution,
)
from .reconcile_board_replay import (
    PROJECTION_ACK_SCHEMA,
    _projection_marker,
    _valid_intent,
)
from .reconcile_board_snapshot import (
    BOARD_ONLY_HOLD_TABLE,
    BOARD_ONLY_LINEAGE_SCHEMA,
    BOARD_ONLY_LINEAGE_TABLE,
    append_same_attempt_running_lineage,
    atomic_projection_resolution_evidence,
    board_only_hold_errors,
    close_skipped_running_lineage,
    ensure_board_only_observation_lineage,
    exact_observation_lineage_tip,
    exact_task_snapshot,
    hold_projection_snapshot,
    minimal_board_task,
)

BOARD_ONLY_HOLD_SCHEMA = "dharma.graph.board_only_campaign_hold.v1"
BOARD_ONLY_OBSERVATION_SCHEMA = "dharma.graph.board_only_campaign_observation.v1"
BOARD_ONLY_RESOLUTION_SCHEMA = "dharma.graph.board_only_campaign_resolution.v1"
BOARD_ONLY_RESOLUTION_TABLE = "board_only_campaign_recovery_resolutions"
_IN_FLIGHT = ("claimed", "running")
_BOARD_IN_FLIGHT = ("assigned", "running")
_CAMPAIGN_OWNER_FIELDS = frozenset(
    {
        "schema_version",
        "backend",
        "mission_id",
        "task_id",
        "dispatch_key",
        "attempt_generation",
        "run_id",
        "claim_id",
        "idempotency_key",
        "trace_id",
        "correlation_id",
    }
)

_CREATE_HOLDS = f"""
CREATE TABLE IF NOT EXISTS {BOARD_ONLY_HOLD_TABLE} (
    hold_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL
        CHECK (schema_version = '{BOARD_ONLY_HOLD_SCHEMA}'),
    task_id TEXT NOT NULL,
    board_status TEXT NOT NULL
        CHECK (board_status IN ('assigned', 'running')),
    assigned_to TEXT NOT NULL DEFAULT '',
    classification TEXT NOT NULL
        CHECK (classification IN ('exact_campaign_attempt',
                                  'malformed_campaign_shape')),
    state TEXT NOT NULL CHECK (state = 'effect_indeterminate'),
    retry_authorized INTEGER NOT NULL CHECK (retry_authorized = 0),
    cessation_proven INTEGER NOT NULL CHECK (cessation_proven = 0),
    owner_run_id TEXT NOT NULL DEFAULT '',
    owner_claim_id TEXT NOT NULL DEFAULT '',
    campaign_id TEXT NOT NULL DEFAULT '',
    goal_id TEXT NOT NULL DEFAULT '',
    authority_digest TEXT NOT NULL DEFAULT '',
    attempt_generation INTEGER,
    board_snapshot_sha256 TEXT NOT NULL,
    board_snapshot_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE(task_id, board_snapshot_sha256)
)"""

_NO_UPDATE = f"""
CREATE TRIGGER IF NOT EXISTS no_update_{BOARD_ONLY_HOLD_TABLE}
BEFORE UPDATE ON {BOARD_ONLY_HOLD_TABLE}
BEGIN SELECT RAISE(ABORT, 'board-only campaign holds are immutable'); END
"""

_NO_DELETE = f"""
CREATE TRIGGER IF NOT EXISTS no_delete_{BOARD_ONLY_HOLD_TABLE}
BEFORE DELETE ON {BOARD_ONLY_HOLD_TABLE}
BEGIN SELECT RAISE(ABORT, 'board-only campaign holds are immutable'); END
"""

_CREATE_RESOLUTIONS = f"""
CREATE TABLE IF NOT EXISTS {BOARD_ONLY_RESOLUTION_TABLE} (
    resolution_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL
        CHECK (schema_version = '{BOARD_ONLY_RESOLUTION_SCHEMA}'),
    hold_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('exact_runtime_attempt_adopted',
                                          'exact_terminal_projection_proven')),
    state TEXT NOT NULL CHECK (state IN ('exact_runtime_authority_observed',
                                        'exact_terminal_effect_observed')),
    retry_authorized INTEGER NOT NULL CHECK (retry_authorized = 0),
    cessation_proven INTEGER NOT NULL CHECK (cessation_proven = 0),
    owner_run_id TEXT NOT NULL,
    owner_claim_id TEXT NOT NULL,
    runtime_authority_snapshot_sha256 TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    UNIQUE(hold_id, reason, runtime_authority_snapshot_sha256)
)"""

_RESOLUTION_NO_UPDATE = f"""
CREATE TRIGGER IF NOT EXISTS no_update_{BOARD_ONLY_RESOLUTION_TABLE}
BEFORE UPDATE ON {BOARD_ONLY_RESOLUTION_TABLE}
BEGIN SELECT RAISE(ABORT, 'board-only campaign resolutions are immutable'); END
"""

_RESOLUTION_NO_DELETE = f"""
CREATE TRIGGER IF NOT EXISTS no_delete_{BOARD_ONLY_RESOLUTION_TABLE}
BEFORE DELETE ON {BOARD_ONLY_RESOLUTION_TABLE}
BEGIN SELECT RAISE(ABORT, 'board-only campaign resolutions are immutable'); END
"""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _metadata(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _campaign_shaped(metadata: dict[str, Any]) -> bool:
    """Exclude the closed generation-less Mission Control owner v1 lane."""
    owner = metadata.get("mission_control_owner_execution")
    campaign_owner = bool(
        isinstance(owner, dict)
        and (
            owner.get("schema_version") == "dharma.mission_control.owner_execution.v2"
            or "attempt_generation" in owner
        )
    )
    return bool(
        campaign_metadata_bound(metadata)
        or campaign_owner
        or any(
            key in metadata
            for key in (
                "campaign_dispatch_recovery",
                "campaign_dispatch_attempt_history",
                "mission_control_governance",
            )
        )
    )


def _exact_campaign_identity(
    *,
    task_id: str,
    status: str,
    assigned_to: str,
    metadata: dict[str, Any],
    runtime_path: Path,
) -> ExecutionIdentity | None:
    try:
        task = Task(
            id=task_id,
            title="board-only recovery witness",
            status=TaskStatus(status),
            assigned_to=assigned_to or None,
            metadata=metadata,
        )
        bound, principal = campaign_principal(task)
        identity = ExecutionIdentity.from_metadata(metadata, require=True)
    except (MissingExecutionIdentity, TypeError, ValueError):
        return None
    nested = metadata.get("execution_identity")
    authority = metadata.get("mission_campaign_authority")
    owner = metadata.get("mission_control_owner_execution")
    active_claim = metadata.get("active_claim")
    aliases = {
        "task_id": identity.task_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "claim_id": identity.claim_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "idempotency_key": identity.idempotency_key,
    }
    runtime_db_path = metadata.get("runtime_db_path")
    try:
        runtime_path_exact = bool(
            isinstance(runtime_db_path, str)
            and Path(runtime_db_path).expanduser().resolve(strict=False) == runtime_path
        )
    except (OSError, RuntimeError, ValueError):
        runtime_path_exact = False
    valid = bool(
        bound
        and principal
        and assigned_to == principal == identity.agent_id
        and identity.task_id == task_id
        and nested == identity.to_dict()
        and valid_board_campaign_authority(metadata, task_id=task_id)
        and isinstance(authority, dict)
        and isinstance(owner, dict)
        and set(owner) == _CAMPAIGN_OWNER_FIELDS
        and owner.get("schema_version")
        == "dharma.mission_control.owner_execution.v2"
        and owner.get("backend") == "orchestrator"
        and owner.get("task_id") == task_id
        and owner.get("mission_id") == authority.get("mission_id")
        and owner.get("dispatch_key") == authority.get("dispatch_key")
        and owner.get("attempt_generation") == authority.get("attempt_generation")
        and metadata.get("attempt_generation") == authority.get("attempt_generation")
        and all(owner.get(key) == getattr(identity, key) for key in (
            "run_id",
            "claim_id",
            "idempotency_key",
            "trace_id",
            "correlation_id",
        ))
        and all(metadata.get(key) == value for key, value in aliases.items())
        and isinstance(active_claim, dict)
        and active_claim.get("claim_id") == identity.claim_id
        and active_claim.get("agent_id") == identity.agent_id
        and runtime_path_exact
    )
    return identity if valid else None


def _ensure_ledger(db: sqlite3.Connection) -> None:
    db.execute(_CREATE_HOLDS)
    db.execute(_NO_UPDATE)
    db.execute(_NO_DELETE)
    db.execute(_CREATE_RESOLUTIONS)
    db.execute(_RESOLUTION_NO_UPDATE)
    db.execute(_RESOLUTION_NO_DELETE)
    ensure_board_only_observation_lineage(db)
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{BOARD_ONLY_HOLD_TABLE}_task"
        f" ON {BOARD_ONLY_HOLD_TABLE}(task_id, observed_at)"
    )


def _runtime_task_ids(db: sqlite3.Connection) -> set[str]:
    runs = db.execute(
        "SELECT DISTINCT task_id FROM delegation_runs"
        " WHERE status IN (?, ?)",
        _IN_FLIGHT,
    ).fetchall()
    claims = db.execute(
        "SELECT DISTINCT task_id FROM task_claims"
        " WHERE status IN (?, ?) AND recovered_at IS NULL",
        _IN_FLIGHT,
    ).fetchall()
    return {str(row[0]) for row in [*runs, *claims] if str(row[0])}


def _runtime_attempt_started(
    db: sqlite3.Connection,
    *,
    task: Task,
    identity: ExecutionIdentity | None,
) -> bool:
    # Only the complete, exact in-flight run+claim authority may suppress a
    # Board-only hold.  A lone row, mismatched statuses, terminal runtime, or a
    # malformed Board identity cannot establish live custody.
    return bool(
        identity is not None
        and _exact_runtime_attempt(db, task=task, identity=identity) is not None
    )


def _observation(row: sqlite3.Row, metadata: dict[str, Any]) -> tuple[str, str]:
    raw = str(row["metadata"] or "")
    snapshot = {
        "schema_version": BOARD_ONLY_OBSERVATION_SCHEMA,
        "task_id": str(row["id"]),
        "status": str(row["status"]),
        "assigned_to": str(row["assigned_to"] or ""),
        "result": row["result"],
        "updated_at": str(row["updated_at"] or ""),
        "metadata": metadata,
        "metadata_raw_sha256": _sha256(raw),
    }
    encoded = _canonical_json(snapshot)
    return _sha256(encoded), encoded


def _append_hold(
    db: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    metadata: dict[str, Any],
    identity: ExecutionIdentity | None,
    now: datetime,
) -> None:
    task_id = str(row["id"])
    snapshot_sha256, snapshot_json = _observation(row, metadata)
    hold_id = "boh_" + hashlib.sha256(
        f"{task_id}\x1f{snapshot_sha256}".encode("utf-8")
    ).hexdigest()
    authority = metadata.get("mission_campaign_authority")
    authority = authority if isinstance(authority, dict) else {}
    classification = (
        "exact_campaign_attempt" if identity is not None else "malformed_campaign_shape"
    )
    values = (
        hold_id,
        BOARD_ONLY_HOLD_SCHEMA,
        task_id,
        str(row["status"]),
        str(row["assigned_to"] or ""),
        classification,
        "effect_indeterminate",
        0,
        0,
        identity.run_id if identity is not None else "",
        identity.claim_id if identity is not None else "",
        str(authority.get("campaign_id") or ""),
        str(authority.get("goal_id") or ""),
        str(authority.get("authority_digest") or ""),
        authority.get("attempt_generation")
        if type(authority.get("attempt_generation")) is int
        else None,
        snapshot_sha256,
        snapshot_json,
        now.isoformat(),
    )
    db.execute(
        f"INSERT OR IGNORE INTO {BOARD_ONLY_HOLD_TABLE}"
        " (hold_id, schema_version, task_id, board_status, assigned_to,"
        " classification, state, retry_authorized, cessation_proven,"
        " owner_run_id, owner_claim_id, campaign_id, goal_id, authority_digest,"
        " attempt_generation, board_snapshot_sha256, board_snapshot_json, observed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        values,
    )
    stored = db.execute(
        f"SELECT hold_id, schema_version, task_id, board_status, assigned_to,"
        " classification, state, retry_authorized, cessation_proven,"
        " owner_run_id, owner_claim_id, campaign_id, goal_id, authority_digest,"
        " attempt_generation, board_snapshot_sha256, board_snapshot_json, observed_at"
        f" FROM {BOARD_ONLY_HOLD_TABLE} WHERE hold_id = ?",
        (hold_id,),
    ).fetchone()
    if (
        stored is None
        or tuple(stored)[:-1] != values[:-1]
        or not str(stored["observed_at"] or "")
    ):
        raise RuntimeError("board-only campaign hold collision or mutation")


def _identity_registry_is_exact(
    db: sqlite3.Connection,
    identity: ExecutionIdentity,
) -> bool:
    row = db.execute(
        "SELECT trace_id, correlation_id, task_id, claim_id, idempotency_key,"
        " causation_id, parent_run_id, agent_id, session_id, external_a2a_task_id,"
        " message_id, event_id, artifact_id, proposal_id, metadata_json"
        " FROM execution_identities WHERE run_id = ?",
        (identity.run_id,),
    ).fetchone()
    if row is None:
        return False
    fields = (
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
    return all(str(row[field] or "") == getattr(identity, field) for field in fields) and (
        _metadata(row["metadata_json"]) == identity.metadata
    )


def _exact_runtime_attempt(
    db: sqlite3.Connection,
    *,
    task: Task,
    identity: ExecutionIdentity,
) -> tuple[sqlite3.Row, sqlite3.Row] | None:
    run = db.execute(
        "SELECT run_id, session_id, task_id, claim_id, parent_run_id, assigned_by,"
        " assigned_to, status, metadata_json FROM delegation_runs WHERE run_id = ?",
        (identity.run_id,),
    ).fetchone()
    claim = db.execute(
        "SELECT claim_id, task_id, session_id, agent_id, status, recovered_at,"
        " metadata_json FROM task_claims WHERE claim_id = ?",
        (identity.claim_id,),
    ).fetchone()
    if run is None or claim is None:
        return None
    canonical = canonical_orchestrator_execution(run, run["metadata_json"])
    run_fence = campaign_runtime_recovery_fence(
        run["metadata_json"],
        task_id=identity.task_id,
    )
    claim_fence = campaign_runtime_recovery_fence(
        claim["metadata_json"],
        task_id=identity.task_id,
    )
    authority = task.metadata.get("mission_campaign_authority")
    authority = authority if isinstance(authority, dict) else {}
    expected_fence = {
        "schema_version": "dharma.sadhana.campaign_runtime_recovery_fence.v1",
        "task_id": identity.task_id,
        "campaign_id": authority.get("campaign_id"),
        "goal_id": authority.get("goal_id"),
        "claimed_principal": identity.agent_id,
        "authority_digest": authority.get("authority_digest"),
        "attempt_generation": authority.get("attempt_generation"),
    }
    exact = bool(
        str(run["status"]) == str(claim["status"])
        and str(run["status"]) in _IN_FLIGHT
        and claim["recovered_at"] is None
        and canonical == identity.to_dict()
        and canonical_claim_execution(claim, canonical)
        and claim_run_match(claim, run)
        and run_fence == claim_fence == expected_fence
        and "campaign_recovery_hold" not in (_metadata(run["metadata_json"]) or {})
        and "campaign_recovery_hold" not in (_metadata(claim["metadata_json"]) or {})
        and _identity_registry_is_exact(db, identity)
    )
    return (run, claim) if exact else None


def _append_resolution(
    db: sqlite3.Connection,
    *,
    hold: sqlite3.Row,
    identity: ExecutionIdentity,
    reason: str,
    state: str,
    evidence: dict[str, Any],
    now: datetime,
) -> None:
    hold_id = str(hold["hold_id"])
    authority_snapshot = {
        "schema_version": "dharma.graph.board_only_runtime_authority_snapshot.v1",
        "task_id": identity.task_id,
        "execution_identity": identity.to_dict(),
        "evidence": evidence,
    }
    authority_sha256 = _sha256(_canonical_json(authority_snapshot))
    resolution_id = "bor_" + hashlib.sha256(
        f"{hold_id}\x1f{reason}\x1f{authority_sha256}".encode("utf-8")
    ).hexdigest()
    values = (
        resolution_id,
        BOARD_ONLY_RESOLUTION_SCHEMA,
        hold_id,
        identity.task_id,
        reason,
        state,
        0,
        0,
        identity.run_id,
        identity.claim_id,
        authority_sha256,
        now.isoformat(),
    )
    db.execute(
        f"INSERT OR IGNORE INTO {BOARD_ONLY_RESOLUTION_TABLE}"
        " (resolution_id, schema_version, hold_id, task_id, reason, state,"
        " retry_authorized, cessation_proven, owner_run_id, owner_claim_id,"
        " runtime_authority_snapshot_sha256, resolved_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        values,
    )
    stored = db.execute(
        f"SELECT resolution_id, schema_version, hold_id, task_id, reason, state,"
        " retry_authorized, cessation_proven, owner_run_id, owner_claim_id,"
        " runtime_authority_snapshot_sha256, resolved_at"
        f" FROM {BOARD_ONLY_RESOLUTION_TABLE} WHERE resolution_id = ?",
        (resolution_id,),
    ).fetchone()
    if (
        stored is None
        or tuple(stored)[:-1] != values[:-1]
        or not str(stored["resolved_at"] or "")
    ):
        raise RuntimeError("board-only campaign resolution collision or mutation")


def _terminal_projection_attempt(
    db: sqlite3.Connection,
    *,
    board_db: sqlite3.Connection,
    hold: sqlite3.Row,
    runtime_path: Path,
    now: datetime,
) -> tuple[ExecutionIdentity, sqlite3.Row, sqlite3.Row, dict[str, Any]] | None:
    expected = hold_projection_snapshot(
        hold,
        observation_schema=BOARD_ONLY_OBSERVATION_SCHEMA,
    )
    if expected is None:
        return None
    task_id = str(hold["task_id"])
    metadata = expected["metadata"]
    identity = _exact_campaign_identity(
        task_id=task_id,
        status=str(expected["status"]),
        assigned_to=str(expected["assigned_to"] or ""),
        metadata=metadata,
        runtime_path=runtime_path,
    )
    if (
        identity is None
        or identity.run_id != str(hold["owner_run_id"])
        or identity.claim_id != str(hold["owner_claim_id"])
    ):
        return None
    lineage_present, lineage_expected, lineage_evidence = (
        exact_observation_lineage_tip(
            db,
            hold=hold,
            identity=identity.to_dict(),
        )
    )
    if lineage_present:
        if lineage_expected is None or lineage_evidence is None:
            return None
        expected = lineage_expected
    run = db.execute(
        "SELECT run_id, session_id, task_id, claim_id, parent_run_id, assigned_by,"
        " assigned_to, status, started_at, completed_at, failure_code, metadata_json"
        " FROM delegation_runs WHERE run_id = ?",
        (identity.run_id,),
    ).fetchone()
    claim = db.execute(
        "SELECT claim_id, task_id, session_id, agent_id, status, recovered_at,"
        " metadata_json FROM task_claims WHERE claim_id = ?",
        (identity.claim_id,),
    ).fetchone()
    if run is None or claim is None:
        return None
    canonical = canonical_orchestrator_execution(run, run["metadata_json"])
    authority = metadata.get("mission_campaign_authority")
    authority = authority if isinstance(authority, dict) else {}
    fence = {
        "schema_version": "dharma.sadhana.campaign_runtime_recovery_fence.v1",
        "task_id": identity.task_id,
        "campaign_id": authority.get("campaign_id"),
        "goal_id": authority.get("goal_id"),
        "claimed_principal": identity.agent_id,
        "authority_digest": authority.get("authority_digest"),
        "attempt_generation": authority.get("attempt_generation"),
    }
    run_metadata = _metadata(run["metadata_json"])
    claim_metadata = _metadata(claim["metadata_json"])
    recovered_at = str(claim["recovered_at"] or "")
    receipt_recovery = bool(
        recovered_at == str(run["completed_at"] or "")
        and is_aware_iso8601(recovered_at)
        and (run_metadata or {}).get("reconciled_from_receipt") is True
        and (claim_metadata or {}).get("reconciled_from_receipt") is True
    )
    intent = _valid_intent(
        (run_metadata or {}).get(TASK_BOARD_PROJECTION_INTENT_KEY),
        task_id=task_id,
        run_id=identity.run_id,
    )
    binding = intent.get("completion_binding") if intent is not None else None
    if not (
        str(run["status"]) in {"completed", "failed"}
        and str(claim["status"]) == str(run["status"])
        and (claim["recovered_at"] is None or receipt_recovery)
        and is_aware_iso8601(str(run["completed_at"] or ""))
        and canonical == identity.to_dict()
        and canonical_claim_execution(claim, canonical)
        and claim_run_match(claim, run)
        and campaign_runtime_recovery_fence(run["metadata_json"], task_id=task_id)
        == campaign_runtime_recovery_fence(claim["metadata_json"], task_id=task_id)
        == fence
        and "campaign_recovery_hold" not in (run_metadata or {})
        and "campaign_recovery_hold" not in (claim_metadata or {})
        and _identity_registry_is_exact(db, identity)
        and intent is not None
        and intent.get("execution_identity") == identity.to_dict()
        and intent.get("claim_id") == identity.claim_id
        and intent.get("agent_id") == identity.agent_id
        and intent.get("action") == "receipt"
        and intent.get("run_status") == str(run["status"])
        and intent.get("source_kind") == "idempotency_record"
        and intent.get("result_sha256")
        == hashlib.sha256(str(intent.get("result")).encode("utf-8")).hexdigest()
        and all(isinstance(key, str) and key for key in intent["metadata_remove"])
        and intent.get("metadata_remove")
        == sorted(set(intent.get("metadata_remove") or []))
        and intent.get("metadata_delta_sha256")
        == stable_sha256(
            {
                "set": intent.get("metadata_set"),
                "remove": intent.get("metadata_remove"),
            }
        )
        and valid_completion_binding(
            binding,
            task_id=identity.task_id,
            run_id=identity.run_id,
            claim_id=identity.claim_id,
            agent_id=identity.agent_id,
            dispatch_idempotency_key=identity.idempotency_key,
            result=str(intent.get("result")),
        )
    ):
        return None
    marker = _projection_marker(intent)
    ack_table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        " AND name = 'task_board_projection_acks'"
    ).fetchone()
    if ack_table is None:
        return None
    ack = db.execute(
        "SELECT * FROM task_board_projection_acks WHERE run_id = ?",
        (identity.run_id,),
    ).fetchone()
    ack_exact = bool(
        ack is not None
        and str(ack["task_id"]) == task_id
        and str(ack["intent_sha256"]) == intent["intent_sha256"]
        and str(ack["board_receipt_sha256"]) == stable_sha256(marker)
        and str(ack["board_receipt_json"]) == _canonical_json(marker)
        and str(ack["schema_version"]) == PROJECTION_ACK_SCHEMA
        and is_aware_iso8601(str(ack["acknowledged_at"] or ""))
    )
    if not ack_exact:
        return None

    if not lineage_present:
        expected, lineage_evidence = close_skipped_running_lineage(
            db,
            board_db=board_db,
            hold=hold,
            expected=expected,
            identity=identity.to_dict(),
            intent=intent,
            marker=marker,
            observation_schema=BOARD_ONLY_OBSERVATION_SCHEMA,
            observed_at=now.isoformat(),
        )
        if expected is None:
            return None

    atomic_present, atomic_evidence = atomic_projection_resolution_evidence(
        db,
        board_db=board_db,
        expected=expected,
        intent=intent,
        marker=marker,
        run=run,
        claim=claim,
        acknowledged_at=str(ack["acknowledged_at"]),
    )
    if not atomic_present or atomic_evidence is None:
        return None
    if lineage_evidence is not None:
        atomic_evidence = {**atomic_evidence, "observation_lineage": lineage_evidence}
    return (
        identity,
        run,
        claim,
        atomic_evidence,
    )


def _valid_resolution_holds(
    db: sqlite3.Connection,
    *,
    board_db: sqlite3.Connection | None,
    board_rows: dict[str, sqlite3.Row],
    runtime_path: Path,
    now: datetime,
) -> set[str]:
    valid: set[str] = set()
    holds = db.execute(
        f"SELECT * FROM {BOARD_ONLY_HOLD_TABLE}"
        " WHERE classification = 'exact_campaign_attempt'"
        " ORDER BY observed_at, hold_id"
    ).fetchall()
    for hold in holds:
        hold_id = str(hold["hold_id"])
        row = board_rows.get(str(hold["task_id"]))
        if row is not None and str(row["status"]) in _BOARD_IN_FLIGHT:
            metadata = _metadata(row["metadata"])
            current_sha256, current_json = (
                _observation(row, metadata) if metadata is not None else ("", "")
            )
            identity = (
                _exact_campaign_identity(
                    task_id=str(row["id"]),
                    status=str(row["status"]),
                    assigned_to=str(row["assigned_to"] or ""),
                    metadata=metadata,
                    runtime_path=runtime_path,
                )
                if metadata is not None
                else None
            )
            exact = (
                _exact_runtime_attempt(
                    db,
                    task=minimal_board_task(row, metadata),
                    identity=identity,
                )
                if identity is not None
                and identity.run_id == str(hold["owner_run_id"])
                and identity.claim_id == str(hold["owner_claim_id"])
                else None
            )
            same_snapshot = current_sha256 == str(hold["board_snapshot_sha256"])
            lineage_exact = bool(
                identity is not None
                and exact is not None
                and not same_snapshot
                and append_same_attempt_running_lineage(
                    db,
                    hold=hold,
                    successor_snapshot_sha256=current_sha256,
                    successor_snapshot_json=current_json,
                    identity=identity.to_dict(),
                    observed_at=now.isoformat(),
                )
            )
            if identity is not None and exact is not None and (
                same_snapshot or lineage_exact
            ):
                _append_resolution(
                    db,
                    hold=hold,
                    identity=identity,
                    reason="exact_runtime_attempt_adopted",
                    state="exact_runtime_authority_observed",
                    evidence={
                        "kind": (
                            "live_attempt"
                            if same_snapshot
                            else "live_attempt_monotonic_board_lineage"
                        ),
                        "board_snapshot_sha256": current_sha256,
                        "run": {key: exact[0][key] for key in exact[0].keys()},
                        "claim": {key: exact[1][key] for key in exact[1].keys()},
                    },
                    now=now,
                )
                valid.add(hold_id)
                continue
        terminal = (
            _terminal_projection_attempt(
                db,
                board_db=board_db,
                hold=hold,
                runtime_path=runtime_path,
                now=now,
            )
            if board_db is not None
            else None
        )
        if terminal is None:
            continue
        identity, _run, _claim, evidence = terminal
        _append_resolution(
            db,
            hold=hold,
            identity=identity,
            reason="exact_terminal_projection_proven",
            state="exact_terminal_effect_observed",
            evidence=evidence,
            now=now,
        )
        valid.add(hold_id)
    return valid


def _board_rows(
    board_db: sqlite3.Connection,
    runtime_task_ids: set[str],
) -> list[sqlite3.Row]:
    rows = board_db.execute(
        "SELECT * FROM tasks WHERE status IN (?, ?)",
        _BOARD_IN_FLIGHT,
    ).fetchall()
    observed = {str(row["id"]) for row in rows}
    for task_id in sorted(runtime_task_ids - observed):
        row = board_db.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is not None:
            rows.append(row)
    return rows


def _locked_census(
    *,
    runtime_path: Path,
    board_path: Path,
    now: datetime,
) -> tuple[dict[str, Any], set[str], list[str]]:
    snapshots: dict[str, Any] = {}
    read_errors: set[str] = set()
    with sqlite3.connect(board_path, timeout=2.0) as board_db:
        board_db.row_factory = sqlite3.Row
        board_db.execute("PRAGMA busy_timeout=2000")
        board_db.execute("BEGIN IMMEDIATE")
        try:
            with sqlite3.connect(runtime_path, timeout=2.0) as runtime_db:
                runtime_db.row_factory = sqlite3.Row
                runtime_db.execute("PRAGMA busy_timeout=2000")
                runtime_db.execute("BEGIN IMMEDIATE")
                _ensure_ledger(runtime_db)
                runtime_task_ids = _runtime_task_ids(runtime_db)
                board_rows = _board_rows(board_db, runtime_task_ids)
                for row in board_rows:
                    task_id = str(row["id"])
                    metadata = _metadata(row["metadata"])
                    if metadata is None:
                        if task_id in runtime_task_ids:
                            read_errors.add(task_id)
                        continue
                    try:
                        snapshots[task_id] = exact_task_snapshot(
                            board_db,
                            row,
                            metadata=metadata,
                        )
                    except (TypeError, ValueError):
                        if task_id in runtime_task_ids:
                            read_errors.add(task_id)
                    if (
                        str(row["status"]) not in _BOARD_IN_FLIGHT
                        or not _campaign_shaped(metadata)
                    ):
                        continue
                    identity = _exact_campaign_identity(
                        task_id=task_id,
                        status=str(row["status"]),
                        assigned_to=str(row["assigned_to"] or ""),
                        metadata=metadata,
                        runtime_path=runtime_path,
                    )
                    if _runtime_attempt_started(
                        runtime_db,
                        task=minimal_board_task(row, metadata),
                        identity=identity,
                    ):
                        continue
                    _append_hold(
                        runtime_db,
                        row=row,
                        metadata=metadata,
                        identity=identity,
                        now=now,
                    )
                valid_holds = _valid_resolution_holds(
                    runtime_db,
                    board_db=board_db,
                    board_rows={str(row["id"]): row for row in board_rows},
                    runtime_path=runtime_path,
                    now=now,
                )
                errors = board_only_hold_errors(runtime_db, valid_holds)
                runtime_db.commit()
            # This is a read fence, not a cross-database commit.
            board_db.rollback()
        except BaseException:
            if board_db.in_transaction:
                board_db.rollback()
            raise
    return snapshots, read_errors, errors


async def _fallback_census(
    *,
    runtime_path: Path,
    task_board: Any,
    now: datetime,
) -> tuple[dict[str, Any], set[str], list[str]]:
    with sqlite3.connect(runtime_path, timeout=2.0) as db:
        db.execute("PRAGMA busy_timeout=2000")
        db.execute("BEGIN IMMEDIATE")
        _ensure_ledger(db)
        task_ids = _runtime_task_ids(db)
        valid_holds = _valid_resolution_holds(
            db,
            board_db=None,
            board_rows={},
            runtime_path=runtime_path,
            now=now,
        )
        errors = board_only_hold_errors(db, valid_holds)
        db.commit()
    get_task = getattr(task_board, "get", None)
    if not callable(get_task):
        return {}, set(), errors
    snapshots: dict[str, Any] = {}
    read_errors: set[str] = set()
    for task_id in task_ids:
        try:
            snapshots[task_id] = await get_task(task_id)
        except Exception:  # noqa: BLE001 - classified under runtime lock by caller
            read_errors.add(task_id)
    return snapshots, read_errors, errors


async def snapshot_board_recovery_census(
    *,
    runtime_state: Any,
    task_board: Any,
    now: datetime,
) -> tuple[dict[str, Any], set[str], list[str]]:
    """Return runtime-linked snapshots and persist any Board-only holds."""
    runtime_path = Path(runtime_state.db_path).expanduser().resolve(strict=False)
    board_raw = getattr(task_board, "_db_path", None)
    if board_raw is None:
        return await _fallback_census(
            runtime_path=runtime_path,
            task_board=task_board,
            now=now,
        )
    board_path = Path(board_raw).expanduser().resolve(strict=False)
    if board_path == runtime_path:
        raise RuntimeError("TaskBoard and runtime state cannot share one SQLite file")
    if not board_path.is_file():
        raise RuntimeError("canonical TaskBoard database is unavailable")
    return _locked_census(runtime_path=runtime_path, board_path=board_path, now=now)


__all__ = [
    "BOARD_ONLY_HOLD_SCHEMA",
    "BOARD_ONLY_HOLD_TABLE",
    "BOARD_ONLY_LINEAGE_SCHEMA",
    "BOARD_ONLY_LINEAGE_TABLE",
    "BOARD_ONLY_RESOLUTION_SCHEMA",
    "BOARD_ONLY_RESOLUTION_TABLE",
    "snapshot_board_recovery_census",
]
