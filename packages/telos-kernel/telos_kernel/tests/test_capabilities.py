"""Macaroon-shaped capability tokens: mint, attenuate (monotone), verify."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from telos_kernel.capabilities import (
    Caveat,
    Macaroon,
    add_first_party_caveat,
    mint,
    new_root_key,
    verify,
)


class TestMint:
    def test_mint_signature_is_hex_and_deterministic(self):
        key = b"\x00" * 32
        m1 = mint(key, "id-1", "telos-kernel/gate")
        m2 = mint(key, "id-1", "telos-kernel/gate")
        assert m1.signature == m2.signature
        assert len(m1.signature) == 64
        assert all(c in "0123456789abcdef" for c in m1.signature)

    def test_different_keys_produce_different_signatures(self):
        m1 = mint(b"\x00" * 32, "id", "loc")
        m2 = mint(b"\x01" * 32, "id", "loc")
        assert m1.signature != m2.signature

    def test_mint_rejects_short_key(self):
        import pytest
        with pytest.raises(Exception):
            mint(b"short", "id", "loc")


class TestVerifyPositive:
    def test_unattenuated_verifies(self):
        key = new_root_key()
        m = mint(key, "id", "telos-kernel/gate")
        assert verify(m, key, context={})

    def test_gate_caveat_matches(self):
        key = new_root_key()
        m = mint(key, "id", "telos-kernel/gate")
        m = add_first_party_caveat(m, "gate == U5_merkle")
        assert verify(m, key, {"gate": "U5_merkle"})

    def test_tier_caveat_matches(self):
        key = new_root_key()
        m = mint(key, "id", "telos-kernel/gate")
        m = add_first_party_caveat(m, "tier <= B")
        assert verify(m, key, {"tier": "A"})
        assert verify(m, key, {"tier": "B"})


class TestVerifyNegative:
    def test_wrong_key_fails(self):
        key = new_root_key()
        wrong = new_root_key()
        m = mint(key, "id", "loc")
        assert not verify(m, wrong, {})

    def test_missing_context_field_fails(self):
        key = new_root_key()
        m = mint(key, "id", "loc")
        m = add_first_party_caveat(m, "gate == U5_merkle")
        assert not verify(m, key, {})  # no 'gate' in context

    def test_tier_over_ceiling_fails(self):
        key = new_root_key()
        m = mint(key, "id", "loc")
        m = add_first_party_caveat(m, "tier <= A")
        assert not verify(m, key, {"tier": "B"})

    def test_unknown_predicate_fails_closed(self):
        key = new_root_key()
        m = mint(key, "id", "loc")
        m = add_first_party_caveat(m, "made_up_predicate == true")
        assert not verify(m, key, {"made_up_predicate": "true"})

    def test_signature_mutation_fails(self):
        key = new_root_key()
        m = mint(key, "id", "loc")
        bad = Macaroon(m.identifier, m.location, m.caveats,
                       signature="00" * 32)
        assert not verify(bad, key, {})


class TestAttenuationMonotonicity:
    """The core macaroon property: attenuation is monotone — appending caveats
    can only *narrow* authority, never widen it."""

    def test_narrowed_token_still_verifies_narrower_context(self):
        key = new_root_key()
        m = mint(key, "id", "loc")
        m1 = add_first_party_caveat(m, "gate == U5_merkle")
        m2 = add_first_party_caveat(m1, "tier <= A")
        assert verify(m2, key, {"gate": "U5_merkle", "tier": "A"})

    def test_widening_context_after_attenuation_still_needs_caveat(self):
        key = new_root_key()
        m = mint(key, "id", "loc")
        m1 = add_first_party_caveat(m, "gate == U5_merkle")
        # With the caveat present, wrong gate must fail.
        assert not verify(m1, key, {"gate": "U0_anekanta"})

    @given(st.lists(
        st.sampled_from([
            "gate == U5_merkle",
            "gate == U0_anekanta",
            "tier <= A",
            "tier <= B",
            "tier <= C",
        ]),
        min_size=0, max_size=5,
    ))
    @settings(max_examples=30, deadline=None)
    def test_attenuation_signature_chain_property(self, caveats):
        key = new_root_key()
        m = mint(key, "id", "loc")
        for c in caveats:
            m = add_first_party_caveat(m, c)
        # A macaroon with these caveats and a matching context must verify.
        assert verify(m, key, {"gate": "U5_merkle", "tier": "A"}) == all(
            c in {"gate == U5_merkle", "tier <= A", "tier <= B", "tier <= C"}
            for c in caveats
        )
