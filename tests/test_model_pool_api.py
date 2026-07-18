"""API contract tests for dashboard model-pool routes."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.model_pool import router
from dharma_swarm import key_oracle, model_pool


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _write_status(home: Path) -> None:
    target = home / ".dharma"
    target.mkdir(parents=True, exist_ok=True)
    rows = {
        "claude_code": {"glyph": "✓", "status": "Max plan oauth", "env_var": "SAFE"},
        "codex (openai-pro)": {"glyph": "✓", "status": "oauth present", "env_var": "SAFE"},
        "openai": {"glyph": "✓", "status": "live", "env_var": "SAFE"},
        "ollama_cloud": {"glyph": "✓", "status": "live", "env_var": "SAFE"},
        "openrouter": {"glyph": "✗", "status": "HTTP 404", "http": "404", "env_var": "SAFE"},
    }
    (target / "keys_status.json").write_text(
        json.dumps({"last_test_ts": time.time(), "rows": rows}),
        encoding="utf-8",
    )


def test_top10_status_returns_canonical_floor_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path)
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("DHARMA_MODEL_PROFILE_PATH", str(tmp_path / "profiles.json"))

    response = _client().get("/api/pool/top10/status")

    assert response.status_code == 200
    payload = response.json()
    expected_floor_ids = {entry.id for entry in model_pool.floor_entries()}
    payload_ids = {row["id"] for row in payload}
    assert len(payload) == len(expected_floor_ids)
    assert payload_ids == expected_floor_ids
    assert {"kimi-k3", "glm-5.2"} <= payload_ids
    assert {row["lane"] for row in payload} == {"floor"}
    kimi = next(row for row in payload if row["id"] == "kimi-k2.6")
    assert kimi["available"] is True
    assert kimi["status"] == "live_routable"
    gpt_codex = next(row for row in payload if row["id"] == "gpt-5-codex")
    assert gpt_codex["available"] is False
    assert gpt_codex["unavailable_reason"] == "provider_dead"
    assert "route_statuses" in gpt_codex


def test_model_profile_patch_updates_dashboard_label(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path)
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("DHARMA_MODEL_PROFILE_PATH", str(tmp_path / "profiles.json"))
    client = _client()

    patched = client.patch(
        "/api/pool/models/kimi-k2.6/profile",
        json={"custom_label": "Kimi Floor", "short_name": "Kimi"},
    )
    status = client.get("/api/pool/top10/status")

    assert patched.status_code == 200
    assert patched.json() == {"custom_label": "Kimi Floor", "short_name": "Kimi"}
    kimi = next(row for row in status.json() if row["id"] == "kimi-k2.6")
    assert kimi["ui_label"] == "Kimi Floor"


def test_model_profile_patch_rejects_unknown_model(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DHARMA_MODEL_PROFILE_PATH", str(tmp_path / "profiles.json"))

    response = _client().patch(
        "/api/pool/models/not-a-model/profile",
        json={"custom_label": "Nope", "short_name": "Nope"},
    )

    assert response.status_code == 404


def test_verify_top10_is_not_an_implicit_live_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path)
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("DHARMA_MODEL_PROFILE_PATH", str(tmp_path / "profiles.json"))
    monkeypatch.delenv("DHARMA_LIVE_MODEL_E2E", raising=False)

    response = _client().post("/api/pool/top10/verify")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok_count"] == 0
    assert payload["live_calls_attempted"] is False
    assert payload["skipped_count"] == len(model_pool.floor_entries())
    assert "DHARMA_LIVE_MODEL_E2E=1" in payload["reason"]
