from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routers.health as health_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router.router)
    return TestClient(app)


def test_api_health_default_is_fast_liveness_only(monkeypatch):
    def fail_get_deps():  # noqa: ANN202
        raise AssertionError("default liveness must not load monitor dependencies")

    monkeypatch.setattr(health_router, "_get_deps", fail_get_deps)

    response = _client().get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"]["overall_status"] == "healthy"
    assert body["data"]["agent_health"] == []
    assert body["data"]["anomalies"] == []
    assert body["data"]["total_traces"] == 0


def test_api_health_deep_mode_uses_monitor(monkeypatch):
    calls = 0

    class Monitor:
        async def check_health(self):  # noqa: ANN202
            nonlocal calls
            calls += 1
            return SimpleNamespace(
                overall_status="degraded",
                agent_health=[
                    SimpleNamespace(
                        agent_name="alpha",
                        total_actions=7,
                        failures=1,
                        success_rate=6 / 7,
                        last_seen=None,
                        status="degraded",
                    )
                ],
                anomalies=[
                    SimpleNamespace(
                        id="anom-1",
                        detected_at="2026-06-18T00:00:00Z",
                        anomaly_type="agent_silent",
                        severity="medium",
                        description="alpha silent",
                        related_traces=["trace-1"],
                    )
                ],
                total_traces=7,
                traces_last_hour=1,
                failure_rate=1 / 7,
                mean_fitness=None,
            )

    monkeypatch.setattr(health_router, "_get_deps", lambda: (None, None, Monitor()))

    response = _client().get("/api/health?deep=true")

    assert response.status_code == 200
    body = response.json()
    assert calls == 1
    assert body["data"]["overall_status"] == "degraded"
    assert body["data"]["agent_health"][0]["agent_name"] == "alpha"
    assert body["data"]["anomalies"][0]["id"] == "anom-1"
    assert body["data"]["total_traces"] == 7


def test_api_health_runtime_truth_opt_in_marks_degraded_on_failed_closeout(monkeypatch):
    monkeypatch.setattr(
        health_router,
        "_runtime_truth_closeout",
        lambda: {
            "schema_version": "runtime_truth_closeout.v1",
            "status": "fail",
            "passed": False,
            "checks": [
                {
                    "id": "provider_model_accounted",
                    "status": "fail",
                    "passed": False,
                    "evidence": "latest_accounted=98.0",
                }
            ],
        },
    )

    response = _client().get("/api/health?runtime_truth=true")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["overall_status"] == "degraded"
    assert body["data"]["runtime_truth"]["passed"] is False
    assert body["data"]["runtime_truth"]["checks"][0]["id"] == "provider_model_accounted"


def test_api_health_runtime_truth_opt_in_keeps_healthy_on_green_closeout(monkeypatch):
    monkeypatch.setattr(
        health_router,
        "_runtime_truth_closeout",
        lambda: {
            "schema_version": "runtime_truth_closeout.v1",
            "status": "pass",
            "passed": True,
            "checks": [],
        },
    )

    response = _client().get("/api/health?runtime_truth=true")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["overall_status"] == "healthy"
    assert body["data"]["runtime_truth"]["passed"] is True
