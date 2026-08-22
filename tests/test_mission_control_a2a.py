from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportError
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_a2a import (
    A2AAdapterError,
    A2ADispatchAuthorization,
    A2ADispatchIntent,
    A2ADispatchRequest,
    A2AMissionAdapter,
)
from dharma_swarm.mission_control_contract import session_id, stable_id
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


@dataclass
class _BrokerAck:
    stream: str = "DS_TASKS"
    seq: int = 1


class _Broker:
    def __init__(self, outcomes: list[object] | None = None) -> None:
        self.outcomes = list(outcomes or [_BrokerAck()])
        self.calls: list[dict[str, Any]] = []
        self.events: list[str] | None = None

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> object:
        if self.events is not None:
            self.events.append("broker_write")
        self.calls.append(
            {
                "subject": subject,
                "payload": json.loads(payload.decode("utf-8")),
                "headers": headers,
                "timeout": timeout,
            }
        )
        outcome = self.outcomes.pop(0) if self.outcomes else _BrokerAck(seq=len(self.calls))
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _Authorizer:
    def __init__(
        self,
        *,
        corrupt: str = "",
        events: list[str] | None = None,
        mutation: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.corrupt = corrupt
        self.events = events
        self.mutation = mutation
        self.authority_ref = "authority_ref_1"
        self.authority_digest = "authority_digest_1"
        self.calls: list[A2ADispatchIntent] = []

    async def authorize(self, intent: A2ADispatchIntent) -> A2ADispatchAuthorization:
        if self.events is not None:
            self.events.append("authorize")
        self.calls.append(intent)
        values = {
            "mission_id": intent.request.mission_id,
            "task_id": intent.request.task_id,
            "dispatch_key": intent.request.dispatch_key,
            "authenticated_principal": intent.request.claimed_principal,
            "operation_digest": intent.operation_digest,
            "authority_ref": self.authority_ref,
            "authority_digest": self.authority_digest,
        }
        if self.corrupt:
            values[self.corrupt] = "wrong"
        if self.mutation is not None:
            await self.mutation()
        return A2ADispatchAuthorization(**values)


@dataclass
class _Stack:
    runtime: RuntimeStateStore
    board: TaskBoard
    mission_control: MissionControl
    broker: _Broker
    authorizer: _Authorizer
    adapter: A2AMissionAdapter
    request: A2ADispatchRequest


async def _stack(
    root: Path,
    *,
    broker: _Broker | None = None,
    authorizer: _Authorizer | None = None,
    depends_on: list[str] | None = None,
) -> _Stack:
    runtime = RuntimeStateStore(root / "runtime.db")
    board = TaskBoard(root / "tasks.db")
    await board.init_db()
    mission_control = MissionControl(board, runtime)
    await mission_control.create_mission("mission_alpha", title="Alpha")
    task = await mission_control.create_task(
        "mission_alpha",
        title="Compile evidence",
        description="Return a bounded evidence packet",
        depends_on=depends_on,
        idempotency_key="task_alpha",
    )
    resolved_broker = broker or _Broker()
    resolved_authorizer = authorizer or _Authorizer()
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=resolved_broker)
    adapter = A2AMissionAdapter(
        mission_control,
        board,
        runtime,
        transport,
        authorizer=resolved_authorizer,
    )
    request = A2ADispatchRequest(
        mission_id="mission_alpha",
        task_id=task.task_id,
        dispatch_key="dispatch_alpha",
        claimed_principal="operator_alpha",
        from_agent="mission_control",
        to_agent="a2a_worker",
        capability="evidence_compile",
        instruction="Compile the canonical evidence packet.",
    )
    return _Stack(
        runtime,
        board,
        mission_control,
        resolved_broker,
        resolved_authorizer,
        adapter,
        request,
    )


