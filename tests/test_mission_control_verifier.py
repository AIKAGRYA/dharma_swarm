from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_campaign import CampaignConfig, CampaignSupervisor
from dharma_swarm.mission_control_contract import stable_id, utc_now
from dharma_swarm.mission_control_evidence import VERIFIER_RESULT_RECEIPT_TYPE
from dharma_swarm.mission_control_execution import (
    EXECUTION_METADATA_KEY,
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.mission_control_roster import (
    CampaignAgentRoster,
    CampaignAgentSeat,
)
from dharma_swarm.mission_control_verifier import (
    ModelVerifierBusy,
    ModelVerifierError,
    VerifierRunLock,
    run_verifier,
)
from dharma_swarm.models import (
    AgentRole,
    LLMRequest,
    LLMResponse,
    ProviderType,
    Task,
    TaskStatus,
)
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard

MISSION_ID = "campaign-verifier"
POLICY_DIGEST = "sha256:" + "a" * 64
OBJECTIVE_DIGEST = "b" * 64
ROSTER_DIGEST = "c" * 64
PRODUCER_MODEL = "glm-5.2"
VERIFIER_MODEL = "nemotron-3-ultra"
FALLBACK_MODEL = "kimi-k3"


class FakeProvider:
    def __init__(
        self,
        *,
        content: str = (
            '{"accepted":true,"rationale":"The candidate satisfies the stated '
            'definition of done.","verdict":"ACCEPT"}'
        ),
        model: str = VERIFIER_MODEL,
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.error = error
        self.calls: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return LLMResponse(
            content=self.content,
            model=self.model,
            provider=ProviderType.OLLAMA.value,
            usage={"input_tokens": 41, "output_tokens": 17},
        )


class OwnerReader:
    def __init__(
        self,
        ref: OwnerExecutionRef,
        observation: OwnerExecutionObservation,
    ) -> None:
        self.ref = ref
        self.observation = observation

    async def recover(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> OwnerExecutionRef | None:
        if (mission_id, task_id, dispatch_key) == (
            self.ref.mission_id,
            self.ref.task_id,
            self.ref.dispatch_key,
        ):
            return self.ref
        return None

    async def observe(self, ref: OwnerExecutionRef) -> OwnerExecutionObservation:
        assert ref == self.ref
        return self.observation


@dataclass(slots=True)
class Stack:
    board: TaskBoard
    runtime: RuntimeStateStore
    control: MissionControl
    task: Task
    roster: CampaignAgentRoster
    ref: OwnerExecutionRef
    observation: OwnerExecutionObservation
    reader: OwnerReader
    supervisor: CampaignSupervisor
    lock_path: Path


def _roster(*, verifier_family: str = "nemotron") -> CampaignAgentRoster:
    now = datetime.now(timezone.utc)
    return CampaignAgentRoster(
        campaign_id=MISSION_ID,
        objective_sha256=OBJECTIVE_DIGEST,
        activation_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=10),
        catalog_observed_at=now - timedelta(minutes=1),
        catalog_models=(PRODUCER_MODEL, VERIFIER_MODEL, FALLBACK_MODEL),
        seats=(
            CampaignAgentSeat(
                name="sadhana-glm",
                role=AgentRole.RESEARCHER,
                provider=ProviderType.OLLAMA,
                model=PRODUCER_MODEL + ":cloud",
                family="glm",
                thread="producer-thread",
                system_prompt="Produce one bounded candidate.",
            ),
            CampaignAgentSeat(
                name="sadhana-nemotron",
                role=AgentRole.VALIDATOR,
                provider=ProviderType.OLLAMA,
                model=VERIFIER_MODEL + ":cloud",
                family=verifier_family,
                thread="verifier-thread",
                system_prompt="Independently verify one bounded candidate.",
            ),
            CampaignAgentSeat(
                name="sadhana-kimi",
                role=AgentRole.REVIEWER,
                provider=ProviderType.OLLAMA,
                model=FALLBACK_MODEL + ":cloud",
                family="kimi",
                thread="fallback-thread",
                system_prompt="Remain an admitted but unrequested fallback.",
            ),
        ),
        manifest_sha256=ROSTER_DIGEST,
    )


def _provider_receipt(
    identity: ExecutionIdentity,
    *,
    created_at: datetime,
) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id="producer-provider-receipt",
        receipt_type="side_effect_complete",
        status="completed",
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key=f"model_completion:{identity.run_id}",
        payload={
            "receipt": {
                "trace_id": identity.trace_id,
                "task_id": identity.task_id,
                "agent_id": identity.agent_id,
                "claim_id": identity.claim_id,
                "status": "ok",
                "attributes": {
                    "run_id": identity.run_id,
                    "dispatch_idempotency_key": identity.idempotency_key,
                    "served_provider": ProviderType.OLLAMA.value,
                    "served_model": PRODUCER_MODEL,
                    "provider_truth_source": "llm_response",
                },
            }
        },
        created_at=created_at,
    )


async def _stack(
    tmp_path: Path,
    *,
    roster: CampaignAgentRoster | None = None,
    producer_agent_id: str = "producer-agent",
) -> Stack:
    admitted = roster or _roster()
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(MISSION_ID, title="Verifier campaign")
    view = await control.create_task(
        MISSION_ID,
        title="Produce a durable canary artifact",
        description="Return the exact text 'candidate artifact'.",
        idempotency_key="verifier-canary",
        metadata={
            "goal_id": "G10",
            "goal_contract_sha256": POLICY_DIGEST,
            EXECUTION_METADATA_KEY: {"dispatch_key": "default"},
        },
    )
    await board.assign(view.task_id, producer_agent_id)
    await board.start(view.task_id)
    await board.complete(view.task_id, result="candidate artifact")
    task = await board.get(view.task_id)
    assert task is not None

    ref = OwnerExecutionRef(
        backend="fixture-owner",
        mission_id=MISSION_ID,
        task_id=task.id,
        dispatch_key="default",
        run_id=stable_id("producer_run", MISSION_ID, task.id),
        claim_id=stable_id("producer_claim", MISSION_ID, task.id),
        agent_id=producer_agent_id,
        idempotency_key=stable_id("producer_idempotency", MISSION_ID, task.id),
        owner_session_id="producer-session",
    )
    identity = ExecutionIdentity.new(
        trace_id=stable_id("producer_trace", ref.run_id),
        correlation_id=f"mission_campaign:{MISSION_ID}",
        task_id=task.id,
        run_id=ref.run_id,
        claim_id=ref.claim_id,
        agent_id=ref.agent_id,
        session_id=ref.owner_session_id,
        idempotency_key=ref.idempotency_key,
    )
    producer_completed_at = utc_now() - timedelta(seconds=2)
    producer_started_at = producer_completed_at - timedelta(seconds=1)
    await runtime.record_execution_identity(identity, source="test-producer")
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=ref.run_id,
            task_id=task.id,
            assigned_to=ref.agent_id,
            assigned_by="fixture-owner",
            status="completed",
            session_id=ref.owner_session_id,
            claim_id=ref.claim_id,
            started_at=producer_started_at,
            completed_at=producer_completed_at,
            metadata={"mission_id": MISSION_ID},
        )
    )
    await runtime.insert_runtime_receipt_exact(
        _provider_receipt(identity, created_at=producer_completed_at)
    )
    observation = OwnerExecutionObservation(
        ref=ref,
        task_status=TaskStatus.COMPLETED,
        run_status="completed",
        claim_status="completed",
        stale=False,
        receipt_ids=("producer-provider-receipt",),
        terminal=True,
        succeeded=True,
        result="candidate artifact",
        failure_code="",
        observed_at=utc_now(),
    )
    reader = OwnerReader(ref, observation)
    supervisor = CampaignSupervisor(
        CampaignConfig(MISSION_ID, canary_task_id=task.id),
        control,
        board,
        runtime,
        reader,
    )
    await supervisor.start()
    lock_parent = tmp_path / "private-locks"
    lock_parent.mkdir(mode=0o700)
    return Stack(
        board=board,
        runtime=runtime,
        control=control,
        task=task,
        roster=admitted,
        ref=ref,
        observation=observation,
        reader=reader,
        supervisor=supervisor,
        lock_path=lock_parent / "verifier.lock",
    )


