"""Versioned state channels for the neutral graph core (Candidate Slice A).

Two-phase contract: the scheduler validates EVERY channel's write group
(``validate``) before committing ANY of them (``commit``), so a failed
superstep commits nothing — no value mutates, no version advances.

Versions advance by exactly one per superstep in which a committed write
group lands (never per write). ``version == 0`` means never written.

Explicit channels only: channels are declared at compile time via
``GraphBuilder.add_channel``; a write to an undeclared name fails closed
with :class:`UnknownChannelError`.
"""

from __future__ import annotations

import copy
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Mapping, Sequence, TypeVar

__all__ = [
    "AppendChannel",
    "BarrierChannel",
    "BarrierMemberError",
    "Channel",
    "ChannelWrite",
    "ChannelWriteConflictError",
    "EmptyChannelError",
    "LastValueChannel",
    "ReducerChannel",
    "TopicChannel",
    "TriggerChannel",
    "UnknownChannelError",
]

logger = logging.getLogger(__name__)

V = TypeVar("V")


@dataclass(frozen=True)
class ChannelWrite:
    """One task's proposed write to one named channel.

    ``task_seq`` distinguishes multiple tasks of one node in one superstep
    (0 = trigger-driven PULL task, Slice A behavior; 1..N = Send-driven PUSH
    tasks). It is part of the canonical commit sort key so same-node task
    writes never tie — final state stays execution-order-invariant.
    """

    node_id: str
    channel: str
    value: Any
    task_seq: int = 0


class EmptyChannelError(LookupError):
    """Reading a channel that has never been written."""

    def __init__(self, channel: str) -> None:
        super().__init__(f"channel {channel!r} has never been written")
        self.channel = channel


class UnknownChannelError(LookupError):
    """A write targeted an undeclared or scheduler-reserved channel name."""

    def __init__(self, channel: str, *, node_id: str = "", reason: str = "undeclared") -> None:
        if reason == "reserved":
            detail = "is reserved for the scheduler ('__'-prefixed names)"
        else:
            detail = "is not a declared channel (declare it with GraphBuilder.add_channel)"
        super().__init__(
            f"channel {channel!r} {detail}; write from {node_id!r} rejected (fail closed)"
        )
        self.channel = channel
        self.node_id = node_id
        self.reason = reason


class ChannelWriteConflictError(RuntimeError):
    """More than one same-superstep write hit a one-write-per-step channel."""

    def __init__(self, channel: str, superstep: int, writers: Sequence[str]) -> None:
        self.channel = channel
        self.superstep = superstep
        self.writers = tuple(sorted(writers))
        super().__init__(
            f"channel {channel!r} received {len(self.writers)} writes in superstep "
            f"{superstep} from nodes {list(self.writers)}: a last-value channel "
            "accepts exactly one write per superstep (use AppendChannel or a "
            "reducer channel to accumulate)"
        )


