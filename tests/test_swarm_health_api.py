"""Tests for dharma_swarm.swarm_health_api — health/metrics HTTP endpoint.

Validates:
- _uptime: format (HH:MM:SS)
- _utc_now: ISO format with timezone
- _read_json: valid/invalid/missing
- _read_lines: tail behavior
- _loop_status: structure and status values
- _provider_status: keys present
- _runtime_dispatch_status: non-secret process dispatch mode
- _telos_summary: no-data and with-data
- _evolution_summary: no-data and with-data
"""

from __future__ import annotations

import json
import http.client
import os
import threading

import pytest

import dharma_swarm.swarm_health_api as health_api


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(health_api, "_STATE_DIR", tmp_path)
    monkeypatch.setenv("DHARMA_EVOLUTION_SHADOW", "1")
    monkeypatch.setenv("DGC_AUTONOMY_LEVEL", "1")


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
# _runtime_dispatch_status
# ---------------------------------------------------------------------------


class TestRuntimeDispatchStatus:
    def test_reports_legacy_when_flag_absent(self, monkeypatch):
        monkeypatch.delenv("DHARMA_SPINE_DISPATCH", raising=False)

        result = health_api._runtime_dispatch_status()

        assert result == {
            "spine_dispatch_enabled": False,
            "dispatch_mode": "legacy",
            "env_key_present": False,
            "source": "process_env_non_secret_boolean",
        }

    def test_reports_spine_when_flag_enabled(self, monkeypatch):
        monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")

        result = health_api._runtime_dispatch_status()

        assert result["spine_dispatch_enabled"] is True
        assert result["dispatch_mode"] == "spine"
        assert result["env_key_present"] is True
        assert set(result) == {
            "spine_dispatch_enabled",
            "dispatch_mode",
            "env_key_present",
            "source",
        }


class TestRuntimeTruthStatus:
    def test_runtime_truth_endpoint_returns_200_when_closeout_passes(self, monkeypatch):
        monkeypatch.setattr(
            health_api,
            "_runtime_truth_status",
            lambda: {
                "schema_version": "runtime_truth_closeout.v1",
                "status": "pass",
                "passed": True,
            },
        )

        status, body = health_api._response_for_path("/runtime-truth")

        assert status == "200 OK"
        assert json.loads(body)["passed"] is True

    def test_runtime_truth_endpoint_returns_503_when_closeout_fails(self, monkeypatch):
        monkeypatch.setattr(
            health_api,
            "_runtime_truth_status",
            lambda: {
                "schema_version": "runtime_truth_closeout.v1",
                "status": "fail",
                "passed": False,
                "checks": [
                    {
                        "id": "provider_model_accounted",
                        "status": "fail",
                        "passed": False,
                    }
                ],
            },
        )

        status, body = health_api._response_for_path("/runtime-truth")

        assert status == "503 Service Unavailable"
        payload = json.loads(body)
        assert payload["passed"] is False
        assert payload["checks"][0]["id"] == "provider_model_accounted"

    def test_metrics_include_runtime_truth(self, monkeypatch):
        monkeypatch.setattr(
            health_api,
            "_runtime_truth_status",
            lambda: {
                "schema_version": "runtime_truth_closeout.v1",
                "status": "pass",
                "passed": True,
            },
        )

        status, body = health_api._response_for_path("/metrics")

        assert status == "200 OK"
        assert json.loads(body)["runtime_truth"]["passed"] is True

    def test_runtime_context_endpoint_returns_orientation_packet(self, monkeypatch):
        monkeypatch.setattr(
            health_api,
            "_runtime_context_packet",
            lambda: {
                "schema": "dharma_swarm.runtime_context.v1",
                "secrets_included": False,
                "provider_routes": {
                    "source": "telemetry_plane.provider_attempts",
                    "recent_success_lanes": ["ollama:qwen3-coder:480b-cloud"],
                },
            },
        )

        status, body = health_api._response_for_path("/runtime-context")

        payload = json.loads(body)
        assert status == "200 OK"
        assert payload["secrets_included"] is False
        assert payload["provider_routes"]["recent_success_lanes"] == [
            "ollama:qwen3-coder:480b-cloud"
        ]


class TestHealthApiThread:
    def test_thread_server_serves_health(self, monkeypatch):
        monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")
        shutdown = threading.Event()
        handle = health_api.start_health_api_thread(
            shutdown,
            host="127.0.0.1",
            port=0,
        )
        try:
            conn = http.client.HTTPConnection(handle.host, handle.port, timeout=2)
            conn.request("GET", "/health")
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            conn.close()
        finally:
            shutdown.set()
            handle.close()

        assert response.status == 200
        assert body["status"] == "ok"
        assert body["runtime_dispatch"]["spine_dispatch_enabled"] is True


class TestHealthApiProcess:
    def test_process_server_serves_pid_bound_health(self, monkeypatch):
        monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")
        handle = health_api.start_health_api_process(
            host="127.0.0.1",
            port=0,
            daemon_pid=os.getpid(),
        )
        try:
            conn = http.client.HTTPConnection(handle.host, handle.port, timeout=5)
            conn.request("GET", "/health")
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            conn.close()
        finally:
            handle.close()

        assert response.status == 200
        assert body["status"] == "ok"
        assert body["daemon_pid"] == os.getpid()
        assert body["daemon_process_alive"] is True
        assert body["health_process_pid"] != os.getpid()
        assert body["runtime_dispatch"]["spine_dispatch_enabled"] is True

    def test_process_server_exits_when_parent_pid_is_dead(self):
        handle = health_api.start_health_api_process(
            host="127.0.0.1",
            port=0,
            daemon_pid=999999999,
        )
        try:
            handle.process.join(timeout=2)
            assert not handle.process.is_alive()
        finally:
            handle.close()


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
