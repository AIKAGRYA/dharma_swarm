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
- EVERY task that suspends in one superstep surfaces its own interrupt:
  a step with N interrupting tasks raises ONE error carrying all N
  (LG20 multiple_interrupts), ordered canonically by ``(node_id,
  task_seq)`` — NOT by dispatch order, so the surfaced sequence is
  execution-order-invariant like every other committed artifact
  (LG20 interrupt_order).
- ``Command(resume={interrupt_id: value})`` resolves pending interrupts
  individually by id; a bare ``Command(resume=value)`` is legal only
  while exactly one interrupt is pending (langgraph 1.2.4 parity,
  verified empirically 2026-08-05: a scalar resume against multiple
  pending interrupts raises RuntimeError "When there are multiple
  pending interrupts, you must specify the interrupt id when
  resuming"). Resolving a subset is legal: the unresolved interrupts
  re-surface on the next step and their tasks stay suspended.

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
from typing import Any, Mapping, Sequence

from dharma_swarm.graph.errors import GraphRuntimeError

__all__ = [
    "GraphInterrupt",
    "GraphInterrupted",
    "Interrupt",
    "InterruptFrame",
    "InterruptRecord",
    "RESUME_PREFIX",
    "interrupt",
    "interrupt_id",
    "resolve_resume_values",
    "resume_channel",
    "task_key",
]

RESUME_PREFIX = "__resume__:"


def task_key(node_id: str, task_seq: int = 0) -> str:
    """Resume-map key for one task identity (``"<node_id>:<task_seq>"``)."""
    return f"{node_id}:{task_seq}"


def resume_channel(node_id: str, task_seq: int = 0) -> str:
    """Reserved pending-record entry name carrying ONE TASK's resume values.

    Keyed by the full task identity ``(node_id, task_seq)`` — N Send packets
    to one interrupting node are N distinct interrupts, each resumed
    independently (a node-only key would replay one resume into every
    packet).
    """
    return f"{RESUME_PREFIX}{task_key(node_id, task_seq)}"


def interrupt_id(run_id: str, node_id: str, task_seq: int = 0) -> str:
    """The deterministic, task-scoped public id of a task's interrupt.

    Pure function of the task identity, so it is stable across resumes and
    recomputable by the scheduler from a pending record's task keys — that
    recomputation is what lets ``Command(resume={id: value})`` address an
    individual pending interrupt without persisting an id->task index.
    """
    digest = hashlib.sha256(
        f"{run_id}:{node_id}:{task_seq}".encode("utf-8")
    ).hexdigest()
    return digest[:32]


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


@dataclass(frozen=True)
class InterruptRecord:
    """One suspended TASK: its identity, surfaced interrupt, consumed resumes.

    A superstep may suspend several tasks at once, so the public error carries
    a tuple of these rather than a single node identity. ``consumed_resumes``
    is that task's own ordered resume history, which the persistence layer
    re-journals under its own ``__resume__:<node>:<seq>`` entry — one task's
    answers must never replay into another's call sequence.
    """

    node_id: str
    task_seq: int
    interrupt: Interrupt
    consumed_resumes: tuple[Any, ...] = ()

    @property
    def key(self) -> str:
        return task_key(self.node_id, self.task_seq)


class GraphInterrupted(GraphRuntimeError):
    """A run suspended on :func:`interrupt`; resume with ``Command(resume=)``.

    Carries the surfaced interrupt(s) plus the inherited ``succeeded_*``
    sibling payload so the persistence layer stores surviving work exactly like a
    task failure. ``suspended`` is the authoritative per-task view: every task
    that suspended this superstep, ordered canonically by ``(node_id,
    task_seq)``. ``interrupts`` is the matching payload tuple (langgraph's
    ``__interrupt__`` shape).

    ``node_id``, ``task_seq`` and ``consumed_resumes`` describe the FIRST
    canonical suspended task and exist so single-interrupt callers written
    against the LG08 resume slice keep working unchanged; anything handling
    multiple interrupts must read ``suspended``.
    """

    interrupts: tuple[Interrupt, ...] = ()
    suspended: tuple[InterruptRecord, ...] = ()
    consumed_resumes: tuple[Any, ...] = ()
    task_seq: int = 0

    def attach(self, records: Sequence[InterruptRecord]) -> None:
        """Bind every suspended task, canonically ordered, to this error."""
        ordered = tuple(
            sorted(records, key=lambda record: (record.node_id, record.task_seq))
        )
        if not ordered:
            raise ValueError("GraphInterrupted requires at least one record")
        self.suspended = ordered
        self.interrupts = tuple(record.interrupt for record in ordered)
        first = ordered[0]
        self.node_id = first.node_id
        self.task_seq = first.task_seq
        self.consumed_resumes = first.consumed_resumes

    def resume_entries(self) -> list[tuple[str, list[Any]]]:
        """Reserved pending-record entries carrying each task's resume history."""
        return [
            (
                resume_channel(record.node_id, record.task_seq),
                list(record.consumed_resumes),
            )
            for record in self.suspended
        ]


def resolve_resume_values(
    resume: Any,
    pending_keys: Sequence[str],
    run_id: str,
) -> dict[str, Any]:
    """Map one ``Command(resume=...)`` payload onto pending task keys.

    ``pending_keys`` are the ``"<node_id>:<task_seq>"`` keys of the tasks that
    are currently suspended. Returns ``{task_key: value}`` for the tasks this
    command answers — possibly a subset, since resolving some interrupts and
    leaving others pending is legal.

    Dict form is recognised by CONTENT, not by type: a mapping is read as an
    id->value map only when every key is a known pending interrupt id. That
    keeps a plain dict usable as an ordinary resume *value* (the common
    ``{"approved": True}`` case) while a partially-matching mapping — genuinely
    ambiguous — fails closed rather than guessing.
    """
    by_id: dict[str, str] = {}
    for key in pending_keys:
        node_id, _, raw_seq = key.rpartition(":")
        by_id[interrupt_id(run_id, node_id, int(raw_seq))] = key
    if isinstance(resume, Mapping) and resume:
        matched = [key for key in resume if key in by_id]
        if len(matched) == len(resume):
            return {by_id[key]: resume[key] for key in matched}
        if matched:
            unknown = sorted(str(key) for key in resume if key not in by_id)
            raise GraphRuntimeError(
                "Command(resume=...) mixes known interrupt ids with "
                f"unrecognised keys {unknown!r}; pass only interrupt ids to "
                "resume individually, or a bare value to resume a single "
                "pending interrupt (fail closed)",
                graph_run_id=run_id,
            )
    if len(pending_keys) != 1:
        raise GraphRuntimeError(
            "Command(resume=...) carries a single value but "
            f"{len(pending_keys)} interrupts are pending "
            f"({sorted(pending_keys)!r}); address them by interrupt id "
            "(langgraph parity: resuming multiple pending interrupts "
            "requires the interrupt id) (fail closed)",
            graph_run_id=run_id,
        )
    return {pending_keys[0]: resume}


@dataclass
class InterruptFrame:
    """Per-task interrupt context: FULL task identity plus resume values."""

    run_id: str
    node_id: str
    task_seq: int = 0
    resumes: list[Any] = field(default_factory=list)
    counter: int = 0

    def interrupt_id(self) -> str:
        return interrupt_id(self.run_id, self.node_id, self.task_seq)


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
