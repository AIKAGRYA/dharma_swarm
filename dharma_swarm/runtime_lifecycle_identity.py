"""Execution identity helper for RuntimeLifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dharma_swarm.models import Task, TaskDispatch
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


def ensure_execution_identity_for_dispatch(
    td: TaskDispatch,
    *,
    task: Task | None,
    task_metadata: dict[str, Any],
    session_id: str,
    ensure_runtime_run_id: Callable[[TaskDispatch], str],
    runtime_state_store: Any | None,
    require: bool = False,
) -> ExecutionIdentity:
    nested = task_metadata.get("execution_identity")
    merged: dict[str, Any] = {}
    if isinstance(nested, dict):
        merged.update(nested)
    merged.update(task_metadata)
    dispatch_nested = td.metadata.get("execution_identity")
    if isinstance(dispatch_nested, dict):
        merged.update(dispatch_nested)
    merged.update(td.metadata)

    run_id = str(
        merged.get("run_id")
        or merged.get("runtime_run_id")
        or ensure_runtime_run_id(td)
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
        session_id=session_id,
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
    td.metadata.update(_identity_metadata(identity))
    if task is not None:
        task.metadata = {**task_metadata, **_identity_metadata(identity)}
    if runtime_state_store is None and require:
        raise MissingExecutionIdentity("RuntimeStateStore is required on this path")
    return identity.require_for_dispatch()


def _identity_metadata(identity: ExecutionIdentity) -> dict[str, Any]:
    return {
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
