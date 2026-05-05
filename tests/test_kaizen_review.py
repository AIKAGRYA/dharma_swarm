"""Tests for KaizenReview v0 — room-scoped learning loop (Law 4).

Tests the SECI cycle at room level:
  Socialization   → packet outcomes shared
  Externalization → findings crystallized from outcomes
  Combination     → playbook entries produced
  Internalization → playbook available for future packets
"""

from __future__ import annotations

import pytest

from dharma_swarm.fractal.kaizen_review import (
    KaizenFinding,
    KaizenReview,
    KaizenReviewStore,
    KaizenReviewValidationError,
    PlaybookEntry,
    ReviewVerdict,
    build_review_from_packets,
    validate_finding,
    validate_review,
)


# -----------------------------------------------------------------------
# Finding validation
# -----------------------------------------------------------------------

class TestKaizenFindingValidation:

    def test_valid_finding(self):
        f = KaizenFinding(
            category="process",
            observation="Build step too slow",
            recommendation="Add caching",
            severity="info",
        )
        validate_finding(f)

    def test_finding_requires_observation(self):
        f = KaizenFinding(category="process", observation="")
        with pytest.raises(KaizenReviewValidationError, match="requires observation"):
            validate_finding(f)

    def test_finding_rejects_invalid_category(self):
        f = KaizenFinding(
            category="invalid_cat",
            observation="Something happened",
        )
        with pytest.raises(KaizenReviewValidationError, match="Invalid category"):
            validate_finding(f)

    def test_finding_allows_empty_category(self):
        f = KaizenFinding(category="", observation="Generic observation")
        validate_finding(f)

    def test_finding_rejects_invalid_severity(self):
        f = KaizenFinding(
            observation="Something",
            severity="catastrophic",
        )
        with pytest.raises(KaizenReviewValidationError, match="Invalid severity"):
            validate_finding(f)

    def test_all_valid_categories_accepted(self):
        for cat in KaizenFinding.VALID_CATEGORIES:
            f = KaizenFinding(category=cat, observation="Test")
            validate_finding(f)

    def test_all_valid_severities_accepted(self):
        for sev in KaizenFinding.VALID_SEVERITIES:
            f = KaizenFinding(observation="Test", severity=sev)
            validate_finding(f)


# -----------------------------------------------------------------------
# Review validation
# -----------------------------------------------------------------------

class TestKaizenReviewValidation:

    def test_valid_review(self):
        review = KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
        )
        validate_review(review)

    def test_review_requires_room_id(self):
        review = KaizenReview(
            room_id="",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
        )
        with pytest.raises(KaizenReviewValidationError, match="requires room_id"):
            validate_review(review)

    def test_review_requires_reviewer(self):
        review = KaizenReview(
            room_id="core-ops",
            reviewer="",
            reviewed_packet_ids=["wp_001"],
        )
        with pytest.raises(KaizenReviewValidationError, match="requires reviewer"):
            validate_review(review)

    def test_review_requires_packet_ids(self):
        review = KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=[],
        )
        with pytest.raises(KaizenReviewValidationError, match="at least one work packet"):
            validate_review(review)

    def test_review_validates_findings(self):
        review = KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            findings=[KaizenFinding(observation="")],
        )
        with pytest.raises(KaizenReviewValidationError, match="requires observation"):
            validate_review(review)


# -----------------------------------------------------------------------
# Review store
# -----------------------------------------------------------------------

