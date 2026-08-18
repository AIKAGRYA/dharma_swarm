"""Pregel-core LG10 channels: step-scoped, untracked, batch-reducer and
after-finish channels (langgraph parity extension).

Split out of :mod:`dharma_swarm.graph.channels` (quality-ratchet
``modules_over_500_lines`` — a pure move, re-exported from ``channels``
so every existing import path keeps working). Append-only extension of
the channel family defined there — every channel above keeps its exact
behavior; the two lifecycle hooks these classes use (``end_step`` /
``finish``) are no-ops on the base :class:`Channel` and on every channel
that predates this module.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping, Sequence

from dharma_swarm.graph.channels import (
    _MISSING,
    BarrierMemberError,
    Channel,
    ChannelWrite,
    ChannelWriteConflictError,
    EmptyChannelError,
)

__all__ = [
    "AnyValueChannel",
    "DeltaChannel",
    "EphemeralChannel",
    "LastValueAfterFinishChannel",
    "NamedBarrierAfterFinishChannel",
    "UntrackedValueChannel",
]


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
