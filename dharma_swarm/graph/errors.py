"""Typed execution errors + checkpoint protocol for the neutral graph core.

Failure doctrine: runs RAISE these; they never return failed results — a
failed superstep commits nothing, checkpoints nothing, yields no result.
Re-exported by ``scheduler`` so existing imports keep working.
"""

from __future__ import annotations

from typing import Literal, Protocol

__all__ = [
    "CheckpointSink",
    "GraphRuntimeError",
    "MalformedDispatchOrderError",
    "NodeExecutionError",
    "NodeResultError",
    "NodeTimeoutError",
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


class NodeTimeoutError(GraphRuntimeError):
    """A node attempt exceeded one of its configured timeout bounds.

    Mirrors ``langgraph.errors.NodeTimeoutError``: ``run_timeout`` and
    ``idle_timeout`` both report the policy in force when the bound fired
    (``None`` when unconfigured), and ``kind`` says which one it was.

    Deliberately NOT a subclass of the built-in ``TimeoutError`` (which is an
    ``OSError``, a class the default retry predicate refuses to retry) — the
    reference makes the same choice for the same reason, so a timed-out node is
    retryable under the DEFAULT policy. See ``retry.default_retry_on``.
    """

    def __init__(
        self,
        node: str,
        elapsed: float,
        *,
        kind: Literal["run", "idle"],
        run_timeout: float | None = None,
        idle_timeout: float | None = None,
        graph_run_id: str = "",
        superstep: int = -1,
    ) -> None:
        if kind == "run":
            if run_timeout is None:
                raise ValueError("run_timeout is required when kind='run'")
            bound = run_timeout
            message = (
                f"Node {node!r} exceeded its run timeout of {run_timeout:.3f}s "
                f"(elapsed: {elapsed:.3f}s)."
            )
        elif kind == "idle":
            if idle_timeout is None:
                raise ValueError("idle_timeout is required when kind='idle'")
            bound = idle_timeout
            message = (
                f"Node {node!r} exceeded its idle timeout of "
                f"{idle_timeout:.3f}s without making progress "
                f"(elapsed: {elapsed:.3f}s)."
            )
        else:
            raise ValueError("kind must be 'run' or 'idle'")
        super().__init__(
            message,
            graph_run_id=graph_run_id,
            superstep=superstep,
            node_id=node,
        )
        self.node = node
        self.elapsed = elapsed
        self.kind = kind
        self.timeout = bound
        self.run_timeout = run_timeout
        self.idle_timeout = idle_timeout


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
