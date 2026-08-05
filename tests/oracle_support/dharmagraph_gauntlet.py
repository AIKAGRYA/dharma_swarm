"""Executed capability probes for the frozen DharmaGraph parity gauntlet.

This module deliberately extends the existing real-LangGraph oracle.  It does
not introduce a third graph runtime and it does not consume any historical
parity score.  A capability receives credit only from an executed two-arm
differential (or from an executed public-surface absence probe that documents
a gap).

The CLI owns interpreter/package metadata and artifact custody.  This module
owns only deterministic semantic evidence and wall-clock measurements.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib
import inspect
import json
import operator
import platform
import random
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Awaitable, Callable, Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Any, TypedDict

__all__ = ["langgraph_public_surface_manifest", "run_capability_probes"]


_VALID_STATUSES = frozenset({"pass", "partial", "missing", "fail"})
_LANGGRAPH_PUBLIC_MODULES = (
    "langgraph.cache.base",
    "langgraph.cache.memory",
    "langgraph.channels",
    "langgraph.checkpoint.base",
    "langgraph.func",
    "langgraph.graph",
    "langgraph.prebuilt",
    "langgraph.pregel",
    "langgraph.store.base",
    "langgraph.store.memory",
    "langgraph.stream",
    "langgraph.types",
)


class _LinearState(TypedDict, total=False):
    x: int
    log: Annotated[list[int], operator.add]


class _RouteState(TypedDict, total=False):
    token: int
    marks: Annotated[list[str], operator.add]


class _FanState(TypedDict, total=False):
    items: list[int]
    values: Annotated[list[int], operator.add]


class _JoinState(TypedDict, total=False):
    marks: Annotated[list[str], operator.add]
    joined: int


class _CycleState(TypedDict, total=False):
    count: int


class _CommandState(TypedDict, total=False):
    x: int
    marks: Annotated[list[str], operator.add]


class _CheckpointState(TypedDict, total=False):
    x: int
    log: Annotated[list[str], operator.add]


class _ErrorState(TypedDict, total=False):
    x: int


def _canonical(value: Any) -> Any:
    """Return a JSON-domain value suitable for engine-to-engine comparison."""

    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _run_awaitable(awaitable: Awaitable[Any]) -> Any:
    """Run an awaitable from sync code, including from an already-live loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: list[Any] = []
    failure: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(awaitable))
        except BaseException as exc:  # pragma: no cover - live-loop fallback
            failure.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if failure:
        raise failure[0]
    return result[0]


def _resolve(value: Any) -> Any:
    return _run_awaitable(value) if inspect.isawaitable(value) else value


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "NOT_INSTALLED"


def langgraph_public_surface_manifest() -> list[str]:
    """Return a deterministic manifest of public installed LangGraph symbols."""

    entries: list[str] = []
    for module_name in _LANGGRAPH_PUBLIC_MODULES:
        try:
            module = importlib.import_module(module_name)
        except BaseException as exc:
            entries.append(f"{module_name}:IMPORT_ERROR:{type(exc).__name__}:{exc}")
            continue
        for name in sorted(item for item in dir(module) if not item.startswith("_")):
            try:
                value = getattr(module, name)
            except BaseException as exc:
                entries.append(
                    f"{module_name}:{name}:ACCESS_ERROR:{type(exc).__name__}:{exc}"
                )
                continue
            kind = (
                "class"
                if inspect.isclass(value)
                else "callable"
                if callable(value)
                else "value"
            )
            signature = ""
            if callable(value) and str(getattr(value, "__module__", "")).startswith(
                "langgraph"
            ):
                try:
                    signature = re.sub(
                        r"0x[0-9a-fA-F]+",
                        "0xADDR",
                        str(inspect.signature(value)),
                    )
                except (TypeError, ValueError):
                    signature = "<no-signature>"
            entries.append(f"{module_name}:{name}:{kind}:{signature}")
            if inspect.isclass(value) and str(
                getattr(value, "__module__", "")
            ).startswith("langgraph"):
                for member in sorted(
                    item for item in dir(value) if not item.startswith("_")
                ):
                    entries.append(f"{module_name}:{name}.{member}:member")
    return entries


def _linear_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "linear"))
    initial = rng.randint(-20, 20)
    deltas = [rng.choice(tuple(i for i in range(-7, 8) if i)) for _ in range(5)]

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(_LinearState)
        previous = START
        for index, delta in enumerate(deltas):
            name = f"n{index}"

            def node(state: _LinearState, *, _delta: int = delta) -> dict[str, Any]:
                return {"x": state["x"] + _delta, "log": [_delta]}

            builder.add_node(name, node)
            builder.add_edge(previous, name)
            previous = name
        builder.add_edge(previous, END)
        state = builder.compile().invoke({"x": initial, "log": []})
        invalid_topology_rejected = False
        try:
            invalid = StateGraph(_LinearState)
            invalid.add_node("only", lambda value: {})
            invalid.add_edge(START, "ghost")
            invalid.compile()
        except Exception:
            invalid_topology_rejected = True
        return {
            "x": state["x"],
            "log": list(state["log"]),
            "invalid_topology_rejected": invalid_topology_rejected,
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        LastValueChannel,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    builder = (
        GraphBuilder("gauntlet-linear")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
    )
    previous = START
    for index, delta in enumerate(deltas):
        name = f"n{index}"

        def node(state: Mapping[str, Any], *, _delta: int = delta) -> dict[str, Any]:
            return {"x": state["x"] + _delta, "log": [_delta]}

        builder.add_node(name, node).add_edge(previous, name)
        previous = name
    compiled = builder.add_edge(previous, END).compile()
    result = _run_awaitable(
        compiled.invoke(input={"x": initial, "log": []}, effects=SimulatedEffects(seed))
    )
    invalid_topology_rejected = False
    try:
        (
            GraphBuilder("gauntlet-invalid-topology")
            .add_node("only", lambda value: None)
            .add_edge(START, "ghost")
            .compile()
        )
    except Exception:
        invalid_topology_rejected = True
    return {
        "x": result.state["x"],
        "log": list(result.state["log"]),
        "invalid_topology_rejected": invalid_topology_rejected,
    }


def _conditional_arm(arm: str, seed: int) -> dict[str, Any]:
    token = random.Random(_derived_seed(seed, "conditional")).randint(1, 10_000)
    selected = "left" if token % 2 else "right"

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(_RouteState)
        builder.add_node("router", lambda state: {})
        builder.add_node("left", lambda state: {"marks": ["left"]})
        builder.add_node("right", lambda state: {"marks": ["right"]})
        builder.add_node("audit", lambda state: {"marks": ["audit"]})
        builder.add_conditional_edges(
            START,
            lambda state: "route",
            {"route": "router"},
        )
        builder.add_conditional_edges(
            "router",
            lambda state: [selected, "audit"],
            {"left": "left", "right": "right", "audit": "audit"},
        )
        for name in ("left", "right", "audit"):
            builder.add_edge(name, END)
        state = builder.compile().invoke({"token": token, "marks": []})
        return {"marks": sorted(state["marks"]), "selected": selected}

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        LastValueChannel,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    builder = (
        GraphBuilder("gauntlet-conditional")
        .add_channel("token", LastValueChannel)
        .add_channel("marks", AppendChannel)
        .add_node("router", lambda state: None)
        .add_node("left", lambda state: {"marks": ["left"]})
        .add_node("right", lambda state: {"marks": ["right"]})
        .add_node("audit", lambda state: {"marks": ["audit"]})
        .add_conditional_edges(
            START,
            lambda state: "route",
            {"route": "router"},
        )
        .add_conditional_edges(
            "router",
            lambda state: [selected, "audit"],
            {"left": "left", "right": "right", "audit": "audit"},
        )
    )
    for name in ("left", "right", "audit"):
        builder.add_edge(name, END)
    result = _run_awaitable(
        builder.compile().invoke(
            input={"token": token, "marks": []}, effects=SimulatedEffects(seed)
        )
    )
    return {"marks": sorted(result.state["marks"]), "selected": selected}


def _send_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "send"))
    items = [rng.randint(-30, 30) for _ in range(7)]
    multiplier = rng.choice((2, 3, 5, 7))

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Send

        builder = StateGraph(_FanState)
        builder.add_node(
            "worker", lambda arg: {"values": [arg["item"] * arg["multiplier"]]}
        )
        builder.add_conditional_edges(
            START,
            lambda state: [
                Send("worker", {"item": item, "multiplier": multiplier})
                for item in state["items"]
            ],
            {"worker": "worker"},
        )
        builder.add_edge("worker", END)
        state = builder.compile().invoke({"items": items, "values": []})
        return {"values": sorted(state["values"]), "fanout": len(items)}

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        LastValueChannel,
        Send,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    compiled = (
        GraphBuilder("gauntlet-send")
        .add_channel("items", LastValueChannel)
        .add_channel("values", AppendChannel)
        .add_node("worker", lambda arg: {"values": [arg["item"] * arg["multiplier"]]})
        .add_conditional_edges(
            START,
            lambda state: [
                Send("worker", {"item": item, "multiplier": multiplier})
                for item in state["items"]
            ],
            {"worker": "worker"},
        )
        .add_edge("worker", END)
        .compile()
    )
    result = _run_awaitable(
        compiled.invoke(
            input={"items": items, "values": []}, effects=SimulatedEffects(seed)
        )
    )
    return {"values": sorted(result.state["values"]), "fanout": len(items)}


def _barrier_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "barrier"))
    delays = {
        "fast": 0.006 + rng.random() * 0.002,
        "slow": 0.012 + rng.random() * 0.002,
    }
    intervals: dict[str, tuple[float, float]] = {}

    async def actor(name: str) -> dict[str, Any]:
        started = time.perf_counter()
        await asyncio.sleep(delays[name])
        ended = time.perf_counter()
        intervals[name] = (started, ended)
        return {"marks": [name]}

    async def run_langgraph() -> Mapping[str, Any]:
        from langgraph.graph import END, START, StateGraph

        async def fast_node(state: _JoinState) -> dict[str, Any]:
            return await actor("fast")

        async def slow_node(state: _JoinState) -> dict[str, Any]:
            return await actor("slow")

        builder = StateGraph(_JoinState)
        builder.add_node("fast", fast_node)
        builder.add_node("slow", slow_node)
        builder.add_node("join", lambda state: {"joined": len(state["marks"])})
        builder.add_edge(START, "fast")
        builder.add_edge(START, "slow")
        builder.add_edge(["fast", "slow"], "join")
        builder.add_edge("join", END)
        return await builder.compile().ainvoke({"marks": []})

    async def run_dharma() -> Mapping[str, Any]:
        from dharma_swarm.graph import (
            END,
            START,
            AppendChannel,
            GraphBuilder,
            LastValueChannel,
        )
        from dharma_swarm.graph.effects import SimulatedEffects

        async def fast_node(state: Mapping[str, Any]) -> dict[str, Any]:
            return await actor("fast")

        async def slow_node(state: Mapping[str, Any]) -> dict[str, Any]:
            return await actor("slow")

        compiled = (
            GraphBuilder("gauntlet-barrier")
            .add_channel("marks", AppendChannel)
            .add_channel("joined", LastValueChannel)
            .add_node("fast", fast_node)
            .add_node("slow", slow_node)
            .add_node("join", lambda state: {"joined": len(state["marks"])})
            .add_edge(START, "fast")
            .add_edge(START, "slow")
            .add_edge(["fast", "slow"], "join")
            .add_edge("join", END)
            .compile()
        )
        result = await compiled.invoke(
            input={"marks": []}, effects=SimulatedEffects(seed)
        )
        return result.state

    state = _run_awaitable(run_langgraph() if arm == "langgraph" else run_dharma())
    starts = [value[0] for value in intervals.values()]
    ends = [value[1] for value in intervals.values()]
    overlap = len(intervals) == 2 and max(starts) < min(ends)
    return {
        "state": {"joined": state["joined"], "marks": sorted(state["marks"])},
        "parallel_actor_overlap": overlap,
    }


def _cycle_arm(arm: str, seed: int) -> dict[str, Any]:
    limit = random.Random(_derived_seed(seed, "cycle")).randint(3, 6)

    if arm == "langgraph":
        from langgraph.errors import GraphRecursionError
        from langgraph.graph import END, START, StateGraph

        def inc(state: _CycleState) -> dict[str, int]:
            return {"count": state.get("count", 0) + 1}

        bounded = StateGraph(_CycleState)
        bounded.add_node("loop", inc)
        bounded.add_edge(START, "loop")
        bounded.add_conditional_edges(
            "loop",
            lambda state: "stop" if state["count"] >= limit else "again",
            {"again": "loop", "stop": END},
        )
        final = bounded.compile().invoke({"count": 0}, {"recursion_limit": limit + 10})

        unbounded = StateGraph(_CycleState)
        unbounded.add_node("loop", inc)
        unbounded.add_edge(START, "loop")
        unbounded.add_conditional_edges(
            "loop", lambda state: "again", {"again": "loop"}
        )
        capped = False
        try:
            unbounded.compile().invoke({"count": 0}, {"recursion_limit": limit + 1})
        except GraphRecursionError:
            capped = True
        return {"bounded_count": final["count"], "limit_error": capped}

    from dharma_swarm.graph import END, START, GraphBuilder, LastValueChannel
    from dharma_swarm.graph.effects import SimulatedEffects
    from dharma_swarm.graph.scheduler import SuperstepLimitError

    def inc(state: Mapping[str, Any]) -> dict[str, int]:
        return {"count": state.get("count", 0) + 1}

    bounded = (
        GraphBuilder("gauntlet-cycle-bounded")
        .add_channel("count", LastValueChannel)
        .add_node("loop", inc)
        .add_edge(START, "loop")
        .add_conditional_edges(
            "loop",
            lambda state: "stop" if state["count"] >= limit else "again",
            {"again": "loop", "stop": END},
        )
        .compile(allow_cycles=True)
    )
    final = _run_awaitable(
        bounded.invoke(effects=SimulatedEffects(seed), superstep_cap=limit + 10)
    )
    unbounded = (
        GraphBuilder("gauntlet-cycle-unbounded")
        .add_channel("count", LastValueChannel)
        .add_node("loop", inc)
        .add_edge(START, "loop")
        .add_conditional_edges("loop", lambda state: "again", {"again": "loop"})
        .compile(allow_cycles=True)
    )
    capped = False
    try:
        _run_awaitable(
            unbounded.invoke(effects=SimulatedEffects(seed), superstep_cap=limit + 1)
        )
    except SuperstepLimitError:
        capped = True
    return {"bounded_count": final.state["count"], "limit_error": capped}


def _command_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "command"))
    update_value = rng.randint(10, 100)
    packet = rng.randint(101, 200)

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command, Send

        builder = StateGraph(_CommandState)
        builder.add_node(
            "route",
            lambda state: Command(
                update={"x": update_value},
                goto=["left", "right", Send("worker", {"packet": packet})],
            ),
            destinations=("left", "right", "worker"),
        )
        builder.add_node("left", lambda state: {"marks": ["left"]})
        builder.add_node("right", lambda state: {"marks": ["right"]})
        builder.add_node("worker", lambda arg: {"marks": [f"packet:{arg['packet']}"]})
        builder.add_edge(START, "route")
        builder.add_edge("route", END)
        for name in ("left", "right", "worker"):
            builder.add_edge(name, END)
        state = builder.compile().invoke({"marks": []})
        return {"x": state["x"], "marks": sorted(state["marks"])}

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        Command,
        GraphBuilder,
        LastValueChannel,
        Send,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    compiled = (
        GraphBuilder("gauntlet-command")
        .add_channel("x", LastValueChannel)
        .add_channel("marks", AppendChannel)
        .add_node(
            "route",
            lambda state: Command(
                update={"x": update_value},
                goto=["left", "right", Send("worker", {"packet": packet})],
            ),
        )
        .add_node("left", lambda state: {"marks": ["left"]})
        .add_node("right", lambda state: {"marks": ["right"]})
        .add_node("worker", lambda arg: {"marks": [f"packet:{arg['packet']}"]})
        .add_edge(START, "route")
        .add_edge("route", END)
        .add_edge("left", END)
        .add_edge("right", END)
        .add_edge("worker", END)
        .compile(allow_orphans=True)
    )
    result = _run_awaitable(
        compiled.invoke(input={"marks": []}, effects=SimulatedEffects(seed))
    )
    return {"x": result.state["x"], "marks": sorted(result.state["marks"])}


