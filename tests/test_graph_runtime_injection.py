"""LG30 unit coverage: config, context, runtime injection, and propagation.

One named test per frozen LG30 facet (``runnable_config``,
``context_schema``, ``runtime_injection``, ``execution_info``,
``get_runtime``, ``get_config``, ``get_store``, ``stream_writer``,
``propagation``) plus the fail-closed and isolation invariants the facets
depend on. Behavior pinned here was verified against installed LangGraph
1.2.4 by the gauntlet's ``seeded_runtime_config_injection`` two-arm arm; the
assertions below are the engine-local restatement of that parity.
"""

from __future__ import annotations

import asyncio
import operator
from dataclasses import dataclass
from typing import Annotated, Any, Mapping, TypedDict

import pytest

from dharma_swarm.graph import (
    END,
    START,
    AppendChannel,
    ExecutionInfo,
    GraphBuilder,
    GraphRuntime,
    InMemoryKVStore,
    LastValueChannel,
    RuntimeAccessError,
    TypedStateGraph,
    get_config,
    get_runtime,
    get_store,
    get_stream_writer,
)
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.store import StoreNamespaceError

SEED = 20260805


class _TypedState(TypedDict, total=False):
    """State schema for the typed front door (LG01 channels, LG30 runtime)."""

    x: int
    log: Annotated[list[Any], operator.add]


@dataclass
class Ctx:
    """Per-invoke runtime context (never state, never checkpointed)."""

    multiplier: int
    label: str


def _graph(*nodes: tuple[str, Any], graph_id: str = "runtime-test"):
    """Compile a linear graph over ``x`` (last-value) and ``log`` (append)."""
    builder = (
        GraphBuilder(graph_id)
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
    )
    previous = START
    for node_id, fn in nodes:
        builder.add_node(node_id, fn)
        builder.add_edge(previous, node_id)
        previous = node_id
    builder.add_edge(previous, END)
    return builder.compile()


def _run(compiled, **kwargs):
    return asyncio.run(
        compiled.invoke(effects=SimulatedEffects(SEED), **kwargs)
    )


# --------------------------------------------------------------------------
# facet: runnable_config
# --------------------------------------------------------------------------


def test_runnable_config_reaches_nodes_with_configurable_shape() -> None:
    """invoke(config=...) is visible in-node with RunnableConfig shape."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["config"] = dict(get_config())
        return {"log": ["node"]}

    _run(
        _graph(("node", node)),
        input={"x": 1, "log": []},
        config={"configurable": {"tenant": "dharma", "attempt": 3}},
    )

    config = seen["config"]
    # langgraph 1.2.4 hands nodes callbacks/configurable/metadata (empirical).
    assert {"callbacks", "configurable", "metadata"} <= set(config)
    assert config["configurable"]["tenant"] == "dharma"
    assert config["configurable"]["attempt"] == 3


def test_runnable_config_merges_the_persisted_thread_id(tmp_path) -> None:
    """A persisted run's thread_id lands in configurable for node code.

    ``thread_id`` is only accepted alongside a persistence kernel (the engine
    rejects one without the other), which is also the only situation in which
    langgraph populates a thread id.
    """
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["thread_id"] = get_config()["configurable"]["thread_id"]
        return {"log": ["node"]}

    _run(
        _graph(("node", node)),
        input={"x": 1, "log": []},
        config={"configurable": {"tenant": "dharma"}},
        persistence=GraphPersistenceKernel(tmp_path / "kernel.json"),
        thread_id="thread-a",
    )
    assert seen["thread_id"] == "thread-a"


def test_runnable_config_explicit_thread_id_is_not_overwritten(tmp_path) -> None:
    """An explicit configurable.thread_id wins over the invoke's thread_id."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["thread_id"] = get_config()["configurable"]["thread_id"]
        return {"log": ["node"]}

    _run(
        _graph(("node", node)),
        input={"x": 1, "log": []},
        config={"configurable": {"thread_id": "caller-wins"}},
        persistence=GraphPersistenceKernel(tmp_path / "kernel.json"),
        thread_id="invoke-loses",
    )
    assert seen["thread_id"] == "caller-wins"


