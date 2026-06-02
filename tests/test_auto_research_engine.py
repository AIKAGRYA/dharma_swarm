"""Tests for dharma_swarm/auto_research/engine.py — AutoResearch engine."""

from __future__ import annotations

from dharma_swarm.auto_research.engine import AutoResearchEngine
from dharma_swarm.auto_research.models import ResearchBrief, ResearchQuery, SourceDocument
from dharma_swarm.auto_research.search import NullSearchBackend


class TestAutoResearchEngine:
    def test_init_defaults(self) -> None:
        engine = AutoResearchEngine()
        assert engine.planner is not None
        assert engine.search_backend is not None
        assert engine.reader is not None
        assert engine.claim_graph is not None
        assert engine.reporter is not None

    def test_init_custom_backend(self) -> None:
        backend = NullSearchBackend()
        engine = AutoResearchEngine(search_backend=backend)
        assert engine.search_backend is backend

    def test_plan_returns_queries(self) -> None:
        engine = AutoResearchEngine()
        brief = ResearchBrief(
            task_id="t-001",
            topic="agent testing",
            question="How to test multi-agent systems?",
        )
        queries = engine.plan(brief)
        assert isinstance(queries, list)
        for q in queries:
            assert isinstance(q, ResearchQuery)

    def test_run_produces_report(self) -> None:
        engine = AutoResearchEngine()
        brief = ResearchBrief(
            task_id="t-002",
            topic="code governance",
            question="What are governance best practices?",
        )
        report = engine.run(brief)
        assert report.task_id == "t-002"
        assert report.report_id != ""

    def test_run_with_null_backend(self) -> None:
        engine = AutoResearchEngine(search_backend=NullSearchBackend())
        brief = ResearchBrief(
            task_id="t-003",
            topic="empty search",
            question="No results expected",
        )
        report = engine.run(brief)
        assert report is not None
        assert report.source_ids == [] or len(report.source_ids) == 0
