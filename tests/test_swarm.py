"""Tests for dharma_swarm.swarm — integration tests."""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from dharma_swarm.agent_constitution import AgentSpec, ConstitutionalLayer, DynamicRoster
from dharma_swarm.engine.conversation_memory import ConversationMemoryStore
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import AgentRole, AgentState, AgentStatus, Message, TaskPriority, TaskStatus, ProviderType
from dharma_swarm.swarm import (
    SwarmCoordinationState,
    SwarmManager,
    _task_counts_as_execution_pressure,
)
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


_AUTO_AGENTS = _expected_agent_count()


async def _ensure_coordination_agents(
    swarm: SwarmManager,
    *,
    count: int = 2,
) -> list[AgentState]:
    agents = await swarm.list_agents()
    while len(agents) < count:
        await swarm.spawn_agent(
            f"coordination-agent-{len(agents) + 1}",
            role=AgentRole.GENERAL,
        )
        agents = await swarm.list_agents()
    return agents[:count]


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
    await s.wait_until_bootstrap_ready(timeout=60.0)
    yield s
    await s.shutdown()


@pytest.mark.asyncio
async def test_init(swarm):
    state = await swarm.status()
    assert state.tasks_pending >= 1
    assert len(state.agents) >= _AUTO_AGENTS


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
        assert not swarm._startup_background_task.done()
    finally:
        gate.set()
        if swarm._startup_background_task is not None:
            await swarm._startup_background_task
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
    assert "coordination_claim_key" not in task.metadata


@pytest.mark.asyncio
async def test_create_task_does_not_infer_coordination_claim_from_title(swarm):
    task = await swarm.create_task("Route policy review")

    assert "coordination_claim_key" not in task.metadata
    assert "coordination_topic" not in task.metadata


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
    baseline = len(await swarm.list_tasks())
    await swarm.create_task("Task 1")
    await swarm.create_task("Task 2")
    tasks = await swarm.list_tasks()
    assert len(tasks) == baseline + 2


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
    swarm._director = None
    swarm._auto_proposer = None

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
async def test_run_publishes_hot_path_liveness_to_snapshot(swarm, monkeypatch):
    async def fake_spawn(*args, **kwargs):
        return []

    async def fake_orchestrator_tick():
        return {"dispatched": 1, "settled": 1, "recovered": 0}

    async def fake_sleep(_seconds):
        swarm._running = False
        return None

    monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", fake_spawn)
    monkeypatch.setattr(swarm, "_in_quiet_hours", lambda: True)
    monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
    monkeypatch.setattr(swarm._orchestrator, "tick", fake_orchestrator_tick)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    swarm._running = True
    await swarm.run(interval=0.2)

    summary = dgc_health_snapshot_summary(swarm.state_dir)
    liveness = summary["liveness"]
    assert summary["payload"]["source"] == "swarm.run"
    assert liveness["last_tick_number"] >= 1
    assert liveness["last_tick_started_at"] is not None
    assert liveness["last_tick_completed_at"] is not None
    assert liveness["tick_interval_s"] == pytest.approx(0.2)
    assert liveness["last_task_dispatch_at"] is not None
    assert liveness["last_task_completion_at"] is not None
    watch_payload = json.loads(
        (swarm.state_dir / "meta" / "swarm_liveness.json").read_text(encoding="utf-8")
    )
    assert watch_payload["liveness"]["status"] in {"healthy", "degraded", "booting", "stalled"}
    assert watch_payload["source"] == "swarm.run"


def test_task_counts_as_execution_pressure_for_primary_campaign():
    task = type(
        "_Task",
        (),
        {
            "created_by": "seed_task",
            "metadata": {"campaign_id": "camp_primary"},
        },
    )()
    assert _task_counts_as_execution_pressure(task, primary_campaign_id="camp_primary") is True


def test_task_counts_as_execution_pressure_for_manual_seed():
    task = type(
        "_Task",
        (),
        {
            "created_by": "swarm",
            "metadata": {"created_via": "manual_seed"},
        },
    )()
    assert _task_counts_as_execution_pressure(task) is True


def test_task_counts_as_execution_pressure_for_persistent_campaign_task():
    task = type(
        "_Task",
        (),
        {
            "created_by": "conductor_claude",
            "metadata": {
                "source": "persistent_agent.campaign",
                "task_source": "campaign",
            },
        },
    )()
    assert _task_counts_as_execution_pressure(task) is True


