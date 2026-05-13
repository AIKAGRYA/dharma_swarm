"""Tests for external zeitgeist and separate internal pressure scanning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.s4.internal_pressure import InternalPressureScanner
from dharma_swarm.zeitgeist import (
    RESEARCH_KEYWORDS,
    THREAT_KEYWORDS,
    ZeitgeistScanner,
    ZeitgeistSignal,
    _parse_llm_signals,
)


def test_signal_serialization_roundtrip() -> None:
    sig = ZeitgeistSignal(
        source="world_zeitgeist",
        category="company",
        title="SubQ-like agent infrastructure signal",
        relevance_score=0.8,
        keywords=["agentic", "startup"],
        metadata={"url": "https://example.com/subq"},
    )

    restored = ZeitgeistSignal.model_validate_json(sig.model_dump_json())

    assert restored.title == sig.title
    assert restored.relevance_score == sig.relevance_score
    assert restored.metadata["url"] == "https://example.com/subq"


def test_keyword_relevance_and_threat_detection() -> None:
    scanner = ZeitgeistScanner()

    text = "A startup release on arxiv shows new agentic benchmark pressure."

    assert scanner.keyword_relevance(text) > 0
    assert {"startup", "release", "arxiv"} <= set(scanner.detect_threats(text))


def test_parse_llm_signal_payload() -> None:
    raw = json.dumps(
        {
            "signals": [
                {
                    "category": "company",
                    "title": "Agent eval pressure is rising",
                    "relevance_score": 0.9,
                    "keywords": ["agentic AI", "governance"],
                    "description": "Frontier agent systems need stronger action gates.",
                    "url": "https://example.com/eval",
                }
            ]
        }
    )

    signals = _parse_llm_signals(raw)

    assert len(signals) == 1
    assert signals[0].source == "llm_scan"
    assert signals[0].category == "company"
    assert signals[0].metadata["url"] == "https://example.com/eval"


@pytest.mark.asyncio
async def test_zeitgeist_reads_external_feeds_only(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta = state_dir / "meta"
    shared = state_dir / "shared"
    meta.mkdir(parents=True)
    shared.mkdir(parents=True)
    (shared / "internal_notes.md").write_text(
        "mechanistic interpretability note should not become external zeitgeist",
        encoding="utf-8",
    )
    (meta / "world_zeitgeist_inbox.jsonl").write_text(
        json.dumps(
            {
                "id": "world-1",
                "source": "world_zeitgeist",
                "category": "company",
                "title": "SubQ launches managed agent runtime",
                "description": "Public launch signal.",
                "relevance_score": 0.82,
                "keywords": ["agentic", "startup"],
                "url": "https://example.com/subq",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    signals = await ZeitgeistScanner(state_dir=state_dir).scan()

    assert [signal.title for signal in signals] == ["SubQ launches managed agent runtime"]
    assert (meta / "zeitgeist.jsonl").exists()
    assert "internal_notes" not in (meta / "zeitgeist.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_zeitgeist_dedupes_existing_recent_signal(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta = state_dir / "meta"
    meta.mkdir(parents=True)
    row = {
        "id": "world-1",
        "source": "world_zeitgeist",
        "category": "company",
        "title": "SubQ launches managed agent runtime",
        "description": "Public launch signal.",
        "relevance_score": 0.82,
        "keywords": ["agentic", "startup"],
        "url": "https://example.com/subq",
    }
    (meta / "world_zeitgeist_inbox.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    scanner = ZeitgeistScanner(state_dir=state_dir)

    await scanner.scan()
    await scanner.scan()

    lines = (meta / "zeitgeist.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_internal_pressure_owns_gate_pressure(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    witness = state_dir / "witness"
    witness.mkdir(parents=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = [
        json.dumps({"outcome": "BLOCKED", "gate": "WITNESS"})
        for _ in range(3)
    ]
    (witness / f"witness_{today}.jsonl").write_text("\n".join(rows), encoding="utf-8")

    signals = await InternalPressureScanner(state_dir=state_dir).scan()

    assert any(signal.category == "threat" for signal in signals)
    pressure = json.loads((state_dir / "meta" / "gate_pressure.json").read_text())
    assert pressure["trust_mode_override"] == "external_strict"


@pytest.mark.asyncio
async def test_internal_pressure_scans_stigmergy_density(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    stigmergy = state_dir / "stigmergy"
    stigmergy.mkdir(parents=True)
    (stigmergy / "marks.jsonl").write_text(
        "\n".join(json.dumps({"mark": i}) for i in range(1001)),
        encoding="utf-8",
    )

    signals = await InternalPressureScanner(state_dir=state_dir).scan()

    assert any("stigmergy" in signal.title.lower() for signal in signals)


def test_constants_nonempty() -> None:
    assert RESEARCH_KEYWORDS
    assert THREAT_KEYWORDS
