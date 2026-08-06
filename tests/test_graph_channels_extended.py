"""Extended channel family (LG10) — dharmagraph-engine-2026-07.

Covers the step-scoped (ephemeral / any-value), untracked, batch-reducer
(delta) and after-finish channels plus the two lifecycle hooks they need:
``Channel.end_step`` at every committed barrier and ``Channel.finish`` at
quiescence. No LangGraph imports here — the two-arm differential lives in
tests/oracle_support/dharmagraph_gauntlet.py::_channel_semantics_arm.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from dharma_swarm.graph.channels import (
    AnyValueChannel,
    AppendChannel,
    BarrierMemberError,
    ChannelWrite,
    ChannelWriteConflictError,
    DeltaChannel,
    EmptyChannelError,
    EphemeralChannel,
    LastValueAfterFinishChannel,
    LastValueChannel,
    NamedBarrierAfterFinishChannel,
    UntrackedValueChannel,
)
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.types import END, START


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _writes(channel: str, *pairs: tuple[str, Any]) -> list[ChannelWrite]:
    return [ChannelWrite(node_id, channel, value) for node_id, value in pairs]


def _semantics_graph() -> Any:
    """START -> (pub_a | pub_b) -> reader -> tail, one of every new channel."""

    def pub_a(state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "eph": 5,
            "anyv": 7,
            "untracked": 11,
            "delta": 3,
            "afterfinish": 21,
            "joined": "pub_a",
            "log": ["pub_a"],
        }

    def pub_b(state: Mapping[str, Any]) -> dict[str, Any]:
        return {"anyv": 7, "delta": 4, "joined": "pub_b", "log": ["pub_b"]}

    def reader(state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "seen": [
                state.get("eph", -1),
                state.get("anyv", -1),
                "afterfinish" in state,
                "joined" in state,
            ],
            "log": ["reader"],
        }

    def tail(state: Mapping[str, Any]) -> dict[str, Any]:
        return {"late": ["eph" in state, "anyv" in state], "log": ["tail"]}

    return (
        GraphBuilder("channels-extended")
        .add_channel("log", AppendChannel)
        .add_channel("seen", AppendChannel)
        .add_channel("late", AppendChannel)
        .add_channel("eph", EphemeralChannel)
        .add_channel("anyv", AnyValueChannel)
        .add_channel("untracked", UntrackedValueChannel)
        .add_channel(
            "delta",
            lambda: DeltaChannel(lambda current, updates: list(current) + list(updates), []),
        )
        .add_channel("afterfinish", LastValueAfterFinishChannel)
        .add_channel(
            "joined",
            lambda: NamedBarrierAfterFinishChannel(frozenset({"pub_a", "pub_b"})),
        )
        .add_node("pub_a", pub_a)
        .add_node("pub_b", pub_b)
        .add_node("reader", reader)
        .add_node("tail", tail)
        .add_edge(START, "pub_a")
        .add_edge(START, "pub_b")
        .add_edge(["pub_a", "pub_b"], "reader")
        .add_edge("reader", "tail")
        .add_edge("tail", END)
        .compile()
    )


def test_ephemeral_channel_visible_exactly_one_step() -> None:
    result = _run(_semantics_graph().invoke(input={"log": []}, effects=SimulatedEffects(7)))
    # reader (superstep after the write) sees it; tail (one more) does not.
    assert result.state["seen"][0] == 5
    assert result.state["late"][0] is False
    assert "eph" not in result.state


def test_ephemeral_channel_resets_to_declared_default() -> None:
    state = GraphState({"e": lambda: EphemeralChannel(default=0)})
    state.apply_writes(_writes("e", ("a", 9)), 1)
    assert state.snapshot()["e"] == 9
    state.apply_writes([], 2)  # a barrier that wrote nothing to it
    assert state.snapshot()["e"] == 0
    # Clearing is not a new value: the version must not advance on a reset.
    assert state.versions["e"] == 1


def test_ephemeral_channel_rejects_concurrent_writes_when_guarded() -> None:
    state = GraphState({"e": lambda: EphemeralChannel()})
    with pytest.raises(ChannelWriteConflictError):
        state.apply_writes(_writes("e", ("a", 1), ("b", 2)), 1)
    unguarded = GraphState({"e": lambda: EphemeralChannel(guard=False)})
    unguarded.apply_writes(_writes("e", ("a", 1), ("b", 2)), 1)
    assert unguarded.snapshot()["e"] == 2


def test_any_value_channel_accepts_concurrent_writes_without_conflict() -> None:
    result = _run(_semantics_graph().invoke(input={"log": []}, effects=SimulatedEffects(7)))
    # Two same-superstep writers, no conflict, one committed value.
    assert result.state["seen"][1] == 7
    # Like langgraph AnyValue it is step-scoped: nobody rewrote it after the
    # publishers, so it is gone by the time tail runs.
    assert result.state["late"][1] is False


def test_untracked_value_channel_user_visible_but_never_checkpointed() -> None:
    result = _run(_semantics_graph().invoke(input={"log": []}, effects=SimulatedEffects(7)))
    assert result.state["untracked"] == 11
    state = GraphState({"u": lambda: UntrackedValueChannel()})
    state.apply_writes(_writes("u", ("a", 11)), 1)
    snapshot = state.checkpoint_channels()["u"]
    assert snapshot == {"version": 1, "untracked": True}
    assert state.snapshot()["u"] == 11
    assert "u" not in state.tracked_snapshot()


def test_untracked_value_channel_resume_digest_integrity() -> None:
    factories = {"u": lambda: UntrackedValueChannel(), "x": LastValueChannel}
    origin = GraphState(factories)
    origin.apply_writes(
        [ChannelWrite("a", "u", 11), ChannelWrite("a", "x", 2)], 1
    )
    rebuilt = GraphState(factories)
    rebuilt.restore_channels(origin.checkpoint_channels())
    # The value is gone after restore, so it must never have been in the
    # digest — otherwise every resume would fail its integrity check.
    assert rebuilt.digest() == origin.digest()
    assert "u" not in rebuilt.snapshot()


def test_delta_channel_folds_each_write_batch_in_canonical_order() -> None:
    calls: list[tuple[Any, list[Any]]] = []

    def reducer(current: Any, updates: Any) -> Any:
        batch = list(updates)
        calls.append((list(current), batch))
        return list(current) + batch

    state = GraphState({"d": lambda: DeltaChannel(reducer, [])})
    state.apply_writes(_writes("d", ("a", 1), ("b", 2)), 1)
    state.apply_writes(_writes("d", ("a", 3)), 2)
    assert state.snapshot()["d"] == [1, 2, 3]
    # Each barrier hands the WHOLE batch to the reducer in one call (not a
    # binary fold) — that is the DeltaChannel contract. Every barrier folds
    # twice: once staged on a deep copy in validate (all-or-nothing), once
    # for real in commit.
    assert calls == [([], [1, 2]), ([], [1, 2]), ([1, 2], [3]), ([1, 2], [3])]


def test_delta_channel_checkpoint_round_trips_reduced_value() -> None:
    factory = lambda: DeltaChannel(  # noqa: E731 - factory must be zero-arg
        lambda current, updates: list(current) + list(updates), []
    )
    origin = GraphState({"d": factory})
    origin.apply_writes(_writes("d", ("a", 1), ("b", 2)), 1)
    rebuilt = GraphState({"d": factory})
    rebuilt.restore_channels(origin.checkpoint_channels())
    assert rebuilt.snapshot() == origin.snapshot()
    assert rebuilt.digest() == origin.digest()


def test_last_value_after_finish_available_only_at_quiescence() -> None:
    result = _run(_semantics_graph().invoke(input={"log": []}, effects=SimulatedEffects(7)))
    # Hidden while the run is live (reader probed it), published at the end.
    assert result.state["seen"][2] is False
    assert result.state["afterfinish"] == 21
    channel = LastValueAfterFinishChannel()
    channel.name = "afterfinish"
    assert channel.finish() is False  # nothing held yet
    channel.commit(_writes("afterfinish", ("a", 1)), 1)
    with pytest.raises(EmptyChannelError):
        channel.get()
    assert channel.finish() is True
    assert channel.get() == 1


def test_named_barrier_after_finish_available_only_at_quiescence() -> None:
    result = _run(_semantics_graph().invoke(input={"log": []}, effects=SimulatedEffects(7)))
    assert result.state["seen"][3] is False
    assert result.state["joined"] is None
    channel = NamedBarrierAfterFinishChannel(frozenset({"m1", "m2"}))
    channel.name = "joined"
    channel.commit(_writes("joined", ("m1", "m1")), 1)
    assert channel.finish() is False  # incomplete barrier never publishes
    channel.commit(_writes("joined", ("m2", "m2")), 2)
    assert channel.is_empty is True
    assert channel.finish() is True
    assert channel.get() is None


def test_named_barrier_after_finish_rejects_stray_writer() -> None:
    state = GraphState(
        {"joined": lambda: NamedBarrierAfterFinishChannel(frozenset({"m1", "m2"}))}
    )
    with pytest.raises(BarrierMemberError):
        state.apply_writes(_writes("joined", ("m9", "m9")), 1)
    assert state.snapshot() == {}


def test_after_finish_channels_survive_checkpoint_resume() -> None:
    factories = {
        "afterfinish": LastValueAfterFinishChannel,
        "joined": lambda: NamedBarrierAfterFinishChannel(frozenset({"m1"})),
    }
    origin = GraphState(factories)
    origin.apply_writes(
        [ChannelWrite("m1", "afterfinish", 3), ChannelWrite("m1", "joined", "m1")],
        1,
    )
    assert origin.finish_all() == frozenset({"afterfinish", "joined"})
    rebuilt = GraphState(factories)
    rebuilt.restore_channels(origin.checkpoint_channels())
    assert rebuilt.snapshot() == origin.snapshot()
    assert rebuilt.digest() == origin.digest()


def test_finish_runs_once_and_a_later_write_unpublishes() -> None:
    state = GraphState({"afterfinish": LastValueAfterFinishChannel})
    state.apply_writes(_writes("afterfinish", ("a", 1)), 1)
    assert state.finish_all() == frozenset({"afterfinish"})
    assert state.finish_all() == frozenset()  # idempotent
    state.apply_writes(_writes("afterfinish", ("a", 2)), 2)
    assert "afterfinish" not in state.snapshot()
    assert state.finish_all() == frozenset({"afterfinish"})
    assert state.snapshot()["afterfinish"] == 2