class TestKaizenReviewStore:

    def _make_store(self) -> KaizenReviewStore:
        return KaizenReviewStore()

    def test_submit_and_retrieve(self):
        store = self._make_store()
        review = KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            summary="All good",
        )
        result = store.submit_review(review)
        assert result.id == review.id
        assert store.review_count("core-ops") == 1

    def test_reviews_scoped_to_room(self):
        store = self._make_store()
        store.submit_review(KaizenReview(
            room_id="room-a",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
        ))
        store.submit_review(KaizenReview(
            room_id="room-b",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_002"],
        ))
        assert store.review_count("room-a") == 1
        assert store.review_count("room-b") == 1

    def test_latest_review(self):
        store = self._make_store()
        r1 = store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            created_at="2025-01-01T00:00:00Z",
        ))
        r2 = store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_002"],
            created_at="2025-01-02T00:00:00Z",
        ))
        latest = store.latest_review("core-ops")
        assert latest is not None
        assert latest.id == r2.id

    def test_latest_review_none_when_empty(self):
        store = self._make_store()
        assert store.latest_review("nonexistent") is None

    def test_playbook_entries_indexed_by_room(self):
        store = self._make_store()
        entry = PlaybookEntry(
            title="Use caching for builds",
            description="Add --cache flag to all build commands",
            tags=["tooling", "performance"],
        )
        store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            playbook_entries=[entry],
        ))
        playbook = store.playbook_for_room("core-ops")
        assert len(playbook) == 1
        assert playbook[0].title == "Use caching for builds"
        assert playbook[0].room_id == "core-ops"

    def test_playbook_entries_tagged_with_source_review(self):
        store = self._make_store()
        entry = PlaybookEntry(title="Test entry", description="Desc")
        review = store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            playbook_entries=[entry],
        ))
        playbook = store.playbook_for_room("core-ops")
        assert playbook[0].source_review_id == review.id

    def test_playbook_not_shared_across_rooms(self):
        store = self._make_store()
        store.submit_review(KaizenReview(
            room_id="room-a",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            playbook_entries=[
                PlaybookEntry(title="A's entry", description="For A only"),
            ],
        ))
        assert store.playbook_count("room-a") == 1
        assert store.playbook_count("room-b") == 0

    def test_all_findings_unfiltered(self):
        store = self._make_store()
        store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            findings=[
                KaizenFinding(observation="Slow", severity="info"),
                KaizenFinding(observation="Bug", severity="critical"),
            ],
        ))
        findings = store.all_findings("core-ops")
        assert len(findings) == 2

    def test_all_findings_filtered_by_severity(self):
        store = self._make_store()
        store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            findings=[
                KaizenFinding(observation="Slow", severity="info"),
                KaizenFinding(observation="Bug", severity="critical"),
            ],
        ))
        critical = store.all_findings("core-ops", severity="critical")
        assert len(critical) == 1
        assert critical[0].observation == "Bug"


# -----------------------------------------------------------------------
# Build review from packets (externalization step)
# -----------------------------------------------------------------------

class TestBuildReviewFromPackets:

    def test_all_passing_packets_verdict_working(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "success", "cost_tokens": 100},
                {"id": "wp_002", "outcome": "completed", "cost_tokens": 50},
            ],
        )
        assert review.verdict == ReviewVerdict.WORKING
        assert len(review.reviewed_packet_ids) == 2
        assert review.room_id == "core-ops"

    def test_some_failures_verdict_needs_improvement(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "success"},
                {"id": "wp_002", "outcome": "failed: timeout"},
                {"id": "wp_003", "outcome": "completed"},
            ],
        )
        assert review.verdict == ReviewVerdict.NEEDS_IMPROVEMENT
        failure_findings = [
            f for f in review.findings if f.category == "quality"
        ]
        assert len(failure_findings) == 1

    def test_majority_failures_verdict_broken(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "failed: OOM"},
                {"id": "wp_002", "outcome": "failed: timeout"},
                {"id": "wp_003", "outcome": "success"},
            ],
        )
        assert review.verdict == ReviewVerdict.BROKEN

    def test_budget_warning_generated(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "success",
                 "cost_tokens": 950, "cost_ceiling": 1000},
            ],
        )
        budget_findings = [
            f for f in review.findings if f.category == "budget"
        ]
        assert len(budget_findings) == 1
        assert ">90%" in budget_findings[0].observation

    def test_no_budget_warning_under_threshold(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "success",
                 "cost_tokens": 100, "cost_ceiling": 1000},
            ],
        )
        budget_findings = [
            f for f in review.findings if f.category == "budget"
        ]
        assert len(budget_findings) == 0

    def test_empty_packets_verdict_working(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[],
        )
        assert review.verdict == ReviewVerdict.WORKING
        assert review.reviewed_packet_ids == []

    def test_summary_includes_counts(self):
        review = build_review_from_packets(
            room_id="core-ops",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "success"},
                {"id": "wp_002", "outcome": "failed"},
            ],
        )
        assert "2 packets" in review.summary
        assert "1 succeeded" in review.summary
        assert "1 failed" in review.summary


