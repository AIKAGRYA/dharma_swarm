"""Pure validation helpers for the dedicated Foundry/RSI NATS lane."""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.a2a.candidate_lease import lease_instant
from dharma_swarm.a2a.nats_transport_support import (
    _nats_endpoint_is_loopback,
    _nats_endpoint_uses_tls,
)
from dharma_swarm.forge_lab.candidate_envelope import (
    MAX_CANDIDATE_LIFETIME_SECONDS,
    SignedCandidateEnvelope,
)

_PUBLIC_NKEY = re.compile(r"^U[A-Z2-7]{55}$")
_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NKEY_PREFIX_SEED = 18 << 3
_NKEY_PREFIX_USER = 20 << 3


class CandidateContractError(ValueError):
    """A static transport or on-wire contract is unsafe or ambiguous."""


def validate_public_user_nkey(value: str) -> str:
    text = str(value or "")
    if not _PUBLIC_NKEY.fullmatch(text):
        raise CandidateContractError("public user NKey encoding is invalid")
    try:
        raw = base64.b32decode(text + "=" * (-len(text) % 8), casefold=False)
    except (ValueError, binascii.Error) as exc:
        raise CandidateContractError("public user NKey encoding is invalid") from exc
    if len(raw) != 35 or raw[0] != _NKEY_PREFIX_USER or _crc16(raw[:-2]) != raw[-2:]:
        raise CandidateContractError("public user NKey encoding or checksum is invalid")
    return text


def _positive_finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateContractError(f"{field} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise CandidateContractError(f"{field} must be a finite positive number")
    return number


def _subject(value: Any, field: str) -> str:
    text = str(value or "")
    tokens = text.split(".")
    if (
        not text.endswith(".v1")
        or any(not token or token in {"*", ">"} for token in tokens)
        or any(character.isspace() or character in "*>" for character in text)
    ):
        raise CandidateContractError(f"{field} must be a concrete versioned NATS subject")
    return text


def _name(value: Any, field: str) -> str:
    text = str(value or "")
    if not _NAME.fullmatch(text):
        raise CandidateContractError(f"{field} must be a concrete NATS name")
    return text


def validate_candidate_config(config: Any) -> None:
    """Fail closed on unsafe topology, retry, endpoint, or auth configuration."""

    if config.require_auth is not True:
        raise CandidateContractError("candidate transport authentication cannot be disabled")
    if not isinstance(config.require_tls, bool):
        raise CandidateContractError("require_tls must be boolean")
    subject = _subject(config.subject, "subject")
    dlq_subject = _subject(config.dlq_subject, "dlq_subject")
    if subject == dlq_subject:
        raise CandidateContractError("candidate and DLQ subjects must be distinct")
    names = (
        _name(config.stream_name, "stream_name"),
        _name(config.dlq_stream_name, "dlq_stream_name"),
        _name(config.consumer_name, "consumer_name"),
    )
    if len(set(names)) != len(names):
        raise CandidateContractError("candidate streams and consumer names must be distinct")
    if not isinstance(config.max_deliveries, int) or isinstance(config.max_deliveries, bool):
        raise CandidateContractError("max_deliveries must be an integer")
    if config.max_deliveries < 2 or len(config.backoff_s) != config.max_deliveries - 1:
        raise CandidateContractError("consumer backoff must exactly cover redelivery attempts")
    if not isinstance(config.publish_attempts, int) or isinstance(config.publish_attempts, bool):
        raise CandidateContractError("publish_attempts must be an integer")
    if config.publish_attempts < 1 or len(config.publish_backoff_s) != config.publish_attempts - 1:
        raise CandidateContractError("publish backoff must exactly cover retry attempts")
    for field in (
        "ack_wait_s", "max_age_s", "dlq_max_age_s", "duplicate_window_s",
        "publish_timeout_s", "max_clock_skew_s", "max_candidate_lifetime_s",
    ):
        _positive_finite(getattr(config, field), field)
    for index, value in enumerate(config.backoff_s):
        _positive_finite(value, f"backoff_s[{index}]")
    for index, value in enumerate(config.publish_backoff_s):
        _positive_finite(value, f"publish_backoff_s[{index}]")
    if config.max_candidate_lifetime_s > MAX_CANDIDATE_LIFETIME_SECONDS:
        raise CandidateContractError("candidate lifetime cannot exceed the envelope protocol bound")
    for field in ("max_bytes", "max_message_bytes"):
        value = getattr(config, field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1024:
            raise CandidateContractError(f"{field} must be an integer of at least 1024")
    if not config.endpoint or (not config.require_tls and not _nats_endpoint_is_loopback(config.endpoint)):
        raise CandidateContractError("non-loopback NATS endpoints require TLS")
    if config.require_tls and not _nats_endpoint_uses_tls(config.endpoint):
        raise CandidateContractError("TLS-required endpoints must use tls:// or wss://")
    password_auth = bool(config.username_env or config.password_env)
    if bool(config.username_env) != bool(config.password_env):
        raise CandidateContractError("username/password environment names must be complete")
    mutual_tls = bool(config.tls_cert_path or config.tls_key_path)
    if bool(config.tls_cert_path) != bool(config.tls_key_path):
        raise CandidateContractError("mutual TLS requires both certificate and private key")
    methods = sum(bool(value) for value in (config.credentials_path, config.nkey_file, password_auth, mutual_tls))
    if methods > 1:
        raise CandidateContractError("configure exactly one NATS authentication method")
    if config.nkey_file:
        try:
            validate_public_user_nkey(config.nkey_public_key)
        except CandidateContractError as exc:
            raise CandidateContractError("nkey_file requires a full public user NKey") from exc


def secure_private_file(path: str, field: str, *, root_owned: bool = False) -> Path:
    candidate = Path(path)
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise CandidateContractError(f"configured {field} is unavailable") from exc
    allowed_owners = {0} if root_owned else {0, os.geteuid()}
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid not in allowed_owners
        or metadata.st_nlink != 1
        or metadata.st_mode & 0o077
        or not metadata.st_mode & 0o400
    ):
        raise CandidateContractError(f"{field} must be a safe owned mode-0600-or-stricter regular file")
    return candidate


def secure_public_file(path: str, field: str) -> Path:
    candidate = Path(path)
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise CandidateContractError(f"configured {field} is unavailable") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid not in {0, os.geteuid()}
        or metadata.st_mode & 0o022
    ):
        raise CandidateContractError(f"{field} must be an owned non-writable regular file")
    return candidate


