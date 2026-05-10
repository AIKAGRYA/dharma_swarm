"""Tests for the multi-section Research RTN orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from dharma_swarm.auto_research.models import ClaimRecord, ResearchBrief, SourceDocument
from dharma_swarm.auto_research.search import NullSearchBackend
from dharma_swarm.auto_grade.models import GradeCard, RewardSignal
from dharma_swarm.research_rtn_multi import (
    COMPETITIVE_LANDSCAPE_SECTIONS,
    MultiSectionResult,
    MultiSectionRTN,
    SectionResult,
    SectionSpec,
)
from dharma_swarm.research_rtn_synthesize import (
    SourceSummary,
    SynthesisEngine,
    SynthesizedSection,
)


# ── Test Fixtures ──


class MockSynthesisEngine(SynthesisEngine):
    """Synthesis engine that returns canned responses without LLM calls."""

    def __init__(self) -> None:
        super().__init__(router=None)

    async def summarize_sources(self, sources, max_concurrent=3):
        return [
            SourceSummary(
                source_id=s.source_id if hasattr(s, "source_id") else "mock-src",
                title=s.title if hasattr(s, "title") else "Mock Source",
                url=s.url if hasattr(s, "url") else "https://example.com",
                summary="Mock summary of source content.",
                key_facts=["Fact 1", "Fact 2"],
            )
            for s in sources
        ]

    async def synthesize_section(self, section_title, section_description, summaries, claims, target_words=600):
        source_ids = [s.source_id for s in summaries]
        mock_claims = [
            ClaimRecord(
                claim_id=f"mock-claim-{i}",
                text=f"Mock finding {i} about {section_title}.",
                support_level="supported",
                supporting_source_ids=source_ids[:1] if source_ids else [],
                citations=[f"[{source_ids[0]}]"] if source_ids else [],
                confidence=0.85,
            )
            for i in range(3)
        ]
        return SynthesizedSection(
            title=section_title,
            text=f"This is a mock synthesis of {section_title}. It contains analytical prose about {section_description[:50]}.",
            claims=mock_claims,
            source_ids_used=source_ids,
            model_used="mock",
            provider_used="mock",
        )


SMALL_SECTIONS = [
    SectionSpec(
        title="Test Section A",
        description="First test section",
        queries=["test query A"],
        target_words=100,
    ),
    SectionSpec(
        title="Test Section B",
        description="Second test section",
        queries=["test query B"],
        target_words=100,
    ),
]


# ── Section Spec Tests ──


class TestSectionSpecs:
    def test_competitive_landscape_has_6_sections(self):
        assert len(COMPETITIVE_LANDSCAPE_SECTIONS) == 6

    def test_each_section_has_queries(self):
        for spec in COMPETITIVE_LANDSCAPE_SECTIONS:
            assert len(spec.queries) >= 2, f"Section '{spec.title}' needs more queries"

    def test_total_target_words(self):
        total = sum(s.target_words for s in COMPETITIVE_LANDSCAPE_SECTIONS)
        assert 3000 <= total <= 5000, f"Total target words ({total}) outside 3-5K range"

    def test_landscape_section_has_most_queries(self):
        landscape = COMPETITIVE_LANDSCAPE_SECTIONS[0]
        assert len(landscape.queries) >= 5


# ── Synthesis Engine Tests ──


class TestMockSynthesisEngine:
    @pytest.mark.asyncio
    async def test_summarize_sources(self):
        engine = MockSynthesisEngine()
        sources = [
            SourceDocument(source_id="s1", url="https://example.com/1", title="Source 1"),
        ]
        summaries = await engine.summarize_sources(sources)
        assert len(summaries) == 1
        assert summaries[0].source_id == "s1"

    @pytest.mark.asyncio
    async def test_synthesize_section(self):
        engine = MockSynthesisEngine()
        summaries = [SourceSummary(source_id="s1", title="T", url="u", summary="S")]
        section = await engine.synthesize_section(
            "Test", "desc", summaries, [], target_words=100
        )
        assert section.title == "Test"
        assert len(section.claims) == 3
        assert "s1" in section.source_ids_used


# ── Multi-Section RTN Tests ──


class TestMultiSectionRTN:
    @pytest.mark.asyncio
    async def test_basic_execution(self, tmp_path):
        from dharma_swarm.artifact_store import RuntimeArtifactStore
        rtn = MultiSectionRTN(
            search_backend=NullSearchBackend(),
            synthesis_engine=MockSynthesisEngine(),
            artifact_store=RuntimeArtifactStore(base_dir=tmp_path / "artifacts"),
            sections=SMALL_SECTIONS,
            artifact_dir=tmp_path / "research",
        )
        result = await rtn.execute()

        assert isinstance(result, MultiSectionResult)
        assert len(result.sections) == 2
        assert result.merged_report is not None
        assert result.reward is not None
        assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_merged_report_has_all_sections(self, tmp_path):
        from dharma_swarm.artifact_store import RuntimeArtifactStore
        rtn = MultiSectionRTN(
            search_backend=NullSearchBackend(),
            synthesis_engine=MockSynthesisEngine(),
            artifact_store=RuntimeArtifactStore(base_dir=tmp_path / "artifacts"),
            sections=SMALL_SECTIONS,
            artifact_dir=tmp_path / "research",
        )
        result = await rtn.execute()

        assert result.merged_report is not None
        body = result.merged_report.body
        assert "Test Section A" in body
        assert "Test Section B" in body

    @pytest.mark.asyncio
    async def test_artifact_written_to_disk(self, tmp_path):
        from dharma_swarm.artifact_store import RuntimeArtifactStore
        rtn = MultiSectionRTN(
            search_backend=NullSearchBackend(),
            synthesis_engine=MockSynthesisEngine(),
            artifact_store=RuntimeArtifactStore(base_dir=tmp_path / "artifacts"),
            sections=SMALL_SECTIONS,
            artifact_dir=tmp_path / "research",
        )
        result = await rtn.execute()

        # Should have written artifact + manifest
        research_dir = tmp_path / "research"
        md_files = list(research_dir.glob("*.md"))
        manifest_files = list(research_dir.glob("*.manifest.json"))
        assert len(md_files) >= 1
        assert len(manifest_files) >= 1

    @pytest.mark.asyncio
    async def test_section_errors_collected(self, tmp_path):
        from dharma_swarm.artifact_store import RuntimeArtifactStore

        class FailingSynthesis(MockSynthesisEngine):
            async def synthesize_section(self, *args, **kwargs):
                raise RuntimeError("synthesis failed")

        rtn = MultiSectionRTN(
            search_backend=NullSearchBackend(),
            synthesis_engine=FailingSynthesis(),
            artifact_store=RuntimeArtifactStore(base_dir=tmp_path / "artifacts"),
            sections=SMALL_SECTIONS,
            artifact_dir=tmp_path / "research",
        )
        result = await rtn.execute()
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_null_backend_still_produces_result(self, tmp_path):
        from dharma_swarm.artifact_store import RuntimeArtifactStore
        rtn = MultiSectionRTN(
            search_backend=NullSearchBackend(),
            synthesis_engine=MockSynthesisEngine(),
            artifact_store=RuntimeArtifactStore(base_dir=tmp_path / "artifacts"),
            sections=SMALL_SECTIONS[:1],
            artifact_dir=tmp_path / "research",
        )
        result = await rtn.execute()
        assert result.merged_report is not None
        assert result.reward is not None


# ── Claim Extraction Enhancement Tests ──


class TestEnhancedClaimExtraction:
    def test_factual_extraction_from_content(self):
        from dharma_swarm.auto_research.claim_graph import ClaimGraphBuilder
        from dharma_swarm.auto_research.models import ResearchBrief

        brief = ResearchBrief(task_id="test", topic="test", question="test")
        sources = [
            SourceDocument(
                source_id="s1",
                url="https://example.com",
                title="Test",
                content="Devin raised $150 million in Series B funding in 2025. The weather is nice. Companies increased AI spending by 40% year over year.",
            ),
        ]
        builder = ClaimGraphBuilder()
        claims = builder.build(brief, sources)
        assert len(claims) >= 2
        for claim in claims:
            assert claim.supporting_source_ids == ["s1"]
            assert "[s1]" in claim.citations

    def test_empty_content_no_claims(self):
        from dharma_swarm.auto_research.claim_graph import ClaimGraphBuilder
        from dharma_swarm.auto_research.models import ResearchBrief

        brief = ResearchBrief(task_id="test", topic="test", question="test")
        sources = [
            SourceDocument(source_id="s1", url="https://example.com", content=""),
        ]
        builder = ClaimGraphBuilder()
        claims = builder.build(brief, sources)
        assert len(claims) == 0
