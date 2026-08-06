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
    "AnyValueChannel",
    "AppendChannel",
    "BarrierChannel",
    "BarrierMemberError",
    "Channel",
    "ChannelWrite",
    "ChannelWriteConflictError",
    "DeltaChannel",
    "EmptyChannelError",
    "EphemeralChannel",
    "LastValueAfterFinishChannel",
    "LastValueChannel",
    "NamedBarrierAfterFinishChannel",
    "ReducerChannel",
    "TopicChannel",
    "TriggerChannel",
    "UnknownChannelError",
    "UntrackedValueChannel",
]

logger = logging.getLogger(__name__)

V = TypeVar("V")

#: Sentinel for "this channel currently holds no value" (langgraph ``MISSING``
#: parity). Never a legal channel value: it is not JSON-serializable, so a
#: write of it fails the digest guard in GraphState's validate phase.
_MISSING: Any = object()


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
    """Versioned state cell with a two-phase write protocol.

    Two optional lifecycle hooks extend the two-phase protocol; both default
    to no-ops so every existing channel keeps its exact behavior:

    * :meth:`end_step` — called on EVERY declared channel at each committed
      superstep barrier (langgraph ``update(EMPTY_SEQ)`` parity), so
      step-scoped channels can clear themselves when nobody wrote them.
    * :meth:`finish` — called on every declared channel when a barrier
      commits nothing that can trigger another node, i.e. at (tentative)
      quiescence (langgraph ``BaseChannel.finish`` parity).

    ``tracked = False`` marks a channel whose VALUE never enters the
    checkpoint or the state digest (langgraph ``UntrackedValue`` parity); it
    stays user-visible in :meth:`GraphState.snapshot`.
    """

    #: False iff this channel's value is excluded from checkpoints/digests.
    tracked: bool = True

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

    def end_step(self, had_writes: bool) -> bool:
        """Superstep-boundary notification. Returns True iff state changed.

        ``had_writes`` is True iff this channel was in the barrier's committed
        write group. Persistent channels ignore the notification entirely.
        Never bumps ``version``: clearing a step-scoped channel is not a new
        value, and the ready predicate must not re-fire on it.
        """
        return False

    def finish(self) -> bool:
        """Quiescence notification. Returns True iff state changed.

        Called once per barrier whose commits cannot trigger any node — the
        (tentatively) last superstep. After-finish channels publish their
        held value here; everything else ignores it.
        """
        return False


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


# ---------------------------------------------------------------------------
# Pregel-core LG10: step-scoped, untracked, batch-reducer and after-finish
# channels. Append-only extension of the channel family — every class above
# keeps its exact behavior; the two lifecycle hooks they inherit
# (``end_step`` / ``finish``) are no-ops for them.
# ---------------------------------------------------------------------------


