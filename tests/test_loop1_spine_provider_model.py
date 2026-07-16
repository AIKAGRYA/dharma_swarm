"""Loop 1 spine closure: the dispatch-layer EvidenceReceipt must carry the
REAL provider and model of the runner that executed the task (not the
hardcoded provider="orchestrator", model="" defaults), and that receipt must
persist to delegation_runs.receipt_json of the same store — re-read from the
db proves it.

No network, no spend: the runner is a fake/stub whose run_task returns a plain
string and whose _config carries a provider/model only.

Also exercises the make orient closure check: Loop 1 is LIVE only when the
latest delegation_runs receipt has non-empty provider AND model.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import types

from dharma_swarm.models import ProviderType
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.spine.receipt import EvidenceReceipt


def _stub_td(agent="agent-1", task_id="t-loop1"):
    return types.SimpleNamespace(
        agent_id=agent,
        task_id=task_id,
        metadata={
            "execution_identity": {
                "trace_id": "trace-xyz",
                "session_id": "sess-1",
                "run_id": f"run-{task_id}",
                "claim_id": f"claim-{task_id}",
                "idempotency_key": f"idem-{task_id}",
            }
        },
        topology=types.SimpleNamespace(value="dispatch"),
    )


def _stub_self_with_store(db_path):
    store = types.SimpleNamespace(db_path=db_path)
    lifecycle = types.SimpleNamespace(_runtime_state_store=lambda: store)
    return types.SimpleNamespace(_runtime_lifecycle=lifecycle)


class _FakeRunner:
    """No network, no spend. run_task returns a plain string (mirrors the real
    AgentRunner.run_task -> str). The provider/model live on _config exactly as
    the real AgentRunner exposes them (agent_runner.py:1632, 885-886)."""

    def __init__(self, provider: ProviderType, model: str):
        self._config = types.SimpleNamespace(provider=provider, model=model)

    async def run_task(self, task):
        return "RUN_RESULT"


def test_spine_receipt_carries_real_provider_and_model_and_persists(tmp_path):
    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, task_id TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO delegation_runs (run_id, task_id, status)"
        " VALUES ('run-t-loop1', 't-loop1', 'running')"
    )
    conn.commit()
    conn.close()

    runner = _FakeRunner(provider=ProviderType.OPENROUTER, model="z-ai/glm-4.6")
    me = _stub_self_with_store(db_path)
    td = _stub_td(task_id="t-loop1")

    result = asyncio.run(Orchestrator._run_task_via_spine(me, runner, object(), td, 5.0))
    assert result == "RUN_RESULT"

    receipt = me._last_evidence_receipt
    assert isinstance(receipt, EvidenceReceipt)
    assert receipt.provider, "receipt.provider must be non-empty"
    assert receipt.model, "receipt.model must be non-empty"
    assert receipt.provider == ProviderType.OPENROUTER.value
    assert receipt.model == "z-ai/glm-4.6"

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT receipt_json FROM delegation_runs WHERE task_id='t-loop1'"
    ).fetchone()
    conn.close()
    assert row is not None and row[0], "receipt_json must be persisted"
    blob = json.loads(row[0])
    assert blob["provider"] == ProviderType.OPENROUTER.value
    assert blob["model"] == "z-ai/glm-4.6"


def test_orient_marks_loop1_live_only_with_provider_and_model(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts/governance/orientation_graph.py"
    spec = importlib.util.spec_from_file_location("orientation_graph_loop1", script)
    og = importlib.util.module_from_spec(spec)
    sys.modules["orientation_graph_loop1"] = og
    spec.loader.exec_module(og)

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE delegation_runs (task_id TEXT PRIMARY KEY, status TEXT, "
        "started_at TEXT, receipt_json TEXT)"
    )
    conn.commit()
    conn.close()

    # No receipt yet -> NOT live.
    closure = og.build_loop1_closure(db_path=db_path)
    assert closure.live is False

    # Receipt with empty provider/model -> NOT live.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status, started_at, receipt_json) "
        "VALUES ('t-empty', 'completed', '2026-06-13T00:00:00Z', ?)",
        (json.dumps({"provider": "", "model": ""}),),
    )
    conn.commit()
    conn.close()
    closure = og.build_loop1_closure(db_path=db_path)
    assert closure.live is False

    # Latest receipt with provider AND model -> LIVE.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status, started_at, receipt_json) "
        "VALUES ('t-real', 'completed', '2026-06-13T01:00:00Z', ?)",
        (json.dumps({"provider": "openrouter", "model": "z-ai/glm-4.6"}),),
    )
    conn.commit()
    conn.close()
    closure = og.build_loop1_closure(db_path=db_path)
    assert closure.live is True
    assert closure.provider == "openrouter"
    assert closure.model == "z-ai/glm-4.6"