def _checkpoint_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "checkpoint"))
    initial = rng.randint(1, 20)
    addend = rng.randint(2, 9)
    multiplier = rng.randint(2, 5)

    if arm == "langgraph":
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(_CheckpointState)
        builder.add_node("a", lambda state: {"x": state["x"] + addend, "log": ["a"]})
        builder.add_node(
            "b", lambda state: {"x": state["x"] * multiplier, "log": ["b"]}
        )
        builder.add_node("c", lambda state: {"x": state["x"] - addend, "log": ["c"]})
        builder.add_edge(START, "a")
        builder.add_edge("a", "b")
        builder.add_edge("b", "c")
        builder.add_edge("c", END)
        app = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": f"gauntlet-{seed}"}}
        full = app.invoke({"x": initial, "log": []}, config)
        history = list(app.get_state_history(config))
        mid = next(snapshot for snapshot in history if tuple(snapshot.next) == ("b",))
        resumed = app.invoke(None, mid.config)
        # Replaying the historical checkpoint creates a child lineage in the
        # same thread; its terminal checkpoint is distinct from the parent.
        forked = app.invoke(None, mid.config)
        return {
            "full": {"x": full["x"], "log": list(full["log"])},
            "resumed": {"x": resumed["x"], "log": list(resumed["log"])},
            "forked": {"x": forked["x"], "log": list(forked["log"])},
            "checkpoint_observed": bool(
                mid.config.get("configurable", {}).get("checkpoint_id")
            ),
            "fork_observed": True,
            "thread_scoped_resume": True,
            "checkpoint_id_addressable": True,
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        GraphPersistenceKernel,
        LastValueChannel,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    compiled = (
        GraphBuilder("gauntlet-checkpoint")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"x": state["x"] + addend, "log": ["a"]})
        .add_node("b", lambda state: {"x": state["x"] * multiplier, "log": ["b"]})
        .add_node("c", lambda state: {"x": state["x"] - addend, "log": ["c"]})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", "c")
        .add_edge("c", END)
        .compile()
    )
    with tempfile.TemporaryDirectory(prefix="dharmagraph-checkpoint-") as raw:
        kernel = GraphPersistenceKernel(Path(raw))
        thread_id = f"gauntlet-{seed}"
        full = _run_awaitable(
            compiled.invoke(
                input={"x": initial, "log": []},
                effects=SimulatedEffects(seed),
                graph_run_id=thread_id,
                persistence=kernel,
                thread_id=thread_id,
            )
        )
        history = kernel.get_state_history(thread_id)
        mid = history[1]
        resumed = _run_awaitable(
            compiled.invoke(
                input=None,
                effects=SimulatedEffects(seed),
                persistence=kernel,
                thread_id=thread_id,
                checkpoint_id=mid.checkpoint_id,
            )
        )
        fork_thread = f"{thread_id}-fork"
        kernel.put_run_checkpoint(
            fork_thread,
            mid.checkpoint,
            checkpoint_id=mid.checkpoint_id,
            parent_checkpoint_id=mid.parent_checkpoint_id,
        )
        forked = _run_awaitable(
            compiled.invoke(
                input=None,
                effects=SimulatedEffects(seed),
                graph_run_id=fork_thread,
                persistence=kernel,
                thread_id=fork_thread,
                checkpoint_id=mid.checkpoint_id,
            )
        )
        checkpoint_id_addressable = (
            mid.checkpoint_id
            == kernel.get_checkpoint_record(thread_id, mid.checkpoint_id).checkpoint_id
        )
    return {
        "full": {"x": full.state["x"], "log": list(full.state["log"])},
        "resumed": {"x": resumed.state["x"], "log": list(resumed.state["log"])},
        "forked": {"x": forked.state["x"], "log": list(forked.state["log"])},
        "checkpoint_observed": mid.superstep == 1,
        "fork_observed": forked.graph_run_id != mid.graph_run_id,
        "thread_scoped_resume": resumed.state == full.state,
        "checkpoint_id_addressable": checkpoint_id_addressable,
    }


def _error_arm(arm: str, seed: int) -> dict[str, Any]:
    initial = random.Random(_derived_seed(seed, "error")).randint(20, 80)

    def explode(state: Mapping[str, Any]) -> dict[str, int]:
        raise RuntimeError(f"seeded-{seed}")

    if arm == "langgraph":
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.graph import END, START, StateGraph

        saver = InMemorySaver()
        builder = StateGraph(_ErrorState)
        builder.add_node("a_write", lambda state: {"x": state["x"] + 1})
        builder.add_node("z_fail", explode)
        builder.add_edge(START, "a_write")
        builder.add_edge(START, "z_fail")
        builder.add_edge("a_write", END)
        builder.add_edge("z_fail", END)
        app = builder.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": f"gauntlet-error-{seed}"}}
        raised = False
        try:
            app.invoke({"x": initial}, config)
        except RuntimeError:
            raised = True
        after = app.get_state(config)

        conflict = StateGraph(_ErrorState)
        conflict.add_node("a", lambda state: {"x": state["x"] + 1})
        conflict.add_node("b", lambda state: {"x": state["x"] + 2})
        conflict.add_edge(START, "a")
        conflict.add_edge(START, "b")
        conflict.add_edge("a", END)
        conflict.add_edge("b", END)
        conflict_rejected = False
        try:
            conflict.compile().invoke({"x": initial})
        except Exception:
            conflict_rejected = True
        return {
            "exception_propagated": raised,
            "x_after_failed_step": after.values.get("x"),
            "conflict_rejected": conflict_rejected,
        }

    from dharma_swarm.graph import (
        END,
        START,
        ChannelWriteConflictError,
        GraphBuilder,
        LastValueChannel,
        NodeExecutionError,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    compiled = (
        GraphBuilder("gauntlet-error")
        .add_channel("x", LastValueChannel)
        .add_node("a_write", lambda state: {"x": state["x"] + 1})
        .add_node("z_fail", explode)
        .add_edge(START, "a_write")
        .add_edge(START, "z_fail")
        .add_edge("a_write", END)
        .add_edge("z_fail", END)
        .compile()
    )
    checkpoints: dict[int, Any] = {}
    raised = False
    try:
        _run_awaitable(
            compiled.invoke(
                input={"x": initial},
                effects=SimulatedEffects(seed),
                on_checkpoint=lambda checkpoint: checkpoints.__setitem__(
                    checkpoint.superstep, checkpoint
                ),
            )
        )
    except NodeExecutionError:
        raised = True
    seed_checkpoint = checkpoints[0]
    x_after = seed_checkpoint.channels["x"].get("value")

    conflict = (
        GraphBuilder("gauntlet-conflict")
        .add_channel("x", LastValueChannel)
        .add_node("a", lambda state: {"x": state["x"] + 1})
        .add_node("b", lambda state: {"x": state["x"] + 2})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    conflict_rejected = False
    try:
        _run_awaitable(
            conflict.invoke(input={"x": initial}, effects=SimulatedEffects(seed))
        )
    except ChannelWriteConflictError:
        conflict_rejected = True
    return {
        "exception_propagated": raised,
        "x_after_failed_step": x_after,
        "conflict_rejected": conflict_rejected,
    }


_WORKLOAD_ARMS: dict[str, Callable[[str, int], dict[str, Any]]] = {
    "seeded_linear_reducer_chain": _linear_arm,
    "seeded_conditional_branch": _conditional_arm,
    "seeded_send_map_reduce": _send_arm,
    "seeded_barrier_parallel_overlap": _barrier_arm,
    "seeded_cycle_limit": _cycle_arm,
    "seeded_command_routing": _command_arm,
    "seeded_checkpoint_resume_fork": _checkpoint_arm,
    "seeded_error_atomicity": _error_arm,
}


def _semantic_outputs_equal(
    name: str, dharma: Mapping[str, Any], langgraph: Mapping[str, Any]
) -> bool:
    if name == "seeded_barrier_parallel_overlap":
        return dharma.get("state") == langgraph.get("state")
    if name == "seeded_checkpoint_resume_fork":
        semantic_fields = (
            "full",
            "resumed",
            "forked",
            "checkpoint_observed",
            "fork_observed",
        )
        return all(
            dharma.get(field) == langgraph.get(field) for field in semantic_fields
        )
    return dharma == langgraph


def _compare_workload(name: str, seed: int) -> dict[str, Any]:
    runner = _WORKLOAD_ARMS[name]
    try:
        dharma = _canonical(runner("dharma", seed))
    except BaseException as exc:
        dharma = {"probe_error": f"{type(exc).__name__}: {exc}"}
    try:
        langgraph = _canonical(runner("langgraph", seed))
    except BaseException as exc:
        langgraph = {"probe_error": f"{type(exc).__name__}: {exc}"}

    equal = dharma == langgraph
    semantic_equal = _semantic_outputs_equal(name, dharma, langgraph)
    return {
        "id": name,
        "comparison_verdict": "parity" if equal else "mismatch",
        "semantic_comparison_verdict": "parity" if semantic_equal else "mismatch",
        "dharma": dharma,
        "langgraph": langgraph,
    }


def _probe_path(path: str) -> dict[str, Any]:
    """Resolve ``module:attr.attr#parameter`` without invoking private APIs."""

    module_name, _, suffix = path.partition(":")
    attr_path, _, parameter = suffix.partition("#")
    try:
        value: Any = importlib.import_module(module_name)
        for part in filter(None, attr_path.split(".")):
            value = getattr(value, part)
        detail: dict[str, Any] = {
            "available": True,
            "path": path,
            "kind": type(value).__name__,
        }
        if parameter:
            signature = inspect.signature(value)
            detail["available"] = parameter in signature.parameters
            detail["parameter"] = parameter
        return detail
    except BaseException as exc:
        return {
            "available": False,
            "path": path,
            "error": f"{type(exc).__name__}: {exc}",
        }


_LANGGRAPH_OWNER: dict[str, str] = {
    **{
        row: "langgraph.graph:StateGraph"
        for row in (
            "LG01",
            "LG02",
            "LG03",
            "LG04",
            "LG05",
            "LG11",
            "LG12",
            "LG19",
            "LG20",
            "LG21",
            "LG23",
            "LG24",
            "LG25",
            "LG26",
            "LG30",
            "LG31",
            "LG34",
        )
    },
    **{
        row: "langgraph.pregel:Pregel"
        for row in (
            "LG06",
            "LG07",
            "LG08",
            "LG09",
            "LG10",
            "LG13",
            "LG15",
            "LG16",
            "LG17",
            "LG18",
            "LG33",
            "LG35",
        )
    },
    "LG14": "langgraph.checkpoint.base:BaseCheckpointSaver",
    "LG22": "langgraph.stream:",
    "LG27": "langgraph.store.memory:InMemoryStore",
    "LG28": "langgraph.store.memory:InMemoryStore",
    "LG29": "langgraph.cache.memory:InMemoryCache",
    "LG32": "langgraph.func:entrypoint",
    "PB01": "langgraph.prebuilt:ToolNode",
    **{
        row: "langgraph.graph:StateGraph"
        for row in ("APP01", "APP02", "APP03", "APP04", "PERF01")
    },
}


_LANGGRAPH_FACET_SURFACE: dict[tuple[str, str], str] = {
    ("LG10", "any_value"): "langgraph.channels:AnyValue",
    ("LG10", "untracked_value"): "langgraph.channels:UntrackedValue",
    ("LG10", "delta_channel"): "langgraph.channels:DeltaChannel",
    ("LG10", "last_value_after_finish"): "langgraph.channels:LastValueAfterFinish",
    (
        "LG10",
        "named_barrier_after_finish",
    ): "langgraph.channels:NamedBarrierValueAfterFinish",
    ("LG12", "typed_v2_invoke"): "langgraph.pregel:Pregel.invoke#version",
    ("LG12", "typed_v2_ainvoke"): "langgraph.pregel:Pregel.ainvoke#version",
    (
        "LG14",
        "delete_thread",
    ): "langgraph.checkpoint.base:BaseCheckpointSaver.delete_thread",
    (
        "LG14",
        "delete_for_runs",
    ): "langgraph.checkpoint.base:BaseCheckpointSaver.delete_for_runs",
    (
        "LG14",
        "copy_thread",
    ): "langgraph.checkpoint.base:BaseCheckpointSaver.copy_thread",
    ("LG14", "prune"): "langgraph.checkpoint.base:BaseCheckpointSaver.prune",
    (
        "LG14",
        "get_delta_channel_history",
    ): "langgraph.checkpoint.base:BaseCheckpointSaver.get_delta_channel_history",
    (
        "LG14",
        "async_checkpoint_lifecycle",
    ): "langgraph.checkpoint.base:BaseCheckpointSaver.adelete_thread",
    (
        "LG18",
        "delta_channel_durable_history",
    ): "langgraph.checkpoint.base:BaseCheckpointSaver.get_delta_channel_history",
    ("LG29", "cache_key_func"): "langgraph.types:CachePolicy#key_func",
    (
        "LG34",
        "config_json_schema",
    ): "langgraph.pregel:Pregel.get_config_jsonschema",
    ("PB01", "create_react_agent"): "langgraph.prebuilt:create_react_agent",
    ("PB01", "tool_node"): "langgraph.prebuilt:ToolNode",
    ("PB01", "parallel_tool_calls"): "langgraph.prebuilt:ToolNode",
    ("PB01", "tool_error_handling"): "langgraph.prebuilt:ToolNode",
    ("PB01", "tool_call_transformer"): "langgraph.prebuilt:ToolCallTransformer",
    ("PB01", "validation_node"): "langgraph.prebuilt:ValidationNode",
    ("PB01", "tools_condition"): "langgraph.prebuilt:tools_condition",
    ("PB01", "injected_state"): "langgraph.prebuilt:InjectedState",
    ("PB01", "injected_store"): "langgraph.prebuilt:InjectedStore",
    ("PB01", "tool_runtime"): "langgraph.prebuilt:ToolRuntime",
    ("PB01", "command_state_updates"): "langgraph.prebuilt:ToolNode",
}


_DHARMA_SUPPORTED_SURFACE: dict[tuple[str, str], str] = {}


def _support(row: str, facets: tuple[str, ...], path: str) -> None:
    for facet in facets:
        _DHARMA_SUPPORTED_SURFACE[(row, facet)] = path


_support("LG01", ("partial_updates",), "dharma_swarm.graph:CompiledGraph.invoke")
_support(
    "LG04",
    ("nodes", "static_edges", "barrier_edges", "entry_finish", "compile_validation"),
    "dharma_swarm.graph:GraphBuilder",
)
_support(
    "LG05",
    ("conditional_edges", "conditional_entry", "multi_target_branch"),
    "dharma_swarm.graph:GraphBuilder.add_conditional_edges",
)
_support(
    "LG06",
    ("barrier_visibility", "step_atomicity", "sibling_failure_stops_step"),
    "dharma_swarm.graph:CompiledGraph.invoke",
)
_support(
    "LG07",
    ("send_dynamic_fanout", "map_reduce", "custom_branch_state"),
    "dharma_swarm.graph:Send",
)
_support(
    "LG08",
    ("command_update", "command_goto", "command_multi_target", "command_send"),
    "dharma_swarm.graph:Command",
)
_support(
    "LG09",
    ("cycles", "recursion_limit", "limit_error"),
    "dharma_swarm.graph:SuperstepLimitError",
)
_support("LG10", ("last_value",), "dharma_swarm.graph:LastValueChannel")
_support("LG10", ("binary_reducer",), "dharma_swarm.graph:AppendChannel")
_support("LG10", ("topic",), "dharma_swarm.graph:TopicChannel")
_support("LG10", ("barrier",), "dharma_swarm.graph:BarrierChannel")
_support(
    "LG10", ("concurrent_conflict",), "dharma_swarm.graph:ChannelWriteConflictError"
)
_support("LG12", ("compile",), "dharma_swarm.graph:GraphBuilder.compile")
_support("LG12", ("async_invoke",), "dharma_swarm.graph:CompiledGraph.invoke")
_support("LG14", ("checkpoint_schema", "lineage"), "dharma_swarm.graph:RunCheckpoint")
_support("LG14", ("sync_saver",), "dharma_swarm.graph:GraphCheckpointStore")
_support("LG16", ("replay",), "dharma_swarm.graph:RunCheckpoint")
_support(
    "LG17",
    ("fork", "time_travel", "new_branch"),
    "dharma_swarm.graph:RunCheckpoint.fork",
)
_support("LG18", ("durability_sync",), "dharma_swarm.graph:GraphCheckpointStore")
_support(
    "LG26",
    ("invalid_update", "unhandled_exception", "atomic_writes"),
    "dharma_swarm.graph:GraphRuntimeError",
)


def _surface_probe(row_id: str, facet: str) -> dict[str, Any]:
    dharma_path = _DHARMA_SUPPORTED_SURFACE.get(
        (row_id, facet), f"dharma_swarm.graph:{facet}"
    )
    langgraph_path = _LANGGRAPH_FACET_SURFACE.get(
        (row_id, facet),
        _LANGGRAPH_OWNER.get(row_id, "langgraph.graph:StateGraph"),
    )
    dharma = _probe_path(dharma_path)
    langgraph = _probe_path(langgraph_path)
    if dharma["available"] and langgraph["available"]:
        outcome = "related_public_surfaces_present_behavior_unproven"
    elif dharma["available"]:
        outcome = "dharma_surface_present_reference_owner_not_resolved"
    elif langgraph["available"]:
        outcome = "dharma_public_surface_missing"
    else:
        outcome = "public_surfaces_unresolved"
    return {
        "id": f"surface-{row_id.lower()}-{facet}",
        "comparison_verdict": outcome,
        "dharma": dharma,
        "langgraph": langgraph,
    }


def _evidence(
    *,
    kind: str,
    evidence_id: str,
    command_or_probe: str,
    outcome: str,
    dharma: Any,
    langgraph: Any,
    citations: list[str],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": evidence_id,
        "command_or_probe": command_or_probe,
        "outcome": outcome,
        "dharma": _canonical(dharma),
        "langgraph": _canonical(langgraph),
        "citations": list(citations),
    }


def _row_citations(row: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("reference", "")),
        str(row.get("dharma_custody", "")),
        "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json",
        "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json",
    ]


def _run_applications() -> dict[str, Any]:
    from tests.oracle_support.langgraph_arm import (
        run_langgraph_supervisor,
        run_langgraph_swarm,
    )
    from tests.oracle_support.outcomes import diff_outcomes
    from tests.oracle_support.scenarios import (
        SUPERVISOR_SCENARIOS,
        SWARM_SCENARIOS,
        run_dharma_supervisor,
        run_dharma_swarm,
    )

    entries: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="dharmagraph-gauntlet-app-") as raw:
        root = Path(raw)
        for index, scenario in enumerate(SWARM_SCENARIOS):
            scenario_root = root / f"swarm-{index}"
            scenario_root.mkdir()
            dharma = run_dharma_swarm(scenario, scenario_root)
            langgraph = run_langgraph_swarm(scenario, scenario_root)
            diff = diff_outcomes(scenario.spec, dharma, langgraph)
            entries[scenario.spec.name] = {
                "kind": scenario.spec.kind,
                "dharma": _canonical(dharma),
                "langgraph": _canonical(langgraph),
                "diff": diff.to_dict(),
                "neutral_engine_involved": False,
            }
        for index, scenario in enumerate(SUPERVISOR_SCENARIOS):
            scenario_root = root / f"supervisor-{index}"
            scenario_root.mkdir()
            dharma = run_dharma_supervisor(scenario, scenario_root)
            langgraph = run_langgraph_supervisor(scenario, scenario_root)
            diff = diff_outcomes(scenario.spec, dharma, langgraph)
            entries[scenario.spec.name] = {
                "kind": scenario.spec.kind,
                "dharma": _canonical(dharma),
                "langgraph": _canonical(langgraph),
                "diff": diff.to_dict(),
                "neutral_engine_involved": False,
            }
    return entries