def test_runnable_config_defaults_to_empty_configurable() -> None:
    """No config passed still yields a usable configurable mapping."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["configurable"] = dict(get_config()["configurable"])
        return {"log": ["node"]}

    _run(_graph(("node", node)), input={"x": 1, "log": []})
    assert seen["configurable"] == {}


def test_runnable_config_rejects_non_mapping_fail_closed() -> None:
    """A malformed config fails closed rather than reaching node code."""
    with pytest.raises(RuntimeAccessError):
        _run(
            _graph(("node", lambda state: {"log": ["node"]})),
            input={"x": 1, "log": []},
            config=["not", "a", "mapping"],
        )


# --------------------------------------------------------------------------
# facet: context_schema
# --------------------------------------------------------------------------


def test_context_schema_declaration_reaches_runtime_accessors() -> None:
    """A TypedStateGraph context declaration is readable via get_runtime()."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["context"] = get_runtime().context
        return {"x": state["x"] * get_runtime().context.multiplier, "log": ["n"]}

    typed = (
        TypedStateGraph(_TypedState, context=Ctx, graph_id="ctx-graph")
        .add_node("n", node)
        .add_edge(START, "n")
        .add_edge("n", END)
        .compile()
    )
    result = asyncio.run(
        typed.invoke(
            input={"x": 4, "log": []},
            context=Ctx(multiplier=3, label="L"),
            effects=SimulatedEffects(SEED),
        )
    )
    assert seen["context"].label == "L"
    assert result.state["x"] == 12


def test_context_schema_declared_but_absent_context_is_none_not_error() -> None:
    """Declared-but-unpassed context yields None (langgraph 1.2.4 parity)."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["context"] = get_runtime().context
        return {"log": ["n"]}

    typed = (
        TypedStateGraph(_TypedState, context=Ctx, graph_id="ctx-absent")
        .add_node("n", node)
        .add_edge(START, "n")
        .add_edge("n", END)
        .compile()
    )
    asyncio.run(
        typed.invoke(input={"x": 1, "log": []}, effects=SimulatedEffects(SEED))
    )
    assert seen["context"] is None


def test_context_is_never_written_into_state() -> None:
    """Context is injection, not state: it never appears in committed state."""
    result = _run(
        _graph(("node", lambda state: {"log": ["node"]})),
        input={"x": 1, "log": []},
        context=Ctx(multiplier=9, label="hidden"),
    )
    assert set(result.state) == {"x", "log"}
    assert "hidden" not in str(result.state)


def test_context_does_not_change_committed_digest() -> None:
    """Passing injection kwargs cannot alter a committed trace."""
    without = _run(
        _graph(("node", lambda state: {"x": state["x"] + 1, "log": ["node"]})),
        input={"x": 1, "log": []},
    )
    with_injection = _run(
        _graph(("node", lambda state: {"x": state["x"] + 1, "log": ["node"]})),
        input={"x": 1, "log": []},
        context=Ctx(multiplier=9, label="L"),
        config={"configurable": {"k": "v"}},
        store=InMemoryKVStore(),
        stream_writer=lambda chunk: None,
    )
    assert without.state_digest == with_injection.state_digest


# --------------------------------------------------------------------------
# facet: runtime_injection
# --------------------------------------------------------------------------


def test_runtime_injection_delivers_every_declared_field() -> None:
    """One GraphRuntime carries context, store, writer, previous, exec info."""
    store = InMemoryKVStore()
    chunks: list[Any] = []
    seen: dict[str, Any] = {}

    def writer(chunk: Any) -> None:
        chunks.append(chunk)

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        runtime = get_runtime()
        seen["runtime"] = runtime
        seen["store_is_same_object"] = runtime.store is store
        seen["writer_is_same_object"] = runtime.stream_writer is writer
        seen["writer_matches_accessor"] = (
            runtime.stream_writer is get_stream_writer()
        )
        return {"log": ["node"]}

    _run(
        _graph(("node", node)),
        input={"x": 1, "log": []},
        context=Ctx(multiplier=2, label="L"),
        store=store,
        stream_writer=writer,
        previous="prior-output",
    )

    runtime = seen["runtime"]
    assert isinstance(runtime, GraphRuntime)
    assert runtime.context.label == "L"
    assert seen["store_is_same_object"] is True
    assert seen["writer_is_same_object"] is True
    assert seen["writer_matches_accessor"] is True
    # previous is the functional-entrypoint field; it is passed through as-is.
    assert runtime.previous == "prior-output"
    assert isinstance(runtime.execution_info, ExecutionInfo)


def test_runtime_injection_is_isolated_between_concurrent_siblings() -> None:
    """Concurrent tasks of one superstep never see each other's runtime."""
    observed: dict[str, str] = {}

    def make(node_id: str):
        def node(state: Mapping[str, Any]) -> dict[str, Any]:
            observed[node_id] = get_runtime().execution_info.node_id
            return {"log": [node_id]}

        return node

    # Two independent branches from START run in the same superstep.
    compiled = (
        GraphBuilder("sibling-isolation")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("left", make("left"))
        .add_node("right", make("right"))
        .add_edge(START, "left")
        .add_edge(START, "right")
        .add_edge("left", END)
        .add_edge("right", END)
        .compile()
    )
    _run(compiled, input={"x": 1, "log": []})
    assert observed == {"left": "left", "right": "right"}


