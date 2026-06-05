"""Tests for dharma_swarm/revenue/spine.py — Revenue pipeline ledger."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dharma_swarm.revenue.spine import RevenueSpine
from dharma_swarm.revenue.spine_models import (
    Engagement,
    EngagementStatus,
    Offer,
    OfferType,
    OutreachChannel,
    RevenueTarget,
    TargetStatus,
)


@pytest.fixture
def spine(tmp_path: Path) -> RevenueSpine:
    """Create a RevenueSpine with a temporary storage directory."""
    return RevenueSpine(storage_dir=tmp_path / "revenue_spine")


@pytest.fixture
def sample_target() -> RevenueTarget:
    return RevenueTarget(name="Acme Corp", domain="acme.com")


@pytest.fixture
def sample_offer() -> Offer:
    return Offer(
        title="Code Governance Sprint",
        offer_type=OfferType.CODE_GOVERNANCE_SPRINT,
        price_range_low_usd=5000,
        price_range_high_usd=15000,
        scope_summary="Two-week sprint to establish governance.",
    )


class TestTargetLifecycle:
    def test_add_target(self, spine: RevenueSpine, sample_target: RevenueTarget) -> None:
        result = spine.add_target(sample_target)
        assert result.name == "Acme Corp"
        assert result.id != ""

    def test_get_target(self, spine: RevenueSpine, sample_target: RevenueTarget) -> None:
        added = spine.add_target(sample_target)
        fetched = spine.get_target(added.id)
        assert fetched is not None
        assert fetched.name == "Acme Corp"

    def test_get_nonexistent_target(self, spine: RevenueSpine) -> None:
        assert spine.get_target("nonexistent") is None

    def test_qualify_target(self, spine: RevenueSpine, sample_target: RevenueTarget) -> None:
        added = spine.add_target(sample_target)
        qualified = spine.qualify_target(added.id, score=0.85, intelligence={"revenue": "10M"})
        assert qualified is not None
        assert qualified.status == TargetStatus.QUALIFIED
        assert qualified.qualification_score == 0.85

    def test_disqualify_target(self, spine: RevenueSpine, sample_target: RevenueTarget) -> None:
        added = spine.add_target(sample_target)
        spine.disqualify_target(added.id, reason="no budget")
        fetched = spine.get_target(added.id)
        assert fetched is not None
        assert fetched.status == TargetStatus.DISQUALIFIED

    def test_list_targets_by_status(self, spine: RevenueSpine) -> None:
        t1 = spine.add_target(RevenueTarget(name="Alpha"))
        t2 = spine.add_target(RevenueTarget(name="Beta"))
        spine.qualify_target(t1.id, score=0.9)

        qualified = spine.list_targets(status=TargetStatus.QUALIFIED)
        assert len(qualified) == 1
        assert qualified[0].name == "Alpha"

        all_targets = spine.list_targets()
        assert len(all_targets) == 2


class TestOfferManagement:
    def test_register_offer(self, spine: RevenueSpine, sample_offer: Offer) -> None:
        result = spine.register_offer(sample_offer)
        assert result.title == "Code Governance Sprint"
        assert result.price_range_low_usd == 5000

    def test_get_offer(self, spine: RevenueSpine, sample_offer: Offer) -> None:
        registered = spine.register_offer(sample_offer)
        fetched = spine.get_offer(registered.id)
        assert fetched is not None
        assert fetched.offer_type == OfferType.CODE_GOVERNANCE_SPRINT

    def test_default_offer(self, spine: RevenueSpine) -> None:
        default = spine.default_offer()
        assert default is not None
        assert default.title != ""


class TestOutreachWorkflow:
    def test_draft_outreach(
        self, spine: RevenueSpine, sample_target: RevenueTarget, sample_offer: Offer
    ) -> None:
        target = spine.add_target(sample_target)
        offer = spine.register_offer(sample_offer)
        draft = spine.draft_outreach(
            target_id=target.id,
            offer_id=offer.id,
            channel=OutreachChannel.EMAIL,
            subject="Governance for Acme",
            body="Hi, we can help with governance.",
        )
        assert draft is not None
        assert draft.subject == "Governance for Acme"

    def test_approve_outreach(
        self, spine: RevenueSpine, sample_target: RevenueTarget, sample_offer: Offer
    ) -> None:
        target = spine.add_target(sample_target)
        offer = spine.register_offer(sample_offer)
        draft = spine.draft_outreach(
            target_id=target.id,
            offer_id=offer.id,
            channel=OutreachChannel.EMAIL,
            subject="Test",
            body="Body",
        )
        result = spine.approve_outreach(draft.id, approved_by="operator")
        assert result is True

    def test_pending_outreach(
        self, spine: RevenueSpine, sample_target: RevenueTarget, sample_offer: Offer
    ) -> None:
        target = spine.add_target(sample_target)
        offer = spine.register_offer(sample_offer)
        spine.draft_outreach(
            target_id=target.id,
            offer_id=offer.id,
            channel=OutreachChannel.EMAIL,
            subject="Draft 1",
            body="Body 1",
        )
        pending = spine.pending_outreach()
        assert len(pending) >= 1


class TestEngagementAndPayment:
    def test_create_engagement(
        self, spine: RevenueSpine, sample_target: RevenueTarget, sample_offer: Offer
    ) -> None:
        target = spine.add_target(sample_target)
        offer = spine.register_offer(sample_offer)
        engagement = spine.create_engagement(
            target_id=target.id, offer_id=offer.id, contracted_value_usd=10000
        )
        assert engagement is not None
        assert engagement.contracted_value_usd == 10000

    def test_record_payment(
        self, spine: RevenueSpine, sample_target: RevenueTarget, sample_offer: Offer
    ) -> None:
        target = spine.add_target(sample_target)
        offer = spine.register_offer(sample_offer)
        engagement = spine.create_engagement(
            target_id=target.id, offer_id=offer.id, contracted_value_usd=10000
        )
        assert engagement is not None
        spine.record_payment(engagement.id, 5000)
        snapshot = spine.snapshot()
        assert snapshot is not None


class TestSnapshot:
    def test_snapshot_empty(self, spine: RevenueSpine) -> None:
        snapshot = spine.snapshot()
        assert snapshot.targets_scouted == 0
        assert snapshot.total_pipeline_value_usd == 0

    def test_snapshot_with_data(
        self, spine: RevenueSpine, sample_target: RevenueTarget, sample_offer: Offer
    ) -> None:
        spine.add_target(sample_target)
        spine.register_offer(sample_offer)
        snapshot = spine.snapshot()
        assert snapshot.targets_scouted == 1


class TestPersistence:
    def test_data_persists_across_instances(self, tmp_path: Path) -> None:
        storage = tmp_path / "revenue_spine"

        spine1 = RevenueSpine(storage_dir=storage)
        spine1.add_target(RevenueTarget(name="Persistent Corp"))

        spine2 = RevenueSpine(storage_dir=storage)
        targets = spine2.list_targets()
        assert len(targets) == 1
        assert targets[0].name == "Persistent Corp"
