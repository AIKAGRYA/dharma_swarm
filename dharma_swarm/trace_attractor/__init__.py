"""Trace Attractor Ledger projection contracts.

This package is intentionally read-model only.  It defines normalized event
and packet types plus deterministic in-memory projection helpers; store readers,
SignalBus subscribers, CLI commands, and dashboard surfaces belong in later
implementation PRs.
"""

from dharma_swarm.trace_attractor.models import (
    ATTRACTOR_PACKET_SCHEMA_VERSION,
    AttractorEvent,
    AttractorPacket,
    FindingSeverity,
    FourfoldWarrantSummary,
    LifecycleFinding,
    ProvenanceEdge,
    ProvenanceGraph,
    ProvenanceNode,
    ValueSummary,
    WarrantStatus,
)
from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

__all__ = [
    "ATTRACTOR_PACKET_SCHEMA_VERSION",
    "AttractorEvent",
    "AttractorPacket",
    "FindingSeverity",
    "FourfoldWarrantSummary",
    "LifecycleFinding",
    "ProvenanceEdge",
    "ProvenanceGraph",
    "ProvenanceNode",
    "TraceAttractorProjector",
    "ValueSummary",
    "WarrantStatus",
]
