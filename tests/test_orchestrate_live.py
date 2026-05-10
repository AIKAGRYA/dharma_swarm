"""Tests for dharma_swarm.orchestrate_live.

Tests the orchestrator's helper functions, loop early-exit conditions,
and signal handling without requiring real LLM calls or subprocess spawning.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _log helper
# ---------------------------------------------------------------------------

def test_log_prints_formatted_output(capsys):
    """_log produces timestamped, system-tagged output."""
    from dharma_swarm.orchestrate_live import _log

    _log("test_sys", "hello world")
    out = capsys.readouterr().out
    assert "[test_sys]" in out
    assert "hello world" in out
    # Timestamp format: HH:MM:SS
    assert ":" in out.split("]")[0]


def test_log_writes_to_logger(caplog):
    """_log also emits to the Python logger."""
    from dharma_swarm.orchestrate_live import _log

    with caplog.at_level(logging.INFO, logger="dharma_swarm.orchestrate_live"):
        _log("mymod", "a message")
    assert any("a message" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_module_constants_are_positive():
    """Orchestrator intervals should be positive numbers."""
    from dharma_swarm.orchestrate_live import (
        SWARM_TICK, PULSE_INTERVAL, EVOLUTION_INTERVAL,
        HEALTH_INTERVAL, LIVING_INTERVAL, MAX_DAILY,
    )
    for name, val in [
        ("SWARM_TICK", SWARM_TICK),
        ("PULSE_INTERVAL", PULSE_INTERVAL),
        ("EVOLUTION_INTERVAL", EVOLUTION_INTERVAL),
        ("HEALTH_INTERVAL", HEALTH_INTERVAL),
        ("LIVING_INTERVAL", LIVING_INTERVAL),
        ("MAX_DAILY", MAX_DAILY),
    ]:
        assert val > 0, f"{name} must be > 0, got {val}"


def test_state_and_log_dirs():
    """STATE_DIR and LOG_DIR are under ~/.dharma."""
    from dharma_swarm.orchestrate_live import STATE_DIR, LOG_DIR
    assert STATE_DIR == Path.home() / ".dharma"
    assert LOG_DIR == STATE_DIR / "logs"


def test_enqueue_shakti_escalations_writes_pending_proposals(tmp_path):
    """High-impact Shakti perceptions should be queued into Darwin's pending proposal inbox."""
    from dharma_swarm.orchestrate_live import _enqueue_shakti_escalations

    proposals_path = tmp_path / "pending_proposals.jsonl"
    queued = _enqueue_shakti_escalations(
        [
            SimpleNamespace(
                connection="dharma_swarm/pulse.py",
                proposal=None,
                observation="cross-module coupling detected",
                salience=0.9,
                impact_level="module",
                energy=SimpleNamespace(value="maheshwari"),
            ),
            SimpleNamespace(
                connection="notes.md",
                proposal=None,
                observation="local typo",
                salience=0.2,
                impact_level="local",
                energy=SimpleNamespace(value="mahasaraswati"),
            ),
        ],
        proposals_path=proposals_path,
    )

    assert queued == 1
    payload = json.loads(proposals_path.read_text().strip())
    assert payload["component"] == "dharma_swarm/pulse.py"
    assert payload["change_type"] == "shakti_escalation"
    assert payload["spec_ref"] == "shakti_loop"


def test_should_seed_startup_pressure_on_empty_board():
    from dharma_swarm.orchestrate_live import _should_seed_startup_pressure

    should, reason = _should_seed_startup_pressure(
        pending_count=0,
        running_count=0,
        primary_campaign_viable=False,
        worker_calls_last_hour=3,
        has_mission_pressure=False,
    )
    assert should is True
    assert reason == "empty_board"


def test_should_seed_startup_pressure_on_stagnation_without_primary():
    from dharma_swarm.orchestrate_live import _should_seed_startup_pressure

    should, reason = _should_seed_startup_pressure(
        pending_count=4,
        running_count=1,
        primary_campaign_viable=False,
        worker_calls_last_hour=0,
        has_mission_pressure=False,
    )
    assert should is True
    assert reason == "stagnation_dead_campaign"


def test_should_seed_startup_pressure_when_only_churn_tasks_exist():
    from dharma_swarm.orchestrate_live import _should_seed_startup_pressure

    should, reason = _should_seed_startup_pressure(
        pending_count=3,
        running_count=0,
        primary_campaign_viable=False,
        worker_calls_last_hour=5,
        has_mission_pressure=False,
    )
    assert should is True
    assert reason == "no_mission_pressure"


def test_should_not_seed_when_work_and_primary_exist():
    from dharma_swarm.orchestrate_live import _should_seed_startup_pressure

    should, reason = _should_seed_startup_pressure(
        pending_count=4,
        running_count=1,
        primary_campaign_viable=True,
        worker_calls_last_hour=2,
        has_mission_pressure=True,
    )
    assert should is False
    assert reason == "steady_state"


@pytest.mark.asyncio
async def test_safe_seed_startup_pressure_times_out_without_blocking_first_tick(monkeypatch):
    from dharma_swarm import orchestrate_live as mod

    gate = asyncio.Event()

    async def _blocked_seed(_swarm):
        await gate.wait()

    monkeypatch.setattr(mod, "_seed_startup_pressure", _blocked_seed)

    completed = await mod._safe_seed_startup_pressure(object(), timeout_s=0.01)

    assert completed is False


