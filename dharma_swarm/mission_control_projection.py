"""Task projections and read-model reconciliation for Mission Control."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from dharma_swarm.mission_control_contract import (
    ACTIVE_CLAIM_STATUSES,
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_CAS_STALE_AFTER_SECONDS,
    TERMINAL_RECEIPT_TYPE,
    AttemptView,
    MissionControlError,
    ReconciliationState,
    TaskView,
    attempt_view,
    claim_is_active,
    claim_is_expired,
    claim_is_open,
    lease_view,
    mission_view,
    receipt_view,
    receipt_matches_identity,
    recovery_receipt_matches_contract,
    session_id,
    stable_id,
    terminal_operation_metadata,
    terminal_receipt_contract,
    task_view,
    utc_now,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    SessionState,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard, TaskBoardError


async def project_assigned_task(
    board: TaskBoard,
    task: Task,
    *,
    mission_id: str,
    agent_id: str,
    attempt_id: str,
    claim_id: str,
) -> None:
    """Project a queued attempt without claiming executor acknowledgement."""
    current = await board.get(task.id)
    if current is None:
        raise MissionControlError(f"task {task.id!r} was not found")
    projection_metadata = {
        **current.metadata,
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "mission_attempt_id": attempt_id,
        "mission_claim_id": claim_id,
    }
    try:
        if current.status == TaskStatus.RUNNING:
            current = await board.requeue(
                current.id,
                reason="mission control queued a replacement lease",
                metadata=projection_metadata,
            )
        if current.status == TaskStatus.ASSIGNED:
            if current.assigned_to == agent_id:
                await board.update_task(current.id, metadata=projection_metadata)
                return
            current = await board.requeue(
                current.id,
                reason="mission control lease reassigned",
                metadata=projection_metadata,
            )
        if current.status == TaskStatus.PENDING:
            await board.assign(current.id, agent_id, metadata=projection_metadata)
            return
    except TaskBoardError as exc:
        raise MissionControlError(str(exc)) from exc
    raise MissionControlError(
        f"attempt {attempt_id!r} cannot project task {task.id!r} "
        f"from {current.status.value!r}"
    )


async def project_running_task(
    board: TaskBoard,
    task: Task,
    *,
    mission_id: str,
    agent_id: str,
    attempt_id: str,
    claim_id: str,
) -> None:
    """Repair the nonterminal TaskBoard projection for an existing run."""
    current = await board.get(task.id)
    if current is None:
        raise MissionControlError(f"task {task.id!r} was not found")
    projection_metadata = {
        **current.metadata,
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "mission_attempt_id": attempt_id,
        "mission_claim_id": claim_id,
    }
    try:
        if current.status == TaskStatus.RUNNING:
            if current.assigned_to != agent_id:
                current = await board.requeue(
                    current.id,
                    reason="mission control lease reassigned",
                    metadata=projection_metadata,
                )
            else:
                await board.update_task(current.id, metadata=projection_metadata)
                return
        if current.status == TaskStatus.ASSIGNED and current.assigned_to != agent_id:
            current = await board.requeue(
                current.id,
                reason="mission control lease reassigned",
                metadata=projection_metadata,
            )
        if current.status == TaskStatus.PENDING:
            current = await board.assign(
                current.id, agent_id, metadata=projection_metadata
            )
        if current.status == TaskStatus.ASSIGNED:
            await board.start(current.id, metadata=projection_metadata)
            return
    except TaskBoardError as exc:
        raise MissionControlError(str(exc)) from exc
    raise MissionControlError(
        f"attempt {attempt_id!r} cannot project task {task.id!r} "
        f"from {current.status.value!r}"
    )


async def project_terminal_task(
    board: TaskBoard,
    task: Task,
    terminal_status: str,
    result: str,
    failure_code: str,
) -> None:
    current = await board.get(task.id)
    if current is None:
        raise MissionControlError(f"task {task.id!r} was not found")
    expected = (
        TaskStatus.COMPLETED
        if terminal_status == "succeeded"
        else TaskStatus.FAILED
    )
    if current.status == expected:
        return
    if current.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
        raise MissionControlError(
            f"task {task.id!r} is already terminal as {current.status.value!r}"
        )
    if current.status != TaskStatus.RUNNING:
        raise MissionControlError(
            f"terminal evidence recorded but task {task.id!r} needs task projection"
        )
    projection_metadata = {
        **current.metadata,
        "mission_terminal_status": terminal_status,
    }
    try:
        if terminal_status == "succeeded":
            await board.complete(
                current.id, result=result, metadata=projection_metadata
            )
        else:
            await board.fail(
                current.id,
                error=str(failure_code or result),
                metadata=projection_metadata,
            )
    except TaskBoardError as exc:
        raise MissionControlError(str(exc)) from exc


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
            or (
                run is None
                and claim.status.lower() not in OPEN_CLAIM_STATUSES
            )
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
            if (
                receipt.run_id not in run_by_id
                or identity.claim_id not in claim_by_id
            ):
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
            or (task is not None and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED})
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
            if run.status in OWNER_TERMINAL_ATTEMPT_STATUSES and run.status != expected_owner:
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
            if run.status not in OWNER_TERMINAL_ATTEMPT_STATUSES or task.status != expected_task:
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
            if (
                task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}
                and not terminal_by_task.get(task.task_id)
            ):
                # Recovery evidence cannot authorize a terminal task outcome.
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if (
                task.status in {TaskStatus.ASSIGNED, TaskStatus.RUNNING}
                and task.metadata.get("mission_attempt_id") == run.run_id
            ):
                # Recovery closes the old lineage before a replacement attempt
                # can repair TaskBoard.  The crash window is drift, not coherence.
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif run.status == "running" and task.status != TaskStatus.RUNNING:
            return ReconciliationState.NEEDS_TASK_PROJECTION
        elif run.status == "queued" and (
            task.status != TaskStatus.ASSIGNED
            or task.assigned_to != run.assigned_to
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
                or (
                    task.status == TaskStatus.FAILED
                    and receipt.status == "failed"
                )
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


class MissionControlProjectionMixin:
    """Shared projection, identity, recovery, and fencing mechanics."""

    _board: TaskBoard
    _runtime: Any

    @staticmethod
    def _attempt_metadata(
        metadata: dict[str, Any] | None,
        *,
        mission_id: str,
        attempt_id: str,
        attempt_key: str,
        base: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            **dict(base or {}),
            **dict(metadata or {}),
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": attempt_id,
            "attempt_key": attempt_key,
        }

    @staticmethod
    def _require_current_claim(
        claim: TaskClaim,
        claims: list[TaskClaim],
        *,
        now: datetime,
        require_active: bool = True,
    ) -> None:
        later = [
            candidate
            for candidate in claims
            if candidate.claim_id != claim.claim_id
            and candidate.claimed_at > claim.claimed_at
        ]
        if later:
            raise MissionControlError(
                f"claim {claim.claim_id!r} was superseded by a newer claim"
            )
        conflicting = [
            candidate
            for candidate in claims
            if candidate.claim_id != claim.claim_id
            and claim_is_open(candidate, now)
        ]
        if conflicting:
            raise MissionControlError(
                f"claim {claim.claim_id!r} is fenced by another active claim"
            )
        if require_active:
            if claim_is_expired(claim, now):
                raise MissionControlError(f"claim {claim.claim_id!r} is expired")
            if not claim_is_active(claim, now):
                raise MissionControlError(
                    f"claim {claim.claim_id!r} is not active and acknowledged"
                )

    async def _project_terminal_lineage(
        self,
        mission_id: str,
        *,
        task: Task,
        run: DelegationRun,
        claim: TaskClaim,
        identity: ExecutionIdentity,
        receipt: RuntimeReceipt,
    ) -> None:
        """Repair terminal owner projections without ever reopening the claim."""
        terminal_status, owner_status, result, failure_code, metadata = (
            terminal_receipt_contract(receipt, identity, mission_id)
        )
        self._require_attempt_identity(
            run, mission_id, identity.task_id, identity.agent_id
        )
        self._require_claim_identity(
            claim,
            mission_id,
            identity.task_id,
            identity.agent_id,
            identity.run_id,
        )
        if run.claim_id != claim.claim_id or identity.claim_id != claim.claim_id:
            raise MissionControlError(
                f"attempt {identity.run_id!r} has conflicting terminal evidence"
            )
        if (
            run.status in OWNER_TERMINAL_ATTEMPT_STATUSES
            and run.status != owner_status
        ):
            raise MissionControlError(
                f"attempt {identity.run_id!r} has conflicting terminal evidence"
            )
        now = utc_now()
        if run.status != owner_status or run.completed_at is None:
            run = await self._runtime.record_delegation_run(
                replace(
                    run,
                    status=owner_status,
                    completed_at=run.completed_at or now,
                    failure_code=failure_code,
                    metadata=self._attempt_metadata(
                        metadata,
                        base=run.metadata,
                        mission_id=mission_id,
                        attempt_id=identity.run_id,
                        attempt_key=identity.idempotency_key,
                    ),
                )
            )
        current_task = await self._board.get(task.id)
        if current_task is None:
            raise MissionControlError(f"task {task.id!r} was not found")
        if current_task.status in {
            TaskStatus.PENDING,
            TaskStatus.ASSIGNED,
            TaskStatus.RUNNING,
        }:
            # A heartbeat can durably advance the run before TaskBoard reaches
            # RUNNING.  Repair that earlier projection from the same fenced
            # identity so terminal retry converges from PENDING or ASSIGNED.
            await self._project_running_task(
                current_task,
                mission_id=mission_id,
                agent_id=identity.agent_id,
                attempt_id=identity.run_id,
                claim_id=identity.claim_id,
            )
        # TaskBoard remains open if either projection crashes. Closing the claim
        # happens last, so a replacement cannot be admitted from partial state.
        await self._project_terminal_task(
            task, terminal_status, result, failure_code
        )
        claim_terminal = "completed" if terminal_status == "succeeded" else "failed"
        if claim.status != claim_terminal:
            await self._runtime.record_task_claim(
                replace(
                    claim,
                    status=claim_terminal,
                    heartbeat_at=now,
                    stale_after=now,
                    metadata=self._attempt_metadata(
                        metadata,
                        base=claim.metadata,
                        mission_id=mission_id,
                        attempt_id=identity.run_id,
                        attempt_key=identity.idempotency_key,
                    ),
                )
            )

    async def _recover_expired_claim(
        self,
        mission_id: str,
        claim: TaskClaim,
        *,
        recovered_at: datetime,
    ) -> bool:
        """Close an expired lineage; no cross-process lease CAS is claimed."""
        attempt_id = str(claim.metadata.get("attempt_id") or "")
        self._require_claim_identity(
            claim, mission_id, claim.task_id, claim.agent_id, attempt_id
        )
        identity = await self._runtime.get_execution_identity(attempt_id)
        if identity is None:
            raise MissionControlError(
                f"execution identity for attempt {attempt_id!r} was not found"
            )
        self._require_identity(
            identity, mission_id, claim.task_id, claim.agent_id, attempt_id
        )
        if identity.claim_id != claim.claim_id:
            raise MissionControlError(
                f"execution identity for {attempt_id!r} has foreign fields"
            )
        run = await self._runtime.get_delegation_run(attempt_id)
        if run is None:
            raise MissionControlError(
                f"expired claim {claim.claim_id!r} has no associated attempt run"
            )
        self._require_attempt_identity(run, mission_id, claim.task_id, claim.agent_id)
        if run.claim_id != claim.claim_id:
            raise MissionControlError(f"attempt {attempt_id!r} has foreign identity")

        terminal_receipts = await self._runtime.list_runtime_receipts(
            run_id=attempt_id,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            limit=2,
        )
        recovery_receipts = await self._runtime.list_runtime_receipts(
            run_id=attempt_id,
            receipt_type=RECOVERY_RECEIPT_TYPE,
            limit=2,
        )
        if terminal_receipts:
            if len(terminal_receipts) != 1 or recovery_receipts:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting terminal evidence"
                )
            terminal = terminal_receipts[0]
            terminal_receipt_contract(terminal, identity, mission_id)
            operation_hash, idempotency_metadata = terminal_operation_metadata(
                terminal, identity, mission_id
            )
            try:
                ownership_token = (
                    await self._runtime.try_begin_idempotent_side_effect_with_token(
                        identity,
                        terminal.side_effect_key,
                        metadata=idempotency_metadata,
                        stale_after_seconds=TERMINAL_CAS_STALE_AFTER_SECONDS,
                    )
                )
                ownership_token, ownership_complete = (
                    await self._recover_terminal_ownership(
                        identity,
                        side_effect_key=terminal.side_effect_key,
                        operation_hash=operation_hash,
                        receipt=terminal,
                        receipt_id=terminal.receipt_id,
                        ownership_token=ownership_token,
                    )
                )
                if not ownership_complete:
                    await self._runtime.complete_idempotent_side_effect(
                        identity,
                        terminal.side_effect_key,
                        status="completed",
                        result_receipt_id=terminal.receipt_id,
                        metadata=idempotency_metadata,
                        expected_updated_at=ownership_token,
                    )
            except (KeyError, RuntimeError, ValueError) as exc:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting terminal evidence"
                ) from exc
            task = await self._require_task(mission_id, claim.task_id)
            await self._project_terminal_lineage(
                mission_id,
                task=task,
                run=run,
                claim=claim,
                identity=identity,
                receipt=terminal,
            )
            return True
        if run.status in {"completed", "failed"}:
            raise MissionControlError(
                f"attempt {attempt_id!r} has conflicting terminal evidence"
            )

        receipt_id = stable_id("receipt", attempt_id, "stale_recovered")
        side_effect_key = f"mission_control:{attempt_id}:stale_recovery"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": attempt_id,
            "recovered_claim_id": claim.claim_id,
            "reason": "expired_lease",
        }
        recovery = self._matching_receipt(
            recovery_receipts,
            identity=identity,
            receipt_type=RECOVERY_RECEIPT_TYPE,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status="stale_recovered",
            payload=payload,
        )
        if recovery is None:
            await self._runtime.record_receipt_for_identity(
                identity,
                receipt_type=RECOVERY_RECEIPT_TYPE,
                status="stale_recovered",
                side_effect_key=side_effect_key,
                payload=payload,
                receipt_id=receipt_id,
            )
        transitioned_at = max(recovered_at, utc_now())
        if run is not None and run.status != "stale_recovered":
            await self._runtime.record_delegation_run(
                replace(
                    run,
                    status="stale_recovered",
                    completed_at=transitioned_at,
                    failure_code="stale_lease_recovered",
                    metadata={
                        **run.metadata,
                        "recovered_claim_id": claim.claim_id,
                        "recovery_receipt_id": receipt_id,
                    },
                )
            )
        if claim.status != "stale_recovered":
            await self._runtime.record_task_claim(
                replace(
                    claim,
                    status="stale_recovered",
                    stale_after=transitioned_at,
                    recovered_at=transitioned_at,
                    metadata={
                        **claim.metadata,
                        "recovery_receipt_id": receipt_id,
                    },
                )
            )
        return False

    async def _recover_terminal_ownership(
        self,
        identity: ExecutionIdentity,
        *,
        side_effect_key: str,
        operation_hash: str,
        receipt: RuntimeReceipt | None,
        receipt_id: str,
        ownership_token: datetime | None,
    ) -> tuple[datetime | None, bool]:
        if ownership_token is not None:
            return ownership_token, False
        record = await self._runtime.get_idempotency_record(
            identity.idempotency_key, side_effect_key
        )
        if record is None or (
            record.run_id != identity.run_id
            or record.task_id != identity.task_id
            or record.trace_id != identity.trace_id
            or record.correlation_id != identity.correlation_id
            or record.metadata.get("operation_hash") != operation_hash
        ):
            raise MissionControlError(
                f"attempt {identity.run_id!r} already has conflicting terminal evidence"
            )
        if record.status == "stale":
            reclaimed = (
                await self._runtime.try_reclaim_idempotent_side_effect_with_token(
                    identity,
                    side_effect_key,
                    expected_status="stale",
                    expected_updated_at=record.updated_at,
                )
            )
            if reclaimed is None:
                raise MissionControlError(
                    f"terminal ownership for attempt {identity.run_id!r} was lost"
                )
            return reclaimed, False
        if record.status == "completed":
            if receipt is None or record.result_receipt_id != receipt_id:
                raise MissionControlError(
                    f"attempt {identity.run_id!r} has conflicting terminal evidence"
                )
            return None, True
        if record.status == "started":
            raise MissionControlError(
                f"terminal finish for attempt {identity.run_id!r} is already in progress"
            )
        raise MissionControlError(
            f"attempt {identity.run_id!r} already has conflicting terminal evidence"
        )

    @staticmethod
    def _matching_terminal_receipt(
        receipts: list[RuntimeReceipt],
        *,
        identity: ExecutionIdentity,
        side_effect_key: str,
        receipt_id: str,
        status: str,
        payload: dict[str, Any],
    ) -> RuntimeReceipt | None:
        return MissionControlProjectionMixin._matching_receipt(
            receipts,
            identity=identity,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status=status,
            payload=payload,
        )

    @staticmethod
    def _matching_receipt(
        receipts: list[RuntimeReceipt],
        *,
        identity: ExecutionIdentity,
        receipt_type: str,
        side_effect_key: str,
        receipt_id: str,
        status: str,
        payload: dict[str, Any],
    ) -> RuntimeReceipt | None:
        if not receipts:
            return None
        if len(receipts) != 1:
            raise MissionControlError(
                f"attempt {identity.run_id!r} already has conflicting terminal evidence"
            )
        receipt = receipts[0]
        if (
            receipt.receipt_id != receipt_id
            or receipt.receipt_type != receipt_type
            or receipt.status != status
            or receipt.run_id != identity.run_id
            or receipt.task_id != identity.task_id
            or receipt.trace_id != identity.trace_id
            or receipt.correlation_id != identity.correlation_id
            or receipt.causation_id != identity.causation_id
            or receipt.parent_run_id != identity.parent_run_id
            or receipt.agent_id != identity.agent_id
            or receipt.idempotency_key != identity.idempotency_key
            or receipt.side_effect_key != side_effect_key
            or receipt.payload != payload
        ):
            raise MissionControlError(
                f"attempt {identity.run_id!r} already has conflicting terminal evidence"
            )
        return receipt

    async def _project_assigned_task(self, task: Task, **kwargs: Any) -> None:
        await project_assigned_task(self._board, task, **kwargs)

    async def _project_running_task(self, task: Task, **kwargs: Any) -> None:
        await project_running_task(self._board, task, **kwargs)

    async def _project_terminal_task(
        self,
        task: Task,
        terminal_status: str,
        result: str,
        failure_code: str,
    ) -> None:
        await project_terminal_task(
            self._board, task, terminal_status, result, failure_code
        )

    async def _attempt_view(self, run: DelegationRun) -> AttemptView:
        identity = await self._runtime.get_execution_identity(run.run_id)
        return attempt_view(run, identity)

    @staticmethod
    def _require_mission_session(session: SessionState, mission_id: str) -> None:
        if (
            session.session_id != session_id(mission_id)
            or session.metadata.get("mission_id") != mission_id
            or session.metadata.get("schema_version") != SCHEMA_VERSION
        ):
            raise MissionControlError(f"mission {mission_id!r} has a foreign session")

    @staticmethod
    def _require_attempt_identity(
        run: DelegationRun, mission_id: str, task_id: str, agent_id: str
    ) -> None:
        if (
            run.session_id != session_id(mission_id)
            or run.task_id != task_id
            or run.assigned_to != agent_id
            or run.metadata.get("mission_id") != mission_id
            or run.metadata.get("schema_version") != SCHEMA_VERSION
        ):
            raise MissionControlError(f"attempt {run.run_id!r} has foreign identity")

    @staticmethod
    def _require_claim_identity(
        claim: TaskClaim,
        mission_id: str,
        task_id: str,
        agent_id: str,
        attempt_id: str,
    ) -> None:
        if (
            claim.session_id != session_id(mission_id)
            or claim.task_id != task_id
            or claim.agent_id != agent_id
            or claim.metadata.get("mission_id") != mission_id
            or claim.metadata.get("schema_version") != SCHEMA_VERSION
            or claim.metadata.get("attempt_id") != attempt_id
        ):
            raise MissionControlError(f"claim {claim.claim_id!r} has foreign identity")

    @staticmethod
    def _require_identity(
        identity: ExecutionIdentity,
        mission_id: str,
        task_id: str,
        agent_id: str,
        attempt_id: str,
    ) -> None:
        if (
            identity.session_id != session_id(mission_id)
            or identity.task_id != task_id
            or identity.agent_id != agent_id
            or identity.run_id != attempt_id
            or identity.metadata.get("mission_id") != mission_id
            or identity.metadata.get("schema_version") != SCHEMA_VERSION
        ):
            raise MissionControlError(
                f"execution identity for {attempt_id!r} has foreign fields"
            )


__all__ = [
    "MissionControlProjectionMixin",
    "attempt_view",
    "lease_view",
    "mission_view",
    "project_assigned_task",
    "project_running_task",
    "project_terminal_task",
    "receipt_view",
    "reconciliation",
    "task_view",
]
