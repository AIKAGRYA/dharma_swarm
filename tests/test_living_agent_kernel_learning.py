from __future__ import annotations

import json

from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkAdmission,
    WorkKind,
)
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
from dharma_swarm.operator_core.living_agent_kernel_learning import (
    LEARNING_DELTA_CAP,
    commit_learning,
)
from dharma_swarm.operator_core.living_agent_kernel_lessons import KernelLessonStore
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash


def _kernel(tmp_path) -> LivingAgentKernel:
    return LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
    )


def _lesson_store(tmp_path) -> KernelLessonStore:
    return KernelLessonStore(tmp_path / "kernel")


def _allow() -> GovernedWorkAdmission:
    return GovernedWorkAdmission(decision="allow")


def _learn_envelope(
    *,
    agent_uid: str = "codex_composer",
    proposed_learning_delta: str = "learned: ledger-grounded intent magnets generalize",
    write_namespaces: list[str] | None = None,
    learning_namespaces: list[str] | None = None,
    work_kind: WorkKind = WorkKind.READ_ONLY,
    mission_contract_present: bool = False,
    workspace_lease_present: bool = False,
    risk_tier: str = "Q1",
    telos_decision: str = "allow",
    with_memory_read: bool = False,
    run_id: str | None = None,
) -> AgentRunEnvelope:
    declared = write_namespaces if write_namespaces is not None else [f"agent:{agent_uid}:lessons"]
    metadata: dict[str, object] = {}
    if learning_namespaces is not None:
        metadata["learning_namespaces"] = list(learning_namespaces)
    kwargs: dict[str, object] = {}
    if run_id is not None:
        kwargs["run_id"] = run_id
    tool_request = ToolRequest()
    if with_memory_read:
        tool_request = ToolRequest(
            requested_tools=["memory_read"],
            tool_calls=[{"name": "memory_read", "arguments": {"namespace": f"agent:{agent_uid}:working"}}],
        )
    return AgentRunEnvelope(
        agent_uid=agent_uid,
        task=KernelTask(text="Reflect and metabolize a lesson at run-close"),
        trigger=TriggerEnvelope(
            source="persistent_self_wake",
            mission_id="mission-learn",
            task_id="task-learn",
            correlation_id="corr-learn",
            parent_run_id="parent-run",
        ),
        authority=AuthorityPassport(
            work_kind=work_kind,
            risk_tier=risk_tier,
            telos_decision=telos_decision,
            mission_contract_present=mission_contract_present,
            workspace_lease_present=workspace_lease_present,
        ),
        memory=MemoryPlan(
            read_namespaces=[f"agent:{agent_uid}:working"],
            write_namespaces=list(declared),
            proposed_learning_delta=proposed_learning_delta,
            metadata=metadata,
        ),
        tool_request=tool_request,
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_learning.py"],
        ),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_commit_learning_appends_exactly_one_row_for_completed_run(tmp_path):
    store = _lesson_store(tmp_path)
    envelope = _learn_envelope(
        proposed_learning_delta="X",
        write_namespaces=["agent:a:lessons"],
        agent_uid="a",
    )
    outcome = commit_learning(store, envelope, _allow(), "completed")

    assert outcome.wrote is True
    assert outcome.receipt is not None
    assert outcome.receipt.namespace == "agent:a:lessons"
    rows = store.lessons("agent:a:lessons")
    assert len(rows) == 1
    assert rows[0].delta_text == "X"
    assert rows[0].run_id == envelope.run_id
    assert rows[0].provenance["executor"] == "automatic_learn"


def test_commit_learning_returns_none_for_empty_delta(tmp_path):
    store = _lesson_store(tmp_path)
    envelope = _learn_envelope(proposed_learning_delta="", write_namespaces=["agent:a:lessons"], agent_uid="a")
    outcome = commit_learning(store, envelope, _allow(), "completed")

    assert outcome.wrote is False
    assert outcome.skipped_reason == "empty_learning_delta"
    assert not store.namespace_path("agent:a:lessons").exists()


def test_commit_learning_returns_none_for_blocked_or_failed_status(tmp_path):
    store = _lesson_store(tmp_path)
    envelope = _learn_envelope(proposed_learning_delta="something", agent_uid="a", write_namespaces=["agent:a:lessons"])

    failed = commit_learning(store, envelope, _allow(), "failed")
    assert failed.wrote is False
    blocked = commit_learning(store, envelope, GovernedWorkAdmission(decision="block"), "completed")
    assert blocked.wrote is False
    assert not store.namespace_path("agent:a:lessons").exists()


