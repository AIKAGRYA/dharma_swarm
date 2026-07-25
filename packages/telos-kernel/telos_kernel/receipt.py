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

from telos_kernel.canonical import JSONValue, canonicalize
from telos_kernel.effects import Effect, effect
from telos_kernel.result import (
    ERR_INVALID_SIGNATURE,
    ERR_MALFORMED_HEX,
    Err,
    KernelError,
    Ok,
    Result,
)

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

    def to_canonical_dict(self) -> dict[str, JSONValue]:
        """Hand-rolled, ordered projection to a JSONValue dict.

        This deliberately does NOT go through Pydantic `model_dump()`.
        Reasons:
          1. Determinism — no dependency on Pydantic serialization
             behavior across versions.
          2. Hot-path latency — Tier A gates have a p95 <= 5 ms budget;
             `model_dump()` walks the C descriptor for every field.
          3. Verifiability — `titanium-verify` (packages/titanium-verify/)
             can prove exhaustiveness of this projection; it cannot see
             through Pydantic's descriptor.

        A drift test (`tests/test_canonical_dict_matches_model_dump`)
        keeps this in lockstep with the Pydantic model.
        """
        return {
            "schema_version": self.schema_version,
            "gate": self.gate,
            "tier": self.tier.value,
            "proposal_id": self.proposal_id,
            "prev_merkle_root": self.prev_merkle_root,
            "measure": _coerce_json(self.measure),
            "threshold": _coerce_json(self.threshold),
            "verdict": self.verdict.value,
            "signature_status": self.signature_status.value,
            "capability_signature": self.capability_signature,
            "signer_key_id": self.signer_key_id,
            "timestamp": self.timestamp,
        }

    def signing_bytes(self) -> bytes:
        """JCS-canonical bytes of the payload with `capability_signature` blanked.

        This is what Ed25519 signs. Verifying re-computes this and compares.
        """
        payload = self.to_canonical_dict()
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

    def verify_result(self, pk: Ed25519PublicKey) -> Result:
        """Structured verify. Returns Ok(True) or Err(KernelError).

        Never raises. Distinguishes signature-mismatch from malformed-hex
        so callers can log the specific failure mode. `titanium-verify`
        proves the fail-closed postcondition on this function.
        """
        if self.signature_status == SignatureStatus.ABSENT:
            if self.capability_signature == "":
                return Ok(True)
            return Err(KernelError(
                ERR_INVALID_SIGNATURE,
                "ABSENT leaf must have empty signature",
            ))
        try:
            sig_bytes = bytes.fromhex(self.capability_signature)
        except ValueError as e:
            return Err(KernelError(ERR_MALFORMED_HEX, str(e)))
        try:
            pk.verify(sig_bytes, self.signing_bytes())
            return Ok(True)
        except InvalidSignature:
            return Err(KernelError(
                ERR_INVALID_SIGNATURE,
                "Ed25519 verification failed",
            ))

    def verify(self, pk: Ed25519PublicKey) -> bool:
        """Boolean shim over verify_result(). Prefer verify_result() in new code."""
        return self.verify_result(pk).is_ok


def _coerce_json(value: Any) -> JSONValue:
    """Deep-coerce a nested dict/list to JSONValue, rejecting non-JCS types.

    This is applied to `measure` and `threshold` (which are `dict[str, Any]`
    at the Pydantic layer). Every leaf must already be a JSONValue; we do not
    silently stringify — unknown types raise so callers see the problem
    immediately.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_json(v) for v in value]
    if isinstance(value, dict):
        out: dict[str, JSONValue] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(
                    f"canonical dict keys must be str, got {type(k).__name__!r}"
                )
            out[k] = _coerce_json(v)
        return out
    raise ValueError(
        f"cannot coerce {type(value).__name__!r} to JSONValue "
        f"(only None, bool, int, float, str, list, tuple, dict allowed)"
    )


@effect(Effect.NONDETERMINISTIC)
def now_iso_utc() -> str:
    """Deterministic-timezone helper.

    Effect: NONDETERMINISTIC — reads the system clock via datetime.now().
    Tests should monkeypatch this or pass an explicit timestamp for
    determinism.
    """
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@effect(Effect.NONDETERMINISTIC)
def new_proposal_id() -> str:
    """Generate a fresh proposal id.

    Effect: NONDETERMINISTIC — uuid.uuid4() draws from OS entropy.
    Callers that want deterministic ids must pass an explicit id string.
    """
    return str(uuid.uuid4())