@pytest.mark.asyncio
async def test_publish_ack_does_not_imply_handler_outcome_or_liveness(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)

    publish_ref = await stack.adapter.dispatch(stack.request)
    observation = await stack.adapter.observe(publish_ref)
    task = await stack.board.get(stack.request.task_id)

    assert publish_ref.broker_accepted is True
    assert publish_ref.proves_handler_contact is False
    assert publish_ref.proves_semantic_outcome is False
    assert publish_ref.proves_verified_outcome is False
    assert publish_ref.proves_executor_liveness is False
    assert observation.publish_acknowledged is True
    assert observation.consumer_acknowledged is False
    assert observation.handler_acknowledged is False
    assert observation.semantic_outcome_observed is False
    assert observation.verified_outcome is False
    assert observation.proves_executor_liveness is False
    assert task is not None
    assert task.status == TaskStatus.PENDING
    assert task.assigned_to is None
    assert await stack.runtime.list_task_claims(session_id=session_id("mission_alpha")) == []
    assert await stack.runtime.list_delegation_runs(session_id=session_id("mission_alpha")) == []


@pytest.mark.asyncio
async def test_stable_identity_canonical_envelope_and_retry_recovery(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)

    first = await stack.adapter.dispatch(stack.request)
    second = await stack.adapter.dispatch(stack.request)

    triple = (stack.request.mission_id, stack.request.task_id, stack.request.dispatch_key)
    assert first.external_a2a_task_id == stable_id("a2a_task", *triple)
    assert first.run_id == stable_id("a2a_run", *triple)
    assert first.claim_id == stable_id("a2a_claim", *triple)
    assert first.idempotency_key == stable_id("a2a_dispatch", *triple)
    assert first.trace_id == stable_id("a2a_trace", *triple)
    assert first.correlation_id == stable_id("a2a_correlation", *triple[:2])
    assert first.idempotency_finalized is True
    assert first.recovered is False
    assert second.receipt_id == first.receipt_id
    assert second.recovered is True
    assert len(stack.broker.calls) == 1
    assert len(stack.authorizer.calls) == 3
    wire = stack.broker.calls[0]["payload"]
    wire_task = wire["payload"]["task"]
    assert wire_task["id"] == first.external_a2a_task_id
    assert wire_task["context_id"] == first.context_id
    assert wire_task["dharma_task_id"] == stack.request.task_id
    assert wire_task["history"][0]["parts"][0]["content"] == stack.request.instruction
    assert wire_task["metadata"]["operation_digest"] == first.operation_digest


@pytest.mark.asyncio
async def test_authorization_precedes_runtime_and_broker_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    broker = _Broker()
    broker.events = events
    stack = await _stack(tmp_path, broker=broker, authorizer=_Authorizer(events=events))
    original = stack.runtime.record_execution_identity

    async def record_identity(*args: Any, **kwargs: Any) -> ExecutionIdentity:
        events.append("runtime_write")
        return await original(*args, **kwargs)

    monkeypatch.setattr(stack.runtime, "record_execution_identity", record_identity)
    await stack.adapter.dispatch(stack.request)

    assert events[0] == "authorize"
    assert events.index("authorize") < events.index("runtime_write")
    assert events.index("authorize") < events.index("broker_write")


@pytest.mark.asyncio
async def test_authority_is_refreshed_immediately_before_transport_publish(
    tmp_path: Path,
) -> None:
    class RevokingAuthorizer(_Authorizer):
        async def authorize(
            self, intent: A2ADispatchIntent
        ) -> A2ADispatchAuthorization:
            authorization = await super().authorize(intent)
            if len(self.calls) == 2:
                return replace(
                    authorization,
                    authority_digest="authority_digest_revoked",
                )
            return authorization

    authorizer = RevokingAuthorizer()
    stack = await _stack(tmp_path, authorizer=authorizer)

    with pytest.raises(A2AAdapterError, match="changed before transport publish"):
        await stack.adapter.dispatch(stack.request)

    run_id = stable_id(
        "a2a_run", stack.request.mission_id, stack.request.task_id, stack.request.dispatch_key
    )
    assert len(authorizer.calls) == 2
    assert stack.broker.calls == []
    assert await stack.runtime.get_execution_identity(run_id) is None


