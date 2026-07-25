"""Pure state-derivation helpers for graph persistence updates."""

from __future__ import annotations

import copy
from typing import Any, Callable, Mapping

from dharma_swarm.graph.channels import Channel, ChannelWrite
from dharma_swarm.graph.state import GraphState, state_digest
from dharma_swarm.graph.types import RunCheckpoint


def extract_state(channels: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Return the user-visible values from serialized channel snapshots."""
    state: dict[str, Any] = {}
    for name, snap in channels.items():
        if name.startswith("__") or int(snap.get("version", 0)) <= 0:
            continue
        if "value" in snap:
            state[name] = copy.deepcopy(snap["value"])
        elif "items" in snap:
            state[name] = copy.deepcopy(snap["items"])
    return state


def derive_updated_checkpoint(
    base: RunCheckpoint,
    values: Mapping[str, Any],
    *,
    channel_factories: Mapping[str, Callable[[], Channel[Any]]] | None,
    as_node: str,
) -> RunCheckpoint:
    """Derive one manual-update checkpoint without performing persistence I/O."""
    step = base.superstep + 1
    if channel_factories is None:
        channels = copy.deepcopy(dict(base.channels))
        for name, value in values.items():
            snap = dict(channels.get(name, {"version": 0}))
            if "items" in snap:
                incoming = value if isinstance(value, list) else [value]
                snap["items"] = list(snap.get("items", [])) + list(incoming)
            else:
                snap["value"] = value
            snap["version"] = int(snap.get("version", 0)) + 1
            channels[name] = snap
        digest = state_digest(extract_state(channels))
    else:
        graph_state = GraphState(channel_factories)
        graph_state.restore_channels(base.channels)
        writes = [
            ChannelWrite(as_node, name, value)
            for name, value in sorted(values.items())
        ]
        graph_state.apply_writes(writes, step)
        channels = graph_state.checkpoint_channels()
        digest = graph_state.digest()
    return RunCheckpoint(
        graph_run_id=base.graph_run_id,
        graph_id=base.graph_id,
        superstep=step,
        state_digest=digest,
        channels=channels,
        versions_seen=base.versions_seen,
    )
