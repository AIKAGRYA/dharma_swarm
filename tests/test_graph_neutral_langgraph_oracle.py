"""Differential oracle: neutral graph core vs REAL langgraph (Slices A + B).

Runs the same graphs through the dharma_swarm neutral core AND langgraph's
StateGraph, diffing semantic outcomes — root-level parity evidence for the
engine slice, not a parity claim for the system. Slice B section covers
conditional routing, Send fan-out, barrier joins, and Command.

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
from langgraph.types import Command as LGCommand  # noqa: E402
from langgraph.types import Send as LGSend  # noqa: E402

from dharma_swarm.graph.channels import (  # noqa: E402
    AppendChannel,
    ChannelWriteConflictError,
    LastValueChannel,
)
from dharma_swarm.graph.compiler import GraphBuilder  # noqa: E402
from dharma_swarm.graph.effects import SimulatedEffects  # noqa: E402
from dharma_swarm.graph.routing import (  # noqa: E402
    BranchDestinationError,
    Command,
    Send,
    SendTargetError,
)
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


# ---------------------------------------------------------------------------
# Slice B differentials: conditional routing, Send fan-out, barriers, Command
# ---------------------------------------------------------------------------


class _RouteState(TypedDict, total=False):
    temp: str
    mark: Annotated[list[Any], operator.add]


def _lg_router(path_return: Any):
    graph = StateGraph(_RouteState)
    graph.add_node("router", lambda state: {})
    graph.add_node("a", lambda state: {"mark": ["a"]})
    graph.add_node("b", lambda state: {"mark": ["b"]})
    graph.add_edge(LG_START, "router")
    graph.add_conditional_edges(
        "router", lambda state: path_return, {"hot": "a", "cold": "b"}
    )
    graph.add_edge("a", LG_END)
    graph.add_edge("b", LG_END)
    return graph.compile()


def _dharma_router(path_return: Any):
    return (
        GraphBuilder("route")
        .add_channel("temp", LastValueChannel)
        .add_channel("mark", AppendChannel)
        .add_node("router", lambda state: None)
        .add_node("a", lambda state: {"mark": ["a"]})
        .add_node("b", lambda state: {"mark": ["b"]})
        .add_edge(START, "router")
        .add_conditional_edges(
            "router", lambda state: path_return, {"hot": "a", "cold": "b"}
        )
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )


async def test_conditional_routing_taken_not_taken_parity():
    lg_final = _lg_router("hot").invoke({"mark": []})
    dharma = await _dharma_router("hot").invoke(
        input={"mark": []}, effects=SimulatedEffects(42)
    )
    assert dharma.state["mark"] == lg_final["mark"] == ["a"]


async def test_conditional_path_to_end_parity():
    graph = StateGraph(_RouteState)
    graph.add_node("n", lambda state: {})
    graph.add_node("next", lambda state: {"mark": ["next"]})
    graph.add_edge(LG_START, "n")
    graph.add_conditional_edges(
        "n", lambda state: "stop", {"stop": LG_END, "go": "next"}
    )
    graph.add_edge("next", LG_END)
    lg_final = graph.compile().invoke({"mark": []})

    compiled = (
        GraphBuilder("halt")
        .add_channel("mark", AppendChannel)
        .add_node("n", lambda state: None)
        .add_node("next", lambda state: {"mark": ["next"]})
        .add_edge(START, "n")
        .add_conditional_edges("n", lambda state: "stop", {"stop": END, "go": "next"})
        .add_edge("next", END)
        .compile()
    )
    dharma = await compiled.invoke(input={"mark": []}, effects=SimulatedEffects(42))
    assert lg_final["mark"] == [] and dharma.state.get("mark", []) == []


class _FanoutState(TypedDict, total=False):
    items: list[int]
    out: Annotated[list[Any], operator.add]


async def test_send_fanout_distinct_args_parity():
    graph = StateGraph(_FanoutState)
    graph.add_node("worker", lambda arg: {"out": [arg["i"] * 10]})
    graph.add_conditional_edges(
        LG_START,
        lambda state: [LGSend("worker", {"i": i}) for i in state["items"]],
        {"worker": "worker"},
    )
    graph.add_edge("worker", LG_END)
    lg_final = graph.compile().invoke({"items": [1, 2, 3], "out": []})

    compiled = (
        GraphBuilder("fan")
        .add_channel("items", LastValueChannel)
        .add_channel("out", AppendChannel)
        .add_node("worker", lambda arg: {"out": [arg["i"] * 10]})
        .add_conditional_edges(
            START,
            lambda state: [Send("worker", {"i": i}) for i in state["items"]],
            {"worker": "worker"},
        )
        .add_edge("worker", END)
        .compile()
    )
    dharma = await compiled.invoke(
        input={"items": [1, 2, 3], "out": []}, effects=SimulatedEffects(42)
    )
    assert sorted(dharma.state["out"]) == sorted(lg_final["out"]) == [10, 20, 30]


class _JoinState(TypedDict, total=False):
    log: Annotated[list[Any], operator.add]
    joined: str


def _lg_join():
    graph = StateGraph(_JoinState)
    graph.add_node("fast", lambda state: {"log": ["fast"]})
    graph.add_node("mid", lambda state: {})
    graph.add_node("slow", lambda state: {"log": ["slow"]})
    graph.add_node("joiner", lambda state: {"joined": f"n={len(state['log'])}"})
    graph.add_edge(LG_START, "fast")
    graph.add_edge(LG_START, "mid")
    graph.add_edge("mid", "slow")
    graph.add_edge(["fast", "slow"], "joiner")
    graph.add_edge("joiner", LG_END)
    return graph.compile()


def _dharma_join():
    return (
        GraphBuilder("join")
        .add_channel("log", AppendChannel)
        .add_channel("joined", LastValueChannel)
        .add_node("fast", lambda state: {"log": ["fast"]})
        .add_node("mid", lambda state: None)
        .add_node("slow", lambda state: {"log": ["slow"]})
        .add_node("joiner", lambda state: {"joined": f"n={len(state['log'])}"})
        .add_edge(START, "fast")
        .add_edge(START, "mid")
        .add_edge("mid", "slow")
        .add_edge(["fast", "slow"], "joiner")
        .add_edge("joiner", END)
        .compile()
    )


async def test_barrier_join_waits_for_slower_branch_parity():
    lg_final = _lg_join().invoke({"log": []})
    dharma = await _dharma_join().invoke(
        input={"log": []}, effects=SimulatedEffects(42)
    )
    assert dharma.state["joined"] == lg_final["joined"] == "n=2"
    assert sorted(dharma.state["log"]) == sorted(lg_final["log"]) == ["fast", "slow"]


async def test_unmapped_path_key_error_parity():
    with pytest.raises(Exception):  # langgraph: KeyError from ends lookup
        _lg_router("lukewarm").invoke({"mark": []})
    with pytest.raises(BranchDestinationError):
        await _dharma_router("lukewarm").invoke(
            input={"mark": []}, effects=SimulatedEffects(42)
        )


async def test_send_to_end_error_parity():
    graph = StateGraph(_FanoutState)
    graph.add_node("worker", lambda arg: {"out": [1]})
    graph.add_conditional_edges(
        LG_START, lambda state: [LGSend(LG_END, {})], {"worker": "worker"}
    )
    graph.add_edge("worker", LG_END)
    with pytest.raises(InvalidUpdateError):
        graph.compile().invoke({"items": [], "out": []})

    compiled = (
        GraphBuilder("sendend")
        .add_channel("out", AppendChannel)
        .add_node("worker", lambda arg: {"out": [1]})
        .add_conditional_edges(
            START, lambda state: [Send(END, {})], {"worker": "worker"}
        )
        .add_edge("worker", END)
        .compile()
    )
    with pytest.raises(SendTargetError):
        await compiled.invoke(input={"out": []}, effects=SimulatedEffects(42))


class _CmdState(TypedDict, total=False):
    x: int
    mark: Annotated[list[Any], operator.add]


async def test_command_update_and_goto_parity():
    graph = StateGraph(_CmdState)
    graph.add_node(
        "a", lambda state: LGCommand(update={"x": 5}, goto="b"), ends=("b",)
    )
    graph.add_node("b", lambda state: {"mark": ["b"]})
    graph.add_edge(LG_START, "a")
    graph.add_edge("a", LG_END)  # static edge alongside goto: additive on both engines
    graph.add_edge("b", LG_END)
    lg_final = graph.compile().invoke({"mark": []})

    compiled = (
        GraphBuilder("cmd")
        .add_channel("x", LastValueChannel)
        .add_channel("mark", AppendChannel)
        .add_node("a", lambda state: Command(update={"x": 5}, goto="b"))
        .add_node("b", lambda state: {"mark": ["b"]})
        .add_edge(START, "a")
        .add_edge("a", END)  # static edge alongside goto: additive on both engines
        .add_edge("b", END)
        .compile(allow_orphans=True)
    )
    dharma = await compiled.invoke(input={"mark": []}, effects=SimulatedEffects(42))
    assert dharma.state["x"] == lg_final["x"] == 5
    assert dharma.state["mark"] == lg_final["mark"] == ["b"]


# ---------------------------------------------------------------------------
# Slice C differential: cyclic recursion-limit parity
# ---------------------------------------------------------------------------

from langgraph.errors import GraphRecursionError  # noqa: E402

from dharma_swarm.graph.scheduler import SuperstepLimitError  # noqa: E402


class _LoopState(TypedDict, total=False):
    count: int


async def test_recursion_limit_both_engines_cap_cyclic_runs():
    """Both engines cap an unbounded cycle; both raise their limit error."""

    def lg_inc(state):
        return {"count": state.get("count", 0) + 1}

    graph = StateGraph(_LoopState)
    graph.add_node("a", lg_inc)
    graph.add_edge(LG_START, "a")
    graph.add_conditional_edges("a", lambda state: "a", {"a": "a"})
    app = graph.compile()
    with pytest.raises(GraphRecursionError):
        app.invoke({"count": 0}, {"recursion_limit": 5})

    def inc(state):
        return {"count": state.get("count", 0) + 1}

    compiled = (
        GraphBuilder("loop")
        .add_channel("count", LastValueChannel)
        .add_node("a", inc)
        .add_edge(START, "a")
        .add_conditional_edges("a", lambda view: "a", {"a": "a"})
        .compile(allow_cycles=True)
    )
    with pytest.raises(SuperstepLimitError):
        await compiled.invoke(effects=SimulatedEffects(42), superstep_cap=5)


async def test_bounded_cycle_reaches_condition_no_error():
    """A cycle that self-terminates before the cap completes on both engines."""

    def lg_inc(state):
        return {"count": state.get("count", 0) + 1}

    graph = StateGraph(_LoopState)
    graph.add_node("a", lg_inc)
    graph.add_edge(LG_START, "a")
    graph.add_conditional_edges(
        "a", lambda s: END if s["count"] >= 3 else "a", {"a": "a", END: END}
    )
    lg_final = graph.compile().invoke({"count": 0}, {"recursion_limit": 25})

    def route(view):
        return "stop" if view.get("count", 0) >= 3 else "loop"

    compiled = (
        GraphBuilder("bounded")
        .add_channel("count", LastValueChannel)
        .add_node("a", lambda s: {"count": s.get("count", 0) + 1})
        .add_edge(START, "a")
        .add_conditional_edges("a", route, {"loop": "a", "stop": END})
        .compile(allow_cycles=True)
    )
    dharma = await compiled.invoke(effects=SimulatedEffects(42), superstep_cap=25)
    assert dharma.state["count"] == lg_final["count"] == 3


# ---------------------------------------------------------------------------
# Slice S2 (Pregel core): failure atomicity + failure resume
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from dharma_swarm.graph.persistence import GraphPersistenceKernel  # noqa: E402
from dharma_swarm.graph.scheduler import NodeExecutionError  # noqa: E402
from dharma_swarm.graph.types import RunCheckpoint  # noqa: E402


class _FailState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]


def _fail_pair(calls: dict[str, int], armed: dict[str, bool]):
    """One (a: writes, b: fails-once) graph body shared by both arms."""

    def node_a(state) -> dict[str, Any]:
        calls["a"] += 1
        return {"x": state["x"] + 1, "log": [f"a_saw_{state['x']}"]}

    def node_b(state) -> dict[str, Any]:
        calls["b"] += 1
        if armed["on"]:
            raise RuntimeError("seeded-failure")
        return {"log": [f"b_saw_{state['x']}"]}

    return node_a, node_b


async def test_failed_step_sibling_writes_survive_and_resume_parity(tmp_path):
    """After a failed superstep both engines expose last-checkpoint state PLUS
    the succeeded sibling's writes; resume re-runs ONLY the failed task,
    against the PRE-step snapshot (empirical langgraph 1.2.4 semantics)."""
    initial = 10

    lg_calls, lg_armed = {"a": 0, "b": 0}, {"on": True}
    lg_a, lg_b = _fail_pair(lg_calls, lg_armed)
    graph = StateGraph(_FailState)
    graph.add_node("a", lg_a)
    graph.add_node("b", lg_b)
    graph.add_edge(LG_START, "a")
    graph.add_edge(LG_START, "b")
    graph.add_edge("a", LG_END)
    graph.add_edge("b", LG_END)
    app = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "fail-parity"}}
    with pytest.raises(RuntimeError, match="seeded-failure"):
        app.invoke({"x": initial, "log": []}, config)
    lg_after = app.get_state(config).values
    lg_armed["on"] = False
    lg_resumed = app.invoke(None, config)

    dh_calls, dh_armed = {"a": 0, "b": 0}, {"on": True}
    dh_a, dh_b = _fail_pair(dh_calls, dh_armed)
    compiled = (
        GraphBuilder("fail-parity")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", dh_a)
        .add_node("b", dh_b)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")
    views: list[RunCheckpoint] = []
    with pytest.raises(NodeExecutionError, match="seeded-failure"):
        await compiled.invoke(
            input={"x": initial, "log": []},
            effects=SimulatedEffects(7),
            graph_run_id="fail-parity",
            persistence=kernel,
            thread_id="fail-parity",
            on_checkpoint=views.append,
        )
    pending_view = views[-1]
    dh_after = {
        "x": pending_view.channels["x"]["value"],
        "log": list(pending_view.channels["log"]["items"]),
    }
    assert dh_after == lg_after == {"x": initial + 1, "log": [f"a_saw_{initial}"]}

    dh_armed["on"] = False
    dh_resumed = await compiled.invoke(
        input=None,
        effects=SimulatedEffects(7),
        persistence=kernel,
        thread_id="fail-parity",
    )
    assert dh_resumed.state == dict(lg_resumed) == {
        "x": initial + 1,
        "log": [f"a_saw_{initial}", f"b_saw_{initial}"],
    }
    # Succeeded task never re-executed on either arm; failed task re-ran once.
    assert lg_calls == dh_calls == {"a": 1, "b": 2}


async def test_typed_input_schema_resume_parity(tmp_path):
    """Command(resume=...) works through a TYPED graph with an input schema
    on both engines, and extra seed keys are dropped, not errors."""
    from langgraph.types import Command as LGResumeCommand
    from langgraph.types import interrupt as lg_interrupt

    from dharma_swarm.graph.interrupts import GraphInterrupted
    from dharma_swarm.graph.interrupts import interrupt as dh_interrupt
    from dharma_swarm.graph.routing import Command as DhCommand
    from dharma_swarm.graph.schema import TypedStateGraph

    class _TypedResumeState(TypedDict, total=False):
        x: int
        log: Annotated[list[Any], operator.add]

    class _TypedResumeInput(TypedDict, total=False):
        x: int

    def lg_ask(state):
        bump = lg_interrupt({"q": "bump?"})
        return {"x": state["x"] + bump, "log": ["ask"]}

    graph = StateGraph(_TypedResumeState, input_schema=_TypedResumeInput)
    graph.add_node("ask", lg_ask)
    graph.add_edge(LG_START, "ask")
    graph.add_edge("ask", LG_END)
    app = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "typed-resume"}}
    first = app.invoke({"x": 10, "log": ["dropped-seed"]}, config)
    assert "__interrupt__" in first
    lg_final = app.invoke(LGResumeCommand(resume=4), config)

    def dh_ask(state):
        bump = dh_interrupt({"q": "bump?"})
        return {"x": state["x"] + bump, "log": ["ask"]}

    typed = (
        TypedStateGraph(
            _TypedResumeState,
            input=_TypedResumeInput,
            graph_id="typed-resume",
        )
        .add_node("ask", dh_ask)
        .add_edge(START, "ask")
        .add_edge("ask", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")
    with pytest.raises(GraphInterrupted):
        await typed.invoke(
            input={"x": 10, "log": ["dropped-seed"]},
            effects=SimulatedEffects(13),
            graph_run_id="typed-resume",
            persistence=kernel,
            thread_id="typed-resume",
        )
    dh_final = await typed.invoke(
        input=DhCommand(resume=4),
        effects=SimulatedEffects(13),
        persistence=kernel,
        thread_id="typed-resume",
    )
    # Both arms: extra seed key dropped, resume value applied, one ask entry.
    assert dict(dh_final.state) == dict(lg_final) == {"x": 14, "log": ["ask"]}
