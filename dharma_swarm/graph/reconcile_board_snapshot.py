"""Exact TaskBoard snapshots captured under the Board writer fence."""

from __future__ import annotations

import json
import hashlib
import sqlite3
from datetime import datetime
from typing import Any

from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.task_board_effect_commit import (
    graph_projection_effect_id,
    load_effect_commit_locked,
)
from dharma_swarm.task_board_projection_intent import is_aware_iso8601, stable_sha256

from .reconcile_board_proof import (
    _atomic_witness_row_is_exact,
    _proof_from_row,
    _witness_row_is_exact,
    validate_atomic_graph_projection_commit,
)


_TASK_ROW_FIELDS = frozenset(
    {
        "id",
        "title",
        "description",
        "status",
        "priority",
        "assigned_to",
        "created_by",
        "created_at",
        "updated_at",
        "result",
        "metadata",
    }
)

BOARD_ONLY_LINEAGE_SCHEMA = "dharma.graph.board_only_observation_lineage.v1"
BOARD_ONLY_LINEAGE_TABLE = "board_only_campaign_observation_lineage"
BOARD_ONLY_HOLD_TABLE = "board_only_campaign_recovery_holds"
_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version", "task_id", "status", "assigned_to", "result",
        "updated_at", "metadata", "metadata_raw_sha256",
    }
)
_CREATE_LINEAGE = f"""
CREATE TABLE IF NOT EXISTS {BOARD_ONLY_LINEAGE_TABLE} (
    lineage_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL
        CHECK (schema_version = '{BOARD_ONLY_LINEAGE_SCHEMA}'),
    hold_id TEXT NOT NULL UNIQUE,
    task_id TEXT NOT NULL,
    transition TEXT NOT NULL CHECK (transition = 'assigned_to_running'),
    owner_run_id TEXT NOT NULL,
    owner_claim_id TEXT NOT NULL,
    execution_identity_sha256 TEXT NOT NULL,
    predecessor_snapshot_sha256 TEXT NOT NULL,
    predecessor_snapshot_json TEXT NOT NULL,
    successor_snapshot_sha256 TEXT NOT NULL,
    successor_snapshot_json TEXT NOT NULL,
    retry_authorized INTEGER NOT NULL CHECK (retry_authorized = 0),
    cessation_proven INTEGER NOT NULL CHECK (cessation_proven = 0),
    observed_at TEXT NOT NULL
)"""


