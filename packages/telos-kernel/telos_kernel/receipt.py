"""Signed Merkle leaf schema for Titanium Telos Gates v3.

Every gate verdict is materialized as a `Leaf` conforming to §3 of the spec:

    gate: U{k}_{name}
    tier: A | B | C
    proposal_id: <uuid>
    prev_merkle_root: <sha256 hex>
    measure: {invariant-specific}
    threshold: {invariant-specific}
    verdict: ALLOW | WARN | REVIEW | BLOCK
    capability_signature: <ed25519 sig over JCS payload>
    timestamp: <utc iso8601>

The signature covers the JCS-canonical serialization of the payload with the
`capability_signature` field elided (or set to the empty string) — this is the
standard "detach the signature field before signing" pattern. See
[JWS RFC 7515 §5.1](https://datatracker.ietf.org/doc/html/rfc7515#section-5.1)
for the archetypal example.
"""
from __future__ import annotations

import datetime as _dt
import enum
import uuid
from typing import Any, Final, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

from telos_kernel.canonical import canonicalize

SCHEMA_VERSION: Final[str] = "v3.0"


class Tier(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class Verdict(str, enum.Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class SignatureStatus(str, enum.Enum):
    """Bootstrapping affordance for Phase 0.

    STUB   — signer set has placeholder keys; kernel emits WARN receipts.
    REAL   — signer set has real Ed25519 keys; enforcement can proceed.
    ABSENT — receipt is unsigned (used only for the pre-signer-init boot leaf).
    """
    STUB = "STUB"
    REAL = "REAL"
    ABSENT = "ABSENT"


class Leaf(BaseModel):
    """A signed Merkle leaf. Immutable, forbid-extra, deterministic under JCS.

    Field order in this class matters only for readability; the wire format
    is determined by JCS (alphabetical key sort)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
        arbitrary_types_allowed=False,
    )

    schema_version: Literal["v3.0"] = SCHEMA_VERSION
    gate: str = Field(pattern=r"^U(0|1|2|3|4|5|6|7|8|9|10|11)_[a-z_]+$|^boot$|^migration$")
    tier: Tier
    proposal_id: str
    prev_merkle_root: str = Field(pattern=r"^[0-9a-f]{64}$|^GENESIS$")
    measure: dict[str, Any]
    threshold: dict[str, Any]
    verdict: Verdict
    signature_status: SignatureStatus
    capability_signature: str  # hex-encoded Ed25519 sig, or "" if ABSENT
    signer_key_id: str          # public-key fingerprint or "STUB_SIGNER_{i}" or ""
    timestamp: str              # ISO 8601 UTC, e.g. "2026-07-03T18:40:00Z"

    @field_validator("proposal_id")
    @classmethod
    def _validate_uuid(cls, v: str) -> str:
        # Accept any parseable UUID form but re-emit as canonical.
        return str(uuid.UUID(v))

    @field_validator("timestamp")
    @classmethod
    def _validate_ts(cls, v: str) -> str:
        # Enforce ISO 8601 with trailing 'Z' (UTC). We parse via fromisoformat
        # after normalizing 'Z' -> '+00:00' per Python 3.11+ semantics.
        parsed = _dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() != _dt.timedelta(0):
            raise ValueError("timestamp must be UTC")
        # Canonical form: 'YYYY-MM-DDTHH:MM:SSZ' or with fractional seconds
        return v

    def signing_bytes(self) -> bytes:
        """JCS-canonical bytes of the payload with `capability_signature` blanked.

        This is what Ed25519 signs. Verifying re-computes this and compares.
        """
        payload = self.model_dump()
        payload["capability_signature"] = ""
        return canonicalize(payload)

    def sign(self, sk: Ed25519PrivateKey, key_id: str) -> "Leaf":
        """Return a new Leaf with capability_signature populated.

        The signing sequence is:
          1. Populate `signer_key_id` (part of the signed payload).
          2. Compute JCS bytes with `capability_signature` blanked.
          3. Sign, then set `capability_signature`.

        This ensures verify() reproduces exactly the same bytes.
        """
        if self.signature_status == SignatureStatus.ABSENT:
            # ABSENT leaves must not be signed — return unchanged.
            return self
        # Step 1: bind the key id into the payload first.
        with_key = self.model_copy(update={"signer_key_id": key_id})
        # Step 2 + 3: sign the JCS payload (with signature field blank) and
        # attach the signature.
        sig = sk.sign(with_key.signing_bytes()).hex()
        return with_key.model_copy(update={"capability_signature": sig})

    def verify(self, pk: Ed25519PublicKey) -> bool:
        """Verify the signature under the given public key."""
        if self.signature_status == SignatureStatus.ABSENT:
            return self.capability_signature == ""
        try:
            pk.verify(bytes.fromhex(self.capability_signature), self.signing_bytes())
            return True
        except (InvalidSignature, ValueError):
            return False


def now_iso_utc() -> str:
    """Deterministic-timezone helper. Tests should monkeypatch this or
    pass an explicit timestamp for determinism."""
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def new_proposal_id() -> str:
    return str(uuid.uuid4())
