"""Tests for dharma_swarm.scout_report — structured scout output schema.

Validates:
- Finding model construction and defaults
- ScoutReport model, computed properties (critical_count, actionable_count, high_confidence)
- write_report: file creation, latest.json, history.jsonl
- read_latest: round-trip, missing domain
- read_all_latest: multi-domain aggregation
- report_summary: formatted string output
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.scout_report import (
    Finding,
    ScoutReport,
    read_all_latest,
    read_latest,
    report_summary,
    write_report,
)


# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------


class TestFinding:
    def test_defaults(self):
        f = Finding(title="Test finding")
        assert f.severity == "info"
        assert f.category == "observation"
        assert f.confidence == 0.7
        assert f.actionable is False
        assert f.suggested_action is None

    def test_full_construction(self):
        f = Finding(
            title="God object detected",
            severity="high",
            category="improvement",
            description="SwarmManager has 2000 lines",
            file_path="dharma_swarm/swarm.py",
            line_number=42,
            confidence=0.95,
            actionable=True,
            suggested_action="Extract routing logic",
        )
        assert f.title == "God object detected"
        assert f.file_path == "dharma_swarm/swarm.py"
        assert f.line_number == 42

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            Finding(title="bad", confidence=1.5)
        with pytest.raises(Exception):
            Finding(title="bad", confidence=-0.1)


# ---------------------------------------------------------------------------
# ScoutReport model
# ---------------------------------------------------------------------------


class TestScoutReport:
    def _sample_report(self, **kwargs) -> ScoutReport:
        defaults = {
            "domain": "architecture",
            "model": "test-model/v1",
            "findings": [
                Finding(title="F1", severity="critical", actionable=True, confidence=0.9),
                Finding(title="F2", severity="high", actionable=False, confidence=0.6),
                Finding(title="F3", severity="info", actionable=True, confidence=0.85),
            ],
        }
        defaults.update(kwargs)
        return ScoutReport(**defaults)

    def test_critical_count(self):
        report = self._sample_report()
        assert report.critical_count == 1

    def test_actionable_count(self):
        report = self._sample_report()
        assert report.actionable_count == 2

    def test_high_confidence_findings(self):
        report = self._sample_report()
        high_conf = report.high_confidence_findings
        assert len(high_conf) == 2
        assert all(f.confidence >= 0.8 for f in high_conf)

    def test_no_findings(self):
        report = self._sample_report(findings=[])
        assert report.critical_count == 0
        assert report.actionable_count == 0
        assert report.high_confidence_findings == []

    def test_timestamp_auto_set(self):
        report = self._sample_report()
        assert report.timestamp is not None
        assert len(report.timestamp) > 0

    def test_serialization(self):
        report = self._sample_report()
        data = json.loads(report.model_dump_json())
        assert data["domain"] == "architecture"
        assert len(data["findings"]) == 3


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------


class TestWriteReport:
    def test_creates_domain_dir_and_files(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            report = ScoutReport(
                domain="security",
                model="test-model",
                findings=[Finding(title="XSS found", severity="critical")],
            )
            path = write_report(report)

        assert path.exists()
        domain_dir = tmp_path / "security"
        assert domain_dir.exists()
        assert (domain_dir / "latest.json").exists()
        assert (domain_dir / "history.jsonl").exists()

    def test_latest_matches_report(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            report = ScoutReport(
                domain="tests",
                model="test-model",
                findings=[Finding(title="Flaky test", severity="medium")],
            )
            write_report(report)

        latest = json.loads((tmp_path / "tests" / "latest.json").read_text())
        assert latest["domain"] == "tests"
        assert latest["findings"][0]["title"] == "Flaky test"

    def test_history_appends(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            for i in range(3):
                report = ScoutReport(
                    domain="routing",
                    model="test-model",
                    findings=[Finding(title=f"Issue {i}")],
                )
                write_report(report)

        history = (tmp_path / "routing" / "history.jsonl").read_text().strip().splitlines()
        assert len(history) == 3

    def test_report_json_valid(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            report = ScoutReport(
                domain="evolution",
                model="test-model",
                findings=[],
                meta_observations="System evolving well",
            )
            path = write_report(report)

        data = json.loads(path.read_text())
        assert data["meta_observations"] == "System evolving well"


# ---------------------------------------------------------------------------
# read_latest
# ---------------------------------------------------------------------------


class TestReadLatest:
    def test_round_trip(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            original = ScoutReport(
                domain="stigmergy",
                model="test-model",
                findings=[Finding(title="Stale marks", severity="low")],
            )
            write_report(original)
            loaded = read_latest("stigmergy")

        assert loaded is not None
        assert loaded.domain == "stigmergy"
        assert len(loaded.findings) == 1
        assert loaded.findings[0].title == "Stale marks"

    def test_missing_domain_returns_none(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            result = read_latest("nonexistent")
        assert result is None

    def test_corrupt_file_returns_none(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            domain_dir = tmp_path / "corrupt"
            domain_dir.mkdir()
            (domain_dir / "latest.json").write_text("not valid json {{{")
            result = read_latest("corrupt")
        assert result is None


# ---------------------------------------------------------------------------
# read_all_latest
# ---------------------------------------------------------------------------


class TestReadAllLatest:
    def test_multi_domain(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            for domain in ["architecture", "security", "tests"]:
                report = ScoutReport(
                    domain=domain,
                    model="test-model",
                    findings=[Finding(title=f"{domain} finding")],
                )
                write_report(report)
            reports = read_all_latest()

        assert len(reports) == 3
        assert "architecture" in reports
        assert "security" in reports

    def test_empty_dir(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            reports = read_all_latest()
        assert reports == {}

    def test_skips_synthesis_domain(self, tmp_path):
        with patch("dharma_swarm.scout_report.SCOUTS_DIR", tmp_path):
            for domain in ["routing", "synthesis"]:
                domain_dir = tmp_path / domain
                domain_dir.mkdir()
                report = ScoutReport(domain=domain, model="test")
                (domain_dir / "latest.json").write_text(
                    report.model_dump_json(indent=2)
                )
            reports = read_all_latest()

        assert "synthesis" not in reports
        assert "routing" in reports


# ---------------------------------------------------------------------------
# report_summary
# ---------------------------------------------------------------------------


class TestReportSummary:
    def test_ok_status(self):
        report = ScoutReport(
            domain="tests",
            model="gpt-4",
            duration_seconds=12.5,
            findings=[Finding(title="minor", severity="low")],
        )
        summary = report_summary(report)
        assert "[OK]" in summary
        assert "tests" in summary
        assert "gpt-4" in summary

    def test_critical_status(self):
        report = ScoutReport(
            domain="security",
            model="claude",
            findings=[Finding(title="vuln", severity="critical")],
        )
        summary = report_summary(report)
        assert "[CRITICAL]" in summary
        assert "1 critical" in summary
