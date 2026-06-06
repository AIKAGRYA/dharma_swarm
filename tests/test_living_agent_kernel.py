from __future__ import annotations

import json

from dharma_swarm.operator_core.governed_work_admission import WorkKind
from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue
from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    AuthorityPassport,
    KernelRunStore,
    KernelTask,
    LivingAgentKernel,
    MemoryPlan,
    ProofRequest,
    ToolRequest,
    TriggerEnvelope,
)


def _kernel(tmp_path) -> LivingAgentKernel:
    return LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
    )


def _envelope(
    *,
    work_kind: WorkKind = WorkKind.READ_ONLY,
    risk_tier: str = "Q1",
    authority: AuthorityPassport | None = None,
    trigger: TriggerEnvelope | None = None,
    tool_request: ToolRequest | None = None,
) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text="Inspect the current runtime state"),
        trigger=trigger or TriggerEnvelope(source="manual"),
        authority=authority or AuthorityPassport(work_kind=work_kind, risk_tier=risk_tier),
        memory=MemoryPlan(
            read_namespaces=["agent:codex_composer:working"],
            write_namespaces=["agent:codex_composer:lessons"],
        ),
        tool_request=tool_request or ToolRequest(),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def test_read_only_manual_envelope_completes_without_provider_execution(tmp_path):
    result = _kernel(tmp_path).run(_envelope())

    assert result.status == "completed"
    assert result.did_execute is False
    assert result.did_persist is True
    assert result.admission.decision == "allow"
    assert "read_file" in result.tool_plan.visible_tools
    assert "search_files" in result.tool_plan.visible_tools
    assert result.event_refs[0]["event_id"].endswith("000_run_started")
    assert result.proof_ledger_entry.envelope_hash.startswith("sha256:")
    assert result.proof_ledger_entry.tool_plan_hash == result.tool_plan.policy_hash
    assert result.proof_ledger_entry.unsupported_claims == ["no_provider_execution_in_v1"]
    assert result.proof_ledger_entry.entry_hash.startswith("sha256:")
    assert result.replay_ref["integrity_ok"] is True


def test_code_write_without_contract_is_review_and_write_tools_are_denied(tmp_path):
    envelope = _envelope(work_kind=WorkKind.CODE_WRITE, risk_tier="Q2")
    result = _kernel(tmp_path).run(envelope)

    assert result.status == "review"
    assert result.admission.decision == "review"
    assert "mission_contract_missing" in result.admission.reasons
    assert "workspace_lease_missing" in result.admission.reasons
    assert result.tool_plan.denial_reasons["apply_patch"] == "authority_decision_review"
    assert result.tool_plan.denial_reasons["write_file"] == "authority_decision_review"


def test_code_write_with_contract_can_see_write_tools(tmp_path):
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.CODE_WRITE,
            risk_tier="Q2",
            mission_contract_present=True,
            workspace_lease_present=True,
            allowed_files=["dharma_swarm/operator_core/living_agent_kernel.py"],
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "completed"
    assert result.admission.decision == "allow"
    assert "apply_patch" in result.tool_plan.visible_tools
    assert "pytest" in result.tool_plan.visible_tools


def test_self_evolution_without_mutation_budget_is_blocked(tmp_path):
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.SELF_EVOLUTION,
            risk_tier="Q3",
            context_quorum_ok=True,
            mission_contract_present=True,
            workspace_lease_present=True,
            mutation_budget_remaining=0,
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert result.admission.decision == "block"
    assert "mutation_budget_exhausted" in result.admission.reasons
    assert result.tool_plan.denial_reasons["self_edit"] == "authority_decision_block"
    assert result.tool_plan.denial_reasons["skill_promote"] == "authority_decision_block"


def test_high_risk_missing_context_quorum_is_blocked(tmp_path):
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q3",
            context_quorum_ok=False,
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert "context_quorum_missing_or_failed" in result.admission.reasons
    assert "context_quorum_receipt" in result.admission.required_receipts


def test_protected_file_hits_block_and_deny_protected_mutation(tmp_path):
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.CODE_WRITE,
            risk_tier="Q3",
            context_quorum_ok=True,
            mission_contract_present=True,
            workspace_lease_present=True,
            protected_file_hits=["docs/governance/ACTIVE_TRACK.yaml"],
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert "protected_file_hits" in result.admission.reasons
    assert result.tool_plan.denial_reasons["mutate_protected_files"] == "protected_file_hits"


def test_external_worker_evidence_only_keeps_action_tools_denied(tmp_path):
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q1",
            external_worker_authority="external_worker_evidence_only",
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.admission.decision == "allow"
    assert result.tool_plan.denial_reasons["apply_patch"] == "external_worker_evidence_only"
    assert result.tool_plan.denial_reasons["external_outreach"] == "external_worker_evidence_only"
    assert result.tool_plan.denial_reasons["payment"] == "external_worker_evidence_only"