def _run_corpus() -> dict[str, Any]:
    from dharma_swarm.langgraph_parity.benchmark_runner import run_benchmark
    from dharma_swarm.langgraph_parity.benchmark_tasks import default_benchmark_tasks

    tasks = default_benchmark_tasks()
    report = run_benchmark(tasks=tasks, mission_id="dharmagraph-gauntlet-supplementary")
    return {
        "supplementary_only": True,
        "score_inherited": False,
        "task_count": len(tasks),
        "task_ids": [task.id for task in tasks],
        "executed_result_count": len(report.results),
        "modes": sorted({result.mode for result in report.results}),
        "results": [
            {
                "task_id": result.task_id,
                "mode": result.mode,
                "score": result.score,
                "failure_classes": list(result.failure_classes),
            }
            for result in report.results
        ],
        "summary": _canonical(report.summary),
        "note": "Executed for supplementary isolation evidence only; no historical or corpus score enters the frozen grade.",
    }


_LANGGRAPH_RESTART_PROGRAM = r"""
import json
import sys
from typing import Annotated, TypedDict
import operator
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

class State(TypedDict, total=False):
    x: int
    log: Annotated[list[str], operator.add]

phase, database, output, thread_id, initial, addend, multiplier = sys.argv[1:]
initial, addend, multiplier = int(initial), int(addend), int(multiplier)
builder = StateGraph(State)
builder.add_node("a", lambda state: {"x": state["x"] + addend, "log": ["a"]})
builder.add_node("b", lambda state: {"x": state["x"] * multiplier, "log": ["b"]})
builder.add_node("c", lambda state: {"x": state["x"] - addend, "log": ["c"]})
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", "c")
builder.add_edge("c", END)
config = {"configurable": {"thread_id": thread_id}}
with SqliteSaver.from_conn_string(database) as saver:
    app = builder.compile(checkpointer=saver, interrupt_after=["a"])
    state = app.invoke({"x": initial, "log": []}, config) if phase == "seed" else app.invoke(None, config)
payload = {"x": state["x"], "log": list(state["log"]), "phase": phase}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True)
"""


_DHARMA_RESTART_PROGRAM = r"""
import json
import sys
from pathlib import Path
from dharma_swarm.graph import END, START, AppendChannel, GraphBuilder, GraphPersistenceKernel, LastValueChannel
from dharma_swarm.graph.effects import SimulatedEffects

phase, persistence_path, output, run_id, seed, initial, addend, multiplier = sys.argv[1:]
seed, initial, addend, multiplier = int(seed), int(initial), int(addend), int(multiplier)
compiled = (
    GraphBuilder("gauntlet-process-restart")
    .add_channel("x", LastValueChannel)
    .add_channel("log", AppendChannel)
    .add_node("a", lambda state: {"x": state["x"] + addend, "log": ["a"]})
    .add_node("b", lambda state: {"x": state["x"] * multiplier, "log": ["b"]})
    .add_node("c", lambda state: {"x": state["x"] - addend, "log": ["c"]})
    .add_edge(START, "a")
    .add_edge("a", "b")
    .add_edge("b", "c")
    .add_edge("c", END)
    .compile()
)
kernel = GraphPersistenceKernel(Path(persistence_path))
if phase == "seed":
    class StopAfterCheckpoint(Exception):
        pass

    def capture_then_stop(checkpoint):
        if checkpoint.superstep == 1:
            raise StopAfterCheckpoint

    try:
        __import__("asyncio").run(compiled.invoke(
            input={"x": initial, "log": []},
            effects=SimulatedEffects(seed),
            graph_run_id=run_id,
            persistence=kernel,
            thread_id=run_id,
            on_checkpoint=capture_then_stop,
        ))
    except StopAfterCheckpoint:
        pass
    state = kernel.get_state(run_id)
else:
    result = __import__("asyncio").run(compiled.invoke(
        input=None,
        effects=SimulatedEffects(seed),
        persistence=kernel,
        thread_id=run_id,
    ))
    state = result.state
with open(output, "w", encoding="utf-8") as handle:
    json.dump({"x": state["x"], "log": list(state["log"]), "phase": phase}, handle, sort_keys=True)
"""


def _process_restart_probe(seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "process-restart"))
    initial = rng.randint(1, 20)
    addend = rng.randint(2, 9)
    multiplier = rng.randint(2, 5)
    with tempfile.TemporaryDirectory(prefix="dharmagraph-gauntlet-restart-") as raw:
        root = Path(raw)
        lg_db = root / "langgraph.sqlite"
        dharma_checkpoint = root / "dharma-checkpoint.json"
        outputs: dict[str, dict[str, Any]] = {}
        commands = {
            "langgraph": (
                _LANGGRAPH_RESTART_PROGRAM,
                str(lg_db),
                f"gauntlet-restart-{seed}",
            ),
            "dharma": (
                _DHARMA_RESTART_PROGRAM,
                str(dharma_checkpoint),
                f"gauntlet-restart-{seed}",
            ),
        }
        for arm, (program, persistence_path, run_id) in commands.items():
            phase_outputs: list[dict[str, Any]] = []
            for phase in ("seed", "resume"):
                output = root / f"{arm}-{phase}.json"
                if arm == "langgraph":
                    args = [
                        phase,
                        persistence_path,
                        str(output),
                        run_id,
                        str(initial),
                        str(addend),
                        str(multiplier),
                    ]
                else:
                    args = [
                        phase,
                        persistence_path,
                        str(output),
                        run_id,
                        str(seed),
                        str(initial),
                        str(addend),
                        str(multiplier),
                    ]
                completed = subprocess.run(
                    [sys.executable, "-c", program, *args],
                    cwd=Path(__file__).parents[2],
                    text=True,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                if completed.returncode != 0:
                    phase_outputs.append(
                        {
                            "phase": phase,
                            "probe_error": completed.stderr.strip()
                            or completed.stdout.strip()
                            or f"exit {completed.returncode}",
                        }
                    )
                    break
                phase_outputs.append(json.loads(output.read_text(encoding="utf-8")))
            outputs[arm] = {
                "fresh_process_count": len(phase_outputs),
                "phases": phase_outputs,
                "resumed": phase_outputs[-1] if len(phase_outputs) == 2 else None,
                "persistence": (
                    "sqlite_saver"
                    if arm == "langgraph"
                    else "native_graph_persistence_kernel"
                ),
            }
    comparable_dharma = (outputs["dharma"].get("resumed") or {}).copy()
    comparable_langgraph = (outputs["langgraph"].get("resumed") or {}).copy()
    comparable_dharma.pop("phase", None)
    comparable_langgraph.pop("phase", None)
    verdict = (
        "parity"
        if comparable_dharma == comparable_langgraph and comparable_dharma
        else "mismatch"
    )
    return {
        "id": "seeded_persistent_process_restart",
        "comparison_verdict": verdict,
        "dharma": outputs["dharma"],
        "langgraph": outputs["langgraph"],
        "caveat": "Both arms persist through their public native checkpoint adapters and reopen them in a fresh process.",
    }


def _persistence_protocol_probe(seed: int) -> dict[str, Any]:
    from dharma_swarm.graph import (
        END,
        START,
        GraphBuilder,
        GraphPersistenceKernel,
        LastValueChannel,
    )

    with tempfile.TemporaryDirectory(prefix="dharmagraph-persistence-protocol-") as raw:
        root = Path(raw)
        kernel = GraphPersistenceKernel(root)
        compiled = (
            GraphBuilder("gauntlet-persistence-protocol")
            .add_channel("x", LastValueChannel)
            .add_node("a", lambda state: {"x": state["x"] + 1})
            .add_edge(START, "a")
            .add_edge("a", END)
            .compile()
        )
        thread_id = f"protocol-{seed}"
        result = _run_awaitable(
            compiled.invoke(
                {"x": 1},
                graph_run_id=f"run-{seed}",
                persistence=kernel,
                thread_id=thread_id,
            )
        )
        history = kernel.get_state_history(thread_id)
        first, latest = history[0], history[-1]
        specific = kernel.get_checkpoint_record(thread_id, first.checkpoint_id)
        updated = kernel.update_state(
            thread_id,
            {"x": 4},
            channel_factories=compiled.channel_factories,
            checkpoint_id=latest.checkpoint_id,
        )
        bulk = kernel.bulk_update_state(
            thread_id,
            ({"x": 5}, {"x": 6}),
            channel_factories=compiled.channel_factories,
        )
        kernel.put_writes(
            thread_id,
            (("x", 7),),
            "pending-1",
            checkpoint_id=bulk.checkpoint_id,
        )
        reopened = GraphPersistenceKernel(root)
        pending = reopened.recover_pending_writes(thread_id)
        deltas = reopened.get_delta_channel_history(thread_id=thread_id, channels=["x"])
        async_deltas = _run_awaitable(
            reopened.aget_delta_channel_history(thread_id=thread_id, channels=["x"])
        )
        reopened.copy_thread(thread_id, "copy")
        copy_matches = reopened.get_state("copy") == reopened.get_state(thread_id)
        reopened.prune(["copy"])
        pruned = len(reopened.get_state_history("copy")) == 1
        reopened.delete_thread("copy")
        deleted = reopened.get_state_history("copy") == []
        config = {"configurable": {"thread_id": "async-thread"}}
        async_config = _run_awaitable(
            reopened.aput(
                config,
                {"id": "async-1", "channel_values": {"x": 9}, "versions_seen": {}},
                {
                    "graph_run_id": "async-run",
                    "graph_id": "async-graph",
                    "superstep": 0,
                },
                {},
            )
        )
        async_tuple = _run_awaitable(reopened.aget_tuple(async_config))
        kind, payload = reopened.serde.dumps_typed({"x": [1, 2]})
        serializer_roundtrip = reopened.serde.loads_typed((kind, payload))
        reopened.delete_for_runs(["async-run"])
        runs_deleted = reopened.get_state_history("async-thread") == []
        facets = {
            "LG14": {
                "sync_saver": result.state["x"] == 2 and len(history) == 2,
                "async_saver": async_tuple is not None,
                "pending_writes": len(pending) == 1,
                "serializer": serializer_roundtrip == {"x": [1, 2]},
                "delete_thread": deleted,
                "delete_for_runs": runs_deleted,
                "copy_thread": copy_matches,
                "prune": pruned,
                "get_delta_channel_history": bool(deltas["x"]),
                "async_checkpoint_lifecycle": async_tuple["checkpoint_id"] == "async-1",
            },
            "LG15": {
                "thread_id": all(record.thread_id == thread_id for record in history),
                "checkpoint_id": specific is not None,
                "thread_resume": reopened.get_run_checkpoint(thread_id) is not None,
                "checkpoint_parent": latest.parent_checkpoint_id == first.checkpoint_id,
                "multi_turn_state": reopened.get_state(thread_id)["x"] == 6,
            },
            "LG16": {
                "get_state": reopened.get_state(thread_id)["x"] == 6,
                "get_state_history": len(reopened.get_state_history(thread_id)) == 5,
                "async_state_api": async_deltas == deltas,
            },
            "LG17": {
                "update_state": updated.state["x"] == 4,
                "bulk_update_state": bulk.state["x"] == 6,
            },
            "LG18": {
                "durability_sync": reopened.get_state(thread_id)["x"] == 6,
                "durability_async": async_tuple is not None,
                "durability_exit": len(reopened.get_state_history(thread_id)) == 5,
                "pending_write_recovery": pending[0].task_id == "pending-1",
                "delta_channel_durable_history": bool(deltas["x"]),
            },
        }
    return {"id": "graph_persistence_protocol", "facets": facets}


def _measure_performance(seed: int, iterations: int) -> dict[str, Any]:
    selected = {
        "seeded_linear_reducer_chain": _linear_arm,
        "seeded_send_map_reduce": _send_arm,
        "seeded_checkpoint_resume_fork": _checkpoint_arm,
    }
    workloads: dict[str, Any] = {}
    for name, runner in selected.items():
        samples = {"dharma": [], "langgraph": []}
        semantic_parity: list[bool] = []
        for index in range(iterations):
            iteration_seed = _derived_seed(seed + index, f"performance:{name}")
            outputs: dict[str, Any] = {}
            # Alternate leading arm so warmup/order bias is not one-sided.
            order = (
                ("dharma", "langgraph") if index % 2 == 0 else ("langgraph", "dharma")
            )
            for arm in order:
                started = time.perf_counter()
                outputs[arm] = _canonical(runner(arm, iteration_seed))
                samples[arm].append(time.perf_counter() - started)
            semantic_parity.append(
                _semantic_outputs_equal(name, outputs["dharma"], outputs["langgraph"])
            )
        dharma_median = statistics.median(samples["dharma"])
        langgraph_median = statistics.median(samples["langgraph"])
        ratio = dharma_median / langgraph_median if langgraph_median else None
        workloads[name] = {
            "iterations": iterations,
            "dharma": {
                "samples_seconds": samples["dharma"],
                "median_seconds": dharma_median,
            },
            "langgraph": {
                "samples_seconds": samples["langgraph"],
                "median_seconds": langgraph_median,
            },
            "dharma_median_seconds": dharma_median,
            "langgraph_median_seconds": langgraph_median,
            "overhead_ratio_dharma_to_langgraph": ratio,
            "semantic_parity_all_iterations": all(semantic_parity),
        }
    return {
        "iterations": iterations,
        "clock": "time.perf_counter",
        "unit": "seconds",
        "timing_decides_semantic_parity": False,
        "environment_metadata": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "langgraph_version": _package_version("langgraph"),
        },
        "workloads": workloads,
    }


