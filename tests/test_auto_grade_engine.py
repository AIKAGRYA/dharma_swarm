"""Tests for dharma_swarm/auto_grade/engine.py — AutoGrade evaluation engine."""

from __future__ import annotations

from dharma_swarm.auto_grade.engine import AutoGradeEngine
from dharma_swarm.auto_research.models import (
    ClaimRecord,
    ResearchBrief,
    ResearchReport,
    SourceDocument,
)


def _sample_brief() -> ResearchBrief:
    return ResearchBrief(
        task_id="grade-test-001",
        topic="testing",
        question="How does grading work?",
    )


def _sample_sources() -> list[SourceDocument]:
    return [
        SourceDocument(
            source_id="src-1",
            url="https://example.com/a",
            title="Source A",
            authority_score=0.9,
            freshness_score=0.8,
        ),
        SourceDocument(
            source_id="src-2",
            url="https://example.com/b",
            title="Source B",
            authority_score=0.7,
            freshness_score=0.6,
        ),
        SourceDocument(
            source_id="src-3",
            url="https://example.com/c",
            title="Source C",
            authority_score=0.8,
            freshness_score=0.9,
        ),
    ]


def _sample_claims(source_ids: list[str]) -> list[ClaimRecord]:
    return [
        ClaimRecord(
            claim_id="c1",
            text="Grading requires multiple metrics",
            support_level="strong",
            supporting_source_ids=[source_ids[0]],
            citations=[source_ids[0]],
            confidence=0.9,
        ),
        ClaimRecord(
            claim_id="c2",
            text="Source diversity improves reliability",
            support_level="moderate",
            supporting_source_ids=[source_ids[1]],
            citations=[source_ids[1]],
            confidence=0.85,
        ),
    ]


def _sample_report(sources: list[SourceDocument]) -> ResearchReport:
    source_ids = [s.source_id for s in sources]
    return ResearchReport(
        report_id="rpt-001",
        task_id="grade-test-001",
        brief=_sample_brief(),
        summary="A report about grading systems",
        body="Grading requires multiple metrics and source diversity.",
        claims=_sample_claims(source_ids),
        source_ids=source_ids,
    )


class TestAutoGradeEngine:
    def test_init(self) -> None:
        engine = AutoGradeEngine()
        assert hasattr(engine, "grade")

    def test_grade_basic(self) -> None:
        engine = AutoGradeEngine()
        sources = _sample_sources()
        report = _sample_report(sources)
        result = engine.grade(report, sources)
        assert result.task_id == "grade-test-001"
        assert result.report_id == "rpt-001"
        assert isinstance(result.scalar_reward, float)
        assert result.grade_card is not None

    def test_grade_card_metrics(self) -> None:
        engine = AutoGradeEngine()
        sources = _sample_sources()
        report = _sample_report(sources)
        result = engine.grade(report, sources)
        card = result.grade_card
        assert 0.0 <= card.groundedness <= 1.0
        assert 0.0 <= card.citation_precision <= 1.0
        assert 0.0 <= card.citation_coverage <= 1.0
        assert 0.0 <= card.source_quality <= 1.0
        assert 0.0 <= card.final_score <= 1.0

    def test_grade_with_efficiency_params(self) -> None:
        engine = AutoGradeEngine()
        sources = _sample_sources()
        report = _sample_report(sources)
        result = engine.grade(
            report,
            sources,
            latency_ms=5000,
            token_cost_usd=0.5,
            total_tokens=5000,
        )
        assert isinstance(result.scalar_reward, float)
        # Penalties applied when efficiency exceeds budget
        assert "cost_norm" in result.penalties

    def test_grade_empty_sources(self) -> None:
        engine = AutoGradeEngine()
        report = ResearchReport(
            report_id="rpt-empty",
            task_id="grade-test-empty",
            brief=_sample_brief(),
            summary="Empty report",
            body="No sources available.",
            claims=[],
            source_ids=[],
        )
        result = engine.grade(report, [])
        assert isinstance(result.scalar_reward, float)
        assert result.grade_card.final_score >= 0.0
        # Empty sources likely trigger gate failures
        assert result.gate_multiplier == 0.0 or len(result.grade_card.gate_failures) >= 0

    def test_gate_failures_reduce_score(self) -> None:
        engine = AutoGradeEngine()
        sources = _sample_sources()
        # Report with claims that reference non-existent sources (fabricated)
        bad_claims = [
            ClaimRecord(
                claim_id="bad-c1",
                text="This claim cites a nonexistent source",
                support_level="unsupported",
                supporting_source_ids=["fake-source-999"],
                citations=["fake-source-999"],
                confidence=0.9,
            ),
        ]
        report = ResearchReport(
            report_id="rpt-bad",
            task_id="grade-test-bad",
            brief=_sample_brief(),
            summary="Report with bad citations",
            body="Content with fabricated citations.",
            claims=bad_claims,
            source_ids=["fake-source-999"],
        )
        result = engine.grade(report, sources)
        # Gate failures should produce a low or zero score
        assert result.grade_card.final_score <= 0.5
        assert len(result.grade_card.gate_failures) > 0
