"""Falsification tests for DharmaGraph thread persistence/resume kernel."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from dharma_swarm.graph import (
    END,
    START,
    AppendChannel,
    GraphBuilder,
    GraphPersistenceKernel,
    JsonGraphSerializer,
    LastValueChannel,
)
from dharma_swarm.graph.types import RunCheckpoint


def _linear_graph():
    return (
        GraphBuilder("persist-linear")
        .add_channel("x", LastValueChannel)
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"x": state["x"] + 2, "log": ["a"]})
        .add_node("b", lambda state: {"x": state["x"] * 3, "log": ["b"]})
        .add_node("c", lambda state: {"x": state["x"] - 1, "log": ["c"]})
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", "c")
        .add_edge("c", END)
        .compile()
    )


def _stop_after(superstep: int):
    class StopAfterCheckpoint(Exception):
        pass

    def callback(checkpoint):
        if checkpoint.superstep == superstep:
            raise StopAfterCheckpoint

    return StopAfterCheckpoint, callback


class CountingSerializer(JsonGraphSerializer):
    def __init__(self):
        self.dumps_count = 0
        self.loads_count = 0

    def dumps_typed(self, obj):
        self.dumps_count += 1
        return super().dumps_typed(obj)

    def loads_typed(self, data):
        self.loads_count += 1
        return super().loads_typed(data)


def _fixture_checkpoint(suffix: str) -> RunCheckpoint:
    return RunCheckpoint(
        graph_run_id=f"run-{suffix}",
        graph_id="concurrency-fixture",
        superstep=0,
        state_digest=suffix * 64,
        channels={"x": {"value": suffix, "version": 1}},
        versions_seen={},
    )


def test_concurrent_kernel_instances_preserve_every_checkpoint(tmp_path):
    left = GraphPersistenceKernel(tmp_path / "kernel")
    right = GraphPersistenceKernel(tmp_path / "kernel")
    barrier = Barrier(2)

    def put_after_barrier(kernel, suffix):
        barrier.wait(timeout=5)
        return kernel.put_run_checkpoint(
            "shared-thread",
            _fixture_checkpoint(suffix),
            checkpoint_id=f"cp-{suffix}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(put_after_barrier, left, "a"),
            pool.submit(put_after_barrier, right, "b"),
        )
        for future in futures:
            future.result(timeout=10)

    history = GraphPersistenceKernel(tmp_path / "kernel").get_state_history(
        "shared-thread"
    )
    assert {record.checkpoint_id for record in history} == {"cp-a", "cp-b"}


def test_concurrent_update_state_serializes_base_derivation_and_append(tmp_path):
    """Two latest-state updates must compose, never become lossy siblings."""
    root = tmp_path / "kernel"
    seed = GraphPersistenceKernel(root)
    seed.put_run_checkpoint(
        "shared-thread",
        RunCheckpoint(
            graph_run_id="run-shared",
            graph_id="concurrency-update-fixture",
            superstep=0,
            state_digest="a" * 64,
            channels={"seed": {"value": 0, "version": 1}},
            versions_seen={},
        ),
        checkpoint_id="cp-root",
    )
    left = GraphPersistenceKernel(root)
    right = GraphPersistenceKernel(root)
    stale_read_barrier = Barrier(2)
    legacy_prelock_reads: list[str] = []

    # This seam makes the old implementation deterministically read the same
    # base before either append. The fixed implementation bypasses the
    # pre-lock public read and resolves latest state inside the mutation lock.
    for kernel in (left, right):
        original = kernel.get_checkpoint_record

        def synchronized_get(
            thread_id,
            checkpoint_id=None,
            *,
            original=original,
        ):
            record = original(thread_id, checkpoint_id)
            legacy_prelock_reads.append(thread_id)
            stale_read_barrier.wait(timeout=5)
            return record

        kernel.get_checkpoint_record = synchronized_get  # type: ignore[method-assign]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(left.update_state, "shared-thread", {"left": 1}),
            pool.submit(right.update_state, "shared-thread", {"right": 2}),
        )
        for future in futures:
            future.result(timeout=10)

    history = GraphPersistenceKernel(root).get_state_history("shared-thread")
    assert history[-1].state == {"seed": 0, "left": 1, "right": 2}
    assert legacy_prelock_reads == []
    assert len(history) == 3
    assert history[-1].parent_checkpoint_id == history[-2].checkpoint_id
    assert history[-2].parent_checkpoint_id == "cp-root"


def test_concurrent_processes_preserve_every_checkpoint(tmp_path):
    program = r"""
import sys
import time
from pathlib import Path
from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.types import RunCheckpoint

