"""WS3 verifier: orchestrator dispatch routes execution through the spine's
invoke_agent path, emitting exactly one EvidenceReceipt per dispatch, while
preserving run_task's result (success) and exception (failure) semantics.

Tests _run_task_via_spine in isolation (unbound method on a stub self) so we
don't need to stand up the full Orchestrator + pool + bus.
"""
from __future__ import annotations

import asyncio
import types

from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.spine.receipt import EvidenceReceipt


def _stub_self():
    return types.SimpleNamespace()


def _stub_td(agent="agent-1", task_id="t-123"):
    return types.SimpleNamespace(
        agent_id=agent,
        task_id=task_id,
        metadata={"execution_identity": {"trace_id": "trace-xyz", "session_id": "sess-1"}},
        topology=types.SimpleNamespace(value="dispatch"),
    )


def test_spine_dispatch_success_emits_one_receipt_and_returns_result():
    calls = {"n": 0}

    class Runner:
        async def run_task(self, task):
            calls["n"] += 1
            return "RUN_RESULT"

    me = _stub_self()
    td = _stub_td()
    result = asyncio.run(
        Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0)
    )
    assert result == "RUN_RESULT"
    assert calls["n"] == 1, "run_task must be invoked exactly once"
    receipt = me._last_evidence_receipt
    assert isinstance(receipt, EvidenceReceipt)
    assert receipt.operation == "invoke_agent"
    assert receipt.status == "ok"
    assert receipt.agent_id == "agent-1"
    assert receipt.task_id == "t-123"
    assert receipt.trace_id == "trace-xyz"
    assert td.metadata["evidence_receipt_id"] == str(receipt.receipt_id)


def test_spine_dispatch_failure_reraises_and_records_failed_receipt():
    class BoomRunner:
        async def run_task(self, task):
            raise RuntimeError("boom")

    me = _stub_self()
    td = _stub_td(task_id="t-fail")
    raised = None
    try:
        asyncio.run(Orchestrator._run_task_via_spine(me, BoomRunner(), object(), td, 5.0))
    except RuntimeError as exc:
        raised = exc
    assert raised is not None and str(raised) == "boom", "exception must propagate to caller"
    receipt = me._last_evidence_receipt
    assert isinstance(receipt, EvidenceReceipt)
    assert receipt.status == "failed"
    assert receipt.error_source == "internal_error"


def test_spine_dispatch_timeout_reraises_and_records_timeout_receipt():
    class SlowRunner:
        async def run_task(self, task):
            await asyncio.sleep(1.0)
            return "late"

    me = _stub_self()
    td = _stub_td(task_id="t-slow")
    raised = False
    try:
        asyncio.run(Orchestrator._run_task_via_spine(me, SlowRunner(), object(), td, 0.05))
    except asyncio.TimeoutError:
        raised = True
    assert raised, "timeout must propagate"
    assert me._last_evidence_receipt.status == "timeout"
