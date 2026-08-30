from __future__ import annotations

import fcntl
import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.lab_supervisor.config import (
    ConfigError,
    SupervisorConfig,
    safe_subprocess_environment,
)
from dharma_swarm.lab_supervisor.engine import Supervisor
from dharma_swarm.lab_supervisor.models import ActionKind, LabState
from dharma_swarm.lab_supervisor.prompts import (
    anomaly_prompt,
    validate_anomaly_output,
)


class Clock:
    def __init__(self, value: float) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float = 1) -> None:
        self.value += seconds


class FakeRun:
    def __init__(self, *, provider_failure: bool = False) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.provider_failure = provider_failure

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)
        self.calls.append(command)
        if self.provider_failure and "probe" in command:
            return subprocess.CompletedProcess(argv, 1, "", "provider_error: rate_limit")
        return subprocess.CompletedProcess(argv, 0, '{"status":"ok"}', "")


def _lab(
    root: Path,
    *,
    name: str = "sublimation-foundry",
    kind: str = "sublimation_foundry",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence = root / "evidence.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text('{"status":"ok"}', encoding="utf-8")
    row: dict[str, object] = {
        "name": name,
        "kind": kind,
        "state_root": str(root),
        "evidence_paths": [str(evidence)],
        "halt_paths": [str(root / "STOP")],
        "max_stale_seconds": 3600,
        "bounded_trial": {
            "argv": ["/usr/bin/true", name],
            "timeout_seconds": 10,
        },
        "trial_interval_seconds": 0,
    }
    row.update(extra or {})
    return row


def _config(labs: list[dict[str, object]], **policy: object) -> SupervisorConfig:
    defaults: dict[str, object] = {
        "dry_run": False,
        "min_free_disk_bytes": 1,
        "max_load_per_cpu": 100,
        "probe_retry_attempts": 1,
        "max_subprocess_calls_per_tick": 20,
        "max_actions_per_lab_per_day": 50,
        "max_trials_per_lab_per_day": 10,
        "max_provider_actions_per_lab_per_day": 10,
        "max_cleanup_actions_per_lab_per_day": 10,
    }
    defaults.update(policy)
    return SupervisorConfig.from_raw(
        {
            "schema": "dharma.lab_supervisor.config.v1",
            "labs": labs,
            "policy": defaults,
        }
    )


def _supervisor(
    config: SupervisorConfig,
    state_root: Path,
    clock: Clock,
    fake: FakeRun | None = None,
) -> Supervisor:
    return Supervisor(
        config,
        state_root=state_root,
        clock=clock,
        load_fn=lambda: (0.0, 0.0, 0.0),
        cpu_count_fn=lambda: 4,
        run_fn=fake,
        sleep_fn=lambda _: None,
    )


def test_five_tick_simulation_for_each_lab(tmp_path: Path) -> None:
    """Five bounded ticks prove both adapters without any model provider."""

    foundry = tmp_path / "foundry"
    rsi = tmp_path / "rsi"
    config = _config(
        [
            _lab(foundry),
            _lab(rsi, name="rsi-lab", kind="rsi_lab"),
        ],
        max_trials_per_lab_per_day=5,
    )
    clock = Clock(max((foundry / "evidence.json").stat().st_mtime, (rsi / "evidence.json").stat().st_mtime))
    fake = FakeRun()
    supervisor = _supervisor(config, tmp_path / "supervisor", clock, fake)

    reports = []
    for _ in range(5):
        reports.append(supervisor.run_tick(allow_actions=True))
        clock.advance()

    assert all(report.state is LabState.HEALTHY for report in reports)
    assert all(len(report.assessments) == 2 for report in reports)
    assert sum(call[-1] == "sublimation-foundry" for call in fake.calls) == 5
    assert sum(call[-1] == "rsi-lab" for call in fake.calls) == 5
    chain = supervisor.receipts.verify()
    assert chain.valid and chain.count == 5
    assert chain.last_hash == reports[-1].receipt_hash


def test_kill_evidence_latches_and_never_restarts_trial(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root)
    stop = lab_root / "STOP"
    stop.write_text("operator halt", encoding="utf-8")
    config = _config([lab])
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    fake = FakeRun()
    supervisor = _supervisor(config, tmp_path / "supervisor", clock, fake)

    reports = [supervisor.run_tick(allow_actions=True)]
    stop.unlink()
    for _ in range(4):
        clock.advance()
        reports.append(supervisor.run_tick(allow_actions=True))

    assert [report.state for report in reports] == [LabState.HALTED] * 5
    assert all(report.assessments[0].halt_latched for report in reports)
    assert fake.calls == []
    assert all(
        report.assessments[0].actions[-1].action is ActionKind.KEEP_HALTED
        for report in reports
    )

    # Deleting only mutable state does not erase historical halt authority.
    (tmp_path / "supervisor" / "state.json").unlink()
    clock.advance()
    recovered = supervisor.run_tick(allow_actions=True)
    assert recovered.state is LabState.HALTED
    assert recovered.assessments[0].halt_latched


def test_normal_stopped_status_is_not_irreversible_halt_authority(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root, extra={"bounded_trial": None})
    evidence = lab_root / "evidence.json"
    evidence.write_text('{"status":"stopped"}', encoding="utf-8")
    report = _supervisor(
        _config([lab]),
        tmp_path / "supervisor",
        Clock(evidence.stat().st_mtime),
        FakeRun(),
    ).run_tick(allow_actions=True)

    assert report.state is LabState.HEALTHY
    assert report.assessments[0].halt_latched is False


def test_stale_evidence_is_degraded_not_healthy(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={"max_stale_seconds": 10, "bounded_trial": None},
    )
    evidence = lab_root / "evidence.json"
    clock = Clock(evidence.stat().st_mtime + 11)
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", clock, FakeRun()
    ).run_tick(allow_actions=True)
    assert report.state is LabState.DEGRADED
    assert "stale_evidence_seconds:11" in report.assessments[0].reasons


