from __future__ import annotations

from pathlib import Path

from dharma_swarm.loop_supervisor import LoopSupervisor, cmd_loop_status
from dharma_swarm.self_improve import run_self_improvement_loop


def test_registered_loop_starts_never_started(monkeypatch) -> None:
    monkeypatch.setattr("dharma_swarm.loop_supervisor.time.monotonic", lambda: 100.0)
    supervisor = LoopSupervisor()
    supervisor.register_loop("swarm", expected_interval=10.0)

    health = supervisor.status()["loops"]["swarm"]

    assert health["state"] == "NEVER_STARTED"
    assert health["is_stalled"] is False
    assert health["stale_seconds"] == 0.0


def test_never_started_escalates_to_stalled_and_alerts(monkeypatch, tmp_path) -> None:
    now = 100.0
    monkeypatch.setattr("dharma_swarm.loop_supervisor.time.monotonic", lambda: now)
    monkeypatch.setattr(
        "dharma_swarm.loop_supervisor.ALERT_FILE", tmp_path / "loop-alert.md"
    )
    supervisor = LoopSupervisor()
    supervisor.register_loop("swarm", expected_interval=10.0)
    now = 121.0

    health = supervisor.status()["loops"]["swarm"]
    alerts = supervisor.tick()

    assert health["state"] == "STALLED"
    assert health["is_stalled"] is True
    assert health["stale_seconds"] == 21.0
    assert [alert.alert_type for alert in alerts] == ["LOOP_STALL"]


def test_disabled_loop_never_stalls_or_alerts(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr("dharma_swarm.loop_supervisor.time.monotonic", lambda: now)
    supervisor = LoopSupervisor()
    supervisor.register_loop("pulse", expected_interval=10.0)
    supervisor.mark_disabled("pulse", "CLAUDECODE nested-session guard")
    now = 1000.0

    health = supervisor.status()["loops"]["pulse"]

    assert health["state"] == "DISABLED"
    assert health["is_stalled"] is False
    assert health["disabled_reason"] == "CLAUDECODE nested-session guard"
    assert supervisor.tick() == []


def test_record_tick_moves_loop_to_running(monkeypatch) -> None:
    monkeypatch.setattr("dharma_swarm.loop_supervisor.time.monotonic", lambda: 100.0)
    supervisor = LoopSupervisor()
    supervisor.register_loop("swarm", expected_interval=10.0)
    supervisor.record_tick("swarm")

    health = supervisor.status()["loops"]["swarm"]

    assert health["state"] == "RUNNING"
    assert health["is_stalled"] is False
    assert health["tick_count"] == 1


def test_cli_never_renders_never_started_as_ok(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        LoopSupervisor,
        "load_state",
        staticmethod(
            lambda: {
                "loops": {
                    "swarm": {
                        "state": "NEVER_STARTED",
                        "last_tick": 0.0,
                        "tick_count": 0,
                        "error_count": 0,
                        "stale_seconds": 2.0,
                        "is_stalled": False,
                    }
                }
            }
        ),
    )

    assert cmd_loop_status() == 0
    output = capsys.readouterr().out
    assert "NEVER_STARTED" in output
    assert " OK " not in output


def test_orchestrator_registers_every_factory_loop() -> None:
    source = Path("dharma_swarm/orchestrate_live.py").read_text(encoding="utf-8")
    interval_block = source.split("_loop_intervals = {", 1)[1].split("}", 1)[0]

    for loop_name in ("archaeology", "guardian", "health-api", "gauntlet", "world-model"):
        assert f'"{loop_name}"' in interval_block


async def test_self_improve_ticks_when_feature_is_disabled(monkeypatch) -> None:
    class Recorder:
        names: list[str] = []

        def record_tick(self, name: str) -> None:
            self.names.append(name)

    class OneCycleEvent:
        def is_set(self) -> bool:
            return False

        async def wait(self) -> bool:
            return True

    recorder = Recorder()
    monkeypatch.setattr("dharma_swarm.self_improve.is_enabled", lambda: False)

    await run_self_improvement_loop(
        OneCycleEvent(),
        interval=1,
        supervisor=recorder,
    )

    assert recorder.names == ["self-improve"]


def test_every_registered_factory_threads_supervisor_handle() -> None:
    source = Path("dharma_swarm/orchestrate_live.py").read_text(encoding="utf-8")
    factories = source.split("task_factories: dict[str, Any] = {", 1)[1].split(
        "optional_clean_exit", 1
    )[0]

    for loop_name in (
        "pulse",
        "recognition",
        "conductors",
        "context-agent",
        "zeitgeist",
        "internal-pressure",
        "witness",
        "consolidation",
        "replication",
        "flywheel",
        "health",
        "self-improve",
        "free-grind",
        "archaeology",
        "guardian",
        "health-api",
        "gauntlet",
        "world-model",
        "revenue-scout",
    ):
        line = next(
            row for row in factories.splitlines() if f'"{loop_name}"' in row
        )
        if "lambda:" in line and "supervisor=" not in line:
            continuation = factories.split(line, 1)[1].split("),", 1)[0]
            assert "supervisor=_supervisor" in continuation