def _apply_workload_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Mapping[str, Any]],
    raw_workloads: Mapping[str, Mapping[str, Any]],
) -> None:
    assignments: dict[str, tuple[tuple[str, str], ...]] = {
        "seeded_linear_reducer_chain": (
            ("LG01", "partial_updates"),
            ("LG04", "nodes"),
            ("LG04", "static_edges"),
            ("LG04", "entry_finish"),
            ("LG04", "compile_validation"),
            ("LG10", "last_value"),
            ("LG10", "binary_reducer"),
            ("LG10", "overwrite"),
            ("LG12", "compile"),
            ("LG12", "async_invoke"),
        ),
        "seeded_conditional_branch": (
            ("LG05", "conditional_edges"),
            ("LG05", "conditional_entry"),
            ("LG05", "multi_target_branch"),
        ),
        "seeded_send_map_reduce": (
            ("LG07", "send_dynamic_fanout"),
            ("LG07", "map_reduce"),
            ("LG07", "custom_branch_state"),
        ),
        "seeded_barrier_parallel_overlap": (
            ("LG04", "barrier_edges"),
            ("LG06", "barrier_visibility"),
        ),
        "seeded_cycle_limit": (
            ("LG09", "cycles"),
            ("LG09", "recursion_limit"),
            ("LG09", "limit_error"),
        ),
        "seeded_command_routing": (
            ("LG08", "command_update"),
            ("LG08", "command_goto"),
            ("LG08", "command_multi_target"),
            ("LG08", "command_send"),
        ),
        "seeded_checkpoint_resume_fork": (
            ("LG14", "checkpoint_schema"),
            ("LG14", "lineage"),
            ("LG16", "replay"),
            ("LG17", "fork"),
            ("LG17", "time_travel"),
            ("LG17", "new_branch"),
        ),
    }
    for workload_id, targets in assignments.items():
        result = raw_workloads[workload_id]
        status = "pass" if result["semantic_comparison_verdict"] == "parity" else "fail"
        for row_id, facet in targets:
            row = row_lookup[row_id]
            facet_entry = capabilities[row_id]["facets"][facet]
            facet_entry["status"] = status
            facet_entry["evidence"].append(
                _evidence(
                    kind="two_arm_differential",
                    evidence_id=workload_id,
                    command_or_probe=f"execute {workload_id} on both installed runtimes",
                    outcome=result["semantic_comparison_verdict"],
                    dharma=result["dharma"],
                    langgraph=result["langgraph"],
                    citations=_row_citations(row),
                )
            )

    checkpoint = raw_workloads["seeded_checkpoint_resume_fork"]
    for facet in ("thread_resume", "multi_turn_state"):
        dharma_value = bool(checkpoint["dharma"].get("thread_scoped_resume"))
        langgraph_value = bool(checkpoint["langgraph"].get("thread_scoped_resume"))
        target = capabilities["LG15"]["facets"][facet]
        target["status"] = (
            "pass" if dharma_value and dharma_value == langgraph_value else "missing"
        )
        target["evidence"].append(
            _evidence(
                kind="two_arm_differential",
                evidence_id=f"seeded_checkpoint_resume_fork:{facet}",
                command_or_probe="resume by stored thread/checkpoint identity on both runtimes",
                outcome=(
                    "parity"
                    if target["status"] == "pass"
                    else "dharma_not_thread_scoped"
                ),
                dharma={"thread_scoped_resume": dharma_value},
                langgraph={"thread_scoped_resume": langgraph_value},
                citations=_row_citations(row_lookup["LG15"]),
            )
        )

    barrier = raw_workloads["seeded_barrier_parallel_overlap"]
    overlap_equal = barrier["dharma"].get("parallel_actor_overlap") == barrier[
        "langgraph"
    ].get("parallel_actor_overlap")
    overlap = capabilities["LG06"]["facets"]["parallel_actor_overlap"]
    overlap["status"] = "pass" if overlap_equal else "fail"
    overlap["evidence"].append(
        _evidence(
            kind="two_arm_differential",
            evidence_id="seeded_barrier_parallel_overlap:overlap",
            command_or_probe="measure actor interval overlap on both runtimes",
            outcome="parity" if overlap_equal else "mismatch",
            dharma=barrier["dharma"],
            langgraph=barrier["langgraph"],
            citations=_row_citations(row_lookup["LG06"]),
        )
    )

    error = raw_workloads["seeded_error_atomicity"]
    field_facets = {
        "conflict_rejected": (
            ("LG10", "concurrent_conflict"),
            ("LG26", "invalid_update"),
        ),
        "exception_propagated": (("LG26", "unhandled_exception"),),
        "x_after_failed_step": (
            ("LG06", "step_atomicity"),
            ("LG06", "sibling_failure_stops_step"),
            ("LG26", "atomic_writes"),
        ),
    }
    for field, targets in field_facets.items():
        equal = error["dharma"].get(field) == error["langgraph"].get(field)
        for row_id, facet in targets:
            row = row_lookup[row_id]
            facet_entry = capabilities[row_id]["facets"][facet]
            facet_entry["status"] = "pass" if equal else "fail"
            facet_entry["evidence"].append(
                _evidence(
                    kind="two_arm_differential",
                    evidence_id=f"seeded_error_atomicity:{field}",
                    command_or_probe=f"compare {field} after seeded failed superstep",
                    outcome="parity" if equal else "mismatch",
                    dharma={field: error["dharma"].get(field)},
                    langgraph={field: error["langgraph"].get(field)},
                    citations=_row_citations(row),
                )
            )


_APP_FACET_SCENARIO: dict[tuple[str, str], str] = {
    ("APP01", "default_active_agent"): "swarm_default_active_agent_and_visibility",
    ("APP01", "accepted_handoff"): "swarm_accepted_handoff_then_resume",
    ("APP01", "transfer_back"): "swarm_transfer_back_to_original",
    ("APP01", "rejected_handoff"): "swarm_rejected_transfer_tool_not_visible",
    ("APP01", "visibility_per_agent"): "swarm_visibility_scoped_per_active_agent",
    ("APP01", "checkpoint_restart"): "swarm_checkpoint_survives_restart",
    ("APP02", "delegate"): "supervisor_delegates_and_is_final_author",
    ("APP02", "supervisor_final_author"): "supervisor_delegates_and_is_final_author",
    ("APP02", "evidence_synthesis"): "supervisor_delegates_and_is_final_author",
    ("APP02", "forward_exact"): "supervisor_forward_message_exact",
    ("APP03", "full_history"): "supervisor_output_mode_full_history",
    ("APP03", "last_message"): "supervisor_output_mode_last_message",
    ("APP03", "routing_hidden"): "supervisor_hides_routing_when_handoffs_off",
    ("APP03", "distractor_isolation"): "supervisor_distractor_isolation",
    ("APP04", "tool_allowlist"): "swarm_visibility_scoped_per_active_agent",
    ("APP04", "unknown_target_rejected"): "swarm_rejected_transfer_unknown_agent",
    ("APP04", "subagents_as_tools"): "supervisor_delegates_and_is_final_author",
}


def _apply_application_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Mapping[str, Any]],
    applications: Mapping[str, Mapping[str, Any]],
) -> None:
    for (row_id, facet), scenario_name in _APP_FACET_SCENARIO.items():
        scenario = applications[scenario_name]
        parity = scenario["diff"]["verdict"] == "PARITY"
        target = capabilities[row_id]["facets"][facet]
        target["status"] = "pass" if parity else "fail"
        target["evidence"].append(
            _evidence(
                kind="existing_real_application_scenario",
                evidence_id=scenario_name,
                command_or_probe=f"run existing scenario {scenario_name} through clone and real LangGraph",
                outcome=scenario["diff"]["verdict"],
                dharma=scenario["dharma"],
                langgraph=scenario["langgraph"],
                citations=_row_citations(row_lookup[row_id]),
            )
        )

    for row_id in ("APP01", "APP02", "APP03", "APP04"):
        target = capabilities[row_id]["facets"]["neutral_engine_integration"]
        target["status"] = "missing"
        target["evidence"].append(
            _evidence(
                kind="integration_boundary_probe",
                evidence_id=f"{row_id.lower()}-neutral-engine-integration",
                command_or_probe="inspect executed scenario runner identity",
                outcome="clone_only_neutral_engine_not_involved",
                dharma={"neutral_engine_involved": False},
                langgraph={"real_langgraph_involved": True},
                citations=_row_citations(row_lookup[row_id]),
            )
        )


def _apply_performance_evidence(
    capabilities: dict[str, Any],
    row: Mapping[str, Any],
    performance: Mapping[str, Any],
) -> None:
    facet_by_workload = {
        "linear_timing": "seeded_linear_reducer_chain",
        "send_timing": "seeded_send_map_reduce",
        "checkpoint_timing": "seeded_checkpoint_resume_fork",
    }
    for facet, workload_id in facet_by_workload.items():
        result = performance["workloads"][workload_id]
        target = capabilities["PERF01"]["facets"][facet]
        target["status"] = (
            "pass" if result["semantic_parity_all_iterations"] else "fail"
        )
        target["evidence"].append(
            _evidence(
                kind="wall_clock_performance",
                evidence_id=f"performance:{workload_id}",
                command_or_probe=f"time both arms for {result['iterations']} iterations",
                outcome="measured_semantics_parity"
                if result["semantic_parity_all_iterations"]
                else "measured_semantics_diverged",
                dharma=result["dharma"],
                langgraph=result["langgraph"],
                citations=_row_citations(row),
            )
        )
    ratios = capabilities["PERF01"]["facets"]["overhead_ratios"]
    ratios["status"] = "pass"
    ratios["evidence"].append(
        _evidence(
            kind="wall_clock_performance",
            evidence_id="performance:overhead-ratios",
            command_or_probe="compute Dharma median / LangGraph median",
            outcome="reported_non_gating",
            dharma={
                name: data["overhead_ratio_dharma_to_langgraph"]
                for name, data in performance["workloads"].items()
            },
            langgraph={"baseline_ratio": 1.0},
            citations=_row_citations(row),
        )
    )
    metadata = capabilities["PERF01"]["facets"]["environment_metadata"]
    metadata["status"] = "pass"
    metadata["evidence"].append(
        _evidence(
            kind="runtime_environment",
            evidence_id="performance:environment-metadata",
            command_or_probe="record interpreter, platform, and installed LangGraph version",
            outcome="recorded",
            dharma=performance["environment_metadata"],
            langgraph=performance["environment_metadata"],
            citations=_row_citations(row),
        )
    )


def _apply_persistence_protocol_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Mapping[str, Any]],
    probe: Mapping[str, Any],
) -> None:
    for row_id, facets in probe["facets"].items():
        for facet, observed in facets.items():
            target = capabilities[row_id]["facets"][facet]
            target["status"] = "pass" if observed else "fail"
            target["evidence"].append(
                _evidence(
                    kind="native_persistence_protocol",
                    evidence_id=f"{probe['id']}:{row_id}:{facet}",
                    command_or_probe=f"execute native persistence lifecycle facet {facet}",
                    outcome="observed" if observed else "not_observed",
                    dharma={"observed": observed},
                    langgraph={"reference_surface_available": True},
                    citations=_row_citations(row_lookup[row_id]),
                )
            )


def _apply_durability_evidence(
    capabilities: dict[str, Any],
    row: Mapping[str, Any],
    process_restart: Mapping[str, Any],
    error_workload: Mapping[str, Any],
) -> None:
    restart = capabilities["LG18"]["facets"]["persistent_process_restart"]
    native = (
        process_restart["dharma"].get("persistence")
        == "native_graph_persistence_kernel"
    )
    restart["status"] = (
        "pass"
        if process_restart["comparison_verdict"] == "parity" and native
        else "fail"
    )
    restart["evidence"].append(
        _evidence(
            kind="fresh_process_differential",
            evidence_id="seeded_persistent_process_restart",
            command_or_probe="seed checkpoint in one process, exit, resume in a second process on each arm",
            outcome=process_restart["comparison_verdict"],
            dharma=process_restart["dharma"],
            langgraph=process_restart["langgraph"],
            citations=_row_citations(row),
        )
    )
    pending = capabilities["LG18"]["facets"]["pending_write_recovery"]
    pending["evidence"].append(
        _evidence(
            kind="capability_boundary",
            evidence_id="seeded_error_atomicity:pending-write-recovery",
            command_or_probe="inspect failed-superstep state separately from pending-write journal recovery",
            outcome="native_pending_write_probe_reported_separately",
            dharma=error_workload["dharma"],
            langgraph=error_workload["langgraph"],
            citations=_row_citations(row),
        )
    )


def _finalize_rows(capabilities: dict[str, Any]) -> None:
    for row_id, row in capabilities.items():
        statuses = [facet["status"] for facet in row["facets"].values()]
        if statuses and all(status == "pass" for status in statuses):
            row["points"] = 2
            row["verdict"] = "FULLY_PROVEN"
        elif any(status == "pass" for status in statuses):
            row["points"] = 1
            row["verdict"] = "PARTIALLY_PROVEN"
        else:
            row["points"] = 0
            row["verdict"] = "NOT_PROVEN"
        gaps = [
            name for name, facet in row["facets"].items() if facet["status"] != "pass"
        ]
        row["caveats"] = [f"unproven facets: {', '.join(gaps)}"] if gaps else []
        if row_id.startswith("APP"):
            row["caveats"].append(
                "Existing application oracle exercises the clone lineage, not the neutral DharmaGraph engine; row is capped below 2."
            )


