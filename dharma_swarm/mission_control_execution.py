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
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

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
from dharma_swarm.mission_control_evidence import (
    EVIDENCE_DELTA_RECEIPT_TYPE,
    EvidenceDelta,
)
from dharma_swarm.mission_control_execution_support import (
    EXECUTION_METADATA_KEY as EXECUTION_METADATA_KEY,
    EXECUTION_SCHEMA_VERSION as EXECUTION_SCHEMA_VERSION,
    OWNER_BACKEND as OWNER_BACKEND,
    OWNER_CLAIM_STATUSES as OWNER_CLAIM_STATUSES,
    OWNER_RUN_STATUSES as OWNER_RUN_STATUSES,
    OWNER_TERMINAL_STATUSES as OWNER_TERMINAL_STATUSES,
    _OwnerExecutionValidationMixin,
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


class OrchestratorMissionAdapter(_OwnerExecutionValidationMixin):
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

    async def recover(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> OwnerExecutionRef | None:
        """Recover an already stamped owner execution without dispatching."""
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        dispatch_key = clean_identifier(dispatch_key, "dispatch_key")
        task = await self._require_task(mission_id, task_id)
        marker = task.metadata.get(EXECUTION_METADATA_KEY)
        if marker is None:
            return None
        if not isinstance(marker, dict):
            raise MissionControlError("owner execution metadata has an invalid shape")
        expected = self._expected_identity(mission_id, task_id, dispatch_key)
        self._require_stamp(task, mission_id, dispatch_key, expected)
        return await self._recover_owner_ref(
            mission_id,
            task_id,
            dispatch_key,
            expected_run_id=expected["run_id"],
            expected_idempotency_key=expected["idempotency_key"],
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

    async def renew_with_evidence(
        self,
        ref: OwnerExecutionRef,
        delta: EvidenceDelta,
        *,
        lease_seconds: float = 300.0,
        max_evidence_age_seconds: float = 300.0,
    ) -> TaskClaim:
        """Renew only the exact live claim generation cited by new evidence."""
        if lease_seconds <= 0 or max_evidence_age_seconds <= 0:
            raise ValueError("evidence renewal budgets must be positive")
        if not isinstance(delta, EvidenceDelta):
            raise MissionControlError("typed EvidenceDelta is required")
        observation = await self.observe(ref)
        if observation.terminal:
            raise MissionControlError("terminal owner execution cannot be renewed")
        if observation.stale:
            raise MissionControlError("stale owner claim cannot be renewed")
        if (
            delta.mission_id,
            delta.task_id,
            delta.run_id,
            delta.claim_id,
            delta.agent_id,
        ) != (
            ref.mission_id,
            ref.task_id,
            ref.run_id,
            ref.claim_id,
            ref.agent_id,
        ):
            raise MissionControlError("evidence delta names a foreign owner execution")

        claim = await self._runtime.get_task_claim(ref.claim_id)
        if claim is None:
            raise MissionControlError("owner claim was not found")
        evidence_state = claim.metadata.get("mission_control_evidence", {})
        if not isinstance(evidence_state, dict):
            raise MissionControlError("claim evidence state has a foreign shape")
        last_sequence = evidence_state.get("last_sequence", 0)
        if isinstance(last_sequence, bool) or not isinstance(last_sequence, int):
            raise MissionControlError("claim evidence sequence has a foreign shape")
        now = utc_now()
        delta.require_fresh(
            now=now,
            last_sequence=last_sequence,
            max_age=timedelta(seconds=max_evidence_age_seconds),
        )
        consumed_artifacts = self._consumed_evidence_ids(
            evidence_state,
            "consumed_artifact_ids",
            fallback_key="artifact_ids",
        )
        consumed_receipts = self._consumed_evidence_ids(
            evidence_state,
            "consumed_receipt_ids",
            fallback_key="receipt_ids",
        )
        if consumed_artifacts.intersection(delta.artifact_ids) or (
            consumed_receipts.intersection(delta.receipt_ids)
        ):
            raise MissionControlError("evidence delta reuses already consumed evidence")
        await self._require_evidence_refs(
            delta,
            ref,
            not_before=claim.heartbeat_at or claim.claimed_at,
        )
        if claim.heartbeat_at is not None and delta.observed_at <= claim.heartbeat_at:
            raise MissionControlError("evidence heartbeat does not advance monotonically")
        new_expiry = delta.observed_at + timedelta(seconds=lease_seconds)
        if new_expiry <= now:
            raise MissionControlError("evidence delta cannot create an expired renewal")
        replacement = replace(
            claim,
            heartbeat_at=delta.observed_at,
            stale_after=new_expiry,
            metadata={
                **claim.metadata,
                "mission_control_evidence": {
                    "last_sequence": delta.sequence,
                    "last_delta_id": delta.delta_id,
                    "last_observed_at": delta.observed_at.isoformat(),
                    "artifact_ids": list(delta.artifact_ids),
                    "receipt_ids": list(delta.receipt_ids),
                    "consumed_artifact_ids": sorted(
                        consumed_artifacts.union(delta.artifact_ids)
                    ),
                    "consumed_receipt_ids": sorted(
                        consumed_receipts.union(delta.receipt_ids)
                    ),
                },
            },
        )
        identity = await self._runtime.get_execution_identity(ref.run_id)
        if identity is None:
            raise MissionControlError("owner execution identity disappeared before renewal")
        evidence_receipt = RuntimeReceipt(
            receipt_id=stable_id("evidence_delta_receipt", delta.delta_id),
            receipt_type=EVIDENCE_DELTA_RECEIPT_TYPE,
            status="recorded",
            run_id=ref.run_id,
            task_id=ref.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=ref.agent_id,
            idempotency_key=ref.idempotency_key,
            side_effect_key=f"mission_evidence:{delta.delta_id}",
            payload={"mission_id": ref.mission_id, **delta.to_payload()},
            created_at=delta.observed_at,
        )
        renewed = await self._runtime.compare_and_swap_task_claim(
            claim,
            replacement,
            require_unexpired_at=now,
            require_open_run_id=ref.run_id,
            atomic_receipt=evidence_receipt,
        )
        if renewed is None:
            raise MissionControlError("owner claim fence changed during evidence renewal")
        return renewed

    async def _require_evidence_refs(
        self,
        delta: EvidenceDelta,
        ref: OwnerExecutionRef,
        *,
        not_before: datetime,
    ) -> None:
        receipts = await self._runtime.list_runtime_receipts(
            run_id=ref.run_id,
            limit=self._scan_limit,
        )
        if len(receipts) >= self._scan_limit:
            raise MissionControlError(
                "runtime receipt scan saturated; evidence cannot be proven"
            )
        indexed = {receipt.receipt_id: receipt for receipt in receipts}
        for receipt_id in delta.receipt_ids:
            receipt = indexed.get(receipt_id)
            if receipt is None:
                raise MissionControlError("evidence delta cites a missing runtime receipt")
            if receipt.task_id != ref.task_id:
                raise MissionControlError("evidence delta cites a foreign task receipt")
            if receipt.agent_id != ref.agent_id:
                raise MissionControlError("evidence delta cites a foreign agent receipt")
            if not not_before < receipt.created_at <= delta.observed_at:
                raise MissionControlError("evidence delta receipt is not fresh")
        for artifact_id in delta.artifact_ids:
            artifact = await self._runtime.get_artifact(artifact_id)
            if artifact is None:
                raise MissionControlError("evidence delta cites a missing artifact")
            if artifact.run_id != ref.run_id or artifact.task_id != ref.task_id:
                raise MissionControlError("evidence delta cites a foreign artifact")
            if not not_before < artifact.created_at <= delta.observed_at:
                raise MissionControlError("evidence delta artifact is not fresh")

    @staticmethod
    def _consumed_evidence_ids(
        evidence_state: dict[str, object],
        key: str,
        *,
        fallback_key: str,
    ) -> set[str]:
        raw = evidence_state.get(key, evidence_state.get(fallback_key, ()))
        if not isinstance(raw, (list, tuple)) or any(
            not isinstance(item, str) or not item for item in raw
        ):
            raise MissionControlError("claim consumed evidence state has a foreign shape")
        if len(set(raw)) != len(raw):
            raise MissionControlError("claim consumed evidence state contains duplicates")
        return set(raw)

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
