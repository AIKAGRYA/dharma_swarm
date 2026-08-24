"""Tests for dharma_swarm.swarm — integration tests."""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dharma_swarm.agent_constitution import AgentSpec, ConstitutionalLayer, DynamicRoster
from dharma_swarm.engine.conversation_memory import ConversationMemoryStore
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import (
    AgentRole,
    AgentState,
    AgentStatus,
    Message,
    ProviderType,
    TaskDispatch,
    TaskPriority,
    TaskStatus,
)
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.swarm import SwarmCoordinationState, SwarmManager
from dharma_swarm.telemetry_plane import (
    AgentIdentityRecord,
    TeamRosterRecord,
    TelemetryPlaneStore,
)
from dharma_swarm.runtime_artifacts import dgc_health_snapshot_summary


# startup_crew auto-spawns agents and seed tasks on init.
# Count is dynamic: skill discovery may override DEFAULT_CREW.
def _expected_agent_count() -> int:
    from dharma_swarm.startup_crew import _crew_from_skills, DEFAULT_CREW
    crew = _crew_from_skills() or DEFAULT_CREW
    return len(crew)


def _expected_seed_task_count() -> int:
    from dharma_swarm.gnani_lodestone import _GNANI_TASK_SEEDS

    return len(_GNANI_TASK_SEEDS)


_AUTO_AGENTS = _expected_agent_count()
_AUTO_TASKS = _expected_seed_task_count()


def _publish_optional_test_doubles(swarm: SwarmManager) -> None:
    """Model a successful aggregate optional-init attempt in focused tests."""
    for name in swarm._OPTIONAL_SUBSYSTEMS:
        setattr(swarm, f"_{name}", object())


@pytest.fixture(autouse=True)
def _clear_boot_mode_flags(monkeypatch):
    monkeypatch.delenv("DHARMA_FAST_BOOT", raising=False)
    monkeypatch.delenv("DHARMA_READ_ONLY_BOOT", raising=False)


def _make_dynamic_spec(name: str, **overrides: object) -> AgentSpec:
    defaults: dict[str, object] = dict(
        name=name,
        role=AgentRole.CODER,
        layer=ConstitutionalLayer.DIRECTOR,
        vsm_function="runtime specialist",
        domain="dynamic swarm specialist",
        system_prompt="You are a dynamic swarm specialist.",
        default_provider=ProviderType.OPENROUTER,
        default_model="dynamic-model",
        backup_models=[],
        constitutional_gates=["SATYA"],
        max_concurrent_workers=4,
        memory_namespace=name,
        spawn_authority=["code_worker"],
        audit_cycle_seconds=0.0,
    )
    defaults.update(overrides)
    return AgentSpec(**defaults)  # type: ignore[arg-type]


@pytest.fixture
async def swarm(tmp_path):
    s = SwarmManager(state_dir=tmp_path / ".dharma")
    await s.init()
    yield s
    await s.shutdown()


async def _init_graph_red_fast_swarm(tmp_path, monkeypatch) -> SwarmManager:
    import dharma_swarm.ecosystem_bridge as ecosystem_bridge
    import dharma_swarm.gnani_lodestone as gnani_lodestone
    import dharma_swarm.startup_crew as startup_crew
    import dharma_swarm.telos_substrate as telos_substrate

    state_dir = tmp_path / ".dharma"
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    monkeypatch.setattr(ecosystem_bridge, "update_manifest", lambda: {})

    async def failed_census(self, *, stale_only=False):
        raise RuntimeError("authority census unavailable")

    async def forbidden(*args, **kwargs):
        raise AssertionError("startup generation must remain Graph-held")

    monkeypatch.setattr(SwarmManager, "reconcile_graph_runs", failed_census)
    monkeypatch.setattr(startup_crew, "spawn_cybernetics_crew", forbidden)
    monkeypatch.setattr(startup_crew, "create_seed_tasks", forbidden)
    monkeypatch.setattr(startup_crew, "spawn_default_crew", forbidden)
    monkeypatch.setattr(telos_substrate.TelosSubstrate, "seed_all", forbidden)
    monkeypatch.setattr(gnani_lodestone.GnaniLodestone, "seed_all", forbidden)

    manager = SwarmManager(state_dir=state_dir)
    await manager.init()
    return manager


@pytest.mark.asyncio
async def test_init(swarm):
    state = await swarm.status()
    assert state.tasks_pending == _AUTO_TASKS
    assert len(state.agents) >= _AUTO_AGENTS


def test_init_graph_census_gates_stale_reaper_source_order():
    import inspect

    src = inspect.getsource(SwarmManager.init)
    reconcile = src.index("boot_report = await self.reconcile_graph_runs()")
    readiness = src.index(
        "if self._get_graph_reconciler().boot_census_succeeded"
    )
    stale_reaper = src.index("reaped = await self._reap_stale_running_tasks()")
    startup_components = src.index("startup_components = {")
    startup_backfill = src.index(
        "startup_report = await self._backfill_graph_held_startup()"
    )
    deferred_startup = src.index("self._complete_deferred_startup()")

    assert reconcile < readiness < stale_reaper
    assert "graph_reconciler.invalidate_boot_census()" in src[
        reconcile:readiness
    ]
    assert stale_reaper < startup_components < startup_backfill
    assert src.rfind(
        "if graph_reconciler.boot_census_succeeded:",
        startup_components,
        startup_backfill,
    ) > startup_components
    assert "seed_all(" not in src
    assert "graph_reconciler.boot_census_succeeded" in src[
        startup_backfill:deferred_startup
    ]

    backfill_src = inspect.getsource(SwarmManager._backfill_graph_held_startup)
    graph_guard = backfill_src.index(
        "if not graph_reconciler.boot_census_succeeded"
    )
    telos = backfill_src.index('("telos_substrate"')
    gnani = backfill_src.index('("gnani_lodestone"')
    assert graph_guard < telos < gnani


