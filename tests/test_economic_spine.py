"""Tests for the EconomicSpine revenue pipeline ledger."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.revenue.spine import (
    ComputeReinvestment,
    EconomicSpine,
    Engagement,
    EngagementStatus,
    Offer,
    OfferType,
    OutreachChannel,
    OutreachDraft,
    RevenueTarget,
    TargetStatus,
)


@pytest.fixture()
def spine(tmp_path: Path) -> EconomicSpine:
    return EconomicSpine(storage_dir=tmp_path / "spine")


@pytest.fixture()
def target() -> RevenueTarget:
    return RevenueTarget(
        name="acme/widgets",
        org="acme",
        domain="python",
        pain_signals=["no_ci_gates", "bot_prs"],
        estimated_value_usd=10000.0,
    )


class TestTargetManagement:
    def test_add_and_retrieve_target(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        added = spine.add_target(target)
        assert added.id == target.id
        retrieved = spine.get_target(target.id)
        assert retrieved is not None
        assert retrieved.name == "acme/widgets"

    def test_qualify_target(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        result = spine.qualify_target(target.id, 0.85, {"note": "high-value"})
        assert result is not None
        assert result.status == TargetStatus.QUALIFIED
        assert result.qualification_score == 0.85

    def test_disqualify_target(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        spine.disqualify_target(target.id, "too small")
        t = spine.get_target(target.id)
        assert t is not None
        assert t.status == TargetStatus.DISQUALIFIED

    def test_list_targets_by_status(self, spine: EconomicSpine) -> None:
        spine.add_target(RevenueTarget(name="a", status=TargetStatus.SCOUTED))
        spine.add_target(RevenueTarget(name="b", status=TargetStatus.SCOUTED))
        t3 = RevenueTarget(name="c")
        spine.add_target(t3)
        spine.qualify_target(t3.id, 0.9)

        scouted = spine.list_targets(status=TargetStatus.SCOUTED)
        assert len(scouted) == 2
        qualified = spine.list_targets(status=TargetStatus.QUALIFIED)
        assert len(qualified) == 1


class TestOutreach:
    def test_draft_outreach(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        draft = spine.draft_outreach(
            target.id, offer.id,
            subject="Test subject",
            body="Test body",
        )
        assert draft is not None
        assert not draft.approved
        assert not draft.sent
        assert draft.target_id == target.id

    def test_approve_outreach(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        draft = spine.draft_outreach(target.id, offer.id, subject="Hi", body="Test")
        assert draft is not None
        ok = spine.approve_outreach(draft.id, "dhyana")
        assert ok
        updated = spine._outreach[draft.id]
        assert updated.approved
        assert updated.approved_by == "dhyana"

    def test_cannot_send_unapproved(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        draft = spine.draft_outreach(target.id, offer.id, subject="Hi", body="Test")
        assert draft is not None
        ok = spine.mark_outreach_sent(draft.id)
        assert not ok

    def test_can_send_after_approval(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        draft = spine.draft_outreach(target.id, offer.id, subject="Hi", body="Test")
        assert draft is not None
        spine.approve_outreach(draft.id, "dhyana")
        ok = spine.mark_outreach_sent(draft.id)
        assert ok

    def test_pending_outreach(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        spine.draft_outreach(target.id, offer.id, subject="Hi", body="Test")
        pending = spine.pending_outreach()
        assert len(pending) == 1


class TestEngagement:
    def test_create_engagement(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        eng = spine.create_engagement(target.id, offer.id, 15000.0)
        assert eng is not None
        assert eng.contracted_value_usd == 15000.0
        assert eng.status == EngagementStatus.SCOPING

    def test_record_payment(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        eng = spine.create_engagement(target.id, offer.id, 10000.0)
        assert eng is not None
        ok = spine.record_payment(eng.id, 10000.0)
        assert ok
        updated = spine._engagements[eng.id]
        assert updated.status == EngagementStatus.PAID

    def test_reinvest(self, spine: EconomicSpine, target: RevenueTarget) -> None:
        spine.add_target(target)
        offer = spine.default_offer()
        eng = spine.create_engagement(target.id, offer.id, 10000.0)
        assert eng is not None
        record = spine.reinvest(eng.id, 6000.0, "training", "runpod")
        assert record.amount_usd == 6000.0
        assert record.provider == "runpod"


class TestPipelineSnapshot:
    def test_snapshot(self, spine: EconomicSpine) -> None:
        t1 = RevenueTarget(name="a", estimated_value_usd=5000.0)
        t2 = RevenueTarget(name="b", estimated_value_usd=10000.0)
        spine.add_target(t1)
        spine.add_target(t2)
        spine.qualify_target(t2.id, 0.8)

        snap = spine.snapshot()
        assert snap.targets_scouted == 1
        assert snap.targets_qualified == 1
        assert snap.total_pipeline_value_usd == 15000.0


class TestPersistence:
    def test_reload_state(self, tmp_path: Path) -> None:
        storage = tmp_path / "spine"
        spine1 = EconomicSpine(storage_dir=storage)
        t = RevenueTarget(name="persistent", estimated_value_usd=7500.0)
        spine1.add_target(t)
        offer = spine1.default_offer()
        spine1.draft_outreach(t.id, offer.id, subject="Hi", body="Test")

        spine2 = EconomicSpine(storage_dir=storage)
        assert spine2.get_target(t.id) is not None
        assert len(spine2.pending_outreach()) == 1
