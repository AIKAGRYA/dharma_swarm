"""A2A → Runtime Truth Spine adapter — the one blessed A2A submit path.

Every production A2A submit surface (bridge ingest, node_gateway HTTP
endpoints, a2a_client local delegation, NATS ingress) dispatches through
:func:`submit_task_via_spine`, which wraps ``A2AServer.submit()`` inside
an ``invoke_agent()`` invoker closure and emits exactly one
``EvidenceReceipt`` per dispatch.

This module exists so the adapter has a single owner while
``a2a_bridge.py`` stays within the 500-line module budget. It is an A2A
package module, not a spine sub-module (the spine package owns only
invoke/receipt/routing/persistence — spine-adoption track non-goal).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timezone
from typing import Any

from dharma_swarm.a2a.a2a_server import (
    A2AServer,
    A2ATask,
    A2ATaskStatus,
    _inherit_trace_id,
)
from dharma_swarm.spine.invoke import invoke_agent
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision


async def submit_task_via_spine(
    server: A2AServer,
    task: A2ATask,
    *,
    router_name: str = "a2a_bridge",
) -> tuple[A2ATask, EvidenceReceipt]:
    """Submit an A2A task through the Runtime Truth Spine.

    Dispatches via ``invoke_agent()`` and produces exactly one
    ``EvidenceReceipt``. The ``A2AServer.submit()`` path is called inside
    the invoker so identity, idempotency, task-log, and ``RuntimeReceipt``
    handling are preserved unchanged.

    Token/cost fields are left ``None`` because A2A dispatch does not yet
    carry provider-level token counts. Receipt persistence: the A2A
    surface persists canonically via RuntimeReceipt + IdempotencyRecord
    and intentionally leaves ``delegation_runs.receipt_json`` empty (see
    ``dharma_swarm/spine/persistence.py`` surface split).

    Returns:
        ``(result_task, evidence_receipt)``
    """
    # Preserve the legacy submit() trace contract: an empty trace_id is
    # filled from CorrelationContext (or a fresh trc_*) BEFORE identity
    # creation, exactly as A2AServer.submit() does at its own top.
    if not task.trace_id:
        task.trace_id = _inherit_trace_id()

    identity = server._ensure_execution_identity(task)
    _proposal_id = str(
        (task.metadata or {}).get("proposal_id")
        or identity.proposal_id
        or ""
    )

    routing = RoutingDecision(
        agent_id=task.to_agent,
        provider="a2a",
        model="",
        reason=f"A2A capability dispatch: {task.capability}",
        router_name=router_name,
        context_id=task.context_id or "",
        task_id=identity.task_id,
    )

    started = datetime.now(timezone.utc)
    a2a_task = task  # capture for closure; inner 'task' is the dict

    async def _a2a_invoker(
        task: dict[str, Any],
        agent_id: str,
        context_id: str,
        routing: RoutingDecision,
    ) -> EvidenceReceipt:
        try:
            result = server.submit(a2a_task)
        except Exception as exc:
            finished = datetime.now(timezone.utc)
            return EvidenceReceipt(
                trace_id=identity.trace_id,
                span_id=identity.run_id,
                parent_span_id=identity.parent_run_id or None,
                context_id=context_id,
                task_id=identity.task_id,
                claim_id=identity.claim_id or None,
                agent_id=agent_id,
                provider="a2a",
                operation="invoke_agent",
                provider_attempted=False,
                status="failed",
                error_source="internal_error",
                error_detail=str(exc),
                started_at=started,
                finished_at=finished,
                latency_ms=int((finished - started).total_seconds() * 1000),
                routing_decision_id=routing.decision_id,
                attributes={
                    "correlation_id": identity.correlation_id,
                    "proposal_id": _proposal_id,
                },
            )

        finished = datetime.now(timezone.utc)
        latency_ms = int((finished - started).total_seconds() * 1000)

        if result.status == A2ATaskStatus.COMPLETED:
            r_status, r_error = "ok", "none"
        elif result.status == A2ATaskStatus.FAILED:
            r_status = "failed"
            r_error = "provider_failed" if result.error else "internal_error"
        elif result.status == A2ATaskStatus.CANCELLED:
            r_status, r_error = "cancelled", "cancelled"
        elif result.status == A2ATaskStatus.REJECTED:
            r_status, r_error = "dropped", "guardrail_blocked"
        else:
            r_status, r_error = "ok", "none"

        return EvidenceReceipt(
            trace_id=identity.trace_id,
            span_id=identity.run_id,
            parent_span_id=identity.parent_run_id or None,
            context_id=context_id,
            task_id=identity.task_id,
            claim_id=identity.claim_id or None,
            agent_id=agent_id,
            provider="a2a",
            operation="invoke_agent",
            provider_attempted=True,
            status=r_status,
            error_source=r_error,
            error_detail=result.error if result.error else None,
            started_at=started,
            finished_at=finished,
            latency_ms=latency_ms,
            routing_decision_id=routing.decision_id,
            attributes={
                "a2a_task_id": result.id,
                "context_id": result.context_id or "",
                "capability": result.capability or "",
                "a2a_status": result.status.value,
                "correlation_id": identity.correlation_id,
                "proposal_id": _proposal_id,
            },
        )

    receipt = await invoke_agent(
        task={
            "id": identity.task_id,
            "to_agent": task.to_agent,
            "capability": task.capability,
        },
        agent_id=task.to_agent,
        context_id=task.context_id or "",
        routing=routing,
        invoker=_a2a_invoker,
    )

    result_task = server.get_task(task.id) or task
    if receipt.status != "ok" and result_task.status not in A2ATaskStatus.terminal_states():
        result_task.status = A2ATaskStatus.FAILED
        result_task.error = receipt.error_detail or f"invoke_agent ended {receipt.status}"
        result_task.updated_at = datetime.now(timezone.utc).isoformat()
    return result_task, receipt


def submit_task_via_spine_sync(
    server: A2AServer,
    task: A2ATask,
    *,
    router_name: str = "a2a_bridge",
) -> tuple[A2ATask, EvidenceReceipt]:
    """Run :func:`submit_task_via_spine` from a synchronous caller.

    Uses ``asyncio.run()`` when no event loop is running. If called from
    within a running loop (a sync method invoked inside async code), the
    coroutine executes on a dedicated worker thread with its own loop so
    the running loop is never blocked on itself.
    """
    coro = submit_task_via_spine(server, task, router_name=router_name)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