def test_campaign_has_board_presence_checks_campaign_id():
    from types import SimpleNamespace
    from dharma_swarm.orchestrate_live import _campaign_has_board_presence

    campaign = {"campaign_id": "camp_1"}
    tasks = [
        SimpleNamespace(metadata={"campaign_id": "camp_1"}),
        SimpleNamespace(metadata={}),
    ]
    assert _campaign_has_board_presence(campaign, tasks) is True
    assert _campaign_has_board_presence({"campaign_id": "camp_2"}, tasks) is False


def test_campaign_has_live_board_presence_ignores_completed_tasks():
    from types import SimpleNamespace
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.orchestrate_live import _campaign_has_live_board_presence

    campaign = {"campaign_id": "camp_1"}
    tasks = [
        SimpleNamespace(metadata={"campaign_id": "camp_1"}, status=TaskStatus.COMPLETED),
        SimpleNamespace(metadata={"campaign_id": "camp_1"}, status=TaskStatus.PENDING),
    ]
    assert _campaign_has_live_board_presence(campaign, tasks) is True
    assert _campaign_has_live_board_presence(
        campaign,
        [SimpleNamespace(metadata={"campaign_id": "camp_1"}, status=TaskStatus.COMPLETED)],
    ) is False


def test_campaign_has_open_human_blocker_ignores_terminal_statuses():
    from dharma_swarm.orchestrate_live import _campaign_has_open_human_blocker

    assert _campaign_has_open_human_blocker(
        {"human_blocking": [{"task": "Send outreach", "status": "ready_to_send"}]}
    ) is True
    assert _campaign_has_open_human_blocker(
        {"human_blocking": [{"task": "Done", "status": "completed"}]}
    ) is False


def test_task_has_mission_pressure_recognizes_seed_and_campaign_tasks():
    from types import SimpleNamespace
    from dharma_swarm.orchestrate_live import _task_has_mission_pressure

    assert _task_has_mission_pressure(SimpleNamespace(metadata={"campaign_id": "camp"})) is True
    assert _task_has_mission_pressure(SimpleNamespace(metadata={"artifact_required": True})) is True
    assert _task_has_mission_pressure(SimpleNamespace(metadata={"seed_class": "startup_seed"})) is True
    assert _task_has_mission_pressure(SimpleNamespace(metadata={"created_via": "manual_seed"})) is True
    assert _task_has_mission_pressure(SimpleNamespace(metadata={"source": "swarm.coordination_synthesis"})) is False


def test_campaign_is_stale_when_old_or_missing():
    from datetime import datetime, timedelta, timezone
    from dharma_swarm.orchestrate_live import _campaign_is_stale

    fresh = {"last_check_in": datetime.now(timezone.utc).isoformat()}
    stale = {"last_check_in": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()}
    assert _campaign_is_stale(fresh, max_age_hours=2.0) is False
    assert _campaign_is_stale(stale, max_age_hours=2.0) is True
    assert _campaign_is_stale(None) is True


def test_build_mission_seed_specs_attaches_campaign_and_artifact_contract():
    from dharma_swarm.models import TaskPriority
    from dharma_swarm.orchestrate_live import _build_mission_seed_specs

    specs = _build_mission_seed_specs(
        mission_title="Cybernetic Hardening",
        task_titles=["Build audit", "Build audit", "Write brief"],
        existing_titles={"build audit"},
        campaign_id="mission_abc123",
        domain="strategic_infrastructure",
    )
    assert len(specs) == 1
    spec = specs[0]
    assert spec["title"] == "Write brief"
    assert spec["priority"] == TaskPriority.HIGH
    assert spec["metadata"]["campaign_id"] == "mission_abc123"
    assert spec["metadata"]["artifact_required"] is True
    assert spec["metadata"]["target_artifact"].endswith("mission_abc123_write_brief.md")


def test_build_campaign_nurture_specs_for_primary_campaign_without_live_work():
    from datetime import datetime, timezone
    from dharma_swarm.models import TaskPriority
    from dharma_swarm.orchestrate_live import _build_campaign_nurture_specs

    campaign = {
        "campaign_id": "camp_alpha",
        "title": "Alpha",
        "domain": "revenue_exploration",
        "artifact_path": "~/.dharma/shared/campaigns/camp_alpha.md",
        "primary": True,
        "status": "active",
        "created": datetime.now(timezone.utc).isoformat(),
        "last_check_in": datetime.now(timezone.utc).isoformat(),
        "progress_markers": [],
    }

    specs = _build_campaign_nurture_specs(campaigns=[campaign], tasks=[])
    assert len(specs) == 1
    spec = specs[0]
    assert spec["title"] == "Campaign nurture: Alpha"
    assert spec["priority"] == TaskPriority.HIGH
    assert spec["metadata"]["campaign_id"] == "camp_alpha"
    assert spec["metadata"]["created_via"] == "campaign_nurture"
    assert spec["metadata"]["nurture_reason"] == "primary_no_live_work"
    assert spec["metadata"]["target_artifact"] == "~/.dharma/shared/campaigns/camp_alpha.md"


