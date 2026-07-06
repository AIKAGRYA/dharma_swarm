from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from dharma_swarm.operator_core.ds_goal_supervisor import (
    run_supervisor_cycle,
    stop_tmux_supervisor,
    tmux_session_running,
)
from scripts.runtime import autonomy_spine


def _pass_ds_goal_preflight() -> dict[str, object]:
    return {
        "schema_version": "dharma.ds_goal_longrun_preflight.v1",
        "read_only": True,
        "passed": True,
        "longrun_start_allowed": True,
        "status": "pass_test_checkout",
        "reason": "test checkout allowed",
        "score_effect": "no_score_movement_preflight_only",
        "audited_checkout": "/Users/dhyana/dharma_swarm",
        "installed_wrapper_path": "/Users/dhyana/.dharma/bin/ds-goal",
        "repo_pin": "/Users/dhyana/dharma_swarm",
        "repo_pin_source": "test",
        "repo_pin_matches_audited_checkout": True,
        "default_target_repo": "/Users/dhyana/dharma_swarm",
        "default_target_matches_audited_checkout": True,
        "safe_current_checkout_invocation": "",
        "operator_convergence_required": False,
    }


def _init_mission(
    tmp_path: Path,
    *,
    mission_id: str,
    allowed_write: str,
    verifier_command: str,
    capsys,
) -> Path:
    state_root = tmp_path / "goals"
    code = autonomy_spine.main(
        [
            "init",
            "--goal",
            "Create a small governed work packet and verify it.",
            "--mission-id",
            mission_id,
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--allowed-write",
            allowed_write,
            "--verifier-command",
            verifier_command,
            "--json",
        ]
    )
    assert code == 0
    capsys.readouterr()
    return state_root


def _task(state_root: Path, mission_id: str) -> dict[str, object]:
    return json.loads((state_root / mission_id / "tasks.jsonl").read_text(encoding="utf-8").splitlines()[0])


