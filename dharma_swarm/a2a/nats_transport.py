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
    stream_name: str = "DHARMA_A2A"
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


@dataclass(frozen=True)
class NatsConsumeAck:
    task_id: str
    subject: str
    action: str
    status: str
    receipt_id: str
    duplicate: bool = False
    error: str = ""


class NatsTransportError(RuntimeError):
    """Raised after a NATS adapter side effect records a nack receipt."""


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

    async def publish_task(
        self,
        task: A2ATask,
        *,
        identity: ExecutionIdentity | None = None,
        subject: str | None = None,
    ) -> NatsPublishAck:
        resolved_identity = self._resolve_identity(task, identity=identity)
        resolved_subject = subject or self.subject_for_task(task)
        side_effect_key = f"nats_publish:{resolved_subject}:{task.id}"
        metadata = {
            "surface": "a2a.nats_transport.publish",
            "subject": resolved_subject,
            "external_a2a_task_id": task.id,
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
        if not await self.runtime_state.try_begin_idempotent_side_effect(
            resolved_identity,
            side_effect_key,
            metadata=metadata,
            stale_after_seconds=self.config.idempotency_stale_after_s,
        ):
            receipt = await self.runtime_state.record_receipt_for_identity(
                resolved_identity,
                receipt_type="nats_publish",
                status="duplicate",
                side_effect_key=side_effect_key,
                payload={**metadata, "action": "ack", "duplicate": True},
            )
            return NatsPublishAck(
                task_id=task.id,
                subject=resolved_subject,
                action="ack",
                status="duplicate",
                receipt_id=receipt.receipt_id,
                duplicate=True,
            )

        if self.jetstream is None:
            await self.connect()
        if self.jetstream is None:
            raise NatsTransportError("JetStream client is unavailable after connect")

        payload = _task_to_wire(task, resolved_identity)
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        headers = {
            "Dharma-Trace-Id": resolved_identity.trace_id,
            "Dharma-Correlation-Id": resolved_identity.correlation_id,
            "Dharma-Run-Id": resolved_identity.run_id,
            "Dharma-Task-Id": resolved_identity.task_id,
            "Dharma-Idempotency-Key": resolved_identity.idempotency_key,
        }
        try:
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
        )

    async def consume_message(self, message: NatsMessageLike) -> NatsConsumeAck:
        subject = str(message.subject)
        try:
            payload = json.loads(message.data.decode("utf-8"))
            task = _task_from_wire(payload)
            identity = ExecutionIdentity.from_metadata(
                payload.get("execution_identity"),
                require=True,
            )
            if identity is None:
                raise MissingExecutionIdentity("NATS payload is missing ExecutionIdentity")
        except Exception as exc:
            await _nack(message)
            raise NatsTransportError(f"invalid NATS A2A payload: {exc}") from exc

        side_effect_key = f"nats_consume:{subject}:{task.id}"
        metadata = {
            "surface": "a2a.nats_transport.consume",
            "subject": subject,
            "external_a2a_task_id": task.id,
            "operation_hash": _operation_hash(subject, task.id, identity.correlation_id),
        }
        await self.runtime_state.record_execution_identity(
            identity,
            source="a2a.nats_transport.consume",
            metadata=metadata,
        )
        if not await self.runtime_state.try_begin_idempotent_side_effect(
            identity,
            side_effect_key,
            metadata=metadata,
            stale_after_seconds=self.config.idempotency_stale_after_s,
        ):
            await _ack(message)
            receipt = await self.runtime_state.record_receipt_for_identity(
                identity,
                receipt_type="nats_consume",
                status="duplicate",
                side_effect_key=side_effect_key,
                payload={**metadata, "action": "ack", "duplicate": True},
            )
            return NatsConsumeAck(
                task_id=task.id,
                subject=subject,
                action="ack",
                status="duplicate",
                receipt_id=receipt.receipt_id,
                duplicate=True,
            )

        try:
            result = self.server.submit(task) if self.server is not None else task
            if result.status in {
                A2ATaskStatus.FAILED,
                A2ATaskStatus.REJECTED,
                A2ATaskStatus.CANCELLED,
            }:
                raise NatsTransportError(result.error or f"A2A task ended {result.status.value}")
            await _ack(message)
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
            )
        except Exception as exc:
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


def _task_to_wire(task: A2ATask, identity: ExecutionIdentity) -> dict[str, Any]:
    return {
        "schema": "dharma.a2a.nats_task.v1",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "execution_identity": identity.to_dict(),
        "task": _json_ready(asdict(task)),
    }


def _task_from_wire(payload: dict[str, Any]) -> A2ATask:
    raw = dict(payload.get("task") or {})
    history = [_message_from_dict(item) for item in raw.get("history") or raw.get("messages") or []]
    artifacts = [_artifact_from_dict(item) for item in raw.get("artifacts") or []]
    extensions = [_extension_from_dict(item) for item in raw.get("extensions") or []]
    metadata = dict(raw.get("metadata") or {})
    identity = payload.get("execution_identity")
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