def test_a2a_and_ds_goal_correlation_survives_proof_and_runtime_truth(tmp_path):
    envelope = _envelope(
        trigger=TriggerEnvelope(
            source="a2a",
            mission_id="living-agent-kernel-20260605",
            task_id="a2a-task-1",
            correlation_id="corr-123",
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.proof_ledger_entry.mission_id == "living-agent-kernel-20260605"
    assert result.proof_ledger_entry.task_id == "a2a-task-1"
    assert result.proof_ledger_entry.correlation_id == "corr-123"
    assert result.runtime_truth_packet["mission_id"] == "living-agent-kernel-20260605"
    assert result.runtime_truth_packet["task_id"] == "a2a-task-1"
    assert result.runtime_truth_packet["correlation_id"] == "corr-123"
    assert result.runtime_truth_packet["missing_machine_fields"] == []


def test_tool_plan_hash_is_stable_for_same_envelope(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        tool_request=ToolRequest(
            requested_tools=["read_file", "custom_read_probe"],
            late_bound_tools=["web_fetch"],
        )
    )
    admission = kernel.evaluate_authority(envelope)

    first = kernel.compile_tool_plan(envelope, admission)
    second = kernel.compile_tool_plan(envelope, admission)

    assert first.policy_hash == second.policy_hash
    assert "custom_read_probe" in first.visible_tools
    assert "web_fetch" in first.late_bound_tools


def test_session_status_tool_executes_and_replays(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        )
    )

    result = kernel.run(envelope)
    replay = kernel.store.replay_run(result.run_id)

    assert result.did_execute is True
    assert result.tool_results[0].status == "completed"
    assert result.tool_results[0].output["authority_decision"] == "allow"
    assert result.runtime_truth_packet["completion_state"] == "COMPLETED_BY_RECEIPT"
    assert len(replay.events) == 3
    assert len(replay.tool_results) == 1
    assert len(replay.proof_entries) == 1
    assert replay.integrity_ok is True
    assert replay.replay_hash == result.replay_ref["replay_hash"]


def test_blocked_authority_records_denied_tool_result(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q3",
            context_quorum_ok=False,
        ),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )

    result = kernel.run(envelope)
    replay = kernel.store.replay_run(result.run_id)

    assert result.status == "blocked"
    assert result.did_execute is False
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "authority_decision_block"
    assert len(replay.tool_results) == 1
    assert replay.tool_results[0]["status"] == "denied"


def test_read_file_tool_requires_explicit_allowed_file(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("do not read")
    envelope = _envelope(
        tool_request=ToolRequest(
            requested_tools=["read_file"],
            tool_calls=[{"name": "read_file", "arguments": {"path": str(secret)}}],
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert result.did_execute is False
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "read_file_requires_explicit_allowed_file"
    assert result.replay_ref["integrity_ok"] is True


def test_read_file_tool_reads_only_explicitly_allowed_file(tmp_path):
    allowed = tmp_path / "allowed.txt"
    allowed.write_text("runtime spine evidence")
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q1",
            allowed_files=[str(allowed)],
        ),
        tool_request=ToolRequest(
            requested_tools=["read_file"],
            tool_calls=[{"name": "read_file", "arguments": {"path": str(allowed)}}],
        ),
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "completed"
    assert result.did_execute is True
    assert result.tool_results[0].status == "completed"
    assert result.tool_results[0].output["content"] == "runtime spine evidence"
    assert result.tool_results[0].output["sha256"].startswith("sha256:")
    assert result.runtime_truth_packet["mutation_truth"]["dry_run_only"] is True


def test_invalid_tool_arguments_fail_run_with_receipt(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q1",
            allowed_files=["allowed.txt"],
        ),
        tool_request=ToolRequest(
            requested_tools=["read_file"],
            tool_calls=[{"name": "read_file", "arguments": {"path": 7}}],
        ),
    )

    result = kernel.run(envelope)
    replay = kernel.store.replay_run(result.run_id)

    assert result.status == "failed"
    assert result.did_execute is False
    assert result.tool_results[0].status == "failed"
    assert result.tool_results[0].error == "invalid_argument_type:path"
    assert result.replay_ref["integrity_ok"] is True
    assert len(replay.tool_results) == 1
    assert replay.tool_results[0]["status"] == "failed"


def _simple_patch(target: str = "editable.txt") -> str:
    return (
        f"--- a/{target}\n"
        f"+++ b/{target}\n"
        "@@ -1,2 +1,2 @@\n"
        " alpha\n"
        "-beta\n"
        "+gamma\n"
    )


def test_read_only_apply_patch_call_is_denied_before_dispatch(tmp_path):
    envelope = _envelope(
        tool_request=ToolRequest(
            requested_tools=["apply_patch"],
            tool_calls=[{"name": "apply_patch", "arguments": {"patch": _simple_patch()}}],
        )
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert result.did_execute is False
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "write_tool_requires_code_write_authority"


def test_apply_patch_dry_run_validates_allowed_diff_without_mutation(tmp_path):
    target = tmp_path / "editable.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.CODE_WRITE,
            risk_tier="Q2",
            mission_contract_present=True,
            workspace_lease_present=True,
            allowed_files=["editable.txt"],
        ),
        tool_request=ToolRequest(
            requested_tools=["apply_patch"],
            tool_calls=[{"name": "apply_patch", "arguments": {"patch": _simple_patch()}}],
            sandbox_policy={"mutation_mode": "dry_run"},
        ),
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "completed"
    assert result.did_execute is True
    assert result.tool_results[0].status == "completed"
    assert result.tool_results[0].output["dry_run"] is True
    assert result.tool_results[0].output["files_changed"] == ["editable.txt"]
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert result.runtime_truth_packet["mutation_truth"]["dry_run_only"] is True
    assert "apply_patch_dry_run_only" in result.proof_ledger_entry.unsupported_claims


def test_apply_patch_denies_diff_target_outside_allowed_files(tmp_path):
    target = tmp_path / "editable.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.CODE_WRITE,
            risk_tier="Q2",
            mission_contract_present=True,
            workspace_lease_present=True,
            allowed_files=["other.txt"],
        ),
        tool_request=ToolRequest(
            requested_tools=["apply_patch"],
            tool_calls=[{"name": "apply_patch", "arguments": {"patch": _simple_patch()}}],
            sandbox_policy={"mutation_mode": "dry_run"},
        ),
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "apply_patch_target_not_allowed"
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_apply_patch_live_apply_requires_explicit_sandbox_flag(tmp_path):
    target = tmp_path / "editable.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.CODE_WRITE,
            risk_tier="Q2",
            mission_contract_present=True,
            workspace_lease_present=True,
            allowed_files=["editable.txt"],
        ),
        tool_request=ToolRequest(
            requested_tools=["apply_patch"],
            tool_calls=[{"name": "apply_patch", "arguments": {"patch": _simple_patch()}}],
            sandbox_policy={"mutation_mode": "apply", "rollback_receipt_required": True},
        ),
    )

    result = _kernel(tmp_path).run(envelope)

    assert result.status == "blocked"
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "apply_patch_live_apply_requires_explicit_sandbox_allowance"
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_apply_patch_live_apply_records_rollback_backup(tmp_path):
    target = tmp_path / "editable.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    envelope = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.CODE_WRITE,
            risk_tier="Q2",
            mission_contract_present=True,
            workspace_lease_present=True,
            allowed_files=["editable.txt"],
        ),
        tool_request=ToolRequest(
            requested_tools=["apply_patch"],
            tool_calls=[{"name": "apply_patch", "arguments": {"patch": _simple_patch()}}],
            sandbox_policy={
                "mutation_mode": "apply",
                "allow_write_tool_execution": True,
                "rollback_receipt_required": True,
            },
        ),
    )

    result = _kernel(tmp_path).run(envelope)
    backup_path = result.tool_results[0].output["backup_paths"][str(target)]

    assert result.status == "completed"
    assert result.tool_results[0].status == "completed"
    assert result.tool_results[0].output["mutation_mode"] == "apply"
    assert result.tool_results[0].output["applied"] is True
    assert result.tool_results[0].output["rollback_available"] is True
    assert target.read_text(encoding="utf-8") == "alpha\ngamma\n"
    assert (tmp_path / "editable.txt.bak").read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert backup_path == str(tmp_path / "editable.txt.bak")
    assert result.runtime_truth_packet["mutation_truth"]["dry_run_only"] is False
    assert "write_tool_execution_limited_to_kernel_diff_adapter" in result.proof_ledger_entry.unsupported_claims


