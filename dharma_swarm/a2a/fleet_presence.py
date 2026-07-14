"""Project NATS heartbeats through CardRegistry, NodeRegistry, and RuntimeState."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry, resolve_agent_uid
from dharma_swarm.a2a.nats_transport_support import NATS_ENVELOPE_SCHEMA
from dharma_swarm.a2a.node_registry import NodeRegistry
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity

logger = logging.getLogger(__name__)

LEGACY_HEARTBEAT_SCHEMA = "dharma.a2a.send.v1"
FLEET_HEARTBEAT_PAYLOAD_SCHEMA = "dharma.a2a.fleet_heartbeat.v1"
FLEET_HEARTBEAT_SUBJECT = "dharma.a2a.fleet"
_RESERVED_METADATA_KEYS = frozenset(
    "agent_uid from from_agent last_heartbeat message_id sender status timestamp".split()
)


class FleetPresenceMessage(Protocol):
    """Minimal explicit-ack JetStream message accepted by the consumer."""

    data: bytes

    async def ack(self) -> Any: ...
    async def nak(self) -> Any: ...


class FleetPresenceError(RuntimeError):
    """Base failure for rejected or unpersisted fleet presence."""


class InvalidFleetPresenceEnvelope(FleetPresenceError):
    """Raised when untrusted heartbeat data violates the boundary contract."""


class UnknownFleetIdentity(FleetPresenceError):
    """Raised when CardRegistry cannot authorize a heartbeat identity."""


class FleetIdentityMismatch(FleetPresenceError):
    """Raised when sender and claimed UID resolve to different cards."""


class FleetPresenceProjectionError(FleetPresenceError):
    """Raised when broker or durable projection work does not complete."""


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
    """Outcome returned after broker acknowledgement succeeds."""

    agent_uid: str
    node_id: str
    message_id: str
    status: str
    receipt_id: str = ""
    duplicate: bool = False


def parse_fleet_heartbeat(data: bytes) -> FleetHeartbeat:
    """Validate untrusted JSON and return a content-identified heartbeat."""
    if not isinstance(data, bytes):
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat data type")
    if not data or len(data) > 64 * 1024:
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat envelope size")
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidFleetPresenceEnvelope("invalid heartbeat JSON encoding") from exc
    envelope = _strict_json(decoded, "fleet heartbeat")
    if not isinstance(envelope, dict):
        raise InvalidFleetPresenceEnvelope("invalid heartbeat JSON object")
    canonical = envelope.get("schema") == NATS_ENVELOPE_SCHEMA
    if canonical:
        body = envelope.get("payload")
        sender_key, target_key, source_key = "from_agent", "to_agent", "message_id"
        envelope_schema = NATS_ENVELOPE_SCHEMA
        timestamp = (
            body.get("last_heartbeat") or body.get("timestamp")
            if isinstance(body, dict)
            else None
        ) or envelope.get("created_at")
    elif envelope.get("schema_version") == LEGACY_HEARTBEAT_SCHEMA:
        content = envelope.get("content")
        body = (
            _strict_json(content, "legacy heartbeat content")
            if isinstance(content, str)
            else content
        )
        sender_key, target_key, source_key = "from", "to", "packet_id"
        envelope_schema = LEGACY_HEARTBEAT_SCHEMA
        timestamp = envelope.get("timestamp")
        _required_text(envelope, "route", "a2a")
    else:
        raise InvalidFleetPresenceEnvelope("invalid heartbeat schema")
    if not isinstance(body, dict):
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat payload")

    _required_text(envelope, "kind", "heartbeat")
    sender = _required_text(envelope, sender_key)
    _required_text(envelope, target_key, "fleet")
    subject = _required_text(envelope, "subject", FLEET_HEARTBEAT_SUBJECT)
    source_message_id = _required_text(envelope, source_key)
    if canonical:
        actor = envelope.get("actor")
        if not isinstance(actor, dict) or _required_text(actor, "from_agent") != sender:
            raise InvalidFleetPresenceEnvelope("canonical actor sender mismatch")
        _required_text(body, "schema", FLEET_HEARTBEAT_PAYLOAD_SCHEMA)

    claimed_agent_uid = _required_text(body, "agent_uid")
    status = _heartbeat_status(body.get("status"))
    observed_at = _normalized_timestamp(timestamp)
    metadata = _heartbeat_metadata(body)
    identity_material = (
        sender,
        claimed_agent_uid,
        status,
        observed_at,
        subject,
        source_message_id,
        envelope_schema,
        metadata,
    )
    encoded = json.dumps(
        identity_material, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return FleetHeartbeat(
        sender=sender,
        claimed_agent_uid=claimed_agent_uid,
        status=status,
        observed_at=observed_at,
        message_id=f"presence_{hashlib.sha256(encoded).hexdigest()[:32]}",
        source_message_id=source_message_id,
        metadata=metadata,
    )


def _required_text(
    payload: Mapping[str, Any],
    key: str,
    expected: str | None = None,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidFleetPresenceEnvelope(f"invalid fleet heartbeat field: {key}")
    text = value.strip()
    if expected is not None and text != expected:
        raise InvalidFleetPresenceEnvelope(f"invalid fleet heartbeat field: {key}")
    return text


def _strict_json(value: str, label: str) -> Any:
    def finite_float(raw: str) -> float:
        parsed = float(raw)
        if not math.isfinite(parsed):
            raise ValueError("JSON float overflow")
        return parsed

    def reject_constant(raw: str) -> None:
        raise ValueError(f"non-finite JSON number: {raw}")

    try:
        return json.loads(
            value,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (ValueError, OverflowError, RecursionError) as exc:
        raise InvalidFleetPresenceEnvelope(f"invalid {label} JSON") from exc


def _heartbeat_status(value: Any) -> str:
    if not isinstance(value, str):
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat status")
    status = value.strip().lower()
    if status not in {"online", "degraded", "offline", "unknown"}:
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat status")
    return status


def _normalized_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidFleetPresenceEnvelope("invalid fleet heartbeat timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip())
        if parsed.tzinfo is None:
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
        fields = ", ".join(sorted(forbidden))
        raise InvalidFleetPresenceEnvelope(f"reserved heartbeat metadata: {fields}")
    metadata = {
        str(key): value
        for key, value in body.items()
        if key not in _RESERVED_METADATA_KEYS and key not in {"schema", "metadata"}
    }
    metadata.update(explicit)
    return metadata


class FleetPresenceProjector:
    """Project validated broker heartbeats through existing authority owners."""

    def __init__(
        self,
        *,
        card_registry: CardRegistry,
        node_registry: NodeRegistry,
        runtime_state: RuntimeStateStore,
        idempotency_stale_after_s: float | None = 300.0,
    ) -> None:
        self.card_registry = card_registry
        self.node_registry = node_registry
        self.runtime_state = runtime_state
        self.idempotency_stale_after_s = idempotency_stale_after_s

    async def consume_message(
        self, message: FleetPresenceMessage
    ) -> FleetPresenceResult:
        """Persist idempotently before ACK; reject or NAK unproven work."""
        try:
            heartbeat = parse_fleet_heartbeat(message.data)
            card, agent_uid = self._resolve_identity(heartbeat)
        except FleetPresenceError as exc:
            await _nak(message, exc)
            raise

        node_id = card.name
        state = self.runtime_state
        nodes = self.node_registry
        identity = _execution_identity(heartbeat, agent_uid)
        idem_key = identity.idempotency_key
        effect_key = f"fleet_presence:{agent_uid}:{heartbeat.message_id}"
        op = {
            "agent_uid": agent_uid,
            "node_id": node_id,
            "message_id": heartbeat.message_id,
            "observed_at": heartbeat.observed_at,
        }
        token: datetime | None = None
        duplicate = False
        previous = nodes.get(node_id)
        node_written = False
        cas_result: Literal["committed", "not_committed", "unknown"] = "not_committed"
        node_metadata = heartbeat.metadata | {
            "agent_uid": agent_uid,
            "presence_message_id": heartbeat.message_id,
        }
        try:
            await state.record_execution_identity(
                identity,
                source="a2a.fleet_presence",
                metadata=op,
            )
            token = await state.try_begin_idempotent_side_effect_with_token(
                identity,
                effect_key,
                metadata=op,
                stale_after_seconds=self.idempotency_stale_after_s,
            )
            if token is None:
                existing = await state.get_idempotency_record(idem_key, effect_key)
                if (
                    existing is not None
                    and existing.status in {"completed", "skipped"}
                    and existing.result_receipt_id
                ):
                    attempts = await state.list_runtime_receipts(
                        run_id=existing.run_id,
                        receipt_type="fleet_presence_attempt",
                    )
                    if not any(
                        receipt.receipt_id == existing.result_receipt_id
                        and receipt.status == "prepared"
                        for receipt in attempts
                    ):
                        raise FleetPresenceProjectionError("prepared receipt missing")
                    node = nodes.record_heartbeat(
                        node_id,
                        last_heartbeat=heartbeat.observed_at,
                        status=heartbeat.status,
                        metadata=node_metadata,
                        canonical_agent_uid=agent_uid,
                    )
                    duplicate = True
                    await message.ack()
                    return FleetPresenceResult(
                        agent_uid,
                        node_id,
                        heartbeat.message_id,
                        "duplicate",
                        existing.result_receipt_id,
                        True,
                    )
                if existing is not None and existing.status in {"failed", "stale"}:
                    token = await state.try_reclaim_idempotent_side_effect_with_token(
                        identity,
                        effect_key,
                        expected_status=existing.status,
                        expected_updated_at=existing.updated_at,
                    )
                if token is None:
                    status = existing.status if existing is not None else "missing"
                    raise FleetPresenceProjectionError(
                        f"projection in progress: {status}"
                    )

            node = nodes.record_heartbeat(
                node_id,
                last_heartbeat=heartbeat.observed_at,
                status=heartbeat.status,
                metadata=node_metadata,
                canonical_agent_uid=agent_uid,
            )
            node_written = True
            attempt = await state.record_receipt_for_identity(
                identity,
                receipt_type="fleet_presence_attempt",
                status="prepared",
                side_effect_key=effect_key,
                payload={**op, "node_status": node.status},
            )
            try:
                await state.complete_idempotent_side_effect(
                    identity,
                    effect_key,
                    result_receipt_id=attempt.receipt_id,
                    metadata={**op, "receipt_id": attempt.receipt_id},
                    expected_updated_at=token,
                )
                cas_result = "committed"
            except Exception as cas_error:
                try:
                    current = await state.get_idempotency_record(idem_key, effect_key)
                except Exception as inspection_error:
                    cas_result = "unknown"
                    _note_secondary(cas_error, "CAS inspect", inspection_error)
                    raise cas_error
                if (
                    current is None
                    or current.status != "completed"
                    or current.result_receipt_id != attempt.receipt_id
                ):
                    raise
                cas_result = "committed"
                logger.warning("CAS committed; reporting failed", exc_info=True)
        except Exception as exc:
            if duplicate:
                raise FleetPresenceProjectionError(
                    "duplicate persisted; ack failed"
                ) from exc
            primary = (
                exc
                if isinstance(exc, FleetPresenceError)
                else FleetPresenceProjectionError(str(exc))
            )
            if node_written and cas_result == "not_committed":
                try:
                    nodes.rollback_heartbeat(
                        node.node_id,
                        expected_presence_message_id=heartbeat.message_id,
                        previous=previous,
                    )
                except Exception as rollback_error:
                    _note_secondary(primary, "node heartbeat rollback", rollback_error)
            if token is not None and cas_result == "not_committed":
                await self._record_failure(identity, effect_key, primary, token)
            if cas_result == "unknown":
                primary.add_note("CAS outcome unknown; prepared node retained")
            await _nak(message, primary)
            if primary is exc:
                raise
            raise primary from exc

        try:
            await message.ack()
        except Exception as exc:
            raise FleetPresenceProjectionError(
                f"persisted but broker ack failed: {exc}"
            ) from exc
        return FleetPresenceResult(
            agent_uid,
            node.node_id,
            heartbeat.message_id,
            "projected",
            attempt.receipt_id,
        )

    def _resolve_identity(self, heartbeat: FleetHeartbeat) -> tuple[AgentCard, str]:
        sender = self.card_registry.get(heartbeat.sender)
        claimed = self.card_registry.get(heartbeat.claimed_agent_uid)
        if sender is None or claimed is None:
            raise UnknownFleetIdentity("unknown fleet identity")
        sender_uid = resolve_agent_uid(sender.name, agent_uid=sender.agent_uid)
        claimed_uid = resolve_agent_uid(claimed.name, agent_uid=claimed.agent_uid)
        if sender_uid != claimed_uid:
            raise FleetIdentityMismatch("fleet sender/UID mismatch")
        return sender, sender_uid

    async def _record_failure(
        self,
        identity: ExecutionIdentity,
        effect_key: str,
        error: Exception,
        token: datetime,
    ) -> None:
        state = self.runtime_state
        receipt_id = ""
        try:
            receipt = await state.record_receipt_for_identity(
                identity,
                receipt_type="fleet_presence",
                status="projection_failed",
                side_effect_key=effect_key,
                payload={"error": str(error)},
            )
            receipt_id = receipt.receipt_id
        except Exception as receipt_error:
            _note_secondary(error, "failure receipt", receipt_error)
        try:
            await state.complete_idempotent_side_effect(
                identity,
                effect_key,
                status="failed",
                result_receipt_id=receipt_id,
                metadata={"error": str(error)},
                expected_updated_at=token,
            )
        except Exception as completion_error:
            _note_secondary(error, "failed-state CAS", completion_error)


def _execution_identity(heartbeat: FleetHeartbeat, agent_uid: str) -> ExecutionIdentity:
    digest = heartbeat.message_id.removeprefix("presence_")
    return ExecutionIdentity.new(
        task_id=f"fleet_presence_{digest}",
        agent_id=agent_uid,
        trace_id=f"trace_presence_{digest}",
        correlation_id=f"corr_presence_{digest}",
        run_id=f"run_presence_{digest}",
        claim_id=f"claim_presence_{digest}",
        idempotency_key=f"idem_presence_{digest}",
        message_id=heartbeat.message_id,
        event_id=heartbeat.source_message_id,
    )


def _note_secondary(
    primary: BaseException,
    action: str,
    secondary: BaseException,
) -> None:
    primary.add_note(f"{action} failed: {type(secondary).__name__}: {secondary}")
    logger.warning(
        "%s failed",
        action,
        exc_info=(type(secondary), secondary, secondary.__traceback__),
    )


async def _nak(message: FleetPresenceMessage, primary: BaseException) -> None:
    try:
        await message.nak()
    except Exception as exc:
        _note_secondary(primary, "broker NAK", exc)
