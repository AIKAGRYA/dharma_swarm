from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import dharma_swarm.mission_control_auto_verifier as auto_module
from dharma_swarm.mission_control_auto_verifier import AutomaticCandidateVerifier
from dharma_swarm.mission_control_contract import MissionControlError, stable_id
from dharma_swarm.mission_control_evidence import (
    IndependentAcceptance,
    candidate_output_digest,
)
from dharma_swarm.mission_control_execution import (
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.mission_control_held_out_oracle import (
    G10EvidenceBundle,
    HeldOutOracleOutcome,
)
from dharma_swarm.mission_control_roster import CampaignAgentRoster, CampaignAgentSeat
from dharma_swarm.models import (
    AgentRole,
    LLMRequest,
    LLMResponse,
    ProviderType,
    TaskStatus,
)
from dharma_swarm.runtime_state import DelegationRun, RuntimeReceipt, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


MISSION = "automatic-verifier"
POLICY = "sha256:" + "a" * 64
PRODUCER_MODEL = "glm-5.2"
VERIFIER_MODEL = "nemotron-3-ultra"


class _Provider:
    def __init__(self, content: str = "") -> None:
        self.content = content or (
            '{"accepted":true,"rationale":"Exact candidate satisfies the policy.",'
            '"verdict":"ACCEPT"}'
        )
        self.calls: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return LLMResponse(
            content=self.content,
            model=VERIFIER_MODEL,
            provider=ProviderType.OLLAMA.value,
            usage={},
        )


class _UnusedLauncher:
    sandbox_evidence_sha256 = "sha256:" + "b" * 64

    async def launch(self, request):  # pragma: no cover - model path only
        raise AssertionError(f"held-out launcher was unexpectedly called: {request}")


@dataclass(frozen=True)
class _Snapshot:
    mission_id: str
    candidate_task_ids: tuple[str, ...]
    owner_executions: tuple[OwnerExecutionObservation, ...]
    cycle_sequence: int = 1


@dataclass
class _Stack:
    runtime: RuntimeStateStore
    board: TaskBoard
    roster: CampaignAgentRoster
    task_id: str
    observation: OwnerExecutionObservation
    snapshot: _Snapshot
    provider: _Provider
    verifier: AutomaticCandidateVerifier


def _roster(*, verifier_family: str = "nemotron") -> CampaignAgentRoster:
    now = datetime.now(timezone.utc)
    return CampaignAgentRoster(
        campaign_id=MISSION,
        objective_sha256="c" * 64,
        activation_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
        catalog_observed_at=now,
        catalog_models=(PRODUCER_MODEL, VERIFIER_MODEL),
        seats=(
            CampaignAgentSeat(
                "sadhana-glm",
                AgentRole.RESEARCHER,
                ProviderType.OLLAMA,
                PRODUCER_MODEL + ":cloud",
                "glm",
                "producer",
                "produce",
            ),
            CampaignAgentSeat(
                "sadhana-nemotron",
                AgentRole.VALIDATOR,
                ProviderType.OLLAMA,
                VERIFIER_MODEL + ":cloud",
                verifier_family,
                "verifier",
                "verify",
            ),
        ),
        manifest_sha256="d" * 64,
    )


async def _stack(
    tmp_path: Path,
    *,
    roster: CampaignAgentRoster | None = None,
    goal_id: str = "G01_EXACT_CANDIDATE",
) -> _Stack:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    board = TaskBoard(tmp_path / "tasks.db")
    await runtime.init_db()
    await board.init_db()
    task = await board.create(
        goal_id,
        description="Return an exact candidate.",
        metadata={
            "mission_id": MISSION,
            "goal_id": goal_id,
            "goal_contract_sha256": POLICY,
        },
    )
    await board.assign(task.id, "producer-agent")
    await board.start(task.id)
    await board.complete(task.id, result="candidate")
    task = await board.get(task.id)
    assert task is not None
    run_id = stable_id("producer", task.id)
    identity = ExecutionIdentity.new(
        trace_id=stable_id("trace", run_id),
        correlation_id=f"mission_campaign:{MISSION}",
        task_id=task.id,
        run_id=run_id,
        claim_id=stable_id("claim", run_id),
        agent_id="producer-agent",
        session_id=f"mission_owner:{MISSION}",
        idempotency_key=stable_id("idem", run_id),
    )
    completed_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await runtime.record_execution_identity(identity, source="test")
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=run_id,
            task_id=task.id,
            assigned_to=identity.agent_id,
            assigned_by="test",
            status="completed",
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            started_at=completed_at - timedelta(seconds=1),
            completed_at=completed_at,
        )
    )
    await runtime.insert_runtime_receipt_exact(
        RuntimeReceipt(
            receipt_id="producer-provider",
            receipt_type="side_effect_complete",
            status="completed",
            run_id=run_id,
            task_id=task.id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=f"model_completion:{run_id}",
            payload={
                "receipt": {
                    "trace_id": identity.trace_id,
                    "task_id": task.id,
                    "agent_id": identity.agent_id,
                    "claim_id": identity.claim_id,
                    "status": "ok",
                    "attributes": {
                        "run_id": run_id,
                        "dispatch_idempotency_key": identity.idempotency_key,
                        "served_provider": ProviderType.OLLAMA.value,
                        "served_model": PRODUCER_MODEL,
                        "provider_truth_source": "llm_response",
                    },
                }
            },
            created_at=completed_at,
        )
    )
    ref = OwnerExecutionRef(
        backend="orchestrator",
        mission_id=MISSION,
        task_id=task.id,
        dispatch_key="default",
        run_id=run_id,
        claim_id=identity.claim_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        owner_session_id=identity.session_id,
    )
    observation = OwnerExecutionObservation(
        ref=ref,
        task_status=TaskStatus.COMPLETED,
        run_status="completed",
        claim_status="completed",
        stale=False,
        receipt_ids=("producer-provider",),
        terminal=True,
        succeeded=True,
        result="candidate",
        failure_code="",
        observed_at=completed_at,
    )
    provider = _Provider()
    admitted = roster or _roster()
    verifier = AutomaticCandidateVerifier(
        runtime=runtime,
        board=board,
        roster=admitted,
        model_provider=provider,
        verifier_seat_name="sadhana-nemotron",
        model_lock_root=tmp_path / "verifier-locks",
        held_out_manifest_path=tmp_path / "held-out.json",
        held_out_manifest_digest="sha256:" + "e" * 64,
        oracle_work_root=tmp_path / "oracle-work",
        oracle_launcher=_UnusedLauncher(),
    )
    snapshot = _Snapshot(MISSION, (task.id,), (observation,))
    return _Stack(runtime, board, admitted, task.id, observation, snapshot, provider, verifier)