# --------------------------------------------------------------------------
# facet: execution_info
# --------------------------------------------------------------------------


def test_execution_info_identifies_the_running_task() -> None:
    """ExecutionInfo names the run, node, task_seq, superstep and attempt."""
    seen: dict[str, ExecutionInfo] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["info"] = get_runtime().execution_info
        return {"log": ["node"]}

    _run(
        _graph(("node", node)),
        input={"x": 1, "log": []},
        graph_run_id="run-fixed",
    )

    info = seen["info"]
    assert info.run_id == "run-fixed"
    assert info.node_id == "node"
    assert info.task_seq == 0
    assert info.superstep == 1
    assert info.node_attempt == 1
    assert len(info.task_id) == 32


def test_execution_info_task_id_is_stable_and_task_scoped() -> None:
    """task_id is deterministic per identity and distinct across tasks."""
    ids: dict[str, str] = {}

    def make(node_id: str):
        def node(state: Mapping[str, Any]) -> dict[str, Any]:
            first = get_runtime().execution_info.task_id
            second = get_runtime().execution_info.task_id
            assert first == second  # stable within one task
            ids[node_id] = first
            return {"log": [node_id]}

        return node

    _run(
        _graph(("a", make("a")), ("b", make("b"))),
        input={"x": 1, "log": []},
        graph_run_id="run-fixed",
    )
    assert ids["a"] != ids["b"]
    # Deterministic: recomputing the identity reproduces the digest.
    assert (
        ExecutionInfo(
            run_id="run-fixed", node_id="a", task_seq=0, superstep=1
        ).task_id
        == ids["a"]
    )


def test_execution_info_is_frozen() -> None:
    """ExecutionInfo is read-only metadata, not a mutable scratchpad."""
    info = ExecutionInfo(run_id="r", node_id="n")
    with pytest.raises(Exception):
        info.node_id = "other"  # type: ignore[misc]


# --------------------------------------------------------------------------
# facet: get_runtime / get_config / get_store / get_stream_writer
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "accessor",
    [get_runtime, get_config, get_store, get_stream_writer],
    ids=["get_runtime", "get_config", "get_store", "get_stream_writer"],
)
def test_accessors_fail_closed_outside_a_running_node(accessor) -> None:
    """All four accessors raise outside a task (langgraph raises RuntimeError).

    RuntimeAccessError subclasses GraphRuntimeError -> RuntimeError, so
    ``except RuntimeError`` behaves identically against either engine.
    """
    with pytest.raises(RuntimeAccessError):
        accessor()
    with pytest.raises(RuntimeError):
        accessor()


