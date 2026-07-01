"""NATS/JetStream transport adapter for A2A runtime truth.

This module is import-safe when nats-py is absent. The real client is imported
only by ``connect()``, while tests and local adapters can inject a JetStream-like
object that exposes ``publish``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from dharma_swarm.a2a.spine_adapter import submit_task_via_spine
from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2AExtension,
    A2AMessage,
    A2APart,
    A2APartType,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


class JetStreamLike(Protocol):
    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        ...


class NatsMessageLike(Protocol):
    subject: str
    data: bytes

    async def ack(self) -> Any:
        ...

    async def nak(self) -> Any:
        ...


@dataclass(frozen=True)
class NatsTransportConfig:
    endpoint: str = "nats://127.0.0.1:4222"
    subject_prefix: str = "dharma.a2a"
    stream_name: str = "DS_TASKS"
    dlq_stream_name: str = "DS_DLQ"
    consumer_name: str = "a2a_task_handler"
    dlq_subject_prefix: str = "dharma.dlq"
    max_deliveries: int = 3
    publish_timeout_s: float = 2.0
    idempotency_stale_after_s: float | None = 300.0


@dataclass(frozen=True)
class NatsPublishAck:
    task_id: str
    subject: str
    action: str
    status: str
    receipt_id: str
    stream: str = ""
    seq: int | None = None
    duplicate: bool = False
    message_id: str = ""


@dataclass(frozen=True)
class NatsConsumeAck:
    task_id: str
    subject: str
    action: str
    status: str
    receipt_id: str
    duplicate: bool = False
    error: str = ""
    message_id: str = ""


class NatsTransportError(RuntimeError):
    """Raised after a NATS adapter side effect records a nack receipt."""


@dataclass(frozen=True)
class _IdempotencyDecision:
    action: str
    side_effect_key: str
    metadata: dict[str, Any]
    existing_status: str = ""


class A2ANatsTransport:
    """Runtime-state-backed NATS/JetStream adapter for A2A tasks."""

    def __init__(
        self,
        *,
        runtime_state: RuntimeStateStore,
        server: A2AServer | None = None,
        jetstream: JetStreamLike | None = None,
        config: NatsTransportConfig | None = None,
        require_execution_identity: bool = True,
    ) -> None:
        if server is not None and not bool(getattr(server, "_require_execution_identity", False)):
            raise NatsTransportError(
                "A2ANatsTransport requires A2AServer(require_execution_identity=True)"
            )
        self.runtime_state = runtime_state
        self.server = server
        self.jetstream = jetstream
        self.config = config or NatsTransportConfig()
        self.require_execution_identity = require_execution_identity
        self._nats_connection: Any | None = None

    async def connect(self) -> None:
        """Connect to a real NATS server and bind ``self.jetstream``.

        This is the only method that imports nats-py. Importing this module,
        constructing the adapter, and running offline tests do not need the
        optional dependency.
        """

        if self.jetstream is not None:
            return
        import nats

        self._nats_connection = await nats.connect(
            servers=[self.config.endpoint],
            allow_reconnect=False,
            max_reconnect_attempts=0,
        )
        self.jetstream = self._nats_connection.jetstream()

    async def close(self) -> None:
        if self._nats_connection is not None:
            await self._nats_connection.close()
            self._nats_connection = None

    async def ensure_stream_topology(self) -> dict[str, Any]:
        """Create the canonical task and DLQ streams when the broker supports it."""

        if self.jetstream is None:
            await self.connect()
        if self.jetstream is None:
            raise NatsTransportError("JetStream client is unavailable after connect")
        if not hasattr(self.jetstream, "add_stream"):
            return {"status": "skipped", "reason": "jetstream has no add_stream"}

        try:
            from nats.js.api import DiscardPolicy, RetentionPolicy, StorageType, StreamConfig

            task_config: Any = StreamConfig(
                name=self.config.stream_name,
                subjects=[f"{self.config.subject_prefix}.task.>"],
                retention=RetentionPolicy.LIMITS,
                storage=StorageType.FILE,
                max_age=30 * 24 * 60 * 60,
                duplicate_window=10 * 60,
                discard=DiscardPolicy.OLD,
            )
            dlq_config: Any = StreamConfig(
                name=self.config.dlq_stream_name,
                subjects=[f"{self.config.dlq_subject_prefix}.>"],
                retention=RetentionPolicy.LIMITS,
                storage=StorageType.FILE,
                max_age=90 * 24 * 60 * 60,
                duplicate_window=10 * 60,
                discard=DiscardPolicy.OLD,
            )
        except Exception:
            task_config = {
                "name": self.config.stream_name,
                "subjects": [f"{self.config.subject_prefix}.task.>"],
                "retention": "limits",
                "storage": "file",
                "max_age": 30 * 24 * 60 * 60,
                "duplicate_window": 10 * 60,
                "discard": "old",
            }
            dlq_config = {
                "name": self.config.dlq_stream_name,
                "subjects": [f"{self.config.dlq_subject_prefix}.>"],
                "retention": "limits",
                "storage": "file",
                "max_age": 90 * 24 * 60 * 60,
                "duplicate_window": 10 * 60,
                "discard": "old",
            }

        created: list[str] = []
        for name, config in (
            (self.config.stream_name, task_config),
            (self.config.dlq_stream_name, dlq_config),
        ):
            try:
                await self.jetstream.add_stream(config)
            except TypeError:
                await self.jetstream.add_stream(**config)
            except Exception:
                pass
            created.append(name)
        return {"status": "ok", "streams": created}

    async def ensure_task_consumer(
        self,
        *,
        durable: str | None = None,
        filter_subject: str | None = None,
    ) -> dict[str, Any]:
        """Create a stable explicit-ack durable consumer for the task stream."""

        if self.jetstream is None:
            await self.connect()
        if self.jetstream is None:
            raise NatsTransportError("JetStream client is unavailable after connect")
        if not hasattr(self.jetstream, "add_consumer"):
            return {"status": "skipped", "reason": "jetstream has no add_consumer"}

        consumer = _consumer_slug(durable or self.config.consumer_name)
        subject = filter_subject or f"{self.config.subject_prefix}.task.>"
        try:
            from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy, ReplayPolicy

            config: Any = ConsumerConfig(
                durable_name=consumer,
                filter_subject=subject,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=60,
                max_deliver=self.config.max_deliveries,
                deliver_policy=DeliverPolicy.NEW,
                replay_policy=ReplayPolicy.INSTANT,
            )
            await self.jetstream.add_consumer(self.config.stream_name, config=config)
        except Exception:
            config = {
                "durable_name": consumer,
                "filter_subject": subject,
                "ack_policy": "explicit",
                "ack_wait": 60,
                "max_deliver": self.config.max_deliveries,
                "deliver_policy": "new",
                "replay_policy": "instant",
            }
            try:
                await self.jetstream.add_consumer(self.config.stream_name, config=config)
            except TypeError:
                await self.jetstream.add_consumer(self.config.stream_name, **config)
        return {
            "status": "ok",
            "stream": self.config.stream_name,
            "consumer": consumer,
            "filter_subject": subject,
            "ack_policy": "explicit",
            "max_deliver": self.config.max_deliveries,
        }

    async def publish_task(
        self,
        task: A2ATask,
        *,
        identity: ExecutionIdentity | None = None,
        subject: str | None = None,
    ) -> NatsPublishAck:
        resolved_identity = self._resolve_identity(task, identity=identity)
        resolved_subject = subject or self.subject_for_task(task)
        message_id = _message_id(resolved_subject, task.id, resolved_identity)
        resolved_identity = resolved_identity.with_updates(message_id=message_id)
        side_effect_key = f"nats_publish:{resolved_subject}:{task.id}"
        metadata = {
            "surface": "a2a.nats_transport.publish",
            "subject": resolved_subject,
            "external_a2a_task_id": task.id,
            "message_id": message_id,
            "operation_hash": _operation_hash(
                resolved_subject,
                task.id,
                resolved_identity.correlation_id,
            ),
        }
        await self.runtime_state.record_execution_identity(
            resolved_identity,
            source="a2a.nats_transport.publish",
            metadata=metadata,
        )
        idempotency = await self._begin_idempotent_side_effect(
            resolved_identity,
            side_effect_key,
            metadata=metadata,
        )
        side_effect_key = idempotency.side_effect_key
        metadata = idempotency.metadata
        if idempotency.action == "duplicate":
            receipt = await self.runtime_state.record_receipt_for_identity(
                resolved_identity,
                receipt_type="nats_publish",
                status="duplicate",
                side_effect_key=side_effect_key,
                payload={
                    **metadata,
                    "action": "ack",
                    "duplicate": True,
                    "duplicate_truth": "completed_side_effect_reused",
                },
            )
            return NatsPublishAck(
                task_id=task.id,
                subject=resolved_subject,
                action="ack",
                status="duplicate",
                receipt_id=receipt.receipt_id,
                duplicate=True,
                message_id=message_id,
            )
        if idempotency.action == "blocked":
            receipt = await self.runtime_state.record_receipt_for_identity(
                resolved_identity,
                receipt_type="nats_publish",
                status="retry_blocked",
                side_effect_key=side_effect_key,
                payload={
                    **metadata,
                    "action": "retry_blocked",
                    "existing_status": idempotency.existing_status,
                },
            )
            raise NatsTransportError(
                "NATS publish idempotency record is still in progress: "
                f"{side_effect_key} status={idempotency.existing_status} receipt={receipt.receipt_id}"
            )

        try:
            if self.jetstream is None:
                await self.connect()
            if self.jetstream is None:
                raise NatsTransportError("JetStream client is unavailable after connect")
            payload = _task_to_wire(task, resolved_identity, subject=resolved_subject)
            encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
            headers = _nats_headers(resolved_identity, message_id=message_id)
            pub_ack = await self.jetstream.publish(
                resolved_subject,
                encoded,
                headers=headers,
                timeout=self.config.publish_timeout_s,
            )
        except Exception as exc:
            receipt = await self.runtime_state.record_receipt_for_identity(
                resolved_identity,
                receipt_type="nats_publish",
                status="nack",
                side_effect_key=side_effect_key,
                payload={**metadata, "action": "nack", "error": str(exc)},
            )
            await self.runtime_state.complete_idempotent_side_effect(
                resolved_identity,
                side_effect_key,
                status="failed",
                result_receipt_id=receipt.receipt_id,
                metadata={"error": str(exc), **metadata},
            )
            raise NatsTransportError(str(exc)) from exc

        stream = str(getattr(pub_ack, "stream", "") or "")
        seq = getattr(pub_ack, "seq", None)
        receipt = await self.runtime_state.record_receipt_for_identity(
            resolved_identity,
            receipt_type="nats_publish",
            status="ack",
            side_effect_key=side_effect_key,
            payload={
                **metadata,
                "action": "ack",
                "stream": stream,
                "seq": seq,
                "message_id": message_id,
                "ack_contract": "publish_ack",
            },
        )
        await self.runtime_state.complete_idempotent_side_effect(
            resolved_identity,
            side_effect_key,
            result_receipt_id=receipt.receipt_id,
            metadata={"stream": stream, "seq": seq, **metadata},
        )
        return NatsPublishAck(
            task_id=task.id,
            subject=resolved_subject,
            action="ack",
            status="ack",
            receipt_id=receipt.receipt_id,
            stream=stream,
            seq=int(seq) if isinstance(seq, int) else None,
            message_id=message_id,
        )

    async def consume_message(self, message: NatsMessageLike) -> NatsConsumeAck:
        subject = str(message.subject)
        try:
            payload = json.loads(message.data.decode("utf-8"))
            task = _task_from_wire(payload)
            identity = _identity_from_wire(payload)
            if identity is None:
                raise MissingExecutionIdentity("NATS payload is missing ExecutionIdentity")
        except Exception as exc:
            await _nack(message)
            raise NatsTransportError(f"invalid NATS A2A payload: {exc}") from exc

        message_id = str(payload.get("message_id") or identity.message_id or "")
        if message_id and identity.message_id != message_id:
            identity = identity.with_updates(message_id=message_id)
        side_effect_key = f"nats_consume:{subject}:{task.id}"
        metadata = {
            "surface": "a2a.nats_transport.consume",
            "subject": subject,
            "external_a2a_task_id": task.id,
            "message_id": message_id,
            "operation_hash": _operation_hash(subject, task.id, identity.correlation_id),
        }
        await self.runtime_state.record_execution_identity(
            identity,
            source="a2a.nats_transport.consume",
            metadata=metadata,
        )
        idempotency = await self._begin_idempotent_side_effect(
            identity,
            side_effect_key,
            metadata=metadata,
        )
        side_effect_key = idempotency.side_effect_key
        metadata = idempotency.metadata
        if idempotency.action == "duplicate":
            try:
                await _ack(message)
            except Exception as exc:
                await self.runtime_state.record_receipt_for_identity(
                    identity,
                    receipt_type="nats_consume",
                    status="duplicate_ack_failed",
                    side_effect_key=side_effect_key,
                    payload={
                        **metadata,
                        "action": "ack",
                        "duplicate": True,
                        "error": str(exc),
                    },
                )
                raise NatsTransportError(f"duplicate NATS consume ack failed: {exc}") from exc
            receipt = await self.runtime_state.record_receipt_for_identity(
                identity,
                receipt_type="nats_consume",
                status="duplicate",
                side_effect_key=side_effect_key,
                payload={
                    **metadata,
                    "action": "ack",
                    "duplicate": True,
                    "duplicate_truth": "completed_side_effect_reused",
                },
            )
            return NatsConsumeAck(
                task_id=task.id,
                subject=subject,
                action="ack",
                status="duplicate",
                receipt_id=receipt.receipt_id,
                duplicate=True,
                message_id=message_id,
            )
        if idempotency.action == "blocked":
            await _nack(message)
            receipt = await self.runtime_state.record_receipt_for_identity(
                identity,
                receipt_type="nats_consume",
                status="retry_blocked",
                side_effect_key=side_effect_key,
                payload={
                    **metadata,
                    "action": "nack",
                    "existing_status": idempotency.existing_status,
                },
            )
            raise NatsTransportError(
                "NATS consume idempotency record is still in progress: "
                f"{side_effect_key} status={idempotency.existing_status} receipt={receipt.receipt_id}"
            )

        broker_acked = False
        try:
            if self.server is not None:
                # Spine-adopted ingress: the local dispatch flows through
                # invoke_agent() and emits exactly one EvidenceReceipt, on
                # top of the transport-level RuntimeReceipt/idempotency
                # records this method already writes.
                result, spine_receipt = await submit_task_via_spine(
                    self.server, task, router_name="nats_transport",
                )
                if (
                    spine_receipt.status == "failed"
                    and not spine_receipt.provider_attempted
                ):
                    # submit() raised pre-spine: preserve the exception →
                    # nack contract of the original ingress path.
                    raise NatsTransportError(
                        spine_receipt.error_detail or "A2A submit failed"
                    )
            else:
                result = task
            if result.status in {
                A2ATaskStatus.FAILED,
                A2ATaskStatus.REJECTED,
                A2ATaskStatus.CANCELLED,
            }:
                raise NatsTransportError(result.error or f"A2A task ended {result.status.value}")
            await self.runtime_state.record_receipt_for_identity(
                identity,
                receipt_type="nats_consume",
                status="ack_intent",
                side_effect_key=side_effect_key,
                payload={
                    **metadata,
                    "action": "ack_intent",
                    "a2a_status": result.status.value,
                    "ack_contract": "consumer_ack_intent",
                },
            )
            await _ack(message)
            broker_acked = True
            receipt = await self.runtime_state.record_receipt_for_identity(
                identity,
                receipt_type="nats_consume",
                status="ack",
                side_effect_key=side_effect_key,
                payload={
                    **metadata,
                    "action": "ack",
                    "a2a_status": result.status.value,
                    "ack_contract": "consumer_ack",
                },
            )
            await self.runtime_state.complete_idempotent_side_effect(
                identity,
                side_effect_key,
                result_receipt_id=receipt.receipt_id,
                metadata={"a2a_status": result.status.value, **metadata},
            )
            return NatsConsumeAck(
                task_id=task.id,
                subject=subject,
                action="ack",
                status="ack",
                receipt_id=receipt.receipt_id,
                message_id=message_id,
            )
        except Exception as exc:
            if broker_acked:
                await self.runtime_state.record_receipt_for_identity(
                    identity,
                    receipt_type="nats_consume",
                    status="ack_finalization_error",
                    side_effect_key=side_effect_key,
                    payload={**metadata, "action": "ack", "error": str(exc)},
                )
                raise NatsTransportError(
                    f"NATS broker ack succeeded but runtime finalization failed: {exc}"
                ) from exc
            if _message_delivery_count(message) >= self.config.max_deliveries:
                try:
                    receipt = await self._publish_dlq(
                        original_subject=subject,
                        original_payload=payload,
                        identity=identity,
                        task=task,
                        side_effect_key=side_effect_key,
                        metadata=metadata,
                        error=str(exc),
                        delivery_count=_message_delivery_count(message),
                    )
                    await _ack(message)
                    await self.runtime_state.complete_idempotent_side_effect(
                        identity,
                        side_effect_key,
                        status="failed",
                        result_receipt_id=receipt.receipt_id,
                        metadata={"error": str(exc), "dlq": True, **metadata},
                    )
                    return NatsConsumeAck(
                        task_id=task.id,
                        subject=subject,
                        action="dlq",
                        status="dlq",
                        receipt_id=receipt.receipt_id,
                        error=str(exc),
                        message_id=message_id,
                    )
                except Exception as dlq_exc:
                    await self.runtime_state.record_receipt_for_identity(
                        identity,
                        receipt_type="nats_consume",
                        status="dlq_failed",
                        side_effect_key=side_effect_key,
                        payload={
                            **metadata,
                            "action": "nack",
                            "error": str(exc),
                            "dlq_error": str(dlq_exc),
                        },
                    )
            await _nack(message)
            receipt = await self.runtime_state.record_receipt_for_identity(
                identity,
                receipt_type="nats_consume",
                status="nack",
                side_effect_key=side_effect_key,
                payload={**metadata, "action": "nack", "error": str(exc)},
            )
            await self.runtime_state.complete_idempotent_side_effect(
                identity,
                side_effect_key,
                status="failed",
                result_receipt_id=receipt.receipt_id,
                metadata={"error": str(exc), **metadata},
            )
            raise NatsTransportError(str(exc)) from exc

    def subject_for_task(self, task: A2ATask) -> str:
        target = _subject_token(task.to_agent or "unassigned")
        capability = _subject_token(task.capability or "default")
        return f"{self.config.subject_prefix}.task.{target}.{capability}"

    def _resolve_identity(
        self,
        task: A2ATask,
        *,
        identity: ExecutionIdentity | None,
    ) -> ExecutionIdentity:
        if identity is None:
            identity = ExecutionIdentity.from_metadata(
                task.metadata,
                task_id=task.dharma_task_id or task.id,
                agent_id=task.to_agent,
                session_id=str((task.metadata or {}).get("session_id") or ""),
                require=self.require_execution_identity,
            )
        if identity is None:
            raise MissingExecutionIdentity("NATS A2A transport requires ExecutionIdentity")
        identity = identity.with_updates(external_a2a_task_id=task.id)
        task.trace_id = identity.trace_id
        task.dharma_task_id = task.dharma_task_id or identity.task_id
        task.metadata.update(
            {
                "execution_identity": identity.to_dict(),
                "trace_id": identity.trace_id,
                "correlation_id": identity.correlation_id,
                "run_id": identity.run_id,
                "claim_id": identity.claim_id,
                "idempotency_key": identity.idempotency_key,
                "external_a2a_task_id": identity.external_a2a_task_id,
            }
        )
        return identity.require_for_dispatch()

    async def _begin_idempotent_side_effect(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        metadata: dict[str, Any],
    ) -> _IdempotencyDecision:
        if await self.runtime_state.try_begin_idempotent_side_effect(
            identity,
            side_effect_key,
            metadata=metadata,
            stale_after_seconds=self.config.idempotency_stale_after_s,
        ):
            return _IdempotencyDecision("proceed", side_effect_key, metadata)

        existing = await self.runtime_state.get_idempotency_record(
            identity.idempotency_key,
            side_effect_key,
        )
        status = str(existing.status if existing is not None else "missing")
        if status in {"completed", "skipped"}:
            return _IdempotencyDecision("duplicate", side_effect_key, metadata, status)
        if status in {"failed", "stale"}:
            retry_key = f"{side_effect_key}:retry:{uuid4().hex[:12]}"
            retry_metadata = {
                **metadata,
                "retry_of_side_effect_key": side_effect_key,
                "retry_of_status": status,
                "retry_of_result_receipt_id": str(existing.result_receipt_id if existing else ""),
            }
            began_retry = await self.runtime_state.try_begin_idempotent_side_effect(
                identity,
                retry_key,
                metadata=retry_metadata,
                stale_after_seconds=self.config.idempotency_stale_after_s,
            )
            if began_retry:
                return _IdempotencyDecision("proceed", retry_key, retry_metadata, status)
        return _IdempotencyDecision("blocked", side_effect_key, metadata, status)

    async def _publish_dlq(
        self,
        *,
        original_subject: str,
        original_payload: dict[str, Any],
        identity: ExecutionIdentity,
        task: A2ATask,
        side_effect_key: str,
        metadata: dict[str, Any],
        error: str,
        delivery_count: int,
    ):
        if self.jetstream is None:
            await self.connect()
        if self.jetstream is None:
            raise NatsTransportError("JetStream client is unavailable for DLQ publish")
        dlq_subject = self.dlq_subject_for_consumer()
        original_message_id = str(original_payload.get("message_id") or identity.message_id or "")
        dlq_message_id = "nmsg_" + _operation_hash(
            "dlq",
            dlq_subject,
            task.id,
            identity.trace_id,
            identity.correlation_id,
            original_message_id,
        )[:32]
        dlq_identity = identity.with_updates(
            causation_id=identity.causation_id or original_message_id,
            message_id=dlq_message_id,
        )
        dlq_payload = _dlq_to_wire(
            task=task,
            identity=dlq_identity,
            subject=dlq_subject,
            original_subject=original_subject,
            original_message_id=original_message_id,
            original_payload=original_payload,
            error=error,
            delivery_count=delivery_count,
            max_deliveries=self.config.max_deliveries,
        )
        await self.jetstream.publish(
            dlq_subject,
            json.dumps(dlq_payload, ensure_ascii=True, sort_keys=True).encode("utf-8"),
            headers=_nats_headers(dlq_identity, message_id=dlq_identity.message_id),
            timeout=self.config.publish_timeout_s,
        )
        return await self.runtime_state.record_receipt_for_identity(
            identity,
            receipt_type="nats_consume",
            status="dlq",
            side_effect_key=side_effect_key,
            payload={
                **metadata,
                "action": "dlq",
                "dlq_subject": dlq_subject,
                "original_subject": original_subject,
                "original_message_id": original_message_id,
                "delivery_count": delivery_count,
                "max_deliveries": self.config.max_deliveries,
                "error": error,
            },
        )

    def dlq_subject_for_consumer(self, *, consumer: str | None = None) -> str:
        return (
            f"{self.config.dlq_subject_prefix}."
            f"{_subject_token(self.config.stream_name)}."
            f"{_consumer_slug(consumer or self.config.consumer_name)}"
        )


NATS_ENVELOPE_SCHEMA = "dharma.nats.envelope.v1"
A2A_TASK_PAYLOAD_SCHEMA = "dharma.a2a.nats_task.v1"
DLQ_PAYLOAD_SCHEMA = "dharma.nats.dlq_failure.v1"


def _task_to_wire(task: A2ATask, identity: ExecutionIdentity, *, subject: str) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    message_id = identity.message_id or _message_id(subject, task.id, identity)
    task_payload = _json_ready(asdict(task))
    actor = _actor_fields(
        from_agent=task.from_agent,
        to_agent=task.to_agent or "fleet",
        identity=identity,
    )
    causality = _causality_fields(identity, message_id=message_id)
    return {
        "schema": NATS_ENVELOPE_SCHEMA,
        "message_id": message_id,
        "trace_id": identity.trace_id,
        "span_id": identity.run_id,
        "parent_span_id": identity.parent_run_id,
        "correlation_id": identity.correlation_id,
        "causation_id": identity.causation_id,
        "subject": subject,
        "from_agent": task.from_agent,
        "to_agent": task.to_agent or "fleet",
        "actor": actor,
        "causality": causality,
        "kind": "task",
        "created_at": created_at,
        "requires_ack": True,
        "payload": {
            "schema": A2A_TASK_PAYLOAD_SCHEMA,
            "sent_at": created_at,
            "execution_identity": identity.to_dict(),
            "task": task_payload,
        },
        "execution_identity": identity.to_dict(),
        "task": task_payload,
    }


def _task_from_wire(payload: dict[str, Any]) -> A2ATask:
    body = _wire_body(payload)
    raw = dict(body.get("task") or payload.get("task") or {})
    history = [_message_from_dict(item) for item in raw.get("history") or raw.get("messages") or []]
    artifacts = [_artifact_from_dict(item) for item in raw.get("artifacts") or []]
    extensions = [_extension_from_dict(item) for item in raw.get("extensions") or []]
    metadata = dict(raw.get("metadata") or {})
    identity = body.get("execution_identity") or payload.get("execution_identity")
    if isinstance(identity, dict):
        metadata["execution_identity"] = identity
    return A2ATask(
        id=str(raw.get("id") or uuid4().hex[:16]),
        context_id=str(raw.get("context_id") or ""),
        from_agent=str(raw.get("from_agent") or ""),
        to_agent=str(raw.get("to_agent") or ""),
        status=A2ATaskStatus(str(raw.get("status") or A2ATaskStatus.SUBMITTED.value)),
        history=history,
        artifacts=artifacts,
        capability=str(raw.get("capability") or ""),
        dharma_task_id=str(raw.get("dharma_task_id") or ""),
        created_at=str(raw.get("created_at") or datetime.now(timezone.utc).isoformat()),
        updated_at=str(raw.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        result=str(raw.get("result") or ""),
        error=str(raw.get("error") or ""),
        trace_id=str(raw.get("trace_id") or ""),
        extensions=extensions,
        metadata=metadata,
    )


def _identity_from_wire(payload: dict[str, Any]) -> ExecutionIdentity | None:
    body = _wire_body(payload)
    identity = body.get("execution_identity") or payload.get("execution_identity")
    if not isinstance(identity, dict):
        identity = {}
    identity = dict(identity)
    message_id = str(payload.get("message_id") or "")
    if message_id and not identity.get("message_id"):
        identity["message_id"] = message_id
    return ExecutionIdentity.from_metadata(identity, require=True)


def _wire_body(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get("payload")
    return dict(body) if isinstance(body, dict) else payload


def _dlq_to_wire(
    *,
    task: A2ATask,
    identity: ExecutionIdentity,
    subject: str,
    original_subject: str,
    original_message_id: str,
    original_payload: dict[str, Any],
    error: str,
    delivery_count: int,
    max_deliveries: int,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    actor = _actor_fields(
        from_agent=task.to_agent or "a2a_task_handler",
        to_agent="operator",
        identity=identity,
    )
    causality = _causality_fields(identity, message_id=identity.message_id)
    return {
        "schema": NATS_ENVELOPE_SCHEMA,
        "message_id": identity.message_id,
        "trace_id": identity.trace_id,
        "span_id": identity.run_id,
        "parent_span_id": identity.parent_run_id,
        "correlation_id": identity.correlation_id,
        "causation_id": identity.causation_id or original_message_id,
        "subject": subject,
        "from_agent": task.to_agent or "a2a_task_handler",
        "to_agent": "operator",
        "actor": actor,
        "causality": causality,
        "kind": "event",
        "created_at": created_at,
        "requires_ack": False,
        "payload": {
            "schema": DLQ_PAYLOAD_SCHEMA,
            "created_at": created_at,
            "task_id": task.id,
            "original_subject": original_subject,
            "original_message_id": original_message_id,
            "original_payload": original_payload,
            "error": error,
            "delivery_count": delivery_count,
            "max_deliveries": max_deliveries,
            "operator_blocker": "NATS_MAX_DELIVER_EXHAUSTED",
        },
    }


def _actor_fields(
    *,
    from_agent: str,
    to_agent: str,
    identity: ExecutionIdentity,
) -> dict[str, str]:
    return {
        "from_agent": str(from_agent or identity.agent_id or ""),
        "to_agent": str(to_agent or ""),
        "execution_agent": identity.agent_id,
        "session_id": identity.session_id,
    }


def _causality_fields(identity: ExecutionIdentity, *, message_id: str) -> dict[str, str]:
    return {
        "message_id": message_id,
        "trace_id": identity.trace_id,
        "span_id": identity.run_id,
        "parent_span_id": identity.parent_run_id,
        "correlation_id": identity.correlation_id,
        "causation_id": identity.causation_id,
    }


def _message_from_dict(raw: dict[str, Any]) -> A2AMessage:
    return A2AMessage(
        role=str(raw.get("role") or "user"),
        parts=[_part_from_dict(item) for item in raw.get("parts") or []],
        metadata=dict(raw.get("metadata") or {}),
    )


def _part_from_dict(raw: dict[str, Any]) -> A2APart:
    return A2APart(
        type=A2APartType(str(raw.get("type") or A2APartType.TEXT.value)),
        content=str(raw.get("content") or ""),
        media_type=str(raw.get("media_type") or ""),
        filename=str(raw.get("filename") or ""),
        metadata=dict(raw.get("metadata") or {}),
        _skip_validation=not bool(raw.get("content")),
    )


def _artifact_from_dict(raw: dict[str, Any]) -> A2AArtifact:
    return A2AArtifact(
        id=str(raw.get("id") or uuid4().hex[:12]),
        parts=[_part_from_dict(item) for item in raw.get("parts") or []],
        name=str(raw.get("name") or ""),
        description=str(raw.get("description") or ""),
        extensions=[_extension_from_dict(item) for item in raw.get("extensions") or []],
        metadata=dict(raw.get("metadata") or {}),
    )


def _extension_from_dict(raw: dict[str, Any]) -> A2AExtension:
    return A2AExtension(
        uri=str(raw.get("uri") or ""),
        required=bool(raw.get("required")),
        data=dict(raw.get("data") or {}),
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _subject_token(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in value.lower())
    return cleaned.strip("._-") or "default"


def _consumer_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in value.lower())
    return cleaned.strip("_-") or "consumer"


def _message_id(subject: str, task_id: str, identity: ExecutionIdentity) -> str:
    if identity.message_id:
        return identity.message_id
    return "nmsg_" + _operation_hash(
        subject,
        task_id,
        identity.trace_id,
        identity.correlation_id,
        identity.idempotency_key,
    )[:32]


def _nats_headers(identity: ExecutionIdentity, *, message_id: str) -> dict[str, str]:
    return {
        "Nats-Msg-Id": message_id,
        "Dharma-Nats-Schema": NATS_ENVELOPE_SCHEMA,
        "Dharma-Trace-Id": identity.trace_id,
        "Dharma-Correlation-Id": identity.correlation_id,
        "Dharma-Causation-Id": identity.causation_id,
        "Dharma-Run-Id": identity.run_id,
        "Dharma-Task-Id": identity.task_id,
        "Dharma-Idempotency-Key": identity.idempotency_key,
    }


def _message_delivery_count(message: NatsMessageLike) -> int:
    metadata = getattr(message, "metadata", None)
    try:
        if callable(metadata):
            metadata = metadata()
    except Exception:
        metadata = None
    for raw in (
        getattr(metadata, "num_delivered", None),
        getattr(metadata, "delivery_count", None),
        getattr(message, "num_delivered", None),
        getattr(message, "delivery_count", None),
    ):
        try:
            count = int(raw)
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return 1


def _operation_hash(*parts: str) -> str:
    import hashlib

    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


async def _ack(message: NatsMessageLike) -> None:
    await message.ack()


async def _nack(message: NatsMessageLike) -> None:
    if hasattr(message, "nak"):
        await message.nak()
    elif hasattr(message, "nack"):
        await getattr(message, "nack")()
    else:
        raise AttributeError("NATS message has neither nak nor nack")
