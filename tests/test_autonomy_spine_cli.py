import asyncio
import json

import pytest

from dharma_swarm.operator_core.runtime_truth import runtime_truth_packets_from_runtime_db
from dharma_swarm.runtime_state import RuntimeStateStore
from scripts.runtime import autonomy_spine


def _pass_ds_goal_preflight() -> dict[str, object]:
    return {
        "schema_version": "dharma.ds_goal_longrun_preflight.v1",
        "read_only": True,
        "passed": True,
        "longrun_start_allowed": True,
        "status": "pass_explicit_audited_checkout_pin",
        "reason": "test-pinned audited checkout",
        "score_effect": "no_score_movement_preflight_only",
        "audited_checkout": "/Users/dhyana/dharma_swarm",
        "installed_wrapper_path": "/Users/dhyana/.dharma/bin/ds-goal",
        "repo_pin": "/Users/dhyana/dharma_swarm",
        "repo_pin_source": "DHARMA_SWARM_REPO",
        "repo_pin_matches_audited_checkout": True,
        "default_target_repo": "/Users/dhyana/dharma_swarm_main",
        "default_target_resolution_source": (
            "installed_wrapper_dharma_swarm_main_preference"
        ),
        "default_target_matches_audited_checkout": False,
        "safe_current_checkout_invocation": (
            "DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
            "/Users/dhyana/.dharma/bin/ds-goal"
        ),
        "operator_convergence_required": True,
        "current_mitigation": "use_DHARMA_SWARM_REPO_pin_for_each_invocation",
        "forbidden_without_operator_approval": [
            "edit_installed_wrapper",
            "patch_default_target_checkout",
            "start_repo_native_longrun_from_unpinned_ds_goal",
            "declare_75_plus_from_pin_mitigation_only",
        ],
    }


def _blocked_ds_goal_preflight() -> dict[str, object]:
    payload = dict(_pass_ds_goal_preflight())
    payload.update(
        {
            "passed": False,
            "longrun_start_allowed": False,
            "status": "blocked_unpinned_default_target",
            "reason": (
                "installed ds-goal default target does not match the audited "
                "checkout"
            ),
            "repo_pin": "",
            "repo_pin_source": "none",
            "repo_pin_matches_audited_checkout": False,
        }
    )
    return payload


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
    assert payload["task_count"] == 2
    assert payload["open_task_count"] == 2
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