# -----------------------------------------------------------------------
# Playbook rendering
# -----------------------------------------------------------------------

class TestPlaybookRendering:

    def test_empty_playbook_renders(self):
        store = KaizenReviewStore()
        md = store.render_playbook_markdown("core-ops")
        assert "No entries yet" in md

    def test_playbook_renders_entries(self):
        store = KaizenReviewStore()
        store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            playbook_entries=[
                PlaybookEntry(
                    title="Always run lint before commit",
                    description="Prevents CI failures from style issues",
                    tags=["process", "ci"],
                ),
                PlaybookEntry(
                    title="Use cost ceilings on all packets",
                    description="Prevents runaway agent spending",
                    tags=["budget"],
                ),
            ],
        ))
        md = store.render_playbook_markdown("core-ops")
        assert "Always run lint" in md
        assert "cost ceilings" in md
        assert "[process, ci]" in md
        assert "2 entries from 1 reviews" in md

    def test_supersedes_renders(self):
        store = KaizenReviewStore()
        store.submit_review(KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            playbook_entries=[
                PlaybookEntry(
                    title="Updated caching strategy",
                    description="Use Redis instead of local",
                    supersedes="pb_old123",
                ),
            ],
        ))
        md = store.render_playbook_markdown("core-ops")
        assert "Supersedes: pb_old123" in md


# -----------------------------------------------------------------------
# Review serialization
# -----------------------------------------------------------------------

class TestReviewSerialization:

    def test_to_dict(self):
        review = KaizenReview(
            room_id="core-ops",
            reviewer="dhyana",
            reviewed_packet_ids=["wp_001"],
            findings=[
                KaizenFinding(
                    category="process",
                    observation="Slow",
                    recommendation="Speed up",
                    severity="info",
                ),
            ],
            playbook_entries=[
                PlaybookEntry(
                    title="Be fast",
                    description="Go faster",
                    tags=["perf"],
                ),
            ],
            summary="One review",
        )
        d = review.to_dict()
        assert d["room_id"] == "core-ops"
        assert len(d["findings"]) == 1
        assert d["findings"][0]["category"] == "process"
        assert len(d["playbook_entries"]) == 1
        assert d["playbook_entries"][0]["title"] == "Be fast"
        assert d["summary"] == "One review"


# -----------------------------------------------------------------------
# Integration: review → store → playbook cycle
# -----------------------------------------------------------------------

class TestSECICycle:
    """End-to-end test proving the SECI knowledge compounding cycle."""

    def test_full_seci_cycle(self):
        """Externalization → Combination → playbook available."""
        store = KaizenReviewStore()

        # Step 1: Build review from packet outcomes (Externalization)
        review = build_review_from_packets(
            room_id="rev-wedge",
            reviewer="dhyana",
            packets=[
                {"id": "wp_001", "outcome": "success", "cost_tokens": 950, "cost_ceiling": 1000},
                {"id": "wp_002", "outcome": "failed: rate limited"},
            ],
        )
        assert review.verdict == ReviewVerdict.NEEDS_IMPROVEMENT
        assert len(review.findings) >= 2  # failure + budget warning

        # Step 2: Reviewer adds playbook entry (Combination)
        review.playbook_entries.append(PlaybookEntry(
            title="Add rate limit retry",
            description="Wrap API calls in exponential backoff",
            tags=["tooling", "reliability"],
        ))

        # Step 3: Submit to store
        store.submit_review(review)

        # Step 4: Playbook is available for next iteration (Internalization)
        playbook = store.playbook_for_room("rev-wedge")
        assert len(playbook) == 1
        assert playbook[0].title == "Add rate limit retry"

        # Step 5: Verify findings are queryable
        warnings = store.all_findings("rev-wedge", severity="warning")
        assert len(warnings) >= 1

        # Step 6: Verify room isolation
        assert store.playbook_count("other-room") == 0
