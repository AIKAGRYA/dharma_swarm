from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import threading
from typing import Any

import pytest

from scripts.ops import vps_resource_guard as guard


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "vps-resource-guard"
MIB = 1024 * 1024


def config_data(tmp_path: Path, *, targets: list[dict[str, Any]] | None = None) -> dict:
    return {
        "guard": {
            "host": "test-host",
            "expected_hostname": socket.gethostname(),
            "memory_ceiling_percent": 85.0,
            "recovery_percent": 78.0,
            "critical_percent": 92.0,
            "minimum_candidate_memory_bytes": 128 * 1024 * 1024,
            "poll_interval_seconds": 5.0,
            "cooldown_seconds": 300.0,
            "state_file": str(tmp_path / "state" / "state.json"),
            "receipt_file": str(tmp_path / "log" / "receipts.jsonl"),
            "receipt_max_bytes": 1024 * 1024,
        },
        "targets": targets
        or [
            {
                "id": "ollama",
                "action": "systemd-restart",
                "target": "ollama.service",
                "priority": 10,
            }
        ],
    }


def parsed_config(
    tmp_path: Path, *, targets: list[dict[str, Any]] | None = None
) -> guard.GuardConfig:
    return guard.parse_config(config_data(tmp_path, targets=targets))


class StubQuery:
    def __init__(self, memory: dict[str, int]) -> None:
        self.memory = memory
        self.queried: list[str] = []

    def memory_bytes(self, target: guard.Target) -> int:
        self.queried.append(target.id)
        return self.memory[target.id]


class StubExecutor:
    def __init__(self, result: guard.ActionResult | None = None) -> None:
        self.executed: list[str] = []
        self.result = result or guard.ActionResult(True, 0)

    def execute(self, target_id: str) -> guard.ActionResult:
        self.executed.append(target_id)
        return self.result


class ExplodingExecutor:
    def execute(self, target_id: str) -> guard.ActionResult:
        raise AssertionError(f"dry run invoked action for {target_id}")


class ExplodingQuery:
    def memory_bytes(self, target: guard.Target) -> int:
        raise AssertionError(f"unexpected query for {target.id}")


class FailingQuery:
    def __init__(self, message: str) -> None:
        self.message = message

    def memory_bytes(self, _target: guard.Target) -> int:
        raise guard.QueryError(self.message)


def pressure_snapshot() -> guard.MemorySnapshot:
    return guard.MemorySnapshot(total_bytes=10_000, available_bytes=1_000)


def test_shipped_host_configs_parse_with_expected_thresholds_and_targets() -> None:
    expected = {
        "rushabdev": [
            ("systemd-restart", "ollama.service"),
            ("systemd-user-restart", "hermes-gateway.service"),
            ("systemd-user-restart", "openclaw-gateway.service"),
        ],
        "agni": [
            ("systemd-restart", "ollama.service"),
            ("systemd-user-restart", "hermes-gateway.service"),
        ],
        "meghadharma": [
            ("docker-restart", "dharma-command-backend"),
            ("docker-restart", "hermes"),
            ("docker-restart", "dharma-swarm"),
            ("docker-restart", "dharma-command-edge"),
        ],
    }
    for host, expected_targets in expected.items():
        config = guard.load_config(DEPLOY / "configs" / f"{host}.toml")
        assert config.host == host
        assert (
            config.expected_hostname
            == {
                "rushabdev": "openclaw23onubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01",
                "agni": "agni-openclaw",
                "meghadharma": "meghadharma-cloud",
            }[host]
        )
        assert config.memory_ceiling_percent == 85.0
        assert config.recovery_percent == 78.0
        assert config.critical_percent == 92.0
        assert config.minimum_candidate_memory_bytes == 128 * 1024 * 1024
        assert config.poll_interval_seconds == 5.0
        assert [(target.action, target.target) for target in config.targets] == (
            expected_targets
        )
        assert config.state_file.is_relative_to("/var/lib")


