"""Tests for the RevenueScoutDaemon."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.revenue.spine import RevenueSpine, RevenueTarget, TargetStatus
from dharma_swarm.revenue.intelligence import RevenueIntelligenceIngestor
from dharma_swarm.revenue.scout_daemon import (
    RevenueScoutDaemon,
    ScoutCycleResult,
    revenue_scout_handler,
)


@pytest.fixture()
def daemon(tmp_path: Path) -> RevenueScoutDaemon:
    spine = RevenueSpine(storage_dir=tmp_path / "spine")
    ingestor = RevenueIntelligenceIngestor(storage_dir=tmp_path / "intel")
    return RevenueScoutDaemon(
        spine=spine,
        ingestor=ingestor,
        github_queries=["test query"],
        min_qualification_score=0.3,
        max_targets_per_cycle=5,
    )


class TestDaemonCycle:
    def test_run_cycle_without_github_token(self, daemon: RevenueScoutDaemon) -> None:
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            result = daemon.run_cycle()
        assert isinstance(result, ScoutCycleResult)
        assert result.duration_seconds >= 0

    def test_ingest_intelligence(self, daemon: RevenueScoutDaemon) -> None:
        result = daemon.ingest_intelligence()
        assert "claims" in result
        assert "patterns" in result
        assert "errors" in result

    def test_draft_outreach_for_qualified(self, daemon: RevenueScoutDaemon) -> None:
        target = RevenueTarget(
            name="test/repo",
            org="test",
            domain="python",
            pain_signals=["no_ci_gates"],
            estimated_value_usd=10000.0,
            status=TargetStatus.QUALIFIED,
            qualification_score=0.8,
        )
        daemon._spine.add_target(target)
        result = daemon.draft_outreach_for_qualified()
        assert result["drafted"] == 1

    def test_draft_skips_existing_drafts(self, daemon: RevenueScoutDaemon) -> None:
        target = RevenueTarget(
            name="test/repo",
            org="test",
            pain_signals=["bot_prs"],
            status=TargetStatus.QUALIFIED,
            qualification_score=0.8,
        )
        daemon._spine.add_target(target)
        daemon.draft_outreach_for_qualified()
        result = daemon.draft_outreach_for_qualified()
        assert result["drafted"] == 0

    def test_persist_result(self, daemon: RevenueScoutDaemon) -> None:
        result = ScoutCycleResult(targets_scouted=3, claims_extracted=5)
        daemon._persist_result(result)
        log = Path.home() / ".dharma" / "revenue_scout" / "cycle_log.jsonl"
        assert log.exists()

    def test_summary(self, daemon: RevenueScoutDaemon) -> None:
        summary = daemon.summary()
        assert "pipeline" in summary
        assert "intelligence" in summary


class TestCronHandler:
    def test_handler_returns_tuple(self) -> None:
        job: dict[str, object] = {
            "id": "revenue_scout",
            "min_qualification_score": 0.5,
            "max_targets_per_cycle": 3,
        }
        success, output, error = revenue_scout_handler(job)
        assert isinstance(success, bool)
        assert isinstance(output, str)
        assert "Revenue Scout Cycle" in output
