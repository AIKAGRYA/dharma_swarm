"""Cascade loop closure: the cybernetics-codex audit must close a loop 2..11 only
when its replay receipt structurally proves a full sense->interpret->constrain->
act->adapt cycle on real data — never on a bare "closed" boolean, a missing
transition, an adapt that did not change state, or a run with tick errors.

This pins the keystone that lets loops 2..11 close via the same proven
bounded-replay pattern as Loop 1. It exercises the audit logic with fixtures;
it does NOT assert any real loop is closed.
"""
from __future__ import annotations

import json

from dharma_swarm.cybernetics_codex import (
    _evaluate_loop_closure_replay,
    build_loop_statuses,
    read_loop_closure_replays,
)


def _valid_replay() -> dict:
    return {
        "loop": 2,
        "loop_id": "organism_heartbeat",
        "cycles": 3,
        "real_data": True,
        "transitions_receipted": {
            "sense": True,
            "interpret": True,
            "constrain": True,
            "act": True,
            "adapt": True,
        },
        "adapt_proof": {"field": "router._routing_bias", "before": 0.0, "after": 0.4, "fed_forward": True},
        "tick_errors": [],
    }


def test_valid_replay_is_closed():
    assert _evaluate_loop_closure_replay(_valid_replay())["closed"] is True


def test_bare_closed_boolean_is_not_trusted():
    # A receipt asserting closure but lacking the evidence must NOT close.
    data = {"closed": True, "cycles": 0}
    assert _evaluate_loop_closure_replay(data)["closed"] is False


def test_missing_transition_blocks_closure():
    data = _valid_replay()
    data["transitions_receipted"]["adapt"] = False
    assert _evaluate_loop_closure_replay(data)["closed"] is False


def test_adapt_without_real_change_blocks_closure():
    data = _valid_replay()
    data["adapt_proof"] = {"before": 0.4, "after": 0.4, "fed_forward": True}
    assert _evaluate_loop_closure_replay(data)["closed"] is False


def test_adapt_not_fed_forward_blocks_closure():
    data = _valid_replay()
    data["adapt_proof"]["fed_forward"] = False
    assert _evaluate_loop_closure_replay(data)["closed"] is False


def test_tick_errors_block_closure():
    data = _valid_replay()
    data["tick_errors"] = ["boom"]
    assert _evaluate_loop_closure_replay(data)["closed"] is False


def test_reader_closes_loop_with_valid_receipt(tmp_path):
    rdir = tmp_path / "reports" / "loop_closure" / "cybernetics_codex"
    rdir.mkdir(parents=True)
    (rdir / "2026-06-21_loop2_heartbeat_closure.json").write_text(
        json.dumps(_valid_replay()), encoding="utf-8"
    )
    replays = read_loop_closure_replays(tmp_path)
    assert replays["loop2"]["closed"] is True
    assert replays["loop3"]["closed"] is False  # no receipt


def test_build_loop_statuses_closes_loop_with_verified_replay():
    bounded = {"loop2": {"closed": True, "cycles": 3}}
    rows = {r["number"]: r for r in build_loop_statuses({}, {}, {}, bounded_replays=bounded)}
    assert rows[2]["verdict"] == "CLOSED_BOUNDED_REPLAY"
    # A loop with no replay is never closed by this path.
    assert rows[4]["verdict"] != "CLOSED_BOUNDED_REPLAY"
