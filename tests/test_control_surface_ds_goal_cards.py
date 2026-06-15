import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from api.routers.control_surface import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _write_mission(root: Path) -> None:
    mission_dir = root / "mission-api"
    mission_dir.mkdir(parents=True)
    mission = {
        "schema_version": "dharma.ds_goal_spine.v1",
        "mission_id": "mission-api",
        "goal": "Expose ds-goal cards through the control surface API",
        "created_at": "2026-06-11T06:05:00Z",
    }
    task = {
        "schema": "dharma.autonomy_task.v1",
        "mission_id": "mission-api",
        "task_id": "mission-api-t01",
        "role": "planner",
        "agent_uid": "codex_composer",
        "title": "Publish ds-goal BoardStore cards",
        "status": "claimed",
        "return_address": "autonomy://mission-api/mission-api-t01",
        "receipt_required": True,
        "lease": {"claimed_by": "codex_composer", "claimed_at": "2026-06-11T06:05:01Z"},
    }
    (mission_dir / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
    (mission_dir / "tasks.jsonl").write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")


def test_control_surface_projects_ds_goal_cards(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    _write_mission(tmp_path)
    monkeypatch.setattr(control_surface_router, "_DS_GOAL_STATE_ROOT", tmp_path)

    resp = _client().get("/api/control-surface/ds-goal/cards?mission_id=mission-api")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["card_count"] == 1
    card = body["data"]["cards"][0]
    assert card["id"] == "dsg_mission-api_mission-api-t01"
    assert card["status"] == "claimed"
    assert card["render_hints"]["lane_hint"] == "ds_goal"
    assert card["receipt_refs"][0]["kind"] == "ds_goal_mission"