def test_wake_queues_leases_executes_and_records_terminal_result(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        trigger=TriggerEnvelope(
            source="manual",
            mission_id="living-agent-kernel-20260605",
            task_id="wake-task-1",
            correlation_id="wake-corr-1",
        ),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )

    execution = kernel.wake(envelope, wake_id="wake-direct-1", lease_owner="codex-test")
    latest = kernel.store.latest_wake_records()["wake-direct-1"]
    ok, errors = kernel.store.verify_wake_ledger()

    assert execution.status == "completed"
    assert execution.result is not None
    assert execution.result.status == "completed"
    assert execution.wake_record is not None
    assert execution.wake_record.status == "completed"
    assert latest.status == "completed"
    assert latest.result_ref["run_id"] == envelope.run_id
    assert latest.result_ref["replay_ref"]["integrity_ok"] is True
    assert len(kernel.store.wake_records()) == 3
    assert ok is True
    assert errors == []


def test_run_next_wake_returns_idle_without_queued_work(tmp_path):
    execution = _kernel(tmp_path).run_next_wake(lease_owner="codex-test")

    assert execution.status == "idle"
    assert execution.wake_record is None
    assert execution.result is None


def test_expired_wake_lease_is_recovered_and_executed(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        trigger=TriggerEnvelope(correlation_id="wake-corr-expired"),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )
    kernel.store.enqueue_wake(
        envelope,
        wake_id="wake-expired-1",
        now="2026-06-05T00:00:00Z",
    )
    leased = kernel.store.lease_next_wake(
        lease_owner="stale-worker",
        lease_seconds=1,
        now="2026-06-05T00:00:01Z",
    )

    recovered = kernel.recover_expired_wakes(now="2026-06-05T00:00:03Z")
    execution = kernel.run_next_wake(lease_owner="codex-recovery")
    latest = kernel.store.latest_wake_records()["wake-expired-1"]

    assert leased is not None
    assert leased.status == "leased"
    assert recovered[0].status == "queued"
    assert recovered[0].reason == "leased_wake_expired_and_requeued"
    assert execution.status == "completed"
    assert latest.status == "completed"
    assert latest.attempt == 2


def test_wake_ledger_integrity_detects_tampering(tmp_path):
    kernel = _kernel(tmp_path)
    record = kernel.enqueue_wake(_envelope(), wake_id="wake-tamper-1")
    rows = [
        json.loads(line)
        for line in kernel.store.wake_ledger_path.read_text().splitlines()
        if line.strip()
    ]
    rows[0]["reason"] = "tampered"
    kernel.store.wake_ledger_path.write_text(json.dumps(rows[0], sort_keys=True) + "\n")

    ok, errors = kernel.store.verify_wake_ledger()

    assert record.record_hash.startswith("sha256:")
    assert ok is False
    assert errors == ["line 1: record_hash mismatch"]


