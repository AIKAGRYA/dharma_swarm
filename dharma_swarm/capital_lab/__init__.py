"""Capital Lab package exports.

Broker-paper names stay available for existing callers, but they are imported
on demand so evidence-only modules can load without importing execution
membrane symbols.
"""

_BROKER_EXPORTS = {
    "BROKER_WRITE_AUTHORITY",
    "CLEAN",
    "LIVE_AUTHORITY",
    "LIVE_READINESS",
    "AuthorityFence",
    "BrokerPaperMembrane",
    "BrokerSnapshotOrder",
    "OrderIntent",
    "OrderLedger",
    "OrderReceipt",
    "ReconciliationPacket",
    "build_client_order_id",
    "run_goal_b_proof_loop",
}


def __getattr__(name: str):
    if name in _BROKER_EXPORTS:
        from dharma_swarm.capital_lab import broker_paper_membrane

        return getattr(broker_paper_membrane, name)
    raise AttributeError(f"module 'dharma_swarm.capital_lab' has no attribute {name!r}")

__all__ = [
    "BROKER_WRITE_AUTHORITY",
    "CLEAN",
    "LIVE_AUTHORITY",
    "LIVE_READINESS",
    "AuthorityFence",
    "BrokerPaperMembrane",
    "BrokerSnapshotOrder",
    "OrderIntent",
    "OrderLedger",
    "OrderReceipt",
    "ReconciliationPacket",
    "build_client_order_id",
    "run_goal_b_proof_loop",
]