@pytest.mark.asyncio
async def test_untyped_or_mismatched_authority_blocks_before_publish(tmp_path: Path) -> None:
    stack = await _stack(tmp_path, authorizer=_Authorizer(corrupt="operation_digest"))

    with pytest.raises(A2AAdapterError, match="does not bind"):
        await stack.adapter.dispatch(stack.request)

    run_id = stable_id(
        "a2a_run", stack.request.mission_id, stack.request.task_id, stack.request.dispatch_key
    )
    assert stack.broker.calls == []
    assert await stack.runtime.get_execution_identity(run_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["authority_ref", "authority_digest"])
async def test_numeric_authority_identifiers_are_not_coerced(
    tmp_path: Path, field: str
) -> None:
    authorizer = _Authorizer()
    setattr(authorizer, field, 7)
    stack = await _stack(tmp_path, authorizer=authorizer)

    with pytest.raises(A2AAdapterError, match="exact nonempty strings"):
        await stack.adapter.dispatch(stack.request)

    assert stack.broker.calls == []


@pytest.mark.asyncio
async def test_failed_base_then_successful_retry_recovers_without_third_publish(
    tmp_path: Path,
) -> None:
    broker = _Broker([RuntimeError("broker unavailable"), _BrokerAck(seq=9)])
    stack = await _stack(tmp_path, broker=broker)

    with pytest.raises(NatsTransportError, match="broker unavailable"):
        await stack.adapter.dispatch(stack.request)
    successful = await stack.adapter.dispatch(stack.request)
    recovered = await stack.adapter.dispatch(stack.request)

    assert len(broker.calls) == 2
    assert successful.idempotency_finalized is True
    assert recovered.receipt_id == successful.receipt_id
    assert recovered.recovered is True
    receipts = await stack.runtime.list_runtime_receipts(run_id=successful.run_id, limit=200)
    assert any(r.receipt_type == "nats_publish" and r.status == "nack" for r in receipts)
    assert any(
        r.receipt_type == "nats_publish"
        and r.status == "ack"
        and ":retry:" in r.side_effect_key
        for r in receipts
    )


@pytest.mark.asyncio
async def test_ack_before_idempotency_finalization_recovers_without_republish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stack = await _stack(tmp_path)

    async def fail_finalization(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("finalization crash")

    monkeypatch.setattr(stack.runtime, "complete_idempotent_side_effect", fail_finalization)
    first = await stack.adapter.dispatch(stack.request)
    second = await stack.adapter.dispatch(stack.request)

    assert len(stack.broker.calls) == 1
    assert first.broker_accepted is True
    assert first.idempotency_finalized is False
    assert first.recovered is True
    assert second.receipt_id == first.receipt_id
    assert second.idempotency_finalized is False


@pytest.mark.asyncio
async def test_owner_mutation_during_recovery_read_blocks_immediately_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stack = await _stack(tmp_path)
    original = stack.runtime.get_execution_identity
    mutated = False

    async def mutate_during_recovery(run_id: str) -> ExecutionIdentity | None:
        nonlocal mutated
        if not mutated:
            mutated = True
            await stack.board.assign(stack.request.task_id, "intruder")
        return await original(run_id)

    monkeypatch.setattr(stack.runtime, "get_execution_identity", mutate_during_recovery)
    with pytest.raises(A2AAdapterError, match="pending, unassigned"):
        await stack.adapter.dispatch(stack.request)

    assert mutated is True
    assert stack.broker.calls == []


@pytest.mark.asyncio
async def test_forged_ack_on_failed_idempotency_record_cannot_recover(tmp_path: Path) -> None:
    stack = await _stack(tmp_path, broker=_Broker([RuntimeError("publish failed")]))
    with pytest.raises(NatsTransportError):
        await stack.adapter.dispatch(stack.request)
    run_id = stable_id(
        "a2a_run", stack.request.mission_id, stack.request.task_id, stack.request.dispatch_key
    )
    identity = await stack.runtime.get_execution_identity(run_id)
    assert identity is not None
    receipts = await stack.runtime.list_runtime_receipts(run_id=run_id, limit=200)
    nack = next(r for r in receipts if r.receipt_type == "nats_publish" and r.status == "nack")
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="forged_publish_ack",
            receipt_type="nats_publish",
            status="ack",
            side_effect_key=nack.side_effect_key,
            payload={
                **nack.payload,
                "action": "ack",
                "ack_contract": "publish_ack",
                "stream": "DS_TASKS",
                "seq": 1,
            },
        )
    )

    with pytest.raises(A2AAdapterError, match="idempotency record"):
        await stack.adapter.dispatch(stack.request)

    assert len(stack.broker.calls) == 1