def test_manual_wake_source_normalizes_and_executes(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "task": "Inspect live kernel status",
        "agent_uid": "codex_composer",
        "correlation_id": "manual-corr-1",
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    record = kernel.enqueue_source_wake("manual", payload, wake_id="manual-source-1")
    execution = kernel.run_next_wake(lease_owner="codex-test")

    assert record.envelope.trigger.source == "manual"
    assert record.envelope.trigger.correlation_id == "manual-corr-1"
    assert execution.status == "completed"
    assert execution.result is not None
    assert execution.result.did_execute is True


def test_a2a_task_row_normalizes_return_address_and_claim_authority(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "id": "a2a-task-42",
        "from": "opus_composer",
        "to": "codex_composer",
        "task": "Read the bounded fixture",
        "mission_id": "mission-a2a",
        "return_address": {
            "resume_surface": "a2a_task_queue",
            "resume_ref": "a2a_task:a2a-task-42",
            "obligation": "close_task_with_receipt",
            "base_case": "terminal receipt",
            "trace_id": "trace-a2a-42",
        },
        "allowed_files": ["fixture.txt"],
    }

    envelope = kernel.normalize_wake_source("a2a", payload)

    assert envelope.agent_uid == "codex_composer"
    assert envelope.trigger.source == "a2a"
    assert envelope.trigger.task_id == "a2a-task-42"
    assert envelope.trigger.correlation_id == "trace-a2a-42"
    assert envelope.trigger.metadata["return_address"]["resume_surface"] == "a2a_task_queue"
    assert envelope.authority.work_kind == WorkKind.A2A_CLAIM
    assert envelope.authority.allowed_files == ["fixture.txt"]


def test_ds_goal_task_normalizes_lease_and_write_authority(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "schema": "dharma.autonomy_task.v1",
        "mission_id": "mission-ds-goal",
        "task_id": "mission-ds-goal-t02-builder",
        "role": "builder",
        "agent_uid": "codex_composer",
        "title": "Implement the scoped change under the mission lease",
        "allowed_writes": ["dharma_swarm/operator_core/"],
        "verifier_command": "pytest -q tests/test_living_agent_kernel.py",
        "lease": {
            "claimed_by": "codex_composer",
            "claimed_at": "2026-06-05T00:00:00Z",
            "expires_at": "2026-06-05T01:00:00Z",
        },
        "return_address": "autonomy://mission-ds-goal/mission-ds-goal-t02-builder",
    }

    envelope = kernel.normalize_wake_source("ds_goal", payload)
    admission = kernel.evaluate_authority(envelope)
    tool_plan = kernel.compile_tool_plan(envelope, admission)

    assert envelope.trigger.source == "ds_goal"
    assert envelope.trigger.mission_id == "mission-ds-goal"
    assert envelope.trigger.task_id == "mission-ds-goal-t02-builder"
    assert envelope.authority.work_kind == WorkKind.CODE_WRITE
    assert envelope.authority.mission_contract_present is True
    assert envelope.authority.workspace_lease_present is True
    assert envelope.authority.allowed_files == ["dharma_swarm/operator_core/"]
    assert envelope.proof.verifier_commands == ["pytest -q tests/test_living_agent_kernel.py"]
    assert admission.decision == "allow"
    assert "apply_patch" in tool_plan.visible_tools


def test_persistent_self_wake_normalizes_agent_identity_and_memory(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "name": "conductor_alpha",
        "wake_reason": "Urgent stigmergy signal: runtime liveness drift",
        "wake_interval_seconds": 300,
        "witness_log": "/tmp/conductor_alpha.jsonl",
        "correlation_id": "self-wake-corr",
    }

    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)

    assert envelope.agent_uid == "conductor_alpha"
    assert envelope.trigger.source == "persistent_self_wake"
    assert envelope.trigger.correlation_id == "self-wake-corr"
    assert envelope.trigger.metadata["wake_interval_seconds"] == 300
    assert envelope.memory.read_namespaces == ["agent:conductor_alpha:working"]
    assert envelope.memory.write_namespaces == ["agent:conductor_alpha:lessons"]


def test_external_fleet_wake_is_evidence_only_and_denies_action_tools(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "name": "hermes-m5",
        "provider": "hermes",
        "model": "hermes-agent",
        "task": "Audit the bounded result and report evidence only",
        "correlation_id": "fleet-corr-1",
        "requested_tools": ["apply_patch"],
        "tool_calls": [{"name": "apply_patch", "arguments": {"patch": "*** Begin Patch"}}],
    }

    envelope = kernel.normalize_wake_source("external_fleet", payload)
    result = kernel.run(envelope)

    assert envelope.authority.external_worker_authority == "external_worker_evidence_only"
    assert envelope.trigger.source == "external_fleet"
    assert result.status == "blocked"
    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "external_worker_evidence_only"