def test_commit_learning_refuses_undeclared_namespace(tmp_path):
    store = _lesson_store(tmp_path)
    envelope = _learn_envelope(
        proposed_learning_delta="secret exfil",
        agent_uid="a",
        write_namespaces=["agent:a:lessons"],
        learning_namespaces=["agent:b:secrets"],
    )
    outcome = commit_learning(store, envelope, _allow(), "completed")

    assert outcome.wrote is False
    assert len(outcome.refusals) == 1
    assert outcome.refusals[0].namespace == "agent:b:secrets"
    assert outcome.refusals[0].reason == "namespace_not_in_write_namespaces"
    assert not store.namespace_path("agent:b:secrets").exists()


def test_learning_ledger_chain_of_three_verifies_and_tamper_detected(tmp_path):
    store = _lesson_store(tmp_path)
    namespace = "agent:a:lessons"
    for index in range(3):
        envelope = _learn_envelope(
            proposed_learning_delta=f"lesson {index}",
            agent_uid="a",
            write_namespaces=[namespace],
            run_id=f"run-{index}",
        )
        outcome = commit_learning(store, envelope, _allow(), "completed")
        assert outcome.wrote is True

    rows = store.lessons(namespace)
    assert len(rows) == 3
    assert rows[1].previous_entry_hash == rows[0].entry_hash
    assert rows[2].previous_entry_hash == rows[1].entry_hash
    ok, errors = store.verify_lesson_ledger(namespace)
    assert ok, errors

    path = store.namespace_path(namespace)
    raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    raw[1]["delta_text"] = "tampered"
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in raw),
        encoding="utf-8",
    )
    bad_ok, bad_errors = store.verify_lesson_ledger(namespace)
    assert bad_ok is False
    assert bad_errors


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