def _crc16(data: bytes) -> bytes:
    """Return the NKey CRC16-XMODEM checksum in its little-endian encoding."""

    return binascii.crc_hqx(data, 0).to_bytes(2, "little")


def nkey_public_from_seed_file(path: str, *, root_owned: bool = True) -> str:
    """Derive a public user NKey without exposing or retaining the seed in receipts."""

    private_seed = _user_seed_bytes(path, root_owned=root_owned)
    try:
        public_raw = Ed25519PrivateKey.from_private_bytes(bytes(private_seed)).public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        public_body = bytes((_NKEY_PREFIX_USER,)) + public_raw
        return base64.b32encode(public_body + _crc16(public_body)).rstrip(b"=").decode("ascii")
    except ValueError as exc:
        raise CandidateContractError("NKey seed encoding is invalid") from exc
    finally:
        private_seed[:] = b"\0" * len(private_seed)


def _user_seed_bytes(path: str, *, root_owned: bool) -> bytearray:
    candidate = secure_private_file(path, "NKey seed", root_owned=root_owned)
    descriptor: int | None = None
    try:
        before = candidate.lstat()
        descriptor = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW)
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise CandidateContractError("NKey seed changed during validation")
        encoded_file = bytearray()
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                break
            encoded_file.extend(chunk)
            if len(encoded_file) > 4096:
                raise CandidateContractError("NKey seed file is unexpectedly large")
        lines = [
            line.strip()
            for line in encoded_file.splitlines()
            if line.strip() and not line.lstrip().startswith(b"#")
        ]
        if len(lines) != 1:
            raise CandidateContractError("NKey seed file must contain exactly one seed")
        encoded = lines[0]
        raw = base64.b32decode(encoded + b"=" * (-len(encoded) % 8), casefold=False)
        if len(raw) != 36 or _crc16(raw[:-2]) != raw[-2:]:
            raise CandidateContractError("NKey seed encoding or checksum is invalid")
        seed_prefix = raw[0] & 248
        public_prefix = ((raw[0] & 7) << 5) | ((raw[1] & 248) >> 3)
        if seed_prefix != _NKEY_PREFIX_SEED or public_prefix != _NKEY_PREFIX_USER:
            raise CandidateContractError("NKey seed is not a user identity")
        private_seed = bytearray(raw[2:-2])
        if len(private_seed) != 32:
            raise CandidateContractError("NKey seed payload is invalid")
        return private_seed
    except (OSError, ValueError, binascii.Error) as exc:
        if isinstance(exc, CandidateContractError):
            raise
        raise CandidateContractError("NKey seed encoding is invalid") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if "encoded_file" in locals():
            encoded_file[:] = b"\0" * len(encoded_file)


def nkey_signature_from_seed_file(path: str, nonce: str) -> bytes:
    """Sign one NATS server nonce with a safe root-owned user seed."""

    private_seed = _user_seed_bytes(path, root_owned=True)
    try:
        signature = Ed25519PrivateKey.from_private_bytes(bytes(private_seed)).sign(
            str(nonce).encode("utf-8")
        )
        return base64.b64encode(signature)
    finally:
        private_seed[:] = b"\0" * len(private_seed)