def test_stale_only_degradation_can_run_one_bounded_recovery_trial(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={"max_stale_seconds": 10},
    )
    evidence = lab_root / "evidence.json"
    clock = Clock(evidence.stat().st_mtime + 11)
    fake = FakeRun()
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", clock, fake
    ).run_tick(allow_actions=True)

    assert report.state is LabState.DEGRADED
    assert report.assessments[0].actions[-1].action is ActionKind.RUN_BOUNDED_TRIAL
    assert report.assessments[0].actions[-1].status == "succeeded"
    assert fake.calls == [("/usr/bin/true", "rsi-lab")]


def test_historical_provider_failure_does_not_override_newest_status(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    evidence_root = lab_root / "evidence"
    evidence_root.mkdir(parents=True)
    old = evidence_root / "001-old.json"
    newest = evidence_root / "999-new.json"
    old.write_text('{"error":"provider_error: rate_limit"}', encoding="utf-8")
    newest.write_text('{"status":"ok"}', encoding="utf-8")
    os.utime(old, (100, 100))
    os.utime(newest, (200, 200))
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={
            "evidence_paths": [str(evidence_root)],
            "max_evidence_files": 1,
            "bounded_trial": None,
            "quarantine_provider": {"argv": ["/usr/bin/true", "quarantine"]},
            "rotate_provider": {"argv": ["/usr/bin/true", "rotate"]},
        },
    )
    fake = FakeRun()
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", Clock(200), fake
    ).run_tick(allow_actions=True)

    assert report.state is LabState.HEALTHY
    assert [ref.path for ref in report.assessments[0].evidence] == [str(newest)]
    assert [action.action for action in report.assessments[0].actions] == [ActionKind.INSPECT]
    assert fake.calls == []


def test_newest_provider_failure_triggers_declared_provider_actions(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    evidence_root = lab_root / "evidence"
    evidence_root.mkdir(parents=True)
    old = evidence_root / "old.json"
    newest = evidence_root / "new.json"
    old.write_text('{"status":"ok"}', encoding="utf-8")
    newest.write_text('{"error":"provider_error: rate_limit"}', encoding="utf-8")
    os.utime(old, (100, 100))
    os.utime(newest, (200, 200))
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={
            "evidence_paths": [str(evidence_root)],
            "max_evidence_files": 1,
            "bounded_trial": None,
            "quarantine_provider": {"argv": ["/usr/bin/true", "quarantine"]},
            "rotate_provider": {"argv": ["/usr/bin/true", "rotate"]},
        },
    )
    fake = FakeRun()
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", Clock(200), fake
    ).run_tick(allow_actions=True)

    assert report.state is LabState.DEGRADED
    assert [action.action for action in report.assessments[0].actions] == [
        ActionKind.INSPECT,
        ActionKind.QUARANTINE_PROVIDER,
        ActionKind.ROTATE_PROVIDER,
    ]
    assert fake.calls == [
        ("/usr/bin/true", "quarantine"),
        ("/usr/bin/true", "rotate"),
    ]


