"""Attempt start and lease-heartbeat lifecycle for Mission Control."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from functools import wraps
from typing import Any

from dharma_swarm.mission_control_contract import (
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    SCHEMA_VERSION,
    AgentLeaseView,
    AttemptView,
    MissionControlError,
    claim_is_expired,
    claim_is_open,
    clean_identifier,
    lease_view,
    session_id as mission_session_id,
    stable_id,
    utc_now,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity


def _serialized_task(method):
    """Serialize lifecycle methods per task within this adapter instance only."""

    @wraps(method)
    async def guarded(self, mission_id, task_id, agent_id, *args, **kwargs):
        lock_key = clean_identifier(task_id, "task_id")
        lock = self._task_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            return await method(self, mission_id, task_id, agent_id, *args, **kwargs)

    return guarded


class MissionControlLifecycleMixin:
    """Create, acknowledge, and renew fenced mission attempts."""

    _runtime: Any
    _task_locks: dict[str, asyncio.Lock]

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
            if (
                identity.claim_id != existing.claim_id
                or identity.idempotency_key != key
            ):
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
        # Recovery may have projected pre-existing terminal evidence. Re-read
        # the independent TaskBoard owner before minting replacement lineage.
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


__all__ = ["MissionControlLifecycleMixin"]
