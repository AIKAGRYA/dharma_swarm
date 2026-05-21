"""BoardStore facade — unified task/state surface for multi-agent coordination.

This package implements the BoardStore facade contract specified in
docs/architecture/SWARM_BOARDSTORE_SPEC.md. It unifies seven existing
truth-bearing stores behind a typed read/write surface with:

- Card schema (stable cross-store identity)
- Event log (append-only audit stream)
- Noticer/doer separation (claims, leases, heartbeats)
- Cost-cap semantics (ceiling enforcement per card)

The facade does NOT replace existing stores. Each store keeps the truth
it already owns. The facade exposes one card contract, one write path,
one lease model, and one append-only audit stream.
"""

from dharma_swarm.board.models import (
    Card,
    CardId,
    CardStatus,
    ClaimLease,
    AcceptanceCriterion,
    ReceiptRef,
    AuditEntry,
    RenderHints,
)
from dharma_swarm.board.event_log import BoardEventLog, BoardEvent

__all__ = [
    "Card",
    "CardId",
    "CardStatus",
    "ClaimLease",
    "AcceptanceCriterion",
    "ReceiptRef",
    "AuditEntry",
    "RenderHints",
    "BoardEventLog",
    "BoardEvent",
]
