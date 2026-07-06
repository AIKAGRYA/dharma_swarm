"""U-invariant manifest — signed, K-of-N quorum-verified.

Loads `kernel/manifest.yaml`, validates its shape via Pydantic, and enforces
the Ed25519 K-of-N quorum on any change (§U2).

Phase 0: manifest is loaded and its hash is bound into the boot receipt.
K=3/N=5 quorum verification is implemented but not yet enforcing edits
(Phase 1 wires the enforcement path in `dharma_swarm/telos_gates.py`).
"""
from __future__ import annotations

import enum
import hashlib
from typing import Any, Final, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from icontract import ensure, require
from pydantic import BaseModel, ConfigDict, Field, field_validator

from telos_kernel.canonical import JSONValue, canonicalize
from telos_kernel.effects import Effect, effect
from telos_kernel.result import (
    ERR_INVALID_SIGNATURE,
    ERR_QUORUM_NOT_MET,
    ERR_STUB_SIGNERS,
    ERR_UNKNOWN_SIGNER,
    Err,
    KernelError,
    Ok,
    Result,
)

MANIFEST_SCHEMA_VERSION: Final[str] = "v3.0"


class EnforcementStatus(str, enum.Enum):
    DECLARED = "declared"   # in-manifest but no enforcement path yet
    ENFORCED = "enforced"   # gate check is active
    RETIRED = "retired"     # kept for audit-trail continuity, not evaluated


class InvariantSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^U(0|1|2|3|4|5|6|7|8|9|10|11)$")
    name: str
    predicate: str
    measure: str
    threshold: dict[str, Any]
    receipt_type: str
    falsification_test: str
    tier: Literal["A", "B", "C", "A+B", "A+B+C"]
    citations: list[str]  # markdown-linked citations, at least one required
    enforcement_status: EnforcementStatus

    @field_validator("citations")
    @classmethod
    def _at_least_one_citation(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("every U-invariant must have at least one citation")
        return v


class Signer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key_id: str  # short human-readable id, e.g. "signer_1" or a real fingerprint
    public_key_hex: str  # 32-byte Ed25519 public key as 64 hex chars, or "STUB"
    role: str
    stub: bool = False  # True if `public_key_hex == "STUB"`

    @field_validator("public_key_hex")
    @classmethod
    def _validate_pk(cls, v: str) -> str:
        if v == "STUB":
            return v
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError(
                "public_key_hex must be 32-byte hex (64 chars) or the literal 'STUB'"
            )
        return v.lower()


class Manifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["v3.0"] = MANIFEST_SCHEMA_VERSION
    version: str  # e.g. "phase-0.1"
    invariants: list[InvariantSpec]
    signer_set: dict[str, Any]  # {"k": int, "n": int, "signers": [Signer, ...]}

    @field_validator("signer_set")
    @classmethod
    def _validate_signer_set(cls, v: dict[str, Any]) -> dict[str, Any]:
        k, n = v.get("k"), v.get("n")
        signers = v.get("signers", [])
        if not isinstance(k, int) or not isinstance(n, int):
            raise ValueError("signer_set.k and signer_set.n must be integers")
        if not (1 <= k <= n):
            raise ValueError(f"require 1 <= K ({k}) <= N ({n})")
        if len(signers) != n:
            raise ValueError(f"signer_set must contain exactly N={n} signers")
        # Validate each signer through the Signer model.
        _ = [Signer.model_validate(s) for s in signers]
        return v

    # ---- Derived accessors ----

    def to_canonical_dict(self) -> dict[str, JSONValue]:
        """Hand-rolled canonical projection. See `Leaf.to_canonical_dict` for
        why we do not use `model_dump()` on the signing/hashing path."""
        return {
            "schema_version": self.schema_version,
            "version": self.version,
            "invariants": [_invariant_to_dict(i) for i in self.invariants],
            "signer_set": _signer_set_to_dict(self.signer_set),
        }

    def content_hash(self) -> str:
        """SHA-256 of the JCS-canonical manifest bytes (excluding signatures)."""
        payload = self.to_canonical_dict()
        # Signatures live external to the manifest object; the hash covers
        # the whole schema-versioned document.
        return hashlib.sha256(canonicalize(payload)).hexdigest()

    def has_stub_signers(self) -> bool:
        return any(
            s.get("public_key_hex") == "STUB" or s.get("stub", False)
            for s in self.signer_set["signers"]
        )

    def enforced_ids(self) -> set[str]:
        return {i.id for i in self.invariants
                if i.enforcement_status == EnforcementStatus.ENFORCED}

    def public_keys(self) -> list[tuple[str, Ed25519PublicKey]]:
        """Return `(key_id, public_key)` pairs for non-stub signers."""
        out: list[tuple[str, Ed25519PublicKey]] = []
        for s in self.signer_set["signers"]:
            if s.get("public_key_hex") == "STUB":
                continue
            pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(s["public_key_hex"]))
            out.append((s["key_id"], pk))
        return out

    # ---- K-of-N quorum verification ----

    @require(lambda self, signatures: isinstance(signatures, dict))
    def verify_quorum_result(
        self,
        payload_bytes: bytes,
        signatures: dict[str, bytes],
    ) -> Result:
        """Structured K-of-N quorum verification.

        Returns Ok({'valid_count': int, 'k': int}) on success or
        Err(KernelError) naming the failure mode (stub signers,
        quorum not met, unknown signer id, malformed signature).
        Never raises.
        """
        if self.has_stub_signers():
            return Err(KernelError(
                ERR_STUB_SIGNERS,
                "manifest signer_set contains STUB entries; quorum disabled",
            ))

        k = self.signer_set["k"]
        pk_by_id = dict(self.public_keys())
        valid = 0
        seen: set[str] = set()
        unknown: list[str] = []
        for key_id, sig in signatures.items():
            if key_id in seen:
                continue
            seen.add(key_id)
            pk = pk_by_id.get(key_id)
            if pk is None:
                unknown.append(key_id)
                continue
            try:
                pk.verify(sig, payload_bytes)
                valid += 1
            except (InvalidSignature, ValueError, TypeError):
                # Malformed or wrong signature; count as a miss, not fatal
                # because K-of-N can still be met by other signers.
                continue
            if valid >= k:
                return Ok({"valid_count": valid, "k": k})
        return Err(KernelError(
            ERR_QUORUM_NOT_MET,
            f"only {valid} valid signatures, need K={k}",
            detail={"valid_count": valid, "k": k, "unknown_signers": unknown},
        ))

    @require(lambda self, signatures: isinstance(signatures, dict))
    @ensure(lambda result: isinstance(result, bool))
    def verify_quorum(
        self,
        payload_bytes: bytes,
        signatures: dict[str, bytes],
    ) -> bool:
        """Boolean shim over verify_quorum_result(). Prefer the Result variant."""
        return self.verify_quorum_result(payload_bytes, signatures).is_ok