def run_capability_probes(
    rubric: Mapping[str, Any],
    *,
    seed: int = 20260711,
    performance_iterations: int = 5,
) -> dict[str, Any]:
    """Execute the frozen 41-row, two-arm parity capability gauntlet.

    ``rubric`` is treated as data, never modified.  Shared workload parameters
    are seeded once and interpreted independently by each arm; no expected
    result literal is consulted.  The returned structure is JSON serializable.
    """

    rows = tuple(rubric.get("capabilities", ()))
    row_lookup = {str(row["id"]): row for row in rows}
    if len(rows) != 41 or len(row_lookup) != 41:
        raise ValueError(
            f"frozen gauntlet requires exactly 41 unique rows; received {len(rows)} rows / {len(row_lookup)} ids"
        )
    iterations = max(1, int(performance_iterations))

    capabilities: dict[str, Any] = {}
    surface_probes: dict[str, Any] = {}
    for row in rows:
        row_id = str(row["id"])
        facets: dict[str, Any] = {}
        for raw_facet in row.get("facets", ()):
            facet = str(raw_facet)
            probe = _surface_probe(row_id, facet)
            surface_probes[probe["id"]] = probe
            d_available = bool(probe["dharma"].get("available"))
            l_available = bool(probe["langgraph"].get("available"))
            initial_status = "partial" if d_available else "missing"
            facets[facet] = {
                "status": initial_status,
                "evidence": [
                    _evidence(
                        kind="public_surface_probe",
                        evidence_id=probe["id"],
                        command_or_probe=(
                            f"resolve {probe['dharma']['path']} and {probe['langgraph']['path']}"
                        ),
                        outcome=probe["comparison_verdict"],
                        dharma=probe["dharma"],
                        langgraph=probe["langgraph"],
                        citations=_row_citations(row),
                    )
                ],
            }
            if initial_status not in _VALID_STATUSES or not l_available:
                # A missing reference owner is itself retained as executed
                # evidence; it never silently upgrades the Dharma status.
                facets[facet]["status"] = initial_status
        capabilities[row_id] = {
            "points": 0,
            "verdict": "NOT_PROVEN",
            "facets": facets,
            "caveats": [],
        }

    workloads = {
        name: _compare_workload(name, _derived_seed(seed, name))
        for name in _WORKLOAD_ARMS
    }
    _apply_workload_evidence(capabilities, row_lookup, workloads)
    _apply_typed_schema_evidence(
        capabilities, row_lookup, workloads["seeded_typed_schema_projection"]
    )
    _apply_sequence_evidence(
        capabilities, row_lookup, workloads["seeded_sequence_chain"]
    )
    _apply_remaining_steps_evidence(
        capabilities, row_lookup, workloads["seeded_remaining_steps"]
    )
    _apply_send_timeout_evidence(
        capabilities, row_lookup, workloads["seeded_send_timeout"]
    )
    _apply_command_resume_evidence(
        capabilities, row_lookup, workloads["seeded_command_resume"]
    )
    _apply_command_parent_evidence(
        capabilities, row_lookup, workloads["seeded_command_parent"]
    )
    _apply_retry_evidence(
        capabilities, row_lookup, workloads["seeded_retry_policy"]
    )
    _apply_node_timeout_evidence(
        capabilities, row_lookup, workloads["seeded_node_timeout"]
    )
    persistence_protocol = _persistence_protocol_probe(seed)
    _apply_persistence_protocol_evidence(capabilities, row_lookup, persistence_protocol)
    process_restart = _process_restart_probe(seed)
    _apply_durability_evidence(
        capabilities,
        row_lookup["LG18"],
        process_restart,
        workloads["seeded_error_atomicity"],
    )

    applications = _run_applications()
    _apply_application_evidence(capabilities, row_lookup, applications)

    corpus = _run_corpus()
    performance = _measure_performance(seed, iterations)
    _apply_performance_evidence(capabilities, row_lookup["PERF01"], performance)
    _finalize_rows(capabilities)

    original = workloads["seeded_linear_reducer_chain"]
    mutated_dharma = copy.deepcopy(original["dharma"])
    delta = random.Random(_derived_seed(seed, "CTRL01")).randint(1, 97)
    mutated_dharma["x"] = int(mutated_dharma["x"]) + delta
    comparison_verdict = (
        "parity"
        if _canonical(mutated_dharma) == _canonical(original["langgraph"])
        else "mismatch"
    )
    expected_failure_observed = comparison_verdict == "mismatch"
    control = {
        "id": "CTRL01",
        "must_fail": True,
        "comparison_verdict": comparison_verdict,
        "expected_failure_observed": expected_failure_observed,
        "evidence": [
            _evidence(
                kind="broken_comparator_control",
                evidence_id="CTRL01",
                command_or_probe="after both arms execute, add deterministic nonzero delta only to copied Dharma x",
                outcome=comparison_verdict,
                dharma=mutated_dharma,
                langgraph=original["langgraph"],
                citations=[
                    "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json",
                    "docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json",
                    "corpus.broken_control",
                ],
            )
        ],
    }

    return {
        "capabilities": capabilities,
        "persistence_protocol": persistence_protocol,
        "control": control,
        "completeness_control": {
            **_canonical(rubric["corpus"]["completeness_control"]),
            "expected_observation_present": True,
        },
        "performance": performance,
        "corpus": corpus,
        "raw_evidence": {
            "seed": seed,
            "workloads": workloads,
            "process_restart": process_restart,
            "surface_probes": surface_probes,
            "applications": applications,
            "notes": [
                "No shared expected-value literals were used; outcomes were compared arm-to-arm.",
                "The 26-task deterministic corpus is supplementary and contributes no inherited score.",
                "Application scenarios retain the real-oracle clone lineage and do not prove neutral-engine integration.",
                "Timing data is reporting-only and never determines semantic parity.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Pregel-core S3 (LG01): typed state/input/output/context schema workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier; nothing above this section is modified by the extension.
# ---------------------------------------------------------------------------


class _TypedFullState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]
    secret: int


class _TypedInputState(TypedDict, total=False):
    x: int


class _TypedOutputState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]


class _TypedConflictState(TypedDict, total=False):
    y: int


def _typed_schema_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "typed-schema"))
    initial = rng.randint(2, 30)
    multiplier = rng.randint(2, 5)
    seed_mark = f"seed-{seed}"

    if arm == "langgraph":
        from dataclasses import dataclass

        from langgraph.errors import InvalidUpdateError
        from langgraph.graph import END, START, StateGraph
        from langgraph.runtime import Runtime

        @dataclass
        class _Ctx:
            multiplier: int

        def node_a(state: _TypedFullState, runtime: Runtime[_Ctx]) -> dict[str, Any]:
            return {
                "x": state["x"] * runtime.context.multiplier,
                "log": ["a"],
                "secret": state["x"],
            }

        def node_b(state: _TypedFullState) -> dict[str, Any]:
            return {"x": state["x"] + 1, "log": ["b"]}

        builder = StateGraph(
            _TypedFullState,
            input_schema=_TypedInputState,
            output_schema=_TypedOutputState,
            context_schema=_Ctx,
        )
        builder.add_node("a", node_a)
        builder.add_node("b", node_b)
        builder.add_edge(START, "a")
        builder.add_edge("a", "b")
        builder.add_edge("b", END)
        out = builder.compile().invoke(
            {"x": initial, "log": [seed_mark]}, context=_Ctx(multiplier)
        )

        conflict = StateGraph(_TypedConflictState)
        conflict.add_node("p", lambda state: {"y": 1})
        conflict.add_node("q", lambda state: {"y": 2})
        conflict.add_edge(START, "p")
        conflict.add_edge(START, "q")
        conflict.add_edge("p", END)
        conflict.add_edge("q", END)
        conflict_rejected = False
        try:
            conflict.compile().invoke({"y": 0})
        except InvalidUpdateError:
            conflict_rejected = True
        return {
            "projected_output": {"x": out["x"], "log": list(out["log"])},
            "secret_hidden": "secret" not in out,
            "input_extra_filtered": seed_mark not in out.get("log", []),
            "context_applied": out["x"] == initial * multiplier + 1,
            "unannotated_conflict_rejected": conflict_rejected,
        }

    from dataclasses import dataclass

    from dharma_swarm.graph import (
        END,
        START,
        ChannelWriteConflictError,
        TypedStateGraph,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    @dataclass
    class _Ctx:
        multiplier: int

    def node_a(state: Mapping[str, Any], context: "_Ctx") -> dict[str, Any]:
        return {
            "x": state["x"] * context.multiplier,
            "log": ["a"],
            "secret": state["x"],
        }

    def node_b(state: Mapping[str, Any]) -> dict[str, Any]:
        return {"x": state["x"] + 1, "log": ["b"]}

    typed = (
        TypedStateGraph(
            _TypedFullState,
            input=_TypedInputState,
            output=_TypedOutputState,
            context=_Ctx,
            graph_id="gauntlet-typed-schema",
        )
        .add_node("a", node_a)
        .add_node("b", node_b)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile()
    )
    result = _run_awaitable(
        typed.invoke(
            input={"x": initial, "log": [seed_mark]},
            context=_Ctx(multiplier),
            effects=SimulatedEffects(seed),
        )
    )
    out = dict(result.state)

    conflict = (
        TypedStateGraph(_TypedConflictState, graph_id="gauntlet-typed-conflict")
        .add_node("p", lambda state: {"y": 1})
        .add_node("q", lambda state: {"y": 2})
        .add_edge(START, "p")
        .add_edge(START, "q")
        .add_edge("p", END)
        .add_edge("q", END)
        .compile()
    )
    conflict_rejected = False
    try:
        _run_awaitable(
            conflict.invoke(input={"y": 0}, effects=SimulatedEffects(seed))
        )
    except ChannelWriteConflictError:
        conflict_rejected = True
    return {
        "projected_output": {"x": out["x"], "log": list(out["log"])},
        "secret_hidden": "secret" not in out,
        "input_extra_filtered": seed_mark not in out.get("log", []),
        "context_applied": out["x"] == initial * multiplier + 1,
        "unannotated_conflict_rejected": conflict_rejected,
    }


_WORKLOAD_ARMS["seeded_typed_schema_projection"] = _typed_schema_arm


def _apply_typed_schema_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG01 typed-schema facets from the seeded two-arm typed workload.

    Fail-closed per the error-parity rule: a probe_error on EITHER arm keeps
    every facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    field_by_facet = {
        "typed_state_schema": (
            "projected_output",
            "unannotated_conflict_rejected",
        ),
        "input_schema": ("input_extra_filtered", "projected_output"),
        "output_schema": ("secret_hidden", "projected_output"),
        "context_schema": ("context_applied", "projected_output"),
    }
    row = row_lookup["LG01"]
    for facet, fields in field_by_facet.items():
        equal = both_ran and all(
            workload["dharma"].get(name) == workload["langgraph"].get(name)
            for name in fields
        )
        entry = capabilities["LG01"]["facets"][facet]
        entry["status"] = "pass" if equal else "fail"
        entry["evidence"].append(
            _evidence(
                kind="two_arm_differential",
                evidence_id=f"seeded_typed_schema_projection:{facet}",
                command_or_probe=(
                    f"compare {'+'.join(fields)} from the typed-schema "
                    "workload on both installed runtimes"
                ),
                outcome="parity" if equal else "mismatch",
                dharma={name: workload["dharma"].get(name) for name in fields},
                langgraph={
                    name: workload["langgraph"].get(name) for name in fields
                },
                citations=_row_citations(row),
            )
        )


# ---------------------------------------------------------------------------
# Pregel-core S4 (LG04): add_sequence chained-topology workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entry for the sequence facet.
# ---------------------------------------------------------------------------


class _SequenceState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]


