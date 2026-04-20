"""PR5 integration test: full 5-stage chain through the dispatcher.

Scope:
- scope → validate → deep_research → capability → mvp completes via
  depends_on chain (one stage per tick, predecessor must complete first).
- Chain stalls at a quarantined deep_research; capability is NOT dispatched.
- After --retry-quarantined clears the flag, the chain resumes.

Uses fake task_board + a deterministic completion driver — no live LLM
calls. The deep_research path is patched to return a quarantine result on
demand for the stall/resume test.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import _campaign_manifest, opportunity_dispatcher
from dharma_swarm.models import GateCheckResult, GateDecision, TaskStatus


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def tmp_dharma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dharma = tmp_path / "dharma"
    meta = dharma / "meta"
    meta.mkdir(parents=True)
    (dharma / "witness").mkdir()
    campaigns = dharma / "campaigns"
    monkeypatch.setattr(opportunity_dispatcher, "DHARMA_HOME", dharma)
    monkeypatch.setattr(opportunity_dispatcher, "META_DIR", meta)
    monkeypatch.setattr(opportunity_dispatcher, "PENDING_PATH", meta / "frontier_tasks_pending.jsonl")
    monkeypatch.setattr(opportunity_dispatcher, "PAUSED_FLAG", meta / "dispatcher_paused.flag")
    monkeypatch.setattr(opportunity_dispatcher, "LOCK_PATH", meta / "dispatcher.lock")
    monkeypatch.setattr(opportunity_dispatcher, "HEALTH_PATH", meta / "opportunity_dispatcher.health.json")
    monkeypatch.setattr(opportunity_dispatcher, "WITNESS_DIR", dharma / "witness")
    monkeypatch.setattr(opportunity_dispatcher, "TASK_BOARD_DB", dharma / "db" / "tasks.db")
    monkeypatch.setattr(_campaign_manifest, "CAMPAIGN_ROOT", campaigns)
    monkeypatch.setattr(opportunity_dispatcher, "CAMPAIGN_ROOT", campaigns)
    return dharma


@dataclass
class _Task:
    id: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class _ChainTaskBoard:
    """Fake task_board that records each create + lets tests flip task
    status manually."""

    by_id: dict[str, _Task] = {}
    create_calls: list[dict[str, Any]] = []
    counter: int = 0

    def __init__(self, db_path=None):
        self._db_path = db_path

    async def init_db(self) -> None:
        return None

    async def create(self, **kwargs) -> _Task:
        type(self).counter += 1
        new_id = f"chaintask_{type(self).counter:04d}"
        t = _Task(id=new_id, metadata=dict(kwargs.get("metadata") or {}))
        type(self).by_id[new_id] = t
        type(self).create_calls.append(dict(kwargs))
        return t

    async def get(self, task_id: str) -> _Task | None:
        return type(self).by_id.get(task_id)


@pytest.fixture
def chain_board(monkeypatch: pytest.MonkeyPatch):
    _ChainTaskBoard.by_id = {}
    _ChainTaskBoard.create_calls = []
    _ChainTaskBoard.counter = 0
    import dharma_swarm.task_board as tb_mod
    monkeypatch.setattr(tb_mod, "TaskBoard", _ChainTaskBoard)
    return _ChainTaskBoard


@pytest.fixture
def gates_open(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "dharma_swarm.telos_gates.check_action",
        lambda action, content="": GateCheckResult(decision=GateDecision.ALLOW, reason="ok"),
    )
    monkeypatch.setattr(opportunity_dispatcher, "_budget_exceeded", lambda: False)
    async def _noop(*a, **kw): return None
    monkeypatch.setattr(opportunity_dispatcher, "_mark_stigmergy", _noop)


def _seed_full_pending(tmp_dharma: Path, opp_id: str = "opp_chain_001") -> None:
    """Seed the pending JSONL with all 5 stages (no first_artifact — PR7)."""
    rows = []
    for stage in ("scope", "validate", "deep_research", "capability", "mvp"):
        rows.append({
            "frontier_id": f"ft_{stage}_{opp_id}",
            "title": f"{stage.title()} for chain demo",
            "description": f"{stage} description for chain demo",
            "source": f"opportunity:{stage}",
            "verifier_type": "research_grade",
            "difficulty": "medium",
            "provenance": {
                "opportunity_id": opp_id,
                "domain": "external_revenue",
                "thesis": "wedge",
                "why_now": "chain test",
                "final_score": 80.0,
                "telos_alignment": 0.95,
                "stage": stage,
            },
            "metadata": {"seed_kind": "opportunity_bootstrap", "stage": stage},
        })
    (tmp_dharma / "meta" / "frontier_tasks_pending.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def _drive_chain_one_step(
    chain_board: _ChainTaskBoard,
    *,
    deep_research_quarantine: bool = False,
) -> str | None:
    """Find the most recent in-flight task and mark it COMPLETED.

    For deep_research, set the result to a quarantine JSON if requested.
    Returns the stage that just completed, or None if no in-flight task.
    """
    # Pick the most recent created task that is still pending.
    pending = [
        t for t in chain_board.by_id.values()
        if t.status == TaskStatus.PENDING
    ]
    if not pending:
        return None
    # Highest counter = most recent.
    target = max(pending, key=lambda t: int(t.id.split("_")[-1]))
    stage = target.metadata.get("stage", "")
    if stage == "deep_research" and deep_research_quarantine:
        target.result = json.dumps({
            "report": {"summary": "quarantined"},
            "grade": {"final_score": 0.2, "promotion_state": "rollback_or_revise"},
            "quarantined": True,
        })
    else:
        target.result = f"# {stage} memo\n\nbody"
    target.status = TaskStatus.COMPLETED
    return stage


# --------------------------------------------------------------------------
# Full happy-path chain
# --------------------------------------------------------------------------


def test_full_chain_completes_in_five_promote_observe_cycles(
    tmp_dharma: Path, chain_board, gates_open,
):
    _seed_full_pending(tmp_dharma)

    expected = ["scope", "validate", "deep_research", "capability", "mvp"]
    completed: list[str] = []

    for _ in range(5):
        # Promote: should add one task per cycle.
        before = len(chain_board.create_calls)
        asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
        after = len(chain_board.create_calls)
        assert after - before == 1, f"expected exactly 1 promotion per cycle, got {after-before}"
        # Observe: drive the just-promoted task to COMPLETED.
        stage = _drive_chain_one_step(chain_board)
        asyncio.run(opportunity_dispatcher.observe_completions())
        completed.append(stage)

    assert completed == expected

    manifest = json.loads(
        (tmp_dharma / "campaigns" / "opp_chain_001" / "manifest.json").read_text()
    )
    for stage in expected:
        assert manifest["stages"][stage]["status"] == "completed", (
            f"stage {stage} not completed: {manifest['stages'][stage]}"
        )

    # depends_on chain check: every non-first task depends on the prior task.
    calls = chain_board.create_calls
    for i in range(1, len(calls)):
        prev_id = next(iter(chain_board.by_id.keys()))  # any
        prev_task_id = list(chain_board.by_id.keys())[i - 1]
        assert calls[i]["depends_on"] == [prev_task_id], (
            f"call {i} depends_on={calls[i]['depends_on']}, expected [{prev_task_id}]"
        )


# --------------------------------------------------------------------------
# Quarantine stall + resume
# --------------------------------------------------------------------------


def test_chain_stalls_at_quarantined_deep_research_and_resumes_after_clear(
    tmp_dharma: Path, chain_board, gates_open,
):
    _seed_full_pending(tmp_dharma)

    # Run scope + validate normally.
    for _ in range(2):
        asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
        _drive_chain_one_step(chain_board)
        asyncio.run(opportunity_dispatcher.observe_completions())

    # Promote deep_research → mark it quarantined.
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    stage = _drive_chain_one_step(chain_board, deep_research_quarantine=True)
    assert stage == "deep_research"
    asyncio.run(opportunity_dispatcher.observe_completions())

    manifest_p = tmp_dharma / "campaigns" / "opp_chain_001" / "manifest.json"
    m = json.loads(manifest_p.read_text())
    assert m["stages"]["deep_research"]["status"] == "quarantined"

    # Try to promote on the next tick — capability MUST NOT be dispatched.
    creates_before = len(chain_board.create_calls)
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert len(chain_board.create_calls) == creates_before, (
        "capability dispatched while deep_research is quarantined"
    )

    # Operator clears the quarantine.
    ok, _ = opportunity_dispatcher.retry_quarantined("opp_chain_001:deep_research")
    assert ok is True

    # Next tick: deep_research re-promoted (status was reset to pending).
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert len(chain_board.create_calls) == creates_before + 1
    last_call = chain_board.create_calls[-1]
    assert last_call["metadata"]["stage"] == "deep_research"

    # Drive it through cleanly this time → capability + mvp can finish.
    _drive_chain_one_step(chain_board)
    asyncio.run(opportunity_dispatcher.observe_completions())

    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert chain_board.create_calls[-1]["metadata"]["stage"] == "capability"
    _drive_chain_one_step(chain_board)
    asyncio.run(opportunity_dispatcher.observe_completions())

    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert chain_board.create_calls[-1]["metadata"]["stage"] == "mvp"
    _drive_chain_one_step(chain_board)
    asyncio.run(opportunity_dispatcher.observe_completions())

    m = json.loads(manifest_p.read_text())
    for stage in ("scope", "validate", "deep_research", "capability", "mvp"):
        assert m["stages"][stage]["status"] == "completed"
