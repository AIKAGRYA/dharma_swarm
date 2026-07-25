"""Typed execution errors + checkpoint protocol for the neutral graph core.

Failure doctrine: runs RAISE these; they never return failed results — a
failed superstep commits nothing, checkpoints nothing, yields no result.
Re-exported by ``scheduler`` so existing imports keep working.
"""

from __future__ import annotations

from typing import Protocol

__all__ = [
    "CheckpointSink",
    "GraphRuntimeError",
    "MalformedDispatchOrderError",
    "NodeExecutionError",
    "NodeResultError",
    "SuperstepLimitError",
]


class GraphRuntimeError(RuntimeError):
    """Base for neutral-core execution failures (runs raise, never return failed).

    ``succeeded_*`` carry the failed superstep's surviving work: when sibling
    tasks had already completed before the failure, the executor attaches
    their identities and proposed writes so the scheduler can persist them as
    pending writes. Step atomicity holds (nothing commits), yet succeeded
    tasks never re-execute on failure resume (langgraph parity, empirical
    2026-07-17: after a failed step, ``get_state`` shows siblings' writes and
    resume re-runs only the failed task against the pre-step snapshot).
    """

    succeeded_tasks: tuple[tuple[str, int], ...] = ()
    succeeded_writes: tuple = ()  # ChannelWrite instances; untyped to stay import-free
    succeeded_pull_nodes: tuple[str, ...] = ()
    unfinished_sends: tuple = ()  # Send packets drained but never completed

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
    """A node returned something other than a Mapping, Command, or None."""


class MalformedDispatchOrderError(GraphRuntimeError):
    """effects.dispatch_order did not return an exact permutation of the ready set."""


class SuperstepLimitError(GraphRuntimeError):
    """superstep_cap exceeded with tasks still ready (future cycle-budget hook)."""


class CheckpointSink(Protocol):
    """Structural checkpoint contract; ``GraphCheckpointStore`` satisfies it.

    The scheduler stays decoupled from the concrete store: records are
    digest/progress markers only — resume/fork is NOT claimed by this slice.
    """

    run_id: str

    def checkpoint(self, superstep: int, node_id: str, state_ref: str) -> object: ...
