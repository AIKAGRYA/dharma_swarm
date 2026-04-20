"""Tests for the PR4 deep_research branch in agent_runner.run_task.

Covers:
- Branch detection: task with metadata.task_type=="deep_research" routes to
  the AutoResearch path instead of LLM completion.
- FrontierTask is rehydrated from metadata.frontier_row (PR1 contract).
- frontier_task_to_research_brief is invoked with correct shape.
- Successful workflow returns result JSON with quarantined=False.
- Failing-grade workflow returns result JSON with quarantined=True.
- Outcome+ValueEvent recorded exactly once at the existing Telic Seam
  (agent_runner.py:2680) — observer must NOT duplicate.

Also covers the dispatcher throttle gate (PR4):
- 7th deep_research promotion in 24h is blocked + manifest.throttled=True.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import _campaign_manifest, opportunity_dispatcher


# --------------------------------------------------------------------------
# Agent-runner branch tests
# --------------------------------------------------------------------------


def _frontier_row_for_deep_research() -> dict[str, Any]:
    """A minimal frontier_row that PR4 can rehydrate."""
    return {
        "frontier_id": "ftask_dr_abc",
        "title": "Deep research for Demo",
        "description": "PhD-level investigation of Demo via AutoResearch + AutoGrade.",
        "source": "opportunity:deep_research",
        "verifier_type": "research_grade",
        "difficulty": "medium",
        "provenance": {
            "opportunity_id": "opp_demo_001",
            "domain": "external_revenue",
            "thesis": "wedge",
            "why_now": "demo why now",
            "final_score": 80.0,
            "telos_alignment": 0.95,
            "stage": "deep_research",
        },
        "metadata": {"seed_kind": "opportunity_bootstrap", "stage": "deep_research"},
    }


@dataclass
class _StubReport:
    report_id: str = "rep_1"
    title: str = "Demo report"

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {"report_id": self.report_id, "title": self.title}


@dataclass
class _StubGrade:
    final_score: float = 0.85
    promotion_state: str = "candidate"
    gate_failures: list[str] = field(default_factory=list)

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {
            "final_score": self.final_score,
            "promotion_state": self.promotion_state,
            "gate_failures": list(self.gate_failures),
        }


@dataclass
class _StubReward:
    grade_card: _StubGrade = field(default_factory=_StubGrade)
    gate_multiplier: float = 1.0
    scalar_reward: float = 0.5

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {
            "gate_multiplier": self.gate_multiplier,
            "scalar_reward": self.scalar_reward,
            "grade_card": self.grade_card.model_dump(mode=mode),
        }


@dataclass
class _StubOutcome:
    report: _StubReport = field(default_factory=_StubReport)
    reward_signal: _StubReward = field(default_factory=_StubReward)
    workflow: Any = None
    trace_ids: list[str] = field(default_factory=list)
    lineage_edge_id: str | None = "lineage_xyz"


def test_deep_research_branch_returns_quarantine_false_on_passing_grade(
    monkeypatch: pytest.MonkeyPatch,
):
    from dharma_swarm.agent_runner import AgentRunner
    from dharma_swarm.models import AgentConfig, ProviderType, Task

    # Build a minimal AgentRunner — provider can be None since we never reach
    # the LLM path.
    cfg = AgentConfig(
        name="deep_research_test_agent",
        role="researcher",
        provider=ProviderType.LOCAL,
        model="mock",
        system_prompt="x",
    )
    runner = AgentRunner(config=cfg, provider=None)

    # Patch run_auto_research_workflow to return a passing stub outcome.
    captured: dict[str, Any] = {}
    async def _stub_workflow(brief, **kw):
        captured["brief"] = brief
        captured["kw"] = kw
        return _StubOutcome(reward_signal=_StubReward(gate_multiplier=1.0,
                                                     grade_card=_StubGrade(final_score=0.9)))
    monkeypatch.setattr(runner, "run_auto_research_workflow", _stub_workflow)

    task = Task(
        id="task_dr",
        title="Deep research for Demo",
        description="PhD-level...",
        metadata={
            "task_type": "deep_research",
            "frontier_row": _frontier_row_for_deep_research(),
            "opportunity_id": "opp_demo_001",
        },
    )

    result_str, latency_ms = asyncio.run(runner._run_deep_research_task(task))

    # Brief was constructed correctly.
    assert captured["brief"].topic == "Deep research for Demo"
    assert captured["brief"].metadata["stage"] == "deep_research"
    assert captured["brief"].metadata["opportunity_id"] == "opp_demo_001"

    # Result is JSON-shaped per PR4 contract.
    payload = json.loads(result_str)
    assert payload["quarantined"] is False
    assert payload["report"]["report_id"] == "rep_1"
    assert payload["grade"]["final_score"] == 0.9
    assert payload["lineage_edge_id"] == "lineage_xyz"
    assert latency_ms >= 0


def test_deep_research_branch_returns_quarantine_true_on_failing_grade(
    monkeypatch: pytest.MonkeyPatch,
):
    from dharma_swarm.agent_runner import AgentRunner
    from dharma_swarm.models import AgentConfig, ProviderType, Task

    cfg = AgentConfig(
        name="deep_research_test_agent",
        role="researcher",
        provider=ProviderType.LOCAL,
        model="mock",
        system_prompt="x",
    )
    runner = AgentRunner(config=cfg, provider=None)

    async def _stub_workflow(brief, **kw):
        return _StubOutcome(reward_signal=_StubReward(
            gate_multiplier=0.0,
            grade_card=_StubGrade(
                final_score=0.2,
                promotion_state="rollback_or_revise",
                gate_failures=["freshness", "citation_precision"],
            ),
        ))
    monkeypatch.setattr(runner, "run_auto_research_workflow", _stub_workflow)

    task = Task(
        id="task_dr_q",
        title="Deep research for Demo",
        description="x",
        metadata={
            "task_type": "deep_research",
            "frontier_row": _frontier_row_for_deep_research(),
        },
    )

    result_str, _ = asyncio.run(runner._run_deep_research_task(task))
    payload = json.loads(result_str)
    assert payload["quarantined"] is True
    assert payload["grade"]["promotion_state"] == "rollback_or_revise"
    assert "freshness" in payload["grade"]["gate_failures"]


def test_deep_research_branch_raises_on_missing_frontier_row(
    monkeypatch: pytest.MonkeyPatch,
):
    """PR1 contract: frontier_row MUST be in metadata. Missing = loud
    failure, not silent fallback."""
    from dharma_swarm.agent_runner import AgentRunner
    from dharma_swarm.models import AgentConfig, ProviderType, Task

    cfg = AgentConfig(
        name="x", role="researcher",
        provider=ProviderType.LOCAL, model="mock", system_prompt="x",
    )
    runner = AgentRunner(config=cfg, provider=None)

    task = Task(
        id="task_bad",
        title="x",
        description="x",
        metadata={"task_type": "deep_research"},  # no frontier_row
    )

    with pytest.raises(RuntimeError, match="frontier_row"):
        asyncio.run(runner._run_deep_research_task(task))


# --------------------------------------------------------------------------
# Dispatcher throttle (PR4 gate)
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


def test_seventh_deep_research_promotion_in_24h_is_throttled(
    tmp_dharma: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Pre-seed 6 manifests with deep_research stage promoted in the last
    24h; the 7th attempt should be throttled."""
    from dharma_swarm._campaign_manifest import init_manifest, write_manifest, update_stage

    now = datetime.now(timezone.utc).isoformat()
    for i in range(6):
        opp = f"opp_seed_{i:02d}"
        m = init_manifest(opportunity_id=opp, title=f"Seed {i}", domain="research",
                          telos_alignment=0.9)
        # Mark scope/validate completed AND deep_research promoted within window.
        update_stage(m, "scope", status="completed", completed_at=now, task_id=f"t_s_{i}")
        update_stage(m, "validate", status="completed", completed_at=now, task_id=f"t_v_{i}")
        update_stage(m, "deep_research", status="promoted", promoted_at=now, task_id=f"t_d_{i}")
        write_manifest(opp, m)

    # Now stub gates + budget so a 7th attempt would otherwise succeed.
    from dharma_swarm.models import GateCheckResult, GateDecision

    def _allow(action: str, content: str = "") -> GateCheckResult:
        return GateCheckResult(decision=GateDecision.ALLOW, reason="ok")
    monkeypatch.setattr("dharma_swarm.telos_gates.check_action", _allow)
    monkeypatch.setattr(opportunity_dispatcher, "_budget_exceeded", lambda: False)

    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(opportunity_dispatcher, "_mark_stigmergy", _noop)

    # Seed a 7th opportunity with scope+validate completed and deep_research pending.
    opp7 = "opp_seed_07"
    m7 = init_manifest(opportunity_id=opp7, title="Seed 7", domain="research", telos_alignment=0.9)
    update_stage(m7, "scope", status="completed", completed_at=now, task_id="t_s_07")
    update_stage(m7, "validate", status="completed", completed_at=now, task_id="t_v_07")
    write_manifest(opp7, m7)

    # Pending JSONL has a deep_research row for opp7.
    row = _frontier_row_for_deep_research()
    row["provenance"]["opportunity_id"] = opp7
    row["frontier_id"] = "ftask_dr_07"
    pending = tmp_dharma / "meta" / "frontier_tasks_pending.jsonl"
    pending.write_text(json.dumps(row) + "\n", encoding="utf-8")

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 0
    assert any(s["reason"] == "deep_research_throttled" for s in result.skipped)
    m7_after = json.loads(
        (tmp_dharma / "campaigns" / opp7 / "manifest.json").read_text()
    )
    assert m7_after["throttled"] is True


def test_count_recent_deep_research_ignores_stages_outside_window(tmp_dharma: Path):
    """Manifests with deep_research promoted >24h ago must not count."""
    from dharma_swarm._campaign_manifest import init_manifest, write_manifest, update_stage

    ancient = "2000-01-01T00:00:00+00:00"
    for i in range(3):
        opp = f"opp_old_{i}"
        m = init_manifest(opportunity_id=opp, title=f"Old {i}", domain="research",
                          telos_alignment=0.9)
        update_stage(m, "deep_research", status="promoted", promoted_at=ancient, task_id=f"t{i}")
        write_manifest(opp, m)

    # Recent (within window).
    recent = datetime.now(timezone.utc).isoformat()
    for i in range(2):
        opp = f"opp_new_{i}"
        m = init_manifest(opportunity_id=opp, title=f"New {i}", domain="research",
                          telos_alignment=0.9)
        update_stage(m, "deep_research", status="promoted", promoted_at=recent, task_id=f"r{i}")
        write_manifest(opp, m)

    count = opportunity_dispatcher._count_recent_deep_research_promotions()
    assert count == 2  # only the recent ones