def test_accessors_do_not_leak_after_the_run_completes() -> None:
    """The runtime unbinds when the task ends, even across a whole run."""
    _run(
        _graph(("node", lambda state: {"log": ["node"]})),
        input={"x": 1, "log": []},
        context=Ctx(multiplier=1, label="L"),
    )
    with pytest.raises(RuntimeAccessError):
        get_runtime()


def test_accessors_unbind_when_a_node_raises() -> None:
    """A failing node still unbinds its runtime (finally-scoped)."""

    def boom(state: Mapping[str, Any]) -> dict[str, Any]:
        raise ValueError("boom")

    with pytest.raises(RuntimeError):
        _run(_graph(("boom", boom)), input={"x": 1, "log": []})
    with pytest.raises(RuntimeAccessError):
        get_runtime()


def test_get_store_returns_none_when_the_run_carried_no_store() -> None:
    """No store injected yields None in-node, not an error (parity)."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        seen["store"] = get_store()
        return {"log": ["node"]}

    _run(_graph(("node", node)), input={"x": 1, "log": []})
    assert seen["store"] is None


def test_get_store_round_trips_and_searches() -> None:
    """The injected store is the caller's object; get/put/search/delete work."""
    store = InMemoryKVStore()
    found: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        live = get_store()
        live.put(("memories", "u1"), "a", {"v": 1})
        live.put(("memories", "u1"), "b", {"v": 2})
        found["get"] = live.get(("memories", "u1"), "a").value
        found["search"] = [item.key for item in live.search(("memories",))]
        found["filtered"] = [
            item.key for item in live.search(("memories",), filter={"v": 2})
        ]
        found["limited"] = [
            item.key for item in live.search(("memories",), limit=1)
        ]
        live.delete(("memories", "u1"), "a")
        found["after_delete"] = live.get(("memories", "u1"), "a")
        return {"log": ["node"]}

    _run(_graph(("node", node)), input={"x": 1, "log": []}, store=store)

    assert found["get"] == {"v": 1}
    assert found["search"] == ["a", "b"]  # deterministic (namespace, key) order
    assert found["filtered"] == ["b"]
    assert found["limited"] == ["a"]
    assert found["after_delete"] is None
    # Writes persist on the caller's object after the run.
    assert store.get(("memories", "u1"), "b").value == {"v": 2}


def test_store_returns_snapshots_not_live_aliases() -> None:
    """Mutating a returned value cannot corrupt stored state."""
    store = InMemoryKVStore()
    store.put(("ns",), "k", {"v": 1})
    item = store.get(("ns",), "k")
    dict(item.value)["v"] = 99  # mutate a copy
    fetched = store.get(("ns",), "k")
    assert fetched.value == {"v": 1}
    assert fetched.value is not item.value


@pytest.mark.parametrize("namespace", [(), ("",), ("ok", "")])
def test_store_rejects_malformed_namespaces_fail_closed(namespace) -> None:
    """Empty namespaces/segments fail closed rather than collapsing keys."""
    store = InMemoryKVStore()
    with pytest.raises(StoreNamespaceError):
        store.put(namespace, "k", {"v": 1})


def test_store_rejects_non_mapping_values_fail_closed() -> None:
    store = InMemoryKVStore()
    with pytest.raises(StoreNamespaceError):
        store.put(("ns",), "k", ["not", "a", "mapping"])


# --------------------------------------------------------------------------
# facet: stream_writer
# --------------------------------------------------------------------------


def test_stream_writer_emits_custom_chunks_in_node_order() -> None:
    """Nodes emit custom chunks to the caller's writer, in execution order."""
    chunks: list[Any] = []

    def first(state: Mapping[str, Any]) -> dict[str, Any]:
        get_stream_writer()({"stage": "first", "x": state["x"]})
        return {"x": state["x"] + 1, "log": ["first"]}

    def second(state: Mapping[str, Any]) -> dict[str, Any]:
        get_stream_writer()({"stage": "second", "x": state["x"]})
        return {"log": ["second"]}

    _run(
        _graph(("first", first), ("second", second)),
        input={"x": 1, "log": []},
        stream_writer=chunks.append,
    )
    assert chunks == [
        {"stage": "first", "x": 1},
        {"stage": "second", "x": 2},
    ]


