import asyncio
import json

import pytest

from dharma_swarm.operator_core.runtime_truth import runtime_truth_packets_from_runtime_db
from dharma_swarm.runtime_state import RuntimeStateStore
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


def test_init_rejects_mission_id_that_escapes_state_root(tmp_path, capsys):
    state_root = tmp_path / "goals"

    code = autonomy_spine.main(
        [
            "init",
            "--goal",
            "Bad mission",
            "--mission-id",
            "../escape",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--json",
        ]
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "invalid"
    assert "path separators are not allowed" in payload["error"]
    assert not (tmp_path / "escape").exists()


def test_init_rejects_existing_symlink_mission_dir_that_escapes_state_root(tmp_path, capsys):
    state_root = tmp_path / "goals"
    outside = tmp_path / "outside_target"
    state_root.mkdir()
    outside.mkdir()
    try:
        (state_root / "mission-link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    code = autonomy_spine.main(
        [
            "init",
            "--goal",
            "Bad symlink mission",
            "--mission-id",
            "mission-link",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--json",
        ]
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "invalid"
    assert "resolves outside state root" in payload["error"]
    assert not (outside / "mission.json").exists()


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
    assert payload["runtime_truth_ref"]["mission_id"] == "mission-run"
    assert payload["runtime_truth_ref"]["idempotency_key"]
    assert payload["runtime_truth_ref"]["side_effect_key"] == "ds_goal.run:mission-run:mission-run-t01"
    assert payload["runtime_truth_ref"]["artifact_id"]
    task = json.loads((state_root / "mission-run" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert task["kernel_result_status"] == "completed"
    assert task["kernel_result_ref"]["run_id"]
    assert task["kernel_closeback_via"] == "operator_core.living_agent_kernel.source_closeback"
    runtime_db = state_root / ".runtime" / "runtime.db"
    packets = runtime_truth_packets_from_runtime_db(runtime_db, observed_at="2026-06-11T09:10:00Z")
    latest = next(packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt")
    assert latest.mission_id == "mission-run"
    assert latest.metadata["idempotency_record_ref"].startswith("idempotency_records:")
    assert latest.artifact_refs
    assert "mission_id" not in latest.missing_machine_fields
    assert "idempotency_record" not in latest.missing_machine_fields
    assert "artifact_refs" not in latest.missing_machine_fields

    store = RuntimeStateStore(runtime_db)
    runtime_receipts = asyncio.run(store.list_runtime_receipts(receipt_type="delegation_run"))
    runtime_receipt = next(
        receipt
        for receipt in runtime_receipts
        if receipt.receipt_id == payload["runtime_truth_ref"]["receipt_id"]
    )
    evidence_ref = payload["runtime_truth_ref"]["spine_evidence_receipt_ref"]
    evidence = runtime_receipt.payload["spine_evidence_receipt"]
    assert evidence_ref["operation"] == "ds_goal.kernel_wake"
    assert runtime_receipt.payload["spine_evidence_receipt_ref"] == evidence_ref
    assert evidence["receipt_id"] == evidence_ref["receipt_id"]
    assert evidence["operation"] == "ds_goal.kernel_wake"
    assert evidence["status"] == "ok"
    assert evidence["trace_id"] == runtime_receipt.trace_id
    assert evidence["span_id"] == runtime_receipt.run_id
    assert evidence["attributes"]["mission_id"] == "mission-run"
    assert evidence["attributes"]["correlation_id"] == runtime_receipt.correlation_id
    assert evidence["attributes"]["idempotency_key"] == runtime_receipt.idempotency_key
    assert evidence["attributes"]["side_effect_key"] == runtime_receipt.side_effect_key

    dispatch_evidence = asyncio.run(store.list_runtime_receipts(receipt_type="dispatch_evidence"))
    assert dispatch_evidence == []


def test_run_runtime_warrant_denial_blocks_kernel_dispatch(tmp_path, capsys, monkeypatch):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Block unpermitted kernel wake",
            "--mission-id",
            "mission-warrant",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
        ]
    ) == 0
    capsys.readouterr()

    def deny_warrant(runtime_dispatch):
        return autonomy_spine.issue_runtime_warrant(
            store=runtime_dispatch["store"],
            identity=runtime_dispatch["identity"],
            surface="scripts/runtime/autonomy_spine.py",
            action="kernel_wake",
            side_effect_key=runtime_dispatch["side_effect_key"],
            idempotency_inserted=runtime_dispatch["idempotency_inserted"],
            requested_claims=("completed",),
            metadata={"denial_source": "hostile_test"},
        )

    monkeypatch.setattr(autonomy_spine, "_issue_runtime_warrant_for_kernel_wake", deny_warrant)

    code = autonomy_spine.main(
        [
            "run",
            "--mission-id",
            "mission-warrant",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--json",
        ]
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "warrant_denied"
    assert payload["runtime_truth_ref"]["idempotency_inserted"] is True
    warrant_ref = payload["runtime_truth_ref"]["runtime_warrant_ref"]
    assert warrant_ref["status"] == "blocked"
    assert warrant_ref["blocked_claims"] == ["completed"]

    runtime_ref = payload["runtime_truth_ref"]
    store = RuntimeStateStore(runtime_ref["runtime_db"])
    record = store.get_idempotency_record_sync(
        runtime_ref["idempotency_key"], runtime_ref["side_effect_key"]
    )
    assert record is not None
    assert record.status == "failed"
    assert record.result_receipt_id == warrant_ref["receipt_id"]
    assert record.metadata["runtime_warrant_ref"]["status"] == "blocked"
    warrant_receipts = asyncio.run(
        store.list_runtime_receipts(receipt_type="runtime_warrant")
    )
    denied_receipt = next(
        receipt
        for receipt in warrant_receipts
        if receipt.receipt_id == warrant_ref["receipt_id"]
    )
    assert denied_receipt.status == "blocked"
    assert not (kernel_store / "wake_ledger.jsonl").exists()


def test_run_skips_kernel_dispatch_when_idempotency_claim_exists(tmp_path, capsys):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    mission_id = "mission-duplicate"
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Prevent duplicate dispatch",
            "--mission-id",
            mission_id,
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
        ]
    ) == 0
    capsys.readouterr()

    args = autonomy_spine.build_parser().parse_args(
        [
            "run",
            "--mission-id",
            mission_id,
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--json",
        ]
    )
    task = json.loads((state_root / mission_id / "tasks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    preclaim = autonomy_spine._begin_runtime_truth_for_dispatch(  # noqa: SLF001
        args=args,
        task=task,
        wake_id="dsgoal-mission-duplicate-preclaim",
    )
    assert preclaim["idempotency_inserted"] is True

    code = autonomy_spine.main(
        [
            "run",
            "--mission-id",
            mission_id,
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "duplicate"
    assert payload["runtime_truth_ref"]["idempotency_inserted"] is False
    assert not (kernel_store / "wake_ledger.jsonl").exists()
