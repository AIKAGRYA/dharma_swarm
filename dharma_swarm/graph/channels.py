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

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Sequence, TypeVar

__all__ = [
    "AppendChannel",
    "Channel",
    "ChannelWrite",
    "ChannelWriteConflictError",
    "EmptyChannelError",
    "LastValueChannel",
    "TriggerChannel",
    "UnknownChannelError",
]

logger = logging.getLogger(__name__)

V = TypeVar("V")


@dataclass(frozen=True)
class ChannelWrite:
    """One node's proposed write to one named channel."""

    node_id: str
    channel: str
    value: Any


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


class TriggerChannel(Channel[bool]):
    """Scheduler-owned barrier channel (``__trigger__:*``): payload-free.

    Any number of same-superstep writes is one activation. The designed
    upgrade path for Send-style fanout is a payload-carrying Topic variant
    of this class — :class:`ChannelWrite` already carries a value.
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
