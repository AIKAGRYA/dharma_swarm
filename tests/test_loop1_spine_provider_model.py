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
import datetime
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
        metadata={"execution_identity": {"trace_id": "trace-xyz", "session_id": "sess-1"}},
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
    conn.execute("CREATE TABLE delegation_runs (task_id TEXT PRIMARY KEY, status TEXT)")
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status) VALUES ('t-loop1', 'running')"
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


class _FakeRoutingRunner:
    """No network, no spend. Simulates routing/race_providers()/fallback: the
    STATIC _config names one provider/model, but run_task() actually SERVES a
    different provider/model (e.g. the fallback chain picked another brain).
    The actually-served identity is exposed post-run via the runner attributes
    the AgentRunner sets just before `return result` (agent_runner.py:2582)."""

    def __init__(
        self,
        config_provider: ProviderType,
        config_model: str,
        served_provider: ProviderType,
        served_model: str,
    ):
        self._config = types.SimpleNamespace(
            provider=config_provider, model=config_model
        )
        self._served_provider = served_provider
        self._served_model = served_model

    async def run_task(self, task):
        # Mirror the real AgentRunner: the served identity is only knowable after
        # the completion attempt (post-fallback / post-race), so it is stamped
        # onto the runner right before returning the result string.
        self._last_served_provider = self._served_provider.value
        self._last_served_model = self._served_model
        return "RUN_RESULT"


def test_spine_receipt_carries_actually_served_provider_not_config(tmp_path):
    """Under routing/fallback the served provider/model differ from the static
    _config. The dispatch EvidenceReceipt must carry the SERVED identity (what
    actually ran), not the configured one — otherwise the receipt mislabels the
    brain whenever the fallback chain or race_providers() picks anything other
    than config.provider."""
    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE delegation_runs (task_id TEXT PRIMARY KEY, status TEXT)")
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status) VALUES ('t-route', 'running')"
    )
    conn.commit()
    conn.close()

    # Configured for ANTHROPIC/claude, but routing actually SERVES openrouter/glm.
    runner = _FakeRoutingRunner(
        config_provider=ProviderType.ANTHROPIC,
        config_model="claude-sonnet-4-20250514",
        served_provider=ProviderType.OPENROUTER,
        served_model="z-ai/glm-4.6",
    )
    me = _stub_self_with_store(db_path)
    td = _stub_td(task_id="t-route")

    result = asyncio.run(Orchestrator._run_task_via_spine(me, runner, object(), td, 5.0))
    assert result == "RUN_RESULT"

    receipt = me._last_evidence_receipt
    assert isinstance(receipt, EvidenceReceipt)
    # The SERVED identity, not the configured one.
    assert receipt.provider == ProviderType.OPENROUTER.value
    assert receipt.model == "z-ai/glm-4.6"
    assert receipt.provider != ProviderType.ANTHROPIC.value
    assert receipt.model != "claude-sonnet-4-20250514"

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT receipt_json FROM delegation_runs WHERE task_id='t-route'"
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

    # Latest receipt with provider AND model AND fresh (<24h) -> LIVE.
    _fresh = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status, started_at, receipt_json) "
        "VALUES ('t-real', 'completed', ?, ?)",
        (_fresh, json.dumps({"provider": "openrouter", "model": "z-ai/glm-4.6"})),
    )
    conn.commit()
    conn.close()
    closure = og.build_loop1_closure(db_path=db_path)
    assert closure.live is True
    assert closure.provider == "openrouter"
    assert closure.model == "z-ai/glm-4.6"


def test_loop1_closure_requires_fresh_receipt(tmp_path):
    """A receipt with provider+model but >24h old reads NOT-LIVE: Loop 1
    closure means continuous dispatch, not one stale receipt frozen in time."""
    import importlib.util
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts/governance/orientation_graph.py"
    spec = importlib.util.spec_from_file_location("orientation_graph_loop1_stale", script)
    og = importlib.util.module_from_spec(spec)
    sys.modules["orientation_graph_loop1_stale"] = og
    spec.loader.exec_module(og)

    db_path = tmp_path / "runtime.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE delegation_runs (task_id TEXT PRIMARY KEY, status TEXT, "
        "started_at TEXT, receipt_json TEXT)"
    )
    stale = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=400)
    ).isoformat()
    conn.execute(
        "INSERT INTO delegation_runs (task_id, status, started_at, receipt_json) "
        "VALUES ('t-stale', 'completed', ?, ?)",
        (stale, json.dumps({"provider": "ollama", "model": "mistral:latest"})),
    )
    conn.commit()
    conn.close()
    closure = og.build_loop1_closure(db_path=db_path)
    assert closure.live is False
    assert "stale" in closure.detail.lower()