root, suffix = Path(sys.argv[1]), sys.argv[2]
kernel = GraphPersistenceKernel(root)
checkpoint = RunCheckpoint(
    f"run-{suffix}", "process-fixture", 0, suffix * 64,
    {"x": {"value": suffix, "version": 1}}, {}
)
(root / f"ready-{suffix}").write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 5
while len(list(root.glob("ready-*"))) < 2:
    if time.monotonic() >= deadline:
        raise TimeoutError("peer process did not reach concurrent start")
    time.sleep(0.01)
kernel.put_run_checkpoint("shared-thread", checkpoint, checkpoint_id=f"cp-{suffix}")
"""
    root = tmp_path / "kernel"
    root.mkdir()
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", program, str(root), suffix],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for suffix in ("a", "b")
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, f"stdout={stdout}\nstderr={stderr}"

    history = GraphPersistenceKernel(root).get_state_history("shared-thread")
    assert {record.checkpoint_id for record in history} == {"cp-a", "cp-b"}


def test_checkpoint_and_pending_write_mutations_share_one_lock(tmp_path):
    left = GraphPersistenceKernel(tmp_path / "kernel")
    right = GraphPersistenceKernel(tmp_path / "kernel")
    write_entered = Event()
    release_write = Event()
    pending_started = Event()
    original_write = left._write_thread

    def paused_write(thread_id, state):
        write_entered.set()
        assert release_write.wait(timeout=5)
        original_write(thread_id, state)

    left._write_thread = paused_write  # type: ignore[method-assign]

    def add_pending_write():
        pending_started.set()
        right.put_writes("shared-thread", [("x", 2)], "task-pending")

    with ThreadPoolExecutor(max_workers=2) as pool:
        checkpoint_future = pool.submit(
            left.put_run_checkpoint,
            "shared-thread",
            _fixture_checkpoint("a"),
            checkpoint_id="cp-a",
        )
        assert write_entered.wait(timeout=5)
        pending_future = pool.submit(add_pending_write)
        assert pending_started.wait(timeout=5)
        assert not pending_future.done()
        release_write.set()
        checkpoint_future.result(timeout=10)
        pending_future.result(timeout=10)

    reopened = GraphPersistenceKernel(tmp_path / "kernel")
    assert [
        record.checkpoint_id
        for record in reopened.get_state_history("shared-thread")
    ] == ["cp-a"]
    assert [
        write.task_id for write in reopened.recover_pending_writes("shared-thread")
    ] == ["task-pending"]


def test_fork_does_not_alias_nested_checkpoint_state():
    parent = RunCheckpoint(
        "parent",
        "fork-fixture",
        0,
        "a" * 64,
        {"x": {"value": 1, "version": 1}},
        {"node": {"x": 1}},
    )

    child = parent.fork("child")
    child.channels["x"]["value"] = 99  # type: ignore[index]
    child.versions_seen["node"]["x"] = 99  # type: ignore[index]

    assert parent.channels["x"]["value"] == 1
    assert parent.versions_seen["node"]["x"] == 1


def test_thread_resume_checkpoint_ids_and_lineage(tmp_path):
    kernel = GraphPersistenceKernel(tmp_path / "kernel")
    compiled = _linear_graph()
    stopper, callback = _stop_after(1)
    with pytest.raises(stopper):
        asyncio.run(
            compiled.invoke(
                {"x": 4, "log": []},
                graph_run_id="run-thread",
                persistence=kernel,
                thread_id="thread-a",
                on_checkpoint=callback,
            )
        )

    history = kernel.get_state_history("thread-a")
    assert [record.superstep for record in history] == [0, 1]
    assert history[1].parent_checkpoint_id == history[0].checkpoint_id
    assert history[1].state == {"log": ["a"], "x": 6}

    result = asyncio.run(
        compiled.invoke(
            input=None,
            persistence=kernel,
            thread_id="thread-a",
            checkpoint_id=history[1].checkpoint_id,
        )
    )
    assert result.state == {"x": 17, "log": ["a", "b", "c"]}
    assert kernel.get_state("thread-a") == result.state


def test_explicit_resume_checkpoint_preserves_fork_parent(tmp_path):
    kernel = GraphPersistenceKernel(tmp_path / "kernel")
    compiled = _linear_graph()
    asyncio.run(
        compiled.invoke(
            {"x": 2, "log": []},
            graph_run_id="run-original",
            persistence=kernel,
            thread_id="thread-fork",
        )
    )
    original = kernel.get_state_history("thread-fork")
    selected = original[1]
    latest = original[-1]

    asyncio.run(
        compiled.invoke(
            input=None,
            graph_run_id="run-child",
            resume_from=selected.checkpoint,
            persistence=kernel,
            thread_id="thread-fork",
            checkpoint_id=selected.checkpoint_id,
        )
    )

    child = next(
        record
        for record in kernel.get_state_history("thread-fork")
        if record.checkpoint.graph_run_id == "run-child"
    )
    assert child.parent_checkpoint_id == selected.checkpoint_id
    assert child.parent_checkpoint_id != latest.checkpoint_id


def test_native_process_restart_uses_kernel_file(tmp_path):
    program = r"""