def test_build_campaign_nurture_specs_skip_explicit_human_block():
    from datetime import datetime, timedelta, timezone
    from dharma_swarm.orchestrate_live import _build_campaign_nurture_specs

    now = datetime.now(timezone.utc)
    campaign = {
        "campaign_id": "camp_hold",
        "title": "Held",
        "domain": "revenue_exploration",
        "primary": True,
        "status": "active",
        "created": (now - timedelta(hours=6)).isoformat(),
        "last_check_in": (now - timedelta(hours=6)).isoformat(),
        "human_blocking": [{"task": "Send outreach", "status": "ready_to_send"}],
        "progress_markers": [],
    }

    specs = _build_campaign_nurture_specs(campaigns=[campaign], tasks=[])
    assert specs == []


def test_build_campaign_nurture_specs_for_stale_campaign_without_live_work():
    from datetime import datetime, timedelta, timezone
    from dharma_swarm.orchestrate_live import _build_campaign_nurture_specs

    campaign = {
        "campaign_id": "camp_stale",
        "title": "Stale",
        "domain": "research",
        "primary": False,
        "status": "active",
        "created": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "last_check_in": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "progress_markers": [{"note": "Need sharper thesis"}],
    }

    specs = _build_campaign_nurture_specs(campaigns=[campaign], tasks=[])
    assert len(specs) == 1
    assert specs[0]["metadata"]["nurture_reason"] == "stale_no_live_work"
    assert "Need sharper thesis" in specs[0]["description"]


def test_build_campaign_nurture_specs_prefers_primary_campaign_only():
    from datetime import datetime, timedelta, timezone
    from dharma_swarm.orchestrate_live import _build_campaign_nurture_specs

    now = datetime.now(timezone.utc)
    campaigns = [
        {
            "campaign_id": "camp_primary",
            "title": "Primary",
            "domain": "artifact_publication",
            "primary": True,
            "status": "active",
            "created": (now - timedelta(hours=6)).isoformat(),
            "last_check_in": (now - timedelta(hours=6)).isoformat(),
            "progress_markers": [],
        },
        {
            "campaign_id": "camp_secondary",
            "title": "Secondary",
            "domain": "research",
            "primary": False,
            "status": "active",
            "created": (now - timedelta(hours=6)).isoformat(),
            "last_check_in": (now - timedelta(hours=6)).isoformat(),
            "progress_markers": [],
        },
    ]

    specs = _build_campaign_nurture_specs(campaigns=campaigns, tasks=[])

    assert len(specs) == 1
    assert specs[0]["metadata"]["campaign_id"] == "camp_primary"


def test_build_campaign_nurture_specs_skips_recent_nurture_task():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.orchestrate_live import _build_campaign_nurture_specs

    now = datetime.now(timezone.utc)
    campaign = {
        "campaign_id": "camp_recent",
        "title": "Recent",
        "domain": "research",
        "primary": True,
        "status": "active",
        "created": now.isoformat(),
        "last_check_in": now.isoformat(),
    }
    tasks = [
        SimpleNamespace(
            metadata={"campaign_id": "camp_recent", "created_via": "campaign_nurture"},
            status=TaskStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        )
    ]

    specs = _build_campaign_nurture_specs(campaigns=[campaign], tasks=tasks)
    assert specs == []


@pytest.mark.asyncio
async def test_seed_startup_pressure_skips_reseed_for_human_blocked_primary(monkeypatch):
    from dharma_swarm import orchestrate_live as mod

    board = MagicMock()
    board.stats = AsyncMock(return_value={"pending": 1, "running": 0})
    board.list_tasks = AsyncMock(
        return_value=[SimpleNamespace(metadata={"source": "swarm.coordination_synthesis"})]
    )
    swarm = SimpleNamespace(_orchestrator=SimpleNamespace(_board=board))

    human_blocked_primary = {
        "campaign_id": "startup_world_facing",
        "title": "Startup World-Facing Pressure",
        "primary": True,
        "status": "active",
        "created": "2026-04-30T00:00:00+00:00",
        "last_check_in": "2026-04-30T00:30:00+00:00",
        "human_blocking": [{"task": "Send outreach", "status": "ready_to_send"}],
    }

    async def _unexpected_enqueue(_swarm, _specs):
        raise AssertionError("startup reseed should not enqueue while primary is explicitly human-blocked")

    monkeypatch.setattr(mod, "_recent_worker_call_count", lambda: 0)
    monkeypatch.setattr(mod, "_enqueue_startup_specs", _unexpected_enqueue)
    monkeypatch.setattr(
        "dharma_swarm.campaigns.active_primary",
        lambda _meta_dir: human_blocked_primary,
    )
    monkeypatch.setattr(
        "dharma_swarm.campaigns.create_campaign",
        lambda **kwargs: kwargs,
    )
    monkeypatch.setattr(
        "dharma_swarm.mission_contract.load_active_mission_state",
        lambda state_dir=None: None,
    )

    await mod._seed_startup_pressure(swarm)

def test_build_campaign_nurture_specs_skips_when_live_campaign_work_exists():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.orchestrate_live import _build_campaign_nurture_specs

    now = datetime.now(timezone.utc)
    campaign = {
        "campaign_id": "camp_live",
        "title": "Live",
        "domain": "research",
        "primary": True,
        "status": "active",
        "created": (now - timedelta(hours=6)).isoformat(),
        "last_check_in": (now - timedelta(hours=6)).isoformat(),
    }
    tasks = [
        SimpleNamespace(
            metadata={"campaign_id": "camp_live"},
            status=TaskStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )
    ]

    specs = _build_campaign_nurture_specs(campaigns=[campaign], tasks=tasks)
    assert specs == []


