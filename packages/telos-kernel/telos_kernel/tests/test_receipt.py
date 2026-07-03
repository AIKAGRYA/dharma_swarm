"""Signed Leaf: schema, JCS-canonical signing bytes, Ed25519 sign/verify."""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from telos_kernel.receipt import (
    Leaf,
    SignatureStatus,
    Tier,
    Verdict,
    new_proposal_id,
    now_iso_utc,
)


def _valid_leaf(**overrides) -> Leaf:
    base = dict(
        gate="U5_merkle",
        tier=Tier.A,
        proposal_id=new_proposal_id(),
        prev_merkle_root="0" * 64,
        measure={"chain_len": 0},
        threshold={"any_break_triggers_quarantine": True},
        verdict=Verdict.ALLOW,
        signature_status=SignatureStatus.ABSENT,
        capability_signature="",
        signer_key_id="",
        timestamp=now_iso_utc(),
    )
    base.update(overrides)
    return Leaf(**base)


class TestLeafSchema:
    def test_valid_leaf_ok(self):
        leaf = _valid_leaf()
        assert leaf.schema_version == "v3.0"

    def test_frozen(self):
        leaf = _valid_leaf()
        with pytest.raises(ValidationError):
            leaf.gate = "boot"  # type: ignore[misc]

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            Leaf(
                gate="U5_merkle",
                tier=Tier.A,
                proposal_id=new_proposal_id(),
                prev_merkle_root="0" * 64,
                measure={},
                threshold={},
                verdict=Verdict.ALLOW,
                signature_status=SignatureStatus.ABSENT,
                capability_signature="",
                signer_key_id="",
                timestamp=now_iso_utc(),
                extra_field="nope",  # type: ignore[call-arg]
            )

    def test_invalid_gate_name(self):
        with pytest.raises(ValidationError):
            _valid_leaf(gate="U99_bogus")

    def test_boot_gate_allowed(self):
        leaf = _valid_leaf(gate="boot")
        assert leaf.gate == "boot"

    def test_invalid_prev_root(self):
        with pytest.raises(ValidationError):
            _valid_leaf(prev_merkle_root="not-hex")

    def test_naive_timestamp_rejected(self):
        with pytest.raises(ValidationError):
            _valid_leaf(timestamp="2026-07-03T18:40:00")  # no tz


class TestLeafSigning:
    def test_absent_leaf_returns_unchanged_on_sign(self):
        sk = Ed25519PrivateKey.generate()
        leaf = _valid_leaf()
        signed = leaf.sign(sk, key_id="signer_1")
        # ABSENT signature status must not be signed.
        assert signed.capability_signature == ""

    def test_real_leaf_signs_and_verifies(self):
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key()
        leaf = _valid_leaf(signature_status=SignatureStatus.REAL)
        signed = leaf.sign(sk, key_id="signer_1")
        assert signed.capability_signature != ""
        assert signed.verify(pk)

    def test_tamper_breaks_signature(self):
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key()
        leaf = _valid_leaf(signature_status=SignatureStatus.REAL)
        signed = leaf.sign(sk, key_id="signer_1")
        # Tamper: replace measure. Since Leaf is frozen we must construct a new one.
        tampered = signed.model_copy(update={"measure": {"chain_len": 999}})
        assert not tampered.verify(pk)

    def test_signing_bytes_omit_signature_field(self):
        leaf = _valid_leaf(signature_status=SignatureStatus.REAL)
        # signing_bytes must equal signing_bytes of the same leaf with a
        # different capability_signature — the field is blanked before signing.
        alt = leaf.model_copy(update={"capability_signature": "ffff"})
        assert leaf.signing_bytes() == alt.signing_bytes()
