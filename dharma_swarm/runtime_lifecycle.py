"""Runtime lifecycle producer helpers for structured runtime records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.models import Task, TaskDispatch, _new_id
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    DelegationRun,
    RuntimeReceipt,
    TaskClaim,
)
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
    def _first_text(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    @staticmethod
    def _falseish(value: Any) -> bool:
        if value is False:
            return True
        return str(value or "").strip().lower() in {"false", "0", "no"}

    @staticmethod
    def _trueish(value: Any) -> bool:
        if value is True:
            return True
        return str(value or "").strip().lower() in {"true", "1", "yes"}

    def _mission_payload(
        self,
        task_metadata: dict[str, Any],
        dispatch_metadata: dict[str, Any],
        identity_metadata: dict[str, Any],
        *,
        task_id: str,
    ) -> dict[str, str]:
        mission_id = self._first_text(
            task_metadata.get("mission_id"),
            task_metadata.get("missionId"),
            dispatch_metadata.get("mission_id"),
            dispatch_metadata.get("missionId"),
            identity_metadata.get("mission_id"),
            identity_metadata.get("missionId"),
        )
        mission = self._first_text(
            task_metadata.get("mission"),
            dispatch_metadata.get("mission"),
            identity_metadata.get("mission"),
            mission_id,
            self._ledger.session_id,
            task_id,
        )
        return {
            "mission_id": mission_id,
            "mission": mission,
        }

    @classmethod
    def _explicit_no_provider_execution(
        cls,
        task_metadata: dict[str, Any],
        dispatch_metadata: dict[str, Any],
        identity_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        provider_execution_false = any(
            cls._falseish(payload.get("provider_execution"))
            for payload in (task_metadata, dispatch_metadata, identity_metadata)
        )
        if not provider_execution_false:
            return {}
        truth_source = cls._first_text(
            task_metadata.get("provider_model_truth_source"),
            dispatch_metadata.get("provider_model_truth_source"),
            identity_metadata.get("provider_model_truth_source"),
            task_metadata.get("route_truth_source"),
            dispatch_metadata.get("route_truth_source"),
            identity_metadata.get("route_truth_source"),
        )
        applicability = cls._first_text(
            task_metadata.get("provider_model_applicability"),
            dispatch_metadata.get("provider_model_applicability"),
            identity_metadata.get("provider_model_applicability"),
        )
        reason = cls._first_text(
            task_metadata.get("no_provider_model_reason"),
            dispatch_metadata.get("no_provider_model_reason"),
            identity_metadata.get("no_provider_model_reason"),
        )
        if not truth_source or not (applicability or reason):
            return {}
        truth: dict[str, Any] = {
            "provider_execution": False,
            "provider_model_truth_source": truth_source,
        }
        if applicability:
            truth["provider_model_applicability"] = applicability
        if reason:
            truth["no_provider_model_reason"] = reason
        return truth

    @classmethod
    def _explicit_unproven_provider_execution(
        cls,
        task_metadata: dict[str, Any],
        dispatch_metadata: dict[str, Any],
        identity_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        provider_execution_true = any(
            cls._trueish(payload.get("provider_execution"))
            for payload in (task_metadata, dispatch_metadata, identity_metadata)
        )
        if not provider_execution_true:
            return {}
        truth_source = cls._first_text(
            task_metadata.get("provider_model_truth_source"),
            dispatch_metadata.get("provider_model_truth_source"),
            identity_metadata.get("provider_model_truth_source"),
            task_metadata.get("route_truth_source"),
            dispatch_metadata.get("route_truth_source"),
            identity_metadata.get("route_truth_source"),
        )
        if not truth_source:
            return {}
        applicability = cls._first_text(
            task_metadata.get("provider_model_applicability"),
            dispatch_metadata.get("provider_model_applicability"),
            identity_metadata.get("provider_model_applicability"),
            "actual_served_unproven",
        )
        reason = cls._first_text(
            task_metadata.get("provider_model_missing_reason"),
            dispatch_metadata.get("provider_model_missing_reason"),
            identity_metadata.get("provider_model_missing_reason"),
            "provider_execution_completed_without_actual_served_runtime_evidence",
        )
        return {
            "provider_execution": True,
            "provider_model_applicability": applicability,
            "provider_model_truth_source": truth_source,
            "provider_model_missing_reason": reason,
        }

    @staticmethod
    def _failure_no_provider_execution(failure_code: str) -> dict[str, Any]:
        normalized = str(failure_code or "").strip()
        reasons = {
            "dispatch_dropoff": "dispatch_dropoff_before_worker_execution",
            "claim_timeout": "claim_timeout_before_worker_execution",
        }
        reason = reasons.get(normalized)
        if not reason:
            return {}
        return {
            "provider_execution": False,
            "provider_model_applicability": "not_applicable",
            "provider_model_truth_source": (
                f"runtime_lifecycle.{normalized}_no_provider_execution"
            ),
            "no_provider_model_reason": reason,
        }

    @staticmethod
    def _is_terminal_status(status: str) -> bool:
        normalized = str(status or "").strip().lower()
        return bool(normalized) and normalized not in {
            "accepted",
            "assigned",
            "claimed",
            "created",
            "in_progress",
            "pending",
            "queued",
            "running",
            "started",
            "submitted",
        }

    @classmethod
    def _terminal_unproven_provider_execution(
        cls,
        *,
        status: str,
    ) -> dict[str, Any]:
        if not cls._is_terminal_status(status):
            return {}
        return {
            "provider_execution": True,
            "provider_model_applicability": "actual_served_unproven",
            "provider_model_truth_source": "runtime_lifecycle.provider_execution_unproven",
            "provider_model_missing_reason": (
                "terminal_receipt_missing_actual_served_or_no_provider_evidence"
            ),
        }

    @classmethod
    def _pending_provider_execution(
        cls,
        *,
        status: str,
    ) -> dict[str, Any]:
        if cls._is_terminal_status(status):
            return {}
        return {
            "provider_execution": "pending",
            "provider_model_applicability": "pending_execution",
            "provider_model_truth_source": "runtime_lifecycle.provider_execution_pending",
            "provider_model_pending_reason": "worker_execution_not_terminal",
        }

    @staticmethod
    def _has_served_provider_model(route: dict[str, Any]) -> bool:
        provider = any(
            route.get(key)
            for key in (
                "actual_served_provider",
                "served_provider",
                "actual_provider",
                "provider_served",
            )
        )
        model = any(
            route.get(key)
            for key in (
                "actual_served_model",
                "served_model",
                "actual_model",
                "model_served",
            )
        )
        return provider and model

    @classmethod
    def _route_truth(
        cls,
        task_metadata: dict[str, Any],
        dispatch_metadata: dict[str, Any],
        identity_metadata: dict[str, Any],
        *,
        failure_code: str = "",
        status: str = "",
    ) -> dict[str, Any]:
        served_provider = cls._first_text(
            task_metadata.get("actual_served_provider"),
            dispatch_metadata.get("actual_served_provider"),
            identity_metadata.get("actual_served_provider"),
            task_metadata.get("served_provider"),
            dispatch_metadata.get("served_provider"),
            identity_metadata.get("served_provider"),
            task_metadata.get("actual_provider"),
            dispatch_metadata.get("actual_provider"),
            identity_metadata.get("actual_provider"),
            task_metadata.get("provider_served"),
            dispatch_metadata.get("provider_served"),
            identity_metadata.get("provider_served"),
        )
        selected_provider = cls._first_text(
            task_metadata.get("selected_provider"),
            dispatch_metadata.get("selected_provider"),
            identity_metadata.get("selected_provider"),
            task_metadata.get("provider_selected"),
            dispatch_metadata.get("provider_selected"),
        )
        ambiguous_provider = cls._first_text(
            task_metadata.get("provider"),
            dispatch_metadata.get("provider"),
            identity_metadata.get("provider"),
        )
        served_model = cls._first_text(
            task_metadata.get("actual_served_model"),
            dispatch_metadata.get("actual_served_model"),
            identity_metadata.get("actual_served_model"),
            task_metadata.get("served_model"),
            dispatch_metadata.get("served_model"),
            identity_metadata.get("served_model"),
            task_metadata.get("actual_model"),
            dispatch_metadata.get("actual_model"),
            identity_metadata.get("actual_model"),
            task_metadata.get("model_served"),
            dispatch_metadata.get("model_served"),
            identity_metadata.get("model_served"),
        )
        selected_model = cls._first_text(
            task_metadata.get("selected_model"),
            dispatch_metadata.get("selected_model"),
            identity_metadata.get("selected_model"),
            task_metadata.get("model_selected"),
            dispatch_metadata.get("model_selected"),
            task_metadata.get("selected_model_hint"),
            dispatch_metadata.get("selected_model_hint"),
        )
        ambiguous_model = cls._first_text(
            task_metadata.get("model"),
            dispatch_metadata.get("model"),
            identity_metadata.get("model"),
        )
        if not selected_provider and not served_provider:
            selected_provider = ambiguous_provider
        if not selected_model and not served_model:
            selected_model = ambiguous_model
        route: dict[str, Any] = {}
        if served_provider:
            route["actual_served_provider"] = served_provider
            route["served_provider"] = served_provider
            route["provider_served"] = served_provider
            route["provider"] = served_provider
        if selected_provider:
            route["selected_provider"] = selected_provider
            route.setdefault("provider", selected_provider)
        if served_model:
            route["actual_served_model"] = served_model
            route["served_model"] = served_model
            route["model_served"] = served_model
            route["model"] = served_model
        if selected_model:
            route["selected_model"] = selected_model
            route["selected_model_hint"] = selected_model
            route.setdefault("model", selected_model)
        source = cls._first_text(
            task_metadata.get("provider_model_truth_source"),
            dispatch_metadata.get("provider_model_truth_source"),
            identity_metadata.get("provider_model_truth_source"),
            task_metadata.get("route_truth_source"),
            dispatch_metadata.get("route_truth_source"),
            identity_metadata.get("route_truth_source"),
        )
        if route and source:
            route["provider_model_truth_source"] = source
        explicit_applicability = cls._first_text(
            task_metadata.get("provider_model_applicability"),
            dispatch_metadata.get("provider_model_applicability"),
            identity_metadata.get("provider_model_applicability"),
        )
        explicit_missing_reason = cls._first_text(
            task_metadata.get("provider_model_missing_reason"),
            dispatch_metadata.get("provider_model_missing_reason"),
            identity_metadata.get("provider_model_missing_reason"),
        )
        explicit_no_provider = cls._explicit_no_provider_execution(
            task_metadata,
            dispatch_metadata,
            identity_metadata,
        )
        if explicit_no_provider and not cls._has_served_provider_model(route):
            return explicit_no_provider
        failure_no_provider = cls._failure_no_provider_execution(failure_code)
        if failure_no_provider and not cls._has_served_provider_model(route):
            return failure_no_provider
        if route and source and not cls._has_served_provider_model(route):
            if cls._is_terminal_status(status):
                route["provider_execution"] = True
                if explicit_applicability:
                    applicability = explicit_applicability
                elif source == "agent_runner.provider_chain_failure":
                    applicability = "failed_before_serve"
                else:
                    applicability = "actual_served_unproven"
                route["provider_model_applicability"] = applicability
                route["provider_model_truth_source"] = source
                if explicit_missing_reason:
                    reason = explicit_missing_reason
                elif applicability == "failed_before_serve":
                    reason = "provider_chain_failed_before_actual_served_response"
                else:
                    reason = "attempted_route_selected_without_actual_served_runtime_evidence"
                route["provider_model_missing_reason"] = reason
                return route
            route["provider_execution"] = "pending"
            route["provider_model_applicability"] = "pending_execution"
            route["provider_model_truth_source"] = source
            route["provider_model_pending_reason"] = "worker_execution_not_terminal"
            return route
        explicit_unproven_provider = cls._explicit_unproven_provider_execution(
            task_metadata,
            dispatch_metadata,
            identity_metadata,
        )
        if explicit_unproven_provider and not cls._has_served_provider_model(route):
            return explicit_unproven_provider
        pending_provider = cls._pending_provider_execution(status=status)
        if pending_provider and not route:
            return pending_provider
        terminal_unproven_provider = cls._terminal_unproven_provider_execution(
            status=status,
        )
        if terminal_unproven_provider and not route:
            return terminal_unproven_provider
        return route

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
        task_meta = self._task_meta(task)
        nested = task_meta.get("execution_identity")
        merged: dict[str, Any] = {}
        if isinstance(nested, dict):
            merged.update(nested)
        merged.update(task_meta)
        dispatch_nested = td.metadata.get("execution_identity")
        if isinstance(dispatch_nested, dict):
            merged.update(dispatch_nested)
        merged.update(td.metadata)

        run_id = str(
            merged.get("run_id")
            or merged.get("runtime_run_id")
            or self.ensure_runtime_run_id(td)
        ).strip()
        trace_id = str(merged.get("trace_id") or "").strip()
        if not trace_id:
            try:
                from dharma_swarm.correlation_context import get_correlation

                trace_id = get_correlation().trace_id
            except Exception:
                trace_id = ""
        if require and not trace_id:
            raise MissingExecutionIdentity("ExecutionIdentity requires trace_id on this path")
        correlation_id = str(merged.get("correlation_id") or trace_id).strip()
        if require and not correlation_id:
            raise MissingExecutionIdentity("ExecutionIdentity requires correlation_id on this path")
        claim_id = str(merged.get("claim_id") or "").strip()
        if require and not claim_id:
            raise MissingExecutionIdentity("ExecutionIdentity requires claim_id on this path")

        identity = ExecutionIdentity.new(
            task_id=td.task_id,
            agent_id=td.agent_id,
            session_id=self._ledger.session_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_id=str(merged.get("causation_id") or ""),
            parent_run_id=str(merged.get("parent_run_id") or ""),
            run_id=run_id,
            claim_id=claim_id,
            idempotency_key=str(merged.get("idempotency_key") or ""),
            external_a2a_task_id=str(merged.get("external_a2a_task_id") or ""),
            message_id=str(merged.get("message_id") or ""),
            event_id=str(merged.get("event_id") or ""),
            artifact_id=str(merged.get("artifact_id") or ""),
            proposal_id=str(merged.get("proposal_id") or ""),
            metadata={
                "source": "runtime_lifecycle.ensure_execution_identity",
                **dict(merged.get("metadata") or {}),
            },
        )
        td.metadata.update(
            {
                "execution_identity": identity.to_dict(),
                "trace_id": identity.trace_id,
                "correlation_id": identity.correlation_id,
                "runtime_run_id": identity.run_id,
                "run_id": identity.run_id,
                "claim_id": identity.claim_id,
                "agent_id": identity.agent_id,
                "session_id": identity.session_id,
                "idempotency_key": identity.idempotency_key,
            }
        )
        if task is not None:
            task.metadata = {
                **self._task_meta(task),
                "execution_identity": identity.to_dict(),
                "trace_id": identity.trace_id,
                "correlation_id": identity.correlation_id,
                "runtime_run_id": identity.run_id,
                "run_id": identity.run_id,
                "claim_id": identity.claim_id,
                "idempotency_key": identity.idempotency_key,
            }
        store = self._runtime_state_store()
        if store is not None:
            store.record_execution_identity_sync(
                identity,
                source="runtime_lifecycle",
            )
        elif require:
            raise MissingExecutionIdentity("RuntimeStateStore is required on this path")
        return identity.require_for_dispatch()

    def runtime_metadata(
        self,
        td: TaskDispatch,
        *,
        status: str,
        failure_code: str = "",
        error: str = "",
        result: str | None = None,
    ) -> dict[str, Any]:
        metadata = {
            "source": "orchestrator",
            "status": status,
            "topology": td.topology.value if td.topology else "dispatch",
            "timeout_seconds": td.timeout_seconds,
            "retry_count": td.metadata.get("retry_count", 0),
            "max_retries": td.metadata.get("max_retries", 0),
            "claim_timeout_seconds": td.metadata.get("claim_timeout_seconds", 0),
        }
        if failure_code:
            metadata["failure_code"] = failure_code
        if error:
            metadata["error"] = error[:500]
        if result is not None:
            metadata["result_chars"] = len(result or "")
        for key in (
            "context_bundle_id",
            "context_bundle_status",
            "context_bundle_error",
            "runtime_db_path",
        ):
            value = td.metadata.get(key)
            if value:
                metadata[key] = value
        return metadata

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
        route_truth = self._route_truth(
            task_meta,
            td.metadata,
            identity.metadata,
            failure_code=failure_code,
            status=status,
        )
        mission_payload = self._mission_payload(
            task_meta,
            td.metadata,
            identity.metadata,
            task_id=td.task_id,
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
            metadata=self.runtime_metadata(
                td,
                status=status,
                failure_code=failure_code,
                error=error,
            )
            | route_truth
            | mission_payload
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
                **mission_payload,
                "receipt_status": status,
                **route_truth,
            }
            inserted = await store.try_begin_idempotent_side_effect(
                identity,
                side_effect_key,
                metadata=receipt_payload,
            )
            await store.record_task_claim(claim, emit_receipt=False)
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
        route_truth = self._route_truth(
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
        mission_payload = self._mission_payload(
            task_meta,
            td.metadata,
            identity.metadata,
            task_id=td.task_id,
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
            metadata=self.runtime_metadata(
                td,
                status=status,
                failure_code=failure_code,
                error=error,
                result=result,
            )
            | route_truth
            | mission_payload
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
                **mission_payload,
                "artifact_refs": artifact_refs,
                "no_artifact_refs_reason": ""
                if artifact_refs
                else "delegation_run has no current_artifact_id",
                "receipt_status": status,
                **route_truth,
            }
            inserted = await store.try_begin_idempotent_side_effect(
                identity,
                side_effect_key,
                metadata=receipt_payload,
            )
            await store.record_delegation_run(run, emit_receipt=False)
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
        mission_id = self._first_text(
            artifact_metadata.get("mission_id"),
            artifact_metadata.get("mission"),
        )
        route_truth = self._route_truth(artifact_metadata, {}, {})
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
                    "mission_id": mission_id,
                    "payload_path": str(payload_path),
                    "manifest_path": str(manifest_path or ""),
                    **route_truth,
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
