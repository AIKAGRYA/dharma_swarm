"""WelfareTonMintGate — the fail-closed gate that refuses to call anything "verified".

Built in direct response to an 8-lens adversarial review (2026-06-28). Its three sink
risks are adopted as SIS's risk register:
  1. the welfare-ton is a category error if treated as a tradable commodity;
  2. decorrelated aggregation is theatre unless it empirically beats the best single
     rater on calibrated holdout cases;
  3. the trust spine is ceremony unless receipts/attestations are signed, externally
     anchored, and FAIL-CLOSED.

This module is the keystone the review named: the gate that **mints nothing** from
internal artifacts and **fails loudly** until externally-sourced evidence exists. It is
projection-only — it imports no owned surface (spine/**, gaia_ledger, telos_gates) and
mutates nothing; it reads a claim packet and decides. The score it gates is a
**Bounded Welfare Assurance Score** — a site-specific, bounded assurance reading, *not*
a fungible unit and *not* a tradable ton (lens 1). Until the world pushes back, the
honest word is "internal rehearsal", never "verified" (lens 8).

Honest scope of v0: this gate enforces the *fail-closed presence + completeness* of the
required external evidence and the conflict-separation rule (self-observation may block
or downgrade, never approve — lens 3). It does **not** yet verify signatures
cryptographically; that is `ReceiptEnvelope v0` (Ed25519 + signer registry + Merkle
anchor), a required follow-up, flagged on every decision so the gate never overclaims
crypto it does not have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# The required external-evidence families (lenses 2, 3, 6, 7). Each must be present and
# externally-sourced for a mint; absence => BLOCKED, never silently allowed.
_REQUIRED_MRV_INPUTS = (
    "baseline", "leakage", "permanence", "biodiversity_protocol", "oracle_dependency_matrix",
)
_MIN_SIGNED_ATTESTATIONS = 3          # quorum of signed external attestations
_MIN_INDEPENDENT_FAMILIES = 2          # correlated oracles collapse into one family


@dataclass(frozen=True, slots=True)
class CommunityCustodyRecord:
    """GaiaCommunityCustodyRecord (lens 7): agency cannot be a desk-scored float.
    A is zero unless a community-designated custodian controls consent."""
    custodian_id: str = ""
    custodian_countersignature: str = ""      # presence-checked (crypto is ReceiptEnvelope v0)
    consent_scope: str = ""
    withdrawal_supported: bool = False
    benefit_sharing_terms: str = ""

    def is_valid(self) -> bool:
        return bool(self.custodian_id and self.custodian_countersignature and self.consent_scope)


@dataclass(frozen=True, slots=True)
class SignedOracleAttestation:
    """An external attestation. 'Signed' = has a registered signer + a signature string
    (cryptographic verification deferred to ReceiptEnvelope v0)."""
    signer_id: str = ""
    signature: str = ""
    evidence_family: str = ""                  # for the independence/dependency collapse
    is_external: bool = True                    # self-issued attestations never count

    def is_signed(self) -> bool:
        return bool(self.signer_id and self.signature and self.is_external)


@dataclass(frozen=True, slots=True)
class ClaimPacket:
    """A hostile, fail-closed claim packet (the review's MRVIntegrityPacket +
    custody + attestations + envelope, assembled)."""
    claim_id: str
    bounded_welfare_assurance_score: float = 0.0      # NOT a welfare-ton; bounded, site-specific
    mrv_integrity: dict[str, Any] = field(default_factory=dict)
    custody: Optional[CommunityCustodyRecord] = None
    attestations: tuple[SignedOracleAttestation, ...] = ()
    external_countersignature: str = ""               # One Wire: a party != issuer
    issuer_id: str = ""
    countersigner_id: str = ""
    receipt_envelope_signed: bool = False             # ReceiptEnvelope v0 present + signed


@dataclass(frozen=True, slots=True)
class MintDecision:
    status: Literal["BLOCKED", "ALLOW"]
    missing: tuple[str, ...]
    reasons: tuple[str, ...]
    crypto_note: str = (
        "v0: presence/completeness + conflict-separation enforced; signatures NOT yet "
        "cryptographically verified (ReceiptEnvelope v0 / Ed25519 is the required next layer)"
    )

    def loud(self) -> str:
        head = f"[{self.status}] claim mint gate"
        if self.status == "ALLOW":
            return f"{head} — all external evidence present ({self.crypto_note})"
        miss = "; ".join(self.missing) or "(none)"
        return f"{head} — FAILED CLOSED. missing: {miss}. {self.crypto_note}"


def evaluate(packet: ClaimPacket) -> MintDecision:
    """Fail-closed. Returns ALLOW only when EVERY external-evidence family is present;
    internal-only packets are always BLOCKED (self-observation never approves)."""
    missing: list[str] = []
    reasons: list[str] = []

    # 1. MRV integrity inputs (lens 2): all required, externally modelled. Fail closed
    # on ABSENT or None only — a legitimate zero-valued measurement (leakage: 0.0) is
    # present evidence, not missing evidence.
    miss_mrv = [
        k for k in _REQUIRED_MRV_INPUTS
        if k not in packet.mrv_integrity or packet.mrv_integrity[k] is None
    ]
    if miss_mrv:
        missing.append(f"mrv_integrity[{','.join(miss_mrv)}]")

    # 2. Community custody (lens 7): no nonzero agency without a custodian countersignature.
    if packet.custody is None or not packet.custody.is_valid():
        missing.append("community_custody_countersignature")
        reasons.append("agency_factor forced to 0: no community-designated custodian consent")

    # 3. Signed external attestation quorum + independence collapse (lenses 2, 6).
    signed = [a for a in packet.attestations if a.is_signed()]
    if len(signed) < _MIN_SIGNED_ATTESTATIONS:
        missing.append(f"signed_external_attestations({len(signed)}/{_MIN_SIGNED_ATTESTATIONS})")
    families = {a.evidence_family for a in signed if a.evidence_family}
    if len(families) < _MIN_INDEPENDENT_FAMILIES:
        missing.append(f"independent_evidence_families({len(families)}/{_MIN_INDEPENDENT_FAMILIES})")
        reasons.append("correlated oracles collapse into one family: no decorrelation lift")

    # 4. One Wire external countersignature (lens 3): a party != issuer. Internal never approves.
    if not packet.external_countersignature or packet.countersigner_id == packet.issuer_id \
            or not packet.countersigner_id:
        missing.append("external_countersignature(One_Wire)")
        reasons.append("self-observation may block/downgrade, never approve public truth")

    # 5. Signed receipt envelope (lens 6): unsigned/mutable receipts are forgeable.
    if not packet.receipt_envelope_signed:
        missing.append("signed_receipt_envelope(ReceiptEnvelope_v0)")

    if missing:
        return MintDecision(status="BLOCKED", missing=tuple(missing), reasons=tuple(reasons))
    return MintDecision(status="ALLOW", missing=(), reasons=("all external evidence present",))


def bayou_as_is_packet() -> ClaimPacket:
    """The current staged Bayou pilot, honestly: a real internal ledger and a 4-of-5
    oracle quorum whose verdicts are SYNTHETIC, with no community custody record and no
    external countersignature. The review's prediction: it must FAIL the gate."""
    return ClaimPacket(
        claim_id="bayou-lafourche-mangroves-staged",
        bounded_welfare_assurance_score=6118.0,   # the proxy number; gated, not minted
        mrv_integrity={"baseline": 304.0},        # baseline only; leakage/permanence/biodiv/dep-matrix absent
        custody=None,                              # no community custodian countersignature
        attestations=(                             # synthetic pilot verdicts are NOT signed-external
            SignedOracleAttestation(signer_id="", signature="", evidence_family="satellite", is_external=False),
            SignedOracleAttestation(signer_id="", signature="", evidence_family="community", is_external=False),
        ),
        external_countersignature="",
        issuer_id="dharma_swarm",
        countersigner_id="dharma_swarm",           # issuer == countersigner: self-grading
        receipt_envelope_signed=False,             # EvidenceReceipt is unsigned today
    )


if __name__ == "__main__":  # pragma: no cover
    decision = evaluate(bayou_as_is_packet())
    print(decision.loud())
    for r in decision.reasons:
        print(f"  · {r}")
    print("\n(the gate is working iff this says BLOCKED — minting requires the world, not us)")