@pytest.mark.asyncio
async def test_init_failed_census_holds_crews_and_seed_generation(
    tmp_path,
    monkeypatch,
):
    swarm = await _init_graph_red_fast_swarm(tmp_path, monkeypatch)
    try:
        assert swarm._get_graph_reconciler().boot_census_succeeded is False
        assert swarm._startup_background_task is None
        assert swarm._startup_backfill_pending_components == {
            "telos_substrate",
            "gnani_lodestone",
            "cybernetics_crew",
            "seed_tasks",
            "default_crew",
            "optional_subsystems",
        }
        assert await swarm.list_agents() == []
        assert (await swarm._task_board.stats()).get("pending", 0) == 0
    finally:
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_red_boot_green_concurrent_ticks_backfill_startup_exactly_once(
    tmp_path,
    monkeypatch,
):
    import dharma_swarm.gnani_lodestone as gnani_lodestone
    import dharma_swarm.startup_crew as startup_crew
    import dharma_swarm.telos_substrate as telos_substrate

    swarm = await _init_graph_red_fast_swarm(tmp_path, monkeypatch)
    graph_reconciler = swarm._get_graph_reconciler()
    calls = {
        "telos_substrate": 0,
        "gnani_lodestone": 0,
        "cybernetics_crew": 0,
        "seed_tasks": 0,
        "default_crew": 0,
        "optional_subsystems": 0,
    }

    async def seed_telos(self):
        calls["telos_substrate"] += 1
        return {"seeded": True}

    async def seed_gnani(self):
        calls["gnani_lodestone"] += 1
        return {"seeded": True}

    def startup_effect(name):
        async def run(_swarm):
            calls[name] += 1
            return []

        return run

    async def init_optional():
        calls["optional_subsystems"] += 1
        _publish_optional_test_doubles(swarm)

    class EmptyReport:
        total_reconciled = 0

    async def green_reconcile(*, stale_only=False):
        graph_reconciler._boot_census_succeeded = True
        if not stale_only:
            graph_reconciler._boot_recovery_completed = True
        return EmptyReport()

    async def no_tasks(*args, **kwargs):
        return []

    async def no_activity():
        return {"dispatched": 0, "settled": 0}

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    monkeypatch.setattr(telos_substrate.TelosSubstrate, "seed_all", seed_telos)
    monkeypatch.setattr(gnani_lodestone.GnaniLodestone, "seed_all", seed_gnani)
    monkeypatch.setattr(
        startup_crew,
        "spawn_cybernetics_crew",
        startup_effect("cybernetics_crew"),
    )
    monkeypatch.setattr(
        startup_crew, "create_seed_tasks", startup_effect("seed_tasks")
    )
    monkeypatch.setattr(
        startup_crew, "spawn_default_crew", startup_effect("default_crew")
    )
    monkeypatch.setattr(swarm, "_init_optional_subsystems", init_optional)
    monkeypatch.setattr(swarm, "reconcile_graph_runs", green_reconcile)
    monkeypatch.setattr(graph_reconciler, "heartbeat_live_claims", lambda: 0)
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", no_tasks)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", no_tasks)
    monkeypatch.setattr(swarm._orchestrator, "tick", no_activity)
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
    swarm._last_auto_rescue_scan = datetime.now(timezone.utc)
    swarm._auto_rescue_scan_interval_seconds = 10**9
    swarm._organism = None
    swarm._director = None
    swarm._auto_proposer = None
    swarm._witness = None
    swarm._living_interval_ticks = 10**9

    try:
        first_results = await asyncio.gather(swarm.tick(), swarm.tick())
        repeated_result = await swarm.tick()
        if swarm._optional_startup_retry_task is not None:
            await swarm._optional_startup_retry_task

        assert all(
            result["startup_backfill_ready"] is True
            for result in first_results
        )
        assert repeated_result["startup_backfill_ready"] is True
        assert swarm._startup_backfill_pending_components == set()
        assert calls == {
            "telos_substrate": 1,
            "gnani_lodestone": 1,
            "cybernetics_crew": 1,
            "seed_tasks": 1,
            "default_crew": 1,
            "optional_subsystems": 1,
        }
    finally:
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_fast_boot_critical_backfill_serializes_with_immediate_tick(
    swarm,
    monkeypatch,
):
    graph_reconciler = swarm._get_graph_reconciler()
    backfill_entered = asyncio.Event()
    release_backfill = asyncio.Event()
    calls = {"backfill": 0, "census": 0, "dispatch": 0}

    async def blocking_backfill():
        calls["backfill"] += 1
        backfill_entered.set()
        await release_backfill.wait()
        swarm._startup_backfill_pending_components.discard("default_crew")
        return {
            "attempted": ["default_crew"],
            "completed": ["default_crew"],
            "created": {"default_crew": 1},
            "pending": [],
        }

    class EmptyReport:
        total_reconciled = 0

    async def green_census(*, stale_only=False):
        assert stale_only is True
        calls["census"] += 1
        graph_reconciler._boot_census_succeeded = True
        return EmptyReport()

    async def no_tasks(*args, **kwargs):
        return []

    async def dispatch():
        calls["dispatch"] += 1
        return {"dispatched": 1, "settled": 0}

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    monkeypatch.setattr(
        swarm, "_backfill_graph_held_startup", blocking_backfill
    )
    monkeypatch.setattr(swarm, "reconcile_graph_runs", green_census)
    monkeypatch.setattr(
        graph_reconciler, "heartbeat_live_claims", lambda: 0
    )
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", no_tasks)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", no_tasks)
    monkeypatch.setattr(swarm._orchestrator, "tick", dispatch)
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
    swarm._startup_backfill_pending_components.add("default_crew")
    swarm._last_auto_rescue_scan = datetime.now(timezone.utc)
    swarm._auto_rescue_scan_interval_seconds = 10**9
    swarm._organism = None
    swarm._director = None
    swarm._auto_proposer = None
    swarm._witness = None
    swarm._living_interval_ticks = 10**9
    swarm._telos_substrate_seeded = True

    startup_task: asyncio.Task[None] | None = None
    tick_task: asyncio.Task[dict] | None = None
    try:
        startup_task = asyncio.create_task(
            swarm._complete_deferred_startup()
        )
        await asyncio.wait_for(backfill_entered.wait(), timeout=1.0)
        assert swarm._effect_tick_lock.locked() is True

        tick_task = asyncio.create_task(swarm.tick())
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert calls == {"backfill": 1, "census": 1, "dispatch": 0}
        assert tick_task.done() is False

        release_backfill.set()
        await asyncio.wait_for(startup_task, timeout=1.0)
        result = await asyncio.wait_for(tick_task, timeout=1.0)

        assert calls == {"backfill": 1, "census": 2, "dispatch": 1}
        assert result["graph_boot_census_succeeded"] is True
        assert result["startup_backfill_ready"] is True
        assert result["dispatched"] == 1
    finally:
        release_backfill.set()
        pending = [
            task
            for task in (startup_task, tick_task)
            if task is not None and not task.done()
        ]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_startup_backfill_failure_preserves_precise_retry_state(
    tmp_path,
    monkeypatch,
):
    import dharma_swarm.gnani_lodestone as gnani_lodestone
    import dharma_swarm.startup_crew as startup_crew
    import dharma_swarm.telos_substrate as telos_substrate

    swarm = await _init_graph_red_fast_swarm(tmp_path, monkeypatch)
    graph_reconciler = swarm._get_graph_reconciler()
    held = await swarm._backfill_graph_held_startup()
    assert held["hold"] == "graph_census_not_succeeded"

    graph_reconciler._boot_census_succeeded = True
    calls = {
        "telos_substrate": 0,
        "gnani_lodestone": 0,
        "cybernetics_crew": 0,
        "seed_tasks": 0,
        "default_crew": 0,
        "optional_subsystems": 0,
    }

    async def seed_telos(self):
        calls["telos_substrate"] += 1
        return {}

    async def seed_gnani(self):
        calls["gnani_lodestone"] += 1
        return {}

    async def cyber(_swarm):
        calls["cybernetics_crew"] += 1
        return []

    async def seeds(_swarm):
        calls["seed_tasks"] += 1
        if calls["seed_tasks"] == 1:
            raise RuntimeError("seed store unavailable")
        return []

    async def default(_swarm):
        calls["default_crew"] += 1
        return []

    async def optional():
        calls["optional_subsystems"] += 1
        _publish_optional_test_doubles(swarm)

    async def fresh_green_census(*, stale_only=False):
        graph_reconciler._boot_census_succeeded = True
        return SimpleNamespace(total_reconciled=0)

    monkeypatch.setattr(telos_substrate.TelosSubstrate, "seed_all", seed_telos)
    monkeypatch.setattr(gnani_lodestone.GnaniLodestone, "seed_all", seed_gnani)
    monkeypatch.setattr(startup_crew, "spawn_cybernetics_crew", cyber)
    monkeypatch.setattr(startup_crew, "create_seed_tasks", seeds)
    monkeypatch.setattr(startup_crew, "spawn_default_crew", default)
    monkeypatch.setattr(swarm, "_init_optional_subsystems", optional)
    monkeypatch.setattr(swarm, "reconcile_graph_runs", fresh_green_census)

    try:
        failed = await swarm._backfill_graph_held_startup()

        assert failed["completed"] == [
            "telos_substrate",
            "gnani_lodestone",
            "cybernetics_crew",
        ]
        assert failed["error"] == (
            "seed_tasks: RuntimeError: seed store unavailable"
        )
        assert failed["pending"] == ["default_crew", "seed_tasks"]
        assert swarm._startup_backfill_last_error == failed["error"]

        recovered = await swarm._backfill_graph_held_startup()
        repeated = await swarm._backfill_graph_held_startup()
        optional_scheduled = swarm._schedule_optional_startup_retry(
            graph_ready=True
        )
        assert swarm._optional_startup_retry_task is not None
        await swarm._optional_startup_retry_task

        assert recovered["pending"] == []
        assert repeated["attempted"] == []
        assert optional_scheduled is True
        assert swarm._startup_backfill_pending_components == set()
        assert swarm._startup_backfill_last_error is None
        assert calls == {
            "telos_substrate": 1,
            "gnani_lodestone": 1,
            "cybernetics_crew": 1,
            "seed_tasks": 2,
            "default_crew": 1,
            "optional_subsystems": 1,
        }
    finally:
        await swarm.shutdown()


