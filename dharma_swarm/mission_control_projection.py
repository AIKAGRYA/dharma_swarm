from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from dharma_swarm.mission_control_contract import (
    COMPLETION_CONTRACT_METADATA_KEY,
    GOVERNED_PATCH_COMPLETION_CONTRACT,
    OPEN_CLAIM_STATUSES,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    AttemptView,
    MissionControlError,
    attempt_view,
    claim_is_active,
    claim_is_expired,
    claim_is_open,
    completion_contract_from_metadata,
    lease_view,
    mission_view,
    receipt_view,
    require_same_completion_contract,
    session_id,
    terminal_receipt_contract,
    task_view,
    utc_now,
)
from dharma_swarm.mission_control_reconciliation import (
    reconciliation,
    terminal_claim_projection_matches,
    terminal_run_projection_matches,
    terminal_task_projection_matches,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    SessionState,
    TaskClaim,
)
from dharma_swarm.runtime_state_effect_fence import EFFECT_RECEIPT_TYPE
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard, TaskBoardError


reconciliation.__module__ = __name__
reconciliation.__qualname__ = "reconciliation"


async def project_assigned_task(
    board: TaskBoard, task: Task, *, mission_id: str, agent_id: str,
    attempt_id: str, claim_id: str,
) -> None:
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
    board: TaskBoard, task: Task, *, mission_id: str, agent_id: str,
    attempt_id: str, claim_id: str,
) -> None:
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
    board: TaskBoard, task: Task, terminal_status: str, result: str,
    failure_code: str,
) -> None:
    current = await board.get(task.id)
    if current is None:
        raise MissionControlError(f"task {task.id!r} was not found")
    expected = (
        TaskStatus.COMPLETED if terminal_status == "succeeded" else TaskStatus.FAILED
    )
    if current.status == expected:
        if not terminal_task_projection_matches(
            current, terminal_status=terminal_status, result=result,
            failure_code=failure_code,
            expected_agent_id=str(task.assigned_to or ""),
            expected_metadata=task.metadata,
        ):
            raise MissionControlError(
                f"task {task.id!r} has conflicting terminal projection"
            )
        return
    if current.status in {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }:
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


class MissionControlProjectionMixin:

    _board: TaskBoard
    _runtime: Any

    @staticmethod
    def _attempt_metadata(
        metadata: dict[str, Any] | None, *, mission_id: str, attempt_id: str,
        attempt_key: str,
        base: dict[str, Any] | None = None,
        completion_contract: str | None = None,
    ) -> dict[str, Any]:
        base_metadata = dict(base or {})
        requested_metadata = dict(metadata or {})
        observed = tuple(
            completion_contract_from_metadata(value)
            for value in (base_metadata, requested_metadata)
            if COMPLETION_CONTRACT_METADATA_KEY in value
        )
        required = completion_contract
        if required is None:
            required = observed[0] if observed else ""
        if required not in {"", GOVERNED_PATCH_COMPLETION_CONTRACT} or any(
            value != required for value in observed
        ):
            raise MissionControlError("completion_contract lineage disagrees")
        result = {
            **base_metadata, **requested_metadata, "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id, "attempt_id": attempt_id,
            "attempt_key": attempt_key,
        }
        result.pop(COMPLETION_CONTRACT_METADATA_KEY, None)
        if required:
            result[COMPLETION_CONTRACT_METADATA_KEY] = required
        return result

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
            if candidate.claim_id != claim.claim_id and claim_is_open(candidate, now)
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
        current_task = await self._board.get(task.id)
        if current_task is None:
            raise MissionControlError(f"task {task.id!r} was not found")
        require_same_completion_contract(
            current_task.metadata, run.metadata, claim.metadata, identity.metadata
        )
        supporting = []
        if completion_contract_from_metadata(identity.metadata):
            supporting = await self._runtime.list_runtime_receipts(
                run_id=identity.run_id, receipt_type=EFFECT_RECEIPT_TYPE, limit=2
            )
        terminal_status, owner_status, result, failure_code, metadata = (
            terminal_receipt_contract(
                receipt, identity, mission_id, supporting_receipts=supporting
            )
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
        if run.status not in {"running", owner_status}:
            raise MissionControlError(
                f"attempt {identity.run_id!r} has conflicting terminal evidence"
            )
        claim_terminal = "completed" if terminal_status == "succeeded" else "failed"
        claim_status = claim.status.lower()
        if claim_status not in OPEN_CLAIM_STATUSES | {claim_terminal}:
            raise MissionControlError(
                f"claim {claim.claim_id!r} has conflicting terminal evidence"
            )
        if run.status == owner_status:
            if not terminal_run_projection_matches(run, receipt):
                raise MissionControlError(
                    f"attempt {identity.run_id!r} has conflicting terminal evidence"
                )
        elif (
            run.completed_at is not None
            or run.failure_code
            or run.started_at > receipt.created_at
        ):
            raise MissionControlError(
                f"attempt {identity.run_id!r} has conflicting terminal evidence"
            )
        if claim_status == claim_terminal and not terminal_claim_projection_matches(
            claim, receipt
        ):
            raise MissionControlError(
                f"claim {claim.claim_id!r} has conflicting terminal evidence"
            )
        now = utc_now()
        if run.status != owner_status or run.completed_at is None:
            run = await self._runtime.record_delegation_run(
                replace(
                    run,
                    status=owner_status,
                    completed_at=receipt.created_at,
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
        if current_task.status in {
            TaskStatus.PENDING,
            TaskStatus.ASSIGNED,
            TaskStatus.RUNNING,
        }:
            await self._project_running_task(
                current_task,
                mission_id=mission_id,
                agent_id=identity.agent_id,
                attempt_id=identity.run_id,
                claim_id=identity.claim_id,
            )
        await self._project_terminal_task(task, terminal_status, result, failure_code)
        if claim_status != claim_terminal:
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
        self, task: Task, terminal_status: str, result: str,
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
            or run.metadata.get("attempt_id") != run.run_id
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