def test_task_counts_as_execution_pressure_for_contract_task():
    task = type(
        "_Task",
        (),
        {
            "created_by": "system",
            "metadata": {
                "contract_version": "task_contract_v1",
                "owner_lane": "builder",
                "settlement_state": "queued",
            },
        },
    )()
    assert _task_counts_as_execution_pressure(task) is True


@pytest.mark.asyncio
async def test_first_tick_without_dispatch_stays_bootstrap_ready(tmp_path, monkeypatch):
    async def _noop_deferred_startup(self):
        return None

    monkeypatch.setattr(SwarmManager, "_complete_deferred_startup", _noop_deferred_startup)

    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    await swarm.init()
    try:
        assert swarm._orchestrator is not None

        async def fake_spawn(*args, **kwargs):
            return []

        async def fake_orchestrator_tick():
            return {"dispatched": 0, "settled": 0, "recovered": 0}

        monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", fake_spawn)
        monkeypatch.setattr(swarm, "_in_quiet_hours", lambda: True)
        monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
        monkeypatch.setattr(swarm._orchestrator, "tick", fake_orchestrator_tick)
        swarm._telos_substrate_seeded = True

        activity = await swarm.tick()

        assert activity["dispatched"] == 0
        liveness = swarm.hot_path_liveness()
        assert liveness["bootstrap_completed_at"] is None
        assert liveness["bootstrap_phase"] == "bootstrap_ready"
        assert liveness["stall_state"] == "bootstrap_waiting_for_dispatch"
    finally:
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_timed_out_orchestrator_tick_preserves_dispatch_progress(tmp_path, monkeypatch):
    async def _noop_deferred_startup(self):
        return None

    monkeypatch.setattr(SwarmManager, "_complete_deferred_startup", _noop_deferred_startup)

    swarm = SwarmManager(state_dir=tmp_path / ".dharma")
    await swarm.init()
    sleepers: list[asyncio.Task] = []
    try:
        assert swarm._orchestrator is not None

        async def fake_spawn(*args, **kwargs):
            return []

        async def fake_orchestrator_tick():
            sleeper = asyncio.create_task(asyncio.sleep(60.0))
            sleepers.append(sleeper)
            swarm._orchestrator._active_dispatches["timeout-task"] = object()
            swarm._orchestrator._running_tasks["timeout-task"] = sleeper
            raise asyncio.TimeoutError

        monkeypatch.setattr(swarm, "spawn_latent_gold_tasks", fake_spawn)
        monkeypatch.setattr(swarm, "_in_quiet_hours", lambda: True)
        monkeypatch.setattr(swarm, "_contribution_allowed", lambda: False)
        monkeypatch.setattr(swarm._orchestrator, "tick", fake_orchestrator_tick)
        swarm._telos_substrate_seeded = True

        activity = await swarm.tick()

        assert activity["dispatched"] == 1
        liveness = swarm.hot_path_liveness()
        assert liveness["bootstrap_phase"] == "bootstrap_complete"
        assert liveness["bootstrap_completed_at"] is not None
        assert liveness["stall_state"] == "none"
    finally:
        for sleeper in sleepers:
            sleeper.cancel()
        if sleepers:
            await asyncio.gather(*sleepers, return_exceptions=True)
        await swarm.shutdown()


@pytest.mark.asyncio
async def test_deferred_startup_does_not_downgrade_bootstrap_complete(tmp_path, monkeypatch):
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")

    async def _no_agents(*_args, **_kwargs):
        return []

    async def _ok_floor():
        return True, "agents=1"

    monkeypatch.setattr("dharma_swarm.startup_crew.spawn_cybernetics_crew", _no_agents)
    monkeypatch.setattr("dharma_swarm.startup_crew.create_seed_tasks", _no_agents)
    monkeypatch.setattr("dharma_swarm.startup_crew.spawn_default_crew", _no_agents)
    monkeypatch.setattr(swarm, "_init_optional_subsystems", AsyncMock())
    monkeypatch.setattr(swarm, "_validate_bootstrap_floor", AsyncMock(side_effect=_ok_floor))

    swarm._record_bootstrap_phase(
        "bootstrap_complete",
        reason="first_dispatch_completed",
    )

    await swarm._execute_deferred_startup()

    liveness = swarm.hot_path_liveness()
    assert liveness["bootstrap_phase"] == "bootstrap_complete"
    assert liveness["bootstrap_completed_at"] is not None


