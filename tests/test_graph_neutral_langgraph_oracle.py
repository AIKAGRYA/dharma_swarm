"""Differential oracle: neutral graph core vs REAL langgraph (Candidate Slice A).

Runs the same acyclic graphs through the new dharma_swarm neutral core AND
langgraph's StateGraph, diffing semantic outcomes — root-level parity
evidence for the engine slice, not a parity claim for the system.

Guarded exactly like tests/test_langgraph_differential_oracle.py: requires
the [test-oracle] extra with langgraph pinned to the oracle version;
skips cleanly otherwise. langgraph is a differential REFERENCE here, never
a runtime dependency of dharma_swarm/graph/**.
"""

from __future__ import annotations

import operator
from importlib.metadata import version as _pkg_version
from typing import Annotated, Any, TypedDict

import pytest

pytest.importorskip("langgraph", reason="test-oracle extra not installed")

_ORACLE_PIN = "1.2.4"
if _pkg_version("langgraph") != _ORACLE_PIN:
    pytest.skip(
        f"differential oracle pins langgraph=={_ORACLE_PIN}; found "
        f"{_pkg_version('langgraph')} (the infra extra's floating version "
        "would give false parity/divergence)",
        allow_module_level=True,
    )

from langgraph.errors import InvalidUpdateError  # noqa: E402
from langgraph.graph import END as LG_END  # noqa: E402
from langgraph.graph import START as LG_START  # noqa: E402
from langgraph.graph import StateGraph  # noqa: E402

from dharma_swarm.graph.channels import (  # noqa: E402
    AppendChannel,
    ChannelWriteConflictError,
    LastValueChannel,
)
from dharma_swarm.graph.compiler import GraphBuilder  # noqa: E402
from dharma_swarm.graph.effects import SimulatedEffects  # noqa: E402
from dharma_swarm.graph.types import END, START  # noqa: E402


class _LinearState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]


class _FanState(TypedDict, total=False):
    log: Annotated[list[Any], operator.add]


class _ConflictState(TypedDict, total=False):
    x: int


def _lg_linear():
    graph = StateGraph(_LinearState)
    graph.add_node("a", lambda state: {"x": 1, "log": ["a"]})
    graph.add_node("b", lambda state: {"x": state["x"] + 1, "log": ["b"]})
    graph.add_edge(LG_START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", LG_END)
    return graph.compile()


def _dharma_linear():
    return (
        GraphBuilder("linear")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"x": 1, "log": ["a"]})
        .add_node("b", lambda state: {"x": state["x"] + 1, "log": ["b"]})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )


async def test_linear_final_state_parity():
    lg_final = _lg_linear().invoke({"x": 0, "log": []})
    dharma_result = await _dharma_linear().invoke(
        input={"x": 0, "log": []}, effects=SimulatedEffects(42)
    )
    assert dict(dharma_result.state) == dict(lg_final) == {"x": 2, "log": ["a", "b"]}


async def test_parallel_append_multiset_parity():
    graph = StateGraph(_FanState)
    graph.add_node("a", lambda state: {"log": ["a"]})
    graph.add_node("b", lambda state: {"log": ["b"]})
    graph.add_edge(LG_START, "a")
    graph.add_edge(LG_START, "b")
    graph.add_edge("a", LG_END)
    graph.add_edge("b", LG_END)
    lg_final = graph.compile().invoke({"log": []})

    compiled = (
        GraphBuilder("fan")
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"log": ["a"]})
        .add_node("b", lambda state: {"log": ["b"]})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    dharma_result = await compiled.invoke(input={"log": []}, effects=SimulatedEffects(42))
    assert sorted(dharma_result.state["log"]) == sorted(lg_final["log"]) == ["a", "b"]


async def test_same_step_lastvalue_conflict_both_fail_closed():
    graph = StateGraph(_ConflictState)
    graph.add_node("a", lambda state: {"x": 1})
    graph.add_node("b", lambda state: {"x": 2})
    graph.add_edge(LG_START, "a")
    graph.add_edge(LG_START, "b")
    graph.add_edge("a", LG_END)
    graph.add_edge("b", LG_END)
    with pytest.raises(InvalidUpdateError):
        graph.compile().invoke({"x": 0})

    compiled = (
        GraphBuilder("conflict")
        .add_channel("x", LastValueChannel)
        .add_node("a", lambda state: {"x": 1})
        .add_node("b", lambda state: {"x": 2})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    with pytest.raises(ChannelWriteConflictError):
        await compiled.invoke(input={"x": 0}, effects=SimulatedEffects(42))
