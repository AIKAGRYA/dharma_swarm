"""WP-LC1 — 4-state loop-health honesty (LOOP1_CLOSURE_SPEC_2026-07-11 §6).

The structural lie being closed: a never-started loop rendered OK, named loops
could not tick, and five live factory loops were invisible even to
registration.  These tests pin the honest 4-state contract:
NEVER_STARTED | RUNNING | STALLED | DISABLED.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import dharma_swarm.loop_supervisor as loop_supervisor_module
from dharma_swarm.loop_supervisor import (
    LoopHealth,
    LoopSupervisor,
    cmd_loop_status,
)

FACTORY_ONLY_LOOPS = ("archaeology", "guardian", "health-api", "gauntlet", "world-model")


# ---------------------------------------------------------------------------
# LoopHealth.state — the 4-state property
# ---------------------------------------------------------------------------


class TestLoopHealthState:
    def test_never_started_state(self):
        h = LoopHealth(name="x")
        assert h.state == "NEVER_STARTED"

    def test_never_started_is_never_ok_or_running(self):
        h = LoopHealth(name="x")
        assert h.state not in ("OK", "RUNNING")

    def test_running_state_after_recent_tick(self):
        h = LoopHealth(name="x", expected_interval=60.0)
        h.last_tick = time.monotonic()
        assert h.state == "RUNNING"

    def test_stalled_state(self):
        h = LoopHealth(name="x", expected_interval=1.0)
        h.last_tick = time.monotonic() - 100.0
        assert h.state == "STALLED"

    def test_disabled_state_wins_over_never_started(self):
        h = LoopHealth(name="x", disabled=True, disabled_reason="env gate")
        assert h.state == "DISABLED"

    def test_to_dict_carries_state_and_compat_is_stalled(self):
        h = LoopHealth(name="x")
        d = h.to_dict()
        assert d["state"] == "NEVER_STARTED"
        assert d["is_stalled"] is False  # compat field preserved

    def test_registered_at_recorded_by_register_loop(self):
        sup = LoopSupervisor()
        before = time.monotonic()
        sup.register_loop("a", expected_interval=60.0)
        assert sup._loops["a"].registered_at >= before


# ---------------------------------------------------------------------------
# NEVER_STARTED escalation — same alert channel as LOOP_STALL
# ---------------------------------------------------------------------------


class TestNeverStartedAlarm:
    def test_no_alarm_before_two_intervals(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.ALERT_FILE", tmp_path / "alert.md")
        sup = LoopSupervisor()
        sup.register_loop("slow", expected_interval=3600.0)
        alerts = sup.tick()
        assert [a for a in alerts if a.loop_name == "slow"] == []

    def test_alarm_after_two_intervals(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.ALERT_FILE", tmp_path / "alert.md")
        clock = SimpleNamespace(now=1.0)
        fake_time = SimpleNamespace(monotonic=lambda: clock.now)
        monkeypatch.setattr(loop_supervisor_module, "time", fake_time)
        sup = LoopSupervisor()
        sup.register_loop("dead", expected_interval=1.0)
        clock.now = 4.0
        alerts = sup.tick()
        never_started = [a for a in alerts if a.alert_type == "LOOP_NEVER_STARTED"]
        assert len(never_started) == 1
        assert never_started[0].loop_name == "dead"

    def test_disabled_exempt_from_alarms(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.ALERT_FILE", tmp_path / "alert.md")
        sup = LoopSupervisor()
        sup.register_loop("gated", expected_interval=1.0)
        sup._loops["gated"].registered_at = time.monotonic() - 100.0
        sup.mark_disabled("gated", "env gate decidable at registration")
        alerts = sup.tick()
        assert [a for a in alerts if a.loop_name == "gated"] == []

    def test_tick_transitions_out_of_never_started(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.ALERT_FILE", tmp_path / "alert.md")
        sup = LoopSupervisor()
        sup.register_loop("late", expected_interval=1.0)
        sup._loops["late"].registered_at = time.monotonic() - 100.0
        sup.record_tick("late")
        assert sup._loops["late"].state == "RUNNING"
        alerts = sup.tick()
        assert [a for a in alerts if a.alert_type == "LOOP_NEVER_STARTED"] == []

    def test_mark_disabled_unknown_loop_is_noop(self):
        sup = LoopSupervisor()
        sup.mark_disabled("ghost", "no such loop")  # must not raise


# ---------------------------------------------------------------------------
# Registration honesty — the five factory-only loops become visible
# ---------------------------------------------------------------------------


class TestFactoryLoopRegistration:
    def test_five_factory_loops_in_loop_intervals(self):
        source = Path("dharma_swarm/orchestrate_live.py").read_text(encoding="utf-8")
        interval_block = source.split("_loop_intervals = {", 1)[1].split("}", 1)[0]
        for name in FACTORY_ONLY_LOOPS:
            assert f'"{name}"' in interval_block, (
                f"factory loop {name!r} is not registered in _loop_intervals — "
                "record_tick silently no-ops for unregistered names"
            )

    def test_pulse_marked_disabled_under_claudecode(self):
        source = Path("dharma_swarm/orchestrate_live.py").read_text(encoding="utf-8")
        assert 'mark_disabled("pulse"' in source, (
            "pulse's CLAUDECODE pre-loop return must surface as DISABLED, "
            "never as a fake tick"
        )

    def test_imported_loop_bodies_tick(self):
        # flywheel has a hardcoded 60s boot delay, so its tick is pinned at
        # source level; the other two are behaviorally tested below.
        flywheel = Path("dharma_swarm/training_flywheel.py").read_text(encoding="utf-8")
        assert 'record_tick("flywheel")' in flywheel
        context_agent = Path("dharma_swarm/context_agent.py").read_text(encoding="utf-8")
        assert 'record_tick("context-agent")' in context_agent
        self_improve = Path("dharma_swarm/self_improve.py").read_text(encoding="utf-8")
        assert 'record_tick("self-improve")' in self_improve


# ---------------------------------------------------------------------------
# Per-iteration tick BEFORE the per-iteration guard (alive-but-idle visible)
# ---------------------------------------------------------------------------


class _StubSupervisor:
    def __init__(self) -> None:
        self.ticks: list[str] = []

    def record_tick(self, name: str) -> None:
        self.ticks.append(name)


class TestAliveButIdleVisible:
    # sync wrappers over asyncio.run — packet gates run with
    # PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, so pytest-asyncio is unavailable there.
    def test_self_improve_ticks_while_disabled(self, monkeypatch):
        from dharma_swarm import self_improve as si

        monkeypatch.setattr(si, "is_enabled", lambda: False)
        stub = _StubSupervisor()

        async def scenario() -> None:
            shutdown = asyncio.Event()

            async def _stop_soon():
                await asyncio.sleep(0.05)
                shutdown.set()

            stopper = asyncio.ensure_future(_stop_soon())
            await si.run_self_improvement_loop(shutdown, interval=0.01, supervisor=stub)
            await stopper

        asyncio.run(scenario())
        assert "self-improve" in stub.ticks, (
            "the guarded loop must tick BEFORE its is_enabled() skip so "
            "alive-but-intentionally-idle is visible"
        )

    def test_context_agent_ticks_per_iteration(self, monkeypatch):
        from dharma_swarm import context_agent as ca

        class _StubAgent:
            _cycle_count = 0

            def __init__(self, *args, **kwargs) -> None:
                pass

            async def run_cycle(self) -> None:
                _StubAgent._cycle_count += 1

        monkeypatch.setattr(ca, "ContextAgent", _StubAgent)
        monkeypatch.setattr(ca, "CONTEXT_AGENT_INTERVAL", 0.01)
        stub = _StubSupervisor()

        async def scenario() -> None:
            shutdown = asyncio.Event()

            async def _stop_soon():
                await asyncio.sleep(0.05)
                shutdown.set()

            stopper = asyncio.ensure_future(_stop_soon())
            await ca.run_context_agent_loop(shutdown, supervisor=stub)
            await stopper

        asyncio.run(scenario())
        assert "context-agent" in stub.ticks


# ---------------------------------------------------------------------------
# CLI render — 4-state, NEVER_STARTED is never OK
# ---------------------------------------------------------------------------


class TestCliRender:
    def _write_state(self, sup: LoopSupervisor) -> None:
        sup.save_state()

    def test_cmd_loop_status_renders_never_started(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.SUPERVISOR_STATE", tmp_path)
        sup = LoopSupervisor()
        sup.register_loop("cold", expected_interval=60.0)
        sup.save_state()
        assert cmd_loop_status() == 0
        out = capsys.readouterr().out
        cold_line = next(line for line in out.splitlines() if "cold" in line)
        assert "NEVER_STARTED" in cold_line
        assert " OK" not in cold_line

    def test_cmd_loop_status_renders_disabled(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.SUPERVISOR_STATE", tmp_path)
        sup = LoopSupervisor()
        sup.register_loop("gated", expected_interval=60.0)
        sup.mark_disabled("gated", "env gate")
        sup.save_state()
        assert cmd_loop_status() == 0
        out = capsys.readouterr().out
        gated_line = next(line for line in out.splitlines() if "gated" in line)
        assert "DISABLED" in gated_line

    def test_cmd_loop_status_renders_running(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("dharma_swarm.loop_supervisor.SUPERVISOR_STATE", tmp_path)
        sup = LoopSupervisor()
        sup.register_loop("warm", expected_interval=60.0)
        sup.record_tick("warm")
        sup.save_state()
        assert cmd_loop_status() == 0
        out = capsys.readouterr().out
        warm_line = next(line for line in out.splitlines() if "warm" in line)
        assert "RUNNING" in warm_line

    def test_cmd_loop_status_legacy_state_file_never_started_not_ok(
        self, tmp_path, monkeypatch, capsys
    ):
        # A state.json written by the pre-WP-LC1 daemon has no "state" key;
        # the renderer must still refuse to call a never-started loop OK.
        import json

        monkeypatch.setattr("dharma_swarm.loop_supervisor.SUPERVISOR_STATE", tmp_path)
        legacy = {
            "loops": {
                "old-cold": {
                    "name": "old-cold",
                    "last_tick": 0.0,
                    "expected_interval": 60.0,
                    "tick_count": 0,
                    "error_count": 0,
                    "stale_seconds": 0.0,
                    "is_stalled": False,
                }
            },
            "recent_alerts": [],
            "total_alerts": 0,
        }
        (tmp_path / "state.json").write_text(json.dumps(legacy))
        assert cmd_loop_status() == 0
        out = capsys.readouterr().out
        line = next(row for row in out.splitlines() if "old-cold" in row)
        assert "NEVER_STARTED" in line
        assert " OK" not in line


# ---------------------------------------------------------------------------
# Negative control (packet-declared): asserting the old lie must FAIL
# ---------------------------------------------------------------------------


def test_negative_control_never_started_asserted_ok_fails():
    """A LoopHealth(last_tick=0) fixture asserted OK must exit nonzero."""
    lie = (
        "from dharma_swarm.loop_supervisor import LoopHealth\n"
        "h = LoopHealth(name='x')\n"
        "assert h.state == 'OK'\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", lie],
        capture_output=True,
        timeout=120,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert proc.returncode != 0