def test_tick_graph_readiness_fences_recovery_generation_and_dispatch_source():
    import inspect

    wrapper_src = inspect.getsource(SwarmManager.tick)
    src = inspect.getsource(SwarmManager._tick_effects)
    boot_retry = src.index(
        "stale_only=graph_reconciler.boot_recovery_completed"
    )
    heartbeat = src.index("graph_reconciler.heartbeat_live_claims()")
    startup_backfill = src.index("await self._backfill_graph_held_startup()")
    rescue = src.index("self.rescue_recent_failures()")
    orphan = src.index("self.reap_orphaned_tasks()")
    generation = src.index("if allow_autonomous_generation and not _has_real_tasks")
    dispatch = src.index("if not gnani_holds and graph_ready")
    settle_only = src.index("self._orchestrator.tick_settle_only()")
    coordination = src.index("self.spawn_coordination_tasks(")

    assert "async with self._effect_tick_lock" in wrapper_src
    assert "return await self._tick_effects()" in wrapper_src
    assert boot_retry < heartbeat < startup_backfill < rescue < orphan
    assert orphan < generation < dispatch < settle_only
    assert "if graph_ready and" in src[heartbeat:rescue]
    assert "graph_ready" in src[src.rfind("if (", rescue, orphan):orphan]
    assert "allow_autonomous_generation = False" in src[heartbeat:generation]
    assert src.count("graph_reconciler.invalidate_boot_census()") >= 4
    assert (
        "if graph_ready and startup_ready and not self._telos_substrate_seeded"
        in src
    )
    samvara_create = src.index("await self._task_board.create(")
    assert "allow_autonomous_generation" in src[
        src.rfind("if (", heartbeat, samvara_create):samvara_create
    ]
    assert "if not allow_autonomous_generation or _has_real_tasks" in src[
        settle_only:coordination
    ]
    assert (
        "if (allow_autonomous_generation and self._director is not None" in src
    )
    assert (
        "if (allow_autonomous_generation and self._auto_proposer is not None"
        in src
    )


def test_tick_never_repeats_completed_destructive_boot_sweep_source():
    import inspect

    src = inspect.getsource(SwarmManager._tick_effects)
    retry_call = src.index("self.reconcile_graph_runs(")
    retry_end = src.index("timeout=10.0", retry_call)

    assert "stale_only=graph_reconciler.boot_recovery_completed" in src[
        retry_call:retry_end
    ]


@pytest.mark.asyncio
async def test_tick_reconcile_error_holds_recovery_generation_and_dispatch(
    swarm,
    monkeypatch,
):
    calls = {"settle_only": 0}
    graph_reconciler = swarm._get_graph_reconciler()
    assert graph_reconciler.boot_census_succeeded is True

    async def failed_reconcile(*, stale_only=False):
        assert stale_only is True
        raise RuntimeError("census unavailable")

    async def forbidden(*args, **kwargs):
        raise AssertionError("Graph-held path must not run")

    def forbidden_heartbeat(*args, **kwargs):
        raise AssertionError("Graph-held path must not heartbeat claims")

    async def settle_only():
        calls["settle_only"] += 1
        return {"dispatched": 0, "settled": 0}

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    class ForbiddenAutoProposer:
        async def cycle(self):
            raise AssertionError("Graph-held path must not generate proposals")

    monkeypatch.setattr(swarm, "reconcile_graph_runs", failed_reconcile)
    monkeypatch.setattr(
        graph_reconciler, "heartbeat_live_claims", forbidden_heartbeat
    )
    monkeypatch.setattr(swarm, "rescue_recent_failures", forbidden)
    monkeypatch.setattr(swarm, "reap_orphaned_tasks", forbidden)
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", forbidden)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", forbidden)
    monkeypatch.setattr(swarm, "_director_pulse", forbidden)
    monkeypatch.setattr(swarm._orchestrator, "tick", forbidden)
    monkeypatch.setattr(swarm._orchestrator, "tick_settle_only", settle_only)
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    swarm._organism = None
    swarm._director = object()
    swarm._director_interval_ticks = 1
    swarm._auto_proposer = ForbiddenAutoProposer()
    swarm._auto_proposer_interval_ticks = 1
    swarm._witness = None
    swarm._living_interval_ticks = 10**9
    swarm._telos_substrate_seeded = True

    result = await swarm.tick()

    assert result["graph_boot_census_succeeded"] is False
    assert result["graph_dispatch_hold"] == "boot_census_not_succeeded"
    assert result["claims_heartbeaten"] == 0
    assert result["auto_rescue_hold"] == "graph_census_not_succeeded"
    assert calls == {"settle_only": 0}


@pytest.mark.asyncio
async def test_concurrent_ticks_wait_for_fresh_failed_census_before_effects(
    swarm,
    monkeypatch,
):
    graph_reconciler = swarm._get_graph_reconciler()
    graph_reconciler._boot_census_succeeded = True
    graph_reconciler._boot_recovery_completed = True
    census_entered = asyncio.Event()
    release_census = asyncio.Event()
    calls = {"census": 0, "settle_only": 0}

    async def blocking_failed_census(*, stale_only=False):
        assert stale_only is True
        calls["census"] += 1
        if calls["census"] == 1:
            census_entered.set()
            await release_census.wait()
        raise RuntimeError("hostile census failure")

    async def forbidden(*args, **kwargs):
        raise AssertionError("effect must remain behind fresh Graph census")

    def forbidden_heartbeat(*args, **kwargs):
        raise AssertionError("claim heartbeat must remain Graph-held")

    async def settle_only():
        calls["settle_only"] += 1
        return {"dispatched": 0, "settled": 0}

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    monkeypatch.setattr(
        swarm, "reconcile_graph_runs", blocking_failed_census
    )
    monkeypatch.setattr(
        graph_reconciler, "heartbeat_live_claims", forbidden_heartbeat
    )
    monkeypatch.setattr(swarm, "_backfill_graph_held_startup", forbidden)
    monkeypatch.setattr(swarm, "rescue_recent_failures", forbidden)
    monkeypatch.setattr(swarm, "reap_orphaned_tasks", forbidden)
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", forbidden)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", forbidden)
    monkeypatch.setattr(swarm, "_director_pulse", forbidden)
    monkeypatch.setattr(swarm._orchestrator, "tick", forbidden)
    monkeypatch.setattr(swarm._orchestrator, "tick_settle_only", settle_only)
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    swarm._startup_backfill_pending_components.add("default_crew")
    swarm._last_auto_rescue_scan = None
    swarm._organism = None
    swarm._director = object()
    swarm._director_interval_ticks = 1
    swarm._auto_proposer = object()
    swarm._auto_proposer_interval_ticks = 1
    swarm._witness = None
    swarm._living_interval_ticks = 10**9
    swarm._telos_substrate_seeded = True

    first: asyncio.Task[dict] | None = None
    second: asyncio.Task[dict] | None = None
    try:
        first = asyncio.create_task(swarm.tick())
        await asyncio.wait_for(census_entered.wait(), timeout=1.0)

        assert graph_reconciler.boot_census_succeeded is False
        second = asyncio.create_task(swarm.tick())
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert calls == {"census": 1, "settle_only": 0}
        assert second.done() is False

        release_census.set()
        results = await asyncio.wait_for(
            asyncio.gather(first, second), timeout=2.0
        )

        assert calls == {"census": 2, "settle_only": 0}
        assert all(
            result["graph_boot_census_succeeded"] is False
            for result in results
        )
        assert all(result["claims_heartbeaten"] == 0 for result in results)
        assert all(result["dispatched"] == 0 for result in results)
        assert graph_reconciler.boot_census_succeeded is False
    finally:
        release_census.set()
        pending = [
            task for task in (first, second) if task is not None and not task.done()
        ]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_deferred_critical_backfill_requires_fresh_green_census(
    swarm,
    monkeypatch,
):
    graph_reconciler = swarm._get_graph_reconciler()
    graph_reconciler._boot_census_succeeded = True
    swarm._startup_backfill_pending_components.add("default_crew")

    async def failed_census(*, stale_only=False):
        assert stale_only is True
        raise RuntimeError("fresh startup census unavailable")

    async def forbidden_backfill():
        raise AssertionError("stale boot-green must not authorize backfill")

    monkeypatch.setattr(swarm, "reconcile_graph_runs", failed_census)
    monkeypatch.setattr(
        swarm,
        "_backfill_graph_held_startup",
        forbidden_backfill,
    )

    await swarm._complete_deferred_startup()

    assert graph_reconciler.boot_census_succeeded is False
    assert swarm._startup_backfill_pending_components == {"default_crew"}
    assert swarm._startup_backfill_last_error is not None
    assert "fresh startup census unavailable" in swarm._startup_backfill_last_error


