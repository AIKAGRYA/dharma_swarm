"""Tests for the PR2 completion observer + retry semantics + validate stage.

Scope:
- observer writes scope.md from task.result to artifact_target
- observer writes validate.md after validate is promoted and completed
- observer is idempotent (re-runs don't double-write)
- retry: failed task with retry_count=0 → next_retry_at set ~1h out
- retry: failed task with retry_count=2 → abandoned
- quarantine: stays quarantined; retry_quarantined CLI clears it
- depends_on chain: validate dispatched with depends_on=[scope.task_id]
- observer never duplicates Outcome/ValueEvent (no calls to those modules)
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import _campaign_manifest, opportunity_dispatcher
from dharma_swarm.models import GateCheckResult, GateDecision, TaskStatus


# --------------------------------------------------------------------------
# Shared fixtures (same shape as PR1 tests)
# --------------------------------------------------------------------------


@pytest.fixture
def tmp_dharma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dharma_home = tmp_path / "dharma"
    meta_dir = dharma_home / "meta"
    meta_dir.mkdir(parents=True)
    witness_dir = dharma_home / "witness"
    witness_dir.mkdir(parents=True)
    campaigns = dharma_home / "campaigns"

    monkeypatch.setattr(opportunity_dispatcher, "DHARMA_HOME", dharma_home)
    monkeypatch.setattr(opportunity_dispatcher, "META_DIR", meta_dir)
    monkeypatch.setattr(opportunity_dispatcher, "PENDING_PATH", meta_dir / "frontier_tasks_pending.jsonl")
    monkeypatch.setattr(opportunity_dispatcher, "PAUSED_FLAG", meta_dir / "dispatcher_paused.flag")
    monkeypatch.setattr(opportunity_dispatcher, "LOCK_PATH", meta_dir / "dispatcher.lock")
    monkeypatch.setattr(opportunity_dispatcher, "HEALTH_PATH", meta_dir / "opportunity_dispatcher.health.json")
    monkeypatch.setattr(opportunity_dispatcher, "WITNESS_DIR", witness_dir)
    monkeypatch.setattr(opportunity_dispatcher, "TASK_BOARD_DB", dharma_home / "db" / "tasks.db")
    monkeypatch.setattr(_campaign_manifest, "CAMPAIGN_ROOT", campaigns)
    # Dispatcher imported CAMPAIGN_ROOT at module load — patch its local copy too.
    monkeypatch.setattr(opportunity_dispatcher, "CAMPAIGN_ROOT", campaigns)
    return dharma_home


def _make_row(stage: str, opp_id: str = "opp_demo_001", title_hint: str = "Demo") -> dict[str, Any]:
    title_map = {
        "scope": f"Scope: define the wedge for {title_hint}",
        "validate": f"Validate: market & telos check for {title_hint}",
        "deep_research": f"Deep research for {title_hint}",
        "capability": f"Capability for {title_hint}",
        "mvp": f"MVP for {title_hint}",
    }
    return {
        "frontier_id": f"ftask_{stage}_{opp_id}",
        "title": title_map.get(stage, f"{stage} for {title_hint}"),
        "description": f"{stage} desc for {title_hint}",
        "source": f"opportunity:{stage}",
        "verifier_type": "research_grade",
        "difficulty": "medium",
        "provenance": {
            "opportunity_id": opp_id,
            "domain": "external_revenue",
            "thesis": "wedge",
            "why_now": "demo",
            "final_score": 80.0,
            "telos_alignment": 0.95,
            "stage": stage,
        },
        "metadata": {"seed_kind": "opportunity_bootstrap", "stage": stage},
    }


def _write_pending(tmp_dharma: Path, rows: list[dict[str, Any]]) -> None:
    pending = tmp_dharma / "meta" / "frontier_tasks_pending.jsonl"
    pending.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Programmable fake task board
# --------------------------------------------------------------------------


@dataclass
class FakeTask:
    id: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_by: str = "opportunity_dispatcher"


class _ProgrammableTaskBoard:
    """Fake task_board that lets tests register tasks and their final state."""

    # Class state — reset by fixture between tests
    by_id: dict[str, FakeTask] = {}
    create_calls: list[dict[str, Any]] = []
    next_id_counter: int = 0

    def __init__(self, db_path=None):
        self._db_path = db_path

    async def init_db(self) -> None:
        return None

    async def create(self, **kwargs) -> FakeTask:
        type(self).next_id_counter += 1
        new_id = f"task_{type(self).next_id_counter:04d}"
        task = FakeTask(id=new_id, metadata=dict(kwargs.get("metadata") or {}))
        type(self).by_id[new_id] = task
        type(self).create_calls.append(dict(kwargs))
        return task

    async def get(self, task_id: str) -> FakeTask | None:
        return type(self).by_id.get(task_id)


@pytest.fixture
def fake_board(monkeypatch: pytest.MonkeyPatch):
    _ProgrammableTaskBoard.by_id = {}
    _ProgrammableTaskBoard.create_calls = []
    _ProgrammableTaskBoard.next_id_counter = 0
    import dharma_swarm.task_board as tb_mod
    monkeypatch.setattr(tb_mod, "TaskBoard", _ProgrammableTaskBoard)
    return _ProgrammableTaskBoard


@pytest.fixture
def stub_gate_allow(monkeypatch: pytest.MonkeyPatch):
    def _allow(action: str, content: str = "") -> GateCheckResult:
        return GateCheckResult(decision=GateDecision.ALLOW, reason="test ALLOW")
    monkeypatch.setattr("dharma_swarm.telos_gates.check_action", _allow)


@pytest.fixture
def stub_budget_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(opportunity_dispatcher, "_budget_exceeded", lambda: False)


@pytest.fixture
def stub_stigmergy_noop(monkeypatch: pytest.MonkeyPatch):
    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(opportunity_dispatcher, "_mark_stigmergy", _noop)
    # Also patch the observer's stigmergy import path to avoid touching real
    # state during reconciliation.
    async def _mark(*a, **kw):
        return "noop_id"
    import dharma_swarm.stigmergy as stig
    monkeypatch.setattr(stig, "leave_stigmergic_mark", _mark)


# --------------------------------------------------------------------------
# Observer: write scope.md
# --------------------------------------------------------------------------


def test_observer_writes_scope_md_from_task_result(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])

    # Promote scope, then mark the task COMPLETED with a result body.
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    promoted_id = next(iter(fake_board.by_id.keys()))
    body = "## Scope memo\n\nThe wedge is X."
    fake_board.by_id[promoted_id].status = TaskStatus.COMPLETED
    fake_board.by_id[promoted_id].result = body

    obs = asyncio.run(opportunity_dispatcher.observe_completions())

    assert len(obs.completed) == 1
    artifact = tmp_dharma / "campaigns" / "opp_demo_001" / "scope.md"
    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == body
    manifest = json.loads(
        (tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text()
    )
    assert manifest["stages"]["scope"]["status"] == "completed"
    assert manifest["stages"]["scope"]["artifact_path"] == "scope.md"


def test_observer_is_idempotent(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    promoted_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[promoted_id].status = TaskStatus.COMPLETED
    fake_board.by_id[promoted_id].result = "memo"
    asyncio.run(opportunity_dispatcher.observe_completions())
    artifact = tmp_dharma / "campaigns" / "opp_demo_001" / "scope.md"
    first_mtime = artifact.stat().st_mtime

    # Re-run the observer. Since the manifest now says "completed", it
    # should not be in the in-flight scan and the artifact must not be
    # rewritten.
    obs = asyncio.run(opportunity_dispatcher.observe_completions())
    assert len(obs.completed) == 0
    second_mtime = artifact.stat().st_mtime
    assert first_mtime == second_mtime


# --------------------------------------------------------------------------
# Validate stage promotion + depends_on chain
# --------------------------------------------------------------------------


def test_validate_dispatches_with_depends_on_after_scope_completes(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope"), _make_row("validate")])

    # First tick: promote scope (only).
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert len(fake_board.create_calls) == 1
    scope_id = fake_board.create_calls[0].get("metadata") and fake_board.create_calls[0].get("metadata", {}).get("stage") == "scope"
    scope_task_id = next(iter(fake_board.by_id.keys()))

    # Second tick (without scope completing): should NOT promote validate.
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert len(fake_board.create_calls) == 1, "validate must wait for scope completion"

    # Mark scope COMPLETED + observe → manifest.scope.status=completed.
    fake_board.by_id[scope_task_id].status = TaskStatus.COMPLETED
    fake_board.by_id[scope_task_id].result = "scope memo"
    asyncio.run(opportunity_dispatcher.observe_completions())

    # Third tick: validate now eligible → promoted with depends_on=[scope].
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    assert len(fake_board.create_calls) == 2
    validate_call = fake_board.create_calls[-1]
    assert validate_call["metadata"]["stage"] == "validate"
    assert validate_call["depends_on"] == [scope_task_id]


def test_observer_writes_validate_md(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope"), _make_row("validate")])

    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))  # promote scope
    scope_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[scope_id].status = TaskStatus.COMPLETED
    fake_board.by_id[scope_id].result = "scope memo"
    asyncio.run(opportunity_dispatcher.observe_completions())  # complete scope
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))  # promote validate

    validate_id = [k for k in fake_board.by_id.keys() if k != scope_id][0]
    fake_board.by_id[validate_id].status = TaskStatus.COMPLETED
    fake_board.by_id[validate_id].result = "validate go/no-go: GO."
    asyncio.run(opportunity_dispatcher.observe_completions())

    validate_md = tmp_dharma / "campaigns" / "opp_demo_001" / "validate.md"
    assert validate_md.exists()
    assert "validate go/no-go" in validate_md.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------


def test_first_failure_sets_next_retry_about_one_hour_out(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[task_id].status = TaskStatus.FAILED
    fake_board.by_id[task_id].result = "agent crashed"

    obs = asyncio.run(opportunity_dispatcher.observe_completions())

    assert len(obs.failed_retried) == 1
    manifest = json.loads(
        (tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text()
    )
    s = manifest["stages"]["scope"]
    assert s["status"] == "failed"
    assert s["retry_count"] == 1
    assert s["next_retry_at"] is not None
    next_retry = datetime.fromisoformat(s["next_retry_at"])
    delta = next_retry - datetime.now(timezone.utc)
    # Backoff is 1h; allow 60s slack.
    assert timedelta(seconds=3540) <= delta <= timedelta(seconds=3660)


def test_three_failures_in_a_row_abandons_stage(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[task_id].status = TaskStatus.FAILED
    fake_board.by_id[task_id].result = "agent error"

    # First failure.
    asyncio.run(opportunity_dispatcher.observe_completions())
    # Backdate next_retry_at so the dispatcher will re-promote on the next tick.
    p = tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json"
    m = json.loads(p.read_text())
    m["stages"]["scope"]["next_retry_at"] = "2000-01-01T00:00:00+00:00"
    p.write_text(json.dumps(m), encoding="utf-8")

    # Re-promote → new task → mark FAILED → observe (retry 2)
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id_2 = sorted(fake_board.by_id.keys())[-1]
    fake_board.by_id[task_id_2].status = TaskStatus.FAILED
    fake_board.by_id[task_id_2].result = "agent error 2"
    asyncio.run(opportunity_dispatcher.observe_completions())

    m = json.loads(p.read_text())
    m["stages"]["scope"]["next_retry_at"] = "2000-01-01T00:00:00+00:00"
    p.write_text(json.dumps(m), encoding="utf-8")

    # Re-promote → new task → mark FAILED → observe (retry 3 → abandon)
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id_3 = sorted(fake_board.by_id.keys())[-1]
    fake_board.by_id[task_id_3].status = TaskStatus.FAILED
    fake_board.by_id[task_id_3].result = "agent error 3"
    obs = asyncio.run(opportunity_dispatcher.observe_completions())

    assert len(obs.failed_abandoned) == 1
    m = json.loads(p.read_text())
    assert m["stages"]["scope"]["status"] == "abandoned"
    assert m["stages"]["scope"]["retry_count"] == 3


# --------------------------------------------------------------------------
# Quarantine
# --------------------------------------------------------------------------


def test_quarantined_task_result_marks_manifest_quarantined(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[task_id].status = TaskStatus.COMPLETED
    fake_board.by_id[task_id].result = json.dumps({
        "report": {"summary": "sloppy"},
        "grade": {"final_score": 0.2, "gate_failures": ["freshness"]},
        "quarantined": True,
    })

    obs = asyncio.run(opportunity_dispatcher.observe_completions())

    assert len(obs.quarantined) == 1
    manifest = json.loads(
        (tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text()
    )
    assert manifest["stages"]["scope"]["status"] == "quarantined"
    # No artifact written for quarantined.
    assert not (tmp_dharma / "campaigns" / "opp_demo_001" / "scope.md").exists()


def test_retry_quarantined_cli_clears_status(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[task_id].status = TaskStatus.COMPLETED
    fake_board.by_id[task_id].result = json.dumps({"quarantined": True})
    asyncio.run(opportunity_dispatcher.observe_completions())

    ok, msg = opportunity_dispatcher.retry_quarantined("opp_demo_001:scope")
    assert ok is True
    manifest = json.loads(
        (tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text()
    )
    assert manifest["stages"]["scope"]["status"] == "pending"
    assert manifest["stages"]["scope"]["quarantine_cleared_by"] == "cli"


def test_retry_quarantined_refuses_unknown_opp(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    ok, msg = opportunity_dispatcher.retry_quarantined("nonexistent:scope")
    assert ok is False
    assert "no manifest" in msg


def test_retry_quarantined_refuses_non_quarantined_stage(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    ok, msg = opportunity_dispatcher.retry_quarantined("opp_demo_001:scope")
    assert ok is False
    assert "not quarantined" in msg


# --------------------------------------------------------------------------
# No double-recording of Outcome / ValueEvent
# --------------------------------------------------------------------------


def test_observer_does_not_call_outcome_recorders(
    tmp_dharma: Path, fake_board, stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
    monkeypatch,
):
    """Observer must NOT touch the modules that record Outcome / ValueEvent /
    Contribution. Those are at the existing Telic Seam in agent_runner.py:2680.
    Duplicating them here would double-count economic events."""
    sentinel = {"called": False}

    # Wrap any plausible recorder. If the observer ever tries to import or
    # call these, the sentinel flips True.
    def _flip(*a, **kw):
        sentinel["called"] = True
        raise AssertionError("observer must not record Outcome/ValueEvent")

    # Best-effort interception of the canonical recorder symbols. If the
    # symbol does not exist, monkeypatch.setattr with raising=False.
    monkeypatch.setattr("dharma_swarm.agent_runner._record_outcome",
                         _flip, raising=False)
    monkeypatch.setattr("dharma_swarm.agent_runner._record_value_event",
                         _flip, raising=False)
    monkeypatch.setattr("dharma_swarm.agent_runner._record_contribution",
                         _flip, raising=False)

    _write_pending(tmp_dharma, [_make_row("scope")])
    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    task_id = next(iter(fake_board.by_id.keys()))
    fake_board.by_id[task_id].status = TaskStatus.COMPLETED
    fake_board.by_id[task_id].result = "memo"
    asyncio.run(opportunity_dispatcher.observe_completions())

    assert sentinel["called"] is False
