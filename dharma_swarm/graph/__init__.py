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
    BarrierChannel,
    BarrierMemberError,
    ChannelWriteConflictError,
    LastValueChannel,
    ReducerChannel,
    TopicChannel,
    TriggerChannel,
    UnknownChannelError,
)
from dharma_swarm.graph.interrupts import (
    GraphInterrupted,
    Interrupt,
    interrupt,
)
from dharma_swarm.graph.schema import (
    RemainingSteps,
    SchemaError,
    TypedCompiledGraph,
    TypedStateGraph,
    context_schema,
    input_schema,
    output_schema,
    typed_state_schema,
)
from dharma_swarm.graph.checkpoint import DispatchCheckpoint, GraphCheckpointStore
from dharma_swarm.graph.compiler import GraphBuilder, GraphCompileError
from dharma_swarm.graph.persistence import (
    GraphCheckpointRecord,
    GraphPendingWrite,
    GraphPersistenceKernel,
    GraphSerializer,
    JsonGraphSerializer,
)
from dharma_swarm.graph.retry import (
    RetryPolicy,
    backoff_interval,
    default_retry_on,
    select_retry_policy,
    should_retry_on,
)
from dharma_swarm.graph.routing import (
    BranchDestinationError,
    Command,
    ParentCommand,
    Send,
    SendTargetError,
)
from dharma_swarm.graph.subgraph import as_node
from dharma_swarm.graph.timeouts import TimeoutPolicy, heartbeat
from dharma_swarm.graph.errors import NodeTimeoutError
from dharma_swarm.graph.scheduler import (
    CompiledGraph,
    GraphRuntimeError,
    MalformedDispatchOrderError,
    NodeExecutionError,
    NodeResultError,
    SuperstepLimitError,
)
from dharma_swarm.graph.types import (
    END,
    START,
    GraphRunEvent,
    GraphRunResult,
    RunCheckpoint,
)
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
    "BarrierChannel",
    "BarrierMemberError",
    "BranchDestinationError",
    "ChannelWriteConflictError",
    "Command",
    "CompiledGraph",
    "DispatchCheckpoint",
    "DuplicateDispatchInFlight",
    "DurableInvoker",
    "EffectsProvider",
    "END",
    "GraphBuilder",
    "GraphCheckpointStore",
    "GraphCompileError",
    "GraphCheckpointRecord",
    "GraphPendingWrite",
    "GraphPersistenceKernel",
    "GraphSerializer",
    "GraphRunEvent",
    "GraphRunResult",
    "RunCheckpoint",
    "GraphRuntimeError",
    "GraphInterrupted",
    "GraphTelosBridge",
    "GraphTelosBridgeResult",
    "Interrupt",
    "interrupt",
    "GATE_GRAPH_RECEIPT_ANCHOR",
    "LastValueChannel",
    "LiveEffects",
    "MalformedDispatchOrderError",
    "NodeExecutionError",
    "NodeResultError",
    "NodeTimeoutError",
    "ParentCommand",
    "ReducerChannel",
    "RetryPolicy",
    "TimeoutPolicy",
    "as_node",
    "backoff_interval",
    "default_retry_on",
    "heartbeat",
    "select_retry_policy",
    "should_retry_on",
    "RemainingSteps",
    "SchemaError",
    "Send",
    "SendTargetError",
    "SimulatedEffects",
    "START",
    "TypedCompiledGraph",
    "TypedStateGraph",
    "context_schema",
    "input_schema",
    "output_schema",
    "typed_state_schema",
    "SuperstepLimitError",
    "TopicChannel",
    "TriggerChannel",
    "UnknownChannelError",
    "JsonGraphSerializer",
    "derive_graph_side_effect_key",
    "append_dispatch_receipt_to_machine_chain",
    "dispatch_machine_receipt",
    "persist_evidence_receipt",
    "receipt_from_dict",
    "wrap_invoker",
]
