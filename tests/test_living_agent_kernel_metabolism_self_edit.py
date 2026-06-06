from __future__ import annotations

import json

from dharma_swarm.operator_core.governed_work_admission import WorkKind
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
from dharma_swarm.operator_core.living_agent_kernel_lessons import KernelLessonStore


def _kernel(tmp_path) -> LivingAgentKernel:
    return LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
    )


def _lesson_store(tmp_path) -> KernelLessonStore:
    return KernelLessonStore(tmp_path / "kernel")


def _seed_skill_file(tmp_path, agent_uid: str = "codex_composer", name: str = "SKILL.md") -> "object":
    skill_dir = tmp_path / "skills" / agent_uid
    skill_dir.mkdir(parents=True, exist_ok=True)
    target = skill_dir / name
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    return target


def _skill_patch(rel_target: str, *, before: str = "beta", after: str = "gamma") -> str:
    return (
        f"--- a/{rel_target}\n"
        f"+++ b/{rel_target}\n"
        "@@ -1,2 +1,2 @@\n"
        " alpha\n"
        f"-{before}\n"
        f"+{after}\n"
    )


def _self_edit_envelope(
    *,
    agent_uid: str = "codex_composer",
    work_kind: WorkKind = WorkKind.SELF_EVOLUTION,
    risk_tier: str = "Q2",
    mission_contract_present: bool = True,
    workspace_lease_present: bool = True,
    external_worker_authority: str = "",
    patch: str | None = None,
    mutation_mode: str = "apply",
    sandbox_policy: dict[str, object] | None = None,
    own_skill_files: list[str] | None = None,
    mutation_budget_remaining: int | None = 5,
) -> AgentRunEnvelope:
    if patch is None:
        patch = _skill_patch(f"skills/{agent_uid}/SKILL.md")
    if sandbox_policy is None:
        sandbox_policy = {
            "mutation_mode": mutation_mode,
            "allow_write_tool_execution": True,
            "rollback_receipt_required": True,
        }
    metadata: dict[str, object] = {}
    if own_skill_files is not None:
        metadata["own_skill_files"] = own_skill_files
    return AgentRunEnvelope(
        agent_uid=agent_uid,
        task=KernelTask(text="Self-edit my own skill file"),
        trigger=TriggerEnvelope(
            source="persistent_self_wake",
            mission_id="mission-self",
            task_id="task-self",
            correlation_id="corr-self",
            parent_run_id="parent-run",
        ),
        authority=AuthorityPassport(
            work_kind=work_kind,
            risk_tier=risk_tier,
            mutation_budget_remaining=mutation_budget_remaining,
            mission_contract_present=mission_contract_present,
            workspace_lease_present=workspace_lease_present,
            external_worker_authority=external_worker_authority,
            metadata=metadata,
        ),
        memory=MemoryPlan(
            read_namespaces=[f"agent:{agent_uid}:working"],
            write_namespaces=[f"agent:{agent_uid}:lessons"],
        ),
        tool_request=ToolRequest(
            requested_tools=["self_edit"],
            tool_calls=[{"name": "self_edit", "arguments": {"patch": patch}}],
            sandbox_policy=dict(sandbox_policy),
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_metabolism_self_edit.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_self_edit_denied_under_non_self_evolution_work_kind(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    envelope = _self_edit_envelope(work_kind=WorkKind.CODE_WRITE)
    result = kernel._dispatch_self_edit(
        envelope, {"patch": _skill_patch("skills/codex_composer/SKILL.md")}
    )

    assert result.status == "denied"
    assert result.denial_reason == "self_edit_requires_self_evolution_authority"
    assert (tmp_path / "skills" / "codex_composer" / "SKILL.md").read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_self_edit_denied_without_contract_or_lease(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    envelope = _self_edit_envelope(mission_contract_present=False, workspace_lease_present=False)
    result = kernel._dispatch_self_edit(
        envelope, {"patch": _skill_patch("skills/codex_composer/SKILL.md")}
    )

    assert result.status == "denied"
    assert result.denial_reason == "self_edit_requires_mission_contract_and_workspace_lease"


def test_self_edit_denied_for_evidence_only_external_worker(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    envelope = _self_edit_envelope(external_worker_authority="external_worker_evidence_only")
    result = kernel._dispatch_self_edit(
        envelope, {"patch": _skill_patch("skills/codex_composer/SKILL.md")}
    )

    assert result.status == "denied"
    assert result.denial_reason == "external_worker_evidence_only"


def test_own_skill_allowlist_rejects_target_one_directory_above(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    # 'skills/SKILL.md' sits one directory above 'skills/<agent_uid>/'
    sibling = tmp_path / "skills" / "SKILL.md"
    sibling.write_text("alpha\nbeta\n", encoding="utf-8")
    envelope = _self_edit_envelope()
    result = kernel._dispatch_self_edit(
        envelope, {"patch": _skill_patch("skills/SKILL.md")}
    )

    assert result.status == "denied"
    assert result.denial_reason == "self_edit_outside_own_skill_files"
    assert sibling.read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_dry_run_self_edit_validates_without_mutating(tmp_path):
    kernel = _kernel(tmp_path)
    target = _seed_skill_file(tmp_path)
    envelope = _self_edit_envelope(
        mutation_mode="dry_run",
        sandbox_policy={"mutation_mode": "dry_run"},
    )
    result = kernel._dispatch_self_edit(
        envelope, {"patch": _skill_patch("skills/codex_composer/SKILL.md")}
    )

    assert result.status == "completed"
    assert result.output["dry_run"] is True
    assert result.output["files_changed"] == ["skills/codex_composer/SKILL.md"]
    assert result.output["delegated_to"] == "apply_patch"
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


def test_live_apply_self_edit_mutates_creates_bak_and_records_lesson(tmp_path):
    kernel = _kernel(tmp_path)
    target = _seed_skill_file(tmp_path)
    result = kernel.run(_self_edit_envelope())

    assert result.status == "completed"
    assert result.did_execute is True
    tool_result = result.tool_results[0]
    assert tool_result.tool_name == "self_edit"
    assert tool_result.status == "completed"
    assert tool_result.output["mutation_mode"] == "apply"
    assert tool_result.output["applied"] is True
    assert tool_result.output["rollback_available"] is True
    assert tool_result.output["delegated_to"] == "apply_patch"
    assert target.read_text(encoding="utf-8") == "alpha\ngamma\n"
    assert (tmp_path / "skills" / "codex_composer" / "SKILL.md.bak").read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert result.runtime_truth_packet["mutation_truth"]["dry_run_only"] is False

    store = _lesson_store(tmp_path)
    namespace = "agent:codex_composer:lessons"
    ledger_ok, errors = store.verify_lesson_ledger(namespace)
    assert ledger_ok, errors
    rows = store.lessons(namespace)
    assert len(rows) == 1
    assert rows[0].provenance["kind"] == "self_edit"
    assert "skills/codex_composer/SKILL.md" in rows[0].provenance["files_changed"]
    assert rows[0].run_id == result.run_id
    assert (
        "self_edit_mutation_limited_to_own_skill_files_via_apply_patch_adapter"
        in result.proof_ledger_entry.unsupported_claims
    )


def test_two_self_edits_chain_lessons_and_keep_ledgers_green(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)

    first = kernel.run(_self_edit_envelope())
    assert first.tool_results[0].status == "completed"
    # remove the .bak so the second live-apply can write a fresh rollback backup
    (tmp_path / "skills" / "codex_composer" / "SKILL.md.bak").unlink()

    second = kernel.run(
        _self_edit_envelope(patch=_skill_patch("skills/codex_composer/SKILL.md", before="gamma", after="delta"))
    )
    assert second.tool_results[0].status == "completed"
    assert (tmp_path / "skills" / "codex_composer" / "SKILL.md").read_text(encoding="utf-8") == "alpha\ndelta\n"

    store = _lesson_store(tmp_path)
    namespace = "agent:codex_composer:lessons"
    rows = store.lessons(namespace)
    assert len(rows) == 2
    assert rows[1].previous_entry_hash == rows[0].entry_hash
    assert rows[1].ledger_sequence == 2
    ledger_ok, errors = store.verify_lesson_ledger(namespace)
    assert ledger_ok, errors

    proof_ok, proof_errors = kernel.store.verify_proof_ledger()
    assert proof_ok, proof_errors
    second_entry = second.proof_ledger_entry
    assert second_entry.previous_entry_hash == first.proof_ledger_entry.entry_hash


def test_replay_integrity_ok_after_live_self_edit(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    result = kernel.run(_self_edit_envelope())

    assert result.replay_ref["integrity_ok"] is True
    replay = kernel.store.replay_run(result.run_id)
    assert replay.integrity_ok is True


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_agent_a_cannot_self_edit_agent_b_skill_files(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path, agent_uid="agent_a")
    victim = _seed_skill_file(tmp_path, agent_uid="agent_b")
    envelope = _self_edit_envelope(
        agent_uid="agent_a",
        patch=_skill_patch("skills/agent_b/SKILL.md"),
    )
    result = kernel.run(envelope)

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "self_edit_outside_own_skill_files"
    assert victim.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert not (tmp_path / "skills" / "agent_b" / "SKILL.md.bak").exists()
    assert _lesson_store(tmp_path).lessons("agent:agent_a:lessons") == []


def test_self_edit_cannot_reach_kernel_core_even_if_patch_header_points_there(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    # plant a fake core file inside the sandbox workspace so the path resolves
    core_dir = tmp_path / "dharma_swarm" / "operator_core"
    core_dir.mkdir(parents=True, exist_ok=True)
    core = core_dir / "living_agent_kernel.py"
    core.write_text("alpha\nbeta\n", encoding="utf-8")
    envelope = _self_edit_envelope(
        patch=_skill_patch("dharma_swarm/operator_core/living_agent_kernel.py")
    )
    result = kernel.run(envelope)

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "self_edit_outside_own_skill_files"
    assert core.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert not core.with_suffix(".py.bak").exists()


def test_path_traversal_diff_target_rejected_writing_nothing(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    outside_dir = tmp_path / "dharma_swarm" / "operator_core"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside = outside_dir / "x.py"
    outside.write_text("alpha\nbeta\n", encoding="utf-8")
    traversal = "skills/codex_composer/../../dharma_swarm/operator_core/x.py"
    envelope = _self_edit_envelope(patch=_skill_patch(traversal))
    result = kernel.run(envelope)

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason in {
        "self_edit_target_path_unsafe",
        "self_edit_outside_own_skill_files",
    }
    assert outside.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert _lesson_store(tmp_path).lessons("agent:codex_composer:lessons") == []


def test_live_apply_without_rollback_receipt_denied_by_inherited_sandbox_gate(tmp_path):
    kernel = _kernel(tmp_path)
    target = _seed_skill_file(tmp_path)
    envelope = _self_edit_envelope(
        sandbox_policy={"mutation_mode": "apply", "allow_write_tool_execution": True},
    )
    result = kernel.run(envelope)

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "apply_patch_live_apply_requires_rollback_receipt"
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert not (tmp_path / "skills" / "codex_composer" / "SKILL.md.bak").exists()


def test_full_run_self_edit_visible_only_under_self_evolution_allow(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    result = kernel.run(_self_edit_envelope())
    assert "self_edit" in result.tool_plan.visible_tools

    denied = kernel.run(_self_edit_envelope(work_kind=WorkKind.CODE_WRITE))
    assert "self_edit" not in denied.tool_plan.visible_tools
    assert denied.tool_plan.denial_reasons["self_edit"] == "self_edit_requires_self_evolution_authority"


def test_tampered_self_edit_lesson_fails_lesson_ledger_but_proof_stays_consistent(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_skill_file(tmp_path)
    first = kernel.run(_self_edit_envelope())

    store = _lesson_store(tmp_path)
    namespace = "agent:codex_composer:lessons"
    path = store.namespace_path(namespace)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["delta_text"] = "tampered self_edit body"
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    ledger_ok, errors = store.verify_lesson_ledger(namespace)
    assert ledger_ok is False
    assert errors

    proof_ok, proof_errors = kernel.store.verify_proof_ledger()
    assert proof_ok, proof_errors
    replay = kernel.store.replay_run(first.run_id)
    assert replay.integrity_ok is True
