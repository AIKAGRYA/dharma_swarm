"""Pregel/BSP execution-core properties (Hypothesis, bounded).

Spec: docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md §3 — properties
1–4 land with S2 (concurrent supersteps + failure atomicity); 5–8 follow
with later slices. Every property is bounded, derandomized, and sleeps
never touch the wall clock, so the file stays far under the tests.yml
30s per-test budget.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dharma_swarm.graph.channels import AppendChannel, LastValueChannel
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.errors import NodeExecutionError
from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.types import END, START, RunCheckpoint

BOUNDED = settings(max_examples=15, deadline=None, derandomize=True)


def _diamond():
    """START fans out to three writers; a barrier edge joins them."""
    return (
        GraphBuilder("prop-diamond")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_channel("joined", LastValueChannel)
        .add_node("a", lambda s: {"log": ["a"]})
        .add_node("b", lambda s: {"log": ["b"]})
        .add_node("c", lambda s: {"log": ["c"]})
        .add_node("join", lambda s: {"joined": len(s["log"])})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge(START, "c")
        .add_edge(["a", "b", "c"], "join")
        .add_edge("join", END)
        .compile()
    )


@BOUNDED
@given(
    seed_one=st.integers(min_value=0, max_value=2**32 - 1),
    seed_two=st.integers(min_value=0, max_value=2**32 - 1),
    initial=st.integers(min_value=-1000, max_value=1000),
)
def test_property_1_permutation_invariance(seed_one, seed_two, initial):
    """Any task-completion order yields byte-identical state and checkpoints."""

    async def run(seed: int):
        caps: dict[int, RunCheckpoint] = {}
        result = await _diamond().invoke(
            input={"x": initial, "log": []},
            effects=SimulatedEffects(seed),
            on_checkpoint=lambda rc: caps.__setitem__(rc.superstep, rc),
        )
        return result, caps

    result_one, caps_one = asyncio.run(run(seed_one))
    result_two, caps_two = asyncio.run(run(seed_two))
    assert result_one.state == result_two.state
    assert result_one.state_digest == result_two.state_digest
    assert sorted(caps_one) == sorted(caps_two)
    for step in caps_one:
        assert caps_one[step].state_digest == caps_two[step].state_digest


@BOUNDED
@given(
    initial=st.integers(min_value=-1000, max_value=1000),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_property_2_snapshot_isolation(initial, seed):
    """Two parallel readers of one channel each observe only the pre-step value."""

    async def reader(name: str):
        async def node(state: Mapping[str, Any]) -> dict[str, Any]:
            first = state["x"]
            await asyncio.sleep(0)  # force an interleave point mid-task
            assert state["x"] == first
            return {f"seen_{name}": first}

        return node

    async def run():
        compiled = (
            GraphBuilder("prop-isolation")
            .add_channel("x", LastValueChannel)
            .add_channel("seen_p", LastValueChannel)
            .add_channel("seen_q", LastValueChannel)
            .add_node("p", await reader("p"))
            .add_node("q", await reader("q"))
            .add_edge(START, "p")
            .add_edge(START, "q")
            .add_edge("p", END)
            .add_edge("q", END)
            .compile()
        )
        return await compiled.invoke(
            input={"x": initial}, effects=SimulatedEffects(seed)
        )

    result = asyncio.run(run())
    assert result.state["seen_p"] == initial
    assert result.state["seen_q"] == initial


def _atomicity_graph(calls: dict[str, int], armed: dict[str, bool]):
    def node_a(state: Mapping[str, Any]) -> dict[str, Any]:
        calls["a"] += 1
        return {"ax": state["x"] + 1, "log": [f"a_saw_{state['x']}"]}

    def node_b(state: Mapping[str, Any]) -> dict[str, Any]:
        calls["b"] += 1
        if armed["on"]:
            raise RuntimeError("seeded-failure")
        return {"bx": state["x"] * 2, "log": [f"b_saw_{state['x']}"]}

    return (
        GraphBuilder("prop-atomicity")
        .add_channel("x", LastValueChannel)
        .add_channel("ax", LastValueChannel)
        .add_channel("bx", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", node_a)
        .add_node("b", node_b)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )


@BOUNDED
@given(
    initial=st.integers(min_value=-1000, max_value=1000),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_property_3_step_atomicity_and_failure_resume(
    initial, seed, tmp_path_factory: pytest.TempPathFactory
):
    """A failed step commits nothing; resume reruns ONLY failed tasks against
    the pre-step snapshot and converges to the never-failed result."""
    root = tmp_path_factory.mktemp("prop-atomicity")

    async def run() -> None:
        calls = {"a": 0, "b": 0}
        armed = {"on": True}
        compiled = _atomicity_graph(calls, armed)
        kernel = GraphPersistenceKernel(Path(root) / "kernel")
        thread = f"prop-{seed}-{initial}"
        with pytest.raises(NodeExecutionError):
            await compiled.invoke(
                input={"x": initial},
                effects=SimulatedEffects(seed),
                graph_run_id=thread,
                persistence=kernel,
                thread_id=thread,
            )
        history = kernel.get_state_history(thread)
        assert len(history) == 1  # only the seed checkpoint: nothing committed
        assert history[0].checkpoint.channels["x"]["value"] == initial
        assert "value" not in history[0].checkpoint.channels.get("ax", {}) or (
            history[0].checkpoint.channels["ax"].get("version", 0) == 0
        )

        armed["on"] = False
        resumed = await compiled.invoke(
            input=None,
            effects=SimulatedEffects(seed),
            persistence=kernel,
            thread_id=thread,
        )
        # a never re-executed; b re-ran once, against the PRE-step snapshot.
        assert calls == {"a": 1, "b": 2}
        assert resumed.state["log"].count(f"a_saw_{initial}") == 1
        assert resumed.state["log"].count(f"b_saw_{initial}") == 1

        never_calls = {"a": 0, "b": 0}
        never_armed = {"on": False}
        never = _atomicity_graph(never_calls, never_armed)
        baseline = await never.invoke(
            input={"x": initial}, effects=SimulatedEffects(seed)
        )
        assert resumed.state == baseline.state
        assert resumed.state_digest == baseline.state_digest

    asyncio.run(run())


def _chain():
    return (
        GraphBuilder("prop-chain")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", lambda s: {"x": s["x"] + 3, "log": ["a"]})
        .add_node("b", lambda s: {"x": s["x"] * 2, "log": ["b"]})
        .add_node("c", lambda s: {"x": s["x"] - 5, "log": ["c"]})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", "c")
        .add_edge("c", END)
        .compile()
    )


@BOUNDED
@given(
    initial=st.integers(min_value=-1000, max_value=1000),
    kill_after=st.integers(min_value=0, max_value=3),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_property_4_checkpoint_resume_equivalence(initial, kill_after, seed):
    """Resume from checkpoint k reaches the uninterrupted run's final state."""

    async def run() -> None:
        compiled = _chain()
        caps: dict[int, RunCheckpoint] = {}
        full = await compiled.invoke(
            input={"x": initial, "log": []},
            effects=SimulatedEffects(seed),
            on_checkpoint=lambda rc: caps.__setitem__(rc.superstep, rc),
        )
        resume_point = caps[min(kill_after, max(caps))]
        resumed = await compiled.invoke(
            effects=SimulatedEffects(seed), resume_from=resume_point
        )
        assert resumed.state == full.state
        assert resumed.state_digest == full.state_digest

    asyncio.run(run())


