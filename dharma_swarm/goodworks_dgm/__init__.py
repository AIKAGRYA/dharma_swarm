"""Goodworks-first DGM wiring.

This package is intentionally small: it binds the existing reciprocity ledger,
GAIA ledger, wiki/context substrate, and DGM loop into one agent-callable
surface. It does not introduce a second orchestrator.
"""

from dharma_swarm.goodworks_dgm.models import (
    AutoResearchReceipt,
    DGMRunReceipt,
    GoalDomain,
    GoalRun,
    GoalRunStatus,
    GoalSpec,
    GoodworksMetricSnapshot,
    MutationMode,
    WikiContextReceipt,
)
from dharma_swarm.goodworks_dgm.service import GoodworksDGMService

__all__ = [
    "DGMRunReceipt",
    "AutoResearchReceipt",
    "GoalDomain",
    "GoalRun",
    "GoalRunStatus",
    "GoalSpec",
    "GoodworksDGMService",
    "GoodworksMetricSnapshot",
    "MutationMode",
    "WikiContextReceipt",
]
