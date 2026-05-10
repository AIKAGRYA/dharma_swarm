"""Economic Spine — Revenue pipeline ledger for dharma_swarm.

Tracks the full lifecycle of revenue generation:
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
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SPINE_DIR = Path.home() / ".dharma" / "economic_spine"


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


# ---------------------------------------------------------------------------
# Spine
# ---------------------------------------------------------------------------


class EconomicSpine:
    """Revenue pipeline ledger.

    Persists all pipeline state to ``~/.dharma/economic_spine/`` as JSONL files.
    Each entity type gets its own append-only ledger file.

    Usage::

        spine = EconomicSpine()

        # Scout a target
        target = spine.add_target(RevenueTarget(name="Acme Corp", ...))

        # Draft outreach (not sent yet — needs human approval)
        draft = spine.draft_outreach(target.id, offer.id, subject="...", body="...")

        # Human approves
        spine.approve_outreach(draft.id, approved_by="dhyana")

        # Record engagement
        engagement = spine.create_engagement(target.id, offer.id, value=10000)

        # Record payment + reinvestment
        spine.record_payment(engagement.id, 10000)
        spine.reinvest(engagement.id, 6000, "training", "runpod")
    """

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self._dir = storage_dir or _SPINE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._targets: dict[str, RevenueTarget] = {}
        self._offers: dict[str, Offer] = {}
        self._outreach: dict[str, OutreachDraft] = {}
        self._engagements: dict[str, Engagement] = {}
        self._reinvestments: list[ComputeReinvestment] = []
        self._load()

    # -- Targets -----------------------------------------------------------

    def add_target(self, target: RevenueTarget) -> RevenueTarget:
        self._targets[target.id] = target
        self._append("targets", target)
        logger.info("Target added: %s (%s)", target.name, target.id)
        return target

    def qualify_target(
        self, target_id: str, score: float, intelligence: dict[str, Any] | None = None
    ) -> RevenueTarget | None:
        target = self._targets.get(target_id)
        if not target:
            return None
        target.status = TargetStatus.QUALIFIED
        target.qualification_score = score
        if intelligence:
            target.intelligence.update(intelligence)
        target.updated_at = _utc_now_iso()
        self._append("targets", target)
        return target

    def disqualify_target(self, target_id: str, reason: str = "") -> None:
        target = self._targets.get(target_id)
        if target:
            target.status = TargetStatus.DISQUALIFIED
            target.intelligence["disqualification_reason"] = reason
            target.updated_at = _utc_now_iso()
            self._append("targets", target)

    def get_target(self, target_id: str) -> RevenueTarget | None:
        return self._targets.get(target_id)

    def list_targets(self, status: TargetStatus | None = None) -> list[RevenueTarget]:
        targets = list(self._targets.values())
        if status is not None:
            targets = [t for t in targets if t.status == status]
        return sorted(targets, key=lambda t: t.qualification_score, reverse=True)

    # -- Offers ------------------------------------------------------------

    def register_offer(self, offer: Offer) -> Offer:
        self._offers[offer.id] = offer
        self._append("offers", offer)
        return offer

    def get_offer(self, offer_id: str) -> Offer | None:
        return self._offers.get(offer_id)

    def default_offer(self) -> Offer:
        """Return the default Code Governance Sprint offer."""
        for o in self._offers.values():
            if o.offer_type == OfferType.CODE_GOVERNANCE_SPRINT:
                return o
        offer = Offer(
            offer_type=OfferType.CODE_GOVERNANCE_SPRINT,
            title="Agentic Code Governance Sprint",
            price_range_low_usd=5000.0,
            price_range_high_usd=25000.0,
            scope_summary=(
                "3-7 day paid engagement: audit repo for AI slop, install "
                "packet provenance + CI gates + evals + audit ledger, "
                "optionally run governed agent repair loops."
            ),
            deliverables=[
                "Ranked slop report (Markdown + JSON)",
                "Provenance records (JSONL)",
                "CI gate config (YAML / GitHub Actions)",
                "Eval dashboard (JSON metrics)",
                "Audit ledger (SQLite + JSONL)",
                "Repair PRs with provenance (optional)",
            ],
            duration_days=5,
        )
        self.register_offer(offer)
        return offer

    # -- Outreach ----------------------------------------------------------

    def draft_outreach(
        self,
        target_id: str,
        offer_id: str,
        *,
        channel: OutreachChannel = OutreachChannel.EMAIL,
        subject: str = "",
        body: str = "",
    ) -> OutreachDraft | None:
        target = self._targets.get(target_id)
        if not target:
            logger.warning("Cannot draft outreach: target %s not found", target_id)
            return None
        draft = OutreachDraft(
            target_id=target_id,
            offer_id=offer_id,
            channel=channel,
            subject=subject,
            body=body,
        )
        self._outreach[draft.id] = draft
        target.status = TargetStatus.OUTREACH_DRAFTED
        target.updated_at = _utc_now_iso()
        self._append("outreach", draft)
        self._append("targets", target)
        logger.info("Outreach drafted for %s: %s", target.name, draft.id)
        return draft

    def approve_outreach(self, outreach_id: str, approved_by: str) -> bool:
        """Human approves an outreach draft for sending."""
        draft = self._outreach.get(outreach_id)
        if not draft:
            return False
        draft.approved = True
        draft.approved_by = approved_by
        draft.approved_at = _utc_now_iso()
        target = self._targets.get(draft.target_id)
        if target:
            target.status = TargetStatus.OUTREACH_APPROVED
            target.updated_at = _utc_now_iso()
            self._append("targets", target)
        self._append("outreach", draft)
        logger.info("Outreach %s approved by %s", outreach_id, approved_by)
        return True

    def mark_outreach_sent(self, outreach_id: str) -> bool:
        """Mark an approved outreach as sent. Refuses if not approved."""
        draft = self._outreach.get(outreach_id)
        if not draft or not draft.approved:
            logger.warning("Cannot send unapproved outreach: %s", outreach_id)
            return False
        draft.sent = True
        draft.sent_at = _utc_now_iso()
        target = self._targets.get(draft.target_id)
        if target:
            target.status = TargetStatus.OUTREACH_SENT
            target.updated_at = _utc_now_iso()
            self._append("targets", target)
        self._append("outreach", draft)
        return True

    def pending_outreach(self) -> list[OutreachDraft]:
        """Return all drafted but unapproved outreach."""
        return [d for d in self._outreach.values() if not d.approved]

    # -- Engagements -------------------------------------------------------

    def create_engagement(
        self,
        target_id: str,
        offer_id: str,
        contracted_value_usd: float = 0.0,
    ) -> Engagement | None:
        target = self._targets.get(target_id)
        if not target:
            return None
        engagement = Engagement(
            target_id=target_id,
            offer_id=offer_id,
            contracted_value_usd=contracted_value_usd,
            started_at=_utc_now_iso(),
        )
        self._engagements[engagement.id] = engagement
        target.status = TargetStatus.ENGAGED
        target.updated_at = _utc_now_iso()
        self._append("engagements", engagement)
        self._append("targets", target)
        logger.info(
            "Engagement created: %s ($%.2f)", engagement.id, contracted_value_usd
        )
        return engagement

    def record_payment(
        self,
        engagement_id: str,
        amount_usd: float,
        economic_engine: Any | None = None,
    ) -> bool:
        eng = self._engagements.get(engagement_id)
        if not eng:
            return False
        eng.paid_usd += amount_usd
        eng.paid_at = _utc_now_iso()
        if eng.paid_usd >= eng.contracted_value_usd:
            eng.status = EngagementStatus.PAID
            target = self._targets.get(eng.target_id)
            if target:
                target.status = TargetStatus.CLOSED_WON
                target.updated_at = _utc_now_iso()
                self._append("targets", target)
        self._append("engagements", eng)

        if economic_engine is not None:
            try:
                from dharma_swarm.economic_engine import RevenueSource
                economic_engine.record_revenue(
                    amount_usd,
                    RevenueSource.FREELANCE_CODING,
                    f"Engagement {engagement_id} payment",
                )
            except Exception as exc:
                logger.warning("Failed to record revenue: %s", exc)
        return True

    # -- Compute reinvestment ----------------------------------------------

    def reinvest(
        self,
        engagement_id: str,
        amount_usd: float,
        target_category: str = "training",
        provider: str = "",
        expected_roi: str = "",
        economic_engine: Any | None = None,
    ) -> ComputeReinvestment:
        record = ComputeReinvestment(
            engagement_id=engagement_id,
            amount_usd=amount_usd,
            target_category=target_category,
            provider=provider,
            expected_roi=expected_roi,
        )
        self._reinvestments.append(record)
        self._append("reinvestments", record)

        if economic_engine is not None:
            try:
                from dharma_swarm.economic_engine import (
                    BudgetCategory,
                    ExpenseCategory,
                )
                cat_map = {
                    "training": (ExpenseCategory.GPU_TRAINING, BudgetCategory.TRAINING),
                    "inference": (ExpenseCategory.GPU_INFERENCE, BudgetCategory.INFERENCE),
                    "operations": (ExpenseCategory.VPS_HOSTING, BudgetCategory.OPERATIONS),
                }
                exp_cat, bud_cat = cat_map.get(
                    target_category,
                    (ExpenseCategory.OTHER, BudgetCategory.REINVESTMENT),
                )
                economic_engine.record_expense(
                    amount_usd, exp_cat,
                    f"Reinvestment from {engagement_id}",
                    budget_source=bud_cat,
                )
            except Exception as exc:
                logger.warning("Failed to record reinvestment expense: %s", exc)
        return record

    # -- Pipeline snapshot -------------------------------------------------

    def snapshot(self) -> PipelineSnapshot:
        targets = list(self._targets.values())
        return PipelineSnapshot(
            targets_scouted=sum(1 for t in targets if t.status == TargetStatus.SCOUTED),
            targets_qualified=sum(1 for t in targets if t.status == TargetStatus.QUALIFIED),
            outreach_drafted=sum(1 for d in self._outreach.values() if not d.approved),
            outreach_sent=sum(1 for d in self._outreach.values() if d.sent),
            replies_received=sum(
                1 for t in targets if t.status == TargetStatus.REPLIED
            ),
            engagements_active=sum(
                1 for e in self._engagements.values()
                if e.status in (EngagementStatus.SCOPING, EngagementStatus.CONTRACTED,
                                EngagementStatus.IN_PROGRESS)
            ),
            total_pipeline_value_usd=sum(t.estimated_value_usd for t in targets
                                         if t.status not in (TargetStatus.DISQUALIFIED,
                                                             TargetStatus.CLOSED_LOST)),
            total_contracted_usd=sum(e.contracted_value_usd
                                     for e in self._engagements.values()),
            total_paid_usd=sum(e.paid_usd for e in self._engagements.values()),
            total_reinvested_usd=sum(r.amount_usd for r in self._reinvestments),
        )

    # -- Persistence -------------------------------------------------------

    def _append(self, collection: str, obj: BaseModel) -> None:
        path = self._dir / f"{collection}.jsonl"
        try:
            with open(path, "a") as f:
                f.write(obj.model_dump_json() + "\n")
        except OSError:
            logger.warning("Failed to persist %s record", collection, exc_info=True)

    def _load(self) -> None:
        self._load_collection("targets", RevenueTarget, self._targets)
        self._load_collection("offers", Offer, self._offers)
        self._load_collection("outreach", OutreachDraft, self._outreach)
        self._load_collection("engagements", Engagement, self._engagements)
        self._load_list("reinvestments", ComputeReinvestment, self._reinvestments)

    def _load_collection(
        self,
        name: str,
        model_cls: type[BaseModel],
        store: dict[str, Any],
    ) -> None:
        path = self._dir / f"{name}.jsonl"
        if not path.exists():
            return
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = model_cls.model_validate_json(line)
                    store[obj.id] = obj  # type: ignore[attr-defined]
                except Exception:
                    continue
        except OSError:
            pass

    def _load_list(
        self,
        name: str,
        model_cls: type[BaseModel],
        store: list[Any],
    ) -> None:
        path = self._dir / f"{name}.jsonl"
        if not path.exists():
            return
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    store.append(model_cls.model_validate_json(line))
                except Exception:
                    continue
        except OSError:
            pass
