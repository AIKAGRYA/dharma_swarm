"""Acyclic BSP superstep scheduler over versioned channels (Candidate Slice A).

State-integrated runtime: execution is DRIVEN by channel versions, not by a
static loop over nodes. A node is ready iff one of its trigger channels has
a version greater than what that node has seen (``versions_seen``); the run
halts when nothing advances. Removing the compiler's acyclic guard (and
giving ``superstep_cap`` a telos-gated budget) is the designed path to legal
cycles — the ready predicate already re-fires nodes on version advance, so
that unlock is a scheduling-predicate change, not a rewrite.

Superstep protocol (all-or-nothing): every ready node executes against a
deep-copied snapshot of committed state; its return value is a write
PROPOSAL; proposals buffer and commit only at the barrier, in canonical
``(channel, node_id)`` order, behind GraphState's validate-all-then-commit
two-phase apply. Final state is therefore execution-order-invariant while
execution order itself is ``effects.dispatch_order``-driven and
seed-deterministic under ``SimulatedEffects``.

Effect-call budget (part of the replay contract): exactly one
``effects.dispatch_order`` call per non-empty superstep and none on halt;
one ``effects.random()`` draw ONLY when minting a default ``graph_run_id``;
the scheduler never calls ``effects.now()`` (events carry no timestamps —
the checkpoint sink stamps its own wall clock, which stays out of digests).

Failure doctrine: fail closed by RAISING typed errors — a failed superstep
commits nothing, checkpoints nothing, and returns no result. Named seams
for later phases (not built here): ``_writes_from_result`` (Command),
``_trigger_writes`` (conditional edges / Send), ``superstep_cap`` (cycle
iteration budget), :class:`TriggerChannel` -> Topic (fanout payloads).

claim_mode: candidate / test_only. Not wired into production dispatch; node
callables are pure/internal state transforms — side effects are not proven
safe here (no durable invoker, no receipts, no telos anchoring).
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from dharma_swarm.graph.channels import Channel, ChannelWrite, UnknownChannelError
from dharma_swarm.graph.effects import EffectsProvider, LiveEffects
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.types import (
    END,
    START,
    GraphRunEvent,
    GraphRunResult,
    NodeSpec,
    trigger_channel,
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


class GraphRuntimeError(RuntimeError):
    """Base for neutral-core execution failures (runs raise, never return failed)."""

    def __init__(
        self,
        message: str,
        *,
        graph_run_id: str = "",
        superstep: int = -1,
        node_id: str = "",
    ) -> None:
        super().__init__(message)
        self.graph_run_id = graph_run_id
        self.superstep = superstep
        self.node_id = node_id


class NodeExecutionError(GraphRuntimeError):
    """A node callable raised; the original exception is chained as __cause__."""


class NodeResultError(GraphRuntimeError):
    """A node returned something other than a Mapping (or None)."""


class MalformedDispatchOrderError(GraphRuntimeError):
    """effects.dispatch_order did not return an exact permutation of the ready set."""


class SuperstepLimitError(GraphRuntimeError):
    """superstep_cap exceeded with nodes still ready (future cycle-budget hook)."""


class CheckpointSink(Protocol):
    """Structural checkpoint contract; ``GraphCheckpointStore`` satisfies it.

    The scheduler stays decoupled from the concrete store: records are
    digest/progress markers only — resume/fork is NOT claimed by this slice.
    """

    run_id: str

    def checkpoint(self, superstep: int, node_id: str, state_ref: str) -> object: ...


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

    async def invoke(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        effects: EffectsProvider | None = None,
        checkpoint_store: CheckpointSink | None = None,
        graph_run_id: str | None = None,
        superstep_cap: int | None = None,
    ) -> GraphRunResult:
        """Run the graph from START to quiescence and return the committed result.

        ``graph_run_id`` resolution: explicit wins; else a passed
        ``checkpoint_store``'s ``run_id`` is adopted; else one id is minted
        from ``effects.random()`` (never uuid4 — same seed, same id, so
        seeded traces replay byte-identically).
        """
        active_effects: EffectsProvider = (
            effects if effects is not None else LiveEffects()
        )
        run_id = graph_run_id
        if run_id is None and checkpoint_store is not None:
            run_id = checkpoint_store.run_id
        if run_id is None:
            run_id = f"graphrun-{active_effects.random().getrandbits(64):016x}"
        if checkpoint_store is not None and checkpoint_store.run_id != run_id:
            raise ValueError(
                f"checkpoint_store.run_id {checkpoint_store.run_id!r} does not "
                f"match graph_run_id {run_id!r}; refusing to run (fail closed)"
            )
        cap = superstep_cap if superstep_cap is not None else len(self.nodes) + 2

        state = GraphState(self.channel_factories)
        versions_seen: dict[str, dict[str, int]] = {n: {} for n in self.nodes}
        events: list[GraphRunEvent] = []

        seed_writes = [
            ChannelWrite(START, name, value)
            for name, value in sorted((input or {}).items())
        ]
        seed_writes.extend(self._trigger_writes(START))
        state.apply_writes(seed_writes, 0)
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
        while True:
            superstep += 1
            start_versions = state.versions
            ready = [
                node_id
                for node_id in self.canonical_order
                if any(
                    start_versions.get(name, 0) > versions_seen[node_id].get(name, 0)
                    for name in self.triggers[node_id]
                )
            ]
            if not ready:
                break
            if superstep > cap:
                raise SuperstepLimitError(
                    f"superstep cap {cap} exceeded with nodes still ready "
                    f"{ready!r} in run {run_id!r}",
                    graph_run_id=run_id,
                    superstep=superstep,
                )
            exec_order = self._validated_dispatch_order(
                active_effects, ready, run_id, superstep
            )

            pending: list[ChannelWrite] = []
            executed: list[str] = []
            for node_id in exec_order:
                result = await self._execute_node(
                    node_id, state.snapshot(), run_id, superstep
                )
                pending.extend(
                    self._writes_from_result(node_id, result, run_id, superstep)
                )
                pending.extend(self._trigger_writes(node_id))
                for name in self.triggers[node_id]:
                    versions_seen[node_id][name] = start_versions.get(name, 0)
                executed.append(node_id)

            pending.sort(key=lambda write: (write.channel, write.node_id))
            state.apply_writes(pending, superstep)
            digest = state.digest()
            for node_id in exec_order:
                events.append(
                    GraphRunEvent(
                        run_id, self.graph_id, node_id, superstep, "ok", digest
                    )
                )
            if checkpoint_store is not None:
                checkpoint_store.checkpoint(
                    superstep=superstep,
                    node_id="+".join(sorted(executed)),
                    state_ref=digest,
                )
            committed = superstep

        return GraphRunResult(
            graph_run_id=run_id,
            graph_id=self.graph_id,
            status="completed",
            state=state.snapshot(),
            state_digest=digest,
            supersteps=committed,
            events=tuple(events),
        )

    async def _execute_node(
        self,
        node_id: str,
        snapshot: Mapping[str, Any],
        run_id: str,
        superstep: int,
    ) -> Mapping[str, Any] | None:
        try:
            raw = self.nodes[node_id].fn(snapshot)
            if inspect.isawaitable(raw):
                raw = await raw
        except asyncio.CancelledError:
            raise
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
        result: Mapping[str, Any] | None,
        run_id: str,
        superstep: int,
    ) -> list[ChannelWrite]:
        if result is None:
            return []
        if not isinstance(result, Mapping):
            raise NodeResultError(
                f"node {node_id!r} returned {type(result).__name__!r} in "
                f"superstep {superstep}; nodes must return a Mapping of "
                "channel writes or None (fail closed)",
                graph_run_id=run_id,
                superstep=superstep,
                node_id=node_id,
            )
        writes: list[ChannelWrite] = []
        for key in result:
            if not isinstance(key, str):
                raise NodeResultError(
                    f"node {node_id!r} returned non-string channel key "
                    f"{key!r} in superstep {superstep}",
                    graph_run_id=run_id,
                    superstep=superstep,
                    node_id=node_id,
                )
            if key.startswith("__"):
                raise UnknownChannelError(key, node_id=node_id, reason="reserved")
            writes.append(ChannelWrite(node_id, key, result[key]))
        return writes

    def _trigger_writes(self, node_id: str) -> list[ChannelWrite]:
        return [
            ChannelWrite(node_id, trigger_channel(target), True)
            for target in self.successors.get(node_id, ())
            if target != END
        ]

    def _validated_dispatch_order(
        self,
        effects: EffectsProvider,
        ready: list[str],
        run_id: str,
        superstep: int,
    ) -> list[str]:
        proposed = effects.dispatch_order(ready)
        try:
            is_permutation = Counter(proposed) == Counter(ready)
        except TypeError:
            is_permutation = False
        if not is_permutation:
            raise MalformedDispatchOrderError(
                f"effects.dispatch_order returned {proposed!r}, which is not a "
                f"permutation of the ready set {ready!r} (superstep {superstep} "
                f"of run {run_id!r}); refusing to execute (fail closed)",
                graph_run_id=run_id,
                superstep=superstep,
            )
        return list(proposed)
