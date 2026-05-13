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
        category="company",
        title="Agent infra startup signal",
        relevance_score=0.8,
        keywords=["agentic", "startup"],
        metadata={"url": "https://example.com"},
    )

    restored = ZeitgeistSignal.model_validate_json(sig.model_dump_json())

    assert restored.title == sig.title
    assert restored.metadata["url"] == "https://example.com"


def test_keyword_relevance_and_threat_detection() -> None:
    scanner = ZeitgeistScanner()

    assert scanner.keyword_relevance("agentic benchmark governance startup") > 0
    assert scanner.keyword_relevance("weather breakfast") == 0
    assert {"preprint", "arxiv"} <= set(scanner.detect_threats("arxiv preprint"))


def test_parse_llm_signal_payload() -> None:
    raw = json.dumps(
        {
            "signals": [
                {
                    "category": "benchmark",
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
    assert signals[0].category == "benchmark"
    assert signals[0].metadata["url"] == "https://example.com/eval"


@pytest.mark.asyncio
async def test_zeitgeist_reads_external_feeds_only(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    meta = state_dir / "meta"
    meta.mkdir(parents=True)
    (meta / "world_zeitgeist_inbox.jsonl").write_text(
        json.dumps(
            {
                "id": "sig-1",
                "source": "world_zeitgeist",
                "raw_source": "operator_drop",
                "category": "company",
                "title": "SubQ-like agent infra signal",
                "relevance_score": 0.91,
                "url": "https://example.com/subq",
                "keywords": ["agentic", "startup"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    shared = state_dir / "shared"
    shared.mkdir()
    (shared / "internal.md").write_text("mechanistic interpretability preprint", encoding="utf-8")

    signals = await ZeitgeistScanner(state_dir=state_dir).scan()

    assert [signal.title for signal in signals] == ["SubQ-like agent infra signal"]
    assert signals[0].source == "world_zeitgeist"
    assert (meta / "zeitgeist.jsonl").exists()


@pytest.mark.asyncio
async def test_internal_pressure_owns_gate_pressure(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    witness_dir = state_dir / "witness"
    witness_dir.mkdir(parents=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    lines = [json.dumps({"outcome": "BLOCKED"}) for _ in range(5)]
    lines.extend(json.dumps({"outcome": "PASS"}) for _ in range(2))
    (witness_dir / f"witness_{today}.jsonl").write_text("\n".join(lines), encoding="utf-8")

    signals = await InternalPressureScanner(state_dir=state_dir).scan()

    assert any("gate_block" in signal.keywords for signal in signals)
    pressure = json.loads((state_dir / "meta" / "gate_pressure.json").read_text())
    assert pressure["trust_mode_override"] == "external_strict"


@pytest.mark.asyncio
async def test_internal_pressure_scans_stigmergy_density(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    stig_dir = state_dir / "stigmergy"
    stig_dir.mkdir(parents=True)
    (stig_dir / "marks.jsonl").write_text(
        "\n".join(json.dumps({"mark": idx}) for idx in range(1101)),
        encoding="utf-8",
    )

    signals = await InternalPressureScanner(state_dir=state_dir).scan()

    assert any("stigmergy" in signal.title.lower() for signal in signals)


def test_constants_nonempty() -> None:
    assert len(RESEARCH_KEYWORDS) > 10
    assert len(THREAT_KEYWORDS) > 3
