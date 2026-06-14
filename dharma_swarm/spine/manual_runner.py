"""Spine wrapper for manual AgentRunner integration scripts."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from dharma_swarm.models import Task
from dharma_swarm.spine.invoke import invoke_agent
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision


def _runtime_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _runner_provider_model(runner: Any) -> tuple[str, str]:
    config = getattr(runner, "_config", None)
    state = getattr(runner, "state", None)
    provider = getattr(config, "provider", None) or getattr(state, "provider", "")
    model = getattr(config, "model", None) or getattr(state, "model", "")
    return _runtime_value(provider), _runtime_value(model)


async def run_manual_agent_runner_via_spine(
    runner: Any,
    task: Task,
    *,
    surface: str,
    agent_name: str = "",
    timeout_seconds: float | None = None,
) -> tuple[Any, EvidenceReceipt]:
    """Run a manual integration-script AgentRunner call through invoke_agent.

    This emits one in-memory ``EvidenceReceipt`` for operator/manual scripts
    without creating a second durable receipt store. Production dispatch
    persistence remains owned by orchestrator/A2A runtime paths.
    """
    state = getattr(runner, "state", None)
    resolved_agent_name = agent_name or str(getattr(state, "name", "") or "")
    agent_id = str(
        getattr(state, "id", "")
        or getattr(runner, "agent_id", "")
        or resolved_agent_name
        or "manual-agent-runner"
    )
    provider, model = _runner_provider_model(runner)
    metadata = dict(task.metadata or {})
    context_id = str(
        metadata.get("session_id")
        or metadata.get("context_id")
        or metadata.get("run_id")
        or surface
    )
    trace_id = str(
        metadata.get("trace_id")
        or metadata.get("correlation_id")
        or metadata.get("run_id")
        or task.id
    )
    routing = RoutingDecision(
        agent_id=agent_id,
        provider=provider,
        model=model,
        reason=f"manual AgentRunner integration script: {surface}",
        router_name="manual_agent_runner_script",
        context_id=context_id,
        task_id=task.id,
        attributes={"surface": surface, "agent_name": resolved_agent_name},
    )
    started = datetime.now(timezone.utc)
    captured: dict[str, Any] = {}

    async def _manual_invoker(
        task: dict[str, Any],
        agent_id: str,
        context_id: str,
        routing: RoutingDecision,
    ) -> EvidenceReceipt:
        status, err_source, err_detail = "ok", "none", None
        try:
            if timeout_seconds is None:
                captured["result"] = await runner.run_task(captured["_task_obj"])
            else:
                captured["result"] = await asyncio.wait_for(
                    runner.run_task(captured["_task_obj"]),
                    timeout=timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            captured["exc"] = exc
            status, err_source, err_detail = "timeout", "timeout", "run_task timed out"
        except Exception as exc:  # noqa: BLE001 - re-raised after receipt emission
            captured["exc"] = exc
            status, err_source, err_detail = "failed", "internal_error", str(exc)
        finished = datetime.now(timezone.utc)
        return EvidenceReceipt(
            trace_id=trace_id,
            context_id=context_id,
            task_id=task["id"],
            agent_id=agent_id,
            provider=provider or f"manual:{surface}",
            model=model,
            operation="invoke_agent",
            provider_attempted=True,
            status=status,
            error_source=err_source,
            error_detail=err_detail,
            started_at=started,
            finished_at=finished,
            latency_ms=int((finished - started).total_seconds() * 1000),
            routing_decision_id=routing.decision_id,
            attributes={
                "router": "manual_agent_runner_script",
                "surface": surface,
                "agent_name": resolved_agent_name,
            },
        )

    captured["_task_obj"] = task
    receipt = await invoke_agent(
        task={"id": task.id, "title": task.title, "surface": surface},
        agent_id=agent_id,
        context_id=context_id,
        routing=routing,
        invoker=_manual_invoker,
    )
    task.metadata["evidence_receipt_id"] = str(receipt.receipt_id)
    if "exc" in captured:
        raise captured["exc"]
    return captured.get("result"), receipt