@pytest.mark.parametrize(
    ("recovery", "ceiling", "critical"),
    [
        (85.0, 85.0, 92.0),
        (78.0, 92.0, 92.0),
        (0.0, 85.0, 92.0),
        (78.0, 85.0, 101.0),
    ],
)
def test_config_rejects_invalid_threshold_order(
    tmp_path: Path, recovery: float, ceiling: float, critical: float
) -> None:
    data = config_data(tmp_path)
    data["guard"].update(
        recovery_percent=recovery,
        memory_ceiling_percent=ceiling,
        critical_percent=critical,
    )
    with pytest.raises(guard.ConfigError, match="thresholds"):
        guard.parse_config(data)


def test_config_rejects_unknown_keys_and_non_five_second_loop(tmp_path: Path) -> None:
    data = config_data(tmp_path)
    data["guard"]["mystery"] = True
    with pytest.raises(guard.ConfigError, match="unknown keys"):
        guard.parse_config(data)

    data = config_data(tmp_path)
    data["guard"]["poll_interval_seconds"] = 10.0
    with pytest.raises(guard.ConfigError, match="must be 5 seconds"):
        guard.parse_config(data)


def test_config_enforces_host_binding_and_128_mib_candidate_floor(
    tmp_path: Path,
) -> None:
    data = config_data(tmp_path)
    data["guard"]["expected_hostname"] = "invalid hostname"
    with pytest.raises(guard.ConfigError, match="expected_hostname"):
        guard.parse_config(data)

    data = config_data(tmp_path)
    data["guard"]["minimum_candidate_memory_bytes"] = 128 * MIB - 1
    with pytest.raises(guard.ConfigError, match="at least"):
        guard.parse_config(data)


def test_malformed_toml_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("[guard\nnot = toml", encoding="utf-8")
    with pytest.raises(guard.ConfigError, match="malformed TOML"):
        guard.load_config(path)


@pytest.mark.parametrize(
    ("action", "target", "message"),
    [
        ("shell", "echo-memory", "unsupported"),
        ("systemd-restart", "not-a-socket", "explicit systemd .service"),
        ("systemd-restart", "--now.service", "explicit systemd .service"),
        ("docker-restart", "container;prune", "explicit Docker container"),
    ],
)
def test_unknown_or_unsafe_actions_and_targets_are_rejected(
    tmp_path: Path, action: str, target: str, message: str
) -> None:
    targets = [{"id": "candidate", "action": action, "target": target, "priority": 1}]
    with pytest.raises(guard.ConfigError, match=message):
        parsed_config(tmp_path, targets=targets)


def test_action_executor_rejects_unknown_target_and_unknown_action() -> None:
    configured = guard.Target("ollama", "systemd-restart", "ollama.service", 10)
    executor = guard.ActionExecutor([configured])
    with pytest.raises(guard.ActionError, match="not allowlisted"):
        executor.execute("outsider")

    invalid = guard.Target("invalid", "kill-pid", "123", 10)
    executor = guard.ActionExecutor([invalid])
    with pytest.raises(guard.ActionError, match="action is not allowlisted"):
        executor.execute("invalid")


def test_thresholds_and_hysteresis(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)

    assert guard.evaluate_pressure(84.9, was_active=False, config=config) == (
        False,
        guard.PressureLevel.NORMAL,
    )
    assert guard.evaluate_pressure(85.0, was_active=False, config=config) == (
        True,
        guard.PressureLevel.PRESSURE,
    )
    assert guard.evaluate_pressure(80.0, was_active=True, config=config) == (
        True,
        guard.PressureLevel.HYSTERESIS,
    )
    assert guard.evaluate_pressure(78.0, was_active=True, config=config) == (
        False,
        guard.PressureLevel.RECOVERED,
    )
    assert guard.evaluate_pressure(92.0, was_active=False, config=config) == (
        True,
        guard.PressureLevel.CRITICAL,
    )


