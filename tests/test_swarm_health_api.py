"""Tests for dharma_swarm.swarm_health_api — health/metrics HTTP endpoint.

Validates:
- _bind_host: fail-closed loopback default and explicit override
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

import asyncio
import json
from pathlib import Path

import pytest
import yaml

import dharma_swarm.swarm_health_api as health_api


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(health_api, "_STATE_DIR", tmp_path)
    monkeypatch.setenv("DHARMA_EVOLUTION_SHADOW", "1")
    monkeypatch.setenv("DGC_AUTONOMY_LEVEL", "1")


# ---------------------------------------------------------------------------
# _bind_host
# ---------------------------------------------------------------------------


class TestBindHost:
    def test_defaults_to_loopback(self, monkeypatch):
        monkeypatch.delenv("DHARMA_API_HOST", raising=False)

        assert health_api._bind_host() == "127.0.0.1"

    def test_blank_value_defaults_to_loopback(self, monkeypatch):
        monkeypatch.setenv("DHARMA_API_HOST", "  ")

        assert health_api._bind_host() == "127.0.0.1"

    def test_honors_explicit_container_override(self, monkeypatch):
        monkeypatch.setenv("DHARMA_API_HOST", "0.0.0.0")

        assert health_api._bind_host() == "0.0.0.0"

    def test_server_uses_loopback_default(self, monkeypatch):
        captured = {}

        class FakeServer:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        async def fake_start_server(handler, host, port):
            captured.update(handler=handler, host=host, port=port)
            return FakeServer()

        async def exercise():
            shutdown_event = asyncio.Event()
            shutdown_event.set()
            await health_api.run_health_api(shutdown_event)

        monkeypatch.delenv("DHARMA_API_HOST", raising=False)
        monkeypatch.setattr(health_api.asyncio, "start_server", fake_start_server)

        asyncio.run(exercise())

        assert captured == {
            "handler": health_api._handle,
            "host": "127.0.0.1",
            "port": health_api._PORT,
        }

    def test_compose_preserves_loopback_host_boundary(self):
        repo_root = Path(__file__).resolve().parents[1]
        compose = yaml.safe_load((repo_root / "docker-compose.yml").read_text())
        swarm = compose["services"]["swarm"]

        assert "127.0.0.1:7433:7433" in swarm["ports"]
        assert swarm["environment"]["DHARMA_API_HOST"] == "0.0.0.0"
        assert swarm["healthcheck"]["test"] == [
            "CMD",
            "curl",
            "-f",
            "http://localhost:7433/health",
        ]

    def test_compose_web_publication_is_loopback_only(self):
        repo_root = Path(__file__).resolve().parents[1]
        compose = yaml.safe_load((repo_root / "docker-compose.yml").read_text())

        assert compose["services"]["web"]["ports"] == ["127.0.0.1:8080:8080"]


# ---------------------------------------------------------------------------
# _uptime
# ---------------------------------------------------------------------------


class TestUptime:
    def test_format(self):
        result = health_api._uptime()
        parts = result.split(":")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow:
    def test_iso_format(self):
        now = health_api._utc_now()
        assert "T" in now
        assert "+" in now or "Z" in now or now.endswith("00:00")


# ---------------------------------------------------------------------------
# _read_json
# ---------------------------------------------------------------------------


class TestReadJson:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}')
        assert health_api._read_json(f) == {"key": "value"}

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        assert health_api._read_json(f) == {}

    def test_missing_file(self, tmp_path):
        assert health_api._read_json(tmp_path / "missing.json") == {}


# ---------------------------------------------------------------------------
# _read_lines
# ---------------------------------------------------------------------------


class TestReadLines:
    def test_reads_last_n(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("\n".join(f"line {i}" for i in range(20)))
        result = health_api._read_lines(f, n=5)
        assert len(result) == 5
        assert result[-1] == "line 19"

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = health_api._read_lines(f)
        assert result == []

    def test_missing_file(self, tmp_path):
        result = health_api._read_lines(tmp_path / "missing.txt")
        assert result == []


# ---------------------------------------------------------------------------
# _loop_status
# ---------------------------------------------------------------------------


class TestLoopStatus:
    def test_returns_list(self):
        result = health_api._loop_status()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_structure(self):
        for item in health_api._loop_status():
            assert "loop" in item
            assert "artifact_exists" in item
            assert "status" in item
            assert item["status"] in ("ok", "no-data")


# ---------------------------------------------------------------------------
# _provider_status
# ---------------------------------------------------------------------------


class TestProviderStatus:
    def test_has_keys(self):
        result = health_api._provider_status()
        assert "circuit_breakers" in result
        assert "shadow_mode" in result
        assert "autonomy_level" in result

    def test_reads_circuit_breakers_from_isolated_state(self):
        meta = health_api._STATE_DIR / "meta"
        meta.mkdir()
        (meta / "circuit_breakers.json").write_text(json.dumps({"open": ["test"]}))

        result = health_api._provider_status()

        assert result["circuit_breakers"] == {"open": ["test"]}
        assert result["shadow_mode"] is True
        assert result["autonomy_level"] == 1


# ---------------------------------------------------------------------------
# _telos_summary
# ---------------------------------------------------------------------------


class TestTelosSummary:
    def test_no_data(self):
        result = health_api._telos_summary()
        assert result == {"status": "no-data"}

    def test_with_data(self):
        telos = health_api._STATE_DIR / "telos"
        telos.mkdir()
        rows = [
            {
                "name": "High priority objective",
                "status": "active",
                "progress": 0.5,
                "priority": 9,
            },
            {
                "name": "Lower priority objective",
                "status": "complete",
                "progress": 1.0,
                "priority": 2,
            },
        ]
        (telos / "objectives.jsonl").write_text("\n".join(json.dumps(row) for row in rows))

        result = health_api._telos_summary()

        assert result["total_objectives"] == 2
        assert result["active"] == 1
        assert result["avg_progress"] == 0.75
        assert result["top_objectives"] == [
            {"name": "High priority objective", "progress": 0.5}
        ]


# ---------------------------------------------------------------------------
# _evolution_summary
# ---------------------------------------------------------------------------


class TestEvolutionSummary:
    def test_no_data(self):
        result = health_api._evolution_summary()
        assert result == {"status": "no-data"}

    def test_with_data(self):
        evolution = health_api._STATE_DIR / "evolution"
        evolution.mkdir()
        rows = [
            {"status": "applied"},
            {"status": "rolled_back"},
            {"status": "applied"},
        ]
        (evolution / "archive.jsonl").write_text("\n".join(json.dumps(row) for row in rows))

        result = health_api._evolution_summary()

        assert result["total_entries"] == 3
        assert result["recent_applied"] == 2
        assert result["recent_rolled_back"] == 1
        assert result["shadow_mode"] is True
