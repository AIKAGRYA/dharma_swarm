"""Tests for dharma_swarm.archaeology_ingestion — institutional memory indexer.

Validates:
- MemoryHit dataclass
- _utc_iso: ISO format
- _truncate: within limit, over limit, at boundary
- ingest_evolution_archive: missing file, empty file, valid entries
- ingest_shared_research: missing dir, no files, with markdown
- ingest_stigmergy_marks: missing file, below threshold, above threshold
- ingest_task_completions: missing file, valid entries
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from dharma_swarm.archaeology_ingestion import (
    MemoryHit,
    _truncate,
    _utc_iso,
    ingest_evolution_archive,
    ingest_shared_research,
    ingest_stigmergy_marks,
    ingest_task_completions,
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