@pytest.mark.asyncio
async def test_deferred_startup_agents_spawned_does_not_overwrite_bootstrap_complete(tmp_path, monkeypatch):
    swarm = SwarmManager(state_dir=tmp_path / ".dharma")

    async def _no_agents(*_args, **_kwargs):
        return []

    async def _some_agents(*_args, **_kwargs):
        return [object()]

    async def _ok_floor():
        return True, "agents=1"

    monkeypatch.setattr("dharma_swarm.startup_crew.spawn_cybernetics_crew", _no_agents)
    monkeypatch.setattr("dharma_swarm.startup_crew.create_seed_tasks", _no_agents)
    monkeypatch.setattr("dharma_swarm.startup_crew.spawn_default_crew", _some_agents)
    monkeypatch.setattr(swarm, "_init_optional_subsystems", AsyncMock())
    monkeypatch.setattr(swarm, "_validate_bootstrap_floor", AsyncMock(side_effect=_ok_floor))

    swarm._record_bootstrap_phase(
        "bootstrap_complete",
        reason="first_dispatch_completed",
    )

    await swarm._execute_deferred_startup()

    liveness = swarm.hot_path_liveness()
    assert liveness["bootstrap_phase"] == "bootstrap_complete"
    assert liveness["bootstrap_completed_at"] is not None
    assert liveness["bootstrap_phase_history"][-1]["phase"] == "bootstrap_complete"


@pytest.mark.asyncio
async def test_publish_runtime_health_snapshot_survives_stuck_agent_pool(tmp_path):
    state_dir = tmp_path / ".dharma"
    swarm = SwarmManager(state_dir=state_dir)

    class _SlowPool:
        async def list_agents(self):
            await asyncio.Event().wait()

    class _FastBoard:
        async def stats(self):
            return {
                "pending": 2,
                "assigned": 1,
                "running": 0,
                "completed": 0,
                "failed": 0,
            }

    swarm._agent_pool = _SlowPool()
    swarm._task_board = _FastBoard()

    await asyncio.wait_for(
        swarm._publish_runtime_health_snapshot(source="test.publish_runtime_health"),
        timeout=5.0,
    )

    summary = dgc_health_snapshot_summary(state_dir)
    assert summary["status"] == "fresh"
    assert summary["payload"]["source"] == "test.publish_runtime_health"
    assert summary["payload"]["task_count"] == 3


@pytest.mark.asyncio
async def test_run_caps_coordination_refresh_interval_to_tick_interval(swarm, monkeypatch):
    async def fake_tick():
        swarm._running = False
        return {"dispatched": 0, "settled": 0, "recovered": 0}

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(swarm, "tick", fake_tick)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    assert swarm._orchestrator is not None
    swarm._orchestrator._coordination_refresh_interval_s = 120.0
    swarm._running = True

    await swarm.run(interval=0.5)

    assert swarm._orchestrator._coordination_refresh_interval_s == 0.5


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
async def test_status(swarm):
    baseline = await swarm.status()
    await swarm.spawn_agent("a1")
    await swarm.create_task("t1")
    state = await swarm.status()
    assert len(state.agents) >= _AUTO_AGENTS + 1
    assert state.tasks_pending == baseline.tasks_pending + 1
    assert state.uptime_seconds > 0


@pytest.mark.asyncio
async def test_coordination_status_reports_global_truth(swarm):
    agents = await _ensure_coordination_agents(swarm)
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
    agents = await _ensure_coordination_agents(swarm)
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
    agents = await _ensure_coordination_agents(swarm)
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
    assert task.metadata["coordination_claim_state"] == "open"
    assert task.metadata["coordination_route"] == "synthesis_review"
    assert task.priority == TaskPriority.HIGH


@pytest.mark.asyncio
async def test_spawn_coordination_tasks_suppresses_recent_completed_attempt(swarm):
    completed = await swarm._task_board.create(
        title="Synthesize disagreement: route-policy",
        created_by="system",
        assigned_to="reviewer-1",
        metadata={
            "source": "swarm.coordination_synthesis",
            "coordination_origin": "sheaf_disagreement",
            "coordination_claim_key": "route-policy",
            "coordination_claim_state": "open",
        },
    )
    await swarm._task_board.assign(
        completed.id,
        "reviewer-1",
        metadata=completed.metadata,
    )
    await swarm._task_board.start(completed.id, metadata=completed.metadata)
    await swarm._task_board.complete(
        completed.id,
        result="Synthesis completed",
        metadata=completed.metadata,
    )

    coordination = SwarmCoordinationState(
        productive_disagreements=1,
        productive_disagreement_claim_keys=["route-policy"],
        observed_at=datetime.now(timezone.utc).isoformat(),
    )

    created = await swarm.spawn_coordination_tasks(coordination=coordination)

    assert created == []