import asyncio, json, sys
from dharma_swarm.graph import END, START, AppendChannel, GraphBuilder, GraphPersistenceKernel, LastValueChannel
phase, root, output = sys.argv[1:]
compiled = (
    GraphBuilder("restart-native")
    .add_channel("x", LastValueChannel)
    .add_channel("log", AppendChannel)
    .add_node("a", lambda state: {"x": state["x"] + 2, "log": ["a"]})
    .add_node("b", lambda state: {"x": state["x"] * 5, "log": ["b"]})
    .add_edge(START, "a").add_edge("a", "b").add_edge("b", END).compile()
)
kernel = GraphPersistenceKernel(__import__("pathlib").Path(root))
if phase == "seed":
    class StopAfter(Exception): pass
    def cb(checkpoint):
        if checkpoint.superstep == 1:
            raise StopAfter
    try:
        asyncio.run(compiled.invoke({"x": 3, "log": []}, graph_run_id="run-restart", persistence=kernel, thread_id="thread-r", on_checkpoint=cb))
    except StopAfter:
        pass
    payload = kernel.get_state("thread-r")
else:
    payload = asyncio.run(compiled.invoke(input=None, persistence=kernel, thread_id="thread-r")).state
open(output, "w", encoding="utf-8").write(json.dumps(payload, sort_keys=True))
"""
    seed_out = tmp_path / "seed.json"
    resume_out = tmp_path / "resume.json"
    for phase, output in (("seed", seed_out), ("resume", resume_out)):
        subprocess.run(
            [
                sys.executable,
                "-c",
                program,
                phase,
                str(tmp_path / "kernel"),
                str(output),
            ],
            check=True,
        )
    assert json.loads(seed_out.read_text()) == {"log": ["a"], "x": 5}
    assert json.loads(resume_out.read_text()) == {"log": ["a", "b"], "x": 25}


def test_update_time_travel_copy_prune_and_delta_history(tmp_path):
    kernel = GraphPersistenceKernel(tmp_path / "kernel")
    compiled = _linear_graph()
    stopper, callback = _stop_after(1)
    with pytest.raises(stopper):
        asyncio.run(
            compiled.invoke(
                {"x": 2, "log": []},
                graph_run_id="run-fork",
                persistence=kernel,
                thread_id="source",
                on_checkpoint=callback,
            )
        )
    mid = kernel.get_state_history("source")[1]

    updated = kernel.update_state(
        "source",
        {"x": 10},
        channel_factories=compiled.channel_factories,
        checkpoint_id=mid.checkpoint_id,
    )
    assert updated.parent_checkpoint_id == mid.checkpoint_id
    forked = asyncio.run(
        compiled.invoke(
            input=None,
            persistence=kernel,
            thread_id="source",
            checkpoint_id=updated.checkpoint_id,
        )
    )
    assert forked.state == {"x": 29, "log": ["a", "b", "c"]}

    kernel.copy_thread("source", "copy")
    assert kernel.get_state("copy") == forked.state
    assert (
        kernel.get_delta_channel_history(thread_id="copy", channels=["x"])["x"][-1][
            "value"
        ]
        == 29
    )
    kernel.prune(["copy"])
    pruned = kernel.get_state_history("copy")
    assert len(pruned) == 1
    assert pruned[0].parent_checkpoint_id is None
    kernel.delete_thread("copy")
    assert kernel.get_state_history("copy") == []


def test_invalid_superstep_is_rejected_before_pending_write_journal(tmp_path):
    compiled = (
        GraphBuilder("pending-recovery")
        .add_channel("x", LastValueChannel)
        .add_node("a", lambda state: {"x": 1})
        .add_node("b", lambda state: {"x": 2})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(tmp_path / "kernel")
    with pytest.raises(Exception, match="received 2 writes|conflict|InvalidUpdate"):
        asyncio.run(
            compiled.invoke(
                {},
                graph_run_id="run-pending",
                persistence=kernel,
                thread_id="thread-pending",
            )
        )
    reopened = GraphPersistenceKernel(tmp_path / "kernel")
    assert reopened.recover_pending_writes("thread-pending") == []

    with pytest.raises(Exception, match="received 2 writes|conflict|InvalidUpdate"):
        asyncio.run(
            compiled.invoke(
                input=None,
                persistence=reopened,
                thread_id="thread-pending",
            )
        )
    assert reopened.recover_pending_writes("thread-pending") == []


def test_default_resume_replays_pending_writes_without_reexecuting_node(tmp_path):
    calls = 0

    def node(state):
        nonlocal calls
        calls += 1
        return {"x": state["x"] + 1}

    compiled = (
        GraphBuilder("pending-runtime-replay")
        .add_channel("x", LastValueChannel)
        .add_node("a", node)
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(tmp_path / "kernel")
    stopper, callback = _stop_after(0)
    with pytest.raises(stopper):
        asyncio.run(
            compiled.invoke(
                {"x": 0},
                graph_run_id="run-replay",
                persistence=kernel,
                thread_id="thread-replay",
                on_checkpoint=callback,
            )
        )
    root = kernel.get_state_history("thread-replay")[0]
    kernel.put_writes(
        "thread-replay",
        [("x", 1)],
        "run-replay:1",
        checkpoint_id=root.checkpoint_id,
        task_path="a",
    )

    result = asyncio.run(
        compiled.invoke(
            input=None,
            persistence=kernel,
            thread_id="thread-replay",
        )
    )

    assert calls == 0
    assert result.state == {"x": 1}
    assert [(event.node_id, event.superstep) for event in result.events] == [("a", 1)]
    history = kernel.get_state_history("thread-replay")
    assert [record.superstep for record in history] == [0, 1]
    assert history[1].parent_checkpoint_id == root.checkpoint_id
    assert kernel.recover_pending_writes("thread-replay") == []


def test_default_resume_clears_pending_write_after_checkpoint_commit(tmp_path):
    compiled = (
        GraphBuilder("pending-after-commit")
        .add_channel("log", AppendChannel)
        .add_node("a", lambda state: {"log": ["a"]})
        .add_edge(START, "a")
        .add_edge("a", END)
        .compile()
    )
    kernel = GraphPersistenceKernel(tmp_path / "kernel")
    result = asyncio.run(
        compiled.invoke(
            {"log": []},
            graph_run_id="run-committed",
            persistence=kernel,
            thread_id="thread-committed",
        )
    )
    history = kernel.get_state_history("thread-committed")
    kernel.put_writes(
        "thread-committed",
        [("log", ["a"])],
        "run-committed:1",
        checkpoint_id=history[0].checkpoint_id,
        task_path="a",
    )

    resumed = asyncio.run(
        compiled.invoke(
            input=None,
            persistence=kernel,
            thread_id="thread-committed",
        )
    )

    assert resumed.state == result.state == {"log": ["a"]}
    assert len(kernel.get_state_history("thread-committed")) == 2
    assert kernel.recover_pending_writes("thread-committed") == []


def test_sync_async_serializer_and_delete_for_runs(tmp_path):
    serializer = CountingSerializer()
    kernel = GraphPersistenceKernel(tmp_path / "kernel", serializer=serializer)
    config = {"configurable": {"thread_id": "compat"}}
    out = asyncio.run(
        kernel.aput(
            config,
            {"id": "c1", "channel_values": {"x": 7}, "versions_seen": {}},
            {"graph_run_id": "run-compat", "graph_id": "compat", "superstep": 0},
            {},
        )
    )
    assert asyncio.run(kernel.aget_tuple(out))["checkpoint_id"] == "c1"
    assert serializer.dumps_count > 0
    assert serializer.loads_count > 0
    assert (
        asyncio.run(
            kernel.aput(
                config,
                {"id": "c1", "channel_values": {"x": 7}, "versions_seen": {}},
                {"graph_run_id": "run-compat", "graph_id": "compat", "superstep": 0},
                {},
            )
        )
        == out
    )
    with pytest.raises(ValueError, match="already exists"):
        asyncio.run(
            kernel.aput(
                config,
                {"id": "c1", "channel_values": {"x": 8}, "versions_seen": {}},
                {"graph_run_id": "run-compat", "graph_id": "compat", "superstep": 0},
                {},
            )
        )
    kind, payload = kernel.serde.dumps_typed({"a": [1, 2]})
    assert kernel.serde.loads_typed((kind, payload)) == {"a": [1, 2]}
    kernel.delete_for_runs(["run-compat"])
    assert kernel.get_state_history("compat") == []
