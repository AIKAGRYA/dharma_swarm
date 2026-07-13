"""Tests for holon_pep — the Policy Enforcement Point over capability leases."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm import holon_signing as hs
from dharma_swarm import holon_pep as pep


def _seat_with_key(root: Path, uid: str) -> tuple[Path, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    home = root / uid
    (home / "keys").mkdir(parents=True)
    priv = Ed25519PrivateKey.generate()
    pem = home / "keys" / "ed25519_private.pem"
    pem.write_bytes(priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pem.chmod(0o600)
    pub = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    (home / "identity.json").write_text(json.dumps({"agent_uid": uid, "public_key": pub}))
    return pem, pub


@pytest.fixture(autouse=True)
def _clear_operator_signers():
    before = pep.operator_signers()
    pep._OPERATOR_SIGNERS.clear()
    yield
    pep._OPERATOR_SIGNERS.clear()
    pep._OPERATOR_SIGNERS.update(before)


def test_grant_when_lease_covers_action(tmp_path):
    root = tmp_path / "agents"
    pem, _pub = _seat_with_key(root, "seat")
    lease = hs.issue_lease(holon="seat", scope=[hs.READ_ONLY, hs.REPLY_ONLY], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    hs.write_lease(lease, agents_root=root)
    grant = pep.enforce_lease("seat", hs.REPLY_ONLY, agents_root=root)
    assert grant["decision"] == "granted"


def test_deny_writes_refusal_receipt(tmp_path):
    root = tmp_path / "agents"
    _seat_with_key(root, "seat")  # no lease issued
    with pytest.raises(pep.LeaseDenied):
        pep.enforce_lease("seat", hs.READ_ONLY, agents_root=root)
    refusals = list((root / "seat" / "leases" / "refusals").glob("*.json"))
    assert len(refusals) == 1
    rec = json.loads(refusals[0].read_text())
    assert rec["decision"] == "refused" and rec["action_class"] == hs.READ_ONLY


def test_operator_only_fail_closed_even_with_seat_lease(tmp_path):
    root = tmp_path / "agents"
    pem, _pub = _seat_with_key(root, "seat")
    # a seat can list git_push in scope, but it cannot self-authorize it
    lease = hs.issue_lease(holon="seat", scope=[hs.GIT_PUSH], ttl_s=3600,
                           signer_key_pem=pem, issuer="seat")
    hs.write_lease(lease, agents_root=root)
    assert not pep.check_lease("seat", hs.GIT_PUSH, agents_root=root)[0]


def test_operator_signed_lease_authorizes_operator_only(tmp_path):
    root = tmp_path / "agents"
    _seat_with_key(root, "seat")
    op_pem, op_pub = _seat_with_key(root, "_operator")  # stand-in operator key
    pep.register_operator_signer(op_pub)
    lease = hs.issue_lease(holon="seat", scope=[hs.GIT_PUSH], ttl_s=3600,
                           signer_key_pem=op_pem, issuer="operator")
    hs.write_lease(lease, agents_root=root)
    ok, _lid, _checked = pep.check_lease("seat", hs.GIT_PUSH, agents_root=root)
    assert ok


def test_unknown_action_class_denied(tmp_path):
    root = tmp_path / "agents"
    _seat_with_key(root, "seat")
    ok, reason, _ = pep.check_lease("seat", "nope", agents_root=root)
    assert not ok and "unknown action class" in reason
