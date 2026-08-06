"""Invocation surfaces (LG12) — dharmagraph-engine-2026-07.

Covers the sync / streaming / typed-v2 projections of the one committed
superstep loop: ``invoke_sync``, ``stream``, ``stream_sync``, and the
``stream_mode`` / ``version`` pair. Every surface must observe the SAME
committed barriers as ``invoke`` — a stream that could show uncommitted
state would break the engine's all-or-nothing superstep contract.
No LangGraph imports here — the two-arm differential lives in the parity
gauntlet (``seeded_invocation_surfaces``).
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, TypedDict

import pytest

from dharma_swarm.graph.channels import AppendChannel, LastValueChannel
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.errors import GraphRuntimeError, NodeExecutionError
from dharma_swarm.graph.schema import SchemaError, TypedStateGraph
from dharma_swarm.graph.scheduler import CompiledGraph
from dharma_swarm.graph.types import END, START

SEED = 20260714


class _TypedFull(TypedDict, total=False):
    x: int
    secret: int


class _TypedProjected(TypedDict, total=False):
    x: int


def _chain() -> CompiledGraph:
    """Two-node reducer chain: one node per superstep, both channels seeded."""
    return (
        GraphBuilder("invocation-chain")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"x": state["x"] + 1, "log": ["a"]})
        .add_node("b", lambda state: {"x": state["x"] * 2, "log": ["b"]})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )


def _parallel() -> CompiledGraph:
    """Two same-superstep writers behind one reducer channel."""
    return (
        GraphBuilder("invocation-parallel")
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"log": ["a"]})
        .add_node("b", lambda state: {"log": ["b"]})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )


def _seed() -> dict[str, Any]:
    return {"x": 1, "log": []}


def test_invoke_sync_matches_async_invoke_result_and_digest():
    graph = _chain()
    sync_result = graph.invoke_sync(
        input=_seed(), effects=SimulatedEffects(SEED)
    )
    async_result = asyncio.run(
        graph.invoke(_seed(), effects=SimulatedEffects(SEED))
    )
    assert dict(sync_result.state) == dict(async_result.state) == {
        "x": 4,
        "log": ["a", "b"],
    }
    assert sync_result.state_digest == async_result.state_digest
    assert sync_result.supersteps == async_result.supersteps == 2


def test_invoke_sync_fails_closed_inside_running_event_loop():
    graph = _chain()

    async def caller() -> None:
        graph.invoke_sync(input=_seed(), effects=SimulatedEffects(SEED))

    with pytest.raises(GraphRuntimeError, match="private event loop"):
        asyncio.run(caller())


def test_stream_sync_fails_closed_inside_running_event_loop_before_first_next():
    graph = _chain()

    async def caller() -> None:
        # The guard must fire on the CALL, not on the first next() — a
        # generator that only fails when pumped would hand the caller a
        # broken iterator instead of a fail-closed error.
        graph.stream_sync(input=_seed(), effects=SimulatedEffects(SEED))

    with pytest.raises(GraphRuntimeError, match="private event loop"):
        asyncio.run(caller())


def test_stream_values_yields_seed_then_each_committed_barrier():
    graph = _chain()

    async def collect() -> list[Any]:
        return [
            chunk
            async for chunk in graph.stream(
                _seed(), stream_mode="values", effects=SimulatedEffects(SEED)
            )
        ]

    assert asyncio.run(collect()) == [
        {"x": 1, "log": []},
        {"x": 2, "log": ["a"]},
        {"x": 4, "log": ["a", "b"]},
    ]


def test_stream_updates_yields_per_task_writes_and_skips_the_seed():
    graph = _chain()

    async def collect() -> list[Any]:
        return [
            chunk
            async for chunk in graph.stream(
                _seed(), stream_mode="updates", effects=SimulatedEffects(SEED)
            )
        ]

    # No seed chunk: the seed commits state but executes no task.
    assert asyncio.run(collect()) == [
        {"a": {"log": ["a"], "x": 2}},
        {"b": {"log": ["b"], "x": 4}},
    ]


def test_stream_updates_orders_same_superstep_chunks_canonically():
    graph = _parallel()

    async def collect() -> list[Any]:
        return [
            chunk
            async for chunk in graph.stream(
                {"log": []},
                stream_mode="updates",
                effects=SimulatedEffects(SEED),
            )
        ]

    # Both nodes commit in ONE barrier; chunk order is canonical node order,
    # never the seeded effects dispatch order.
    assert asyncio.run(collect()) == [
        {"a": {"log": ["a"]}},
        {"b": {"log": ["b"]}},
    ]


def test_stream_sync_sequence_equals_async_stream_sequence():
    graph = _chain()

    async def collect() -> list[Any]:
        return [
            chunk
            async for chunk in graph.stream(
                _seed(), stream_mode="values", effects=SimulatedEffects(SEED)
            )
        ]

    sync_chunks = list(
        graph.stream_sync(
            input=_seed(), stream_mode="values", effects=SimulatedEffects(SEED)
        )
    )
    assert sync_chunks == asyncio.run(collect())


def test_stream_yields_nothing_past_the_last_committed_barrier():
    def _boom(state: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("node exploded")

    graph = (
        GraphBuilder("invocation-failure")
        .add_channel("x", LastValueChannel)
        .add_node("a", lambda state: {"x": state["x"] + 1})
        .add_node("b", _boom)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    seen: list[Any] = []

    async def drain() -> None:
        async for chunk in graph.stream(
            {"x": 1}, stream_mode="values", effects=SimulatedEffects(SEED)
        ):
            seen.append(chunk)

    with pytest.raises(NodeExecutionError):
        asyncio.run(drain())
    # Seed barrier + node 'a' barrier only; the failed superstep commits
    # nothing and therefore emits nothing.
    assert seen == [{"x": 1}, {"x": 2}]


@pytest.mark.parametrize("surface", ["sync", "async"])
def test_invoke_v2_updates_returns_type_ns_data_stream_parts(surface: str):
    graph = _chain()
    if surface == "sync":
        parts = graph.invoke_sync(
            input=_seed(),
            stream_mode="updates",
            version="v2",
            effects=SimulatedEffects(SEED),
        )
    else:
        parts = asyncio.run(
            graph.invoke(
                _seed(),
                stream_mode="updates",
                version="v2",
                effects=SimulatedEffects(SEED),
            )
        )
    assert parts == [
        {"type": "updates", "ns": (), "data": {"a": {"log": ["a"], "x": 2}}},
        {"type": "updates", "ns": (), "data": {"b": {"log": ["b"], "x": 4}}},
    ]


def test_invoke_v1_updates_returns_raw_chunks_and_values_returns_the_result():
    graph = _chain()
    v1_parts = graph.invoke_sync(
        input=_seed(), stream_mode="updates", effects=SimulatedEffects(SEED)
    )
    assert v1_parts == [
        {"a": {"log": ["a"], "x": 2}},
        {"b": {"log": ["b"], "x": 4}},
    ]
    # The historical default contract is untouched.
    result = graph.invoke_sync(input=_seed(), effects=SimulatedEffects(SEED))
    assert dict(result.state) == {"x": 4, "log": ["a", "b"]}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stream_mode": "debug"},
        {"version": "v3"},
    ],
)
def test_invocation_surfaces_reject_unknown_stream_contracts(kwargs: dict):
    graph = _chain()
    with pytest.raises(ValueError, match="fail closed"):
        graph.invoke_sync(input=_seed(), **kwargs)
    with pytest.raises(ValueError, match="fail closed"):
        graph.stream_sync(input=_seed(), **kwargs)


def test_typed_graph_invoke_sync_projects_output_and_refuses_stream_mode():
    typed = (
        TypedStateGraph(
            _TypedFull,
            output=_TypedProjected,
            graph_id="typed-invocation",
        )
        .add_node("a", lambda state: {"x": state["x"] + 1, "secret": 99})
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    result = typed.invoke_sync(
        input={"x": 1, "secret": 0}, effects=SimulatedEffects(SEED)
    )
    assert dict(result.state) == {"x": 2}
    with pytest.raises(SchemaError, match="stream the compiled inner graph"):
        typed.invoke_sync(input={"x": 1}, stream_mode="updates")