@pytest.mark.asyncio
async def test_exact_candidate_is_automatically_verified_once(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)

    first = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]
    replay = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]

    assert first.status == replay.status == "accepted"
    assert first.acceptance == replay.acceptance
    assert first.attempt == replay.attempt == 1
    assert len(stack.provider.calls) == 1
    assert first.acceptance is not None
    assert first.acceptance.producer_model_family == PRODUCER_MODEL
    assert first.acceptance.verifier_model_family == VERIFIER_MODEL


@pytest.mark.asyncio
async def test_failed_verifier_advances_one_bounded_attempt_per_cycle(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    stack.provider.content = "not-json"
    failed = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]
    stack.provider.content = (
        '{"accepted":true,"rationale":"Recovered exact verification.",'
        '"verdict":"ACCEPT"}'
    )
    recovered = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]

    assert failed.status == "failed" and failed.attempt == 1
    assert recovered.status == "accepted" and recovered.attempt == 2
    assert recovered.acceptance is not None
    assert len(stack.provider.calls) == 2


@pytest.mark.asyncio
async def test_same_family_never_calls_provider(tmp_path: Path) -> None:
    stack = await _stack(tmp_path, roster=_roster(verifier_family="glm"))

    outcome = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]

    assert outcome.status == "failed"
    assert "families must differ" in outcome.error
    assert stack.provider.calls == []


