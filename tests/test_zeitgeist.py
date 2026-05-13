"""Tests for external-only zeitgeist scanning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.internal_pressure import InternalPressureScanner
from dharma_swarm.zeitgeist import (
    RESEARCH_KEYWORDS,
    THREAT_KEYWORDS,
    ZeitgeistScanner,
    ZeitgeistSignal,
    _parse_llm_signals,
)


class TestZeitgeistSignalModel:
    def test_signal_has_correct_fields(self) -> None:
        sig = ZeitgeistSignal(
            source="operator_drop",
            category="product_company",
            title="SubQ-like agent infra launch",
            metadata={"url": "https://example.test"},
        )
        assert sig.id
        assert sig.source == "operator_drop"
        assert sig.category == "product_company"
        assert sig.relevance_score == 0.0
        assert sig.metadata["url"] == "https://example.test"

    def test_signal_serialization_roundtrip(self) -> None:
        sig = ZeitgeistSignal(
            source="world_scout",
            category="agent_infra",
            title="Long context coding agent",
            relevance_score=0.8,
            keywords=["long context", "agent"],
        )
        restored = ZeitgeistSignal.model_validate_json(sig.model_dump_json())
        assert restored.title == sig.title
        assert restored.keywords == sig.keywords


class TestKeywordRelevance:
    def test_keyword_relevance_high(self) -> None:
        scanner = ZeitgeistScanner()
        text = (
            "A subquadratic long context coding agent uses mechanistic "
            "interpretability evidence for safer workflow automation."
        )
        assert scanner.keyword_relevance(text) >= 0.8

    def test_keyword_relevance_zero(self) -> None:
        scanner = ZeitgeistScanner()
        assert scanner.keyword_relevance("The weather is nice today.") == 0.0

    def test_detect_threats_finds_keywords(self) -> None:
        scanner = ZeitgeistScanner()
        threats = scanner.detect_threats("A preprint on arxiv contradicts our finding.")
        assert {"preprint", "arxiv", "contradicts"} <= set(threats)


class TestLLMSignalParsing:
    def test_parse_llm_signal_payload(self) -> None:
        raw = json.dumps(
            {
                "signals": [
                    {
                        "category": "product_company",
                        "title": "Agent workflow company launches",
                        "relevance_score": 0.9,
                        "keywords": ["agent", "workflow"],
                        "description": "A new outside-world company signal.",
                    }
                ]
            }
        )
        signals = _parse_llm_signals(raw)
        assert len(signals) == 1
        assert signals[0].source == "llm_scan"
        assert signals[0].category == "product_company"
        assert signals[0].relevance_score == 0.9

    def test_parse_cli_transcript_uses_last_json_payload(self) -> None:
        raw = "\n".join(
            [
                "user",
                '{"signals":[{"category":"opportunity","title":"prompt echo"}]}',
                "assistant",
                '{"signals":[{"category":"agent_infra","title":"parsed result","relevance_score":0.7}]}',
            ]
        )
        signals = _parse_llm_signals(raw)
        assert len(signals) == 1
        assert signals[0].category == "agent_infra"
        assert signals[0].title == "parsed result"

    def test_parse_unknown_category_as_world_signal(self) -> None:
        raw = json.dumps(
            {"signals": [{"category": "signal", "title": "Frontier pressure", "relevance_score": 1.5}]}
        )
        signals = _parse_llm_signals(raw)
        assert len(signals) == 1
        assert signals[0].category == "world_signal"
        assert signals[0].relevance_score == 1.0


class TestExternalScan:
    @pytest.mark.asyncio
    async def test_scan_no_external_data(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        scanner = ZeitgeistScanner(state_dir=state_dir)
        signals = await scanner.scan()
        assert signals == []
        assert (state_dir / "meta" / "zeitgeist.md").exists()

    @pytest.mark.asyncio
    async def test_scan_external_world_inbox(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        meta = state_dir / "meta"
        meta.mkdir(parents=True)
        row = {
            "id": "subq-1",
            "source": "operator_drop",
            "category": "product_company",
            "title": "SubQ long context coding agent company",
            "description": "Subquadratic inference and workflow signal.",
            "relevance_score": 0.92,
            "keywords": ["subquadratic", "long context", "agent"],
            "url": "https://example.test/subq",
        }
        (meta / "world_zeitgeist_inbox.jsonl").write_text(json.dumps(row) + "\n")

        signals = await ZeitgeistScanner(state_dir=state_dir).scan()

        assert len(signals) == 1
        assert signals[0].source == "operator_drop"
        assert signals[0].category == "product_company"
        assert signals[0].metadata["url"] == "https://example.test/subq"
        assert "External Zeitgeist" in (meta / "zeitgeist.md").read_text()

    @pytest.mark.asyncio
    async def test_scan_ignores_internal_shared_notes(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        shared = state_dir / "shared"
        shared.mkdir(parents=True)
        (shared / "research_notes.md").write_text(
            "mechanistic interpretability participation ratio self-reference"
        )
        signals = await ZeitgeistScanner(state_dir=state_dir).scan()
        assert signals == []


class TestInternalPressure:
    @pytest.mark.asyncio
    async def test_internal_pressure_handles_shared_notes(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        shared = state_dir / "shared"
        shared.mkdir(parents=True)
        (shared / "research_notes.md").write_text(
            "mechanistic interpretability participation ratio self-reference"
        )
        signals = await InternalPressureScanner(state_dir=state_dir).scan()
        assert len(signals) == 1
        assert signals[0].source == "internal_pressure"
        assert signals[0].category == "methodology"

    @pytest.mark.asyncio
    async def test_internal_pressure_writes_gate_pressure(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".dharma"
        witness = state_dir / "witness"
        witness.mkdir(parents=True)
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        rows = [json.dumps({"outcome": "BLOCKED"}) for _ in range(3)]
        (witness / f"witness_{today}.jsonl").write_text("\n".join(rows))

        signals = await InternalPressureScanner(state_dir=state_dir).scan()

        assert any("gate_block" in signal.keywords for signal in signals)
        pressure = json.loads((state_dir / "meta" / "gate_pressure.json").read_text())
        assert pressure["trust_mode_override"] == "external_strict"


def test_keyword_sets_still_exported() -> None:
    assert "mechanistic interpretability" in RESEARCH_KEYWORDS
    assert "preprint" in THREAT_KEYWORDS