@pytest.mark.asyncio
async def test_shutdown_joins_in_progress_effect_tick_before_teardown(
    tmp_path,
    monkeypatch,
):
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    tick_entered = asyncio.Event()
    release_tick = asyncio.Event()
    events: list[str] = []

    async def held_effect_tick():
        async with swarm._effect_tick_lock:
            events.append("tick_entered")
            tick_entered.set()
            await release_tick.wait()
            events.append("tick_finished")

    async def teardown(_timeout):
        events.append("teardown")

    monkeypatch.setattr(swarm, "_shutdown_under_effect_lock", teardown)
    tick_task = asyncio.create_task(held_effect_tick())
    await asyncio.wait_for(tick_entered.wait(), timeout=1.0)
    shutdown_task = asyncio.create_task(swarm.shutdown(drain_timeout=0.01))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert shutdown_task.done() is False
    assert events == ["tick_entered"]

    release_tick.set()
    await asyncio.wait_for(asyncio.gather(tick_task, shutdown_task), timeout=1.0)

    assert events == ["tick_entered", "tick_finished", "teardown"]
    held = await swarm.tick()
    assert held["paused"] is True
    assert held["shutdown"] is True


@pytest.mark.asyncio
async def test_shutdown_retains_dependencies_while_orchestrator_has_live_custody(
    tmp_path,
    monkeypatch,
):
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    orchestrator = Orchestrator()
    started = asyncio.Event()
    cancellation_seen = asyncio.Event()
    release_work = asyncio.Event()

    async def stubborn_work():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellation_seen.set()
            await release_work.wait()

    background = asyncio.create_task(stubborn_work())
    await started.wait()
    dispatch = TaskDispatch(task_id="shutdown-live", agent_id="live-agent")
    orchestrator._running_tasks[dispatch.task_id] = background
    orchestrator._running_dispatch_owners[dispatch.task_id] = (
        background,
        dispatch,
    )
    orchestrator._active_dispatches[dispatch.task_id] = dispatch

    class Pool:
        shutdown_calls = 0

        async def shutdown_all(self):
            self.shutdown_calls += 1

    pool = Pool()
    swarm._orchestrator = orchestrator
    swarm._agent_pool = pool
    monkeypatch.setattr(swarm, "_persist_session_digest", AsyncMock())

    try:
        with pytest.raises(RuntimeError, match="retains 1 live owner"):
            await swarm.shutdown(drain_timeout=0.01)
        await cancellation_seen.wait()

        assert swarm._shutdown_complete is False
        assert pool.shutdown_calls == 0
        assert orchestrator._running_tasks[dispatch.task_id] is background
        assert orchestrator._active_dispatches[dispatch.task_id] is dispatch

        release_work.set()
        await background
        await swarm.shutdown(drain_timeout=0.1)
        assert swarm._shutdown_complete is True
        assert pool.shutdown_calls == 1
    finally:
        release_work.set()
        if not background.done():
            background.cancel()
        await asyncio.gather(background, return_exceptions=True)


@pytest.mark.asyncio
async def test_optional_director_is_not_published_before_success(
    tmp_path,
    monkeypatch,
):
    import dharma_swarm.thinkodynamic_director as director_module

    class FailingDirector:
        def __init__(self, **_kwargs):
            pass

        async def init(self):
            raise RuntimeError("director store unavailable")

    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    monkeypatch.setattr(
        director_module,
        "ThinkodynamicDirector",
        FailingDirector,
    )

    with pytest.raises(RuntimeError, match="director store unavailable"):
        await swarm._init_optional_director()

    assert swarm._director is None


@pytest.mark.asyncio
async def test_optional_engine_bundle_is_not_published_before_init_success(
    tmp_path,
    monkeypatch,
):
    import dharma_swarm.evolution as evolution_module
    import dharma_swarm.traces as traces_module

    engine_entered = asyncio.Event()
    engine_never_finishes = asyncio.Event()

    class ReadyTraceStore:
        def __init__(self, **_kwargs):
            pass

        async def init(self):
            return None

    class BlockingEngine:
        def __init__(self, **_kwargs):
            self.archive = object()
            self.predictor = object()

        async def init(self):
            engine_entered.set()
            await engine_never_finishes.wait()

    monkeypatch.setattr(traces_module, "TraceStore", ReadyTraceStore)
    monkeypatch.setattr(evolution_module, "DarwinEngine", BlockingEngine)
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    init_task = asyncio.create_task(swarm._init_optional_subsystems())
    try:
        await asyncio.wait_for(engine_entered.wait(), timeout=1.0)
        assert swarm._trace_store is None
        assert swarm._engine is None
        assert swarm._meta_engine is None
        assert swarm._monitor is None
    finally:
        init_task.cancel()
        engine_never_finishes.set()
        await asyncio.gather(init_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_partial_optional_retry_remains_observable_and_pending(
    tmp_path,
    monkeypatch,
):
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    swarm._startup_backfill_pending_components.add("optional_subsystems")

    class GreenGraph:
        boot_census_succeeded = True
        boot_recovery_completed = True

        def invalidate_boot_census(self):
            self.boot_census_succeeded = False

    swarm._graph_reconciler = GreenGraph()

    async def green_census(*, stale_only=False):
        assert stale_only is True
        swarm._graph_reconciler.boot_census_succeeded = True
        return SimpleNamespace(total_reconciled=0)

    async def partial_init():
        swarm._director = object()

    monkeypatch.setattr(swarm, "_init_optional_subsystems", partial_init)
    monkeypatch.setattr(swarm, "reconcile_graph_runs", green_census)

    await swarm._retry_optional_startup_once()

    assert swarm._startup_backfill_pending_components == {
        "optional_subsystems"
    }
    assert swarm._optional_startup_last_error is not None
    assert "SubsystemNotReady" in swarm._optional_startup_last_error
    assert "gateway" in swarm._optional_startup_last_error


@pytest.mark.asyncio
async def test_optional_retry_and_red_tick_are_effect_serialized(
    swarm,
    monkeypatch,
):
    graph_reconciler = swarm._get_graph_reconciler()
    optional_entered = asyncio.Event()
    release_optional = asyncio.Event()
    calls = {"census": 0}

    async def changing_census(*, stale_only=False):
        assert stale_only is True
        calls["census"] += 1
        if calls["census"] == 1:
            graph_reconciler._boot_census_succeeded = True
            return SimpleNamespace(total_reconciled=0)
        raise RuntimeError("Graph turned red")

    async def blocked_optional_init():
        optional_entered.set()
        await release_optional.wait()
        _publish_optional_test_doubles(swarm)

    async def no_tasks(*args, **kwargs):
        return []

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    monkeypatch.setattr(swarm, "reconcile_graph_runs", changing_census)
    monkeypatch.setattr(swarm, "_init_optional_subsystems", blocked_optional_init)
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", no_tasks)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", no_tasks)
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    swarm._startup_backfill_pending_components.add("optional_subsystems")
    swarm._last_auto_rescue_scan = datetime.now(timezone.utc)
    swarm._auto_rescue_scan_interval_seconds = 10**9
    swarm._organism = None
    swarm._director = None
    swarm._auto_proposer = None
    swarm._witness = None
    swarm._living_interval_ticks = 10**9
    swarm._telos_substrate_seeded = True

    optional_task = asyncio.create_task(swarm._retry_optional_startup_once())
    await asyncio.wait_for(optional_entered.wait(), timeout=1.0)
    tick_task = asyncio.create_task(swarm.tick())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert tick_task.done() is False
    assert calls == {"census": 1}

    release_optional.set()
    await asyncio.wait_for(optional_task, timeout=1.0)
    result = await asyncio.wait_for(tick_task, timeout=1.0)

    assert calls == {"census": 2}
    assert result["graph_boot_census_succeeded"] is False
    assert result["graph_dispatch_hold"] == "boot_census_not_succeeded"
    assert result["dispatched"] == 0


