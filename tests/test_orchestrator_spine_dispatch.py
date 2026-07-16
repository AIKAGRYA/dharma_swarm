"""WS3 verifier: orchestrator dispatch routes execution through the spine's
invoke_agent path, emitting exactly one EvidenceReceipt per dispatch, while
preserving run_task's result (success) and exception (failure) semantics.

Tests _run_task_via_spine in isolation (unbound method on a stub self) so we
don't need to stand up the full Orchestrator + pool + bus.
"""
from __future__ import annotations

import asyncio
import types

import pytest

from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.spine.receipt import EvidenceReceipt


def _stub_self():
    return types.SimpleNamespace()


def _stub_td(agent="agent-1", task_id="t-123"):
    return types.SimpleNamespace(
        agent_id=agent,
        task_id=task_id,
        metadata={
            "execution_identity": {
                "trace_id": "trace-xyz",
                "session_id": "sess-1",
                "run_id": "run-xyz",
                "claim_id": "claim-xyz",
                "idempotency_key": "idem-xyz",
            }
        },
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
    assert receipt.claim_id == "claim-xyz"
    assert receipt.attributes["run_id"] == "run-xyz"
    assert receipt.attributes["idempotency_key"] == "idem-xyz"
    assert receipt.attributes["side_effect_key"] == "invoke_agent:t-123:agent-1"
    assert receipt.attributes["topology"] == "dispatch"
    assert receipt.attributes["agent_identity"] == "agent-1"
    assert receipt.attributes["planned_provider"] == "orchestrator"
    assert receipt.attributes["actual_provider"] == "orchestrator"
    assert td.metadata["evidence_receipt_id"] == str(receipt.receipt_id)


def test_spine_dispatch_receipt_records_actual_route_and_fallback_truth():
    from dharma_swarm.decision_router import RoutePath
    from dharma_swarm.models import LLMResponse, ProviderType
    from dharma_swarm.provider_policy import ProviderRouteDecision, ProviderRouteRequest

    class RoutedRunner:
        _config = types.SimpleNamespace(
            provider=ProviderType.ANTHROPIC,
            model="claude-sonnet-4-20250514",
        )

        async def run_task(self, task):
            self._last_route_request = ProviderRouteRequest(
                action_name="route_truth",
                risk_score=0.2,
                uncertainty=0.4,
                novelty=0.3,
                urgency=0.5,
                expected_impact=0.4,
                context={
                    "preferred_provider": ProviderType.ANTHROPIC.value,
                    "preferred_model": "claude-sonnet-4-20250514",
                },
            )
            self._last_route_decision = ProviderRouteDecision(
                path=RoutePath.DELIBERATIVE,
                selected_provider=ProviderType.OPENROUTER,
                selected_model_hint="moonshotai/kimi-k2.5",
                fallback_providers=[ProviderType.CLAUDE_CODE, ProviderType.OPENAI],
                fallback_model_hints=["claude-opus-4-6", "gpt-5"],
                confidence=0.82,
                requires_human=False,
                reasons=["deliberative_route", "fallback_provider_selected"],
            )
            self._last_response = LLMResponse(
                content="RUN_RESULT",
                model="moonshotai/kimi-k2.5",
                provider=ProviderType.OPENROUTER.value,
                usage={"prompt_tokens": 12, "completion_tokens": 5},
            )
            self._last_usage = dict(self._last_response.usage)
            return "RUN_RESULT"

    me = _stub_self()
    td = _stub_td(task_id="t-route-truth")
    result = asyncio.run(
        Orchestrator._run_task_via_spine(me, RoutedRunner(), object(), td, 5.0)
    )

    assert result == "RUN_RESULT"
    receipt = me._last_evidence_receipt
    attrs = receipt.attributes
    assert receipt.provider == ProviderType.OPENROUTER.value
    assert receipt.model == "moonshotai/kimi-k2.5"
    assert receipt.input_tokens == 12
    assert receipt.output_tokens == 5
    assert attrs["requested_provider"] == ProviderType.ANTHROPIC.value
    assert attrs["planned_provider"] == ProviderType.ANTHROPIC.value
    assert attrs["actual_provider"] == ProviderType.OPENROUTER.value
    assert attrs["served_provider"] == ProviderType.OPENROUTER.value
    assert attrs["planned_model"] == "claude-sonnet-4-20250514"
    assert attrs["actual_model"] == "moonshotai/kimi-k2.5"
    assert attrs["route_path"] == RoutePath.DELIBERATIVE.value
    assert attrs["route_confidence"] == 0.82
    assert attrs["route_reasons"] == ["deliberative_route", "fallback_provider_selected"]
    assert attrs["route_fallback_plan"] == [
        {"provider": ProviderType.CLAUDE_CODE.value, "model": "claude-opus-4-6"},
        {"provider": ProviderType.OPENAI.value, "model": "gpt-5"},
    ]
    assert attrs["provider_truth_source"] == "llm_response"
    assert attrs["fallback_used"] is True
    assert attrs["actual_differs_from_requested"] is True


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
    conn.execute(
        "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, task_id TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO delegation_runs (run_id, task_id, status)"
        " VALUES ('run-xyz', 't-persist', 'running')"
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


def test_spine_dispatch_projects_receipt_to_exact_retry_only(tmp_path):
    """Retries share task_id; receipt projection must remain run-scoped."""
    import sqlite3

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, task_id TEXT,"
        " status TEXT, receipt_json TEXT)"
    )
    conn.executemany(
        "INSERT INTO delegation_runs (run_id, task_id, status) VALUES (?, ?, 'running')",
        (("run-old", "t-retry"), ("run-xyz", "t-retry")),
    )
    conn.commit()
    conn.close()

    class Runner:
        async def run_task(self, task):
            return "RUN_RESULT"

    me = _stub_self_with_store(db_path)
    td = _stub_td(task_id="t-retry")
    assert (
        asyncio.run(Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0))
        == "RUN_RESULT"
    )

    conn = sqlite3.connect(db_path)
    rows = dict(
        conn.execute(
            "SELECT run_id, receipt_json FROM delegation_runs WHERE task_id='t-retry'"
        ).fetchall()
    )
    conn.close()
    assert rows["run-old"] is None
    assert rows["run-xyz"]