def prove_nkey_seed_identity(path: str, expected_public_nkey: str) -> str:
    """Fail closed unless a safe root-owned seed derives to the configured public NKey."""

    derived = nkey_public_from_seed_file(path, root_owned=True)
    if derived != expected_public_nkey:
        raise CandidateContractError("NKey seed does not match its configured public identity")
    return derived


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CandidateContractError(f"candidate JSON contains duplicate key: {key}")
        value[key] = item
    return value


def _header_text(headers: Mapping[str, Any], name: str) -> str:
    value = headers.get(name)
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise CandidateContractError(f"candidate NATS header has multiple values: {name}")
        value = value[0]
    return value if isinstance(value, str) else ""


def parse_candidate_wire(
    data: bytes,
    *,
    headers: Mapping[str, Any] | None,
    nats_schema: str,
    delivery_schema: str,
    subject: str,
    now: str,
    max_message_bytes: int,
    max_clock_skew_s: float,
    max_candidate_lifetime_s: float,
) -> SignedCandidateEnvelope:
    """Parse one exact v1 outer envelope and bind every duplicated field."""

    if not isinstance(data, bytes) or not data or len(data) > max_message_bytes:
        raise CandidateContractError("candidate message size is invalid")
    try:
        decoded = data.decode("utf-8")
        wire = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CandidateContractError(f"candidate JSON constant is invalid: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CandidateContractError("candidate message is not canonical UTF-8 JSON") from exc
    canonical = json.dumps(wire, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if decoded != canonical:
        raise CandidateContractError("candidate message is not canonical UTF-8 JSON")
    expected_fields = {
        "schema", "kind", "message_id", "subject", "correlation_id", "causation_id",
        "created_at", "requires_ack", "lease_verification_sha256", "payload",
    }
    if not isinstance(wire, dict) or set(wire) != expected_fields:
        raise CandidateContractError("candidate outer envelope fields are invalid")
    body = wire["payload"]
    if not isinstance(body, dict) or set(body) != {"schema", "signed_envelope"}:
        raise CandidateContractError("candidate delivery body fields are invalid")
    if (
        wire["schema"] != nats_schema or wire["kind"] != "candidate"
        or wire["subject"] != subject or wire["requires_ack"] is not True
        or not _SHA256.fullmatch(str(wire["lease_verification_sha256"]))
        or body["schema"] != delivery_schema or not isinstance(body["signed_envelope"], dict)
    ):
        raise CandidateContractError("candidate outer envelope metadata is invalid")
    try:
        signed = SignedCandidateEnvelope.from_dict(body["signed_envelope"])
    except (TypeError, ValueError) as exc:
        raise CandidateContractError("signed candidate body is invalid") from exc
    envelope = signed.envelope
    if (
        wire["message_id"] != envelope.envelope_id
        or wire["correlation_id"] != envelope.correlation_id
        or wire["causation_id"] != envelope.predecessor_envelope_id
    ):
        raise CandidateContractError("candidate outer envelope binding is invalid")
    wire_at, current = lease_instant(wire["created_at"], "wire.created_at"), lease_instant(now, "now")
    created, expires = lease_instant(envelope.created_at, "created_at"), lease_instant(envelope.expires_at, "expires_at")
    if not (created <= wire_at < expires and wire_at <= current):
        raise CandidateContractError("candidate outer envelope time binding is invalid")
    if (expires - created).total_seconds() > max_candidate_lifetime_s:
        raise CandidateContractError("candidate envelope exceeds the configured lifetime bound")
    if (wire_at - current).total_seconds() > max_clock_skew_s:
        raise CandidateContractError("candidate outer envelope exceeds clock-skew bound")
    if headers is None:
        raise CandidateContractError("candidate NATS headers are required")
    expected_headers = {
        "Nats-Msg-Id": envelope.envelope_id,
        "Dharma-Nats-Schema": nats_schema,
        "Dharma-Candidate-Schema": delivery_schema,
        "Dharma-Envelope-Id": envelope.envelope_id,
        "Dharma-Correlation-Id": envelope.correlation_id,
        "Dharma-Idempotency-Key": envelope.idempotency_key,
        "Dharma-Fence": str(envelope.fence),
        "Dharma-Lease-Verification": str(wire["lease_verification_sha256"]),
    }
    if {str(name) for name in headers} != set(expected_headers):
        raise CandidateContractError("candidate NATS header set is invalid")
    if any(_header_text(headers, name) != value for name, value in expected_headers.items()):
        raise CandidateContractError("candidate NATS headers do not bind the signed envelope")
    return signed


__all__ = [
    "CandidateContractError",
    "parse_candidate_wire",
    "nkey_public_from_seed_file",
    "nkey_signature_from_seed_file",
    "prove_nkey_seed_identity",
    "secure_private_file",
    "secure_public_file",
    "validate_candidate_config",
    "validate_public_user_nkey",
]
