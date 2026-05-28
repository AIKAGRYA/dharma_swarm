"""Runtime Truth Spine — one invariant, one invocation path, one receipt.

See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md for doctrine.
"""

from dharma_swarm.spine.receipt import EvidenceReceipt, ErrorSource, ReceiptStatus
from dharma_swarm.spine.routing import RoutingDecision
from dharma_swarm.spine.invoke import invoke_agent, AgentInvoker

__all__ = [
    "EvidenceReceipt",
    "ErrorSource",
    "ReceiptStatus",
    "RoutingDecision",
    "invoke_agent",
    "AgentInvoker",
]
