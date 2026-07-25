"""Typed topology -> Memory Kernel isolation semantics.

Kept out of default_context.py so the map is import-cycle-free and testable
alone. The map is TOTAL over ``TopologyType``; unknown, missing, or
non-enum topology values ("dispatch", drifted vocabulary) resolve to
``FAIL_CLOSED_MINIMAL`` with a warning — never to an unrestricted policy,
because empty allowed_* tuples historically meant allow-all downstream.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dharma_swarm.memory_kernel.atoms import MemoryLane, MemoryScope
from dharma_swarm.models import TopologyType

ISOLATION_LEGACY_ENV = "DHARMA_MEMORY_KERNEL_ISOLATION_LEGACY"

_SHARED_LANES = (
    MemoryLane.WORKING,
    MemoryLane.EPISODIC,
    MemoryLane.SEMANTIC,
    MemoryLane.PROCEDURAL,
    MemoryLane.REFLECTION,
    MemoryLane.PROVENANCE,
)


@dataclass(frozen=True)
class IsolationSemantics:
    name: str
    allowed_scopes: tuple[MemoryScope, ...]
    allowed_memory_lanes: tuple[MemoryLane, ...]


WORKER_SCOPED = IsolationSemantics(
    name="worker_scoped",
    # SESSION excluded: a non-originating worker must not read another
    # agent's session-scoped memory.
    allowed_scopes=(
        MemoryScope.PROJECT,
        MemoryScope.REPO,
        MemoryScope.WORKTREE,
        MemoryScope.AGENT,
        MemoryScope.SWARM,
    ),
    allowed_memory_lanes=_SHARED_LANES,
)

SUPERVISOR_SCOPED = IsolationSemantics(
    name="supervisor_scoped",
    allowed_scopes=(
        MemoryScope.PROJECT,
        MemoryScope.REPO,
        MemoryScope.WORKTREE,
        MemoryScope.SESSION,
        MemoryScope.AGENT,
        MemoryScope.SWARM,
    ),
    allowed_memory_lanes=_SHARED_LANES,
)

FAIL_CLOSED_MINIMAL = IsolationSemantics(
    name="fail_closed_minimal",
    # There is no GLOBAL member in MemoryScope; PROJECT/REPO are the shared
    # curated scopes, SEMANTIC/PROCEDURAL the curated lanes.
    allowed_scopes=(MemoryScope.PROJECT, MemoryScope.REPO),
    allowed_memory_lanes=(MemoryLane.SEMANTIC, MemoryLane.PROCEDURAL),
)

ISOLATION_SEMANTICS: dict[TopologyType, IsolationSemantics] = {
    TopologyType.FAN_OUT: WORKER_SCOPED,
    TopologyType.FAN_IN: WORKER_SCOPED,
    TopologyType.PIPELINE: WORKER_SCOPED,
    TopologyType.BROADCAST: WORKER_SCOPED,
    TopologyType.SWARM: WORKER_SCOPED,
    TopologyType.SUPERVISOR: SUPERVISOR_SCOPED,
    TopologyType.SUBAGENTS_AS_TOOLS: WORKER_SCOPED,
}


def isolation_legacy_enabled() -> bool:
    """One-release escape hatch back to the pre-typed isolation behavior."""

    raw = os.environ.get(ISOLATION_LEGACY_ENV, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve(raw: str | TopologyType | None) -> tuple[IsolationSemantics, tuple[str, ...]]:
    """Resolve a topology value to isolation semantics; fail closed on unknown."""

    if isinstance(raw, TopologyType):
        return ISOLATION_SEMANTICS[raw], ()
    text = str(raw or "").strip()
    if not text:
        return FAIL_CLOSED_MINIMAL, ("topology_missing_fail_closed",)
    try:
        topology = TopologyType(text)
    except ValueError:
        return FAIL_CLOSED_MINIMAL, (f"unknown_topology_fail_closed:{text[:40]}",)
    return ISOLATION_SEMANTICS[topology], ()
