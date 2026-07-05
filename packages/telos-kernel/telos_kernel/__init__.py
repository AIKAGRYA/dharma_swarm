"""telos-kernel — Titanium Telos Gates v3 TCB.

Public surface (Phase 0):
  * `MerkleLog`, `verify_merkle_inclusion`
  * `Leaf`, `Tier`, `Verdict`, `SignatureStatus`, `now_iso_utc`, `new_proposal_id`
  * `Manifest`, `load_manifest`, `EnforcementStatus`
  * `Macaroon`, `mint`, `add_first_party_caveat`, `verify`, `new_root_key`
  * `LocalFileAnchor`, `NotaryAnchor`, `AnchorReceipt`
  * `Certificate`, `verify_certificate` (stub — Phase 6 fills in)
  * `check(...)` — top-level gate dispatch (Phase 0: routes only U5-related receipts)
  * `boot(...)` — emits the boot receipt on kernel init
  * `verify_chain(...)` — proxy to the ambient MerkleLog

Nothing in this module performs `eval`, `exec`, `__import__`, or dynamic
attribute mutation. See SECURITY.md.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from telos_kernel.canonical import canonicalize
from telos_kernel.capabilities import (
    Caveat,
    Macaroon,
    add_first_party_caveat,
    mint,
    new_root_key,
    verify as verify_capability,
)
from telos_kernel.checker import Certificate, verify_certificate
from telos_kernel.manifest import (
    EnforcementStatus,
    InvariantSpec,
    Manifest,
    Signer,
    load_manifest,
)
from telos_kernel.merkle_log import (
    FileBackend,
    MemoryBackend,
    MerkleLog,
    verify_merkle_inclusion,
)
from telos_kernel.notary import AnchorReceipt, LocalFileAnchor, NotaryAnchor
from telos_kernel.receipt import (
    Leaf,
    SignatureStatus,
    Tier,
    Verdict,
    new_proposal_id,
    now_iso_utc,
)

__all__ = [
    # Merkle
    "MerkleLog", "MemoryBackend", "FileBackend", "verify_merkle_inclusion",
    # Receipts
    "Leaf", "Tier", "Verdict", "SignatureStatus", "now_iso_utc", "new_proposal_id",
    # Manifest
    "Manifest", "InvariantSpec", "Signer", "EnforcementStatus", "load_manifest",
    # Capabilities
    "Macaroon", "Caveat", "mint", "add_first_party_caveat", "verify_capability",
    "new_root_key",
    # Notary
    "LocalFileAnchor", "NotaryAnchor", "AnchorReceipt",
    # Certificate
    "Certificate", "verify_certificate",
    # Top-level ops
    "boot", "check", "verify_chain",
]

__version__ = "0.1.0"

# Module-scoped ambient log is deliberately absent — every caller passes an
# explicit MerkleLog in. See SECURITY.md §4 (no ambient authority).


def _sbom_digest() -> str:
    """Cheap software-bill-of-materials digest for the boot receipt.

    Binds the boot leaf to (Python version, executable path, kernel version,
    kernel source file digests). Any drift in the TCB itself is caught by
    receipt diffing across boots.
    """
    tcb_root = Path(__file__).parent
    parts: list[str] = [
        f"python={sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        f"executable_hash={hashlib.sha256(sys.executable.encode('utf-8')).hexdigest()}",
        f"telos_kernel_version={__version__}",
    ]
    # Digest every kernel .py file (excluding tests). Deterministic order.
    for p in sorted(tcb_root.rglob("*.py")):
        if "/tests/" in str(p).replace("\\", "/"):
            continue
        with open(p, "rb") as f:
            parts.append(f"{p.relative_to(tcb_root)}={hashlib.sha256(f.read()).hexdigest()}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def boot(
    log: MerkleLog,
    manifest: Manifest,
    anchor: NotaryAnchor | None = None,
) -> Leaf:
    """Emit the boot leaf and (optionally) anchor the new head.

    The boot leaf's `verdict` is:
      * ALLOW if manifest has no stub signers,
      * WARN  if any signer is a STUB (Phase 0 default).

    Returns the appended Leaf.
    """
    stubs = manifest.has_stub_signers()
    verdict = Verdict.WARN if stubs else Verdict.ALLOW
    sig_status = SignatureStatus.STUB if stubs else SignatureStatus.ABSENT
    leaf = Leaf(
        gate="boot",
        tier=Tier.A,
        proposal_id=new_proposal_id(),
        prev_merkle_root=log.head_hash(),
        measure={
            "manifest_hash": manifest.content_hash(),
            "sbom_digest": _sbom_digest(),
            "kernel_version": __version__,
            "enforced_ids": sorted(manifest.enforced_ids()),
            "signer_stubs_present": stubs,
        },
        threshold={"boot_must_have_manifest": True},
        verdict=verdict,
        signature_status=sig_status,
        capability_signature="",
        signer_key_id="",
        timestamp=now_iso_utc(),
    )
    log.append(leaf)
    if anchor is not None:
        anchor.anchor(log.head_hash())
    return leaf


def check(
    gate: str,
    tier: Tier,
    measure: dict[str, Any],
    threshold: dict[str, Any],
    verdict: Verdict,
    log: MerkleLog,
    capability: Macaroon | None = None,
    root_key: bytes | None = None,
    proposal_id: str | None = None,
) -> Leaf:
    """Top-level gate dispatch.

    Phase 0 responsibility: build the Leaf, verify the (optional) capability
    against a context, append to the log, return the leaf.

    Later phases route by `gate` to specialized verifiers (U4 causal, U7
    contextual, etc.) that produce the `measure`/`threshold`/`verdict`
    themselves. In Phase 0 the caller supplies those directly.
    """
    if capability is not None:
        if root_key is None:
            raise ValueError("root_key required when capability is provided")
        ctx = {"gate": gate, "tier": tier.value}
        if not verify_capability(capability, root_key, ctx):
            # Fail-closed BLOCK — record the refusal.
            verdict = Verdict.BLOCK

    leaf = Leaf(
        gate=gate,
        tier=tier,
        proposal_id=proposal_id or new_proposal_id(),
        prev_merkle_root=log.head_hash(),
        measure=measure,
        threshold=threshold,
        verdict=verdict,
        signature_status=SignatureStatus.ABSENT,  # signing lands with real signers in Phase 1
        capability_signature="",
        signer_key_id="",
        timestamp=now_iso_utc(),
    )
    log.append(leaf)
    return leaf


def verify_chain(log: MerkleLog) -> tuple[bool, int | None]:
    """Verify the ambient MerkleLog. Returns (True, None) on full validity."""
    return log.verify_chain()
