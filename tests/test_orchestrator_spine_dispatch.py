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


def test_runner_served_route_metadata_requires_explicit_served_fields():
    runner = types.SimpleNamespace(
        _config=types.SimpleNamespace(provider="openrouter", model="qwen3-coder-live")
    )

    assert Orchestrator._runner_served_route_metadata(runner) == {}


def test_runner_served_route_metadata_preserves_actual_served_fields_only():
    runner = types.SimpleNamespace(
        actual_served_provider="openrouter",
        actual_served_model="qwen3-coder-live",
        provider_model_truth_source="runtime_provider.actual_served",
    )

    route = Orchestrator._runner_served_route_metadata(runner)

    assert route["actual_served_provider"] == "openrouter"
    assert route["actual_served_model"] == "qwen3-coder-live"
    assert route["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert "selected_provider" not in route
    assert "selected_model" not in route


def test_runner_attempted_route_metadata_preserves_selected_fields_only():
    runner = types.SimpleNamespace(
        selected_provider="openrouter",
        selected_model="gpt-5.5",
        provider_model_truth_source="agent_runner.provider_chain_failure",
    )

    route = Orchestrator._runner_attempted_route_metadata(runner)

    assert route["selected_provider"] == "openrouter"
    assert route["selected_model"] == "gpt-5.5"
    assert route["selected_model_hint"] == "gpt-5.5"
    assert route["provider_model_truth_source"] == (
        "agent_runner.provider_chain_failure"
    )
    assert route["provider_execution"] is True
    assert route["provider_model_applicability"] == "failed_before_serve"
    assert route["provider_model_missing_reason"] == (
        "provider_chain_failed_before_actual_served_response"
    )
    assert "actual_served_provider" not in route
    assert "actual_served_model" not in route


def test_runner_failure_route_prefers_served_route_over_attempted_route():
    runner = types.SimpleNamespace(
        actual_served_provider="ollama",
        actual_served_model="kimi-k2.5",
        selected_provider="openrouter",
        selected_model="gpt-5.5",
        provider_model_truth_source="runtime_provider.actual_served",
    )
    task = types.SimpleNamespace(metadata={})
    td = types.SimpleNamespace(metadata={})

    route = Orchestrator._stamp_runner_failure_route(runner, task=task, td=td)

    assert route["actual_served_provider"] == "ollama"
    assert route["actual_served_model"] == "kimi-k2.5"
    assert "selected_provider" not in route
    assert td.metadata["actual_served_provider"] == "ollama"
    assert task.metadata["actual_served_model"] == "kimi-k2.5"


def test_runner_no_provider_execution_metadata_is_explicit():
    runner = types.SimpleNamespace(
        provider_execution=False,
        provider_model_applicability="not_applicable",
        provider_model_truth_source="agent_runner.no_provider_execution",
        no_provider_model_reason="agent_runner_no_provider_attached",
    )

    route = Orchestrator._runner_no_provider_execution_metadata(runner)

    assert route == {
        "provider_execution": False,
        "provider_model_applicability": "not_applicable",
        "provider_model_truth_source": "agent_runner.no_provider_execution",
        "no_provider_model_reason": "agent_runner_no_provider_attached",
    }


def test_runner_success_route_stamps_no_provider_execution_when_no_served_route():
    runner = types.SimpleNamespace(
        provider_execution=False,
        provider_model_applicability="not_applicable",
        provider_model_truth_source="agent_runner.no_provider_execution",
        no_provider_model_reason="agent_runner_no_provider_attached",
    )
    task = types.SimpleNamespace(metadata={})
    td = types.SimpleNamespace(metadata={})

    route = Orchestrator._stamp_runner_served_route(runner, task=task, td=td)

    assert route["provider_execution"] is False
    assert route["provider_model_truth_source"] == "agent_runner.no_provider_execution"
    assert td.metadata["provider_execution"] is False
    assert task.metadata["no_provider_model_reason"] == (
        "agent_runner_no_provider_attached"
    )


def test_runner_success_route_infers_no_provider_when_agent_runner_has_none():
    runner = types.SimpleNamespace(_provider=None)
    task = types.SimpleNamespace(metadata={})
    td = types.SimpleNamespace(metadata={})

    route = Orchestrator._stamp_runner_served_route(runner, task=task, td=td)

    assert route == {
        "provider_execution": False,
        "provider_model_applicability": "not_applicable",
        "provider_model_truth_source": "agent_runner.no_provider_execution",
        "no_provider_model_reason": "agent_runner_no_provider_attached",
    }
    assert td.metadata["provider_execution"] is False
    assert task.metadata["provider_model_truth_source"] == "agent_runner.no_provider_execution"


def test_runner_success_route_marks_provider_execution_unproven_without_served_evidence():
    runner = types.SimpleNamespace(_provider=object())
    task = types.SimpleNamespace(metadata={})
    td = types.SimpleNamespace(metadata={})

    route = Orchestrator._stamp_runner_served_route(runner, task=task, td=td)

    assert route == {
        "provider_execution": True,
        "provider_model_applicability": "actual_served_unproven",
        "provider_model_truth_source": "orchestrator.provider_execution_unproven",
        "provider_model_missing_reason": (
            "provider_execution_completed_without_actual_served_runtime_evidence"
        ),
    }
    assert td.metadata["provider_execution"] is True
    assert task.metadata["provider_model_applicability"] == "actual_served_unproven"


def test_runner_pending_provider_execution_metadata_requires_attached_provider():
    assert Orchestrator._runner_pending_provider_execution_metadata(
        types.SimpleNamespace(_provider=None)
    ) == {}

    route = Orchestrator._runner_pending_provider_execution_metadata(
        types.SimpleNamespace(_provider=object())
    )

    assert route == {
        "provider_execution": "pending",
        "provider_model_applicability": "pending_execution",
        "provider_model_truth_source": "orchestrator.provider_execution_pending",
        "provider_model_pending_reason": "agent_task_started_provider_route_pending",
    }


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


def test_spine_dispatch_failure_stamps_runner_served_route_before_reraising():
    class BoomAfterModelRunner:
        actual_served_provider = ""
        actual_served_model = ""
        provider_model_truth_source = ""

        async def run_task(self, task):
            self.actual_served_provider = "ollama"
            self.actual_served_model = "kimi-k2.5"
            self.provider_model_truth_source = "runtime_provider.actual_served"
            raise RuntimeError("local tool loop exceeded")

    me = _stub_self()
    td = _stub_td(task_id="t-route-fail")
    task = types.SimpleNamespace(metadata={})

    try:
        asyncio.run(
            Orchestrator._run_task_via_spine(
                me,
                BoomAfterModelRunner(),
                task,
                td,
                5.0,
            )
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("exception must propagate to caller")

    assert task.metadata["actual_served_provider"] == "ollama"
    assert task.metadata["actual_served_model"] == "kimi-k2.5"
    assert task.metadata["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert td.metadata["served_provider"] == "ollama"
    assert td.metadata["served_model"] == "kimi-k2.5"


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


def _stub_self_with_store(db_path):
    """Stub self whose runtime lifecycle resolves to a store at db_path —
    the persistence wire must write to THIS db, never a hardcoded default."""
    store = types.SimpleNamespace(db_path=db_path)
    lifecycle = types.SimpleNamespace(_runtime_state_store=lambda: store)
    me = types.SimpleNamespace(_runtime_lifecycle=lifecycle)
    return me


def test_spine_dispatch_persists_receipt_json_to_the_stores_db(tmp_path):
    """GATE-1 falsifiability: a flagged dispatch must land its EvidenceReceipt
    in delegation_runs.receipt_json of the SAME db the run row was written to.
    (The witness kit counts this column; without this write the gate is
    unfalsifiable — divergence rounds 1+2 findings.)"""
    import json
    import sqlite3

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE delegation_runs (task_id TEXT PRIMARY KEY, status TEXT)")
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status) VALUES ('t-persist', 'running')"
    )
    conn.commit()
    conn.close()

    class Runner:
        async def run_task(self, task):
            return "RUN_RESULT"

    me = _stub_self_with_store(db_path)
    td = _stub_td(task_id="t-persist")
    result = asyncio.run(
        Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0)
    )
    assert result == "RUN_RESULT"

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT receipt_json FROM delegation_runs WHERE task_id='t-persist'"
    ).fetchone()
    conn.close()
    assert row is not None and row[0], "receipt_json must be populated"
    blob = json.loads(row[0])
    assert blob["task_id"] == "t-persist"
    assert blob["operation"] == "invoke_agent"
    assert blob["receipt_id"] == str(me._last_evidence_receipt.receipt_id)


def test_spine_dispatch_zero_row_persist_is_loud_not_silent(tmp_path, caplog):
    """A receipt whose task_id matches NO delegation_runs row must surface as a
    warning (persist_receipt raises; the wire's fail-open logs it) — never as a
    silent 0-row success that leaves the witness flat with no diagnostic."""
    import logging
    import sqlite3

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE delegation_runs (task_id TEXT PRIMARY KEY, status TEXT)")
    conn.commit()
    conn.close()  # table exists, but NO row for this task

    class Runner:
        async def run_task(self, task):
            return "RUN_RESULT"

    me = _stub_self_with_store(db_path)
    td = _stub_td(task_id="t-orphan")
    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0)
        )
    assert result == "RUN_RESULT", "dispatch must not break on persistence failure"
    assert any(
        "NOT persisted" in rec.message for rec in caplog.records
    ), "0-row persist must produce a visible warning"
