import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from api.routers.control_surface import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _write_packet(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    packet = {
        "id": "agentops-api",
        "base_ref": "HEAD",
        "branch": "chore/agentops-api",
        "worktree": "/tmp/agentops-api",
        "intent": "Expose AgentOps work packets through the control surface API.",
        "gates": [
            {
                "name": "agentops-card-tests",
                "command": "pytest -q tests/test_control_surface_agentops_cards.py",
            }
        ],
        "approval": {
            "before_commit": True,
            "before_merge": True,
        },
    }
    (root / "agentops-api.json").write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")


def test_control_surface_projects_agentops_cards(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    _write_packet(tmp_path)
    monkeypatch.setattr(control_surface_router, "_AGENTOPS_WORK_PACKET_ROOT", tmp_path)

    resp = _client().get("/api/control-surface/agentops/cards?packet_id=agentops-api")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["card_count"] == 1
    card = body["data"]["cards"][0]
    assert card["id"] == "agop_agentops-api"
    assert card["status"] == "planned"
    assert card["render_hints"]["lane_hint"] == "agentops"
    assert card["receipt_refs"][0]["kind"] == "agentops_work_packet"
    assert card["acceptance_criteria"][0]["verifier"] == (
        "pytest -q tests/test_control_surface_agentops_cards.py"
    )
