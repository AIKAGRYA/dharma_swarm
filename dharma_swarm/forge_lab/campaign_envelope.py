"""Strict Ed25519 operator-envelope verification without provider imports."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX_RE = re.compile(r"^[0-9a-f]+$")
_ENVELOPE_KEYS = {
    "schema",
    "campaign_name",
    "manifest_digest",
    "total_tokens",
    "total_usd_micros",
    "total_requests",
    "deadline_utc",
    "host_caps",
    "issued_at",
    "nonce",
    "signer",
    "signature",
}
_SIGNER_KEYS = {"algorithm", "key_id", "public_key"}


def _bad(code: str, message: str) -> None:
    from dharma_swarm.forge_lab.campaign_contract import CampaignContractError

    raise CampaignContractError(code, message)


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _bad("INVALID_ENVELOPE_TIMESTAMP", f"{field} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _bad("INVALID_ENVELOPE_TIMESTAMP", f"{field} is invalid")
    return parsed.astimezone(timezone.utc)


def _observed(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        return _time(value, "now")
    if not isinstance(value, datetime) or value.tzinfo is None:
        _bad("INVALID_ENVELOPE_TIMESTAMP", "now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decode_hex(value: Any, *, size: int, field: str) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) != size * 2
        or not _HEX_RE.fullmatch(value)
    ):
        _bad("INVALID_OPERATOR_ENVELOPE", f"{field} must be {size} raw bytes")
    return bytes.fromhex(value)


def _trusted_key(
    trusted: Mapping[str, str | bytes] | Iterable[str | bytes],
    key_id: str,
    declared: bytes,
) -> bytes:
    if isinstance(trusted, Mapping):
        candidate = trusted.get(key_id)
        if candidate is None:
            _bad("UNTRUSTED_OPERATOR_KEY", f"operator key {key_id!r} is not trusted")
        values = [candidate]
    else:
        values = list(trusted)
    decoded: list[bytes] = []
    for value in values:
        if isinstance(value, bytes):
            decoded.append(value)
        elif isinstance(value, str):
            decoded.append(_decode_hex(value, size=32, field="trusted_public_key"))
        else:
            _bad("INVALID_TRUST_ROOT", "trusted public keys must be raw bytes or hex")
    if declared not in decoded:
        _bad("UNTRUSTED_OPERATOR_KEY", "declared signer key differs from trust root")
    return declared


def verify_operator_envelope(
    envelope: Mapping[str, Any] | str | None,
    manifest: Mapping[str, Any],
    *,
    trusted_public_keys: Mapping[str, str | bytes] | Iterable[str | bytes],
    expected_host: str,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Verify exact manifest/limit/host binding and an Ed25519 signature."""

    if isinstance(envelope, str):
        try:
            value = json.loads(envelope)
        except json.JSONDecodeError as exc:
            _bad("INVALID_OPERATOR_ENVELOPE", f"envelope JSON is invalid: {exc}")
    elif isinstance(envelope, Mapping):
        value = dict(envelope)
    else:
        _bad("MISSING_OPERATOR_ENVELOPE", "operator envelope is required")
    if not isinstance(value, dict) or set(value) != _ENVELOPE_KEYS:
        _bad("INVALID_OPERATOR_ENVELOPE", "operator envelope has non-exact shape")
    if value["schema"] != "forge_lab.operator_envelope.v1":
        _bad("INVALID_OPERATOR_ENVELOPE", "operator envelope schema is invalid")
    if not isinstance(manifest, Mapping):
        _bad("INVALID_MANIFEST", "manifest must be an object")
    limits = manifest.get("limits")
    if not isinstance(limits, Mapping) or any(
        limits.get(field) is None
        for field in (
            "total_tokens",
            "total_usd_micros",
            "total_requests",
            "deadline_utc",
            "host_caps",
        )
    ):
        _bad("MISSING_SPEND_AUTHORITY", "manifest has null cumulative ceilings")
    expected = {
        "campaign_name": manifest.get("campaign_name"),
        "manifest_digest": manifest.get("manifest_digest"),
        "total_tokens": limits["total_tokens"],
        "total_usd_micros": limits["total_usd_micros"],
        "total_requests": limits["total_requests"],
        "deadline_utc": limits["deadline_utc"],
        "host_caps": limits["host_caps"],
    }
    if any(value.get(field) != binding for field, binding in expected.items()):
        _bad(
            "ENVELOPE_BINDING_MISMATCH",
            "operator envelope differs from manifest identity or ceilings",
        )
    if not _DIGEST_RE.fullmatch(str(value["manifest_digest"])):
        _bad("INVALID_OPERATOR_ENVELOPE", "manifest digest is invalid")
    caps = value["host_caps"]
    if not isinstance(caps, Mapping) or caps.get("host") != expected_host:
        _bad("ENVELOPE_HOST_MISMATCH", "operator host cap is not authoritative host")
    issued = _time(value["issued_at"], "issued_at")
    deadline = _time(value["deadline_utc"], "deadline_utc")
    observed = _observed(now)
    if issued > observed:
        _bad("ENVELOPE_NOT_YET_VALID", "operator envelope was issued in the future")
    if observed >= deadline:
        _bad("ENVELOPE_EXPIRED", "operator spend deadline has passed")
    nonce = value["nonce"]
    if not isinstance(nonce, str) or not 16 <= len(nonce) <= 256:
        _bad("INVALID_OPERATOR_ENVELOPE", "operator nonce length is invalid")
    signer = value["signer"]
    if not isinstance(signer, Mapping) or set(signer) != _SIGNER_KEYS:
        _bad("INVALID_OPERATOR_ENVELOPE", "operator signer shape is invalid")
    if signer["algorithm"] != "ed25519":
        _bad("INVALID_OPERATOR_ENVELOPE", "only Ed25519 operator keys are allowed")
    key_id = signer["key_id"]
    if not isinstance(key_id, str) or not key_id:
        _bad("INVALID_OPERATOR_ENVELOPE", "operator key_id is required")
    public = _decode_hex(signer["public_key"], size=32, field="signer.public_key")
    _trusted_key(trusted_public_keys, key_id, public)
    signature = _decode_hex(value["signature"], size=64, field="signature")
    body = dict(value)
    body.pop("signature")
    from dharma_swarm.forge_lab.campaign_contract import canonical_json

    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, canonical_json(body)
        )
    except (InvalidSignature, ValueError) as exc:
        _bad("INVALID_OPERATOR_SIGNATURE", f"operator signature failed: {type(exc).__name__}")
    return value
