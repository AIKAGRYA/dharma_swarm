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
from dataclasses import replace
from datetime import timedelta
from functools import wraps
from typing import Any

from dharma_swarm.mission_control_contract import (
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    PUBLIC_TERMINAL_ATTEMPT_STATUSES,
    RUNTIME_SCAN_LIMIT,
    SCHEMA_VERSION,
    TASK_SCAN_LIMIT,
    TERMINAL_CAS_STALE_AFTER_SECONDS,
    TERMINAL_RECEIPT_TYPE,
    AgentLeaseView,
    AttemptView,
    MissionControlError,
    MissionSnapshot,
    MissionView,
    ReceiptView,
    ReconciliationState,
    TaskView,
    claim_is_expired,
    claim_is_open,
    clean_identifier,
    session_id as mission_session_id,
    stable_id,
    utc_now,
)
from dharma_swarm.mission_control_projection import (
    MissionControlProjectionMixin,
    lease_view,
    mission_view,
    receipt_view,
    reconciliation,
    task_view,
)
from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionState,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


def _serialized_task(method):
    """Serialize lifecycle methods per task within this adapter instance only."""

    @wraps(method)
    async def guarded(self, mission_id, task_id, agent_id, *args, **kwargs):
        lock_key = clean_identifier(task_id, "task_id")
        lock = self._task_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            return await method(
                self, mission_id, task_id, agent_id, *args, **kwargs
            )

    return guarded


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
        raise MissionControlError(f"{label} metadata must be JSON-serializable") from exc
    return hashlib.sha256(encoded).hexdigest()


