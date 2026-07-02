from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import pool as pool_router
from dharma_swarm.model_pool_registry import ModelPoolEntry, ModelPoolSnapshot


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(pool_router.router)
    return TestClient(app)


def test_pool_top10_status_exposes_no_secret_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pool_router, "_PROFILE_PATH", tmp_path / "profiles.json")
    monkeypatch.setattr(pool_router, "_VERIFY_PATH", tmp_path / "verify.json")
    monkeypatch.setattr(
        pool_router,
        "build_model_pool_snapshot",
        lambda refresh_nim=False: ModelPoolSnapshot(
            entries=(
                ModelPoolEntry(
                    provider="openrouter",
                    model="moonshotai/kimi-k2.5",
                    route="runtime_provider",
                    cost_tier="paid_api",
                    lane_role="research_delegate",
                    source="test",
                    availability="live_verified",
                    status="<set:len=73>",
                    power_score=96,
                    context_length=128_000,
                    tags=("reasoning",),
                ),
            ),
            sources=("test",),
        ),
    )

    resp = _client().get("/api/pool/top10/status")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    model = payload["data"][0]
    assert model["provider"] == "openrouter"
    assert model["available"] is True
    assert "API_KEY" not in json.dumps(payload)
    assert "sk-" not in json.dumps(payload)


def test_pool_profile_patch_round_trips_label(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pool_router, "_PROFILE_PATH", tmp_path / "profiles.json")
    monkeypatch.setattr(pool_router, "_VERIFY_PATH", tmp_path / "verify.json")
    monkeypatch.setattr(
        pool_router,
        "build_model_pool_snapshot",
        lambda refresh_nim=False: ModelPoolSnapshot(
            entries=(
                ModelPoolEntry(
                    provider="codex",
                    model="gpt-5.4",
                    route="subscription",
                    cost_tier="subscription",
                    lane_role="primary_driver",
                    source="test",
                    availability="credential_present",
                    power_score=97,
                ),
            ),
            sources=("test",),
        ),
    )
    model_id = _client().get("/api/pool/top10/status").json()["data"][0]["id"]

    resp = _client().patch(
        f"/api/pool/models/{model_id}/profile",
        json={"custom_label": "Codex main", "short_name": "Codex"},
    )

    assert resp.status_code == 200
    assert resp.json()["data"] == {"custom_label": "Codex main", "short_name": "Codex"}
    refreshed = _client().get("/api/pool/top10/status").json()["data"][0]
    assert refreshed["ui_label"] == "Codex main"
