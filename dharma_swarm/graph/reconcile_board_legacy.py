"""Exact, replayable TaskBoard settlement for non-campaign legacy runs.

Legacy runtime rows lack campaign-grade execution identity. They may settle a
Board attempt only when the pre-terminal census captured one complete,
versioned Task whose active claim closes over the runtime claim. Runtime seals
the full predecessor and target; TaskBoard then commits the exact CAS and an
immutable effect receipt in one local transaction before runtime may ACK it.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import aiosqlite

from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board_campaign_guard import campaign_metadata_bound
from dharma_swarm.task_board_effect_commit import (
    AUTHORITATIVE_PROJECTION_COMMIT_MODE,
    commit_locked_task_effect,
    load_board_effect_commit,
    load_effect_commit,
    task_effect_snapshot,
    validate_effect_commit_receipt,
)
from dharma_swarm.task_board_projection_intent import (
    is_aware_iso8601,
    is_sha256_hex,
    stable_sha256,
)

LEGACY_SETTLEMENT_INTENT_SCHEMA = "dharma.graph.legacy_board_settlement_intent.v2"
LEGACY_SETTLEMENT_ACK_SCHEMA = "dharma.graph.legacy_board_settlement_ack.v2"
LEGACY_SETTLEMENT_EFFECT_KIND = "dharma.graph.legacy_board_settlement.v1"
LEGACY_SETTLEMENT_EFFECT_PAYLOAD_SCHEMA = (
    "dharma.graph.legacy_board_settlement_commit_payload.v1"
)
LEGACY_SETTLEMENT_AUTHORITY_SCHEMA = (
    "dharma.graph.legacy_board_settlement_authority.v1"
)
LEGACY_SETTLEMENT_EFFECT_PREFIX = "graph_legacy_settlement:"
LEGACY_SETTLEMENT_PROOF_MODE = "task_board_atomic_effect_commit.v1"

WEAK_TEST_INTENT_SCHEMA = "dharma.graph.legacy_board_settlement_test_intent.v1"
WEAK_TEST_ACK_SCHEMA = "dharma.graph.legacy_board_settlement_test_ack.v1"
WEAK_TEST_PROOF_MODE = "explicit_nonproduction_test_double.v1"
WEAK_TEST_BOARD_MODE_ATTRIBUTE = "legacy_settlement_test_mode"

_INTENT_FIELDS = frozenset(
    "schema_version run_id task_id claim_id agent_id action predecessor_snapshot "
    "target_snapshot result metadata_set metadata_remove authority_sha256 effect_id "
    "effect_kind effect_payload prepared_at intent_sha256".split()
)
_WEAK_INTENT_FIELDS = frozenset(
    "schema_version run_id task_id action target_status target_assigned_to result "
    "metadata_set proof_mode prepared_at intent_sha256".split()
)
_SNAPSHOT_FIELDS = frozenset(
    {
        "id", "title", "description", "status", "priority", "assigned_to",
        "created_by", "created_at", "updated_at", "depends_on", "blocked_by",
        "result", "metadata",
    }
)
_CAMPAIGN_SHAPE_KEYS = frozenset(
    {
        "mission_campaign_authority", "mission_control_governance",
        "campaign_dispatch_recovery", "campaign_dispatch_attempt_history",
        "attempt_generation",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _append_error(report: Any, value: str) -> None:
    errors = getattr(report, "errors", None)
    if isinstance(errors, list) and value not in errors:
        errors.append(value)


def authoritative_effect_board(board: Any) -> bool:
    from dharma_swarm.task_board import TaskBoard

    return bool(
        isinstance(board, TaskBoard)
        and getattr(board, "projection_commit_mode", None)
        == AUTHORITATIVE_PROJECTION_COMMIT_MODE
        and callable(getattr(board, "_open", None))
        and callable(getattr(board, "_fetch_deps", None))
        and callable(getattr(board, "_row_to_task", None))
        and callable(getattr(board, "_coerce_db_value", None))
    )


def explicit_weak_test_board(board: Any) -> bool:
    return bool(
        not authoritative_effect_board(board)
        and getattr(board, WEAK_TEST_BOARD_MODE_ATTRIBUTE, None)
        == WEAK_TEST_PROOF_MODE
    )


async def ensure_legacy_settlement_ledger(db: aiosqlite.Connection) -> None:
    await db.execute(
        "CREATE TABLE IF NOT EXISTS legacy_task_board_settlement_intents ("
        "run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL"
        " UNIQUE, intent_json TEXT NOT NULL, prepared_at TEXT NOT NULL,"
        " schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS legacy_board_intent_no_update "
        "BEFORE UPDATE ON legacy_task_board_settlement_intents BEGIN SELECT "
        "RAISE(ABORT, 'legacy board settlement intent is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS legacy_board_intent_no_delete "
        "BEFORE DELETE ON legacy_task_board_settlement_intents BEGIN SELECT "
        "RAISE(ABORT, 'legacy board settlement intent is immutable'); END"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS legacy_task_board_settlement_acks ("
        "run_id TEXT PRIMARY KEY, intent_sha256 TEXT NOT NULL UNIQUE,"
        "effect_receipt_sha256 TEXT NOT NULL, effect_receipt_json TEXT NOT NULL,"
        "proof_mode TEXT NOT NULL, acknowledged_at TEXT NOT NULL,"
        "schema_version TEXT NOT NULL)"
    )
    for name in ("effect_receipt_sha256", "effect_receipt_json", "proof_mode"):
        try:
            await db.execute(
                f"SELECT {name} FROM legacy_task_board_settlement_acks LIMIT 0"
            )
        except aiosqlite.Error:
            await db.execute(
                f"ALTER TABLE legacy_task_board_settlement_acks ADD COLUMN {name} "
                "TEXT NOT NULL DEFAULT ''"
            )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS legacy_board_ack_no_update "
        "BEFORE UPDATE ON legacy_task_board_settlement_acks BEGIN SELECT "
        "RAISE(ABORT, 'legacy board settlement ack is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS legacy_board_ack_no_delete "
        "BEFORE DELETE ON legacy_task_board_settlement_acks BEGIN SELECT "
        "RAISE(ABORT, 'legacy board settlement ack is immutable'); END"
    )


def _snapshot_valid(raw: Any, *, task_id: str) -> bool:
    return bool(
        isinstance(raw, dict)
        and set(raw) == _SNAPSHOT_FIELDS
        and raw.get("id") == task_id
        and isinstance(raw.get("metadata"), dict)
        and isinstance(raw.get("depends_on"), list)
        and all(isinstance(value, str) and value for value in raw["depends_on"])
        and isinstance(raw.get("blocked_by"), list)
        and all(isinstance(value, str) and value for value in raw["blocked_by"])
        and is_aware_iso8601(raw.get("created_at"))
        and is_aware_iso8601(raw.get("updated_at"))
    )


def _legacy_predecessor_is_exact(
    snapshot: dict[str, Any],
    *,
    run_id: str,
    claim_id: str,
    agent_id: str,
) -> bool:
    metadata = snapshot["metadata"]
    active_claim = metadata.get("active_claim")
    return bool(
        snapshot.get("status") in {"assigned", "running"}
        and snapshot.get("assigned_to") == agent_id
        and isinstance(active_claim, dict)
        and active_claim.get("claim_id") == claim_id
        and active_claim.get("agent_id") == agent_id
        and not campaign_metadata_bound(metadata)
        and not any(key in metadata for key in _CAMPAIGN_SHAPE_KEYS)
        and all(
            key not in metadata or metadata.get(key) == value
            for key, value in {
                "run_id": run_id,
                "runtime_run_id": run_id,
                "claim_id": claim_id,
                "agent_id": agent_id,
            }.items()
        )
    )


def _target_status(action: str) -> str | None:
    return {
        "requeue": "pending",
        "complete": "completed",
        "fail": "failed",
    }.get(action)


def _authority_payload(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": LEGACY_SETTLEMENT_AUTHORITY_SCHEMA,
        "authority_kind": "exact_versioned_board_attempt_plus_legacy_runtime.v1",
        "run_id": intent["run_id"],
        "task_id": intent["task_id"],
        "claim_id": intent["claim_id"],
        "agent_id": intent["agent_id"],
        "predecessor_snapshot_sha256": stable_sha256(
            intent["predecessor_snapshot"]
        ),
        "target_snapshot_sha256": stable_sha256(intent["target_snapshot"]),
    }


def _effect_payload(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": LEGACY_SETTLEMENT_EFFECT_PAYLOAD_SCHEMA,
        "run_id": intent["run_id"],
        "task_id": intent["task_id"],
        "claim_id": intent["claim_id"],
        "agent_id": intent["agent_id"],
        "action": intent["action"],
        "authority_sha256": intent["authority_sha256"],
        "predecessor_snapshot_sha256": stable_sha256(
            intent["predecessor_snapshot"]
        ),
        "target_snapshot_sha256": stable_sha256(intent["target_snapshot"]),
        "result_sha256": stable_sha256(intent["result"]),
        "metadata_delta_sha256": stable_sha256(
            {
                "set": intent["metadata_set"],
                "remove": intent["metadata_remove"],
            }
        ),
    }


def _build_exact_intent(
    *,
    run_id: str,
    task_id: str,
    claim_id: str,
    agent_id: str,
    action: str,
    result: str,
    metadata_set: dict[str, Any],
    board_task: Any,
    now: datetime,
) -> dict[str, Any]:
    status = _target_status(action)
    identity_values = (run_id, task_id, claim_id, agent_id)
    if (
        not all(isinstance(value, str) and value for value in identity_values)
        or status is None
        or not isinstance(result, str)
        or not isinstance(metadata_set, dict)
        or not all(isinstance(key, str) and key for key in metadata_set)
        or not is_aware_iso8601(now.isoformat())
    ):
        raise ValueError("legacy Board settlement boundary is invalid")
    predecessor = task_effect_snapshot(board_task)
    if not _snapshot_valid(
        predecessor,
        task_id=task_id,
    ) or not _legacy_predecessor_is_exact(
        predecessor,
        run_id=run_id,
        claim_id=claim_id,
        agent_id=agent_id,
    ):
        raise ValueError("legacy Board source attempt is not distinguishable")
    metadata_remove = ["active_claim"]
    target_metadata = dict(predecessor["metadata"])
    for key in metadata_remove:
        target_metadata.pop(key, None)
    target_metadata.update(metadata_set)
    target_task = board_task.model_copy(
        deep=True,
        update={
            "status": TaskStatus(status),
            "assigned_to": None if action == "requeue" else agent_id,
            "result": result,
            "metadata": target_metadata,
            "updated_at": now,
        },
    )
    target = task_effect_snapshot(target_task)
    intent: dict[str, Any] = {
        "schema_version": LEGACY_SETTLEMENT_INTENT_SCHEMA,
        "run_id": run_id,
        "task_id": task_id,
        "claim_id": claim_id,
        "agent_id": agent_id,
        "action": action,
        "predecessor_snapshot": predecessor,
        "target_snapshot": target,
        "result": result,
        "metadata_set": dict(metadata_set),
        "metadata_remove": metadata_remove,
        "authority_sha256": "",
        "effect_id": LEGACY_SETTLEMENT_EFFECT_PREFIX + run_id,
        "effect_kind": LEGACY_SETTLEMENT_EFFECT_KIND,
        "effect_payload": {},
        "prepared_at": now.isoformat(),
    }
    intent["authority_sha256"] = stable_sha256(_authority_payload(intent))
    intent["effect_payload"] = _effect_payload(intent)
    intent["intent_sha256"] = stable_sha256(intent)
    return intent


def _build_weak_test_intent(
    *,
    run_id: str,
    task_id: str,
    action: str,
    target_assigned_to: str | None,
    result: str,
    metadata_set: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    target_status = _target_status(action)
    if target_status is None or not run_id or not task_id:
        raise ValueError("weak legacy Board test boundary is invalid")
    intent: dict[str, Any] = {
        "schema_version": WEAK_TEST_INTENT_SCHEMA,
        "run_id": run_id,
        "task_id": task_id,
        "action": action,
        "target_status": target_status,
        "target_assigned_to": target_assigned_to,
        "result": result,
        "metadata_set": dict(metadata_set),
        "proof_mode": WEAK_TEST_PROOF_MODE,
        "prepared_at": now.isoformat(),
    }
    intent["intent_sha256"] = stable_sha256(intent)
    return intent


async def prepare_legacy_settlement(
    db: aiosqlite.Connection,
    *,
    run_id: str,
    task_id: str,
    claim_id: str,
    agent_id: str,
    action: str,
    result: str,
    metadata_set: dict[str, Any],
    board_task: Any,
    weak_test_mode: bool,
    now: datetime,
) -> None:
    """Append one immutable Board effect inside the runtime transaction."""
    intent = (
        _build_weak_test_intent(
            run_id=run_id,
            task_id=task_id,
            action=action,
            target_assigned_to=None if action == "requeue" else agent_id or None,
            result=result,
            metadata_set=metadata_set,
            now=now,
        )
        if weak_test_mode
        else _build_exact_intent(
            run_id=run_id,
            task_id=task_id,
            claim_id=claim_id,
            agent_id=agent_id,
            action=action,
            result=result,
            metadata_set=metadata_set,
            board_task=board_task,
            now=now,
        )
    )
    encoded = _canonical_json(intent)
    await db.execute(
        "INSERT OR IGNORE INTO legacy_task_board_settlement_intents"
        " (run_id, task_id, intent_sha256, intent_json, prepared_at, schema_version)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            run_id,
            task_id,
            intent["intent_sha256"],
            encoded,
            intent["prepared_at"],
            intent["schema_version"],
        ),
    )
    row = await (
        await db.execute(
            "SELECT task_id, intent_sha256, intent_json, prepared_at, schema_version"
            " FROM legacy_task_board_settlement_intents WHERE run_id = ?",
            (run_id,),
        )
    ).fetchone()
    expected = (
        task_id,
        intent["intent_sha256"],
        encoded,
        intent["prepared_at"],
        intent["schema_version"],
    )
    if row is None or tuple(row) != expected:
        raise ValueError("legacy Board settlement intent conflicts")


def _valid_exact_intent(intent: dict[str, Any]) -> dict[str, Any] | None:
    task_id = intent.get("task_id")
    predecessor = intent.get("predecessor_snapshot")
    target = intent.get("target_snapshot")
    action = intent.get("action")
    if not (
        set(intent) == _INTENT_FIELDS
        and intent.get("schema_version") == LEGACY_SETTLEMENT_INTENT_SCHEMA
        and isinstance(task_id, str)
        and task_id
        and all(
            isinstance(intent.get(key), str) and intent[key]
            for key in ("run_id", "claim_id", "agent_id")
        )
        and action in {"requeue", "complete", "fail"}
        and isinstance(intent.get("result"), str)
        and isinstance(intent.get("metadata_set"), dict)
        and all(
            isinstance(key, str) and key for key in intent.get("metadata_set", {})
        )
        and intent.get("metadata_remove") == ["active_claim"]
        and _snapshot_valid(predecessor, task_id=task_id)
        and _snapshot_valid(target, task_id=task_id)
        and _legacy_predecessor_is_exact(
            predecessor,
            run_id=intent["run_id"],
            claim_id=intent["claim_id"],
            agent_id=intent["agent_id"],
        )
        and is_sha256_hex(intent.get("authority_sha256"))
        and intent.get("effect_id")
        == LEGACY_SETTLEMENT_EFFECT_PREFIX + intent["run_id"]
        and intent.get("effect_kind") == LEGACY_SETTLEMENT_EFFECT_KIND
        and is_aware_iso8601(intent.get("prepared_at"))
        and datetime.fromisoformat(
            str(target.get("updated_at")).replace("Z", "+00:00")
        )
        == datetime.fromisoformat(
            str(intent.get("prepared_at")).replace("Z", "+00:00")
        )
        and intent.get("authority_sha256")
        == stable_sha256(_authority_payload(intent))
        and intent.get("effect_payload") == _effect_payload(intent)
        and intent.get("intent_sha256")
        == stable_sha256(
            {key: value for key, value in intent.items() if key != "intent_sha256"}
        )
    ):
        return None
    unchanged = _SNAPSHOT_FIELDS - {
        "status",
        "assigned_to",
        "result",
        "metadata",
        "updated_at",
    }
    target_metadata = dict(predecessor["metadata"])
    for key in intent["metadata_remove"]:
        target_metadata.pop(key, None)
    target_metadata.update(intent["metadata_set"])
    if not (
        all(predecessor[key] == target[key] for key in unchanged)
        and target.get("status") == _target_status(action)
        and target.get("assigned_to")
        == (None if action == "requeue" else intent["agent_id"])
        and target.get("result") == intent["result"]
        and target.get("metadata") == target_metadata
    ):
        return None
    return intent


def _valid_weak_intent(intent: dict[str, Any]) -> dict[str, Any] | None:
    unsigned = {
        key: value for key, value in intent.items() if key != "intent_sha256"
    }
    return (
        intent
        if (
            set(intent) == _WEAK_INTENT_FIELDS
            and intent.get("schema_version") == WEAK_TEST_INTENT_SCHEMA
            and intent.get("proof_mode") == WEAK_TEST_PROOF_MODE
            and intent.get("action") in {"requeue", "complete", "fail"}
            and intent.get("target_status") == _target_status(intent.get("action"))
            and all(
                isinstance(intent.get(key), str) and intent[key]
                for key in ("run_id", "task_id", "result", "prepared_at")
            )
            and is_aware_iso8601(intent.get("prepared_at"))
            and isinstance(intent.get("metadata_set"), dict)
            and intent.get("intent_sha256") == stable_sha256(unsigned)
        )
        else None
    )


def _valid_intent(raw: Any) -> dict[str, Any] | None:
    try:
        intent = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(intent, dict):
        return None
    if intent.get("schema_version") == LEGACY_SETTLEMENT_INTENT_SCHEMA:
        return _valid_exact_intent(intent)
    if intent.get("schema_version") == WEAK_TEST_INTENT_SCHEMA:
        return _valid_weak_intent(intent)
    return None


def _receipt_matches_intent(receipt: Any, intent: dict[str, Any]) -> bool:
    valid = validate_effect_commit_receipt(receipt)
    return bool(
        valid is not None
        and valid.get("effect_id") == intent["effect_id"]
        and valid.get("effect_kind") == intent["effect_kind"]
        and valid.get("task_id") == intent["task_id"]
        and valid.get("authority_sha256") == intent["authority_sha256"]
        and valid.get("expected_snapshot") == intent["predecessor_snapshot"]
        and valid.get("target_snapshot") == intent["target_snapshot"]
        and valid.get("effect_payload") == intent["effect_payload"]
    )


async def _runtime_authority_is_exact_locked(
    db: aiosqlite.Connection,
    *,
    intent: dict[str, Any],
) -> bool:
    """Validate the closed runtime attempt while its writer fence is held."""
    try:
        durable = await (
            await db.execute(
                "SELECT task_id, intent_sha256, intent_json, schema_version"
                " FROM legacy_task_board_settlement_intents WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
        run = await (
            await db.execute(
                "SELECT run_id, session_id, task_id, claim_id, assigned_by,"
                " assigned_to, status, completed_at, failure_code, metadata_json"
                " FROM delegation_runs WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
        claim = await (
            await db.execute(
                "SELECT claim_id, task_id, session_id, agent_id, status,"
                " recovered_at, retry_count, metadata_json FROM task_claims"
                " WHERE claim_id = ?",
                (intent["claim_id"],),
            )
        ).fetchone()
        if durable is None or run is None or claim is None:
            return False
        try:
            run_metadata = json.loads(str(run["metadata_json"] or "{}"))
            claim_metadata = json.loads(str(claim["metadata_json"] or "{}"))
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
        live_claim = await (
            await db.execute(
                "SELECT claim_id FROM task_claims WHERE task_id = ?"
                " AND status IN ('claimed', 'running') AND recovered_at IS NULL"
                " LIMIT 1",
                (intent["task_id"],),
            )
        ).fetchone()
        live_run = await (
            await db.execute(
                "SELECT run_id FROM delegation_runs WHERE task_id = ?"
                " AND status IN ('claimed', 'running') LIMIT 1",
                (intent["task_id"],),
            )
        ).fetchone()
        terminal_status = (
            "completed" if intent["action"] == "complete" else "failed"
        )
        receipt_close = bool(
            str(claim["status"]) == terminal_status
            and run_metadata.get("reconciled_from_receipt") is True
            and claim_metadata.get("reconciled_from_receipt") is True
        )
        recovery_close = bool(
            intent["action"] in {"requeue", "fail"}
            and str(claim["status"]) == "recovered"
            and isinstance(run["failure_code"], str)
            and bool(run["failure_code"])
            and claim_metadata.get("recovery_reason") == run["failure_code"]
            and int(claim["retry_count"]) >= 1
        )
        return bool(
            tuple(durable)
            == (
                intent["task_id"],
                intent["intent_sha256"],
                _canonical_json(intent),
                LEGACY_SETTLEMENT_INTENT_SCHEMA,
            )
            and str(run["run_id"]) == intent["run_id"]
            and str(run["task_id"]) == intent["task_id"]
            and str(run["claim_id"] or "") == intent["claim_id"]
            and str(run["assigned_by"] or "") in {"", "orchestrator"}
            and str(run["assigned_to"] or "") == intent["agent_id"]
            and str(run["status"]) == terminal_status
            and str(run["completed_at"] or "") == intent["prepared_at"]
            and str(claim["claim_id"]) == intent["claim_id"]
            and str(claim["task_id"]) == intent["task_id"]
            and str(claim["agent_id"]) == intent["agent_id"]
            and str(claim["session_id"] or "") == str(run["session_id"] or "")
            and str(claim["recovered_at"] or "") == intent["prepared_at"]
            and live_claim is None
            and live_run is None
            and isinstance(run_metadata, dict)
            and isinstance(claim_metadata, dict)
            and run_metadata.get("legacy_no_identity_allowed") is True
            and run_metadata.get("runtime_spine_status") == "legacy_no_identity"
            and claim_metadata.get("legacy_no_identity_allowed") is True
            and claim_metadata.get("runtime_spine_status") == "legacy_no_identity"
            and run_metadata.get("reconciled_at") == intent["prepared_at"]
            and (receipt_close or recovery_close)
        )
    except (aiosqlite.Error, AttributeError, KeyError, TypeError, ValueError):
        return False


async def _append_ack(
    runtime_state: RuntimeStateStore,
    *,
    intent: dict[str, Any],
    receipt: dict[str, Any] | None,
    proof_mode: str,
    now: datetime,
) -> None:
    encoded_receipt = _canonical_json(receipt) if receipt is not None else ""
    receipt_sha256 = stable_sha256(receipt) if receipt is not None else ""
    schema = (
        LEGACY_SETTLEMENT_ACK_SCHEMA
        if proof_mode == LEGACY_SETTLEMENT_PROOF_MODE
        else WEAK_TEST_ACK_SCHEMA
    )
    async with aiosqlite.connect(runtime_state.db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        await ensure_legacy_settlement_ledger(db)
        row = await (
            await db.execute(
                "SELECT task_id, intent_sha256, intent_json, schema_version FROM"
                " legacy_task_board_settlement_intents WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
        if row is None or tuple(row) != (
            intent["task_id"],
            intent["intent_sha256"],
            _canonical_json(intent),
            intent["schema_version"],
        ):
            await db.rollback()
            raise RuntimeError("legacy Board settlement intent changed before ack")
        await db.execute(
            "INSERT OR IGNORE INTO legacy_task_board_settlement_acks"
            " (run_id, intent_sha256, effect_receipt_sha256, effect_receipt_json,"
            " proof_mode, acknowledged_at, schema_version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                intent["run_id"], intent["intent_sha256"], receipt_sha256,
                encoded_receipt, proof_mode, now.isoformat(), schema,
            ),
        )
        ack = await (
            await db.execute(
                "SELECT intent_sha256, effect_receipt_sha256, effect_receipt_json,"
                " proof_mode, schema_version FROM legacy_task_board_settlement_acks"
                " WHERE run_id = ?",
                (intent["run_id"],),
            )
        ).fetchone()
        if ack is None or tuple(ack) != (
            intent["intent_sha256"], receipt_sha256, encoded_receipt,
            proof_mode, schema,
        ):
            await db.rollback()
            raise RuntimeError("legacy Board settlement ack conflicts")
        await db.commit()


def _ack_is_exact(row: Any, intent: dict[str, Any]) -> bool:
    if row["run_id"] is None:
        return False
    if intent["schema_version"] == WEAK_TEST_INTENT_SCHEMA:
        return bool(
            str(row["intent_sha256"]) == intent["intent_sha256"]
            and str(row["effect_receipt_sha256"]) == ""
            and str(row["effect_receipt_json"]) == ""
            and str(row["proof_mode"]) == WEAK_TEST_PROOF_MODE
            and str(row["schema_version"]) == WEAK_TEST_ACK_SCHEMA
        )
    try:
        receipt = json.loads(str(row["effect_receipt_json"]))
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    return bool(
        str(row["intent_sha256"]) == intent["intent_sha256"]
        and str(row["proof_mode"]) == LEGACY_SETTLEMENT_PROOF_MODE
        and str(row["schema_version"]) == LEGACY_SETTLEMENT_ACK_SCHEMA
        and str(row["effect_receipt_sha256"]) == stable_sha256(receipt)
        and _receipt_matches_intent(receipt, intent)
    )


async def _settle_exact(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any,
    intent: dict[str, Any],
    now: datetime,
) -> None:
    if not authoritative_effect_board(task_board):
        raise TypeError("legacy settlement requires authoritative TaskBoard effects")
    receipt = await load_board_effect_commit(
        task_board,
        effect_id=intent["effect_id"],
    )
    if receipt is not None:
        if not _receipt_matches_intent(receipt, intent):
            raise RuntimeError("legacy Board effect commit conflicts")
        await _append_ack(
            runtime_state,
            intent=intent,
            receipt=receipt,
            proof_mode=LEGACY_SETTLEMENT_PROOF_MODE,
            now=now,
        )
        return
    target = intent["target_snapshot"]
    async with task_board._open() as board_db:
        await board_db.execute("PRAGMA busy_timeout=2000")
        await board_db.execute("BEGIN IMMEDIATE")
        try:
            row = await (
                await board_db.execute(
                    "SELECT * FROM tasks WHERE id = ?", (intent["task_id"],)
                )
            ).fetchone()
            deps = await task_board._fetch_deps(board_db, intent["task_id"])
            current = task_board._row_to_task(row, deps) if row is not None else None
            if current is None:
                raise KeyError(intent["task_id"])
            if task_effect_snapshot(current) != intent["predecessor_snapshot"]:
                raise RuntimeError("legacy Board predecessor CAS lost")
            async with aiosqlite.connect(
                runtime_state.db_path, timeout=2.0
            ) as runtime_db:
                runtime_db.row_factory = aiosqlite.Row
                await runtime_db.execute("PRAGMA busy_timeout=2000")
                await runtime_db.execute("BEGIN IMMEDIATE")
                try:
                    await ensure_legacy_settlement_ledger(runtime_db)
                    if not await _runtime_authority_is_exact_locked(
                        runtime_db, intent=intent
                    ):
                        raise ValueError(
                            "legacy Board effect lacks exact terminal runtime authority"
                        )
                    projected = await commit_locked_task_effect(
                        task_board,
                        board_db,
                        current,
                        status=target["status"],
                        assigned_to=target["assigned_to"],
                        result=target["result"],
                        metadata=dict(target["metadata"]),
                        effect_id=intent["effect_id"],
                        effect_kind=intent["effect_kind"],
                        authority_sha256=intent["authority_sha256"],
                        effect_payload=dict(intent["effect_payload"]),
                        target_updated_at=datetime.fromisoformat(
                            intent["prepared_at"]
                        ),
                        committed_at=now,
                    )
                    receipt = await load_effect_commit(
                        board_db, effect_id=intent["effect_id"]
                    )
                    if (
                        projected is None
                        or task_effect_snapshot(projected) != target
                        or not _receipt_matches_intent(receipt, intent)
                    ):
                        raise RuntimeError(
                            "legacy Board effect lacks exact atomic commit evidence"
                        )
                    # The runtime writer fence stays live until the Board row,
                    # receipt, and transition provenance have all committed.
                    await board_db.commit()
                except BaseException:
                    if runtime_db.in_transaction:
                        await runtime_db.rollback()
                    raise
                else:
                    await runtime_db.rollback()
        except BaseException:
            if board_db.in_transaction:
                await board_db.rollback()
            raise
    await _append_ack(
        runtime_state,
        intent=intent,
        receipt=receipt,
        proof_mode=LEGACY_SETTLEMENT_PROOF_MODE,
        now=now,
    )


def _weak_task_matches(task: Any, intent: dict[str, Any]) -> bool:
    status = getattr(
        getattr(task, "status", None),
        "value",
        getattr(task, "status", None),
    )
    metadata = getattr(task, "metadata", None)
    return bool(
        getattr(task, "id", None) == intent["task_id"]
        and status == intent["target_status"]
        and getattr(task, "assigned_to", None) == intent["target_assigned_to"]
        and getattr(task, "result", None) == intent["result"]
        and isinstance(metadata, dict)
        and all(
            metadata.get(key) == value
            for key, value in intent["metadata_set"].items()
        )
    )


async def _settle_weak_test(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any,
    intent: dict[str, Any],
    now: datetime,
) -> None:
    if not explicit_weak_test_board(task_board):
        raise TypeError("weak legacy settlement is test-double-only")
    get_task = getattr(task_board, "get", None)
    current = await get_task(intent["task_id"]) if callable(get_task) else None
    if current is None or not _weak_task_matches(current, intent):
        metadata = dict(getattr(current, "metadata", {}) or {})
        metadata.pop("active_claim", None)
        metadata.update(intent["metadata_set"])
        if intent["action"] == "requeue":
            await task_board.requeue(
                intent["task_id"],
                reason=intent["result"],
                metadata=metadata,
            )
        elif intent["action"] == "complete":
            await task_board.complete(
                intent["task_id"],
                result=intent["result"],
                metadata=metadata,
            )
        else:
            await task_board.fail(
                intent["task_id"],
                error=intent["result"],
                metadata=metadata,
            )
        current = await get_task(intent["task_id"]) if callable(get_task) else None
        if callable(get_task) and not _weak_task_matches(current, intent):
            raise RuntimeError("weak legacy Board adapter lacks exact readback")
    await _append_ack(
        runtime_state,
        intent=intent,
        receipt=None,
        proof_mode=WEAK_TEST_PROOF_MODE,
        now=now,
    )


async def settle_legacy_task_board(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any | None,
    report: Any,
    now: datetime,
    logger: logging.Logger,
) -> None:
    """Replay all legacy intents while preserving proof class and exact order."""
    await runtime_state.init_db()
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await ensure_legacy_settlement_ledger(db)
        await db.commit()
        rows = await (
            await db.execute(
                "SELECT i.run_id AS intent_run_id, i.intent_json, a.run_id,"
                " a.intent_sha256,"
                " a.effect_receipt_sha256, a.effect_receipt_json, a.proof_mode,"
                " a.schema_version FROM legacy_task_board_settlement_intents i"
                " LEFT JOIN legacy_task_board_settlement_acks a"
                " ON a.run_id = i.run_id ORDER BY i.prepared_at, i.run_id"
            )
        ).fetchall()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        intent = _valid_intent(row["intent_json"])
        run_id = str(intent.get("run_id") if intent else row["intent_run_id"])
        if intent is None:
            _append_error(report, f"legacy_projection:{run_id}:malformed_intent")
            continue
        if row["run_id"] is not None:
            if not _ack_is_exact(row, intent):
                _append_error(report, f"legacy_projection:{run_id}:conflicting_ack")
            continue
        candidates.append(intent)

    if task_board is None:
        for intent in candidates:
            _append_error(
                report,
                f"legacy_projection:{intent['run_id']}:task_board_unavailable",
            )
        return
    for intent in candidates:
        run_id = intent["run_id"]
        task_id = intent["task_id"]
        try:
            if intent["schema_version"] == LEGACY_SETTLEMENT_INTENT_SCHEMA:
                await _settle_exact(
                    runtime_state=runtime_state,
                    task_board=task_board,
                    intent=intent,
                    now=now,
                )
            else:
                await _settle_weak_test(
                    runtime_state=runtime_state,
                    task_board=task_board,
                    intent=intent,
                    now=now,
                )
        except Exception as exc:  # noqa: BLE001 - replay is fail-closed
            _append_error(report, f"legacy_projection:{run_id}:{type(exc).__name__}")
            logger.error(
                "reconciler: legacy TaskBoard settlement failed for %s/%s: %s",
                run_id,
                task_id,
                exc,
                exc_info=True,
            )


__all__ = [
    "LEGACY_SETTLEMENT_ACK_SCHEMA", "LEGACY_SETTLEMENT_EFFECT_KIND",
    "LEGACY_SETTLEMENT_INTENT_SCHEMA", "LEGACY_SETTLEMENT_PROOF_MODE",
    "WEAK_TEST_BOARD_MODE_ATTRIBUTE", "WEAK_TEST_PROOF_MODE",
    "authoritative_effect_board", "ensure_legacy_settlement_ledger",
    "explicit_weak_test_board", "prepare_legacy_settlement",
    "settle_legacy_task_board",
]
