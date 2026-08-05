"""LG20 — dynamic HITL interrupt aggregation and per-interrupt-id resume.

Engine pins for the multi-interrupt behaviour the LG20 gauntlet workload
measures against langgraph 1.2.4. The reference semantics recorded here were
re-derived empirically against the installed langgraph 1.2.4 on 2026-08-05
(two sibling nodes each calling ``interrupt()`` in one superstep):

- both interrupts surface from ONE run; neither task's writes commit;
- ``Command(resume={id: value})`` resolves them individually by id;
- resolving a SUBSET is legal: the unresolved interrupt re-surfaces with its
  id unchanged and its task stays suspended;
- a bare ``Command(resume=value)`` is rejected while several are pending
  (langgraph raises RuntimeError: "When there are multiple pending
  interrupts, you must specify the interrupt id when resuming");
- every interrupted node re-executes FROM THE TOP on each resume.

The surfaced ORDER is canonical ``(node_id, task_seq)``, deliberately not
``effects.dispatch_order`` — the interrupt set a caller sees must not depend
on which seed shuffled this superstep's task starts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from dharma_swarm.graph.channels import AppendChannel
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.errors import GraphRuntimeError
from dharma_swarm.graph.interrupts import (
    GraphInterrupted,
    interrupt,
    interrupt_id,
)
from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.routing import Command, Send
from dharma_swarm.graph.types import END, START


def _pair_graph(calls: dict[str, int]):
    """Two sibling nodes, each suspending once on its own interrupt."""

    def left(state: Mapping[str, Any]) -> dict[str, Any]:
        calls["left"] += 1
        return {"log": [f"left={interrupt({'ask': 'left'})}"]}

    def right(state: Mapping[str, Any]) -> dict[str, Any]:
        calls["right"] += 1
        return {"log": [f"right={interrupt({'ask': 'right'})}"]}

    return (
        GraphBuilder("dynamic-interrupt")
        .add_channel("log", AppendChannel)
        .add_node("left", left)
        .add_node("right", right)
        .add_edge(START, "left")
        .add_edge(START, "right")
        .add_edge("left", END)
        .add_edge("right", END)
        .compile()
    )


async def _suspend(compiled, kernel, thread: str, seed: int = 7):
    """Seed a run expected to suspend; return the raised GraphInterrupted."""
    with pytest.raises(GraphInterrupted) as caught:
        await compiled.invoke(
            input={"log": []},
            effects=SimulatedEffects(seed),
            graph_run_id=thread,
            persistence=kernel,
            thread_id=thread,
        )
    return caught.value


async def _resume(compiled, kernel, thread: str, payload: Any, seed: int = 7):
    return await compiled.invoke(
        input=Command(resume=payload),
        effects=SimulatedEffects(seed),
        persistence=kernel,
        thread_id=thread,
    )


async def test_all_step_interrupts_surface_on_one_error(tmp_path):
    """Both suspended tasks ride ONE GraphInterrupted, not just the first."""
    calls = {"left": 0, "right": 0}
    compiled = _pair_graph(calls)
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")

    suspended = await _suspend(compiled, kernel, "both")

    assert len(suspended.suspended) == 2
    assert len(suspended.interrupts) == 2
    assert [record.node_id for record in suspended.suspended] == ["left", "right"]
    assert [item.value["ask"] for item in suspended.interrupts] == ["left", "right"]
    # Each task owns a distinct id and an empty resume history so far.
    assert len({item.id for item in suspended.interrupts}) == 2
    assert all(record.consumed_resumes == () for record in suspended.suspended)
    # Neither task committed, and each ran exactly once.
    assert calls == {"left": 1, "right": 1}


async def test_interrupt_order_is_canonical_not_dispatch_order(tmp_path):
    """The surfaced order is seed-invariant: canonical (node_id, task_seq).

    ``SimulatedEffects`` permutes task start order per seed, so if interrupts
    were collected in dispatch order some seed would reorder them.
    """
    orders: set[tuple[str, ...]] = set()
    payloads: set[tuple[str, ...]] = set()
    for seed in (1, 2, 3, 7, 11, 42, 99):
        calls = {"left": 0, "right": 0}
        compiled = _pair_graph(calls)
        kernel = GraphPersistenceKernel(Path(tmp_path) / f"kernel-{seed}")
        suspended = await _suspend(compiled, kernel, f"order-{seed}", seed=seed)
        orders.add(tuple(r.node_id for r in suspended.suspended))
        payloads.add(tuple(i.value["ask"] for i in suspended.interrupts))

    assert orders == {("left", "right")}
    assert payloads == {("left", "right")}


async def test_resume_by_interrupt_id_resolves_every_pending_interrupt(tmp_path):
    """One Command(resume={id: value}) answers both interrupts and commits."""
    calls = {"left": 0, "right": 0}
    compiled = _pair_graph(calls)
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")

    suspended = await _suspend(compiled, kernel, "by-id")
    answers = {
        item.id: f"ANS-{item.value['ask']}" for item in suspended.interrupts
    }
    final = await _resume(compiled, kernel, "by-id", answers)

    assert list(final.state["log"]) == ["left=ANS-left", "right=ANS-right"]
    # Both nodes re-executed from the top exactly once more (node_reexecution).
    assert calls == {"left": 2, "right": 2}


async def test_partial_resume_holds_the_unanswered_interrupt(tmp_path):
    """Answering one id leaves the other pending under its original id."""
    calls = {"left": 0, "right": 0}
    compiled = _pair_graph(calls)
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")

    opened = await _suspend(compiled, kernel, "partial")
    left_id, right_id = (item.id for item in opened.interrupts)

    with pytest.raises(GraphInterrupted) as caught:
        await _resume(compiled, kernel, "partial", {left_id: "ONLY-LEFT"})
    held = caught.value

    # Only the unanswered interrupt remains, and its id is stable.
    assert [item.id for item in held.interrupts] == [right_id]
    assert [item.value["ask"] for item in held.interrupts] == ["right"]

    # The answered task's value is not lost: finishing the second interrupt
    # commits BOTH writes, so the first answer survived in the pending record.
    final = await _resume(compiled, kernel, "partial", {right_id: "THEN-RIGHT"})
    assert list(final.state["log"]) == ["left=ONLY-LEFT", "right=THEN-RIGHT"]
    # 'left' never re-executed after it succeeded; only 'right' re-ran.
    assert calls == {"left": 2, "right": 3}


async def test_bare_resume_rejected_while_several_interrupts_pending(tmp_path):
    """A value with no id is ambiguous against 2 pending interrupts."""
    calls = {"left": 0, "right": 0}
    compiled = _pair_graph(calls)
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")

    await _suspend(compiled, kernel, "bare")

    with pytest.raises(GraphRuntimeError, match="interrupts are pending"):
        await _resume(compiled, kernel, "bare", "AMBIGUOUS")


async def test_partially_recognised_resume_map_fails_closed(tmp_path):
    """A map mixing a real id with an unknown key never half-applies."""
    calls = {"left": 0, "right": 0}
    compiled = _pair_graph(calls)
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")

    opened = await _suspend(compiled, kernel, "mixed")
    known = opened.interrupts[0].id

    with pytest.raises(GraphRuntimeError, match="unrecognised keys"):
        await _resume(
            compiled, kernel, "mixed", {known: "OK", "not-an-id": "BAD"}
        )


async def test_single_interrupt_still_accepts_a_bare_resume_value(tmp_path):
    """LG08 regression pin: one pending interrupt needs no id, and a dict
    payload stays usable as an ordinary resume VALUE."""

    def ask(state: Mapping[str, Any]) -> dict[str, Any]:
        answer = interrupt({"ask": "approve?"})
        return {"log": [f"ask={answer['approved']}"]}

    compiled = (
        GraphBuilder("single-interrupt")
        .add_channel("log", AppendChannel)
        .add_node("ask", ask)
        .add_edge(START, "ask")
        .add_edge("ask", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")

    suspended = await _suspend(compiled, kernel, "single")
    assert len(suspended.interrupts) == 1
    # Back-compat scalars on the error still describe the one suspended task.
    assert suspended.node_id == "ask"
    assert suspended.task_seq == 0

    final = await _resume(compiled, kernel, "single", {"approved": True})
    assert list(final.state["log"]) == ["ask=True"]


async def test_send_packets_to_one_node_are_independent_interrupts(tmp_path):
    """N Send packets into one interrupting node yield N addressable ids."""

    def fan(state: Mapping[str, Any]) -> Any:
        return [Send("worker", {"i": index}) for index in state["items"]]

    def worker(arg: Mapping[str, Any]) -> dict[str, Any]:
        return {"log": [f"w{arg['i']}={interrupt({'ask': arg['i']})}"]}

    compiled = (
        GraphBuilder("send-interrupt")
        .add_channel("items", AppendChannel)
        .add_channel("log", AppendChannel)
        .add_node("worker", worker)
        .add_conditional_edges(START, fan, {"worker": "worker"})
        .add_edge("worker", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(Path(tmp_path) / "kernel")
    thread = "sends"

    with pytest.raises(GraphInterrupted) as caught:
        await compiled.invoke(
            input={"items": [0, 1], "log": []},
            effects=SimulatedEffects(7),
            graph_run_id=thread,
            persistence=kernel,
            thread_id=thread,
        )
    suspended = caught.value

    # One interrupt per PACKET, ordered by task_seq, each with its own id.
    assert [(r.node_id, r.task_seq) for r in suspended.suspended] == [
        ("worker", 1),
        ("worker", 2),
    ]
    assert len({item.id for item in suspended.interrupts}) == 2
    # Ids are the pure function of task identity the scheduler recomputes.
    assert [item.id for item in suspended.interrupts] == [
        interrupt_id(thread, "worker", 1),
        interrupt_id(thread, "worker", 2),
    ]

    answers = {
        item.id: f"a{item.value['ask']}" for item in suspended.interrupts
    }
    final = await _resume(compiled, kernel, thread, answers)
    assert sorted(final.state["log"]) == ["w0=a0", "w1=a1"]
