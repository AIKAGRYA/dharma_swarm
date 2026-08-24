"""Prepare exact TaskBoard projection intents inside ``runtime.db``.

The runtime and TaskBoard are separate SQLite stores.  This module owns only
phase one of the projection protocol: while the caller already owns the
terminal runtime transaction, turn its pending projection witness into one
sealed :class:`ProjectionIntent`.  Board I/O is deliberately absent here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from typing import Any

import aiosqlite

from dharma_swarm.runtime_state import _row_to_idempotency_record, _row_to_run
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.task_board_projection_intent import (
    GRAPH_PROJECTION_HISTORY_KEY,
    GRAPH_PROJECTION_KEY,
    TASK_BOARD_PROJECTION_INTENT_KEY,
    TASK_BOARD_PROJECTION_WITNESS_KEY,
    build_task_board_projection_intent,
    runtime_idempotency_authority_snapshot_sha256,
    runtime_run_projection_authority_snapshot_sha256,
    valid_completion_binding,
)

BOARD_COMPLETION_BINDING_KEY = "task_board_completion_binding"
BOARD_COMPLETION_BINDING_SCHEMA = "dharma.graph.task_board_completion_binding.v1"
PROJECTION_WITNESS_SCHEMA = "dharma.graph.task_board_projection_prepare.v1"

_PROJECTION_ACTIONS = frozenset({"receipt", "retry", "requeue", "quarantine"})
_RECEIPT_ACTIONS = frozenset({"receipt", "retry"})
_WITNESS_FIELDS = frozenset(
    {
        "schema_version",
        "state",
        "task_id",
        "run_id",
        "action",
        "run_status",
        "result",
        "completion_binding",
        "metadata_set",
        "metadata_remove",
        "source",
        "prepared_at",
    }
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


def build_task_board_completion_binding(
    dispatch: Any,
    *,
    result: str,
) -> dict[str, Any]:
    """Bind one Board terminal value to the exact provider side effect."""
    metadata = getattr(dispatch, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    identity = metadata.get("execution_identity")
    identity = identity if isinstance(identity, dict) else {}
    task_id = str(getattr(dispatch, "task_id", "") or identity.get("task_id") or "")
    agent_id = str(getattr(dispatch, "agent_id", "") or identity.get("agent_id") or "")
    side_effect_key = f"invoke_agent:{task_id}:{agent_id}"
    return {
        "schema_version": BOARD_COMPLETION_BINDING_SCHEMA,
        "task_id": task_id,
        "run_id": str(identity.get("run_id") or ""),
        "claim_id": str(identity.get("claim_id") or ""),
        "agent_id": agent_id,
        "receipt_id": str(metadata.get("evidence_receipt_id") or ""),
        "side_effect_key": side_effect_key,
        "idempotency_key": "sek_"
        + hashlib.sha256(side_effect_key.encode("utf-8")).hexdigest(),
        "dispatch_idempotency_key": str(identity.get("idempotency_key") or ""),
        "result_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
    }


def _pending_projection_metadata(
    raw: Any,
    *,
    task_id: str,
    run_id: str,
    run_status: str,
    board_result: str,
    completion_binding: dict[str, Any] | None,
    now: datetime,
    source: str,
    action: str,
    board_metadata_set: dict[str, Any] | None,
    board_metadata_remove: list[str] | None,
) -> dict[str, Any]:
    if (
        action not in _PROJECTION_ACTIONS
        or run_status not in {"completed", "failed"}
        or action == "retry" and run_status != "failed"
        or action in {"requeue", "quarantine"} and run_status != "failed"
        or not task_id
        or not run_id
        or not isinstance(board_result, str)
        or not isinstance(source, str)
        or not source
    ):
        raise ValueError("terminal TaskBoard projection boundary is invalid")
    delta_set = dict(board_metadata_set or {})
    delta_remove = sorted(set(board_metadata_remove or []))
    supplied_binding = delta_set.pop(BOARD_COMPLETION_BINDING_KEY, None)
    if supplied_binding is not None and supplied_binding != completion_binding:
        raise ValueError("terminal TaskBoard completion binding delta conflicts")
    reserved_delta_keys = {
        GRAPH_PROJECTION_KEY,
        GRAPH_PROJECTION_HISTORY_KEY,
        BOARD_COMPLETION_BINDING_KEY,
        TASK_BOARD_PROJECTION_INTENT_KEY,
        TASK_BOARD_PROJECTION_WITNESS_KEY,
    }
    if (
        not all(isinstance(key, str) and key for key in delta_set)
        or not all(isinstance(key, str) and key for key in delta_remove)
        or set(delta_set).intersection(delta_remove)
        or reserved_delta_keys.intersection(delta_set)
        or reserved_delta_keys.intersection(delta_remove)
    ):
        raise ValueError("terminal TaskBoard metadata delta is invalid")
    if action in _RECEIPT_ACTIONS:
        if not isinstance(completion_binding, dict):
            raise ValueError("terminal TaskBoard projection lacks completion binding")
    elif completion_binding is not None and not isinstance(completion_binding, dict):
        raise ValueError("recovery TaskBoard completion binding is malformed")

    metadata = _load_json(raw)
    if TASK_BOARD_PROJECTION_INTENT_KEY in metadata:
        raise ValueError("terminal TaskBoard ProjectionIntent is runtime-owned")
    witness = {
        "schema_version": PROJECTION_WITNESS_SCHEMA,
        "state": "pending",
        "task_id": task_id,
        "run_id": run_id,
        "action": action,
        "run_status": run_status,
        "result": board_result,
        "completion_binding": (
            dict(completion_binding) if completion_binding is not None else None
        ),
        "metadata_set": delta_set,
        "metadata_remove": delta_remove,
        "source": source,
        "prepared_at": now.isoformat(),
    }
    existing = metadata.get(TASK_BOARD_PROJECTION_WITNESS_KEY)
    if existing is not None and existing != witness:
        raise ValueError("terminal TaskBoard projection witness conflicts")
    metadata[TASK_BOARD_PROJECTION_WITNESS_KEY] = witness
    if completion_binding is not None:
        metadata[BOARD_COMPLETION_BINDING_KEY] = dict(completion_binding)
    return metadata


def terminal_task_board_projection_metadata(
    raw: Any,
    *,
    task_id: str,
    run_id: str,
    run_status: str,
    board_result: str,
    completion_binding: dict[str, Any] | None,
    now: datetime,
    source: str,
    action: str = "receipt",
    board_metadata_set: dict[str, Any] | None = None,
    board_metadata_remove: list[str] | None = None,
) -> dict[str, Any]:
    """Attach one pending projection witness for any governed terminal action."""
    if action not in _PROJECTION_ACTIONS:
        raise ValueError("terminal projection action is invalid")
    return _pending_projection_metadata(
        raw,
        task_id=task_id,
        run_id=run_id,
        run_status=run_status,
        board_result=board_result,
        completion_binding=completion_binding,
        now=now,
        source=source,
        action=action,
        board_metadata_set=board_metadata_set,
        board_metadata_remove=board_metadata_remove,
    )


def recovery_task_board_projection_metadata(
    raw: Any,
    *,
    task_id: str,
    run_id: str,
    board_result: str,
    now: datetime,
    action: str,
    completion_binding: dict[str, Any] | None = None,
    source: str = "graph_reconciler.runtime_recovery",
) -> dict[str, Any]:
    """Attach an exact non-campaign recovery projection witness."""
    if action not in {"requeue", "quarantine"}:
        raise ValueError("recovery TaskBoard projection action is invalid")
    return _pending_projection_metadata(
        raw,
        task_id=task_id,
        run_id=run_id,
        run_status="failed",
        board_result=board_result,
        # Recovery carries no new receipt authority, but must preserve the
        # Board attempt's existing binding byte-for-byte when one exists.
        completion_binding=completion_binding,
        now=now,
        source=source,
        action=action,
        board_metadata_set={},
        board_metadata_remove=["active_claim"] if action == "requeue" else [],
    )


def _valid_witness(raw: Any, *, task_id: str, run_id: str) -> dict[str, Any] | None:
    witness = _load_json(raw).get(TASK_BOARD_PROJECTION_WITNESS_KEY)
    if not (
        isinstance(witness, dict)
        and set(witness) == _WITNESS_FIELDS
        and witness.get("schema_version") == PROJECTION_WITNESS_SCHEMA
        and witness.get("state") == "pending"
        and witness.get("task_id") == task_id
        and witness.get("run_id") == run_id
        and witness.get("action") in _PROJECTION_ACTIONS
        and witness.get("run_status") in {"completed", "failed"}
        and isinstance(witness.get("result"), str)
        and isinstance(witness.get("metadata_set"), dict)
        and isinstance(witness.get("metadata_remove"), list)
        and isinstance(witness.get("source"), str)
        and witness.get("source")
        and isinstance(witness.get("prepared_at"), str)
        and witness.get("prepared_at")
    ):
        return None
    return witness


def _canonical_run_identity(row: aiosqlite.Row, metadata: dict[str, Any]) -> dict[str, Any] | None:
    nested = metadata.get("execution_identity")
    if not isinstance(nested, dict):
        return None
    try:
        identity = ExecutionIdentity.from_metadata(metadata, require=True)
    except (MissingExecutionIdentity, TypeError, ValueError):
        return None
    if identity is None or identity.to_dict() != nested:
        return None
    expected = {
        "run_id": str(row["run_id"] or ""),
        "task_id": str(row["task_id"] or ""),
        "claim_id": str(row["claim_id"] or ""),
        "agent_id": str(row["assigned_to"] or ""),
        "session_id": str(row["session_id"] or ""),
        "parent_run_id": str(row["parent_run_id"] or ""),
    }
    if str(row["assigned_by"] or "") != "orchestrator" or any(
        getattr(identity, key) != value for key, value in expected.items()
    ):
        return None
    aliases = {
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "task_id": identity.task_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "parent_run_id": identity.parent_run_id,
        "causation_id": identity.causation_id,
        "idempotency_key": identity.idempotency_key,
    }
    if any(
        key in metadata and metadata.get(key) != value
        for key, value in aliases.items()
    ):
        return None
    return nested


async def _identity_row_is_exact(
    db: aiosqlite.Connection,
    identity: dict[str, Any],
) -> bool:
    row = await (
        await db.execute(
            "SELECT trace_id, correlation_id, task_id, claim_id, idempotency_key,"
            " causation_id, parent_run_id, agent_id, session_id,"
            " external_a2a_task_id, message_id, event_id, artifact_id, proposal_id,"
            " metadata_json FROM execution_identities WHERE run_id = ?",
            (identity["run_id"],),
        )
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
    return all(str(row[field] or "") == identity[field] for field in fields) and (
        _load_json(row["metadata_json"]) == identity["metadata"]
    )


async def _projection_authority_digest(
    db: aiosqlite.Connection,
    *,
    run: Any,
    identity: dict[str, Any],
    witness: dict[str, Any],
) -> str:
    action = str(witness["action"])
    if action not in _RECEIPT_ACTIONS:
        return runtime_run_projection_authority_snapshot_sha256(run)
    binding = witness.get("completion_binding")
    result = str(witness["result"])
    if not valid_completion_binding(
        binding,
        task_id=identity["task_id"],
        run_id=identity["run_id"],
        claim_id=identity["claim_id"],
        agent_id=identity["agent_id"],
        dispatch_idempotency_key=identity["idempotency_key"],
        result=result,
    ):
        return ""
    row = await (
        await db.execute(
            "SELECT idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, metadata_json, created_at,"
            " updated_at FROM idempotency_records WHERE idempotency_key = ?"
            " AND side_effect_key = ?",
            (binding["idempotency_key"], binding["side_effect_key"]),
        )
    ).fetchone()
    if row is None:
        return ""
    record = _row_to_idempotency_record(row)
    record_metadata = record.metadata if isinstance(record.metadata, dict) else {}
    receipt = record_metadata.get("receipt")
    attributes = receipt.get("attributes") if isinstance(receipt, dict) else None
    if not isinstance(receipt, dict) or not isinstance(attributes, dict):
        return ""
    if witness["run_status"] == "completed":
        encoded_result = record_metadata.get("result_json")
        try:
            durable_result = (
                json.loads(encoded_result) if isinstance(encoded_result, str) else None
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return ""
        outcome_exact = receipt.get("status") == "ok" and durable_result == result
    else:
        error_source = receipt.get("error_source")
        error_detail = receipt.get("error_detail")
        outcome_exact = bool(
            receipt.get("status") in {"failed", "dropped", "timeout", "cancelled"}
            and isinstance(error_source, str)
            and error_source.strip()
            and error_source != "none"
            and isinstance(error_detail, str)
            and error_detail.strip()
            and error_detail == result
            and run.failure_code == error_source
            and str(run.metadata.get("error") or "") == error_detail
        )
    if (
        not outcome_exact
        or record.run_id != identity["run_id"]
        or record.task_id != identity["task_id"]
        or record.trace_id != identity["trace_id"]
        or record.correlation_id != identity["correlation_id"]
        or record.result_receipt_id != binding["receipt_id"]
        or record.status != witness["run_status"]
        or record_metadata.get("task_id") != identity["task_id"]
        or record_metadata.get("operation_hash")
        != hashlib.sha256(binding["side_effect_key"].encode("utf-8")).hexdigest()
        or receipt.get("receipt_id") != binding["receipt_id"]
        or receipt.get("trace_id") != identity["trace_id"]
        or receipt.get("context_id") != identity["session_id"]
        or receipt.get("task_id") != identity["task_id"]
        or receipt.get("claim_id") != identity["claim_id"]
        or receipt.get("agent_id") != identity["agent_id"]
        or receipt.get("operation") != "invoke_agent"
        or receipt.get("provider_attempted") is not True
        or attributes.get("run_id") != identity["run_id"]
        or attributes.get("idempotency_key") != binding["idempotency_key"]
        or attributes.get("dispatch_idempotency_key")
        != identity["idempotency_key"]
        or attributes.get("side_effect_key") != binding["side_effect_key"]
        or attributes.get("unprotected_dispatch") is True
    ):
        return ""
    return runtime_idempotency_authority_snapshot_sha256(record)


async def projection_intent_authority_is_exact(
    db: aiosqlite.Connection,
    *,
    run_id: str,
    expected_intent: dict[str, Any],
) -> bool:
    """Re-derive one prepared intent from its durable runtime authority.

    A structurally valid, self-hashed intent is only a claim.  Consumers may
    treat it as a pending projection only when the execution registry and the
    receipt/run authority still derive the exact digest sealed in the intent.
    The caller owns the read transaction so this proof and any subsequent ACK
    lookup share one runtime snapshot.
    """
    row = await (
        await db.execute(
            "SELECT metadata_json FROM delegation_runs WHERE run_id = ?",
            (run_id,),
        )
    ).fetchone()
    if row is None:
        return False
    metadata = _load_json(row["metadata_json"])
    if metadata.get(TASK_BOARD_PROJECTION_INTENT_KEY) != expected_intent:
        return False
    # The exact durable intent is already present, so preparation reaches its
    # read-only validation branch: it re-derives identity, source authority,
    # and the canonical intent without issuing an UPDATE.
    return await prepare_task_board_projection_snapshot(db, run_id=run_id)


async def prepare_task_board_projection_snapshot(
    db: aiosqlite.Connection,
    *,
    run_id: str,
) -> bool:
    """Seal phase-one ProjectionIntent in the caller's runtime transaction."""
    if db.row_factory is None:
        db.row_factory = aiosqlite.Row
    row = await (
        await db.execute(
            "SELECT run_id, session_id, task_id, claim_id, parent_run_id, assigned_by,"
            " assigned_to, requested_output_json, current_artifact_id, status,"
            " started_at, completed_at, failure_code, metadata_json"
            " FROM delegation_runs WHERE run_id = ?",
            (run_id,),
        )
    ).fetchone()
    if row is None or str(row["status"]) not in {"completed", "failed"}:
        return False
    metadata = _load_json(row["metadata_json"])
    task_id = str(row["task_id"] or "")
    witness = _valid_witness(metadata, task_id=task_id, run_id=run_id)
    identity = _canonical_run_identity(row, metadata)
    if witness is None or identity is None or witness["run_status"] != row["status"]:
        return False
    if not await _identity_row_is_exact(db, identity):
        return False
    aliases = {
        "trace_id": identity["trace_id"],
        "correlation_id": identity["correlation_id"],
        "task_id": identity["task_id"],
        "run_id": identity["run_id"],
        "runtime_run_id": identity["run_id"],
        "claim_id": identity["claim_id"],
        "agent_id": identity["agent_id"],
        "session_id": identity["session_id"],
        "parent_run_id": identity["parent_run_id"],
        "causation_id": identity["causation_id"],
        "idempotency_key": identity["idempotency_key"],
    }
    enriched_metadata = {**metadata, **aliases}
    # The runtime normalization carrier historically omitted three flat
    # aliases.  They are derivable only from the exact nested identity and
    # are written in the same prepare CAS before the authority digest seals.
    run = replace(_row_to_run(row), metadata=enriched_metadata)
    digest = await _projection_authority_digest(
        db,
        run=run,
        identity=identity,
        witness=witness,
    )
    if not digest:
        return False
    try:
        intent = build_task_board_projection_intent(
            execution_identity=identity,
            action=str(witness["action"]),
            run_status=str(witness["run_status"]),
            source_kind=(
                "idempotency_record"
                if witness["action"] in _RECEIPT_ACTIONS
                else "delegation_run"
            ),
            runtime_authority_snapshot_sha256=digest,
            result=str(witness["result"]),
            metadata_set=dict(witness["metadata_set"]),
            metadata_remove=list(witness["metadata_remove"]),
            completion_binding=witness.get("completion_binding"),
            prepared_at=str(witness["prepared_at"]),
        )
    except (TypeError, ValueError):
        return False
    existing = enriched_metadata.get(TASK_BOARD_PROJECTION_INTENT_KEY)
    if existing is not None:
        return existing == intent and metadata == enriched_metadata
    enriched_metadata[TASK_BOARD_PROJECTION_INTENT_KEY] = intent
    cursor = await db.execute(
        "UPDATE delegation_runs SET metadata_json = ? WHERE run_id = ?"
        " AND status = ? AND metadata_json = ?",
        (
            json.dumps(enriched_metadata, sort_keys=True, separators=(",", ":")),
            run_id,
            str(row["status"]),
            str(row["metadata_json"]),
        ),
    )
    return cursor.rowcount == 1


__all__ = [
    "BOARD_COMPLETION_BINDING_KEY",
    "BOARD_COMPLETION_BINDING_SCHEMA",
    "PROJECTION_WITNESS_SCHEMA",
    "build_task_board_completion_binding",
    "prepare_task_board_projection_snapshot",
    "projection_intent_authority_is_exact",
    "recovery_task_board_projection_metadata",
    "terminal_task_board_projection_metadata",
]