@BOUNDED
@given(
    xs=st.lists(st.integers(min_value=-50, max_value=50), max_size=6),
    ys=st.lists(st.integers(min_value=-50, max_value=50), max_size=6),
    superstep=st.integers(min_value=1, max_value=5),
)
def test_property_5_reducer_batching_invariance(xs, ys, superstep):
    """reduce(reduce(s, xs), ys) == reduce(s, xs + ys) for all batchings."""
    import operator

    from dharma_swarm.graph.channels import ChannelWrite, ReducerChannel

    def fresh():
        channel = ReducerChannel(operator.add, empty_value=0)
        channel.name = "acc"
        return channel

    def writes(values, step):
        return [ChannelWrite("n", "acc", value, i) for i, value in enumerate(values)]

    split = fresh()
    if xs:
        split.commit(writes(xs, superstep), superstep)
    if ys:
        split.commit(writes(ys, superstep + 1), superstep + 1)
    joined = fresh()
    if xs + ys:
        joined.commit(writes(xs + ys, superstep), superstep)
    if xs + ys:
        assert split.get() == joined.get()
    # list reducer: same law over sequence concatenation
    split_l = ReducerChannel(operator.add, empty_value=[])
    split_l.name = "log"
    if xs:
        split_l.commit(writes([[v] for v in xs], superstep), superstep)
    if ys:
        split_l.commit(writes([[v] for v in ys], superstep + 1), superstep + 1)
    joined_l = ReducerChannel(operator.add, empty_value=[])
    joined_l.name = "log"
    if xs + ys:
        joined_l.commit(writes([[v] for v in xs + ys], superstep), superstep)
    if xs + ys:
        assert split_l.get() == joined_l.get() == xs + ys


# ---------------------------------------------------------------------------
# Review-fix regression pins (PR #1002 post-reseal round). Not properties —
# each pins one repaired engine behavior with a single bounded scenario.
# ---------------------------------------------------------------------------


def test_reducer_validate_stages_fold_before_any_commit():
    """A raising reducer must abort the barrier BEFORE any channel mutates."""
    import operator

    from dharma_swarm.graph.channels import ChannelWrite, ReducerChannel
    from dharma_swarm.graph.state import GraphState

    def explosive(acc, value):
        raise RuntimeError("bad reducer")

    state = GraphState(
        {
            "aaa_boom": lambda: ReducerChannel(explosive, empty_value=0),
            "zzz_ok": lambda: ReducerChannel(operator.add, empty_value=0),
        }
    )
    with pytest.raises(RuntimeError, match="bad reducer"):
        state.apply_writes(
            [
                ChannelWrite("n", "aaa_boom", 1, 0),
                ChannelWrite("n", "zzz_ok", 2, 0),
            ],
            1,
        )
    assert state.versions == {"aaa_boom": 0, "zzz_ok": 0}  # nothing committed


