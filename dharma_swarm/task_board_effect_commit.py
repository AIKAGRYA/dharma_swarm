"""Atomic, immutable TaskBoard-local receipts for exact committed effects."""

from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

import aiosqlite

from dharma_swarm.task_board_projection_intent import (
    GRAPH_PROJECTION_HISTORY_KEY,
    GRAPH_PROJECTION_KEY,
    is_aware_iso8601,
    is_sha256_hex,
    stable_sha256,
)

EFFECT_COMMIT_SCHEMA = "dharma.task_board.effect_commit.v1"
EFFECT_TRANSITION_SCHEMA = "dharma.task_board.effect_transition.v1"
EFFECT_MUTATION_SCHEMA = "dharma.task_board.effect_mutation.v1"
GRAPH_PROJECTION_EFFECT_KIND = "dharma.graph.terminal_projection.v1"
GRAPH_PROJECTION_PAYLOAD_SCHEMA = (
    "dharma.graph.terminal_projection_commit_payload.v1"
)
GRAPH_PROJECTION_EFFECT_PREFIX = "graph_projection:"
AUTHORITATIVE_PROJECTION_COMMIT_MODE = "task_board_atomic_effect_commit.v1"
NON_PRODUCTION_PROJECTION_COMMIT_MODE = "non_production_exact_readback.v1"

_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "effect_id",
        "effect_kind",
        "task_id",
        "authority_sha256",
        "expected_snapshot",
        "target_snapshot",
        "effect_payload",
        "committed_at",
        "receipt_sha256",
    }
)
_TASK_SNAPSHOT_FIELDS = frozenset(
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
        "depends_on",
        "blocked_by",
        "result",
        "metadata",
    }
)


