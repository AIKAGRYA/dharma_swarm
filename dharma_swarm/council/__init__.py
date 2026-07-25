"""One Council substrate (multi-profile), minimal keystone build.

Only the ``orchestration_trace_verification`` profile is implemented here (spec
§10 step 1). The Council verifies and quarantines; it never scores, plans,
dispatches, or judges correctness (spec §2). Shared invariants live in
``invariants.py`` and hold for every future profile.
"""

from dharma_swarm.council.council import (
    ORCHESTRATION_TRACE_VERIFICATION,
    Council,
    CouncilReceipt,
    TraceVerificationRequest,
)
from dharma_swarm.council.invariants import (
    DISPATCH_AUTHORITY,
    VALID_VERDICTS,
    Verdict,
    meets_decorrelation,
)

__all__ = [
    "DISPATCH_AUTHORITY",
    "ORCHESTRATION_TRACE_VERIFICATION",
    "VALID_VERDICTS",
    "Council",
    "CouncilReceipt",
    "TraceVerificationRequest",
    "Verdict",
    "meets_decorrelation",
]
