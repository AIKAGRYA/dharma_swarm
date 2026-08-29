"""Exact result contract for operator-owned candidate lease verification."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Protocol

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LeaseVerificationError(ValueError):
    """A verifier result is structurally incomplete or self-contradictory."""


def lease_instant(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeaseVerificationError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise LeaseVerificationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _stamp(value: str, field: str) -> str:
    return lease_instant(value, field).isoformat().replace("+00:00", "Z")


def _token(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 512 or any(ord(character) < 32 for character in text):
        raise LeaseVerificationError(f"{field} must be a non-empty printable token")
    return text


@dataclass(frozen=True)
class LeaseVerification:
    """Verifier result carrying every security-relevant request binding."""

    allowed: bool
    reason_code: str
    authority_id: str
    lease_id: str
    candidate_id: str
    envelope_id: str
    fence: int
    expires_at: str
    required_scope: str
    verified_at: str
    verifier_receipt_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise LeaseVerificationError("allowed must be boolean")
        for field in ("reason_code", "authority_id", "lease_id", "candidate_id", "required_scope"):
            object.__setattr__(self, field, _token(getattr(self, field), field))
        envelope_id = str(self.envelope_id or "").lower()
        if not _SHA256.fullmatch(envelope_id):
            raise LeaseVerificationError("envelope_id must be a lowercase SHA-256 digest")
        object.__setattr__(self, "envelope_id", envelope_id)
        if not isinstance(self.fence, int) or isinstance(self.fence, bool) or self.fence < 1:
            raise LeaseVerificationError("fence must be a positive integer")
        object.__setattr__(self, "expires_at", _stamp(self.expires_at, "expires_at"))
        object.__setattr__(self, "verified_at", _stamp(self.verified_at, "verified_at"))
        receipt = str(self.verifier_receipt_sha256 or "").lower()
        if self.allowed and not _SHA256.fullmatch(receipt):
            raise LeaseVerificationError("allowed result requires a full verifier receipt digest")
        if receipt and not _SHA256.fullmatch(receipt):
            raise LeaseVerificationError("verifier receipt must be a lowercase SHA-256 digest")
        object.__setattr__(self, "verifier_receipt_sha256", receipt)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OperatorLeaseVerifier(Protocol):
    """Boundary to an operator-owned, durable, authenticated lease authority."""

    def verify(
        self,
        *,
        authority_id: str,
        lease_id: str,
        candidate_id: str,
        envelope_id: str,
        fence: int,
        lease_expires_at: str,
        required_scope: str,
        now: str,
    ) -> LeaseVerification | Awaitable[LeaseVerification]: ...


def lease_result_is_exact(
    result: LeaseVerification,
    *,
    authority_id: str,
    lease_id: str,
    candidate_id: str,
    envelope_id: str,
    fence: int,
    lease_expires_at: str,
    required_scope: str,
    now: str,
) -> bool:
    """Compare all request fields and require verification before lease expiry."""

    try:
        return bool(
            result.allowed
            and result.authority_id == authority_id
            and result.lease_id == lease_id
            and result.candidate_id == candidate_id
            and result.envelope_id == envelope_id
            and result.fence == fence
            and result.expires_at == _stamp(lease_expires_at, "lease_expires_at")
            and result.required_scope == required_scope
            and result.verified_at == _stamp(now, "now")
            and lease_instant(now, "now") < lease_instant(result.expires_at, "expires_at")
            and bool(_SHA256.fullmatch(result.verifier_receipt_sha256))
        )
    except (AttributeError, LeaseVerificationError):
        return False


__all__ = [
    "LeaseVerification",
    "LeaseVerificationError",
    "OperatorLeaseVerifier",
    "lease_instant",
    "lease_result_is_exact",
]
