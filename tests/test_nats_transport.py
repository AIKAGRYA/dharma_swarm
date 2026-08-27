from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from dharma_swarm.a2a.a2a_server import A2AMessage, A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportConfig, NatsTransportError
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
    stream: str = "DS_TASKS"
    seq: int = 1


class _FakeJetStream:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, dict[str, str] | None]] = []
        self.streams: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.consumers: list[tuple[tuple[object, ...], dict[str, object]]] = []

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

    async def add_stream(self, *args: object, **kwargs: object) -> dict[str, str]:
        self.streams.append((args, kwargs))
        return {"status": "ok"}

    async def add_consumer(self, *args: object, **kwargs: object) -> dict[str, str]:
        self.consumers.append((args, kwargs))
        return {"status": "ok"}


class _FlakyJetStream(_FakeJetStream):
    def __init__(self, *, failures: int = 1) -> None:
        super().__init__()
        self.failures = failures

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _FakePubAck:
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("jetstream publish failed")
        return await super().publish(subject, payload, headers=headers, timeout=timeout)


class _FakeMessage:
    def __init__(
        self,
        subject: str,
        data: bytes,
        *,
        delivery_count: int = 1,
        fail_ack: bool = False,
    ) -> None:
        self.subject = subject
        self.data = data
        self.delivery_count = delivery_count
        self.fail_ack = fail_ack
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        if self.fail_ack:
            raise RuntimeError("broker ack failed")
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1

    @property
    def metadata(self):
        return type(
            "FakeNatsMetadata",
            (),
            {
                "num_delivered": self.delivery_count,
                "stream": "DS_TASKS",
                "consumer": "a2a_task_handler",
            },
        )()


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
    subject, encoded, headers = fake_js.published[0]
    assert headers["Dharma-Correlation-Id"] == identity.correlation_id
    assert headers["Dharma-Nats-Schema"] == "dharma.nats.envelope.v1"
    assert headers["Nats-Msg-Id"] == ack.message_id
    envelope = json.loads(encoded.decode("utf-8"))
    assert envelope["schema"] == "dharma.nats.envelope.v1"
    assert envelope["message_id"] == headers["Nats-Msg-Id"]
    assert envelope["subject"] == subject
    assert envelope["trace_id"] == identity.trace_id
    assert envelope["span_id"] == identity.run_id
    assert envelope["correlation_id"] == identity.correlation_id
    assert envelope["actor"] == {
        "from_agent": "operator",
        "to_agent": "worker",
        "execution_agent": identity.agent_id,
        "session_id": identity.session_id,
    }
    assert envelope["causality"] == {
        "message_id": headers["Nats-Msg-Id"],
        "trace_id": identity.trace_id,
        "span_id": identity.run_id,
        "parent_span_id": identity.parent_run_id,
        "correlation_id": identity.correlation_id,
        "causation_id": identity.causation_id,
    }
    assert envelope["payload"]["schema"] == "dharma.a2a.nats_task.v1"
    assert envelope["payload"]["task"]["id"] == "a2a-task"

    ledger = await runtime.get_run_ledger(identity.run_id)
    assert ledger["identity"] is not None
    assert any(receipt.receipt_type == "nats_publish" and receipt.status == "ack" for receipt in ledger["receipts"])
    assert any(record.side_effect_key.startswith("nats_publish:") for record in ledger["idempotency_records"])