@pytest.mark.asyncio
async def test_changed_content_conflicts_before_second_publish(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    await stack.adapter.dispatch(stack.request)

    with pytest.raises(A2AAdapterError, match="operation digest conflicts"):
        await stack.adapter.dispatch(
            replace(stack.request, instruction="Perform a different operation.")
        )

    assert len(stack.broker.calls) == 1


@pytest.mark.asyncio
async def test_recovery_requires_exact_fresh_authorization_metadata(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    await stack.adapter.dispatch(stack.request)
    stack.authorizer.authority_ref = "authority_ref_rotated"
    stack.authorizer.authority_digest = "authority_digest_rotated"

    with pytest.raises(A2AAdapterError, match="operation digest conflicts"):
        await stack.adapter.dispatch(stack.request)

    assert len(stack.broker.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_kind", ["status", "content", "dependency"])
async def test_post_authorization_owner_mutation_blocks_before_transport(
    tmp_path: Path, mutation_kind: str
) -> None:
    authorizer = _Authorizer()
    stack = await _stack(tmp_path, authorizer=authorizer)
    dependency_id = ""
    if mutation_kind == "dependency":
        dependency = await stack.mission_control.create_task(
            "mission_alpha", title="Completed dependency"
        )
        dependency_id = dependency.task_id
        await stack.board.assign(dependency_id, "worker")
        await stack.board.start(dependency_id)
        await stack.board.complete(dependency_id, "done")
        await stack.board.add_dependency(stack.request.task_id, dependency_id)

    async def mutate() -> None:
        if mutation_kind == "status":
            await stack.board.assign(stack.request.task_id, "intruder")
        elif mutation_kind == "content":
            await stack.board.update_task(stack.request.task_id, description="mutated")
        else:
            await stack.board.update_task(
                dependency_id,
                metadata={"mission_id": "foreign", "schema_version": "foreign"},
            )

    authorizer.mutation = mutate
    with pytest.raises(A2AAdapterError):
        await stack.adapter.dispatch(stack.request)

    run_id = stable_id(
        "a2a_run", stack.request.mission_id, stack.request.task_id, stack.request.dispatch_key
    )
    assert stack.broker.calls == []
    assert await stack.runtime.get_execution_identity(run_id) is None


@pytest.mark.asyncio
async def test_observe_rejects_ref_that_does_not_join_its_durable_ack(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)

    with pytest.raises(A2AAdapterError, match="does not join durable"):
        await stack.adapter.observe(replace(publish_ref, receipt_id="forged_receipt"))


@pytest.mark.asyncio
async def test_observe_rejects_forged_transport_and_outcome_fields(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    forged = replace(
        publish_ref,
        stream="forged",
        seq=999,
        proves_verified_outcome=True,
        proves_executor_liveness=True,
    )

    with pytest.raises(A2AAdapterError, match="unproven transport or outcome"):
        await stack.adapter.observe(forged)


@pytest.mark.asyncio
async def test_foreign_external_identity_fails_closed(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    foreign = ExecutionIdentity.new(
        task_id=stack.request.task_id,
        run_id="foreign_run",
        trace_id="foreign_trace",
        correlation_id="foreign_correlation",
        claim_id="foreign_claim",
        idempotency_key="foreign_idempotency",
        external_a2a_task_id=publish_ref.external_a2a_task_id,
    )
    await stack.runtime.record_execution_identity(foreign, source="test.foreign")

    with pytest.raises(A2AAdapterError, match="missing or ambiguous"):
        await stack.adapter.dispatch(stack.request)

    assert len(stack.broker.calls) == 1


def _receipt_from_identity(
    identity: ExecutionIdentity,
    *,
    receipt_id: str,
    receipt_type: str,
    status: str,
    side_effect_key: str,
    payload: dict[str, Any],
) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id=receipt_id,
        receipt_type=receipt_type,
        status=status,
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key=side_effect_key,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_ambiguous_publish_ack_receipts_fail_closed(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="foreign_publish_ack",
            receipt_type="nats_publish",
            status="ack",
            side_effect_key="nats_publish:foreign",
            payload={
                "action": "ack",
                "external_a2a_task_id": publish_ref.external_a2a_task_id,
                "subject": "dharma.a2a.task.foreign.route",
                "message_id": "foreign_message",
            },
        )
    )

    with pytest.raises(A2AAdapterError, match="malformed nats_publish"):
        await stack.adapter.observe(publish_ref)


@pytest.mark.asyncio
async def test_same_key_publish_acks_with_conflicting_result_fields_fail_closed(
    tmp_path: Path,
) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    receipts = await stack.runtime.list_runtime_receipts(run_id=publish_ref.run_id, limit=200)
    original = next(r for r in receipts if r.receipt_id == publish_ref.receipt_id)
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="conflicting_same_key_ack",
            receipt_type="nats_publish",
            status="ack",
            side_effect_key=original.side_effect_key,
            payload={**original.payload, "stream": "OTHER", "seq": 999},
        )
    )

    with pytest.raises(A2AAdapterError, match="ambiguous nats_publish"):
        await stack.adapter.observe(publish_ref)


@pytest.mark.asyncio
@pytest.mark.parametrize("receipt_type", ["nats_consume", "a2a_task"])
async def test_observe_rejects_receipts_outside_exact_transport_or_handler_join(
    tmp_path: Path, receipt_type: str
) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    if receipt_type == "nats_consume":
        status = "ack"
        payload = {
            "external_a2a_task_id": publish_ref.external_a2a_task_id,
            "subject": "dharma.a2a.task.foreign.route",
            "message_id": publish_ref.message_id,
            "operation_hash": identity.metadata["nats_operation_hash"],
            "action": "ack",
            "ack_contract": "consumer_ack",
        }
    else:
        status = "completed"
        payload = {
            "external_a2a_task_id": publish_ref.external_a2a_task_id,
            "context_id": "foreign_context",
            "capability": "evidence_compile",
        }
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id=f"forged_{receipt_type}",
            receipt_type=receipt_type,
            status=status,
            side_effect_key=f"{receipt_type}:forged",
            payload=payload,
        )
    )

    with pytest.raises(A2AAdapterError, match="malformed"):
        await stack.adapter.observe(publish_ref)