def test_a2a_closeback_closes_queue_with_kernel_receipt(tmp_path):
    kernel = _kernel(tmp_path)
    queue = tmp_path / "a2a_bus" / "tasks" / "queue.jsonl"
    queue.parent.mkdir(parents=True)
    return_address = {
        "resume_surface": "a2a_task_queue",
        "resume_ref": "a2a_task:a2a-close-1",
        "obligation": "close_task_with_receipt",
        "base_case": "terminal receipt",
        "trace_id": "a2a-close-trace",
    }
    task_row = {
        "id": "a2a-close-1",
        "from": "opus_composer",
        "to": "codex_composer",
        "status": "claimed",
        "claimed_by": "codex_composer",
        "task": "Close this A2A task through the kernel.",
        "mission_id": "mission-a2a-close",
        "return_address": return_address,
    }
    queue.write_text(json.dumps(task_row, sort_keys=True) + "\n", encoding="utf-8")
    payload = {
        **task_row,
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    kernel.enqueue_source_wake("a2a", payload, wake_id="wake-a2a-close")
    execution = kernel.run_next_wake(lease_owner="codex-test")
    closeback = kernel.closeback_source_wake(execution.wake_record, execution.result, source_root=tmp_path)
    closed = read_queue(tmp_path)[0]
    latest = kernel.store.latest_wake_records()["wake-a2a-close"]

    assert execution.status == "completed"
    assert closeback.status == "closed"
    assert closeback.mutated is True
    assert closeback.receipt_ref["content_hash"].startswith("sha256:")
    assert closed["status"] == "completed"
    assert closed["receipt"]["schema_version"] == "dharma_a2a_task_receipt.v1"
    assert closed["receipt"]["evidence"]["kernel_result"]["run_id"] == execution.result.run_id
    assert latest.result_ref["source_closeback"]["status"] == "closed"


def test_ds_goal_closeback_records_kernel_result_ref_without_closing_task(tmp_path):
    kernel = _kernel(tmp_path)
    mission_root = tmp_path / "mission-ds-close"
    mission_root.mkdir(parents=True)
    task = {
        "schema": "dharma.autonomy_task.v1",
        "mission_id": "mission-ds-close",
        "task_id": "mission-ds-close-t02-builder",
        "role": "builder",
        "agent_uid": "codex_composer",
        "title": "Record the kernel result against this leased task.",
        "status": "claimed",
        "allowed_writes": ["dharma_swarm/operator_core/"],
        "verifier_command": "pytest -q tests/test_living_agent_kernel.py",
        "lease": {
            "claimed_by": "codex_composer",
            "claimed_at": "2026-06-05T00:00:00Z",
            "expires_at": "2026-06-05T01:00:00Z",
        },
        "return_address": "autonomy://mission-ds-close/mission-ds-close-t02-builder",
        "receipt_required": True,
    }
    (mission_root / "tasks.jsonl").write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")
    payload = {
        **task,
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    kernel.enqueue_source_wake("ds_goal", payload, wake_id="wake-ds-close")
    execution = kernel.run_next_wake(lease_owner="codex-test")
    closeback = kernel.closeback_source_wake(execution.wake_record, execution.result, source_root=tmp_path)
    updated = [
        json.loads(line)
        for line in (mission_root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][0]

    assert execution.status == "completed"
    assert closeback.status == "recorded"
    assert closeback.mutated is True
    assert updated["status"] == "claimed"
    assert updated["kernel_result_status"] == "completed"
    assert updated["kernel_result_ref"]["run_id"] == execution.result.run_id
    assert updated["kernel_closeback_via"] == "operator_core.living_agent_kernel.source_closeback"


def test_persistent_self_wake_closeback_writes_witness_receipt(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "name": "conductor_alpha",
        "wake_reason": "Record source witness closeback",
        "witness_log": "witness/conductor_alpha.jsonl",
        "correlation_id": "self-close-corr",
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    kernel.enqueue_source_wake("persistent_self_wake", payload, wake_id="wake-self-close")
    execution = kernel.run_next_wake(lease_owner="codex-test")
    closeback = kernel.closeback_source_wake(execution.wake_record, execution.result, source_root=tmp_path)
    witness_rows = [
        json.loads(line)
        for line in (tmp_path / "witness" / "conductor_alpha.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert closeback.status == "recorded"
    assert closeback.mutated is True
    assert witness_rows[0]["schema_version"] == "dharma_living_agent_kernel_self_wake_receipt.v1"
    assert witness_rows[0]["result_ref"]["run_id"] == execution.result.run_id
    assert witness_rows[0]["correlation_id"] == "self-close-corr"


def test_external_fleet_closeback_is_refused_without_mutating_source(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "name": "hermes-m5",
        "provider": "hermes",
        "task": "Report evidence only.",
        "correlation_id": "fleet-close-corr",
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    kernel.enqueue_source_wake("external_fleet", payload, wake_id="wake-fleet-close")
    execution = kernel.run_next_wake(lease_owner="codex-test")
    closeback = kernel.closeback_source_wake(execution.wake_record, execution.result, source_root=tmp_path)
    latest = kernel.store.latest_wake_records()["wake-fleet-close"]

    assert execution.status == "completed"
    assert closeback.status == "refused"
    assert closeback.mutated is False
    assert closeback.reason == "external_fleet_evidence_only_closeback_refused"
    assert latest.result_ref["source_closeback"]["status"] == "refused"


def test_latest_wake_status_projects_operator_view(tmp_path):
    kernel = _kernel(tmp_path)
    payload = {
        "task": "Show latest wake state",
        "agent_uid": "codex_composer",
        "mission_id": "mission-operator-view",
        "task_id": "wake-view-task",
        "correlation_id": "wake-view-corr",
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    kernel.enqueue_source_wake("manual", payload, wake_id="wake-view-1")
    execution = kernel.run_next_wake(lease_owner="codex-test")
    rows = kernel.latest_wake_status(limit=1)

    assert execution.status == "completed"
    assert rows[0]["wake_id"] == "wake-view-1"
    assert rows[0]["source"] == "manual"
    assert rows[0]["task_id"] == "wake-view-task"
    assert rows[0]["result_ref"]["replay_ref"]["integrity_ok"] is True
    assert rows[0]["source_payload_hash"].startswith("sha256:")


def test_source_closeback_requires_persisted_kernel_proof(tmp_path):
    kernel = LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
        persist=False,
    )
    queue = tmp_path / "a2a_bus" / "tasks" / "queue.jsonl"
    queue.parent.mkdir(parents=True)
    task_row = {
        "id": "a2a-proof-required",
        "from": "opus_composer",
        "to": "codex_composer",
        "status": "claimed",
        "claimed_by": "codex_composer",
        "task": "This should not close without persisted kernel proof.",
        "return_address": {
            "resume_surface": "a2a_task_queue",
            "resume_ref": "a2a_task:a2a-proof-required",
            "obligation": "close_task_with_receipt",
            "base_case": "terminal receipt",
        },
    }
    queue.write_text(json.dumps(task_row, sort_keys=True) + "\n", encoding="utf-8")
    payload = {
        **task_row,
        "requested_tools": ["session_status"],
        "tool_calls": [{"name": "session_status", "arguments": {}}],
    }

    kernel.enqueue_source_wake("a2a", payload, wake_id="wake-proof-required")
    execution = kernel.run_next_wake(lease_owner="codex-test")
    closeback = kernel.closeback_source_wake(execution.wake_record, execution.result, source_root=tmp_path)

    assert execution.result.did_persist is False
    assert closeback.status == "blocked"
    assert closeback.reason == "kernel_result_proof_missing"
    assert read_queue(tmp_path)[0]["status"] == "claimed"


def test_control_tick_runs_wakes_and_auto_closebacks_sources(tmp_path):
    kernel = _kernel(tmp_path)
    queue = tmp_path / "a2a_bus" / "tasks" / "queue.jsonl"
    queue.parent.mkdir(parents=True)
    return_address = {
        "resume_surface": "a2a_task_queue",
        "resume_ref": "a2a_task:a2a-control-1",
        "obligation": "close_task_with_receipt",
        "base_case": "terminal receipt",
        "trace_id": "a2a-control-trace",
    }
    task_row = {
        "id": "a2a-control-1",
        "from": "opus_composer",
        "to": "codex_composer",
        "status": "claimed",
        "claimed_by": "codex_composer",
        "task": "Close through a control tick.",
        "mission_id": "mission-control",
        "return_address": return_address,
    }
    queue.write_text(json.dumps(task_row, sort_keys=True) + "\n", encoding="utf-8")
    kernel.enqueue_source_wake(
        "manual",
        {
            "task": "Manual control tick wake",
            "correlation_id": "manual-control-corr",
            "requested_tools": ["session_status"],
            "tool_calls": [{"name": "session_status", "arguments": {}}],
        },
        wake_id="wake-control-manual",
    )
    kernel.enqueue_source_wake(
        "a2a",
        {
            **task_row,
            "requested_tools": ["session_status"],
            "tool_calls": [{"name": "session_status", "arguments": {}}],
        },
        wake_id="wake-control-a2a",
    )

    tick = kernel.run_control_tick(
        lease_owner="control-test",
        max_wakes=2,
        source_roots={"a2a": tmp_path},
    )
    closebacks_by_source = {closeback.source: closeback for closeback in tick.closebacks}

    assert tick.status == "completed"
    assert len(tick.executions) == 2
    assert closebacks_by_source["manual"].status == "recorded"
    assert closebacks_by_source["a2a"].status == "closed"
    assert read_queue(tmp_path)[0]["status"] == "completed"
    assert {row["wake_id"] for row in tick.latest_wake_status} >= {"wake-control-manual", "wake-control-a2a"}


def test_control_tick_recovers_expired_wake_before_running(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        trigger=TriggerEnvelope(correlation_id="control-expired-corr"),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )
    kernel.store.enqueue_wake(
        envelope,
        wake_id="wake-control-expired",
        now="2026-06-05T00:00:00Z",
    )
    leased = kernel.store.lease_next_wake(
        lease_owner="stale-control-worker",
        lease_seconds=1,
        now="2026-06-05T00:00:01Z",
    )

    tick = kernel.run_control_tick(lease_owner="control-recovery", max_wakes=1)
    latest = kernel.store.latest_wake_records()["wake-control-expired"]

    assert leased is not None
    assert tick.status == "completed"
    assert tick.recovered_wake_ids == ["wake-control-expired"]
    assert len(tick.executions) == 1
    assert tick.closebacks[0].status == "recorded"
    assert latest.status == "completed"
    assert latest.attempt == 2


def test_control_snapshot_reports_empty_store_as_integrity_ok(tmp_path):
    snapshot = _kernel(tmp_path).control_snapshot()

    assert snapshot.integrity_ok is True
    assert snapshot.integrity_errors == []
    assert snapshot.queued_wake_ids == []
    assert snapshot.latest_wake_status == []


def test_control_snapshot_survives_restart_and_recovers_expired_wake(tmp_path):
    store_path = tmp_path / "kernel"
    first_kernel = LivingAgentKernel(
        store=KernelRunStore(store_path),
        workspace_root=tmp_path,
    )
    envelope = _envelope(
        trigger=TriggerEnvelope(correlation_id="restart-expired-corr"),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )
    first_kernel.store.enqueue_wake(
        envelope,
        wake_id="wake-restart-expired",
        now="2026-06-05T00:00:00Z",
    )
    first_kernel.store.lease_next_wake(
        lease_owner="worker-before-crash",
        lease_seconds=1,
        now="2026-06-05T00:00:01Z",
    )

    restarted_kernel = LivingAgentKernel(
        store=KernelRunStore(store_path),
        workspace_root=tmp_path,
    )
    before = restarted_kernel.control_snapshot(now="2026-06-05T00:00:03Z")
    tick = restarted_kernel.run_control_tick(lease_owner="worker-after-restart", max_wakes=1)
    after = restarted_kernel.control_snapshot(now="2026-06-05T00:00:04Z")

    assert before.integrity_ok is True
    assert before.leased_wake_ids == ["wake-restart-expired"]
    assert before.expired_lease_wake_ids == ["wake-restart-expired"]
    assert tick.recovered_wake_ids == ["wake-restart-expired"]
    assert tick.status == "completed"
    assert after.expired_lease_wake_ids == []
    assert after.terminal_wake_ids == ["wake-restart-expired"]


def test_spawn_subagent_wake_inherits_authority_and_control_tick_records_delivery(tmp_path):
    kernel = _kernel(tmp_path)
    parent = _envelope(
        trigger=TriggerEnvelope(
            source="manual",
            mission_id="mission-subagent",
            task_id="parent-task",
            correlation_id="subagent-corr",
        ),
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q1",
            allowed_files=["workspace/"],
        ),
        tool_request=ToolRequest(
            inherited_subagent_limits={
                "max_children": 2,
                "allowed_agents": ["child_worker"],
                "max_depth": 1,
            }
        ),
    )

    dispatch = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="child_worker",
        task_text="Inspect child state",
        role="verifier",
        allowed_files=["workspace/child.txt"],
        requested_tools=["session_status"],
        tool_calls=[{"name": "session_status", "arguments": {}}],
        wake_id="wake-subagent-child",
    )
    queued = kernel.store.latest_wake_records()["wake-subagent-child"]

    assert dispatch.status == "spawned"
    assert dispatch.parent_run_id == parent.run_id
    assert dispatch.child_agent_uid == "child_worker"
    assert dispatch.wake_id == "wake-subagent-child"
    assert queued.status == "queued"
    assert queued.envelope.trigger.source == "subagent"
    assert queued.envelope.trigger.parent_run_id == parent.run_id
    assert queued.envelope.trigger.metadata["subagent_depth"] == 1
    assert queued.envelope.trigger.metadata["subagent_role"] == "verifier"
    assert queued.envelope.authority.allowed_files == ["workspace/child.txt"]
    assert queued.envelope.proof.receipt_refs[-1]["kind"] == "subagent_parent_run"
    assert queued.envelope.proof.receipt_refs[-1]["payload_hash"].startswith("sha256:")

    tick = kernel.run_control_tick(lease_owner="subagent-control", max_wakes=1)
    completed = kernel.store.latest_wake_records()["wake-subagent-child"]
    closeback = tick.closebacks[0]

    assert tick.status == "completed"
    assert tick.executions[0].result.run_id == dispatch.child_run_id
    assert closeback.source == "subagent"
    assert closeback.status == "recorded"
    assert closeback.reason == "subagent_result_recorded"
    assert closeback.source_ref["parent_run_id"] == parent.run_id
    assert closeback.receipt_ref["kind"] == "subagent_delivery"
    assert closeback.receipt_ref["payload_hash"].startswith("sha256:")
    assert completed.result_ref["source_closeback"]["reason"] == "subagent_result_recorded"


def test_spawn_subagent_denies_disallowed_agent_and_scope_escalation(tmp_path):
    kernel = _kernel(tmp_path)
    parent = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q1",
            allowed_files=["workspace/"],
        ),
        tool_request=ToolRequest(
            inherited_subagent_limits={
                "allowed_agents": ["allowed_child"],
                "max_depth": 1,
            }
        ),
    )

    denied_agent = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="other_child",
        task_text="Try disallowed child",
    )
    denied_scope = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="allowed_child",
        task_text="Try wider scope",
        allowed_files=["outside.txt"],
    )

    assert denied_agent.status == "denied"
    assert denied_agent.child_agent_uid == "other_child"
    assert denied_agent.reason == "subagent_agent_not_allowed"
    assert denied_scope.status == "denied"
    assert denied_scope.child_agent_uid == "allowed_child"
    assert denied_scope.reason == "subagent_allowed_files_escalation"
    assert kernel.store.wake_records() == []


def test_spawn_subagent_respects_max_children(tmp_path):
    kernel = _kernel(tmp_path)
    parent = _envelope(
        authority=AuthorityPassport(
            work_kind=WorkKind.READ_ONLY,
            risk_tier="Q1",
            allowed_files=["workspace/"],
        ),
        tool_request=ToolRequest(
            inherited_subagent_limits={
                "max_children": 1,
                "allowed_agents": ["child_worker"],
            }
        ),
    )

    first = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="child_worker",
        task_text="First child",
        allowed_files=["workspace/first.txt"],
        wake_id="wake-first-child",
    )
    second = kernel.spawn_subagent_wake(
        parent,
        child_agent_uid="child_worker",
        task_text="Second child",
        allowed_files=["workspace/second.txt"],
        wake_id="wake-second-child",
    )

    assert first.status == "spawned"
    assert second.status == "denied"
    assert second.reason == "subagent_max_children_exceeded"
    assert [record.wake_id for record in kernel.store.wake_records()] == ["wake-first-child"]


