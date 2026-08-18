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
from dharma_swarm.graph.effects import (
    EffectsProvider,
    monotonic_clock,
    provider_retry_sleep,
    wait_for_task,
)
from dharma_swarm.graph.errors import (
    GraphRuntimeError,
    MalformedDispatchOrderError,
    NodeExecutionError,
    NodeTimeoutError,
)
from dharma_swarm.graph.interrupts import (
    GraphInterrupt,
    GraphInterrupted,
    InterruptFrame,
    pop_frame,
    push_frame,
)
from dharma_swarm.graph.retry import (
    RetryPolicy,
    retry_candidate,
    retry_sleep_seconds,
    select_retry_policy,
)
from dharma_swarm.graph.routing import (
    Command,
    Send,
    evaluate_branch,
    interpret_result,
    send_write,
)
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.timeouts import (
    IdleWatchdog,
    TimeoutPolicy,
    pop_watchdog,
    push_watchdog,
)
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
    # Declared per-node hard/idle bounds (NodeSpec.timeout); applies to PULL
    # and PUSH tasks alike, per ATTEMPT, and is independent of Send.timeout.
    timeout_policy: TimeoutPolicy | None = None
    retry: tuple[RetryPolicy, ...] = ()  # first-match ladder (NodeSpec.retry)

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
            _Task(
                node_id,
                0,
                timeout_policy=graph.nodes[node_id].timeout,
                retry=graph.nodes[node_id].retry,
            )
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
                spec = graph.nodes.get(send.node)
                push.append(
                    _Task(
                        send.node,
                        seq,
                        send.arg,
                        send.timeout,
                        timeout_policy=spec.timeout if spec is not None else None,
                        retry=spec.retry if spec is not None else (),
                    )
                )
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

        Under a declared retry ladder the ATTEMPT body (frame push, node run,
        timeout envelopes) repeats while the ladder claims the failure; the
        write bundle is interpreted once, from the SUCCEEDING attempt's result
        only. That is the engine's ``task.writes.clear()`` equivalent: a failed
        attempt returns nothing, contributes no proposal, and nothing commits
        before the scheduler's barrier — so a node that fails twice and then
        succeeds commits exactly one set of writes.
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
        failed = 0
        while True:
            try:
                result = await self._run_attempt(
                    task, node_input, run_id, superstep, resumes
                )
            except (GraphInterrupt, asyncio.CancelledError):
                # Control-flow signals, never failures: interrupts must reach
                # run_tasks unretried (GraphBubbleUp parity) and cancellation
                # belongs to the step teardown.
                raise
            except Exception as exc:
                policy = select_retry_policy(task.retry, retry_candidate(exc))
                if policy is None:
                    raise
                failed += 1
                if failed >= policy.max_attempts:
                    # max_attempts INCLUDES the first attempt (reference parity).
                    raise
                await self._retry_sleep(
                    retry_sleep_seconds(policy, failed, self._effects)
                )
                continue
            break
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

    async def _run_attempt(
        self,
        task: _Task,
        node_input: Any,
        run_id: str,
        superstep: int,
        resumes: Mapping[str, list[Any]] | None,
    ) -> Mapping[str, Any] | Command | None:
        """ONE attempt: fresh interrupt frame + fresh timeout deadlines.

        Resume values are replayed from the top on every attempt (a retried
        node re-executes from its first ``interrupt()`` call), and each attempt
        gets its own hard/idle deadline pair — the langgraph contract that makes
        ``timeout`` and ``retry_policy`` compose.
        """
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
            if task.timeout_policy is not None:
                return await self._run_timed_attempt(
                    task, node_input, run_id, superstep
                )
            if task.timeout is not None:
                try:
                    async with asyncio.timeout(task.timeout):
                        return await self._execute_node(
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
            return await self._execute_node(
                task.node_id, node_input, run_id, superstep
            )
        finally:
            pop_frame(token)

    async def _run_timed_attempt(
        self,
        task: _Task,
        node_input: Any,
        run_id: str,
        superstep: int,
    ) -> Mapping[str, Any] | Command | None:
        """Run one attempt under its node's hard and/or idle bounds.

        The node runs as its own asyncio task so the watchdog can observe it
        while it works. The HARD bound (``run_timeout``) is measured from this
        attempt's start and is never refreshed; the IDLE bound is measured from
        the last :func:`~dharma_swarm.graph.timeouts.heartbeat` and IS. The
        watchdog re-derives both deadlines after every wake-up, so a heartbeat
        that lands during a wait extends only the idle deadline. Whichever bound
        expires first cancels the node and raises
        :class:`NodeTimeoutError` — a ``GraphRuntimeError``, so the failed
        superstep keeps its normal fail-closed semantics.
        """
        policy = task.timeout_policy
        assert policy is not None  # guarded by the caller
        run_timeout = policy.run_timeout
        idle_timeout = policy.idle_timeout
        clock = monotonic_clock(self._effects)
        started = clock()
        watchdog = (
            IdleWatchdog(task.node_id, clock=clock)
            if idle_timeout is not None
            else None
        )
        wd_token = push_watchdog(watchdog)
        try:
            node_task = asyncio.ensure_future(
                self._execute_node(
                    task.node_id,
                    node_input,
                    run_id,
                    superstep,
                    sync_in_thread=True,
                )
            )
            try:
                while True:
                    now = clock()
                    deadlines: list[float] = []
                    if run_timeout is not None:
                        deadlines.append(started + float(run_timeout))
                    if idle_timeout is not None and watchdog is not None:
                        deadlines.append(
                            watchdog.idle_deadline(float(idle_timeout))
                        )
                    budget = min(deadlines) - now
                    if budget <= 0:
                        kind: str = "idle"
                        if run_timeout is not None and (
                            now - started >= float(run_timeout)
                        ):
                            kind = "run"
                        raise NodeTimeoutError(
                            task.node_id,
                            now - started,
                            kind=kind,  # type: ignore[arg-type]
                            run_timeout=(
                                float(run_timeout)
                                if run_timeout is not None
                                else None
                            ),
                            idle_timeout=(
                                float(idle_timeout)
                                if idle_timeout is not None
                                else None
                            ),
                            graph_run_id=run_id,
                            superstep=superstep,
                        )
                    if await wait_for_task(node_task, budget):
                        return node_task.result()
                    # Woke on the bound, not on completion: loop and re-derive
                    # the deadlines, since a heartbeat may have moved the idle
                    # one forward while we waited.
            finally:
                if not node_task.done():
                    node_task.cancel()
                    await wait_for_task(node_task, None)
        finally:
            pop_watchdog(wd_token)

    async def _retry_sleep(self, seconds: float) -> None:
        """Wait out a retry backoff through the effects seam when available.

        Duck-typed providers predating the seam fall back to a real sleep; the
        engine's own providers implement ``retry_sleep`` so seeded runs record
        the ladder and never actually wait.
        """
        await provider_retry_sleep(self._effects, seconds)

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
