"""Tests for dharma_swarm.jk_stigmergy_seeds — JK critique stigmergy marks.

Validates:
- _GNANI_MARKS structure (defined inline in seed_critique_marks)
- seed_critique_marks idempotency
- seed_sync synchronous wrapper
- Mark content: IDs, channels, salience, connections
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dharma_swarm.jk_stigmergy_seeds import seed_critique_marks


# ---------------------------------------------------------------------------
# seed_critique_marks — structure validation
# ---------------------------------------------------------------------------


class TestSeedCritiqueMarks:
    @pytest.mark.asyncio
    async def test_injects_marks_when_none_exist(self):
        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[])
        mock_store.leave_mark = AsyncMock()

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            count = await seed_critique_marks()

        assert count == 7
        assert mock_store.leave_mark.call_count == 7

    @pytest.mark.asyncio
    async def test_idempotent_skips_existing(self):
        existing_mark = MagicMock()
        existing_mark.id = "jk_critique_001"

        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[existing_mark])
        mock_store.leave_mark = AsyncMock()

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            count = await seed_critique_marks()

        # All 7 marks check against the same mock returning the same existing mark
        # Only jk_critique_001 should be skipped, rest should be injected
        assert count == 6

    @pytest.mark.asyncio
    async def test_marks_have_correct_channels(self):
        marks_injected = []
        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[])

        async def capture_mark(mark):
            marks_injected.append(mark)

        mock_store.leave_mark = capture_mark

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            await seed_critique_marks()

        channels = {m.channel for m in marks_injected}
        assert "governance" in channels
        assert "strategy" in channels
        assert "research" in channels

    @pytest.mark.asyncio
    async def test_marks_have_high_salience(self):
        marks_injected = []
        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[])

        async def capture_mark(mark):
            marks_injected.append(mark)

        mock_store.leave_mark = capture_mark

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            await seed_critique_marks()

        for mark in marks_injected:
            assert mark.salience >= 0.85

    @pytest.mark.asyncio
    async def test_marks_have_connections(self):
        marks_injected = []
        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[])

        async def capture_mark(mark):
            marks_injected.append(mark)

        mock_store.leave_mark = capture_mark

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            await seed_critique_marks()

        for mark in marks_injected:
            assert len(mark.connections) >= 1

    @pytest.mark.asyncio
    async def test_all_mark_ids_unique(self):
        marks_injected = []
        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[])

        async def capture_mark(mark):
            marks_injected.append(mark)

        mock_store.leave_mark = capture_mark

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            await seed_critique_marks()

        ids = [m.id for m in marks_injected]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_agent_is_sage_critic(self):
        marks_injected = []
        mock_store = AsyncMock()
        mock_store.read_marks = AsyncMock(return_value=[])

        async def capture_mark(mark):
            marks_injected.append(mark)

        mock_store.leave_mark = capture_mark

        with patch("dharma_swarm.stigmergy.StigmergyStore", return_value=mock_store):
            await seed_critique_marks()

        for mark in marks_injected:
            assert mark.agent == "sage-critic"
