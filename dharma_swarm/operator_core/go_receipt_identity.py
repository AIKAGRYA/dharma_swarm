"""Python port of the Go SDK receipt identity chain, for verify-on-ingest.

The Go evidence sense-organ derives three identity fields deterministically
(see tools/go_sdk/receipt/receipt.go)::

    content_hash = "sha256:" + hex(sha256(raw_payload_bytes))
    event_uid    = "evt_"    + short_digest(source, source_url, content_hash)
    receipt_id   = "goev_"   + short_digest(correlation_id, event_uid)

short_digest NUL-joins its string parts, sha256s the bytes, and hex-encodes the
first twelve bytes (24 hex chars).

Honest ceiling: content_hash is taken over the raw payload bytes the sidecar
ingested. The normalized receipt on disk no longer carries those raw bytes
(Normalize may reshape non-JSON payloads and JSON whitespace differs), so
content_hash cannot be re-derived from the stored payload Python-side. The
identity chain above is a pure function of stored string fields, so it CAN be
recomputed and MUST self-verify before a receipt is trusted. This module ports
exactly that verifiable part; content_hash is treated as an opaque input string.
"""
from __future__ import annotations

import hashlib

EVENT_UID_PREFIX = "evt_"
RECEIPT_ID_PREFIX = "goev_"


class GoReceiptIdentityError(ValueError):
    """Raised when a Go receipt's identity chain does not self-verify."""


def short_digest(*parts: str) -> str:
    """NUL-join parts, sha256, hex-encode the first 12 bytes (hex12).

    Byte-for-byte port of shortDigest in tools/go_sdk/receipt/receipt.go.
    """
    buf = b"\x00".join(part.encode("utf-8") for part in parts)
    return hashlib.sha256(buf).hexdigest()[:24]


def content_hash(payload_bytes: bytes) -> str:
    """Canonical content-hash form over RAW payload bytes.

    Provided for conformance testing against the Go SDK. Not usable to verify a
    normalized on-disk receipt, whose raw payload bytes are not retained.
    """
    return "sha256:" + hashlib.sha256(payload_bytes).hexdigest()


def derive_event_uid(source: str, source_url: str, content_hash_value: str) -> str:
    return EVENT_UID_PREFIX + short_digest(source, source_url, content_hash_value)


def derive_receipt_id(correlation_id: str, event_uid: str) -> str:
    return RECEIPT_ID_PREFIX + short_digest(correlation_id, event_uid)


def verify_identity_chain(
    *,
    source: str,
    source_url: str,
    content_hash_value: str,
    correlation_id: str,
    event_uid: str,
    receipt_id: str,
) -> None:
    """Reject any receipt whose identity chain does not self-verify.

    Raises GoReceiptIdentityError when the stored event_uid or receipt_id does
    not equal the value recomputed from the stored string fields.
    """
    expected_event_uid = derive_event_uid(source, source_url, content_hash_value)
    if event_uid != expected_event_uid:
        raise GoReceiptIdentityError(
            "event_uid does not verify against (source, source_url, content_hash): "
            f"stored={event_uid!r} recomputed={expected_event_uid!r}"
        )
    expected_receipt_id = derive_receipt_id(correlation_id, event_uid)
    if receipt_id != expected_receipt_id:
        raise GoReceiptIdentityError(
            "receipt_id does not verify against (correlation_id, event_uid): "
            f"stored={receipt_id!r} recomputed={expected_receipt_id!r}"
        )
