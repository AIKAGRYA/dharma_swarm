"""Manifest loading, quorum verification, stub-signer refusal."""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from telos_kernel.manifest import (
    EnforcementStatus,
    Manifest,
    Signer,
    load_manifest,
)


class TestManifestLoad:
    def test_default_manifest_loads(self, loaded_manifest):
        m = loaded_manifest
        assert m.schema_version == "v3.0"
        # All 12 invariants declared.
        ids = {i.id for i in m.invariants}
        assert ids == {f"U{k}" for k in range(12)}

    def test_only_u5_enforced_in_phase_0(self, loaded_manifest):
        assert loaded_manifest.enforced_ids() == {"U5"}

    def test_stub_signers_flagged(self, loaded_manifest):
        assert loaded_manifest.has_stub_signers() is True

    def test_all_invariants_have_citations(self, loaded_manifest):
        for inv in loaded_manifest.invariants:
            assert len(inv.citations) >= 1, f"{inv.id} missing citations"

    def test_all_invariants_have_falsification_test(self, loaded_manifest):
        for inv in loaded_manifest.invariants:
            assert inv.falsification_test, f"{inv.id} missing falsification_test"

    def test_content_hash_stable(self, loaded_manifest):
        h1 = loaded_manifest.content_hash()
        h2 = loaded_manifest.content_hash()
        assert h1 == h2
        assert len(h1) == 64


class TestSignerValidation:
    def test_stub_pk_accepted(self):
        s = Signer(key_id="k", public_key_hex="STUB", role="test", stub=True)
        assert s.public_key_hex == "STUB"

    def test_real_pk_lowercased(self):
        pk_hex = "A" * 64
        s = Signer(key_id="k", public_key_hex=pk_hex, role="test")
        assert s.public_key_hex == "a" * 64

    def test_bad_length_rejected(self):
        with pytest.raises(ValidationError):
            Signer(key_id="k", public_key_hex="deadbeef", role="test")

    def test_bad_chars_rejected(self):
        with pytest.raises(ValidationError):
            Signer(key_id="k", public_key_hex="Z" * 64, role="test")


class TestQuorumVerification:
    """K-of-N Ed25519 quorum. Phase 0 lands the verifier; Phase 1 enforces
    it on manifest edits."""

    def _build_manifest_with_real_signers(self, n=5, k=3):
        sks = [Ed25519PrivateKey.generate() for _ in range(n)]
        pks_hex = [sk.public_key().public_bytes_raw().hex() for sk in sks]
        return (sks, {
            "schema_version": "v3.0",
            "version": "test",
            "invariants": [{
                "id": "U5",
                "name": "kernel_tamper_evidence_hash_chain",
                "predicate": "test",
                "measure": "test",
                "threshold": {"any_break_triggers_quarantine": True},
                "receipt_type": "U5_merkle",
                "falsification_test": "test.py",
                "tier": "A",
                "citations": ["[RFC 9162](https://datatracker.ietf.org/doc/html/rfc9162)"],
                "enforcement_status": "enforced",
            }],
            "signer_set": {
                "k": k,
                "n": n,
                "signers": [
                    {"key_id": f"signer_{i+1}", "public_key_hex": pks_hex[i],
                     "role": "test", "stub": False}
                    for i in range(n)
                ],
            },
        })

    def test_stub_manifest_never_reaches_quorum(self, loaded_manifest):
        # Even with 5 fake signatures, stub-signer manifest fails closed.
        result = loaded_manifest.verify_quorum(
            b"payload",
            {f"signer_{i}": b"\x00" * 64 for i in range(1, 6)},
        )
        assert result is False

    def test_k_valid_signatures_pass(self):
        sks, raw = self._build_manifest_with_real_signers(n=5, k=3)
        m = Manifest.model_validate(raw)
        payload = b"important manifest edit"
        # Sign with 3 signers.
        sigs = {
            f"signer_{i+1}": sks[i].sign(payload)
            for i in range(3)
        }
        assert m.verify_quorum(payload, sigs) is True

    def test_k_minus_one_valid_fails(self):
        sks, raw = self._build_manifest_with_real_signers(n=5, k=3)
        m = Manifest.model_validate(raw)
        payload = b"important manifest edit"
        # Only 2 valid signatures.
        sigs = {
            f"signer_{i+1}": sks[i].sign(payload)
            for i in range(2)
        }
        assert m.verify_quorum(payload, sigs) is False

    def test_wrong_signer_signature_ignored(self):
        sks, raw = self._build_manifest_with_real_signers(n=5, k=3)
        m = Manifest.model_validate(raw)
        payload = b"important manifest edit"
        # 2 valid + 1 with wrong key.
        wrong = Ed25519PrivateKey.generate()
        sigs = {
            "signer_1": sks[0].sign(payload),
            "signer_2": sks[1].sign(payload),
            "signer_3": wrong.sign(payload),  # bad key
        }
        assert m.verify_quorum(payload, sigs) is False

    def test_replay_over_different_payload_fails(self):
        sks, raw = self._build_manifest_with_real_signers(n=5, k=3)
        m = Manifest.model_validate(raw)
        payload = b"payload A"
        sigs = {f"signer_{i+1}": sks[i].sign(payload) for i in range(3)}
        # Try to verify against a different payload — must fail.
        assert m.verify_quorum(b"payload B", sigs) is False
