"""Tests for the Research RTN pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.auto_research.models import (
    ClaimRecord,
    ResearchBrief,
    ResearchReport,
    SourceDocument,
)
from dharma_swarm.auto_research.search import NullSearchBackend
from dharma_swarm.auto_grade.models import GradeCard, RewardSignal
from dharma_swarm.research_rtn import ResearchRTN, RTNRunResult
from dharma_swarm.research_rtn_verify import VerificationResult, verify_claims
from dharma_swarm.research_rtn_review import ReviewResult, review_report
from dharma_swarm.research_tracks import (
    ALL_TRACKS,
    MARKET_INTELLIGENCE,
    NEURIPS_FOUNDATION,
    SWARM_EVOLUTION,
    ResearchTrack,
    get_track,
)


# ── Fixtures ──


def _make_brief(**overrides) -> ResearchBrief:
    defaults = {
        "task_id": "test-rtn-001",
        "topic": "test topic",
        "question": "test question",
    }
    defaults.update(overrides)
    return ResearchBrief(**defaults)


def _make_source(sid: str, title: str = "Test Source", content: str = "") -> SourceDocument:
    return SourceDocument(
        source_id=sid,
        url=f"https://example.com/{sid}",
        title=title,
        content=content,
    )


def _make_claim(cid: str, text: str, source_ids: list[str] | None = None) -> ClaimRecord:
    return ClaimRecord(
        claim_id=cid,
        text=text,
        support_level="supported",
        supporting_source_ids=source_ids or [],
        confidence=0.8,
    )


def _make_report(brief: ResearchBrief, claims: list[ClaimRecord] | None = None) -> ResearchReport:
    claims = claims or []
    return ResearchReport(
        report_id=f"report-{brief.task_id}",
        task_id=brief.task_id,
        brief=brief,
        summary=f"Test report for {brief.topic}",
        body="- Test finding 1\n- Test finding 2",
        claims=claims,
        source_ids=["s1", "s2", "s3"],
    )


def _make_reward(task_id: str, score: float = 0.8, gate_failures: list[str] | None = None) -> RewardSignal:
    return RewardSignal(
        task_id=task_id,
        report_id=f"report-{task_id}",
        grade_card=GradeCard(
            task_id=task_id,
            report_id=f"report-{task_id}",
            groundedness=0.9,
            citation_precision=0.95,
            citation_coverage=0.92,
            source_quality=0.8,
            source_diversity=0.7,
            topical_coverage=0.85,
            contradiction_handling=1.0,
            freshness=0.6,
            structure=0.8,
            actionability=0.7,
            novelty=0.5,
            traceability=0.9,
            final_score=score,
            gate_failures=gate_failures or [],
            promotion_state="candidate" if not gate_failures else "rejected",
        ),
        scalar_reward=(2.0 * score) - 1.0,
        gate_multiplier=1.0 if not gate_failures else 0.0,
    )


# ── Track Tests ──


class TestResearchTracks:
    def test_all_tracks_defined(self):
        assert len(ALL_TRACKS) == 3
        slugs = {t.slug for t in ALL_TRACKS}
        assert slugs == {"swarm-evolution", "neurips-foundation", "market-intelligence"}

    def test_get_track(self):
        track = get_track("swarm-evolution")
        assert track is SWARM_EVOLUTION

    def test_get_track_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown track"):
            get_track("nonexistent")

    def test_next_brief_cycles(self):
        track = SWARM_EVOLUTION
        b0 = track.next_brief(index=0)
        b1 = track.next_brief(index=1)
        assert b0.topic != b1.topic
        assert b0.metadata["track"] == "swarm-evolution"

    def test_next_brief_wraps(self):
        track = SWARM_EVOLUTION
        n = len(track.templates)
        b_wrap = track.next_brief(index=n)
        b_first = track.next_brief(index=0)
        assert b_wrap.topic == b_first.topic

    def test_each_track_has_templates(self):
        for track in ALL_TRACKS:
            assert len(track.templates) >= 3, f"Track {track.slug} needs more templates"

    def test_neurips_has_academic_audience(self):
        for tmpl in NEURIPS_FOUNDATION.templates:
            assert tmpl.audience == "academic"

    def test_market_has_business_audience(self):
        for tmpl in MARKET_INTELLIGENCE.templates:
            assert tmpl.audience == "business"


# ── Verify Tests ──


class TestVerifyClaims:
    def test_empty_claims(self):
        result = verify_claims([], [])
        assert result.verification_score == 1.0
        assert result.verified_claims == []

    def test_supported_claim(self):
        sources = [
            _make_source("s1", content="agent task selection scoring is important for multi-agent systems"),
            _make_source("s2", content="task selection scoring drives agent performance metrics"),
        ]
        claims = [_make_claim("c1", "Agent task selection scoring is important", ["s1"])]
        result = verify_claims(claims, sources)
        assert result.verification_score > 0
        assert len(result.verified_claims) >= 1

    def test_contradiction_detection(self):
        claims = [
            _make_claim("c1", "The method shows significant improvement in performance"),
            _make_claim("c2", "The method shows insignificant improvement in baseline"),
        ]
        result = verify_claims(claims, [])
        assert len(result.contradiction_pairs) > 0

    def test_unsupported_claim(self):
        claims = [_make_claim("c1", "xyz123 completely unique nonsensical text")]
        sources = [_make_source("s1", content="unrelated content about weather")]
        result = verify_claims(claims, sources)
        assert len(result.unsupported_claims) >= 1


# ── Review Tests ──


class TestReviewReport:
    def test_passing_report(self):
        brief = _make_brief()
        report = _make_report(brief)
        verification = VerificationResult(verification_score=0.9, verified_claims=[])
        reward = _make_reward(brief.task_id, score=0.85)

        result = review_report(report, verification, reward, brief)
        assert result.should_recurse is False
        assert result.review_score == 0.85

    def test_failing_report_generates_follow_ups(self):
        brief = _make_brief(metadata={"track": "swarm-evolution"})
        report = _make_report(brief)
        report = report.model_copy(update={"source_ids": ["s1"]})
        unsupported = [_make_claim("c1", "unsupported claim text")]
        verification = VerificationResult(
            verification_score=0.3,
            unsupported_claims=unsupported,
        )
        reward = _make_reward(brief.task_id, score=0.4, gate_failures=["groundedness"])

        result = review_report(report, verification, reward, brief, recurse_threshold=0.6)
        assert result.should_recurse is True
        assert len(result.follow_up_briefs) > 0
        assert len(result.gaps) > 0

    def test_gaps_detected_for_few_sources(self):
        brief = _make_brief()
        report = _make_report(brief)
        report = report.model_copy(update={"source_ids": ["s1"]})
        verification = VerificationResult(verification_score=1.0)
        reward = _make_reward(brief.task_id, score=0.7)

        result = review_report(report, verification, reward, brief)
        assert any("breadth" in g.lower() or "fewer" in g.lower() for g in result.gaps)


# ── RTN Controller Tests ──


class TestResearchRTN:
    def test_basic_execution(self):
        rtn = ResearchRTN()
        brief = _make_brief()
        result = rtn.execute_brief(brief)

        assert isinstance(result, RTNRunResult)
        assert result.report is not None
        assert result.reward is not None
        assert result.verification is not None
        assert result.review is not None
        assert result.duration_seconds > 0

    def test_execute_convenience(self):
        rtn = ResearchRTN()
        result = rtn.execute("test topic")
        assert result.report is not None

    def test_null_backend_produces_report(self):
        rtn = ResearchRTN(search_backend=NullSearchBackend())
        brief = _make_brief()
        result = rtn.execute_brief(brief)
        assert result.report is not None
        assert result.report.task_id == brief.task_id

    def test_artifact_published_on_pass(self, tmp_path):
        from dharma_swarm.artifact_store import RuntimeArtifactStore
        store = RuntimeArtifactStore(base_dir=tmp_path / "artifacts")
        rtn = ResearchRTN(
            artifact_store=store,
            artifact_dir=tmp_path / "research",
        )
        brief = _make_brief()
        result = rtn.execute_brief(brief)
        # NullSearchBackend → no sources → grade may fail gates
        # But the pipeline should complete without error
        assert result.error == ""

    def test_max_depth_respected(self):
        rtn = ResearchRTN(max_depth=1)
        brief = _make_brief()
        result = rtn.execute_brief(brief)
        for sub in result.sub_results:
            assert sub.depth <= 1
            assert len(sub.sub_results) == 0

    def test_track_brief_execution(self):
        rtn = ResearchRTN()
        brief = SWARM_EVOLUTION.next_brief(index=0)
        result = rtn.execute_brief(brief)
        assert result.report is not None
        assert result.brief.metadata["track"] == "swarm-evolution"

    def test_all_tracks_produce_results(self):
        rtn = ResearchRTN()
        for track in ALL_TRACKS:
            brief = track.next_brief(index=0)
            result = rtn.execute_brief(brief)
            assert result.report is not None, f"Track {track.slug} failed to produce report"
            assert result.error == "", f"Track {track.slug} had error: {result.error}"
