"""DharmaGraph — the sovereign durable graph runtime (dharmagraph-engine-2026-07).

Consolidation target for the repo's executors, checkpoint mechanisms, and
workflow compilers (spec: docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md).
Dependency direction: ``graph/`` imports ``spine/`` types; never the reverse.
"""

from __future__ import annotations

from dharma_swarm.graph.checkpoint import DispatchCheckpoint, GraphCheckpointStore
from dharma_swarm.graph.durable_invoker import (
    DuplicateDispatchInFlight,
    DurableInvoker,
    derive_graph_side_effect_key,
    persist_evidence_receipt,
    receipt_from_dict,
    wrap_invoker,
)

__all__ = [
    "DispatchCheckpoint",
    "DuplicateDispatchInFlight",
    "DurableInvoker",
    "GraphCheckpointStore",
    "derive_graph_side_effect_key",
    "persist_evidence_receipt",
    "receipt_from_dict",
    "wrap_invoker",
]