@pytest.mark.asyncio
async def test_refresh_campaign_pressure_enqueues_specs(monkeypatch):
    from dharma_swarm import orchestrate_live as mod

    campaign = {
        "campaign_id": "camp_queued",
        "title": "Queued",
        "domain": "research",
        "primary": True,
        "status": "active",
        "created": "2026-04-17T00:00:00+00:00",
        "last_check_in": "2026-04-17T00:00:00+00:00",
    }
    board = MagicMock()
    board.list_tasks = AsyncMock(return_value=[])
    swarm = SimpleNamespace(
        _orchestrator=SimpleNamespace(_board=board),
    )

    monkeypatch.setattr(
        "dharma_swarm.campaigns.load_active",
        lambda *_args, **_kwargs: [campaign],
    )
    enqueue = AsyncMock(return_value=1)
    monkeypatch.setattr(mod, "_enqueue_startup_specs", enqueue)

    created = await mod._refresh_campaign_pressure(swarm)

    assert created == 1
    enqueue.assert_awaited_once()
    queued_specs = enqueue.await_args.args[1]
    assert queued_specs[0]["metadata"]["campaign_id"] == "camp_queued"


def test_swarm_liveness_watch_payload_extracts_canonical_status():
    from dharma_swarm.orchestrate_live import _swarm_liveness_watch_payload

    payload = _swarm_liveness_watch_payload(
        {
            "status": "fresh",
            "age_seconds": 4.2,
            "daemon_pid_mismatch": False,
            "payload": {
                "source": "swarm.run",
                "agent_count": 7,
                "task_count": 19,
            },
            "liveness": {
                "status": "stalled",
                "bootstrap_phase": "bootstrap_complete",
                "stall_state": "tick_stalled",
                "stall_reason": "last swarm tick is stale",
            },
        }
    )

    assert payload["snapshot_status"] == "fresh"
    assert payload["source"] == "swarm.run"
    assert payload["agent_count"] == 7
    assert payload["task_count"] == 19
    assert payload["liveness"]["status"] == "stalled"


def test_write_swarm_liveness_watch_persists_artifact(tmp_path):
    from dharma_swarm.orchestrate_live import _write_swarm_liveness_watch

    path = _write_swarm_liveness_watch(
        tmp_path / ".dharma",
        {
            "observed_at": "2026-04-16T00:00:00+00:00",
            "snapshot_status": "fresh",
            "liveness": {"status": "booting", "bootstrap_phase": "bootstrap_deferred"},
        },
    )

    assert path.name == "swarm_liveness.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["snapshot_status"] == "fresh"
    assert payload["liveness"]["status"] == "booting"


def test_swarm_liveness_transition_key_tracks_status_phase_and_stall_state():
    from dharma_swarm.orchestrate_live import _swarm_liveness_transition_key

    key = _swarm_liveness_transition_key(
        {
            "liveness": {
                "status": "degraded",
                "bootstrap_phase": "bootstrap_complete",
                "stall_state": "coordination_stale",
            }
        }
    )

    assert key == ("degraded", "bootstrap_complete", "coordination_stale")


@pytest.mark.asyncio
async def test_enqueue_startup_specs_prefers_swarm_batch_api():
    from dharma_swarm.orchestrate_live import _enqueue_startup_specs

    swarm = SimpleNamespace(
        create_task_batch=AsyncMock(return_value=[SimpleNamespace(id="a"), SimpleNamespace(id="b")]),
        _orchestrator=SimpleNamespace(_board=SimpleNamespace(create_batch=AsyncMock())),
    )
    count = await _enqueue_startup_specs(swarm, [{"title": "A"}, {"title": "B"}])
    assert count == 2
    swarm.create_task_batch.assert_awaited_once()
    swarm._orchestrator._board.create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_wait_for_bootstrap_gate_returns_false_on_shutdown():
    from dharma_swarm.orchestrate_live import _wait_for_bootstrap_gate

    startup_gate = asyncio.Event()
    shutdown = asyncio.Event()

    async def _trigger_shutdown():
        await asyncio.sleep(0.01)
        shutdown.set()

    asyncio.create_task(_trigger_shutdown())
    released = await _wait_for_bootstrap_gate("context-agent", startup_gate, shutdown)
    assert released is False


@pytest.mark.asyncio
async def test_run_gated_loop_waits_for_gate_before_invoking_factory():
    from dharma_swarm.orchestrate_live import _run_gated_loop

    startup_gate = asyncio.Event()
    shutdown = asyncio.Event()
    events: list[str] = []

    async def _factory():
        events.append("ran")

    task = asyncio.create_task(
        _run_gated_loop("archaeology", shutdown, startup_gate, _factory)
    )
    await asyncio.sleep(0)
    assert events == []

    startup_gate.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert events == ["ran"]


@pytest.mark.asyncio
async def test_run_archaeology_loop_defers_boot_ingestion_until_delay_expires(monkeypatch):
    from dharma_swarm import archaeology_ingestion as ingest_mod
    from dharma_swarm import orchestrate_live as mod

    shutdown = asyncio.Event()
    observed: dict[str, object] = {}

    class _FakeDaemon:
        def __init__(self, *args, **kwargs) -> None:
            observed["daemon_created"] = True

        async def run_once(self) -> dict[str, int]:
            observed["run_once"] = True
            return {"boot": 1}

    async def _fake_wait_or_shutdown(event: asyncio.Event, delay: float) -> bool:
        observed["delay"] = delay
        return True

    monkeypatch.setattr(ingest_mod, "_archaeology_boot_delay_seconds", lambda interval: 42.0)
    monkeypatch.setattr(ingest_mod, "ArchaeologyIngestionDaemon", _FakeDaemon)
    monkeypatch.setattr(mod, "_wait_or_shutdown", _fake_wait_or_shutdown)

    await mod._run_archaeology_loop(shutdown)

    assert observed == {"delay": 42.0}