@pytest.mark.asyncio
async def test_spawn_coordination_tasks_permanently_suppresses_completed_synthesis(swarm):
    """Completed synthesis permanently suppresses the claim_key — no respawn
    even with cooldown=0, unless explicitly reopened."""
    task = await swarm._task_board.create(
        title="Synthesize disagreement: route-policy",
        created_by="system",
        assigned_to="reviewer-1",
        metadata={
            "source": "swarm.coordination_synthesis",
            "coordination_origin": "sheaf_disagreement",
            "coordination_claim_key": "route-policy",
            "coordination_claim_state": "open",
        },
    )
    await swarm._task_board.assign(
        task.id,
        "reviewer-1",
        metadata=task.metadata,
    )
    await swarm._task_board.start(task.id, metadata=task.metadata)
    await swarm._task_board.complete(
        task.id,
        result="Synthesis completed",
        metadata=task.metadata,
    )

    coordination = SwarmCoordinationState(
        productive_disagreements=1,
        productive_disagreement_claim_keys=["route-policy"],
        observed_at=datetime.now(timezone.utc).isoformat(),
    )

    created = await swarm.spawn_coordination_tasks(
        coordination=coordination,
        completed_cooldown_seconds=0.0,
    )

    assert created == [], "Completed synthesis should permanently suppress, not respawn"


@pytest.mark.asyncio
async def test_spawn_coordination_tasks_allows_reopened_claim(swarm):
    """A claim explicitly marked 'reopened' can be re-synthesized even if
    a previous synthesis completed."""
    task = await swarm._task_board.create(
        title="Synthesize disagreement: route-policy",
        created_by="system",
        assigned_to="reviewer-1",
        metadata={
            "source": "swarm.coordination_synthesis",
            "coordination_origin": "sheaf_disagreement",
            "coordination_claim_key": "route-policy",
            "coordination_claim_state": "reopened",
        },
    )
    await swarm._task_board.assign(
        task.id,
        "reviewer-1",
        metadata=task.metadata,
    )
    await swarm._task_board.start(task.id, metadata=task.metadata)
    await swarm._task_board.complete(
        task.id,
        result="Synthesis completed",
        metadata=task.metadata,
    )

    coordination = SwarmCoordinationState(
        productive_disagreements=1,
        productive_disagreement_claim_keys=["route-policy"],
        observed_at=datetime.now(timezone.utc).isoformat(),
    )

    created = await swarm.spawn_coordination_tasks(
        coordination=coordination,
    )

    assert len(created) == 1
    assert created[0].metadata["coordination_claim_key"] == "route-policy"


@pytest.mark.asyncio
async def test_spawn_coordination_tasks_suppresses_resolved_claim(swarm):
    resolved = await swarm._task_board.create(
        title="Synthesize disagreement: route-policy",
        created_by="system",
        assigned_to="reviewer-1",
        metadata={
            "source": "swarm.coordination_synthesis",
            "coordination_origin": "sheaf_disagreement",
            "coordination_claim_key": "route-policy",
            "coordination_claim_state": "resolved",
        },
    )
    await swarm._task_board.assign(
        resolved.id,
        "reviewer-1",
        metadata=resolved.metadata,
    )
    await swarm._task_board.start(resolved.id, metadata=resolved.metadata)
    await swarm._task_board.complete(
        resolved.id,
        result="Resolved disagreement",
        metadata=resolved.metadata,
    )

    coordination = SwarmCoordinationState(
        productive_disagreements=1,
        productive_disagreement_claim_keys=["route-policy"],
        observed_at=datetime.now(timezone.utc).isoformat(),
    )

    created = await swarm.spawn_coordination_tasks(
        coordination=coordination,
        completed_cooldown_seconds=0.0,
    )

    assert created == []


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


@pytest.mark.xfail(reason="Tests old instant-HOLD policy; replaced by 3-consecutive-critical policy")
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