@pytest.mark.asyncio
async def test_shutdown_stops_optional_resource_published_during_cancellation(
    tmp_path,
    monkeypatch,
):
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    swarm._startup_backfill_pending_components.add("optional_subsystems")
    init_entered = asyncio.Event()
    stopped = asyncio.Event()

    class GreenGraph:
        boot_census_succeeded = True
        boot_recovery_completed = True

        def invalidate_boot_census(self):
            self.boot_census_succeeded = False

    class LateDirector:
        async def stop(self):
            stopped.set()

    graph = GreenGraph()
    swarm._graph_reconciler = graph

    async def green_census(*, stale_only=False):
        assert stale_only is True
        graph.boot_census_succeeded = True
        return SimpleNamespace(total_reconciled=0)

    async def cancellation_delaying_init():
        init_entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            swarm._director = LateDirector()

    monkeypatch.setattr(swarm, "reconcile_graph_runs", green_census)
    monkeypatch.setattr(
        swarm,
        "_init_optional_subsystems",
        cancellation_delaying_init,
    )
    retry = asyncio.create_task(swarm._retry_optional_startup_once())
    swarm._optional_startup_retry_task = retry
    await asyncio.wait_for(init_entered.wait(), timeout=1.0)

    await asyncio.wait_for(swarm.shutdown(drain_timeout=0.01), timeout=1.0)

    assert retry.done() is True
    assert stopped.is_set() is True
    assert swarm._shutdown_complete is True


@pytest.mark.asyncio
async def test_optional_startup_timeout_does_not_block_core_dispatch(
    swarm,
    monkeypatch,
):
    graph_reconciler = swarm._get_graph_reconciler()
    calls = {"census": 0, "dispatch": 0, "optional": 0}
    optional_entered = asyncio.Event()
    optional_never_finishes = asyncio.Event()

    class EmptyReport:
        total_reconciled = 0

    async def green_census(*, stale_only=False):
        assert stale_only is True
        calls["census"] += 1
        graph_reconciler._boot_census_succeeded = True
        return EmptyReport()

    async def blocked_optional_init():
        calls["optional"] += 1
        optional_entered.set()
        await optional_never_finishes.wait()

    async def no_tasks(*args, **kwargs):
        return []

    async def dispatch():
        calls["dispatch"] += 1
        return {"dispatched": 1, "settled": 0}

    async def forbidden_settle_only():
        raise AssertionError("optional startup must not hold core dispatch")

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    monkeypatch.setattr(swarm, "reconcile_graph_runs", green_census)
    monkeypatch.setattr(
        graph_reconciler, "heartbeat_live_claims", lambda: 0
    )
    monkeypatch.setattr(
        swarm, "_init_optional_subsystems", blocked_optional_init
    )
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", no_tasks)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", no_tasks)
    monkeypatch.setattr(swarm._orchestrator, "tick", dispatch)
    monkeypatch.setattr(
        swarm._orchestrator, "tick_settle_only", forbidden_settle_only
    )
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
    swarm._startup_backfill_pending_components.add("optional_subsystems")
    swarm._optional_startup_retry_timeout_seconds = 0.05
    swarm._optional_startup_retry_interval_seconds = 3600.0
    swarm._last_auto_rescue_scan = datetime.now(timezone.utc)
    swarm._auto_rescue_scan_interval_seconds = 10**9
    swarm._organism = None
    swarm._director = None
    swarm._auto_proposer = None
    swarm._witness = None
    swarm._living_interval_ticks = 10**9
    swarm._telos_substrate_seeded = True

    first = await asyncio.wait_for(swarm.tick(), timeout=1.0)
    await asyncio.wait_for(optional_entered.wait(), timeout=1.0)

    assert first["startup_backfill_ready"] is True
    assert "startup_dispatch_hold" not in first
    assert first["optional_startup_pending"] is True
    assert first["optional_startup_retry_scheduled"] is True
    assert first["optional_startup_retry_running"] is True
    assert first["dispatched"] == 1
    assert swarm._optional_startup_retry_task is not None
    await asyncio.wait_for(swarm._optional_startup_retry_task, timeout=1.0)

    assert swarm._optional_startup_last_error == (
        "optional_subsystems: TimeoutError: exceeded 0.05s"
    )
    assert swarm._startup_backfill_pending_components == {
        "optional_subsystems"
    }

    second = await asyncio.wait_for(swarm.tick(), timeout=1.0)

    assert second["startup_backfill_ready"] is True
    assert second["optional_startup_pending"] is True
    assert second["optional_startup_retry_scheduled"] is False
    assert second["optional_startup_retry_running"] is False
    assert second["optional_startup_error"] == (
        "optional_subsystems: TimeoutError: exceeded 0.05s"
    )
    assert second["dispatched"] == 1
    assert calls == {"census": 3, "dispatch": 2, "optional": 1}


@pytest.mark.asyncio
async def test_tick_retries_only_stale_census_after_boot_recovery_completed(
    swarm,
    monkeypatch,
):
    stale_only_calls: list[bool] = []
    graph_reconciler = swarm._get_graph_reconciler()
    assert graph_reconciler.boot_recovery_completed is True
    graph_reconciler.invalidate_boot_census()

    class EmptyReport:
        total_reconciled = 0

    async def record_reconcile(*, stale_only=False):
        stale_only_calls.append(stale_only)
        graph_reconciler._boot_census_succeeded = True
        return EmptyReport()

    async def no_tasks(*args, **kwargs):
        return []

    async def no_activity():
        return {"dispatched": 0, "settled": 0}

    async def coordination_status(*, refresh=True):
        return SwarmCoordinationState()

    monkeypatch.setattr(swarm, "reconcile_graph_runs", record_reconcile)
    monkeypatch.setattr(graph_reconciler, "heartbeat_live_claims", lambda: 0)
    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", no_tasks)
    monkeypatch.setattr(swarm, "spawn_coordination_tasks", no_tasks)
    monkeypatch.setattr(swarm._orchestrator, "tick", no_activity)
    monkeypatch.setattr(swarm, "coordination_status", coordination_status)
    swarm._last_auto_rescue_scan = datetime.now(timezone.utc)
    swarm._auto_rescue_scan_interval_seconds = 10**9
    swarm._organism = None
    swarm._director = None
    swarm._auto_proposer = None
    swarm._witness = None
    swarm._living_interval_ticks = 10**9
    swarm._telos_substrate_seeded = True

    result = await swarm.tick()

    assert stale_only_calls == [True]
    assert result["graph_boot_census_succeeded"] is True


@pytest.mark.asyncio
async def test_init_falls_back_to_state_local_manifest_when_global_write_is_blocked(
    tmp_path,
    monkeypatch,
):
    import dharma_swarm.ecosystem_bridge as ecosystem_bridge

    state_dir = tmp_path / ".dharma"
    calls: list[Path | None] = []

    def fake_update_manifest(manifest_path=None):
        calls.append(Path(manifest_path) if manifest_path is not None else None)
        if manifest_path is None:
            raise PermissionError("sandbox blocked global manifest")
        return {"ecosystem": {}, "last_scan": "2026-03-11T00:00:00+00:00"}

    monkeypatch.setattr(ecosystem_bridge, "update_manifest", fake_update_manifest)

    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()
    try:
        assert calls == [None, state_dir / "ecosystem_manifest.json"]
        assert swarm._manifest["ecosystem"] == {}
    finally:
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_init_uses_state_local_ledger_dir(tmp_path):
    state_dir = tmp_path / ".dharma"

    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()
    try:
        assert swarm._orchestrator is not None
        assert swarm._orchestrator._ledger.base_dir == state_dir / "ledgers"
    finally:
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_init_fast_boot_defers_default_crew_and_optional_subsystems(
    tmp_path,
    monkeypatch,
):
    import dharma_swarm.startup_crew as startup_crew

    state_dir = tmp_path / ".dharma"
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")

    async def _fake_spawn_default_crew(_swarm):
        return []

    async def _fake_spawn_cybernetics_crew(_swarm):
        return [object(), object()]

    async def _fake_create_seed_tasks(_swarm):
        return [object()]

    gate = asyncio.Event()

    async def _fake_optional_init(self):
        await gate.wait()

    monkeypatch.setattr(startup_crew, "spawn_default_crew", _fake_spawn_default_crew)
    monkeypatch.setattr(startup_crew, "spawn_cybernetics_crew", _fake_spawn_cybernetics_crew)
    monkeypatch.setattr(startup_crew, "create_seed_tasks", _fake_create_seed_tasks)
    monkeypatch.setattr(SwarmManager, "_init_optional_subsystems", _fake_optional_init)

    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()
    try:
        assert swarm._startup_background_task is not None
        await swarm._startup_background_task
        assert swarm._optional_startup_retry_task is not None
        assert not swarm._optional_startup_retry_task.done()
    finally:
        gate.set()
        if swarm._optional_startup_retry_task is not None:
            await swarm._optional_startup_retry_task
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_spawn_agent(swarm):
    agent = await swarm.spawn_agent("worker-1", role=AgentRole.CODER)
    assert agent.name == "worker-1"
    assert agent.role == AgentRole.CODER

    agents = await swarm.list_agents()
    assert len(agents) >= _AUTO_AGENTS + 1


