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


def _memory_write_envelope(
    *,
    agent_uid: str = "codex_composer",
    work_kind: WorkKind = WorkKind.CODE_WRITE,
    mission_contract_present: bool = True,
    workspace_lease_present: bool = True,
    write_namespaces: list[str] | None = None,
    namespace: str | None = None,
    delta: str | None = "learned: prefer ledger-grounded intent magnets",
    proposed_learning_delta: str = "",
    external_worker_authority: str = "",
) -> AgentRunEnvelope:
    declared = write_namespaces if write_namespaces is not None else [f"agent:{agent_uid}:lessons"]
    ns = namespace if namespace is not None else f"agent:{agent_uid}:lessons"
    arguments: dict[str, object] = {"namespace": ns}
    if delta is not None:
        arguments["delta"] = delta
    return AgentRunEnvelope(
        agent_uid=agent_uid,
        task=KernelTask(text="Metabolize a lesson into my own ledger"),
        trigger=TriggerEnvelope(
            source="persistent_self_wake",
            mission_id="mission-meta",
            task_id="task-meta",
            correlation_id="corr-meta",
            parent_run_id="parent-run",
        ),
        authority=AuthorityPassport(
            work_kind=work_kind,
            risk_tier="Q2",
            mission_contract_present=mission_contract_present,
            workspace_lease_present=workspace_lease_present,
            external_worker_authority=external_worker_authority,
        ),
        memory=MemoryPlan(
            read_namespaces=[f"agent:{agent_uid}:working"],
            write_namespaces=list(declared),
            proposed_learning_delta=proposed_learning_delta,
        ),
        tool_request=ToolRequest(
            requested_tools=["memory_write"],
            tool_calls=[{"name": "memory_write", "arguments": arguments}],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_metabolism_memory_write.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_memory_write_in_write_tools_invisible_then_denied_without_contract(tmp_path):
    envelope = _memory_write_envelope(
        mission_contract_present=False,
        workspace_lease_present=False,
    )
    result = _kernel(tmp_path).run(envelope)

    assert result.status == "review"
    assert result.admission.decision == "review"
    assert result.tool_plan.denial_reasons["memory_write"] == "authority_decision_review"
    assert result.tool_results[0].denial_reason == "authority_decision_review"


def test_dispatch_memory_write_denies_read_only_authority(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _memory_write_envelope(work_kind=WorkKind.READ_ONLY)
    result = kernel._dispatch_memory_write(envelope, {"namespace": "agent:codex_composer:lessons", "delta": "x"})

    assert result.status == "denied"
    assert result.denial_reason == "memory_write_requires_code_write_authority"


def test_dispatch_memory_write_denies_out_of_scope_namespace_and_writes_nothing(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _memory_write_envelope(write_namespaces=["agent:codex_composer:lessons"])
    out_of_scope = "agent:codex_composer:secrets"
    result = kernel._dispatch_memory_write(envelope, {"namespace": out_of_scope, "delta": "x"})

    assert result.status == "denied"
    assert result.denial_reason == "memory_write_namespace_not_declared"
    store = _lesson_store(tmp_path)
    assert not store.namespace_path(out_of_scope).exists()


def test_dispatch_memory_write_falls_back_to_proposed_learning_delta(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _memory_write_envelope(
        delta=None,
        proposed_learning_delta="fallback: the namespace ledger is the living loop",
    )
    result = kernel._dispatch_memory_write(envelope, {"namespace": "agent:codex_composer:lessons"})

    assert result.status == "completed"
    rows = _lesson_store(tmp_path).lessons("agent:codex_composer:lessons")
    assert len(rows) == 1
    assert rows[0].delta_text == "fallback: the namespace ledger is the living loop"


def test_dispatch_memory_write_empty_fallback_is_typed_failure_not_silent_success(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _memory_write_envelope(delta=None, proposed_learning_delta="")
    result = kernel._dispatch_memory_write(envelope, {"namespace": "agent:codex_composer:lessons"})

    assert result.status == "failed"
    assert result.error == "memory_write_requires_delta_or_proposed_learning_delta"
    assert not _lesson_store(tmp_path).namespace_path("agent:codex_composer:lessons").exists()


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


def test_full_run_authorized_memory_write_appends_one_row_and_seals_receipt(tmp_path):
    kernel = _kernel(tmp_path)
    result = kernel.run(_memory_write_envelope())

    assert result.status == "completed"
    assert result.did_execute is True
    tool_result = result.tool_results[0]
    assert tool_result.status == "completed"
    assert tool_result.tool_name == "memory_write"
    assert tool_result.output["receipt_hash"].startswith("sha256:")
    assert tool_result.receipt_hash.startswith("sha256:")

    store = _lesson_store(tmp_path)
    ledger_ok, errors = store.verify_lesson_ledger("agent:codex_composer:lessons")
    assert ledger_ok, errors
    rows = store.lessons("agent:codex_composer:lessons")
    assert len(rows) == 1
    assert rows[0].run_id == result.run_id
    assert rows[0].provenance["source"] == "persistent_self_wake"
    assert rows[0].provenance["mission_id"] == "mission-meta"


def test_run_finished_proof_marks_mutation_and_hash_chains(tmp_path):
    kernel = _kernel(tmp_path)
    result = kernel.run(_memory_write_envelope())

    entry = result.proof_ledger_entry
    assert "memory_write_mutation_limited_to_agent_lessons_ledger" in entry.unsupported_claims
    assert entry.entry_hash.startswith("sha256:")
    assert result.replay_ref["integrity_ok"] is True


def test_two_consecutive_runs_chain_both_proof_and_lesson_ledgers(tmp_path):
    kernel = _kernel(tmp_path)
    first = kernel.run(_memory_write_envelope(delta="lesson one"))
    second = kernel.run(_memory_write_envelope(delta="lesson two"))

    store = _lesson_store(tmp_path)
    rows = store.lessons("agent:codex_composer:lessons")
    assert len(rows) == 2
    assert rows[0].entry_hash.startswith("sha256:")
    assert rows[1].previous_entry_hash == rows[0].entry_hash
    assert rows[1].ledger_sequence == 2
    ledger_ok, errors = store.verify_lesson_ledger("agent:codex_composer:lessons")
    assert ledger_ok, errors

    second_entry = second.proof_ledger_entry
    assert second_entry.previous_entry_hash == first.proof_ledger_entry.entry_hash
    assert second.replay_ref["integrity_ok"] is True


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_cannot_write_into_victim_namespace_via_forged_arg(tmp_path):
    kernel = _kernel(tmp_path)
    victim_ns = "agent:victim:lessons"
    envelope = _memory_write_envelope(
        agent_uid="attacker",
        write_namespaces=["agent:attacker:lessons"],
        namespace=victim_ns,
    )
    result = kernel.run(envelope)

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "memory_write_namespace_not_declared"
    store = _lesson_store(tmp_path)
    assert not store.namespace_path(victim_ns).exists()
    assert store.lessons("agent:attacker:lessons") == []


def test_cannot_write_into_victim_namespace_even_if_attacker_declares_it(tmp_path):
    kernel = _kernel(tmp_path)
    victim_ns = "agent:victim:lessons"
    envelope = _memory_write_envelope(
        agent_uid="attacker",
        write_namespaces=[victim_ns],
        namespace=victim_ns,
        delta="cross-namespace poison",
    )
    result = kernel.run(envelope)

    assert result.tool_results[0].status == "completed"
    store = _lesson_store(tmp_path)
    victim_rows = store.lessons(victim_ns)
    assert len(victim_rows) == 1
    assert victim_rows[0].agent_uid == "attacker"


def test_path_traversal_namespace_is_denied_or_sandboxed(tmp_path):
    kernel = _kernel(tmp_path)
    traversal_ns = "agent:x:../../etc"
    declared_envelope = _memory_write_envelope(
        write_namespaces=[traversal_ns],
        namespace=traversal_ns,
        delta="traversal attempt",
    )
    result = kernel.run(declared_envelope)

    store = _lesson_store(tmp_path)
    lessons_root = store.lessons_dir.resolve()
    if result.tool_results[0].status == "completed":
        written = store.namespace_path(traversal_ns)
        assert written.resolve().parent == lessons_root
    for path in lessons_root.rglob("*.jsonl"):
        assert path.resolve().parent == lessons_root
    etc_dir = (tmp_path / "kernel").resolve()
    assert not (etc_dir / "etc").exists()


def test_tampered_lesson_row_fails_lesson_ledger_but_proof_ledger_stays_consistent(tmp_path):
    kernel = _kernel(tmp_path)
    first = kernel.run(_memory_write_envelope(delta="genuine lesson"))

    store = _lesson_store(tmp_path)
    namespace = "agent:codex_composer:lessons"
    path = store.namespace_path(namespace)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["delta_text"] = "tampered lesson body"
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
