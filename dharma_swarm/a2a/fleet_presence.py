"""NATS fleet-presence projection through existing identity and state owners."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Literal, Protocol

from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry, resolve_agent_uid
from dharma_swarm.a2a.nats_transport_support import NATS_ENVELOPE_SCHEMA
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity

logger = logging.getLogger(__name__)
LEGACY_HEARTBEAT_SCHEMA = "dharma.a2a.send.v1"
FLEET_HEARTBEAT_PAYLOAD_SCHEMA = "dharma.a2a.fleet_heartbeat.v1"
FLEET_HEARTBEAT_SUBJECT = "dharma.a2a.fleet"
DEFAULT_PRESENCE_SUBJECT = "dharma.agent.*.presence"
DEFAULT_PRESENCE_URL = "nats://127.0.0.1:4222"
DEFAULT_PRESENCE_STREAM = "DS_PRESENCE"
DEFAULT_PRESENCE_DURABLE = "fleet_presence_projector"
_DEDICATED_FILTER = re.compile(r"dharma\.agent\.(?:\*|[A-Za-z0-9_-]+)\.presence")
_DEDICATED_MESSAGE = re.compile(r"dharma\.agent\.([A-Za-z0-9_-]+)\.presence")
_RESERVED_METADATA_KEYS = frozenset(
    "agent_uid from from_agent last_heartbeat message_id sender status timestamp".split()
)


class FleetPresenceMessage(Protocol):
    """Minimal explicit-ack JetStream message consumed by the projector."""

    subject: str
    data: bytes
    headers: Mapping[str, str] | None

    async def ack(self) -> Any: ...
    async def nak(self) -> Any: ...


class FleetPresenceError(RuntimeError):
    """Base failure for rejected or unpersisted fleet presence."""


class InvalidFleetPresenceEnvelope(FleetPresenceError):
    """Untrusted heartbeat data violated the boundary contract."""


class FleetPresenceConfigurationError(FleetPresenceError):
    """An enabled consumer cannot start safely."""


@dataclass(frozen=True, slots=True)
class FleetPresenceConsumerConfig:
    """Validated NATS settings; password is excluded from representations."""

    url: str = DEFAULT_PRESENCE_URL
    user: str = ""
    password: str = field(default="", repr=False)
    stream: str = DEFAULT_PRESENCE_STREAM
    subject: str = DEFAULT_PRESENCE_SUBJECT
    durable: str = DEFAULT_PRESENCE_DURABLE
    compatibility_mode: bool = False
    max_future_skew_s: float = 60.0

    # fmt: off
    def __post_init__(self) -> None:
        if not all(v.strip() for v in (self.url, self.stream, self.subject, self.durable)):
            raise FleetPresenceConfigurationError("presence NATS config is incomplete")
        if bool(self.user) != bool(self.password):
            raise FleetPresenceConfigurationError("presence NATS user and password must be configured together")
        if not _DEDICATED_FILTER.fullmatch(self.subject) and not (self.compatibility_mode and self.subject == FLEET_HEARTBEAT_SUBJECT):
            raise FleetPresenceConfigurationError("unsafe shared presence subject requires compatibility mode")
        if not math.isfinite(self.max_future_skew_s) or self.max_future_skew_s < 0:
            raise FleetPresenceConfigurationError("invalid heartbeat future skew")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> FleetPresenceConsumerConfig:
        """Load fleet-specific values with established NATS env fallbacks."""
        env = os.environ if environ is None else environ

        def pick(*names: str, default: str = "") -> str:
            return next((env[name].strip() for name in names if env.get(name, "").strip()), default)

        try:
            skew = float(pick("DHARMA_FLEET_PRESENCE_MAX_FUTURE_SKEW_SECONDS", default="60"))
        except ValueError as exc:
            raise FleetPresenceConfigurationError("invalid heartbeat future skew") from exc
        return cls(
            url=pick("DHARMA_FLEET_PRESENCE_URL", "DHARMA_NATS_URL", "NATS_URL", default=DEFAULT_PRESENCE_URL),
            user=pick("DHARMA_FLEET_PRESENCE_USER", "DHARMA_NATS_USER", "NATS_USER"),
            password=pick("DHARMA_FLEET_PRESENCE_PASSWORD", "DHARMA_NATS_PASSWORD", "DHARMA_NATS_PW", "NATS_PASSWORD"),
            stream=pick("DHARMA_FLEET_PRESENCE_STREAM", "NATS_STREAM", default=DEFAULT_PRESENCE_STREAM),
            subject=pick("DHARMA_FLEET_PRESENCE_SUBJECT", "NATS_SUBJECT", default=DEFAULT_PRESENCE_SUBJECT),
            durable=pick("DHARMA_FLEET_PRESENCE_DURABLE", "NATS_CONSUMER", default=DEFAULT_PRESENCE_DURABLE),
            compatibility_mode=pick("DHARMA_FLEET_PRESENCE_COMPATIBILITY").lower() in {"1", "true", "yes", "on"},
            max_future_skew_s=skew,
        )
    # fmt: on


@dataclass(frozen=True, slots=True)
class FleetHeartbeat:
    """Validated, transport-neutral fleet heartbeat."""

    sender: str
    claimed_agent_uid: str
    status: str
    observed_at: str
    message_id: str
    source_message_id: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FleetPresenceResult:
    """Outcome returned only after any required broker ACK succeeds."""

    agent_uid: str
    node_id: str
    message_id: str
    status: str
    receipt_id: str = ""
    duplicate: bool = False


# fmt: off
def parse_fleet_heartbeat(data: bytes, *, transport_subject: str, compatibility_mode: bool = False) -> FleetHeartbeat:
    """Strictly validate untrusted legacy or canonical heartbeat JSON."""
    if not isinstance(transport_subject, str) or not transport_subject.strip():
        raise InvalidFleetPresenceEnvelope("invalid transport subject")
    actual_subject = transport_subject.strip()
    if actual_subject == FLEET_HEARTBEAT_SUBJECT and not compatibility_mode:
        raise InvalidFleetPresenceEnvelope("shared subject requires compatibility mode")
    _transport_agent_uid(actual_subject, compatibility_mode=compatibility_mode)
    envelope = _decode_envelope(data)
    canonical = envelope.get("schema") == NATS_ENVELOPE_SCHEMA
    if canonical:
        body = envelope.get("payload")
        sender_key, target_key, id_key = "from_agent", "to_agent", "message_id"
        schema = NATS_ENVELOPE_SCHEMA
        timestamp = (body.get("last_heartbeat") or body.get("timestamp") if isinstance(body, dict) else None) or envelope.get("created_at")
    elif envelope.get("schema_version") == LEGACY_HEARTBEAT_SCHEMA:
        content = envelope.get("content")
        body = _strict_json(content, "legacy heartbeat content") if isinstance(content, str) else content
        sender_key, target_key, id_key = "from", "to", "packet_id"
        schema, timestamp = LEGACY_HEARTBEAT_SCHEMA, envelope.get("timestamp")
        _required_text(envelope, "route", "a2a")
    else:
        raise InvalidFleetPresenceEnvelope("invalid heartbeat schema")
    if not isinstance(body, dict):
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat payload")
    _required_text(envelope, "kind", "heartbeat")
    sender = _required_text(envelope, sender_key)
    _required_text(envelope, target_key, "fleet")
    if _required_text(envelope, "subject") != actual_subject:
        raise InvalidFleetPresenceEnvelope("envelope/transport subject mismatch")
    source_id = _required_text(envelope, id_key)
    if canonical:
        actor = envelope.get("actor")
        if not isinstance(actor, dict) or _required_text(actor, "from_agent") != sender:
            raise InvalidFleetPresenceEnvelope("canonical actor sender mismatch")
        _required_text(body, "schema", FLEET_HEARTBEAT_PAYLOAD_SCHEMA)
    uid = _required_text(body, "agent_uid")
    status = _heartbeat_status(body.get("status"))
    observed = _normalized_timestamp(timestamp)
    metadata = _heartbeat_metadata(body)
    material = (sender, uid, status, observed, actual_subject, source_id, schema, metadata)
    encoded = json.dumps(material, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return FleetHeartbeat(sender, uid, status, observed, f"presence_{hashlib.sha256(encoded).hexdigest()[:32]}", source_id, metadata)
def _decode_envelope(data: bytes) -> dict[str, Any]:
    if not isinstance(data, bytes):
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat data type")
    if not data or len(data) > 64 * 1024:
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat envelope size")
    try:
        decoded = data.decode()
    except UnicodeDecodeError as exc:
        raise InvalidFleetPresenceEnvelope("invalid heartbeat JSON encoding") from exc
    value = _strict_json(decoded, "fleet heartbeat")
    if not isinstance(value, dict):
        raise InvalidFleetPresenceEnvelope("invalid heartbeat JSON object")
    return value
def _strict_json(value: str, label: str) -> Any:
    def finite(raw: str) -> float:
        parsed = float(raw)
        if not math.isfinite(parsed):
            raise ValueError("JSON float overflow")
        return parsed

    try:
        return json.loads(value, parse_constant=lambda raw: (_ for _ in ()).throw(ValueError(f"non-finite JSON number: {raw}")), parse_float=finite)
    except (ValueError, OverflowError, RecursionError) as exc:
        raise InvalidFleetPresenceEnvelope(f"invalid {label} JSON") from exc
def _required_text(payload: Mapping[str, Any], key: str, expected: str | None = None) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidFleetPresenceEnvelope(f"invalid fleet heartbeat field: {key}")
    text = value.strip()
    if expected is not None and text != expected:
        raise InvalidFleetPresenceEnvelope(f"invalid fleet heartbeat field: {key}")
    return text

def _heartbeat_status(value: Any) -> str:
    status = value.strip().lower() if isinstance(value, str) else ""
    if status not in {"online", "degraded", "offline", "unknown"}:
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat status")
    return status

def _normalized_timestamp(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(value.strip()) if isinstance(value, str) else None
        if parsed is None or parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError) as exc:
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat timestamp") from exc

def _heartbeat_metadata(body: Mapping[str, Any]) -> dict[str, Any]:
    explicit = body.get("metadata", {})
    if not isinstance(explicit, dict):
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat metadata")
    forbidden = _RESERVED_METADATA_KEYS.intersection(explicit)
    if forbidden:
        raise InvalidFleetPresenceEnvelope(f"reserved heartbeat metadata: {', '.join(sorted(forbidden))}")
    metadata = {str(key): value for key, value in body.items() if key not in _RESERVED_METADATA_KEYS and key not in {"schema", "metadata"}}
    metadata.update(explicit)
    return metadata
# fmt: on


# fmt: off
class FleetPresenceProjector:
    """Persist validated heartbeats through CardRegistry, NodeRegistry and runtime state.
    Subject validation is not cryptographic authentication. NATS ACLs must bind
    each publisher to its own ``dharma.agent.<stable-uid>.presence`` subject.
    """

    def __init__(
        self,
        *,
        card_registry: CardRegistry,
        node_registry: NodeRegistry,
        runtime_state: RuntimeStateStore,
        idempotency_stale_after_s: float | None = 300.0,
        compatibility_mode: bool = False,
        clock: Callable[[], datetime] | None = None,
        max_future_skew_s: float = 60.0,
    ) -> None:
        if not math.isfinite(max_future_skew_s) or max_future_skew_s < 0:
            raise FleetPresenceConfigurationError("invalid heartbeat future skew")
        self.card_registry, self.node_registry = card_registry, node_registry
        self.runtime_state = runtime_state
        self.idempotency_stale_after_s = idempotency_stale_after_s
        self.compatibility_mode = compatibility_mode
        self.clock, self.max_future_skew_s = clock or _utc_now, max_future_skew_s

    async def consume_message(self, message: FleetPresenceMessage) -> FleetPresenceResult:
        """Persist idempotently before ACK; NAK rejected or unproven work."""
        try:
            heartbeat = parse_fleet_heartbeat(message.data, transport_subject=message.subject, compatibility_mode=self.compatibility_mode)
            self._validate_time(heartbeat)
            card, agent_uid = self._resolve_identity(heartbeat)
            transport_uid = _transport_agent_uid(message.subject, compatibility_mode=self.compatibility_mode)
            if transport_uid is not None and transport_uid != agent_uid:
                raise FleetPresenceError("fleet subject/UID mismatch")
        except FleetPresenceError as exc:
            if self.compatibility_mode and _is_nonheartbeat(message.data):
                try:
                    await message.ack()
                except Exception as ack_error:
                    raise FleetPresenceError(f"skipped message ack failed: {ack_error}") from ack_error
                return FleetPresenceResult("", "", "", "skipped")
            await _nak(message, exc)
            raise
        node_id, state, nodes = card.name, self.runtime_state, self.node_registry
        identity = _execution_identity(heartbeat, agent_uid)
        idem_key = identity.idempotency_key
        effect_key = f"fleet_presence:{agent_uid}:{heartbeat.message_id}"
        operation = {"agent_uid": agent_uid, "node_id": node_id, "message_id": heartbeat.message_id, "observed_at": heartbeat.observed_at}
        metadata = heartbeat.metadata | {"agent_uid": agent_uid, "presence_message_id": heartbeat.message_id}
        token: datetime | None = None
        duplicate, node_written = False, False
        previous, node = nodes.get(node_id), None
        cas: Literal["committed", "not_committed", "unknown"] = "not_committed"
        try:
            await state.record_execution_identity(identity, source="a2a.fleet_presence", metadata=operation)
            token = await state.try_begin_idempotent_side_effect_with_token(
                identity, effect_key, metadata=operation, stale_after_seconds=self.idempotency_stale_after_s
            )
            if token is None:
                existing = await state.get_idempotency_record(idem_key, effect_key)
                if existing is not None and existing.status in {"completed", "skipped"} and existing.result_receipt_id:
                    receipts = await state.list_runtime_receipts(run_id=existing.run_id, receipt_type="fleet_presence_attempt")
                    if not any(r.receipt_id == existing.result_receipt_id and r.status == "prepared" for r in receipts):
                        raise FleetPresenceError("prepared receipt missing")
                    node = _record_node(nodes, node_id, heartbeat, agent_uid, metadata)
                    duplicate = True
                    await message.ack()
                    return FleetPresenceResult(agent_uid, node_id, heartbeat.message_id, "duplicate", existing.result_receipt_id, True)
                if existing is not None and existing.status in {"failed", "stale"}:
                    token = await state.try_reclaim_idempotent_side_effect_with_token(
                        identity, effect_key, expected_status=existing.status, expected_updated_at=existing.updated_at
                    )
                if token is None:
                    status = existing.status if existing is not None else "missing"
                    raise FleetPresenceError(f"projection in progress: {status}")
            node = _record_node(nodes, node_id, heartbeat, agent_uid, metadata)
            node_written = True
            attempt = await state.record_receipt_for_identity(
                identity, receipt_type="fleet_presence_attempt", status="prepared",
                side_effect_key=effect_key, payload={**operation, "node_status": node.status},
            )
            try:
                await state.complete_idempotent_side_effect(
                    identity, effect_key, result_receipt_id=attempt.receipt_id,
                    metadata={**operation, "receipt_id": attempt.receipt_id}, expected_updated_at=token,
                )
                cas = "committed"
            except Exception as cas_error:
                try:
                    current = await state.get_idempotency_record(idem_key, effect_key)
                except Exception as inspect_error:
                    cas = "unknown"
                    _record_secondary_failure(cas_error, "CAS inspect", inspect_error)
                    raise cas_error
                if current is None or current.status != "completed" or current.result_receipt_id != attempt.receipt_id:
                    raise
                cas = "committed"
                logger.warning("CAS committed; completion reporting failed", exc_info=True)
        except Exception as exc:
            if duplicate:
                raise FleetPresenceError("duplicate persisted; ack failed") from exc
            primary = exc if isinstance(exc, FleetPresenceError) else FleetPresenceError(str(exc))
            if node_written and cas == "not_committed" and node is not None:
                try:
                    nodes.rollback_heartbeat(node.node_id, expected_presence_message_id=heartbeat.message_id, previous=previous)
                except Exception as rollback_error:
                    _record_secondary_failure(primary, "node heartbeat rollback", rollback_error)
            if token is not None and cas == "not_committed":
                await self._record_failure(identity, effect_key, primary, token)
            if cas == "unknown":
                primary.add_note("CAS outcome unknown; prepared node retained")
            await _nak(message, primary)
            if primary is exc:
                raise
            raise primary from exc
        try:
            await message.ack()
        except Exception as exc:
            raise FleetPresenceError(f"persisted but broker ack failed: {exc}") from exc
        return FleetPresenceResult(agent_uid, node_id, heartbeat.message_id, "projected", attempt.receipt_id)

    def _resolve_identity(self, heartbeat: FleetHeartbeat) -> tuple[AgentCard, str]:
        sender = self.card_registry.get(heartbeat.sender)
        claimed = self.card_registry.get(heartbeat.claimed_agent_uid)
        if sender is None or claimed is None:
            raise FleetPresenceError("unknown fleet identity")
        sender_uid = resolve_agent_uid(sender.name, agent_uid=sender.agent_uid)
        claimed_uid = resolve_agent_uid(claimed.name, agent_uid=claimed.agent_uid)
        if sender_uid != claimed_uid:
            raise FleetPresenceError("fleet sender/UID mismatch")
        return sender, sender_uid

    def _validate_time(self, heartbeat: FleetHeartbeat) -> None:
        now = self.clock()
        if now.tzinfo is None:
            raise FleetPresenceConfigurationError("presence clock must be timezone-aware")
        limit = now.astimezone(timezone.utc) + timedelta(seconds=self.max_future_skew_s)
        if datetime.fromisoformat(heartbeat.observed_at) > limit:
            raise InvalidFleetPresenceEnvelope("fleet heartbeat timestamp is in the future")

    async def _record_failure(self, identity: ExecutionIdentity, effect_key: str, error: Exception, token: datetime) -> None:
        receipt_id = ""
        try:
            receipt = await self.runtime_state.record_receipt_for_identity(
                identity, receipt_type="fleet_presence", status="projection_failed",
                side_effect_key=effect_key, payload={"error": str(error)},
            )
            receipt_id = receipt.receipt_id
        except Exception as receipt_error:
            _record_secondary_failure(error, "failure receipt", receipt_error)
        try:
            await self.runtime_state.complete_idempotent_side_effect(
                identity, effect_key, status="failed", result_receipt_id=receipt_id,
                metadata={"error": str(error)}, expected_updated_at=token,
            )
        except Exception as completion_error:
            _record_secondary_failure(error, "failed-state CAS", completion_error)


def _record_node(nodes: NodeRegistry, node_id: str, heartbeat: FleetHeartbeat, agent_uid: str, metadata: Mapping[str, Any]) -> RemoteNode:
    return nodes.record_heartbeat(
        node_id, last_heartbeat=heartbeat.observed_at, status=heartbeat.status,
        metadata=metadata, canonical_agent_uid=agent_uid,
    )


def _execution_identity(heartbeat: FleetHeartbeat, agent_uid: str) -> ExecutionIdentity:
    digest = heartbeat.message_id.removeprefix("presence_")
    return ExecutionIdentity.new(
        task_id=f"fleet_presence_{digest}", agent_id=agent_uid, trace_id=f"trace_presence_{digest}",
        correlation_id=f"corr_presence_{digest}", run_id=f"run_presence_{digest}",
        claim_id=f"claim_presence_{digest}", idempotency_key=f"idem_presence_{digest}",
        message_id=heartbeat.message_id, event_id=heartbeat.source_message_id,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _transport_agent_uid(subject: str, *, compatibility_mode: bool) -> str | None:
    match = _DEDICATED_MESSAGE.fullmatch(subject)
    if match:
        return match.group(1)
    if compatibility_mode and subject == FLEET_HEARTBEAT_SUBJECT:
        return None
    raise InvalidFleetPresenceEnvelope("invalid dedicated fleet presence subject")

def _is_nonheartbeat(data: bytes) -> bool:
    try:
        kind = _decode_envelope(data).get("kind")
    except InvalidFleetPresenceEnvelope:
        return False
    return isinstance(kind, str) and bool(kind.strip()) and kind != "heartbeat"


def _record_secondary_failure(primary: BaseException, action: str, secondary: BaseException) -> None:
    primary.add_note(f"{action} failed: {type(secondary).__name__}: {secondary}")
    logger.warning("%s failed", action, exc_info=(type(secondary), secondary, secondary.__traceback__))


async def _nak(message: FleetPresenceMessage, primary: BaseException) -> None:
    try:
        await message.nak()
    except Exception as exc:
        _record_secondary_failure(primary, "broker NAK", exc)


async def run_fleet_presence_consumer(
    projector: FleetPresenceProjector, *, config: FleetPresenceConsumerConfig | None = None,
    connect: Callable[..., Awaitable[Any]] | None = None, ready: asyncio.Future[None] | None = None,
) -> None:
    """Run an explicit-ack JetStream consumer until clean cancellation.

    The optional nats-py dependency is imported only when no connector is
    injected. Broker ACLs, not this subject comparison, authenticate publishers.
    """
    connection: Any | None = None
    subscription: Any | None = None
    try:
        settings = config or FleetPresenceConsumerConfig.from_env()
        connector = connect
        if connector is None:
            try:
                import nats
            except ImportError as exc:
                raise FleetPresenceConfigurationError("nats-py is required when fleet presence is enabled") from exc
            connector = nats.connect
        options: dict[str, Any] = {"servers": [settings.url], "name": "dharma-fleet-presence"}
        if settings.user:
            options.update(user=settings.user, password=settings.password)
        connection = await connector(**options)
        subscription = await connection.jetstream().subscribe(
            settings.subject, stream=settings.stream, durable=settings.durable,
            manual_ack=True, cb=projector.consume_message,
        )
        if ready is not None and not ready.done():
            ready.set_result(None)
        await asyncio.Future()
    except BaseException as exc:
        if ready is not None and not ready.done():
            ready.cancel() if isinstance(
                exc, asyncio.CancelledError
            ) else ready.set_exception(exc)
        raise
    finally:
        calls = []
        labels = []
        if subscription is not None:
            calls.append(subscription.unsubscribe())
            labels.append("unsubscribe")
        if connection is not None:
            calls.append(connection.drain())
            labels.append("NATS drain")
        for label, result in zip(labels, await asyncio.gather(*calls, return_exceptions=True), strict=True):
            if isinstance(result, BaseException):
                logger.error("fleet presence %s failed: %s", label, result)
# fmt: on
