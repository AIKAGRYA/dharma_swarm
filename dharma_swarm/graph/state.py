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
from dharma_swarm.graph.types import TRIGGER_PREFIX

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
    :class:`UnknownChannelError`. Trigger channels (``__trigger__:*``) are
    scheduler-owned and auto-registered on first use.
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
        groups: dict[str, list[ChannelWrite]] = {}
        for write in writes:
            groups.setdefault(write.channel, []).append(write)

        resolved: list[tuple[Channel[Any], list[ChannelWrite]]] = []
        for name in sorted(groups):
            channel = self.channel(name)
            group = groups[name]
            channel.validate(group, superstep)
            if not name.startswith(TRIGGER_PREFIX):
                for write in group:
                    try:
                        _canonical_json(write.value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"write to channel {name!r} from node "
                            f"{write.node_id!r} in superstep {superstep} is not "
                            f"stably JSON-serializable: {exc}"
                        ) from exc
            resolved.append((channel, group))

        advanced: set[str] = set()
        for channel, group in resolved:
            if channel.commit(group, superstep):
                advanced.add(channel.name)
        return frozenset(advanced)

    @property
    def versions(self) -> dict[str, int]:
        """All channel versions, trigger channels included (scheduling input)."""
        return {name: ch.version for name, ch in self._channels.items()}

    def snapshot(self) -> dict[str, Any]:
        """Deep-copied view of committed USER state (triggers excluded).

        Deep copy is the snapshot-isolation guarantee: a node mutating its
        input (or a value it previously returned) never touches committed
        state.
        """
        return {
            name: copy.deepcopy(channel.get())
            for name, channel in sorted(self._channels.items())
            if not name.startswith(TRIGGER_PREFIX) and not channel.is_empty
        }

    def digest(self) -> str:
        return state_digest(self.snapshot())
