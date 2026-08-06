"""BSP superstep scheduler over versioned channels (Candidate Slices A–C).

State-integrated runtime: execution is DRIVEN by channel versions. A node is
ready iff a trigger channel's version exceeds what it has seen
(``versions_seen``); the run halts when nothing advances. Cycles are legal
under ``compile(allow_cycles=True)`` + an explicit ``superstep_cap`` — the
ready predicate re-fires nodes on its own, so the unlock is a scheduling
change, not a rewrite.

Superstep protocol (all-or-nothing): PULL (trigger) and PUSH (Send) tasks
run against deep-copied inputs; returns are write PROPOSALS buffered and
committed only at the barrier, in canonical ``(channel, node_id, task_seq)``
order behind GraphState's validate-all-then-commit apply. Final state is
execution-order-invariant; execution order is ``effects.dispatch_order``,
seed-deterministic under ``SimulatedEffects``. Task-execution internals
(ready-set build, node run, write interpretation, dispatch-order
validation) live in ``executor.SuperstepExecutor``; this module owns the
run lifecycle: seeding, resume, the commit barrier, and checkpoints.

Effect-call budget (replay contract): exactly one ``dispatch_order`` call
per non-empty superstep over the full task-identity list, none on halt; one
``random()`` draw only to mint a default ``graph_run_id``; never ``now()``.
Branch paths and Command handling are pure.

Failure doctrine: fail closed by RAISING typed errors — a failed superstep
commits nothing, checkpoints nothing, returns no result. ``resume_from`` /
``on_checkpoint`` add crash-resume and fork; the resume integrity contract
is digest equality at the join point, never event-stream identity.

Invocation surfaces (LG12 parity): the run lifecycle IS the async
generator :meth:`CompiledGraph._run_supersteps`, which emits one
:class:`SuperstepEmission` per COMMITTED barrier (seed included) and a
final :class:`GraphRunResult`. Every public surface is a projection of
that one loop, so no surface can observe uncommitted state:
``invoke`` (async, the historical entry point) drains it and returns the
result; ``stream`` re-yields each barrier; ``invoke_sync`` / ``stream_sync``
run the same coroutine on a PRIVATE event loop and fail closed inside a
live loop (an async-native engine never re-enters a running loop). The
``stream_mode`` / ``version`` pair matches langgraph 1.2.4 empirically:
``values`` yields the post-barrier state snapshot (seed snapshot first),
``updates`` yields one ``{node: writes}`` chunk PER TASK in canonical node
order (never for the seed), and ``version="v2"`` wraps each chunk as the
StreamPart mapping ``{"type", "ns", "data"}`` with ``ns=()`` for flat
graphs. Recorded deviation: ``invoke(stream_mode="values", version="v2")``
returns this engine's ``GraphRunResult`` envelope, not langgraph's
``GraphOutput`` — the envelope is the sovereign result type and carries
the digest the receipt chain anchors.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import AsyncIterator, Awaitable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, TypeVar

from dharma_swarm.graph.channels import (
    Channel,
    ChannelWrite,
    UnknownChannelError,
)
from dharma_swarm.graph.effects import EffectsProvider, LiveEffects
from dharma_swarm.graph.errors import (
    CheckpointSink,
    GraphRuntimeError,
    MalformedDispatchOrderError,
    NodeExecutionError,
    NodeResultError,
    SuperstepLimitError,
)
from dharma_swarm.graph.executor import SuperstepExecutor
from dharma_swarm.graph.interrupts import GraphInterrupted, resume_channel
from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.persistence_runtime import (
    GraphRunPersistence,
    persist_failure_remains,
)
from dharma_swarm.graph.routing import BranchSpec, Command
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.types import (
    RESERVED_PREFIX,
    START,
    GraphRunEvent,
    GraphRunResult,
    NodeSpec,
    RunCheckpoint,
)

__all__ = [
    "CheckpointSink",
    "CompiledGraph",
    "GraphRuntimeError",
    "MalformedDispatchOrderError",
    "NodeExecutionError",
    "NodeResultError",
    "StreamMode",
    "StreamVersion",
    "SuperstepEmission",
    "SuperstepLimitError",
    "run_on_private_loop",
]

logger = logging.getLogger(__name__)

StreamMode = Literal["values", "updates"]
StreamVersion = Literal["v1", "v2"]

_T = TypeVar("_T")


@dataclass(frozen=True)
class SuperstepEmission:
    """One COMMITTED barrier, as seen by every invocation surface.

    ``values`` is the post-commit user-state snapshot (already deep-copied
    by :meth:`GraphState.snapshot`). ``updates`` is one ``{node: writes}``
    mapping per executed TASK, in canonical node order then Send task order
    — langgraph 1.2.4 emits a separate updates chunk per task, not one per
    superstep (verified empirically). ``is_seed`` marks the superstep-0
    emission, which has state but no task updates.
    """

    superstep: int
    values: Mapping[str, Any]
    updates: tuple[Mapping[str, Mapping[str, Any]], ...] = ()
    is_seed: bool = False


def _reject_running_loop(surface: str) -> None:
    """Fail closed when a sync surface is called from inside a live loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise GraphRuntimeError(
        f"{surface} needs a private event loop but one is already running in "
        "this thread; await the async surface instead (fail closed — an "
        "async-native engine never re-enters a running loop)"
    )


