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


# ---------------------------------------------------------------------------
# Digest dedupe + per-cycle insert budget (PR-11)
# ---------------------------------------------------------------------------

from dharma_swarm.archaeology_ingestion import (  # noqa: E402
    ArchaeologyIngestionDaemon,
    IngestCycleLedger,
    _cycle_insert_budget,
    _ingest_into_palace,
)


class _FakePalace:
    """Stands in for MemoryPalace inside daemon.run_once."""

    ingest_calls: list[str] = []

    def __init__(self, state_dir=None, **_kwargs):
        self._state_dir = state_dir

    async def ingest(self, content, source, *, layer="working", tags=None,
                     metadata=None, event_time=None, dedupe_digest=None):
        _FakePalace.ingest_calls.append(source)
        return f"doc{len(_FakePalace.ingest_calls)}"

    async def recall(self, query):
        class _Resp:
            results: list = []
        return _Resp()


@pytest.fixture
def fake_palace(monkeypatch):
    _FakePalace.ingest_calls = []
    monkeypatch.setattr("dharma_swarm.memory_palace.MemoryPalace", _FakePalace)
    monkeypatch.delenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", raising=False)
    return _FakePalace


def _write_archive(state_dir: Path, n: int, prefix: str = "e") -> None:
    evo_dir = state_dir / "evolution"
    evo_dir.mkdir(exist_ok=True)
    entries = [
        {"id": f"{prefix}{i}", "component": "router.py", "status": "applied",
         "diff": f"change {i}", "fitness": {"weighted": 0.5}}
        for i in range(n)
    ]
    (evo_dir / "archive.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries)
    )


class TestDigestDedupeCycles:
    @pytest.mark.asyncio
    async def test_second_cycle_inserts_zero(self, tmp_path, fake_palace):
        _write_archive(tmp_path, 3)
        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path)

        counts1 = await daemon.run_once()
        assert counts1["evolution_archive"] == 3
        calls_after_first = len(fake_palace.ingest_calls)

        counts2 = await daemon.run_once()
        assert counts2["evolution_archive"] == 0
        assert counts2["skipped_unchanged"] == 3
        assert len(fake_palace.ingest_calls) == calls_after_first

    @pytest.mark.asyncio
    async def test_state_file_written(self, tmp_path, fake_palace):
        _write_archive(tmp_path, 2)
        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path)
        await daemon.run_once()
        state_path = tmp_path / "meta" / "archaeology_ingest_state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert len(state) == 2
        assert all(k.startswith("evolution_archive:") for k in state)

    @pytest.mark.asyncio
    async def test_changed_entry_reingested(self, tmp_path, fake_palace):
        _write_archive(tmp_path, 3)
        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path)
        await daemon.run_once()

        # Mutate one entry's content; keep the other two byte-identical
        archive = tmp_path / "evolution" / "archive.jsonl"
        lines = archive.read_text().splitlines()
        entry = json.loads(lines[0])
        entry["status"] = "rolled_back"
        lines[0] = json.dumps(entry)
        archive.write_text("\n".join(lines))

        counts = await daemon.run_once()
        assert counts["evolution_archive"] == 1
        assert counts["skipped_unchanged"] == 2

    @pytest.mark.asyncio
    async def test_corrupt_state_starts_fresh(self, tmp_path, fake_palace):
        _write_archive(tmp_path, 2)
        meta = tmp_path / "meta"
        meta.mkdir()
        (meta / "archaeology_ingest_state.json").write_text("{not json")
        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path)
        counts = await daemon.run_once()
        assert counts["evolution_archive"] == 2


class TestCycleInsertBudget:
    @pytest.mark.asyncio
    async def test_budget_cap_honored(self, tmp_path, fake_palace, monkeypatch):
        monkeypatch.setenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", "2")
        _write_archive(tmp_path, 5)
        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path)
        counts = await daemon.run_once()
        assert counts["evolution_archive"] == 2
        assert counts["skipped_budget"] == 3

    @pytest.mark.asyncio
    async def test_budget_resumes_next_cycle(self, tmp_path, fake_palace, monkeypatch):
        monkeypatch.setenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", "2")
        _write_archive(tmp_path, 5)
        daemon = ArchaeologyIngestionDaemon(state_dir=tmp_path)
        await daemon.run_once()

        counts2 = await daemon.run_once()
        assert counts2["evolution_archive"] == 2
        assert counts2["skipped_unchanged"] == 2
        assert counts2["skipped_budget"] == 1

        counts3 = await daemon.run_once()
        assert counts3["evolution_archive"] == 1
        assert counts3["skipped_unchanged"] == 4

        counts4 = await daemon.run_once()
        assert counts4["evolution_archive"] == 0
        assert counts4["skipped_unchanged"] == 5

    def test_env_parsing_fail_closed(self, monkeypatch):
        monkeypatch.delenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", raising=False)
        assert _cycle_insert_budget() == 500
        monkeypatch.setenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", "garbage")
        assert _cycle_insert_budget() == 500
        monkeypatch.setenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", "-3")
        assert _cycle_insert_budget() == 500
        monkeypatch.setenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", "0")
        assert _cycle_insert_budget() == 500
        monkeypatch.setenv("DHARMA_ARCHAEOLOGY_CYCLE_BUDGET", "7")
        assert _cycle_insert_budget() == 7


class TestIngestIntoPalaceLedger:
    @pytest.mark.asyncio
    async def test_no_ledger_keeps_legacy_behavior(self):
        palace = AsyncMock()
        palace.ingest = AsyncMock(return_value="doc1")
        doc_id = await _ingest_into_palace(
            palace, content="hello", source="s1", layer="working",
            tags=[], metadata={},
        )
        assert doc_id == "doc1"
        assert palace.ingest.call_args.kwargs["dedupe_digest"] is None

    @pytest.mark.asyncio
    async def test_failed_ingest_not_recorded(self):
        palace = AsyncMock()
        palace.ingest = AsyncMock(side_effect=RuntimeError("boom"))
        ledger = IngestCycleLedger()
        doc_id = await _ingest_into_palace(
            palace, content="hello", source="s1", layer="working",
            tags=[], metadata={}, ledger=ledger,
        )
        assert doc_id is None
        assert ledger.inserted == 0
        assert ledger.state == {}