def test_send_timeout_enforced_for_sync_nodes():
    """A blocking SYNC callable under Send timeout must still time out."""
    import time

    from dharma_swarm.graph.routing import Send

    def fan(state: Mapping[str, Any]):
        return None

    def blocker(arg: Mapping[str, Any]) -> dict[str, Any]:
        time.sleep(0.7)
        return {"out": "never"}

    compiled = (
        GraphBuilder("sync-timeout")
        .add_channel("out", LastValueChannel)
        .add_node("fan", fan)
        .add_node("worker", blocker)
        .add_edge(START, "fan")
        .add_conditional_edges(
            "fan",
            lambda view: [Send("worker", {"go": 1}, timeout=0.05)],
            ["worker"],
        )
        .add_edge("worker", END)
        .compile()
    )
    with pytest.raises(NodeExecutionError, match="exceeded its send timeout"):
        asyncio.run(
            compiled.invoke(input={}, effects=SimulatedEffects(11))
        )


def test_remaining_steps_budget_resets_on_resume():
    """Every invocation gets the FULL superstep budget, including resume."""
    from typing import TypedDict

    from dharma_swarm.graph.schema import RemainingSteps, TypedStateGraph

    class S(TypedDict, total=False):
        seen: Any
        hops: int
        remaining: RemainingSteps

    observed: list[int] = []

    def hop(state: Mapping[str, Any]) -> dict[str, Any]:
        observed.append(state["remaining"])
        return {"hops": state.get("hops", 0) + 1}

    typed = (
        TypedStateGraph(S, graph_id="remaining-reset")
        .add_node("a", hop)
        .add_node("b", hop)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )

    async def run() -> None:
        caps: dict[int, RunCheckpoint] = {}
        await typed.invoke(
            input={"hops": 0},
            effects=SimulatedEffects(4),
            superstep_cap=9,
            on_checkpoint=lambda rc: caps.__setitem__(rc.superstep, rc),
        )
        assert observed == [8, 7]  # cap 9: superstep 1 sees 8, superstep 2 sees 7
        observed.clear()
        await typed.inner.invoke(
            effects=SimulatedEffects(4),
            superstep_cap=9,
            resume_from=caps[1],
        )
        # Resumed invocation: b runs in absolute superstep 2 but sees the
        # budget RESET (8), not the continued countdown (7).
        assert observed == [8]

    asyncio.run(run())


def test_failure_view_preserves_unfinished_send_packets():
    """Resuming from the post-failure view re-runs ONLY unfinished Sends."""
    from dharma_swarm.graph.routing import Send

    calls: dict[str, int] = {"ok": 0, "bad": 0}
    armed = {"on": True}

    def fan(state: Mapping[str, Any]):
        return None

    def worker(arg: Mapping[str, Any]) -> dict[str, Any]:
        which = arg["which"]
        calls[which] += 1
        if which == "bad" and armed["on"]:
            raise RuntimeError("seeded-send-failure")
        return {"log": [which]}

    def build():
        return (
            GraphBuilder("send-failure-view")
            .add_channel("log", AppendChannel)
            .add_node("fan", fan)
            .add_node("worker", worker)
            .add_edge(START, "fan")
            .add_conditional_edges(
                "fan",
                lambda view: [
                    Send("worker", {"which": "ok"}),
                    Send("worker", {"which": "bad"}),
                ],
                ["worker"],
            )
            .add_edge("worker", END)
            .compile()
        )

    async def run() -> None:
        views: list[RunCheckpoint] = []
        with pytest.raises(NodeExecutionError, match="seeded-send-failure"):
            await build().invoke(
                input={"log": []},
                effects=SimulatedEffects(6),
                on_checkpoint=views.append,
            )
        armed["on"] = False
        resumed = await build().invoke(
            effects=SimulatedEffects(6), resume_from=views[-1]
        )
        assert sorted(resumed.state["log"]) == ["bad", "ok"]
        # ok-packet ran once (its write survived in the view); bad twice.
        assert calls == {"ok": 1, "bad": 2}

    asyncio.run(run())


def test_partial_replay_emits_events_for_recorded_tasks(tmp_path):
    """Failure-resume receipts cover recorded siblings, not just live tasks."""
    calls = {"a": 0, "b": 0}
    armed = {"on": True}
    compiled = _atomicity_graph(calls, armed)

    async def run() -> None:
        kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")
        with pytest.raises(NodeExecutionError):
            await compiled.invoke(
                input={"x": 3},
                effects=SimulatedEffects(9),
                graph_run_id="events",
                persistence=kernel,
                thread_id="events",
            )
        armed["on"] = False
        resumed = await compiled.invoke(
            input=None,
            effects=SimulatedEffects(9),
            persistence=kernel,
            thread_id="events",
        )
        replay_step_nodes = sorted(
            event.node_id for event in resumed.events if event.superstep == 1
        )
        assert replay_step_nodes == ["a", "b"]  # recorded a + re-executed b

    asyncio.run(run())
