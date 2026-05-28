# spine: writes EvidenceReceipt
"""invoke_agent — the one blessed agent invocation path.

PR A: thin pass-through that wraps the current call site and emits a receipt.
PR B: A2A becomes the default invoker.
PR C+: every router collapses onto this signature.

See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §7 Fix 2.
"""

from __future__ import annotations

from typing import Any, Protocol

from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision


class AgentInvoker(Protocol):
    """Protocol for the actual execution backend.

    Callers pass an invoker — the spine does not own execution logic.
    This indirection allows the orchestrator, A2A client, or any future
    backend to serve as the invoker while producing a canonical receipt.
    """

    async def __call__(
        self,
        task: dict[str, Any],
        agent_id: str,
        context_id: str,
        routing: RoutingDecision,
    ) -> EvidenceReceipt: ...


async def invoke_agent(
    task: dict[str, Any],
    agent_id: str,
    context_id: str,
    routing: RoutingDecision,
    *,
    invoker: AgentInvoker,
) -> EvidenceReceipt:
    """The one blessed agent invocation path.

    PR A: thin pass-through that wraps the current call site and emits a receipt.
    PR B: A2A becomes the default invoker.
    PR C+: every router collapses onto this signature.
    """
    return await invoker(
        task=task,
        agent_id=agent_id,
        context_id=context_id,
        routing=routing,
    )