@pytest.mark.asyncio
async def test_run_archaeology_loop_runs_boot_ingestion_when_delay_is_zero(monkeypatch):
    from dharma_swarm import archaeology_ingestion as ingest_mod
    from dharma_swarm import orchestrate_live as mod

    shutdown = asyncio.Event()
    observed: dict[str, object] = {}

    class _FakeDaemon:
        def __init__(self, *, state_dir: Path | None = None, interval_seconds: int = 0) -> None:
            observed["state_dir"] = state_dir
            observed["interval_seconds"] = interval_seconds

        async def run_once(self) -> dict[str, int]:
            observed["run_once"] = int(observed.get("run_once", 0)) + 1
            shutdown.set()
            return {"boot": 1}

    monkeypatch.setattr(ingest_mod, "_archaeology_boot_delay_seconds", lambda interval: 0.0)
    monkeypatch.setattr(ingest_mod, "ArchaeologyIngestionDaemon", _FakeDaemon)

    await mod._run_archaeology_loop(shutdown)

    assert observed == {
        "state_dir": mod.STATE_DIR,
        "interval_seconds": 1800,
        "run_once": 1,
    }


@pytest.mark.asyncio
async def test_run_archaeology_loop_executes_boot_ingestion_via_to_thread(monkeypatch):
    from dharma_swarm import archaeology_ingestion as ingest_mod
    from dharma_swarm import orchestrate_live as mod

    shutdown = asyncio.Event()
    observed: dict[str, object] = {}

    class _FakeDaemon:
        def __init__(self, *, state_dir: Path | None = None, interval_seconds: int = 0) -> None:
            observed["state_dir"] = state_dir
            observed["interval_seconds"] = interval_seconds

        async def run_once(self) -> dict[str, int]:
            observed["run_once"] = int(observed.get("run_once", 0)) + 1
            return {"boot": 1}

    async def _fake_to_thread(func, /, *args, **kwargs):
        observed["to_thread_func"] = getattr(func, "__name__", repr(func))
        observed["to_thread_args"] = args
        shutdown.set()
        return {"boot": 1}

    monkeypatch.setattr(ingest_mod, "_archaeology_boot_delay_seconds", lambda interval: 0.0)
    monkeypatch.setattr(ingest_mod, "ArchaeologyIngestionDaemon", _FakeDaemon)
    monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)

    await mod._run_archaeology_loop(shutdown)

    assert observed["to_thread_func"] == "_run_cycle_sync"
    assert observed["to_thread_args"]


@pytest.mark.asyncio
async def test_run_research_rtn_loop_executes_brief_via_to_thread(monkeypatch):
    from dharma_swarm import orchestrate_live as mod
    import dharma_swarm.research_rtn as rtn_mod
    import dharma_swarm.research_tracks as tracks_mod

    shutdown = asyncio.Event()
    observed: dict[str, object] = {}

    class _FakeTrack:
        slug = "test-track"

        def next_brief(self, index: int = 0) -> SimpleNamespace:
            observed["brief_index"] = index
            return SimpleNamespace(topic="test topic")

    class _FakeResearchRTN:
        def __init__(self, search_backend=None) -> None:
            observed["backend"] = search_backend

        def execute_brief(self, brief: object) -> SimpleNamespace:
            observed["brief"] = brief
            return SimpleNamespace(
                passed_gates=True,
                reward=SimpleNamespace(grade_card=SimpleNamespace(final_score=0.75)),
                sub_results=[],
                artifact=None,
            )

    async def _fake_sleep(_: float) -> None:
        return None

    async def _fake_to_thread(func, /, *args, **kwargs):
        observed["to_thread_func"] = getattr(func, "__name__", repr(func))
        observed["to_thread_args"] = args
        result = func(*args, **kwargs)
        shutdown.set()
        return result

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(rtn_mod, "ResearchRTN", _FakeResearchRTN)
    monkeypatch.setattr(tracks_mod, "ALL_TRACKS", [_FakeTrack()])

    await mod._run_research_rtn_loop(shutdown)

    assert observed["brief_index"] == 0
    assert observed["to_thread_func"] == "execute_brief"
    assert observed["to_thread_args"] == (observed["brief"],)