def _tasks(state_root: Path, mission_id: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (state_root / mission_id / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_init_compiles_verifier_gated_task_not_session_status_only(tmp_path, capsys):
    receipt = tmp_path / "workspace" / "reports" / "smoke" / "receipt.json"
    state_root = _init_mission(
        tmp_path,
        mission_id="mission-compiled",
        allowed_write=str(receipt.parent),
        verifier_command=f"test -f {receipt} && python -m json.tool {receipt}",
        capsys=capsys,
    )

    task = _task(state_root, "mission-compiled")
    tasks = _tasks(state_root, "mission-compiled")

    assert len(tasks) == 2
    assert task["task_id"] == "mission-compiled-t01"
    assert "ds_goal_write_artifact" in task["requested_tools"]
    assert "ds_goal_run_verifier" in task["requested_tools"]
    assert task["tool_calls"] == [{"name": "session_status", "arguments": {}}]
    assert task["required_artifacts"] == [str(receipt)]
    assert task["stop_conditions"] == ["required_artifacts_exist", "verifier_command_exit_0"]
    assert tasks[1]["task_id"] == "mission-compiled-t02-verifier"
    assert tasks[1]["depends_on"] == ["mission-compiled-t01"]
    assert tasks[1]["actuation_mode"] == "verify_only"


def test_supervisor_writes_allowed_artifact_and_closes_only_after_verifier_pass(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    receipt = workspace / "reports" / "smoke" / "receipt.json"
    state_root = _init_mission(
        tmp_path,
        mission_id="mission-supervisor-pass",
        allowed_write=str(receipt.parent),
        verifier_command=f"test -f {receipt} && python -m json.tool {receipt}",
        capsys=capsys,
    )

    cycle = run_supervisor_cycle(
        state_root=state_root,
        mission_id="mission-supervisor-pass",
        kernel_store=tmp_path / "kernel",
        workspace_root=workspace,
        max_tasks=2,
    )
    tasks = _tasks(state_root, "mission-supervisor-pass")

    assert cycle["status"] == "completed"
    assert receipt.exists()
    assert json.loads(receipt.read_text(encoding="utf-8"))["schema_version"] == "dharma.ds_goal_worker_artifact.v1"
    assert [task["status"] for task in tasks] == ["done", "done"]
    assert [task["kernel_result_status"] for task in tasks] == ["completed", "completed"]
    assert all(task["kernel_closeback_via"] == "operator_core.ds_goal_supervisor" for task in tasks)
    assert all(task["kernel_result_ref"]["kind"] == "ds_goal_supervisor_result" for task in tasks)
    assert all(task["verifier_result"]["status"] == "passed" for task in tasks)


def test_supervisor_blocks_required_artifact_outside_allowed_writes(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    allowed = workspace / "reports" / "allowed"
    forbidden_receipt = workspace / "reports" / "forbidden" / "receipt.json"
    state_root = _init_mission(
        tmp_path,
        mission_id="mission-supervisor-forbidden",
        allowed_write=str(allowed),
        verifier_command=f"test -f {forbidden_receipt}",
        capsys=capsys,
    )

    cycle = run_supervisor_cycle(
        state_root=state_root,
        mission_id="mission-supervisor-forbidden",
        kernel_store=tmp_path / "kernel",
        workspace_root=workspace,
        max_tasks=2,
    )
    tasks = _tasks(state_root, "mission-supervisor-forbidden")
    task = tasks[0]

    assert cycle["status"] == "blocked"
    assert not forbidden_receipt.exists()
    assert task["status"] == "blocked"
    assert task["failure_reason"].startswith("artifact_target_outside_allowed_writes")
    assert task["kernel_result_status"] == "blocked"
    assert tasks[1]["status"] == "claimable"


def test_supervisor_keeps_task_blocked_when_verifier_fails(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    receipt = workspace / "reports" / "smoke" / "receipt.json"
    state_root = _init_mission(
        tmp_path,
        mission_id="mission-supervisor-verifier-fails",
        allowed_write=str(receipt.parent),
        verifier_command=f"test -f {receipt} && false",
        capsys=capsys,
    )

    cycle = run_supervisor_cycle(
        state_root=state_root,
        mission_id="mission-supervisor-verifier-fails",
        kernel_store=tmp_path / "kernel",
        workspace_root=workspace,
        max_tasks=2,
    )
    tasks = _tasks(state_root, "mission-supervisor-verifier-fails")
    task = tasks[0]

    assert cycle["status"] == "blocked"
    assert receipt.exists()
    assert task["status"] == "blocked"
    assert task["failure_reason"] == "verifier_command_failed"
    assert task["verifier_result"]["status"] == "failed"
    assert tasks[1]["status"] == "claimable"


def test_autonomy_run_tmux_uses_supervisor_dispatch_without_kernel_projection(
    tmp_path,
    capsys,
    monkeypatch,
):
    receipt = tmp_path / "workspace" / "reports" / "smoke" / "receipt.json"
    state_root = _init_mission(
        tmp_path,
        mission_id="mission-tmux-dispatch",
        allowed_write=str(receipt.parent),
        verifier_command=f"test -f {receipt}",
        capsys=capsys,
    )
    monkeypatch.setattr(autonomy_spine, "_ds_goal_longrun_preflight_for_receipt", _pass_ds_goal_preflight)

    def fake_start_tmux_supervisor(**kwargs):
        assert kwargs["duration_hours"] == 0.1
        assert kwargs["live_provider_requested"] is False
        return {
            "status": "running",
            "mission_id": kwargs["mission_id"],
            "tmux_session": "ds_goal_test",
            "tmux_session_created": True,
        }

    monkeypatch.setattr(autonomy_spine, "start_tmux_supervisor", fake_start_tmux_supervisor)

    code = autonomy_spine.main(
        [
            "run",
            "--mission-id",
            "mission-tmux-dispatch",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(tmp_path / "kernel"),
            "--duration-hours",
            "0.1",
            "--dispatch-mode",
            "tmux",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "running"
    assert payload["dispatch_mode"] == "tmux"
    assert payload["tmux_supervisor"]["tmux_session_created"] is True
    assert not (tmp_path / "kernel" / "wake_ledger.jsonl").exists()


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is not installed")
def test_dispatch_mode_tmux_creates_real_session(tmp_path, capsys, monkeypatch):
    workspace = tmp_path / "workspace"
    receipt = workspace / "reports" / "smoke" / "receipt.json"
    state_root = _init_mission(
        tmp_path,
        mission_id="mission-real-tmux",
        allowed_write=str(receipt.parent),
        verifier_command=f"sleep 2 && test -f {receipt}",
        capsys=capsys,
    )
    monkeypatch.setattr(autonomy_spine, "_ds_goal_longrun_preflight_for_receipt", _pass_ds_goal_preflight)
    session = f"ds_goal_pytest_{uuid4().hex[:8]}"

    try:
        code = autonomy_spine.main(
            [
                "run",
                "--mission-id",
                "mission-real-tmux",
                "--state-root",
                str(state_root),
                "--kernel-store",
                str(tmp_path / "kernel"),
                "--duration-hours",
                "0.01",
                "--dispatch-mode",
                "tmux",
                "--tmux-session",
                session,
                "--supervisor-interval-seconds",
                "0.1",
                "--json",
            ]
        )
        payload = json.loads(capsys.readouterr().out)

        assert code == 0
        assert payload["status"] == "running"
        assert payload["tmux_supervisor"]["tmux_session_created"] is True
        assert tmux_session_running(session)
    finally:
        stop_tmux_supervisor(state_root=state_root, mission_id="mission-real-tmux", session_name=session)
