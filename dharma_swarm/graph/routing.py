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

from dharma_swarm.graph.types import END, START

__all__ = [
    "BranchDestinationError",
    "BranchSpec",
    "Command",
    "Send",
    "SendTargetError",
    "evaluate_branch",
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
    """

    node: str
    arg: Any


@dataclass(frozen=True)
class Command:
    """Node return value combining state writes with dynamic routing.

    ``update`` = channel writes (same validation as a plain Mapping return);
    ``goto`` = node name(s) and/or :class:`Send` packets triggered for the
    next superstep, ADDITIVE to the node's static and branch routing.
    ``goto=END`` entries are silently skipped (langgraph parity). No
    ``resume``/``graph`` fields this slice.
    """

    update: Mapping[str, Any] | None = None
    goto: str | Send | Sequence[str | Send] = field(default_factory=tuple)

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
