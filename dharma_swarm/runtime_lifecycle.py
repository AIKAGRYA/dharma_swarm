"""Runtime lifecycle producer helpers for structured runtime records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.models import Task, TaskDispatch, _new_id
from dharma_swarm.runtime_state import ArtifactRecord, DelegationRun, RuntimeReceipt, TaskClaim
from dharma_swarm.runtime_topology import record_subagent_tool_children, record_topology_state
from dharma_swarm.runtime_lifecycle_identity import ensure_execution_identity_for_dispatch
from dharma_swarm.runtime_lifecycle_payloads import mission_payload, route_truth, runtime_metadata
from dharma_swarm.session_ledger import SessionLedger
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

logger = logging.getLogger(__name__)


class RuntimeLifecycle:
    """Centralizes structured runtime producer writes for the orchestrator."""

    def __init__(self, ledger: SessionLedger) -> None:
        self._ledger = ledger

    @staticmethod
    def _task_meta(task: Task | None) -> dict[str, Any]:
        if task is None or not isinstance(task.metadata, dict):
            return {}
        return dict(task.metadata)

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _utc_datetime_from(value: Any, fallback: datetime | None = None) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), timezone.utc)
            except Exception:
                pass
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return fallback or datetime.now(timezone.utc)

    @staticmethod
    def _runtime_status_time(status: str) -> datetime | None:
        if status in {"running", "completed", "failed"}:
            return datetime.now(timezone.utc)
        return None

    def _runtime_state_store(self) -> Any | None:
        return getattr(self._ledger, "_runtime_state", None)

    def ensure_runtime_run_id(self, td: TaskDispatch) -> str:
        existing = str(td.metadata.get("runtime_run_id", "") or "").strip()
        if existing:
            return existing
        run_id = f"run_{_new_id()}"
        td.metadata["runtime_run_id"] = run_id
        return run_id

    def ensure_execution_identity(
        self,
        td: TaskDispatch,
        *,
        task: Task | None = None,
        require: bool = False,
    ) -> ExecutionIdentity:
        return ensure_execution_identity_for_dispatch(
            td,
            task=task,
            task_metadata=self._task_meta(task),
            session_id=self._ledger.session_id,
            ensure_runtime_run_id=self.ensure_runtime_run_id,
            runtime_state_store=self._runtime_state_store(),
            require=require,
        )

    async def record_task_claim(
        self,
        td: TaskDispatch,
        *,
        task: Task | None,
        status: str,
        failure_code: str = "",
        error: str = "",
        require_identity: bool = False,
    ) -> None:
        store = self._runtime_state_store()
        claim_id = str(td.metadata.get("claim_id", "") or "").strip()
        if store is None or not claim_id:
            if require_identity:
                raise MissingExecutionIdentity("RuntimeStateStore and claim_id are required")
            return
        identity = self.ensure_execution_identity(
            td,
            task=task,
            require=require_identity,
        )
        task_meta = self._task_meta(task)
        route_payload = route_truth(
            task_meta,
            td.metadata,
            identity.metadata,
            failure_code=failure_code,
            status=status,
        )
        mission = mission_payload(
            task_meta,
            td.metadata,
            identity.metadata,
            task_id=td.task_id,
            session_id=self._ledger.session_id,
        )
        active_claim = task_meta.get("active_claim")
        if not isinstance(active_claim, dict):
            active_claim = {}
        now = datetime.now(timezone.utc)
        acked_at = self._runtime_status_time(status)
        heartbeat_at = now if status in {"running", "completed", "failed"} else None
        stale_after = None
        if active_claim.get("claim_expires_at_epoch") is not None:
            stale_after = self._utc_datetime_from(active_claim.get("claim_expires_at_epoch"))
        claim = TaskClaim(
            claim_id=claim_id,
            task_id=td.task_id,
            agent_id=td.agent_id,
            status=status,
            session_id=self._ledger.session_id,
            claimed_at=self._utc_datetime_from(active_claim.get("claimed_at"), now),
            acked_at=acked_at,
            heartbeat_at=heartbeat_at,
            stale_after=stale_after,
            retry_count=max(0, self._coerce_int(td.metadata.get("retry_count"), 0)),
            metadata=runtime_metadata(
                td,
                status=status,
                failure_code=failure_code,
                error=error,
            )
            | route_payload
            | mission
            | identity.to_metadata()
            | {
                "trace_id": identity.trace_id,
                "correlation_id": identity.correlation_id,
                "run_id": identity.run_id,
                "idempotency_key": identity.idempotency_key,
            },
        )
        try:
            side_effect_key = f"task_claim:{identity.claim_id}:{status}"
            receipt_id = f"rr_{identity.run_id}_{status}_claim"
            receipt_payload = {
                "claim_id": identity.claim_id,
                "failure_code": failure_code,
                **({"attempt_generation": td.metadata["attempt_generation"]}
                   if "attempt_generation" in td.metadata else {}),
                **mission,
                "receipt_status": status,
                **route_payload,
            }
            await store.record_execution_identity(
                identity,
                source="runtime_lifecycle.record_task_claim",
            )
            inserted = await store.try_begin_idempotent_side_effect(
                identity,
                side_effect_key,
                metadata=receipt_payload,
            )
            await store.record_task_claim(claim)
            await store.record_runtime_receipt(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="task_claim",
                    status=status,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=side_effect_key,
                    payload=receipt_payload,
                )
            )
            if inserted:
                await store.complete_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt_id,
                    metadata=receipt_payload,
                )
        except Exception:
            if require_identity:
                raise
            logger.debug("Runtime task claim recording failed", exc_info=True)

    async def record_delegation_run(
        self,
        td: TaskDispatch,
        *,
        task: Task | None,
        status: str,
        failure_code: str = "",
        error: str = "",
        result: str | None = None,
        require_identity: bool = False,
    ) -> None:
        store = self._runtime_state_store()
        if store is None:
            if require_identity:
                raise MissingExecutionIdentity("RuntimeStateStore is required")
            return
        identity = self.ensure_execution_identity(
            td,
            task=task,
            require=require_identity,
        )
        run_id = identity.run_id
        started_raw = td.metadata.get("runtime_run_started_at")
        started_at = self._utc_datetime_from(started_raw)
        if not started_raw:
            td.metadata["runtime_run_started_at"] = started_at.isoformat()
        task_meta = self._task_meta(task)
        route_payload = route_truth(
            task_meta,
            td.metadata,
            identity.metadata,
            failure_code=failure_code,
            status=status,
        )
        requested_output = task_meta.get("requested_output", [])
        if not isinstance(requested_output, list):
            requested_output = []
        current_artifact_id = str(task_meta.get("current_artifact_id", "") or "")
        mission = mission_payload(
            task_meta,
            td.metadata,
            identity.metadata,
            task_id=td.task_id,
            session_id=self._ledger.session_id,
        )
        artifact_refs = (
            [f"artifact_records:{current_artifact_id}"]
            if current_artifact_id
            else []
        )
        completed_at = datetime.now(timezone.utc) if status in {"completed", "failed"} else None
        run = DelegationRun(
            run_id=run_id,
            task_id=td.task_id,
            assigned_to=td.agent_id,
            status=status,
            session_id=self._ledger.session_id,
            claim_id=str(td.metadata.get("claim_id", "") or ""),
            parent_run_id=str(task_meta.get("parent_run_id", "") or ""),
            assigned_by="orchestrator",
            requested_output=[str(item) for item in requested_output],
            current_artifact_id=current_artifact_id,
            started_at=started_at,
            completed_at=completed_at,
            failure_code=failure_code,
            metadata=runtime_metadata(
                td,
                status=status,
                failure_code=failure_code,
                error=error,
                result=result,
            )
            | route_payload
            | mission
            | identity.to_metadata()
            | {
                "trace_id": identity.trace_id,
                "correlation_id": identity.correlation_id,
                "idempotency_key": identity.idempotency_key,
            },
        )
        try:
            side_effect_key = f"delegation_run:{identity.run_id}:{status}"
            receipt_id = f"rr_{identity.run_id}_{status}_run"
            receipt_payload = {
                "failure_code": failure_code,
                "result_chars": len(result or ""),
                **({"attempt_generation": td.metadata["attempt_generation"]}
                   if "attempt_generation" in td.metadata else {}),
                **mission,
                "artifact_refs": artifact_refs,
                "no_artifact_refs_reason": ""
                if artifact_refs
                else "delegation_run has no current_artifact_id",
                "receipt_status": status,
                **route_payload,
            }
            await store.record_execution_identity(
                identity,
                source="runtime_lifecycle.record_delegation_run",
            )
            inserted = await store.try_begin_idempotent_side_effect(
                identity,
                side_effect_key,
                metadata=receipt_payload,
            )
            await store.record_delegation_run(run)
            await record_subagent_tool_children(
                store=store,
                identity=identity,
                td=td,
                session_id=self._ledger.session_id,
                status=status,
                started_at=started_at,
                mission=mission,
                route_payload=route_payload,
            )
            await record_topology_state(
                store=store,
                identity=identity,
                td=td,
                task_meta=task_meta,
                session_id=self._ledger.session_id,
                status=status,
            )
            await store.record_runtime_receipt(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="delegation_run",
                    status=status,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=side_effect_key,
                    payload=receipt_payload,
                )
            )
            if inserted:
                await store.complete_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt_id,
                    metadata=receipt_payload,
                )
            if identity.parent_run_id and status in {"queued", "claimed", "running"}:
                await store.record_receipt_for_identity(
                    identity,
                    receipt_id=f"rr_{identity.parent_run_id}_{identity.run_id}_child_spawned",
                    receipt_type="child_spawned",
                    status=status,
                    side_effect_key=f"child:{identity.parent_run_id}:{identity.run_id}",
                    payload={
                        "child_run_id": identity.run_id,
                        "parent_run_id": identity.parent_run_id,
                        "assigned_to": identity.agent_id,
                    },
                )
            if identity.parent_run_id and status in {"completed", "failed"}:
                await store.record_receipt_for_identity(
                    identity,
                    receipt_id=f"rr_{identity.parent_run_id}_{identity.run_id}_child_completed_{status}",
                    receipt_type="child_completed",
                    status=status,
                    side_effect_key=f"child:{identity.parent_run_id}:{identity.run_id}",
                    payload={
                        "child_run_id": identity.run_id,
                        "parent_run_id": identity.parent_run_id,
                        "failure_code": failure_code,
                        "result_chars": len(result or ""),
                    },
                )
        except Exception:
            if require_identity:
                raise
            logger.debug("Runtime delegation run recording failed", exc_info=True)

    async def record_artifact(
        self,
        *,
        task: Task,
        artifact_id: str,
        artifact_kind: str,
        payload_path: Path,
        checksum: str,
        manifest_path: Path | None = None,
        run_id: str = "",
        metadata: dict[str, Any] | None = None,
        require_identity: bool = False,
    ) -> None:
        store = self._runtime_state_store()
        if store is None:
            if require_identity:
                raise MissingExecutionIdentity("RuntimeStateStore is required")
            return
        artifact_metadata = {
            **self._task_meta(task),
            **dict(metadata or {}),
        }
        mission = mission_payload(
            artifact_metadata,
            {},
            {},
            task_id=task.id,
            session_id=self._ledger.session_id,
        )
        route_payload = route_truth(artifact_metadata, {}, {})
        identity = ExecutionIdentity.from_metadata(
            artifact_metadata,
            task_id=task.id,
            session_id=self._ledger.session_id,
            require=require_identity,
        )
        if identity is None:
            if require_identity:
                raise MissingExecutionIdentity("ExecutionIdentity is required for artifact")
            trace_id = str(artifact_metadata.get("trace_id") or "")
            correlation_id = str(artifact_metadata.get("correlation_id") or trace_id)
        else:
            trace_id = identity.trace_id
            correlation_id = identity.correlation_id
            run_id = run_id or identity.run_id
        artifact = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            session_id=self._ledger.session_id,
            task_id=task.id,
            run_id=run_id,
            trace_id=trace_id,
            manifest_path=str(manifest_path or ""),
            payload_path=str(payload_path),
            checksum=checksum,
            promotion_state="ephemeral",
            metadata={
                "source": "orchestrator._persist_result",
                "task_title": task.title,
                "trace_id": trace_id,
                "correlation_id": correlation_id,
                **dict(metadata or {}),
            },
        )
        try:
            await store.record_artifact(artifact)
            if identity is not None:
                artifact_payload = {
                    "artifact_id": artifact_id,
                    "artifact_kind": artifact_kind,
                    "artifact_refs": [f"artifact_records:{artifact_id}"],
                    **mission,
                    "payload_path": str(payload_path),
                    "manifest_path": str(manifest_path or ""),
                    **route_payload,
                }
                await store.record_runtime_receipt(
                    RuntimeReceipt(
                        receipt_id=f"rr_{identity.run_id}_{artifact_id}_artifact",
                        receipt_type="artifact",
                        status="completed",
                        run_id=identity.run_id,
                        task_id=identity.task_id,
                        trace_id=identity.trace_id,
                        correlation_id=identity.correlation_id,
                        causation_id=identity.causation_id,
                        parent_run_id=identity.parent_run_id,
                        agent_id=identity.agent_id,
                        idempotency_key=identity.idempotency_key,
                        side_effect_key=f"artifact:{artifact_id}",
                        payload=artifact_payload,
                    )
                )
                await store.record_receipt_for_identity(
                    identity.with_updates(artifact_id=artifact_id),
                    receipt_id=f"rr_{identity.run_id}_{artifact_id}_artifact_written",
                    receipt_type="artifact_written",
                    status="completed",
                    side_effect_key=f"artifact:{artifact_id}",
                    payload=artifact_payload,
                )
        except Exception:
            if require_identity:
                raise
            logger.debug("Runtime artifact recording failed", exc_info=True)
