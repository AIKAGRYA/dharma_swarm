"""Joined-state reconciliation for Mission Control read models."""

from __future__ import annotations

from datetime import datetime

from dharma_swarm.mission_control_contract import (
    ACTIVE_CLAIM_STATUSES,
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
    receipt_matches_identity,
    recovery_receipt_matches_contract,
    session_id,
    terminal_receipt_contract,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import DelegationRun, RuntimeReceipt, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity


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
            or (run is None and claim.status.lower() not in OPEN_CLAIM_STATUSES)
            or (run is not None and run.claim_id != claim.claim_id)
        ):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD

    terminal_by_run: dict[str, list[RuntimeReceipt]] = {}
    recovery_by_run: dict[str, list[RuntimeReceipt]] = {}
    for receipt in receipts:
        identity = identities.get(receipt.run_id)
        if identity is None or not receipt_matches_identity(receipt, identity):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD
        if receipt.receipt_type == TERMINAL_RECEIPT_TYPE:
            if receipt.run_id not in run_by_id or identity.claim_id not in claim_by_id:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            try:
                terminal_receipt_contract(receipt, identity, mission_id)
            except MissionControlError:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            terminal_by_run.setdefault(receipt.run_id, []).append(receipt)
        elif receipt.receipt_type == RECOVERY_RECEIPT_TYPE:
            if (
                receipt.run_id not in run_by_id
                or identity.claim_id not in claim_by_id
                or not recovery_receipt_matches_contract(receipt, identity, mission_id)
            ):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            recovery_by_run.setdefault(receipt.run_id, []).append(receipt)

    if any(len(group) != 1 for group in terminal_by_run.values()) or any(
        len(group) != 1 for group in recovery_by_run.values()
    ):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    if set(terminal_by_run) & set(recovery_by_run):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    terminal_by_task: dict[str, list[RuntimeReceipt]] = {}
    for run_id, group in terminal_by_run.items():
        terminal_by_task.setdefault(run_by_id[run_id].task_id, []).extend(group)

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
        elif task.status != TaskStatus.PENDING:
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    if any(
        claim.status.lower() in OPEN_CLAIM_STATUSES and claim_is_expired(claim, now)
        for claim in claims
    ):
        return ReconciliationState.EXPIRED_LEASE
    return ReconciliationState.COHERENT


__all__ = ["reconciliation"]