def run_on_private_loop(
    factory: Callable[[], Awaitable[_T]], surface: str
) -> _T:
    """Run one engine coroutine from sync code on a private event loop.

    The coroutine is built only AFTER the live-loop check, so a fail-closed
    call never leaves an un-awaited coroutine behind.
    """
    _reject_running_loop(surface)
    return asyncio.run(factory())  # type: ignore[arg-type]


def _validate_stream_contract(stream_mode: str, version: str) -> None:
    if stream_mode not in ("values", "updates"):
        raise ValueError(
            f"stream_mode {stream_mode!r} is not supported; expected "
            "'values' or 'updates' (fail closed)"
        )
    if version not in ("v1", "v2"):
        raise ValueError(
            f"version {version!r} is not supported; expected 'v1' or 'v2' "
            "(fail closed)"
        )


def _stream_chunks(
    emission: SuperstepEmission, stream_mode: str, version: str
) -> list[Any]:
    """Project one barrier into the chunks a stream surface yields."""
    if stream_mode == "values":
        chunks: list[Any] = [emission.values]
    else:
        chunks = list(emission.updates)
    if version == "v2":
        return [
            {"type": stream_mode, "ns": (), "data": chunk} for chunk in chunks
        ]
    return chunks


@dataclass(frozen=True)
class CompiledGraph:
    """Validated, immutable topology. Construct via ``GraphBuilder.compile()``."""

    graph_id: str
    nodes: Mapping[str, NodeSpec]
    canonical_order: tuple[str, ...]
    successors: Mapping[str, tuple[str, ...]]
    triggers: Mapping[str, tuple[str, ...]]
    channel_factories: Mapping[str, Callable[[], Channel[Any]]]
    allow_orphans: bool = False
    allow_cycles: bool = False
    branches: Mapping[str, BranchSpec] = field(default_factory=dict)
    join_writes: Mapping[str, tuple[tuple[str, str], ...]] = field(
        default_factory=dict
    )
    # Managed-value field name receiving the remaining superstep budget in
    # every pull-task snapshot (schema.RemainingSteps; None = not declared).
    managed_remaining: str | None = None

    async def invoke(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> GraphRunResult | list[Any]:
        """Run to quiescence (async) and return the committed outcome.

        Default ``stream_mode="values"`` is the historical contract: the
        :class:`GraphRunResult` envelope, unchanged. ``stream_mode="updates"``
        returns the LIST of per-task update chunks the stream would have
        yielded — raw dicts under ``version="v1"``, StreamPart mappings
        (``{"type", "ns", "data"}``) under ``version="v2"`` — matching
        langgraph 1.2.4's ``Pregel.ainvoke(stream_mode=..., version=...)``.
        Run keywords (``effects``, ``resume_from``, ``persistence``, ...)
        pass through to :meth:`_run_supersteps` unchanged.
        """
        _validate_stream_contract(stream_mode, version)
        parts: list[Any] = []
        result: GraphRunResult | None = None
        async for kind, payload in self._run_supersteps(input, **kwargs):
            if kind == "result":
                result = payload
            elif stream_mode != "values":
                parts.extend(_stream_chunks(payload, stream_mode, version))
        if stream_mode == "values":
            assert result is not None  # the generator always ends with one
            return result
        return parts

    def invoke_sync(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> GraphRunResult | list[Any]:
        """Blocking twin of :meth:`invoke` on a private event loop.

        langgraph is sync-native with async twins; this engine is the mirror
        image, so the sync surface is a thin private-loop wrapper and fails
        closed (``GraphRuntimeError``) when a loop is already running in this
        thread rather than silently nesting loops or spawning hidden threads.
        """
        _validate_stream_contract(stream_mode, version)
        return run_on_private_loop(
            lambda: self.invoke(
                input, stream_mode=stream_mode, version=version, **kwargs
            ),
            "CompiledGraph.invoke_sync",
        )

    async def stream(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Yield each COMMITTED barrier as it lands (langgraph astream parity).

        ``values`` yields the seed snapshot first, then the state after every
        committed superstep; ``updates`` yields one ``{node: writes}`` chunk
        per executed task and nothing for the seed. Failure doctrine is
        preserved by construction: the run raises out of the generator and
        nothing is yielded past the last COMMITTED barrier.
        """
        _validate_stream_contract(stream_mode, version)
        async for kind, payload in self._run_supersteps(input, **kwargs):
            if kind != "step":
                continue
            for chunk in _stream_chunks(payload, stream_mode, version):
                yield chunk

    def stream_sync(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> Iterator[Any]:
        """Blocking twin of :meth:`stream`, pumped on a private event loop.

        Eagerly fails closed inside a live loop (this is a plain function
        returning a generator, so the check does not wait for the first
        ``next()``). The private loop is closed when the iterator is
        exhausted or garbage-collected.
        """
        _validate_stream_contract(stream_mode, version)
        _reject_running_loop("CompiledGraph.stream_sync")
        emitter = self.stream(
            input, stream_mode=stream_mode, version=version, **kwargs
        )

        def _pump() -> Iterator[Any]:
            loop = asyncio.new_event_loop()
            try:
                while True:
                    try:
                        yield loop.run_until_complete(emitter.__anext__())
                    except StopAsyncIteration:
                        return
            finally:
                loop.run_until_complete(emitter.aclose())
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

        return _pump()

    def _update_chunks(
        self, writes: Sequence[ChannelWrite]
    ) -> tuple[Mapping[str, Mapping[str, Any]], ...]:
        """One ``{node: writes}`` chunk per TASK, in canonical dispatch order.

        Reserved (``__``) routing writes never surface. Chunk order is the
        compiled canonical node order then Send task order — never the
        effects-driven execution order — so a stream is as execution-order
        invariant as the committed state it reports.
        """
        grouped: dict[tuple[str, int], dict[str, Any]] = {}
        for write in writes:
            if write.channel.startswith(RESERVED_PREFIX):
                continue
            grouped.setdefault((write.node_id, write.task_seq), {})[
                write.channel
            ] = copy.deepcopy(write.value)
        rank = {node: index for index, node in enumerate(self.canonical_order)}
        return tuple(
            {node_id: payload}
            for (node_id, task_seq), payload in sorted(
                grouped.items(),
                key=lambda item: (
                    rank.get(item[0][0], len(rank)),
                    item[0][0],
                    item[0][1],
                ),
            )
        )

    async def _run_supersteps(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        effects: EffectsProvider | None = None,
        checkpoint_store: CheckpointSink | None = None,
        graph_run_id: str | None = None,
        superstep_cap: int | None = None,
        resume_from: RunCheckpoint | None = None,
        on_checkpoint: Callable[[RunCheckpoint], None] | None = None,
        persistence: GraphPersistenceKernel | None = None,
        thread_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """The run lifecycle: yield every committed barrier, then the result.

        Emits ``("step", SuperstepEmission)`` after each barrier COMMITS —
        never before — and finally ``("result", GraphRunResult)``. Every
        public invocation surface consumes this one generator, so sync,
        async, streaming, and typed-v2 callers observe byte-identical
        committed state.

        ``graph_run_id`` resolution: explicit wins; else a passed
        ``checkpoint_store``'s ``run_id`` is adopted; else one id is minted
        from ``effects.random()`` (never uuid4 — same seed, same id, so
        seeded traces replay byte-identically).

        ``resume_from`` rebuilds channel state + versions_seen from a
        :class:`RunCheckpoint` and continues from ``superstep + 1`` (fork = a
        checkpoint copied under a new run id). ``on_checkpoint`` receives a
        RunCheckpoint after every committed superstep (0 included).
        """
        active_effects: EffectsProvider = (
            effects if effects is not None else LiveEffects()
        )
        executor = SuperstepExecutor(self, active_effects)
        resume_command: Command | None = None
        if isinstance(input, Command):
            if not input.has_resume:
                raise GraphRuntimeError(
                    "Command input supports only resume this slice; pass "
                    "update/goto commands as node returns (fail closed)",
                    graph_run_id=graph_run_id or "",
                )
            if persistence is None or thread_id is None:
                raise GraphRuntimeError(
                    "Cannot use Command(resume=...) without a persistence "
                    "kernel and thread_id (fail closed; langgraph parity: "
                    "resume requires a checkpointer)",
                    graph_run_id=graph_run_id or "",
                )
            resume_command = input
            input = None
        run_persistence, resume_from = GraphRunPersistence.resolve(
            persistence, thread_id, checkpoint_id, input, resume_from
        )
        if resume_command is not None and run_persistence.pending_write is None:
            raise GraphRuntimeError(
                "Command(resume=...) found no pending interrupt record on "
                f"thread {thread_id!r} (fail closed)",
                graph_run_id=graph_run_id or "",
            )
        run_id = graph_run_id
        if run_id is None and resume_from is not None:
            run_id = resume_from.graph_run_id
        if run_id is None and checkpoint_store is not None:
            run_id = checkpoint_store.run_id
        if run_id is None:
            run_id = f"graphrun-{active_effects.random().getrandbits(64):016x}"
        if checkpoint_store is not None and checkpoint_store.run_id != run_id:
            raise ValueError(
                f"checkpoint_store.run_id {checkpoint_store.run_id!r} does not "
                f"match graph_run_id {run_id!r}; refusing to run (fail closed)"
            )
        if self.allow_cycles and superstep_cap is None:
            raise ValueError(
                "a cyclic graph (allow_cycles=True) requires an explicit "
                "superstep_cap — the iteration budget IS the termination "
                "guarantee (fail closed)"
            )
        cap = superstep_cap if superstep_cap is not None else len(self.nodes) + 2

        state = GraphState(self.channel_factories)
        versions_seen: dict[str, dict[str, int]] = {n: {} for n in self.nodes}
        events: list[GraphRunEvent] = []

        def _emit_checkpoint(
            step: int, current_digest: str, pending_task_id: str | None = None
        ) -> None:
            checkpoint = RunCheckpoint(
                graph_run_id=run_id,
                graph_id=self.graph_id,
                superstep=step,
                state_digest=current_digest,
                channels=state.checkpoint_channels(),
                versions_seen={n: dict(v) for n, v in versions_seen.items()},
            )
            run_persistence.commit(checkpoint, pending_task_id)
            if on_checkpoint is not None:
                on_checkpoint(checkpoint)

        if resume_from is not None:
            state.restore_channels(resume_from.channels)
            versions_seen = {
                n: dict(resume_from.versions_seen.get(n, {})) for n in self.nodes
            }
            digest = state.digest()
            if digest != resume_from.state_digest:
                raise ValueError(
                    f"resume integrity check failed: rebuilt digest {digest} != "
                    f"checkpoint state_ref {resume_from.state_digest} (fail closed)"
                )
            committed = resume_from.superstep
            superstep = resume_from.superstep
            # A resumed run has no seed barrier; its restored state is the
            # stream's starting snapshot, so a values stream still opens on
            # the state the caller resumes FROM.
            yield (
                "step",
                SuperstepEmission(superstep, state.snapshot(), (), is_seed=True),
            )
        else:
            seed_input = self._validated_seed(input, run_id)
            seed_writes = [
                ChannelWrite(START, name, value)
                for name, value in sorted(seed_input.items())
            ]
            routing_writes = executor.trigger_writes(START)
            if START in self.branches:
                state.apply_writes(seed_writes, 0)
                view = state.snapshot()
                routing_writes.extend(
                    executor.branch_writes(START, 0, view, run_id, 0)
                )
                state.apply_writes(routing_writes, 0)
            else:
                state.apply_writes(seed_writes + routing_writes, 0)
            digest = state.digest()
            events.append(
                GraphRunEvent(run_id, self.graph_id, START, 0, "ok", digest)
            )
            if checkpoint_store is not None:
                checkpoint_store.checkpoint(
                    superstep=0, node_id=START, state_ref=digest
                )
            committed = 0
            superstep = 0
            _emit_checkpoint(0, digest)
            yield (
                "step",
                SuperstepEmission(0, state.snapshot(), (), is_seed=True),
            )

        # Superstep budgets are per-INVOCATION (langgraph parity: every
        # invoke gets its full recursion budget, including resume —
        # pregel/_loop.py:1676-1677); absolute superstep numbering continues
        # across resumes for checkpoint identity only.
        invocation_base = superstep

        if run_persistence.pending_write is not None:
            superstep += 1
            start_versions = state.versions
            tasks = executor.prepare_tasks(state, start_versions, versions_seen)
            plan = run_persistence.pending_replay_plan(tasks, run_id, superstep)
            if resume_command is not None:
                if len(plan.resumes) != 1:
                    raise GraphRuntimeError(
                        "Command(resume=...) needs exactly one interrupted "
                        f"node in the pending record; found "
                        f"{sorted(plan.resumes)!r} (fail closed)",
                        graph_run_id=run_id,
                        superstep=superstep,
                    )
                plan.resumes[next(iter(plan.resumes))].append(
                    resume_command.resume
                )
            replayed_writes: list[ChannelWrite] = []
            if plan.full:
                run_persistence.replay(
                    state, versions_seen, self.triggers, tasks, run_id, superstep
                )
                replayed_ids = [(task.node_id, task.seq) for task in tasks]
            else:
                # Failure/interrupt resume: succeeded tasks' recorded writes
                # replay without re-execution; only uncovered tasks run,
                # against the restored pre-step snapshot (langgraph parity).
                for node in plan.covered_pull_nodes:
                    for name in self.triggers[node]:
                        versions_seen[node][name] = start_versions.get(name, 0)
                try:
                    live_pending, _live_nodes, replayed_ids = (
                        await executor.run_tasks(
                            plan.live_tasks,
                            state,
                            versions_seen,
                            start_versions,
                            run_id,
                            superstep,
                            remaining=cap - (superstep - invocation_base),
                            resumes=plan.resumes,
                        )
                    )
                except GraphInterrupted as suspended:
                    # Re-interrupt during resume: replace the pending record
                    # with prior siblings + newly succeeded work + the full
                    # accumulated resume history, then surface the interrupt.
                    prior = run_persistence.pending_write
                    prior_path = prior.task_path if prior is not None else ""
                    merged_path = "+".join(
                        sorted(
                            ([p for p in prior_path.split("+") if p])
                            + [n for n, _seq in suspended.succeeded_tasks]
                        )
                    )
                    run_persistence.journal_replace(
                        [
                            (w.channel, w.value)
                            for w in plan.recorded_writes
                        ]
                        + [
                            (w.channel, w.value)
                            for w in suspended.succeeded_writes
                        ]
                        + [
                            (
                                resume_channel(
                                    suspended.node_id,
                                    suspended.task_seq,
                                ),
                                list(suspended.consumed_resumes),
                            )
                        ],
                        plan.task_id,
                        task_path=merged_path,
                    )
                    raise
                replayed_writes = list(plan.recorded_writes) + list(live_pending)
                state.apply_writes(
                    plan.recorded_writes + live_pending, superstep
                )
                # Recorded siblings commit in this same barrier: emit their
                # receipts too, matching the full-replay convention (their
                # work is in the committed state even though only live
                # tasks re-executed).
                live_ids = {task.identity for task in plan.live_tasks}
                replayed_ids = [
                    task.identity
                    for task in tasks
                    if task.identity not in live_ids
                ] + list(replayed_ids)
            digest, committed = state.digest(), superstep
            events.extend(
                GraphRunEvent(
                    run_id, self.graph_id, node_id, superstep, "ok", digest, seq
                )
                for node_id, seq in replayed_ids
            )
            _emit_checkpoint(superstep, digest, plan.task_id)
            # Full replay re-applies journalled writes inside the persistence
            # runtime, so only the partial path can report per-task updates;
            # the values projection is exact either way.
            yield (
                "step",
                SuperstepEmission(
                    superstep,
                    state.snapshot(),
                    self._update_chunks(replayed_writes),
                ),
            )
        while True:
            superstep += 1
            start_versions = state.versions
            tasks = executor.prepare_tasks(state, start_versions, versions_seen)
            if not tasks:
                break
            if superstep - invocation_base > cap:
                raise SuperstepLimitError(
                    f"superstep cap {cap} exceeded with tasks still ready "
                    f"{[t.identity for t in tasks]!r} in run {run_id!r}",
                    graph_run_id=run_id,
                    superstep=superstep,
                )
            try:
                pending, executed, event_ids = await executor.run_tasks(
                    tasks,
                    state,
                    versions_seen,
                    start_versions,
                    run_id,
                    superstep,
                    remaining=cap - (superstep - invocation_base),
                )
            except GraphRuntimeError as error:
                persist_failure_remains(
                    self,
                    error,
                    state,
                    versions_seen,
                    start_versions,
                    run_persistence,
                    run_id,
                    superstep,
                    committed,
                    on_checkpoint,
                )
                raise
            state.validate_writes(pending, superstep)  # Pure pre-journal validation.
            pending_task_id = f"{run_id}:{superstep}"
            run_persistence.journal(
                [(write.channel, write.value) for write in pending],
                pending_task_id,
                task_path="+".join(sorted(executed)),
            )
            state.apply_writes(pending, superstep)
            digest = state.digest()
            for node_id, task_seq in event_ids:
                events.append(
                    GraphRunEvent(
                        run_id,
                        self.graph_id,
                        node_id,
                        superstep,
                        "ok",
                        digest,
                        task_seq,
                    )
                )
            if checkpoint_store is not None:
                checkpoint_store.checkpoint(
                    superstep=superstep,
                    node_id="+".join(sorted(executed)),
                    state_ref=digest,
                )
            committed = superstep
            _emit_checkpoint(superstep, digest, pending_task_id)
            yield (
                "step",
                SuperstepEmission(
                    superstep, state.snapshot(), self._update_chunks(pending)
                ),
            )

        yield (
            "result",
            GraphRunResult(
                graph_run_id=run_id,
                graph_id=self.graph_id,
                status="completed",
                state=state.snapshot(),
                state_digest=digest,
                supersteps=committed,
                events=tuple(events),
            ),
        )

    def _validated_seed(
        self, input: Mapping[str, Any] | None, run_id: str
    ) -> Mapping[str, Any]:
        """B0: the seed path gets the same key validation as node outputs."""
        seed = dict(input or {})
        for key in seed:
            if not isinstance(key, str):
                raise NodeResultError(
                    f"invoke(input=...) received non-string channel key "
                    f"{key!r} (fail closed)",
                    graph_run_id=run_id,
                    superstep=0,
                    node_id=START,
                )
            if key.startswith(RESERVED_PREFIX):
                raise UnknownChannelError(key, node_id=START, reason="reserved")
        return seed
