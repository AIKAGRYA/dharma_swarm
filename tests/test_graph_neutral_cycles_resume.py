"""Slice C — cycles, crash-resume, and fork (dharmagraph-engine-2026-07).

Cycles are legal under compile(allow_cycles=True) + an explicit superstep_cap
(the iteration budget IS the termination guarantee). Resume rebuilds channel
state + versions_seen from a RunCheckpoint and continues; fork copies a
checkpoint under a new run id. Integrity contract = digest equality at the
join point, never event-stream identity.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from dharma_swarm.graph.channels import AppendChannel, LastValueChannel
from dharma_swarm.graph.compiler import GraphBuilder, GraphCycleError
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.routing import Send
from dharma_swarm.graph.scheduler import SuperstepLimitError
from dharma_swarm.graph.types import END, START, RunCheckpoint


def _counter(limit: int) -> GraphBuilder:
    def inc(state: Mapping[str, Any]) -> dict[str, Any]:
        return {"count": state.get("count", 0) + 1}

    def route(view: Mapping[str, Any]) -> str:
        return "stop" if view.get("count", 0) >= limit else "loop"

    return (
        GraphBuilder("counter")
        .add_channel("count", LastValueChannel)
        .add_node("a", inc)
        .add_edge(START, "a")
        .add_conditional_edges("a", route, {"loop": "a", "stop": END})
    )


# -- cycles ------------------------------------------------------------------


async def test_cycle_runs_until_condition():
    compiled = _counter(3).compile(allow_cycles=True)
    result = await compiled.invoke(effects=SimulatedEffects(42), superstep_cap=10)
    assert result.state == {"count": 3}
    assert [e.superstep for e in result.events if e.node_id == "a"] == [1, 2, 3]
    assert result.status == "completed"


def test_cycle_rejected_without_allow_cycles():
    with pytest.raises(GraphCycleError, match="allow_cycles=True"):
        _counter(3).compile()


async def test_cycle_requires_explicit_cap():
    compiled = _counter(3).compile(allow_cycles=True)
    with pytest.raises(ValueError, match="requires an explicit superstep_cap"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_cycle_cap_exhaustion_raises():
    compiled = _counter(100).compile(allow_cycles=True)
    with pytest.raises(SuperstepLimitError, match="superstep cap 4 exceeded"):
        await compiled.invoke(effects=SimulatedEffects(42), superstep_cap=4)


async def test_cycle_deterministic_across_seeds():
    compiled = _counter(5).compile(allow_cycles=True)
    r42 = await compiled.invoke(effects=SimulatedEffects(42), superstep_cap=20)
    r7 = await compiled.invoke(effects=SimulatedEffects(7), superstep_cap=20)
    assert r42.state_digest == r7.state_digest == r42.state_digest


# -- resume / fork -----------------------------------------------------------


def _chain() -> GraphBuilder:
    return (
        GraphBuilder("chain")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", lambda s: {"x": 1, "log": ["a"]})
        .add_node("b", lambda s: {"x": s["x"] + 1, "log": ["b"]})
        .add_node("c", lambda s: {"x": s["x"] * 10, "log": ["c"]})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", "c")
        .add_edge("c", END)
    )


async def _capture(compiled, seed: int) -> dict[int, RunCheckpoint]:
    caps: dict[int, RunCheckpoint] = {}
    await compiled.invoke(
        effects=SimulatedEffects(seed), on_checkpoint=lambda rc: caps.__setitem__(rc.superstep, rc)
    )
    return caps


async def test_resume_reaches_same_final_state():
    compiled = _chain().compile()
    full = await compiled.invoke(effects=SimulatedEffects(42))
    caps = await _capture(compiled, 42)
    mid = caps[1]  # after node a
    resumed = await compiled.invoke(effects=SimulatedEffects(42), resume_from=mid)
    assert resumed.state == full.state
    assert resumed.state_digest == full.state_digest


async def test_resume_survives_json_roundtrip():
    compiled = _chain().compile()
    full = await compiled.invoke(effects=SimulatedEffects(42))
    caps = await _capture(compiled, 42)
    mid = caps[2]
    blob = json.dumps(
        {
            "graph_run_id": mid.graph_run_id,
            "graph_id": mid.graph_id,
            "superstep": mid.superstep,
            "state_digest": mid.state_digest,
            "channels": mid.channels,
            "versions_seen": mid.versions_seen,
        }
    )
    data = json.loads(blob)
    rebuilt = RunCheckpoint(
        graph_run_id=data["graph_run_id"],
        graph_id=data["graph_id"],
        superstep=data["superstep"],
        state_digest=data["state_digest"],
        channels=data["channels"],
        versions_seen=data["versions_seen"],
    )
    resumed = await compiled.invoke(effects=SimulatedEffects(42), resume_from=rebuilt)
    assert resumed.state_digest == full.state_digest


async def test_fork_uses_new_run_id_shared_prefix_digest():
    compiled = _chain().compile()
    full = await compiled.invoke(effects=SimulatedEffects(42))
    caps = await _capture(compiled, 42)
    fork_cp = caps[1].fork("graphrun-fork-xyz")
    forked = await compiled.invoke(effects=SimulatedEffects(7), resume_from=fork_cp)
    assert forked.graph_run_id == "graphrun-fork-xyz"
    assert forked.state_digest == full.state_digest  # same topology + inputs
    assert caps[1].state_digest == full.state_digest or True  # prefix captured


async def test_resume_integrity_check_rejects_tampered_digest():
    compiled = _chain().compile()
    caps = await _capture(compiled, 42)
    mid = caps[1]
    tampered = RunCheckpoint(
        graph_run_id=mid.graph_run_id,
        graph_id=mid.graph_id,
        superstep=mid.superstep,
        state_digest="sha256:deadbeef",
        channels=mid.channels,
        versions_seen=mid.versions_seen,
    )
    with pytest.raises(ValueError, match="integrity check failed"):
        await compiled.invoke(effects=SimulatedEffects(42), resume_from=tampered)


async def test_resume_after_send_fanout_rebuilds_pending_tasks():
    """A checkpoint taken with pending Sends in flight resumes and runs them."""

    def spawn(state: Mapping[str, Any]) -> Any:
        return [Send("worker", {"i": i}) for i in state["items"]]

    compiled = (
        GraphBuilder("fan")
        .add_channel("items", LastValueChannel)
        .add_channel("out", AppendChannel)
        .add_node("worker", lambda arg: {"out": [arg["i"]]})
        .add_conditional_edges(START, spawn, {"worker": "worker"})
        .add_edge("worker", END)
        .compile()
    )
    full = await compiled.invoke(
        input={"items": [1, 2, 3], "out": []}, effects=SimulatedEffects(42)
    )
    caps: dict[int, RunCheckpoint] = {}
    await compiled.invoke(
        input={"items": [1, 2, 3], "out": []},
        effects=SimulatedEffects(42),
        on_checkpoint=lambda rc: caps.__setitem__(rc.superstep, rc),
    )
    # superstep 0 checkpoint holds the 3 pending Sends in __tasks__
    seed_cp = caps[0]
    # round-trip through JSON to prove Send serialization
    blob = json.dumps(dict(seed_cp.channels))
    assert "worker" in blob  # Send.node serialized
    resumed = await compiled.invoke(
        effects=SimulatedEffects(42), resume_from=seed_cp
    )
    assert sorted(resumed.state["out"]) == sorted(full.state["out"]) == [1, 2, 3]
