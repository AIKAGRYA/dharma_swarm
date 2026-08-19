"""Tests for the non-stop engine (daemon) — halts, budget, kill-metric gating."""

from __future__ import annotations

import json

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.campaign import CampaignResult
from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon


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
