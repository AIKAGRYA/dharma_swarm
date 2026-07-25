"""Revenue pipeline models — enums and Pydantic schemas.

Covers the full lifecycle of revenue generation:
    target -> offer -> outreach -> reply -> engagement -> paid_work -> compute_reinvestment

Every stage is telos-gated. The system scouts and drafts; humans approve sends.
No autonomous spam. All outreach requires explicit human approval before dispatch.

Integrates with:
    - EconomicEngine (dharma_swarm/economic_engine.py) for transaction recording
    - OpportunityDispatcher for stage execution
    - TelicSeam for provenance and gate decisions
    - AutoResearchEngine for target intelligence gathering

Schema:
    RevenueTarget  — a potential buyer/opportunity identified by scouting
    Offer          — a packaged service offering mapped to the target's pain
    OutreachDraft  — a drafted message awaiting human approval
    Engagement     — an active paid engagement
    ComputeReinvestment — reinvestment of revenue into compute/training
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SPINE_DIR = Path.home() / ".dharma" / "revenue_spine"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SPINE_COUNTER = 0


def _spine_id(prefix: str) -> str:
    global _SPINE_COUNTER
    _SPINE_COUNTER += 1
    return f"{prefix}-{int(time.time() * 1000) % 1_000_000_000}-{_SPINE_COUNTER}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TargetStatus(str, Enum):
    SCOUTED = "scouted"
    QUALIFIED = "qualified"
    OUTREACH_DRAFTED = "outreach_drafted"
    OUTREACH_APPROVED = "outreach_approved"
    OUTREACH_SENT = "outreach_sent"
    REPLIED = "replied"
    ENGAGED = "engaged"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    DISQUALIFIED = "disqualified"


class OfferType(str, Enum):
    CODE_GOVERNANCE_SPRINT = "code_governance_sprint"
    AGENT_EVAL_AUDIT = "agent_eval_audit"
    PROVENANCE_INSTALL = "provenance_install"
    CUSTOM = "custom"


class OutreachChannel(str, Enum):
    EMAIL = "email"
    GITHUB = "github"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    DISCORD = "discord"
    DIRECT = "direct"


class EngagementStatus(str, Enum):
    SCOPING = "scoping"
    CONTRACTED = "contracted"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    PAID = "paid"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RevenueTarget(BaseModel):
    """A potential buyer identified by scouting."""

    id: str = Field(default_factory=lambda: _spine_id("tgt"))
    name: str
    org: str = ""
    domain: str = ""
    pain_signals: list[str] = Field(default_factory=list)
    repo_urls: list[str] = Field(default_factory=list)
    estimated_value_usd: float = 0.0
    status: TargetStatus = TargetStatus.SCOUTED
    qualification_score: float = 0.0
    intelligence: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)


class Offer(BaseModel):
    """A packaged service offering."""

    id: str = Field(default_factory=lambda: _spine_id("ofr"))
    offer_type: OfferType = OfferType.CODE_GOVERNANCE_SPRINT
    title: str = "Agentic Code Governance Sprint"
    price_range_low_usd: float = 5000.0
    price_range_high_usd: float = 25000.0
    scope_summary: str = ""
    deliverables: list[str] = Field(default_factory=list)
    duration_days: int = 5
    created_at: str = Field(default_factory=_utc_now_iso)


class OutreachDraft(BaseModel):
    """A drafted outreach message awaiting human approval.

    Rule: no autonomous spam. The system drafts; the human approves sends.
    The ``approved`` field MUST be set to True by a human before dispatch.
    """

    id: str = Field(default_factory=lambda: _spine_id("out"))
    target_id: str
    offer_id: str
    channel: OutreachChannel = OutreachChannel.EMAIL
    subject: str = ""
    body: str = ""
    approved: bool = False
    approved_by: str = ""
    approved_at: str = ""
    sent: bool = False
    sent_at: str = ""
    created_at: str = Field(default_factory=_utc_now_iso)


class Engagement(BaseModel):
    """An active paid engagement."""

    id: str = Field(default_factory=lambda: _spine_id("eng"))
    target_id: str
    offer_id: str
    status: EngagementStatus = EngagementStatus.SCOPING
    contracted_value_usd: float = 0.0
    paid_usd: float = 0.0
    started_at: str = ""
    delivered_at: str = ""
    paid_at: str = ""
    deliverables_completed: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)


class ComputeReinvestment(BaseModel):
    """Record of revenue reinvested into compute/training."""

    id: str = Field(default_factory=lambda: _spine_id("crv"))
    engagement_id: str
    amount_usd: float
    target_category: str = "training"
    provider: str = ""
    expected_roi: str = ""
    created_at: str = Field(default_factory=_utc_now_iso)


class PipelineSnapshot(BaseModel):
    """Point-in-time view of the full revenue pipeline."""

    timestamp: str = Field(default_factory=_utc_now_iso)
    targets_scouted: int = 0
    targets_qualified: int = 0
    outreach_drafted: int = 0
    outreach_sent: int = 0
    replies_received: int = 0
    engagements_active: int = 0
    total_pipeline_value_usd: float = 0.0
    total_contracted_usd: float = 0.0
    total_paid_usd: float = 0.0
    total_reinvested_usd: float = 0.0