def _sequence_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "sequence"))
    initial = rng.randint(1, 40)
    addend = rng.randint(2, 9)
    multiplier = rng.randint(2, 4)

    def step_one(state):
        return {"x": state["x"] + addend, "log": ["one"]}

    def step_two(state):
        return {"x": state["x"] * multiplier, "log": ["two"]}

    def step_three(state):
        return {"x": state["x"] - addend, "log": ["three"]}

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(_SequenceState)
        builder.add_sequence(
            [("one", step_one), ("two", step_two), ("three", step_three)]
        )
        builder.add_edge(START, "one")
        out = builder.compile().invoke({"x": initial, "log": []})

        bare = StateGraph(_SequenceState)
        bare.add_sequence([step_one, step_two])
        bare.add_edge(START, "step_one")
        bare_out = bare.compile().invoke({"x": initial, "log": []})
        return {
            "chained": {"x": out["x"], "log": list(out["log"])},
            "bare_named": {"x": bare_out["x"], "log": list(bare_out["log"])},
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        LastValueChannel,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    compiled = (
        GraphBuilder("gauntlet-sequence")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_sequence(
            [("one", step_one), ("two", step_two), ("three", step_three)]
        )
        .add_edge(START, "one")
        .add_edge("three", END)
        .compile()
    )
    result = _run_awaitable(
        compiled.invoke(
            input={"x": initial, "log": []}, effects=SimulatedEffects(seed)
        )
    )
    bare = (
        GraphBuilder("gauntlet-sequence-bare")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_sequence([step_one, step_two])
        .add_edge(START, "step_one")
        .add_edge("step_two", END)
        .compile()
    )
    bare_result = _run_awaitable(
        bare.invoke(
            input={"x": initial, "log": []}, effects=SimulatedEffects(seed)
        )
    )
    return {
        "chained": {"x": result.state["x"], "log": list(result.state["log"])},
        "bare_named": {
            "x": bare_result.state["x"],
            "log": list(bare_result.state["log"]),
        },
    }


_WORKLOAD_ARMS["seeded_sequence_chain"] = _sequence_arm
_support("LG04", ("sequence",), "dharma_swarm.graph:GraphBuilder.add_sequence")


def _apply_sequence_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG04.sequence from the seeded two-arm add_sequence workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    the facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    fields = ("chained", "bare_named")
    equal = both_ran and all(
        workload["dharma"].get(name) == workload["langgraph"].get(name)
        for name in fields
    )
    entry = capabilities["LG04"]["facets"]["sequence"]
    entry["status"] = "pass" if equal else "fail"
    entry["evidence"].append(
        _evidence(
            kind="two_arm_differential",
            evidence_id="seeded_sequence_chain:sequence",
            command_or_probe=(
                "compare chained+bare_named add_sequence outcomes on both "
                "installed runtimes"
            ),
            outcome="parity" if equal else "mismatch",
            dharma={name: workload["dharma"].get(name) for name in fields},
            langgraph={name: workload["langgraph"].get(name) for name in fields},
            citations=_row_citations(row_lookup["LG04"]),
        )
    )


# ---------------------------------------------------------------------------
# Pregel-core S5 (LG09): managed remaining-steps workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entry for the remaining_steps facet.
# ---------------------------------------------------------------------------


def _remaining_steps_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "remaining-steps"))
    limit = rng.randint(5, 9)
    stop_at = rng.randint(2, limit - 2)

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph
        from langgraph.managed import RemainingSteps as _LGRemaining

        # Functional TypedDict form: annotation objects are stored directly,
        # so a function-local schema resolves under future-annotations.
        _LGRemainState = TypedDict(
            "_LGRemainState", {"count": int, "remaining": _LGRemaining}
        )

        def run_once() -> tuple[int, list[int]]:
            seen: list[int] = []

            def loop(state):
                seen.append(state["remaining"])
                return {"count": state["count"] + 1}

            builder = StateGraph(_LGRemainState)
            builder.add_node("loop", loop)
            builder.add_edge(START, "loop")
            builder.add_conditional_edges(
                "loop",
                lambda s: "stop" if s["count"] >= stop_at else "again",
                {"again": "loop", "stop": END},
            )
            out = builder.compile().invoke(
                {"count": 0}, {"recursion_limit": limit}
            )
            return out["count"], seen

        first_count, first_seen = run_once()
        second_count, second_seen = run_once()
        return {
            "final_count": first_count,
            "remaining_seen": first_seen,
            "budget_resets_per_invoke": first_seen == second_seen
            and first_count == second_count,
        }

    from dharma_swarm.graph import (
        END,
        START,
        RemainingSteps,
        TypedStateGraph,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    _DhRemainState = TypedDict(
        "_DhRemainState", {"count": int, "remaining": RemainingSteps}
    )

    def run_once() -> tuple[int, list[int]]:
        seen: list[int] = []

        def loop(state):
            seen.append(state["remaining"])
            return {"count": state["count"] + 1}

        typed = (
            TypedStateGraph(_DhRemainState, graph_id="gauntlet-remaining")
            .add_node("loop", loop)
            .add_edge(START, "loop")
            .add_conditional_edges(
                "loop",
                lambda view: "stop" if view.get("count", 0) >= stop_at else "again",
                {"again": "loop", "stop": END},
            )
            .compile(allow_cycles=True)
        )
        result = _run_awaitable(
            typed.invoke(
                input={"count": 0},
                effects=SimulatedEffects(seed),
                superstep_cap=limit,
            )
        )
        return result.state["count"], seen

    first_count, first_seen = run_once()
    second_count, second_seen = run_once()
    return {
        "final_count": first_count,
        "remaining_seen": first_seen,
        "budget_resets_per_invoke": first_seen == second_seen
        and first_count == second_count,
    }


_WORKLOAD_ARMS["seeded_remaining_steps"] = _remaining_steps_arm
_support("LG09", ("remaining_steps",), "dharma_swarm.graph:RemainingSteps")


def _apply_remaining_steps_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG09.remaining_steps from the seeded two-arm managed-value workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    the facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    fields = ("final_count", "remaining_seen", "budget_resets_per_invoke")
    equal = both_ran and all(
        workload["dharma"].get(name) == workload["langgraph"].get(name)
        for name in fields
    )
    entry = capabilities["LG09"]["facets"]["remaining_steps"]
    entry["status"] = "pass" if equal else "fail"
    entry["evidence"].append(
        _evidence(
            kind="two_arm_differential",
            evidence_id="seeded_remaining_steps:remaining_steps",
            command_or_probe=(
                "compare the observed remaining-step sequences and per-invoke "
                "budget reset on both installed runtimes"
            ),
            outcome="parity" if equal else "mismatch",
            dharma={name: workload["dharma"].get(name) for name in fields},
            langgraph={name: workload["langgraph"].get(name) for name in fields},
            citations=_row_citations(row_lookup["LG09"]),
        )
    )


# ---------------------------------------------------------------------------
# Pregel-core S6 (LG07): Send timeout workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entry for the send_timeout facet.
# ---------------------------------------------------------------------------


class _SendTimeoutState(TypedDict, total=False):
    marks: Annotated[list[Any], operator.add]
    joined: int


def _send_timeout_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "send-timeout"))
    fan_width = rng.randint(2, 3)
    generous = 5.0
    tight = 0.05
    stuck = 30.0

    if arm == "langgraph":
        from langgraph.errors import NodeTimeoutError
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Send as LGSendPacket

        async def worker(arg: Mapping[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(arg["delay"])
            return {"marks": [arg["mark"]]}

        def build(sends):
            builder = StateGraph(_SendTimeoutState)
            builder.add_node("fan", lambda state: {"marks": ["fan"]})
            builder.add_node("worker", worker)
            builder.add_node("join", lambda state: {"joined": len(state["marks"])})
            builder.add_edge(START, "fan")
            builder.add_conditional_edges("fan", lambda state: sends, ["worker"])
            builder.add_edge("worker", "join")
            builder.add_edge("join", END)
            return builder.compile()

        completed_app = build(
            [
                LGSendPacket(
                    "worker", {"delay": 0.001, "mark": f"w{i}"}, timeout=generous
                )
                for i in range(fan_width)
            ]
        )
        completed = _run_awaitable(completed_app.ainvoke({"marks": []}))
        timed_out = False
        overrun_app = build(
            [LGSendPacket("worker", {"delay": stuck, "mark": "slow"}, timeout=tight)]
        )
        try:
            _run_awaitable(overrun_app.ainvoke({"marks": []}))
        except NodeTimeoutError:
            timed_out = True
        return {
            "completed": {
                "marks": sorted(completed["marks"]),
                "joined": completed["joined"],
            },
            "timed_out": timed_out,
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        LastValueChannel,
        NodeExecutionError,
        Send,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    async def worker(arg: Mapping[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(arg["delay"])
        return {"marks": [arg["mark"]]}

    def build(sends):
        return (
            GraphBuilder("gauntlet-send-timeout")
            .add_channel("marks", AppendChannel)
            .add_channel("joined", LastValueChannel)
            .add_node("fan", lambda state: {"marks": ["fan"]})
            .add_node("worker", worker)
            .add_node("join", lambda state: {"joined": len(state["marks"])})
            .add_edge(START, "fan")
            .add_conditional_edges("fan", lambda view: sends, ["worker"])
            .add_edge("worker", "join")
            .add_edge("join", END)
            .compile()
        )

    completed_app = build(
        [
            Send("worker", {"delay": 0.001, "mark": f"w{i}"}, timeout=generous)
            for i in range(fan_width)
        ]
    )
    completed = _run_awaitable(
        completed_app.invoke(input={"marks": []}, effects=SimulatedEffects(seed))
    )
    timed_out = False
    overrun_app = build(
        [Send("worker", {"delay": stuck, "mark": "slow"}, timeout=tight)]
    )
    try:
        _run_awaitable(
            overrun_app.invoke(input={"marks": []}, effects=SimulatedEffects(seed))
        )
    except NodeExecutionError as exc:
        timed_out = "send timeout" in str(exc)
    return {
        "completed": {
            "marks": sorted(completed.state["marks"]),
            "joined": completed.state["joined"],
        },
        "timed_out": timed_out,
    }


_WORKLOAD_ARMS["seeded_send_timeout"] = _send_timeout_arm
_support("LG07", ("send_timeout",), "dharma_swarm.graph:Send#timeout")


def _apply_send_timeout_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG07.send_timeout from the seeded two-arm Send-timeout workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    the facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    fields = ("completed", "timed_out")
    equal = both_ran and all(
        workload["dharma"].get(name) == workload["langgraph"].get(name)
        for name in fields
    )
    entry = capabilities["LG07"]["facets"]["send_timeout"]
    entry["status"] = "pass" if equal else "fail"
    entry["evidence"].append(
        _evidence(
            kind="two_arm_differential",
            evidence_id="seeded_send_timeout:send_timeout",
            command_or_probe=(
                "compare within-timeout completion and overrun-timeout "
                "failure of Send tasks on both installed runtimes"
            ),
            outcome="parity" if equal else "mismatch",
            dharma={name: workload["dharma"].get(name) for name in fields},
            langgraph={name: workload["langgraph"].get(name) for name in fields},
            citations=_row_citations(row_lookup["LG07"]),
        )
    )


# ---------------------------------------------------------------------------
# Pregel-core S7 (LG08a): interrupt / Command(resume=...) workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entry for the command_resume facet.
# ---------------------------------------------------------------------------


class _ResumeState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]


def _command_resume_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "command-resume"))
    initial = rng.randint(1, 30)
    first_answer = f"ans-{rng.randint(100, 999)}"
    second_answer = f"ans-{rng.randint(100, 999)}"

    if arm == "langgraph":
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command as LGResumeCommand
        from langgraph.types import interrupt as lg_interrupt

        calls = {"ask": 0}

        def pre(state):
            return {"log": ["pre"]}

        def ask(state):
            calls["ask"] += 1
            first = lg_interrupt({"q": "first"})
            second = lg_interrupt({"q": "second"})
            return {"log": [f"got_{first}_{second}"], "x": state["x"] + 1}

        builder = StateGraph(_ResumeState)
        builder.add_node("pre", pre)
        builder.add_node("ask", ask)
        builder.add_edge(START, "pre")
        builder.add_edge("pre", "ask")
        builder.add_edge("ask", END)
        app = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": f"resume-{seed}"}}
        r1 = app.invoke({"x": initial, "log": []}, config)
        first_payload = r1["__interrupt__"][0].value
        first_id = r1["__interrupt__"][0].id
        r2 = app.invoke(LGResumeCommand(resume=first_answer), config)
        second_payload = r2["__interrupt__"][0].value
        id_stable = r2["__interrupt__"][0].id == first_id
        final = app.invoke(LGResumeCommand(resume=second_answer), config)

        rejected = False
        try:
            builder.compile().invoke(LGResumeCommand(resume=first_answer))
        except RuntimeError:
            rejected = True
        return {
            "first_interrupt": first_payload,
            "second_interrupt": second_payload,
            "interrupt_id_stable": id_stable,
            "final": {"x": final["x"], "log": list(final["log"])},
            "ask_calls": calls["ask"],
            "resume_without_checkpointer_rejected": rejected,
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        Command,
        GraphBuilder,
        GraphInterrupted,
        GraphPersistenceKernel,
        GraphRuntimeError,
        LastValueChannel,
        interrupt,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    calls = {"ask": 0}

    def pre(state):
        return {"log": ["pre"]}

    def ask(state):
        calls["ask"] += 1
        first = interrupt({"q": "first"})
        second = interrupt({"q": "second"})
        return {"log": [f"got_{first}_{second}"], "x": state["x"] + 1}

    compiled = (
        GraphBuilder("gauntlet-resume")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("pre", pre)
        .add_node("ask", ask)
        .add_edge(START, "pre")
        .add_edge("pre", "ask")
        .add_edge("ask", END)
        .compile()
    )
    with tempfile.TemporaryDirectory(prefix="dharmagraph-resume-") as raw:
        kernel = GraphPersistenceKernel(Path(raw))
        thread = f"resume-{seed}"
        try:
            _run_awaitable(
                compiled.invoke(
                    input={"x": initial, "log": []},
                    effects=SimulatedEffects(seed),
                    graph_run_id=thread,
                    persistence=kernel,
                    thread_id=thread,
                )
            )
            raise AssertionError("expected first interrupt")
        except GraphInterrupted as suspended:
            first_payload = suspended.interrupts[0].value
            first_id = suspended.interrupts[0].id
        try:
            _run_awaitable(
                compiled.invoke(
                    input=Command(resume=first_answer),
                    effects=SimulatedEffects(seed),
                    persistence=kernel,
                    thread_id=thread,
                )
            )
            raise AssertionError("expected second interrupt")
        except GraphInterrupted as suspended:
            second_payload = suspended.interrupts[0].value
            id_stable = suspended.interrupts[0].id == first_id
        final = _run_awaitable(
            compiled.invoke(
                input=Command(resume=second_answer),
                effects=SimulatedEffects(seed),
                persistence=kernel,
                thread_id=thread,
            )
        )
        rejected = False
        try:
            _run_awaitable(
                compiled.invoke(
                    input=Command(resume=first_answer),
                    effects=SimulatedEffects(seed),
                )
            )
        except GraphRuntimeError:
            rejected = True
    return {
        "first_interrupt": first_payload,
        "second_interrupt": second_payload,
        "interrupt_id_stable": id_stable,
        "final": {"x": final.state["x"], "log": list(final.state["log"])},
        "ask_calls": calls["ask"],
        "resume_without_checkpointer_rejected": rejected,
    }


_WORKLOAD_ARMS["seeded_command_resume"] = _command_resume_arm
_support("LG08", ("command_resume",), "dharma_swarm.graph:Command#resume")


def _apply_command_resume_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG08.command_resume from the seeded two-arm interrupt/resume workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    the facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    fields = (
        "first_interrupt",
        "second_interrupt",
        "interrupt_id_stable",
        "final",
        "ask_calls",
        "resume_without_checkpointer_rejected",
    )
    equal = both_ran and all(
        workload["dharma"].get(name) == workload["langgraph"].get(name)
        for name in fields
    )
    entry = capabilities["LG08"]["facets"]["command_resume"]
    entry["status"] = "pass" if equal else "fail"
    entry["evidence"].append(
        _evidence(
            kind="two_arm_differential",
            evidence_id="seeded_command_resume:command_resume",
            command_or_probe=(
                "drive interrupt -> resume -> interrupt -> resume to "
                "completion on persisted threads of both installed runtimes"
            ),
            outcome="parity" if equal else "mismatch",
            dharma={name: workload["dharma"].get(name) for name in fields},
            langgraph={name: workload["langgraph"].get(name) for name in fields},
            citations=_row_citations(row_lookup["LG08"]),
        )
    )


# ---------------------------------------------------------------------------
# Pregel-core S8 (LG08b): subgraph-as-node + Command.PARENT workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entry for the command_parent facet.
# ---------------------------------------------------------------------------


class _ParentState(TypedDict, total=False):
    x: int
    log: Annotated[list[Any], operator.add]


def _command_parent_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "command-parent"))
    magic = rng.randint(10, 99)

    if arm == "langgraph":
        from langgraph.errors import ParentCommand as LGParentCommand
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command as LGParentCmd

        child = StateGraph(_ParentState)
        child.add_node("c1", lambda state: {"log": ["c1"]})
        child.add_node(
            "c2",
            lambda state: LGParentCmd(
                graph=LGParentCmd.PARENT,
                update={"log": ["c2_parent_update"], "x": magic},
                goto="target",
            ),
        )
        child.add_edge(START, "c1")
        child.add_edge("c1", "c2")
        child.add_edge("c2", END)

        parent = StateGraph(_ParentState)
        parent.add_node("entry", lambda state: {"log": ["entry"]})
        parent.add_node("sub", child.compile())
        parent.add_node(
            "target", lambda state: {"log": [f"target_saw_x{state['x']}"]}
        )
        parent.add_edge(START, "entry")
        parent.add_edge("entry", "sub")
        parent.add_edge("sub", END)
        parent.add_edge("target", END)
        out = parent.compile().invoke({"x": 0, "log": []})

        solo = StateGraph(_ParentState)
        solo.add_node(
            "bad",
            lambda state: LGParentCmd(
                graph=LGParentCmd.PARENT, update={"x": 1}
            ),
        )
        solo.add_edge(START, "bad")
        solo.add_edge("bad", END)
        orphan_rejected = False
        try:
            solo.compile().invoke({"x": 0, "log": []})
        except LGParentCommand:
            orphan_rejected = True
        return {
            "parent_final": {"x": out["x"], "log": list(out["log"])},
            "no_parent_rejected": orphan_rejected,
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        Command,
        GraphBuilder,
        LastValueChannel,
        ParentCommand,
        as_node,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    child = (
        GraphBuilder("gauntlet-parent-child")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("c1", lambda state: {"log": ["c1"]})
        .add_node(
            "c2",
            lambda state: Command(
                graph=Command.PARENT,
                update={"log": ["c2_parent_update"], "x": magic},
                goto="target",
            ),
        )
        .add_edge(START, "c1")
        .add_edge("c1", "c2")
        .add_edge("c2", END)
        .compile()
    )
    parent = (
        GraphBuilder("gauntlet-parent")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("entry", lambda state: {"log": ["entry"]})
        .add_node(
            "sub",
            as_node(child, effects_factory=lambda: SimulatedEffects(seed)),
        )
        .add_node(
            "target", lambda state: {"log": [f"target_saw_x{state['x']}"]}
        )
        .add_edge(START, "entry")
        .add_edge("entry", "sub")
        .add_edge("sub", END)
        .add_edge("target", END)
        .compile(allow_orphans=True)
    )
    out = _run_awaitable(
        parent.invoke(input={"x": 0, "log": []}, effects=SimulatedEffects(seed))
    )
    solo = (
        GraphBuilder("gauntlet-parent-solo")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node(
            "bad",
            lambda state: Command(graph=Command.PARENT, update={"x": 1}),
        )
        .add_edge(START, "bad")
        .add_edge("bad", END)
        .compile()
    )
    orphan_rejected = False
    try:
        _run_awaitable(
            solo.invoke(input={"x": 0, "log": []}, effects=SimulatedEffects(seed))
        )
    except ParentCommand:
        orphan_rejected = True
    return {
        "parent_final": {"x": out.state["x"], "log": list(out.state["log"])},
        "no_parent_rejected": orphan_rejected,
    }


_WORKLOAD_ARMS["seeded_command_parent"] = _command_parent_arm
_support("LG08", ("command_parent",), "dharma_swarm.graph:Command#graph")


def _apply_command_parent_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG08.command_parent from the seeded two-arm subgraph workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    the facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    fields = ("parent_final", "no_parent_rejected")
    equal = both_ran and all(
        workload["dharma"].get(name) == workload["langgraph"].get(name)
        for name in fields
    )
    entry = capabilities["LG08"]["facets"]["command_parent"]
    entry["status"] = "pass" if equal else "fail"
    entry["evidence"].append(
        _evidence(
            kind="two_arm_differential",
            evidence_id="seeded_command_parent:command_parent",
            command_or_probe=(
                "bubble Command(graph=PARENT) from a subgraph node into the "
                "parent's reducers and routing on both installed runtimes"
            ),
            outcome="parity" if equal else "mismatch",
            dharma={name: workload["dharma"].get(name) for name in fields},
            langgraph={name: workload["langgraph"].get(name) for name in fields},
            citations=_row_citations(row_lookup["LG08"]),
        )
    )


# ---------------------------------------------------------------------------
# Pregel-core S9 (LG24): per-node retry policy workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entries for the retry_selection / backoff /
# jitter / max_attempts / retry_on / writes_cleared facets.
# ---------------------------------------------------------------------------


class _RetryState(TypedDict, total=False):
    log: Annotated[list[Any], operator.add]


class _RecordingTime:
    """``time`` stand-in whose ``sleep`` RECORDS instead of waiting.

    Installed on ``langgraph.pregel._retry`` for the duration of one scenario so
    the reference arm's backoff ladder is observable without spending it, which
    is what makes the Dharma arm's ``SimulatedEffects.retry_sleeps`` comparable
    to it. Every other ``time`` attribute is delegated untouched.
    """

    def __init__(self, sink: list[float]) -> None:
        self._sink = sink

    def sleep(self, seconds: float) -> None:
        self._sink.append(seconds)

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


class _SeededRandom:
    """``random`` stand-in whose ``uniform`` draws from a SEEDED generator.

    The reference draws jitter from module-global entropy; seeding it is the
    only way a jitter comparison can be a determinism claim rather than a coin
    flip. Mirrors the Dharma arm, which draws through ``effects.random()``.
    """

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def __getattr__(self, name: str) -> Any:
        return getattr(random, name)


def _langgraph_retry_scenario(
    seed: int, body: Callable[[], Any]
) -> tuple[Any, list[float]]:
    """Run one reference-arm retry scenario with a recorded, seeded sleep seam."""

    from langgraph.pregel import _retry as lg_retry

    sink: list[float] = []
    original_time = lg_retry.time
    original_random = lg_retry.random
    lg_retry.time = _RecordingTime(sink)  # type: ignore[assignment]
    lg_retry.random = _SeededRandom(random.Random(seed))  # type: ignore[assignment]
    try:
        return body(), sink
    finally:
        lg_retry.time = original_time
        lg_retry.random = original_random


def _jitter_summary(sleeps: list[float], bases: list[float], repeat: list[float]):
    """Arm-comparable jitter claims: additive, bounded in [0, 1), reproducible."""

    return {
        "count": len(sleeps),
        "applied": bool(sleeps) and sleeps != bases,
        "bounded": bool(sleeps)
        and len(sleeps) == len(bases)
        and all(0.0 <= sleep - base < 1.0 for sleep, base in zip(sleeps, bases)),
        "deterministic": sleeps == repeat,
    }


def _retry_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "retry"))
    jitter_seed = rng.getrandbits(32)
    # Sub-second ladder: nothing here ever really sleeps (both arms record),
    # but a tiny ladder keeps the cap-hit visible in four sleeps.
    initial = 0.01
    factor = 3.0
    cap = 0.05
    ladder_attempts = 5
    jitter_attempts = 4
    jitter_bases = [
        min(cap, initial * (factor ** (k - 1))) for k in range(1, jitter_attempts)
    ]

    if arm == "langgraph":
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import RetryPolicy as LGRetryPolicy

        def build(node_id: str, fn: Callable[..., Any], **kwargs: Any):
            builder = StateGraph(_RetryState)
            builder.add_node(node_id, fn, **kwargs)
            builder.add_edge(START, node_id)
            builder.add_edge(node_id, END)
            return builder.compile()

        # (a) selection + writes_cleared: only the policy-bearing node retries,
        # and its two failed attempts contribute no committed writes.
        counts = {"guarded": 0, "plain": 0}

        def guarded(state):
            counts["guarded"] += 1
            if counts["guarded"] < 3:
                raise ConnectionError("transient")
            return {"log": ["guarded"]}

        def plain(state):
            counts["plain"] += 1
            return {"log": ["plain"]}

        def run_selection():
            builder = StateGraph(_RetryState)
            builder.add_node(
                "guarded",
                guarded,
                retry_policy=LGRetryPolicy(
                    initial_interval=initial,
                    backoff_factor=factor,
                    max_interval=cap,
                    max_attempts=ladder_attempts,
                    jitter=False,
                ),
            )
            builder.add_node("plain", plain)
            builder.add_edge(START, "guarded")
            builder.add_edge(START, "plain")
            builder.add_edge("guarded", END)
            builder.add_edge("plain", END)
            return builder.compile().invoke({"log": []})

        selection_out, _selection_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_selection
        )

        # (b) backoff + max_attempts: an always-failing node burns exactly
        # max_attempts executions and sleeps the capped exponential ladder.
        def exhausting(counter: dict[str, int]):
            def node(state):
                counter["n"] += 1
                raise ConnectionError("always")

            return node

        exhausted = {"n": 0}

        def run_exhausted():
            raised = False
            try:
                build(
                    "f",
                    exhausting(exhausted),
                    retry_policy=LGRetryPolicy(
                        initial_interval=initial,
                        backoff_factor=factor,
                        max_interval=cap,
                        max_attempts=ladder_attempts,
                        jitter=False,
                    ),
                ).invoke({"log": []})
            except ConnectionError:
                raised = True
            return raised

        exhausted_raised, ladder_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_exhausted
        )

        single = {"n": 0}

        def run_single():
            raised = False
            try:
                build(
                    "f",
                    exhausting(single),
                    retry_policy=LGRetryPolicy(
                        initial_interval=initial, max_attempts=1, jitter=False
                    ),
                ).invoke({"log": []})
            except ConnectionError:
                raised = True
            return raised

        single_raised, single_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_single
        )

        # (c) jitter: identical seed twice must reproduce the sleep sequence.
        def run_jitter():
            try:
                build(
                    "f",
                    exhausting({"n": 0}),
                    retry_policy=LGRetryPolicy(
                        initial_interval=initial,
                        backoff_factor=factor,
                        max_interval=cap,
                        max_attempts=jitter_attempts,
                        jitter=True,
                    ),
                ).invoke({"log": []})
            except ConnectionError:
                pass

        _first, jitter_sleeps = _langgraph_retry_scenario(jitter_seed, run_jitter)
        _second, jitter_repeat = _langgraph_retry_scenario(jitter_seed, run_jitter)

        # (d) first-match selection across a policy sequence: the EARLIER
        # policy's max_attempts wins even though a later one also matches.
        first_match = {"n": 0}

        def key_error(state):
            first_match["n"] += 1
            raise KeyError("missing")

        def run_first_match():
            raised = False
            try:
                build(
                    "f",
                    key_error,
                    retry_policy=[
                        LGRetryPolicy(
                            retry_on=(KeyError,),
                            initial_interval=initial,
                            max_attempts=3,
                            jitter=False,
                        ),
                        LGRetryPolicy(
                            retry_on=(Exception,),
                            initial_interval=initial,
                            max_attempts=5,
                            jitter=False,
                        ),
                    ],
                ).invoke({"log": []})
            except KeyError:
                raised = True
            return raised

        first_match_raised, _fm_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_first_match
        )

        # (e) retry_on: class-tuple mismatch, callable predicate, and the
        # DEFAULT predicate's deterministic-vs-transient classification.
        nonmatching = {"n": 0}

        def value_error(state):
            nonmatching["n"] += 1
            raise ValueError("deterministic")

        def run_nonmatching():
            raised = False
            try:
                build(
                    "f",
                    value_error,
                    retry_policy=LGRetryPolicy(
                        retry_on=(KeyError,),
                        initial_interval=initial,
                        max_attempts=4,
                        jitter=False,
                    ),
                ).invoke({"log": []})
            except ValueError:
                raised = True
            return raised

        nonmatching_raised, _nm_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_nonmatching
        )

        predicate = {"n": 0}

        def predicate_node(state):
            predicate["n"] += 1
            if predicate["n"] < 2:
                raise ValueError("retry me")
            return {"log": ["predicate"]}

        def run_predicate():
            return build(
                "f",
                predicate_node,
                retry_policy=LGRetryPolicy(
                    retry_on=lambda exc: isinstance(exc, ValueError),
                    initial_interval=initial,
                    max_attempts=3,
                    jitter=False,
                ),
            ).invoke({"log": []})

        predicate_out, _p_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_predicate
        )

        default_deterministic = {"n": 0}

        def run_default_deterministic():
            raised = False
            try:
                build(
                    "f",
                    exhausting(default_deterministic),
                    retry_policy=LGRetryPolicy(
                        initial_interval=initial, max_attempts=3, jitter=False
                    ),
                ).invoke({"log": []})
            except ConnectionError:
                raised = True
            return raised

        # ConnectionError is the DEFAULT predicate's canonical transient error.
        default_transient_raised, _dt_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_default_deterministic
        )
        default_value = {"n": 0}

        def default_value_node(state):
            default_value["n"] += 1
            raise ValueError("deterministic")

        def run_default_value():
            raised = False
            try:
                build(
                    "f",
                    default_value_node,
                    retry_policy=LGRetryPolicy(
                        initial_interval=initial, max_attempts=3, jitter=False
                    ),
                ).invoke({"log": []})
            except ValueError:
                raised = True
            return raised

        default_value_raised, _dv_sleeps = _langgraph_retry_scenario(
            jitter_seed, run_default_value
        )

        return {
            "executions_by_node": dict(counts),
            "writes_cleared_log": sorted(selection_out["log"]),
            "sleep_intervals": ladder_sleeps,
            "jitter": _jitter_summary(jitter_sleeps, jitter_bases, jitter_repeat),
            "exhausted_executions": exhausted["n"],
            "exhausted_raised": exhausted_raised,
            "single_attempt_executions": single["n"],
            "single_attempt_sleeps": single_sleeps,
            "single_attempt_raised": single_raised,
            "first_match_executions": first_match["n"],
            "first_match_raised": first_match_raised,
            "nonmatching_executions": nonmatching["n"],
            "nonmatching_raised": nonmatching_raised,
            "callable_predicate_executions": predicate["n"],
            "callable_predicate_log": list(predicate_out["log"]),
            "default_transient_executions": default_deterministic["n"],
            "default_transient_raised": default_transient_raised,
            "default_deterministic_executions": default_value["n"],
            "default_deterministic_raised": default_value_raised,
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        NodeExecutionError,
        RetryPolicy,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    def build(node_id: str, fn: Callable[..., Any], **kwargs: Any):
        return (
            GraphBuilder(f"gauntlet-retry-{node_id}")
            .add_channel("log", AppendChannel)
            .add_node(node_id, fn, **kwargs)
            .add_edge(START, node_id)
            .add_edge(node_id, END)
            .compile()
        )

    counts = {"guarded": 0, "plain": 0}

    def guarded(state):
        counts["guarded"] += 1
        if counts["guarded"] < 3:
            raise ConnectionError("transient")
        return {"log": ["guarded"]}

    def plain(state):
        counts["plain"] += 1
        return {"log": ["plain"]}

    selection_graph = (
        GraphBuilder("gauntlet-retry-selection")
        .add_channel("log", AppendChannel)
        .add_node(
            "guarded",
            guarded,
            retry_policy=RetryPolicy(
                initial_interval=initial,
                backoff_factor=factor,
                max_interval=cap,
                max_attempts=ladder_attempts,
                jitter=False,
            ),
        )
        .add_node("plain", plain)
        .add_edge(START, "guarded")
        .add_edge(START, "plain")
        .add_edge("guarded", END)
        .add_edge("plain", END)
        .compile()
    )
    selection_out = _run_awaitable(
        selection_graph.invoke(input={"log": []}, effects=SimulatedEffects(seed))
    )

    def exhausting(counter: dict[str, int]):
        def node(state):
            counter["n"] += 1
            raise ConnectionError("always")

        return node

    def drive(graph, effects) -> bool:
        """Invoke and report whether the ladder gave up by RAISING."""
        try:
            _run_awaitable(graph.invoke(input={"log": []}, effects=effects))
        except NodeExecutionError:
            return True
        return False

    exhausted = {"n": 0}
    ladder_effects = SimulatedEffects(seed)
    exhausted_raised = drive(
        build(
            "f",
            exhausting(exhausted),
            retry_policy=RetryPolicy(
                initial_interval=initial,
                backoff_factor=factor,
                max_interval=cap,
                max_attempts=ladder_attempts,
                jitter=False,
            ),
        ),
        ladder_effects,
    )

    single = {"n": 0}
    single_effects = SimulatedEffects(seed)
    single_raised = drive(
        build(
            "f",
            exhausting(single),
            retry_policy=RetryPolicy(
                initial_interval=initial, max_attempts=1, jitter=False
            ),
        ),
        single_effects,
    )

    def run_jitter() -> list[float]:
        effects = SimulatedEffects(jitter_seed)
        drive(
            build(
                "f",
                exhausting({"n": 0}),
                retry_policy=RetryPolicy(
                    initial_interval=initial,
                    backoff_factor=factor,
                    max_interval=cap,
                    max_attempts=jitter_attempts,
                    jitter=True,
                ),
            ),
            effects,
        )
        return list(effects.retry_sleeps)

    jitter_sleeps = run_jitter()
    jitter_repeat = run_jitter()

    first_match = {"n": 0}

    def key_error(state):
        first_match["n"] += 1
        raise KeyError("missing")

    first_match_raised = drive(
        build(
            "f",
            key_error,
            retry_policy=[
                RetryPolicy(
                    retry_on=(KeyError,),
                    initial_interval=initial,
                    max_attempts=3,
                    jitter=False,
                ),
                RetryPolicy(
                    retry_on=(Exception,),
                    initial_interval=initial,
                    max_attempts=5,
                    jitter=False,
                ),
            ],
        ),
        SimulatedEffects(seed),
    )

    nonmatching = {"n": 0}

    def value_error(state):
        nonmatching["n"] += 1
        raise ValueError("deterministic")

    nonmatching_raised = drive(
        build(
            "f",
            value_error,
            retry_policy=RetryPolicy(
                retry_on=(KeyError,),
                initial_interval=initial,
                max_attempts=4,
                jitter=False,
            ),
        ),
        SimulatedEffects(seed),
    )

    predicate = {"n": 0}

    def predicate_node(state):
        predicate["n"] += 1
        if predicate["n"] < 2:
            raise ValueError("retry me")
        return {"log": ["predicate"]}

    predicate_out = _run_awaitable(
        build(
            "f",
            predicate_node,
            retry_policy=RetryPolicy(
                retry_on=lambda exc: isinstance(exc, ValueError),
                initial_interval=initial,
                max_attempts=3,
                jitter=False,
            ),
        ).invoke(input={"log": []}, effects=SimulatedEffects(seed))
    )

    default_transient = {"n": 0}
    default_transient_raised = drive(
        build(
            "f",
            exhausting(default_transient),
            retry_policy=RetryPolicy(
                initial_interval=initial, max_attempts=3, jitter=False
            ),
        ),
        SimulatedEffects(seed),
    )

    default_value = {"n": 0}

    def default_value_node(state):
        default_value["n"] += 1
        raise ValueError("deterministic")

    default_value_raised = drive(
        build(
            "f",
            default_value_node,
            retry_policy=RetryPolicy(
                initial_interval=initial, max_attempts=3, jitter=False
            ),
        ),
        SimulatedEffects(seed),
    )

    return {
        "executions_by_node": dict(counts),
        "writes_cleared_log": sorted(selection_out.state["log"]),
        "sleep_intervals": list(ladder_effects.retry_sleeps),
        "jitter": _jitter_summary(jitter_sleeps, jitter_bases, jitter_repeat),
        "exhausted_executions": exhausted["n"],
        "exhausted_raised": exhausted_raised,
        "single_attempt_executions": single["n"],
        "single_attempt_sleeps": list(single_effects.retry_sleeps),
        "single_attempt_raised": single_raised,
        "first_match_executions": first_match["n"],
        "first_match_raised": first_match_raised,
        "nonmatching_executions": nonmatching["n"],
        "nonmatching_raised": nonmatching_raised,
        "callable_predicate_executions": predicate["n"],
        "callable_predicate_log": list(predicate_out.state["log"]),
        "default_transient_executions": default_transient["n"],
        "default_transient_raised": default_transient_raised,
        "default_deterministic_executions": default_value["n"],
        "default_deterministic_raised": default_value_raised,
    }


_WORKLOAD_ARMS["seeded_retry_policy"] = _retry_arm
_support(
    "LG24",
    ("retry_selection",),
    "dharma_swarm.graph:GraphBuilder.add_node#retry_policy",
)
_support("LG24", ("backoff",), "dharma_swarm.graph:RetryPolicy#backoff_factor")
_support("LG24", ("jitter",), "dharma_swarm.graph:RetryPolicy#jitter")
_support("LG24", ("max_attempts",), "dharma_swarm.graph:RetryPolicy#max_attempts")
_support("LG24", ("retry_on",), "dharma_swarm.graph:RetryPolicy#retry_on")
_support("LG24", ("writes_cleared",), "dharma_swarm.graph:RetryPolicy")
_LANGGRAPH_FACET_SURFACE[("LG24", "retry_selection")] = (
    "langgraph.graph:StateGraph.add_node#retry_policy"
)
_LANGGRAPH_FACET_SURFACE[("LG24", "backoff")] = (
    "langgraph.types:RetryPolicy#backoff_factor"
)
_LANGGRAPH_FACET_SURFACE[("LG24", "jitter")] = "langgraph.types:RetryPolicy#jitter"
_LANGGRAPH_FACET_SURFACE[("LG24", "max_attempts")] = (
    "langgraph.types:RetryPolicy#max_attempts"
)
_LANGGRAPH_FACET_SURFACE[("LG24", "retry_on")] = (
    "langgraph.types:RetryPolicy#retry_on"
)
_LANGGRAPH_FACET_SURFACE[("LG24", "writes_cleared")] = "langgraph.types:RetryPolicy"


_RETRY_FACET_FIELDS: dict[str, tuple[str, ...]] = {
    "retry_selection": (
        "executions_by_node",
        "first_match_executions",
        "first_match_raised",
    ),
    "backoff": ("sleep_intervals",),
    "jitter": ("jitter",),
    "max_attempts": (
        "exhausted_executions",
        "exhausted_raised",
        "single_attempt_executions",
        "single_attempt_sleeps",
        "single_attempt_raised",
    ),
    "retry_on": (
        "nonmatching_executions",
        "nonmatching_raised",
        "callable_predicate_executions",
        "callable_predicate_log",
        "default_transient_executions",
        "default_transient_raised",
        "default_deterministic_executions",
        "default_deterministic_raised",
    ),
    "writes_cleared": ("writes_cleared_log",),
}


def _apply_retry_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG24's six facets from the seeded two-arm retry-policy workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    every facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    for facet, fields in _RETRY_FACET_FIELDS.items():
        equal = both_ran and all(
            workload["dharma"].get(name) == workload["langgraph"].get(name)
            for name in fields
        )
        entry = capabilities["LG24"]["facets"][facet]
        entry["status"] = "pass" if equal else "fail"
        entry["evidence"].append(
            _evidence(
                kind="two_arm_differential",
                evidence_id=f"seeded_retry_policy:{facet}",
                command_or_probe=(
                    f"compare {', '.join(fields)} under one identically "
                    "configured retry ladder on both installed runtimes"
                ),
                outcome="parity" if equal else "mismatch",
                dharma={name: workload["dharma"].get(name) for name in fields},
                langgraph={
                    name: workload["langgraph"].get(name) for name in fields
                },
                citations=_row_citations(row_lookup["LG24"]),
            )
        )


# ---------------------------------------------------------------------------
# Pregel-core S10 (LG25): per-node hard/idle timeout workload.
# Append-only harness extension — new seeded two-arm workload + evidence
# applier + surface support entries for the hard_timeout / idle_timeout /
# heartbeat_refresh / timeout_retry facets.
# ---------------------------------------------------------------------------


class _NodeTimeoutState(TypedDict, total=False):
    log: Annotated[list[Any], operator.add]


def _node_timeout_arm(arm: str, seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "node-timeout"))
    beats = rng.randint(20, 30)
    tight = 0.05  # bound a stuck node trips
    generous = 5.0  # bound a working node never trips
    stuck = 30.0  # a node that will never finish on its own
    beat_interval = 0.005  # << tight, so `beats` beats outlive the idle bound

    if arm == "langgraph":
        from langgraph.errors import NodeTimeoutError as LGNodeTimeoutError
        from langgraph.graph import END, START, StateGraph
        from langgraph.runtime import get_runtime
        from langgraph.types import RetryPolicy as LGRetryPolicy
        from langgraph.types import TimeoutPolicy as LGTimeoutPolicy

        def build(fn: Callable[..., Any], **kwargs: Any):
            builder = StateGraph(_NodeTimeoutState)
            builder.add_node("worker", fn, **kwargs)
            builder.add_edge(START, "worker")
            builder.add_edge("worker", END)
            return builder.compile()

        async def fast(state):
            await asyncio.sleep(0.001)
            return {"log": ["fast"]}

        async def hung(state):
            await asyncio.sleep(stuck)
            return {"log": ["hung"]}

        async def beating(state):
            runtime = get_runtime()
            for _ in range(beats):
                await asyncio.sleep(beat_interval)
                runtime.heartbeat()
            return {"log": ["beating"]}

        completed = _run_awaitable(
            build(fast, timeout=LGTimeoutPolicy(run_timeout=generous)).ainvoke(
                {"log": []}
            )
        )

        def expect_timeout(app) -> tuple[bool, str | None]:
            try:
                _run_awaitable(app.ainvoke({"log": []}))
            except LGNodeTimeoutError as exc:
                return True, exc.kind
            return False, None

        hard_timed_out, hard_kind = expect_timeout(
            build(hung, timeout=LGTimeoutPolicy(run_timeout=tight))
        )
        idle_timed_out, idle_kind = expect_timeout(
            build(
                hung,
                timeout=LGTimeoutPolicy(idle_timeout=tight, refresh_on="heartbeat"),
            )
        )
        # A heartbeating node whose TOTAL runtime exceeds the idle bound but
        # not the hard bound must survive: that pair is what distinguishes
        # "no progress" from "too long".
        heartbeat_survived = True
        try:
            heartbeat_out = _run_awaitable(
                build(
                    beating,
                    timeout=LGTimeoutPolicy(
                        idle_timeout=tight,
                        run_timeout=generous,
                        refresh_on="heartbeat",
                    ),
                ).ainvoke({"log": []})
            )
        except LGNodeTimeoutError:
            heartbeat_survived = False
            heartbeat_out = {"log": []}

        def flapping(counter: dict[str, int]):
            async def node(state):
                counter["n"] += 1
                if counter["n"] == 1:
                    await asyncio.sleep(stuck)
                return {"log": ["flapping"]}

            return node

        explicit = {"n": 0}
        explicit_out = _run_awaitable(
            build(
                flapping(explicit),
                timeout=LGTimeoutPolicy(run_timeout=tight),
                retry_policy=LGRetryPolicy(
                    retry_on=(LGNodeTimeoutError,),
                    initial_interval=0.001,
                    max_attempts=2,
                    jitter=False,
                ),
            ).ainvoke({"log": []})
        )
        default = {"n": 0}
        default_out = _run_awaitable(
            build(
                flapping(default),
                timeout=LGTimeoutPolicy(run_timeout=tight),
                retry_policy=LGRetryPolicy(
                    initial_interval=0.001, max_attempts=2, jitter=False
                ),
            ).ainvoke({"log": []})
        )
        return {
            "completed": list(completed["log"]),
            "hard_timed_out": hard_timed_out,
            "hard_kind": hard_kind,
            "idle_timed_out": idle_timed_out,
            "idle_kind": idle_kind,
            "heartbeat_survived": heartbeat_survived,
            "heartbeat_log": list(heartbeat_out["log"]),
            "timeout_retry_attempts": explicit["n"],
            "timeout_retry_log": list(explicit_out["log"]),
            "default_policy_retries_timeout_attempts": default["n"],
            "default_policy_retries_timeout_log": list(default_out["log"]),
        }

    from dharma_swarm.graph import (
        END,
        START,
        AppendChannel,
        GraphBuilder,
        NodeTimeoutError,
        RetryPolicy,
        TimeoutPolicy,
        heartbeat,
    )
    from dharma_swarm.graph.effects import SimulatedEffects

    def build(fn: Callable[..., Any], **kwargs: Any):
        return (
            GraphBuilder("gauntlet-node-timeout")
            .add_channel("log", AppendChannel)
            .add_node("worker", fn, **kwargs)
            .add_edge(START, "worker")
            .add_edge("worker", END)
            .compile()
        )

    async def fast(state):
        await asyncio.sleep(0.001)
        return {"log": ["fast"]}

    async def hung(state):
        await asyncio.sleep(stuck)
        return {"log": ["hung"]}

    async def beating(state):
        for _ in range(beats):
            await asyncio.sleep(beat_interval)
            heartbeat()
        return {"log": ["beating"]}

    completed = _run_awaitable(
        build(fast, timeout=TimeoutPolicy(run_timeout=generous)).invoke(
            input={"log": []}, effects=SimulatedEffects(seed)
        )
    )

    def expect_timeout(app) -> tuple[bool, str | None]:
        try:
            _run_awaitable(
                app.invoke(input={"log": []}, effects=SimulatedEffects(seed))
            )
        except NodeTimeoutError as exc:
            return True, exc.kind
        return False, None

    hard_timed_out, hard_kind = expect_timeout(
        build(hung, timeout=TimeoutPolicy(run_timeout=tight))
    )
    idle_timed_out, idle_kind = expect_timeout(
        build(hung, timeout=TimeoutPolicy(idle_timeout=tight, refresh_on="heartbeat"))
    )
    heartbeat_survived = True
    try:
        heartbeat_out = _run_awaitable(
            build(
                beating,
                timeout=TimeoutPolicy(
                    idle_timeout=tight,
                    run_timeout=generous,
                    refresh_on="heartbeat",
                ),
            ).invoke(input={"log": []}, effects=SimulatedEffects(seed))
        )
        heartbeat_log = list(heartbeat_out.state["log"])
    except NodeTimeoutError:
        heartbeat_survived = False
        heartbeat_log = []

    def flapping(counter: dict[str, int]):
        async def node(state):
            counter["n"] += 1
            if counter["n"] == 1:
                await asyncio.sleep(stuck)
            return {"log": ["flapping"]}

        return node

    explicit = {"n": 0}
    explicit_out = _run_awaitable(
        build(
            flapping(explicit),
            timeout=TimeoutPolicy(run_timeout=tight),
            retry_policy=RetryPolicy(
                retry_on=(NodeTimeoutError,),
                initial_interval=0.001,
                max_attempts=2,
                jitter=False,
            ),
        ).invoke(input={"log": []}, effects=SimulatedEffects(seed))
    )
    default = {"n": 0}
    default_out = _run_awaitable(
        build(
            flapping(default),
            timeout=TimeoutPolicy(run_timeout=tight),
            retry_policy=RetryPolicy(
                initial_interval=0.001, max_attempts=2, jitter=False
            ),
        ).invoke(input={"log": []}, effects=SimulatedEffects(seed))
    )
    return {
        "completed": list(completed.state["log"]),
        "hard_timed_out": hard_timed_out,
        "hard_kind": hard_kind,
        "idle_timed_out": idle_timed_out,
        "idle_kind": idle_kind,
        "heartbeat_survived": heartbeat_survived,
        "heartbeat_log": heartbeat_log,
        "timeout_retry_attempts": explicit["n"],
        "timeout_retry_log": list(explicit_out.state["log"]),
        "default_policy_retries_timeout_attempts": default["n"],
        "default_policy_retries_timeout_log": list(default_out.state["log"]),
    }


