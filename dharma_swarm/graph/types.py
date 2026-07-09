"""Neutral graph-core vocabulary — DharmaGraph Candidate Slice A.

Shared types for the neutral graph substrate (dharmagraph-engine-2026-07,
built acyclic-first toward the spec's Phase 3 primitives). claim_mode:
candidate / test_only — nothing here is wired into production dispatch.

Failure doctrine for the whole slice: runs RAISE typed errors; they never
return "failed" result objects. ``RunStatus`` therefore has one value —
persisted multi-status runs belong to a later durable phase.

Dependency direction: ``graph/`` imports ``spine/`` types, never the
reverse; this module imports neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Final, Literal, Mapping

__all__ = [
    "END",
    "EdgeSpec",
    "EventStatus",
    "GraphRunEvent",
    "GraphRunResult",
    "NodeCallable",
    "NodeSpec",
    "RunStatus",
    "START",
    "TRIGGER_PREFIX",
    "trigger_channel",
]

START: Final[str] = "__start__"
END: Final[str] = "__end__"
TRIGGER_PREFIX: Final[str] = "__trigger__:"

NodeResult = Mapping[str, Any] | None
NodeCallable = Callable[[Mapping[str, Any]], "NodeResult | Awaitable[NodeResult]"]

RunStatus = Literal["completed"]
EventStatus = Literal["ok"]


def trigger_channel(node_id: str) -> str:
    """Name of the scheduler-owned trigger channel for ``node_id``."""
    return f"{TRIGGER_PREFIX}{node_id}"


@dataclass(frozen=True)
class NodeSpec:
    """A named node: an async-or-sync callable from state snapshot to writes."""

    node_id: str
    fn: NodeCallable


@dataclass(frozen=True)
class EdgeSpec:
    """A directed edge; compiles to "source's commit writes target's trigger"."""

    source: str
    target: str


@dataclass(frozen=True)
class GraphRunEvent:
    """Receipt-friendly metadata for one committed node firing.

    Vocabulary (``run_id`` / ``superstep`` / ``node_id``) deliberately matches
    ``derive_graph_side_effect_key(run_id, superstep, node_id, retry_count)``
    in ``durable_invoker`` so later durable wiring needs no renaming.
    ``state_digest`` is the digest of the state committed at this superstep's
    barrier (all events of one superstep share it).
    """

    graph_run_id: str
    graph_id: str
    node_id: str
    superstep: int
    status: EventStatus
    state_digest: str


@dataclass(frozen=True)
class GraphRunResult:
    """Outcome of a completed run (failures raise; see module docstring)."""

    graph_run_id: str
    graph_id: str
    status: RunStatus
    state: Mapping[str, Any]
    state_digest: str
    supersteps: int
    events: tuple[GraphRunEvent, ...]