def test_provider_failure_uses_only_declared_quarantine_and_rotation(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={
            "bounded_trial": None,
            "status_probe": {"argv": ["/usr/bin/true", "probe"]},
            "quarantine_provider": {"argv": ["/usr/bin/true", "quarantine"]},
            "rotate_provider": {"argv": ["/usr/bin/true", "rotate"]},
        },
    )
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    fake = FakeRun(provider_failure=True)
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", clock, fake
    ).run_tick(allow_actions=True)

    assert report.state is LabState.DEGRADED
    actions = report.assessments[0].actions
    assert [action.action for action in actions] == [
        ActionKind.INSPECT,
        ActionKind.QUARANTINE_PROVIDER,
        ActionKind.ROTATE_PROVIDER,
    ]
    assert fake.calls == [
        ("/usr/bin/true", "probe"),
        ("/usr/bin/true", "quarantine"),
        ("/usr/bin/true", "rotate"),
    ]


def test_circuit_breaker_stops_repeated_provider_probe(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={
            "bounded_trial": None,
            "status_probe": {"argv": ["/usr/bin/true", "probe"]},
        },
    )
    config = _config([lab], circuit_failure_threshold=3, circuit_cooldown_seconds=60)
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    fake = FakeRun(provider_failure=True)
    supervisor = _supervisor(config, tmp_path / "supervisor", clock, fake)
    states = []
    for _ in range(4):
        states.append(supervisor.run_tick(allow_actions=True).state)
        clock.advance()
    assert states == [
        LabState.DEGRADED,
        LabState.DEGRADED,
        LabState.DEGRADED,
        LabState.BLOCKED,
    ]
    assert fake.calls == [("/usr/bin/true", "probe")] * 3


def test_circuit_cooldown_is_fixed_and_recovers_after_expiry(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={
            "bounded_trial": None,
            "status_probe": {"argv": ["/usr/bin/true", "probe"]},
        },
    )
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    fake = FakeRun(provider_failure=True)
    supervisor = _supervisor(
        _config([lab], circuit_failure_threshold=1, circuit_cooldown_seconds=60),
        tmp_path / "supervisor",
        clock,
        fake,
    )

    first = supervisor.run_tick(allow_actions=True)
    deadline = supervisor.status()["labs"]["rsi-lab"]["circuit_open_until"]
    assert first.state is LabState.DEGRADED
    assert deadline == clock.value + 60

    clock.advance(10)
    during = supervisor.run_tick(allow_actions=True)
    assert during.state is LabState.BLOCKED
    assert supervisor.status()["labs"]["rsi-lab"]["circuit_open_until"] == deadline
    assert fake.calls == [("/usr/bin/true", "probe")]

    fake.provider_failure = False
    clock.advance(50)
    recovered = supervisor.run_tick(allow_actions=True)
    assert recovered.state is LabState.HEALTHY
    runtime = supervisor.status()["labs"]["rsi-lab"]
    assert runtime["consecutive_failures"] == 0
    assert runtime["circuit_open_until"] == 0.0
    assert fake.calls == [("/usr/bin/true", "probe")] * 2


def test_benign_stale_observation_does_not_trip_circuit(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={"max_stale_seconds": 1, "bounded_trial": None},
    )
    evidence = lab_root / "evidence.json"
    clock = Clock(evidence.stat().st_mtime + 2)
    supervisor = _supervisor(
        _config([lab], circuit_failure_threshold=2),
        tmp_path / "supervisor",
        clock,
        FakeRun(),
    )
    reports = []
    for _ in range(5):
        reports.append(supervisor.run_tick(allow_actions=True))
        clock.advance()

    assert [report.state for report in reports] == [LabState.DEGRADED] * 5
    runtime = supervisor.status()["labs"]["rsi-lab"]
    assert runtime["consecutive_failures"] == 0
    assert runtime["circuit_open_until"] == 0.0


def test_budget_exhaustion_caps_trials_across_five_ticks(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root)
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    fake = FakeRun()
    supervisor = _supervisor(
        _config([lab], max_trials_per_lab_per_day=2),
        tmp_path / "supervisor",
        clock,
        fake,
    )
    statuses = []
    for _ in range(5):
        result = supervisor.run_tick(allow_actions=True)
        statuses.append(result.assessments[0].actions[-1].status)
        clock.advance()
    assert statuses == ["succeeded", "succeeded", "skipped", "skipped", "skipped"]
    assert len(fake.calls) == 2
    assert supervisor.status()["labs"]["sublimation-foundry"]["trials_today"] == 2