@pytest.mark.asyncio
async def test_spawn_agent_applies_dynamic_roster_defaults(tmp_path, monkeypatch):
    state_dir = tmp_path / ".dharma"
    roster = DynamicRoster(state_dir=state_dir)
    roster.add(_make_dynamic_spec("runtime_specialist"))

    swarm = SwarmManager(state_dir=state_dir)

    class _FakePool:
        async def spawn(self, config, **_: object):
            return type(
                "_Runner",
                (),
                {
                    "state": AgentState(
                        id=config.id,
                        name=config.name,
                        role=config.role,
                        status=AgentStatus.IDLE,
                        provider=config.provider.value,
                        model=config.model,
                    )
                },
            )()

    class _FakeMemory:
        async def remember(self, *args, **kwargs):
            return None

    async def _noop_sync(*args, **kwargs):
        return None

    swarm._agent_pool = _FakePool()
    swarm._memory = _FakeMemory()
    monkeypatch.setattr(swarm, "_sync_agent_contracts", _noop_sync)

    agent = await swarm.spawn_agent("runtime_specialist")
    spawner = swarm.get_worker_spawner("runtime_specialist")

    assert agent.name == "runtime_specialist"
    assert agent.role == AgentRole.CODER
    assert spawner is not None
    assert spawner._max_concurrent == 4


@pytest.mark.asyncio
async def test_spawn_agent_preserves_constitutional_routing_metadata(tmp_path, monkeypatch):
    state_dir = tmp_path / ".dharma"
    captured: dict[str, object] = {}

    class _FakePool:
        async def spawn(self, config, **_: object):
            captured["config"] = config
            return type(
                "_Runner",
                (),
                {
                    "state": AgentState(
                        id=config.id,
                        name=config.name,
                        role=config.role,
                        status=AgentStatus.IDLE,
                        provider=config.provider.value,
                        model=config.model,
                    )
                },
            )()

    class _FakeMemory:
        async def remember(self, *args, **kwargs):
            return None

    async def _noop_sync(*args, **kwargs):
        return None

    swarm = SwarmManager(state_dir=state_dir)
    swarm._agent_pool = _FakePool()
    swarm._memory = _FakeMemory()
    monkeypatch.setattr(swarm, "_sync_agent_contracts", _noop_sync)

    agent = await swarm.spawn_agent("operator")
    config = captured["config"]

    assert agent.name == "operator"
    assert config.metadata["allow_provider_routing"] is True
    assert config.metadata["state_dir"] == str(state_dir)


@pytest.mark.asyncio
async def test_sync_agents_retires_stale_live_contracts(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime.db"
    telemetry = TelemetryPlaneStore(db_path)
    await telemetry.init_db()
    await telemetry.upsert_agent_identity(
        AgentIdentityRecord(
            agent_id="stale-agent",
            codename="stale-agent",
            status="idle",
        )
    )
    await telemetry.record_team_roster(
        TeamRosterRecord(
            roster_id="roster:dharma_swarm:stale-agent",
            team_id="dharma_swarm",
            agent_id="stale-agent",
            role="surgeon",
            active=True,
        )
    )

    class _StaticPool:
        async def list_agents(self) -> list[AgentState]:
            return [
                AgentState(
                    id="agent-live-1",
                    name="live-agent",
                    role=AgentRole.CODER,
                    status=AgentStatus.IDLE,
                )
            ]

    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(db_path))

    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    swarm._agent_pool = _StaticPool()
    swarm._agent_configs = {}

    results = await swarm.sync_agents()

    retired_identity = await telemetry.get_agent_identity("stale-agent")
    retired_roster = await telemetry.list_team_roster(
        team_id="dharma_swarm",
        agent_id="stale-agent",
        active_only=False,
        limit=10,
    )

    assert len(results) == 1
    assert retired_identity is not None
    assert retired_identity.status == "retired"
    assert retired_roster[0].active is False


@pytest.mark.asyncio
async def test_sync_agents_preserves_bus_readiness_for_live_agents(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime.db"
    bus = MessageBus(tmp_path / "message_bus.db")
    await bus.init_db()
    await bus.subscribe("live-agent", "orchestrator.lifecycle")
    await bus.subscribe("live-agent", "operator.bridge.lifecycle")
    await bus.heartbeat("live-agent", metadata={"role": "coder"})

    class _StaticPool:
        async def list_agents(self) -> list[AgentState]:
            return [
                AgentState(
                    id="agent-live-1",
                    name="live-agent",
                    role=AgentRole.CODER,
                    status=AgentStatus.IDLE,
                )
            ]

    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(db_path))

    telemetry = TelemetryPlaneStore(db_path)
    await telemetry.init_db()

    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    swarm._agent_pool = _StaticPool()
    swarm._agent_configs = {}
    swarm._message_bus = bus

    results = await swarm.sync_agents()
    identity = await telemetry.get_agent_identity("live-agent")

    assert len(results) == 1
    assert results[0]["communication_ready"] is True
    assert results[0]["bus_status"] == "online"
    assert results[0]["missing_topics"] == []
    assert identity is not None
    assert identity.metadata["communication_ready"] is True
    assert identity.metadata["bus_status"] == "online"


@pytest.mark.asyncio
async def test_list_agents_retires_stale_live_contracts_when_pool_is_empty(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "runtime.db"
    telemetry = TelemetryPlaneStore(db_path)
    await telemetry.init_db()
    await telemetry.upsert_agent_identity(
        AgentIdentityRecord(
            agent_id="stale-agent",
            codename="stale-agent",
            status="idle",
        )
    )
    await telemetry.record_team_roster(
        TeamRosterRecord(
            roster_id="roster:dharma_swarm:stale-agent",
            team_id="dharma_swarm",
            agent_id="stale-agent",
            role="surgeon",
            active=True,
        )
    )

    class _StaticPool:
        async def list_agents(self) -> list[AgentState]:
            return []

    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(db_path))

    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    swarm._agent_pool = _StaticPool()
    swarm._agent_configs = {}

    agents = await swarm.list_agents()
    retired_identity = await telemetry.get_agent_identity("stale-agent")
    retired_roster = await telemetry.list_team_roster(
        team_id="dharma_swarm",
        agent_id="stale-agent",
        active_only=False,
        limit=10,
    )

    assert agents == []
    assert retired_identity is not None
    assert retired_identity.status == "retired"
    assert retired_roster[0].active is False


@pytest.mark.asyncio
async def test_create_task(swarm):
    task = await swarm.create_task("Build module", priority=TaskPriority.HIGH)
    assert task.title == "Build module"
    assert task.priority == TaskPriority.HIGH
    assert task.metadata.get("trace_id", "").startswith("trc_")
    assert task.metadata.get("created_via") == "swarm.create_task"


@pytest.mark.asyncio
async def test_create_task_normalizes_coordination_metadata(swarm):
    task = await swarm.create_task(
        "Route policy review",
        metadata={
            "claim_key": "route-policy",
            "uncertainty": 0.7,
            "coordination_shared_context": "Existing disagreement context",
        },
    )

    assert task.metadata["coordination_claim_key"] == "route-policy"
    assert task.metadata["coordination_topic"] == "route-policy"
    assert task.metadata["coordination_uncertainty"] == pytest.approx(0.7)
    assert task.metadata["coordination_state"] == "uncertain"
    assert task.metadata["coordination_route"] == "synthesis_review"
    assert "reviewer" in task.metadata["coordination_preferred_roles"]


@pytest.mark.asyncio
async def test_create_task_blocked(swarm):
    with pytest.raises(ValueError, match="Telos gate blocked"):
        await swarm.create_task("rm -rf /everything")


@pytest.mark.asyncio
async def test_create_task_blocks_self_referential_heartbeat_task(swarm):
    with pytest.raises(ValueError, match="Self-referential heartbeat task blocked"):
        await swarm.create_task(
            "Parse heartbeat.md",
            description="Create a task about heartbeat.md and summarize heartbeat loops",
            metadata={"source": "heartbeat"},
        )


@pytest.mark.asyncio
async def test_list_tasks(swarm):
    await swarm.create_task("Task 1")
    await swarm.create_task("Task 2")
    tasks = await swarm.list_tasks()
    assert len(tasks) == _AUTO_TASKS + 2


