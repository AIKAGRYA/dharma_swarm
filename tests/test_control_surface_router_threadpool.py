"""Regression tests for control-surface API handler scheduling."""

from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from api.routers import control_surface


def _write_mission(root: Path) -> None:
    mission_dir = root / "mission-threaded"
    mission_dir.mkdir(parents=True)
    mission = {
        "schema_version": "dharma.ds_goal_spine.v1",
        "mission_id": "mission-threaded",
        "goal": "Exercise concurrent ds-goal card projection",
        "created_at": "2026-06-11T07:20:00Z",
    }
    task = {
        "schema": "dharma.autonomy_task.v1",
        "mission_id": "mission-threaded",
        "task_id": "mission-threaded-t01",
        "role": "planner",
        "agent_uid": "codex_composer",
        "title": "Threaded ds-goal card projection",
        "status": "claimed",
        "return_address": "autonomy://mission-threaded/mission-threaded-t01",
        "receipt_required": True,
    }
    (mission_dir / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
    (mission_dir / "tasks.jsonl").write_text(
        json.dumps(task, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_packet(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    packet = {
        "id": "agentops-threaded",
        "base_ref": "HEAD",
        "branch": "chore/agentops-threaded",
        "worktree": "/tmp/agentops-threaded",
        "intent": "Exercise concurrent AgentOps card projection.",
        "gates": [{"name": "threaded", "command": "pytest -q"}],
        "approval": {"before_commit": True, "before_merge": True},
    }
    (root / "agentops-threaded.json").write_text(
        json.dumps(packet, sort_keys=True),
        encoding="utf-8",
    )


def test_blocking_control_surface_handlers_run_in_fastapi_threadpool() -> None:
    handlers = [
        control_surface.control_surface_summary,
        control_surface.control_surface_rows,
        control_surface.control_surface_ds_goal_cards,
        control_surface.control_surface_agentops_cards,
        control_surface.control_surface_a2a_cards,
        control_surface.control_surface_handoff_prompt,
        control_surface.control_surface_row,
    ]

    assert all(not inspect.iscoroutinefunction(handler) for handler in handlers)


def test_control_surface_stream_remains_async() -> None:
    assert inspect.iscoroutinefunction(control_surface.control_surface_stream)


def test_concurrent_card_projection_imports_are_serialized(tmp_path, monkeypatch) -> None:
    mission_root = tmp_path / "ds_goals"
    packet_root = tmp_path / "agentops"
    _write_mission(mission_root)
    _write_packet(packet_root)

    monkeypatch.setattr(control_surface, "_DS_GOAL_STATE_ROOT", mission_root)
    monkeypatch.setattr(control_surface, "_AGENTOPS_WORK_PACKET_ROOT", packet_root)
    monkeypatch.setattr(control_surface, "_DS_GOAL_CARD_LOADER", None)
    monkeypatch.setattr(control_surface, "_AGENTOPS_CARD_LOADER", None)

    with ThreadPoolExecutor(max_workers=2) as executor:
        ds_goal_future = executor.submit(
            control_surface.control_surface_ds_goal_cards,
            "mission-threaded",
        )
        agentops_future = executor.submit(
            control_surface.control_surface_agentops_cards,
            "",
            1,
        )

    ds_goal_body = ds_goal_future.result()
    agentops_body = agentops_future.result()

    assert ds_goal_body["source_errors"] == []
    assert ds_goal_body["data"]["card_count"] == 1
    assert agentops_body["source_errors"] == []
    assert agentops_body["data"]["card_count"] == 1
