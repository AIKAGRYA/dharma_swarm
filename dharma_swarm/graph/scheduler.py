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

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

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
from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.persistence_runtime import GraphRunPersistence
from dharma_swarm.graph.routing import BranchSpec
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
    "SuperstepLimitError",
]

logger = logging.getLogger(__name__)


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

    async def invoke(
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
    ) -> GraphRunResult:
        """Run the graph from START to quiescence and return the committed result.

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
        run_persistence, resume_from = GraphRunPersistence.resolve(
            persistence, thread_id, checkpoint_id, input, resume_from
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

        if run_persistence.pending_write is not None:
            superstep += 1
            tasks = executor.prepare_tasks(state, state.versions, versions_seen)
            pending_task_id = run_persistence.replay(
                state, versions_seen, self.triggers, tasks, run_id, superstep
            )
            digest, committed = state.digest(), superstep
            events.extend(
                GraphRunEvent(
                    run_id, self.graph_id, task.node_id, superstep, "ok", digest, task.seq
                )
                for task in tasks
            )
            _emit_checkpoint(superstep, digest, pending_task_id)
        while True:
            superstep += 1
            start_versions = state.versions
            tasks = executor.prepare_tasks(state, start_versions, versions_seen)
            if not tasks:
                break
            if superstep > cap:
                raise SuperstepLimitError(
                    f"superstep cap {cap} exceeded with tasks still ready "
                    f"{[t.identity for t in tasks]!r} in run {run_id!r}",
                    graph_run_id=run_id,
                    superstep=superstep,
                )
            pending, executed, event_ids = await executor.run_tasks(
                tasks, state, versions_seen, start_versions, run_id, superstep
            )
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

        return GraphRunResult(
            graph_run_id=run_id,
            graph_id=self.graph_id,
            status="completed",
            state=state.snapshot(),
            state_digest=digest,
            supersteps=committed,
            events=tuple(events),
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