def test_stream_writer_defaults_to_a_noop_never_none() -> None:
    """Nodes may always call the writer; an absent writer discards silently."""
    seen: dict[str, Any] = {}

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        writer = get_stream_writer()
        seen["callable"] = callable(writer)
        seen["returned"] = writer({"ignored": True})
        return {"log": ["node"]}

    _run(_graph(("node", node)), input={"x": 1, "log": []})
    assert seen["callable"] is True
    assert seen["returned"] is None


# --------------------------------------------------------------------------
# facet: propagation
# --------------------------------------------------------------------------


def test_propagation_across_supersteps_shares_context_and_store() -> None:
    """Every node of a run sees one context and one store, across supersteps."""
    store = InMemoryKVStore()
    observed: dict[str, Any] = {}

    def upstream(state: Mapping[str, Any]) -> dict[str, Any]:
        get_store().put(("relay",), "token", {"v": state["x"]})
        return {"x": state["x"] * get_runtime().context.multiplier, "log": ["up"]}

    def downstream(state: Mapping[str, Any]) -> dict[str, Any]:
        runtime = get_runtime()
        observed["label"] = runtime.context.label
        observed["relayed"] = get_store().get(("relay",), "token").value["v"]
        observed["config_token"] = get_config()["configurable"]["token"]
        observed["node_id"] = runtime.execution_info.node_id
        observed["superstep"] = runtime.execution_info.superstep
        return {"log": ["down"]}

    result = _run(
        _graph(("up", upstream), ("down", downstream)),
        input={"x": 5, "log": []},
        context=Ctx(multiplier=3, label="shared"),
        store=store,
        config={"configurable": {"token": "t-1"}},
    )

    assert observed["label"] == "shared"
    assert observed["relayed"] == 5  # written upstream, read a superstep later
    assert observed["config_token"] == "t-1"
    assert observed["node_id"] == "down"
    assert observed["superstep"] == 2  # distinct superstep from upstream
    assert result.state["x"] == 15
    assert list(result.state["log"]) == ["up", "down"]


def test_propagation_reaches_send_push_tasks() -> None:
    """Send-driven (PUSH) tasks receive the runtime with their own identity."""
    from dharma_swarm.graph import Send

    observed: list[tuple[str, int]] = []

    def fan(state: Mapping[str, Any]) -> Any:
        return {"log": ["fan"]}

    def worker(payload: Mapping[str, Any]) -> dict[str, Any]:
        info = get_runtime().execution_info
        observed.append((info.node_id, info.task_seq))
        return {"log": [f"worker{payload['i']}:{get_runtime().context.label}"]}

    compiled = (
        GraphBuilder("push-propagation")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("fan", fan)
        .add_node("worker", worker)
        .add_conditional_edges(
            "fan",
            lambda state: [Send("worker", {"i": i}) for i in (1, 2)],
            ["worker"],
        )
        .add_edge(START, "fan")
        .add_edge("worker", END)
        .compile()
    )
    result = _run(
        compiled,
        input={"x": 1, "log": []},
        context=Ctx(multiplier=1, label="pushed"),
    )

    # PUSH tasks are seq 1..N; each got its own ExecutionInfo.
    assert sorted(observed) == [("worker", 1), ("worker", 2)]
    log = list(result.state["log"])
    assert "worker1:pushed" in log
    assert "worker2:pushed" in log


# --------------------------------------------------------------------------
# supporting types
# --------------------------------------------------------------------------


def test_graph_runtime_for_task_refines_only_execution_info() -> None:
    """for_task() is a pure refinement: nothing else about the runtime moves."""
    store = InMemoryKVStore()
    template = GraphRuntime(
        context=Ctx(multiplier=2, label="L"),
        store=store,
        config={"configurable": {"k": "v"}},
    )
    bound = template.for_task(
        run_id="r", node_id="n", task_seq=2, superstep=4
    )
    assert template.execution_info is None
    assert bound.context is template.context
    assert bound.store is store
    assert bound.config == template.config
    assert bound.execution_info == ExecutionInfo(
        run_id="r", node_id="n", task_seq=2, superstep=4
    )
