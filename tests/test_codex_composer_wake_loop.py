from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.execution_lease import build_execution_lease, write_execution_lease
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


def test_valid_file_backed_execution_lease_is_recognized_for_classification(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    task_id = "lease-backed-local-task"
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=task_id,
        correlation_id="corr-lease-backed-local-task",
        allowed_actions=["read", "write_artifact", "close_task", "publish_domain_reply"],
        allowed_paths=[paths.repo_root / "reports" / "a2a" / "phase_a"],
    )
    write_execution_lease(lease, paths.leases)
    paths.task_queue.parent.mkdir(parents=True, exist_ok=True)
    paths.task_queue.write_text(
        json.dumps(
            {
                "id": task_id,
                "to": "codex_composer",
                "status": "pending",
                "body": "Please write an allowed artifact and close the task.",
                "requires_execution_lease": True,
                "requested_actions": ["write_artifact", "close_task"],
                "execution_lease_id": lease["lease_id"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    receipt = wake.run_once(paths, runner=_runner)
    observed = receipt["work"]["observed_messages"][0]

    assert receipt["status"] == "completed_read_only_analysis"
    assert observed["has_execution_lease"] is True
    assert observed["execution_lease"]["valid"] is True
    assert receipt["work"]["work_requiring_execution_lease"] == []
    assert receipt["safety"]["source_mutation_performed"] is False


def test_execution_lease_does_not_authorize_an_unscoped_requested_action(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    task_id = "scope-mismatch-task"
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=task_id,
        allowed_actions=["read"],
    )
    write_execution_lease(lease, paths.leases)
    record = {
        "trigger_id": task_id,
        "kind": "task",
        "source_path": str(paths.task_queue),
        "summary": "Please write an artifact.",
        "status": "pending",
    }
    payload = {
        "id": task_id,
        "body": "Please write an artifact.",
        "requires_execution_lease": True,
        "requested_actions": ["write_artifact"],
        "execution_lease_id": lease["lease_id"],
    }

    classified = wake.classify_record(
        record,
        payload,
        agent_uid="codex_composer",
        lease_root=paths.leases,
    )

    assert classified["requested_actions"] == ["write_artifact"]
    assert classified["has_execution_lease"] is False
    assert classified["blocked"] is True
    assert any("write_artifact" in error for error in classified["execution_lease"]["errors"])


def test_lease_required_payload_without_typed_action_scope_stays_blocked(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    task_id = "missing-declared-scope-task"
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=task_id,
        allowed_actions=["write_artifact"],
    )
    write_execution_lease(lease, paths.leases)
    record = {
        "trigger_id": task_id,
        "kind": "task",
        "source_path": str(paths.task_queue),
        "summary": "Alter the artifact.",
        "status": "pending",
    }
    payload = {
        "id": task_id,
        "body": "Alter the artifact.",
        "requires_execution_lease": True,
        "execution_lease_id": lease["lease_id"],
    }

    classified = wake.classify_record(
        record,
        payload,
        agent_uid="codex_composer",
        lease_root=paths.leases,
    )

    assert classified["declared_actions"] == []
    assert classified["has_execution_lease"] is False
    assert classified["blocked"] is True
    assert any(
        "must declare non-empty requested_actions" in error
        for error in classified["execution_lease"]["errors"]
    )


def test_execution_lease_enforces_explicit_requested_path(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    task_id = "path-scope-mismatch-task"
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=task_id,
        allowed_actions=["write_artifact"],
        allowed_paths=[paths.repo_root / "allowed"],
    )
    write_execution_lease(lease, paths.leases)
    record = {
        "trigger_id": task_id,
        "kind": "task",
        "source_path": str(paths.task_queue),
        "summary": "Write the requested artifact.",
        "status": "pending",
    }
    payload = {
        "id": task_id,
        "body": "Write the requested artifact.",
        "target_path": str(paths.repo_root / "outside" / "artifact.md"),
        "requires_execution_lease": True,
        "requested_actions": ["write_artifact"],
        "execution_lease_id": lease["lease_id"],
    }

    classified = wake.classify_record(
        record,
        payload,
        agent_uid="codex_composer",
        lease_root=paths.leases,
    )

    assert classified["has_execution_lease"] is False
    assert any("outside lease allowed_paths" in error for error in classified["execution_lease"]["errors"])


def test_inbox_delivery_packet_matches_file_backed_lease_by_packet_id(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    packet_id = "f393c7c5d390"
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=packet_id,
        correlation_id=f"a2a_send:codex_composer:{packet_id}",
        allowed_actions=["read", "write_artifact", "close_task", "publish_domain_reply"],
        allowed_paths=[paths.dharma_home / "a2a_bus" / "operator" / "handoffs"],
    )
    write_execution_lease(lease, paths.leases)
    _write_json(
        paths.assigned_inbox / f"{packet_id}.json",
        {
            "agent_uid": "codex_composer",
            "bridge_kind": "filesystem_delivery_handler",
            "delivered_at": "2026-07-02T13:00:14Z",
            "envelope": {
                "from": "fable_composer",
                "kind": "engineering_spec_commission",
                "packet_id": packet_id,
                "reply_subject": f"dharma.agent.codex_composer.inbox.reply.{packet_id}",
                "target_uid": "codex_composer",
                "content": "Write PHASE_A_ENGINEERING_SPEC.md in the shared handoff directory.",
                "requested_actions": ["write_artifact"],
            },
        },
    )

    receipt = wake.run_once(paths, runner=_runner)
    observed = receipt["work"]["observed_messages"][0]

    assert receipt["status"] == "completed_read_only_analysis"
    assert observed["summary"] == f"{packet_id}.json"
    assert observed["has_execution_lease"] is True
    assert observed["execution_lease"]["valid"] is True
    assert observed["execution_lease"]["matched_by"] == "task_or_correlation_id"
    assert receipt["work"]["work_requiring_execution_lease"] == []


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


@pytest.mark.parametrize("session", ["-L/tmp/socket", "bad:target", "bad session", "../escape"])
def test_tmux_session_rejects_option_and_target_injection(tmp_path: Path, session: str) -> None:
    paths = _paths(tmp_path)
    args = type("Args", (), {"session": session})()

    with pytest.raises(ValueError, match="single safe token"):
        wake._session_for(args, paths)


def test_start_rejects_nonempty_but_unloadable_activation_lease(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    args = type(
        "Args",
        (),
        {
            "activation_lease": "convincing-looking-text",
            "interval_s": 5.0,
            "orientation_timeout_s": 1.0,
            "max_cycles": 1,
            "skip_orientation_command": True,
            "session": "codex-composer-test",
        },
    )()

    start = wake.start_loop(args, paths)

    assert start["status"] == "blocked_activation_lease_invalid"
    assert start["wake_loop_active"] is False
    assert start["activation_lease_validation"]["valid"] is False


def test_activation_lease_must_bind_agent_task_and_start_action(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    wrong_scope = build_execution_lease(
        issued_to="codex_composer",
        task_id="some-other-task",
        allowed_actions=["read"],
    )
    write_execution_lease(wrong_scope, paths.leases)

    status = wake.activation_lease_status(wrong_scope["lease_id"], paths)

    assert status["valid"] is False
    assert status["requested_action"] == "wake_loop_start"
    assert any("task_id" in error for error in status["errors"])
    assert any("not allowed" in error for error in status["errors"])


def test_activation_lease_accepts_exact_local_scope(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    lease = build_execution_lease(
        issued_to="codex_composer",
        issuer="operator",
        task_id="wake-loop-start:codex_composer",
        allowed_actions=["wake_loop_start"],
    )
    write_execution_lease(lease, paths.leases)

    status = wake.activation_lease_status(lease["lease_id"], paths)

    assert status["valid"] is True
    assert status["authority_assurance"] == "local_scoped_checksum_not_operator_signature"


def test_repeated_loop_revalidates_lease_before_every_cycle(tmp_path: Path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    args = type(
        "Args",
        (),
        {
            "activation_lease": "lease-id",
            "interval_s": 0.0,
            "orientation_timeout_s": 1.0,
            "max_cycles": 0,
            "skip_orientation_command": True,
        },
    )()
    validations = iter(
        [
            {"valid": True, "lease_id": "lease-id", "errors": []},
            {"valid": False, "lease_id": "lease-id", "errors": ["lease is expired"]},
        ]
    )
    run_calls: list[str] = []
    monkeypatch.setattr(wake, "activation_lease_status", lambda *_: next(validations))
    monkeypatch.setattr(wake, "run_once", lambda *_args, **_kwargs: run_calls.append("ran"))
    monkeypatch.setattr(wake.time, "sleep", lambda *_: None)

    result = wake.loop_cycles(args, paths)

    assert result == 2
    assert run_calls == ["ran"]
    status = json.loads(paths.status.read_text(encoding="utf-8"))
    assert status["last_loop_block"]["cycles_completed"] == 1
    assert status["last_loop_block"]["activation_lease_validation"]["errors"] == [
        "lease is expired"
    ]


def _seed_fable_context(root: Path) -> None:
    (root / "agents" / "fable_composer").mkdir(parents=True, exist_ok=True)
    (root / "agents" / "fable_composer" / "BOOT.md").write_text(
        "# FABLE_COMPOSER COLD BOOT\nread_only_until_execution_lease\n",
        encoding="utf-8",
    )
    _write_json(
        root / "agents" / "fable_composer" / "identity.json",
        {"agent_uid": "fable_composer", "authority_mode": "read_only_until_execution_lease", "wake_loop_active": False},
    )
    _write_json(root / "a2a" / "cards" / "fable_composer.json", {"agent": "fable_composer"})
    _write_json(
        root / "agent_passports" / "fable_composer.json",
        {"agent_uid": "fable_composer", "authority_mode": "read_only_until_execution_lease"},
    )
    _write_json(
        root / "a2a_bus" / "bridge_heartbeats" / "fable_composer.json",
        {"agent_uid": "fable_composer", "status": "IDLE"},
    )
    _write_json(
        root / "a2a_bus" / "state" / "fable_composer.json",
        {"agent": "fable_composer", "wake_loop_active": False},
    )


def test_resolve_profile_selects_seat_and_is_lease_gated() -> None:
    codex = wake.resolve_profile("codex_composer")
    fable = wake.resolve_profile("fable_composer")
    sarathi = wake.resolve_profile("sarathi")
    assert codex.agent_uid == "codex_composer"
    assert fable.agent_uid == "fable_composer"
    assert sarathi.agent_uid == "sarathi"
    assert fable.session == "fable-composer-wake"
    assert fable.schema_prefix == "dharma.fable_composer"
    assert sarathi.session == "sarathi-wake"
    assert sarathi.schema_prefix == "dharma.sarathi"
    assert sarathi.display_name == "Sarathi Apex"
    # Default (None/empty) resolves to codex for backward compatibility.
    assert wake.resolve_profile(None).agent_uid == "codex_composer"
    assert wake.resolve_profile("").agent_uid == "codex_composer"


def test_resolve_profile_rejects_malformed_uid() -> None:
    import pytest

    with pytest.raises(ValueError):
        wake.resolve_profile("../etc/passwd")


def test_composer_paths_are_agent_scoped() -> None:
    codex = wake.composer_paths("~/.dharma", agent_uid="codex_composer")
    fable = wake.composer_paths("~/.dharma", agent_uid="fable_composer")
    assert codex.agent_uid == "codex_composer"
    assert fable.agent_uid == "fable_composer"
    assert fable.assigned_inbox.name == "fable_composer"
    assert str(fable.agent_home).endswith("/agents/fable_composer")
    assert str(fable.nest).endswith("/external_agents/fable_composer/nest")
    assert codex.assigned_inbox != fable.assigned_inbox


def test_fable_once_wakes_with_boot_context_and_scoped_schema(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_fable_context(state)
    paths = wake.composer_paths(state, repo_root=repo, agent_uid="fable_composer")

    receipt = wake.run_once(paths, runner=_runner)

    # BOOT.md counts as canonical context, so no required context is missing.
    assert receipt["context"]["missing"] == []
    assert receipt["agent_uid"] == "fable_composer"
    assert receipt["schema_version"] == "dharma.fable_composer.wake_receipt.v1"
    assert receipt["receipt_id"].startswith("fable-composer-wake-")
    assert receipt["safety"]["repo_write_performed"] is False
    heartbeat = json.loads(paths.heartbeat.read_text())
    assert heartbeat["agent_uid"] == "fable_composer"
    assert heartbeat["schema_version"] == "dharma.fable_composer.wake_heartbeat.v1"
    assert (paths.nest / "README.md").read_text().startswith("# fable_composer Wake Nest")


def test_fable_once_blocks_write_capable_work_without_lease(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_fable_context(state)
    paths = wake.composer_paths(state, repo_root=repo, agent_uid="fable_composer")
    paths.task_queue.parent.mkdir(parents=True, exist_ok=True)
    paths.task_queue.write_text(
        json.dumps(
            {
                "id": "fable-write",
                "to": "fable_composer",
                "status": "pending",
                "body": "Please edit repo files and commit.",
                "requires_execution_lease": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    receipt = wake.run_once(paths, runner=_runner)

    assert receipt["status"] == "blocked_execution_lease_required"
    assert len(receipt["work"]["work_requiring_execution_lease"]) == 1
    assert receipt["safety"]["source_mutation_performed"] is False


def _seed_sarathi_context(root: Path) -> None:
    (root / "agents" / "sarathi").mkdir(parents=True, exist_ok=True)
    (root / "agents" / "sarathi" / "BOOT.md").write_text(
        "# SARATHI APEX COLD BOOT\nread_only_until_execution_lease\n",
        encoding="utf-8",
    )
    _write_json(
        root / "agents" / "sarathi" / "identity.json",
        {
            "agent_uid": "sarathi",
            "model": "gemini-2.5-flash",
            "provider": "google_ai",
            "authority_mode": "read_only_until_execution_lease",
            "wake_loop_active": False,
        },
    )
    _write_json(root / "a2a" / "cards" / "sarathi.json", {"agent": "sarathi"})
    _write_json(
        root / "agent_passports" / "sarathi.json",
        {"agent_uid": "sarathi", "authority_mode": "read_only_until_execution_lease"},
    )
    _write_json(
        root / "a2a_bus" / "bridge_heartbeats" / "sarathi.json",
        {"agent_uid": "sarathi", "status": "IDLE"},
    )
    _write_json(
        root / "a2a_bus" / "state" / "sarathi.json",
        {"agent": "sarathi", "wake_loop_active": False},
    )


def test_sarathi_once_uses_registered_profile_without_forking_wake_loop(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_sarathi_context(state)
    paths = wake.composer_paths(state, repo_root=repo, agent_uid="sarathi")

    receipt = wake.run_once(paths, runner=_runner)

    assert receipt["status"] == "completed_read_only_analysis"
    assert receipt["context"]["missing"] == []
    assert receipt["agent_uid"] == "sarathi"
    assert receipt["schema_version"] == "dharma.sarathi.wake_receipt.v1"
    assert receipt["receipt_id"].startswith("sarathi-wake-")
    assert receipt["safety"]["source_mutation_performed"] is False
    heartbeat = json.loads(paths.heartbeat.read_text())
    assert heartbeat["agent_uid"] == "sarathi"
    assert heartbeat["schema_version"] == "dharma.sarathi.wake_heartbeat.v1"
    assert (paths.nest / "README.md").read_text().startswith("# sarathi Wake Nest")


def test_sarathi_model_identity_is_frontier_and_honors_override(monkeypatch) -> None:
    """PR-S3 (operator ruling 2026-07-30): DGC_DIRECTOR_SARATHI_MODEL is the
    operator override, and the default resolution must never be the retired
    gemini-2.5-flash flash-tier identity."""
    monkeypatch.setenv("DGC_DIRECTOR_SARATHI_MODEL", "frontier-override-x")
    assert wake._sarathi_model_identity() == "frontier-override-x"
    monkeypatch.delenv("DGC_DIRECTOR_SARATHI_MODEL", raising=False)
    resolved = wake._sarathi_model_identity()
    assert resolved
    assert resolved != "gemini-2.5-flash"
