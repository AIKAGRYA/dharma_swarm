"""Bind Mission Control tasks to the canonical in-process Orchestrator.

This module is an additive adapter.  It owns no scheduler, worker pool, state
store, transport, or lifecycle.  The Orchestrator remains the only executor
and writes its native claim, run, identity, and receipts.  Mission Control is
used only to validate the mission boundary; its attempt lifecycle is never
called here because wrapping an Orchestrator dispatch in a second attempt
would create competing owner records.

TaskBoard metadata and runtime state are separate transactional domains.  A
per-task lock prevents duplicate dispatches through one adapter instance, and
a stable durable identity lets retries recover completed or in-flight owner
runs.  There is no cross-process compare-and-swap, so this is not a fleet-wide
exactly-once guarantee.  Recorded owner state also does not prove that an
executor process is alive.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (
    OPEN_CLAIM_STATUSES,
    RUNTIME_SCAN_LIMIT,
    SCHEMA_VERSION,
    MissionControlError,
    clean_identifier,
    session_id as mission_session_id,
    stable_id,
    utc_now,
)
from dharma_swarm.models import Task, TaskStatus, TopologyType
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


EXECUTION_SCHEMA_VERSION = "dharma.mission_control.owner_execution.v1"
EXECUTION_METADATA_KEY = "mission_control_owner_execution"
OWNER_BACKEND = "orchestrator"
OWNER_TERMINAL_STATUSES = frozenset({"completed", "failed"})
OWNER_RUN_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})
OWNER_CLAIM_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})


@dataclass(frozen=True, slots=True)
class OwnerExecutionRef:
    """Stable join keys for one Orchestrator-owned mission execution."""

    backend: str
    mission_id: str
    task_id: str
    dispatch_key: str
    run_id: str
    claim_id: str
    agent_id: str
    idempotency_key: str
    owner_session_id: str


@dataclass(frozen=True, slots=True)
class OwnerExecutionObservation:
    """Read-only projection of canonical owner records.

    ``proves_executor_liveness`` is deliberately false.  Claims, heartbeats,
    and a recorded ``running`` state prove only that lifecycle writes occurred.
    """

    ref: OwnerExecutionRef
    task_status: TaskStatus
    run_status: str
    claim_status: str
    stale: bool
    receipt_ids: tuple[str, ...]
    terminal: bool
    succeeded: bool
    result: str
    failure_code: str
    observed_at: datetime
    proves_executor_liveness: bool = False


class OrchestratorMissionAdapter:
    """Dispatch existing mission tasks through an injected Orchestrator."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        mission_control: MissionControl,
        board: TaskBoard,
        runtime_state: RuntimeStateStore,
        *,
        scan_limit: int = RUNTIME_SCAN_LIMIT,
    ) -> None:
        if scan_limit < 2:
            raise ValueError("scan_limit must be at least 2")
        self._orchestrator = orchestrator
        self._mission_control = mission_control
        self._board = board
        self._runtime = runtime_state
        self._scan_limit = scan_limit
        self._task_locks: dict[str, asyncio.Lock] = {}

    async def dispatch(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> OwnerExecutionRef:
        """Dispatch once locally or recover the matching durable owner run.

        The Orchestrator chooses the agent and creates its own claim.  Stable
        run and idempotency keys are stamped on the existing task immediately
        before the public dispatch call so the Orchestrator's native lifecycle
        adopts them.  A crash between the metadata write and dispatch is safe
        to retry only while the task remains pending.
        """

        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        dispatch_key = clean_identifier(dispatch_key, "dispatch_key")
        lock = self._task_locks.setdefault(task_id, asyncio.Lock())
        async with lock:
            task = await self._require_task(mission_id, task_id)
            expected = self._expected_identity(mission_id, task_id, dispatch_key)
            recovered = await self._recover_owner_ref(
                mission_id,
                task_id,
                dispatch_key,
                expected_run_id=expected["run_id"],
                expected_idempotency_key=expected["idempotency_key"],
            )
            if recovered is not None:
                return recovered

            self._require_dispatchable(task)
            await self._require_dependencies_completed(task)
            stamped = self._stamp_metadata(
                task,
                mission_id=mission_id,
                dispatch_key=dispatch_key,
                expected=expected,
            )
            await self._board.update_task(task_id, metadata=stamped)
            task = await self._require_task(mission_id, task_id)
            self._require_stamp(task, mission_id, dispatch_key, expected)

            dispatches = await self._orchestrator.dispatch(
                task,
                TopologyType.PIPELINE,
            )
            if len(dispatches) != 1:
                raise MissionControlError(
                    "canonical Orchestrator must return exactly one PIPELINE dispatch"
                )
            dispatch = dispatches[0]
            if dispatch.task_id != task_id or dispatch.topology != TopologyType.PIPELINE:
                raise MissionControlError("Orchestrator returned a foreign dispatch")
            self._require_dispatch_metadata(dispatch.metadata, expected)

            run = await self._runtime.get_delegation_run(expected["run_id"])
            identity = await self._runtime.get_execution_identity(expected["run_id"])
            if run is None or identity is None:
                raise MissionControlError(
                    "Orchestrator returned without durable run and identity evidence"
                )
            return await self._ref_from_records(
                mission_id,
                task_id,
                dispatch_key,
                expected["idempotency_key"],
                run,
                identity,
            )

    async def observe(
        self,
        ref: OwnerExecutionRef,
    ) -> OwnerExecutionObservation:
        """Read canonical owner records without mutating or acknowledging them."""

        self._require_ref_shape(ref)
        expected = self._expected_identity(
            ref.mission_id,
            ref.task_id,
            ref.dispatch_key,
        )
        if (
            ref.run_id != expected["run_id"]
            or ref.idempotency_key != expected["idempotency_key"]
        ):
            raise MissionControlError(
                "owner execution reference conflicts with its stable dispatch key"
            )
        task = await self._require_task(ref.mission_id, ref.task_id)
        run = await self._runtime.get_delegation_run(ref.run_id)
        identity = await self._runtime.get_execution_identity(ref.run_id)
        claim = await self._runtime.get_task_claim(ref.claim_id)
        if run is None or identity is None or claim is None:
            raise MissionControlError("owner execution records are incomplete")
        validated = await self._ref_from_records(
            ref.mission_id,
            ref.task_id,
            ref.dispatch_key,
            ref.idempotency_key,
            run,
            identity,
        )
        if validated != ref:
            raise MissionControlError("owner execution reference conflicts with durable state")
        self._require_claim(claim, run, identity, ref.mission_id)

        receipts = await self._runtime.list_runtime_receipts(
            run_id=ref.run_id,
            limit=self._scan_limit,
        )
        if len(receipts) >= self._scan_limit:
            raise MissionControlError(
                "runtime receipt scan saturated; complete evidence cannot be proven"
            )
        self._require_receipts(receipts, ref)

        observed_at = utc_now()
        run_status = run.status.lower()
        claim_status = claim.status.lower()
        stale = (
            claim_status in OPEN_CLAIM_STATUSES
            and claim.stale_after is not None
            and claim.stale_after <= observed_at
        )
        terminal = run_status in OWNER_TERMINAL_STATUSES
        succeeded = run_status == "completed" and task.status == TaskStatus.COMPLETED
        if run_status == "completed" and task.status != TaskStatus.COMPLETED:
            raise MissionControlError(
                "completed owner run conflicts with non-completed TaskBoard state"
            )
        return OwnerExecutionObservation(
            ref=ref,
            task_status=task.status,
            run_status=run_status,
            claim_status=claim_status,
            stale=stale,
            receipt_ids=tuple(receipt.receipt_id for receipt in receipts),
            terminal=terminal,
            succeeded=succeeded,
            result=str(task.result or ""),
            failure_code=str(run.failure_code or ""),
            observed_at=observed_at,
        )

    async def wait(
        self,
        ref: OwnerExecutionRef,
        *,
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 0.25,
    ) -> OwnerExecutionObservation:
        """Poll the read-only owner projection until its run is terminal."""

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        while True:
            observation = await self.observe(ref)
            if observation.terminal:
                return observation
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"owner execution {ref.run_id!r} did not become terminal"
                )
            await asyncio.sleep(min(poll_interval_seconds, remaining))

    async def _require_task(self, mission_id: str, task_id: str) -> Task:
        mission = await self._mission_control.get_mission(mission_id)
        if mission is None:
            raise MissionControlError(f"mission {mission_id!r} was not found")
        task = await self._board.get(task_id)
        if task is None:
            raise MissionControlError(f"task {task_id!r} was not found")
        if task.metadata.get("mission_id") != mission_id:
            raise MissionControlError(
                f"task {task_id!r} does not belong to mission {mission_id!r}"
            )
        if task.metadata.get("schema_version") != SCHEMA_VERSION:
            raise MissionControlError(f"task {task_id!r} has a foreign schema")
        return task

    async def _recover_owner_ref(
        self,
        mission_id: str,
        task_id: str,
        dispatch_key: str,
        *,
        expected_run_id: str,
        expected_idempotency_key: str,
    ) -> OwnerExecutionRef | None:
        runs = await self._runtime.list_delegation_runs(
            task_id=task_id,
            limit=self._scan_limit,
        )
        if len(runs) >= self._scan_limit:
            raise MissionControlError(
                "delegation run scan saturated; uniqueness cannot be proven"
            )
        matches: list[tuple[DelegationRun, ExecutionIdentity]] = []
        for run in runs:
            identity = await self._runtime.get_execution_identity(run.run_id)
            candidate = (
                run.run_id == expected_run_id
                or run.metadata.get("idempotency_key") == expected_idempotency_key
                or (
                    identity is not None
                    and identity.idempotency_key == expected_idempotency_key
                )
            )
            if not candidate:
                if (
                    run.assigned_by == OWNER_BACKEND
                    and run.status.lower() not in OWNER_TERMINAL_STATUSES
                ):
                    raise MissionControlError(
                        "task has a conflicting active Orchestrator execution"
                    )
                continue
            if identity is None:
                raise MissionControlError(
                    "matching owner run has no durable execution identity"
                )
            matches.append((run, identity))
        if len(matches) > 1:
            raise MissionControlError(
                "matching owner execution is ambiguous; refusing duplicate dispatch"
            )
        if not matches:
            return None
        run, identity = matches[0]
        return await self._ref_from_records(
            mission_id,
            task_id,
            dispatch_key,
            expected_idempotency_key,
            run,
            identity,
        )

    async def _ref_from_records(
        self,
        mission_id: str,
        task_id: str,
        dispatch_key: str,
        expected_idempotency_key: str,
        run: DelegationRun,
        identity: ExecutionIdentity,
    ) -> OwnerExecutionRef:
        expected = self._expected_identity(mission_id, task_id, dispatch_key)
        if (
            run.run_id != expected["run_id"]
            or expected_idempotency_key != expected["idempotency_key"]
        ):
            raise MissionControlError("owner run conflicts with stable dispatch identity")
        if run.run_id != identity.run_id or run.task_id != task_id:
            raise MissionControlError("owner run identity does not match the mission task")
        if identity.task_id != task_id:
            raise MissionControlError("execution identity names a foreign task")
        if identity.idempotency_key != expected_idempotency_key:
            raise MissionControlError("owner idempotency key conflicts with dispatch key")
        if not identity.claim_id or run.claim_id != identity.claim_id:
            raise MissionControlError("owner claim identity is missing or inconsistent")
        if not identity.agent_id or run.assigned_to != identity.agent_id:
            raise MissionControlError("owner agent identity is missing or inconsistent")
        if not identity.session_id or run.session_id != identity.session_id:
            raise MissionControlError("owner session identity is missing or inconsistent")
        if identity.session_id == mission_session_id(mission_id):
            raise MissionControlError(
                "Orchestrator owner session must remain distinct from mission session"
            )
        if run.assigned_by != OWNER_BACKEND:
            raise MissionControlError("delegation run is not owned by the Orchestrator")
        if run.metadata.get("mission_id") != mission_id:
            raise MissionControlError("delegation run names a foreign mission")
        if run.metadata.get("topology") != TopologyType.PIPELINE.value:
            raise MissionControlError("delegation run is not a PIPELINE execution")
        if run.status.lower() not in OWNER_RUN_STATUSES:
            raise MissionControlError("delegation run has an invalid owner status")
        claim = await self._runtime.get_task_claim(identity.claim_id)
        if claim is None:
            raise MissionControlError("owner claim was not found")
        self._require_claim(claim, run, identity, mission_id)
        return OwnerExecutionRef(
            backend=OWNER_BACKEND,
            mission_id=mission_id,
            task_id=task_id,
            dispatch_key=dispatch_key,
            run_id=run.run_id,
            claim_id=identity.claim_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            owner_session_id=identity.session_id,
        )

    @staticmethod
    def _require_claim(
        claim: TaskClaim,
        run: DelegationRun,
        identity: ExecutionIdentity,
        mission_id: str,
    ) -> None:
        if (
            claim.claim_id != identity.claim_id
            or claim.task_id != identity.task_id
            or claim.agent_id != identity.agent_id
            or claim.session_id != identity.session_id
            or run.claim_id != claim.claim_id
        ):
            raise MissionControlError("owner claim conflicts with run identity")
        if claim.metadata.get("mission_id") != mission_id:
            raise MissionControlError("owner claim names a foreign mission")
        if claim.status.lower() not in OWNER_CLAIM_STATUSES:
            raise MissionControlError("owner claim has an invalid status")

    @staticmethod
    def _require_receipts(
        receipts: list[RuntimeReceipt],
        ref: OwnerExecutionRef,
    ) -> None:
        seen: set[str] = set()
        for receipt in receipts:
            if receipt.receipt_id in seen:
                raise MissionControlError("duplicate runtime receipt identity observed")
            seen.add(receipt.receipt_id)
            if receipt.run_id != ref.run_id:
                raise MissionControlError("runtime receipt names a foreign run")
            if receipt.task_id and receipt.task_id != ref.task_id:
                raise MissionControlError("runtime receipt names a foreign task")
            if receipt.agent_id and receipt.agent_id != ref.agent_id:
                raise MissionControlError("runtime receipt names a foreign agent")
            if (
                receipt.receipt_type in {"task_claim", "delegation_run"}
                and receipt.idempotency_key != ref.idempotency_key
            ):
                raise MissionControlError(
                    "runtime receipt names a foreign idempotency key"
                )

    @staticmethod
    def _expected_identity(
        mission_id: str,
        task_id: str,
        dispatch_key: str,
    ) -> dict[str, str]:
        parts = (mission_id, task_id, dispatch_key)
        return {
            "run_id": stable_id("owner_run", *parts),
            "idempotency_key": stable_id("owner_dispatch", *parts),
            "trace_id": stable_id("owner_trace", *parts),
            "correlation_id": stable_id("owner_correlation", *parts),
        }

    def _stamp_metadata(
        self,
        task: Task,
        *,
        mission_id: str,
        dispatch_key: str,
        expected: dict[str, str],
    ) -> dict[str, Any]:
        self._require_stamp_compatible(task.metadata, mission_id, dispatch_key, expected)
        marker = {
            "schema_version": EXECUTION_SCHEMA_VERSION,
            "backend": OWNER_BACKEND,
            "mission_id": mission_id,
            "task_id": task.id,
            "dispatch_key": dispatch_key,
            **expected,
        }
        return {
            **dict(task.metadata),
            EXECUTION_METADATA_KEY: marker,
            "runtime_run_id": expected["run_id"],
            "run_id": expected["run_id"],
            "idempotency_key": expected["idempotency_key"],
            "trace_id": expected["trace_id"],
            "correlation_id": expected["correlation_id"],
        }

    def _require_stamp(
        self,
        task: Task,
        mission_id: str,
        dispatch_key: str,
        expected: dict[str, str],
    ) -> None:
        self._require_stamp_compatible(task.metadata, mission_id, dispatch_key, expected)
        marker = task.metadata.get(EXECUTION_METADATA_KEY)
        if not isinstance(marker, dict):
            raise MissionControlError("owner dispatch metadata was not persisted")

    @staticmethod
    def _require_stamp_compatible(
        metadata: dict[str, Any],
        mission_id: str,
        dispatch_key: str,
        expected: dict[str, str],
    ) -> None:
        marker = metadata.get(EXECUTION_METADATA_KEY)
        if marker is not None and not isinstance(marker, dict):
            raise MissionControlError("owner execution metadata has an invalid shape")
        if isinstance(marker, dict):
            required = {
                "schema_version": EXECUTION_SCHEMA_VERSION,
                "backend": OWNER_BACKEND,
                "mission_id": mission_id,
                "dispatch_key": dispatch_key,
                **expected,
            }
            if any(marker.get(key) != value for key, value in required.items()):
                raise MissionControlError("task carries a conflicting owner dispatch")
        elif any(
            str(metadata.get(key) or "").strip()
            for key in (
                "runtime_run_id",
                "run_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            )
        ) or isinstance(metadata.get("execution_identity"), dict):
            raise MissionControlError(
                "task already carries foreign execution identity metadata"
            )
        for key in (
            "runtime_run_id",
            "run_id",
            "idempotency_key",
            "trace_id",
            "correlation_id",
        ):
            value = str(metadata.get(key) or "").strip()
            if value and value != expected[key if key != "runtime_run_id" else "run_id"]:
                raise MissionControlError("task owner identity metadata is inconsistent")
        nested = metadata.get("execution_identity")
        if isinstance(nested, dict):
            for key in ("run_id", "idempotency_key", "trace_id", "correlation_id"):
                value = str(nested.get(key) or "").strip()
                if value and value != expected[key]:
                    raise MissionControlError("nested owner identity is inconsistent")

    @staticmethod
    def _require_dispatch_metadata(
        metadata: dict[str, Any],
        expected: dict[str, str],
    ) -> None:
        nested = metadata.get("execution_identity")
        identity = nested if isinstance(nested, dict) else {}
        observed_run = str(
            identity.get("run_id")
            or metadata.get("runtime_run_id")
            or metadata.get("run_id")
            or ""
        )
        observed_key = str(
            identity.get("idempotency_key")
            or metadata.get("idempotency_key")
            or ""
        )
        if observed_run != expected["run_id"] or observed_key != expected["idempotency_key"]:
            raise MissionControlError("Orchestrator changed the stable owner identity")

    async def _require_dependencies_completed(self, task: Task) -> None:
        for dependency_id in task.depends_on:
            dependency = await self._board.get(dependency_id)
            if dependency is None or dependency.status != TaskStatus.COMPLETED:
                raise MissionControlError(
                    f"task dependency {dependency_id!r} is not completed"
                )

    def _require_dispatchable(self, task: Task) -> None:
        if task.status != TaskStatus.PENDING:
            raise MissionControlError(
                f"task {task.id!r} is {task.status.value}, not pending"
            )
        if task.blocked_by:
            raise MissionControlError(f"task {task.id!r} is explicitly blocked")

    @staticmethod
    def _require_ref_shape(ref: OwnerExecutionRef) -> None:
        if ref.backend != OWNER_BACKEND:
            raise MissionControlError("owner execution backend is not supported")
        for label, value in (
            ("mission_id", ref.mission_id),
            ("task_id", ref.task_id),
            ("dispatch_key", ref.dispatch_key),
            ("run_id", ref.run_id),
            ("claim_id", ref.claim_id),
            ("agent_id", ref.agent_id),
            ("idempotency_key", ref.idempotency_key),
            ("owner_session_id", ref.owner_session_id),
        ):
            clean_identifier(value, label)


__all__ = [
    "EXECUTION_METADATA_KEY",
    "EXECUTION_SCHEMA_VERSION",
    "OWNER_BACKEND",
    "OrchestratorMissionAdapter",
    "OwnerExecutionObservation",
    "OwnerExecutionRef",
]
