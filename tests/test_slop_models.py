"""Tests for unified-schema models."""

from __future__ import annotations

import pytest

from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    ModuleScore,
    Severity,
    SlopLedgerEntry,
)


def f(confidence: float = 0.5) -> Finding:
    return Finding(
        tool="t",
        family=DetectorFamily.AI_SLOP,
        issue_type="x",
        path="a.py",
        line=1,
        symbol=None,
        severity=Severity.MEDIUM,
        confidence=confidence,
        evidence="e",
    )


class TestFinding:
    def test_basic_construction(self) -> None:
        finding = f(0.6)
        assert finding.confidence == 0.6
        assert finding.family is DetectorFamily.AI_SLOP

    def test_confidence_lower_bound(self) -> None:
        with pytest.raises(ValueError):
            f(-0.01)

    def test_confidence_upper_bound(self) -> None:
        with pytest.raises(ValueError):
            f(1.01)

    def test_to_dict_serializes_enums(self) -> None:
        d = f(0.5).to_dict()
        assert d["family"] == "ai_slop"
        assert d["severity"] == "medium"


class TestDetectorResult:
    def test_ok_when_clean_exit_no_error(self) -> None:
        r = DetectorResult(
            tool="t",
            family=DetectorFamily.DEAD_CODE,
            findings=[],
            duration_sec=0.1,
            exit_code=0,
        )
        assert r.ok is True

    def test_not_ok_on_error(self) -> None:
        r = DetectorResult(
            tool="t",
            family=DetectorFamily.DEAD_CODE,
            findings=[],
            duration_sec=0.1,
            exit_code=0,
            error="boom",
        )
        assert r.ok is False

    def test_to_dict_includes_finding_count(self) -> None:
        r = DetectorResult(
            tool="t",
            family=DetectorFamily.AI_SLOP,
            findings=[f(0.4), f(0.6)],
            duration_sec=0.1,
            exit_code=0,
        )
        d = r.to_dict()
        assert d["finding_count"] == 2
        assert len(d["findings"]) == 2


class TestSlopLedgerEntry:
    def test_now_attaches_iso_timestamp(self) -> None:
        score = ModuleScore(
            path="a.py",
            p_raw=0.4,
            p=0.4,
            agreement=1,
            family_scores={"ai_slop": 0.4},
            finding_count=1,
            capped=False,
        )
        e = SlopLedgerEntry.now(mode="ci", score=score, action="pr_warning", findings=[f()])
        assert "T" in e.timestamp
        assert e.mode == "ci"
        assert e.action == "pr_warning"

    def test_jsonl_dict_roundtrip_safe(self) -> None:
        import json

        score = ModuleScore(
            path="a.py",
            p_raw=0.4,
            p=0.4,
            agreement=1,
            family_scores={"ai_slop": 0.4},
            finding_count=1,
            capped=False,
        )
        e = SlopLedgerEntry.now(mode="ci", score=score, action="pr_warning", findings=[f()])
        encoded = json.dumps(e.to_jsonl_dict())
        decoded = json.loads(encoded)
        assert decoded["mode"] == "ci"
        assert decoded["module_score"]["path"] == "a.py"
