"""Wire-format helpers for the A2A NATS transport."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import ipaddress
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2AExtension,
    A2AMessage,
    A2APart,
    A2APartType,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.spine.identity import ExecutionIdentity


class NatsWireMessageLike(Protocol):
    subject: str
    data: bytes

    async def ack(self) -> Any:
        ...

    async def nak(self) -> Any:
        ...


NATS_ENVELOPE_SCHEMA = "dharma.nats.envelope.v1"
A2A_TASK_PAYLOAD_SCHEMA = "dharma.a2a.nats_task.v1"
DLQ_PAYLOAD_SCHEMA = "dharma.nats.dlq_failure.v1"

_NATS_DURATION_FIELDS = {
    "max_age",
    "duplicate_window",
    "ack_wait",
    "inactive_threshold",
    "idle_heartbeat",
}


def _nats_endpoint_is_loopback(endpoint: str) -> bool:
    """True only for literal loopback IPs or the exact localhost hostname."""

    try:
        host = urlparse(endpoint).hostname
        if host == "localhost":
            return True
        return bool(host and ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False


def _nats_endpoint_uses_tls(endpoint: str) -> bool:
    return urlparse(endpoint).scheme.lower() in {"tls", "wss"}


def _normalize_nats_topology_value(field: str, value: Any, expected: Any) -> Any:
    """Normalize nats.py enums and raw nanoseconds, preserving real drift."""

    value = getattr(value, "value", value)
    if value is None:
        return None
    if field == "backoff":
        return tuple(
            _normalize_nats_topology_value("ack_wait", item, 1.0)
            for item in value
        )
    if isinstance(expected, tuple) and isinstance(value, (list, tuple)):
        return tuple(getattr(item, "value", item) for item in value)
    if field in _NATS_DURATION_FIELDS and isinstance(value, (int, float)):
        # Raw JetStream API responses encode durations as nanoseconds. nats.py
        # model instances expose seconds. Only the raw-scale representation is
        # converted; None and all non-duration defaults remain visible drift.
        if abs(float(value)) >= 1_000_000_000 and abs(float(expected or 0)) < 100_000_000:
            return float(value) / 1_000_000_000
        return float(value)
    return value


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


def _message_delivery_count(message: NatsWireMessageLike) -> int:
    metadata = getattr(message, "metadata", None)
    try:
        if callable(metadata):
            metadata = metadata()
    except Exception as exc:
        metadata = _record_metadata_lookup_failure(exc)
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


async def _ack(message: NatsWireMessageLike) -> None:
    await message.ack()


async def _nack(message: NatsWireMessageLike) -> None:
    if hasattr(message, "nak"):
        await message.nak()
    elif hasattr(message, "nack"):
        await getattr(message, "nack")()
    else:
        raise AttributeError("NATS message has neither nak nor nack")


def _record_metadata_lookup_failure(exc: Exception) -> None:
    return None
