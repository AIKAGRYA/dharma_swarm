"""DharmaGraph — the sovereign durable graph runtime (dharmagraph-engine-2026-07).

Consolidation target for the repo's executors, checkpoint mechanisms, and
workflow compilers (spec: docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md).
Dependency direction: ``graph/`` imports ``spine/`` types; never the reverse.

Neutral graph-core exports (GraphBuilder / CompiledGraph / channels /
scheduler errors) are Candidate Slice A: candidate / test-only, NOT wired
into the production dispatch hot path.
"""

from __future__ import annotations

from dharma_swarm.graph.channels import (
    AppendChannel,
    ChannelWriteConflictError,
    LastValueChannel,
    TriggerChannel,
    UnknownChannelError,
)
from dharma_swarm.graph.checkpoint import DispatchCheckpoint, GraphCheckpointStore
from dharma_swarm.graph.compiler import GraphBuilder, GraphCompileError
from dharma_swarm.graph.scheduler import (
    CompiledGraph,
    GraphRuntimeError,
    MalformedDispatchOrderError,
    NodeExecutionError,
    NodeResultError,
    SuperstepLimitError,
)
from dharma_swarm.graph.types import END, START, GraphRunEvent, GraphRunResult
from dharma_swarm.graph.durable_invoker import (
    DuplicateDispatchInFlight,
    DurableInvoker,
    derive_graph_side_effect_key,
    persist_evidence_receipt,
    receipt_from_dict,
    wrap_invoker,
)
from dharma_swarm.graph.effects import EffectsProvider, LiveEffects, SimulatedEffects
from dharma_swarm.graph.receipt_chain import (
    append_dispatch_receipt_to_machine_chain,
    dispatch_machine_receipt,
)
from dharma_swarm.graph.telos_bridge import (
    GATE_GRAPH_RECEIPT_ANCHOR,
    GraphTelosBridge,
    GraphTelosBridgeResult,
)

__all__ = [
    "AppendChannel",
    "ChannelWriteConflictError",
    "CompiledGraph",
    "DispatchCheckpoint",
    "DuplicateDispatchInFlight",
    "DurableInvoker",
    "EffectsProvider",
    "END",
    "GraphBuilder",
    "GraphCheckpointStore",
    "GraphCompileError",
    "GraphRunEvent",
    "GraphRunResult",
    "GraphRuntimeError",
    "GraphTelosBridge",
    "GraphTelosBridgeResult",
    "GATE_GRAPH_RECEIPT_ANCHOR",
    "LastValueChannel",
    "LiveEffects",
    "MalformedDispatchOrderError",
    "NodeExecutionError",
    "NodeResultError",
    "SimulatedEffects",
    "START",
    "SuperstepLimitError",
    "TriggerChannel",
    "UnknownChannelError",
    "derive_graph_side_effect_key",
    "append_dispatch_receipt_to_machine_chain",
    "dispatch_machine_receipt",
    "persist_evidence_receipt",
    "receipt_from_dict",
    "wrap_invoker",
]