def test_dry_run_ticks_do_not_consume_live_budget_or_trial_cadence(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root, extra={"trial_interval_seconds": 3600})
    evidence = lab_root / "evidence.json"
    clock = Clock(evidence.stat().st_mtime)
    fake = FakeRun()
    supervisor = _supervisor(
        _config([lab], max_trials_per_lab_per_day=1),
        tmp_path / "supervisor",
        clock,
        fake,
    )

    for _ in range(5):
        report = supervisor.run_tick()
        assert report.assessments[0].actions[-1].status == "dry_run"
        clock.advance()
    runtime = supervisor.status()["labs"]["sublimation-foundry"]
    assert runtime["actions_today"] == 0
    assert runtime["trials_today"] == 0
    assert runtime["last_trial_at"] == 0.0

    live = supervisor.run_tick(allow_actions=True)
    assert live.assessments[0].actions[-1].status == "succeeded"
    assert fake.calls == [("/usr/bin/true", "sublimation-foundry")]
    runtime = supervisor.status()["labs"]["sublimation-foundry"]
    assert runtime["actions_today"] == 1
    assert runtime["trials_today"] == 1
    assert runtime["last_trial_at"] == clock.value


def test_evidence_discovery_cap_blocks_actions_fail_closed(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    evidence_root = lab_root / "evidence"
    evidence_root.mkdir(parents=True)
    for index in range(3):
        (evidence_root / f"{index}.json").write_text('{"status":"ok"}', encoding="utf-8")
    lab = _lab(
        lab_root,
        extra={
            "evidence_paths": [str(evidence_root)],
            "max_scan_entries": 2,
        },
    )
    fake = FakeRun()
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", Clock(10), fake
    ).run_tick(allow_actions=True)

    assert report.state is LabState.BLOCKED
    assert any(
        reason.startswith("evidence_discovery_limit_reached:")
        for reason in report.assessments[0].reasons
    )
    assert [action.action for action in report.assessments[0].actions] == [ActionKind.INSPECT]
    assert fake.calls == []


