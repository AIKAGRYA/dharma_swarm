import json

from scripts.runtime import autonomy_spine


def test_init_writes_mission_task_and_receipt(tmp_path, capsys):
    state_root = tmp_path / "goals"
    code = autonomy_spine.main(
        [
            "init",
            "--goal",
            "Build the composer holon substrate",
            "--mission-id",
            "mission-cli",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mission_id"] == "mission-cli"
    mission_dir = state_root / "mission-cli"
    assert (mission_dir / "mission.json").is_file()
    task = json.loads((mission_dir / "tasks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert task["schema"] == "dharma.autonomy_task.v1"
    assert task["return_address"] == "autonomy://mission-cli/mission-cli-t01"
    receipt = json.loads((mission_dir / "receipts.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert receipt["event"] == "ds_goal_init"
    assert receipt["record_hash"].startswith("sha256:")


def test_status_reports_mission_tasks_and_kernel_status(tmp_path, capsys):
    state_root = tmp_path / "goals"
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Inspect the shared repo truth",
            "--mission-id",
            "mission-status",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
        ]
    ) == 0
    capsys.readouterr()

    code = autonomy_spine.main(
        [
            "status",
            "--mission-id",
            "mission-status",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_count"] == 1
    assert payload["open_task_count"] == 1
    assert payload["latest_wake_status"] == []


def test_status_can_include_board_card_projection(tmp_path, capsys):
    state_root = tmp_path / "goals"
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Expose ds-goal as board cards",
            "--mission-id",
            "mission-board",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
        ]
    ) == 0
    capsys.readouterr()

    code = autonomy_spine.main(
        [
            "status",
            "--mission-id",
            "mission-board",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--board-cards",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["board_cards"][0]["id"] == "dsg_mission-board_mission-board-t01"
    assert payload["board_cards"][0]["render_hints"]["lane_hint"] == "ds_goal"


def test_run_dry_run_records_receipt_without_kernel_wake(tmp_path, capsys):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Dry run the mission",
            "--mission-id",
            "mission-dry",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
        ]
    ) == 0
    capsys.readouterr()

    code = autonomy_spine.main(
        [
            "run",
            "--mission-id",
            "mission-dry",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--dry-run",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert not (kernel_store / "wake_ledger.jsonl").exists()


def test_run_executes_bounded_ds_goal_tick_and_records_closeback(tmp_path, capsys):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Run one bounded ds-goal wake",
            "--mission-id",
            "mission-run",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
        ]
    ) == 0
    capsys.readouterr()

    code = autonomy_spine.main(
        [
            "run",
            "--mission-id",
            "mission-run",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--max-wakes",
            "1",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["tick"]["closebacks"][0]["status"] == "recorded"
    task = json.loads((state_root / "mission-run" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert task["kernel_result_status"] == "completed"
    assert task["kernel_result_ref"]["run_id"]
    assert task["kernel_closeback_via"] == "operator_core.living_agent_kernel.source_closeback"
