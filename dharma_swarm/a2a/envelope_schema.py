"""Canonical ``dharma.a2a.send.v1`` envelope contract.

One definition of the send envelope, imported by both the operator send
surface (``scripts/runtime/a2a_send.py``) and the inbox drain
(``scripts/runtime/a2a_inbox_bridge.py``). Before this module the two sides
defined the contract independently, so an envelope the sender never stamped
with ``ack_subject`` was silently dead-lettered by the drain as
``MALFORMED_ENVELOPE``. Centralizing the builder and the validator here makes
that drift impossible: the builder always emits ``ack_subject`` and the drain
accepts exactly what the builder produces.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SEND_SCHEMA_VERSION = "dharma.a2a.send.v1"

# The delivery-critical fields the inbox drain must find to persist an envelope
# and publish its ack. Kept intentionally minimal: it is the exact set the
# drain enforced inline before this module, so centralizing cannot start
# dead-lettering envelopes that already deliver today.
REQUIRED_SEND_FIELDS: tuple[str, ...] = ("packet_id", "ack_subject")


class EnvelopeValidationError(ValueError):
    """A payload violates the canonical ``dharma.a2a.send.v1`` contract."""


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def validate_send_envelope(payload: Any) -> dict[str, Any]:
    """Return ``payload`` if it is a deliverable send envelope, else raise."""
    if not isinstance(payload, dict):
        raise EnvelopeValidationError("A2A send envelope must be a JSON object")
    packet_id = payload.get("packet_id")
    if not isinstance(packet_id, str) or not packet_id.strip():
        raise EnvelopeValidationError("A2A send envelope is missing packet_id")
    ack_subject = payload.get("ack_subject")
    if not isinstance(ack_subject, str) or not ack_subject:
        raise EnvelopeValidationError("A2A send envelope is missing ack_subject")
    return payload


def build_send_envelope(
    *,
    packet_id: str,
    sender: str,
    to: str,
    subject: str,
    ack_subject: str | None = None,
    reply_subject: str | None = None,
    kind: str = "",
    route: str = "",
    target_uid: str = "",
    timestamp: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a validated canonical send envelope.

    ``ack_subject``/``reply_subject`` default to the spec derivation
    ``<subject>.ack.<packet_id>`` / ``<subject>.reply.<packet_id>`` so a built
    envelope always carries an ``ack_subject``. Caller-specific fields (content,
    sha256, file path, ...) ride in ``extra``. The result is validated before
    return, so a builder can never emit an undeliverable envelope.
    """
    envelope: dict[str, Any] = {
        "schema_version": SEND_SCHEMA_VERSION,
        "packet_id": packet_id,
        "timestamp": timestamp or _utc_now_iso(),
        "from": sender,
        "to": to,
        "kind": kind,
        "route": route,
        "target_uid": target_uid,
        "subject": subject,
        "ack_subject": ack_subject or f"{subject}.ack.{packet_id}",
        "reply_subject": reply_subject or f"{subject}.reply.{packet_id}",
    }
    if extra:
        envelope.update(extra)
    validate_send_envelope(envelope)
    return envelope