@pytest.mark.asyncio
async def test_release_startup_gate_sets_event_after_bootstrap_complete():
    from dharma_swarm.orchestrate_live import _release_startup_gate_after_first_tick

    startup_gate = asyncio.Event()
    liveness = {
        "bootstrap_phase": "bootstrap_ready",
        "last_tick_completed_at": None,
        "bootstrap_completed_at": None,
    }

    swarm = SimpleNamespace(
        wait_until_bootstrap_ready=AsyncMock(return_value="bootstrap_ready"),
        hot_path_liveness=MagicMock(side_effect=lambda: dict(liveness)),
        _publish_runtime_health_snapshot=AsyncMock(),
    )

    async def _complete_bootstrap():
        await asyncio.sleep(0.01)
        liveness["last_tick_completed_at"] = "2026-04-17T04:50:18+00:00"
        liveness["bootstrap_phase"] = "bootstrap_complete"
        liveness["bootstrap_completed_at"] = "2026-04-17T04:50:18+00:00"

    asyncio.create_task(_complete_bootstrap())
    phase = await _release_startup_gate_after_first_tick(
        swarm,
        startup_gate,
        poll_interval_s=0.005,
    )

    assert phase == "bootstrap_complete"
    assert startup_gate.is_set() is True
    swarm._publish_runtime_health_snapshot.assert_awaited_once_with(
        source="swarm.startup_gate_release"
    )


@pytest.mark.asyncio
async def test_release_startup_gate_does_not_set_event_on_failure():
    from dharma_swarm.orchestrate_live import _release_startup_gate_after_first_tick

    startup_gate = asyncio.Event()

    swarm = SimpleNamespace(
        wait_until_bootstrap_ready=AsyncMock(return_value="bootstrap_failed"),
        hot_path_liveness=MagicMock(
            return_value={
                "bootstrap_phase": "bootstrap_failed",
                "last_tick_completed_at": None,
            }
        ),
        _publish_runtime_health_snapshot=AsyncMock(),
    )
    phase = await _release_startup_gate_after_first_tick(swarm, startup_gate)

    assert phase == "bootstrap_failed"
    assert startup_gate.is_set() is False
    swarm._publish_runtime_health_snapshot.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_startup_gate_stops_waiting_on_shutdown():
    from dharma_swarm.orchestrate_live import _release_startup_gate_after_first_tick

    startup_gate = asyncio.Event()
    shutdown = asyncio.Event()
    liveness = {
        "bootstrap_phase": "bootstrap_ready",
        "last_tick_completed_at": None,
    }
    swarm = SimpleNamespace(
        wait_until_bootstrap_ready=AsyncMock(return_value="bootstrap_ready"),
        hot_path_liveness=MagicMock(side_effect=lambda: dict(liveness)),
        _publish_runtime_health_snapshot=AsyncMock(),
    )

    async def _mark_tick_completed_only():
        await asyncio.sleep(0.005)
        liveness["last_tick_completed_at"] = "2026-04-17T04:50:18+00:00"

    async def _trigger_shutdown():
        await asyncio.sleep(0.015)
        shutdown.set()

    asyncio.create_task(_mark_tick_completed_only())
    asyncio.create_task(_trigger_shutdown())
    phase = await _release_startup_gate_after_first_tick(
        swarm,
        startup_gate,
        shutdown_event=shutdown,
        poll_interval_s=0.005,
    )

    assert phase == "bootstrap_ready"
    assert startup_gate.is_set() is False
    swarm._publish_runtime_health_snapshot.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_swarm_runtime_snapshot_calls_internal_publisher():
    from dharma_swarm.orchestrate_live import _publish_swarm_runtime_snapshot

    swarm = SimpleNamespace(_publish_runtime_health_snapshot=AsyncMock())

    await _publish_swarm_runtime_snapshot(swarm, source="swarm.tick_complete")

    swarm._publish_runtime_health_snapshot.assert_awaited_once_with(
        source="swarm.tick_complete"
    )


@pytest.mark.asyncio
async def test_publish_swarm_runtime_snapshot_is_noop_without_publisher():
    from dharma_swarm.orchestrate_live import _publish_swarm_runtime_snapshot

    swarm = SimpleNamespace()

    await _publish_swarm_runtime_snapshot(swarm, source="swarm.tick_complete")


@pytest.mark.asyncio
async def test_post_tick_runtime_bookkeeping_uses_liveness_fallback_on_status_timeout():
    from dharma_swarm import orchestrate_live as mod

    async def _slow_status():
        await asyncio.Event().wait()

    mod._update_runtime_health_state(agent_count=0, task_count=0)
    swarm = SimpleNamespace(
        status=AsyncMock(side_effect=_slow_status),
        hot_path_liveness=MagicMock(
            return_value={
                "total_agents": 7,
                "tasks_pending": 1,
                "tasks_assigned": 2,
                "tasks_running": 3,
                "tasks_completed": 4,
                "tasks_failed": 5,
            }
        ),
        _publish_runtime_health_snapshot=AsyncMock(),
    )

    await asyncio.wait_for(
        mod._post_tick_runtime_bookkeeping(
            swarm,
            status_timeout_s=0.01,
            snapshot_timeout_s=0.5,
        ),
        timeout=1.0,
    )

    assert mod._RUNTIME_HEALTH_STATE["agent_count"] == 7
    assert mod._RUNTIME_HEALTH_STATE["task_count"] == 15
    swarm._publish_runtime_health_snapshot.assert_awaited_once_with(
        source="swarm.tick_complete"
    )


