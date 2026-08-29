"""Signed, file-backed operator lease grants for bounded candidate-lane jobs.

Verification alone does not make a grant one-shot.  Live authorization is
one-shot only where PromotionController atomically consumes its grant binding in
CandidateStore before returning an enabled decision.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from dharma_swarm.a2a.candidate_lease import LeaseVerification
from dharma_swarm.a2a.candidate_transport_contract import secure_public_file
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    sign_receipt,
    verify_trusted_signed_receipt,
)

OPERATOR_LEASE_SCHEMA = "forge_lab.operator_candidate_lease.v1"
OPERATOR_LEASE_RECEIPT = "rsi_foundry_operator_candidate_lease"


class OperatorLeaseReceiptError(ValueError):
    pass


def _token(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 512 or any(ord(character) < 32 for character in text):
        raise OperatorLeaseReceiptError(f"{field} must be a non-empty printable token")
    return text


def _sha(value: Any, field: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise OperatorLeaseReceiptError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _instant(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperatorLeaseReceiptError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise OperatorLeaseReceiptError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _stamp(value: str, field: str) -> str:
    return _instant(value, field).isoformat().replace("+00:00", "Z")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise OperatorLeaseReceiptError("operator lease receipt is not JSON")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class OperatorLeaseGrant:
    authority_id: str
    lease_id: str
    candidate_id: str
    envelope_id: str
    fence: int
    scopes: tuple[str, ...]
    issued_at: str
    expires_at: str
    schema: str = OPERATOR_LEASE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != OPERATOR_LEASE_SCHEMA:
            raise OperatorLeaseReceiptError(f"unsupported operator lease schema: {self.schema}")
        for field in ("authority_id", "lease_id", "candidate_id"):
            object.__setattr__(self, field, _token(getattr(self, field), field))
        object.__setattr__(self, "envelope_id", _sha(self.envelope_id, "envelope_id"))
        if not isinstance(self.fence, int) or isinstance(self.fence, bool) or self.fence < 1:
            raise OperatorLeaseReceiptError("fence must be a positive integer")
        scopes = tuple(_token(scope, "scope") for scope in self.scopes)
        if not scopes or len(scopes) != len(set(scopes)):
            raise OperatorLeaseReceiptError("operator lease scopes must be non-empty and unique")
        object.__setattr__(self, "scopes", scopes)
        object.__setattr__(self, "issued_at", _stamp(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", _stamp(self.expires_at, "expires_at"))
        if not _instant(self.issued_at, "issued_at") < _instant(self.expires_at, "expires_at"):
            raise OperatorLeaseReceiptError("operator lease expiry must follow issuance")

    def content_dict(self) -> dict[str, Any]:
        return {**asdict(self), "scopes": list(self.scopes)}

    @property
    def grant_id(self) -> str:
        return canonical_sha256(self.content_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.content_dict(), "grant_id": self.grant_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OperatorLeaseGrant":
        expected = {
            "schema", "authority_id", "lease_id", "candidate_id", "envelope_id",
            "fence", "scopes", "issued_at", "expires_at", "grant_id",
        }
        if set(payload) != expected:
            raise OperatorLeaseReceiptError("operator lease grant fields are invalid")
        grant = cls(
            schema=str(payload.get("schema") or ""),
            authority_id=str(payload.get("authority_id") or ""),
            lease_id=str(payload.get("lease_id") or ""),
            candidate_id=str(payload.get("candidate_id") or ""),
            envelope_id=str(payload.get("envelope_id") or ""),
            fence=payload.get("fence"),
            scopes=tuple(payload.get("scopes") or ()),
            issued_at=str(payload.get("issued_at") or ""),
            expires_at=str(payload.get("expires_at") or ""),
        )
        if payload.get("grant_id") != grant.grant_id:
            raise OperatorLeaseReceiptError("operator lease grant content hash mismatch")
        return grant


@dataclass(frozen=True)
class SignedOperatorLeaseGrant:
    grant: OperatorLeaseGrant
    signature_receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "signature_receipt", _freeze(self.signature_receipt))

    def to_dict(self) -> dict[str, Any]:
        return {"grant": self.grant.to_dict(), "signature_receipt": _thaw(self.signature_receipt)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SignedOperatorLeaseGrant":
        if set(payload) != {"grant", "signature_receipt"}:
            raise OperatorLeaseReceiptError("signed operator lease fields are invalid")
        receipt = payload.get("signature_receipt")
        if not isinstance(receipt, Mapping):
            raise OperatorLeaseReceiptError("operator lease signature receipt is invalid")
        return cls(
            grant=OperatorLeaseGrant.from_dict(payload.get("grant") or {}),
            signature_receipt=dict(receipt),
        )

    def verify(self, trusted_public_keys: Iterable[str | bytes]) -> bool:
        receipt = _thaw(self.signature_receipt)
        return bool(
            receipt.get("name") == OPERATOR_LEASE_RECEIPT
            and receipt.get("payload") == self.grant.to_dict()
            and verify_trusted_signed_receipt(receipt, trusted_public_keys=trusted_public_keys)
        )


def sign_operator_lease_grant(
    grant: OperatorLeaseGrant,
    *,
    signing_key: Any,
    authority_epoch_sha256: str,
) -> SignedOperatorLeaseGrant:
    receipt = sign_receipt(
        name=OPERATOR_LEASE_RECEIPT,
        payload=grant.to_dict(),
        signing_key=signing_key,
        epoch_ruler_sha256=_sha(authority_epoch_sha256, "authority_epoch_sha256"),
    )
    return SignedOperatorLeaseGrant(grant=grant, signature_receipt=receipt)


class SignedLeaseFileVerifier:
    """Verify an operator-signed public grant from a safe immutable receipt path."""

    def __init__(self, path: Path | str, *, trusted_public_keys: Iterable[str | bytes]) -> None:
        self.path = str(path)
        self.trusted_public_keys = tuple(trusted_public_keys)
        if not self.trusted_public_keys:
            raise OperatorLeaseReceiptError("at least one trusted operator lease key is required")

    def verify(self, **request: Any) -> LeaseVerification:
        receipt_sha256 = ""
        allowed = False
        reason = "operator_lease_unreadable"
        try:
            path = secure_public_file(self.path, "operator lease receipt")
            payload = json.loads(path.read_text(encoding="utf-8"))
            signed = SignedOperatorLeaseGrant.from_dict(payload)
            receipt_sha256 = canonical_sha256(signed.to_dict())
            grant = signed.grant
            now = _instant(request["now"], "now")
            exact = (
                signed.verify(self.trusted_public_keys)
                and grant.authority_id == request["authority_id"]
                and grant.lease_id == request["lease_id"]
                and grant.candidate_id == request["candidate_id"]
                and grant.envelope_id == request["envelope_id"]
                and grant.fence == request["fence"]
                and grant.expires_at == _stamp(request["lease_expires_at"], "lease_expires_at")
                and request["required_scope"] in grant.scopes
                and _instant(grant.issued_at, "issued_at") <= now < _instant(grant.expires_at, "expires_at")
            )
            allowed, reason = exact, "verified" if exact else "operator_lease_binding_invalid"
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass
        return LeaseVerification(
            allowed=allowed,
            reason_code=reason,
            authority_id=request["authority_id"],
            lease_id=request["lease_id"],
            candidate_id=request["candidate_id"],
            envelope_id=request["envelope_id"],
            fence=request["fence"],
            expires_at=request["lease_expires_at"],
            required_scope=request["required_scope"],
            verified_at=request["now"],
            verifier_receipt_sha256=receipt_sha256 if allowed else "",
        )


__all__ = [
    "OPERATOR_LEASE_RECEIPT",
    "OPERATOR_LEASE_SCHEMA",
    "OperatorLeaseGrant",
    "OperatorLeaseReceiptError",
    "SignedLeaseFileVerifier",
    "SignedOperatorLeaseGrant",
    "sign_operator_lease_grant",
]