def exact_task_snapshot(
    db: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    metadata: dict[str, Any] | None = None,
) -> Task:
    """Rebuild the same complete ``Task`` value returned by ``TaskBoard.get``.

    The caller holds TaskBoard's ``BEGIN IMMEDIATE`` fence.  Dependencies are
    read through that same connection so the returned value is one exact CAS
    predecessor rather than a lossy reconstruction assembled across reads.
    """
    if not _TASK_ROW_FIELDS.issubset(row.keys()):
        raise ValueError("TaskBoard census row is incomplete")
    if metadata is None:
        raw = row["metadata"]
        try:
            metadata = json.loads(raw) if isinstance(raw, str) else None
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError("TaskBoard census metadata is malformed") from exc
    if not isinstance(metadata, dict):
        raise ValueError("TaskBoard census metadata is malformed")
    dependencies = [
        str(value[0])
        for value in db.execute(
            "SELECT depends_on_id FROM task_dependencies WHERE task_id = ?",
            (str(row["id"]),),
        ).fetchall()
    ]
    return Task(
        id=str(row["id"]),
        title=str(row["title"]),
        description=str(row["description"] or ""),
        status=TaskStatus(str(row["status"])),
        priority=TaskPriority(str(row["priority"])),
        assigned_to=row["assigned_to"],
        created_by=str(row["created_by"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        depends_on=dependencies,
        blocked_by=[],
        result=row["result"],
        metadata=dict(metadata),
    )


def minimal_board_task(row: sqlite3.Row, metadata: dict[str, Any]) -> Task:
    """Build the exact identity-bearing view needed by runtime adoption."""
    return Task(
        id=str(row["id"]),
        title=str(row["title"]),
        status=TaskStatus(str(row["status"])),
        assigned_to=row["assigned_to"],
        result=row["result"],
        metadata=metadata,
    )


def board_only_hold_errors(
    db: sqlite3.Connection,
    valid_hold_ids: set[str],
) -> list[str]:
    rows = db.execute(
        f"SELECT hold_id, task_id, classification FROM {BOARD_ONLY_HOLD_TABLE}"
        " ORDER BY observed_at, hold_id"
    ).fetchall()
    return list(dict.fromkeys(
        f"board_only_campaign:{row[1]}:{row[2]}:effect_indeterminate"
        for row in rows if str(row[0]) not in valid_hold_ids
    ))


def ensure_board_only_observation_lineage(db: sqlite3.Connection) -> None:
    """Install the immutable same-attempt Board observation ledger."""
    db.execute(_CREATE_LINEAGE)
    db.execute(
        f"CREATE TRIGGER IF NOT EXISTS no_update_{BOARD_ONLY_LINEAGE_TABLE} "
        f"BEFORE UPDATE ON {BOARD_ONLY_LINEAGE_TABLE} BEGIN SELECT "
        "RAISE(ABORT, 'board-only observation lineage is immutable'); END"
    )
    db.execute(
        f"CREATE TRIGGER IF NOT EXISTS no_delete_{BOARD_ONLY_LINEAGE_TABLE} "
        f"BEFORE DELETE ON {BOARD_ONLY_LINEAGE_TABLE} BEGIN SELECT "
        "RAISE(ABORT, 'board-only observation lineage is immutable'); END"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _prefixed_sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def hold_projection_snapshot(
    hold: sqlite3.Row,
    *,
    observation_schema: str,
) -> dict[str, Any] | None:
    """Validate a held observation and return its projection-facing fields."""
    raw = str(hold["board_snapshot_json"] or "")
    try:
        observation = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not (
        isinstance(observation, dict)
        and raw == _canonical_json(observation)
        and str(hold["board_snapshot_sha256"]) == _prefixed_sha256(raw)
        and observation.get("schema_version") == observation_schema
        and observation.get("task_id") == str(hold["task_id"])
        and isinstance(observation.get("metadata"), dict)
    ):
        return None
    return {
        "task_id": observation["task_id"],
        "status": observation.get("status"),
        "assigned_to": observation.get("assigned_to"),
        "result": observation.get("result"),
        "metadata": observation["metadata"],
    }


def _lineage_observation(
    encoded: str,
    digest: str,
    *,
    task_id: str,
) -> dict[str, Any] | None:
    try:
        value = json.loads(encoded)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return (
        value
        if (
            isinstance(value, dict)
            and set(value) == _OBSERVATION_FIELDS
            and encoded == _canonical_json(value)
            and digest == _prefixed_sha256(encoded)
            and value.get("task_id") == task_id
            and value.get("status") in {"assigned", "running"}
            and isinstance(value.get("assigned_to"), str)
            and bool(value["assigned_to"])
            and isinstance(value.get("metadata"), dict)
            and is_aware_iso8601(value.get("updated_at"))
        )
        else None
    )


def _same_attempt_transition(
    predecessor: dict[str, Any],
    successor: dict[str, Any],
    *,
    identity: dict[str, Any],
) -> bool:
    unchanged = _OBSERVATION_FIELDS - {"status", "updated_at"}
    metadata = predecessor.get("metadata")
    aliases = {
        "task_id": identity.get("task_id"),
        "agent_id": identity.get("agent_id"),
        "claim_id": identity.get("claim_id"),
        "run_id": identity.get("run_id"),
        "runtime_run_id": identity.get("run_id"),
    }
    active_claim = metadata.get("active_claim") if isinstance(metadata, dict) else None
    return bool(
        predecessor.get("status") == "assigned"
        and successor.get("status") == "running"
        and all(predecessor[key] == successor[key] for key in unchanged)
        and predecessor.get("task_id") == identity.get("task_id")
        and predecessor.get("assigned_to") == identity.get("agent_id")
        and isinstance(metadata, dict)
        and metadata.get("execution_identity") == identity
        and all(metadata.get(key) == value for key, value in aliases.items())
        and isinstance(active_claim, dict)
        and active_claim.get("claim_id") == identity.get("claim_id")
        and active_claim.get("agent_id") == identity.get("agent_id")
    )


def receipt_running_lineage_observation(
    hold: sqlite3.Row,
    *,
    receipt_expected: dict[str, Any],
    identity: dict[str, Any],
    observation_schema: str,
) -> tuple[str, str] | None:
    """Derive the skipped RUNNING observation from an exact receipt predecessor."""
    task_id = str(hold["task_id"])
    predecessor = _lineage_observation(
        str(hold["board_snapshot_json"]),
        str(hold["board_snapshot_sha256"]),
        task_id=task_id,
    )
    if predecessor is None:
        return None
    successor = {
        **predecessor,
        "schema_version": observation_schema,
        "task_id": receipt_expected.get("id"),
        "status": receipt_expected.get("status"),
        "assigned_to": receipt_expected.get("assigned_to"),
        "result": receipt_expected.get("result"),
        "updated_at": receipt_expected.get("updated_at"),
        "metadata": receipt_expected.get("metadata"),
    }
    if not _same_attempt_transition(predecessor, successor, identity=identity):
        return None
    encoded = _canonical_json(successor)
    digest = _prefixed_sha256(encoded)
    return (digest, encoded) if _lineage_observation(
        encoded,
        digest,
        task_id=task_id,
    ) == successor else None


def append_same_attempt_running_lineage(
    db: sqlite3.Connection,
    *,
    hold: sqlite3.Row,
    successor_snapshot_sha256: str,
    successor_snapshot_json: str,
    identity: dict[str, Any],
    observed_at: str,
) -> bool:
    """Append ASSIGNED→RUNNING only when every execution authority stays exact."""
    task_id = str(hold["task_id"])
    predecessor = _lineage_observation(
        str(hold["board_snapshot_json"]),
        str(hold["board_snapshot_sha256"]),
        task_id=task_id,
    )
    successor = _lineage_observation(
        successor_snapshot_json,
        successor_snapshot_sha256,
        task_id=task_id,
    )
    if (
        predecessor is None
        or successor is None
        or not is_aware_iso8601(observed_at)
        or identity.get("run_id") != str(hold["owner_run_id"])
        or identity.get("claim_id") != str(hold["owner_claim_id"])
        or not _same_attempt_transition(predecessor, successor, identity=identity)
    ):
        return False
    identity_sha256 = stable_sha256(identity)
    lineage_id = "bol_" + hashlib.sha256(
        (
            f"{hold['hold_id']}\x1f{hold['board_snapshot_sha256']}\x1f"
            f"{successor_snapshot_sha256}\x1f{identity_sha256}"
        ).encode("utf-8")
    ).hexdigest()
    values = (
        lineage_id, BOARD_ONLY_LINEAGE_SCHEMA, str(hold["hold_id"]), task_id,
        "assigned_to_running", str(hold["owner_run_id"]),
        str(hold["owner_claim_id"]), identity_sha256,
        str(hold["board_snapshot_sha256"]), str(hold["board_snapshot_json"]),
        successor_snapshot_sha256, successor_snapshot_json, 0, 0, observed_at,
    )
    db.execute(
        f"INSERT OR IGNORE INTO {BOARD_ONLY_LINEAGE_TABLE}"
        " (lineage_id, schema_version, hold_id, task_id, transition, owner_run_id,"
        " owner_claim_id, execution_identity_sha256, predecessor_snapshot_sha256,"
        " predecessor_snapshot_json, successor_snapshot_sha256,"
        " successor_snapshot_json, retry_authorized, cessation_proven, observed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        values,
    )
    stored = db.execute(
        f"SELECT * FROM {BOARD_ONLY_LINEAGE_TABLE} WHERE hold_id = ?",
        (str(hold["hold_id"]),),
    ).fetchone()
    return bool(
        stored is not None
        and tuple(stored)[:-1] == values[:-1]
        and is_aware_iso8601(str(stored["observed_at"] or ""))
    )


def exact_observation_lineage_tip(
    db: sqlite3.Connection,
    *,
    hold: sqlite3.Row,
    identity: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None]:
    """Return (present, projection predecessor, challengeable edge evidence)."""
    rows = db.execute(
        f"SELECT * FROM {BOARD_ONLY_LINEAGE_TABLE} WHERE hold_id = ?",
        (str(hold["hold_id"]),),
    ).fetchall()
    if not rows:
        return False, None, None
    if len(rows) != 1:
        return True, None, None
    row = rows[0]
    task_id = str(hold["task_id"])
    predecessor = _lineage_observation(
        str(row["predecessor_snapshot_json"]),
        str(row["predecessor_snapshot_sha256"]),
        task_id=task_id,
    )
    successor = _lineage_observation(
        str(row["successor_snapshot_json"]),
        str(row["successor_snapshot_sha256"]),
        task_id=task_id,
    )
    identity_sha256 = stable_sha256(identity)
    lineage_id = "bol_" + hashlib.sha256(
        (
            f"{hold['hold_id']}\x1f{hold['board_snapshot_sha256']}\x1f"
            f"{row['successor_snapshot_sha256']}\x1f{identity_sha256}"
        ).encode("utf-8")
    ).hexdigest()
    exact = bool(
        str(row["lineage_id"]) == lineage_id
        and str(row["schema_version"]) == BOARD_ONLY_LINEAGE_SCHEMA
        and str(row["hold_id"]) == str(hold["hold_id"])
        and str(row["task_id"]) == task_id
        and str(row["transition"]) == "assigned_to_running"
        and str(row["owner_run_id"]) == str(hold["owner_run_id"])
        == str(identity.get("run_id") or "")
        and str(row["owner_claim_id"]) == str(hold["owner_claim_id"])
        == str(identity.get("claim_id") or "")
        and str(row["execution_identity_sha256"]) == identity_sha256
        and str(row["predecessor_snapshot_sha256"])
        == str(hold["board_snapshot_sha256"])
        and str(row["predecessor_snapshot_json"])
        == str(hold["board_snapshot_json"])
        and int(row["retry_authorized"]) == 0
        and int(row["cessation_proven"]) == 0
        and is_aware_iso8601(str(row["observed_at"] or ""))
        and predecessor is not None
        and successor is not None
        and _same_attempt_transition(predecessor, successor, identity=identity)
    )
    if not exact or successor is None:
        return True, None, None
    expected = {
        "task_id": successor["task_id"],
        "status": successor["status"],
        "assigned_to": successor["assigned_to"],
        "result": successor["result"],
        "metadata": successor["metadata"],
    }
    evidence = {
        "schema_version": BOARD_ONLY_LINEAGE_SCHEMA,
        "lineage_id": str(row["lineage_id"]),
        "predecessor_snapshot_sha256": str(row["predecessor_snapshot_sha256"]),
        "successor_snapshot_sha256": str(row["successor_snapshot_sha256"]),
        "transition": str(row["transition"]),
        "observed_at": str(row["observed_at"]),
    }
    return True, expected, evidence


def atomic_projection_resolution_evidence(
    db: sqlite3.Connection,
    *,
    board_db: sqlite3.Connection,
    expected: dict[str, Any],
    intent: dict[str, Any],
    marker: dict[str, Any],
    run: sqlite3.Row,
    claim: sqlite3.Row,
    acknowledged_at: str,
) -> tuple[bool, dict[str, Any] | None]:
    """Bind a runtime witness to mutation provenance in the locked Board."""
    table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        " AND name = 'task_board_atomic_projection_witnesses'"
    ).fetchone()
    atomic = (
        db.execute(
            "SELECT * FROM task_board_atomic_projection_witnesses WHERE run_id = ?",
            (intent["run_id"],),
        ).fetchone()
        if table is not None
        else None
    )
    if atomic is None:
        return False, None
    try:
        authoritative = load_effect_commit_locked(
            board_db,
            effect_id=graph_projection_effect_id(intent["run_id"]),
        )
        receipt_raw = json.loads(str(atomic["board_receipt_json"] or ""))
        receipt = validate_atomic_graph_projection_commit(
            receipt_raw,
            intent=intent,
            marker=marker,
        )
        receipt_expected = receipt["expected_snapshot"] if receipt else {}
        expected_from_receipt = {
            "task_id": receipt_expected.get("id"),
            "status": receipt_expected.get("status"),
            "assigned_to": receipt_expected.get("assigned_to"),
            "result": receipt_expected.get("result"),
            "metadata": receipt_expected.get("metadata"),
        }
        exact = bool(
            authoritative is not None
            and receipt is not None
            and receipt == authoritative
            and str(atomic["board_receipt_json"]) == _canonical_json(authoritative)
            and _atomic_witness_row_is_exact(
                atomic,
                intent=intent,
                marker=marker,
            )
            and expected_from_receipt == expected
        )
    except (IndexError, KeyError, RuntimeError, TypeError, ValueError):
        return True, None
    if not exact or receipt is None:
        return True, None
    return True, {
        "kind": "terminal_projection_atomic_board_commit",
        "run": {key: run[key] for key in run.keys()},
        "claim": {key: claim[key] for key in claim.keys()},
        "intent_sha256": intent["intent_sha256"],
        "board_receipt_sha256": receipt["receipt_sha256"],
        "expected_snapshot_sha256": stable_sha256(receipt["expected_snapshot"]),
        "target_snapshot_sha256": stable_sha256(receipt["target_snapshot"]),
        "witnessed_at": str(atomic["witnessed_at"]),
        "acknowledged_at": acknowledged_at,
    }


def atomic_projection_predecessor_snapshot(
    db: sqlite3.Connection,
    *,
    board_db: sqlite3.Connection,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None]:
    """Return the full predecessor from one exact atomic witness, if present."""
    table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        " AND name = 'task_board_atomic_projection_witnesses'"
    ).fetchone()
    atomic = (
        db.execute(
            "SELECT * FROM task_board_atomic_projection_witnesses WHERE run_id = ?",
            (intent["run_id"],),
        ).fetchone()
        if table is not None
        else None
    )
    if atomic is None:
        return False, None
    try:
        authoritative = load_effect_commit_locked(
            board_db,
            effect_id=graph_projection_effect_id(intent["run_id"]),
        )
        receipt = validate_atomic_graph_projection_commit(
            json.loads(str(atomic["board_receipt_json"] or "")),
            intent=intent,
            marker=marker,
        )
        exact = bool(
            authoritative is not None
            and receipt is not None
            and receipt == authoritative
            and str(atomic["board_receipt_json"]) == _canonical_json(authoritative)
            and _atomic_witness_row_is_exact(
                atomic,
                intent=intent,
                marker=marker,
            )
        )
    except (IndexError, KeyError, RuntimeError, TypeError, ValueError):
        return True, None
    return True, dict(receipt["expected_snapshot"]) if exact and receipt else None


def close_skipped_running_lineage(
    db: sqlite3.Connection,
    *,
    board_db: sqlite3.Connection,
    hold: sqlite3.Row,
    expected: dict[str, Any],
    identity: dict[str, Any],
    intent: dict[str, Any],
    marker: dict[str, Any],
    observation_schema: str,
    observed_at: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Close an omitted RUNNING census from its exact atomic predecessor."""
    atomic_present, receipt_expected = atomic_projection_predecessor_snapshot(
        db,
        board_db=board_db,
        intent=intent,
        marker=marker,
    )
    if not atomic_present:
        return expected, None
    if receipt_expected is None:
        return None, None
    receipt_projection = {
        "task_id": receipt_expected.get("id"),
        "status": receipt_expected.get("status"),
        "assigned_to": receipt_expected.get("assigned_to"),
        "result": receipt_expected.get("result"),
        "metadata": receipt_expected.get("metadata"),
    }
    if receipt_projection == expected:
        return expected, None
    observation = receipt_running_lineage_observation(
        hold,
        receipt_expected=receipt_expected,
        identity=identity,
        observation_schema=observation_schema,
    )
    if observation is None or not append_same_attempt_running_lineage(
        db,
        hold=hold,
        successor_snapshot_sha256=observation[0],
        successor_snapshot_json=observation[1],
        identity=identity,
        observed_at=observed_at,
    ):
        return None, None
    _present, tip, evidence = exact_observation_lineage_tip(
        db,
        hold=hold,
        identity=identity,
    )
    return (tip, evidence) if tip is not None and evidence is not None else (None, None)


def legacy_projection_resolution_evidence(
    db: sqlite3.Connection,
    *,
    expected: dict[str, Any],
    intent: dict[str, Any],
    marker: dict[str, Any],
    run: sqlite3.Row,
    claim: sqlite3.Row,
    acknowledged_at: str,
) -> dict[str, Any] | None:
    """Validate the explicit nonproduction target+witness compatibility proof."""
    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?)",
            (
                "task_board_projection_targets",
                "task_board_projection_target_witnesses",
            ),
        ).fetchall()
    }
    if len(tables) != 2:
        return None
    target = db.execute(
        "SELECT * FROM task_board_projection_targets WHERE run_id = ?",
        (intent["run_id"],),
    ).fetchone()
    witness = db.execute(
        "SELECT * FROM task_board_projection_target_witnesses WHERE run_id = ?",
        (intent["run_id"],),
    ).fetchone()
    if target is None or witness is None:
        return None
    try:
        proof = _proof_from_row(
            target,
            run_id=intent["run_id"],
            task_id=intent["task_id"],
            intent=intent,
            marker=marker,
        )
        exact = bool(
            proof.expected_snapshot == expected
            and _witness_row_is_exact(witness, proof)
        )
    except (IndexError, KeyError, RuntimeError, TypeError, ValueError):
        return None
    if not exact:
        return None
    return {
        "kind": "terminal_projection",
        "run": {key: run[key] for key in run.keys()},
        "claim": {key: claim[key] for key in claim.keys()},
        "intent_sha256": intent["intent_sha256"],
        "target_snapshot_sha256": str(target["target_snapshot_sha256"]),
        "witnessed_at": str(witness["witnessed_at"]),
        "acknowledged_at": acknowledged_at,
    }


__all__ = [
    "BOARD_ONLY_LINEAGE_SCHEMA",
    "BOARD_ONLY_LINEAGE_TABLE",
    "BOARD_ONLY_HOLD_TABLE",
    "append_same_attempt_running_lineage",
    "atomic_projection_predecessor_snapshot",
    "atomic_projection_resolution_evidence",
    "board_only_hold_errors",
    "close_skipped_running_lineage",
    "ensure_board_only_observation_lineage",
    "exact_observation_lineage_tip",
    "exact_task_snapshot",
    "hold_projection_snapshot",
    "legacy_projection_resolution_evidence",
    "minimal_board_task",
    "receipt_running_lineage_observation",
]
