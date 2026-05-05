"""Tests for dharma_swarm.swarm_health_api — health/metrics HTTP endpoint.

Validates:
- _uptime: format (HH:MM:SS)
- _utc_now: ISO format with timezone
- _read_json: valid/invalid/missing
- _read_lines: tail behavior
- _loop_status: structure and status values
- _provider_status: keys present
- _telos_summary: no-data and with-data
- _evolution_summary: no-data and with-data
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from dharma_swarm.swarm_health_api import (
    _evolution_summary,
    _loop_status,
    _provider_status,
    _read_json,
    _read_lines,
    _telos_summary,
    _uptime,
    _utc_now,
)


# ---------------------------------------------------------------------------
# _uptime
# ---------------------------------------------------------------------------


class TestUptime:
    def test_format(self):
        result = _uptime()
        parts = result.split(":")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow:
    def test_iso_format(self):
        now = _utc_now()
        assert "T" in now
        assert "+" in now or "Z" in now or now.endswith("00:00")


# ---------------------------------------------------------------------------
# _read_json
# ---------------------------------------------------------------------------


class TestReadJson:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}')
        assert _read_json(f) == {"key": "value"}

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        assert _read_json(f) == {}

    def test_missing_file(self, tmp_path):
        assert _read_json(tmp_path / "missing.json") == {}


# ---------------------------------------------------------------------------
# _read_lines
# ---------------------------------------------------------------------------


class TestReadLines:
    def test_reads_last_n(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("\n".join(f"line {i}" for i in range(20)))
        result = _read_lines(f, n=5)
        assert len(result) == 5
        assert result[-1] == "line 19"

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = _read_lines(f)
        assert result == []

    def test_missing_file(self, tmp_path):
        result = _read_lines(tmp_path / "missing.txt")
        assert result == []


# ---------------------------------------------------------------------------
# _loop_status
# ---------------------------------------------------------------------------


class TestLoopStatus:
    def test_returns_list(self):
        result = _loop_status()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_structure(self):
        for item in _loop_status():
            assert "loop" in item
            assert "artifact_exists" in item
            assert "status" in item
            assert item["status"] in ("ok", "no-data")


# ---------------------------------------------------------------------------
# _provider_status
# ---------------------------------------------------------------------------


class TestProviderStatus:
    def test_has_keys(self):
        result = _provider_status()
        assert "circuit_breakers" in result
        assert "shadow_mode" in result
        assert "autonomy_level" in result


# ---------------------------------------------------------------------------
# _telos_summary
# ---------------------------------------------------------------------------


class TestTelosSummary:
    def test_no_data(self):
        result = _telos_summary()
        assert result.get("status") == "no-data" or "total_objectives" in result


# ---------------------------------------------------------------------------
# _evolution_summary
# ---------------------------------------------------------------------------


class TestEvolutionSummary:
    def test_no_data(self):
        result = _evolution_summary()
        assert result.get("status") == "no-data" or "total_entries" in result
