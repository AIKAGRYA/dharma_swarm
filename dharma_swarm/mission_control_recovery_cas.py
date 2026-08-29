"""Exact owner-store CAS for one expired Mission Control lineage."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from dharma_swarm.mission_control_contract import (
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    completion_contract_from_metadata,
    receipt_matches_identity,
    recovery_receipt_matches_contract,
    session_id,
    stable_id,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    TaskClaim,
    _row_to_claim,
    _row_to_execution_identity,
    _row_to_run,
    _row_to_runtime_receipt,
)
from dharma_swarm.runtime_state_effect_fence import EFFECT_RECEIPT_TYPE
from dharma_swarm.spine.identity import ExecutionIdentity


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _one(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    label: str,
) -> sqlite3.Row:
    rows = connection.execute(query, parameters).fetchall()
    if len(rows) != 1:
        raise MissionControlError(f"canonical {label} row is not unique")
    return rows[0]


def _task_matches(row: sqlite3.Row, task: Task) -> bool:
    try:
        metadata = json.loads(str(row["metadata"]))
    except (TypeError, ValueError):
        return False
    return bool(
        row["id"] == task.id
        and row["title"] == task.title
        and row["description"] == task.description
        and row["status"] == task.status.value
        and row["priority"] == task.priority.value
        and row["assigned_to"] == task.assigned_to
        and row["created_by"] == task.created_by
        and row["created_at"] == task.created_at.isoformat()
        and row["updated_at"] == task.updated_at.isoformat()
        and row["result"] == task.result
        and metadata == task.metadata
    )


def _canonical_preimage(
    mission_id: str,
    task: Task,
    run: DelegationRun,
    claim: TaskClaim,
    identity: ExecutionIdentity,
    recovered_at: datetime,
) -> bool:
    try:
        completion_contract = completion_contract_from_metadata(task.metadata)
    except MissionControlError:
        return False
    expected_identity_metadata: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
    }
    if completion_contract:
        expected_identity_metadata["completion_contract"] = completion_contract
    # Heartbeat records the claim activation before it records the run's
    # queued-to-running transition.  Recovery owns only this one interrupted
    # durable window; pre-heartbeat and already-running states are not
    # interchangeable recovery preimages.
    interrupted_heartbeat = (run.status, claim.status.lower()) == ("queued", "active")
    timeline = (
        claim.acked_at is not None
        and claim.heartbeat_at is not None
        and claim.acked_at == claim.heartbeat_at
        and claim.claimed_at <= claim.acked_at
    )
    task_projection = (
        task.status == TaskStatus.ASSIGNED
        and task.assigned_to == run.assigned_to
        and task.metadata.get("mission_attempt_id") == run.run_id
        and task.metadata.get("mission_claim_id") == claim.claim_id
    )
    return bool(
        interrupted_heartbeat
        and timeline
        and task_projection
        and task.status
        in {TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING}
        and run.completed_at is None
        and run.failure_code == ""
        and claim.recovered_at is None
        and claim.stale_after is not None
        and claim.heartbeat_at is not None
        and claim.heartbeat_at <= claim.stale_after
        and claim.claimed_at == run.started_at
        and claim.claimed_at < claim.stale_after <= recovered_at
        and run.task_id == task.id == claim.task_id == identity.task_id
        and task.metadata.get("schema_version") == SCHEMA_VERSION
        and task.metadata.get("mission_id") == mission_id
        and run.session_id == claim.session_id == identity.session_id
        == session_id(mission_id)
        and run.run_id == identity.run_id
        and run.claim_id == claim.claim_id == identity.claim_id
        and run.assigned_to == claim.agent_id == identity.agent_id
        and run.session_id == claim.session_id == identity.session_id
        and run.parent_run_id == identity.parent_run_id == ""
        and identity.idempotency_key == run.metadata.get("attempt_key")
        and run.metadata.get("schema_version") == SCHEMA_VERSION
        and run.metadata.get("mission_id") == mission_id
        and run.metadata.get("attempt_id") == run.run_id
        and claim.metadata.get("attempt_id") == run.run_id
        and claim.metadata.get("schema_version") == SCHEMA_VERSION
        and claim.metadata.get("mission_id") == mission_id
        and claim.metadata.get("attempt_key") == identity.idempotency_key
        and identity.trace_id == stable_id("trace", run.run_id)
        and identity.correlation_id == f"mission:{mission_id}:attempt:{run.run_id}"
        and identity.metadata == expected_identity_metadata
        and not any(
            (
                identity.causation_id,
                identity.parent_run_id,
                identity.external_a2a_task_id,
                identity.message_id,
                identity.event_id,
                identity.artifact_id,
                identity.proposal_id,
            )
        )
    )


def _exact_poststate(
    run_row: sqlite3.Row,
    claim_row: sqlite3.Row,
    run: DelegationRun,
    claim: TaskClaim,
    receipt: RuntimeReceipt,
    recovered_at: datetime,
) -> bool:
    expected_run = DelegationRun(
        **{
            **run.__dict__,
            "status": "stale_recovered",
            "completed_at": recovered_at,
            "failure_code": "stale_lease_recovered",
            "metadata": {
                **run.metadata,
                "recovered_claim_id": claim.claim_id,
                "recovery_receipt_id": receipt.receipt_id,
            },
        }
    )
    expected_claim = TaskClaim(
        **{
            **claim.__dict__,
            "status": "stale_recovered",
            "recovered_at": recovered_at,
            "metadata": {
                **claim.metadata,
                "recovery_receipt_id": receipt.receipt_id,
            },
        }
    )
    return bool(
        _row_to_run(run_row) == expected_run
        and _row_to_claim(claim_row) == expected_claim
        and run_row["receipt_json"] is None
    )


def recover_stale_lineage_cas(
    connection: sqlite3.Connection,
    *,
    mission_id: str,
    task: Task,
    run: DelegationRun,
    claim: TaskClaim,
    identity: ExecutionIdentity,
    receipt: RuntimeReceipt,
    recovered_at: datetime,
) -> RuntimeReceipt:
    """Commit or exact-replay one stale transition in the joined transaction."""

    if (
        type(connection) is not sqlite3.Connection
        or not connection.in_transaction
        or connection.row_factory is not sqlite3.Row
        or type(task) is not Task
        or type(run) is not DelegationRun
        or type(claim) is not TaskClaim
        or type(identity) is not ExecutionIdentity
        or type(receipt) is not RuntimeReceipt
        or recovered_at.tzinfo is None
        or not _canonical_preimage(
            mission_id, task, run, claim, identity, recovered_at
        )
        or not receipt_matches_identity(receipt, identity)
        or not recovery_receipt_matches_contract(
            receipt,
            identity,
            mission_id,
            expired_stale_after=claim.stale_after,
        )
        or not claim.stale_after <= receipt.created_at <= recovered_at
    ):
        raise MissionControlError("exact stale recovery expectation is required")
    task_row = _one(
        connection,
        "SELECT * FROM taskboard.tasks WHERE id=? LIMIT 2",
        (task.id,),
        "TaskBoard task",
    )
    run_row = _one(
        connection,
        "SELECT * FROM delegation_runs WHERE run_id=? LIMIT 2",
        (run.run_id,),
        "attempt",
    )
    claim_row = _one(
        connection,
        "SELECT * FROM task_claims WHERE claim_id=? LIMIT 2",
        (claim.claim_id,),
        "claim",
    )
    identity_row = _one(
        connection,
        "SELECT * FROM execution_identities WHERE run_id=? LIMIT 2",
        (identity.run_id,),
        "identity",
    )
    transition_keys = (
        f"mission_control:{run.run_id}:terminal",
        receipt.side_effect_key,
    )
    receipt_rows = connection.execute(
        "SELECT * FROM runtime_receipts WHERE"
        " (run_id=? AND receipt_type IN (?,?,?)) OR side_effect_key IN (?,?)"
        " LIMIT 4",
        (
            run.run_id,
            TERMINAL_RECEIPT_TYPE,
            RECOVERY_RECEIPT_TYPE,
            EFFECT_RECEIPT_TYPE,
            *transition_keys,
        ),
    ).fetchall()
    idempotency_rows = connection.execute(
        "SELECT * FROM idempotency_records WHERE side_effect_key IN (?,?)"
        " OR result_receipt_id=? LIMIT 4",
        (*transition_keys, receipt.receipt_id),
    ).fetchall()
    newer_claim = connection.execute(
        "SELECT 1 FROM task_claims WHERE task_id=? AND claim_id<>?"
        " AND claimed_at>=? LIMIT 1",
        (task.id, claim.claim_id, claim.claimed_at.isoformat()),
    ).fetchone()
    newer_run = connection.execute(
        "SELECT 1 FROM delegation_runs WHERE task_id=? AND run_id<>?"
        " AND started_at>=? LIMIT 1",
        (task.id, run.run_id, run.started_at.isoformat()),
    ).fetchone()
    if (
        not _task_matches(task_row, task)
        or _row_to_execution_identity(identity_row) != identity
        or identity_row["source"] != "mission_control.start_attempt"
        or newer_claim is not None
        or newer_run is not None
        or idempotency_rows
    ):
        raise MissionControlError("stale recovery owner preimage drifted")
    if receipt_rows:
        if (
            len(receipt_rows) != 1
            or _row_to_runtime_receipt(receipt_rows[0]) != receipt
            or not _exact_poststate(
                run_row, claim_row, run, claim, receipt, recovered_at
            )
        ):
            raise MissionControlError("stale recovery replay conflicts")
        return receipt
    if (
        _row_to_run(run_row) != run
        or _row_to_claim(claim_row) != claim
        or run_row["receipt_json"] is not None
    ):
        raise MissionControlError("stale recovery owner preimage drifted")
    connection.execute(
        "INSERT INTO runtime_receipts"
        " (receipt_id,receipt_type,run_id,task_id,trace_id,correlation_id,"
        " causation_id,parent_run_id,agent_id,idempotency_key,side_effect_key,"
        " status,payload_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            receipt.receipt_id,
            receipt.receipt_type,
            receipt.run_id,
            receipt.task_id,
            receipt.trace_id,
            receipt.correlation_id,
            receipt.causation_id,
            receipt.parent_run_id,
            receipt.agent_id,
            receipt.idempotency_key,
            receipt.side_effect_key,
            receipt.status,
            _json(receipt.payload),
            receipt.created_at.isoformat(),
        ),
    )
    run_metadata = {
        **run.metadata,
        "recovered_claim_id": claim.claim_id,
        "recovery_receipt_id": receipt.receipt_id,
    }
    claim_metadata = {
        **claim.metadata,
        "recovery_receipt_id": receipt.receipt_id,
    }
    run_cursor = connection.execute(
        "UPDATE delegation_runs SET status='stale_recovered',completed_at=?,"
        " failure_code='stale_lease_recovered',metadata_json=? WHERE run_id=?"
        " AND status=? AND completed_at IS NULL AND failure_code='' AND metadata_json=?",
        (
            recovered_at.isoformat(),
            _json(run_metadata),
            run.run_id,
            run.status,
            _json(run.metadata),
        ),
    )
    claim_cursor = connection.execute(
        "UPDATE task_claims SET status='stale_recovered',recovered_at=?,metadata_json=?"
        " WHERE claim_id=? AND status=? AND stale_after=? AND recovered_at IS NULL"
        " AND metadata_json=?",
        (
            recovered_at.isoformat(),
            _json(claim_metadata),
            claim.claim_id,
            claim.status,
            claim.stale_after.isoformat(),
            _json(claim.metadata),
        ),
    )
    if run_cursor.rowcount != 1 or claim_cursor.rowcount != 1:
        raise MissionControlError("expired claim recovery CAS was lost")
    post_run = _one(
        connection,
        "SELECT * FROM delegation_runs WHERE run_id=? LIMIT 2",
        (run.run_id,),
        "post-recovery attempt",
    )
    post_claim = _one(
        connection,
        "SELECT * FROM task_claims WHERE claim_id=? LIMIT 2",
        (claim.claim_id,),
        "post-recovery claim",
    )
    if not _exact_poststate(
        post_run, post_claim, run, claim, receipt, recovered_at
    ):
        raise MissionControlError("stale recovery postread disagrees")
    return receipt


__all__ = ["recover_stale_lineage_cas"]
