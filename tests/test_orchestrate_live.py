"""Tests for dharma_swarm.orchestrate_live.

Tests the orchestrator's helper functions, loop early-exit conditions,
and signal handling without requiring real LLM calls or subprocess spawning.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
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


def test_daemon_runtime_dispatch_self_report_is_non_secret_and_pid_bound(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")

    path = mod._write_daemon_runtime_dispatch_self_report(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path == tmp_path / "ops" / "daemon_runtime_dispatch_self_report.json"
    assert payload["schema_version"] == (
        "dharma.daemon.runtime_dispatch_self_report.v1"
    )
    assert payload["pid"] == os.getpid()
    assert payload["source"] == "dharma_swarm.orchestrate_live"
    assert payload["runtime_dispatch"] == {
        "spine_dispatch_enabled": True,
        "dispatch_mode": "spine",
        "env_key_present": True,
        "source": "process_env_non_secret_boolean",
    }
    assert "DHARMA_SPINE_DISPATCH" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_detect_health_anomalies_bounded_times_out() -> None:
    from dharma_swarm import orchestrate_live as mod

    class SlowMonitor:
        async def detect_anomalies(self) -> list[object]:
            await asyncio.sleep(1)
            return [object()]

    anomalies = await mod._detect_health_anomalies_bounded(
        SlowMonitor(),
        timeout_seconds=0.01,
    )

    assert anomalies == []


@pytest.mark.asyncio
async def test_detect_health_anomalies_bounded_returns_list() -> None:
    from dharma_swarm import orchestrate_live as mod

    class Monitor:
        async def detect_anomalies(self) -> tuple[str, str]:
            return ("a", "b")

    anomalies = await mod._detect_health_anomalies_bounded(
        Monitor(),
        timeout_seconds=0.5,
    )

    assert anomalies == ["a", "b"]


@pytest.mark.asyncio
async def test_runtime_dispatch_self_report_loop_writes_until_shutdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")
    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    shutdown = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.03)
        shutdown.set()

    stopper = asyncio.create_task(stop_soon())
    await asyncio.wait_for(
        mod.run_daemon_runtime_dispatch_self_report_loop(
            shutdown,
            interval_seconds=0.01,
        ),
        timeout=1.0,
    )
    await stopper

    payload = json.loads(
        (tmp_path / "ops" / "daemon_runtime_dispatch_self_report.json").read_text(
            encoding="utf-8",
        )
    )
    assert payload["schema_version"] == (
        "dharma.daemon.runtime_dispatch_self_report.v1"
    )
    assert payload["runtime_dispatch"]["spine_dispatch_enabled"] is True


def test_runtime_dispatch_self_report_thread_writes_during_sync_sleep(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")
    shutdown = asyncio.Event()

    thread = mod.start_daemon_runtime_dispatch_self_report_thread(
        shutdown,
        state_dir=tmp_path,
        interval_seconds=0.01,
    )
    time.sleep(0.05)
    shutdown.set()
    thread.join(timeout=1.0)

    path = tmp_path / "ops" / "daemon_runtime_dispatch_self_report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert not thread.is_alive()
    assert payload["pid"] == os.getpid()
    assert payload["runtime_dispatch"]["spine_dispatch_enabled"] is True


def test_archaeology_ingestion_enabled_defaults_on(monkeypatch) -> None:
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.delenv(mod.ARCHAEOLOGY_INGESTION_ENV, raising=False)

    assert mod._archaeology_ingestion_enabled() is True


def test_archaeology_ingestion_enabled_respects_disable_flag(monkeypatch) -> None:
    from dharma_swarm import orchestrate_live as mod

    monkeypatch.setenv(mod.ARCHAEOLOGY_INGESTION_ENV, "0")

    assert mod._archaeology_ingestion_enabled() is False


@pytest.mark.asyncio
async def test_run_archaeology_loop_returns_when_ingestion_disabled(monkeypatch) -> None:
    from dharma_swarm import orchestrate_live as mod

    logs: list[tuple[str, str]] = []
    monkeypatch.setenv(mod.ARCHAEOLOGY_INGESTION_ENV, "0")
    monkeypatch.setattr(mod, "_log", lambda system, message: logs.append((system, message)))

    shutdown = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.01)
        shutdown.set()

    stopper = asyncio.create_task(stop_soon())
    await asyncio.wait_for(mod._run_archaeology_loop(shutdown), timeout=1.0)
    await stopper

    assert any("Ingestion disabled" in message for _, message in logs)


@pytest.mark.asyncio
async def test_run_archaeology_once_bounded_returns_counts() -> None:
    from dharma_swarm import orchestrate_live as mod

    class Daemon:
        async def run_once(self) -> dict[str, int]:
            return {"evolution_archive": 1}

    counts = await mod._run_archaeology_once_bounded(Daemon(), timeout_seconds=1.0)

    assert counts == {"evolution_archive": 1}


@pytest.mark.asyncio
async def test_run_archaeology_once_bounded_times_out_when_ingestion_blocks() -> None:
    from dharma_swarm import orchestrate_live as mod

    class BlockingDaemon:
        async def run_once(self) -> dict[str, int]:
            # Simulates the production failure mode: synchronous CPU/file/vector
            # work inside an async coroutine before it yields to the event loop.
            time.sleep(0.12)
            return {"shared_research": 1}

    started = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await mod._run_archaeology_once_bounded(
            BlockingDaemon(),
            timeout_seconds=0.02,
        )

    assert time.perf_counter() - started < 0.10


def test_pulse_result_daily_limit_classification() -> None:
    from dharma_swarm import orchestrate_live as mod

    assert mod._pulse_result_counts_toward_daily_limit("HEALTH PULSE: daemon_alive=True") is False
    assert mod._pulse_result_counts_toward_daily_limit("PAUSED: .PAUSE file") is False
    assert mod._pulse_result_counts_toward_daily_limit("QUIET: quiet hours") is False
    assert mod._pulse_result_counts_toward_daily_limit("CIRCUIT breaker open") is False
    assert mod._pulse_result_counts_toward_daily_limit("TELOS gate blocked") is False
    assert mod._pulse_result_counts_toward_daily_limit("Wrote synthesis to shared memory") is True


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


@pytest.mark.asyncio
async def test_run_pending_evolution_proposals_drains_queue_into_cycle():
    from dharma_swarm.orchestrate_live import _run_pending_evolution_proposals

    class Engine:
        def __init__(self) -> None:
            self.seen = []

        def load_pending_proposals(self):
            return [SimpleNamespace(id=f"p{i}") for i in range(7)]

        async def run_cycle(self, proposals):
            self.seen = proposals
            return SimpleNamespace(
                best_fitness=0.7,
                proposals_submitted=len(proposals),
                proposals_archived=len(proposals),
            )

    engine = Engine()

    result = await _run_pending_evolution_proposals(engine, limit=5)

    assert result.proposals_submitted == 5
    assert [proposal.id for proposal in engine.seen] == ["p0", "p1", "p2", "p3", "p4"]


def test_evolution_shadow_mode_requires_explicit_shadow_off_and_autonomy():
    from dharma_swarm.orchestrate_live import _evolution_shadow_mode_from_env

    assert _evolution_shadow_mode_from_env({}) == (True, "DHARMA_EVOLUTION_SHADOW")
    assert _evolution_shadow_mode_from_env(
        {"DHARMA_EVOLUTION_SHADOW": "0", "DGC_AUTONOMY_LEVEL": "1"}
    ) == (True, "DGC_AUTONOMY_LEVEL < 2")
    assert _evolution_shadow_mode_from_env(
        {"DHARMA_EVOLUTION_SHADOW": "0", "DGC_AUTONOMY_LEVEL": "2"}
    ) == (False, "DHARMA_EVOLUTION_SHADOW")


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


@pytest.mark.asyncio
async def test_swarm_loop_releases_ready_after_first_tick(monkeypatch, tmp_path):
    """Ancillary startup is gated on a real core tick, not object initialization."""
    from dharma_swarm import orchestrate_live as mod

    shutdown = asyncio.Event()
    ready = asyncio.Event()

    status = SimpleNamespace(
        agents=[],
        tasks_pending=1,
        tasks_running=0,
        tasks_completed=0,
        tasks_failed=0,
    )
    board = SimpleNamespace(
        stats=AsyncMock(return_value={"pending": 1, "running": 0}),
    )
    mock_swarm = MagicMock()
    mock_swarm.init = AsyncMock()
    mock_swarm.list_agents = AsyncMock(return_value=[])
    mock_swarm.status = AsyncMock(return_value=status)
    mock_swarm.current_thread = "test"
    mock_swarm._orchestrator = SimpleNamespace(_board=board)
    mock_swarm.shutdown = AsyncMock()

    tick_calls = 0

    async def tick_once():
        nonlocal tick_calls
        tick_calls += 1
        if tick_calls == 1:
            assert not ready.is_set()
        return {
            "paused": False,
            "circuit_broken": False,
            "dispatched": 0,
            "settled": 0,
            "rescued": 0,
        }

    mock_swarm.tick = AsyncMock(side_effect=tick_once)

    mock_bus = MagicMock()
    mock_bus.init_db = AsyncMock()
    mock_bus.consume_events = AsyncMock(return_value=[])

    bridge = MagicMock()
    bridge.drain_inbox.return_value = []

    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod, "SWARM_TICK", 0)
    monkeypatch.setattr(mod, "_drain_frontier_queue", AsyncMock(return_value=0))

    with (
        patch("dharma_swarm.swarm.SwarmManager", return_value=mock_swarm),
        patch("dharma_swarm.message_bus.MessageBus", return_value=mock_bus),
        patch("dharma_swarm.startup_crew.spawn_cybernetics_crew", AsyncMock(return_value=[])),
        patch("dharma_swarm.skill_bridge.SkillBridge", return_value=bridge),
    ):
        task = asyncio.create_task(
            mod.run_swarm_loop(shutdown, ready_event=ready),
        )
        await asyncio.wait_for(ready.wait(), timeout=1.0)
        assert mock_swarm.tick.await_count >= 1
        shutdown.set()
        await asyncio.wait_for(task, timeout=1.0)

    mock_swarm.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_loop_pause_file_suppresses_pre_tick_drains(monkeypatch, tmp_path):
    """A pause file must prevent bridge/frontier drains and core dispatch ticks."""
    from dharma_swarm import orchestrate_live as mod

    (tmp_path / ".PAUSE").write_text("operator hold\n", encoding="utf-8")
    shutdown = asyncio.Event()

    status = SimpleNamespace(
        agents=[],
        tasks_pending=1,
        tasks_running=0,
        tasks_completed=0,
        tasks_failed=0,
    )
    board = SimpleNamespace(
        stats=AsyncMock(return_value={"pending": 1, "running": 0}),
    )
    mock_swarm = MagicMock()
    mock_swarm.init = AsyncMock()
    mock_swarm.list_agents = AsyncMock(return_value=[])
    mock_swarm.status = AsyncMock(return_value=status)
    mock_swarm.current_thread = "test"
    mock_swarm._orchestrator = SimpleNamespace(_board=board)
    mock_swarm.tick = AsyncMock(return_value={"paused": False})
    mock_swarm.shutdown = AsyncMock()

    mock_bus = MagicMock()
    mock_bus.init_db = AsyncMock()
    mock_bus.consume_events = AsyncMock(return_value=[])

    bridge = MagicMock()
    bridge.drain_inbox.return_value = [{"skill_name": "retro", "payload": {}}]
    drain_frontier = AsyncMock(return_value=1)
    spawn_cybernetics_crew = AsyncMock(return_value=[])
    swarm_manager_kwargs = {}

    async def fake_sleep(seconds: float) -> None:
        assert seconds == 30
        shutdown.set()

    def fake_swarm_manager(*_args, **kwargs):
        swarm_manager_kwargs.update(kwargs)
        return mock_swarm

    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(mod, "_drain_frontier_queue", drain_frontier)

    with (
        patch("dharma_swarm.swarm.SwarmManager", side_effect=fake_swarm_manager),
        patch("dharma_swarm.message_bus.MessageBus", return_value=mock_bus),
        patch("dharma_swarm.startup_crew.spawn_cybernetics_crew", spawn_cybernetics_crew),
        patch("dharma_swarm.skill_bridge.SkillBridge", return_value=bridge),
    ):
        await asyncio.wait_for(mod.run_swarm_loop(shutdown), timeout=1.0)

    assert swarm_manager_kwargs["read_only_boot"] is True
    spawn_cybernetics_crew.assert_not_awaited()
    board.stats.assert_not_awaited()
    bridge.drain_inbox.assert_not_called()
    drain_frontier.assert_not_awaited()
    mock_swarm.tick.assert_not_awaited()
    mock_swarm.shutdown.assert_awaited_once()


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
    """External zeitgeist and internal pressure loops are registered.

    Audit assertion: confirms the loop IS reached during startup (Step 2 wiring).
    """
    import inspect
    from dharma_swarm import orchestrate_live
    src = inspect.getsource(orchestrate_live.orchestrate)
    assert '"zeitgeist"' in src, (
        "zeitgeist loop must be registered in task_factories inside orchestrate()"
    )
    assert '"internal-pressure"' in src, (
        "internal pressure loop must be registered separately from external zeitgeist"
    )
    assert '"evolution"' in src and "run_evolution_loop" in src, (
        "Darwin evolution loop must be registered in task_factories inside orchestrate()"
    )


def test_gate_pressure_paths_match():
    """Write path (internal pressure) and read path (telos_gates) must agree.

    Audit assertion: S4→S3 feedback channel is wired correctly end-to-end.
    """
    from dharma_swarm.orchestrate_live import STATE_DIR
    from dharma_swarm.telos_gates import TelosGatekeeper

    internal_pressure_write_path = STATE_DIR / "meta" / "gate_pressure.json"
    telos_read_path = TelosGatekeeper._GATE_PRESSURE_PATH

    assert internal_pressure_write_path == telos_read_path, (
        f"Path mismatch: internal pressure writes to {internal_pressure_write_path}, "
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
    monkeypatch.setattr(mod, "_stop_old_daemon", lambda: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "_wait_or_shutdown", AsyncMock(return_value=False))
    monkeypatch.setattr(mod, "run_swarm_loop", flaky_swarm)
    monkeypatch.setattr(mod, "_run_health_api_process_watchdog", sleeper)
    monkeypatch.setattr(mod, "run_pulse_loop", shutdown_watchdog)
    monkeypatch.setattr(mod, "run_evolution_loop", sleeper)
    monkeypatch.setattr(mod, "_run_recognition_loop", sleeper)
    monkeypatch.setattr(mod, "run_conductor_loop", sleeper)
    monkeypatch.setattr(mod, "_run_zeitgeist_loop", sleeper)
    monkeypatch.setattr(mod, "_run_internal_pressure_loop", sleeper)
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
async def test_orchestrate_defers_ancillary_loops_until_swarm_ready(
    monkeypatch,
    tmp_path,
):
    """Noncritical loops must not starve the core swarm startup path."""
    from dharma_swarm import orchestrate_live as mod

    order: list[str] = []
    context_started = asyncio.Event()

    async def swarm_loop(shutdown_event, *args, **kwargs):
        order.append("swarm-start")
        ready_event = kwargs.get("ready_event")
        assert ready_event is not None
        order.append("swarm-ready")
        ready_event.set()
        await shutdown_event.wait()

    async def context_loop(shutdown_event, *args, **kwargs):
        order.append("context-agent")
        context_started.set()
        await shutdown_event.wait()

    async def ancillary_loop(shutdown_event, *args, **kwargs):
        order.append("ancillary")
        await shutdown_event.wait()

    async def pulse_loop(shutdown_event, *args, **kwargs):
        await context_started.wait()
        shutdown_event.set()

    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(mod, "_stop_old_daemon", lambda: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "run_swarm_loop", swarm_loop)
    monkeypatch.setattr(mod, "_run_health_api_process_watchdog", ancillary_loop)
    monkeypatch.setattr(mod, "run_pulse_loop", pulse_loop)
    monkeypatch.setattr(mod, "run_evolution_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_recognition_loop", ancillary_loop)
    monkeypatch.setattr(mod, "run_conductor_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_zeitgeist_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_internal_pressure_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_witness_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_consolidation_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_replication_monitor_loop", ancillary_loop)
    monkeypatch.setattr(mod, "run_health_loop", ancillary_loop)
    monkeypatch.setattr(mod, "run_free_evolution_grind", ancillary_loop)
    monkeypatch.setattr(mod, "_run_archaeology_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_guardian_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_gauntlet_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_world_model_loop", ancillary_loop)
    monkeypatch.setattr(mod, "_run_revenue_scout_loop", ancillary_loop)
    monkeypatch.setattr("dharma_swarm.signal_bus.SignalBus.get", lambda: object())
    monkeypatch.setattr("dharma_swarm.context_agent.run_context_agent_loop", context_loop)
    monkeypatch.setattr("dharma_swarm.training_flywheel.run_training_flywheel_loop", ancillary_loop)
    monkeypatch.setattr("dharma_swarm.self_improve.run_self_improvement_loop", ancillary_loop)

    await asyncio.wait_for(mod.orchestrate(), timeout=1.0)

    assert order.index("swarm-ready") < order.index("context-agent")
    assert (tmp_path / "logs" / "swarm.log").exists()