@pytest.mark.asyncio
async def test_consumer_ack_requires_native_owner_side_effect_key(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="consumer_wrong_key",
            receipt_type="nats_consume",
            status="ack",
            side_effect_key="nats_consume:foreign",
            payload={
                "external_a2a_task_id": publish_ref.external_a2a_task_id,
                "subject": publish_ref.subject,
                "message_id": publish_ref.message_id,
                "operation_hash": identity.metadata["nats_operation_hash"],
                "action": "ack",
                "ack_contract": "consumer_ack",
            },
        )
    )

    with pytest.raises(A2AAdapterError, match="malformed nats_consume"):
        await stack.adapter.observe(publish_ref)


@pytest.mark.asyncio
async def test_handler_receipt_requires_native_a2a_status(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="handler_non_native_status",
            receipt_type="a2a_task",
            status="verified",
            side_effect_key=(
                f"a2a_handler:{publish_ref.external_a2a_task_id}:evidence_compile"
            ),
            payload={
                "external_a2a_task_id": publish_ref.external_a2a_task_id,
                "context_id": publish_ref.context_id,
                "capability": "evidence_compile",
            },
        )
    )

    with pytest.raises(A2AAdapterError, match="malformed A2A handler"):
        await stack.adapter.observe(publish_ref)


@pytest.mark.asyncio
async def test_handler_receipt_rejects_empty_owner_retry_suffix(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="handler_empty_retry_suffix",
            receipt_type="a2a_task",
            status="completed",
            side_effect_key=(
                f"a2a_handler:{publish_ref.external_a2a_task_id}:evidence_compile:retry:"
            ),
            payload={
                "external_a2a_task_id": publish_ref.external_a2a_task_id,
                "context_id": publish_ref.context_id,
                "capability": "evidence_compile",
            },
        )
    )

    with pytest.raises(A2AAdapterError, match="malformed A2A handler"):
        await stack.adapter.observe(publish_ref)