@dataclass(frozen=True)
class _LockedTaskTransition:
    """Unexported capability minted only after one exact locked SQL UPDATE."""

    connection_id: int
    mutation_id: str
    effect_id: str
    task_id: str
    expected_snapshot_sha256: str
    target_snapshot_sha256: str
    receipt_sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _canonical_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _load_json(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def task_effect_snapshot(task: Any) -> dict[str, Any]:
    """Serialize the complete Task value participating in one exact CAS."""
    dump = getattr(task, "model_dump", None)
    if not callable(dump):
        raise TypeError("TaskBoard effect receipt requires a concrete Task value")
    snapshot = dump(mode="json")
    if not isinstance(snapshot, dict) or set(snapshot) != _TASK_SNAPSHOT_FIELDS:
        raise ValueError("TaskBoard effect snapshot shape is invalid")
    return snapshot


async def ensure_effect_commit_ledger(db: aiosqlite.Connection) -> None:
    """Create the generic append-only Board effect-commit ledger."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_effect_commits ("
        "effect_id TEXT PRIMARY KEY, effect_kind TEXT NOT NULL, task_id TEXT NOT NULL,"
        " authority_sha256 TEXT NOT NULL, expected_snapshot_sha256 TEXT NOT NULL,"
        " expected_snapshot_json TEXT NOT NULL, target_snapshot_sha256 TEXT NOT NULL,"
        " target_snapshot_json TEXT NOT NULL, effect_payload_sha256 TEXT NOT NULL,"
        " effect_payload_json TEXT NOT NULL, committed_at TEXT NOT NULL,"
        " receipt_sha256 TEXT NOT NULL UNIQUE, receipt_json TEXT NOT NULL,"
        " schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_commit_no_update "
        "BEFORE UPDATE ON task_board_effect_commits BEGIN SELECT RAISE(ABORT,"
        " 'task board effect commit is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_commit_no_delete "
        "BEFORE DELETE ON task_board_effect_commits BEGIN SELECT RAISE(ABORT,"
        " 'task board effect commit is immutable'); END"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_effect_transitions ("
        "effect_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " expected_snapshot_sha256 TEXT NOT NULL,"
        " target_snapshot_sha256 TEXT NOT NULL, receipt_sha256 TEXT NOT NULL UNIQUE,"
        " transitioned_at TEXT NOT NULL, schema_version TEXT NOT NULL)"
    )
    transition_columns = {
        str(row[1])
        for row in await (
            await db.execute("PRAGMA table_info(task_board_effect_transitions)")
        ).fetchall()
    }
    if "mutation_id" not in transition_columns:
        # Old assertion-only transition rows cannot be promoted.  They remain
        # readable at the SQL layer but fail closed in ``load_effect_commit``.
        await db.execute(
            "ALTER TABLE task_board_effect_transitions ADD COLUMN mutation_id TEXT"
        )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS"
        " idx_task_board_effect_transition_mutation"
        " ON task_board_effect_transitions(mutation_id)"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_effect_transition_arms ("
        "mutation_id TEXT PRIMARY KEY, effect_id TEXT NOT NULL UNIQUE,"
        " task_id TEXT NOT NULL UNIQUE, expected_snapshot_sha256 TEXT NOT NULL,"
        " target_snapshot_sha256 TEXT NOT NULL, receipt_sha256 TEXT NOT NULL UNIQUE,"
        " transitioned_at TEXT NOT NULL, schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_effect_mutations ("
        "mutation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " old_title TEXT NOT NULL, old_description TEXT NOT NULL,"
        " old_status TEXT NOT NULL, old_priority TEXT NOT NULL,"
        " old_assigned_to TEXT, old_created_by TEXT NOT NULL,"
        " old_created_at TEXT NOT NULL, old_updated_at TEXT NOT NULL,"
        " old_result TEXT, old_metadata TEXT NOT NULL,"
        " new_title TEXT NOT NULL, new_description TEXT NOT NULL,"
        " new_status TEXT NOT NULL, new_priority TEXT NOT NULL,"
        " new_assigned_to TEXT, new_created_by TEXT NOT NULL,"
        " new_created_at TEXT NOT NULL, new_updated_at TEXT NOT NULL,"
        " new_result TEXT, new_metadata TEXT NOT NULL,"
        " schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_mutation_no_update "
        "BEFORE UPDATE ON task_board_effect_mutations BEGIN SELECT RAISE(ABORT,"
        " 'task board effect mutation is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_mutation_no_delete "
        "BEFORE DELETE ON task_board_effect_mutations BEGIN SELECT RAISE(ABORT,"
        " 'task board effect mutation is immutable'); END"
    )
    # This trigger is the mechanical coupling: the mutation and transition
    # records are minted by the same SQLite statement that changes ``tasks``.
    # Merely inserting a receipt plus a matching transition assertion cannot
    # manufacture the OLD/NEW row image recorded here.
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_transition_on_task_update "
        "AFTER UPDATE ON tasks WHEN EXISTS (SELECT 1 FROM "
        "task_board_effect_transition_arms WHERE task_id = NEW.id) BEGIN "
        "INSERT INTO task_board_effect_mutations (mutation_id, task_id,"
        " old_title, old_description, old_status, old_priority, old_assigned_to,"
        " old_created_by, old_created_at, old_updated_at, old_result, old_metadata,"
        " new_title, new_description, new_status, new_priority, new_assigned_to,"
        " new_created_by, new_created_at, new_updated_at, new_result, new_metadata,"
        " schema_version) SELECT mutation_id, NEW.id, OLD.title, OLD.description,"
        " OLD.status, OLD.priority, OLD.assigned_to, OLD.created_by, OLD.created_at,"
        " OLD.updated_at, OLD.result, OLD.metadata, NEW.title, NEW.description,"
        " NEW.status, NEW.priority, NEW.assigned_to, NEW.created_by, NEW.created_at,"
        " NEW.updated_at, NEW.result, NEW.metadata, '"
        + EFFECT_MUTATION_SCHEMA
        + "' FROM task_board_effect_transition_arms WHERE task_id = NEW.id; "
        "INSERT INTO task_board_effect_transitions (effect_id, task_id,"
        " expected_snapshot_sha256, target_snapshot_sha256, receipt_sha256,"
        " transitioned_at, schema_version, mutation_id) SELECT effect_id, task_id,"
        " expected_snapshot_sha256, target_snapshot_sha256, receipt_sha256,"
        " transitioned_at, schema_version, mutation_id FROM "
        "task_board_effect_transition_arms WHERE task_id = NEW.id; "
        "DELETE FROM task_board_effect_transition_arms WHERE task_id = NEW.id; END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_transition_requires_mutation "
        "BEFORE INSERT ON task_board_effect_transitions WHEN NOT EXISTS (SELECT 1"
        " FROM task_board_effect_mutations WHERE mutation_id = NEW.mutation_id"
        " AND task_id = NEW.task_id) BEGIN SELECT RAISE(ABORT,"
        " 'task board effect transition lacks task mutation'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_transition_no_update "
        "BEFORE UPDATE ON task_board_effect_transitions BEGIN SELECT RAISE(ABORT,"
        " 'task board effect transition is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_effect_transition_no_delete "
        "BEFORE DELETE ON task_board_effect_transitions BEGIN SELECT RAISE(ABORT,"
        " 'task board effect transition is immutable'); END"
    )


def _valid_snapshot(raw: Any, *, task_id: str) -> bool:
    return bool(
        isinstance(raw, dict)
        and set(raw) == _TASK_SNAPSHOT_FIELDS
        and raw.get("id") == task_id
        and isinstance(raw.get("metadata"), dict)
        and isinstance(raw.get("depends_on"), list)
        and isinstance(raw.get("blocked_by"), list)
        and is_aware_iso8601(raw.get("created_at"))
        and is_aware_iso8601(raw.get("updated_at"))
    )


def validate_effect_commit_receipt(raw: Any) -> dict[str, Any] | None:
    """Validate the full self-hashed generic effect receipt."""
    if not isinstance(raw, dict) or set(raw) != _RECEIPT_FIELDS:
        return None
    unsigned = {key: value for key, value in raw.items() if key != "receipt_sha256"}
    task_id = raw.get("task_id")
    return (
        raw
        if (
            raw.get("schema_version") == EFFECT_COMMIT_SCHEMA
            and isinstance(raw.get("effect_id"), str)
            and raw["effect_id"]
            and isinstance(raw.get("effect_kind"), str)
            and raw["effect_kind"]
            and isinstance(task_id, str)
            and task_id
            and is_sha256_hex(raw.get("authority_sha256"))
            and _valid_snapshot(raw.get("expected_snapshot"), task_id=task_id)
            and _valid_snapshot(raw.get("target_snapshot"), task_id=task_id)
            and isinstance(raw.get("effect_payload"), dict)
            and is_aware_iso8601(raw.get("committed_at"))
            and raw.get("receipt_sha256") == stable_sha256(unsigned)
        )
        else None
    )


def _receipt_from_row(row: Any) -> dict[str, Any]:
    receipt = _load_json(row["receipt_json"])
    valid = validate_effect_commit_receipt(receipt)
    if valid is None:
        raise ValueError("TaskBoard effect commit receipt is malformed")
    expected = valid["expected_snapshot"]
    target = valid["target_snapshot"]
    payload = valid["effect_payload"]
    if not (
        str(row["effect_id"]) == valid["effect_id"]
        and str(row["effect_kind"]) == valid["effect_kind"]
        and str(row["task_id"]) == valid["task_id"]
        and str(row["authority_sha256"]) == valid["authority_sha256"]
        and str(row["expected_snapshot_sha256"]) == stable_sha256(expected)
        and str(row["expected_snapshot_json"]) == _canonical_json(expected)
        and str(row["target_snapshot_sha256"]) == stable_sha256(target)
        and str(row["target_snapshot_json"]) == _canonical_json(target)
        and str(row["effect_payload_sha256"]) == stable_sha256(payload)
        and str(row["effect_payload_json"]) == _canonical_json(payload)
        and str(row["committed_at"]) == valid["committed_at"]
        and str(row["receipt_sha256"]) == valid["receipt_sha256"]
        and str(row["receipt_json"]) == _canonical_json(valid)
        and str(row["schema_version"]) == EFFECT_COMMIT_SCHEMA
    ):
        raise ValueError("TaskBoard effect commit ledger conflicts")
    return valid


def _transition_row_is_exact(
    row: Any,
    receipt: dict[str, Any],
) -> bool:
    return bool(
        str(row["effect_id"]) == receipt["effect_id"]
        and str(row["task_id"]) == receipt["task_id"]
        and str(row["expected_snapshot_sha256"])
        == stable_sha256(receipt["expected_snapshot"])
        and str(row["target_snapshot_sha256"])
        == stable_sha256(receipt["target_snapshot"])
        and str(row["receipt_sha256"]) == receipt["receipt_sha256"]
        and str(row["transitioned_at"]) == receipt["committed_at"]
        and str(row["schema_version"]) == EFFECT_TRANSITION_SCHEMA
        and isinstance(row["mutation_id"], str)
        and bool(str(row["mutation_id"]))
    )


def _snapshot_time_as_db(value: Any) -> str | None:
    if not is_aware_iso8601(value):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    except (TypeError, ValueError):
        return None


def _mutation_side_is_exact(
    row: Any,
    *,
    prefix: str,
    snapshot: dict[str, Any],
) -> bool:
    metadata = _load_json(row[f"{prefix}_metadata"])
    return bool(
        str(row["task_id"]) == snapshot["id"]
        and str(row[f"{prefix}_title"]) == snapshot["title"]
        and str(row[f"{prefix}_description"]) == snapshot["description"]
        and str(row[f"{prefix}_status"]) == snapshot["status"]
        and str(row[f"{prefix}_priority"]) == snapshot["priority"]
        and row[f"{prefix}_assigned_to"] == snapshot["assigned_to"]
        and str(row[f"{prefix}_created_by"]) == snapshot["created_by"]
        and str(row[f"{prefix}_created_at"])
        == _snapshot_time_as_db(snapshot["created_at"])
        and str(row[f"{prefix}_updated_at"])
        == _snapshot_time_as_db(snapshot["updated_at"])
        and row[f"{prefix}_result"] == snapshot["result"]
        and metadata == snapshot["metadata"]
    )


def _mutation_row_is_exact(
    row: Any,
    *,
    transition: Any,
    receipt: dict[str, Any],
) -> bool:
    expected = receipt["expected_snapshot"]
    target = receipt["target_snapshot"]
    return bool(
        str(row["mutation_id"]) == str(transition["mutation_id"])
        and str(row["task_id"]) == receipt["task_id"]
        and str(row["schema_version"]) == EFFECT_MUTATION_SCHEMA
        and expected["depends_on"] == target["depends_on"]
        and expected["blocked_by"] == target["blocked_by"]
        and _mutation_side_is_exact(row, prefix="old", snapshot=expected)
        and _mutation_side_is_exact(row, prefix="new", snapshot=target)
    )


def _task_row_is_exact_target(
    row: Any,
    *,
    receipt: dict[str, Any],
    dependencies: list[str],
) -> bool:
    """Require the canonical task value or its durable history to attest it."""
    target = receipt["target_snapshot"]
    current_metadata = _load_json(row["metadata"])
    exact_target = bool(
        str(row["id"]) == receipt["task_id"] == target["id"]
        and str(row["title"]) == target["title"]
        and str(row["description"]) == target["description"]
        and str(row["status"]) == target["status"]
        and str(row["priority"]) == target["priority"]
        and row["assigned_to"] == target["assigned_to"]
        and str(row["created_by"]) == target["created_by"]
        and str(row["created_at"]) == _snapshot_time_as_db(target["created_at"])
        and str(row["updated_at"]) == _snapshot_time_as_db(target["updated_at"])
        and row["result"] == target["result"]
        and current_metadata == target["metadata"]
        and sorted(dependencies) == sorted(target["depends_on"])
        and target["blocked_by"] == []
    )
    if exact_target:
        return True
    # A later canonical Board transition may supersede the projected target
    # before runtime imports its receipt.  The projection remains attributable
    # only while its exact marker persists in canonical append-only history.
    target_metadata = target["metadata"]
    marker = target_metadata.get(GRAPH_PROJECTION_KEY)
    payload = receipt["effect_payload"]
    payload_marker = payload.get("marker")
    run_id = marker.get("run_id") if isinstance(marker, dict) else None
    target_history = target_metadata.get(GRAPH_PROJECTION_HISTORY_KEY)
    current_history = current_metadata.get(GRAPH_PROJECTION_HISTORY_KEY)
    return bool(
        receipt["effect_kind"] == GRAPH_PROJECTION_EFFECT_KIND
        and str(row["id"]) == receipt["task_id"] == target["id"]
        and isinstance(run_id, str)
        and bool(run_id)
        and receipt["effect_id"] == GRAPH_PROJECTION_EFFECT_PREFIX + run_id
        and set(payload) == {"schema_version", "intent_sha256", "marker"}
        and payload.get("schema_version") == GRAPH_PROJECTION_PAYLOAD_SCHEMA
        and payload.get("intent_sha256") == receipt["authority_sha256"]
        and payload_marker == marker
        and isinstance(target_history, dict)
        and target_history.get(run_id) == marker
        and isinstance(current_history, dict)
        and current_history.get(run_id) == marker
        and all(current_history.get(key) == value for key, value in target_history.items())
    )


async def load_effect_commit(
    db: aiosqlite.Connection,
    *,
    effect_id: str,
) -> dict[str, Any] | None:
    """Load and fully validate one immutable Board-local receipt."""
    db.row_factory = aiosqlite.Row
    await ensure_effect_commit_ledger(db)
    row = await (
        await db.execute(
            "SELECT * FROM task_board_effect_commits WHERE effect_id = ?",
            (effect_id,),
        )
    ).fetchone()
    transition = await (
        await db.execute(
            "SELECT * FROM task_board_effect_transitions WHERE effect_id = ?",
            (effect_id,),
        )
    ).fetchone()
    if row is None:
        if transition is not None:
            raise ValueError("TaskBoard effect transition lacks its receipt")
        return None
    receipt = _receipt_from_row(row)
    if transition is None or not _transition_row_is_exact(transition, receipt):
        raise ValueError("TaskBoard effect receipt lacks exact transition provenance")
    mutation = await (
        await db.execute(
            "SELECT * FROM task_board_effect_mutations WHERE mutation_id = ?",
            (str(transition["mutation_id"]),),
        )
    ).fetchone()
    if mutation is None or not _mutation_row_is_exact(
        mutation,
        transition=transition,
        receipt=receipt,
    ):
        raise ValueError("TaskBoard effect transition lacks exact task mutation")
    task_row = await (
        await db.execute("SELECT * FROM tasks WHERE id = ?", (receipt["task_id"],))
    ).fetchone()
    dependencies = [
        str(row[0])
        for row in await (
            await db.execute(
                "SELECT depends_on_id FROM task_dependencies WHERE task_id = ?",
                (receipt["task_id"],),
            )
        ).fetchall()
    ]
    if task_row is None or not _task_row_is_exact_target(
        task_row,
        receipt=receipt,
        dependencies=dependencies,
    ):
        raise ValueError("TaskBoard effect receipt target is not canonical")
    return receipt


def load_effect_commit_locked(
    db: sqlite3.Connection,
    *,
    effect_id: str,
) -> dict[str, Any] | None:
    """Validate one receipt from an already-locked canonical Board connection.

    This synchronous boundary is deliberately read-only: Board-only recovery
    must prove an effect from the same SQLite writer fence that supplied its
    census, and must never manufacture missing ledgers while evaluating proof.
    """
    db.row_factory = sqlite3.Row
    required = {
        "task_board_effect_commits",
        "task_board_effect_transitions",
        "task_board_effect_mutations",
    }
    present = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name IN (?, ?, ?)",
            tuple(sorted(required)),
        ).fetchall()
    }
    if not present:
        return None
    if present != required:
        raise ValueError("TaskBoard effect provenance ledger is incomplete")
    row = db.execute(
        "SELECT * FROM task_board_effect_commits WHERE effect_id = ?",
        (effect_id,),
    ).fetchone()
    transition = db.execute(
        "SELECT * FROM task_board_effect_transitions WHERE effect_id = ?",
        (effect_id,),
    ).fetchone()
    if row is None:
        if transition is not None:
            raise ValueError("TaskBoard effect transition lacks its receipt")
        return None
    receipt = _receipt_from_row(row)
    if transition is None or not _transition_row_is_exact(transition, receipt):
        raise ValueError("TaskBoard effect receipt lacks exact transition provenance")
    mutation = db.execute(
        "SELECT * FROM task_board_effect_mutations WHERE mutation_id = ?",
        (str(transition["mutation_id"]),),
    ).fetchone()
    if mutation is None or not _mutation_row_is_exact(
        mutation,
        transition=transition,
        receipt=receipt,
    ):
        raise ValueError("TaskBoard effect transition lacks exact task mutation")
    task_row = db.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (receipt["task_id"],),
    ).fetchone()
    dependencies = [
        str(row[0])
        for row in db.execute(
            "SELECT depends_on_id FROM task_dependencies WHERE task_id = ?",
            (receipt["task_id"],),
        ).fetchall()
    ]
    if task_row is None or not _task_row_is_exact_target(
        task_row,
        receipt=receipt,
        dependencies=dependencies,
    ):
        raise ValueError("TaskBoard effect receipt target is not canonical")
    return receipt


async def _append_effect_commit(
    board: Any,
    db: aiosqlite.Connection,
    *,
    transition: _LockedTaskTransition,
    effect_id: str,
    effect_kind: str,
    authority_sha256: str,
    expected: Any,
    target: Any,
    effect_payload: dict[str, Any],
    committed_at: datetime,
) -> dict[str, Any]:
    """Append a receipt after SQLite minted the exact transition provenance."""
    expected_snapshot = task_effect_snapshot(expected)
    target_snapshot = task_effect_snapshot(target)
    task_id = str(target_snapshot["id"])
    unsigned = {
        "schema_version": EFFECT_COMMIT_SCHEMA,
        "effect_id": effect_id,
        "effect_kind": effect_kind,
        "task_id": task_id,
        "authority_sha256": authority_sha256,
        "expected_snapshot": expected_snapshot,
        "target_snapshot": target_snapshot,
        "effect_payload": dict(effect_payload),
        "committed_at": _canonical_time(committed_at),
    }
    receipt = {**unsigned, "receipt_sha256": stable_sha256(unsigned)}
    if validate_effect_commit_receipt(receipt) is None:
        raise ValueError("TaskBoard effect commit receipt boundary is invalid")
    if transition != _LockedTaskTransition(
        connection_id=id(db),
        mutation_id=transition.mutation_id,
        effect_id=effect_id,
        task_id=task_id,
        expected_snapshot_sha256=stable_sha256(expected_snapshot),
        target_snapshot_sha256=stable_sha256(target_snapshot),
        receipt_sha256=receipt["receipt_sha256"],
    ):
        raise ValueError("TaskBoard effect receipt lacks its locked transition")
    row = await (
        await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    ).fetchone()
    deps = await board._fetch_deps(db, task_id)
    current = board._row_to_task(row, deps) if row is not None else None
    if current is None or task_effect_snapshot(current) != target_snapshot:
        raise ValueError("TaskBoard effect receipt target is not current")
    transition_row = await (
        await db.execute(
            "SELECT * FROM task_board_effect_transitions WHERE effect_id = ?",
            (effect_id,),
        )
    ).fetchone()
    mutation_row = await (
        await db.execute(
            "SELECT * FROM task_board_effect_mutations WHERE mutation_id = ?",
            (transition.mutation_id,),
        )
    ).fetchone()
    if (
        transition_row is None
        or not _transition_row_is_exact(transition_row, receipt)
        or str(transition_row["mutation_id"]) != transition.mutation_id
        or mutation_row is None
        or not _mutation_row_is_exact(
            mutation_row,
            transition=transition_row,
            receipt=receipt,
        )
    ):
        raise ValueError("TaskBoard effect receipt lacks its SQLite task mutation")
    existing_row = await (
        await db.execute(
            "SELECT * FROM task_board_effect_commits WHERE effect_id = ?",
            (effect_id,),
        )
    ).fetchone()
    if existing_row is not None:
        existing = _receipt_from_row(existing_row)
        if existing != receipt:
            raise ValueError("TaskBoard effect commit receipt conflicts")
        return existing
    await db.execute(
        "INSERT INTO task_board_effect_commits"
        " (effect_id, effect_kind, task_id, authority_sha256,"
        " expected_snapshot_sha256, expected_snapshot_json,"
        " target_snapshot_sha256, target_snapshot_json, effect_payload_sha256,"
        " effect_payload_json, committed_at, receipt_sha256, receipt_json,"
        " schema_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            effect_id,
            effect_kind,
            task_id,
            authority_sha256,
            stable_sha256(expected_snapshot),
            _canonical_json(expected_snapshot),
            stable_sha256(target_snapshot),
            _canonical_json(target_snapshot),
            stable_sha256(effect_payload),
            _canonical_json(effect_payload),
            _canonical_time(committed_at),
            receipt["receipt_sha256"],
            _canonical_json(receipt),
            EFFECT_COMMIT_SCHEMA,
        ),
    )
    loaded = await load_effect_commit(db, effect_id=effect_id)
    if loaded != receipt:
        raise ValueError("TaskBoard effect commit did not retain exact provenance")
    return loaded


async def commit_locked_task_effect(
    board: Any,
    db: aiosqlite.Connection,
    expected: Any,
    *,
    status: str,
    assigned_to: str | None,
    result: str | None,
    metadata: dict[str, Any],
    effect_id: str,
    effect_kind: str,
    authority_sha256: str,
    effect_payload: dict[str, Any],
    committed_at: datetime,
    target_updated_at: datetime | None = None,
) -> Any | None:
    """Update an exact locked Task and append its receipt without committing."""
    db.row_factory = aiosqlite.Row
    await ensure_effect_commit_ledger(db)
    predecessor_row = await (
        await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
    ).fetchone()
    predecessor_deps = await board._fetch_deps(db, expected.id)
    predecessor = (
        board._row_to_task(predecessor_row, predecessor_deps)
        if predecessor_row is not None
        else None
    )
    if predecessor != expected:
        return None
    expected_snapshot = task_effect_snapshot(predecessor)
    target_time = target_updated_at or committed_at
    target_snapshot = {
        **expected_snapshot,
        "status": status,
        "assigned_to": assigned_to,
        "result": result,
        "metadata": dict(metadata),
        "updated_at": _canonical_time(target_time),
    }
    unsigned = {
        "schema_version": EFFECT_COMMIT_SCHEMA,
        "effect_id": effect_id,
        "effect_kind": effect_kind,
        "task_id": expected.id,
        "authority_sha256": authority_sha256,
        "expected_snapshot": expected_snapshot,
        "target_snapshot": target_snapshot,
        "effect_payload": dict(effect_payload),
        "committed_at": _canonical_time(committed_at),
    }
    receipt = {**unsigned, "receipt_sha256": stable_sha256(unsigned)}
    if validate_effect_commit_receipt(receipt) is None:
        raise ValueError("TaskBoard effect commit receipt boundary is invalid")
    mutation_id = "tbm_" + secrets.token_hex(32)
    await db.execute(
        "INSERT INTO task_board_effect_transition_arms"
        " (mutation_id, effect_id, task_id, expected_snapshot_sha256,"
        " target_snapshot_sha256, receipt_sha256, transitioned_at, schema_version)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mutation_id,
            effect_id,
            expected.id,
            stable_sha256(expected_snapshot),
            stable_sha256(target_snapshot),
            receipt["receipt_sha256"],
            _canonical_time(committed_at),
            EFFECT_TRANSITION_SCHEMA,
        ),
    )
    cursor = await db.execute(
        "UPDATE tasks SET status = ?, assigned_to = ?, result = ?, metadata = ?,"
        " updated_at = ? WHERE id = ? AND status = ? AND assigned_to IS ?"
        " AND result IS ? AND metadata = ? AND updated_at = ?",
        (
            status,
            assigned_to,
            result,
            board._coerce_db_value("metadata", metadata),
            target_time.isoformat(),
            expected.id,
            getattr(expected.status, "value", str(expected.status)),
            expected.assigned_to,
            expected.result,
            board._coerce_db_value("metadata", expected.metadata),
            expected.updated_at.isoformat(),
        ),
    )
    if cursor.rowcount != 1:
        await db.execute(
            "DELETE FROM task_board_effect_transition_arms WHERE mutation_id = ?",
            (mutation_id,),
        )
        return None
    row = await (
        await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
    ).fetchone()
    deps = await board._fetch_deps(db, expected.id)
    target = board._row_to_task(row, deps) if row is not None else None
    if target is None:
        raise ValueError("TaskBoard exact effect lost its target row")
    observed_target_snapshot = task_effect_snapshot(target)
    if observed_target_snapshot != target_snapshot:
        raise ValueError("TaskBoard exact effect target differs from its armed mutation")
    unconsumed_arm = await (
        await db.execute(
            "SELECT 1 FROM task_board_effect_transition_arms WHERE mutation_id = ?",
            (mutation_id,),
        )
    ).fetchone()
    if unconsumed_arm is not None:
        raise ValueError("TaskBoard exact effect did not consume its mutation arm")
    transition = _LockedTaskTransition(
        connection_id=id(db),
        mutation_id=mutation_id,
        effect_id=effect_id,
        task_id=expected.id,
        expected_snapshot_sha256=stable_sha256(expected_snapshot),
        target_snapshot_sha256=stable_sha256(target_snapshot),
        receipt_sha256=receipt["receipt_sha256"],
    )
    await _append_effect_commit(
        board,
        db,
        transition=transition,
        effect_id=effect_id,
        effect_kind=effect_kind,
        authority_sha256=authority_sha256,
        expected=expected,
        target=target,
        effect_payload=effect_payload,
        committed_at=committed_at,
    )
    return target


async def compare_and_swap_task_effect(
    board: Any,
    expected: Any,
    *,
    status: str,
    assigned_to: str | None,
    result: str | None,
    metadata: dict[str, Any],
    effect_id: str,
    effect_kind: str,
    authority_sha256: str,
    effect_payload: dict[str, Any],
    authorize: Callable[[Any], Awaitable[bool]],
    committed_at: datetime,
    target_updated_at: datetime | None = None,
) -> Any | None:
    """Public exact Board CAS + receipt transaction for governed effects."""
    async with board._open() as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (
            await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
        ).fetchone()
        deps = await board._fetch_deps(db, expected.id)
        observed = board._row_to_task(row, deps) if row is not None else None
        if observed != expected:
            await db.rollback()
            return None
        if not await authorize(observed):
            await db.rollback()
            raise ValueError("TaskBoard effect lacks exact durable authority")
        try:
            target = await commit_locked_task_effect(
                board,
                db,
                observed,
                status=status,
                assigned_to=assigned_to,
                result=result,
                metadata=metadata,
                effect_id=effect_id,
                effect_kind=effect_kind,
                authority_sha256=authority_sha256,
                effect_payload=effect_payload,
                committed_at=committed_at,
                target_updated_at=target_updated_at,
            )
            if target is None:
                await db.rollback()
                return None
            await db.commit()
            return target
        except Exception:
            await db.rollback()
            raise


async def load_board_effect_commit(
    board: Any,
    *,
    effect_id: str,
) -> dict[str, Any] | None:
    """Read one receipt through a concrete Board's guarded connection."""
    async with board._open() as db:
        receipt = await load_effect_commit(db, effect_id=effect_id)
        await db.commit()
        return receipt


def graph_projection_effect_id(run_id: str) -> str:
    return GRAPH_PROJECTION_EFFECT_PREFIX + run_id


__all__ = [
    "AUTHORITATIVE_PROJECTION_COMMIT_MODE",
    "GRAPH_PROJECTION_EFFECT_KIND",
    "GRAPH_PROJECTION_PAYLOAD_SCHEMA",
    "NON_PRODUCTION_PROJECTION_COMMIT_MODE",
    "commit_locked_task_effect",
    "compare_and_swap_task_effect",
    "ensure_effect_commit_ledger",
    "graph_projection_effect_id",
    "load_board_effect_commit",
    "load_effect_commit",
    "load_effect_commit_locked",
    "task_effect_snapshot",
    "validate_effect_commit_receipt",
]