@pytest.mark.asyncio
async def test_get_task(swarm):
    task = await swarm.create_task("Findable")
    found = await swarm.get_task(task.id)
    assert found is not None
    assert found.title == "Findable"


@pytest.mark.asyncio
async def test_memory(swarm):
    await swarm.remember("test memory entry")
    entries = await swarm.recall(limit=5)
    assert len(entries) >= 1


@pytest.mark.asyncio
async def test_spawn_latent_gold_tasks_reopens_orphaned_branches(swarm):
    store = ConversationMemoryStore(swarm.state_dir / "db" / "memory_plane.db")
    store.record_turn(
        session_id="sess-latent",
        task_id="task-source",
        role="user",
        content=(
            "We could build a memory palace index for task recall.\n"
            "Maybe preserve abandoned branches from the conversation."
        ),
        turn_index=1,
    )
    store.mark_task_outcome("task-source", outcome="success")

    created = await swarm.spawn_latent_gold_tasks(
        limit=2,
        max_pending=100,
        min_salience=0.0,
    )

    assert created
    assert created[0].metadata["latent_gold_reopened"] is True
    assert created[0].metadata["latent_gold_shard_id"].startswith("shd_")

    second = await swarm.spawn_latent_gold_tasks(
        limit=2,
        max_pending=100,
        min_salience=0.0,
    )
    assert second == []


@pytest.mark.asyncio
async def test_run_dispatches_pending_work_even_when_generation_rate_limited(
    swarm,
    monkeypatch,
):
    calls = {"spawn": 0, "tick": 0}

    async def fake_spawn(*args, **kwargs):
        calls["spawn"] += 1
        return []

    async def fake_tick():
        calls["tick"] += 1
        swarm._running = False
        return {"dispatched": 1, "settled": 0, "recovered": 0}

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", fake_spawn)
    monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
    monkeypatch.setattr(swarm, "_in_quiet_hours", lambda: True)
    monkeypatch.setattr(swarm._orchestrator, "tick", fake_tick)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    swarm._running = True
    await swarm.run(interval=0.0)

    assert calls["spawn"] == 0
    assert calls["tick"] == 1
    assert swarm._daily_contributions == 1


@pytest.mark.asyncio
async def test_run_does_not_consume_contribution_budget_without_work(
    swarm,
    monkeypatch,
):
    calls = {"spawn": 0, "tick": 0}

    async def fake_spawn(*args, **kwargs):
        calls["spawn"] += 1
        return []

    async def fake_tick():
        calls["tick"] += 1
        swarm._running = False
        return {"dispatched": 0, "settled": 0, "recovered": 0}

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", fake_spawn)
    monkeypatch.setattr(swarm, "_contribution_allowed", lambda: True)
    monkeypatch.setattr(swarm, "_in_quiet_hours", lambda: False)
    monkeypatch.setattr(swarm._orchestrator, "tick", fake_tick)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    swarm._running = True
    swarm._daily_contributions = 0
    swarm._last_contribution = None
    await swarm.run(interval=0.0)

    # spawn_latent_gold_tasks may or may not be called depending on whether
    # operator tasks are present. tick MUST be called once.
    assert calls["tick"] == 1
    assert swarm._daily_contributions == 0
    assert swarm._last_contribution is None


@pytest.mark.asyncio
async def test_run_publishes_fresh_dgc_health_snapshot(swarm, monkeypatch):
    async def fake_tick():
        swarm._running = False
        return {"dispatched": 0, "settled": 0, "recovered": 0}

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(swarm._orchestrator, "tick", fake_tick)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    daemon_pid = os.getpid()
    (swarm.state_dir / "daemon.pid").write_text(f"{daemon_pid}\n", encoding="utf-8")

    swarm._running = True
    await swarm.run(interval=0.0)

    summary = dgc_health_snapshot_summary(swarm.state_dir)
    assert summary["status"] == "fresh"
    assert summary["daemon_pid"] == daemon_pid
    assert summary["daemon_pid_mismatch"] is False
    assert summary["payload"]["source"] == "swarm.run"


@pytest.mark.asyncio
async def test_rescue_recent_failures_requeues_transient_failure(swarm):
    task = await swarm.create_task("Transient rescue target")
    await swarm._task_board.assign(task.id, "agent-1")
    await swarm._task_board.start(task.id)
    await swarm._task_board.fail(
        task.id,
        "Connection error.",
        metadata={"last_failure_source": "execution_error"},
    )

    rescued = await swarm.rescue_recent_failures(limit=4)

    assert rescued
    refreshed = await swarm.get_task(task.id)
    assert refreshed is not None
    assert refreshed.status == TaskStatus.PENDING
    assert refreshed.metadata["auto_rescue_count"] == 1
    assert refreshed.metadata["last_failure_class"] == "connection_transient"


@pytest.mark.asyncio
async def test_rescue_recent_failures_skips_duplicate_active_title(swarm):
    failed = await swarm.create_task("Duplicate rescue title")
    await swarm._task_board.assign(failed.id, "agent-1")
    await swarm._task_board.start(failed.id)
    await swarm._task_board.fail(
        failed.id,
        "Task execution timed out after 300.0s",
        metadata={"last_failure_source": "timeout", "timeout_seconds": 300.0},
    )

    active = await swarm.create_task("Duplicate rescue title")
    assert active.status == TaskStatus.PENDING

    rescued = await swarm.rescue_recent_failures(limit=4)

    assert rescued == []
    refreshed = await swarm.get_task(failed.id)
    assert refreshed is not None
    assert refreshed.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_rescue_recent_failures_preserves_campaign_authority(swarm):
    campaign_metadata = {"mission_campaign_authority": {}}
    task = await swarm.create_task(
        "Campaign rescue must remain typed",
        metadata=campaign_metadata,
    )
    # Fixture-only prior-process state. Production campaign transitions require
    # the typed authority CAS and generic recovery must not emulate it.
    async with swarm._task_board._open() as db:
        await db.execute(
            "UPDATE tasks SET status = ?, assigned_to = ?, result = ?, metadata = ?"
            " WHERE id = ?",
            (
                TaskStatus.FAILED.value,
                "campaign-agent",
                "Connection error.",
                json.dumps(campaign_metadata),
                task.id,
            ),
        )
        await db.commit()

    rescued = await swarm.rescue_recent_failures(limit=4)

    assert rescued == []
    preserved = await swarm.get_task(task.id)
    assert preserved is not None
    assert preserved.status == TaskStatus.FAILED
    assert preserved.metadata == campaign_metadata


@pytest.mark.asyncio
async def test_stale_reaper_preserves_campaign_authority(swarm):
    campaign_metadata = {"mission_campaign_authority": {}}
    task = await swarm.create_task(
        "Campaign stale recovery must remain typed",
        metadata=campaign_metadata,
    )
    stale = datetime.now(timezone.utc) - timedelta(hours=7)
    async with swarm._task_board._open() as db:
        await db.execute(
            "UPDATE tasks SET status = ?, assigned_to = ?, updated_at = ?, metadata = ?"
            " WHERE id = ?",
            (
                TaskStatus.RUNNING.value,
                "prior-campaign-agent",
                stale.isoformat(),
                json.dumps(campaign_metadata),
                task.id,
            ),
        )
        await db.commit()

    reaped = await swarm._reap_stale_running_tasks(max_age_hours=6.0)

    assert reaped == 0
    preserved = await swarm.get_task(task.id)
    assert preserved is not None
    assert preserved.status == TaskStatus.RUNNING
    assert preserved.assigned_to == "prior-campaign-agent"
    assert preserved.result is None
    assert preserved.metadata == campaign_metadata


@pytest.mark.asyncio
async def test_status(swarm):
    await swarm.spawn_agent("a1")
    await swarm.create_task("t1")
    state = await swarm.status()
    assert len(state.agents) >= _AUTO_AGENTS + 1
    assert state.tasks_pending == _AUTO_TASKS + 1
    assert state.uptime_seconds > 0