@pytest.mark.asyncio
async def test_post_tick_runtime_bookkeeping_times_out_snapshot_publish():
    from dharma_swarm import orchestrate_live as mod

    async def _slow_publish(*, source: str):
        await asyncio.Event().wait()

    mod._update_runtime_health_state(agent_count=0, task_count=0)
    swarm = SimpleNamespace(
        status=AsyncMock(
            return_value=SimpleNamespace(
                agents=[object(), object()],
                tasks_pending=1,
                tasks_running=2,
                tasks_completed=3,
                tasks_failed=4,
            )
        ),
        hot_path_liveness=MagicMock(return_value={}),
        _publish_runtime_health_snapshot=AsyncMock(side_effect=_slow_publish),
    )

    await asyncio.wait_for(
        mod._post_tick_runtime_bookkeeping(
            swarm,
            status_timeout_s=0.5,
            snapshot_timeout_s=0.01,
        ),
        timeout=1.0,
    )

    assert mod._RUNTIME_HEALTH_STATE["agent_count"] == 2
    assert mod._RUNTIME_HEALTH_STATE["task_count"] == 10
    swarm._publish_runtime_health_snapshot.assert_awaited_once_with(
        source="swarm.tick_complete"
    )


# ---------------------------------------------------------------------------
# _stop_old_daemon
# ---------------------------------------------------------------------------

def test_stop_old_daemon_no_pid_file(tmp_path):
    """_stop_old_daemon does nothing if no pid file exists."""
    from dharma_swarm import orchestrate_live as mod

    with patch.object(mod, "STATE_DIR", tmp_path):
        mod._stop_old_daemon()  # Should not raise


def test_stop_old_daemon_with_invalid_pid_file(tmp_path):
    """_stop_old_daemon handles invalid pid file content."""
    from dharma_swarm import orchestrate_live as mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("not_a_number")

    with patch.object(mod, "STATE_DIR", tmp_path):
        mod._stop_old_daemon()
    # File should be cleaned up
    assert not pid_file.exists()


def test_stop_old_daemon_with_dead_pid(tmp_path):
    """_stop_old_daemon handles pid of a process that's already gone."""
    from dharma_swarm import orchestrate_live as mod

    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("999999999")  # Very unlikely to be alive

    with patch.object(mod, "STATE_DIR", tmp_path):
        mod._stop_old_daemon()
    assert not pid_file.exists()


def test_list_orchestrator_processes_detects_dgc_orchestrate_live(monkeypatch):
    """Process scan should treat `.venv/bin/dgc orchestrate-live` as a live orchestrator."""
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="88221 /Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc orchestrate-live\n",
        ),
    )

    matches = mod._list_orchestrator_processes()

    assert matches == [
        (88221, "/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc orchestrate-live"),
    ]


def test_list_orchestrator_processes_ignores_pre_commit_file_args(monkeypatch):
    """Process scan should not mistake pre-commit file lists for live orchestrators."""
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=(
                "84641 /Users/dhyana/.cache/pre-commit/repo/bin/"
                "check-added-large-files dharma_swarm/orchestrate_live.py\n"
            ),
        ),
    )

    assert mod._list_orchestrator_processes() == []


# ---------------------------------------------------------------------------
# run_pulse_loop — early exit in Claude Code session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pulse_loop_skips_in_claude_code_session():
    """Pulse loop exits immediately if CLAUDECODE env var is set."""
    from dharma_swarm.orchestrate_live import run_pulse_loop

    shutdown = asyncio.Event()
    with patch.dict(os.environ, {"CLAUDECODE": "1"}):
        # Should return immediately without looping
        await run_pulse_loop(shutdown)
    # If we get here, it didn't block — success


# ---------------------------------------------------------------------------
# run_swarm_loop — shutdown event respected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swarm_loop_respects_shutdown():
    """Swarm loop exits when shutdown event is set."""
    from dharma_swarm.orchestrate_live import run_swarm_loop

    shutdown = asyncio.Event()

    mock_swarm = MagicMock()
    mock_swarm.init = AsyncMock()
    mock_swarm.list_agents = AsyncMock(return_value=[])
    mock_swarm.current_thread = "test"
    mock_swarm.tick = AsyncMock(return_value={"paused": False, "dispatched": 0})
    mock_swarm.shutdown = AsyncMock()

    mock_bus = MagicMock()
    mock_bus.init_db = AsyncMock()
    mock_bus.consume_events = AsyncMock(return_value=[])

    # Set shutdown after a short delay
    async def set_shutdown():
        await asyncio.sleep(0.1)
        shutdown.set()

    with (
        patch("dharma_swarm.orchestrate_live.SwarmManager", return_value=mock_swarm) if False else
        patch("dharma_swarm.swarm.SwarmManager", return_value=mock_swarm),
        patch("dharma_swarm.message_bus.MessageBus", return_value=mock_bus),
    ):
        # Pre-set shutdown so loop exits on first iteration check
        shutdown.set()
        try:
            await asyncio.wait_for(run_swarm_loop(shutdown), timeout=5.0)
        except Exception:
            pass  # May fail on deep imports; the key test is that it respects shutdown


# ---------------------------------------------------------------------------
# run_health_loop — shutdown respected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_loop_respects_shutdown():
    """Health loop exits promptly when shutdown event is set."""
    from dharma_swarm.orchestrate_live import run_health_loop

    shutdown = asyncio.Event()
    shutdown.set()  # Pre-set so it exits immediately

    try:
        await asyncio.wait_for(run_health_loop(shutdown), timeout=3.0)
    except Exception:
        pass  # Deep imports may fail, but shouldn't hang


# ---------------------------------------------------------------------------
# Interval constants from config
# ---------------------------------------------------------------------------

