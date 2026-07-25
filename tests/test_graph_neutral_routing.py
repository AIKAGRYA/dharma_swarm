"""Slice B routing primitives — dharmagraph-engine-2026-07.

Covers: barrier joins (all-of fan-in), conditional edges (branch routing),
Send fan-out (PUSH tasks with per-task inputs), Command (update+goto), the
B0 seed-path hardening, and multi-task determinism. No LangGraph imports —
the differential lives in tests/test_graph_neutral_langgraph_oracle.py.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from dharma_swarm.graph.channels import (
    AppendChannel,
    BarrierChannel,
    BarrierMemberError,
    ChannelWrite,
    LastValueChannel,
    UnknownChannelError,
)
from dharma_swarm.graph.compiler import (
    FanInNotSupportedError,
    GraphBuilder,
    GraphCompileError,
    UnknownEdgeEndpointError,
)
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.routing import (
    BranchDestinationError,
    Command,
    Send,
    SendTargetError,
    join_channel,
)
from dharma_swarm.graph.types import END, START


def _write(**updates: Any):
    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        return dict(updates)

    return node


def _noop(state: Mapping[str, Any]) -> None:
    return None


# -- BarrierChannel unit semantics ----------------------------------------


def test_barrier_completes_then_rearms():
    channel = BarrierChannel(frozenset({"a", "b"}))
    channel.name = "__join__:a+b:c"
    assert channel.commit([ChannelWrite("a", channel.name, "a")], 1) is False
    assert channel.version == 0
    assert channel.commit([ChannelWrite("b", channel.name, "b")], 2) is True
    assert channel.version == 1
    assert channel.seen == frozenset()  # re-armed
    assert channel.commit([ChannelWrite("a", channel.name, "a")], 3) is False
    assert channel.version == 1


def test_barrier_duplicate_member_does_not_bump():
    channel = BarrierChannel(frozenset({"a", "b"}))
    channel.name = "j"
    channel.commit([ChannelWrite("a", "j", "a")], 1)
    assert channel.commit([ChannelWrite("a", "j", "a")], 2) is False
    assert channel.version == 0
    assert channel.seen == frozenset({"a"})


def test_barrier_rejects_non_member_write():
    channel = BarrierChannel(frozenset({"a", "b"}))
    channel.name = "j"
    with pytest.raises(BarrierMemberError, match="not in its member set"):
        channel.validate([ChannelWrite("z", "j", "z")], 1)


# -- barrier joins end-to-end ----------------------------------------------


def _join_graph() -> GraphBuilder:
    return (
        GraphBuilder("join")
        .add_channel("log", AppendChannel)
        .add_node("fast", _write(log=["fast"]))
        .add_node("mid", _noop)
        .add_node("slow", _write(log=["slow"]))
        .add_node("joiner", lambda state: {"log": [f"joined:{len(state['log'])}"]})
        .add_edge(START, "fast")
        .add_edge(START, "mid")
        .add_edge("mid", "slow")
        .add_edge(["fast", "slow"], "joiner")
        .add_edge("joiner", END)
    )


async def test_barrier_waits_for_slower_branch():
    result = await _join_graph().compile().invoke(effects=SimulatedEffects(42))
    joiner_events = [e for e in result.events if e.node_id == "joiner"]
    assert len(joiner_events) == 1
    slow_step = next(e.superstep for e in result.events if e.node_id == "slow")
    assert joiner_events[0].superstep == slow_step + 1
    assert result.state["log"][-1] == "joined:2"


async def test_barrier_plus_reducer_sees_both_contributions():
    result = await _join_graph().compile().invoke(effects=SimulatedEffects(7))
    assert sorted(result.state["log"][:2]) == ["fast", "slow"]


def test_mixed_static_and_join_fanin_compiles_and_or_fires():
    builder = (
        GraphBuilder("mixed")
        .add_node("a", _noop)
        .add_node("b", _noop)
        .add_node("d", _noop)
        .add_node("c", _noop)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge(START, "d")
        .add_edge(["a", "b"], "c")
        .add_edge("d", "c")
        .add_edge("c", END)
    )
    compiled = builder.compile()
    assert join_channel(["a", "b"], "c") in compiled.triggers["c"]
    import asyncio

    result = asyncio.run(compiled.invoke(effects=SimulatedEffects(42)))
    c_events = [e for e in result.events if e.node_id == "c"]
    assert len(c_events) == 1  # trigger OR barrier collapse to one activation


def test_plain_fanin_error_directs_to_list_form():
    builder = (
        GraphBuilder("g")
        .add_node("a", _noop)
        .add_node("b", _noop)
        .add_node("c", _noop)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", "c")
        .add_edge("b", "c")
        .add_edge("c", END)
    )
    with pytest.raises(FanInNotSupportedError, match="all-of join"):
        builder.compile()


def test_join_edge_validation():
    with pytest.raises(GraphCompileError, match="at least two sources"):
        GraphBuilder("g").add_node("a", _noop).add_edge(["a"], "a").compile()
    builder = (
        GraphBuilder("g")
        .add_node("a", _noop)
        .add_node("b", _noop)
        .add_edge(START, "a")
        .add_edge(["a", "b"], "ghost")
    )
    with pytest.raises(UnknownEdgeEndpointError, match="unknown node"):
        builder.compile()


# -- conditional edges -------------------------------------------------------


def _router_graph(path) -> GraphBuilder:
    return (
        GraphBuilder("cond")
        .add_channel("route", LastValueChannel)
        .add_channel("mark", AppendChannel)
        .add_node("router", _noop)
        .add_node("a", _write(mark=["a"]))
        .add_node("b", _write(mark=["b"]))
        .add_edge(START, "router")
        .add_conditional_edges("router", path, {"hot": "a", "cold": "b"})
        .add_edge("a", END)
        .add_edge("b", END)
    )


async def test_conditional_taken_and_not_taken():
    compiled = _router_graph(lambda state: "hot").compile()
    result = await compiled.invoke(effects=SimulatedEffects(42))
    fired = {e.node_id for e in result.events}
    assert "a" in fired and "b" not in fired
    assert result.state["mark"] == ["a"]


async def test_conditional_list_of_keys_fires_both():
    compiled = _router_graph(lambda state: ["hot", "cold"]).compile()
    result = await compiled.invoke(effects=SimulatedEffects(42))
    fired = {e.node_id for e in result.events}
    assert {"a", "b"} <= fired
    assert sorted(result.state["mark"]) == ["a", "b"]


async def test_conditional_path_to_end_halts():
    compiled = (
        GraphBuilder("halt")
        .add_channel("mark", AppendChannel)
        .add_node("n", _noop)
        .add_node("next", _write(mark=["next"]))
        .add_edge(START, "n")
        .add_conditional_edges("n", lambda s: "stop", {"stop": END, "go": "next"})
        .add_edge("next", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert "next" not in {e.node_id for e in result.events}
    assert "mark" not in result.state
    assert result.status == "completed"


async def test_conditional_unmapped_key_fails_closed():
    compiled = _router_graph(lambda state: "lukewarm").compile()
    with pytest.raises(BranchDestinationError, match="not .* path_map|not\\b.*in"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_conditional_none_return_fails_closed():
    compiled = _router_graph(lambda state: None).compile()
    with pytest.raises(BranchDestinationError, match="valid destination"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_conditional_from_start_routes_on_input():
    compiled = (
        GraphBuilder("entry")
        .add_channel("who", LastValueChannel)
        .add_channel("mark", AppendChannel)
        .add_node("a", _write(mark=["a"]))
        .add_node("b", _write(mark=["b"]))
        .add_conditional_edges(
            START, lambda s: s.get("who", "a"), {"a": "a", "b": "b"}
        )
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    result = await compiled.invoke(input={"who": "b"}, effects=SimulatedEffects(42))
    assert result.state["mark"] == ["b"]
    assert "a" not in {e.node_id for e in result.events}


def test_conditional_requires_path_map():
    builder = GraphBuilder("g").add_node("n", _noop)
    with pytest.raises(GraphCompileError, match="requires an explicit path_map"):
        builder.add_conditional_edges("n", lambda s: "x")


def test_conditional_unknown_destination_rejected_at_compile():
    builder = (
        GraphBuilder("g")
        .add_node("n", _noop)
        .add_edge(START, "n")
        .add_conditional_edges("n", lambda s: "x", {"x": "ghost"})
    )
    with pytest.raises(UnknownEdgeEndpointError, match="unknown node"):
        builder.compile()


async def test_branch_sees_own_writes_not_siblings():
    """The path reads the source's OWN same-superstep writes, nothing else."""
    seen: dict[str, Any] = {}

    def path(view: Mapping[str, Any]) -> str:
        seen["flag"] = view.get("flag")
        seen["own"] = view.get("own")
        return "go"

    compiled = (
        GraphBuilder("view")
        .add_channel("flag", LastValueChannel)
        .add_channel("own", LastValueChannel)
        .add_channel("mark", AppendChannel)
        .add_node("router", _write(own="mine"))
        .add_node("sibling", _write(flag=True))
        .add_node("t", _write(mark=["t"]))
        .add_edge(START, "router")
        .add_edge(START, "sibling")
        .add_conditional_edges("router", path, {"go": "t"})
        .add_edge("t", END)
        .add_edge("sibling", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert seen["own"] == "mine"  # own pending write visible
    assert seen["flag"] is None  # sibling's same-superstep write NOT visible
    assert result.state["mark"] == ["t"]


# -- Send fan-out -------------------------------------------------------------


def _fanout_graph(items: list[int]) -> GraphBuilder:
    def spawn(state: Mapping[str, Any]) -> Any:
        return [Send("worker", {"i": i}) for i in state["items"]]

    def worker(arg: Mapping[str, Any]) -> dict[str, Any]:
        return {"out": [arg["i"]]}

    return (
        GraphBuilder("fan")
        .add_channel("items", LastValueChannel)
        .add_channel("out", AppendChannel)
        .add_node("worker", worker)
        .add_conditional_edges(START, spawn, {"worker": "worker"})
        .add_edge("worker", END)
    )


async def test_send_fanout_runs_one_task_per_send_with_own_arg():
    compiled = _fanout_graph([1, 2, 3]).compile()
    result = await compiled.invoke(
        input={"items": [1, 2, 3]}, effects=SimulatedEffects(42)
    )
    worker_events = [e for e in result.events if e.node_id == "worker"]
    assert len(worker_events) == 3
    assert sorted(e.task_index for e in worker_events) == [1, 2, 3]
    assert all(e.superstep == 1 for e in worker_events)
    assert sorted(result.state["out"]) == [1, 2, 3]


async def test_send_fanout_deterministic_across_seeds():
    compiled = _fanout_graph([1, 2, 3]).compile()
    r42 = await compiled.invoke(
        input={"items": [1, 2, 3]}, effects=SimulatedEffects(42)
    )
    r7 = await compiled.invoke(
        input={"items": [1, 2, 3]}, effects=SimulatedEffects(7)
    )
    assert r42.state_digest == r7.state_digest
    assert {(e.node_id, e.superstep, e.task_index) for e in r42.events} == {
        (e.node_id, e.superstep, e.task_index) for e in r7.events
    }


async def test_pull_and_push_tasks_coexist_one_superstep():
    """A node with a fired trigger AND a pending Send runs BOTH tasks."""
    inputs: list[Any] = []

    def probe(node_input: Any) -> dict[str, Any]:
        inputs.append(node_input)
        tag = node_input.get("tag", "pull") if isinstance(node_input, Mapping) else "?"
        return {"log": [tag]}

    def sender(state: Mapping[str, Any]) -> Any:
        return Command(goto=Send("c", {"tag": "push"}))

    compiled = (
        GraphBuilder("both")
        .add_channel("log", AppendChannel)
        .add_node("a", sender)
        .add_node("c", probe)
        .add_edge(START, "a")
        .add_edge("a", "c")
        .add_edge("c", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    c_events = [e for e in result.events if e.node_id == "c"]
    assert sorted(e.task_index for e in c_events) == [0, 1]
    assert all(e.superstep == 2 for e in c_events)
    assert sorted(result.state["log"]) == ["pull", "push"]


async def test_send_to_unknown_node_fails_closed():
    def spawn(state: Mapping[str, Any]) -> Any:
        return [Send("ghost", {})]

    compiled = (
        GraphBuilder("g")
        .add_channel("out", AppendChannel)
        .add_node("worker", _write(out=["w"]))
        .add_conditional_edges(START, spawn, {"worker": "worker"})
        .add_edge("worker", END)
        .compile()
    )
    with pytest.raises(SendTargetError, match="unknown node 'ghost'"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_send_to_end_fails_closed():
    def spawn(state: Mapping[str, Any]) -> Any:
        return [Send(END, {})]

    compiled = (
        GraphBuilder("g")
        .add_channel("out", AppendChannel)
        .add_node("worker", _write(out=["w"]))
        .add_conditional_edges(START, spawn, {"worker": "worker"})
        .add_edge("worker", END)
        .compile()
    )
    with pytest.raises(SendTargetError, match="END"):
        await compiled.invoke(effects=SimulatedEffects(42))


# -- Command ------------------------------------------------------------------


async def test_command_update_and_goto_are_additive():
    compiled = (
        GraphBuilder("cmd")
        .add_channel("x", LastValueChannel)
        .add_channel("mark", AppendChannel)
        .add_node("a", lambda s: Command(update={"x": 5}, goto="b"))
        .add_node("b", _write(mark=["b"]))
        .add_node("c", _write(mark=["c"]))
        .add_edge(START, "a")
        .add_edge("a", "c")
        .add_edge("b", END)
        .add_edge("c", END)
        .compile(allow_orphans=True)
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert result.state["x"] == 5
    fired = {e.node_id for e in result.events}
    assert {"b", "c"} <= fired  # goto ADDS to static routing, never replaces
    assert sorted(result.state["mark"]) == ["b", "c"]


async def test_command_goto_end_silently_skipped():
    compiled = (
        GraphBuilder("cmdend")
        .add_channel("x", LastValueChannel)
        .add_node("a", lambda s: Command(update={"x": 1}, goto=END))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    result = await compiled.invoke(effects=SimulatedEffects(42))
    assert result.state == {"x": 1}
    assert result.status == "completed"


async def test_command_goto_unknown_fails_closed():
    compiled = (
        GraphBuilder("cmdbad")
        .add_node("a", lambda s: Command(goto="ghost"))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(SendTargetError, match="unknown node 'ghost'"):
        await compiled.invoke(effects=SimulatedEffects(42))


async def test_command_update_reserved_key_rejected():
    compiled = (
        GraphBuilder("cmdres")
        .add_node("a", lambda s: Command(update={"__trigger__:a": True}))
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    with pytest.raises(UnknownChannelError, match="reserved"):
        await compiled.invoke(effects=SimulatedEffects(42))


# -- B0 seed hardening ----------------------------------------------------------


def _tiny() -> GraphBuilder:
    return (
        GraphBuilder("tiny")
        .add_channel("x", LastValueChannel)
        .add_node("a", _write(x=1))
        .add_edge(START, "a")
        .add_edge("a", END)
    )


async def test_seed_reserved_key_rejected():
    compiled = _tiny().compile()
    with pytest.raises(UnknownChannelError, match="reserved"):
        await compiled.invoke(
            input={"__trigger__:a": True}, effects=SimulatedEffects(42)
        )
    with pytest.raises(UnknownChannelError, match="reserved"):
        await compiled.invoke(input={"__tasks__": []}, effects=SimulatedEffects(42))


async def test_seed_non_string_key_rejected():
    compiled = _tiny().compile()
    from dharma_swarm.graph.scheduler import NodeResultError

    with pytest.raises(NodeResultError, match="non-string channel key"):
        await compiled.invoke(input={1: "x"}, effects=SimulatedEffects(42))


async def test_reserved_channels_never_leak_into_state_or_digest():
    result = await _fanout_graph([1]).compile().invoke(
        input={"items": [1]}, effects=SimulatedEffects(42)
    )
    assert all(not key.startswith("__") for key in result.state)
