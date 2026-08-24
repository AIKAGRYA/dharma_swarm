"""Immutable pre-effect targets and exact-readback witnesses for Board replay."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiosqlite

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board_effect_commit import (
    GRAPH_PROJECTION_EFFECT_KIND,
    GRAPH_PROJECTION_PAYLOAD_SCHEMA,
    graph_projection_effect_id,
    load_board_effect_commit,
    validate_effect_commit_receipt,
)
from dharma_swarm.task_board_projection_intent import (
    GRAPH_PROJECTION_HISTORY_KEY,
    GRAPH_PROJECTION_KEY,
    TASK_BOARD_PROJECTION_INTENT_KEY,
    is_aware_iso8601,
    stable_sha256,
)

TARGET_SCHEMA = "dharma.graph.task_board_projection_target.v1"
WITNESS_SCHEMA = "dharma.graph.task_board_projection_target_witness.v1"
ATOMIC_COMMIT_WITNESS_SCHEMA = (
    "dharma.graph.task_board_atomic_projection_commit_witness.v1"
)
_SNAPSHOT_FIELDS = frozenset(
    {"task_id", "status", "assigned_to", "result", "metadata"}
)


@dataclass(frozen=True)
class ProjectionTargetProof:
    """One immutable before/after projection value prepared before Board CAS."""

    run_id: str
    task_id: str
    intent_sha256: str
    expected_snapshot: dict[str, Any]
    target_snapshot: dict[str, Any]
    marker: dict[str, Any]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load_json(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def task_projection_snapshot(task: Any) -> dict[str, Any]:
    """Return every Board value changed by terminal projection CAS."""
    status = getattr(getattr(task, "status", None), "value", getattr(task, "status", None))
    return {
        "task_id": str(getattr(task, "id", "")),
        "status": status,
        "assigned_to": getattr(task, "assigned_to", None),
        "result": getattr(task, "result", None),
        "metadata": dict(getattr(task, "metadata", {}) or {}),
    }


def target_projection_snapshot(
    expected: Any,
    *,
    intent: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    action = intent["action"]
    status = (
        "pending"
        if action in {"retry", "requeue"}
        else "completed"
        if action == "receipt" and intent["run_status"] == "completed"
        else "failed"
    )
    return {
        "task_id": str(getattr(expected, "id", "")),
        "status": status,
        "assigned_to": (
            None if action in {"retry", "requeue"} else intent["agent_id"]
        ),
        "result": intent["result"],
        "metadata": dict(metadata),
    }


def _derived_target_snapshot(
    expected: dict[str, Any],
    *,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> dict[str, Any] | None:
    metadata = expected.get("metadata")
    metadata_set = intent.get("metadata_set")
    metadata_remove = intent.get("metadata_remove")
    if not (
        set(expected) == _SNAPSHOT_FIELDS
        and isinstance(metadata, dict)
        and isinstance(metadata_set, dict)
        and isinstance(metadata_remove, list)
    ):
        return None
    target_metadata = dict(metadata)
    for key in metadata_remove:
        target_metadata.pop(key, None)
    target_metadata.update(metadata_set)
    if intent.get("action") in {"receipt", "retry"}:
        target_metadata["task_board_completion_binding"] = dict(
            intent["completion_binding"]
        )
    history = target_metadata.get(GRAPH_PROJECTION_HISTORY_KEY, {})
    if not isinstance(history, dict):
        return None
    history = dict(history)
    prior = target_metadata.get(GRAPH_PROJECTION_KEY)
    if prior is not None:
        if not isinstance(prior, dict):
            return None
        prior_run_id = prior.get("run_id")
        if not isinstance(prior_run_id, str) or not prior_run_id:
            return None
        historical = history.get(prior_run_id)
        if historical is not None and historical != prior:
            return None
        history[prior_run_id] = prior
    existing = history.get(intent["run_id"])
    if existing is not None and existing != marker:
        return None
    history[intent["run_id"]] = marker
    target_metadata[GRAPH_PROJECTION_KEY] = marker
    target_metadata[GRAPH_PROJECTION_HISTORY_KEY] = history
    action = intent["action"]
    return {
        "task_id": expected["task_id"],
        "status": (
            "pending"
            if action in {"retry", "requeue"}
            else "completed"
            if action == "receipt" and intent["run_status"] == "completed"
            else "failed"
        ),
        "assigned_to": (
            None if action in {"retry", "requeue"} else intent["agent_id"]
        ),
        "result": intent["result"],
        "metadata": target_metadata,
    }


def _projection_from_full_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": snapshot.get("id"),
        "status": snapshot.get("status"),
        "assigned_to": snapshot.get("assigned_to"),
        "result": snapshot.get("result"),
        "metadata": snapshot.get("metadata"),
    }


def validate_atomic_graph_projection_commit(
    raw: Any,
    *,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> dict[str, Any] | None:
    """Prove a Board-local receipt is the exact ProjectionIntent effect."""
    receipt = validate_effect_commit_receipt(raw)
    if receipt is None:
        return None
    expected = receipt["expected_snapshot"]
    target = receipt["target_snapshot"]
    expected_projection = _projection_from_full_snapshot(expected)
    target_projection = _projection_from_full_snapshot(target)
    derived_target = _derived_target_snapshot(
        expected_projection,
        intent=intent,
        marker=marker,
    )
    unchanged_fields = set(expected) - {
        "status",
        "assigned_to",
        "result",
        "metadata",
        "updated_at",
    }
    payload = {
        "schema_version": GRAPH_PROJECTION_PAYLOAD_SCHEMA,
        "intent_sha256": intent["intent_sha256"],
        "marker": marker,
    }
    return (
        receipt
        if (
            receipt["effect_id"] == graph_projection_effect_id(intent["run_id"])
            and receipt["effect_kind"] == GRAPH_PROJECTION_EFFECT_KIND
            and receipt["task_id"] == intent["task_id"]
            and receipt["authority_sha256"] == intent["intent_sha256"]
            and receipt["effect_payload"] == payload
            and target_projection == derived_target
            and target.get("updated_at") == receipt["committed_at"]
            and all(expected.get(key) == target.get(key) for key in unchanged_fields)
        )
        else None
    )


async def ensure_projection_proof_ledger(db: aiosqlite.Connection) -> None:
    """Create immutable target and witness ledgers."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_projection_targets ("
        "run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL"
        " UNIQUE, expected_snapshot_sha256 TEXT NOT NULL,"
        " expected_snapshot_json TEXT NOT NULL, target_snapshot_sha256 TEXT NOT NULL,"
        " target_snapshot_json TEXT NOT NULL, marker_sha256 TEXT NOT NULL,"
        " marker_json TEXT NOT NULL, prepared_at TEXT NOT NULL,"
        " schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_projection_target_no_update "
        "BEFORE UPDATE ON task_board_projection_targets BEGIN SELECT RAISE(ABORT,"
        " 'task board projection target is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_projection_target_no_delete "
        "BEFORE DELETE ON task_board_projection_targets BEGIN SELECT RAISE(ABORT,"
        " 'task board projection target is immutable'); END"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_projection_target_witnesses ("
        "run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL"
        " UNIQUE, target_snapshot_sha256 TEXT NOT NULL,"
        " target_snapshot_json TEXT NOT NULL, marker_sha256 TEXT NOT NULL,"
        " marker_json TEXT NOT NULL, witnessed_at TEXT NOT NULL,"
        " schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_projection_target_witness_no_update "
        "BEFORE UPDATE ON task_board_projection_target_witnesses BEGIN SELECT RAISE("
        "ABORT, 'task board projection target witness is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_projection_target_witness_no_delete "
        "BEFORE DELETE ON task_board_projection_target_witnesses BEGIN SELECT RAISE("
        "ABORT, 'task board projection target witness is immutable'); END"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_atomic_projection_witnesses ("
        "run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL"
        " UNIQUE, marker_sha256 TEXT NOT NULL, marker_json TEXT NOT NULL,"
        " board_receipt_sha256 TEXT NOT NULL UNIQUE, board_receipt_json TEXT NOT NULL,"
        " witnessed_at TEXT NOT NULL, schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_atomic_projection_witness_no_update "
        "BEFORE UPDATE ON task_board_atomic_projection_witnesses BEGIN SELECT RAISE("
        "ABORT, 'task board atomic projection witness is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_atomic_projection_witness_no_delete "
        "BEFORE DELETE ON task_board_atomic_projection_witnesses BEGIN SELECT RAISE("
        "ABORT, 'task board atomic projection witness is immutable'); END"
    )


def _proof_from_row(
    row: aiosqlite.Row,
    *,
    run_id: str,
    task_id: str,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> ProjectionTargetProof:
    expected = _load_json(row["expected_snapshot_json"])
    target = _load_json(row["target_snapshot_json"])
    stored_marker = _load_json(row["marker_json"])
    derived_target = _derived_target_snapshot(
        expected,
        intent=intent,
        marker=marker,
    )
    if not (
        str(row["run_id"]) == run_id
        and str(row["task_id"]) == task_id
        and str(row["intent_sha256"]) == intent["intent_sha256"]
        and str(row["expected_snapshot_sha256"]) == stable_sha256(expected)
        and str(row["target_snapshot_sha256"]) == stable_sha256(target)
        and str(row["marker_sha256"]) == stable_sha256(stored_marker)
        and str(row["schema_version"]) == TARGET_SCHEMA
        and is_aware_iso8601(str(row["prepared_at"]))
        and str(row["expected_snapshot_json"]) == _canonical_json(expected)
        and str(row["target_snapshot_json"]) == _canonical_json(target)
        and str(row["marker_json"]) == _canonical_json(stored_marker)
        and expected.get("task_id") == task_id
        and target.get("task_id") == task_id
        and stored_marker == marker
        and target == derived_target
    ):
        raise RuntimeError("projection target ledger conflicts")
    return ProjectionTargetProof(
        run_id=run_id,
        task_id=task_id,
        intent_sha256=intent["intent_sha256"],
        expected_snapshot=expected,
        target_snapshot=target,
        marker=stored_marker,
    )


async def load_projection_target(
    runtime_state: RuntimeStateStore,
    *,
    run_id: str,
    task_id: str,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> ProjectionTargetProof | None:
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await ensure_projection_proof_ledger(db)
        await db.commit()
        row = await (
            await db.execute(
                "SELECT * FROM task_board_projection_targets WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
    if row is None:
        return None
    return _proof_from_row(
        row,
        run_id=run_id,
        task_id=task_id,
        intent=intent,
        marker=marker,
    )


async def prepare_projection_target(
    runtime_state: RuntimeStateStore,
    *,
    run_id: str,
    task_id: str,
    intent: dict[str, Any],
    marker: dict[str, Any],
    expected: Any,
    target_metadata: dict[str, Any],
    now: datetime,
) -> ProjectionTargetProof:
    """Durably seal the exact expected and target Board values before CAS."""
    expected_snapshot = task_projection_snapshot(expected)
    target_snapshot = target_projection_snapshot(
        expected,
        intent=intent,
        metadata=target_metadata,
    )
    encoded_expected = _canonical_json(expected_snapshot)
    encoded_target = _canonical_json(target_snapshot)
    encoded_marker = _canonical_json(marker)
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await ensure_projection_proof_ledger(db)
        run_row = await (
            await db.execute(
                "SELECT assigned_by, metadata_json FROM delegation_runs"
                " WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
        durable_intent = (
            _load_json(run_row["metadata_json"]).get(TASK_BOARD_PROJECTION_INTENT_KEY)
            if run_row is not None
            else None
        )
        if (
            run_row is None
            or str(run_row["assigned_by"] or "") != "orchestrator"
            or durable_intent != intent
        ):
            await db.rollback()
            raise RuntimeError("projection target lost exact runtime intent")
        row = await (
            await db.execute(
                "SELECT * FROM task_board_projection_targets WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO task_board_projection_targets"
                " (run_id, task_id, intent_sha256, expected_snapshot_sha256,"
                " expected_snapshot_json, target_snapshot_sha256,"
                " target_snapshot_json, marker_sha256, marker_json, prepared_at,"
                " schema_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    task_id,
                    intent["intent_sha256"],
                    stable_sha256(expected_snapshot),
                    encoded_expected,
                    stable_sha256(target_snapshot),
                    encoded_target,
                    stable_sha256(marker),
                    encoded_marker,
                    now.isoformat(),
                    TARGET_SCHEMA,
                ),
            )
            row = await (
                await db.execute(
                    "SELECT * FROM task_board_projection_targets WHERE run_id = ?",
                    (run_id,),
                )
            ).fetchone()
        assert row is not None
        proof = _proof_from_row(
            row,
            run_id=run_id,
            task_id=task_id,
            intent=intent,
            marker=marker,
        )
        if (
            proof.expected_snapshot != expected_snapshot
            or proof.target_snapshot != target_snapshot
        ):
            await db.rollback()
            raise RuntimeError("projection target was already prepared differently")
        await db.commit()
        return proof


def _witness_row_is_exact(row: aiosqlite.Row, proof: ProjectionTargetProof) -> bool:
    target = _load_json(row["target_snapshot_json"])
    marker = _load_json(row["marker_json"])
    return bool(
        str(row["run_id"]) == proof.run_id
        and str(row["task_id"]) == proof.task_id
        and str(row["intent_sha256"]) == proof.intent_sha256
        and str(row["target_snapshot_sha256"])
        == stable_sha256(proof.target_snapshot)
        and target == proof.target_snapshot
        and str(row["marker_sha256"]) == stable_sha256(proof.marker)
        and marker == proof.marker
        and str(row["target_snapshot_json"])
        == _canonical_json(proof.target_snapshot)
        and str(row["marker_json"]) == _canonical_json(proof.marker)
        and str(row["schema_version"]) == WITNESS_SCHEMA
        and is_aware_iso8601(str(row["witnessed_at"]))
    )


def _atomic_witness_row_is_exact(
    row: aiosqlite.Row,
    *,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> bool:
    stored_marker = _load_json(row["marker_json"])
    receipt = _load_json(row["board_receipt_json"])
    valid_receipt = validate_atomic_graph_projection_commit(
        receipt,
        intent=intent,
        marker=marker,
    )
    return bool(
        str(row["run_id"]) == intent["run_id"]
        and str(row["task_id"]) == intent["task_id"]
        and str(row["intent_sha256"]) == intent["intent_sha256"]
        and stored_marker == marker
        and str(row["marker_sha256"]) == stable_sha256(marker)
        and str(row["marker_json"]) == _canonical_json(marker)
        and valid_receipt is not None
        and str(row["board_receipt_sha256"])
        == valid_receipt["receipt_sha256"]
        and str(row["board_receipt_json"]) == _canonical_json(valid_receipt)
        and is_aware_iso8601(str(row["witnessed_at"]))
        and str(row["schema_version"]) == ATOMIC_COMMIT_WITNESS_SCHEMA
    )


async def append_atomic_projection_witness(
    runtime_state: RuntimeStateStore,
    *,
    task_board: Any,
    board_receipt: dict[str, Any],
    intent: dict[str, Any],
    marker: dict[str, Any],
    now: datetime,
) -> None:
    """Import one exact atomic Board commit into the runtime witness ledger."""
    authoritative = await load_board_effect_commit(
        task_board,
        effect_id=graph_projection_effect_id(intent["run_id"]),
    )
    if (
        authoritative is None
        or _canonical_json(authoritative) != _canonical_json(board_receipt)
    ):
        raise RuntimeError("atomic witness receipt is not Board-authoritative")
    receipt = validate_atomic_graph_projection_commit(
        authoritative,
        intent=intent,
        marker=marker,
    )
    if receipt is None:
        raise RuntimeError("Board projection commit receipt is not exact")
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await ensure_projection_proof_ledger(db)
        run_row = await (
            await db.execute(
                "SELECT assigned_by, metadata_json FROM delegation_runs"
                " WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
        durable_intent = (
            _load_json(run_row["metadata_json"]).get(TASK_BOARD_PROJECTION_INTENT_KEY)
            if run_row is not None
            else None
        )
        if (
            run_row is None
            or str(run_row["assigned_by"] or "") != "orchestrator"
            or durable_intent != intent
        ):
            await db.rollback()
            raise RuntimeError("atomic Board witness lost exact runtime intent")
        row = await (
            await db.execute(
                "SELECT * FROM task_board_atomic_projection_witnesses"
                " WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO task_board_atomic_projection_witnesses"
                " (run_id, task_id, intent_sha256, marker_sha256, marker_json,"
                " board_receipt_sha256, board_receipt_json, witnessed_at,"
                " schema_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    intent["run_id"],
                    intent["task_id"],
                    intent["intent_sha256"],
                    stable_sha256(marker),
                    _canonical_json(marker),
                    receipt["receipt_sha256"],
                    _canonical_json(receipt),
                    now.isoformat(),
                    ATOMIC_COMMIT_WITNESS_SCHEMA,
                ),
            )
        elif not _atomic_witness_row_is_exact(
            row,
            intent=intent,
            marker=marker,
        ):
            await db.rollback()
            raise RuntimeError("atomic Board projection witness conflicts")
        await db.commit()


async def load_exact_atomic_projection_witness(
    runtime_state: RuntimeStateStore,
    *,
    intent: dict[str, Any],
    marker: dict[str, Any],
    expected_board_receipt: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return the exact atomic witness receipt, optionally Board-bound."""
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await ensure_projection_proof_ledger(db)
        await db.commit()
        row = await (
            await db.execute(
                "SELECT * FROM task_board_atomic_projection_witnesses"
                " WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
    if row is None:
        return None
    if not _atomic_witness_row_is_exact(row, intent=intent, marker=marker):
        raise RuntimeError("atomic Board projection witness ledger conflicts")
    receipt = _load_json(row["board_receipt_json"])
    if expected_board_receipt is not None:
        expected = validate_atomic_graph_projection_commit(
            expected_board_receipt,
            intent=intent,
            marker=marker,
        )
        if (
            expected is None
            or receipt != expected
            or str(row["board_receipt_json"]) != _canonical_json(expected)
        ):
            raise RuntimeError("atomic witness differs from canonical Board receipt")
    return receipt


async def has_exact_atomic_projection_witness(
    runtime_state: RuntimeStateStore,
    *,
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> bool:
    return (
        await load_exact_atomic_projection_witness(
            runtime_state,
            intent=intent,
            marker=marker,
        )
        is not None
    )


async def has_exact_projection_witness(
    runtime_state: RuntimeStateStore,
    *,
    proof: ProjectionTargetProof,
) -> bool:
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await ensure_projection_proof_ledger(db)
        await db.commit()
        row = await (
            await db.execute(
                "SELECT * FROM task_board_projection_target_witnesses"
                " WHERE run_id = ?",
                (proof.run_id,),
            )
        ).fetchone()
    if row is None:
        return False
    if not _witness_row_is_exact(row, proof):
        raise RuntimeError("projection target witness ledger conflicts")
    return True


async def append_exact_projection_witness(
    runtime_state: RuntimeStateStore,
    *,
    proof: ProjectionTargetProof,
    observed: Any,
    intent: dict[str, Any],
    now: datetime,
) -> None:
    """Append evidence only after an exact target Board readback."""
    observed_snapshot = task_projection_snapshot(observed)
    if observed_snapshot != proof.target_snapshot:
        raise RuntimeError("projection witness lacks exact target readback")
    encoded_target = _canonical_json(proof.target_snapshot)
    encoded_marker = _canonical_json(proof.marker)
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await ensure_projection_proof_ledger(db)
        run_row = await (
            await db.execute(
                "SELECT assigned_by, metadata_json FROM delegation_runs"
                " WHERE run_id = ?",
                (proof.run_id,),
            )
        ).fetchone()
        durable_intent = (
            _load_json(run_row["metadata_json"]).get(TASK_BOARD_PROJECTION_INTENT_KEY)
            if run_row is not None
            else None
        )
        if (
            run_row is None
            or str(run_row["assigned_by"] or "") != "orchestrator"
            or durable_intent != intent
        ):
            await db.rollback()
            raise RuntimeError("projection witness lost exact runtime intent")
        target_row = await (
            await db.execute(
                "SELECT * FROM task_board_projection_targets WHERE run_id = ?",
                (proof.run_id,),
            )
        ).fetchone()
        if target_row is None:
            await db.rollback()
            raise RuntimeError("projection witness lacks prepared target")
        durable_proof = _proof_from_row(
            target_row,
            run_id=proof.run_id,
            task_id=proof.task_id,
            intent=intent,
            marker=proof.marker,
        )
        if durable_proof != proof:
            await db.rollback()
            raise RuntimeError("projection witness target changed")
        row = await (
            await db.execute(
                "SELECT * FROM task_board_projection_target_witnesses"
                " WHERE run_id = ?",
                (proof.run_id,),
            )
        ).fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO task_board_projection_target_witnesses"
                " (run_id, task_id, intent_sha256, target_snapshot_sha256,"
                " target_snapshot_json, marker_sha256, marker_json, witnessed_at,"
                " schema_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proof.run_id,
                    proof.task_id,
                    proof.intent_sha256,
                    stable_sha256(proof.target_snapshot),
                    encoded_target,
                    stable_sha256(proof.marker),
                    encoded_marker,
                    now.isoformat(),
                    WITNESS_SCHEMA,
                ),
            )
        elif not _witness_row_is_exact(row, proof):
            await db.rollback()
            raise RuntimeError("projection target witness ledger conflicts")
        await db.commit()


__all__ = [
    "ProjectionTargetProof",
    "append_exact_projection_witness",
    "append_atomic_projection_witness",
    "ensure_projection_proof_ledger",
    "has_exact_atomic_projection_witness",
    "has_exact_projection_witness",
    "load_exact_atomic_projection_witness",
    "load_projection_target",
    "prepare_projection_target",
    "task_projection_snapshot",
    "validate_atomic_graph_projection_commit",
]
