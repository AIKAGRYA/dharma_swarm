"""Integration regression tests for U5+U6 COMPOSITION.

An adversarial detonation (2026-06-09) found the autonomously-built wake loop had three real
defects: persistence was a disconnected island, the budget gate was a frozen value (could never
trip mid-loop), and a runner exception bypassed governance with an uncaught crash. These tests
prove the fixes — and that the holon now actually composes into one coherent, restartable thing.
"""
from __future__ import annotations

from dharma_swarm import holon_persistence, holon_runtime


async def _ok_runner(name):
    return "self-task", "reply dharma jagat kalyan"


# --- Fix 1: persistence is WIRED into the loop (was a disconnected island) ---

async def test_ran_cycle_is_persisted(tmp_path):
    res = await holon_runtime.holon_wake_cycle("h", _ok_runner, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path)
    assert res["status"] == "ran"
    events = holon_persistence.load_session("h", agents_root=tmp_path)
    assert len(events) == 1
    assert events[0]["record"]["status"] == "ran"


async def test_holon_survives_restart_and_continues_numbering(tmp_path):
    r1 = await holon_runtime.run_holon_loop("h", _ok_runner, max_cycles=3, cap_usd=10.0, agents_root=tmp_path)
    assert [x["status"] for x in r1] == ["ran", "ran", "ran"]
    # "restart": a fresh loop call must CONTINUE the cycle numbering, not repeat from 0
    r2 = await holon_runtime.run_holon_loop("h", _ok_runner, max_cycles=2, cap_usd=10.0, agents_root=tmp_path)
    assert len(r2) == 2
    events = holon_persistence.load_session("h", agents_root=tmp_path)
    assert [e["cycle"] for e in events] == [0, 1, 2, 3, 4]  # continuous, no repeat
    assert holon_persistence.resume_point("h", agents_root=tmp_path)["cycle"] == 4


# --- Fix 2: budget is enforced MID-LOOP via spend_fn (was a frozen value) ---

async def test_budget_enforced_mid_loop_via_spend_fn(tmp_path):
    spend = {"v": 0.0}

    async def spending_runner(name):
        spend["v"] += 2.0  # each completed cycle burns $2
        return "t", "r"

    res = await holon_runtime.run_holon_loop(
        "h", spending_runner, max_cycles=10, cap_usd=5.0,
        spend_fn=lambda: spend["v"], agents_root=tmp_path,
    )
    statuses = [x["status"] for x in res]
    assert statuses[-1] == "halted:budget"   # the loop DID halt mid-run on real accumulating spend
    assert statuses.count("ran") == 3        # 0,2,4 under cap=5; cycle 4 sees spend=6 -> halt


async def test_static_spent_never_trips_is_documented_behaviour(tmp_path):
    # Without spend_fn, a static under-cap spend runs all cycles (caller's job to halt) — but it
    # must NOT silently pretend to enforce. 3 cycles all ran.
    res = await holon_runtime.run_holon_loop("h", _ok_runner, max_cycles=3, spent_usd=1.0, cap_usd=5.0, agents_root=tmp_path)
    assert [x["status"] for x in res] == ["ran", "ran", "ran"]


# --- Fix 3: a runner exception is GOVERNED (halted:error), not an uncaught crash ---

async def test_runner_exception_is_governed(tmp_path):
    async def boom(name):
        raise RuntimeError("model blew up")

    res = await holon_runtime.holon_wake_cycle("h", boom, spent_usd=0.0, cap_usd=10.0, agents_root=tmp_path)
    assert res["status"] == "halted:error"   # governed, not an uncaught exception
    assert "model blew up" in res["error"]


async def test_loop_stops_on_runner_exception(tmp_path):
    calls = {"n": 0}

    async def flaky(name):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("cycle 2 failed")
        return "t", "r"

    res = await holon_runtime.run_holon_loop("h", flaky, max_cycles=5, cap_usd=10.0, agents_root=tmp_path)
    assert [x["status"] for x in res] == ["ran", "halted:error"]
    assert calls["n"] == 2  # stopped — did not run cycle 3