@pytest.mark.asyncio
async def test_execution_identity_run_id_conflict_is_rejected(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    original = _identity(run_id="run-conflict", trace_id="trace-original")
    conflicting = _identity(run_id="run-conflict", trace_id="trace-rewritten")

    await runtime.record_execution_identity(original, source="test")
    with pytest.raises(ValueError, match="execution identity conflict"):
        await runtime.record_execution_identity(conflicting, source="test")

    loaded = await runtime.get_execution_identity("run-conflict")
    assert loaded is not None
    assert loaded.trace_id == "trace-original"


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
async def test_publish_failure_is_retryable_not_duplicate(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FlakyJetStream(failures=1)
    identity = _identity(run_id="run-publish-retry", idempotency_key="idem-publish-retry")
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=fake_js)
    task = _task(identity, task_id="a2a-publish-retry")

    with pytest.raises(NatsTransportError, match="jetstream publish failed"):
        await transport.publish_task(task, identity=identity)

    retry = await transport.publish_task(task, identity=identity)

    assert retry.status == "ack"
    assert retry.duplicate is False
    assert len(fake_js.published) == 1
    ledger = await runtime.get_run_ledger(identity.run_id)
    records = {
        record.side_effect_key: record.status
        for record in ledger["idempotency_records"]
        if record.side_effect_key.startswith("nats_publish:")
    }
    assert records[f"nats_publish:{retry.subject}:a2a-publish-retry"] == "failed"
    assert any(":retry:" in key and status == "completed" for key, status in records.items())


@pytest.mark.asyncio
async def test_publish_requires_execution_identity_before_side_effect(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=fake_js)

    with pytest.raises(MissingExecutionIdentity):
        await transport.publish_task(_task(None))

    assert fake_js.published == []


@pytest.mark.asyncio
async def test_consume_server_must_require_execution_identity(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=False)

    with pytest.raises(NatsTransportError, match="requires A2AServer\\(require_execution_identity=True\\)"):
        A2ANatsTransport(runtime_state=runtime, server=server, jetstream=_FakeJetStream())


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
async def test_consume_failure_redelivery_retries_handler_instead_of_duplicate_ack(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-redelivery", idempotency_key="idem-redelivery")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)
    calls = 0

    def handler(task: A2ATask) -> A2ATask:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient handler failed")
        task.status = A2ATaskStatus.COMPLETED
        return task

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(runtime_state=runtime, server=server, jetstream=fake_js)
    await transport.publish_task(_task(identity, task_id="a2a-redelivery"), identity=identity)
    data = fake_js.published[0][1]
    first = _FakeMessage("dharma.a2a.task.worker.probe", data, delivery_count=1)
    second = _FakeMessage("dharma.a2a.task.worker.probe", data, delivery_count=2)

    with pytest.raises(NatsTransportError, match="transient handler failed"):
        await transport.consume_message(first)
    ack = await transport.consume_message(second)

    assert ack.status == "ack"
    assert calls == 2
    assert first.acked == 0
    assert first.nacked == 1
    assert second.acked == 1
    assert second.nacked == 0
    ledger = await runtime.get_run_ledger(identity.run_id)
    consume_records = [
        record for record in ledger["idempotency_records"]
        if record.side_effect_key.startswith("nats_consume:")
    ]
    assert any(record.status == "failed" and ":retry:" not in record.side_effect_key for record in consume_records)
    assert any(record.status == "completed" and ":retry:" in record.side_effect_key for record in consume_records)


@pytest.mark.asyncio
async def test_consume_stale_started_record_is_retryable(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-stale", idempotency_key="idem-stale")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)
    seen: list[str] = []

    def handler(task: A2ATask) -> A2ATask:
        seen.append(task.id)
        task.status = A2ATaskStatus.COMPLETED
        return task

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(
        runtime_state=runtime,
        server=server,
        jetstream=fake_js,
        config=NatsTransportConfig(idempotency_stale_after_s=0),
    )
    task = _task(identity, task_id="a2a-stale")
    await transport.publish_task(task, identity=identity)
    data = fake_js.published[0][1]
    envelope = json.loads(data.decode("utf-8"))
    subject = "dharma.a2a.task.worker.probe"
    side_effect_key = f"nats_consume:{subject}:{task.id}"
    await runtime.try_begin_idempotent_side_effect(
        identity.with_updates(message_id=envelope["message_id"]),
        side_effect_key,
        metadata=_consume_metadata(subject, task.id, identity, envelope["message_id"]),
    )
    message = _FakeMessage(subject, data, delivery_count=2)

    ack = await transport.consume_message(message)

    assert ack.status == "ack"
    assert message.acked == 1
    assert seen == ["a2a-stale"]
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(
        record.side_effect_key == side_effect_key and record.status == "stale"
        for record in ledger["idempotency_records"]
    )
    assert any(
        record.side_effect_key.startswith(f"{side_effect_key}:retry:") and record.status == "completed"
        for record in ledger["idempotency_records"]
    )


@pytest.mark.asyncio
async def test_consume_in_progress_duplicate_is_nacked_not_acked(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-in-progress", idempotency_key="idem-in-progress")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)
    seen: list[str] = []

    def handler(task: A2ATask) -> A2ATask:
        seen.append(task.id)
        return task

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(runtime_state=runtime, server=server, jetstream=fake_js)
    task = _task(identity, task_id="a2a-in-progress")
    await transport.publish_task(task, identity=identity)
    data = fake_js.published[0][1]
    envelope = json.loads(data.decode("utf-8"))
    subject = "dharma.a2a.task.worker.probe"
    side_effect_key = f"nats_consume:{subject}:{task.id}"
    await runtime.try_begin_idempotent_side_effect(
        identity.with_updates(message_id=envelope["message_id"]),
        side_effect_key,
        metadata=_consume_metadata(subject, task.id, identity, envelope["message_id"]),
        stale_after_seconds=300,
    )
    message = _FakeMessage(subject, data, delivery_count=1)

    with pytest.raises(NatsTransportError, match="still in progress"):
        await transport.consume_message(message)

    assert seen == []
    assert message.acked == 0
    assert message.nacked == 1
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(
        receipt.receipt_type == "nats_consume" and receipt.status == "retry_blocked"
        for receipt in ledger["receipts"]
    )


@pytest.mark.asyncio
async def test_duplicate_consume_ack_failure_records_truth_not_duplicate_success(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-duplicate-ack-fail", idempotency_key="idem-duplicate-ack-fail")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)

    def handler(task: A2ATask) -> A2ATask:
        task.status = A2ATaskStatus.COMPLETED
        return task

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(runtime_state=runtime, server=server, jetstream=fake_js)
    await transport.publish_task(_task(identity, task_id="a2a-duplicate-ack-fail"), identity=identity)
    data = fake_js.published[0][1]
    first = _FakeMessage("dharma.a2a.task.worker.probe", data)
    duplicate = _FakeMessage("dharma.a2a.task.worker.probe", data, fail_ack=True)

    first_ack = await transport.consume_message(first)
    with pytest.raises(NatsTransportError, match="duplicate NATS consume ack failed"):
        await transport.consume_message(duplicate)

    assert first_ack.status == "ack"
    assert first.acked == 1
    assert duplicate.acked == 0
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(
        receipt.receipt_type == "nats_consume" and receipt.status == "duplicate_ack_failed"
        for receipt in ledger["receipts"]
    )
    assert not any(
        receipt.receipt_type == "nats_consume"
        and receipt.status == "duplicate"
        and receipt.payload.get("duplicate_truth") == "completed_side_effect_reused"
        for receipt in ledger["receipts"]
        if receipt.payload.get("error") == "broker ack failed"
    )


@pytest.mark.asyncio
async def test_consume_max_delivery_publishes_dlq_and_acks_original(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    identity = _identity(run_id="run-dlq", idempotency_key="idem-dlq")
    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)

    def handler(task: A2ATask) -> A2ATask:
        raise RuntimeError("poison message")

    server.register_handler("probe", handler)
    transport = A2ANatsTransport(
        runtime_state=runtime,
        server=server,
        jetstream=fake_js,
        config=NatsTransportConfig(max_deliveries=3),
    )
    await transport.publish_task(_task(identity, task_id="a2a-dlq"), identity=identity)
    message = _FakeMessage("dharma.a2a.task.worker.probe", fake_js.published[0][1], delivery_count=3)

    ack = await transport.consume_message(message)

    assert ack.action == "dlq"
    assert ack.status == "dlq"
    assert message.acked == 1
    assert message.nacked == 0
    assert len(fake_js.published) == 2
    dlq_subject, dlq_encoded, dlq_headers = fake_js.published[1]
    assert dlq_subject == "dharma.dlq.ds_tasks.a2a_task_handler"
    assert dlq_headers["Nats-Msg-Id"]
    dlq_envelope = json.loads(dlq_encoded.decode("utf-8"))
    assert dlq_envelope["schema"] == "dharma.nats.envelope.v1"
    assert dlq_envelope["subject"] == dlq_subject
    assert dlq_envelope["kind"] == "event"
    assert dlq_envelope["payload"]["schema"] == "dharma.nats.dlq_failure.v1"
    assert dlq_envelope["payload"]["operator_blocker"] == "NATS_MAX_DELIVER_EXHAUSTED"
    assert dlq_envelope["payload"]["delivery_count"] == 3
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(receipt.receipt_type == "nats_consume" and receipt.status == "dlq" for receipt in ledger["receipts"])


@pytest.mark.asyncio
async def test_transport_can_declare_durable_stream_and_consumer_contract(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    fake_js = _FakeJetStream()
    transport = A2ANatsTransport(runtime_state=runtime, jetstream=fake_js)

    streams = await transport.ensure_stream_topology()
    consumer = await transport.ensure_task_consumer(filter_subject="dharma.a2a.task.worker.probe")

    assert streams == {"status": "ok", "streams": ["DS_TASKS", "DS_DLQ"]}
    assert consumer["stream"] == "DS_TASKS"
    assert consumer["consumer"] == "a2a_task_handler"
    assert consumer["ack_policy"] == "explicit"
    assert consumer["max_deliver"] == 3
    assert len(fake_js.streams) == 2
    assert len(fake_js.consumers) == 1


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


def _consume_metadata(
    subject: str,
    task_id: str,
    identity: ExecutionIdentity,
    message_id: str,
) -> dict[str, str]:
    operation = hashlib.sha256(
        "|".join((subject, task_id, identity.correlation_id)).encode("utf-8")
    ).hexdigest()
    return {
        "surface": "a2a.nats_transport.consume",
        "subject": subject,
        "external_a2a_task_id": task_id,
        "message_id": message_id,
        "operation_hash": operation,
    }
