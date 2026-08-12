"""Task projections and read-model reconciliation for Mission Control."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from dharma_swarm.mission_control_contract import (
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    AgentLeaseView,
    AttemptView,
    MissionControlError,
    MissionView,
    ReceiptView,
    ReconciliationState,
    TaskView,
    claim_is_active,
    claim_is_expired,
    claim_is_open,
    public_attempt_status,
    session_id,
    stable_id,
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


def mission_view(session: SessionState) -> MissionView:
    mission_id = str(session.metadata.get("mission_id") or "")
    return MissionView(
        mission_id=mission_id,
        session_id=session.session_id,
        title=str(session.metadata.get("title") or ""),
        goal=str(session.metadata.get("goal") or ""),
        operator_id=session.operator_id,
        status=session.status,
        metadata=dict(session.metadata),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def task_view(task: Task, mission_id: str) -> TaskView:
    return TaskView(
        task_id=task.id,
        mission_id=mission_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assigned_to=str(task.assigned_to or ""),
        result=str(task.result or ""),
        metadata=dict(task.metadata),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def attempt_view(
    run: DelegationRun, identity: ExecutionIdentity | None
) -> AttemptView:
    return AttemptView(
        attempt_id=run.run_id,
        mission_id=str(run.metadata.get("mission_id") or ""),
        session_id=run.session_id,
        task_id=run.task_id,
        claim_id=run.claim_id,
        assigned_to=run.assigned_to,
        assigned_by=run.assigned_by,
        status=public_attempt_status(run.status),
        failure_code=run.failure_code,
        idempotency_key=identity.idempotency_key if identity is not None else "",
        metadata=dict(run.metadata),
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def lease_view(claim: TaskClaim, *, now: datetime) -> AgentLeaseView:
    return AgentLeaseView(
        claim_id=claim.claim_id,
        mission_id=str(claim.metadata.get("mission_id") or ""),
        session_id=claim.session_id,
        task_id=claim.task_id,
        agent_id=claim.agent_id,
        attempt_id=str(claim.metadata.get("attempt_id") or ""),
        status=claim.status,
        active=claim_is_active(claim, now),
        expired=claim_is_expired(claim, now),
        heartbeat_at=claim.heartbeat_at,
        stale_after=claim.stale_after,
        metadata=dict(claim.metadata),
    )


def receipt_view(receipt: RuntimeReceipt, mission_id: str) -> ReceiptView:
    return ReceiptView(
        receipt_id=receipt.receipt_id,
        mission_id=str(receipt.payload.get("mission_id") or mission_id),
        task_id=receipt.task_id,
        attempt_id=receipt.run_id,
        agent_id=receipt.agent_id,
        receipt_type=receipt.receipt_type,
        status=receipt.status,
        idempotency_key=receipt.idempotency_key,
        payload=dict(receipt.payload),
        created_at=receipt.created_at,
    )


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


def _receipt_matches_identity(
    receipt: RuntimeReceipt, identity: ExecutionIdentity
) -> bool:
    return (
        receipt.run_id == identity.run_id
        and receipt.task_id == identity.task_id
        and receipt.trace_id == identity.trace_id
        and receipt.correlation_id == identity.correlation_id
        and receipt.causation_id == identity.causation_id
        and receipt.parent_run_id == identity.parent_run_id
        and receipt.agent_id == identity.agent_id
        and receipt.idempotency_key == identity.idempotency_key
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

    for run in runs:
        identity = identities.get(run.run_id)
        claim = claim_by_id.get(run.claim_id)
        if (
            run.session_id != expected_session
            or run.task_id not in task_by_id
            or not run.assigned_to
            or run.metadata.get("schema_version") != SCHEMA_VERSION
            or run.metadata.get("mission_id") != mission_id
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
            or not attempt_id
            or identity is None
            or not _identity_matches(
                identity, mission_id=mission_id, run=run, claim=claim
            )
            or (run is not None and run.claim_id != claim.claim_id)
        ):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD

    terminal_by_run: dict[str, list[RuntimeReceipt]] = {}
    recovery_by_run: dict[str, list[RuntimeReceipt]] = {}
    for receipt in receipts:
        identity = identities.get(receipt.run_id)
        if identity is None or not _receipt_matches_identity(receipt, identity):
            return ReconciliationState.FOREIGN_RUNTIME_RECORD
        if receipt.receipt_type in {TERMINAL_RECEIPT_TYPE, RECOVERY_RECEIPT_TYPE}:
            if (
                receipt.payload.get("schema_version") != SCHEMA_VERSION
                or receipt.payload.get("mission_id") != mission_id
                or receipt.payload.get("attempt_id") != receipt.run_id
            ):
                return ReconciliationState.FOREIGN_RUNTIME_RECORD
        if receipt.receipt_type == TERMINAL_RECEIPT_TYPE:
            terminal_by_run.setdefault(receipt.run_id, []).append(receipt)
        elif receipt.receipt_type == RECOVERY_RECEIPT_TYPE:
            recovery_by_run.setdefault(receipt.run_id, []).append(receipt)

    if any(len(group) != 1 for group in terminal_by_run.values()) or any(
        len(group) != 1 for group in recovery_by_run.values()
    ):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    if set(terminal_by_run) & set(recovery_by_run):
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
            or (task is not None and task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED})
        ):
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
            if run.status not in OWNER_TERMINAL_ATTEMPT_STATUSES or task.status != expected_task:
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif recoveries:
            if recoveries[0].status != "stale_recovered":
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if run.status != "stale_recovered":
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif run.status == "running" and task.status != TaskStatus.RUNNING:
            return ReconciliationState.NEEDS_TASK_PROJECTION
        elif run.status == "queued" and (
            task.status != TaskStatus.ASSIGNED
            or task.assigned_to != run.assigned_to
        ):
            return ReconciliationState.NEEDS_TASK_PROJECTION

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

    async def _recover_expired_claim(
        self,
        mission_id: str,
        claim: TaskClaim,
        *,
        recovered_at: datetime,
    ) -> None:
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
        if run is not None:
            self._require_attempt_identity(
                run, mission_id, claim.task_id, claim.agent_id
            )
            if run.claim_id != claim.claim_id:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has foreign identity"
                )
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
        existing = await self._runtime.list_runtime_receipts(
            run_id=attempt_id,
            receipt_type=RECOVERY_RECEIPT_TYPE,
            limit=100,
        )
        recovery = self._matching_receipt(
            existing,
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
