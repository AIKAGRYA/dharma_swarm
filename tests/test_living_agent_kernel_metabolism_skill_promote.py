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
from dharma_swarm.operator_core.living_agent_kernel_promotion import KernelPromotionStore


def _kernel(tmp_path) -> LivingAgentKernel:
    return LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
    )


def _promotion_store(tmp_path) -> KernelPromotionStore:
    return KernelPromotionStore(tmp_path / "kernel")


def _lesson_store(tmp_path) -> KernelLessonStore:
    return KernelLessonStore(tmp_path / "kernel")


def _seed_promotion(
    tmp_path,
    *,
    agent_uid: str = "self_evolving_agent",
    level: str = "worker",
    status: str = "promoted",
    evidence_refs: list[dict] | None = None,
    allowed_work_kinds: list[str] | None = None,
    expires_at: str = "",
):
    refs = evidence_refs if evidence_refs is not None else [{"kind": "operator_review", "path": "review.json"}]
    return _promotion_store(tmp_path).append_promotion(
        agent_uid=agent_uid,
        level=level,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        allowed_sources=["persistent_self_wake"],
        allowed_tools=["skill_promote"],
        allowed_work_kinds=allowed_work_kinds or ["self_evolution", "promotion"],  # type: ignore[arg-type]
        max_lease_seconds=60,
        expires_at=expires_at,
        reviewer="operator",
        reason="operator-seeded promotion",
        evidence_refs=refs,
        now="2026-06-06T00:00:00Z",
    )