def test_full_run_consumes_proposed_learning_delta_and_drops_false_claim(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _learn_envelope(
        agent_uid="learner",
        write_namespaces=["agent:learner:lessons"],
        proposed_learning_delta="the namespace ledger is the living loop",
        with_memory_read=True,
    )
    result = kernel.run(envelope)

    # The memory_read executed, so the false 'projection only' claim was added...
    assert any(r.tool_name == "memory_read" and r.status == "completed" for r in result.tool_results)

    learning_refs = [ref for ref in result.event_refs if ref.get("kind") == "kernel_learning"]
    assert len(learning_refs) == 1
    assert learning_refs[0]["namespace"] == "agent:learner:lessons"
    assert learning_refs[0]["run_id"] == result.run_id

    store = _lesson_store(tmp_path)
    rows = store.lessons("agent:learner:lessons")
    assert len(rows) == 1
    assert rows[0].delta_text == "the namespace ledger is the living loop"

    claims = result.proof_ledger_entry.unsupported_claims
    # ...and then DROPPED because a real learning record was written.
    assert "memory_read_projection_only" not in claims
    assert "kernel_learning_limited_to_agent_lessons_ledger" in claims
    assert result.replay_ref["integrity_ok"] is True


def test_empty_delta_run_writes_no_lessons_and_keeps_default_claims(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _learn_envelope(
        agent_uid="quiet",
        write_namespaces=["agent:quiet:lessons"],
        proposed_learning_delta="",
    )
    result = kernel.run(envelope)

    assert [ref for ref in result.event_refs if ref.get("kind") == "kernel_learning"] == []
    store = _lesson_store(tmp_path)
    assert not store.namespace_path("agent:quiet:lessons").exists()
    assert "kernel_learning_limited_to_agent_lessons_ledger" not in result.proof_ledger_entry.unsupported_claims


def test_two_wakes_accumulate_lessons_chained_across_runs(tmp_path):
    kernel = _kernel(tmp_path)
    namespace = "agent:learner:lessons"
    first = kernel.run(
        _learn_envelope(agent_uid="learner", write_namespaces=[namespace], proposed_learning_delta="wake one lesson")
    )
    second = kernel.run(
        _learn_envelope(agent_uid="learner", write_namespaces=[namespace], proposed_learning_delta="wake two lesson")
    )

    store = _lesson_store(tmp_path)
    rows = store.lessons(namespace)
    assert len(rows) == 2
    assert rows[0].run_id == first.run_id
    assert rows[1].run_id == second.run_id
    assert rows[1].previous_entry_hash == rows[0].entry_hash
    assert rows[1].ledger_sequence == 2
    ok, errors = store.verify_lesson_ledger(namespace)
    assert ok, errors


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_oversized_delta_is_truncated_not_rejected_and_hash_matches(tmp_path):
    store = _lesson_store(tmp_path)
    big = "z" * (LEARNING_DELTA_CAP + 500)
    envelope = _learn_envelope(agent_uid="a", write_namespaces=["agent:a:lessons"], proposed_learning_delta=big)
    outcome = commit_learning(store, envelope, _allow(), "completed")

    assert outcome.wrote is True
    rows = store.lessons("agent:a:lessons")
    assert len(rows) == 1
    assert len(rows[0].delta_text) == LEARNING_DELTA_CAP
    assert rows[0].delta_hash == stable_payload_hash("z" * LEARNING_DELTA_CAP)
    assert rows[0].provenance["truncated"] is True


def test_duplicate_delta_same_run_and_namespace_dedupes_to_one_row(tmp_path):
    store = _lesson_store(tmp_path)
    envelope = _learn_envelope(
        agent_uid="a",
        write_namespaces=["agent:a:lessons"],
        proposed_learning_delta="repeated insight",
        run_id="dup-run",
    )
    first = commit_learning(store, envelope, _allow(), "completed")
    second = commit_learning(store, envelope, _allow(), "completed")

    assert first.wrote is True
    assert second.wrote is False
    assert second.skipped_reason == "duplicate_delta"
    assert len(store.lessons("agent:a:lessons")) == 1


def test_run_refusing_cross_namespace_route_writes_nothing_and_audits(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _learn_envelope(
        agent_uid="a",
        write_namespaces=["agent:a:lessons"],
        learning_namespaces=["agent:b:secrets"],
        proposed_learning_delta="cross-namespace poison",
    )
    result = kernel.run(envelope)

    assert [ref for ref in result.event_refs if ref.get("kind") == "kernel_learning"] == []
    store = _lesson_store(tmp_path)
    assert not store.namespace_path("agent:b:secrets").exists()
    assert not store.namespace_path("agent:a:lessons").exists()

    replay = kernel.store.replay_run(result.run_id)
    refusal_events = [
        evt
        for evt in replay.events
        if evt.get("payload", {}).get("gate") == "living_agent_kernel.commit_learning"
    ]
    assert refusal_events, "expected an audit event recording the refusal"
    assert refusal_events[0]["payload"]["reason"] == "namespace_not_in_write_namespaces"


def test_admission_blocked_run_with_delta_writes_no_lesson(tmp_path):
    kernel = _kernel(tmp_path)
    # A telos block forces the admission to block; the delta must NOT be learned.
    envelope = _learn_envelope(
        agent_uid="a",
        write_namespaces=["agent:a:lessons"],
        proposed_learning_delta="learning on un-admitted work",
        telos_decision="block",
    )
    result = kernel.run(envelope)

    assert result.admission.decision == "block"
    store = _lesson_store(tmp_path)
    assert not store.namespace_path("agent:a:lessons").exists()
    assert [ref for ref in result.event_refs if ref.get("kind") == "kernel_learning"] == []


# ---------------------------------------------------------------------------
# tamper
# ---------------------------------------------------------------------------


def test_byte_edit_breaks_entry_hash_and_chain_continuity(tmp_path):
    store = _lesson_store(tmp_path)
    namespace = "agent:a:lessons"
    for index in range(3):
        commit_learning(
            store,
            _learn_envelope(
                agent_uid="a",
                write_namespaces=[namespace],
                proposed_learning_delta=f"chain lesson {index}",
                run_id=f"r-{index}",
            ),
            _allow(),
            "completed",
        )

    path = store.namespace_path(namespace)
    lines = path.read_text(encoding="utf-8").splitlines()
    # Hand-edit a byte of the FIRST record's sealed entry_hash. This both
    # fails the record's own self-check AND breaks the chain for all rows
    # after it (their previous_entry_hash no longer matches the new value).
    record = json.loads(lines[0])
    record["entry_hash"] = record["entry_hash"][:-1] + ("0" if record["entry_hash"][-1] != "0" else "1")
    lines[0] = json.dumps(record, sort_keys=True, ensure_ascii=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, errors = store.verify_lesson_ledger(namespace)
    assert ok is False
    assert any("line 1" in err and "entry_hash" in err for err in errors)
    # Continuity break propagates to the next row.
    assert any("line 2" in err and "previous_entry_hash" in err for err in errors)