@pytest.mark.parametrize(
    ("receipt_claim_id", "receipt_agent_id"),
    (
        ("claim-foreign", "agent-valid"),
        ("claim-valid", "agent-foreign"),
    ),
)
async def test_receipt_projection_rejects_foreign_authority_without_poisoning(
    tmp_path, receipt_claim_id, receipt_agent_id
):
    """A task/run collision cannot replace its claim/agent-owned witness."""
    import aiosqlite
    import json
    import sqlite3

    from dharma_swarm.spine.persistence import persist_receipt

    db_path = tmp_path / "runtime.db"
    valid_witness = json.dumps({"receipt_id": "valid-authoritative-witness"})
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, task_id TEXT,"
            " claim_id TEXT, assigned_to TEXT, status TEXT, receipt_json TEXT)"
        )
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, claim_id, assigned_to,"
            " status, receipt_json) VALUES (?, ?, ?, ?, 'completed', ?)",
            ("run-xyz", "t-authority", "claim-valid", "agent-valid", valid_witness),
        )

    foreign = EvidenceReceipt(
        task_id="t-authority",
        claim_id=receipt_claim_id,
        agent_id=receipt_agent_id,
        status="ok",
        attributes={"run_id": "run-xyz"},
    )
    async with aiosqlite.connect(db_path) as db:
        with pytest.raises(RuntimeError, match="authoritative delegation_runs"):
            await persist_receipt(foreign, db)

    with sqlite3.connect(db_path) as db:
        stored = db.execute(
            "SELECT receipt_json FROM delegation_runs WHERE run_id = 'run-xyz'"
        ).fetchone()
    assert stored == (valid_witness,)


def test_spine_dispatch_ambiguous_run_projection_writes_nothing(tmp_path, caplog):
    """Malformed duplicate run rows fail closed without partial projection."""
    import logging
    import sqlite3

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE delegation_runs (run_id TEXT, task_id TEXT, status TEXT,"
        " receipt_json TEXT)"
    )
    conn.executemany(
        "INSERT INTO delegation_runs (run_id, task_id, status)"
        " VALUES ('run-xyz', 't-ambiguous', 'running')",
        ((), ()),
    )
    conn.commit()
    conn.close()

    class Runner:
        async def run_task(self, task):
            return "RUN_RESULT"

    me = _stub_self_with_store(db_path)
    td = _stub_td(task_id="t-ambiguous")
    with caplog.at_level(logging.WARNING):
        assert (
            asyncio.run(
                Orchestrator._run_task_via_spine(me, Runner(), object(), td, 5.0)
            )
            == "RUN_RESULT"
        )

    conn = sqlite3.connect(db_path)
    projections = [
        row[0]
        for row in conn.execute(
            "SELECT receipt_json FROM delegation_runs WHERE task_id='t-ambiguous'"
        )
    ]
    conn.close()
    assert projections == [None, None]
    assert any("NOT persisted" in record.message for record in caplog.records)


def test_spine_dispatch_zero_row_persist_is_loud_not_silent(tmp_path, caplog):
    """A receipt whose task_id matches NO delegation_runs row must surface as a
    warning (persist_receipt raises; the wire's fail-open logs it) — never as a
    silent 0-row success that leaves the witness flat with no diagnostic."""
    import logging
    import sqlite3

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, task_id TEXT, status TEXT)"
    )
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