def test_lock_contention_is_blocked_and_writes_no_receipt(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root)
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    state_root = tmp_path / "supervisor"
    supervisor = _supervisor(_config([lab]), state_root, clock, FakeRun())
    state_root.mkdir(parents=True)
    with (state_root / "supervisor.lock").open("w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        report = supervisor.run_tick(allow_actions=True)
        fcntl.flock(held.fileno(), fcntl.LOCK_UN)
    assert report.state is LabState.BLOCKED
    assert report.lock_contended
    assert report.internal_failure
    assert not (state_root / "receipts.jsonl").exists()


def test_cleanup_prunes_only_explicit_old_cache_files(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    cache = lab_root / "cache"
    cache.mkdir(parents=True)
    disposable = cache / "old.tmp"
    disposable.write_text("discard", encoding="utf-8")
    evidence = lab_root / "evidence.json"
    lab = _lab(
        lab_root,
        extra={
            "bounded_trial": None,
            "disposable_paths": [str(cache)],
            "disposable_min_age_seconds": 10,
        },
    )
    clock = Clock(max(disposable.stat().st_mtime, evidence.stat().st_mtime) + 20)
    old = clock.value - 20
    os.utime(disposable, (old, old))
    supervisor = _supervisor(
        _config([lab], min_free_disk_bytes=10**15),
        tmp_path / "supervisor",
        clock,
        FakeRun(),
    )
    report = supervisor.run_tick(allow_actions=True)
    assert report.state is LabState.BLOCKED
    assert not disposable.exists()
    assert evidence.exists()
    assert report.assessments[0].actions[-1].action is ActionKind.PRUNE_DISPOSABLE


def test_cleanup_config_rejects_receipts_and_non_cache_paths(tmp_path: Path) -> None:
    root = tmp_path / "foundry"
    with pytest.raises(ConfigError, match="temp/cache named"):
        _config([_lab(root, extra={"disposable_paths": [str(root / "scratch")]})])
    with pytest.raises(ConfigError, match="durable evidence"):
        _config([_lab(root, extra={"disposable_paths": [str(root / "cache" / "receipts")]})])


def test_receipt_chain_detects_tampering(tmp_path: Path) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root, extra={"bounded_trial": None})
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    supervisor = _supervisor(_config([lab]), tmp_path / "supervisor", clock, FakeRun())
    supervisor.run_tick()
    clock.advance()
    supervisor.run_tick()
    chain = supervisor.receipts.verify()
    assert chain.valid and chain.count == 2

    path = tmp_path / "supervisor" / "receipts.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["dry_run"] = not first["dry_run"]
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not supervisor.receipts.verify().valid
    blocked = supervisor.run_tick()
    assert blocked.state is LabState.BLOCKED
    assert "receipt_chain_invalid" in blocked.notes


@pytest.mark.parametrize("mutation", ["blank", "truncated", "non_object"])
def test_receipt_chain_rejects_noncanonical_jsonl_rows(
    tmp_path: Path, mutation: str
) -> None:
    lab_root = tmp_path / "foundry"
    lab = _lab(lab_root, extra={"bounded_trial": None})
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    supervisor = _supervisor(_config([lab]), tmp_path / "supervisor", clock, FakeRun())
    supervisor.run_tick()
    path = tmp_path / "supervisor" / "receipts.jsonl"
    raw = path.read_bytes()
    if mutation == "blank":
        path.write_bytes(raw + b"\n")
    elif mutation == "truncated":
        path.write_bytes(raw.removesuffix(b"\n"))
    else:
        path.write_bytes(b"[]\n")

    status = supervisor.receipts.verify()
    assert status.valid is False
    blocked = supervisor.run_tick()
    assert blocked.internal_failure is True
    assert "receipt_chain_invalid" in blocked.notes


def test_missing_status_command_is_blocked(tmp_path: Path) -> None:
    lab_root = tmp_path / "rsi"
    lab = _lab(
        lab_root,
        name="rsi-lab",
        kind="rsi_lab",
        extra={
            "bounded_trial": None,
            "status_probe": {"argv": [str(tmp_path / "missing-rsi"), "status"]},
        },
    )
    clock = Clock((lab_root / "evidence.json").stat().st_mtime)
    report = _supervisor(
        _config([lab]), tmp_path / "supervisor", clock, FakeRun()
    ).run_tick()
    assert report.state is LabState.BLOCKED
    assert any(reason.startswith("executable_unavailable") for reason in report.assessments[0].reasons)


@pytest.mark.parametrize(
    "argv",
    [
        ["bash", "-c", "anything"],
        ["git", "push"],
        ["python3", "-c", "print(1)"],
        ["/usr/bin/true", "api_key=not-allowed"],
        ["/usr/bin/true", "--api-key", "not-allowed"],
        ["/usr/bin/true", "--token", "not-allowed"],
        ["/usr/bin/true", "Authorization: Bearer not-allowed"],
        ["/usr/bin/true", "deploy"],
    ],
)
def test_config_rejects_arbitrary_or_secret_bearing_commands(
    tmp_path: Path, argv: list[str]
) -> None:
    with pytest.raises(ConfigError):
        _config([_lab(tmp_path / "lab", extra={"bounded_trial": {"argv": argv}})])


def test_v1_config_rejects_cadence_that_disagrees_with_timer(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cadence_seconds must equal 300"):
        _config([_lab(tmp_path / "lab")], cadence_seconds=600)


def test_anomaly_prompt_is_bounded_and_output_cannot_claim_authority() -> None:
    rendered = anomaly_prompt({"state": "Degraded", "refs": ["sha256:abc"]})
    assert "Do not call tools" in rendered
    assert "clear or reinterpret KILL/HALT" in rendered
    valid = {
        "schema": "dharma.lab_supervisor.anomaly_analysis.v1",
        "verdict": "insufficient_evidence",
        "confidence": 0.3,
        "claims": [],
        "hypotheses": [],
        "next_safe_action": "inspect",
        "requires_human": True,
        "forbidden_effects": {
            "clear_kill": False,
            "merge": False,
            "deploy": False,
            "expand_budget": False,
        },
    }
    assert validate_anomaly_output(valid) == (True, ())
    invalid = {**valid, "forbidden_effects": {**valid["forbidden_effects"], "deploy": True}}
    ok, errors = validate_anomaly_output(invalid)
    assert not ok
    assert "forbidden_effect_contract_breached" in errors


def test_subprocess_environment_is_static_and_credential_free(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "/tmp/untrusted-imports")
    monkeypatch.setenv("HOME", "/tmp/credential-home")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-pass")
    assert safe_subprocess_environment() == {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": "/tmp",
    }