def test_hysteresis_holds_pressure_state_without_shedding(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)
    state_store = guard.StateStore(config.state_file)
    state_store.save(guard.GuardState(pressure_active=True))
    controller = guard.GuardController(
        config,
        state_store=state_store,
        target_query=ExplodingQuery(),  # type: ignore[arg-type]
        executor=ExplodingExecutor(),  # type: ignore[arg-type]
        memory_reader=lambda: guard.MemorySnapshot(10_000, 2_000),
        clock=lambda: 1000.0,
    )

    result = controller.run_cycle()

    assert result.level is guard.PressureLevel.HYSTERESIS
    assert result.pressure_active is True
    assert result.decision == "hysteresis-hold"
    assert result.selected_target_id is None


def test_controller_fails_closed_on_runtime_hostname_mismatch(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)
    with pytest.raises(guard.HostBindingError, match="runtime hostname mismatch"):
        guard.GuardController(config, hostname_reader=lambda: "wrong-host")
    assert not config.state_file.exists()
    assert not config.receipt_file.exists()


def test_memavailable_is_used_for_global_pressure(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       1000000 kB\n"
        "MemFree:          10000 kB\n"
        "MemAvailable:    200000 kB\n",
        encoding="ascii",
    )
    snapshot = guard.read_memory_snapshot(meminfo)
    assert snapshot.total_bytes == 1_000_000 * 1024
    assert snapshot.available_bytes == 200_000 * 1024
    assert snapshot.used_percent == 80.0


def test_state_store_persists_hysteresis_and_per_target_cooldown(
    tmp_path: Path,
) -> None:
    path = tmp_path / "var" / "lib" / "state.json"
    store = guard.StateStore(path)
    store.save(guard.GuardState(True, {"ollama": 1234.5}, 1200.0))

    loaded = guard.StateStore(path).load()
    assert loaded.pressure_active is True
    assert loaded.last_attempt_epoch == {"ollama": 1234.5}
    assert loaded.last_global_attempt_epoch == 1200.0
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_instance_lock_rejects_a_second_controller_for_same_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json.lock"

    with guard.InstanceLock(path):
        with pytest.raises(guard.GuardError, match="another guard instance"):
            with guard.InstanceLock(path):
                pass

    with guard.InstanceLock(path):
        assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_state_and_receipt_namespace_changes_are_directory_fsynced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fsynced: list[Path] = []
    monkeypatch.setattr(guard, "_fsync_directory", fsynced.append)
    state_path = tmp_path / "state" / "state.json"
    receipt_path = tmp_path / "receipts" / "receipts.jsonl"

    guard.StateStore(state_path).save(guard.GuardState())
    writer = guard.ReceiptWriter(receipt_path, max_bytes=30)
    writer.append({"record": "first-record"})
    writer.append({"record": "second-record"})

    assert fsynced == [
        state_path.parent,
        receipt_path.parent,
        receipt_path.parent,
        receipt_path.parent,
    ]


