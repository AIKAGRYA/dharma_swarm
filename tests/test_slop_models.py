"""Tests for Dharma slop governance contracts."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.slop import (
    DetectorFamily,
    RouterAction,
    SlopFinding,
    SlopLedgerEntry,
    aggregate_probability,
    route_probability,
    score_module,
)


def test_slop_finding_schema_round_trip() -> None:
    finding = SlopFinding(
        tool="vulture",
        detector_family=DetectorFamily.DEAD_CODE,
        issue_type="unused_function",
        path="dharma_swarm/example.py",
        line=42,
        symbol="unused_function",
        confidence=0.91,
        introduced=True,
        evidence="unused function 'unused_function' (91%)",
    )

    restored = SlopFinding.model_validate_json(finding.model_dump_json())

    assert restored.tool == "vulture"
    assert restored.path == "dharma_swarm/example.py"
    assert restored.confidence == 0.91
    assert restored.introduced is True


def test_single_detector_family_cannot_block() -> None:
    probability = aggregate_probability(
        {"structure": 1.0},
        weights={"structure": 1.0},
    )
    decision = route_probability(probability, introduced=True)

    assert probability == 0.49
    assert decision.action == RouterAction.WARN
    assert decision.blocks is False


def test_two_detector_families_can_block_introduced_regression() -> None:
    probability = aggregate_probability(
        {"dead_code": 1.0, "complexity": 1.0},
        weights={"dead_code": 0.35, "complexity": 0.35},
    )
    decision = route_probability(probability, introduced=True)

    assert 0.50 <= probability < 0.80
    assert decision.action == RouterAction.BLOCK_REGRESSION
    assert decision.blocks is True


def test_module_score_uses_max_confidence_per_family() -> None:
    findings = [
        SlopFinding(
            tool="vulture",
            detector_family=DetectorFamily.DEAD_CODE,
            issue_type="unused_function",
            path="dharma_swarm/example.py",
            confidence=0.40,
        ),
        SlopFinding(
            tool="coverage",
            detector_family=DetectorFamily.DEAD_CODE,
            issue_type="uncovered_symbol",
            path="dharma_swarm/example.py",
            confidence=0.82,
        ),
        SlopFinding(
            tool="radon",
            detector_family=DetectorFamily.COMPLEXITY,
            issue_type="complex_function",
            path="dharma_swarm/example.py",
            confidence=0.70,
        ),
    ]

    score = score_module("dharma_swarm/example.py", findings)

    assert score.family_scores == {"dead_code": 0.82, "complexity": 0.70}
    assert score.slop_probability > 0.0
    assert len(score.findings) == 3


def test_ledger_entry_json_is_machine_readable(tmp_path: Path) -> None:
    finding = SlopFinding(
        tool="bandit",
        detector_family=DetectorFamily.SECURITY,
        issue_type="shell_injection",
        path="dharma_swarm/example.py",
        severity="high",
        confidence=0.80,
    )
    score = score_module("dharma_swarm/example.py", [finding])
    entry = SlopLedgerEntry(
        module=score,
        decision=route_probability(score.slop_probability, introduced=False),
    )
    path = tmp_path / "ledger.jsonl"
    path.write_text(entry.model_dump_json() + "\n", encoding="utf-8")

    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["schema_version"] == 1
    assert row["module"]["path"] == "dharma_swarm/example.py"
    assert row["decision"]["action"] in {"log", "warn", "block_regression"}