def test_daemon_cycle_runs_control_tick_and_records_heartbeat(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        trigger=TriggerEnvelope(correlation_id="daemon-cycle-corr"),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )
    kernel.enqueue_wake(envelope, wake_id="wake-daemon-cycle", reason="daemon_cycle_test")

    cycle = kernel.run_daemon_cycle(
        daemon_id="kernel-daemon",
        max_wakes=1,
        interval_seconds=30,
        now="2026-06-05T00:00:00Z",
    )
    latest = kernel.store.latest_wake_records()["wake-daemon-cycle"]
    cycles = kernel.store.daemon_cycles()
    ok, errors = kernel.store.verify_daemon_cycle_ledger()

    assert cycle.status == "completed"
    assert cycle.control_state.status == "running"
    assert cycle.tick.status == "completed"
    assert cycle.tick.executions[0].wake_record.wake_id == "wake-daemon-cycle"
    assert latest.status == "completed"
    assert cycle.next_run_after == "2026-06-05T00:00:30Z"
    assert cycle.heartbeat_ref["cycle_id"] == cycle.cycle_id
    assert cycle.heartbeat_ref["path"].endswith("daemon_cycles.jsonl")
    assert cycle.record_hash.startswith("sha256:")
    assert cycles[0].record_hash == cycle.record_hash
    assert ok is True
    assert errors == []


