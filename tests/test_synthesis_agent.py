"""Tests for dharma_swarm.synthesis_agent — Tier 2 scout synthesis.

Validates:
- _utc_now: formatted timestamp
- _date_stamp: date format
- _build_cross_reference: convergence detection, severity counting,
  thin domains, scout quality grading
- _build_synthesis_prompt: prompt assembly
"""

from __future__ import annotations

import pytest

from dharma_swarm.scout_report import Finding, ScoutReport
from dharma_swarm.synthesis_agent import (
    _build_cross_reference,
    _build_synthesis_prompt,
    _date_stamp,
    _utc_now,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_utc_now_format(self):
        result = _utc_now()
        assert "UTC" in result

    def test_date_stamp_format(self):
        result = _date_stamp()
        assert "_" in result
        assert len(result) >= 13  # YYYY-MM-DD_HHMM


# ---------------------------------------------------------------------------
# _build_cross_reference
# ---------------------------------------------------------------------------


def _make_report(
    domain: str,
    findings: list[Finding] | None = None,
) -> ScoutReport:
    return ScoutReport(
        domain=domain,
        model="test-model",
        duration_seconds=1.0,
        findings=findings or [],
    )


def _make_finding(
    title: str = "Test",
    severity: str = "medium",
    file_path: str = "",
    actionable: bool = True,
    confidence: float = 0.8,
) -> Finding:
    return Finding(
        title=title,
        severity=severity,
        category="observation",
        description="Test finding",
        file_path=file_path,
        actionable=actionable,
        confidence=confidence,
    )


class TestBuildCrossReference:
    def test_basic(self):
        reports = {
            "architecture": _make_report("architecture", [
                _make_finding("God object", severity="high", file_path="dharma_swarm/swarm.py"),
            ]),
            "tests": _make_report("tests", [
                _make_finding("Missing tests", severity="medium", file_path="dharma_swarm/swarm.py"),
            ]),
        }
        xref = _build_cross_reference(reports)
        assert xref["total_findings"] == 2
        assert xref["severity_counts"]["high"] == 1
        assert xref["severity_counts"]["medium"] == 1
        # swarm.py mentioned by both scouts
        assert "dharma_swarm/swarm.py" in xref["convergence_files"]
        assert len(xref["convergence_files"]["dharma_swarm/swarm.py"]) == 2

    def test_thin_domains(self):
        reports = {
            "security": _make_report("security", [
                _make_finding("Info only", actionable=False),
            ]),
        }
        xref = _build_cross_reference(reports)
        assert "security" in xref["thin_domains"]

    def test_scout_quality(self):
        reports = {
            "arch": _make_report("arch", [
                _make_finding("Structured", confidence=0.9),
            ]),
        }
        xref = _build_cross_reference(reports)
        assert "arch" in xref["scout_quality"]
        assert xref["scout_quality"]["arch"]["total_findings"] == 1
        assert xref["scout_quality"]["arch"]["parse_quality"] == "good"

    def test_unstructured_parse_quality(self):
        reports = {
            "routing": _make_report("routing", [
                Finding(
                    title="Scout analysis (unstructured)",
                    severity="info",
                    category="observation",
                    description="Free text",
                    confidence=0.5,
                ),
            ]),
        }
        xref = _build_cross_reference(reports)
        assert xref["scout_quality"]["routing"]["parse_quality"] == "failed"

    def test_no_convergence(self):
        reports = {
            "a": _make_report("a", [
                _make_finding("A", file_path="a.py"),
            ]),
            "b": _make_report("b", [
                _make_finding("B", file_path="b.py"),
            ]),
        }
        xref = _build_cross_reference(reports)
        assert xref["convergence_files"] == {}

    def test_empty_reports(self):
        xref = _build_cross_reference({})
        assert xref["total_findings"] == 0


# ---------------------------------------------------------------------------
# _build_synthesis_prompt
# ---------------------------------------------------------------------------


class TestBuildSynthesisPrompt:
    def test_prompt_contains_domain(self):
        reports = {
            "architecture": _make_report("architecture", [
                _make_finding("Code smell"),
            ]),
        }
        xref = _build_cross_reference(reports)
        prompt = _build_synthesis_prompt(reports, xref)
        assert "ARCHITECTURE" in prompt
        assert "Code smell" in prompt

    def test_prompt_contains_instructions(self):
        reports = {"test": _make_report("test")}
        xref = _build_cross_reference(reports)
        prompt = _build_synthesis_prompt(reports, xref)
        assert "READ BETWEEN THE LINES" in prompt
        assert "PRIORITIZE RUTHLESSLY" in prompt

    def test_prompt_has_actionable_flag(self):
        reports = {
            "sec": _make_report("sec", [
                _make_finding("Vuln", actionable=True),
            ]),
        }
        xref = _build_cross_reference(reports)
        prompt = _build_synthesis_prompt(reports, xref)
        assert "[ACTIONABLE]" in prompt
