"""Per-superstep task execution for the DharmaGraph scheduler.

Pure extraction of the task-execution internals out of ``scheduler.py``
(dharmagraph-engine-2026-07, Pregel-core S1): the ready-set builder, node
runner, write interpretation, routing writes, and dispatch-order validation
live here so the scheduler owns only run-lifecycle concerns (seeding,
resume, barrier commit, checkpoint emission). Behavior is unchanged by
construction: the scheduler calls these methods in the same order with the
same inputs as the pre-extraction inline code.

Superstep protocol (unchanged): PULL (trigger) and PUSH (Send) tasks run
against deep-copied inputs; returns are write PROPOSALS buffered and
returned in canonical ``(channel, node_id, task_seq)`` order for the
scheduler's validate-all-then-commit barrier apply.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from dharma_swarm.graph.channels import ChannelWrite, TopicChannel
from dharma_swarm.graph.effects import EffectsProvider
from dharma_swarm.graph.errors import (
    GraphRuntimeError,
    MalformedDispatchOrderError,
    NodeExecutionError,
)
from dharma_swarm.graph.interrupts import (
    GraphInterrupt,
    GraphInterrupted,
    InterruptFrame,
    pop_frame,
    push_frame,
)
from dharma_swarm.graph.routing import (
    Command,
    Send,
    evaluate_branch,
    interpret_result,
    send_write,
)
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.types import END, TASKS_CHANNEL, trigger_channel

if TYPE_CHECKING:
    from dharma_swarm.graph.scheduler import CompiledGraph

__all__ = ["SuperstepExecutor"]


@dataclass(frozen=True)
class _Task:
    """One unit of execution: a PULL (trigger-driven) or PUSH (Send) task.

    Identity ``(node_id, seq)`` is unique within a superstep: PULL = seq 0
    (Slice A behavior, unchanged trace), PUSH = 1..N in canonical drain
    order. Identity enters BOTH the dispatch-order permutation check and the
    commit sort key, so same-node task writes never tie.
    """

    node_id: str
    seq: int
    arg: Any = None  # PUSH input; PULL tasks read the shared snapshot
    timeout: float | None = None  # PUSH execution bound (Send.timeout)

    @property
    def is_pull(self) -> bool:
        return self.seq == 0

    @property
    def identity(self) -> tuple[str, int]:
        return (self.node_id, self.seq)


class SuperstepExecutor:
    """Executes one superstep's ready set and returns sorted write proposals.

    Owns no state of its own beyond the compiled topology and the effects
    provider; all mutation (``versions_seen`` bookkeeping excepted, which is
    part of the execution contract) stays with the scheduler's commit path.
    """

    def __init__(self, graph: "CompiledGraph", effects: EffectsProvider) -> None:
        self._graph = graph
        self._effects = effects

    def prepare_tasks(
        self,
        state: GraphState,
        start_versions: Mapping[str, int],
        versions_seen: Mapping[str, Mapping[str, int]],
    ) -> list[_Task]:
        """Ready set = PULL tasks ∪ PUSH tasks (langgraph parity).

        A node with a fired trigger AND N pending Sends runs N+1 times this
        superstep: once on the shared snapshot, N times on Send args.
        """
        graph = self._graph
        pull = [
            _Task(node_id, 0)
            for node_id in graph.canonical_order
            if any(
                start_versions.get(name, 0) > versions_seen[node_id].get(name, 0)
                for name in graph.triggers[node_id]
            )
        ]
        tasks_channel = state.channel(TASKS_CHANNEL)
        push: list[_Task] = []
        if isinstance(tasks_channel, TopicChannel):
            seq_counter: dict[str, int] = {}
            for send in tasks_channel.drain():
                seq = seq_counter.get(send.node, 0) + 1
                seq_counter[send.node] = seq
                push.append(_Task(send.node, seq, send.arg, send.timeout))
        return pull + push

    async def run_tasks(
        self,
        tasks: list[_Task],
        state: GraphState,
        versions_seen: dict[str, dict[str, int]],
        start_versions: Mapping[str, int],
        run_id: str,
        superstep: int,
        *,
        remaining: int | None = None,
        resumes: Mapping[str, list[Any]] | None = None,
    ) -> tuple[list[ChannelWrite], list[str], list[tuple[str, int]]]:
        """Run every ready task CONCURRENTLY; return (sorted proposals, executed, ids).

        All tasks of a superstep run as concurrent asyncio tasks (langgraph
        parity: parallel actors' execution intervals overlap). Task START
        order is ``effects.dispatch_order`` (validated as a permutation,
        called exactly once); write proposals are assembled in dispatch order
        and stable-sorted by the canonical ``(channel, node_id, task_seq)``
        commit key, so committed state is completion-order-invariant and
        byte-identical to the former sequential execution.

        On the first task failure the remaining tasks are cancelled and the
        superstep aborts with zero commits; already-succeeded siblings'
        identities and writes ride the raised :class:`GraphRuntimeError`
        (``succeeded_*``) for the scheduler's pending-write persistence. A
        node raising :class:`asyncio.CancelledError` propagates unwrapped
        after the step drains.
        """
        graph = self._graph
        exec_order = self._validated_dispatch_order(tasks, run_id, superstep)

        aio_tasks: dict[asyncio.Task[list[ChannelWrite]], _Task] = {
            asyncio.ensure_future(
                self._run_one(task, state, run_id, superstep, remaining, resumes)
            ): task
            for task in exec_order
        }
        done, not_done = await asyncio.wait(
            aio_tasks, return_when=asyncio.FIRST_EXCEPTION
        )
        bundles: dict[tuple[str, int], list[ChannelWrite]] = {}
        failures: list[tuple[_Task, BaseException]] = []
        saw_cancelled = False
        for aio in done:
            task = aio_tasks[aio]
            if aio.cancelled():
                saw_cancelled = True
            elif aio.exception() is not None:
                failures.append((task, aio.exception()))  # type: ignore[arg-type]
            else:
                bundles[task.identity] = aio.result()
        if failures or saw_cancelled:
            for aio in not_done:
                aio.cancel()
            if not_done:
                await asyncio.wait(not_done)
            if not failures:
                raise asyncio.CancelledError()
            order = {t.identity: i for i, t in enumerate(exec_order)}
            failures.sort(key=lambda pair: order[pair[0].identity])
            failed_task, error = failures[0]
            if isinstance(error, GraphInterrupt):
                public = GraphInterrupted(
                    f"node {failed_task.node_id!r} interrupted in superstep "
                    f"{superstep} of run {run_id!r}; resume with "
                    "Command(resume=...)",
                    graph_run_id=run_id,
                    superstep=superstep,
                    node_id=failed_task.node_id,
                )
                public.interrupts = (error.interrupt,)
                public.consumed_resumes = error.consumed
                public.task_seq = failed_task.seq
                error = public
            if isinstance(error, GraphRuntimeError):
                succeeded = [t for t in exec_order if t.identity in bundles]
                writes = [w for t in succeeded for w in bundles[t.identity]]
                writes.sort(
                    key=lambda w: (w.channel, w.node_id, w.task_seq)
                )
                error.succeeded_tasks = tuple(t.identity for t in succeeded)
                error.succeeded_writes = tuple(writes)
                error.succeeded_pull_nodes = tuple(
                    t.node_id for t in succeeded if t.is_pull
                )
                # PUSH packets that did not complete were already drained
                # from __tasks__ at planning; they ride the error so the
                # failure view stays resumable (failed pulls re-fire via
                # trigger versions, failed pushes need their packets back).
                error.unfinished_sends = tuple(
                    Send(t.node_id, t.arg, timeout=t.timeout)
                    for t in exec_order
                    if not t.is_pull and t.identity not in bundles
                )
            raise error

        pending: list[ChannelWrite] = []
        executed: list[str] = []
        event_ids: list[tuple[str, int]] = []
        for task in exec_order:
            pending.extend(bundles[task.identity])
            if task.is_pull:
                for name in graph.triggers[task.node_id]:
                    versions_seen[task.node_id][name] = start_versions.get(
                        name, 0
                    )
            executed.append(task.node_id)
            event_ids.append(task.identity)

        pending.sort(
            key=lambda write: (write.channel, write.node_id, write.task_seq)
        )
        return pending, executed, event_ids

    async def _run_one(
        self,
        task: _Task,
        state: GraphState,
        run_id: str,
        superstep: int,
        remaining: int | None = None,
        resumes: Mapping[str, list[Any]] | None = None,
    ) -> list[ChannelWrite]:
        """One task: snapshot-isolated input, node run, write interpretation.

        The returned bundle preserves the canonical intra-task write order
        (result writes, then static routing, then branch writes) so the
        caller's dispatch-order assembly + stable sort reproduces the exact
        pre-concurrency commit sequence. A declared managed-remaining field
        is injected into pull-task snapshots only — never committed state.
        Every task runs under an interrupt frame carrying its recorded
        resume values (task-scoped, call-order replay).
        """
        graph = self._graph
        node_input = (
            state.snapshot() if task.is_pull else copy.deepcopy(task.arg)
        )
        if (
            task.is_pull
            and graph.managed_remaining is not None
            and remaining is not None
        ):
            node_input[graph.managed_remaining] = remaining
        frame = InterruptFrame(
            run_id=run_id,
            node_id=task.node_id,
            task_seq=task.seq,
            resumes=list(
                (resumes or {}).get(f"{task.node_id}:{task.seq}", ())
            ),
        )
        token = push_frame(frame)
        try:
            if task.timeout is not None:
                try:
                    async with asyncio.timeout(task.timeout):
                        result = await self._execute_node(
                            task.node_id,
                            node_input,
                            run_id,
                            superstep,
                            sync_in_thread=True,
                        )
                except TimeoutError as exc:
                    raise NodeExecutionError(
                        f"node {task.node_id!r} exceeded its send timeout of "
                        f"{task.timeout}s in superstep {superstep} of run "
                        f"{run_id!r} (langgraph Send timeout parity)",
                        graph_run_id=run_id,
                        superstep=superstep,
                        node_id=task.node_id,
                    ) from exc
            else:
                result = await self._execute_node(
                    task.node_id, node_input, run_id, superstep
                )
        finally:
            pop_frame(token)
        task_writes = self._writes_from_result(
            task.node_id, result, run_id, superstep, task.seq
        )
        bundle = list(task_writes)
        bundle.extend(self.trigger_writes(task.node_id, task_seq=task.seq))
        if task.node_id in graph.branches:
            view = state.own_writes_view(task_writes, superstep)
            bundle.extend(
                self.branch_writes(
                    task.node_id, task.seq, view, run_id, superstep
                )
            )
        return bundle

    def trigger_writes(
        self, node_id: str, task_seq: int = 0
    ) -> list[ChannelWrite]:
        """Static routing: plain-edge triggers + this node's barrier-join writes."""
        graph = self._graph
        writes = [
            ChannelWrite(node_id, trigger_channel(target), True, task_seq)
            for target in graph.successors.get(node_id, ())
            if target != END
        ]
        writes.extend(
            ChannelWrite(node_id, join_name, member, task_seq)
            for join_name, member in graph.join_writes.get(node_id, ())
        )
        return writes

    def branch_writes(
        self,
        node_id: str,
        task_seq: int,
        view: Mapping[str, Any],
        run_id: str,
        superstep: int,
    ) -> list[ChannelWrite]:
        """Evaluate the node's conditional edge; pure, pre-commit, atomic."""
        graph = self._graph
        spec = graph.branches[node_id]
        writes: list[ChannelWrite] = []
        for destination in evaluate_branch(spec, view):
            if isinstance(destination, Send):
                writes.append(
                    send_write(node_id, destination, task_seq, graph.nodes)
                )
            elif destination == END:
                continue
            else:
                writes.append(
                    ChannelWrite(
                        node_id, trigger_channel(destination), True, task_seq
                    )
                )
        return writes

    async def _execute_node(
        self,
        node_id: str,
        node_input: Any,
        run_id: str,
        superstep: int,
        *,
        sync_in_thread: bool = False,
    ) -> Mapping[str, Any] | Command | None:
        try:
            fn = self._graph.nodes[node_id].fn
            if sync_in_thread and not inspect.iscoroutinefunction(fn):
                # Timed tasks: a sync callable would block the event loop and
                # make the surrounding asyncio.timeout unable to expire, so
                # it runs on a worker thread (a timed-out thread is orphaned
                # and its result discarded — langgraph executor parity).
                raw = await asyncio.to_thread(fn, node_input)
            else:
                raw = fn(node_input)
            if inspect.isawaitable(raw):
                raw = await raw
        except asyncio.CancelledError:
            raise
        except GraphInterrupt:
            raise  # control-flow signal, converted by run_tasks — never wrapped
        except Exception as exc:
            raise NodeExecutionError(
                f"node {node_id!r} failed in superstep {superstep} of run "
                f"{run_id!r}: {type(exc).__name__}: {exc}",
                graph_run_id=run_id,
                superstep=superstep,
                node_id=node_id,
            ) from exc
        return raw

    def _writes_from_result(
        self,
        node_id: str,
        result: Mapping[str, Any] | Command | None,
        run_id: str,
        superstep: int,
        task_seq: int,
    ) -> list[ChannelWrite]:
        return interpret_result(
            node_id,
            result,
            run_id=run_id,
            superstep=superstep,
            task_seq=task_seq,
            known_nodes=self._graph.nodes,
        )

    def _validated_dispatch_order(
        self,
        tasks: list[_Task],
        run_id: str,
        superstep: int,
    ) -> list[_Task]:
        identities = [task.identity for task in tasks]
        proposed = self._effects.dispatch_order(identities)
        try:
            is_permutation = Counter(proposed) == Counter(identities)
        except TypeError:
            is_permutation = False
        if not is_permutation:
            raise MalformedDispatchOrderError(
                f"effects.dispatch_order returned {proposed!r}, which is not a "
                f"permutation of the ready task set {identities!r} (superstep "
                f"{superstep} of run {run_id!r}); refusing to execute "
                "(fail closed)",
                graph_run_id=run_id,
                superstep=superstep,
            )
        by_identity = {task.identity: task for task in tasks}
        return [by_identity[identity] for identity in proposed]