def _skill_promote_envelope(
    *,
    agent_uid: str = "self_evolving_agent",
    work_kind: WorkKind = WorkKind.SELF_EVOLUTION,
    mission_contract_present: bool = True,
    workspace_lease_present: bool = True,
    external_worker_authority: str = "",
    level: str = "worker",
) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid=agent_uid,
        task=KernelTask(text="Promote myself only against operator evidence"),
        trigger=TriggerEnvelope(
            source="persistent_self_wake",
            mission_id="mission-promo",
            task_id="task-promo",
            correlation_id="corr-promo",
            parent_run_id="parent-run",
        ),
        authority=AuthorityPassport(
            work_kind=work_kind,
            risk_tier="Q2",
            mutation_budget_remaining=3,
            mission_contract_present=mission_contract_present,
            workspace_lease_present=workspace_lease_present,
            external_worker_authority=external_worker_authority,
        ),
        memory=MemoryPlan(
            read_namespaces=[f"agent:{agent_uid}:working"],
            write_namespaces=[f"agent:{agent_uid}:lessons"],
        ),
        tool_request=ToolRequest(
            requested_tools=["skill_promote"],
            tool_calls=[{"name": "skill_promote", "arguments": {"level": level, "source": "persistent_self_wake"}}],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_metabolism_skill_promote.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_dispatch_skill_promote_denies_when_no_receipt_and_writes_nothing(tmp_path):
    kernel = _kernel(tmp_path)
    envelope = _skill_promote_envelope()
    result = kernel._dispatch_skill_promote(envelope, {"level": "worker", "source": "persistent_self_wake"})

    assert result.status == "denied"
    assert result.denial_reason == "skill_promote_requires_evidence_backed_promotion"
    assert "promotion_receipt_missing" in result.error
    assert _promotion_store(tmp_path).promotions() == []
    assert _lesson_store(tmp_path).lessons("agent:self_evolving_agent:lessons") == []


def test_dispatch_skill_promote_denies_when_evidence_refs_empty(tmp_path):
    _seed_promotion(tmp_path, evidence_refs=[])
    kernel = _kernel(tmp_path)
    envelope = _skill_promote_envelope()
    result = kernel._dispatch_skill_promote(envelope, {"level": "worker", "source": "persistent_self_wake"})

    assert result.status == "denied"
    assert result.denial_reason == "skill_promote_requires_evidence_backed_promotion"
    # the seed remains the only row — no promotion-applied row written
    assert len(_promotion_store(tmp_path).promotions()) == 1
    assert _lesson_store(tmp_path).lessons("agent:self_evolving_agent:lessons") == []


def test_dispatch_skill_promote_denies_under_non_self_evolution_work_kinds(tmp_path):
    _seed_promotion(tmp_path)
    kernel = _kernel(tmp_path)
    for kind in (WorkKind.READ_ONLY, WorkKind.CODE_WRITE, WorkKind.LONG_RUNNING):
        envelope = _skill_promote_envelope(work_kind=kind)
        result = kernel._dispatch_skill_promote(envelope, {"level": "worker"})
        assert result.status == "denied"
        assert result.denial_reason == "skill_promote_requires_self_evolution_or_promotion_authority"
    # only the operator seed exists
    assert len(_promotion_store(tmp_path).promotions()) == 1


def test_skill_promote_invisible_and_denied_in_plan_under_code_write(tmp_path):
    _seed_promotion(tmp_path)
    kernel = _kernel(tmp_path)
    envelope = _skill_promote_envelope(work_kind=WorkKind.CODE_WRITE)
    result = kernel.run(envelope)

    assert "skill_promote" not in result.tool_plan.visible_tools
    assert result.tool_results[0].status == "denied"


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


def test_full_run_evidence_backed_skill_promote_completes_and_ledgers_green(tmp_path):
    seed = _seed_promotion(tmp_path)
    kernel = _kernel(tmp_path)
    result = kernel.run(_skill_promote_envelope())

    assert result.status == "completed"
    assert result.did_execute is True
    tool_result = result.tool_results[0]
    assert tool_result.status == "completed"
    assert tool_result.tool_name == "skill_promote"
    assert tool_result.output["source_receipt_hash"] == seed.record_hash
    assert tool_result.output["promotion_record_hash"].startswith("sha256:")

    store = _promotion_store(tmp_path)
    promotions = store.promotions()
    assert len(promotions) == 2  # operator seed + kernel-applied row
    applied = promotions[-1]
    assert applied.reviewer == "living_agent_kernel"
    assert applied.metadata["applied_via"] == "skill_promote"
    assert applied.metadata["source_receipt_hash"] == seed.record_hash
    ledger_ok, errors = store.verify_promotion_ledger()
    assert ledger_ok, errors


def test_full_run_records_tamper_evident_lesson_with_run_provenance(tmp_path):
    _seed_promotion(tmp_path)
    kernel = _kernel(tmp_path)
    result = kernel.run(_skill_promote_envelope())

    lessons = _lesson_store(tmp_path)
    namespace = "agent:self_evolving_agent:lessons"
    rows = lessons.lessons(namespace)
    assert len(rows) == 1
    row = rows[0]
    assert row.run_id == result.run_id
    assert row.provenance["kind"] == "skill_promote"
    assert row.provenance["correlation_id"] == "corr-promo"
    assert row.provenance["promotion_level"] == "worker"
    ledger_ok, errors = lessons.verify_lesson_ledger(namespace)
    assert ledger_ok, errors


def test_proof_ledger_and_replay_remain_consistent_after_skill_promote(tmp_path):
    _seed_promotion(tmp_path)
    kernel = _kernel(tmp_path)
    result = kernel.run(_skill_promote_envelope())

    entry = result.proof_ledger_entry
    assert "skill_promote_applies_pre_existing_evidence_backed_promotion_only" in entry.unsupported_claims
    assert entry.entry_hash.startswith("sha256:")
    assert result.replay_ref["integrity_ok"] is True

    proof_ok, proof_errors = kernel.store.verify_proof_ledger()
    assert proof_ok, proof_errors
    replay = kernel.store.replay_run(result.run_id)
    assert replay.integrity_ok is True


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_agent_cannot_manufacture_promotion_mid_run_without_pre_existing_receipt(tmp_path):
    # No operator seed: the agent tries to self-promote from nothing.
    kernel = _kernel(tmp_path)
    result = kernel.run(_skill_promote_envelope())

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].denial_reason == "skill_promote_requires_evidence_backed_promotion"
    # zero writes: no promotion rows, no lessons
    assert _promotion_store(tmp_path).promotions() == []
    assert _lesson_store(tmp_path).lessons("agent:self_evolving_agent:lessons") == []


