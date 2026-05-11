"""dharma_swarm.revenue — Revenue pipeline sub-package.

Contains the economic spine (revenue ledger), intelligence ingestor,
scout daemon, and intelligence-report wedge pipeline.
"""

from dharma_swarm.revenue.spine import (
    ComputeReinvestment,
    EconomicSpine,
    RevenueSpine,
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
from dharma_swarm.revenue.telic_bridge import RevenueTelicBridge
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
    "RevenueSpine",
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
    "RevenueTelicBridge",
]