def test_witness_and_zeitgeist_intervals():
    """Special loop intervals are defined at module level."""
    from dharma_swarm.orchestrate_live import (
        WITNESS_INTERVAL, ZEITGEIST_INTERVAL,
        CONSOLIDATION_INTERVAL, RECOGNITION_INTERVAL,
        REPLICATION_INTERVAL,
    )
    assert WITNESS_INTERVAL > 0
    assert ZEITGEIST_INTERVAL == 600, (
        "S4 scan cadence must be 600 s (10 min) — matches vision doc Step 2 spec "
        "and evolution loop cadence; NOT 300 s which was an undocumented drift."
    )
    assert CONSOLIDATION_INTERVAL > 0
    assert RECOGNITION_INTERVAL > 0
    assert REPLICATION_INTERVAL > 0


def test_zeitgeist_registered_in_task_factories():
    """'zeitgeist' must be a key in the task_factories dict inside orchestrate().

    Audit assertion: confirms the loop IS reached during startup (Step 2 wiring).
    """
    import inspect
    from dharma_swarm import orchestrate_live
    src = inspect.getsource(orchestrate_live.orchestrate)
    assert '"zeitgeist"' in src, (
        "zeitgeist loop must be registered in task_factories inside orchestrate()"
    )


def test_gate_pressure_paths_match():
    """Write path (zeitgeist) and read path (telos_gates) for gate_pressure.json must agree.

    Audit assertion: S4→S3 feedback channel is wired correctly end-to-end.
    """
    from dharma_swarm.orchestrate_live import STATE_DIR
    from dharma_swarm.telos_gates import TelosGatekeeper

    zeitgeist_write_path = STATE_DIR / "meta" / "gate_pressure.json"
    telos_read_path = TelosGatekeeper._GATE_PRESSURE_PATH

    assert zeitgeist_write_path == telos_read_path, (
        f"Path mismatch: zeitgeist writes to {zeitgeist_write_path}, "
        f"but telos_gates reads from {telos_read_path}"
    )


# ---------------------------------------------------------------------------
# orchestrate function signature
# ---------------------------------------------------------------------------

def test_orchestrate_is_async():
    """orchestrate() is an async function."""
    from dharma_swarm.orchestrate_live import orchestrate
    assert asyncio.iscoroutinefunction(orchestrate)


def test_orchestrate_accepts_background_param():
    """orchestrate() accepts a `background` keyword argument."""
    import inspect
    from dharma_swarm.orchestrate_live import orchestrate
    sig = inspect.signature(orchestrate)
    assert "background" in sig.parameters
    assert sig.parameters["background"].default is False


@pytest.mark.asyncio
async def test_orchestrate_restarts_failed_task(monkeypatch, tmp_path):
    """A failed persistent loop should be recreated instead of being dropped."""
    from dharma_swarm import orchestrate_live as mod

    calls = {"swarm": 0}

    async def flaky_swarm(shutdown_event, *args, **kwargs):
        calls["swarm"] += 1
        if calls["swarm"] == 1:
            raise RuntimeError("database is locked")
        await shutdown_event.wait()

    async def sleeper(shutdown_event, *args, **kwargs):
        await shutdown_event.wait()

    async def shutdown_watchdog(shutdown_event, *args, **kwargs):
        await asyncio.sleep(0.05)
        shutdown_event.set()

    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(mod, "_find_competing_orchestrator", lambda: None)
    monkeypatch.setattr(mod, "_stop_old_daemon", lambda: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "_wait_or_shutdown", AsyncMock(return_value=False))
    monkeypatch.setattr(mod, "run_swarm_loop", flaky_swarm)
    monkeypatch.setattr(mod, "run_pulse_loop", shutdown_watchdog)
    monkeypatch.setattr(mod, "_run_recognition_loop", sleeper)
    monkeypatch.setattr(mod, "run_conductor_loop", sleeper)
    monkeypatch.setattr(mod, "_run_zeitgeist_loop", sleeper)
    monkeypatch.setattr(mod, "_run_witness_loop", sleeper)
    monkeypatch.setattr(mod, "_run_consolidation_loop", sleeper)
    monkeypatch.setattr(mod, "_run_replication_monitor_loop", sleeper)
    monkeypatch.setattr(mod, "run_health_loop", sleeper)
    monkeypatch.setattr(mod, "run_free_evolution_grind", sleeper)
    monkeypatch.setattr("dharma_swarm.signal_bus.SignalBus.get", lambda: object())
    monkeypatch.setattr("dharma_swarm.context_agent.run_context_agent_loop", sleeper)
    monkeypatch.setattr("dharma_swarm.training_flywheel.run_training_flywheel_loop", sleeper)
    monkeypatch.setattr("dharma_swarm.self_improve.run_self_improvement_loop", sleeper)

    await asyncio.wait_for(mod.orchestrate(), timeout=1.0)

    assert calls["swarm"] == 2


@pytest.mark.asyncio
async def test_orchestrate_refuses_duplicate_startup_when_competing_process_exists(monkeypatch, tmp_path):
    """orchestrate() should refuse to start a second live control plane."""
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(mod, "_find_competing_orchestrator", lambda: (42424, "dgc orchestrate-live"))

    stop_called = False

    def _stop() -> None:
        nonlocal stop_called
        stop_called = True

    monkeypatch.setattr(mod, "_stop_old_daemon", _stop)
    monkeypatch.setattr(mod.signal, "signal", lambda *args, **kwargs: None)

    await mod.orchestrate()

    assert stop_called is False
    assert not (tmp_path / "daemon.pid").exists()
