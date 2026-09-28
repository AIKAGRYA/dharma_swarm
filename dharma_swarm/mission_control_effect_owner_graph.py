"""Canonical Mission Control graph check used as recovery-only context."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from dharma_swarm.mission_control_a2a_owner_snapshot import (
    owner_object,
    owner_text,
    owner_time,
)
from dharma_swarm.mission_control_contract import (
    RECOVERY_RECEIPT_TYPE,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    ReconciliationState,
    TaskView,
)
from dharma_swarm.mission_control_effect_owner import inspect_owner_stores
from dharma_swarm.mission_control_effect_records import OwnerStoreBinding
from dharma_swarm.mission_control_effect_fence_store import row_binding
from dharma_swarm.mission_control_effect_terminal_store import existing_terminal
from dharma_swarm.mission_control_reconciliation import reconciliation
from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.runtime_state import (
    _row_to_claim,
    _row_to_execution_identity,
    _row_to_run,
    _row_to_runtime_receipt,
)
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.runtime_state_effect_fence import (
    EFFECT_FENCE_TABLE,
    EFFECT_RECEIPT_TYPE,
)

_SCAN_LIMIT = 10_000


def _bounded(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    label: str,
) -> list[sqlite3.Row]:
    rows = connection.execute(query, parameters).fetchall()
    if len(rows) > _SCAN_LIMIT:
        raise MissionControlError(f"{label} scan saturated")
    return rows


def _validate_runtime_rows(
    run_rows: list[sqlite3.Row],
    claim_rows: list[sqlite3.Row],
    identity_rows: list[sqlite3.Row],
    receipt_rows: list[sqlite3.Row],
) -> None:
    for row in run_rows:
        owner_object(row["metadata_json"], "Mission Control attempt")
        owner_time(row, "started_at")
        if row["completed_at"] is not None:
            owner_time(row, "completed_at")
    for row in claim_rows:
        owner_object(row["metadata_json"], "Mission Control claim")
        owner_time(row, "claimed_at")
        for name in ("acked_at", "heartbeat_at", "stale_after", "recovered_at"):
            if row[name] is not None:
                owner_time(row, name)
    for row in identity_rows:
        owner_object(row["metadata_json"], "Mission Control identity")
    for row in receipt_rows:
        receipt_type = owner_text(row, "receipt_type")
        raw_payload = owner_text(row, "payload_json")
        payload = owner_object(raw_payload, "Mission Control receipt")
        separators = (",", ":") if receipt_type == EFFECT_RECEIPT_TYPE else None
        if json.dumps(
            payload, sort_keys=True, ensure_ascii=True, separators=separators
        ) != raw_payload:
            raise MissionControlError("Mission Control receipt is noncanonical")
        owner_time(row, "created_at")
        run_id = owner_text(row, "run_id")
        side_effect_key = owner_text(row, "side_effect_key")
        expected_key = {
            TERMINAL_RECEIPT_TYPE: f"mission_control:{run_id}:terminal",
            RECOVERY_RECEIPT_TYPE: f"mission_control:{run_id}:stale_recovery",
        }.get(receipt_type)
        if receipt_type == EFFECT_RECEIPT_TYPE:
            if not side_effect_key:
                raise MissionControlError("effect receipt key is empty")
        elif expected_key is None or side_effect_key != expected_key:
            raise MissionControlError("Mission Control transition slot is aliased")


def _validate_effect_owner_triples(
    connection: sqlite3.Connection,
    receipt_rows: list[sqlite3.Row],
    *,
    expected_owner_stores: OwnerStoreBinding,
) -> None:
    for row in receipt_rows:
        if owner_text(row, "receipt_type") != EFFECT_RECEIPT_TYPE:
            continue
        effect_key = owner_text(row, "side_effect_key")
        fences = connection.execute(
            f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE effect_key=? LIMIT 2",
            (effect_key,),
        ).fetchall()
        if len(fences) != 1:
            raise MissionControlError("exact effect owner fence is not unique")
        binding = row_binding(fences[0])
        if binding.owner_stores != expected_owner_stores:
            raise MissionControlError("effect owner stores disagree with the snapshot source")
        terminal = existing_terminal(connection, fences[0])
        expected = _row_to_runtime_receipt(row)
        if (
            expected.receipt_id != terminal.terminal_receipt_id
            or expected.run_id != binding.mission_attempt_id
            or expected.task_id != binding.task_id
            or expected.trace_id != ""
            or expected.correlation_id != binding.correlation_id
            or expected.causation_id != binding.proposal_receipt_id
            or expected.parent_run_id != binding.executor_run_id
            or expected.agent_id != terminal.claimed_by
            or expected.idempotency_key != "idem_" + terminal.terminal_receipt_id
            or expected.side_effect_key != terminal.effect_key
            or expected.status != "consumed"
            or expected.payload != terminal.to_dict()
            or expected.created_at != terminal.consumed_at
        ):
            raise MissionControlError("exact effect owner triple disagrees")


def _connection_owner_stores(connection: sqlite3.Connection) -> OwnerStoreBinding:
    if type(connection) is not sqlite3.Connection or connection.row_factory is not sqlite3.Row:
        raise MissionControlError("exact owner snapshot identity is required")
    databases = {
        owner_text(row, "name"): owner_text(row, "file")
        for row in connection.execute("PRAGMA database_list").fetchall()
    }
    if (
        set(databases) != {"main", "taskboard"}
        or not databases["main"]
        or not databases["taskboard"]
    ):
        raise MissionControlError("exact owner snapshot identity is required")
    try:
        return inspect_owner_stores(
            Path(databases["main"]), Path(databases["taskboard"])
        )
    except (OSError, ValueError) as exc:
        raise MissionControlError("exact owner snapshot identity is unavailable") from exc


def validate_observed_effect_owner_triples(
    connection: sqlite3.Connection,
    receipts: Sequence[RuntimeReceipt],
    *,
    expected_owner_stores: OwnerStoreBinding | None = None,
) -> None:
    """Rejoin each observed governed effect receipt to one durable triple."""

    if not receipts:
        return
    rows: list[sqlite3.Row] = []
    for receipt in receipts:
        if type(receipt) is not RuntimeReceipt or receipt.receipt_type != EFFECT_RECEIPT_TYPE:
            raise MissionControlError("observed effect receipt has the wrong type")
        matches = connection.execute(
            "SELECT * FROM runtime_receipts WHERE receipt_id=?"
            " AND receipt_type=? LIMIT 2",
            (receipt.receipt_id, EFFECT_RECEIPT_TYPE),
        ).fetchall()
        if len(matches) != 1 or _row_to_runtime_receipt(matches[0]) != receipt:
            raise MissionControlError("observed effect receipt no longer matches its owner")
        rows.append(matches[0])
    _validate_effect_owner_triples(
        connection,
        rows,
        expected_owner_stores=expected_owner_stores
        if expected_owner_stores is not None
        else _connection_owner_stores(connection),
    )


def observe_recovery_owner_graph(
    connection: sqlite3.Connection,
    *,
    mission_id: str,
    task_row: sqlite3.Row,
    task_metadata: dict[str, object],
    original_attempt_id: str,
    observed_at: datetime,
) -> tuple[ReconciliationState, tuple[str, ...]]:
    """Reconcile every lineage for this task and identify later attempts."""

    task_id = owner_text(task_row, "id")
    run_rows = _bounded(
        connection,
        "SELECT * FROM delegation_runs WHERE task_id = ?"
        " ORDER BY started_at LIMIT 10001",
        (task_id,),
        "Mission Control attempt",
    )
    claim_rows = _bounded(
        connection,
        "SELECT * FROM task_claims WHERE task_id = ?"
        " ORDER BY claimed_at LIMIT 10001",
        (task_id,),
        "Mission Control claim",
    )
    run_ids = tuple(owner_text(row, "run_id") for row in run_rows)
    if original_attempt_id not in run_ids:
        raise MissionControlError("original effect attempt is absent")
    placeholders = ",".join("?" for _ in run_ids)
    identity_rows = _bounded(
        connection,
        f"SELECT * FROM execution_identities WHERE run_id IN ({placeholders})"
        " ORDER BY run_id LIMIT 10001",
        run_ids,
        "Mission Control identity",
    )
    side_effect_keys = tuple(
        key
        for run_id in run_ids
        for key in (
            f"mission_control:{run_id}:terminal",
            f"mission_control:{run_id}:stale_recovery",
        )
    )
    key_placeholders = ",".join("?" for _ in side_effect_keys)
    receipt_rows = _bounded(
        connection,
        f"SELECT * FROM runtime_receipts WHERE receipt_type IN (?, ?, ?)"
        f" AND (run_id IN ({placeholders})"
        f" OR side_effect_key IN ({key_placeholders}))"
        " ORDER BY created_at LIMIT 10001",
        (
            TERMINAL_RECEIPT_TYPE,
            RECOVERY_RECEIPT_TYPE,
            EFFECT_RECEIPT_TYPE,
            *run_ids,
            *side_effect_keys,
        ),
        "Mission Control receipt",
    )
    _validate_runtime_rows(run_rows, claim_rows, identity_rows, receipt_rows)
    _validate_effect_owner_triples(
        connection,
        receipt_rows,
        expected_owner_stores=_connection_owner_stores(connection),
    )
    runs = [_row_to_run(row) for row in run_rows]
    claims = [_row_to_claim(row) for row in claim_rows]
    receipts = [_row_to_runtime_receipt(row) for row in receipt_rows]
    identities = {
        identity.run_id: identity
        for identity in (_row_to_execution_identity(row) for row in identity_rows)
    }
    task = TaskView(
        task_id=task_id,
        mission_id=mission_id,
        title=owner_text(task_row, "title"),
        description=owner_text(task_row, "description"),
        status=TaskStatus(owner_text(task_row, "status")),
        priority=TaskPriority(owner_text(task_row, "priority")),
        assigned_to=str(task_row["assigned_to"] or ""),
        result=str(task_row["result"] or ""),
        metadata=dict(task_metadata),
        created_at=owner_time(task_row, "created_at"),
        updated_at=owner_time(task_row, "updated_at"),
    )
    original_started = next(
        run.started_at for run in runs if run.run_id == original_attempt_id
    )
    successors = tuple(
        run.run_id
        for run in runs
        if run.run_id != original_attempt_id and run.started_at >= original_started
    )
    return (
        reconciliation(
            mission_id, (task,), runs, claims, receipts, identities, observed_at,
        ),
        successors,
    )


__all__ = [
    "observe_recovery_owner_graph",
    "validate_observed_effect_owner_triples",
]