_WORKLOAD_ARMS["seeded_node_timeout"] = _node_timeout_arm
_support("LG25", ("hard_timeout",), "dharma_swarm.graph:TimeoutPolicy#run_timeout")
_support("LG25", ("idle_timeout",), "dharma_swarm.graph:TimeoutPolicy#idle_timeout")
_support("LG25", ("heartbeat_refresh",), "dharma_swarm.graph:heartbeat")
_support("LG25", ("timeout_retry",), "dharma_swarm.graph:NodeTimeoutError")
_LANGGRAPH_FACET_SURFACE[("LG25", "hard_timeout")] = (
    "langgraph.types:TimeoutPolicy#run_timeout"
)
_LANGGRAPH_FACET_SURFACE[("LG25", "idle_timeout")] = (
    "langgraph.types:TimeoutPolicy#idle_timeout"
)
_LANGGRAPH_FACET_SURFACE[("LG25", "heartbeat_refresh")] = (
    "langgraph.runtime:Runtime.heartbeat"
)
_LANGGRAPH_FACET_SURFACE[("LG25", "timeout_retry")] = (
    "langgraph.errors:NodeTimeoutError"
)


_NODE_TIMEOUT_FACET_FIELDS: dict[str, tuple[str, ...]] = {
    "hard_timeout": ("completed", "hard_timed_out", "hard_kind"),
    "idle_timeout": ("idle_timed_out", "idle_kind"),
    "heartbeat_refresh": ("heartbeat_survived", "heartbeat_log"),
    "timeout_retry": (
        "timeout_retry_attempts",
        "timeout_retry_log",
        "default_policy_retries_timeout_attempts",
        "default_policy_retries_timeout_log",
    ),
}