def test_daemon_pause_blocks_cycle_until_resume(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(
        trigger=TriggerEnvelope(correlation_id="daemon-pause-corr"),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
    )
    pause = kernel.request_daemon_control(
        "pause",
        daemon_id="kernel-daemon",
        requested_by="operator",
        reason="maintenance",
        ttl_seconds=60,
        now="2026-06-05T00:00:00Z",
    )
    kernel.enqueue_wake(envelope, wake_id="wake-daemon-paused", reason="daemon_pause_test")

    paused = kernel.run_daemon_cycle(
        daemon_id="kernel-daemon",
        max_wakes=1,
        now="2026-06-05T00:00:10Z",
    )
    kernel.request_daemon_control(
        "resume",
        daemon_id="kernel-daemon",
        requested_by="operator",
        reason="maintenance complete",
        now="2026-06-05T00:00:20Z",
    )
    resumed = kernel.run_daemon_cycle(
        daemon_id="kernel-daemon",
        max_wakes=1,
        now="2026-06-05T00:00:21Z",
    )
    latest = kernel.store.latest_wake_records()["wake-daemon-paused"]
    ok, errors = kernel.store.verify_daemon_control_ledger()

    assert pause.record_hash.startswith("sha256:")
    assert pause.expires_at == "2026-06-05T00:01:00Z"
    assert paused.status == "paused"
    assert paused.tick is None
    assert paused.control_state.active_control_ref["record_hash"] == pause.record_hash
    assert kernel.store.daemon_cycles()[0].status == "paused"
    assert resumed.status == "completed"
    assert resumed.tick.status == "completed"
    assert latest.status == "completed"
    assert ok is True
    assert errors == []


def test_daemon_stop_blocks_until_resume_without_losing_wake(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _envelope(trigger=TriggerEnvelope(correlation_id="daemon-stop-corr"))
    kernel.enqueue_wake(envelope, wake_id="wake-daemon-stopped", reason="daemon_stop_test")
    stop = kernel.request_daemon_control(
        "stop",
        daemon_id="kernel-daemon",
        requested_by="operator",
        reason="operator stop",
        now="2026-06-05T00:00:00Z",
    )

    stopped = kernel.run_daemon_cycle(
        daemon_id="kernel-daemon",
        max_wakes=1,
        now="2026-06-05T00:00:01Z",
    )
    kernel.request_daemon_control(
        "resume",
        daemon_id="kernel-daemon",
        requested_by="operator",
        reason="operator restart",
        now="2026-06-05T00:00:02Z",
    )
    resumed = kernel.run_daemon_cycle(
        daemon_id="kernel-daemon",
        max_wakes=1,
        now="2026-06-05T00:00:03Z",
    )
    latest = kernel.store.latest_wake_records()["wake-daemon-stopped"]

    assert stop.record_hash.startswith("sha256:")
    assert stopped.status == "stopped"
    assert stopped.tick is None
    assert latest.status == "completed"
    assert resumed.status == "completed"
    assert resumed.tick.executions[0].wake_record.wake_id == "wake-daemon-stopped"


def test_daemon_ledgers_detect_tampering(tmp_path):
    kernel = _kernel(tmp_path)
    kernel.request_daemon_control(
        "pause",
        daemon_id="kernel-daemon",
        requested_by="operator",
        reason="before tamper",
        now="2026-06-05T00:00:00Z",
    )
    kernel.run_daemon_cycle(daemon_id="kernel-daemon", now="2026-06-05T00:00:01Z")

    control_rows = [
        json.loads(line)
        for line in kernel.store.daemon_control_path.read_text().splitlines()
        if line.strip()
    ]
    cycle_rows = [
        json.loads(line)
        for line in kernel.store.daemon_cycles_path.read_text().splitlines()
        if line.strip()
    ]
    control_rows[0]["reason"] = "tampered"
    cycle_rows[0]["status"] = "completed"
    kernel.store.daemon_control_path.write_text(json.dumps(control_rows[0], sort_keys=True) + "\n")
    kernel.store.daemon_cycles_path.write_text(json.dumps(cycle_rows[0], sort_keys=True) + "\n")

    control_ok, control_errors = kernel.store.verify_daemon_control_ledger()
    cycle_ok, cycle_errors = kernel.store.verify_daemon_cycle_ledger()

    assert control_ok is False
    assert control_errors == ["line 1: record_hash mismatch"]
    assert cycle_ok is False
    assert cycle_errors == ["line 1: record_hash mismatch"]


def test_proof_ledger_integrity_detects_tampering(tmp_path):
    kernel = _kernel(tmp_path)
    result = kernel.run(_envelope())
    rows = [
        json.loads(line)
        for line in kernel.store.proof_ledger_path.read_text().splitlines()
        if line.strip()
    ]
    rows[0]["status"] = "completed-but-tampered"
    kernel.store.proof_ledger_path.write_text(json.dumps(rows[0], sort_keys=True) + "\n")

    ok, errors = kernel.store.verify_proof_ledger()

    assert result.proof_ledger_entry.entry_hash.startswith("sha256:")
    assert ok is False
    assert errors == ["line 1: entry_hash mismatch"]