@pytest.mark.asyncio
async def test_receipt_scan_uses_limit_plus_one_and_saturates_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    observed_limits: list[int] = []
    original = stack.runtime.list_runtime_receipts

    async def list_receipts(**kwargs: Any) -> list[RuntimeReceipt]:
        observed_limits.append(int(kwargs["limit"]))
        return await original(**kwargs)

    monkeypatch.setattr(stack.runtime, "list_runtime_receipts", list_receipts)
    bounded = A2AMissionAdapter(
        stack.mission_control,
        stack.board,
        stack.runtime,
        stack.adapter._transport,
        authorizer=stack.authorizer,
        receipt_scan_limit=1,
    )

    with pytest.raises(A2AAdapterError, match="scan saturated"):
        await bounded.observe(publish_ref)

    assert observed_limits == [2]


@pytest.mark.asyncio
async def test_pending_dependency_blocks_before_authorization_or_publish(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    mission_control = MissionControl(board, runtime)
    await mission_control.create_mission("mission_alpha", title="Alpha")
    dependency = await mission_control.create_task("mission_alpha", title="Dependency")
    stack = await _stack(tmp_path, depends_on=[dependency.task_id])

    with pytest.raises(A2AAdapterError, match="dependency .* is not completed"):
        await stack.adapter.dispatch(stack.request)

    assert stack.authorizer.calls == []
    assert stack.broker.calls == []


@pytest.mark.asyncio
async def test_handler_receipt_is_distinct_unverified_semantic_evidence(tmp_path: Path) -> None:
    stack = await _stack(tmp_path)
    publish_ref = await stack.adapter.dispatch(stack.request)
    identity = await stack.runtime.get_execution_identity(publish_ref.run_id)
    assert identity is not None
    await stack.runtime.record_runtime_receipt(
        _receipt_from_identity(
            identity,
            receipt_id="handler_completed",
            receipt_type="a2a_task",
            status="completed",
            side_effect_key=f"a2a_handler:{publish_ref.external_a2a_task_id}:evidence_compile",
            payload={
                "external_a2a_task_id": publish_ref.external_a2a_task_id,
                "context_id": publish_ref.context_id,
                "capability": "evidence_compile",
            },
        )
    )

    observation = await stack.adapter.observe(publish_ref)

    assert observation.handler_acknowledged is True
    assert observation.semantic_outcome_observed is True
    assert observation.semantic_status == "completed"
    assert observation.verified_outcome is False
    assert observation.proves_executor_liveness is False