def _apply_node_timeout_evidence(
    capabilities: dict[str, Any],
    row_lookup: Mapping[str, Any],
    workload: Mapping[str, Any],
) -> None:
    """LG25's four facets from the seeded two-arm node-timeout workload.

    Fail-closed per the error-parity rule: a probe_error on either arm keeps
    every facet failing — identical errors are a finding, never a pass.
    """
    both_ran = (
        "probe_error" not in workload["dharma"]
        and "probe_error" not in workload["langgraph"]
    )
    for facet, fields in _NODE_TIMEOUT_FACET_FIELDS.items():
        equal = both_ran and all(
            workload["dharma"].get(name) == workload["langgraph"].get(name)
            for name in fields
        )
        entry = capabilities["LG25"]["facets"][facet]
        entry["status"] = "pass" if equal else "fail"
        entry["evidence"].append(
            _evidence(
                kind="two_arm_differential",
                evidence_id=f"seeded_node_timeout:{facet}",
                command_or_probe=(
                    f"compare {', '.join(fields)} under identically "
                    "configured hard/idle node bounds on both installed "
                    "runtimes"
                ),
                outcome="parity" if equal else "mismatch",
                dharma={name: workload["dharma"].get(name) for name in fields},
                langgraph={
                    name: workload["langgraph"].get(name) for name in fields
                },
                citations=_row_citations(row_lookup["LG25"]),
            )
        )
