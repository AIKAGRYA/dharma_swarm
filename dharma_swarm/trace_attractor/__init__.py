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
from dharma_swarm.trace_attractor.readers import (
    DEFAULT_ONTOLOGY_TYPES,
    TraceAttractorStoreReader,
    read_ontology_events,
    read_runtime_events,
    read_telemetry_events,
)

__all__ = [
    "ATTRACTOR_PACKET_SCHEMA_VERSION",
    "AttractorEvent",
    "AttractorPacket",
    "DEFAULT_ONTOLOGY_TYPES",
    "FindingSeverity",
    "FourfoldWarrantSummary",
    "LifecycleFinding",
    "ProvenanceEdge",
    "ProvenanceGraph",
    "ProvenanceNode",
    "TraceAttractorProjector",
    "TraceAttractorStoreReader",
    "ValueSummary",
    "WarrantStatus",
    "read_ontology_events",
    "read_runtime_events",
    "read_telemetry_events",
]