def test_forged_promoted_receipt_with_no_evidence_is_rejected_at_admission_layer(tmp_path):
    # Defense in depth: a 'promoted' receipt with empty evidence_refs is rejected
    # by the evidence check, not silently honored by the tool layer.
    _seed_promotion(tmp_path, evidence_refs=[])
    kernel = _kernel(tmp_path)
    envelope = _skill_promote_envelope()
    result = kernel.run(envelope)

    tool_result = result.tool_results[0]
    assert tool_result.status == "denied"
    assert tool_result.denial_reason == "skill_promote_requires_evidence_backed_promotion"
    # still only the seed row; nothing appended
    assert len(_promotion_store(tmp_path).promotions()) == 1
    assert _lesson_store(tmp_path).lessons("agent:self_evolving_agent:lessons") == []


def test_revoked_receipt_is_denied_with_underlying_admission_reason(tmp_path):
    _seed_promotion(tmp_path, status="revoked")
    kernel = _kernel(tmp_path)
    envelope = _skill_promote_envelope()
    result = kernel.run(envelope)

    tool_result = result.tool_results[0]
    assert tool_result.status == "denied"
    assert tool_result.denial_reason == "skill_promote_requires_evidence_backed_promotion"
    assert "promotion_revoked" in tool_result.error
    assert len(_promotion_store(tmp_path).promotions()) == 1


def test_insufficient_level_request_is_denied(tmp_path):
    _seed_promotion(tmp_path, level="observer")
    kernel = _kernel(tmp_path)
    envelope = _skill_promote_envelope(level="executor")
    result = kernel.run(envelope)

    tool_result = result.tool_results[0]
    assert tool_result.status == "denied"
    assert tool_result.denial_reason == "skill_promote_requires_evidence_backed_promotion"
    assert "promotion_level_insufficient" in tool_result.error
    assert len(_promotion_store(tmp_path).promotions()) == 1


def test_expired_receipt_is_denied(tmp_path):
    _seed_promotion(tmp_path, expires_at="2020-01-01T00:00:00Z")
    kernel = _kernel(tmp_path)
    result = kernel.run(_skill_promote_envelope())

    tool_result = result.tool_results[0]
    assert tool_result.status == "denied"
    assert tool_result.denial_reason == "skill_promote_requires_evidence_backed_promotion"
    assert "promotion_expired" in tool_result.error
    assert len(_promotion_store(tmp_path).promotions()) == 1


def test_three_ledgers_are_not_co_forgeable(tmp_path):
    _seed_promotion(tmp_path)
    kernel = _kernel(tmp_path)
    result = kernel.run(_skill_promote_envelope())
    assert result.tool_results[0].status == "completed"

    promo_store = _promotion_store(tmp_path)
    lessons = _lesson_store(tmp_path)
    namespace = "agent:self_evolving_agent:lessons"

    # all three independent ledgers are green to start
    assert promo_store.verify_promotion_ledger()[0] is True
    assert lessons.verify_lesson_ledger(namespace)[0] is True
    assert kernel.store.verify_proof_ledger()[0] is True

    # tamper ONLY the promotion ledger on disk
    promo_path = promo_store.promotion_path
    rows = [json.loads(line) for line in promo_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[-1]["level"] = "provider_executor"
    promo_path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    promo_ok, promo_errors = promo_store.verify_promotion_ledger()
    assert promo_ok is False
    assert promo_errors
    # the other two ledgers remain independently green (non-co-forgeable)
    assert lessons.verify_lesson_ledger(namespace)[0] is True
    assert kernel.store.verify_proof_ledger()[0] is True
    assert kernel.store.replay_run(result.run_id).integrity_ok is True
