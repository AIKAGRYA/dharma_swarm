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


def test_signal_serialization_roundtrip() -> None:
    sig = ZeitgeistSignal(
        source="world_scout",
        category="agent_infra",
        title="Long context coding agent",
        relevance_score=0.8,
        keywords=["long context", "agent"],
        metadata={"url": "https://example.test"},
    )
    restored = ZeitgeistSignal.model_validate_json(sig.model_dump_json())
    assert restored.title == sig.title
    assert restored.metadata["url"] == "https://example.test"


def test_keyword_helpers_remain_available() -> None:
    scanner = ZeitgeistScanner()
    assert scanner.keyword_relevance("subquadratic long context coding agent") > 0
    threats = scanner.detect_threats("A preprint on arxiv contradicts our result.")
    assert {"preprint", "arxiv", "contradicts"} <= set(threats)
    assert "mechanistic interpretability" in RESEARCH_KEYWORDS
    assert "preprint" in THREAT_KEYWORDS


def test_parse_llm_unknown_category_as_world_signal() -> None:
    signals = _parse_llm_signals(
        json.dumps({"signals": [{"category": "signal", "title": "Frontier move", "relevance_score": 1.5}]})
    )
    assert len(signals) == 1
    assert signals[0].category == "world_signal"
    assert signals[0].relevance_score == 1.0


@pytest.mark.asyncio
async def test_scan_external_world_inbox(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    row = {
        "id": "subq-1",
        "source": "operator_drop",
        "category": "agent_infra",
        "title": "SubQ long context coding agent company",
        "description": "Subquadratic inference workflow for AI agents.",
        "relevance_score": 0.92,
        "keywords": ["subquadratic", "long context", "agent"],
        "url": "https://example.test/subq",
    }
    (meta / "world_zeitgeist_inbox.jsonl").write_text(json.dumps(row) + "\n")

    signals = await ZeitgeistScanner(state_dir=state).scan()

    assert len(signals) == 1
    assert signals[0].source == "operator_drop"
    assert signals[0].metadata["url"] == "https://example.test/subq"
    assert "External Zeitgeist" in (meta / "zeitgeist.md").read_text()


@pytest.mark.asyncio
async def test_scan_ignores_internal_shared_notes(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    shared = state / "shared"
    shared.mkdir(parents=True)
    (shared / "research_notes.md").write_text(
        "mechanistic interpretability participation ratio self-reference"
    )
    assert await ZeitgeistScanner(state_dir=state).scan() == []


@pytest.mark.asyncio
async def test_internal_pressure_writes_gate_pressure(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    witness = state / "witness"
    witness.mkdir(parents=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = [json.dumps({"outcome": "BLOCKED"}) for _ in range(3)]
    (witness / f"witness_{today}.jsonl").write_text("\n".join(rows))

    signals = await InternalPressureScanner(state_dir=state).scan()

    assert any("gate_block" in signal.keywords for signal in signals)
    pressure = json.loads((state / "meta" / "gate_pressure.json").read_text())
    assert pressure["trust_mode_override"] == "external_strict"
