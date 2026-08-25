"""Tests for the non-stop engine (daemon) — halts, budget, kill-metric gating."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from dharma_swarm.foundry.artifacts import ArtifactReplayError
from dharma_swarm.foundry.campaign import CampaignResult
from dharma_swarm.foundry import daemon
from dharma_swarm.foundry.daemon import (
    DaemonConfig,
    DaemonState,
    FoundryStateError,
    run_daemon,
)


def _result(**kw) -> CampaignResult:
    base = dict(target_id="openevolve-mlx", generations_run=3, proposed=6,
                ring1_wins=6, ring2_checked=4, ring2_survivors=3,
                best_fitness=2.0, mean_survival=0.8, spend_usd=0.01)
    base.update(kw)
    return CampaignResult(**base)


def _cycle_fn(result: CampaignResult):
    def cycle(target_id, generations, budget_cap, state_root):  # noqa: ARG001
        return result

    return cycle


def test_runs_to_max_cycles_when_healthy(tmp_path):
    state = run_daemon(
        DaemonConfig(targets=["openevolve-mlx"], max_cycles=3, interval_seconds=0,
                     state_root=tmp_path),
        cycle_fn=_cycle_fn(_result()),
        sleep_fn=lambda s: None,
    )
    assert state.cycles_run == 3
    assert "max_cycles=3" in state.stopped_reason
    # brief + metrics written for the operator's phone
    assert (tmp_path / "kill_metrics.json").exists()
    assert (tmp_path / "brief_fragment.md").exists()


def test_halts_on_killswitch(tmp_path):
    (tmp_path / "STOP").write_text("operator halt")
    state = run_daemon(
        DaemonConfig(targets=["openevolve-mlx"], max_cycles=5, interval_seconds=0,
                     state_root=tmp_path),
        cycle_fn=_cycle_fn(_result()),
        sleep_fn=lambda s: None,
    )
    assert state.cycles_run == 0
    assert "kill-switch" in state.stopped_reason


def test_halts_when_budget_exhausted(tmp_path):
    # Each cycle spends $60; a $100 cap allows 2 cycles, then remaining<=0.
    state = run_daemon(
        DaemonConfig(targets=["openevolve-mlx"], max_cycles=10, interval_seconds=0,
                     budget_cap_usd=100.0, state_root=tmp_path),
        cycle_fn=_cycle_fn(_result(spend_usd=60.0)),
        sleep_fn=lambda s: None,
    )
    assert state.cycles_run == 2
    assert state.stopped_reason == "budget exhausted"


def test_halts_on_kill_metric_verdict(tmp_path):
    # A single cycle with a replication failure is a fatal KILL verdict.
    def cycle(target_id, generations, budget_cap, state_root):  # noqa: ARG001
        return _result(mean_survival=0.9, ring2_survivors=3)

    # Force a KILL by making survival collapse across two cohorts.
    low = _result(mean_survival=0.1, ring2_survivors=0)
    state = run_daemon(
        DaemonConfig(targets=["openevolve-mlx"], max_cycles=5, interval_seconds=0,
                     state_root=tmp_path),
        cycle_fn=_cycle_fn(low),
        sleep_fn=lambda s: None,
    )
    # cycle 1: one low cohort (WARN, no prior) -> continues
    # cycle 2: low + prior low -> survival_collapse KILL -> halt
    assert state.cycles_run == 2
    assert "kill-metric verdict" in state.stopped_reason
    assert "survival_collapse" in state.stopped_reason


def test_snapshot_written_reflects_last_cycle(tmp_path):
    run_daemon(
        DaemonConfig(targets=["openevolve-mlx"], max_cycles=1, interval_seconds=0,
                     state_root=tmp_path),
        cycle_fn=_cycle_fn(_result(mean_survival=0.75, ring2_survivors=4)),
        sleep_fn=lambda s: None,
    )
    payload = json.loads((tmp_path / "kill_metrics.json").read_text())
    assert payload["cohort_survival"] == 0.75
    assert payload["verified_improvements"] == 4


def test_spend_ledger_survives_restart(tmp_path):
    # Restart=always must not reset the monthly budget (2026-08-19 doctrine).
    from dharma_swarm.foundry.campaign import CampaignResult
    from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon

    def spending_cycle(target_id, gens, cap, root):
        return CampaignResult(
            target_id=target_id,
            generations_run=1,
            spend_usd=10.0,
            mean_survival=0.8,
            ring2_survivors=1,
        )

    cfg = DaemonConfig(targets=["t"], max_cycles=2, budget_cap_usd=300.0,
                       state_root=tmp_path, interval_seconds=0)
    first = run_daemon(cfg, cycle_fn=spending_cycle, sleep_fn=lambda s: None)
    assert first.total_spend_usd == 20.0
    second = run_daemon(cfg, cycle_fn=spending_cycle, sleep_fn=lambda s: None)
    assert second.total_spend_usd == 40.0  # resumed 20 from ledger, spent 20 more


def test_live_cycle_reservation_survives_process_crash_and_reduces_capacity(tmp_path):
    class SimulatedProcessCrash(BaseException):
        pass

    def crash_after_reservation(target_id, gens, cap, root):  # noqa: ARG001
        assert cap == 5.0
        raise SimulatedProcessCrash

    cfg = DaemonConfig(
        targets=["t"],
        max_cycles=1,
        budget_cap_usd=5.0,
        cycle_budget_cap_usd=5.0,
        state_root=tmp_path,
        interval_seconds=0,
        mode="campaign",
    )
    with pytest.raises(SimulatedProcessCrash):
        run_daemon(cfg, cycle_fn=crash_after_reservation, sleep_fn=lambda s: None)

    ledger = json.loads((tmp_path / "spend_ledger.json").read_text())
    assert ledger["committed_spend_usd"] == 0.0
    assert ledger["spend_usd"] == 5.0
    assert len(ledger["reservations"]) == 1

    calls = {"n": 0}

    def must_not_reopen_capacity(target_id, gens, cap, root):  # noqa: ARG001
        calls["n"] += 1
        return _result(spend_usd=0.0)

    restarted = run_daemon(
        cfg, cycle_fn=must_not_reopen_capacity, sleep_fn=lambda s: None
    )
    assert calls["n"] == 0
    assert restarted.total_spend_usd == 5.0
    assert restarted.reserved_spend_usd == 5.0
    assert restarted.stopped_reason == "budget exhausted"


def test_spend_ledger_write_is_atomic_and_fsyncs_file_and_directory(
    tmp_path, monkeypatch
):
    real_fsync = daemon.os.fsync
    synced: list[int] = []

    def recording_fsync(fd: int) -> None:
        synced.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(daemon.os, "fsync", recording_fsync)
    daemon._write_month_spend(tmp_path, 1.25)
    assert len(synced) >= 2
    assert json.loads((tmp_path / "spend_ledger.json").read_text())["spend_usd"] == 1.25
    assert not list(tmp_path.glob(".spend_ledger.json.*.tmp"))


def test_service_state_concurrent_heartbeat_writes_are_serialized_and_durable(
    tmp_path
):
    state = DaemonState(boot_id="boot-concurrent")

    def write(index: int) -> None:
        daemon._write_service_state(
            tmp_path,
            state,
            status="running",
            mode="campaign",
            target_id=f"target-{index}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(64)))
    payload = json.loads((tmp_path / "service_state.json").read_text())
    assert payload["boot_id"] == "boot-concurrent"
    assert payload["target_id"].startswith("target-")
    assert not list(tmp_path.glob(".service_state.json.*.tmp"))


def test_three_consecutive_failures_halt(tmp_path):
    from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon

    def broken_cycle(target_id, gens, cap, root):
        raise RuntimeError("baseline oracle failed")

    cfg = DaemonConfig(targets=["t"], max_cycles=10, state_root=tmp_path,
                       interval_seconds=0)
    state = run_daemon(cfg, cycle_fn=broken_cycle, sleep_fn=lambda s: None)
    assert state.consecutive_failures == 3
    assert "3 consecutive cycle failures" in state.stopped_reason
    assert state.cycles_run == 0
    assert state.terminal_kill is True
    assert (tmp_path / "KILL.json").exists()

    calls = {"n": 0}

    def must_not_restart(target_id, gens, cap, root):
        calls["n"] += 1
        return _result()

    restarted = run_daemon(cfg, cycle_fn=must_not_restart, sleep_fn=lambda s: None)
    assert restarted.cycles_run == 0
    assert restarted.terminal_kill is True
    assert calls["n"] == 0


def test_one_failure_recovers(tmp_path):
    from dharma_swarm.foundry.campaign import CampaignResult
    from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon

    calls = {"n": 0}

    def flaky_cycle(target_id, gens, cap, root):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("transient")
        return CampaignResult(target_id=target_id, generations_run=1)

    cfg = DaemonConfig(targets=["t"], max_cycles=3, state_root=tmp_path,
                       interval_seconds=0)
    state = run_daemon(cfg, cycle_fn=flaky_cycle, sleep_fn=lambda s: None)
    assert state.cycles_run == 2
    assert state.consecutive_failures == 0
    assert "TimeoutError" in state.last_error


def test_replication_failure_is_immediately_terminal(tmp_path):
    calls = {"n": 0}

    def mismatch(target_id, gens, cap, root):
        calls["n"] += 1
        raise ArtifactReplayError("seeded tree mismatch")

    state = run_daemon(
        DaemonConfig(targets=["t"], max_cycles=10, state_root=tmp_path),
        cycle_fn=mismatch,
        sleep_fn=lambda s: None,
    )
    assert calls["n"] == 1
    assert state.terminal_kill is True
    marker = json.loads((tmp_path / "KILL.json").read_text())
    assert marker["category"] == "replication_failure"


def test_corrupt_spend_ledger_fails_closed(tmp_path):
    (tmp_path / "spend_ledger.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(FoundryStateError, match="spend ledger invalid"):
        run_daemon(
            DaemonConfig(targets=["t"], max_cycles=1, state_root=tmp_path),
            cycle_fn=_cycle_fn(_result()),
            sleep_fn=lambda s: None,
        )


def test_service_state_records_exact_checkout_sha(tmp_path):
    state = run_daemon(
        DaemonConfig(targets=["t"], max_cycles=1, state_root=tmp_path, mode="dry"),
        cycle_fn=_cycle_fn(_result()),
        sleep_fn=lambda s: None,
    )
    service = json.loads((tmp_path / "service_state.json").read_text())
    assert service["boot_id"] == state.boot_id
    assert len(service["code_sha"]) == 40
    assert service["status"] == "stopped"
    assert service["mode"] == "dry"


def test_all_provider_failed_cycles_trip_bounded_terminal_fuse(tmp_path):
    calls = {"n": 0}
    sleeps: list[float] = []

    def exhausted(target_id, gens, cap, root):
        calls["n"] += 1
        return CampaignResult(
            target_id=target_id,
            generations_run=1,
            proposed=0,
            provider_failures=4,
        )

    state = run_daemon(
        DaemonConfig(
            targets=["t"],
            max_cycles=10,
            state_root=tmp_path,
            interval_seconds=999,
            provider_outage_threshold=3,
            provider_outage_cooldown_seconds=7,
        ),
        cycle_fn=exhausted,
        sleep_fn=sleeps.append,
    )
    assert calls["n"] == 3
    assert state.cycles_run == 0
    assert state.consecutive_provider_outages == 3
    assert state.total_provider_failures == 12
    assert sleeps == [7, 7]
    marker = json.loads((tmp_path / "KILL.json").read_text())
    assert marker["category"] == "provider_exhausted"
