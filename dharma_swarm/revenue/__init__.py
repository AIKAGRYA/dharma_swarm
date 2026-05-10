"""dharma_swarm.revenue — Revenue pipeline sub-package.

Contains the economic spine (revenue ledger), intelligence ingestor,
and scout daemon for autonomous target scouting.
"""

from dharma_swarm.revenue.spine import (
    ComputeReinvestment,
    EconomicSpine,
    Engagement,
    EngagementStatus,
    Offer,
    OfferType,
    OutreachChannel,
    OutreachDraft,
    PipelineSnapshot,
    RevenueTarget,
    TargetStatus,
)
from dharma_swarm.revenue.intelligence import (
    ClaimType,
    CompetitorProfile,
    IntelClaim,
    IntelDocument,
    IntelSource,
    RevenueIntelligenceIngestor,
    RevenuePattern,
)

__all__ = [
    "ComputeReinvestment",
    "EconomicSpine",
    "Engagement",
    "EngagementStatus",
    "Offer",
    "OfferType",
    "OutreachChannel",
    "OutreachDraft",
    "PipelineSnapshot",
    "RevenueTarget",
    "TargetStatus",
    "ClaimType",
    "CompetitorProfile",
    "IntelClaim",
    "IntelDocument",
    "IntelSource",
    "RevenueIntelligenceIngestor",
    "RevenuePattern",
]
