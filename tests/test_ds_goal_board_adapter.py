import json

from dharma_swarm.board.adapters.ds_goal_adapter import (
    DsGoalBoardAdapter,
    ds_goal_task_to_card,
    load_ds_goal_cards,
)


def _write_mission(tmp_path, *, result: bool = False):
    mission_dir = tmp_path / "mission-board"
    mission_dir.mkdir()
    mission = {
        "schema_version": "dharma.ds_goal_spine.v1",
        "mission_id": "mission-board",
        "goal": "Make the A2A substrate visible as cards",
        "title": "A2A substrate board projection",
        "created_at": "2026-06-11T06:00:00Z",
    }
    task = {
        "schema": "dharma.autonomy_task.v1",
        "mission_id": "mission-board",
        "task_id": "mission-board-t01",
        "role": "builder",
        "agent_uid": "codex_composer",
        "title": "Project ds-goal task into BoardStore card",
        "status": "claimed",
        "return_address": "autonomy://mission-board/mission-board-t01",
        "verifier_command": "pytest -q tests/test_ds_goal_board_adapter.py",
        "receipt_required": True,
        "lease": {"claimed_by": "codex_composer", "claimed_at": "2026-06-11T06:01:00Z"},
    }
    if result:
        task["kernel_result_status"] = "completed"
        task["kernel_closeback_at"] = "2026-06-11T06:02:00Z"
        task["kernel_result_ref"] = {
            "run_id": "kernel_run_board",
            "status": "completed",
            "proof_entry_hash": "sha256:proof",
        }
    (mission_dir / "mission.json").write_text(json.dumps(mission), encoding="utf-8")
    (mission_dir / "tasks.jsonl").write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")
    return mission_dir, mission, task


def test_ds_goal_task_to_card_preserves_identity_receipts_and_acceptance(tmp_path):
    mission_dir, mission, task = _write_mission(tmp_path)

    card = ds_goal_task_to_card(task, mission=mission, mission_dir=mission_dir)

    assert card.id == "dsg_mission-board_mission-board-t01"
    assert card.parent_objective == "dsg_mission-board"
    assert card.status == "claimed"
    assert card.assignee_kind == "codex"
    assert card.source_surface == "cli"
    assert card.render_hints.lane_hint == "ds_goal"
    assert card.acceptance_criteria[0].verifier == "pytest -q tests/test_ds_goal_board_adapter.py"
    assert {ref.kind for ref in card.receipt_refs} == {"ds_goal_mission", "ds_goal_tasks"}


def test_ds_goal_task_to_card_maps_kernel_closeback_to_done_with_result_ref(tmp_path):
    mission_dir, mission, task = _write_mission(tmp_path, result=True)

    card = ds_goal_task_to_card(task, mission=mission, mission_dir=mission_dir)

    assert card.status == "done"
    assert card.arjuna_weight == 0.25
    assert card.acceptance_criteria[1].evidence_ref == "kernel_run_board"
    result_refs = [ref for ref in card.receipt_refs if ref.kind == "living_agent_kernel_result"]
    assert len(result_refs) == 1
    assert result_refs[0].uri == "kernel_run_board"
    assert result_refs[0].checksum == "sha256:proof"


def test_ds_goal_task_to_card_requires_kernel_ref_for_done_projection(tmp_path):
    mission_dir, mission, task = _write_mission(tmp_path)
    task["status"] = "done"

    card = ds_goal_task_to_card(task, mission=mission, mission_dir=mission_dir)

    assert card.status == "review"

    task.pop("status")
    task["kernel_result_status"] = "completed"
    card = ds_goal_task_to_card(task, mission=mission, mission_dir=mission_dir)

    assert card.status == "review"


def test_adapter_lists_cards_across_state_root(tmp_path):
    _write_mission(tmp_path)

    cards = DsGoalBoardAdapter(tmp_path).list_cards()

    assert [card.title for card in cards] == ["Project ds-goal task into BoardStore card"]
    assert load_ds_goal_cards(tmp_path, mission_id="mission-board")[0].id == cards[0].id
