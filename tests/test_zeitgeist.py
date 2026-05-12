"""Tests for dharma_swarm.zeitgeist -- S4 external world intelligence.

Tests the ZeitgeistSignal model, keyword relevance scoring,
threat detection, world-feed scanning, and persistence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.zeitgeist import (
    RESEARCH_KEYWORDS,
    THREAT_KEYWORDS,
    ZeitgeistScanner,
    ZeitgeistSignal,
    _parse_llm_signals,
)
from dharma_swarm.internal_pressure import InternalPressureScanner


# -- Model tests -----------------------------------------------------------


class TestZeitgeistSignalModel:
    def test_signal_has_correct_fields(self) -> None:
        sig = ZeitgeistSignal(
            source="manual",
            category="methodology",
            title="Test signal",
        )
        assert sig.id  # non-empty auto-generated
        assert sig.source == "manual"
        assert sig.category == "methodology"
        assert sig.title == "Test signal"
        assert sig.relevance_score == 0.0
        assert sig.keywords == []
        assert sig.description == ""
        assert sig.timestamp is not None

    def test_signal_serialization_roundtrip(self) -> None:
        sig = ZeitgeistSignal(
            source="world_feed",
            category="threat",
            title="Preprint detected",
            relevance_score=0.8,
            keywords=["preprint", "recursive"],
        )
        raw = sig.model_dump_json()
        restored = ZeitgeistSignal.model_validate_json(raw)
        assert restored.title == sig.title
        assert restored.relevance_score == sig.relevance_score
        assert restored.keywords == sig.keywords


# -- Keyword relevance tests -----------------------------------------------


class TestKeywordRelevance:
    def test_keyword_relevance_high(self) -> None:
        scanner = ZeitgeistScanner()
        text = (
            "mechanistic interpretability of the participation ratio "
            "shows self-reference in the value matrix with contraction "
            "and phase transition patterns"
        )
        score = scanner.keyword_relevance(text)
        assert score >= 0.8

    def test_keyword_relevance_zero(self) -> None:
        scanner = ZeitgeistScanner()
        text = "The weather is nice today and I had eggs for breakfast."
        score = scanner.keyword_relevance(text)
        assert score == 0.0

    def test_keyword_relevance_partial(self) -> None:
        scanner = ZeitgeistScanner()
        text = "A new SAE paper on superposition was released."
        score = scanner.keyword_relevance(text)
        assert 0.0 < score < 1.0


# -- Threat detection tests ------------------------------------------------


class TestDetectThreats:
    def test_detect_threats_finds_keywords(self) -> None:
        scanner = ZeitgeistScanner()
        text = "A preprint on arxiv contradicts our finding."
        threats = scanner.detect_threats(text)
        assert "preprint" in threats
        assert "arxiv" in threats
        assert "contradicts" in threats

    def test_detect_no_threats(self) -> None:
        scanner = ZeitgeistScanner()
        text = "Normal research progress on transformer architecture."
        threats = scanner.detect_threats(text)
        assert threats == []


# -- LLM scan parsing tests -------------------------------------------------


class TestLLMSignalParsing:
    def test_parse_llm_signal_payload(self) -> None:
        raw = json.dumps(
            {
                "signals": [
                    {
                        "category": "threat",
                        "title": "Agent eval pressure is rising",
                        "relevance_score": 0.9,
                        "keywords": ["agentic AI", "governance"],
                        "description": "Frontier agent systems need stronger action gates.",
                    }
                ]
            }
        )

        signals = _parse_llm_signals(raw)

        assert len(signals) == 1
        assert signals[0].source == "world_llm_scan"
        assert signals[0].category == "threat"
        assert signals[0].relevance_score == 0.9

    def test_parse_cli_transcript_uses_last_json_payload(self) -> None:
        raw = "\n".join(
            [
                "user",
                '{"signals":[{"category":"opportunity","title":"prompt echo"}]}',
                "assistant",
                '{"signals":[{"category":"methodology","title":"parsed result","relevance_score":0.7}]}',
            ]
        )

        signals = _parse_llm_signals(raw)

        assert len(signals) == 1
        assert signals[0].category == "methodology"
        assert signals[0].title == "parsed result"

    def test_parse_unknown_category_as_methodology(self) -> None:
        raw = json.dumps(
            {
                "signals": [
                    {
                        "category": "signal",
                        "title": "Governance pressure",
                        "relevance_score": 1.5,
                    }
                ]
            }
        )

        signals = _parse_llm_signals(raw)

        assert len(signals) == 1
        assert signals[0].category == "opportunity"
        assert signals[0].relevance_score == 1.0


# -- World feed scan tests ------------------------------------------------


class TestScanWorldFeeds:
    @pytest.mark.asyncio
    async def test_scan_no_world_data(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        scanner = ZeitgeistScanner(state_dir=state_dir)
        signals = await scanner.scan()
        assert signals == []

    @pytest.mark.asyncio
    async def test_internal_notes_are_not_zeitgeist(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        shared_dir = state_dir / "shared"
        shared_dir.mkdir(parents=True)

        (shared_dir / "research_notes.md").write_text(
            "Found interesting results on mechanistic interpretability "
            "and participation ratio in self-reference experiments."
        )

        scanner = ZeitgeistScanner(state_dir=state_dir)
        signals = await scanner.scan()

        assert signals == []

    @pytest.mark.asyncio
    async def test_scan_world_feed_with_product_signal(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        feed_dir = state_dir / "world_feeds"
        feed_dir.mkdir(parents=True)
        (feed_dir / "ai_products.jsonl").write_text(
            json.dumps(
                {
                    "source": "instagram",
                    "source_url": "https://subq.ai/",
                    "category": "model_release",
                    "title": "SubQ announces subquadratic long-context model",
                    "relevance_score": 0.92,
                    "keywords": ["subquadratic", "long context", "coding agents"],
                    "description": "External product signal.",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        scanner = ZeitgeistScanner(state_dir=state_dir)
        signals = await scanner.scan()

        assert len(signals) == 1
        assert signals[0].source == "instagram"
        assert signals[0].category == "model_release"
        assert signals[0].metadata["source_url"] == "https://subq.ai/"

    @pytest.mark.asyncio
    async def test_internal_stigmergy_is_not_zeitgeist(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        stig_dir = state_dir / "stigmergy"
        stig_dir.mkdir(parents=True)

        lines = [json.dumps({"mark": i}) for i in range(1100)]
        (stig_dir / "marks.jsonl").write_text("\n".join(lines))

        scanner = ZeitgeistScanner(state_dir=state_dir)
        signals = await scanner.scan()

        assert signals == []


# -- Persistence tests -----------------------------------------------------


class TestSaveAndLoad:
    @pytest.mark.asyncio
    async def test_save_creates_files(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        scanner = ZeitgeistScanner(state_dir=state_dir)

        # Manually add a signal
        scanner._signals = [
            ZeitgeistSignal(
                source="manual",
                category="tool_release",
                title="New SAE toolkit",
                relevance_score=0.6,
                keywords=["SAE", "sparse autoencoder"],
            )
        ]
        scanner._save()

        meta_dir = state_dir / "meta"
        assert (meta_dir / "zeitgeist.md").exists()
        assert (meta_dir / "zeitgeist.jsonl").exists()

        md_content = (meta_dir / "zeitgeist.md").read_text()
        assert "tool_release" in md_content
        assert "New SAE toolkit" in md_content

    @pytest.mark.asyncio
    async def test_load_history(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        scanner = ZeitgeistScanner(state_dir=state_dir)

        # Save two signals
        scanner._signals = [
            ZeitgeistSignal(source="manual", category="methodology", title="A"),
            ZeitgeistSignal(source="manual", category="threat", title="B"),
        ]
        scanner._save()

        # Load them back
        loaded = scanner.load_history()
        assert len(loaded) == 2
        assert loaded[0].title == "A"
        assert loaded[1].title == "B"


# -- Constant tests --------------------------------------------------------


class TestConstants:
    def test_research_keywords_nonempty(self) -> None:
        assert len(RESEARCH_KEYWORDS) > 10

    def test_threat_keywords_nonempty(self) -> None:
        assert len(THREAT_KEYWORDS) > 3


# -- Filter property tests -------------------------------------------------


class TestLatestThreats:
    def test_latest_threats_filter(self) -> None:
        scanner = ZeitgeistScanner()
        scanner._signals = [
            ZeitgeistSignal(source="manual", category="threat", title="T1"),
            ZeitgeistSignal(source="manual", category="methodology", title="M1"),
            ZeitgeistSignal(source="manual", category="threat", title="T2"),
        ]
        threats = scanner.latest_threats
        assert len(threats) == 2
        assert all(t.category == "threat" for t in threats)

    def test_latest_threats_empty(self) -> None:
        scanner = ZeitgeistScanner()
        scanner._signals = [
            ZeitgeistSignal(source="manual", category="methodology", title="M1"),
        ]
        threats = scanner.latest_threats
        assert threats == []


# -- S3↔S4 gate pressure feedback tests -----------------------------------


class TestGatePressureFeedback:
    """Test internal pressure gate feedback."""

    @pytest.mark.asyncio
    async def test_high_block_rate_writes_gate_pressure(self, tmp_path: Path) -> None:
        """When witness logs show >=3 BLOCKEDs, internal pressure writes gate_pressure.json."""
        state_dir = tmp_path / ".dharma"
        witness_dir = state_dir / "witness"
        witness_dir.mkdir(parents=True)

        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        log_file = witness_dir / f"witness_{today}.jsonl"

        # Write 5 BLOCKED + 2 PASS outcomes
        lines = []
        for i in range(5):
            lines.append(json.dumps({"outcome": "BLOCKED", "phase": f"t{i}"}))
        for i in range(2):
            lines.append(json.dumps({"outcome": "PASS", "phase": f"p{i}"}))
        log_file.write_text("\n".join(lines))

        scanner = InternalPressureScanner(state_dir=state_dir)
        signals = await scanner.scan()

        # Should have generated a gate_block threat signal
        gate_signals = [s for s in signals if "gate_block" in s.keywords]
        assert len(gate_signals) >= 1

        # Should have written gate_pressure.json
        pressure_file = state_dir / "meta" / "gate_pressure.json"
        assert pressure_file.exists()

        data = json.loads(pressure_file.read_text())
        assert data["trust_mode_override"] == "external_strict"
        assert "expires" in data
        assert data["expires"] > data["set_at"]

    @pytest.mark.asyncio
    async def test_no_blocks_no_pressure_file(self, tmp_path: Path) -> None:
        """When witness logs are clean, no gate_pressure.json is written."""
        state_dir = tmp_path / ".dharma"
        witness_dir = state_dir / "witness"
        witness_dir.mkdir(parents=True)

        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        log_file = witness_dir / f"witness_{today}.jsonl"

        lines = [json.dumps({"outcome": "PASS"}) for _ in range(10)]
        log_file.write_text("\n".join(lines))

        scanner = InternalPressureScanner(state_dir=state_dir)
        await scanner.scan()

        pressure_file = state_dir / "meta" / "gate_pressure.json"
        assert not pressure_file.exists()

    def test_gate_reads_pressure_override(self, tmp_path: Path) -> None:
        """TelosGatekeeper._apply_gate_pressure reads the pressure file."""
        import time
        from dharma_swarm.telos_gates import TelosGatekeeper

        gk = TelosGatekeeper()
        # Write a valid pressure file
        pressure_dir = tmp_path / "meta"
        pressure_dir.mkdir(parents=True)
        pressure_file = pressure_dir / "gate_pressure.json"
        pressure_file.write_text(json.dumps({
            "trust_mode_override": "external_strict",
            "set_at": time.time(),
            "expires": time.time() + 3600,
        }))

        # Monkey-patch the path
        original = TelosGatekeeper._GATE_PRESSURE_PATH
        TelosGatekeeper._GATE_PRESSURE_PATH = pressure_file
        try:
            result = gk._apply_gate_pressure("internal_yolo")
            assert result == "external_strict"
        finally:
            TelosGatekeeper._GATE_PRESSURE_PATH = original

    def test_gate_ignores_expired_pressure(self, tmp_path: Path) -> None:
        """Expired gate_pressure.json does not override trust mode."""
        import time
        from dharma_swarm.telos_gates import TelosGatekeeper

        gk = TelosGatekeeper()
        pressure_dir = tmp_path / "meta"
        pressure_dir.mkdir(parents=True)
        pressure_file = pressure_dir / "gate_pressure.json"
        pressure_file.write_text(json.dumps({
            "trust_mode_override": "external_strict",
            "set_at": time.time() - 7200,
            "expires": time.time() - 3600,  # expired 1 hour ago
        }))

        original = TelosGatekeeper._GATE_PRESSURE_PATH
        TelosGatekeeper._GATE_PRESSURE_PATH = pressure_file
        try:
            result = gk._apply_gate_pressure("internal_yolo")
            assert result == "internal_yolo"  # not overridden
        finally:
            TelosGatekeeper._GATE_PRESSURE_PATH = original

    def test_gate_no_pressure_file_passthrough(self) -> None:
        """When no gate_pressure.json exists, mode passes through unchanged."""
        from dharma_swarm.telos_gates import TelosGatekeeper

        gk = TelosGatekeeper()
        original = TelosGatekeeper._GATE_PRESSURE_PATH
        TelosGatekeeper._GATE_PRESSURE_PATH = Path("/nonexistent/gate_pressure.json")
        try:
            result = gk._apply_gate_pressure("internal_yolo")
            assert result == "internal_yolo"
        finally:
            TelosGatekeeper._GATE_PRESSURE_PATH = original
