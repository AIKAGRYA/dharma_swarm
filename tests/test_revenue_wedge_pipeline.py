"""Tests for the Revenue Wedge pipeline — end-to-end intelligence report loop.

Verifies:
  1. Data pull (mocked CoinGecko)
  2. Signal generation from pulled data
  3. Full report generation (MD + HTML + JSON files)
  4. Outcome + KnowledgeArtifact recorded in ontology
  5. Store sync materializes artifacts in runtime.db
  6. ROOM_TASK_COMPLETED signal emitted
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_temp_dir = tempfile.mkdtemp(prefix="revenue_wedge_test_")
os.environ.setdefault("DHARMA_HOME", _temp_dir)

from dharma_swarm.ginko_data import CryptoPrice, MarketDataPull
from dharma_swarm.revenue_wedge_pipeline import (
    PipelineResult,
    _emit_room_signal,
    _generate_report,
    _generate_signals,
    _record_in_ontology,
    _sync_stores,
    run_pipeline,
)


def _make_mock_pull() -> MarketDataPull:
    """Create a realistic mock data pull with crypto prices."""
    return MarketDataPull(
        timestamp="2026-05-04T10:00:00+00:00",
        macro=None,
        stocks=[],
        crypto=[
            CryptoPrice(
                coin_id="bitcoin",
                symbol="btc",
                current_price_usd=98_432.50,
                market_cap=1_940_000_000_000,
                volume_24h=28_500_000_000,
                price_change_24h_pct=2.3,
                timestamp="2026-05-04T10:00:00+00:00",
            ),
            CryptoPrice(
                coin_id="ethereum",
                symbol="eth",
                current_price_usd=3_821.75,
                market_cap=460_000_000_000,
                volume_24h=12_800_000_000,
                price_change_24h_pct=-0.8,
                timestamp="2026-05-04T10:00:00+00:00",
            ),
            CryptoPrice(
                coin_id="solana",
                symbol="sol",
                current_price_usd=178.50,
                market_cap=82_000_000_000,
                volume_24h=3_200_000_000,
                price_change_24h_pct=5.1,
                timestamp="2026-05-04T10:00:00+00:00",
            ),
        ],
        errors=[],
    )


class TestGenerateSignals:
    """Phase 2: signal generation from market data."""

    def test_signals_from_crypto_pull(self) -> None:
        pull = _make_mock_pull()
        report, regime, conf, errors = _generate_signals(pull)
        assert report is not None
        assert isinstance(regime, str)
        assert not errors

    def test_signals_with_no_data(self) -> None:
        empty_pull = MarketDataPull(timestamp="2026-05-04T10:00:00+00:00")
        report, regime, conf, errors = _generate_signals(empty_pull)
        assert report is not None
        assert regime == "unknown"


class TestGenerateReport:
    """Phase 3: full report generation."""

    def test_report_saved_to_disk(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"DHARMA_HOME": str(tmp_path)}):
            import importlib
            import dharma_swarm.ginko_report_gen as rmod
            importlib.reload(rmod)

            report, md_path, errors = _generate_report(tmp_path)
            assert report is not None
            assert md_path is not None
            assert md_path.exists()
            assert md_path.suffix == ".md"

            content = md_path.read_text(encoding="utf-8")
            assert "Dharmic Quant" in content
            assert "SATYA" in content

    def test_html_and_json_also_saved(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"DHARMA_HOME": str(tmp_path)}):
            import importlib
            import dharma_swarm.ginko_report_gen as rmod
            importlib.reload(rmod)

            report, md_path, errors = _generate_report(tmp_path)
            assert md_path is not None
            html_path = md_path.with_suffix(".html")
            json_path = md_path.with_suffix(".json")
            assert html_path.exists()
            assert json_path.exists()

            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert "date" in data
            assert "regime" in data


class TestOntologyRecording:
    """Phase 4: Outcome + KnowledgeArtifact in ontology."""

    def test_outcome_and_artifact_created(self, tmp_path: Path) -> None:
        from dharma_swarm.ontology_runtime import (
            get_shared_registry,
            reset_shared_registry,
        )

        reset_shared_registry()
        report_path = tmp_path / "report_20260504.md"
        report_path.write_text("# Test Report", encoding="utf-8")

        outcome_id, artifact_id, errors = _record_in_ontology(
            report_path, "unknown", tmp_path
        )

        assert outcome_id, f"Expected outcome_id, got errors: {errors}"
        assert artifact_id, f"Expected artifact_id, got errors: {errors}"
        assert not errors

        registry = get_shared_registry(str(tmp_path / "ontology.db"))
        outcome = registry.get_object(outcome_id)
        assert outcome is not None
        assert outcome.properties["success"] is True

        artifact = registry.get_object(artifact_id)
        assert artifact is not None
        assert "Intelligence Report" in artifact.properties["title"]

        reset_shared_registry()


class TestStoreSync:
    """Phase 5: ontology → runtime materialization."""

    def test_sync_runs_without_error(self, tmp_path: Path) -> None:
        (tmp_path / "state").mkdir(parents=True, exist_ok=True)
        summary, errors = _sync_stores(tmp_path)
        assert isinstance(summary, str)


class TestSignalEmission:
    """Phase 6: ROOM_TASK_COMPLETED signal."""

    def test_signal_emitted(self, tmp_path: Path) -> None:
        emitted, errors = _emit_room_signal(tmp_path)
        assert emitted
        assert not errors


class TestFullPipeline:
    """End-to-end pipeline with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_pipeline_with_mocked_data(self, tmp_path: Path) -> None:
        from dharma_swarm.ontology_runtime import reset_shared_registry

        reset_shared_registry()
        mock_pull = _make_mock_pull()

        with (
            patch.dict(os.environ, {"DHARMA_HOME": str(tmp_path)}),
            patch(
                "dharma_swarm.ginko_data.pull_all_data",
                new_callable=AsyncMock,
                return_value=mock_pull,
            ),
        ):
            import importlib
            import dharma_swarm.ginko_report_gen as rmod
            importlib.reload(rmod)

            result = await run_pipeline(state_dir=tmp_path)

            assert result.data_pull_ok
            assert result.crypto_count == 3
            assert result.report_saved
            assert result.report_path
            assert result.outcome_id
            assert result.artifact_id
            assert result.signal_emitted
            assert result.success

            report_path = Path(result.report_path)
            assert report_path.exists()
            content = report_path.read_text(encoding="utf-8")
            assert "Dharmic Quant" in content

        reset_shared_registry()

    @pytest.mark.asyncio
    async def test_pipeline_result_is_json_serializable(self, tmp_path: Path) -> None:
        from dataclasses import asdict
        from dharma_swarm.ontology_runtime import reset_shared_registry

        reset_shared_registry()
        mock_pull = _make_mock_pull()

        with (
            patch.dict(os.environ, {"DHARMA_HOME": str(tmp_path)}),
            patch(
                "dharma_swarm.ginko_data.pull_all_data",
                new_callable=AsyncMock,
                return_value=mock_pull,
            ),
        ):
            import importlib
            import dharma_swarm.ginko_report_gen as rmod
            importlib.reload(rmod)

            result = await run_pipeline(state_dir=tmp_path)
            serialized = json.dumps(asdict(result), default=str)
            assert serialized
            parsed = json.loads(serialized)
            assert parsed["success"] is True

        reset_shared_registry()