class MissionControl(MissionControlProjectionMixin):
    """Join and mutate canonical owner records without creating new storage."""

    def __init__(self, board: TaskBoard, runtime_state: RuntimeStateStore) -> None:
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
                    or existing.metadata.get("mission_creation_hash")
                    != creation_hash
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
        task_metadata = {
            **dict(metadata or {}),
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

    @_serialized_task
    async def start_attempt(
        self,
        mission_id: str,
        task_id: str,
        agent_id: str,
        *,
        attempt_key: str = "",
        lease_seconds: int = 300,
        assigned_by: str = "mission_control",
        metadata: dict[str, Any] | None = None,
    ) -> AttemptView:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        agent_id = clean_identifier(agent_id, "agent_id")
        task = await self._require_task(mission_id, task_id)
        if lease_seconds < 1:
            raise MissionControlError("lease_seconds must be positive")

        key = str(attempt_key or "").strip() or stable_id(
            "attempt_key", mission_id, task_id, agent_id
        )
        attempt_id = stable_id("attempt", mission_id, task_id, agent_id, key)
        claim_id = stable_id("lease", attempt_id)
        claims = await self._claims_for_fencing(task_id)
        existing = await self._runtime.get_delegation_run(attempt_id)
        if existing is not None:
            self._require_attempt_identity(existing, mission_id, task_id, agent_id)
            if existing.metadata.get("attempt_key") != key:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting idempotency content"
                )
            identity = await self._runtime.get_execution_identity(attempt_id)
            if identity is None:
                raise MissionControlError(
                    f"execution identity for attempt {attempt_id!r} was not found"
                )
            self._require_identity(identity, mission_id, task_id, agent_id, attempt_id)
            if identity.claim_id != existing.claim_id or identity.idempotency_key != key:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting idempotency content"
                )
            claim = await self._runtime.get_task_claim(existing.claim_id)
            if claim is None:
                raise MissionControlError(f"claim {existing.claim_id!r} was not found")
            self._require_claim_identity(
                claim, mission_id, task_id, agent_id, attempt_id
            )
            if claim.metadata.get("attempt_key") != key:
                raise MissionControlError(
                    f"claim {claim.claim_id!r} has conflicting idempotency content"
                )
            if existing.status not in OWNER_TERMINAL_ATTEMPT_STATUSES:
                retry_now = utc_now()
                self._require_current_claim(
                    claim,
                    claims,
                    now=retry_now,
                    require_active=existing.status == "running",
                )
                if existing.status == "queued":
                    if not claim_is_open(claim, retry_now):
                        raise MissionControlError(
                            f"claim {claim.claim_id!r} is not open"
                        )
                    await self._project_assigned_task(
                        task,
                        mission_id=mission_id,
                        agent_id=agent_id,
                        attempt_id=attempt_id,
                        claim_id=claim.claim_id,
                    )
                elif existing.status == "running":
                    await self._project_running_task(
                        task,
                        mission_id=mission_id,
                        agent_id=agent_id,
                        attempt_id=attempt_id,
                        claim_id=claim.claim_id,
                    )
                else:
                    raise MissionControlError(
                        f"attempt {attempt_id!r} has unsupported status "
                        f"{existing.status!r}"
                    )
            return await self._attempt_view(existing)
        if task.status not in {
            TaskStatus.PENDING,
            TaskStatus.ASSIGNED,
            TaskStatus.RUNNING,
        }:
            raise MissionControlError(
                f"task {task_id!r} cannot start from {task.status.value!r}"
            )

        now = utc_now()
        orphan_claim = await self._runtime.get_task_claim(claim_id)
        terminal_repaired = False
        for prior_claim in claims:
            if (
                prior_claim.claim_id != claim_id
                and prior_claim.status.lower() in OPEN_CLAIM_STATUSES
                and claim_is_expired(prior_claim, now)
            ):
                terminal_repaired = await self._recover_expired_claim(
                    mission_id, prior_claim, recovered_at=now
                )
                if terminal_repaired:
                    break
        # Recovery may have projected pre-existing terminal evidence.  Re-read
        # the independent TaskBoard owner before minting any replacement lineage.
        task = await self._require_task(mission_id, task_id)
        if task.status not in {
            TaskStatus.PENDING,
            TaskStatus.ASSIGNED,
            TaskStatus.RUNNING,
        }:
            raise MissionControlError(
                f"task {task_id!r} cannot start from {task.status.value!r}"
            )
        claims = await self._claims_for_fencing(task_id)
        active = [
            claim
            for claim in claims
            if claim.claim_id != claim_id and claim_is_open(claim, now)
        ]
        if active:
            holders = ", ".join(sorted({claim.agent_id for claim in active}))
            raise MissionControlError(
                f"task {task_id!r} already has active claim holder(s): {holders}"
            )

        trace_id = stable_id("trace", attempt_id)
        identity = await self._runtime.get_execution_identity(attempt_id)
        if identity is None:
            identity = ExecutionIdentity.new(
                task_id=task_id,
                agent_id=agent_id,
                session_id=mission_session_id(mission_id),
                trace_id=trace_id,
                correlation_id=f"mission:{mission_id}:attempt:{attempt_id}",
                run_id=attempt_id,
                claim_id=claim_id,
                idempotency_key=key,
                metadata={"schema_version": SCHEMA_VERSION, "mission_id": mission_id},
            )
            await self._runtime.record_execution_identity(
                identity,
                source="mission_control.start_attempt",
            )
        else:
            self._require_identity(identity, mission_id, task_id, agent_id, attempt_id)
            if identity.claim_id != claim_id or identity.idempotency_key != key:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting idempotency content"
                )
        common_metadata = self._attempt_metadata(
            metadata,
            mission_id=mission_id,
            attempt_id=attempt_id,
            attempt_key=key,
        )
        if orphan_claim is None:
            claim = TaskClaim(
                claim_id=claim_id,
                task_id=task_id,
                agent_id=agent_id,
                status="claimed",
                session_id=mission_session_id(mission_id),
                claimed_at=now,
                acked_at=None,
                heartbeat_at=None,
                stale_after=now + timedelta(seconds=lease_seconds),
                metadata=common_metadata,
            )
            await self._runtime.record_task_claim(claim)
        else:
            claim = orphan_claim
            self._require_claim_identity(
                claim, mission_id, task_id, agent_id, attempt_id
            )
            if claim.metadata.get("attempt_key") != key:
                raise MissionControlError(
                    f"claim {claim.claim_id!r} has conflicting idempotency content"
                )
            self._require_current_claim(
                claim,
                claims,
                now=now,
                require_active=False,
            )
            if not claim_is_open(claim, now):
                state = "expired" if claim_is_expired(claim, now) else "not open"
                raise MissionControlError(f"claim {claim.claim_id!r} is {state}")
            common_metadata = self._attempt_metadata(
                metadata,
                base=claim.metadata,
                mission_id=mission_id,
                attempt_id=attempt_id,
                attempt_key=key,
            )
        run = DelegationRun(
            run_id=attempt_id,
            task_id=task_id,
            assigned_to=agent_id,
            status="queued",
            session_id=mission_session_id(mission_id),
            claim_id=claim_id,
            assigned_by=str(assigned_by or "mission_control"),
            started_at=now,
            metadata=common_metadata,
        )
        run = await self._runtime.record_delegation_run(run)
        await self._project_assigned_task(
            task,
            mission_id=mission_id,
            agent_id=agent_id,
            attempt_id=attempt_id,
            claim_id=claim_id,
        )
        return await self._attempt_view(run)

    @_serialized_task
    async def heartbeat_lease(
        self,
        mission_id: str,
        task_id: str,
        agent_id: str,
        *,
        attempt_id: str = "",
        lease_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> AgentLeaseView:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        agent_id = clean_identifier(agent_id, "agent_id")
        run = await self._resolve_attempt(
            mission_id, task_id, agent_id, attempt_id=attempt_id
        )
        if lease_seconds < 1:
            raise MissionControlError("lease_seconds must be positive")
        if run.status not in {"queued", "running"}:
            raise MissionControlError(
                f"attempt {run.run_id!r} cannot heartbeat from {run.status!r}"
            )
        claim = await self._runtime.get_task_claim(run.claim_id)
        if claim is None:
            raise MissionControlError(f"claim {run.claim_id!r} was not found")
        self._require_claim_identity(claim, mission_id, task_id, agent_id, run.run_id)
        if claim.status.lower() not in OPEN_CLAIM_STATUSES:
            raise MissionControlError(f"claim {claim.claim_id!r} is not open")
        now = utc_now()
        if claim_is_expired(claim, now):
            raise MissionControlError(f"claim {claim.claim_id!r} is expired")
        task = await self._require_task(mission_id, task_id)
        if task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            raise MissionControlError(
                f"task {task_id!r} is terminal and cannot be heartbeated"
            )
        claims = await self._claims_for_fencing(task_id)
        self._require_current_claim(claim, claims, now=now, require_active=False)
        attempt_key = str(run.metadata.get("attempt_key") or "")
        updated = replace(
            claim,
            status="active",
            acked_at=claim.acked_at or now,
            heartbeat_at=now,
            stale_after=now + timedelta(seconds=lease_seconds),
            metadata=self._attempt_metadata(
                metadata,
                base=claim.metadata,
                mission_id=mission_id,
                attempt_id=run.run_id,
                attempt_key=attempt_key,
            ),
        )
        updated = await self._runtime.record_task_claim(updated)
        if run.status != "running":
            run = await self._runtime.record_delegation_run(
                replace(
                    run,
                    status="running",
                    metadata=self._attempt_metadata(
                        metadata,
                        base=run.metadata,
                        mission_id=mission_id,
                        attempt_id=run.run_id,
                        attempt_key=attempt_key,
                    ),
                )
            )
        await self._project_running_task(
            task,
            mission_id=mission_id,
            agent_id=agent_id,
            attempt_id=run.run_id,
            claim_id=claim.claim_id,
        )
        return lease_view(updated, now=now)

    @_serialized_task
    async def finish_attempt(
        self,
        mission_id: str,
        task_id: str,
        agent_id: str,
        *,
        attempt_id: str = "",
        status: str,
        result: str = "",
        failure_code: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReceiptView:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        agent_id = clean_identifier(agent_id, "agent_id")
        terminal_status = str(status or "").strip().lower()
        if terminal_status not in PUBLIC_TERMINAL_ATTEMPT_STATUSES:
            raise MissionControlError("status must be 'succeeded' or 'failed'")
        run = await self._resolve_attempt(
            mission_id, task_id, agent_id, attempt_id=attempt_id
        )
        task = await self._require_task(mission_id, task_id)
        identity = await self._runtime.get_execution_identity(run.run_id)
        if identity is None:
            raise MissionControlError(
                f"execution identity for attempt {run.run_id!r} was not found"
            )
        self._require_identity(identity, mission_id, task_id, agent_id, run.run_id)
        if identity.claim_id != run.claim_id:
            raise MissionControlError(
                f"execution identity for {run.run_id!r} has foreign fields"
            )
        attempt_key = str(run.metadata.get("attempt_key") or identity.idempotency_key)
        owner_terminal_status = (
            "completed" if terminal_status == "succeeded" else "failed"
        )
        safe_metadata = self._attempt_metadata(
            metadata,
            mission_id=mission_id,
            attempt_id=run.run_id,
            attempt_key=attempt_key,
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": run.run_id,
            "result": str(result or ""),
            "failure_code": str(failure_code or ""),
            "metadata": safe_metadata,
        }
        receipt_id = stable_id("receipt", run.run_id, terminal_status)
        side_effect_key = f"mission_control:{run.run_id}:terminal"
        operation = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": run.run_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "status": terminal_status,
            "receipt_id": receipt_id,
            "payload": payload,
        }
        operation_hash = hashlib.sha256(
            json.dumps(
                operation,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        idempotency_metadata = {
            "operation_hash": operation_hash,
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": run.run_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "terminal_status": terminal_status,
        }
        existing_receipts = await self._runtime.list_runtime_receipts(
            run_id=run.run_id,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            limit=100,
        )
        receipt = self._matching_terminal_receipt(
            existing_receipts,
            identity=identity,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status=terminal_status,
            payload=payload,
        )
        claim = await self._runtime.get_task_claim(run.claim_id)
        if claim is None:
            raise MissionControlError(f"claim {run.claim_id!r} was not found")
        self._require_claim_identity(claim, mission_id, task_id, agent_id, run.run_id)
        claims = await self._claims_for_fencing(task_id)
        self._require_current_claim(
            claim,
            claims,
            now=utc_now(),
            require_active=receipt is None,
        )
        if (
            run.status in OWNER_TERMINAL_ATTEMPT_STATUSES
            and run.status != owner_terminal_status
        ):
            raise MissionControlError(
                f"attempt {run.run_id!r} already has conflicting terminal evidence"
            )
        if receipt is None and run.status != "running":
            raise MissionControlError(
                f"attempt {run.run_id!r} has not been acknowledged as running"
            )

        try:
            ownership_token = (
                await self._runtime.try_begin_idempotent_side_effect_with_token(
                    identity,
                    side_effect_key,
                    metadata=idempotency_metadata,
                    stale_after_seconds=TERMINAL_CAS_STALE_AFTER_SECONDS,
                )
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            raise MissionControlError(
                f"attempt {run.run_id!r} already has conflicting terminal evidence"
            ) from exc

        # Re-read after the compare-and-set.  A duplicate can repair projections,
        # but only the holder of the ownership token may create terminal evidence.
        existing_receipts = await self._runtime.list_runtime_receipts(
            run_id=run.run_id,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            limit=100,
        )
        receipt = self._matching_terminal_receipt(
            existing_receipts,
            identity=identity,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status=terminal_status,
            payload=payload,
        )
        ownership_token, ownership_complete = await self._recover_terminal_ownership(
            identity,
            side_effect_key=side_effect_key,
            operation_hash=operation_hash,
            receipt=receipt,
            receipt_id=receipt_id,
            ownership_token=ownership_token,
        )
        if receipt is None:
            receipt = await self._runtime.record_receipt_for_identity(
                identity,
                receipt_type=TERMINAL_RECEIPT_TYPE,
                status=terminal_status,
                side_effect_key=side_effect_key,
                payload=payload,
                receipt_id=receipt_id,
            )
        if not ownership_complete:
            try:
                await self._runtime.complete_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt.receipt_id,
                    metadata=idempotency_metadata,
                    expected_updated_at=ownership_token,
                )
            except (KeyError, RuntimeError, ValueError) as exc:
                raise MissionControlError(
                    f"terminal ownership for attempt {run.run_id!r} was lost"
                ) from exc
        await self._project_terminal_lineage(
            mission_id,
            task=task,
            run=run,
            claim=claim,
            identity=identity,
            receipt=receipt,
        )
        return receipt_view(receipt, mission_id)

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
        state = (
            ReconciliationState.EVIDENCE_SCAN_SATURATED
            if scan_saturated
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
