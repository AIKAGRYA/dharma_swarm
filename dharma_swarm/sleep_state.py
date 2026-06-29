"""State-root predicates for sleep-cycle graph phases."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir

_OPERATIONAL_STATE_MARKERS = (
    Path("semantic/concept_graph.json"),
    Path("memory/semantic_sleep.db"),
    Path("db/bridges.db"),
    Path("db/temporal_graph.db"),
    Path("stigmergy/marks.jsonl"),
)


def has_operational_sleep_state(state_root: Path) -> bool:
    """Return true when expensive graph phases have persisted state to use."""
    if state_root == dharma_state_dir():
        return True
    return any((state_root / marker).exists() for marker in _OPERATIONAL_STATE_MARKERS)
