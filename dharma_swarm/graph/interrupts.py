"""Interrupt-as-write primitives for human-in-the-loop resume (LG08a).

langgraph 1.2.4 parity, verified empirically 2026-07-17:

- ``interrupt(value)`` inside a node suspends the run and surfaces the
  payload; the interrupted superstep commits nothing (LG06 atomicity),
  succeeded siblings persist as pending writes.
- Resume re-executes the interrupted node FROM THE TOP; recorded resume
  values are returned by call order, task-scoped; consecutive interrupts
  in one node share one deterministic, task-scoped interrupt id.
- ``Command(resume=...)`` without a persistence kernel fails closed
  (langgraph: RuntimeError "Cannot use Command(resume=...) without
  checkpointer").

The dharma engine RAISES :class:`GraphInterrupted` (failure doctrine: runs
raise, they never return suspended results); the payload rides the error.
Resume values are persisted inside the failed step's pending-write record
under the reserved ``__resume__:<node>`` entry, which the failure-resume
replay path strips before applying real writes.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import contextvars
import hashlib
from dataclasses import dataclass, field
from typing import Any

from dharma_swarm.graph.errors import GraphRuntimeError

__all__ = [
    "GraphInterrupt",
    "GraphInterrupted",
    "Interrupt",
    "InterruptFrame",
    "RESUME_PREFIX",
    "interrupt",
    "resume_channel",
]

RESUME_PREFIX = "__resume__:"


def resume_channel(node_id: str, task_seq: int = 0) -> str:
    """Reserved pending-record entry name carrying ONE TASK's resume values.

    Keyed by the full task identity ``(node_id, task_seq)`` — N Send packets
    to one interrupting node are N distinct interrupts, each resumed
    independently (a node-only key would replay one resume into every
    packet).
    """
    return f"{RESUME_PREFIX}{node_id}:{task_seq}"


@dataclass(frozen=True)
class Interrupt:
    """One surfaced interrupt: the payload and its task-scoped stable id."""

    value: Any
    id: str


class GraphInterrupt(Exception):
    """INTERNAL control-flow signal raised by :func:`interrupt`.

    Passes through the node-error wrapper unwrapped (like CancelledError)
    so the executor can convert it into the public typed
    :class:`GraphInterrupted` with sibling payload attached. Never catch
    this in node code.
    """

    def __init__(self, intr: Interrupt, consumed: tuple[Any, ...]) -> None:
        super().__init__(f"graph interrupted: {intr.id}")
        self.interrupt = intr
        self.consumed = consumed


class GraphInterrupted(GraphRuntimeError):
    """A run suspended on :func:`interrupt`; resume with ``Command(resume=)``.

    Carries the surfaced interrupt(s) plus the inherited ``succeeded_*``
    sibling payload so the scheduler persists surviving work exactly like a
    task failure. ``consumed_resumes`` is the full ordered list of resume
    values the interrupted node consumed before suspending again — the
    persistence layer stores it for the next resume's replay.
    """

    interrupts: tuple[Interrupt, ...] = ()
    consumed_resumes: tuple[Any, ...] = ()
    task_seq: int = 0


@dataclass
class InterruptFrame:
    """Per-task interrupt context: FULL task identity plus resume values."""

    run_id: str
    node_id: str
    task_seq: int = 0
    resumes: list[Any] = field(default_factory=list)
    counter: int = 0

    def interrupt_id(self) -> str:
        digest = hashlib.sha256(
            f"{self.run_id}:{self.node_id}:{self.task_seq}".encode("utf-8")
        ).hexdigest()
        return digest[:32]


_ACTIVE_FRAME: contextvars.ContextVar[InterruptFrame | None] = (
    contextvars.ContextVar("dharmagraph_interrupt_frame", default=None)
)


def push_frame(frame: InterruptFrame) -> contextvars.Token:
    """Executor-only: bind the running task's interrupt frame."""
    return _ACTIVE_FRAME.set(frame)


def pop_frame(token: contextvars.Token) -> None:
    """Executor-only: unbind the running task's interrupt frame."""
    _ACTIVE_FRAME.reset(token)


def interrupt(value: Any) -> Any:
    """Suspend the run here, surfacing ``value``; return the resume value.

    Call order is the replay key: the k-th ``interrupt`` call in a node
    returns the k-th recorded resume value; the first unrecorded call
    raises :class:`GraphInterrupt`, aborting the superstep (nothing
    commits). The node re-executes from the top on every resume —
    langgraph parity — so code before an interrupt must be idempotent.
    """
    frame = _ACTIVE_FRAME.get()
    if frame is None:
        raise GraphRuntimeError(
            "interrupt() called outside a graph task (fail closed)"
        )
    index = frame.counter
    frame.counter += 1
    if index < len(frame.resumes):
        return frame.resumes[index]
    raise GraphInterrupt(
        Interrupt(value=value, id=frame.interrupt_id()),
        consumed=tuple(frame.resumes),
    )
