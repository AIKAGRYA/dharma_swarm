"""Recovery-only observation of one expired Mission Control owner lineage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from dharma_swarm.mission_control_a2a import _receipt_digest
from dharma_swarm.mission_control_a2a_candidate import (
    ExactProposalStoreExpectation,
    require_store_expectation,
    require_task_native_ref,
)
from dharma_swarm.mission_control_a2a_owner_snapshot import (
    one_owner_row,
    owner_object,
    owner_text,
    owner_time,
    require_owner_schema,
)
from dharma_swarm.mission_control_contract import (
    MAX_LEASE_SECONDS,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    ReconciliationState,
    recovery_receipt_matches_contract,
    stable_id,
    terminal_operation_metadata,
    terminal_receipt_contract,
)
from dharma_swarm.mission_control_effect_owner_graph import (
    observe_recovery_owner_graph,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.spine.identity import ExecutionIdentity


@dataclass(frozen=True, slots=True)
class ExpiredProposalRecoveryObservation:
    """Historical owner evidence which cannot inhabit issuance or apply."""

    mission_id: str
    task_id: str
    mission_attempt_id: str
    mission_claim_id: str
    proposal_id: str
    executor_run_id: str
    executor_process_boot_id: str
    proposal_receipt_id: str
    proposal_receipt_sha256: str
    lease_acked_at: datetime
    lease_stale_after: datetime
    observed_at: datetime
    owner_transition: Literal[
        "expired_active", "canonical_stale_recovery", "canonical_terminal"
    ]
    owner_reconciliation: Literal[
        "expired_lease", "coherent", "needs_task_projection"
    ]
    transition_receipt_id: str
    transition_receipt_sha256: str
    successor_attempt_ids: tuple[str, ...]
    recovery_only: Literal[True] = True
    authorizes_effect_issuance: Literal[False] = False
    authorizes_repository_apply: Literal[False] = False

    def __bool__(self) -> bool:
        raise TypeError("expired owner evidence is recovery-only, not authority")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, tuple):
                value = list(value)
            result[name] = value
        return result


@dataclass(frozen=True, slots=True)
class _ExpiredRecoveryBinding:
    mission_attempt_id: str
    mission_claim_id: str
    proposal_receipt_id: str
    proposal_receipt_sha256: str


def _runtime_object(raw: object, label: str) -> dict[str, Any]:
    value = owner_object(raw, label)
    if json.dumps(value, sort_keys=True, ensure_ascii=True) != raw:
        raise MissionControlError(f"{label} is not in RuntimeState canonical form")
    return value


def _attempt_identity(
    connection: sqlite3.Connection,
    expected: ExactProposalStoreExpectation,
    attempt_id: str,
    claim_id: str,
) -> ExecutionIdentity:
    ref = expected.native_ref
    row = one_owner_row(
        connection,
        "SELECT * FROM execution_identities WHERE run_id = ? LIMIT 2",
        (attempt_id,),
        "Mission Control parent identity",
    )
    metadata = owner_object(row["metadata_json"], "parent identity")
    values = {
        "trace_id": stable_id("trace", attempt_id),
        "correlation_id": f"mission:{ref.mission_id}:attempt:{attempt_id}",
        "task_id": ref.task_id,
        "run_id": attempt_id,
        "claim_id": claim_id,
        "idempotency_key": expected.attempt_key,
        "causation_id": "",
        "parent_run_id": "",
        "agent_id": ref.agent_uid,
        "session_id": f"mission:{ref.mission_id}",
        "external_a2a_task_id": "",
        "message_id": "",
        "event_id": "",
        "artifact_id": "",
        "proposal_id": "",
    }
    if (
        any(owner_text(row, name) != value for name, value in values.items())
        or owner_text(row, "source") != "mission_control.start_attempt"
        or metadata
        != {"schema_version": SCHEMA_VERSION, "mission_id": ref.mission_id}
    ):
        raise MissionControlError("Mission Control parent identity disagrees")
    return ExecutionIdentity(**values, metadata=metadata)


def _runtime_receipt(row: sqlite3.Row) -> RuntimeReceipt:
    payload = _runtime_object(
        owner_text(row, "payload_json"), "Mission Control recovery receipt",
    )
    created_at = owner_time(row, "created_at")
    return RuntimeReceipt(
        receipt_id=owner_text(row, "receipt_id"),
        receipt_type=owner_text(row, "receipt_type"),
        status=owner_text(row, "status"),
        run_id=owner_text(row, "run_id"),
        task_id=owner_text(row, "task_id"),
        trace_id=owner_text(row, "trace_id"),
        correlation_id=owner_text(row, "correlation_id"),
        causation_id=owner_text(row, "causation_id"),
        parent_run_id=owner_text(row, "parent_run_id"),
        agent_id=owner_text(row, "agent_id"),
        idempotency_key=owner_text(row, "idempotency_key"),
        side_effect_key=owner_text(row, "side_effect_key"),
        payload=payload,
        created_at=created_at,
    )


def _terminal_slot_matches(
    row: sqlite3.Row,
    receipt: RuntimeReceipt,
    identity: ExecutionIdentity,
    mission_id: str,
) -> bool:
    operation_hash, expected_metadata = terminal_operation_metadata(
        receipt, identity, mission_id,
    )
    metadata = _runtime_object(
        owner_text(row, "metadata_json"), "Mission Control terminal slot",
    )
    created_at = owner_time(row, "created_at")
    updated_at = owner_time(row, "updated_at")
    return bool(
        owner_text(row, "idempotency_key") == identity.idempotency_key
        and owner_text(row, "side_effect_key") == receipt.side_effect_key
        and owner_text(row, "run_id") == identity.run_id
        and owner_text(row, "task_id") == identity.task_id
        and owner_text(row, "trace_id") == identity.trace_id
        and owner_text(row, "correlation_id") == identity.correlation_id
        and owner_text(row, "status") == "completed"
        and owner_text(row, "result_receipt_id") == receipt.receipt_id
        and metadata == expected_metadata
        and metadata.get("operation_hash") == operation_hash
        and created_at <= updated_at
    )


def observe_expired_proposal_for_effect_recovery_from_connection(
    connection: sqlite3.Connection,
    expected: ExactProposalStoreExpectation,
    *,
    mission_attempt_id: str,
    mission_claim_id: str,
    proposal_receipt_id: str,
    proposal_receipt_sha256: str,
) -> ExpiredProposalRecoveryObservation:
    """Prove one expired, unchanged lineage without minting live authority."""

    values = (
        mission_attempt_id,
        mission_claim_id,
        proposal_receipt_id,
        proposal_receipt_sha256,
    )
    databases: dict[str, str] = {}
    if type(connection) is sqlite3.Connection and connection.row_factory is sqlite3.Row:
        databases = {
            owner_text(row, "name"): owner_text(row, "file")
            for row in connection.execute("PRAGMA database_list").fetchall()
        }
    if (
        type(connection) is not sqlite3.Connection
        or not connection.in_transaction
        or connection.row_factory is not sqlite3.Row
        or set(databases) != {"main", "taskboard"}
        or not databases["main"]
        or not databases["taskboard"]
        or databases["main"] == databases["taskboard"]
        or any(type(value) is not str or not value or len(value) > 512 for value in values)
        or len(proposal_receipt_sha256) != 64
        or proposal_receipt_sha256 != proposal_receipt_sha256.lower()
        or any(character not in "0123456789abcdef" for character in proposal_receipt_sha256)
    ):
        raise MissionControlError("exact expired recovery binding is required")
    require_store_expectation(expected)
    require_owner_schema(connection)
    ref = expected.native_ref
    attempt_id = stable_id(
        "attempt", ref.mission_id, ref.task_id, ref.agent_uid, expected.attempt_key,
    )
    claim_id = stable_id("lease", attempt_id)
    if (attempt_id, claim_id) != (mission_attempt_id, mission_claim_id):
        raise MissionControlError("stored recovery lifecycle binding disagrees")
    observed_at = datetime.now(timezone.utc)
    session = one_owner_row(
        connection,
        "SELECT * FROM sessions WHERE session_id = ? LIMIT 2",
        (f"mission:{ref.mission_id}",),
        "mission session",
    )
    session_metadata = owner_object(session["metadata_json"], "mission")
    if (
        owner_text(session, "status") != "active"
        or owner_text(session, "operator_id") != expected.operator_id
        or session_metadata.get("schema_version") != SCHEMA_VERSION
        or session_metadata.get("mission_id") != ref.mission_id
    ):
        raise MissionControlError("mission session binding disagrees")
    task = one_owner_row(
        connection,
        "SELECT * FROM taskboard.tasks WHERE id = ? LIMIT 2",
        (ref.task_id,),
        "Mission Control task",
    )
    task_metadata = owner_object(task["metadata"], "task")
    require_task_native_ref(task_metadata, ref)
    if (
        owner_text(task, "status") not in {status.value for status in TaskStatus}
        or task_metadata.get("schema_version") != SCHEMA_VERSION
        or task_metadata.get("mission_id") != ref.mission_id
    ):
        raise MissionControlError("Mission Control task projection disagrees")
    run = one_owner_row(
        connection,
        "SELECT * FROM delegation_runs WHERE run_id = ? LIMIT 2",
        (attempt_id,),
        "Mission Control attempt",
    )
    run_metadata = owner_object(run["metadata_json"], "attempt")
    lineage = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": ref.mission_id,
        "attempt_id": attempt_id,
        "attempt_key": expected.attempt_key,
    }
    if (
        (
            owner_text(run, "session_id"),
            owner_text(run, "task_id"),
            owner_text(run, "claim_id"),
            owner_text(run, "assigned_to"),
            owner_text(run, "assigned_by"),
        )
        != (
            f"mission:{ref.mission_id}",
            ref.task_id,
            claim_id,
            ref.agent_uid,
            expected.assigned_by,
        )
        or any(run_metadata.get(key) != value for key, value in lineage.items())
        or ("quarantined_at" in run.keys() and run["quarantined_at"] not in (None, ""))
    ):
        raise MissionControlError("Mission Control attempt binding disagrees")
    identity = _attempt_identity(connection, expected, attempt_id, claim_id)
    claim = one_owner_row(
        connection,
        "SELECT * FROM task_claims WHERE claim_id = ? LIMIT 2",
        (claim_id,),
        "Mission Control claim",
    )
    claim_metadata = owner_object(claim["metadata_json"], "claim")
    if (
        (
            owner_text(claim, "session_id"),
            owner_text(claim, "task_id"),
            owner_text(claim, "agent_id"),
        )
        != (f"mission:{ref.mission_id}", ref.task_id, ref.agent_uid)
        or any(claim_metadata.get(key) != value for key, value in lineage.items())
    ):
        raise MissionControlError("Mission Control claim binding disagrees")
    claimed_at = owner_time(claim, "claimed_at")
    acked_at = owner_time(claim, "acked_at")
    heartbeat_at = owner_time(claim, "heartbeat_at")
    stale_after = owner_time(claim, "stale_after")
    transition_keys = (
        f"mission_control:{attempt_id}:terminal",
        f"mission_control:{attempt_id}:stale_recovery",
    )
    transition_rows = connection.execute(
        "SELECT * FROM runtime_receipts WHERE receipt_type IN (?, ?)"
        " AND (run_id = ? OR side_effect_key IN (?, ?))"
        " ORDER BY created_at LIMIT 4",
        (
            TERMINAL_RECEIPT_TYPE,
            RECOVERY_RECEIPT_TYPE,
            attempt_id,
            *transition_keys,
        ),
    ).fetchall()
    terminals = [
        row for row in transition_rows if row["receipt_type"] == TERMINAL_RECEIPT_TYPE
    ]
    recoveries = [
        row for row in transition_rows if row["receipt_type"] == RECOVERY_RECEIPT_TYPE
    ]
    transition_slots = connection.execute(
        "SELECT * FROM idempotency_records WHERE side_effect_key IN (?, ?) LIMIT 3",
        transition_keys,
    ).fetchall()
    active_expired = owner_text(claim, "status") == "active"
    transition_receipt_id = transition_receipt_sha256 = ""
    successors: tuple[str, ...] = ()
    if terminals:
        if (
            len(transition_rows) != 1
            or len(terminals) != 1
            or recoveries
            or len(transition_slots) != 1
        ):
            raise MissionControlError("canonical terminal evidence is not unique")
        terminal = _runtime_receipt(terminals[0])
        terminal_receipt_contract(terminal, identity, ref.mission_id)
        if (
            not _terminal_slot_matches(
                transition_slots[0], terminal, identity, ref.mission_id,
            )
            or terminal.created_at > observed_at
            or not claimed_at <= acked_at <= heartbeat_at
        ):
            raise MissionControlError("canonical terminal transition disagrees")
        graph_state, successors = observe_recovery_owner_graph(
            connection,
            mission_id=ref.mission_id,
            task_row=task,
            task_metadata=task_metadata,
            original_attempt_id=attempt_id,
            observed_at=observed_at,
        )
        if (
            graph_state
            not in {
                ReconciliationState.COHERENT,
                ReconciliationState.NEEDS_TASK_PROJECTION,
            }
            or successors
        ):
            raise MissionControlError("terminal owner graph is not recoverable")
        transition_receipt_id = terminal.receipt_id
        transition_receipt_sha256 = _receipt_digest(terminal)
        owner_transition = "canonical_terminal"
        owner_reconciliation = graph_state.value
        lease_boundary = terminal.created_at
    elif active_expired:
        if (
            owner_text(run, "status") != "running"
            or run["completed_at"] is not None
            or owner_text(run, "failure_code") != ""
            or claim["recovered_at"] is not None
            or transition_rows
            or transition_slots
            or not claimed_at <= acked_at <= heartbeat_at < stale_after <= observed_at
            or (stale_after - heartbeat_at).total_seconds() > MAX_LEASE_SECONDS
            or owner_text(task, "status") != TaskStatus.RUNNING.value
            or owner_text(task, "assigned_to") != ref.agent_uid
            or task_metadata.get("mission_attempt_id") != attempt_id
            or task_metadata.get("mission_claim_id") != claim_id
        ):
            raise MissionControlError("expired active owner lineage disagrees")
        later = connection.execute(
            "SELECT run_id FROM delegation_runs WHERE task_id = ? AND run_id != ?"
            " AND started_at >= ? LIMIT 2",
            (ref.task_id, attempt_id, owner_text(run, "started_at")),
        ).fetchall()
        if later:
            raise MissionControlError("expired active lineage has a successor")
        owner_transition = "expired_active"
        owner_reconciliation = ReconciliationState.EXPIRED_LEASE.value
        lease_boundary = stale_after
    else:
        if (
            len(transition_rows) != 1
            or terminals
            or len(recoveries) != 1
            or transition_slots
        ):
            raise MissionControlError("canonical stale recovery evidence is not unique")
        recovery = _runtime_receipt(recoveries[0])
        recovered_at = owner_time(claim, "recovered_at")
        completed_at = owner_time(run, "completed_at")
        expected_receipt_id = stable_id("receipt", attempt_id, "stale_recovered")
        if (
            owner_text(claim, "status") != "stale_recovered"
            or owner_text(run, "status") != "stale_recovered"
            or owner_text(run, "failure_code") != "stale_lease_recovered"
            or claim_metadata.get("recovery_receipt_id") != expected_receipt_id
            or run_metadata.get("recovered_claim_id") != claim_id
            or run_metadata.get("recovery_receipt_id") != expected_receipt_id
            or not recovery_receipt_matches_contract(
                recovery,
                identity,
                ref.mission_id,
                expired_stale_after=stale_after,
            )
            or not claimed_at <= acked_at <= heartbeat_at < stale_after
            or not stale_after <= recovery.created_at <= recovered_at <= observed_at
            or (stale_after - heartbeat_at).total_seconds() > MAX_LEASE_SECONDS
            or completed_at != recovered_at
        ):
            raise MissionControlError("canonical stale recovery transition disagrees")
        graph_state, successors = observe_recovery_owner_graph(
            connection,
            mission_id=ref.mission_id,
            task_row=task,
            task_metadata=task_metadata,
            original_attempt_id=attempt_id,
            observed_at=observed_at,
        )
        if graph_state not in {
            ReconciliationState.COHERENT,
            ReconciliationState.NEEDS_TASK_PROJECTION,
        }:
            raise MissionControlError("successor owner graph is not recoverable")
        transition_receipt_id = recovery.receipt_id
        transition_receipt_sha256 = _receipt_digest(recovery)
        owner_transition = "canonical_stale_recovery"
        owner_reconciliation = graph_state.value
        lease_boundary = stale_after
    from dharma_swarm.mission_control_a2a_owner_readback import _observe_candidate

    result = _observe_candidate(
        connection,
        expected,
        attempt_id=attempt_id,
        claim_id=claim_id,
        observed_at=observed_at,
        lease_acked_at=acked_at,
        lease_stale_after=lease_boundary,
        expired_recovery=_ExpiredRecoveryBinding(
            mission_attempt_id=mission_attempt_id,
            mission_claim_id=mission_claim_id,
            proposal_receipt_id=proposal_receipt_id,
            proposal_receipt_sha256=proposal_receipt_sha256,
        ),
        expired_owner_transition=owner_transition,
        expired_owner_reconciliation=owner_reconciliation,
        transition_receipt_id=transition_receipt_id,
        transition_receipt_sha256=transition_receipt_sha256,
        successor_attempt_ids=successors,
    )
    if type(result) is not ExpiredProposalRecoveryObservation:
        raise MissionControlError("expired recovery readback returned live authority")
    return result


__all__ = [
    "ExpiredProposalRecoveryObservation",
    "observe_expired_proposal_for_effect_recovery_from_connection",
]
