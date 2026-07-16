"""Committed graph state: named channels, two-phase writes, stable digest.

The digest convention matches the receipt chain's canonical-JSON form
(``sort_keys=True, separators=(",", ":"), ensure_ascii=False``) with two
deliberate hardenings: ``allow_nan=False`` and NO ``default=`` coercion —
a state value that cannot digest stably fails the run loudly instead of
producing an unstable or lossy digest. JSON-serializability is checked in
the VALIDATE phase, before any channel mutates, so an undigestable write
can never half-commit a superstep.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Callable, Mapping, Sequence

from dharma_swarm.graph.channels import (
    Channel,
    ChannelWrite,
    TriggerChannel,
    UnknownChannelError,
)
from dharma_swarm.graph.routing import Send
from dharma_swarm.graph.types import RESERVED_PREFIX, TASKS_CHANNEL, TRIGGER_PREFIX

__all__ = ["GraphState", "state_digest"]

logger = logging.getLogger(__name__)


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def state_digest(snapshot: Mapping[str, Any]) -> str:
    """``sha256:<hex>`` over canonical JSON; raises on non-JSON values or NaN."""
    payload = _canonical_json(dict(snapshot))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GraphState:
    """Named, versioned channels behind a validate-all-then-commit barrier.

    Explicit channels only: every user channel is declared at compile time;
    a write (node output or input seed) to an undeclared name raises
    :class:`UnknownChannelError`. Reserved ``__`` channels are runtime-owned:
    ``__trigger__:*`` auto-registers lazily; every other reserved channel
    (``__join__:*``, ``__tasks__``) must be compiler-declared — never created
    on demand, so a stray write cannot mint scheduler state.
    """

    def __init__(
        self, channel_factories: Mapping[str, Callable[[], Channel[Any]]]
    ) -> None:
        self._channels: dict[str, Channel[Any]] = {}
        for name, factory in channel_factories.items():
            channel = factory()
            channel.name = name
            self._channels[name] = channel

    def channel(self, name: str) -> Channel[Any]:
        if name.startswith(TRIGGER_PREFIX):
            existing = self._channels.get(name)
            if existing is None:
                existing = TriggerChannel()
                existing.name = name
                self._channels[name] = existing
            return existing
        if name.startswith(RESERVED_PREFIX):
            try:
                return self._channels[name]
            except KeyError:
                raise UnknownChannelError(name, reason="reserved") from None
        try:
            return self._channels[name]
        except KeyError:
            raise UnknownChannelError(name) from None

    def apply_writes(
        self, writes: Sequence[ChannelWrite], superstep: int
    ) -> frozenset[str]:
        """Two-phase apply; returns the names of channels that advanced.

        Phase 1 resolves every channel (undeclared -> UnknownChannelError),
        validates every group (conflicts -> ChannelWriteConflictError), and
        proves every user-channel value digestable. Only then does phase 2
        mutate, so a failing superstep commits nothing.
        """
        groups = self._group_writes(writes)
        self._validate_grouped_writes(groups, superstep)

        advanced: set[str] = set()
        for name in sorted(groups):
            channel = self.channel(name)
            group = groups[name]
            if channel.commit(group, superstep):
                advanced.add(channel.name)
        return frozenset(advanced)

    def validate_writes(
        self, writes: Sequence[ChannelWrite], superstep: int
    ) -> None:
        """Pure preflight for a barrier; never commits or copies channels.

        Missing trigger channels are validated against an ephemeral trigger
        instance. Their runtime registration remains part of the one real
        :meth:`apply_writes` after the pending-write journal succeeds.
        """
        self._validate_grouped_writes(self._group_writes(writes), superstep)

    @staticmethod
    def _group_writes(
        writes: Sequence[ChannelWrite],
    ) -> dict[str, list[ChannelWrite]]:
        groups: dict[str, list[ChannelWrite]] = {}
        for write in writes:
            groups.setdefault(write.channel, []).append(write)
        return groups

    def _validate_grouped_writes(
        self,
        groups: Mapping[str, list[ChannelWrite]],
        superstep: int,
    ) -> None:
        for name in sorted(groups):
            channel = self._channels.get(name)
            if channel is None and name.startswith(TRIGGER_PREFIX):
                channel = TriggerChannel()
                channel.name = name
            elif channel is None:
                # Preserve channel()'s typed fail-closed diagnostics without
                # letting validation register runtime-owned channels.
                channel = self.channel(name)
            group = groups[name]
            channel.validate(group, superstep)
            if not name.startswith(RESERVED_PREFIX):
                for write in group:
                    try:
                        _canonical_json(write.value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"write to channel {name!r} from node "
                            f"{write.node_id!r} in superstep {superstep} is not "
                            f"stably JSON-serializable: {exc}"
                        ) from exc

    @property
    def versions(self) -> dict[str, int]:
        """All channel versions, trigger channels included (scheduling input)."""
        return {name: ch.version for name, ch in self._channels.items()}

    def snapshot(self) -> dict[str, Any]:
        """Deep-copied view of committed USER state (reserved ``__`` excluded).

        Deep copy is the snapshot-isolation guarantee: a node mutating its
        input (or a value it previously returned) never touches committed
        state. Every runtime-owned ``__`` channel (triggers, joins, tasks)
        stays out of user snapshots and digests.
        """
        return {
            name: copy.deepcopy(channel.get())
            for name, channel in sorted(self._channels.items())
            if not name.startswith(RESERVED_PREFIX) and not channel.is_empty
        }

    def digest(self) -> str:
        return state_digest(self.snapshot())

    def checkpoint_channels(self) -> dict[str, dict[str, Any]]:
        """Per-channel STATE for resume/fork (Send packets serialized)."""
        out: dict[str, dict[str, Any]] = {}
        for name, channel in self._channels.items():
            snap = channel.checkpoint()
            if name == TASKS_CHANNEL and "items" in snap:
                snap = {**snap, "items": [s.to_dict() for s in snap["items"]]}
            out[name] = snap
        return out

    def restore_channels(self, snapshots: Mapping[str, Mapping[str, Any]]) -> None:
        """Rebuild every channel from :meth:`checkpoint_channels` output."""
        for name, snap in snapshots.items():
            channel = self.channel(name)
            if name == TASKS_CHANNEL and "items" in snap:
                snap = {
                    **snap,
                    "items": [Send.from_dict(d) for d in snap["items"]],
                }
            channel.restore(snap)

    def own_writes_view(
        self, writes: Sequence[ChannelWrite], superstep: int
    ) -> dict[str, Any]:
        """Snapshot + ONE task's pending writes, reducer-correct (branch view).

        langgraph parity: a branch path sees the source node's own pending
        writes but not other same-superstep tasks' writes. Writes apply to
        deep-copied channel objects so reducers show old+new, never new-only;
        committed state is untouched.
        """
        view = self.snapshot()
        groups: dict[str, list[ChannelWrite]] = {}
        for write in writes:
            if not write.channel.startswith(RESERVED_PREFIX):
                groups.setdefault(write.channel, []).append(write)
        for name, group in groups.items():
            channel_copy = copy.deepcopy(self.channel(name))
            channel_copy.validate(group, superstep)
            channel_copy.commit(group, superstep)
            view[name] = copy.deepcopy(channel_copy.get())
        return view
