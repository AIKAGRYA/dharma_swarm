"""Arena parity-control tests (Metabolic Loop Ignition, Improvement 2).

Covers the surfaces added on weaver/arena-parity-controls:
  * best_single_parity_budget control arm — instrumented AND asserted parity
    (kill-list doctrine: transport-level equality, externally auditable ledger);
  * seeded paired-bootstrap significance with CI95 on BOTH baselines
    (point estimate alone is forbidden);
  * fail-closed behavior when the parity instrument itself breaks;
  * LiveWorkerPool fail-closed contract (no silent fallback, no zero-token
    "successes", public-view-only prompts) without any network dependency;
  * measurement-mode disclosure so hermetic runs can never masquerade as live.
"""

from __future__ import annotations

from typing import Any

import pytest

from dharma_swarm.coordination.arena import ArenaRunner
from dharma_swarm.coordination.arena.live_pool import (
    RECORDED_SCHEMA,
    LiveDispatchError,
    LiveWorkerPool,
    RecordedReplayPool,
)
from dharma_swarm.coordination.genome import OrchestrationGenome


def _router_genome() -> OrchestrationGenome:
    return OrchestrationGenome(
        roster=[
            {"role_id": "r1", "member_id": "alpha-math", "kind": "model"},
            {"role_id": "r2", "member_id": "beta-code", "kind": "model"},
            {"role_id": "r3", "member_id": "gamma-logic", "kind": "model"},
        ],
        adjudication_rule="synthesize",
    )


# --------------------------------------------------------------- parity arm
def test_parity_control_arm_present_verified_and_auditable():
    run = ArenaRunner().run(_router_genome())
    assert "best_single_parity_budget" in run["arm_scores"]
    report = run["parity_control"]
    assert report["verified"] is True
    assert report["calls_per_task_match"] is True
    assert report["candidate_total_calls"] == report["control_total_calls"]
    assert report["control_model"], "gate winner must be resolved as control model"
    # Externally auditable ledger: every arm reports compute, calls, shared cap.
    ledger = run["parity_ledger"]
    for arm in (
        "candidate",
        "best_single_full_budget",
        "best_single_parity_budget",
        "same_budget_self_moa",
        "random_or_static_ensemble",
    ):
        assert arm in ledger
        assert "total_compute" in ledger[arm] and "total_calls" in ledger[arm]
    caps = {ledger[a]["per_call_cap"] for a in ledger}
    assert len(caps) == 1, "one pool serves every arm — the cap cannot differ"


def test_significance_carries_ci95_on_both_baselines():
    run = ArenaRunner().run(_router_genome())
    for key in ("significance", "significance_vs_parity_control"):
        sig = run[key]
        assert sig["method"] == "paired_seeded_bootstrap_percentile"
        lo, hi = sig["ci95_lift"]
        assert lo <= hi
        assert "observed_lift" in sig and "p_value" in sig
        # No-win-below-significance is closeout-enforced; here we assert the
        # CI is present so a point estimate can never render alone.


def test_broken_parity_instrument_fails_closed():
    class TamperedRunner(ArenaRunner):
        def _best_single_parity_budget(self, gate, cand):  # type: ignore[override]
            result, report = super()._best_single_parity_budget(gate, cand)
            report = dict(report)
            report["verified"] = False  # simulate a broken parity instrument
            return result, report

    run = TamperedRunner().run(_router_genome())
    assert run["closeout_state"] == "blocked_with_evidence"


def test_measurement_mode_disclosed_for_hermetic_runs():
    run = ArenaRunner().run(_router_genome())
    assert run["measurement_mode"] == "hermetic_fixture"


# ------------------------------------------------------------ live pool (no network)
_PUBLIC = [{"task_id": "t1", "family": "math", "prompt": "2+2?"}]


def test_live_pool_unknown_task_fails_closed():
    pool = LiveWorkerPool(_PUBLIC, transport=lambda url, payload, timeout: {})
    with pytest.raises(LiveDispatchError):
        pool.dispatch("any-model", "not-a-task")


def test_live_pool_transport_error_fails_closed_no_fallback():
    def broken_transport(url: str, payload: dict[str, Any], timeout: float):
        raise OSError("daemon unreachable")

    pool = LiveWorkerPool(_PUBLIC, transport=broken_transport)
    with pytest.raises(LiveDispatchError):
        pool.dispatch("any-model", "t1")


def test_live_pool_zero_token_success_is_refused():
    def hollow_transport(url: str, payload: dict[str, Any], timeout: float):
        return {"message": {"content": "4"}}  # no token accounting

    pool = LiveWorkerPool(_PUBLIC, transport=hollow_transport)
    with pytest.raises(LiveDispatchError):
        pool.dispatch("any-model", "t1")


def test_live_pool_caches_and_bills_parity_honestly():
    calls = {"n": 0}

    def counting_transport(url: str, payload: dict[str, Any], timeout: float):
        calls["n"] += 1
        return {
            "message": {"content": "4"},
            "prompt_eval_count": 7,
            "eval_count": 1,
        }

    pool = LiveWorkerPool(_PUBLIC, transport=counting_transport)
    first = pool.dispatch("m", "t1")
    second = pool.dispatch("m", "t1")
    assert calls["n"] == 1, "temperature-0 resample replays the cached draw"
    assert first.cost == second.cost == 8, "each dispatch still bills its budget"


def test_replay_pool_rejects_unexpected_schema():
    with pytest.raises(LiveDispatchError):
        RecordedReplayPool({"schema": "not-the-schema"})
    assert RECORDED_SCHEMA == "orchestration_arena_v1_live_receipts.v1"
