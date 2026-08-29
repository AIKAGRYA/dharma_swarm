"""Typed Mission Control projection over existing Dharma state owners.

Mission Control is an additive adapter, not a scheduler or state store.  It
joins TaskBoard tasks to RuntimeStateStore sessions, execution identities,
claims, delegation runs, and receipts.  Recorded state never proves that an
executor process is live.

TaskBoard and RuntimeStateStore use separate databases.  Mutations therefore
write runtime evidence before projecting terminal task state; a crash between
those steps is reported as ``needs_task_projection`` and is never presented as
an atomic completion. Terminal retry repairs a PENDING or ASSIGNED TaskBoard
projection from the same fenced identity before completing it. The adapter
serializes its own terminal writes with the runtime idempotency record, but the
owner still permits direct receipt upserts; true receipt immutability requires
an owner-schema constraint.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from typing import Any

from dharma_swarm.mission_control_contract import (
    GOVERNED_PATCH_COMPLETION_CONTRACT,
    RUNTIME_SCAN_LIMIT,
    SCHEMA_VERSION,
    TASK_SCAN_LIMIT,
    TERMINAL_RECEIPT_TYPE,
    AgentLeaseView,
    AttemptView,
    MissionControlError,
    MissionSnapshot,
    MissionView,
    ReceiptView,
    ReconciliationState,
    TaskView,
    clean_identifier,
    completion_contract_from_metadata,
    session_id as mission_session_id,
    utc_now,
)
from dharma_swarm.mission_control_lifecycle import MissionControlLifecycleMixin
from dharma_swarm.mission_control_effect_completion import (
    MissionControlEffectCompletionMixin,
)
from dharma_swarm.mission_control_projection import (
    MissionControlProjectionMixin,
    lease_view,
    mission_view,
    receipt_view,
    reconciliation,
    task_view,
)
from dharma_swarm.mission_control_recovery import MissionControlRecoveryMixin
from dharma_swarm.mission_control_effect_records import OwnerStoreBinding
from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionState,
    TaskClaim,
)
from dharma_swarm.runtime_state_effect_fence import EFFECT_RECEIPT_TYPE
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


def _operation_hash(label: str, payload: dict[str, Any]) -> str:
    """Hash caller-controlled creation intent using TaskBoard's JSON boundary."""
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionControlError(
            f"{label} metadata must be JSON-serializable"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


class MissionControl(
    MissionControlLifecycleMixin,
    MissionControlRecoveryMixin,
    MissionControlEffectCompletionMixin,
    MissionControlProjectionMixin,
):
    """Join and mutate canonical owner records without creating new storage."""

    def __init__(
        self,
        board: TaskBoard,
        runtime_state: RuntimeStateStore,
        *,
        immutable_snapshot_source_owners: OwnerStoreBinding | None = None,
    ) -> None:
        """Build an adapter over the two canonical owners.

        The owners use separate databases, so lifecycle mutations are not
        cross-database atomic.  RuntimeStateStore also has no uniqueness
        constraint for one active claim per task.  This adapter scans and
        fails closed on observed conflicts.  Per-task locks serialize calls on
        this instance, but they cannot provide a cross-process uniqueness
        guarantee against another writer; that requires an owner-store CAS.
        """
        self._board = board
        self._runtime = runtime_state
        self._task_locks: dict[str, asyncio.Lock] = {}
        self._mission_locks: dict[str, asyncio.Lock] = {}
        self._task_creation_locks: dict[str, asyncio.Lock] = {}
        self._immutable_snapshot_source_owners = immutable_snapshot_source_owners

    async def create_mission(
        self,
        mission_id: str,
        *,
        title: str,
        goal: str = "",
        operator_id: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> MissionView:
        mission_id = clean_identifier(mission_id, "mission_id")
        title = str(title or "").strip()
        if not title:
            raise MissionControlError("title is required")
        goal = str(goal or "")
        operator_id = str(operator_id or "system")
        requested_metadata = {
            **dict(metadata or {}),
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "title": title,
            "goal": goal,
        }
        creation_hash = _operation_hash(
            "mission",
            {
                "operator_id": operator_id,
                "metadata": requested_metadata,
            },
        )
        expected = {
            **requested_metadata,
            "mission_creation_hash": creation_hash,
        }
        lock = self._mission_locks.setdefault(mission_id, asyncio.Lock())
        async with lock:
            session_id = mission_session_id(mission_id)
            existing = await self._runtime.get_session(session_id)
            if existing is not None:
                if (
                    existing.operator_id != operator_id
                    or existing.metadata.get("mission_creation_hash") != creation_hash
                ):
                    raise MissionControlError(
                        f"mission {mission_id!r} already exists with conflicting content"
                    )
                return mission_view(existing)
            session = SessionState(
                session_id=session_id,
                operator_id=operator_id,
                status="active",
                metadata=expected,
            )
            return mission_view(await self._runtime.upsert_session(session))

    async def get_mission(self, mission_id: str) -> MissionView | None:
        session = await self._runtime.get_session(mission_session_id(mission_id))
        if session is None:
            return None
        self._require_mission_session(session, mission_id)
        return mission_view(session)

    async def create_task(
        self,
        mission_id: str,
        *,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        created_by: str = "system",
        depends_on: list[str] | None = None,
        idempotency_key: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TaskView:
        mission_id = clean_identifier(mission_id, "mission_id")
        await self._require_mission(mission_id)
        title = str(title or "")
        description = str(description or "")
        try:
            priority = TaskPriority(priority)
        except ValueError as exc:
            raise MissionControlError(f"invalid task priority: {priority!r}") from exc
        created_by = str(created_by or "system")
        dependency_ids = [
            clean_identifier(dependency_id, "depends_on item")
            for dependency_id in (depends_on or ())
        ]
        if len(set(dependency_ids)) != len(dependency_ids):
            raise MissionControlError("depends_on contains a duplicate task ID")
        for dependency_id in dependency_ids:
            dependency = await self._board.get(dependency_id)
            if dependency is None:
                raise MissionControlError(
                    f"dependency task {dependency_id!r} was not found"
                )
            if (
                dependency.metadata.get("mission_id") != mission_id
                or dependency.metadata.get("schema_version") != SCHEMA_VERSION
            ):
                raise MissionControlError(
                    f"dependency task {dependency_id!r} does not belong to "
                    f"mission {mission_id!r}"
                )
        key = str(idempotency_key or "").strip()
        requested_task_metadata = dict(metadata or {})
        completion_contract_from_metadata(requested_task_metadata)
        task_metadata = {
            **requested_task_metadata,
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
        }
        if key:
            task_metadata["mission_task_idempotency_key"] = key
        operation_hash = _operation_hash(
            "task",
            {
                "title": title,
                "description": description,
                "priority": priority.value,
                "created_by": created_by,
                "depends_on": sorted(dependency_ids),
                "metadata": task_metadata,
            },
        )
        task_metadata["mission_task_creation_hash"] = operation_hash
        lock_key = f"{mission_id}\x1f{key}" if key else f"{mission_id}\x1f:new"
        lock = self._task_creation_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            if key:
                scanned = await self._board.list_tasks(limit=TASK_SCAN_LIMIT + 1)
                for task in scanned[:TASK_SCAN_LIMIT]:
                    if task.metadata.get("mission_task_idempotency_key") == key:
                        if (
                            task.metadata.get("mission_id") != mission_id
                            or task.metadata.get("schema_version") != SCHEMA_VERSION
                        ):
                            continue
                        if (
                            task.metadata.get("mission_task_creation_hash")
                            != operation_hash
                        ):
                            raise MissionControlError(
                                f"task idempotency key {key!r} has conflicting content"
                            )
                        return task_view(task, mission_id)
                if len(scanned) > TASK_SCAN_LIMIT:
                    raise MissionControlError(
                        "task idempotency scan saturated; uniqueness cannot be proven"
                    )
            task = await self._board.create(
                title=title,
                description=description,
                priority=priority,
                created_by=created_by,
                depends_on=dependency_ids,
                metadata=task_metadata,
            )
            return task_view(task, mission_id)

    async def list_tasks(
        self,
        mission_id: str,
        *,
        status: TaskStatus | None = None,
        assigned_to: str | None = None,
        limit: int = 100,
    ) -> tuple[TaskView, ...]:
        mission_id = clean_identifier(mission_id, "mission_id")
        await self._require_mission(mission_id)
        if limit < 1:
            raise MissionControlError("limit must be positive")
        tasks = await self._mission_tasks(
            mission_id,
            status=status,
            assigned_to=assigned_to,
            limit=limit,
        )
        return tuple(task_view(task, mission_id) for task in tasks)

    async def get_snapshot(self, mission_id: str) -> MissionSnapshot | None:
        mission_id = clean_identifier(mission_id, "mission_id")
        mission = await self.get_mission(mission_id)
        if mission is None:
            return None
        now = utc_now()
        scanned_tasks = await self._board.list_tasks(limit=TASK_SCAN_LIMIT + 1)
        scan_saturated = len(scanned_tasks) > TASK_SCAN_LIMIT
        tasks = tuple(
            task_view(task, mission_id)
            for task in scanned_tasks[:TASK_SCAN_LIMIT]
            if task.metadata.get("mission_id") == mission_id
            and task.metadata.get("schema_version") == SCHEMA_VERSION
        )
        scanned_runs = await self._runtime.list_delegation_runs(
            session_id=mission_session_id(mission_id), limit=RUNTIME_SCAN_LIMIT + 1
        )
        scanned_claims = await self._runtime.list_task_claims(
            session_id=mission_session_id(mission_id), limit=RUNTIME_SCAN_LIMIT + 1
        )
        scan_saturated = scan_saturated or len(scanned_runs) > RUNTIME_SCAN_LIMIT
        scan_saturated = scan_saturated or len(scanned_claims) > RUNTIME_SCAN_LIMIT
        runs = scanned_runs[:RUNTIME_SCAN_LIMIT]
        claims = scanned_claims[:RUNTIME_SCAN_LIMIT]
        receipts: list[RuntimeReceipt] = []
        identities: dict[str, ExecutionIdentity | None] = {}
        attempt_ids = {run.run_id for run in runs}
        attempt_ids.update(
            str(claim.metadata.get("attempt_id") or "") for claim in claims
        )
        attempt_ids.discard("")
        receipt_budget = RUNTIME_SCAN_LIMIT
        for attempt_id in sorted(attempt_ids):
            identities[attempt_id] = await self._runtime.get_execution_identity(
                attempt_id
            )
            run_receipts = await self._runtime.list_runtime_receipts(
                run_id=attempt_id, limit=receipt_budget + 1
            )
            scan_saturated = scan_saturated or len(run_receipts) > receipt_budget
            receipts.extend(run_receipts[:receipt_budget])
            receipt_budget = max(0, receipt_budget - len(run_receipts))
        governed_proof_conflict = False
        if not scan_saturated:
            for receipt in receipts:
                if receipt.receipt_type == EFFECT_RECEIPT_TYPE:
                    identity = identities.get(receipt.run_id)
                    try:
                        if identity is not None and (
                            completion_contract_from_metadata(identity.metadata)
                            == GOVERNED_PATCH_COMPLETION_CONTRACT
                        ):
                            await self._validate_observed_patch_effect_receipts(
                                (receipt,)
                            )
                    except (
                        MissionControlError,
                        OSError,
                        RuntimeError,
                        sqlite3.Error,
                        TypeError,
                        ValueError,
                    ):
                        governed_proof_conflict = True
                        break
                    continue
                if receipt.receipt_type != TERMINAL_RECEIPT_TYPE:
                    continue
                identity = identities.get(receipt.run_id)
                try:
                    governed = identity is not None and (
                        completion_contract_from_metadata(identity.metadata)
                        == GOVERNED_PATCH_COMPLETION_CONTRACT
                    )
                    if not governed:
                        continue
                    metadata = receipt.payload.get("metadata")
                    effect_key = (
                        metadata.get("effect_key")
                        if type(metadata) is dict
                        else None
                    )
                    if type(effect_key) is not str or not effect_key:
                        raise MissionControlError(
                            "governed parent receipt lacks an effect key"
                        )
                    await self._validate_patch_effect_completion_readback(
                        receipt,
                        mission_id=mission_id,
                        task_id=identity.task_id,
                        agent_id=identity.agent_id,
                        attempt_id=identity.run_id,
                        effect_key=effect_key,
                    )
                except (
                    MissionControlError,
                    OSError,
                    RuntimeError,
                    sqlite3.Error,
                    TypeError,
                    ValueError,
                ):
                    governed_proof_conflict = True
                    break
        state = (
            ReconciliationState.EVIDENCE_SCAN_SATURATED
            if scan_saturated
            else ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if governed_proof_conflict
            else reconciliation(
                mission_id, tasks, runs, claims, receipts, identities, now
            )
        )
        return MissionSnapshot(
            mission=mission,
            tasks=tasks,
            attempts=tuple([await self._attempt_view(run) for run in runs]),
            leases=tuple(lease_view(claim, now=now) for claim in claims),
            receipts=tuple(receipt_view(receipt, mission_id) for receipt in receipts),
            reconciliation=state,
            observed_at=now,
        )

    async def _require_mission(self, mission_id: str) -> MissionView:
        mission = await self.get_mission(mission_id)
        if mission is None:
            raise MissionControlError(f"mission {mission_id!r} was not found")
        return mission

    async def _require_task(self, mission_id: str, task_id: str) -> Task:
        await self._require_mission(mission_id)
        task = await self._board.get(clean_identifier(task_id, "task_id"))
        if task is None:
            raise MissionControlError(f"task {task_id!r} was not found")
        if task.metadata.get("mission_id") != mission_id:
            raise MissionControlError(
                f"task {task_id!r} does not belong to mission {mission_id!r}"
            )
        if task.metadata.get("schema_version") != SCHEMA_VERSION:
            raise MissionControlError(f"task {task_id!r} has a foreign schema")
        return task

    async def _mission_tasks(
        self,
        mission_id: str,
        *,
        status: TaskStatus | None = None,
        assigned_to: str | None = None,
        limit: int,
    ) -> list[Task]:
        scan_limit = max(1_000, min(TASK_SCAN_LIMIT, limit * 10))
        scanned = await self._board.list_tasks(
            status=status, assigned_to=assigned_to, limit=scan_limit + 1
        )
        tasks = [
            task
            for task in scanned[:scan_limit]
            if task.metadata.get("mission_id") == mission_id
            and task.metadata.get("schema_version") == SCHEMA_VERSION
        ]
        if len(tasks) < limit and len(scanned) > scan_limit:
            raise MissionControlError(
                "task scan saturated; requested mission list may be incomplete"
            )
        return tasks[:limit]

    async def _resolve_attempt(
        self,
        mission_id: str,
        task_id: str,
        agent_id: str,
        *,
        attempt_id: str,
    ) -> DelegationRun:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        agent_id = clean_identifier(agent_id, "agent_id")
        await self._require_task(mission_id, task_id)
        if attempt_id:
            run = await self._runtime.get_delegation_run(attempt_id)
        else:
            runs = await self._runtime.list_delegation_runs(
                session_id=mission_session_id(mission_id),
                task_id=task_id,
                limit=RUNTIME_SCAN_LIMIT + 1,
            )
            if len(runs) > RUNTIME_SCAN_LIMIT:
                raise MissionControlError(
                    "attempt scan saturated; unique attempt cannot be proven"
                )
            matching = [run for run in runs if run.assigned_to == agent_id]
            if len(matching) > 1:
                raise MissionControlError(
                    "matching attempt is ambiguous; attempt_id is required"
                )
            run = matching[0] if matching else None
        if run is None:
            raise MissionControlError("matching attempt was not found")
        self._require_attempt_identity(run, mission_id, task_id, agent_id)
        return run

    async def _claims_for_fencing(self, task_id: str) -> list[TaskClaim]:
        claims = await self._runtime.list_task_claims(
            task_id=task_id,
            limit=RUNTIME_SCAN_LIMIT + 1,
        )
        if len(claims) > RUNTIME_SCAN_LIMIT:
            raise MissionControlError(
                "claim scan saturated; exclusive lease ownership cannot be proven"
            )
        return claims


# Preserve pre-split callable provenance for introspection and function pickles.
for _public_method_name in (
    "start_attempt",
    "heartbeat_lease",
    "finish_attempt",
    "finish_attempt_from_patch_effect",
):
    _public_method = getattr(MissionControl, _public_method_name)
    _public_method.__module__ = __name__
    _public_method.__qualname__ = f"MissionControl.{_public_method_name}"
del _public_method, _public_method_name


__all__ = [
    "AgentLeaseView",
    "AttemptView",
    "MissionControl",
    "MissionControlError",
    "MissionSnapshot",
    "MissionView",
    "ReceiptView",
    "ReconciliationState",
    "SCHEMA_VERSION",
    "TaskView",
]
