"""Non-authorizing readback of exact proposal and Mission Control owner state."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.mission_control_a2a import (
    PATCH_CANDIDATE_SCHEMA,
    _receipt_digest,
)
from dharma_swarm.mission_control_a2a_candidate import (
    ExactProposalStoreExpectation,
    ExactProposalStoreObservation,
    _load_canonical_object,
    load_exact_proposals_from_connection,
    require_store_expectation,
    require_task_native_ref,
    unwrap_exact_proposal,
)
from dharma_swarm.mission_control_a2a_owner_snapshot import (
    one_owner_row,
    owner_object,
    owner_text,
    owner_time,
    read_only_owner_snapshot,
    require_owner_schema,
)
from dharma_swarm.mission_control_contract import (
    MAX_LEASE_SECONDS,
    OPEN_CLAIM_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    stable_id,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.spine.identity import ExecutionIdentity

_OWNER_SCAN_LIMIT = 10_000
_PATCH_EVIDENCE_FIELDS = {
    "schema_version",
    "mission_id",
    "task_id",
    "attempt_id",
    "lease_id",
    "packet_id",
    "correlation_id",
    "delivery_id",
    "proposal_id",
    "candidate_digest",
    "diff_sha256",
    "base_sha",
    "artifact_sha256",
    "authorized_source_files",
}


def _require_no_terminal_transition(
    connection: sqlite3.Connection,
    attempt_id: str,
) -> None:
    terminal_key = f"mission_control:{attempt_id}:terminal"
    recovery_key = f"mission_control:{attempt_id}:stale_recovery"
    lifecycle = connection.execute(
        "SELECT 1 FROM runtime_receipts WHERE"
        " (run_id = ? AND receipt_type IN (?, ?))"
        " OR side_effect_key IN (?, ?) LIMIT 1",
        (
            attempt_id,
            TERMINAL_RECEIPT_TYPE,
            RECOVERY_RECEIPT_TYPE,
            terminal_key,
            recovery_key,
        ),
    ).fetchone()
    transition = connection.execute(
        "SELECT 1 FROM idempotency_records WHERE side_effect_key IN (?, ?) LIMIT 1",
        (terminal_key, recovery_key),
    ).fetchone()
    if lifecycle is not None or transition is not None:
        raise MissionControlError("Mission Control attempt is transitioning terminal")


def _observe_candidate(
    connection: sqlite3.Connection,
    expected: ExactProposalStoreExpectation,
    *,
    attempt_id: str,
    claim_id: str,
    observed_at: datetime,
    lease_acked_at: datetime,
    lease_stale_after: datetime,
) -> ExactProposalStoreObservation:
    ref = expected.native_ref
    rows = connection.execute(
        "SELECT * FROM execution_identities WHERE parent_run_id = ?"
        " AND claim_id = ? AND session_id = ? AND task_id = ? AND agent_id = ?"
        " AND proposal_id = ? AND correlation_id = ? AND source = ? LIMIT 3",
        (
            attempt_id,
            claim_id,
            f"mission:{ref.mission_id}",
            ref.task_id,
            ref.agent_uid,
            ref.proposal_id,
            ref.correlation_id,
            "exact:governed_patch_semantic_executor",
        ),
    ).fetchall()
    if len(rows) != 1:
        raise MissionControlError("exact semantic executor lineage is not unique")
    row = rows[0]
    metadata = _load_canonical_object(
        owner_text(row, "metadata_json"),
        label="exact semantic executor metadata",
    )
    identity = ExecutionIdentity(
        **{
            name: owner_text(row, name)
            for name in (
                "trace_id",
                "correlation_id",
                "task_id",
                "run_id",
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
        },
        metadata=metadata,
    )
    required_metadata = {
        "process_boot_id": expected.executor_process_boot_id,
        "role": "governed_patch_semantic_executor",
    }
    if identity.run_id != expected.executor_run_id or metadata != required_metadata:
        raise MissionControlError("exact semantic executor binding disagrees")
    records = load_exact_proposals_from_connection(
        connection,
        ref,
        scan_limit=_OWNER_SCAN_LIMIT,
    )
    if len(records) != 1:
        raise MissionControlError("exact proposal evidence is not unique")
    evidence = unwrap_exact_proposal(records[0], ref, identity)
    required = {
        "schema_version": PATCH_CANDIDATE_SCHEMA,
        "mission_id": ref.mission_id,
        "task_id": ref.task_id,
        "attempt_id": ref.packet_id,
        "lease_id": ref.delivery_id,
        "packet_id": ref.packet_id,
        "correlation_id": ref.correlation_id,
        "delivery_id": ref.delivery_id,
        "proposal_id": ref.proposal_id,
        "candidate_digest": expected.candidate_digest,
        "diff_sha256": expected.diff_sha256,
        "base_sha": expected.base_sha,
        "artifact_sha256": expected.artifact_sha256,
        "authorized_source_files": list(expected.authorized_source_files),
    }
    if set(evidence) != _PATCH_EVIDENCE_FIELDS or evidence != required:
        raise MissionControlError("exact proposal candidate binding disagrees")
    receipt = records[0].receipt
    if not lease_stale_after > observed_at >= receipt.created_at >= lease_acked_at:
        raise MissionControlError("exact proposal is outside the observed lease window")
    return ExactProposalStoreObservation._mint(
        native_ref=ref,
        mission_attempt_id=attempt_id,
        mission_claim_id=claim_id,
        executor_run_id=identity.run_id,
        executor_process_boot_id=expected.executor_process_boot_id,
        proposal_receipt_id=receipt.receipt_id,
        proposal_receipt_sha256=_receipt_digest(receipt),
        observed_at=observed_at,
        lease_stale_after=lease_stale_after,
    )


def observe_exact_proposal_store(
    runtime_database: Path,
    task_database: Path,
    expected: ExactProposalStoreExpectation,
) -> ExactProposalStoreObservation:
    """Return one internally consistent observation with no effect authority."""

    require_store_expectation(expected)
    ref = expected.native_ref
    session_id = f"mission:{ref.mission_id}"
    attempt_id = stable_id(
        "attempt",
        ref.mission_id,
        ref.task_id,
        ref.agent_uid,
        expected.attempt_key,
    )
    claim_id = stable_id("lease", attempt_id)
    if {attempt_id, claim_id} & {ref.packet_id, ref.delivery_id}:
        raise MissionControlError("transport and Mission Control IDs are aliased")

    with read_only_owner_snapshot(runtime_database, task_database) as connection:
        require_owner_schema(connection)
        observed_at = datetime.now(timezone.utc)
        session = one_owner_row(
            connection,
            "SELECT * FROM sessions WHERE session_id = ? LIMIT 2",
            (session_id,),
            "mission session",
        )
        session_metadata = owner_object(session["metadata_json"], "mission")
        if (
            owner_text(session, "status") != "active"
            or owner_text(session, "operator_id") != expected.operator_id
            or session_metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
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
            owner_text(task, "status") != TaskStatus.RUNNING.value
            or owner_text(task, "assigned_to") != ref.agent_uid
            or task_metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
            or task_metadata.get("mission_id") != ref.mission_id
            or task_metadata.get("mission_attempt_id") != attempt_id
            or task_metadata.get("mission_claim_id") != claim_id
        ):
            raise MissionControlError("RUNNING task projection binding disagrees")

        run = one_owner_row(
            connection,
            "SELECT * FROM delegation_runs WHERE run_id = ? LIMIT 2",
            (attempt_id,),
            "Mission Control attempt",
        )
        run_metadata = owner_object(run["metadata_json"], "attempt")
        lineage_metadata = {
            "schema_version": MISSION_CONTROL_SCHEMA,
            "mission_id": ref.mission_id,
            "attempt_id": attempt_id,
            "attempt_key": expected.attempt_key,
        }
        run_values = (
            owner_text(run, "status"),
            owner_text(run, "session_id"),
            owner_text(run, "task_id"),
            owner_text(run, "claim_id"),
            owner_text(run, "assigned_to"),
            owner_text(run, "assigned_by"),
            owner_text(run, "failure_code"),
        )
        if (
            run_values
            != (
                "running",
                session_id,
                ref.task_id,
                claim_id,
                ref.agent_uid,
                expected.assigned_by,
                "",
            )
            or run["completed_at"] is not None
        ):
            raise MissionControlError("Mission Control attempt binding disagrees")
        if "quarantined_at" in run.keys() and run["quarantined_at"] not in (None, ""):
            raise MissionControlError("Mission Control attempt is quarantined")
        if any(
            run_metadata.get(key) != value for key, value in lineage_metadata.items()
        ):
            raise MissionControlError("Mission Control attempt metadata disagrees")

        parent = one_owner_row(
            connection,
            "SELECT * FROM execution_identities WHERE run_id = ? LIMIT 2",
            (attempt_id,),
            "Mission Control parent identity",
        )
        parent_metadata = owner_object(parent["metadata_json"], "parent identity")
        parent_values = {
            "trace_id": stable_id("trace", attempt_id),
            "correlation_id": f"mission:{ref.mission_id}:attempt:{attempt_id}",
            "task_id": ref.task_id,
            "run_id": attempt_id,
            "claim_id": claim_id,
            "idempotency_key": expected.attempt_key,
            "causation_id": "",
            "parent_run_id": "",
            "agent_id": ref.agent_uid,
            "session_id": session_id,
            "external_a2a_task_id": "",
            "message_id": "",
            "event_id": "",
            "artifact_id": "",
            "proposal_id": "",
            "source": "mission_control.start_attempt",
        }
        if any(
            owner_text(parent, key) != value for key, value in parent_values.items()
        ) or parent_metadata != {
            "schema_version": MISSION_CONTROL_SCHEMA,
            "mission_id": ref.mission_id,
        }:
            raise MissionControlError("Mission Control parent identity disagrees")
        _require_no_terminal_transition(connection, attempt_id)

        claim = one_owner_row(
            connection,
            "SELECT * FROM task_claims WHERE claim_id = ? LIMIT 2",
            (claim_id,),
            "Mission Control claim",
        )
        claim_metadata = owner_object(claim["metadata_json"], "claim")
        if (
            owner_text(claim, "status") != "active"
            or owner_text(claim, "session_id") != session_id
            or owner_text(claim, "task_id") != ref.task_id
            or owner_text(claim, "agent_id") != ref.agent_uid
            or claim["recovered_at"] is not None
            or any(
                claim_metadata.get(key) != value
                for key, value in lineage_metadata.items()
            )
        ):
            raise MissionControlError("Mission Control claim binding disagrees")
        claimed_at = owner_time(claim, "claimed_at")
        acked_at = owner_time(claim, "acked_at")
        heartbeat_at = owner_time(claim, "heartbeat_at")
        stale_after = owner_time(claim, "stale_after")
        if not claimed_at <= acked_at <= heartbeat_at <= observed_at < stale_after:
            raise MissionControlError("Mission Control claim timeline is invalid")
        if (stale_after - heartbeat_at).total_seconds() > MAX_LEASE_SECONDS:
            raise MissionControlError("Mission Control claim lease is excessive")

        claims = connection.execute(
            "SELECT claim_id, status, claimed_at, stale_after FROM task_claims"
            " WHERE task_id = ? ORDER BY claimed_at LIMIT ?",
            (ref.task_id, _OWNER_SCAN_LIMIT + 1),
        ).fetchall()
        if len(claims) > _OWNER_SCAN_LIMIT:
            raise MissionControlError("Mission Control claim scan saturated")
        for other in claims:
            if owner_text(other, "claim_id") == claim_id:
                continue
            other_claimed = owner_time(other, "claimed_at")
            other_stale = other["stale_after"]
            open_other = owner_text(other, "status").lower() in OPEN_CLAIM_STATUSES
            if other_claimed >= claimed_at or (
                open_other
                and (
                    other_stale is None
                    or owner_time(other, "stale_after") > observed_at
                )
            ):
                raise MissionControlError("Mission Control claim fence is not unique")

        live_runs = connection.execute(
            "SELECT run_id FROM delegation_runs WHERE task_id = ?"
            " AND status IN ('queued', 'running') LIMIT ?",
            (ref.task_id, _OWNER_SCAN_LIMIT + 1),
        ).fetchall()
        if [owner_text(item, "run_id") for item in live_runs] != [attempt_id]:
            raise MissionControlError("Mission Control live attempt is not unique")
        return _observe_candidate(
            connection,
            expected,
            attempt_id=attempt_id,
            claim_id=claim_id,
            observed_at=observed_at,
            lease_acked_at=acked_at,
            lease_stale_after=stale_after,
        )


__all__ = ["observe_exact_proposal_store"]