class EphemeralChannel(Channel[Any]):
    """Step-scoped cell (langgraph ``EphemeralValue`` parity).

    "Stores the value received in the step immediately preceding, clears
    after": a write in superstep N is readable by every task of superstep
    N+1 and is dropped at N+1's barrier unless somebody rewrites it. It
    therefore survives into the final state only when the LAST committed
    superstep wrote it.

    ``default`` (when given) is what the channel resets TO instead of
    clearing, so an ephemeral channel can be declared with a resting value;
    with no default the reset makes the channel empty again, which is what
    keeps it out of the snapshot and the digest (langgraph parity).
    ``guard=True`` (default) rejects concurrent writes exactly like
    :class:`LastValueChannel`.
    """

    def __init__(self, default: Any = _MISSING, *, guard: bool = True) -> None:
        super().__init__()
        self.default = default
        self.guard = guard
        self._value: Any = None if default is _MISSING else copy.deepcopy(default)
        self._present = False

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        if self.guard and len(writes) > 1:
            raise ChannelWriteConflictError(
                writes[0].channel, superstep, [w.node_id for w in writes]
            )

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._value = writes[-1].value
        self._present = True
        self.version += 1
        return True

    def end_step(self, had_writes: bool) -> bool:
        if had_writes or not self._present:
            return False
        if self.default is _MISSING:
            self._value = None
            self._present = False
        else:
            self._value = copy.deepcopy(self.default)
        return True

    @property
    def is_empty(self) -> bool:
        return self.version == 0 or not self._present

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return self._value

    def checkpoint(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "value": self._value,
            "present": self._present,
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._value = snapshot.get("value")
        self._present = bool(snapshot.get("present", False))


class AnyValueChannel(Channel[Any]):
    """Concurrency-tolerant last-value cell (langgraph ``AnyValue`` parity).

    Any number of same-superstep writes is legal — upstream "assumes that if
    multiple values are received, they are all equal", so no conflict is
    raised and the LAST write in canonical commit order wins. Like
    ``AnyValue``, the channel clears at a barrier that wrote nothing to it,
    so it is present in the final state only when the last committed
    superstep wrote it.
    """

    def __init__(self) -> None:
        super().__init__()
        self._value: Any = None
        self._present = False

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._value = writes[-1].value
        self._present = True
        self.version += 1
        return True

    def end_step(self, had_writes: bool) -> bool:
        if had_writes or not self._present:
            return False
        self._value = None
        self._present = False
        return True

    @property
    def is_empty(self) -> bool:
        return self.version == 0 or not self._present

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return self._value

    def checkpoint(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "value": self._value,
            "present": self._present,
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._value = snapshot.get("value")
        self._present = bool(snapshot.get("present", False))


class UntrackedValueChannel(Channel[Any]):
    """Last-value cell whose VALUE is never persisted (``UntrackedValue`` parity).

    ``tracked = False`` has two consequences, both required for the resume
    contract to keep holding: the value stays out of :meth:`checkpoint` (only
    the version is durable) AND out of the state digest. If the digest kept
    it, every resume would rebuild a channel without its value and fail the
    integrity check. The value remains user-visible in the live run's
    snapshot, exactly like upstream (present in ``invoke`` output, absent
    from the saver's ``channel_values``).

    ``guard=True`` (default) rejects concurrent writes, matching
    ``UntrackedValue(guard=True)``.
    """

    tracked = False

    def __init__(self, *, guard: bool = True) -> None:
        super().__init__()
        self.guard = guard
        self._value: Any = None
        self._present = False

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        if self.guard and len(writes) > 1:
            raise ChannelWriteConflictError(
                writes[0].channel, superstep, [w.node_id for w in writes]
            )

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._value = writes[-1].value
        self._present = True
        self.version += 1
        return True

    @property
    def is_empty(self) -> bool:
        return self.version == 0 or not self._present

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return self._value

    def checkpoint(self) -> dict[str, Any]:
        """Version-only: the value is deliberately NOT durable."""
        return {"version": self.version, "untracked": True}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._value = None
        self._present = False


class DeltaChannel(Channel[Any]):
    """BATCH-reducer channel (langgraph ``DeltaChannel`` parity).

    Unlike :class:`ReducerChannel`'s binary left fold, the reducer receives
    the whole superstep's writes at once —
    ``reducer(current_value, [w1, w2, ...]) -> new_value`` — in canonical
    commit order. Reducers must be deterministic and batching-invariant
    (``reduce(reduce(s, xs), ys) == reduce(s, xs + ys)``); that property is
    what lets a replay fold larger batches than were originally produced.

    Recorded deviation: upstream stores only a sentinel in checkpoint blobs
    and reconstructs by replaying ancestor writes through the reducer (see
    ``GraphPersistenceKernel.get_delta_channel_history``). This channel
    checkpoints its value-complete state instead. The reconstructed value is
    identical under the batching-invariance contract; only the on-disk
    representation and replay depth differ.
    """

    def __init__(
        self,
        reducer: "Any",
        empty_value: Any = None,
    ) -> None:
        super().__init__()
        self._reducer = reducer
        self._empty = copy.deepcopy(empty_value)
        self._value: Any = copy.deepcopy(empty_value)

    def _fold(self, start: Any, writes: Sequence[ChannelWrite]) -> Any:
        return self._reducer(start, [write.value for write in writes])

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        """Stage the batch fold on a deep copy — a raising reducer or an
        unserializable folded result must fail BEFORE any channel commits."""
        if not writes:
            return None
        staged = self._fold(copy.deepcopy(self._value), writes)
        try:
            json.dumps(staged, sort_keys=True, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"delta reducer on channel {writes[0].channel!r} produced a "
                "value that is not stably JSON-serializable in superstep "
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
        self._value = snapshot.get("value", copy.deepcopy(self._empty))


class LastValueAfterFinishChannel(Channel[Any]):
    """Last value, published only at quiescence (``LastValueAfterFinish`` parity).

    Writes land normally but the channel reads as EMPTY until
    :meth:`finish` runs at the (tentatively) last barrier; a later write
    un-publishes it again. The practical effect matches upstream: the key
    appears in the final state and nowhere in mid-run snapshots.

    Recorded deviation: upstream additionally clears the value when a reader
    ``consume()``s it after finish. This engine has no consume protocol on
    the read path, so the published value persists in the final snapshot
    (which is where the two-arm evidence observes it).
    """

    def __init__(self) -> None:
        super().__init__()
        self._value: Any = None
        self._present = False
        self._finished = False

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        return None

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        self._value = writes[-1].value
        self._present = True
        self._finished = False
        self.version += 1
        return True

    def finish(self) -> bool:
        if self._finished or not self._present:
            return False
        self._finished = True
        return True

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def is_empty(self) -> bool:
        return not (self._present and self._finished)

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return self._value

    def checkpoint(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "value": self._value,
            "present": self._present,
            "finished": self._finished,
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._value = snapshot.get("value")
        self._present = bool(snapshot.get("present", False))
        self._finished = bool(snapshot.get("finished", False))


class NamedBarrierAfterFinishChannel(Channel[Any]):
    """All-of join published only at quiescence (``NamedBarrierValueAfterFinish``).

    Same fail-closed member contract as :class:`BarrierChannel` (a stray
    writer raises :class:`BarrierMemberError`), but the completed barrier is
    readable only after :meth:`finish`, and it does NOT re-arm on completion:
    ``finish()`` needs the full seen-set still in place. ``get()`` returns
    ``None`` — the value of a completed upstream named barrier.
    """

    def __init__(self, names: frozenset[str]) -> None:
        super().__init__()
        self.names = frozenset(names)
        self._seen: set[str] = set()
        self._finished = False

    def validate(self, writes: Sequence[ChannelWrite], superstep: int) -> None:
        for write in writes:
            if write.value not in self.names:
                raise BarrierMemberError(
                    write.channel, superstep, str(write.value), self.names
                )

    def commit(self, writes: Sequence[ChannelWrite], superstep: int) -> bool:
        if not writes:
            return False
        before = set(self._seen)
        for write in writes:
            self._seen.add(write.value)
        if self._seen == self.names and before != self.names:
            self.version += 1
            return True
        return False

    def finish(self) -> bool:
        if self._finished or self._seen != self.names:
            return False
        self._finished = True
        return True

    @property
    def seen(self) -> frozenset[str]:
        return frozenset(self._seen)

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def is_empty(self) -> bool:
        return not (self._finished and self._seen == self.names)

    def get(self) -> Any:
        if self.is_empty:
            raise EmptyChannelError(self.name or "<unbound>")
        return None

    def checkpoint(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "seen": sorted(self._seen),
            "finished": self._finished,
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        super().restore(snapshot)
        self._seen = set(snapshot.get("seen", []))
        self._finished = bool(snapshot.get("finished", False))
