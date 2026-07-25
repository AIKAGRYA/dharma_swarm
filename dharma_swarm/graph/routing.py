"""Dynamic routing vocabulary: Send, Command, conditional branches (Slice B).

State-driven routing WITHOUT mutable shared state: every routing decision is
expressed as channel writes that commit at the superstep barrier, so dynamic
topologies inherit the engine's determinism, atomicity, and replay guarantees.

langgraph 1.2.4 parity notes (deviations recorded in the PR body):
- path callables may return a mapped key, a list of keys, ``END``, or
  :class:`Send` objects; unmapped key / ``None`` / ``START`` / ``Send(END)``
  raise typed errors mirroring langgraph's KeyError / ValueError /
  InvalidUpdateError vocabulary.
- ``path_map`` is REQUIRED (dict or list). langgraph can infer destinations
  from ``Literal`` return hints and otherwise WARN-drops unknown names at
  runtime; requiring the map and raising is strictly fail-closed.
- ``Command.goto`` is ADDITIVE to static/branch routing (verified against
  langgraph source: static edges are unconditional writers; goto only adds).
- Send/goto to an unknown node raises :class:`SendTargetError` (langgraph
  WARN-drops — recorded deviation, fail closed).

claim_mode: candidate / test_only — not wired into production dispatch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from dharma_swarm.graph.channels import ChannelWrite, UnknownChannelError
from dharma_swarm.graph.errors import NodeResultError
from dharma_swarm.graph.types import (
    END,
    RESERVED_PREFIX,
    START,
    TASKS_CHANNEL,
    trigger_channel,
)

__all__ = [
    "BranchDestinationError",
    "BranchSpec",
    "Command",
    "ParentCommand",
    "Send",
    "SendTargetError",
    "evaluate_branch",
    "interpret_result",
    "join_channel",
]

logger = logging.getLogger(__name__)

PathCallable = Callable[[Mapping[str, Any]], Any]


class BranchDestinationError(ValueError):
    """A branch path returned something that is not a valid destination."""

    def __init__(self, source: str, message: str, *, returned: Any = None) -> None:
        super().__init__(message)
        self.source = source
        self.returned = returned


class SendTargetError(ValueError):
    """A Send or Command.goto referenced an unknown or illegal node."""

    def __init__(self, node: str, message: str) -> None:
        super().__init__(message)
        self.node = node


@dataclass(frozen=True)
class Send:
    """One dynamic task: run ``node`` next superstep with ``arg`` as its input.

    The target executes with a deep copy of ``arg`` — NOT the shared state
    snapshot (langgraph parity: map-reduce fan-out with per-task inputs).
    N Sends to one node = N independent tasks in one superstep. Never use
    Send as a dict key or set member (unhashable by design this slice).

    ``timeout`` bounds the target task's execution in seconds (langgraph
    ``Send(..., timeout=)`` parity): an overrun cancels the task and fails
    its superstep with a typed timeout execution error, exactly like any
    other task failure (LG06 atomicity applies).
    """

    node: str
    arg: Any
    timeout: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"node": self.node, "arg": self.arg, "timeout": self.timeout}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Send:
        return cls(
            node=str(data["node"]),
            arg=data.get("arg"),
            timeout=data.get("timeout"),
        )


_RESUME_UNSET: Any = object()


class ParentCommand(Exception):
    """A ``Command(graph=Command.PARENT)`` bubbling out of its graph run.

    Raised where the command is interpreted; a subgraph wrapper
    (``subgraph.as_node``) catches it ONE level up and returns the carried
    command as the parent node's result. Reaching the caller uncaught means
    the command was issued with no parent graph — langgraph 1.2.4 parity
    (empirical: top-level ``Command.PARENT`` raises ``ParentCommand``).
    """

    def __init__(self, command: "Command") -> None:
        super().__init__(f"Command(graph=PARENT) with no parent graph: {command!r}")
        self.command = command


@dataclass(frozen=True)
class Command:
    """Node return value combining state writes with dynamic routing.

    ``update`` = channel writes (same validation as a plain Mapping return);
    ``goto`` = node name(s) and/or :class:`Send` packets triggered for the
    next superstep, ADDITIVE to the node's static and branch routing.
    ``goto=END`` entries are silently skipped (langgraph parity).

    ``resume`` is INPUT-ONLY (``invoke(input=Command(resume=v))``): it
    answers a pending :func:`dharma_swarm.graph.interrupts.interrupt` on a
    persisted thread. A node RETURNING a resume command fails closed —
    langgraph resumes only from the caller side. ``None`` is a legal resume
    value, so presence is tracked against an unset sentinel.

    ``graph=Command.PARENT`` addresses the command ONE level up: the node's
    own run aborts and the parent graph applies ``update`` through ITS
    reducers and ``goto`` to ITS nodes (langgraph parity; empirical: the
    child's local writes never reach the parent). With no parent, the
    bubbling :class:`ParentCommand` reaches the caller. Only the PARENT
    sentinel is supported — arbitrary graph addressing fails closed.
    """

    PARENT = "__parent__"

    update: Mapping[str, Any] | None = None
    goto: str | Send | Sequence[str | Send] = field(default_factory=tuple)
    resume: Any = _RESUME_UNSET
    graph: Any = None

    @property
    def has_resume(self) -> bool:
        return self.resume is not _RESUME_UNSET

    def goto_items(self) -> tuple[str | Send, ...]:
        if isinstance(self.goto, (str, Send)):
            return (self.goto,)
        return tuple(self.goto)


@dataclass(frozen=True)
class BranchSpec:
    """A compiled conditional edge: source node + path callable + key map."""

    source: str
    path: PathCallable
    path_map: Mapping[str, str]

    def destinations(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.path_map.values())))


def join_channel(sources: Sequence[str], target: str) -> str:
    """Reserved name for the all-of join channel of a list-form edge."""
    return f"__join__:{'+'.join(sorted(sources))}:{target}"


def send_write(
    origin: str, send: Send, task_seq: int, known_nodes: Mapping[str, Any]
) -> ChannelWrite:
    """A Send packet as a write to the task channel (arg deep-copied at store)."""
    import copy

    if send.node not in known_nodes:
        raise SendTargetError(
            send.node,
            f"Send from {origin!r} targets unknown node {send.node!r} "
            "(fail closed; langgraph WARN-drops)",
        )
    return ChannelWrite(
        origin,
        TASKS_CHANNEL,
        Send(send.node, copy.deepcopy(send.arg), timeout=send.timeout),
        task_seq,
    )


def interpret_result(
    node_id: str,
    result: Mapping[str, Any] | Command | None,
    *,
    run_id: str,
    superstep: int,
    task_seq: int,
    known_nodes: Mapping[str, Any],
) -> list[ChannelWrite]:
    """Turn a node return (Mapping / Command / None) into channel writes.

    Command.goto is ADDITIVE to static routing (langgraph parity); goto=END is
    silently skipped; reserved/non-string keys and unknown goto targets fail
    closed.
    """
    if result is None:
        return []
    writes: list[ChannelWrite] = []
    if isinstance(result, Command):
        if result.has_resume:
            raise NodeResultError(
                f"node {node_id!r} returned Command(resume=...) in superstep "
                f"{superstep}; resume commands are invoke-input only "
                "(fail closed)",
                graph_run_id=run_id,
                superstep=superstep,
                node_id=node_id,
            )
        if result.graph is not None:
            if result.graph == Command.PARENT:
                raise ParentCommand(result)
            raise NodeResultError(
                f"node {node_id!r} returned Command(graph={result.graph!r}) "
                f"in superstep {superstep}; only Command.PARENT addressing "
                "is supported (fail closed)",
                graph_run_id=run_id,
                superstep=superstep,
                node_id=node_id,
            )
        if result.update is not None:
            writes.extend(
                _mapping_writes(
                    node_id, result.update, run_id, superstep, task_seq
                )
            )
        for target in result.goto_items():
            if isinstance(target, Send):
                writes.append(send_write(node_id, target, task_seq, known_nodes))
            elif target == END:
                continue
            elif target in known_nodes:
                writes.append(
                    ChannelWrite(node_id, trigger_channel(target), True, task_seq)
                )
            else:
                raise SendTargetError(
                    str(target),
                    f"Command.goto from {node_id!r} references unknown node "
                    f"{target!r} (fail closed; langgraph WARN-drops)",
                )
        return writes
    if not isinstance(result, Mapping):
        raise NodeResultError(
            f"node {node_id!r} returned {type(result).__name__!r} in superstep "
            f"{superstep}; nodes must return a Mapping, a Command, or None "
            "(fail closed)",
            graph_run_id=run_id,
            superstep=superstep,
            node_id=node_id,
        )
    return _mapping_writes(node_id, result, run_id, superstep, task_seq)


def _mapping_writes(
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
                f"node {node_id!r} returned non-string channel key {key!r} in "
                f"superstep {superstep}",
                graph_run_id=run_id,
                superstep=superstep,
                node_id=node_id,
            )
        if key.startswith(RESERVED_PREFIX):
            raise UnknownChannelError(key, node_id=node_id, reason="reserved")
        writes.append(ChannelWrite(node_id, key, mapping[key], task_seq))
    return writes


def evaluate_branch(
    spec: BranchSpec, state_view: Mapping[str, Any]
) -> list[str | Send]:
    """Run the path callable and resolve its result to destinations.

    Pure: no effects access. Raises :class:`BranchDestinationError` /
    :class:`SendTargetError` on invalid results — the scheduler evaluates
    pre-commit, so a bad path aborts its superstep atomically.
    """
    result = spec.path(state_view)
    raw: list[Any]
    if result is None:
        raise BranchDestinationError(
            spec.source,
            f"branch on {spec.source!r} did not return a valid destination "
            "(got None)",
            returned=None,
        )
    if isinstance(result, (str, Send)):
        raw = [result]
    elif isinstance(result, Sequence):
        raw = list(result)
    else:
        raise BranchDestinationError(
            spec.source,
            f"branch on {spec.source!r} returned {type(result).__name__!r}; "
            "expected a mapped key, END, a Send, or a sequence of those",
            returned=result,
        )

    destinations: list[str | Send] = []
    for item in raw:
        if isinstance(item, Send):
            if item.node == END:
                raise SendTargetError(
                    END, "cannot send a packet to the END node"
                )
            destinations.append(item)
            continue
        if not isinstance(item, str) or item == START:
            raise BranchDestinationError(
                spec.source,
                f"branch on {spec.source!r} did not return a valid destination "
                f"(got {item!r})",
                returned=item,
            )
        if item == END:
            destinations.append(END)
            continue
        try:
            destinations.append(spec.path_map[item])
        except KeyError:
            raise BranchDestinationError(
                spec.source,
                f"branch on {spec.source!r} returned key {item!r} which is not "
                f"in its path_map {sorted(spec.path_map)}",
                returned=item,
            ) from None
    return destinations
