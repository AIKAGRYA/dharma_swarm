import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION


def _client() -> TestClient:
    from api.routers.control_surface import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _write_receipt(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": "semr-api",
        "created_at": "2026-06-11T16:50:00Z",
        "agent_uid": "codex_composer",
        "critic_agent_id": "ollama:glm-5:cloud",
        "model_identity": {"provider": "ollama", "model": "glm-5:cloud"},
        "authored_by_model": True,
        "review_target": "prompt:api",
        "intent_ack": True,
        "capability_match": 0.83,
        "understood_request": True,
        "missing_context": [],
        "verdict": "pass",
        "summary": "API should expose the semantic receipt card.",
        "recommendations": [{"priority": "p1", "action": "keep route read-only"}],
        "acceptance_gates": [{"name": "route", "condition": "200", "met": True}],
        "explicit_disagreement": "",
        "evidence_refs": ["prompt:api"],
        "confidence": 0.81,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": "",
        "failure_reason": "",
        "correlation_id": "corr-api",
        "reply_to": "",
        "model_call_latency_ms": 333,
    }
    (root / "semr-api.json").write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")


def test_control_surface_projects_semantic_receipt_cards(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    _write_receipt(tmp_path)
    monkeypatch.setattr(control_surface_router, "_SEMANTIC_RECEIPT_ROOT", tmp_path)

    resp = _client().get("/api/control-surface/semantic-receipts/cards?model=glm-5:cloud")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["card_count"] == 1
    assert body["data"]["receipt_root"] == str(tmp_path)
    card = body["data"]["cards"][0]
    assert card["id"] == "semr_semr-api"
    assert card["status"] == "review"
    assert card["render_hints"]["lane_hint"] == "semantic_receipts"
    assert "provider: ollama" in card["body"]
    assert card["receipt_refs"][0]["kind"] == "semantic_receipt"


def test_control_surface_reads_live_semantic_receipts_from_runtime_state() -> None:
    import api.routers.control_surface as control_surface_router

    assert control_surface_router._SEMANTIC_RECEIPT_ROOT.is_relative_to(
        control_surface_router._SEMANTIC_RESPONDER_STATE_ROOT
    )
    assert control_surface_router._A2A_DOMAIN_REPLY_RECEIPT_ROOT.is_relative_to(
        control_surface_router._SEMANTIC_RESPONDER_STATE_ROOT
    )
    assert not control_surface_router._SEMANTIC_RECEIPT_ROOT.is_relative_to(
        control_surface_router._REPO_ROOT
    )
