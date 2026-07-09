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
``effects.dispatch_order`` call per non-empty superstep — over the full
task-identity list ``(node_id, task_seq)``, PULL and PUSH together — and
none on halt; one ``effects.random()`` draw ONLY when minting a default
``graph_run_id``; the scheduler never calls ``effects.now()`` (events carry
no timestamps — the checkpoint sink stamps its own wall clock, which stays
out of digests). Branch paths and Command handling are pure: they never
touch effects.

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
import copy
import inspect
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from dharma_swarm.graph.channels import (
    Channel,
    ChannelWrite,
    TopicChannel,
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
from dharma_swarm.graph.routing import (
    BranchSpec,
    Command,
    Send,
    SendTargetError,
    evaluate_branch,
)
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.types import (
    END,
    RESERVED_PREFIX,
    START,
    TASKS_CHANNEL,
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

    @property
    def is_pull(self) -> bool:
        return self.seq == 0

    @property
    def identity(self) -> tuple[str, int]:
        return (self.node_id, self.seq)


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

        seed_input = self._validated_seed(input, run_id)
        seed_writes = [
            ChannelWrite(START, name, value)
            for name, value in sorted(seed_input.items())
        ]
        routing_writes = self._trigger_writes(START)
        if START in self.branches:
            state.apply_writes(seed_writes, 0)
            view = state.snapshot()
            routing_writes.extend(
                self._branch_writes(START, 0, view, run_id, 0)
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
        while True:
            superstep += 1
            start_versions = state.versions
            tasks = self._prepare_tasks(state, start_versions, versions_seen)
            if not tasks:
                break
            if superstep > cap:
                raise SuperstepLimitError(
                    f"superstep cap {cap} exceeded with tasks still ready "
                    f"{[t.identity for t in tasks]!r} in run {run_id!r}",
                    graph_run_id=run_id,
                    superstep=superstep,
                )
            exec_order = self._validated_dispatch_order(
                active_effects, tasks, run_id, superstep
            )

            pending: list[ChannelWrite] = []
            executed: list[str] = []
            event_ids: list[tuple[str, int]] = []
            for task in exec_order:
                node_input = (
                    state.snapshot()
                    if task.is_pull
                    else copy.deepcopy(task.arg)
                )
                result = await self._execute_node(
                    task.node_id, node_input, run_id, superstep
                )
                task_writes = self._writes_from_result(
                    task.node_id, result, run_id, superstep, task.seq
                )
                pending.extend(task_writes)
                pending.extend(
                    self._trigger_writes(task.node_id, task_seq=task.seq)
                )
                if task.node_id in self.branches:
                    view = state.own_writes_view(task_writes, superstep)
                    pending.extend(
                        self._branch_writes(
                            task.node_id, task.seq, view, run_id, superstep
                        )
                    )
                if task.is_pull:
                    for name in self.triggers[task.node_id]:
                        versions_seen[task.node_id][name] = start_versions.get(
                            name, 0
                        )
                executed.append(task.node_id)
                event_ids.append(task.identity)

            pending.sort(
                key=lambda write: (write.channel, write.node_id, write.task_seq)
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
        node_input: Any,
        run_id: str,
        superstep: int,
    ) -> Mapping[str, Any] | Command | None:
        try:
            raw = self.nodes[node_id].fn(node_input)
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

    def _prepare_tasks(
        self,
        state: GraphState,
        start_versions: Mapping[str, int],
        versions_seen: Mapping[str, Mapping[str, int]],
    ) -> list[_Task]:
        """Ready set = PULL tasks ∪ PUSH tasks (langgraph parity).

        A node with a fired trigger AND N pending Sends runs N+1 times this
        superstep: once on the shared snapshot, N times on Send args.
        """
        pull = [
            _Task(node_id, 0)
            for node_id in self.canonical_order
            if any(
                start_versions.get(name, 0) > versions_seen[node_id].get(name, 0)
                for name in self.triggers[node_id]
            )
        ]
        tasks_channel = state.channel(TASKS_CHANNEL)
        push: list[_Task] = []
        if isinstance(tasks_channel, TopicChannel):
            seq_counter: dict[str, int] = {}
            for send in tasks_channel.drain():
                seq = seq_counter.get(send.node, 0) + 1
                seq_counter[send.node] = seq
                push.append(_Task(send.node, seq, send.arg))
        return pull + push

    def _writes_from_result(
        self,
        node_id: str,
        result: Mapping[str, Any] | Command | None,
        run_id: str,
        superstep: int,
        task_seq: int,
    ) -> list[ChannelWrite]:
        if result is None:
            return []
        if isinstance(result, Command):
            writes: list[ChannelWrite] = []
            if result.update is not None:
                writes.extend(
                    self._mapping_writes(
                        node_id, result.update, run_id, superstep, task_seq
                    )
                )
            for target in result.goto_items():
                if isinstance(target, Send):
                    writes.append(self._send_write(node_id, target, task_seq))
                elif target == END:
                    continue  # langgraph parity: goto=END silently skipped
                elif target in self.nodes:
                    writes.append(
                        ChannelWrite(
                            node_id, trigger_channel(target), True, task_seq
                        )
                    )
                else:
                    raise SendTargetError(
                        str(target),
                        f"Command.goto from {node_id!r} references unknown "
                        f"node {target!r} (fail closed; langgraph WARN-drops)",
                    )
            return writes
        if not isinstance(result, Mapping):
            raise NodeResultError(
                f"node {node_id!r} returned {type(result).__name__!r} in "
                f"superstep {superstep}; nodes must return a Mapping of "
                "channel writes, a Command, or None (fail closed)",
                graph_run_id=run_id,
                superstep=superstep,
                node_id=node_id,
            )
        return self._mapping_writes(node_id, result, run_id, superstep, task_seq)

    def _mapping_writes(
        self,
        node_id: str,
        mapping: Mapping[str, Any],
        run_id: str,
        superstep: int,
        task_seq: int,
    ) -> list[ChannelWrite]:
        writes: list[ChannelWrite] = []
        for key in mapping:
            if not isinstance(key, str):
                raise NodeResultError(
                    f"node {node_id!r} returned non-string channel key "
                    f"{key!r} in superstep {superstep}",
                    graph_run_id=run_id,
                    superstep=superstep,
                    node_id=node_id,
                )
            if key.startswith(RESERVED_PREFIX):
                raise UnknownChannelError(key, node_id=node_id, reason="reserved")
            writes.append(ChannelWrite(node_id, key, mapping[key], task_seq))
        return writes

    def _trigger_writes(self, node_id: str, task_seq: int = 0) -> list[ChannelWrite]:
        """Static routing: plain-edge triggers + this node's barrier-join writes."""
        writes = [
            ChannelWrite(node_id, trigger_channel(target), True, task_seq)
            for target in self.successors.get(node_id, ())
            if target != END
        ]
        writes.extend(
            ChannelWrite(node_id, join_name, member, task_seq)
            for join_name, member in self.join_writes.get(node_id, ())
        )
        return writes

    def _branch_writes(
        self,
        node_id: str,
        task_seq: int,
        view: Mapping[str, Any],
        run_id: str,
        superstep: int,
    ) -> list[ChannelWrite]:
        """Evaluate the node's conditional edge; pure, pre-commit, atomic."""
        spec = self.branches[node_id]
        writes: list[ChannelWrite] = []
        for destination in evaluate_branch(spec, view):
            if isinstance(destination, Send):
                writes.append(self._send_write(node_id, destination, task_seq))
            elif destination == END:
                continue
            else:
                writes.append(
                    ChannelWrite(
                        node_id, trigger_channel(destination), True, task_seq
                    )
                )
        return writes

    def _send_write(
        self, origin: str, send: Send, task_seq: int
    ) -> ChannelWrite:
        if send.node not in self.nodes:
            raise SendTargetError(
                send.node,
                f"Send from {origin!r} targets unknown node {send.node!r} "
                "(fail closed; langgraph WARN-drops)",
            )
        packet = Send(send.node, copy.deepcopy(send.arg))
        return ChannelWrite(origin, TASKS_CHANNEL, packet, task_seq)

    def _validated_dispatch_order(
        self,
        effects: EffectsProvider,
        tasks: list[_Task],
        run_id: str,
        superstep: int,
    ) -> list[_Task]:
        identities = [task.identity for task in tasks]
        proposed = effects.dispatch_order(identities)
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