# ---- Canonical-projection helpers ------------------------------------------

def _invariant_to_dict(i: InvariantSpec) -> dict[str, JSONValue]:
    return {
        "id": i.id,
        "name": i.name,
        "predicate": i.predicate,
        "measure": i.measure,
        "threshold": _coerce_json_manifest(i.threshold),
        "receipt_type": i.receipt_type,
        "falsification_test": i.falsification_test,
        "tier": i.tier,
        "citations": list(i.citations),
        "enforcement_status": i.enforcement_status.value,
    }


def _signer_set_to_dict(v: dict[str, Any]) -> dict[str, JSONValue]:
    return {
        "k": int(v["k"]),
        "n": int(v["n"]),
        "signers": [
            {
                "key_id": s["key_id"],
                "public_key_hex": s["public_key_hex"],
                "role": s["role"],
                "stub": bool(s.get("stub", s["public_key_hex"] == "STUB")),
            }
            for s in v["signers"]
        ],
    }


def _coerce_json_manifest(value: Any) -> JSONValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_json_manifest(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _coerce_json_manifest(v) for k, v in value.items()}
    raise ValueError(f"cannot coerce {type(value).__name__!r} to JSONValue")


# ---- Loader ----------------------------------------------------------------
#
# The `load_manifest` function used to live here; it did `open()` +
# `yaml.safe_load()`, both of which are Effect.FS_READ and must not live
# in the verified core. It now lives in `telos_kernel._io.manifest_loader`
# and is re-exported at package level for backwards compatibility.
#
# See `telos_kernel/_io/README.md` for the trust-boundary contract.


@effect(Effect.FS_READ)
def load_manifest(path: object = None) -> Manifest:
    """Backwards-compat re-export. Delegates to the I/O rim.

    New code should call `telos_kernel._io.load_manifest_from_disk`
    directly so the effect is visible at the call site.
    """
    # Local import to avoid pulling I/O into the core module's import graph.
    from telos_kernel._io.manifest_loader import load_manifest_from_disk
    return load_manifest_from_disk(path)
