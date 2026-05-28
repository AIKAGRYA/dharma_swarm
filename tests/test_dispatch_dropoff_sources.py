"""Runtime Truth Spine — dispatch dropoff source tests (doctrine §11 PR 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from dharma_swarm.spine.receipt import EvidenceReceipt, ErrorSource, ReceiptStatus
from dharma_swarm.spine.routing import RoutingDecision
from dharma_swarm.spine.invoke import invoke_agent, AgentInvoker



def _make_routing() -> RoutingDecision:
    return RoutingDecision(
        agent_id="agent-001",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        reason="cheapest healthy provider for tier=fast",
        router_name="provider_policy",
        context_id="ctx-abc",
        task_id="task-123",
    )


async def _invoker_ok(
    task: dict, agent_id: str, context_id: str, routing: RoutingDecision,
) -> EvidenceReceipt:
    return EvidenceReceipt(
        status="ok", error_source="none",
        task_id=task.get("id", ""), agent_id=agent_id, context_id=context_id,
        provider=routing.provider, model=routing.model,
        provider_attempted=True, routing_decision_id=routing.decision_id,
        input_tokens=150, output_tokens=300,
        finished_at=datetime.now(timezone.utc), latency_ms=420,
    )


async def _invoker_task_missing(
    task: dict, agent_id: str, context_id: str, routing: RoutingDecision,
) -> EvidenceReceipt:
    return EvidenceReceipt(
        status="dropped", error_source="task_missing",
        task_id=task.get("id", ""), agent_id=agent_id, context_id=context_id,
        provider_attempted=False, routing_decision_id=routing.decision_id,
        error_detail="Task not found in board after routing decision",
    )


async def _invoker_runner_missing(
    task: dict, agent_id: str, context_id: str, routing: RoutingDecision,
) -> EvidenceReceipt:
    return EvidenceReceipt(
        status="dropped", error_source="runner_missing",
        task_id=task.get("id", ""), agent_id=agent_id, context_id=context_id,
        provider_attempted=False, routing_decision_id=routing.decision_id,
        error_detail="AgentPool.get(agent_id) returned None",
    )


async def _invoker_both_missing(
    task: dict, agent_id: str, context_id: str, routing: RoutingDecision,
) -> EvidenceReceipt:
    return EvidenceReceipt(
        status="dropped", error_source="task_and_runner_missing",
        task_id=task.get("id", ""), agent_id=agent_id, context_id=context_id,
        provider_attempted=False, routing_decision_id=routing.decision_id,
    )


async def _invoker_provider_failed(
    task: dict, agent_id: str, context_id: str, routing: RoutingDecision,
) -> EvidenceReceipt:
    return EvidenceReceipt(
        status="failed", error_source="provider_failed",
        task_id=task.get("id", ""), agent_id=agent_id, context_id=context_id,
        provider=routing.provider, model=routing.model,
        provider_attempted=True, routing_decision_id=routing.decision_id,
        error_detail="API returned 429 rate_limit_exceeded",
        finished_at=datetime.now(timezone.utc), latency_ms=85,
    )


@pytest.mark.asyncio
async def test_normal_execution_emits_success_receipt():
    routing = _make_routing()
    task = {"id": "task-123", "title": "test task"}

    receipt = await invoke_agent(
        task=task,
        agent_id="agent-001",
        context_id="ctx-abc",
        routing=routing,
        invoker=_invoker_ok,
    )

    assert receipt.status == "ok"
    assert receipt.error_source == "none"
    assert receipt.provider_attempted is True
    assert receipt.task_id == "task-123"
    assert receipt.agent_id == "agent-001"
    assert receipt.context_id == "ctx-abc"
    assert receipt.input_tokens == 150
    assert receipt.output_tokens == 300
    assert receipt.routing_decision_id == routing.decision_id


@pytest.mark.asyncio
async def test_task_missing_emits_precise_receipt():
    routing = _make_routing()
    task = {"id": "task-456"}

    receipt = await invoke_agent(
        task=task,
        agent_id="agent-001",
        context_id="ctx-abc",
        routing=routing,
        invoker=_invoker_task_missing,
    )

    assert receipt.status == "dropped"
    assert receipt.error_source == "task_missing"
    assert receipt.provider_attempted is False
    assert "not found" in (receipt.error_detail or "").lower()


@pytest.mark.asyncio
async def test_runner_missing_emits_precise_receipt():
    routing = _make_routing()
    task = {"id": "task-789"}

    receipt = await invoke_agent(
        task=task,
        agent_id="agent-001",
        context_id="ctx-abc",
        routing=routing,
        invoker=_invoker_runner_missing,
    )

    assert receipt.status == "dropped"
    assert receipt.error_source == "runner_missing"
    assert receipt.provider_attempted is False


@pytest.mark.asyncio
async def test_both_missing_emits_combined_receipt():
    routing = _make_routing()
    task = {"id": "task-000"}

    receipt = await invoke_agent(
        task=task,
        agent_id="agent-001",
        context_id="ctx-abc",
        routing=routing,
        invoker=_invoker_both_missing,
    )

    assert receipt.status == "dropped"
    assert receipt.error_source == "task_and_runner_missing"
    assert receipt.provider_attempted is False


@pytest.mark.asyncio
async def test_provider_failure_not_confused_with_dropoff():
    routing = _make_routing()
    task = {"id": "task-fail"}

    receipt = await invoke_agent(
        task=task,
        agent_id="agent-001",
        context_id="ctx-abc",
        routing=routing,
        invoker=_invoker_provider_failed,
    )

    # CRITICAL: provider failure has provider_attempted=True
    # dispatch dropoff has provider_attempted=False
    assert receipt.status == "failed"
    assert receipt.error_source == "provider_failed"
    assert receipt.provider_attempted is True
    assert receipt.provider == "anthropic"
    assert receipt.model == "claude-sonnet-4-20250514"


def test_receipt_is_frozen():
    receipt = EvidenceReceipt(task_id="t1")
    with pytest.raises(AttributeError):
        receipt.task_id = "t2"  # type: ignore[misc]


def test_receipt_to_dict_serializable():
    import json

    receipt = EvidenceReceipt(
        task_id="task-001",
        agent_id="agent-001",
        provider="openai",
        model="gpt-4o",
        status="ok",
        error_source="none",
    )
    d = receipt.to_dict()
    serialized = json.dumps(d, default=str)
    assert "task-001" in serialized
    assert isinstance(d["receipt_id"], str)


def test_receipt_to_otel_span():
    receipt = EvidenceReceipt(
        task_id="task-001",
        agent_id="agent-001",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        status="ok",
        input_tokens=100,
        output_tokens=200,
    )
    span = receipt.to_otel_span()
    assert span["attributes"]["gen_ai.operation.name"] == "invoke_agent"
    assert span["attributes"]["gen_ai.system"] == "anthropic"
    assert span["attributes"]["gen_ai.request.model"] == "claude-sonnet-4-20250514"
    assert span["attributes"]["gen_ai.usage.input_tokens"] == 100
    assert span["attributes"]["gen_ai.usage.output_tokens"] == 200
    assert span["attributes"]["dharma.status"] == "ok"


def test_routing_decision_is_frozen():
    rd = RoutingDecision(agent_id="a1")
    with pytest.raises(AttributeError):
        rd.agent_id = "a2"  # type: ignore[misc]


def test_routing_decision_has_uuid():
    rd = RoutingDecision()
    assert isinstance(rd.decision_id, UUID)


def test_error_source_type_literals():
    from typing import get_args
    sources = get_args(ErrorSource)
    assert len(sources) == len(set(sources))
    assert "task_missing" in sources
    assert "runner_missing" in sources
    assert "task_and_runner_missing" in sources
    assert "provider_failed" in sources
    assert "none" in sources
