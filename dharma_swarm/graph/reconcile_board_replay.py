"""Replay sealed runtime ProjectionIntents into TaskBoard.

Production protocol phases are intentionally separate:

1. Runtime commits the terminal row and sealed intent.
2. TaskBoard locks the current value, revalidates runtime authority, and commits
   the exact mutation plus an immutable before/after receipt atomically.
3. Runtime imports that receipt as a witness, then appends an acknowledgement.

Non-production Board doubles use the older prepared-target/readback protocol.
A crash between any two phases leaves a durable, idempotently replayable prefix.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import aiosqlite

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board_effect_commit import (
    AUTHORITATIVE_PROJECTION_COMMIT_MODE,
    NON_PRODUCTION_PROJECTION_COMMIT_MODE,
    graph_projection_effect_id,
    load_board_effect_commit,
)
from dharma_swarm.task_board_projection_intent import (
    GRAPH_PROJECTION_HISTORY_KEY,
    GRAPH_PROJECTION_KEY,
    TASK_BOARD_PROJECTION_INTENT_KEY,
    is_aware_iso8601,
    is_sha256_hex,
    stable_sha256,
)

from .reconcile_board_intent import BOARD_COMPLETION_BINDING_KEY
from .reconcile_board_proof import (
    ProjectionTargetProof,
    append_atomic_projection_witness,
    append_exact_projection_witness,
    ensure_projection_proof_ledger,
    has_exact_projection_witness,
    load_exact_atomic_projection_witness,
    load_projection_target,
    prepare_projection_target,
    task_projection_snapshot,
)

PROJECTION_ACK_SCHEMA = "dharma.graph.task_board_projection_ack.v1"
PROJECTION_MARKER_SCHEMA = "dharma.graph.board_projection_receipt.v1"
_INTENT_FIELDS = frozenset(
    "schema_version task_id run_id claim_id agent_id action run_status source_kind "
    "runtime_authority_snapshot_sha256 result result_sha256 metadata_set "
    "metadata_remove metadata_delta_sha256 completion_binding execution_identity "
    "prepared_at intent_sha256".split()
)
_MARKER_FIELDS = frozenset(
    "schema_version task_id run_id action run_status "
    "runtime_authority_snapshot_sha256 board_result_sha256 projected_at".split()
)


def _load_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


async def ensure_projection_ack_ledger(db: aiosqlite.Connection) -> None:
    """Create the append-only phase-three acknowledgement ledger."""
    await ensure_projection_proof_ledger(db)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS task_board_projection_acks ("
        "run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL"
        " UNIQUE, board_receipt_sha256 TEXT NOT NULL, board_receipt_json TEXT NOT NULL,"
        " acknowledged_at TEXT NOT NULL, schema_version TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_projection_ack_no_update "
        "BEFORE UPDATE ON task_board_projection_acks BEGIN SELECT RAISE(ABORT,"
        " 'task board projection ack is immutable'); END"
    )
    await db.execute(
        "CREATE TRIGGER IF NOT EXISTS task_board_projection_ack_no_delete "
        "BEFORE DELETE ON task_board_projection_acks BEGIN SELECT RAISE(ABORT,"
        " 'task board projection ack is immutable'); END"
    )


def _valid_intent(raw: Any, *, task_id: str, run_id: str) -> dict[str, Any] | None:
    if not (
        isinstance(raw, dict)
        and set(raw) == _INTENT_FIELDS
        and raw.get("schema_version")
        == "dharma.graph.task_board_projection_intent.v1"
        and raw.get("task_id") == task_id
        and raw.get("run_id") == run_id
        and raw.get("action") in {"receipt", "retry", "requeue", "quarantine"}
        and raw.get("run_status") in {"completed", "failed"}
        and isinstance(raw.get("result"), str)
        and isinstance(raw.get("metadata_set"), dict)
        and isinstance(raw.get("metadata_remove"), list)
        and isinstance(raw.get("execution_identity"), dict)
        and is_sha256_hex(raw.get("runtime_authority_snapshot_sha256"))
        and is_sha256_hex(raw.get("result_sha256"))
        and is_sha256_hex(raw.get("metadata_delta_sha256"))
        and is_sha256_hex(raw.get("intent_sha256"))
        and is_aware_iso8601(raw.get("prepared_at"))
        and raw.get("intent_sha256")
        == stable_sha256({key: value for key, value in raw.items() if key != "intent_sha256"})
    ):
        return None
    return raw


def _projection_marker(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_MARKER_SCHEMA,
        "task_id": intent["task_id"],
        "run_id": intent["run_id"],
        "action": intent["action"],
        "run_status": intent["run_status"],
        "runtime_authority_snapshot_sha256": intent[
            "runtime_authority_snapshot_sha256"
        ],
        "board_result_sha256": intent["result_sha256"],
        "projected_at": intent["prepared_at"],
    }


def _target_metadata(
    current: dict[str, Any],
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> dict[str, Any]:
    metadata_set = intent["metadata_set"]
    metadata_remove = intent["metadata_remove"]
    target = dict(current)
    for key in metadata_remove:
        target.pop(key, None)
    target.update(metadata_set)
    if intent["action"] in {"receipt", "retry"}:
        target[BOARD_COMPLETION_BINDING_KEY] = dict(intent["completion_binding"])
    history = target.get(GRAPH_PROJECTION_HISTORY_KEY, {})
    if not isinstance(history, dict):
        raise ValueError("TaskBoard projection history is malformed")
    history = dict(history)
    prior = target.get(GRAPH_PROJECTION_KEY)
    if prior is not None:
        if not isinstance(prior, dict):
            raise ValueError("TaskBoard projection receipt is malformed")
        prior_run_id = prior.get("run_id")
        if not isinstance(prior_run_id, str) or not prior_run_id:
            raise ValueError("TaskBoard projection receipt lacks run identity")
        historical = history.get(prior_run_id)
        if historical is not None and historical != prior:
            raise ValueError("TaskBoard projection history conflicts")
        history[prior_run_id] = prior
    existing = history.get(intent["run_id"])
    if existing is not None and existing != marker:
        raise ValueError("TaskBoard projection history collision")
    history[intent["run_id"]] = marker
    target[GRAPH_PROJECTION_KEY] = marker
    target[GRAPH_PROJECTION_HISTORY_KEY] = history
    return target


def _marker_is_exact(raw: Any, marker: dict[str, Any]) -> bool:
    return bool(
        isinstance(raw, dict)
        and set(raw) == _MARKER_FIELDS
        and raw == marker
    )


def _projection_witnessed(metadata: dict[str, Any], marker: dict[str, Any]) -> bool:
    current = metadata.get(GRAPH_PROJECTION_KEY)
    history = metadata.get(GRAPH_PROJECTION_HISTORY_KEY)
    historical = history.get(marker["run_id"]) if isinstance(history, dict) else None
    return _marker_is_exact(current, marker) or _marker_is_exact(historical, marker)


def _append_error(report: Any, value: str) -> None:
    errors = getattr(report, "errors", None)
    if isinstance(errors, list) and value not in errors:
        errors.append(value)


async def _append_projection_ack(
    runtime_state: RuntimeStateStore,
    *,
    run_id: str,
    task_id: str,
    intent: dict[str, Any],
    marker: dict[str, Any],
    proof: ProjectionTargetProof | None,
    authoritative_board_receipt: dict[str, Any] | None = None,
    now: datetime,
) -> None:
    """Append an ack only if the exact prepared intent is still durable."""
    atomic_witness = (
        await load_exact_atomic_projection_witness(
            runtime_state,
            intent=intent,
            marker=marker,
            expected_board_receipt=authoritative_board_receipt,
        )
        if authoritative_board_receipt is not None
        else None
    )
    target_witness = bool(
        proof is not None
        and await has_exact_projection_witness(runtime_state, proof=proof)
    )
    if atomic_witness is None and not target_witness:
        raise RuntimeError("projection ack lacks exact target witness")
    encoded_marker = json.dumps(marker, sort_keys=True, separators=(",", ":"))
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await ensure_projection_ack_ledger(db)
        row = await (
            await db.execute(
                "SELECT assigned_by, metadata_json FROM delegation_runs WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
        if row is None or str(row["assigned_by"] or "") != "orchestrator":
            await db.rollback()
            raise RuntimeError("projection ack lost orchestrator-owned runtime row")
        durable_intent = _load_json(row["metadata_json"]).get(
            TASK_BOARD_PROJECTION_INTENT_KEY
        )
        if durable_intent != intent:
            await db.rollback()
            raise RuntimeError("projection ack intent changed after Board readback")
        existing = await (
            await db.execute(
                "SELECT task_id, intent_sha256, board_receipt_sha256,"
                " board_receipt_json, schema_version FROM task_board_projection_acks"
                " WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
        expected = {
            "task_id": task_id,
            "intent_sha256": intent["intent_sha256"],
            "board_receipt_sha256": stable_sha256(marker),
            "board_receipt_json": encoded_marker,
            "schema_version": PROJECTION_ACK_SCHEMA,
        }
        if existing is not None:
            if any(str(existing[key]) != value for key, value in expected.items()):
                await db.rollback()
                raise RuntimeError("projection ack ledger conflicts")
            await db.commit()
            return
        await db.execute(
            "INSERT INTO task_board_projection_acks"
            " (run_id, task_id, intent_sha256, board_receipt_sha256,"
            " board_receipt_json, acknowledged_at, schema_version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                task_id,
                intent["intent_sha256"],
                expected["board_receipt_sha256"],
                encoded_marker,
                now.isoformat(),
                PROJECTION_ACK_SCHEMA,
            ),
        )
        await db.commit()


def _is_authoritative_task_board(task_board: Any) -> bool:
    if (
        getattr(task_board, "projection_commit_mode", None)
        != AUTHORITATIVE_PROJECTION_COMMIT_MODE
    ):
        return False
    from dharma_swarm.task_board import TaskBoard

    return isinstance(task_board, TaskBoard)


async def _settle_authoritative_board(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any,
    run_id: str,
    task_id: str,
    intent: dict[str, Any],
    now: datetime,
) -> None:
    """Settle through the Board-local atomic commit, never an unlocked target."""
    marker = _projection_marker(intent)
    effect_id = graph_projection_effect_id(run_id)
    receipt = await load_board_effect_commit(task_board, effect_id=effect_id)
    if receipt is None:
        current = await task_board.get(task_id)
        if current is None:
            raise KeyError(task_id)
        replacement = _target_metadata(
            dict(getattr(current, "metadata", {}) or {}),
            intent,
            marker,
        )
        projected = await task_board.compare_and_swap_terminal_projection(
            current,
            metadata=replacement,
            result=intent["result"],
            expected_claim_id=intent["claim_id"],
            expected_agent_id=intent["agent_id"],
            runtime_state_store=runtime_state,
        )
        if projected is None:
            raise RuntimeError("TaskBoard projection CAS lost")
        receipt = await load_board_effect_commit(task_board, effect_id=effect_id)
        if receipt is None:
            raise RuntimeError("TaskBoard projection lacks atomic commit receipt")
    await append_atomic_projection_witness(
        runtime_state,
        task_board=task_board,
        board_receipt=receipt,
        intent=intent,
        marker=marker,
        now=now,
    )
    await _append_projection_ack(
        runtime_state,
        run_id=run_id,
        task_id=task_id,
        intent=intent,
        marker=marker,
        proof=None,
        authoritative_board_receipt=receipt,
        now=now,
    )


async def _settle_one(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any,
    run_id: str,
    task_id: str,
    intent: dict[str, Any],
    now: datetime,
) -> None:
    if _is_authoritative_task_board(task_board):
        await _settle_authoritative_board(
            runtime_state=runtime_state,
            task_board=task_board,
            run_id=run_id,
            task_id=task_id,
            intent=intent,
            now=now,
        )
        return
    if (
        getattr(task_board, "projection_commit_mode", None)
        != NON_PRODUCTION_PROJECTION_COMMIT_MODE
    ):
        raise TypeError("non-production TaskBoard double must declare replay mode")
    get_task = getattr(task_board, "get", None)
    project = getattr(task_board, "compare_and_swap_terminal_projection", None)
    if not callable(get_task) or not callable(project):
        raise TypeError("TaskBoard must provide exact get and terminal projection CAS")
    marker = _projection_marker(intent)
    current = await get_task(task_id)
    if current is None:
        raise KeyError(task_id)
    current_metadata = dict(getattr(current, "metadata", {}) or {})
    proof = await load_projection_target(
        runtime_state,
        run_id=run_id,
        task_id=task_id,
        intent=intent,
        marker=marker,
    )
    if proof is None:
        # A Board marker is an effect receipt, not proof of its complete value.
        # Preparing a target after seeing it would bless a partial/corrupt write.
        if _projection_witnessed(current_metadata, marker):
            raise RuntimeError("TaskBoard marker lacks a prepared target proof")
        replacement = _target_metadata(current_metadata, intent, marker)
        proof = await prepare_projection_target(
            runtime_state,
            run_id=run_id,
            task_id=task_id,
            intent=intent,
            marker=marker,
            expected=current,
            target_metadata=replacement,
            now=now,
        )

    # The immutable witness records an earlier exact target readback.  It is
    # sufficient even if a later, valid attempt has advanced the Board row.
    if await has_exact_projection_witness(runtime_state, proof=proof):
        await _append_projection_ack(
            runtime_state,
            run_id=run_id,
            task_id=task_id,
            intent=intent,
            marker=marker,
            proof=proof,
            now=now,
        )
        return

    observed_snapshot = task_projection_snapshot(current)
    if observed_snapshot == proof.target_snapshot:
        await append_exact_projection_witness(
            runtime_state,
            proof=proof,
            observed=current,
            intent=intent,
            now=now,
        )
        await _append_projection_ack(
            runtime_state,
            run_id=run_id,
            task_id=task_id,
            intent=intent,
            marker=marker,
            proof=proof,
            now=now,
        )
        return
    if observed_snapshot != proof.expected_snapshot:
        if _projection_witnessed(current_metadata, marker):
            raise RuntimeError("TaskBoard marker contradicts prepared target")
        raise RuntimeError("TaskBoard value contradicts prepared projection proof")

    projected = await project(
        current,
        metadata=dict(proof.target_snapshot["metadata"]),
        result=intent["result"],
        expected_claim_id=intent["claim_id"],
        expected_agent_id=intent["agent_id"],
        runtime_state_store=runtime_state,
    )
    if projected is None:
        raise RuntimeError("TaskBoard projection CAS lost")
    readback = await get_task(task_id)
    if readback is None or task_projection_snapshot(readback) != proof.target_snapshot:
        raise RuntimeError("TaskBoard projection lacks exact readback")
    await append_exact_projection_witness(
        runtime_state,
        proof=proof,
        observed=readback,
        intent=intent,
        now=now,
    )
    await _append_projection_ack(
        runtime_state,
        run_id=run_id,
        task_id=task_id,
        intent=intent,
        marker=marker,
        proof=proof,
        now=now,
    )


async def settle_task_board(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any | None,
    report: Any,
    now: datetime,
    logger: logging.Logger,
    run_id: str | None = None,
) -> None:
    """Replay one or every durable, unacknowledged ProjectionIntent."""
    await runtime_state.init_db()
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await ensure_projection_ack_ledger(db)
        await db.commit()
        filters = [
            "status IN ('completed', 'failed')",
            "metadata_json LIKE ?",
        ]
        params: list[Any] = [f'%"{TASK_BOARD_PROJECTION_INTENT_KEY}"%']
        if run_id is not None:
            filters.append("run_id = ?")
            params.append(run_id)
        rows = await (
            await db.execute(
                "SELECT run_id, task_id, assigned_by, metadata_json"
                " FROM delegation_runs WHERE " + " AND ".join(filters),
                params,
            )
        ).fetchall()
        ack_rows = await (
            await db.execute(
                "SELECT run_id, task_id, intent_sha256, board_receipt_sha256,"
                " board_receipt_json, schema_version"
                " FROM task_board_projection_acks"
            )
        ).fetchall()
        acknowledgements = {str(row["run_id"]): row for row in ack_rows}

    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for row in rows:
        candidate_run_id = str(row["run_id"])
        task_id = str(row["task_id"])
        metadata = _load_json(row["metadata_json"])
        intent = _valid_intent(
            metadata.get(TASK_BOARD_PROJECTION_INTENT_KEY),
            task_id=task_id,
            run_id=candidate_run_id,
        )
        if str(row["assigned_by"] or "") != "orchestrator":
            _append_error(report, f"projection:{candidate_run_id}:unknown_runtime_owner")
            continue
        if intent is None:
            _append_error(report, f"projection:{candidate_run_id}:malformed_intent")
            continue
        ack = acknowledgements.get(candidate_run_id)
        if ack is not None:
            marker = _projection_marker(intent)
            expected_marker_json = json.dumps(
                marker, sort_keys=True, separators=(",", ":")
            )
            if not (
                str(ack["task_id"]) == task_id
                and str(ack["intent_sha256"]) == intent["intent_sha256"]
                and str(ack["board_receipt_sha256"]) == stable_sha256(marker)
                and str(ack["board_receipt_json"]) == expected_marker_json
                and str(ack["schema_version"]) == PROJECTION_ACK_SCHEMA
            ):
                _append_error(
                    report,
                    f"projection:{candidate_run_id}:conflicting_ack",
                )
                continue
            try:
                authoritative = _is_authoritative_task_board(task_board)
                nonproduction = bool(
                    task_board is not None
                    and getattr(task_board, "projection_commit_mode", None)
                    == NON_PRODUCTION_PROJECTION_COMMIT_MODE
                )
                atomic_witness = None
                proof = None
                if authoritative:
                    board_receipt = await load_board_effect_commit(
                        task_board,
                        effect_id=graph_projection_effect_id(candidate_run_id),
                    )
                    if board_receipt is not None:
                        atomic_witness = await load_exact_atomic_projection_witness(
                            runtime_state,
                            intent=intent,
                            marker=marker,
                            expected_board_receipt=board_receipt,
                        )
                elif nonproduction:
                    proof = await load_projection_target(
                        runtime_state,
                        run_id=candidate_run_id,
                        task_id=task_id,
                        intent=intent,
                        marker=marker,
                    )
                target_witness = bool(
                    proof is not None
                    and await has_exact_projection_witness(
                        runtime_state,
                        proof=proof,
                    )
                )
                if atomic_witness is None and not target_witness:
                    _append_error(
                        report,
                        f"projection:{candidate_run_id}:unproven_ack",
                    )
            except Exception:  # noqa: BLE001 - malformed proof is fail-closed
                _append_error(
                    report,
                    f"projection:{candidate_run_id}:unproven_ack",
                )
            continue
        candidates.append((candidate_run_id, task_id, intent))

    if task_board is None:
        for candidate_run_id, _task_id, _intent in candidates:
            _append_error(
                report,
                f"projection:{candidate_run_id}:task_board_unavailable",
            )
        return
    for candidate_run_id, task_id, intent in candidates:
        try:
            await _settle_one(
                runtime_state=runtime_state,
                task_board=task_board,
                run_id=candidate_run_id,
                task_id=task_id,
                intent=intent,
                now=now,
            )
        except Exception as exc:  # noqa: BLE001 - durable replay records exact failure
            logger.error(
                "reconciler: TaskBoard projection failed for run %s: %s",
                candidate_run_id,
                exc,
                exc_info=True,
            )
            _append_error(
                report,
                f"projection:{candidate_run_id}:{type(exc).__name__}",
            )


__all__ = [
    "PROJECTION_ACK_SCHEMA",
    "ensure_projection_ack_ledger",
    "settle_task_board",
]
