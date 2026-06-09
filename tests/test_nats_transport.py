from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from dharma_swarm.a2a.a2a_server import A2AMessage, A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportError
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


def _identity(**overrides: str) -> ExecutionIdentity:
    payload = {
        "task_id": "task-nats",
        "agent_id": "agent-nats",
        "session_id": "session-nats",
        "trace_id": "trace-nats",
        "correlation_id": "corr-nats",
        "run_id": "run-nats",
        "claim_id": "claim-nats",
        "idempotency_key": "idem-nats",
    }
    payload.update(overrides)
    return ExecutionIdentity.new(**payload)


def _task(identity: ExecutionIdentity | None = None, *, task_id: str = "a2a-task") -> A2ATask:
    metadata = identity.to_metadata() if identity else {}
    return A2ATask(
        id=task_id,
        from_agent="operator",
        to_agent="worker",
        capability="probe",
        history=[A2AMessage.text("run probe")],
        metadata=metadata,
    )


@dataclass
class _FakePubAck:
    stream: str = "DHARMA_A2A"
    seq: int = 1


class _FakeJetStream:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, dict[str, str] | None]] = []

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _FakePubAck:
        self.published.append((subject, payload, headers))
        return _FakePubAck(seq=len(self.published))


class _FakeMessage:
    def __init__(self, subject: str, data: bytes) -> None:
        self.subject = subject
        self.data = data
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1


class _InspectingAckMessage(_FakeMessage):
    def __init__(
        self,
        subject: str,
        data: bytes,
        *,
        runtime: RuntimeStateStore,
        run_id: str,
    ) -> None:
        super().__init__(subject, data)
        self._runtime = runtime
        self._run_id = run_id

    async def ack(self) -> None:
        ledger = await self._runtime.get_run_ledger(self._run_id)
        assert any(
            receipt.receipt_type == "nats_consume"
            and receipt.status == "ack_intent"
            for receipt in ledger["receipts"]
        )
        await super().ack()


@pytest.mark.asyncio
async def test_publish_task_records_identity_idempotency_and_ack_receipt(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity()
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=fake_js)

    ack = await transport.publish_task(_task(identity), identity=identity)

    assert ack.action == "ack"
    assert ack.status == "ack"
    assert ack.seq == 1
    assert len(fake_js.published) == 1
    assert fake_js.published[0][2]["Dharma-Correlation-Id"] == identity.correlation_id

    ledger = await runtime.get_run_ledger(identity.run_id)
    assert ledger["identity"] is not None
    assert any(receipt.receipt_type == "nats_publish" and receipt.status == "ack" for receipt in ledger["receipts"])
    assert any(record.side_effect_key.startswith("nats_publish:") for record in ledger["idempotency_records"])


@pytest.mark.asyncio
async def test_publish_duplicate_does_not_publish_again(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity()
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=fake_js)
    task = _task(identity)

    first = await transport.publish_task(task, identity=identity)
    second = await transport.publish_task(task, identity=identity)

    assert first.status == "ack"
    assert second.status == "duplicate"
    assert second.duplicate is True
    assert len(fake_js.published) == 1


@pytest.mark.asyncio
async def test_publish_requires_execution_identity_before_side_effect(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=fake_js)

    with pytest.raises(MissingExecutionIdentity):
        await transport.publish_task(_task(None))

    assert fake_js.published == []


@pytest.mark.asyncio
async def test_consume_message_ack_records_receipt_and_dispatches(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-consume", idempotency_key="idem-consume")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)
    seen: list[str] = []

    def handler(task: A2ATask) -> A2ATask:
        seen.append(task.id)
        task.status = A2ATaskStatus.COMPLETED
        return task

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(runtime_state=runtime, server=server, jetstream=fake_js)
    task = _task(identity, task_id="a2a-consume")
    await transport.publish_task(task, identity=identity)
    message = _InspectingAckMessage(
        "dharma.a2a.task.worker.probe",
        fake_js.published[0][1],
        runtime=runtime,
        run_id=identity.run_id,
    )

    ack = await transport.consume_message(message)

    assert ack.action == "ack"
    assert ack.status == "ack"
    assert message.acked == 1
    assert message.nacked == 0
    assert seen == ["a2a-consume"]
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(receipt.receipt_type == "nats_consume" and receipt.status == "ack_intent" for receipt in ledger["receipts"])
    assert any(receipt.receipt_type == "nats_consume" and receipt.status == "ack" for receipt in ledger["receipts"])


@pytest.mark.asyncio
async def test_consume_message_nacks_when_handler_fails(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-nack", idempotency_key="idem-nack")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)

    def handler(task: A2ATask) -> A2ATask:
        raise RuntimeError("handler failed")

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(runtime_state=runtime, server=server, jetstream=fake_js)
    await transport.publish_task(_task(identity, task_id="a2a-nack"), identity=identity)
    message = _FakeMessage("dharma.a2a.task.worker.probe", fake_js.published[0][1])

    with pytest.raises(NatsTransportError):
        await transport.consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(receipt.receipt_type == "nats_consume" and receipt.status == "nack" for receipt in ledger["receipts"])


@pytest.mark.asyncio
async def test_consume_message_does_not_nak_after_broker_ack(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-post-ack-error", idempotency_key="idem-post-ack-error")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)

    def handler(task: A2ATask) -> A2ATask:
        task.status = A2ATaskStatus.COMPLETED
        return task

    async def fail_complete(*args: object, **kwargs: object) -> object:
        raise RuntimeError("runtime finalization failed")

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(runtime_state=runtime, server=server, jetstream=fake_js)
    await transport.publish_task(_task(identity, task_id="a2a-post-ack-error"), identity=identity)
    transport.runtime_state.complete_idempotent_side_effect = fail_complete  # type: ignore[method-assign]
    message = _FakeMessage("dharma.a2a.task.worker.probe", fake_js.published[0][1])

    with pytest.raises(NatsTransportError, match="broker ack succeeded"):
        await transport.consume_message(message)

    assert message.acked == 1
    assert message.nacked == 0
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(
        receipt.receipt_type == "nats_consume"
        and receipt.status == "ack_finalization_error"
        for receipt in ledger["receipts"]
    )