class Channel(ABC, Generic[V]):
    """Versioned state cell with a two-phase write protocol."""

    def __init__(self) -> None:
        self.version: int = 0
        self.name: str = ""

    @abstractmethod
    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        """Raise if this superstep's write group is illegal. Must not mutate."""

    @abstractmethod
    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        """Apply a validated write group; bump ``version`` by exactly one.

        Returns True iff the version advanced this superstep.
        """

    @abstractmethod
    def get(self) -> V:
        """Committed value. Raises :class:`EmptyChannelError` if never written."""

    @property
    def is_empty(self) -> bool:
        return self.version == 0

    def checkpoint(self) -> dict[str, Any]:
        """JSON-serializable STATE of this channel (not ``get()`` — that raises
        when empty and hides barrier/topic internals). Round-trips through
        :meth:`restore`. Subclasses add their own payload under ``data``."""
        return {"version": self.version}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Rebuild channel state from a :meth:`checkpoint` payload."""
        self.version = int(snapshot["version"])


class LastValueChannel(Channel[Any]):
    """Default channel: at most ONE write per superstep (LastValue parity).

    Any two same-superstep writes conflict — same node, different nodes,
    equal values: all illegal. Overwrites across supersteps are the point
    of last-value and never conflict.
    """

    def __init__(self) -> None:
        super().__init__()
        self._value: Any = None

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        if len(writes) > 1:
            raise ChannelWriteConflictError(
                writes[0].channel, superstep, [w.node_id for w in writes]
            )

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._value = writes[0].value
        self.version += 1
        return True

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return self._value

    def checkpoint(self) -> dict[str, Any]:
        return {"version": self.version, "value": self._value}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._value = snapshot.get("value")


class AppendChannel(Channel[list[Any]]):
    """Reducer channel accumulating writes into a list (``operator.add`` parity).

    A write whose value is a list EXTENDS the accumulator; any other value
    APPENDS as one element. Multiple same-superstep writes are legal and
    applied in the caller-given (canonical) order.
    """

    def __init__(self) -> None:
        super().__init__()
        self._items: list[Any] = []

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        for write in writes:
            if isinstance(write.value, list):
                self._items.extend(write.value)
            else:
                self._items.append(write.value)
        self.version += 1
        return True

    def get(self) -> list[Any]:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return list(self._items)

    def checkpoint(self) -> dict[str, Any]:
        return {"version": self.version, "items": list(self._items)}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._items = list(snapshot.get("items", []))


class ReducerChannel(Channel[Any]):
    """Generic binary-reducer channel (``Annotated[T, reducer]`` parity).

    Multiple same-superstep writes are legal; each folds LEFT onto the
    accumulator in caller-given (canonical) order. The reducer must be a
    pure, associative binary callable — associativity is the batching
    invariance contract: ``reduce(reduce(s, xs), ys) == reduce(s, xs+ys)``
    (spec §3 property 5). ``empty_value`` seeds the accumulator before the
    first fold (langgraph constructs the annotated type's default — ``[]``
    for a list, ``0`` for an int).
    """

    def __init__(
        self,
        reducer: "Any",
        empty_value: Any = None,
    ) -> None:
        super().__init__()
        self._reducer = reducer
        self._empty = empty_value
        self._value: Any = empty_value

    def _fold(self, start: Any, writes: Sequence[ChannelWrite]) -> Any:
        value = start
        for write in writes:
            value = self._reducer(value, write.value)
        return value

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        """Stage the whole fold on a deep copy — a raising reducer or an
        unserializable folded result must fail BEFORE any channel commits
        (all-or-nothing superstep contract; commit() never validates)."""
        if not writes:
            return None
        staged = self._fold(copy.deepcopy(self._value), writes)
        try:
            json.dumps(
                staged, sort_keys=True, ensure_ascii=False, allow_nan=False
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"reducer on channel {writes[0].channel!r} produced a value "
                f"that is not stably JSON-serializable in superstep "
                f"{superstep}: {exc}"
            ) from exc
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._value = self._fold(self._value, writes)
        self.version += 1
        return True

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return self._value

    def checkpoint(self) -> dict[str, Any]:
        return {"version": self.version, "value": self._value}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._value = snapshot.get("value", self._empty)


class TriggerChannel(Channel[bool]):
    """Scheduler-owned barrier channel (``__trigger__:*``): payload-free.

    Any number of same-superstep writes is one activation. Send-style
    fanout payloads ride :class:`TopicChannel` instead.
    """

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self.version += 1
        return True

    def get(self) -> bool:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return True


class BarrierMemberError(RuntimeError):
    """A barrier channel received a write from a node outside its member set.

    langgraph parity: ``NamedBarrierValue.update`` raises ``InvalidUpdateError``
    for a value not in ``names`` (fail closed on stray writers).
    """

    def __init__(self, channel: str, superstep: int, writer: str, names: frozenset[str]) -> None:
        self.channel = channel
        self.superstep = superstep
        self.writer = writer
        self.names = names
        super().__init__(
            f"barrier channel {channel!r} received a write of {writer!r} in "
            f"superstep {superstep}, which is not in its member set "
            f"{sorted(names)} (fail closed)"
        )


class BarrierChannel(Channel[bool]):
    """All-of join channel (langgraph ``NamedBarrierValue`` parity).

    Each member source commits its OWN node name as the write value. The
    version advances ONLY when every member has been seen (then the seen-set
    resets — the barrier re-arms, matching langgraph ``consume()``). A commit
    group containing only already-seen members does not bump the version.

    Recorded deviation: langgraph bumps the join channel's version on every
    new member; advance-at-completion is scheduling-equivalent for our ready
    predicate (which has no ``is_available``) but differs in version-space.
    """

    def __init__(self, names: frozenset[str]) -> None:
        super().__init__()
        self.names = frozenset(names)
        self._seen: set[str] = set()

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        for write in writes:
            if write.value not in self.names:
                raise BarrierMemberError(
                    write.channel, superstep, str(write.value), self.names
                )

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        for write in writes:
            self._seen.add(write.value)
        if self._seen == self.names:
            self._seen = set()
            self.version += 1
            return True
        return False

    @property
    def seen(self) -> frozenset[str]:
        return frozenset(self._seen)

    def get(self) -> bool:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return True

    def checkpoint(self) -> dict[str, Any]:
        return {"version": self.version, "seen": sorted(self._seen)}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._seen = set(snapshot.get("seen", []))


class TopicChannel(Channel[list[Any]]):
    """Accumulating pub-sub channel (langgraph ``Topic`` parity, non-persistent).

    Backs the scheduler-owned ``__tasks__`` channel carrying Send packets:
    list values extend, scalars append; the version bumps once per non-empty
    commit; :meth:`drain` returns-and-clears (the scheduler drains at task
    preparation, so pending Sends live exactly one barrier).
    """

    def __init__(self) -> None:
        super().__init__()
        self._items: list[Any] = []

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        for write in writes:
            if isinstance(write.value, list):
                self._items.extend(write.value)
            else:
                self._items.append(write.value)
        self.version += 1
        return True

    def drain(self) -> list[Any]:
        items = self._items
        self._items = []
        return items

    def get(self) -> list[Any]:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return list(self._items)

    def checkpoint(self) -> dict[str, Any]:
        return {"version": self.version, "items": list(self._items)}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._items = list(snapshot.get("items", []))
