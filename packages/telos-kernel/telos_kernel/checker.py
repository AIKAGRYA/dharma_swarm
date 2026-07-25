"""Proof-carrying self-modification certificate verifier (§U11).

Phase 0: stub. Real verifier lands in Phase 6 (Fiat-Shamir Σ-protocol v1).
Phase 8 research spike adds Nova/Sonobe folding IVC.

This stub exists so the kernel `__init__.py` has a stable import surface and
`titanium-verify` has a target from day one (see packages/titanium-verify/).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from icontract import ensure

PHASE_0_UNIMPLEMENTED: Final[str] = (
    "U11 PCC verifier lands in Phase 6 (Fiat-Shamir v1). "
    "See specs/TITANIUM_TELOS_GATES_SPEC_v3.md §U11."
)


@dataclass(frozen=True)
class Certificate:
    """Placeholder shape. Phase 6 replaces this with the real transcript
    of a Fiat-Shamir Σ-protocol: (commitment, challenge, response) with
    the challenge derived from the kernel's head Merkle hash."""
    prev_manifest_hash: str
    new_manifest_hash: str
    scheme: str  # "phase-0-stub" | "fiat-shamir-v1" | ...
    transcript: bytes


@ensure(lambda result: isinstance(result, bool))
def verify_certificate(cert: Certificate, prev_root_hex: str) -> bool:
    """Stub verifier — refuses everything except the empty phase-0 stub.

    Any real self-modification that arrives before Phase 6 must be rejected.
    """
    if cert.scheme != "phase-0-stub":
        return False
    if cert.transcript != b"":
        return False
    # Prev-root binding still required even at stub level, to shake out
    # integration bugs early.
    return cert.prev_manifest_hash != "" and len(prev_root_hex) == 64