@pytest.mark.asyncio
async def test_missing_or_duplicate_candidate_coordinates_block(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    missing = _Snapshot(MISSION, (stack.task_id,), ())
    duplicate = _Snapshot(
        MISSION,
        (stack.task_id,),
        (stack.observation, stack.observation),
    )

    missing_result = await stack.verifier.reconcile(missing)  # type: ignore[arg-type]
    duplicate_result = await stack.verifier.reconcile(duplicate)  # type: ignore[arg-type]

    assert missing_result.status == duplicate_result.status == "blocked"
    assert stack.provider.calls == []


@pytest.mark.asyncio
async def test_g10_uses_only_automatic_deterministic_held_out_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack = await _stack(tmp_path, goal_id="G10_SAFETY_TCB")
    acceptance = IndependentAcceptance.new(
        mission_id=MISSION,
        task_id=stack.task_id,
        producer_run_id=stack.observation.ref.run_id,
        producer_agent_id=stack.observation.ref.agent_id,
        producer_model_family="",
        producer_output_digest=candidate_output_digest(stack.observation.result),
        verifier_run_id="held-out-run",
        verifier_agent_id="held-out-agent",
        verifier_model_family="deterministic-held-out",
        oracle_kind="deterministic_held_out",
        oracle_digest="sha256:" + "e" * 64,
        accepted=True,
        observed_at=datetime.now(timezone.utc),
        rationale="Exact deterministic held-out verdict.",
        evidence_receipt_ids=("held-out-receipt",),
        evidence_artifact_ids=("held-out-artifact",),
    )
    calls = 0
    bundle_digest = "sha256:" + "f" * 64

    monkeypatch.setattr(auto_module, "load_held_out_oracle_manifest", lambda *_a, **_k: object())
    monkeypatch.setattr(
        auto_module,
        "collect_g10_evidence",
        lambda *_a, **_k: G10EvidenceBundle({}, bundle_digest, ()),
    )

    async def held_out(**kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["attempt_number"] == 1
        assert kwargs["expected_evidence_bundle_sha256"] == bundle_digest
        return HeldOutOracleOutcome(
            "accept",
            "held-out-run",
            {"verdict": "ACCEPT"},
            acceptance,
            False,
        )

    monkeypatch.setattr(auto_module, "run_held_out_oracle", held_out)
    outcome = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]

    assert outcome.acceptance == acceptance
    assert outcome.status == "accept"
    assert calls == 1
    assert stack.provider.calls == []


@pytest.mark.asyncio
async def test_g10_missing_evidence_generation_advances_after_bundle_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack = await _stack(tmp_path, goal_id="G10_SAFETY_TCB")
    prior_digest = "sha256:" + "1" * 64
    current_digest = "sha256:" + "2" * 64
    await stack.runtime.record_delegation_run(
        DelegationRun(
            run_id="g10-blocked-attempt-one",
            task_id=stack.task_id,
            assigned_to="held-out-agent",
            assigned_by="mission-control-held-out-oracle",
            status="completed",
            session_id=f"mission_verifier:{MISSION}",
            parent_run_id=stack.observation.ref.run_id,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            metadata={
                "attempt_number": 1,
                "candidate_output_sha256": candidate_output_digest(
                    stack.observation.result
                ),
                "evidence_bundle_sha256": prior_digest,
                "missing_evidence_ids": ["authority_binding"],
            },
        )
    )
    monkeypatch.setattr(auto_module, "load_held_out_oracle_manifest", lambda *_a, **_k: object())
    monkeypatch.setattr(
        auto_module,
        "collect_g10_evidence",
        lambda *_a, **_k: G10EvidenceBundle({}, current_digest, ()),
    )
    attempts: list[int] = []

    async def held_out(**kwargs):
        attempts.append(kwargs["attempt_number"])
        assert kwargs["expected_evidence_bundle_sha256"] == current_digest
        return HeldOutOracleOutcome(
            "blocked",
            "g10-attempt-two",
            {"verdict": "BLOCKED"},
            None,
            False,
        )

    monkeypatch.setattr(auto_module, "run_held_out_oracle", held_out)
    outcome = await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]

    assert outcome.status == "blocked"
    assert outcome.attempt == 2
    assert attempts == [2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("goal_id", "assigned_by", "attempt_key", "output_key"),
    [
        (
            "G01_EXACT_CANDIDATE",
            "mission-control-verifier",
            "attempt",
            "producer_output_digest",
        ),
        (
            "G10_SAFETY_TCB",
            "mission-control-held-out-oracle",
            "attempt_number",
            "candidate_output_sha256",
        ),
    ],
)
async def test_candidate_output_history_equivocation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    goal_id: str,
    assigned_by: str,
    attempt_key: str,
    output_key: str,
) -> None:
    stack = await _stack(tmp_path, goal_id=goal_id)
    if goal_id == "G10_SAFETY_TCB":
        monkeypatch.setattr(
            auto_module,
            "load_held_out_oracle_manifest",
            lambda *_a, **_k: object(),
        )
        monkeypatch.setattr(
            auto_module,
            "collect_g10_evidence",
            lambda *_a, **_k: G10EvidenceBundle(
                {}, "sha256:" + "1" * 64, ()
            ),
        )
    await stack.runtime.record_delegation_run(
        DelegationRun(
            run_id=f"foreign-{goal_id}",
            task_id=stack.task_id,
            assigned_to="verifier-agent",
            assigned_by=assigned_by,
            status="failed",
            session_id=f"mission_verifier:{MISSION}",
            parent_run_id=stack.observation.ref.run_id,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            failure_code="fixture_failure",
            metadata={
                attempt_key: 1,
                output_key: "sha256:" + "f" * 64,
            },
        )
    )

    with pytest.raises(MissionControlError, match="history conflicts"):
        await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]
    assert stack.provider.calls == []


