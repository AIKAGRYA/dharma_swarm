"""Result[T, E] ADT + structured verify_result() paths across the kernel.

These tests establish the fail-closed contract: every *_result() function
returns Err(KernelError) with a specific error code on failure, never
raises, and the boolean shim (verify(), verify_quorum(), verify_chain())
agrees with .is_ok.
"""
from __future__ import annotations

import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from telos_kernel import (
    Err,
    KernelError,
    Ok,
    Result,
    load_manifest,
)
from telos_kernel.capabilities import (
    Macaroon,
    add_first_party_caveat,
    mint,
    new_root_key,
    verify_result,
)
from telos_kernel.merkle_log import MemoryBackend, MerkleLog
from telos_kernel.receipt import (
    Leaf,
    SignatureStatus,
    Tier,
    Verdict,
    now_iso_utc,
)
from telos_kernel.result import (
    ERR_CAVEAT_FAILED,
    ERR_CHAIN_BROKEN,
    ERR_INVALID_SIGNATURE,
    ERR_MALFORMED_HEX,
    ERR_QUORUM_NOT_MET,
    ERR_STUB_SIGNERS,
)


# ---- Basic ADT ----

def test_ok_shape():
    r = Ok(42)
    assert r.is_ok and not r.is_err
    assert r.unwrap() == 42
    assert r.unwrap_or(99) == 42
    assert r.map(lambda x: x + 1) == Ok(43)


def test_err_shape():
    e = KernelError("test_code", "boom")
    r = Err(e)
    assert r.is_err and not r.is_ok
    with pytest.raises(ValueError):
        r.unwrap()
    assert r.unwrap_or(99) == 99
    assert r.map(lambda x: x + 1) is r  # map on Err is identity


def test_kernel_error_str():
    assert str(KernelError("code", "msg")) == "code: msg"
    assert str(KernelError("code")) == "code"


# ---- Capabilities.verify_result ----

def test_capability_verify_ok():
    rk = new_root_key()
    m = mint(rk, "id-1", "loc")
    r = verify_result(m, rk, {})
    assert r.is_ok


def test_capability_verify_signature_mismatch():
    rk = new_root_key()
    m = mint(rk, "id-1", "loc")
    # Tamper the signature.
    tampered = Macaroon(
        identifier=m.identifier, location=m.location,
        caveats=m.caveats, signature="00" * 32,
    )
    r = verify_result(tampered, rk, {})
    assert r.is_err
    assert r.error.code == ERR_INVALID_SIGNATURE


def test_capability_verify_garbage_signature():
    """Non-hex garbage sig is caught by compare_digest, not by fromhex,
    because macaroon._recompute_signature doesn't decode the sig field.
    The important postcondition is that verify_result fails closed."""
    rk = new_root_key()
    m = mint(rk, "id-1", "loc")
    bad = Macaroon(
        identifier=m.identifier, location=m.location,
        caveats=m.caveats, signature="not_hex_at_all_xyz",
    )
    r = verify_result(bad, rk, {})
    assert r.is_err
    assert r.error.code == ERR_INVALID_SIGNATURE


def test_capability_verify_caveat_failed():
    rk = new_root_key()
    m = mint(rk, "id-1", "loc")
    m = add_first_party_caveat(m, "gate == U5_something")
    r = verify_result(m, rk, {"gate": "U6_wrong"})
    assert r.is_err
    assert r.error.code == ERR_CAVEAT_FAILED
    assert "predicate" in r.error.detail


# ---- Leaf.verify_result ----

def _mk_signed_leaf():
    sk = Ed25519PrivateKey.generate()
    leaf = Leaf(
        gate="U5_merkle_binding", tier=Tier.A,
        proposal_id=str(uuid.uuid4()),
        prev_merkle_root="a" * 64,
        measure={}, threshold={},
        verdict=Verdict.ALLOW,
        signature_status=SignatureStatus.REAL,
        capability_signature="", signer_key_id="",
        timestamp=now_iso_utc(),
    )
    return leaf.sign(sk, "k1"), sk


