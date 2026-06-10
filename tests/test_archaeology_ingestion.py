"""Tests for dharma_swarm.archaeology_ingestion — institutional memory indexer.

Validates:
- MemoryHit dataclass
- _utc_iso: ISO format
- _truncate: within limit, over limit, at boundary
- ingest_evolution_archive: missing file, empty file, valid entries
- ingest_shared_research: missing dir, no files, with markdown
- ingest_stigmergy_marks: missing file, below threshold, above threshold
- ingest_task_completions: missing file, valid entries
- ArchaeologyIngestionDaemon: real VectorStore-backed canary pass
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from dharma_swarm.archaeology_ingestion import (
    ArchaeologyIngestionDaemon,
    MemoryHit,
    _truncate,
    _utc_iso,
    ingest_evolution_archive,
    ingest_shared_research,
    ingest_stigmergy_marks,
    ingest_task_completions,
    query_archaeology,
)


# ---------------------------------------------------------------------------
# MemoryHit
# ---------------------------------------------------------------------------


class TestMemoryHit:
    def test_defaults(self):
        hit = MemoryHit(content="Test", source="s", layer="meta")
        assert hit.relevance_score == 0.0
        assert hit.metadata is None

    def test_with_metadata(self):
        hit = MemoryHit(content="C", source="s", layer="dev", metadata={"k": 1})
        assert hit.metadata["k"] == 1


# ---------------------------------------------------------------------------
# _utc_iso
# ---------------------------------------------------------------------------


class TestUtcIso:
    def test_iso_format(self):
        result = _utc_iso()
        assert "T" in result


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_within_limit(self):
        assert _truncate("hello", 100) == "hello"

    def test_over_limit(self):
        result = _truncate("a" * 200, 100)
        assert len(result) > 100  # includes truncation notice
        assert "truncated" in result

    def test_at_boundary(self):
        assert _truncate("abc", 3) == "abc"


# ---------------------------------------------------------------------------
# ingest_evolution_archive
# ---------------------------------------------------------------------------


class TestIngestEvolutionArchive:
    @pytest.mark.asyncio
    async def test_missing_file(self, tmp_path):
        palace = AsyncMock()
        result = await ingest_evolution_archive(palace, tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_valid_entries(self, tmp_path):
        evo_dir = tmp_path / "evolution"
        evo_dir.mkdir()
        entries = [
            {"id": "e1", "component": "router.py", "status": "applied",
             "diff": "- old\n+ new", "fitness": {"weighted": 0.8, "correctness": 0.9, "dharmic_alignment": 0.7}},
            {"id": "e2", "component": "cascade.py", "status": "rolled_back",
             "diff": "changed", "fitness": {"weighted": 0.3}},
        ]
        (evo_dir / "archive.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries)
        )

        palace = AsyncMock()
        palace.ingest = AsyncMock(side_effect=["doc1", "doc2"])
        result = await ingest_evolution_archive(palace, tmp_path)
        assert result == 2
        assert palace.ingest.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        evo_dir = tmp_path / "evolution"
        evo_dir.mkdir()
        (evo_dir / "archive.jsonl").write_text("")

        palace = AsyncMock()
        result = await ingest_evolution_archive(palace, tmp_path)
        assert result == 0


# ---------------------------------------------------------------------------
# ingest_shared_research
# ---------------------------------------------------------------------------


class TestIngestSharedResearch:
    @pytest.mark.asyncio
    async def test_missing_dir(self, tmp_path):
        palace = AsyncMock()
        result = await ingest_shared_research(palace, tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_with_markdown(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "analysis.md").write_text("# Competitor Analysis\nSome research.")

        palace = AsyncMock()
        palace.ingest = AsyncMock(return_value="doc1")
        result = await ingest_shared_research(palace, tmp_path)
        assert result == 1


# ---------------------------------------------------------------------------
# ingest_stigmergy_marks
# ---------------------------------------------------------------------------


class TestIngestStigmergyMarks:
    @pytest.mark.asyncio
    async def test_missing_file(self, tmp_path):
        palace = AsyncMock()
        result = await ingest_stigmergy_marks(palace, tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_filters_by_salience(self, tmp_path):
        stig_dir = tmp_path / "stigmergy"
        stig_dir.mkdir()
        marks = [
            {"id": "m1", "salience": 0.5, "channel": "test", "observation": "Low sal", "agent": "a1"},
            {"id": "m2", "salience": 0.95, "channel": "gnani", "observation": "High sal mark", "agent": "gnani-lodestone"},
        ]
        (stig_dir / "marks.jsonl").write_text(
            "\n".join(json.dumps(m) for m in marks)
        )

        palace = AsyncMock()
        palace.ingest = AsyncMock(return_value="doc1")
        result = await ingest_stigmergy_marks(palace, tmp_path)
        assert result == 1  # only the high-salience mark

    @pytest.mark.asyncio
    async def test_skips_empty_observation(self, tmp_path):
        stig_dir = tmp_path / "stigmergy"
        stig_dir.mkdir()
        marks = [
            {"id": "m1", "salience": 0.95, "channel": "test", "observation": "", "agent": "a1"},
        ]
        (stig_dir / "marks.jsonl").write_text(json.dumps(marks[0]))

        palace = AsyncMock()
        result = await ingest_stigmergy_marks(palace, tmp_path)
        assert result == 0


# ---------------------------------------------------------------------------
# ingest_task_completions
# ---------------------------------------------------------------------------


class TestIngestTaskCompletions:
    @pytest.mark.asyncio
    async def test_missing_file(self, tmp_path):
        palace = AsyncMock()
        result = await ingest_task_completions(palace, tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_with_entries(self, tmp_path):
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks = [
            {"title": "Fix router", "status": "completed", "result_summary": "Fixed timeout"},
            {"title": "Add tests", "status": "completed", "output": "14 tests added"},
        ]
        (tasks_dir / "completed.jsonl").write_text(
            "\n".join(json.dumps(t) for t in tasks)
        )

        palace = AsyncMock()
        palace.ingest = AsyncMock(side_effect=["d1", "d2"])
        result = await ingest_task_completions(palace, tmp_path)
        assert result == 2


# ---------------------------------------------------------------------------
# ArchaeologyIngestionDaemon canary
# ---------------------------------------------------------------------------


class TestArchaeologyIngestionDaemonCanary:
    @pytest.mark.asyncio
    async def test_run_once_indexes_all_streams_into_vector_store(self, tmp_path):
        evo_dir = tmp_path / "evolution"
        shared_dir = tmp_path / "shared"
        stig_dir = tmp_path / "stigmergy"
        tasks_dir = tmp_path / "tasks"
        for directory in [evo_dir, shared_dir, stig_dir, tasks_dir]:
            directory.mkdir()

        evolution_entry = {
            "id": "canary-evo-1",
            "component": "provider_router.py",
            "status": "applied",
            "timestamp": "2026-05-28T00:00:00+00:00",
            "diff": "+ cobalt canary vector store provider timeout repair",
            "fitness": {
                "weighted": 0.91,
                "correctness": 0.94,
                "dharmic_alignment": 0.89,
            },
            "test_results": {"pytest": "passed"},
        }
        (evo_dir / "archive.jsonl").write_text(json.dumps(evolution_entry), encoding="utf-8")

        (shared_dir / "canary_research.md").write_text(
            "# Canary Research\n\n"
            "Cobalt canary archaeology research confirms vector store retrieval.",
            encoding="utf-8",
        )

        high_salience_mark = {
            "id": "canary-mark-1",
            "salience": 0.93,
            "channel": "canary",
            "observation": "Cobalt canary stigmergy mark survived ingestion.",
            "agent": "archaeology-canary",
        }
        low_salience_mark = {
            "id": "canary-mark-low",
            "salience": 0.2,
            "channel": "canary",
            "observation": "This low salience mark should not be ingested.",
            "agent": "archaeology-canary",
        }
        (stig_dir / "marks.jsonl").write_text(
            "\n".join(json.dumps(mark) for mark in [high_salience_mark, low_salience_mark]),
            encoding="utf-8",
        )

        task_completion = {
            "id": "canary-task-1",
            "title": "Complete archaeology vector store canary",
            "status": "completed",
            "agent_id": "archaeology-canary",
            "completed_at": "2026-05-28T00:01:00+00:00",
            "result_summary": "Cobalt canary verifier completed query archaeology hit checks.",
        }
        (tasks_dir / "completed.jsonl").write_text(
            json.dumps(task_completion),
            encoding="utf-8",
        )

        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path, interval_seconds=1)
        counts = await daemon.run_once()

        assert counts == {
            "evolution_archive": 1,
            "shared_research": 1,
            "stigmergy_marks": 1,
            "task_completions": 1,
        }

        from dharma_swarm.vector_store import VectorStore

        stats = VectorStore(state_dir=tmp_path).stats()
        assert stats["total_documents"] == 4
        assert stats["valid_documents"] == 4
        assert stats["by_layer"] == {
            "development": 2,
            "meta": 1,
            "session": 1,
        }

        lessons_path = tmp_path / "meta" / "lessons_learned.md"
        assert lessons_path.exists()
        assert "# DHARMA SWARM Lessons Learned" in lessons_path.read_text(encoding="utf-8")

        hits = await query_archaeology(
            "cobalt canary vector store provider timeout",
            state_dir=tmp_path,
            top_k=5,
        )
        hit_text = "\n".join(hit.content for hit in hits)
        hit_sources = {hit.source for hit in hits}

        assert len(hits) >= 2
        assert "Cobalt canary" in hit_text or "cobalt canary" in hit_text
        assert "evolution_archive:canary-evo-1" in hit_sources
