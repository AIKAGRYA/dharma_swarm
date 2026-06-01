"""Runtime Truth Spine — one invariant, one invocation path, one receipt.

See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md for doctrine.

Closure-layer doctrine (PR A.5, three-agent convergence):

    Receipts may differ by closure layer. Correlation identity must not.
    Each closure layer may have its own canonical receipt.
    Cross-layer identity continuity is the global invariant.

Closure layers and their canonical receipts:

  * Request/response layer (Hermes A2A surface):
      ``dharma_swarm.operator_core.a2a_task_lifecycle.A2ATaskReceipt``
      Identity field: ``correlation_id``.

  * Dispatch/invocation layer (this package):
      ``dharma_swarm.spine.receipt.EvidenceReceipt``
      Identity field: ``trace_id`` (also exported under
      ``dharma.correlation_id`` for cross-layer joins).

  * Test/acceptance layer (closure_v0 evidence):
      ``dharma_swarm.operator_core.closure_v0.EvidenceReceipt``
      Identity field: ``correlation_id``.

Each receipt is canonical-within-its-layer (not a derived view). The
cross-layer invariant is identity continuity — the same correlation
value MUST appear on the receipts in every layer a request traverses.
See ACTIVE_SURFACE_MANIFEST.yaml ``correlation_spine`` block.
"""

from dharma_swarm.spine.receipt import EvidenceReceipt, ErrorSource, ReceiptStatus
from dharma_swarm.spine.routing import RoutingDecision
from dharma_swarm.spine.invoke import invoke_agent, AgentInvoker
from dharma_swarm.spine.identity import (
    ExecutionIdentity,
    MissingExecutionIdentity,
    require_execution_identity,
)
from dharma_swarm.spine.adapters import (
    adapt_execution_identity,
    attach_execution_identity,
    identity_from_carrier,
    identity_metadata,
    runtime_receipt_kwargs,
)

__all__ = [
    "ExecutionIdentity",
    "EvidenceReceipt",
    "ErrorSource",
    "MissingExecutionIdentity",
    "ReceiptStatus",
    "RoutingDecision",
    "adapt_execution_identity",
    "attach_execution_identity",
    "identity_from_carrier",
    "identity_metadata",
    "invoke_agent",
    "AgentInvoker",
    "require_execution_identity",
    "runtime_receipt_kwargs",
]
