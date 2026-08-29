"""Joined-state reconciliation for Mission Control read models."""

from __future__ import annotations

from datetime import datetime

from dharma_swarm.mission_control_contract import (
    ACTIVE_CLAIM_STATUSES,
    GOVERNED_PATCH_COMPLETION_CONTRACT,
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    ReconciliationState,
    TaskView,
    claim_is_expired,
    claim_is_open,
    completion_contract_from_metadata,
    receipt_matches_identity,
    recovery_receipt_matches_contract,
    require_same_completion_contract,
    session_id,
    terminal_receipt_contract,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import DelegationRun, RuntimeReceipt, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.runtime_state_effect_fence import EFFECT_RECEIPT_TYPE
from dharma_swarm.mission_control_effect_codec import canonical_json, terminal_from_json


def _identity_matches(
    identity: ExecutionIdentity,
    *,
    mission_id: str,
    run: DelegationRun | None,
    claim: TaskClaim | None,
) -> bool:
    if (
        identity.session_id != session_id(mission_id)
        or identity.metadata.get("schema_version") != SCHEMA_VERSION
        or identity.metadata.get("mission_id") != mission_id
    ):
        return False
    if run is not None and (
        identity.run_id != run.run_id
        or identity.task_id != run.task_id
        or identity.claim_id != run.claim_id
        or identity.agent_id != run.assigned_to
    ):
        return False
    if claim is not None and (
        identity.task_id != claim.task_id
        or identity.claim_id != claim.claim_id
        or identity.agent_id != claim.agent_id
        or identity.run_id != claim.metadata.get("attempt_id")
    ):
        return False
    return True


def _same_contract(*metadata: dict[str, object]) -> bool:
    try:
        require_same_completion_contract(*metadata)
    except MissionControlError:
        return False
    return True


def _effect_receipt_matches_identity(
    receipt: RuntimeReceipt, identity: ExecutionIdentity
) -> bool:
    try:
        terminal = terminal_from_json(canonical_json(receipt.payload))
    except (TypeError, ValueError):
        return False
    return bool(
        receipt.receipt_id == terminal.terminal_receipt_id
        and receipt.run_id == identity.run_id
        and receipt.task_id == identity.task_id
        and receipt.trace_id == ""
        and receipt.correlation_id
        and receipt.causation_id
        and receipt.parent_run_id
        and receipt.agent_id == terminal.claimed_by
        and receipt.idempotency_key == "idem_" + terminal.terminal_receipt_id
        and receipt.side_effect_key == terminal.effect_key
        and receipt.status == "consumed"
        and receipt.payload == terminal.to_dict()
        and receipt.created_at == terminal.consumed_at
    )


def terminal_task_projection_matches(
    task: object,
    *,
    terminal_status: str,
    result: str,
    failure_code: str,
    expected_agent_id: str,
    expected_metadata: dict[str, object],
) -> bool:
    expected_result = result if terminal_status == "succeeded" else failure_code or result
    metadata = getattr(task, "metadata", {})
    return bool(
        getattr(task, "assigned_to", "") == expected_agent_id
        and getattr(task, "result", "") == expected_result
        and metadata.get("mission_terminal_status") == terminal_status
        and all(
            metadata.get(key) == expected_metadata.get(key)
            for key in (
                "schema_version",
                "mission_id",
                "mission_attempt_id",
                "mission_claim_id",
                "completion_contract",
            )
        )
    )


def terminal_run_projection_matches(
    run: DelegationRun,
    receipt: RuntimeReceipt,
) -> bool:
    """Return whether a terminal run exactly materializes its receipt."""

    expected_owner = "completed" if receipt.status == "succeeded" else "failed"
    expected_failure = str(receipt.payload.get("failure_code") or "")
    metadata = receipt.payload.get("metadata")
    return bool(
        type(metadata) is dict
        and run.status == expected_owner
        and run.completed_at == receipt.created_at
        and run.started_at <= receipt.created_at
        and run.failure_code == expected_failure
        and all(run.metadata.get(key) == value for key, value in metadata.items())
    )


def terminal_claim_projection_matches(
    claim: TaskClaim,
    receipt: RuntimeReceipt,
) -> bool:
    """Return whether a closed claim exactly materializes its receipt."""

    expected_owner = "completed" if receipt.status == "succeeded" else "failed"
    metadata = receipt.payload.get("metadata")
    return bool(
        type(metadata) is dict
        and claim.status == expected_owner
        and claim.recovered_at is None
        and claim.acked_at is not None
        and claim.heartbeat_at is not None
        and claim.stale_after == claim.heartbeat_at
        and claim.claimed_at <= claim.acked_at <= claim.heartbeat_at
        and all(claim.metadata.get(key) == value for key, value in metadata.items())
    )


def _terminal_task_matches_receipt(
    task: TaskView,
    receipt: RuntimeReceipt,
    run: DelegationRun,
    identity: ExecutionIdentity,
    mission_id: str,
) -> bool:
    return terminal_task_projection_matches(
        task,
        terminal_status=receipt.status,
        result=str(receipt.payload.get("result") or ""),
        failure_code=str(receipt.payload.get("failure_code") or ""),
        expected_agent_id=identity.agent_id,
        expected_metadata={
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "mission_attempt_id": run.run_id,
            "mission_claim_id": run.claim_id,
            "completion_contract": identity.metadata.get("completion_contract"),
        },
    )


def reconciliation(
    mission_id: str,
    tasks: tuple[TaskView, ...],
    runs: list[DelegationRun],
    claims: list[TaskClaim],
    receipts: list[RuntimeReceipt],
    identities: dict[str, ExecutionIdentity | None],
    now: datetime,
) -> ReconciliationState:
    """Validate the complete joined graph before reporting projection drift."""
    expected_session = session_id(mission_id)
    task_by_id = {task.task_id: task for task in tasks}
    run_by_id = {run.run_id: run for run in runs}
    claim_by_id = {claim.claim_id: claim for claim in claims}
    allowed_run_statuses = {"queued", "running", *OWNER_TERMINAL_ATTEMPT_STATUSES}
    allowed_claim_statuses = {
        *OPEN_CLAIM_STATUSES,
        "completed",
        "failed",
        "stale_recovered",
    }

    for run in runs:
        identity = identities.get(run.run_id)
        claim = claim_by_id.get(run.claim_id)
        if (
            run.session_id != expected_session
            or run.task_id not in task_by_id
            or not run.assigned_to
            or run.metadata.get("schema_version") != SCHEMA_VERSION
            or run.metadata.get("mission_id") != mission_id
            or run.status not in allowed_run_statuses
            or identity is None
            or not _identity_matches(
                identity, mission_id=mission_id, run=run, claim=claim
            )
            or not _same_contract(
                task_by_id[run.task_id].metadata,
                run.metadata,
                identity.metadata,
                claim.metadata if claim is not None else run.metadata,
            )
            or (claim is None and run.status not in OWNER_TERMINAL_ATTEMPT_STATUSES)
        ):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD

    for claim in claims:
        attempt_id = str(claim.metadata.get("attempt_id") or "")
        run = run_by_id.get(attempt_id)
        identity = identities.get(attempt_id)
        if (
            claim.session_id != expected_session
            or claim.task_id not in task_by_id
            or not claim.agent_id
            or claim.metadata.get("schema_version") != SCHEMA_VERSION
            or claim.metadata.get("mission_id") != mission_id
            or claim.status.lower() not in allowed_claim_statuses
            or not attempt_id
            or identity is None
            or not _identity_matches(
                identity, mission_id=mission_id, run=run, claim=claim
            )
            or not _same_contract(
                task_by_id[claim.task_id].metadata,
                claim.metadata,
                identity.metadata,
                run.metadata if run is not None else claim.metadata,
            )
            or (run is None and claim.status.lower() not in OPEN_CLAIM_STATUSES)
            or (run is not None and run.claim_id != claim.claim_id)
        ):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD

    terminal_by_run: dict[str, list[RuntimeReceipt]] = {}
    recovery_by_run: dict[str, list[RuntimeReceipt]] = {}
    effect_support_by_run: dict[str, list[RuntimeReceipt]] = {}
    for receipt in receipts:
        if receipt.receipt_type == EFFECT_RECEIPT_TYPE:
            run = run_by_id.get(receipt.run_id)
            identity = identities.get(receipt.run_id)
            claim = claim_by_id.get(identity.claim_id) if identity is not None else None
            task = task_by_id.get(receipt.task_id)
            if (
                run is None
                or identity is None
                or claim is None
                or task is None
                or run.task_id != receipt.task_id
                or not _effect_receipt_matches_identity(receipt, identity)
                or completion_contract_from_metadata(identity.metadata)
                != GOVERNED_PATCH_COMPLETION_CONTRACT
                or not _same_contract(
                    task.metadata,
                    run.metadata,
                    claim.metadata,
                    identity.metadata,
                )
            ):
                return ReconciliationState.FOREIGN_RUNTIME_RECORD
            effect_support_by_run.setdefault(receipt.run_id, []).append(receipt)
            continue
        identity = identities.get(receipt.run_id)
        if identity is None or not receipt_matches_identity(receipt, identity):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD
        if receipt.receipt_type == TERMINAL_RECEIPT_TYPE:
            if receipt.run_id not in run_by_id or identity.claim_id not in claim_by_id:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            terminal_by_run.setdefault(receipt.run_id, []).append(receipt)
        elif receipt.receipt_type == RECOVERY_RECEIPT_TYPE:
            claim = claim_by_id.get(identity.claim_id)
            if (
                receipt.run_id not in run_by_id
                or claim is None
                or not recovery_receipt_matches_contract(
                    receipt,
                    identity,
                    mission_id,
                    expired_stale_after=claim.stale_after,
                )
            ):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            recovery_by_run.setdefault(receipt.run_id, []).append(receipt)

    if any(len(group) != 1 for group in terminal_by_run.values()) or any(
        len(group) != 1 for group in recovery_by_run.values()
    ):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    if set(terminal_by_run) & set(recovery_by_run):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    if any(len(group) != 1 for group in effect_support_by_run.values()):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    for run_id, group in terminal_by_run.items():
        receipt = group[0]
        identity = identities[run_id]
        run = run_by_id[run_id]
        if identity is None:
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        claim = claim_by_id.get(identity.claim_id)
        try:
            terminal_receipt_contract(
                receipt, identity, mission_id,
                supporting_receipts=effect_support_by_run.get(run_id, ()),
            )
        except MissionControlError:
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        if claim is None:
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        governed = (
            completion_contract_from_metadata(identity.metadata)
            == GOVERNED_PATCH_COMPLETION_CONTRACT
        )
        if run.status in OWNER_TERMINAL_ATTEMPT_STATUSES:
            if not terminal_run_projection_matches(run, receipt):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        elif governed or run.status != "running":
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        if claim.status.lower() not in OPEN_CLAIM_STATUSES and not (
            terminal_claim_projection_matches(claim, receipt)
        ):
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    terminal_by_task: dict[str, list[RuntimeReceipt]] = {}
    for run_id, group in terminal_by_run.items():
        terminal_by_task.setdefault(run_by_id[run_id].task_id, []).extend(group)
    for task in tasks:
        if task.status not in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
            continue
        matching = [
            receipt
            for receipt in terminal_by_task.get(task.task_id, [])
            if (task.status == TaskStatus.COMPLETED and receipt.status == "succeeded")
            or (task.status == TaskStatus.FAILED and receipt.status == "failed")
        ]
        if len(matching) != 1:
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        receipt = matching[0]
        identity = identities[receipt.run_id]
        if identity is None or not _terminal_task_matches_receipt(
            task, receipt, run_by_id[receipt.run_id], identity, mission_id
        ):
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    active_by_task: dict[str, int] = {}
    for claim in claims:
        if claim_is_open(claim, now):
            active_by_task[claim.task_id] = active_by_task.get(claim.task_id, 0) + 1
    if any(count > 1 for count in active_by_task.values()):
        return ReconciliationState.CONFLICTING_ACTIVE_CLAIMS

    for claim in claims:
        run = run_by_id.get(str(claim.metadata.get("attempt_id") or ""))
        task = task_by_id.get(claim.task_id)
        status_is_open = claim.status.lower() in OPEN_CLAIM_STATUSES
        if status_is_open and (
            (run is not None and run.status in OWNER_TERMINAL_ATTEMPT_STATUSES)
            or (
                task is not None
                and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}
            )
        ):
            if run is not None and (
                terminal_by_run.get(run.run_id) or recovery_by_run.get(run.run_id)
            ):
                # Durable evidence and the run precede the claim projection.
                # This is repairable drift, not contradictory truth.
                return ReconciliationState.NEEDS_TASK_PROJECTION
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    run_claim_ids = {run.claim_id for run in runs if run.claim_id}
    if any(
        claim_is_open(claim, now) and claim.claim_id not in run_claim_ids
        for claim in claims
    ):
        return ReconciliationState.ACTIVE_CLAIM_WITHOUT_RUN

    for run in runs:
        terminals = terminal_by_run.get(run.run_id, [])
        recoveries = recovery_by_run.get(run.run_id, [])
        task = task_by_id[run.task_id]
        claim = claim_by_id.get(run.claim_id)
        if run.status in {"completed", "failed"} and not terminals:
            return ReconciliationState.MISSING_TERMINAL_RECEIPT
        if run.status == "stale_recovered" and not recoveries:
            return ReconciliationState.MISSING_TERMINAL_RECEIPT
        if terminals:
            receipt = terminals[0]
            expected_owner = "completed" if receipt.status == "succeeded" else "failed"
            if receipt.status not in {"succeeded", "failed"}:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if (
                run.status in OWNER_TERMINAL_ATTEMPT_STATUSES
                and run.status != expected_owner
            ):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            expected_task = (
                TaskStatus.COMPLETED
                if receipt.status == "succeeded"
                else TaskStatus.FAILED
            )
            if claim is None:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if claim.status.lower() in OPEN_CLAIM_STATUSES:
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if claim.status != expected_owner:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if (
                run.status not in OWNER_TERMINAL_ATTEMPT_STATUSES
                or task.status != expected_task
            ):
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif recoveries:
            if recoveries[0].status != "stale_recovered":
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if claim is None:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if claim.status.lower() in OPEN_CLAIM_STATUSES:
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if claim.status != "stale_recovered":
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if run.status != "stale_recovered":
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            } and not terminal_by_task.get(task.task_id):
                # Recovery evidence cannot authorize a terminal task outcome.
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if (
                task.status in {TaskStatus.ASSIGNED, TaskStatus.RUNNING}
                and task.metadata.get("mission_attempt_id") == run.run_id
            ):
                # Recovery closes the old lineage before a replacement attempt
                # can repair TaskBoard. The crash window is drift, not coherence.
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif run.status == "running" and task.status != TaskStatus.RUNNING:
            return ReconciliationState.NEEDS_TASK_PROJECTION
        elif run.status == "queued" and (
            task.status != TaskStatus.ASSIGNED or task.assigned_to != run.assigned_to
        ):
            return ReconciliationState.NEEDS_TASK_PROJECTION

        if run.status == "queued" and claim is not None:
            if claim.status.lower() in OPEN_CLAIM_STATUSES:
                if claim.status.lower() != "claimed":
                    return ReconciliationState.NEEDS_TASK_PROJECTION
            else:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        if run.status == "running" and claim is not None:
            if claim.status.lower() in OPEN_CLAIM_STATUSES:
                if (
                    claim.status.lower() not in ACTIVE_CLAIM_STATUSES
                    or claim.acked_at is None
                ):
                    return ReconciliationState.NEEDS_TASK_PROJECTION
            else:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    runs_by_task: dict[str, list[DelegationRun]] = {}
    for run in runs:
        runs_by_task.setdefault(run.task_id, []).append(run)
    for task in tasks:
        task_runs = runs_by_task.get(task.task_id, [])
        if task.status == TaskStatus.ASSIGNED:
            matching = [
                run
                for run in task_runs
                if run.status == "queued"
                and run.assigned_to == task.assigned_to
                and task.metadata.get("mission_attempt_id") == run.run_id
                and task.metadata.get("mission_claim_id") == run.claim_id
            ]
            if len(matching) != 1:
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif task.status == TaskStatus.RUNNING:
            matching = [
                run
                for run in task_runs
                if run.status == "running"
                and run.assigned_to == task.assigned_to
                and task.metadata.get("mission_attempt_id") == run.run_id
                and task.metadata.get("mission_claim_id") == run.claim_id
            ]
            if len(matching) != 1:
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
            matching = [
                receipt
                for receipt in terminal_by_task.get(task.task_id, [])
                if (
                    task.status == TaskStatus.COMPLETED
                    and receipt.status == "succeeded"
                )
                or (task.status == TaskStatus.FAILED and receipt.status == "failed")
            ]
            if len(matching) != 1:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            receipt = matching[0]
            run = run_by_id[receipt.run_id]
            identity = identities[receipt.run_id]
            if identity is None or not _terminal_task_matches_receipt(
                task, receipt, run, identity, mission_id
            ):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        elif task.status != TaskStatus.PENDING:
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    if any(
        claim.status.lower() in OPEN_CLAIM_STATUSES and claim_is_expired(claim, now)
        for claim in claims
    ):
        return ReconciliationState.EXPIRED_LEASE
    return ReconciliationState.COHERENT


__all__ = ["reconciliation"]
