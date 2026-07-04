"""Tests for the fail-closed WelfareTonMintGate (SEED-1 credit-side).

The contract: the gate mints nothing from internal artifacts, fails closed on missing
external evidence, and never approves from self-observation alone. Built against the
8-lens adversarial review (2026-06-28).
"""

from __future__ import annotations

from dharma_swarm.gaia_sis_mint_gate import (
    ClaimPacket,
    CommunityCustodyRecord,
    SignedOracleAttestation,
    bayou_as_is_packet,
    evaluate,
)


def test_bayou_as_is_fails_closed_loudly():
    # The review's prediction: today's staged Bayou packet MUST fail.
    d = evaluate(bayou_as_is_packet())
    assert d.status == "BLOCKED"
    miss = " ".join(d.missing)
    assert "community_custody_countersignature" in miss      # lens 7
    assert "external_countersignature" in miss               # lens 3 / One Wire
    assert "signed_receipt_envelope" in miss                 # lens 6
    assert "mrv_integrity" in miss                           # lens 2
    assert "BLOCKED" in d.loud()


def test_empty_packet_fails_closed():
    d = evaluate(ClaimPacket(claim_id="empty"))
    assert d.status == "BLOCKED"
    assert len(d.missing) >= 4


def _full_external_packet() -> ClaimPacket:
    """A packet with every external-evidence family present (the only mint path)."""
    return ClaimPacket(
        claim_id="fully-evidenced",
        bounded_welfare_assurance_score=100.0,
        mrv_integrity={
            "baseline": 304.0, "leakage": 0.1, "permanence": 0.9,
            "biodiversity_protocol": "wallacea-basket", "oracle_dependency_matrix": {"ok": True},
        },
        custody=CommunityCustodyRecord(
            custodian_id="bayou-reciprocity-coop", custodian_countersignature="sig-c",
            consent_scope="full", withdrawal_supported=True, benefit_sharing_terms="60pct",
        ),
        attestations=(
            SignedOracleAttestation("auditor-1", "sig-1", "human_auditor", True),
            SignedOracleAttestation("sat-vendor", "sig-2", "satellite", True),
            SignedOracleAttestation("ground-team", "sig-3", "ground_truth", True),
        ),
        external_countersignature="sig-ext",
        issuer_id="dharma_swarm",
        countersigner_id="independent-registry",   # != issuer
        receipt_envelope_signed=True,
    )


def test_internal_only_never_approves():
    # Self-observation may block/downgrade, never approve (lens 3): strip the external
    # countersignature from an otherwise-complete packet -> still BLOCKED.
    p = _full_external_packet()
    internal = ClaimPacket(
        claim_id=p.claim_id,
        bounded_welfare_assurance_score=p.bounded_welfare_assurance_score,
        mrv_integrity=p.mrv_integrity,
        custody=p.custody,
        attestations=p.attestations,
        external_countersignature="",
        issuer_id="dharma_swarm",
        countersigner_id="dharma_swarm",            # self == self
        receipt_envelope_signed=p.receipt_envelope_signed,
    )
    d = evaluate(internal)
    assert d.status == "BLOCKED"
    assert any("external_countersignature" in m for m in d.missing)


def test_correlated_oracles_collapse_to_one_family_blocks():
    # Three signed attestations but all the same evidence family -> no decorrelation lift.
    p = _full_external_packet()
    same_family = ClaimPacket(
        claim_id=p.claim_id, bounded_welfare_assurance_score=p.bounded_welfare_assurance_score,
        mrv_integrity=p.mrv_integrity, custody=p.custody,
        attestations=(
            SignedOracleAttestation("a", "s1", "satellite", True),
            SignedOracleAttestation("b", "s2", "satellite", True),
            SignedOracleAttestation("c", "s3", "satellite", True),
        ),
        external_countersignature=p.external_countersignature,
        issuer_id=p.issuer_id, countersigner_id=p.countersigner_id,
        receipt_envelope_signed=p.receipt_envelope_signed,
    )
    d = evaluate(same_family)
    assert d.status == "BLOCKED"
    assert any("independent_evidence_families" in m for m in d.missing)


def test_zero_valued_mrv_evidence_is_present_not_missing():
    # Review fix: a legitimate measured zero (leakage: 0.0) is evidence, not absence.
    # The gate must fail closed on ABSENT or None only, never on numeric zero.
    p = _full_external_packet()
    zero_leakage = ClaimPacket(
        claim_id=p.claim_id, bounded_welfare_assurance_score=p.bounded_welfare_assurance_score,
        mrv_integrity={**p.mrv_integrity, "leakage": 0.0},
        custody=p.custody, attestations=p.attestations,
        external_countersignature=p.external_countersignature,
        issuer_id=p.issuer_id, countersigner_id=p.countersigner_id,
        receipt_envelope_signed=p.receipt_envelope_signed,
    )
    d = evaluate(zero_leakage)
    assert d.status == "ALLOW"
    assert not any("mrv_integrity" in m for m in d.missing)


def test_none_valued_mrv_evidence_still_blocks():
    # None means the measurement was never made -> still missing, still BLOCKED.
    p = _full_external_packet()
    none_leakage = ClaimPacket(
        claim_id=p.claim_id, bounded_welfare_assurance_score=p.bounded_welfare_assurance_score,
        mrv_integrity={**p.mrv_integrity, "leakage": None},
        custody=p.custody, attestations=p.attestations,
        external_countersignature=p.external_countersignature,
        issuer_id=p.issuer_id, countersigner_id=p.countersigner_id,
        receipt_envelope_signed=p.receipt_envelope_signed,
    )
    d = evaluate(none_leakage)
    assert d.status == "BLOCKED"
    assert any("mrv_integrity[leakage]" in m for m in d.missing)


def test_only_full_external_evidence_allows():
    d = evaluate(_full_external_packet())
    assert d.status == "ALLOW"
    # ...but the gate never claims crypto it doesn't have.
    assert "NOT yet cryptographically verified" in d.crypto_note


def test_gate_imports_no_owned_surface():
    import dharma_swarm.gaia_sis_mint_gate as mod
    src = open(mod.__file__).read()
    for owned in ("from dharma_swarm.spine", "import gaia_ledger",
                  "from dharma_swarm.gaia_ledger", "import telos_gates"):
        assert owned not in src