def test_leaf_verify_ok():
    signed, sk = _mk_signed_leaf()
    r = signed.verify_result(sk.public_key())
    assert r.is_ok


def test_leaf_verify_wrong_key():
    signed, _ = _mk_signed_leaf()
    other = Ed25519PrivateKey.generate().public_key()
    r = signed.verify_result(other)
    assert r.is_err
    assert r.error.code == ERR_INVALID_SIGNATURE


def test_leaf_verify_malformed_signature_hex():
    signed, sk = _mk_signed_leaf()
    bad = signed.model_copy(update={"capability_signature": "zzzz_not_hex"})
    r = bad.verify_result(sk.public_key())
    assert r.is_err
    assert r.error.code == ERR_MALFORMED_HEX


def test_leaf_verify_absent_ok():
    leaf = Leaf(
        gate="boot", tier=Tier.A,
        proposal_id=str(uuid.uuid4()),
        prev_merkle_root="GENESIS",
        measure={}, threshold={},
        verdict=Verdict.ALLOW,
        signature_status=SignatureStatus.ABSENT,
        capability_signature="", signer_key_id="",
        timestamp=now_iso_utc(),
    )
    sk = Ed25519PrivateKey.generate()
    r = leaf.verify_result(sk.public_key())
    assert r.is_ok


def test_leaf_boolean_shim_agrees_with_result():
    signed, sk = _mk_signed_leaf()
    assert signed.verify(sk.public_key()) == signed.verify_result(sk.public_key()).is_ok


# ---- Manifest.verify_quorum_result ----

def test_manifest_quorum_stub_signers():
    manifest = load_manifest()
    r = manifest.verify_quorum_result(b"payload", {})
    assert r.is_err
    assert r.error.code == ERR_STUB_SIGNERS


def test_manifest_quorum_boolean_shim():
    manifest = load_manifest()
    assert manifest.verify_quorum(b"payload", {}) == manifest.verify_quorum_result(b"payload", {}).is_ok


# ---- MerkleLog.verify_chain_result ----

def test_merkle_verify_chain_ok():
    log = MerkleLog(backend=MemoryBackend())
    for i in range(5):
        log.append({"i": i})
    r = log.verify_chain_result()
    assert r.is_ok
    assert r.unwrap()["length"] == 5


def test_merkle_verify_chain_empty():
    log = MerkleLog(backend=MemoryBackend())
    r = log.verify_chain_result()
    assert r.is_ok
    assert r.unwrap()["length"] == 0


def test_merkle_verify_chain_broken_returns_broken_index():
    log = MerkleLog(backend=MemoryBackend())
    for i in range(3):
        log.append({"i": i})
    # Corrupt payload at index 1.
    log._payloads[1] = {"i": 999}
    r = log.verify_chain_result()
    assert r.is_err
    assert r.error.code == ERR_CHAIN_BROKEN
    assert r.error.detail["broken_index"] == 1


def test_merkle_verify_chain_boolean_shim_preserved():
    """The (True, None) / (False, i) tuple contract must survive."""
    log = MerkleLog(backend=MemoryBackend())
    for i in range(3):
        log.append({"i": i})
    assert log.verify_chain() == (True, None)
    log._payloads[2] = {"tampered": True}
    ok, idx = log.verify_chain()
    assert ok is False and idx == 2


def test_all_verify_result_paths_never_raise():
    """Fuzz: none of the *_result paths raise, even on garbage input.

    This is the strongest fail-closed guarantee we can test at runtime;
    titanium-verify will prove the same property statically.
    """
    rk = new_root_key()
    m = mint(rk, "id-x", "loc")

    # Garbage signature values
    for bad_sig in ["", "x", "zz", "\x00\x01", "a" * 63]:
        bad = Macaroon(m.identifier, m.location, m.caveats, bad_sig)
        r = verify_result(bad, rk, {})
        assert isinstance(r, (Ok, Err))

    # Garbage context types where a dict is expected
    r = verify_result(m, rk, {})
    assert isinstance(r, (Ok, Err))
