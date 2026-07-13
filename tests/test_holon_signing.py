"""Tests for holon_signing — signed, scoped, TTL-bound capability leases."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm import holon_signing as hs


def _keypair(tmp: Path, name: str = "k") -> tuple[Path, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.generate()
    pem = tmp / f"{name}.pem"
    pem.write_bytes(priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pub = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return pem, pub


def test_sign_verify_roundtrip(tmp_path):
    pem, pub = _keypair(tmp_path)
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    assert lease["signer_pubkey"] == pub
    ok, why = hs.verify_lease(lease, allowed_signers={pub})
    assert ok, why


def test_tamper_rejected(tmp_path):
    pem, pub = _keypair(tmp_path)
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    lease["scope"] = [hs.READ_ONLY, hs.GIT_PUSH]  # widen scope after signing
    ok, why = hs.verify_lease(lease, allowed_signers={pub})
    assert not ok and "signature" in why


def test_expired_lease_fails(tmp_path):
    pem, pub = _keypair(tmp_path)
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY], ttl_s=1,
                           signer_key_pem=pem, issuer="seat")
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    ok, why = hs.verify_lease(lease, allowed_signers={pub}, now=future)
    assert not ok and why == "expired"


def test_wrong_signer_rejected(tmp_path):
    pem, _pub = _keypair(tmp_path, "a")
    _pem2, other = _keypair(tmp_path, "b")
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    ok, why = hs.verify_lease(lease, allowed_signers={other})
    assert not ok and "not authorized" in why


def test_empty_allowed_set_is_fail_closed(tmp_path):
    pem, _pub = _keypair(tmp_path)
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    ok, _ = hs.verify_lease(lease, allowed_signers=set())
    assert not ok  # empty set != None; no signer is a member


def test_none_allowed_skips_membership_but_verifies_signature(tmp_path):
    pem, _pub = _keypair(tmp_path)
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    assert hs.verify_lease(lease, allowed_signers=None)[0]
    lease["signature"] = "00" * 64  # corrupt signature
    assert not hs.verify_lease(lease, allowed_signers=None)[0]


def test_issue_rejects_unknown_action_class(tmp_path):
    pem, _pub = _keypair(tmp_path)
    with pytest.raises(hs.LeaseError):
        hs.issue_lease(holon="seat", scope=["delete_everything"], ttl_s=60,
                       signer_key_pem=pem, issuer="seat")


def test_write_load_roundtrip(tmp_path):
    pem, _pub = _keypair(tmp_path)
    root = tmp_path / "agents"
    lease = hs.issue_lease(holon="seat", scope=[hs.REPLY_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    path = hs.write_lease(lease, agents_root=root)
    assert path.exists() and path.parent == root / "seat" / "leases"
    loaded = hs.load_leases("seat", agents_root=root)
    assert len(loaded) == 1 and loaded[0]["lease_id"] == lease["lease_id"]
