"""Revenue–TelicSeam bridge — makes revenue events ontology-native.

Adapts RevenueSpine operations into the metabolic loop by recording
ontology objects through TelicSeam.  The bridge is injected into the
spine (not scattered through it) so revenue/spine.py stays a clean
pipeline ledger and this module owns the ontology projection.

Usage::

    from dharma_swarm.telic_seam import TelicSeam
    from dharma_swarm.revenue.spine import RevenueSpine
    from dharma_swarm.revenue.telic_bridge import RevenueTelicBridge

    seam = TelicSeam()
    spine = RevenueSpine()
    bridge = RevenueTelicBridge(seam)

    # After spine.create_engagement():
    bridge.record_engagement(engagement)

    # After spine.record_payment():
    bridge.record_payment(engagement, amount_usd=10000.0)

    # After spine.reinvest():
    bridge.record_reinvestment(reinvestment)

All bridge methods are best-effort: ontology failures never block the
revenue ledger.  This matches TelicSeam's existing contract.
"""

from __future__ import annotations

import logging
from typing import Any

from dharma_swarm.revenue.spine_models import (
    ComputeReinvestment,
    Engagement,
    OutreachDraft,
    RevenueTarget,
)

logger = logging.getLogger(__name__)


class RevenueTelicBridge:
    """Ontology write-through adapter for revenue operations.

    Records revenue events as typed ontology objects and links them
    into the metabolic chain (Outcome → ValueEvent → Contribution).
    """

    def __init__(
        self,
        seam: Any,  # TelicSeam — lazy typed to avoid import cycle
        *,
        dry_run: bool = False,
    ) -> None:
        self._seam = seam
        self._dry_run = dry_run
        self._obj_map: dict[str, str] = {}

    @property
    def registry(self) -> Any:
        return self._seam.registry

    def _create_obj(
        self,
        type_name: str,
        properties: dict[str, Any],
        created_by: str = "revenue_bridge",
    ) -> str | None:
        if self._dry_run:
            logger.debug("DRY-RUN: would create %s %s", type_name, properties)
            return None
        try:
            obj, errors = self.registry.create_object(
                type_name, properties=properties, created_by=created_by,
            )
            if obj is None:
                logger.debug("%s creation failed: %s", type_name, errors)
                return None
            return obj.id
        except Exception as exc:
            logger.debug("RevenueTelicBridge._create_obj(%s) failed: %s",
                         type_name, exc)
            return None

    def _link(
        self,
        link_name: str,
        source_id: str | None,
        target_id: str | None,
    ) -> None:
        if self._dry_run or source_id is None or target_id is None:
            return
        try:
            self.registry.create_link(
                link_name, source_id=source_id, target_id=target_id,
                created_by="revenue_bridge",
            )
        except Exception as exc:
            logger.debug("RevenueTelicBridge._link(%s) failed: %s",
                         link_name, exc)

    def _flush(self) -> None:
        if self._dry_run:
            return
        self._seam._flush_registry()

    # ── Revenue target ────────────────────────────────────────────────

    def record_target(self, target: RevenueTarget) -> str | None:
        """Project a RevenueTarget into the ontology."""
        pain = target.intelligence if target.intelligence else {}
        oid = self._create_obj("RevenueTarget", {
            "name": target.name,
            "source": "github_scout",
            "status": target.status.value if hasattr(target.status, "value") else str(target.status),
            "qualification_score": target.qualification_score,
            "pain_signals": pain,
            "spine_ref": target.id,
        })
        if oid:
            self._obj_map[f"target:{target.id}"] = oid
        self._flush()
        return oid

    # ── Engagement ────────────────────────────────────────────────────

    def record_engagement(self, engagement: Engagement) -> str | None:
        """Project an Engagement into the ontology.

        Creates a RevenueEngagement object and an ActionProposal with
        action_type="revenue" to record the dispatch through gates.
        """
        eng_oid = self._create_obj("RevenueEngagement", {
            "target_id": engagement.target_id,
            "offer_id": engagement.offer_id,
            "status": engagement.status.value if hasattr(engagement.status, "value") else str(engagement.status),
            "contracted_value_usd": engagement.contracted_value_usd,
            "paid_usd": engagement.paid_usd,
            "spine_ref": engagement.id,
        })
        if eng_oid:
            self._obj_map[f"engagement:{engagement.id}"] = eng_oid

        # Also create an ActionProposal for this revenue action
        proposal_oid = self._create_obj("ActionProposal", {
            "task_id": f"revenue-engagement-{engagement.id}",
            "agent_id": "revenue_bridge",
            "action_type": "revenue",
            "title": f"Revenue engagement {engagement.id}",
            "description": f"Contracted ${engagement.contracted_value_usd:.2f}",
            "status": "completed",
            "priority": "high",
        })
        if proposal_oid:
            self._obj_map[f"proposal:{engagement.id}"] = proposal_oid

        # Link engagement → proposal
        self._link("revenue_proposal", eng_oid, proposal_oid)

        # Link engagement → target (if target ontology obj exists)
        target_oid = self._obj_map.get(f"target:{engagement.target_id}")
        self._link("has_engagement", target_oid, eng_oid)

        self._flush()
        return eng_oid

    # ── Payment ───────────────────────────────────────────────────────

    def record_payment(
        self,
        engagement: Engagement,
        amount_usd: float,
    ) -> str | None:
        """Record a payment as Outcome + ValueEvent in the ontology.

        The Outcome captures the fact that payment was received.
        The ValueEvent captures the USD value for Shakti scoring.
        """
        if self._dry_run:
            logger.debug("DRY-RUN: would record payment $%.2f for %s",
                         amount_usd, engagement.id)
            return None

        eng_oid = self._obj_map.get(f"engagement:{engagement.id}")
        proposal_oid = self._obj_map.get(f"proposal:{engagement.id}")

        # Create Outcome for payment
        outcome_oid = self._create_obj("Outcome", {
            "proposal_id": proposal_oid or "",
            "task_id": f"revenue-payment-{engagement.id}",
            "agent_id": "revenue_bridge",
            "success": True,
            "result_summary": f"Payment received: ${amount_usd:.2f}",
            "outcome_kind": "revenue",
            "economic_amount_usd": amount_usd,
            "external_ref": engagement.id,
        })

        # Link outcome → proposal
        if proposal_oid and outcome_oid:
            self._link("has_outcome", proposal_oid, outcome_oid)

        # Link engagement → outcome
        self._link("engagement_outcome", eng_oid, outcome_oid)

        # Create ValueEvent for the payment
        ve_oid = self._create_obj("ValueEvent", {
            "outcome_id": outcome_oid or "",
            "agent_id": "revenue_bridge",
            "cell_id": "",
            "task_id": f"revenue-payment-{engagement.id}",
            "task_type": "revenue.payment",
            "value_kind": "paid_revenue",
            "economic_value_usd": amount_usd,
            "revenue_source": engagement.id,
            "behavioral_signal": 1.0,
            "success_value": 1.0,
            "duration_efficiency": 1.0,
            "composite_value": amount_usd,
            "scoring_method": "revenue_v1",
        })

        # Link outcome → value event
        if outcome_oid and ve_oid:
            self._link("has_value_event", outcome_oid, ve_oid)

        # Emit signal via seam's signal bus
        if self._seam._signal_bus is not None:
            try:
                from dharma_swarm.signal_bus import SIGNAL_OUTCOME_RECORDED
                self._seam._signal_bus.emit({
                    "type": SIGNAL_OUTCOME_RECORDED,
                    "outcome_id": outcome_oid or "",
                    "proposal_id": proposal_oid or "",
                    "task_id": f"revenue-payment-{engagement.id}",
                    "agent_id": "revenue_bridge",
                    "success": True,
                    "domain_hint": "external_revenue",
                })
            except Exception as exc:
                logger.debug("Revenue payment signal emit failed: %s", exc)

        self._flush()
        return outcome_oid

    # ── Reinvestment ──────────────────────────────────────────────────

    def record_reinvestment(
        self,
        reinvestment: ComputeReinvestment,
    ) -> str | None:
        """Record a compute reinvestment as Contribution in the ontology.

        Creates a ComputeReinvestment ontology object and a Contribution
        that credits the reinvestment back to the system.
        """
        ri_oid = self._create_obj("ComputeReinvestment", {
            "engagement_id": reinvestment.engagement_id,
            "amount_usd": reinvestment.amount_usd,
            "category": reinvestment.target_category,
            "provider": reinvestment.provider,
            "spine_ref": reinvestment.id,
        })

        # Link reinvestment → engagement
        eng_oid = self._obj_map.get(f"engagement:{reinvestment.engagement_id}")
        self._link("engagement_reinvestment", eng_oid, ri_oid)

        # Find the most recent ValueEvent for this engagement
        ve_oid = self._find_ve_for_engagement(reinvestment.engagement_id)

        # Create Contribution crediting the reinvestment
        contrib_oid = self._create_obj("Contribution", {
            "value_event_id": ve_oid or "",
            "agent_id": "revenue_bridge",
            "cell_id": "",
            "task_type": "revenue.reinvestment",
            "credit_share": 1.0,
            "attributed_value": reinvestment.amount_usd,
            "beneficiary_type": self._category_to_beneficiary(
                reinvestment.target_category),
            "revenue_ref": reinvestment.engagement_id,
        })

        # Link value event → contribution
        if ve_oid and contrib_oid:
            self._link("has_contribution", ve_oid, contrib_oid)

        self._flush()
        return ri_oid

    # ── Outreach ──────────────────────────────────────────────────────

    def record_outreach(self, draft: OutreachDraft) -> str | None:
        """Project an OutreachDraft into the ontology."""
        oid = self._create_obj("RevenueOutreachDraft", {
            "target_id": draft.target_id,
            "offer_id": draft.offer_id,
            "channel": draft.channel.value if hasattr(draft.channel, "value") else str(draft.channel),
            "subject": draft.subject,
            "body": draft.body[:500] if draft.body else "",
            "approved": draft.approved,
            "approved_by": draft.approved_by,
        })
        if oid:
            self._obj_map[f"outreach:{draft.id}"] = oid
            target_oid = self._obj_map.get(f"target:{draft.target_id}")
            self._link("has_outreach", target_oid, oid)
        self._flush()
        return oid

    # ── Helpers ───────────────────────────────────────────────────────

    def _find_ve_for_engagement(self, engagement_id: str) -> str | None:
        try:
            for ve in self.registry.get_objects_by_type("ValueEvent"):
                if ve.properties.get("revenue_source") == engagement_id:
                    return ve.id
        except Exception:
            pass
        return None

    @staticmethod
    def _category_to_beneficiary(category: str) -> str:
        mapping = {
            "training": "training",
            "inference": "compute",
            "operations": "operator",
        }
        return mapping.get(category, "compute")

    def stats(self) -> dict[str, int]:
        return {
            "mapped_objects": len(self._obj_map),
            "dry_run": int(self._dry_run),
        }
