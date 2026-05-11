"""Revenue Spine — Revenue pipeline ledger for dharma_swarm.

The ``RevenueSpine`` class manages the full revenue lifecycle.
Models and enums live in ``spine_models.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from dharma_swarm.revenue.spine_models import (
    ComputeReinvestment,
    Engagement,
    EngagementStatus,
    Offer,
    OfferType,
    OutreachChannel,
    OutreachDraft,
    PipelineSnapshot,
    RevenueTarget,
    TargetStatus,
    _SPINE_DIR,
    _utc_now_iso,
)

logger = logging.getLogger(__name__)

# Re-export models so callers can do ``from .spine import RevenueTarget``
__all__ = [
    "ComputeReinvestment",
    "RevenueSpine",
    "EconomicSpine",  # backward compat alias
    "Engagement",
    "EngagementStatus",
    "Offer",
    "OfferType",
    "OutreachChannel",
    "OutreachDraft",
    "PipelineSnapshot",
    "RevenueTarget",
    "TargetStatus",
]


class RevenueSpine:
    """Revenue pipeline ledger.

    Persists all pipeline state to ``~/.dharma/revenue_spine/`` as JSONL files.
    Each entity type gets its own append-only ledger file.

    Usage::

        spine = RevenueSpine()

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

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        telic_bridge: Any | None = None,
    ) -> None:
        self._dir = storage_dir or _SPINE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._bridge = telic_bridge
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
        if self._bridge:
            self._bridge.record_target(target)
        logger.info("Target added: %s (%s)", target.name.replace('\n', ''), target.id)
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
        if self._bridge:
            self._bridge.record_outreach(draft)
        logger.info("Outreach drafted for %s: %s", target.name.replace('\n', ''), draft.id)
        return draft

    def approve_outreach(self, outreach_id: str, approved_by: str) -> bool:
        """Human approves an outreach draft for sending.

        Requires a non-empty human approver name. Autonomous callers
        cannot bypass this — the name is logged for audit.
        """
        if not approved_by or not approved_by.strip():
            logger.warning("Approval rejected: approver name required for %s", outreach_id)
            return False
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
        logger.info("Outreach %s approved by %s", outreach_id.replace('\n', ''), approved_by.replace('\n', ''))
        return True

    def mark_outreach_sent(
        self,
        outreach_id: str,
        *,
        operator: str = "",
    ) -> bool:
        """Mark an approved outreach as sent.

        Fail-closed: refuses unless ALL of:
        - draft exists
        - draft has been human-approved (approved=True, approved_by non-empty)
        - operator name is provided (the person confirming the send)
        """
        draft = self._outreach.get(outreach_id)
        if not draft:
            logger.warning("Send rejected: outreach %s not found", outreach_id)
            return False
        if not draft.approved or not draft.approved_by:
            logger.warning(
                "Send rejected: outreach %s not human-approved", outreach_id,
            )
            return False
        if not operator:
            logger.warning(
                "Send rejected: operator name required to send outreach %s",
                outreach_id,
            )
            return False
        if draft.sent:
            logger.info("Outreach %s already sent, skipping", outreach_id)
            return True
        draft.sent = True
        draft.sent_at = _utc_now_iso()
        target = self._targets.get(draft.target_id)
        if target:
            target.status = TargetStatus.OUTREACH_SENT
            target.updated_at = _utc_now_iso()
            self._append("targets", target)
        self._append("outreach", draft)
        logger.info(
            "Outreach %s sent by operator %s",
            outreach_id,
            operator.replace('\n', ''),
        )
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
        if self._bridge:
            self._bridge.record_engagement(engagement)
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
        if self._bridge:
            self._bridge.record_payment(eng, amount_usd)

        if economic_engine is not None:
            try:
                from dharma_swarm.economic_engine import RevenueSource
                economic_engine.record_revenue(
                    amount_usd,
                    RevenueSource.FREELANCE_CODING,
                    f"Engagement {engagement_id} payment",
                    idempotency_key=f"rev-pay-{engagement_id}-{amount_usd}",
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
        if self._bridge:
            self._bridge.record_reinvestment(record)

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
                    idempotency_key=f"rev-reinvest-{engagement_id}-{amount_usd}",
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


# Backward-compat alias — the codex spec renamed this to avoid
# collision with the internal dharma_swarm/economic_spine.py class.
EconomicSpine = RevenueSpine