def test_run_blocks_unsafe_ds_goal_preflight_before_runtime_side_effects(
    tmp_path,
    capsys,
    monkeypatch,
):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    monkeypatch.setattr(
        autonomy_spine,
        "_ds_goal_longrun_preflight_for_receipt",
        _blocked_ds_goal_preflight,
    )
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Block unsafe unpinned ds-goal run",
            "--mission-id",
            "mission-preflight-block",
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
            "mission-preflight-block",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--max-wakes",
            "1",
            "--json",
        ]
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "preflight_blocked"
    assert (
        payload["ds_goal_longrun_preflight"]["status"]
        == "blocked_unpinned_default_target"
    )
    assert payload["ds_goal_longrun_preflight"]["longrun_start_allowed"] is False
    assert not (kernel_store / "wake_ledger.jsonl").exists()
    assert not (state_root / ".runtime" / "runtime.db").exists()
    receipts = [
        json.loads(line)
        for line in (
            state_root / "mission-preflight-block" / "receipts.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert receipts[-1]["status"] == "preflight_blocked"
    assert (
        receipts[-1]["ds_goal_longrun_preflight"]["score_effect"]
        == "no_score_movement_preflight_only"
    )


def test_run_executes_bounded_ds_goal_tick_and_records_closeback(
    tmp_path,
    capsys,
    monkeypatch,
):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    monkeypatch.setattr(
        autonomy_spine,
        "_ds_goal_longrun_preflight_for_receipt",
        _pass_ds_goal_preflight,
    )
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
    major_receipts = [
        receipt
        for receipt in asyncio.run(
            store.list_runtime_receipts(
                run_id=payload["runtime_truth_ref"]["run_id"],
                limit=50,
            )
        )
        if receipt.receipt_type in {"task_claim", "delegation_run"}
    ]
    assert major_receipts
    for receipt in major_receipts:
        assert receipt.side_effect_key, receipt.receipt_id
        assert receipt.payload["provider_execution"] is False
        assert (
            receipt.payload["provider_model_truth_source"]
            == "runtime_control.no_provider_execution"
        )
        assert (
            receipt.payload["no_provider_model_reason"]
            == "living_agent_kernel_v1_no_provider_execution"
        )
        preflight = receipt.payload["ds_goal_longrun_preflight"]
        assert preflight["schema_version"] == "dharma.ds_goal_longrun_preflight.v1"
        assert preflight["read_only"] is True
        assert preflight["status"] == "pass_explicit_audited_checkout_pin"
        assert preflight["repo_pin_source"] == "DHARMA_SWARM_REPO"
        assert preflight["score_effect"] == "no_score_movement_preflight_only"
        idem = store.get_idempotency_record_sync(
            receipt.idempotency_key,
            receipt.side_effect_key,
        )
        assert idem is not None, receipt.receipt_id
        assert idem.status == "completed"
        assert idem.result_receipt_id == receipt.receipt_id

    evidence_ref = payload["runtime_truth_ref"]["spine_evidence_receipt_ref"]
    evidence = runtime_receipt.payload["spine_evidence_receipt"]
    assert runtime_receipt.payload["provider_execution"] is False
    assert (
        runtime_receipt.payload["provider_model_truth_source"]
        == "runtime_control.no_provider_execution"
    )
    assert (
        runtime_receipt.payload["no_provider_model_reason"]
        == "living_agent_kernel_v1_no_provider_execution"
    )
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


def test_run_live_provider_executes_promoted_worker_and_records_provider_truth(
    tmp_path,
    capsys,
    monkeypatch,
):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    monkeypatch.setattr(
        autonomy_spine,
        "_ds_goal_longrun_preflight_for_receipt",
        _pass_ds_goal_preflight,
    )
    monkeypatch.setattr(
        autonomy_spine,
        "_resolve_live_provider_config",
        lambda _args: autonomy_spine.RuntimeProviderConfig(
            provider=autonomy_spine.ProviderType.OLLAMA,
            default_model="glm-5:cloud",
            available=True,
            source="test",
        ),
    )

    async def fake_live_worker_cycle(*, args, config, worker_id):
        store = autonomy_spine.KernelRunStore(args.kernel_store)
        wake = next(
            record
            for record in store.latest_wake_records().values()
            if record.status == "queued"
        )
        result_ref = {
            "kind": "kernel_provider_worker_result",
            "provider_execution": True,
            "provider": config.provider.value,
            "model": config.default_model,
            "wake_id": wake.wake_id,
            "run_id": wake.run_id,
            "request_hash": "sha256:test-request",
            "response_hash": "sha256:test-response",
            "provider_worker_receipt_hash": "sha256:test-provider-worker",
        }
        store.complete_external_wake(
            wake,
            status="completed",
            result_ref=result_ref,
            reason="test_provider_worker_terminal_result",
        )
        return autonomy_spine.KernelProviderWorkerCycleResult(
            status="completed",
            worker_id=worker_id,
            agent_uid=args.agent_uid,
            admission={
                "decision": "allowed",
                "agent_uid": args.agent_uid,
                "requested_level": "provider_executor",
                "requested_work_kind": "provider_execution",
            },
            lease_ref={
                "kind": "kernel_external_worker_lease",
                "wake_id": wake.wake_id,
                "run_id": wake.run_id,
                "record_hash": "sha256:test-lease",
                "status": "leased",
            },
            provider_receipt_ref={
                "kind": "kernel_provider_worker_receipt",
                "path": str(args.kernel_store / "provider_worker_results.jsonl"),
                "record_hash": "sha256:test-provider-worker",
            },
            worker_result_ref={
                "kind": "kernel_external_worker_result",
                "path": str(args.kernel_store / "worker_results.jsonl"),
                "record_hash": "sha256:test-worker-result",
                "wake_id": wake.wake_id,
                "run_id": wake.run_id,
            },
            message="live provider worker completed under test",
        )

    monkeypatch.setattr(
        autonomy_spine,
        "_run_live_provider_worker_cycle",
        fake_live_worker_cycle,
    )
    assert autonomy_spine.main(
        [
            "init",
            "--goal",
            "Run one live provider ds-goal wake",
            "--mission-id",
            "mission-live-provider",
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
            "mission-live-provider",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--live-provider",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["live_provider"] is True
    assert payload["provider"] == "ollama"
    assert payload["model"] == "glm-5:cloud"
    assert payload["tick"]["schema_version"] == "dharma.ds_goal_live_provider_tick.v1"
    assert payload["tick"]["closebacks"][0]["result_ref"]["provider_execution"] is True

    task = json.loads(
        (state_root / "mission-live-provider" / "tasks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert task["kernel_result_status"] == "completed"
    assert task["kernel_result_ref"]["provider"] == "ollama"
    assert (
        task["kernel_closeback_via"]
        == "operator_core.living_agent_kernel.provider_worker"
    )

    promotions = [
        json.loads(line)
        for line in (kernel_store / "promotion_receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    promotion = promotions[-1]
    assert promotion["level"] == "provider_executor"
    assert promotion["allowed_sources"] == ["ds_goal"]
    assert promotion["allowed_tools"] == ["provider_complete"]
    assert promotion["evidence_refs"][0]["kind"] == "operator_review"

    store = RuntimeStateStore(state_root / ".runtime" / "runtime.db")
    runtime_receipts = asyncio.run(store.list_runtime_receipts(receipt_type="delegation_run"))
    runtime_receipt = next(
        receipt
        for receipt in runtime_receipts
        if receipt.receipt_id == payload["runtime_truth_ref"]["receipt_id"]
    )
    assert runtime_receipt.payload["provider_execution"] is True
    assert (
        runtime_receipt.payload["provider_model_truth_source"]
        == "runtime_provider.actual_served"
    )
    assert (
        runtime_receipt.payload["provider_execution_truth_source"]
        == "living_agent_kernel_provider_worker"
    )
    assert runtime_receipt.payload["actual_provider"] == "ollama"
    assert runtime_receipt.payload["actual_model"] == "glm-5:cloud"
    assert runtime_receipt.payload["provider"] == "ollama"
    assert runtime_receipt.payload["model"] == "glm-5:cloud"
    assert "no_provider_model_reason" not in runtime_receipt.payload


def test_run_runtime_warrant_denial_blocks_kernel_dispatch(tmp_path, capsys, monkeypatch):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    monkeypatch.setattr(
        autonomy_spine,
        "_ds_goal_longrun_preflight_for_receipt",
        _pass_ds_goal_preflight,
    )
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

    def deny_warrant(*_args, **_kwargs):
        raise autonomy_spine.RuntimeWarrantDenied("blocked by test warrant")

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
    assert not (kernel_store / "wake_ledger.jsonl").exists()


def test_run_skips_kernel_dispatch_when_idempotency_claim_exists(
    tmp_path,
    capsys,
    monkeypatch,
):
    state_root = tmp_path / "goals"
    kernel_store = tmp_path / "kernel"
    mission_id = "mission-duplicate"
    monkeypatch.setattr(
        autonomy_spine,
        "_ds_goal_longrun_preflight_for_receipt",
        _pass_ds_goal_preflight,
    )
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