async def _verify(
    stack: Stack,
    provider: FakeProvider,
    *,
    task: Task | None = None,
    attempt: int = 1,
):
    return await run_verifier(
        runtime=stack.runtime,
        provider=provider,
        roster=stack.roster,
        verifier_seat_name="sadhana-nemotron",
        task=task or stack.task,
        candidate=stack.observation,
        policy_digest=POLICY_DIGEST,
        lock_path=stack.lock_path,
        attempt_number=attempt,
    )


async def test_success_records_exact_evidence_and_supervisor_consumes_it(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider()

    acceptance = await _verify(stack, provider)

    assert acceptance.accepted is True
    assert acceptance.producer_run_id == stack.ref.run_id
    assert acceptance.producer_model_family == PRODUCER_MODEL
    assert acceptance.verifier_model_family == VERIFIER_MODEL
    assert acceptance.verifier_agent_id != stack.ref.agent_id
    assert len(provider.calls) == 1
    assert provider.calls[0].model == VERIFIER_MODEL + ":cloud"
    assert provider.calls[0].tools == []
    identity = await stack.runtime.get_execution_identity(acceptance.verifier_run_id)
    run = await stack.runtime.get_delegation_run(acceptance.verifier_run_id)
    receipts = await stack.runtime.list_runtime_receipts(
        run_id=acceptance.verifier_run_id,
        limit=20,
    )
    assert identity is not None
    assert run is not None and run.status == "completed"
    assert [receipt.receipt_type for receipt in receipts] == [
        "side_effect_intent",
        "side_effect_complete",
        VERIFIER_RESULT_RECEIPT_TYPE,
    ]
    provider_receipt = receipts[1]
    assert provider_receipt.payload["receipt"]["attributes"] == {
        "run_id": acceptance.verifier_run_id,
        "dispatch_idempotency_key": identity.idempotency_key,
        "served_provider": ProviderType.OLLAMA.value,
        "served_model": VERIFIER_MODEL,
        "provider_truth_source": "llm_response",
    }

    promotion = await stack.supervisor.accept(acceptance)
    snapshot = await stack.supervisor.status()
    assert promotion.status == "accepted"
    assert snapshot.accepted_task_ids == (stack.task.id,)
    assert snapshot.canary_acceptance == "accepted"
    assert snapshot.proves_semantic_acceptance is True


async def test_successful_replay_reuses_evidence_without_provider_call(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider()
    first = await _verify(stack, provider)
    second = await _verify(stack, provider)

    assert second == first
    assert len(provider.calls) == 1


async def test_same_roster_family_fails_before_provider(tmp_path: Path) -> None:
    stack = await _stack(tmp_path, roster=_roster(verifier_family="glm"))
    provider = FakeProvider()

    with pytest.raises(ModelVerifierError, match="families must differ"):
        await _verify(stack, provider)

    assert provider.calls == []


async def test_policy_or_foreign_task_binding_fails_before_provider(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider()
    foreign = stack.task.model_copy(
        update={
            "metadata": {
                **stack.task.metadata,
                "goal_contract_sha256": "sha256:" + "f" * 64,
            }
        }
    )

    with pytest.raises(ModelVerifierError, match="binding is invalid"):
        await _verify(stack, provider, task=foreign)

    assert provider.calls == []


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"accepted":true,"rationale":"ok","verdict":"REJECT"}',
        '{"accepted":true,"accepted":true,"rationale":"ok","verdict":"ACCEPT"}',
        '{"accepted":true,"rationale":"ok","verdict":"ACCEPT","extra":1}',
    ],
)
async def test_malformed_output_fails_closed_and_attempt_cannot_replay(
    tmp_path: Path,
    content: str,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider(content=content)

    with pytest.raises(ModelVerifierError):
        await _verify(stack, provider)
    with pytest.raises(ModelVerifierError, match="use a new bounded attempt"):
        await _verify(stack, provider)

    assert len(provider.calls) == 1
    runs = await stack.runtime.list_delegation_runs(
        session_id=f"mission_verifier:{MISSION_ID}",
        limit=5,
    )
    results = await stack.runtime.list_runtime_receipts(
        receipt_type=VERIFIER_RESULT_RECEIPT_TYPE,
        limit=5,
    )
    assert len(runs) == 1 and runs[0].status == "failed"
    assert results == []


async def test_provider_failure_fails_closed_and_attempt_cannot_replay(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider(error=RuntimeError("provider unavailable"))

    with pytest.raises(ModelVerifierError, match="provider failed"):
        await _verify(stack, provider)
    with pytest.raises(ModelVerifierError, match="use a new bounded attempt"):
        await _verify(stack, provider)

    assert len(provider.calls) == 1
    runs = await stack.runtime.list_delegation_runs(
        session_id=f"mission_verifier:{MISSION_ID}",
        limit=5,
    )
    receipts = await stack.runtime.list_runtime_receipts(
        run_id=runs[0].run_id,
        limit=10,
    )
    assert runs[0].status == "failed"
    assert [receipt.receipt_type for receipt in receipts] == ["side_effect_intent"]


async def test_actual_fallback_model_is_recorded_but_never_accepted(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider(model=FALLBACK_MODEL)

    with pytest.raises(ModelVerifierError, match="fallback"):
        await _verify(stack, provider)

    assert len(provider.calls) == 1
    runs = await stack.runtime.list_delegation_runs(
        session_id=f"mission_verifier:{MISSION_ID}",
        limit=5,
    )
    receipts = await stack.runtime.list_runtime_receipts(
        run_id=runs[0].run_id,
        limit=10,
    )
    assert runs[0].status == "failed"
    assert [receipt.receipt_type for receipt in receipts] == [
        "side_effect_intent",
        "side_effect_complete",
    ]
    assert (
        receipts[1].payload["receipt"]["attributes"]["served_model"]
        == FALLBACK_MODEL
    )


async def test_busy_attempt_lock_fails_before_provider(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider()

    with VerifierRunLock(stack.lock_path):
        with pytest.raises(ModelVerifierBusy, match="already running"):
            await _verify(stack, provider)

    assert provider.calls == []


async def test_same_agent_identity_fails_before_provider(tmp_path: Path) -> None:
    roster = _roster()
    verifier_agent = stable_id(
        "campaign_verifier_agent",
        MISSION_ID,
        roster.manifest_sha256,
        "sadhana-nemotron",
    )
    stack = await _stack(
        tmp_path,
        roster=roster,
        producer_agent_id=verifier_agent,
    )
    provider = FakeProvider()

    with pytest.raises(ModelVerifierError, match="agents must differ"):
        await _verify(stack, provider)

    assert provider.calls == []


async def test_new_bounded_attempt_may_retry_after_failed_attempt(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    malformed = FakeProvider(content="not-json")
    with pytest.raises(ModelVerifierError):
        await _verify(stack, malformed, attempt=1)

    recovered = FakeProvider()
    acceptance = await _verify(stack, recovered, attempt=2)

    assert acceptance.accepted is True
    assert len(malformed.calls) == 1
    assert len(recovered.calls) == 1
    runs = await stack.runtime.list_delegation_runs(
        session_id=f"mission_verifier:{MISSION_ID}",
        limit=5,
    )
    assert {run.status for run in runs} == {"completed", "failed"}


@pytest.mark.parametrize("attempt", [0, 6, True])
async def test_verifier_attempt_bounds_are_strict(
    tmp_path: Path,
    attempt: int,
) -> None:
    stack = await _stack(tmp_path)
    provider = FakeProvider()

    with pytest.raises(ModelVerifierError, match="attempt must be from 1 to 5"):
        await _verify(stack, provider, attempt=attempt)

    assert provider.calls == []