@pytest.mark.asyncio
async def test_coordination_status_reports_global_truth(swarm):
    agents = await swarm.list_agents()
    left, right = agents[0], agents[1]
    await swarm._message_bus.send(
        Message(
            id="coord-msg-1",
            from_agent=left.id,
            to_agent=right.id,
            subject="route-policy",
            body="Mechanism, witness, ecosystem all agree.",
            metadata={"topic": "route-policy"},
        )
    )
    await swarm._message_bus.send(
        Message(
            id="coord-msg-2",
            from_agent=right.id,
            to_agent=left.id,
            subject="route-policy",
            body="Mechanism, witness, ecosystem all agree.",
            metadata={"topic": "route-policy"},
        )
    )

    coordination = await swarm.coordination_status(refresh=True)

    assert isinstance(coordination, SwarmCoordinationState)
    assert coordination.agent_count >= 2
    assert coordination.message_count >= 2
    assert coordination.global_truths >= 1
    assert coordination.productive_disagreements == 0
    assert coordination.is_globally_coherent is True
    assert "route-policy" in coordination.global_truth_claim_keys


@pytest.mark.asyncio
async def test_coordination_status_reports_productive_disagreement(swarm):
    agents = await swarm.list_agents()
    left, right = agents[0], agents[1]
    await swarm._message_bus.send(
        Message(
            id="coord-msg-3",
            from_agent=left.id,
            to_agent=right.id,
            subject="route-policy",
            body="Mechanism and architecture dominate this route.",
            metadata={"topic": "route-policy"},
        )
    )
    await swarm._message_bus.send(
        Message(
            id="coord-msg-4",
            from_agent=right.id,
            to_agent=left.id,
            subject="route-policy",
            body="Witness awareness and introspection dominate this route.",
            metadata={"topic": "route-policy"},
        )
    )

    coordination = await swarm.coordination_status(refresh=True)

    assert coordination.global_truths == 0
    assert coordination.productive_disagreements >= 1
    assert coordination.is_globally_coherent is False
    assert "route-policy" in coordination.productive_disagreement_claim_keys


@pytest.mark.asyncio
async def test_spawn_coordination_tasks_creates_synthesis_task(swarm):
    agents = await swarm.list_agents()
    left, right = agents[0], agents[1]
    await swarm._message_bus.send(
        Message(
            id="coord-msg-5",
            from_agent=left.id,
            to_agent=right.id,
            subject="route-policy",
            body="Mechanism and architecture dominate this route.",
            metadata={"topic": "route-policy"},
        )
    )
    await swarm._message_bus.send(
        Message(
            id="coord-msg-6",
            from_agent=right.id,
            to_agent=left.id,
            subject="route-policy",
            body="Witness awareness and introspection dominate this route.",
            metadata={"topic": "route-policy"},
        )
    )

    coordination = await swarm.coordination_status(refresh=True)
    created = await swarm.spawn_coordination_tasks(coordination=coordination, limit=2)

    assert created
    task = created[0]
    assert task.metadata["coordination_origin"] == "sheaf_disagreement"
    assert task.metadata["coordination_claim_key"] == "route-policy"
    assert task.metadata["coordination_route"] == "synthesis_review"
    assert task.priority == TaskPriority.HIGH


# --- Gödel Claw v0.3.0 tests ---


@pytest.mark.asyncio
async def test_dharma_status(swarm):
    """dharma_status returns subsystem state."""
    status = await swarm.dharma_status()
    assert status["kernel"] is True
    assert status["kernel_axioms"] == 25
    assert status["kernel_integrity"] is True
    assert status["corpus"] is True
    assert status["compiler"] is True
    assert status["canary"] is True


@pytest.mark.asyncio
async def test_propose_claim(swarm):
    """propose_claim creates a claim with DC-ID."""
    result = await swarm.propose_claim("Test safety claim", category="safety")
    assert result["id"].startswith("DC-")
    assert result["status"] == "proposed"


@pytest.mark.asyncio
async def test_review_claim(swarm):
    """review_claim adds a review record."""
    claim = await swarm.propose_claim("Review test claim", category="operational")
    result = await swarm.review_claim(
        claim["id"], reviewer="test", action="review", comment="looks good"
    )
    assert result["status"] == "under_review"
    assert result["reviews"] == 1


@pytest.mark.asyncio
async def test_promote_claim(swarm):
    """promote_claim changes status to accepted."""
    claim = await swarm.propose_claim("Promote test", category="ethics")
    result = await swarm.promote_claim(claim["id"])
    assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_compile_policy(swarm):
    """compile_policy produces rules from kernel."""
    result = await swarm.compile_policy(context="test")
    assert result["immutable"] == 25  # kernel axioms
    assert result["context"] == "test"


@pytest.mark.asyncio
async def test_compile_policy_with_claims(swarm):
    """compile_policy includes accepted claims."""
    claim = await swarm.propose_claim(
        "Policy test claim", category="safety", confidence=0.8
    )
    await swarm.promote_claim(claim["id"])
    result = await swarm.compile_policy()
    assert result["mutable"] >= 1


@pytest.mark.asyncio
async def test_kernel_integrity_on_init(swarm):
    """Kernel should be valid after init."""
    status = await swarm.dharma_status()
    assert status["kernel_integrity"] is True


@pytest.mark.asyncio
async def test_corpus_claims_count(swarm):
    """Corpus claim count tracks proposals."""
    s1 = await swarm.dharma_status()
    initial = s1.get("corpus_claims", 0)
    await swarm.propose_claim("Counting test", category="operational")
    s2 = await swarm.dharma_status()
    assert s2["corpus_claims"] == initial + 1


# ---------------------------------------------------------------------------
# Algedonic channel (Beer S5 bypass)
# ---------------------------------------------------------------------------


def test_algedonic_handler_writes_signal_log(tmp_path):
    """_algedonic_handler writes JSONL entry to algedonic_signals.jsonl."""
    import json

    sm = SwarmManager.__new__(SwarmManager)
    sm.state_dir = tmp_path

    # Simulate a critical AlgedonicSignal via a simple namespace
    class FakeSignal:
        kind = "telos_drift"
        severity = "critical"
        action = "gnani_checkpoint"
        value = 0.28
        timestamp = 1234567890.0

    sm._algedonic_handler(FakeSignal())

    log_path = tmp_path / "algedonic_signals.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text().strip())
    assert entry["kind"] == "telos_drift"
    assert entry["severity"] == "critical"
    assert entry["value"] == 0.28


@pytest.mark.xfail(reason="Tests old instant-HOLD policy; replaced by 3-consecutive-critical policy (commit 8a4d9626, CONSECUTIVE_HOLDS_BEFORE_EMERGENCY=3, organism.py:1056)")
def test_algedonic_critical_creates_emergency_hold(tmp_path):
    """Critical signal writes EMERGENCY_HOLD marker file (after cold-start grace)."""
    import time
    sm = SwarmManager.__new__(SwarmManager)
    sm.state_dir = tmp_path
    # Simulate post-grace-period: set _start_time far in the past
    sm._start_time = time.monotonic() - 300.0

    class FakeSignal:
        kind = "telos_drift"
        severity = "critical"
        action = "gnani_checkpoint"
        value = 0.15
        timestamp = 0.0

    sm._algedonic_handler(FakeSignal())

    hold_path = tmp_path / "EMERGENCY_HOLD"
    assert hold_path.exists()
    assert "telos_drift" in hold_path.read_text()


def test_algedonic_noncritical_no_emergency_hold(tmp_path):
    """Non-critical signal does NOT write EMERGENCY_HOLD."""
    sm = SwarmManager.__new__(SwarmManager)
    sm.state_dir = tmp_path

    class FakeSignal:
        kind = "omega_divergence"
        severity = "medium"
        action = "rebalance_priorities"
        value = 0.55
        timestamp = 0.0

    sm._algedonic_handler(FakeSignal())

    # Log file should exist, but not the emergency hold
    assert (tmp_path / "algedonic_signals.jsonl").exists()
    assert not (tmp_path / "EMERGENCY_HOLD").exists()


def test_emergency_hold_pauses_dispatch(tmp_path):
    """EMERGENCY_HOLD marker causes _check_human_overrides to report paused."""
    import types

    sm = SwarmManager.__new__(SwarmManager)
    sm.state_dir = tmp_path
    # Minimal daemon stub with pause_file attribute
    sm._daemon = types.SimpleNamespace(pause_file=".PAUSE")
    sm._thread_mgr = None

    # No hold → not paused
    result = sm._check_human_overrides()
    assert result["paused"] is False

    # Create hold marker → paused
    (tmp_path / "EMERGENCY_HOLD").write_text("telos_drift: value=0.15\n")
    result = sm._check_human_overrides()
    assert result["paused"] is True
