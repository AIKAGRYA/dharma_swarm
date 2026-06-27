from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime import codex_composer_wake_loop as wake


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_context(root: Path) -> None:
    (root / "agents" / "codex_composer").mkdir(parents=True, exist_ok=True)
    (root / "agents" / "codex_composer" / "HOLON_CONTEXT.md").write_text(
        "\n".join(
            [
                "# Codex Composer Holon Context",
                "",
                "Default authority remains read_only_until_execution_lease.",
                "PUBLISH_ACCEPTED is not live collaboration.",
                "The standing wake loop is not ratified.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        root / "agents" / "codex_composer" / "identity.json",
        {
            "agent_uid": "codex_composer",
            "authority_mode": "read_only_until_execution_lease",
            "status": "registered_operator_candidate",
            "wake_loop_active": False,
        },
    )
    _write_json(
        root / "a2a" / "cards" / "codex_composer.json",
        {
            "agent": "codex_composer",
            "metadata": {
                "authority": "external_worker_evidence_only",
                "autonomy_policy": {"can_approve_prs": False, "can_write_source": False},
            },
        },
    )
    _write_json(
        root / "agent_passports" / "codex_composer.json",
        {
            "agent_uid": "codex_composer",
            "authority_mode": "read_only_until_execution_lease",
            "wake_loop_active": False,
            "never_allowed": ["self_approve_execution_lease", "approve_prs"],
        },
    )
    _write_json(
        root / "external_agents" / "codex_composer" / "registration.json",
        {
            "agent_uid": "codex_composer",
            "authority": "external_worker_evidence_only",
            "autonomy_policy": {
                "can_approve_prs": False,
                "can_write_source": False,
                "requires_approval": True,
            },
        },
    )
    _write_json(
        root / "a2a_bus" / "bridge_heartbeats" / "codex_composer.json",
        {
            "agent_uid": "codex_composer",
            "status": "IDLE",
            "subject": "dharma.agent.codex_composer.inbox",
        },
    )
    _write_json(
        root / "a2a_bus" / "state" / "codex_composer.json",
        {
            "agent": "codex_composer",
            "status": "interactive_audit_session_active",
            "wake_loop_active": False,
        },
    )
    _write_json(
        root / "external_agents" / "codex_composer" / "authority" / "passport.json",
        {
            "agent_uid": "codex_composer",
            "status": "scaffolded_not_promoted",
            "capabilities": {
                "allowed": ["write_own_wake_receipts"],
                "gated": ["write_repo_files", "modify_cron_or_launchd"],
                "forbidden": ["approve_prs", "self_promote_authority"],
            },
        },
    )


def _paths(tmp_path: Path) -> wake.ComposerPaths:
    state = tmp_path / ".dharma"
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_context(state)
    return wake.composer_paths(state, repo_root=repo)


def _runner(command: list[str], cwd: Path, timeout_s: float) -> wake.CommandResult:
    if command[:3] == ["git", "status", "--short"]:
        return wake.CommandResult(0, "## main\n", "", 0.01)
    if command[:2] == ["git", "rev-parse"]:
        return wake.CommandResult(0, "abc123\n", "", 0.01)
    return wake.CommandResult(0, '{"orientation":"ok"}\n', "", 0.01)


def test_bootstrap_nest_writes_core_surfaces_and_future_slots(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    status = wake.bootstrap_nest(paths)

    assert status["agent_uid"] == "codex_composer"
    assert (paths.nest / "README.md").exists()
    assert (paths.nest / "COMMANDS.md").exists()
    assert paths.future_orchestration.exists()
    future = json.loads(paths.future_orchestration.read_text())
    assert future["living_dock_projection"].endswith("/agents/codex_composer")
    assert future["external_sandbox"].endswith("/external_agents/codex_composer")
    assert set(future["reserved_slots"]) == {"holocron", "aerie", "landing_dock", "droid_factory"}
    assert future["reserved_slots"]["holocron"].endswith("/nest/holocron")
    assert future["load_policy"]["requires_operator_execution_lease"] is True
    for slot in future["reserved_slots"].values():
        assert Path(slot).exists()
    assert paths.wake_receipts.exists()
    assert paths.action_log.exists()


def test_once_writes_heartbeat_receipt_and_status(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    receipt = wake.run_once(paths, runner=_runner)

    assert receipt["status"] == "completed_read_only_analysis"
    assert receipt["context"]["missing"] == []
    assert receipt["safety"]["repo_write_performed"] is False
    assert paths.heartbeat.exists()
    assert paths.latest_receipt.exists()
    assert paths.status.exists()
    heartbeat = json.loads(paths.heartbeat.read_text())
    assert heartbeat["receipt_id"] == receipt["receipt_id"]
    assert heartbeat["wake_loop_active"] is False
    assert wake.count_lines(paths.wake_receipts) == 1


def test_once_blocks_write_capable_work_without_execution_lease(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.task_queue.parent.mkdir(parents=True, exist_ok=True)
    paths.task_queue.write_text(
        json.dumps(
            {
                "id": "task-write",
                "to": "codex_composer",
                "status": "pending",
                "body": "Please edit repo files, commit, and push.",
                "requires_execution_lease": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    receipt = wake.run_once(paths, runner=_runner)
    work = receipt["work"]

    assert receipt["status"] == "blocked_execution_lease_required"
    assert work["accepted_task_claims"] == []
    assert len(work["work_requiring_execution_lease"]) == 1
    assert work["work_requiring_execution_lease"][0]["block_reason"] == "execution_lease_required"
    assert receipt["safety"]["source_mutation_performed"] is False
    assert "completed_read_only_analysis" not in {item.get("status") for item in work["work_requiring_execution_lease"]}


def test_once_distinguishes_observed_claims_blocked_and_publish_only(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.task_queue.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "id": "task-read",
            "to": "codex_composer",
            "status": "pending",
            "body": "Summarize the current inbox state only.",
        },
        {
            "id": "task-publish",
            "to": "codex_composer",
            "status": "pending",
            "body": "Inspect publish ack evidence.",
            "contact_evidence": "PUBLISH_ACCEPTED",
        },
    ]
    paths.task_queue.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    _write_json(
        paths.assigned_inbox / "needs-lease.json",
        {
            "id": "msg-1",
            "subject": "Start a tmux daemon",
            "requires_execution_lease": True,
        },
    )

    receipt = wake.run_once(paths, runner=_runner)
    work = receipt["work"]

    assert len(work["observed_messages"]) == 3
    assert {item["claim_scope"] for item in work["accepted_task_claims"]} == {"receipt_only_read_only_analysis"}
    assert len(work["blocked_work"]) == 1
    assert work["publish_acceptance_guard"]["publish_only_count"] == 1
    publish = next(item for item in work["observed_messages"] if item["summary"] == "Inspect publish ack evidence.")
    assert publish["publish_acceptance_only"] is True
    assert publish["live_collaboration_claim"] is False
    assert work["completed_read_only_analysis"][0]["status"] == "completed"


def test_start_requires_activation_lease_and_stop_is_idempotent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    args = type(
        "Args",
        (),
        {
            "activation_lease": "",
            "interval_s": 5.0,
            "orientation_timeout_s": 1.0,
            "max_cycles": 1,
            "skip_orientation_command": True,
            "session": "codex-composer-test",
        },
    )()

    start = wake.start_loop(args, paths)
    stopped = wake.stop_loop("codex-composer-test", paths)

    assert start["status"] == "blocked_activation_lease_required"
    assert start["wake_loop_active"] is False
    assert stopped["ok"] is True
    assert stopped["wake_loop_active"] is False
