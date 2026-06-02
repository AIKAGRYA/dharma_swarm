"""Tests for dharma_swarm/auto_research/search.py — SearchBackend Protocol."""

from __future__ import annotations

from typing import Any

from dharma_swarm.auto_research.models import ResearchBrief, ResearchQuery, SourceDocument
from dharma_swarm.auto_research.search import NullSearchBackend, SearchBackend


def _sample_brief() -> ResearchBrief:
    return ResearchBrief(
        task_id="task-001",
        topic="code governance",
        question="What are best practices?",
    )


def _sample_queries() -> list[ResearchQuery]:
    return [
        ResearchQuery(query_id="q1", text="code governance best practices", intent="overview"),
        ResearchQuery(query_id="q2", text="agent evaluation patterns", intent="compare"),
    ]


class TestNullSearchBackend:
    def test_has_search_method(self) -> None:
        backend = NullSearchBackend()
        assert hasattr(backend, "search")
        assert callable(backend.search)

    def test_returns_empty_list(self) -> None:
        backend = NullSearchBackend()
        result = backend.search(_sample_brief(), _sample_queries())
        assert result == []

    def test_returns_list_type(self) -> None:
        backend = NullSearchBackend()
        result = backend.search(_sample_brief(), [])
        assert isinstance(result, list)


class TestSearchBackendProtocol:
    def test_custom_backend_conforms(self) -> None:
        class StubBackend:
            def search(
                self,
                brief: ResearchBrief,
                queries: list[ResearchQuery],
            ) -> list[SourceDocument | dict[str, Any]]:
                return [
                    SourceDocument(
                        source_id="src-1",
                        url="https://example.com",
                        title="Test",
                    )
                ]

        backend = StubBackend()
        assert hasattr(backend, "search")
        results = backend.search(_sample_brief(), _sample_queries())
        assert len(results) == 1

    def test_dict_return_type(self) -> None:
        class DictBackend:
            def search(
                self,
                brief: ResearchBrief,
                queries: list[ResearchQuery],
            ) -> list[SourceDocument | dict[str, Any]]:
                return [{"source_id": "raw-1", "url": "https://raw.example.com"}]

        backend = DictBackend()
        assert hasattr(backend, "search")
        results = backend.search(_sample_brief(), _sample_queries())
        assert results[0]["url"] == "https://raw.example.com"