def test_state_store_clamps_small_future_skew_and_rejects_large_skew(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    store = guard.StateStore(path)
    store.save(guard.GuardState(True, {"ollama": 1050.0}, 1300.0))

    loaded = store.load(now=1000.0)
    assert loaded.last_attempt_epoch == {"ollama": 1000.0}
    assert loaded.last_global_attempt_epoch == 1000.0
    assert guard.StateStore(path).load(now=1000.0) == loaded

    store.save(guard.GuardState(True, {"ollama": 1300.001}, 1000.0))
    with pytest.raises(guard.StateError, match="too far future"):
        store.load(now=1000.0)


def test_corrupt_state_is_quarantined_and_recovers_fail_safe(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)
    config.state_file.parent.mkdir(parents=True)
    corrupt_payload = (
        '{"version":1,"pressure_active":false,"last_attempt_epoch":{"ollama":"now"}}'
    )
    config.state_file.write_text(corrupt_payload, encoding="utf-8")

    controller = guard.GuardController(config, clock=lambda: 1000.0)

    corrupt_path = config.state_file.with_name(f"{config.state_file.name}.corrupt")
    assert corrupt_path.read_text(encoding="utf-8") == corrupt_payload
    assert controller.state.pressure_active is True
    assert controller.state.last_global_attempt_epoch == 1000.0
    assert controller.state.pending_state_fault is None
    receipt = json.loads(config.receipt_file.read_text(encoding="utf-8"))
    assert receipt["receipt_reasons"] == ["state-fault"]
    assert receipt["decision"] == "state-fault-fail-safe"


def test_cooldown_prevents_query_and_second_action(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)
    state_store = guard.StateStore(config.state_file)
    state_store.save(guard.GuardState(True, {"ollama": 900.0}))
    query = StubQuery({"ollama": 500})
    executor = StubExecutor()
    controller = guard.GuardController(
        config,
        state_store=state_store,
        target_query=query,  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
    )

    result = controller.run_cycle()

    assert result.decision == "no-eligible-target"
    assert query.queried == []
    assert executor.executed == []


def test_persisted_global_settle_blocks_all_actions_even_at_critical(
    tmp_path: Path,
) -> None:
    targets = [
        {
            "id": "alpha",
            "action": "docker-restart",
            "target": "alpha",
            "priority": 10,
        },
        {
            "id": "beta",
            "action": "docker-restart",
            "target": "beta",
            "priority": 10,
        },
    ]
    config = parsed_config(tmp_path, targets=targets)
    executor = StubExecutor()
    first = guard.GuardController(
        config,
        target_query=StubQuery({"alpha": 300 * MIB, "beta": 200 * MIB}),  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
    )
    assert first.run_cycle().selected_target_id == "alpha"
    assert (
        guard.StateStore(config.state_file).load().last_global_attempt_epoch == 1000.0
    )

    normal_settle = guard.GuardController(
        config,
        target_query=ExplodingQuery(),  # type: ignore[arg-type]
        executor=ExplodingExecutor(),  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1059.999,
    )
    assert normal_settle.run_cycle().decision == "global-settle"

    def critical_snapshot() -> guard.MemorySnapshot:
        return guard.MemorySnapshot(10_000, 500)

    during_settle = guard.GuardController(
        config,
        target_query=ExplodingQuery(),  # type: ignore[arg-type]
        executor=ExplodingExecutor(),  # type: ignore[arg-type]
        memory_reader=critical_snapshot,
        clock=lambda: 1014.999,
    )
    result = during_settle.run_cycle()
    assert result.level is guard.PressureLevel.CRITICAL
    assert result.decision == "global-settle"
    assert result.selected_target_id is None

    after_settle = guard.GuardController(
        config,
        target_query=StubQuery({"beta": 200 * MIB}),  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        memory_reader=critical_snapshot,
        clock=lambda: 1015.0,
    )
    assert after_settle.run_cycle().selected_target_id == "beta"
    assert executor.executed == ["alpha", "beta"]


def test_candidate_below_128_mib_floor_is_never_restarted(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)
    executor = StubExecutor()
    controller = guard.GuardController(
        config,
        target_query=StubQuery({"ollama": 128 * MIB - 1}),  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
    )

    result = controller.run_cycle()

    assert result.decision == "no-eligible-target"
    assert executor.executed == []
    receipt = json.loads(config.receipt_file.read_text(encoding="utf-8"))
    assert receipt["candidates"] == [
        {
            "id": "ollama",
            "memory_bytes": 128 * MIB - 1,
            "minimum_candidate_memory_bytes": 128 * MIB,
            "status": "below-minimum-memory",
        }
    ]


def test_only_one_action_per_cycle_and_selection_is_deterministic(
    tmp_path: Path,
) -> None:
    targets = [
        {
            "id": "alpha",
            "action": "docker-restart",
            "target": "alpha",
            "priority": 10,
        },
        {
            "id": "beta",
            "action": "docker-restart",
            "target": "beta",
            "priority": 10,
        },
        {
            "id": "gamma",
            "action": "docker-restart",
            "target": "gamma",
            "priority": 10,
        },
    ]
    config = parsed_config(tmp_path, targets=targets)
    query = StubQuery({"alpha": 200 * MIB, "beta": 900 * MIB, "gamma": 900 * MIB})
    executor = StubExecutor()
    controller = guard.GuardController(
        config,
        target_query=query,  # type: ignore[arg-type]
        executor=executor,  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
    )

    result = controller.run_cycle()

    assert query.queried.count("alpha") == 1
    assert query.queried.count("beta") == 2
    assert query.queried.count("gamma") == 1
    assert result.selected_target_id == "beta"
    assert executor.executed == ["beta"]
    persisted = guard.StateStore(config.state_file).load()
    assert persisted.last_attempt_epoch == {"beta": 1000.0}


def test_configured_priority_precedes_candidate_memory(tmp_path: Path) -> None:
    targets = [
        {
            "id": "first",
            "action": "docker-restart",
            "target": "first",
            "priority": 1,
        },
        {
            "id": "large",
            "action": "docker-restart",
            "target": "large",
            "priority": 20,
        },
    ]
    config = parsed_config(tmp_path, targets=targets)
    executor = StubExecutor()
    controller = guard.GuardController(
        config,
        target_query=StubQuery(  # type: ignore[arg-type]
            {"first": 200 * MIB, "large": 1000 * MIB}
        ),
        executor=executor,  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
    )
    controller.run_cycle()
    assert executor.executed == ["first"]


def test_dry_run_writes_receipt_without_action_or_cooldown_state(
    tmp_path: Path,
) -> None:
    config = parsed_config(tmp_path)
    controller = guard.GuardController(
        config,
        dry_run=True,
        target_query=StubQuery({"ollama": 200 * MIB}),  # type: ignore[arg-type]
        executor=ExplodingExecutor(),  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
    )

    result = controller.run_cycle()

    assert result.decision == "dry-run-would-restart"
    assert not config.state_file.exists()
    receipt = json.loads(config.receipt_file.read_text(encoding="utf-8"))
    assert receipt["dry_run"] is True
    assert receipt["selected_target_id"] == "ollama"
    assert receipt["action"]["error"] == "dry-run"


def test_action_receipt_records_measured_candidate_and_result(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)
    controller = guard.GuardController(
        config,
        target_query=StubQuery({"ollama": 200 * MIB}),  # type: ignore[arg-type]
        executor=StubExecutor(guard.ActionResult(False, 1, "nonzero-exit")),  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
        event_id_factory=lambda: "fixed-event-id",
    )
    result = controller.run_cycle()

    assert result.decision == "restart-rejected"
    records = [
        json.loads(line)
        for line in config.receipt_file.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    intent, receipt = records
    assert intent["receipt_reasons"] == ["action-intent"]
    assert intent["decision"] == "restart-intent"
    assert intent["action_phase"] == "intent"
    assert intent["event_id"] == "fixed-event-id"
    assert receipt["schema"] == "vps-resource-guard.receipt.v1"
    assert receipt["receipt_reasons"] == ["action-outcome"]
    assert receipt["action_phase"] == "outcome"
    assert receipt["event_id"] == intent["event_id"]
    assert receipt["selected_memory_bytes"] == 200 * MIB
    assert receipt["postcondition"] == {
        "memory_bytes": 200 * MIB,
        "status": "ok",
    }
    assert receipt["action"] == {
        "error": "nonzero-exit",
        "returncode": 1,
        "succeeded": False,
    }


def test_receipts_rotate_at_configured_bound(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    writer = guard.ReceiptWriter(path, max_bytes=30)
    writer.append({"record": "first-record"})
    writer.append({"record": "second-record"})
    assert path.with_name("receipts.jsonl.1").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["record"] == "second-record"


def test_one_receipt_cannot_exceed_the_configured_bound(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    writer = guard.ReceiptWriter(path, max_bytes=10)

    with pytest.raises(guard.GuardError, match="one receipt exceeds"):
        writer.append({"record": "larger-than-ten-bytes"})

    assert not path.exists()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("12.5MiB / 2GiB", int(12.5 * 1024**2)), ("900kB / 1GB", 900_000)],
)
def test_parse_docker_current_memory(raw: str, expected: int) -> None:
    assert guard.parse_memory_size(raw) == expected


def test_target_queries_run_in_parallel_and_results_keep_configured_order() -> None:
    targets = [
        guard.Target(name, "docker-restart", name, 10)
        for name in ("alpha", "beta", "gamma")
    ]
    barrier = threading.Barrier(len(targets))

    class BarrierQuery:
        def memory_bytes(self, target: guard.Target) -> int:
            barrier.wait(timeout=1.0)
            return {"alpha": 1, "beta": 2, "gamma": 3}[target.id]

    results = guard.query_target_memories(
        targets,
        BarrierQuery(),  # type: ignore[arg-type]
    )

    assert list(results) == ["alpha", "beta", "gamma"]
    assert results == {
        "alpha": (1, None),
        "beta": (2, None),
        "gamma": (3, None),
    }


def test_target_query_commands_have_five_second_timeout() -> None:
    observed_timeouts: list[float] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed_timeouts.append(kwargs["timeout"])
        return subprocess.CompletedProcess(command, 0, "200MiB / 1GiB\n", "")

    target = guard.Target("hermes", "docker-restart", "hermes", 10)
    assert guard.TargetMemoryQuery(runner=runner).memory_bytes(target) == 200 * MIB
    assert observed_timeouts == [5.0]


def test_systemd_user_query_uses_explicit_root_user_manager_argv() -> None:
    calls: list[list[str]] = []
    outputs = iter(["active\n", f"{200 * MIB}\n"])

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, next(outputs), "")

    target = guard.Target(
        "hermes-gateway",
        "systemd-user-restart",
        "hermes-gateway.service",
        10,
    )
    assert guard.TargetMemoryQuery(runner=runner).memory_bytes(target) == 200 * MIB
    prefix = ["systemctl", "--user", "show"]
    assert calls == [
        [
            *prefix,
            "--property=ActiveState",
            "--value",
            "--",
            "hermes-gateway.service",
        ],
        [
            *prefix,
            "--property=MemoryCurrent",
            "--value",
            "--",
            "hermes-gateway.service",
        ],
    ]


def test_query_error_has_bounded_sanitized_stderr() -> None:
    secret = "token=super-secret-value"

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 1, "", f"failed {secret} " + "x" * 400
        )

    target = guard.Target("hermes", "docker-restart", "hermes", 10)
    with pytest.raises(guard.QueryError) as error:
        guard.TargetMemoryQuery(runner=runner).memory_bytes(target)
    diagnostic = str(error.value)
    assert "super-secret-value" not in diagnostic
    assert "[REDACTED]" in diagnostic
    assert len(diagnostic) < 300


