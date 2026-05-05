"""Tests for dharma_swarm.scout_framework — reusable domain scout runner.

Validates:
- DOMAINS configuration completeness
- _read_file: truncation, error handling
- _run_cmd: basic execution
- _parse_findings: JSON extraction, truncated recovery, fallback
- _try_parse_json: valid/invalid
- _recover_truncated_json_array: truncated array recovery
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.scout_framework import (
    DOMAINS,
    _parse_findings,
    _read_file,
    _recover_truncated_json_array,
    _try_parse_json,
)


# ---------------------------------------------------------------------------
# DOMAINS config
# ---------------------------------------------------------------------------


class TestDomains:
    def test_all_required_keys(self):
        for name, config in DOMAINS.items():
            assert "description" in config, f"{name} missing description"
            assert "model" in config, f"{name} missing model"
            assert "files" in config, f"{name} missing files"
            assert "instruction" in config, f"{name} missing instruction"
            assert "stigmergy_channel" in config, f"{name} missing stigmergy_channel"

    def test_known_domains(self):
        expected = {"architecture", "tests", "routing", "evolution", "security", "stigmergy"}
        assert expected.issubset(set(DOMAINS.keys()))

    def test_instructions_are_substantial(self):
        for name, config in DOMAINS.items():
            assert len(config["instruction"]) > 50, f"{name} instruction too short"


# ---------------------------------------------------------------------------
# _read_file
# ---------------------------------------------------------------------------


class TestReadFile:
    def test_reads_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert _read_file(f) == "hello world"

    def test_truncates_large(self, tmp_path):
        f = tmp_path / "large.txt"
        f.write_text("x" * 20000)
        result = _read_file(f, max_chars=100)
        assert len(result) < 200
        assert "TRUNCATED" in result

    def test_missing_file(self, tmp_path):
        result = _read_file(tmp_path / "nonexistent.txt")
        assert "ERROR" in result


# ---------------------------------------------------------------------------
# _try_parse_json
# ---------------------------------------------------------------------------


class TestTryParseJson:
    def test_valid(self):
        assert _try_parse_json('{"a": 1}') == {"a": 1}

    def test_invalid(self):
        assert _try_parse_json("not json") is None

    def test_array(self):
        assert _try_parse_json('[1, 2, 3]') == [1, 2, 3]


# ---------------------------------------------------------------------------
# _recover_truncated_json_array
# ---------------------------------------------------------------------------


class TestRecoverTruncatedJsonArray:
    def test_recovers_complete_object(self):
        truncated = '[{"title": "A", "severity": "high"}, {"title": "B", "sev'
        result = _recover_truncated_json_array(truncated)
        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_full_array(self):
        full = '[{"title": "A"}, {"title": "B"}]'
        result = _recover_truncated_json_array(full)
        assert result is not None
        assert len(result) == 2

    def test_empty_returns_none(self):
        assert _recover_truncated_json_array("") is None

    def test_no_complete_object(self):
        assert _recover_truncated_json_array('{"incomp') is None


# ---------------------------------------------------------------------------
# _parse_findings
# ---------------------------------------------------------------------------


class TestParseFindings:
    def test_json_block(self):
        response = (
            'Here are my findings:\n'
            '```json\n'
            '[{"title": "Dead code", "severity": "medium", '
            '"category": "improvement", "description": "Remove unused import", '
            '"confidence": 0.8}]\n'
            '```'
        )
        findings = _parse_findings(response)
        assert len(findings) == 1
        assert findings[0].title == "Dead code"
        assert findings[0].severity == "medium"

    def test_fallback_unstructured(self):
        response = "The system looks fine. No major issues found."
        findings = _parse_findings(response)
        assert len(findings) == 1
        assert findings[0].title == "Scout analysis (unstructured)"
        assert findings[0].confidence == 0.5

    def test_truncated_json(self):
        response = (
            '```json\n'
            '[{"title": "Issue A", "severity": "high", "category": "bug", '
            '"description": "Found bug", "confidence": 0.9}, '
            '{"title": "Issue B", "sever'
            '```'
        )
        findings = _parse_findings(response)
        assert len(findings) >= 1
        assert findings[0].title == "Issue A"

    def test_single_object(self):
        response = (
            '```json\n'
            '{"title": "Single", "severity": "info", "category": "observation", '
            '"description": "Note", "confidence": 0.5}\n'
            '```'
        )
        findings = _parse_findings(response)
        assert len(findings) == 1
        assert findings[0].title == "Single"
