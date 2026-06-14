from __future__ import annotations

import pytest

import dharma_swarm.spine.manual_runner as manual_runner
from dharma_swarm.models import Task


@pytest.mark.asyncio
async def test_manual_agent_runner_wrapper_invokes_spine_once(monkeypatch):
    class _Runner:
        async def run_task(self, task):
            return f"ran {task.id}"

    traversals = []

    async def _counting_invoke(task, agent_id, context_id, routing, *, invoker):
        receipt = await invoker(
            task=task,
            agent_id=agent_id,
            context_id=context_id,
            routing=routing,
        )
        traversals.append((task, agent_id, context_id, routing, receipt))
        return receipt

    monkeypatch.setattr(manual_runner, "invoke_agent", _counting_invoke)
    task = Task(
        id="manual-task-1",
        title="Manual live script task",
        description="prove the manual script wrapper",
        metadata={"trace_id": "trace-manual-1", "session_id": "sess-manual-1"},
    )

    result, receipt = await manual_runner.run_manual_agent_runner_via_spine(
        _Runner(),
        task,
        surface="scripts/live_test.py",
        agent_name="manual-agent",
    )

    assert result == "ran manual-task-1"
    assert receipt.operation == "invoke_agent"
    assert receipt.trace_id == "trace-manual-1"
    assert receipt.attributes["surface"] == "scripts/live_test.py"
    assert task.metadata["evidence_receipt_id"] == str(receipt.receipt_id)
    assert len(traversals) == 1
    _, agent_id, context_id, routing, _ = traversals[0]
    assert agent_id == "manual-agent"
    assert context_id == "sess-manual-1"
    assert routing.router_name == "manual_agent_runner_script"