def test_executor_uses_argument_vector_without_shell(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    target = guard.Target("hermes", "docker-restart", "hermes", 10)
    result = guard.ActionExecutor(
        [target],
        runner=runner,
        docker_operation_lock_path=tmp_path / "operation.lock",
    ).execute("hermes")
    assert result.succeeded is True
    assert calls == [["docker", "restart", "--timeout", "10", "--", "hermes"]]


def test_docker_restart_refuses_while_scope_policy_operation_is_locked(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    lock_path = tmp_path / "operation.lock"
    target = guard.Target("hermes", "docker-restart", "hermes", 10)
    executor = guard.ActionExecutor(
        [target], runner=runner, docker_operation_lock_path=lock_path
    )

    with guard.InstanceLock(lock_path):
        result = executor.execute("hermes")

    assert result == guard.ActionResult(False, None, "operation-lock-busy")
    assert calls == []


def test_systemd_executor_waits_for_completed_restart_job() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    target = guard.Target("ollama", "systemd-restart", "ollama.service", 10)
    result = guard.ActionExecutor([target], runner=runner).execute("ollama")
    assert result.succeeded is True
    assert calls == [["systemctl", "restart", "--", "ollama.service"]]


def test_systemd_user_executor_uses_explicit_root_user_manager_argv() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    target = guard.Target(
        "hermes-gateway",
        "systemd-user-restart",
        "hermes-gateway.service",
        10,
    )
    result = guard.ActionExecutor([target], runner=runner).execute("hermes-gateway")
    assert result.succeeded is True
    assert calls == [
        [
            "systemctl",
            "--user",
            "restart",
            "--",
            "hermes-gateway.service",
        ]
    ]


def test_timeout_is_unknown_and_intent_precedes_execution(tmp_path: Path) -> None:
    config = parsed_config(tmp_path)

    class IntentCheckingExecutor:
        def execute(self, _target_id: str) -> guard.ActionResult:
            records = config.receipt_file.read_text(encoding="utf-8").splitlines()
            assert len(records) == 1
            assert json.loads(records[0])["action_phase"] == "intent"
            return guard.ActionResult(False, None, "timeout-unknown")

    controller = guard.GuardController(
        config,
        target_query=StubQuery({"ollama": 200 * MIB}),  # type: ignore[arg-type]
        executor=IntentCheckingExecutor(),  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: 1000.0,
        event_id_factory=lambda: "stable-timeout-event",
    )

    result = controller.run_cycle()

    assert result.decision == "restart-outcome-unknown"
    records = [
        json.loads(line)
        for line in config.receipt_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["action_phase"] for record in records] == ["intent", "outcome"]
    assert {record["event_id"] for record in records} == {"stable-timeout-event"}
    assert records[-1]["action"]["error"] == "timeout-unknown"
    assert records[-1]["postcondition"]["status"] == "ok"


def test_executor_classifies_subprocess_timeout_as_unknown() -> None:
    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, 30.0)

    target = guard.Target("ollama", "systemd-restart", "ollama.service", 10)
    result = guard.ActionExecutor([target], runner=runner).execute("ollama")
    assert result == guard.ActionResult(False, None, "timeout-unknown")


def test_normal_cycles_emit_first_receipt_then_five_minute_heartbeats(
    tmp_path: Path,
) -> None:
    config = parsed_config(tmp_path)
    now = [1000.0]
    controller = guard.GuardController(
        config,
        memory_reader=lambda: guard.MemorySnapshot(10_000, 3_000),
        clock=lambda: now[0],
    )

    controller.run_cycle()
    now[0] = 1005.0
    controller.run_cycle()
    now[0] = 1299.999
    controller.run_cycle()
    records = [
        json.loads(line)
        for line in config.receipt_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["receipt_reasons"] for record in records] == [["first-cycle"]]

    now[0] = 1300.0
    controller.run_cycle()
    records = [
        json.loads(line)
        for line in config.receipt_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["receipt_reasons"] for record in records] == [
        ["first-cycle"],
        ["heartbeat"],
    ]


def test_cooldown_cycles_are_bounded_by_same_heartbeat_interval(
    tmp_path: Path,
) -> None:
    data = config_data(tmp_path)
    data["guard"]["cooldown_seconds"] = 600.0
    config = guard.parse_config(data)
    state_store = guard.StateStore(config.state_file)
    state_store.save(guard.GuardState(True, {"ollama": 900.0}))
    now = [1000.0]
    controller = guard.GuardController(
        config,
        state_store=state_store,
        target_query=StubQuery({"ollama": 500}),  # type: ignore[arg-type]
        memory_reader=pressure_snapshot,
        clock=lambda: now[0],
    )

    controller.run_cycle()
    now[0] = 1005.0
    controller.run_cycle()
    now[0] = 1299.999
    controller.run_cycle()
    records = config.receipt_file.read_text(encoding="utf-8").splitlines()
    assert len(records) == 1

    now[0] = 1300.0
    controller.run_cycle()
    records = [
        json.loads(line)
        for line in config.receipt_file.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert records[-1]["receipt_reasons"] == ["heartbeat"]
    assert records[-1]["candidates"][0]["status"] == "cooldown"


def test_level_and_query_status_transitions_emit_event_receipts(
    tmp_path: Path,
) -> None:
    config = parsed_config(tmp_path)
    now = [1000.0]
    snapshot = [guard.MemorySnapshot(10_000, 3_000)]
    query = FailingQuery("temporary query failure")
    controller = guard.GuardController(
        config,
        target_query=query,  # type: ignore[arg-type]
        memory_reader=lambda: snapshot[0],
        clock=lambda: now[0],
    )

    controller.run_cycle()
    now[0] = 1005.0
    snapshot[0] = pressure_snapshot()
    controller.run_cycle()
    now[0] = 1010.0
    controller.run_cycle()
    query.message = "different query failure"
    now[0] = 1015.0
    controller.run_cycle()

    records = [
        json.loads(line)
        for line in config.receipt_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["receipt_reasons"] for record in records] == [
        ["first-cycle"],
        ["level-transition", "query-status-transition"],
        ["query-status-transition"],
    ]


def test_validate_config_has_no_runtime_side_effects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = DEPLOY / "configs" / "rushabdev.toml"
    destination = tmp_path / "rushabdev.toml"
    text = source.read_text(encoding="utf-8")
    text = text.replace(
        "/var/lib/vps-resource-guard/state.json", str(tmp_path / "state.json")
    ).replace(
        "/var/log/vps-resource-guard/receipts.jsonl",
        str(tmp_path / "receipts.jsonl"),
    )
    destination.write_text(text, encoding="utf-8")

    assert guard.main(["--config", str(destination), "--validate-config"]) == 0
    assert not (tmp_path / "state.json").exists()
    assert not (tmp_path / "receipts.jsonl").exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "expected_hostname": ("openclaw23onubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01"),
        "host": "rushabdev",
        "minimum_candidate_memory_bytes": 128 * MIB,
        "poll_interval_seconds": 5.0,
        "targets": ["ollama", "hermes-gateway", "openclaw-gateway"],
        "valid": True,
    }


def test_verify_host_mode_is_read_only_and_fails_closed_on_mismatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = config_data(tmp_path)
    data["guard"]["expected_hostname"] = "bound-host"
    config = guard.parse_config(data)
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[guard]",
                f'host = "{config.host}"',
                f'expected_hostname = "{config.expected_hostname}"',
                "memory_ceiling_percent = 85.0",
                "recovery_percent = 78.0",
                "critical_percent = 92.0",
                f"minimum_candidate_memory_bytes = {128 * MIB}",
                "poll_interval_seconds = 5.0",
                "cooldown_seconds = 300.0",
                f'state_file = "{config.state_file}"',
                f'receipt_file = "{config.receipt_file}"',
                "receipt_max_bytes = 1048576",
                "",
                "[[targets]]",
                'id = "ollama"',
                'action = "systemd-restart"',
                'target = "ollama.service"',
                "priority = 10",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(guard.socket, "gethostname", lambda: "wrong-host")
    assert guard.main(["--config", str(config_path), "--validate-config"]) == 0
    capsys.readouterr()
    assert guard.main(["--config", str(config_path), "--verify-host"]) == 2
    assert "runtime hostname mismatch" in capsys.readouterr().err
    assert not config.state_file.exists()
    assert not config.receipt_file.exists()


def test_self_test_targets_is_read_only_and_nonzero_on_query_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = parsed_config(tmp_path)
    monkeypatch.setattr(guard.socket, "gethostname", lambda: config.expected_hostname)
    monkeypatch.setattr(
        guard.TargetMemoryQuery,
        "memory_bytes",
        lambda _self, _target: 200 * MIB,
    )
    succeeded, summary = guard.self_test_targets(config)
    assert succeeded is True
    assert summary["valid"] is True
    assert summary["targets"][0]["memory_bytes"] == 200 * MIB
    assert not config.state_file.exists()
    assert not config.receipt_file.exists()

    def fail_query(_self: object, _target: guard.Target) -> int:
        raise guard.QueryError("target unavailable")

    monkeypatch.setattr(guard.TargetMemoryQuery, "memory_bytes", fail_query)
    succeeded, summary = guard.self_test_targets(config)
    assert succeeded is False
    assert summary["valid"] is False
    assert summary["targets"][0]["status"] == "error"

    monkeypatch.setattr(guard, "load_config", lambda _path: config)
    assert guard.main(["--self-test-targets"]) == 1
    cli_summary = json.loads(capsys.readouterr().out)
    assert cli_summary["valid"] is False
    assert cli_summary["targets"][0]["status"] == "error"
    assert not config.state_file.exists()
    assert not config.receipt_file.exists()
