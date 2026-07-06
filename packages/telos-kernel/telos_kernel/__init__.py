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
from telos_kernel.effects import Effect, effect
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
from telos_kernel.result import Err, KernelError, Ok, Result

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
    # Result ADT
    "Ok", "Err", "Result", "KernelError",
    # Certificate
    "Certificate", "verify_certificate",
    # Top-level ops
    "boot", "check", "verify_chain",
]

__version__ = "0.1.0"

# Module-scoped ambient log is deliberately absent — every caller passes an
# explicit MerkleLog in. See SECURITY.md §4 (no ambient authority).


@effect(Effect.FS_READ)
def _sbom_digest() -> str:
    """Backwards-compat shim. Delegates to the I/O rim.

    New callers should import `compute_sbom_digest` from
    `telos_kernel._io.sbom` directly so the FS_READ effect is visible.
    """
    from telos_kernel._io.sbom import compute_sbom_digest
    return compute_sbom_digest()


@effect(Effect.FS_READ, Effect.NONDETERMINISTIC)
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


@effect(Effect.NONDETERMINISTIC)
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
