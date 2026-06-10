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


def _stub_self_with_store(store):
    me = types.SimpleNamespace()
    me._runtime_lifecycle = types.SimpleNamespace(_runtime_state_store=lambda: store)
    return me


def _read_receipt_json(db_path, task_id):
    import sqlite3

    with sqlite3.connect(db_path) as db:
        row = db.execute(
            "SELECT receipt_json FROM delegation_runs WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    return row[0] if row else None


def test_spine_dispatch_persists_receipt_json_to_delegation_runs(tmp_path):
    """The receipt produced by _run_task_via_spine must land durably in
    delegation_runs.receipt_json via spine.persistence.persist_receipt."""
    import json

    from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore

    store = RuntimeStateStore(tmp_path / "runtime.db")

    class Runner:
        async def run_task(self, task):
            return "RUN_RESULT"

    async def _run():
        await store.record_delegation_run(
            DelegationRun(
                run_id="run-persist-1",
                task_id="t-123",
                assigned_to="agent-1",
                status="running",
            )
        )
        me = _stub_self_with_store(store)
        td = _stub_td()
        result = await Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0)
        return me, result

    me, result = asyncio.run(_run())
    assert result == "RUN_RESULT"
    blob = _read_receipt_json(store.db_path, "t-123")
    assert blob, "receipt_json must be populated on the delegation_runs row"
    payload = json.loads(blob)
    assert payload["receipt_id"] == str(me._last_evidence_receipt.receipt_id)
    assert payload["task_id"] == "t-123"
    assert payload["status"] == "ok"
    assert payload["operation"] == "invoke_agent"


def test_spine_dispatch_persists_failed_receipt_before_reraise(tmp_path):
    """Failure path: the failed receipt is persisted, then the exception
    still propagates to the caller."""
    import json

    from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore

    store = RuntimeStateStore(tmp_path / "runtime.db")

    class BoomRunner:
        async def run_task(self, task):
            raise RuntimeError("boom")

    async def _run():
        await store.record_delegation_run(
            DelegationRun(
                run_id="run-persist-2",
                task_id="t-fail",
                assigned_to="agent-1",
                status="running",
            )
        )
        me = _stub_self_with_store(store)
        td = _stub_td(task_id="t-fail")
        try:
            await Orchestrator._run_task_via_spine(me, BoomRunner(), object(), td, 5.0)
        except RuntimeError as exc:
            return str(exc)
        return None

    raised = asyncio.run(_run())
    assert raised == "boom", "exception must still propagate after persistence"
    blob = _read_receipt_json(store.db_path, "t-fail")
    assert blob, "failed receipt must still be persisted"
    payload = json.loads(blob)
    assert payload["status"] == "failed"


def test_spine_dispatch_absent_store_does_not_crash():
    """No runtime store (None) — dispatch completes; persistence is a no-op."""

    class Runner:
        async def run_task(self, task):
            return "RUN_RESULT"

    me = _stub_self_with_store(None)
    td = _stub_td(task_id="t-no-store")
    result = asyncio.run(Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0))
    assert result == "RUN_RESULT"
    assert me._last_evidence_receipt.status == "ok"


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