@pytest.mark.asyncio
async def test_attempt_history_gap_fails_closed(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    await stack.runtime.record_delegation_run(
        DelegationRun(
            run_id="attempt-two-without-one",
            task_id=stack.task_id,
            assigned_to="verifier-agent",
            assigned_by="mission-control-verifier",
            status="failed",
            session_id=f"mission_verifier:{MISSION}",
            parent_run_id=stack.observation.ref.run_id,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            failure_code="fixture_failure",
            metadata={
                "attempt": 2,
                "producer_output_digest": candidate_output_digest(
                    stack.observation.result
                ),
            },
        )
    )

    with pytest.raises(MissionControlError, match="history has a gap"):
        await stack.verifier.reconcile(stack.snapshot)  # type: ignore[arg-type]
    assert stack.provider.calls == []


@pytest.mark.asyncio
async def test_cycle_cursor_prevents_blocked_first_candidate_starvation(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    candidates = ("0000-blocked-candidate", stack.task_id)
    first = _Snapshot(MISSION, candidates, (stack.observation,), cycle_sequence=1)
    second = _Snapshot(MISSION, candidates, (stack.observation,), cycle_sequence=2)

    blocked = await stack.verifier.reconcile(first)  # type: ignore[arg-type]
    serviced = await stack.verifier.reconcile(second)  # type: ignore[arg-type]

    assert blocked.status == "blocked"
    assert serviced.status == "accepted"
    assert serviced.task_id == stack.task_id
    assert len(stack.provider.calls) == 1
