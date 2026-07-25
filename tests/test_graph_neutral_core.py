"""Neutral graph core (Candidate Slice A) — dharmagraph-engine-2026-07.

Covers: compile validation battery, state-integrated superstep execution
(versions drive readiness), two-phase fail-closed commits, snapshot
isolation, effects-budget determinism, and the CheckpointSink hook.
No LangGraph imports here — the differential lives in
tests/test_graph_neutral_langgraph_oracle.py behind the test-oracle extra.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Sequence

import pytest

from dharma_swarm.graph.channels import (
    AppendChannel,
    ChannelWrite,
    ChannelWriteConflictError,
    LastValueChannel,
    UnknownChannelError,
)
from dharma_swarm.graph.checkpoint import GraphCheckpointStore
from dharma_swarm.graph.compiler import (
    DuplicateNodeError,
    FanInNotSupportedError,
    GraphBuilder,
    GraphCompileError,
    GraphCycleError,
    OrphanNodeError,
    UnknownEdgeEndpointError,
)
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.scheduler import (
    MalformedDispatchOrderError,
    NodeExecutionError,
    NodeResultError,
    SuperstepLimitError,
)
from dharma_swarm.graph.state import state_digest
from dharma_swarm.graph.types import END, START


def _write(**updates: Any):
    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        return dict(updates)

    return node


def _linear() -> GraphBuilder:
    return (
        GraphBuilder("linear")
        .add_channel("x", LastValueChannel)
        .add_channel("y", LastValueChannel)
        .add_node("a", _write(x=1))
        .add_node("b", lambda state: {"y": state["x"] + 1})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
    )


def _fanout_append() -> GraphBuilder:
    return (
        GraphBuilder("fanout")
        .add_channel("log", AppendChannel)
        .add_node("a", _write(log=["a1", "a2"]))
        .add_node("b", _write(log="b"))
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
    )


class CountingEffects:
    def __init__(self, inner: SimulatedEffects) -> None:
        self.inner = inner
        self.random_calls = 0
        self.dispatch_calls = 0

    def now(self):
        return self.inner.now()

    def random(self):
        self.random_calls += 1
        return self.inner.random()

    def dispatch_order(self, items: Sequence[Any]) -> list[Any]:
        self.dispatch_calls += 1
        return self.inner.dispatch_order(items)


class BrokenOrderEffects(SimulatedEffects):
    def __init__(self, mode: str) -> None:
        super().__init__(seed=0)
        self.mode = mode

    def dispatch_order(self, items: Sequence[Any]) -> list[Any]:
        ordered = list(items)
        if self.mode == "dropped":
            return ordered[:-1]
        if self.mode == "duplicated":
            return ordered + ordered[:1]
        return ordered[:-1] + ["__ghost__"]


class CommitCountingChannel(LastValueChannel):
    total_commits = 0

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        type(self).total_commits += 1
        return super().commit(writes, superstep)


class NonDeepcopyableChannel(LastValueChannel):
    def __deepcopy__(self, memo):
        raise TypeError("channel runtime handle is not deepcopyable")


# -- compile validation -------------------------------------------------


def test_compile_duplicate_node_rejected():
    builder = GraphBuilder("g").add_node("a", _write()).add_node("a", _write())
    builder.add_edge(START, "a").add_edge("a", END)
    with pytest.raises(DuplicateNodeError, match="duplicate node id") as exc_info:
        builder.compile()
    assert exc_info.value.node_id == "a"


@pytest.mark.parametrize("node_id", ["__start__", "__end__", "__x", "a+b", ""])
def test_compile_reserved_node_ids_rejected(node_id: str):
    builder = GraphBuilder("g").add_node(node_id, _write())
    with pytest.raises(GraphCompileError, match="reserved"):
        builder.compile()


def test_compile_duplicate_edges_dedupe_silently():
    builder = _linear().add_edge("a", "b")
    compiled = builder.compile()
    assert compiled.successors["a"] == ("b",)


@pytest.mark.parametrize(
    "source,target,endpoint",
    [(START, "ghost", "ghost"), ("ghost", END, "ghost")],
)
def test_compile_unknown_edge_endpoints_rejected(source, target, endpoint):
    builder = GraphBuilder("g").add_node("a", _write())
    builder.add_edge(START, "a").add_edge("a", END).add_edge(source, target)
    with pytest.raises(UnknownEdgeEndpointError, match="unknown node") as exc_info:
        builder.compile()
    assert exc_info.value.endpoint == endpoint


def test_compile_end_source_and_start_target_rejected():
    base = GraphBuilder("g").add_node("a", _write())
    with pytest.raises(GraphCompileError, match="END cannot be an edge source"):
        base.add_edge(END, "a").compile()
    base2 = GraphBuilder("g").add_node("a", _write())
    with pytest.raises(GraphCompileError, match="START cannot be an edge target"):
        base2.add_edge("a", START).compile()


def test_compile_direct_start_to_end_rejected():
    with pytest.raises(GraphCompileError, match="direct START -> END"):
        GraphBuilder("g").add_edge(START, END).compile()


def test_compile_no_start_entry_rejected():
    builder = GraphBuilder("g").add_node("a", _write()).add_edge("a", END)
    with pytest.raises(GraphCompileError, match="no entry edge from START"):
        builder.compile()


def test_compile_end_unreachable_rejected():
    builder = GraphBuilder("g").add_node("a", _write()).add_edge(START, "a")
    with pytest.raises(GraphCompileError, match="END is not reachable"):
        builder.compile()


def test_compile_fan_in_rejected_but_end_fan_in_allowed():
    builder = (
        GraphBuilder("g")
        .add_node("a", _write())
        .add_node("b", _write())
        .add_node("c", _write())
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", "c")
        .add_edge("b", "c")
        .add_edge("c", END)
    )
    with pytest.raises(FanInNotSupportedError, match="fan-in") as exc_info:
        builder.compile()
    assert exc_info.value.target == "c"
    assert exc_info.value.sources == ("a", "b")
    assert _fanout_append().compile().graph_id == "fanout"


def test_compile_orphan_rejected_unless_allowed():
    def orphan_builder() -> GraphBuilder:
        return (
            GraphBuilder("g")
            .add_channel("x", LastValueChannel)
            .add_node("a", _write(x=1))
            .add_node("z", _write(x=99))
            .add_edge(START, "a")
            .add_edge("a", END)
        )

    with pytest.raises(OrphanNodeError, match="unreachable") as exc_info:
        orphan_builder().compile()
    assert exc_info.value.node_ids == ("z",)
    compiled = orphan_builder().compile(allow_orphans=True)
    result = asyncio.run(compiled.invoke(effects=SimulatedEffects(1)))
    assert "z" not in {event.node_id for event in result.events}
    assert result.state == {"x": 1}


def test_compile_cycle_rejected():
    builder = (
        GraphBuilder("g")
        .add_node("a", _write())
        .add_node("b", _write())
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", "a")
    )
    with pytest.raises(GraphCycleError, match="allow_cycles=True") as exc_info:
        builder.compile()
    assert exc_info.value.node_ids == ("a", "b")


def test_compile_reserved_and_duplicate_channels_rejected():
    with pytest.raises(GraphCompileError, match="reserved"):
        GraphBuilder("g").add_channel("__x", LastValueChannel).compile()
    builder = (
        GraphBuilder("g")
        .add_channel("x", LastValueChannel)
        .add_channel("x", LastValueChannel)
    )
    with pytest.raises(GraphCompileError, match="declared more than once"):
        builder.compile()


# -- execution semantics -------------------------------------------------


async def test_start_node_end_runs_with_frozen_superstep_numbering():
    compiled = (
        GraphBuilder("tiny")
        .add_channel("x", LastValueChannel)
        .add_node("a", _write(x=1))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert result.status == "completed"
    assert result.state == {"x": 1}
    assert [(e.node_id, e.superstep) for e in result.events] == [(START, 0), ("a", 1)]
    assert result.supersteps == 1
    assert result.state_digest.startswith("sha256:")


async def test_scheduler_commits_custom_channel_once_per_barrier():
    CommitCountingChannel.total_commits = 0
    compiled = (
        GraphBuilder("single-commit")
        .add_channel("x", CommitCountingChannel)
        .add_node("a", _write(x=2))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )

    result = await compiled.invoke({"x": 1}, graph_run_id="run-single-commit")

    assert result.state == {"x": 2}
    assert CommitCountingChannel.total_commits == 2  # seed + node barrier


async def test_scheduler_preflight_does_not_deepcopy_channel_runtime_state():
    compiled = (
        GraphBuilder("non-deepcopyable-channel")
        .add_channel("x", NonDeepcopyableChannel)
        .add_node("a", _write(x=2))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )

    result = await compiled.invoke({"x": 1}, graph_run_id="run-nondeepcopy")

    assert result.state == {"x": 2}


async def test_sequential_nodes_deterministic_state():
    result = await _linear().compile().invoke(effects=SimulatedEffects(42))
    assert result.state == {"x": 1, "y": 2}
    assert [(e.node_id, e.superstep) for e in result.events] == [
        (START, 0),
        ("a", 1),
        ("b", 2),
    ]


async def test_parallel_siblings_snapshot_isolation():
    seen: dict[str, set[str]] = {}

    def probe(name: str, write_key: str):
        def node(state: Mapping[str, Any]) -> dict[str, Any]:
            seen[name] = set(state)
            return {write_key: name}

        return node

    compiled = (
        GraphBuilder("iso")
        .add_channel("xa", LastValueChannel)
        .add_channel("xb", LastValueChannel)
        .add_node("a", probe("a", "xa"))
        .add_node("b", probe("b", "xb"))
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert seen["a"] == set() and seen["b"] == set()
    assert result.state == {"xa": "a", "xb": "b"}


async def test_noop_node_still_triggers_successor():
    compiled = (
        GraphBuilder("noop")
        .add_channel("y", LastValueChannel)
        .add_node("a", lambda state: None)
        .add_node("b", _write(y=2))
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert result.state == {"y": 2}
    assert result.supersteps == 2


async def test_node_mutating_snapshot_does_not_affect_committed_state():
    def vandal(state: Mapping[str, Any]) -> None:
        state["log"].append("EVIL")  # type: ignore[index]
        return None

    compiled = (
        GraphBuilder("mut")
        .add_channel("log", AppendChannel)
        .add_node("a", _write(log=["a"]))
        .add_node("b", vandal)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert result.state == {"log": ["a"]}


async def test_sync_and_async_nodes_mix():
    async def async_node(state: Mapping[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0)
        return {"y": state["x"] * 10}

    compiled = (
        GraphBuilder("mix")
        .add_channel("x", LastValueChannel)
        .add_channel("y", LastValueChannel)
        .add_node("a", _write(x=3))
        .add_node("b", async_node)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert result.state == {"x": 3, "y": 30}


async def test_node_exception_raises_with_cause():
    def bomb(state: Mapping[str, Any]) -> None:
        raise ValueError("boom")

    compiled = (
        GraphBuilder("bomb")
        .add_channel("x", LastValueChannel)
        .add_node("a", _write(x=1))
        .add_node("b", bomb)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    with pytest.raises(NodeExecutionError, match="boom") as exc_info:
        await compiled.invoke(effects=SimulatedEffects(42))
    assert exc_info.value.node_id == "b"
    assert exc_info.value.superstep == 2
    assert isinstance(exc_info.value.__cause__, ValueError)


async def test_cancelled_error_passes_through_unwrapped():
    def cancel(state: Mapping[str, Any]) -> None:
        raise asyncio.CancelledError()

    compiled = (
        GraphBuilder("cancel")
        .add_node("a", cancel)
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(asyncio.CancelledError):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_non_mapping_return_fails_closed():
    compiled = (
        GraphBuilder("bad")
        .add_node("a", lambda state: 42)
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(NodeResultError, match="must return a Mapping"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_reserved_trigger_write_rejected():
    compiled = (
        GraphBuilder("res")
        .add_node("a", _write(**{"__trigger__:a": True}))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(UnknownChannelError, match="reserved"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_undeclared_channel_write_and_input_rejected():
    compiled = (
        GraphBuilder("undeclared")
        .add_node("a", _write(nope=1))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(UnknownChannelError, match="not a declared channel"):
        await compiled.invoke(effects=SimulatedEffects(42))
    with pytest.raises(UnknownChannelError, match="not a declared channel"):
        await compiled.invoke(input={"nope": 1}, effects=SimulatedEffects(42))


async def test_same_superstep_lastvalue_conflict_commits_nothing(tmp_path):
    compiled = (
        GraphBuilder("conflict")
        .add_channel("x", LastValueChannel)
        .add_node("a", _write(x="from_a"))
        .add_node("b", _write(x="from_b"))
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    store = GraphCheckpointStore("run-conflict", persist_dir=tmp_path / "cp")
    with pytest.raises(ChannelWriteConflictError, match="exactly one write") as exc_info:
        await compiled.invoke(
            effects=SimulatedEffects(42),
            checkpoint_store=store,
            graph_run_id="run-conflict",
        )
    assert exc_info.value.channel == "x"
    assert exc_info.value.writers == ("a", "b")
    assert exc_info.value.superstep == 1
    restored = GraphCheckpointStore.restore("run-conflict", persist_dir=tmp_path / "cp")
    latest = restored.latest()
    assert latest is not None and latest.superstep == 0


async def test_append_reducer_accumulates_in_canonical_order():
    result = await _fanout_append().compile().invoke(effects=SimulatedEffects(42))
    assert result.state == {"log": ["a1", "a2", "b"]}


async def test_superstep_cap_raises():
    with pytest.raises(SuperstepLimitError, match="superstep cap 1 exceeded"):
        await _linear().compile().invoke(
            effects=SimulatedEffects(42), superstep_cap=1
        )


@pytest.mark.parametrize("mode", ["dropped", "duplicated", "unknown"])
async def test_malformed_dispatch_order_fails_before_execution(mode: str):
    calls: list[str] = []

    def tracked(name: str):
        def node(state: Mapping[str, Any]) -> None:
            calls.append(name)
            return None

        return node

    compiled = (
        GraphBuilder("broken")
        .add_node("a", tracked("a"))
        .add_node("b", tracked("b"))
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    with pytest.raises(MalformedDispatchOrderError, match="not a permutation"):
        await compiled.invoke(effects=BrokenOrderEffects(mode))
    assert calls == []


# -- determinism / effects budget ----------------------------------------


@pytest.mark.parametrize("seed", [42, 7])
async def test_seeded_runs_replay_identical_event_traces(seed: int):
    compiled = _fanout_append().compile()
    first = await compiled.invoke(effects=SimulatedEffects(seed))
    second = await compiled.invoke(effects=SimulatedEffects(seed))
    assert first.events == second.events
    assert first.graph_run_id == second.graph_run_id
    assert first.state_digest == second.state_digest


async def test_final_digest_invariant_across_seeds():
    compiled = _fanout_append().compile()
    result_a = await compiled.invoke(effects=SimulatedEffects(42))
    result_b = await compiled.invoke(effects=SimulatedEffects(7))
    assert result_a.state_digest == result_b.state_digest
    assert result_a.state == result_b.state


async def test_explicit_run_id_uses_zero_random_draws():
    effects = CountingEffects(SimulatedEffects(42))
    result = await _linear().compile().invoke(effects=effects, graph_run_id="run-x")
    assert result.graph_run_id == "run-x"
    assert effects.random_calls == 0


async def test_dispatch_order_called_once_per_superstep_none_on_halt():
    effects = CountingEffects(SimulatedEffects(42))
    result = await _linear().compile().invoke(effects=effects, graph_run_id="run-x")
    assert result.supersteps == 2
    assert effects.dispatch_calls == 2


async def test_no_refire_without_version_advance():
    calls: list[str] = []

    def tracked(name: str, updates: dict[str, Any]):
        def node(state: Mapping[str, Any]) -> dict[str, Any]:
            calls.append(name)
            return updates

        return node

    compiled = (
        GraphBuilder("once")
        .add_channel("x", LastValueChannel)
        .add_channel("y", LastValueChannel)
        .add_node("a", tracked("a", {"x": 1}))
        .add_node("b", tracked("b", {"y": 2}))
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    await compiled.invoke(effects=SimulatedEffects(42))
    assert calls == ["a", "b"]


async def test_digest_rejects_non_json_and_nan():
    compiled = (
        GraphBuilder("weird")
        .add_channel("x", LastValueChannel)
        .add_node("a", _write(x=object()))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(ValueError, match="not stably JSON-serializable"):
        await compiled.invoke(effects=SimulatedEffects(42))
    with pytest.raises(ValueError):
        state_digest({"x": float("nan")})


async def test_same_topology_same_input_same_digest():
    compiled = _linear().compile()
    first = await compiled.invoke(effects=SimulatedEffects(42))
    second = await compiled.invoke(effects=SimulatedEffects(99))
    assert first.state_digest == second.state_digest
    assert first.state_digest == state_digest(dict(first.state))


# -- checkpoint hook -------------------------------------------------------


async def test_checkpoint_records_one_entry_per_committed_superstep(tmp_path):
    compiled = _fanout_append().compile()
    store = GraphCheckpointStore("run-cp", persist_dir=tmp_path / "cp")
    result = await compiled.invoke(effects=SimulatedEffects(42), checkpoint_store=store)
    assert result.graph_run_id == "run-cp"
    restored = GraphCheckpointStore.restore("run-cp", persist_dir=tmp_path / "cp")
    records = restored.checkpoints
    assert [(r.superstep, r.node_id) for r in records] == [
        (0, START),
        (1, "a+b"),
    ]
    assert records[-1].state_ref == result.state_digest


async def test_checkpoint_run_id_mismatch_raises_before_execution(tmp_path):
    calls: list[str] = []

    def tracked(state: Mapping[str, Any]) -> None:
        calls.append("a")
        return None

    compiled = (
        GraphBuilder("mismatch")
        .add_node("a", tracked)
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    store = GraphCheckpointStore("run-1", persist_dir=tmp_path / "cp")
    with pytest.raises(ValueError, match="does not match"):
        await compiled.invoke(
            effects=SimulatedEffects(42),
            checkpoint_store=store,
            graph_run_id="run-2",
        )
    assert calls == []


async def test_checkpoint_failure_propagates_and_yields_no_result():
    class FailingSink:
        run_id = "run-fail"

        def checkpoint(self, superstep: int, node_id: str, state_ref: str) -> object:
            raise OSError("disk full")

    calls: list[str] = []

    def tracked(state: Mapping[str, Any]) -> None:
        calls.append("a")
        return None

    compiled = (
        GraphBuilder("sink")
        .add_node("a", tracked)
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(OSError, match="disk full"):
        await compiled.invoke(effects=SimulatedEffects(42), checkpoint_store=FailingSink())
    assert calls == []


def test_import_smoke():
    import dharma_swarm.graph as graph_pkg

    for name in ("GraphBuilder", "CompiledGraph", "START", "END", "GraphRunResult"):
        assert hasattr(graph_pkg, name)
