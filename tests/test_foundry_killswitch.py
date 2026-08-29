"""Tests for foundry kill-switch wiring."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.foundry import killswitch
from dharma_swarm.holon_killswitch import request_kill


def test_not_stopped_by_default(tmp_path):
    agents = tmp_path / "agents"
    state = tmp_path / "state"
    assert killswitch.is_stopped(agents_root=agents, state_root=state) is False
    killswitch.check(agents_root=agents, state_root=state)  # no raise


def test_stop_file_stops(tmp_path):
    agents = tmp_path / "agents"
    state = tmp_path / "state"
    state.mkdir()
    (state / "STOP").write_text("operator halt")
    assert killswitch.is_stopped(agents_root=agents, state_root=state)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(agents_root=agents, state_root=state)


def test_holon_kill_stops(tmp_path):
    agents = tmp_path / "agents"
    state = tmp_path / "state"
    request_kill(killswitch.FOUNDRY_HOLON, reason="guardian tripped", agents_root=agents)
    assert killswitch.is_stopped(agents_root=agents, state_root=state)
    reason = killswitch.stop_reason(agents_root=agents, state_root=state)
    assert "guardian tripped" in reason


def test_terminal_kill_is_persistent_and_first_cause_wins(tmp_path):
    path = killswitch.persist_terminal_kill(
        tmp_path,
        category="replication_failure",
        reason="seed replay mismatch",
        evidence={"target_id": "t"},
    )
    first = path.read_bytes()
    killswitch.persist_terminal_kill(
        tmp_path,
        category="later_failure",
        reason="must not overwrite",
    )
    assert path.read_bytes() == first
    assert killswitch.has_terminal_kill(tmp_path)
    assert killswitch.is_stopped(state_root=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["category"] == "replication_failure"
    assert "seed replay mismatch" in killswitch.stop_reason(state_root=tmp_path)


def test_deleting_terminal_and_halt_projections_cannot_resume(tmp_path):
    killswitch.persist_terminal_kill(
        tmp_path, category="oracle_failure", reason="immutable terminal cause"
    )
    assert list((tmp_path / "control_receipts").glob("halt__*.json"))
    (tmp_path / "KILL.json").unlink()
    (tmp_path / "HALT.json").unlink()

    assert killswitch.is_stopped(state_root=tmp_path)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    assert (tmp_path / "HALT.json").exists()
    assert "immutable terminal cause" in killswitch.stop_reason(state_root=tmp_path)


def test_deleting_stop_and_halt_projections_cannot_resume(tmp_path):
    (tmp_path / "STOP").write_text("operator halt", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    (tmp_path / "STOP").unlink()
    (tmp_path / "HALT.json").unlink()

    assert killswitch.is_stopped(state_root=tmp_path)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    assert (tmp_path / "HALT.json").exists()


def _signed_resume(state, private_key, *, nonce="n-1"):
    from cryptography.hazmat.primitives import serialization

    halt = killswitch.read_halt(state)
    now = datetime.now(timezone.utc)
    body = {
        "schema_version": "foundry_resume_authority.v1",
        "authority_id": "operator-test",
        "lease_id": "lease-test",
        "scope": "foundry.resume",
        "halt_digest": halt["halt_digest"],
        "issued_at": (now - timedelta(seconds=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "nonce": nonce,
    }
    message = json.dumps(
        body, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    return {
        **body,
        "signature": {
            "scheme": "ed25519",
            "public_key": public,
            "signature": private_key.sign(message).hex(),
        },
    }, public


def _resign(envelope, private_key, **updates):
    body = {key: value for key, value in envelope.items() if key != "signature"}
    body.update(updates)
    signature = private_key.sign(json.dumps(
        body, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hex()
    return {
        **body,
        "signature": {
            **envelope["signature"],
            "signature": signature,
        },
    }


def test_resume_requires_trusted_halt_bound_signature_and_writes_receipt(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    (tmp_path / "STOP").write_text("halt", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    key = Ed25519PrivateKey.generate()
    envelope, public = _signed_resume(tmp_path, key)
    receipt = killswitch.resume_with_authority(
        tmp_path, envelope, trusted_public_keys=[public]
    )
    assert receipt.exists()
    payload = json.loads(receipt.read_text())
    assert payload["halt"]["source"] == "STOP"
    assert payload["authority_envelope"]["authority_id"] == "operator-test"
    assert not killswitch.is_stopped(state_root=tmp_path)
    assert (tmp_path / "control_history").is_dir()


def test_untrusted_or_wrong_halt_resume_fails_closed(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    (tmp_path / "STOP").write_text("halt", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    key = Ed25519PrivateKey.generate()
    envelope, public = _signed_resume(tmp_path, key)
    envelope["halt_digest"] = "sha256:" + "0" * 64
    with pytest.raises(killswitch.ResumeAuthorityError, match="not bound"):
        killswitch.resume_with_authority(
            tmp_path, envelope, trusted_public_keys=[public]
        )
    assert killswitch.is_stopped(state_root=tmp_path)


@pytest.mark.parametrize(
    "updates",
    [
        {"nonce": "../escape"},
        {"authority_id": "bad/operator"},
        {"lease_id": "../../lease"},
    ],
)
def test_resume_rejects_unsafe_path_identifiers_before_receipt_write(
    tmp_path, updates
):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    (tmp_path / "STOP").write_text("halt", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    key = Ed25519PrivateKey.generate()
    envelope, public = _signed_resume(tmp_path, key)
    malicious = _resign(envelope, key, **updates)
    with pytest.raises(killswitch.ResumeAuthorityError, match="invalid"):
        killswitch.resume_with_authority(
            tmp_path, malicious, trusted_public_keys=[public]
        )
    assert not list((tmp_path / "control_receipts").glob("resume__*.json"))
    assert killswitch.is_stopped(state_root=tmp_path)


@pytest.mark.parametrize("timing", ["future", "expired", "too_long"])
def test_resume_enforces_issued_expiry_and_tight_lease_lifetime(tmp_path, timing):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    (tmp_path / "STOP").write_text("halt", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    key = Ed25519PrivateKey.generate()
    envelope, public = _signed_resume(tmp_path, key)
    now = datetime.now(timezone.utc)
    if timing == "future":
        updates = {
            "issued_at": (now + timedelta(seconds=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        }
    elif timing == "expired":
        updates = {
            "issued_at": (now - timedelta(minutes=4)).isoformat(),
            "expires_at": (now - timedelta(seconds=1)).isoformat(),
        }
    else:
        updates = {
            "issued_at": (now - timedelta(seconds=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=16)).isoformat(),
        }
    invalid = _resign(envelope, key, **updates)
    with pytest.raises(killswitch.ResumeAuthorityError, match="not currently valid"):
        killswitch.resume_with_authority(
            tmp_path, invalid, trusted_public_keys=[public], now=now
        )


def test_resume_nonce_cannot_be_replayed_for_a_later_halt(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    (tmp_path / "STOP").write_text("first", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    first, public = _signed_resume(tmp_path, key, nonce="one-use")
    killswitch.resume_with_authority(
        tmp_path, first, trusted_public_keys=[public]
    )

    (tmp_path / "STOP").write_text("second", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
    second, _ = _signed_resume(tmp_path, key, nonce="one-use")
    with pytest.raises(killswitch.ResumeAuthorityError, match="already consumed"):
        killswitch.resume_with_authority(
            tmp_path, second, trusted_public_keys=[public]
        )


def test_terminal_kill_rejects_nonfinite_evidence_without_persisting(tmp_path):
    with pytest.raises(ValueError, match="non-canonical"):
        killswitch.persist_terminal_kill(
            tmp_path,
            category="oracle_failure",
            reason="bad numeric evidence",
            evidence={"score": float("nan")},
        )
    assert not (tmp_path / "KILL.json").exists()


def test_existing_openssh_key_can_authorize_exact_halt_bound_resume(tmp_path):
    key = tmp_path / "operator_ed25519"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
    )
    state = tmp_path / "state"
    state.mkdir()
    (state / "STOP").write_text("halt", encoding="utf-8")
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=state)
    now = datetime.now(timezone.utc)
    body = {
        "schema_version": "foundry_resume_authority.v1",
        "authority_id": "existing-ssh-operator",
        "lease_id": "ssh-lease",
        "scope": "foundry.resume",
        "halt_digest": killswitch.read_halt(state)["halt_digest"],
        "issued_at": (now - timedelta(seconds=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "nonce": "ssh-nonce",
    }
    body_path = tmp_path / "resume-body.json"
    body_path.write_bytes(json.dumps(
        body, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
    subprocess.run(
        [
            "ssh-keygen", "-Y", "sign", "-f", str(key),
            "-n", "foundry-resume", str(body_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    envelope = {
        **body,
        "signature": {
            "scheme": "openssh-sshsig",
            "namespace": "foundry-resume",
            "signature": (tmp_path / "resume-body.json.sig").read_text(encoding="utf-8"),
        },
    }
    receipt = killswitch.resume_with_authority(
        state,
        envelope,
        trusted_openssh_public_keys=[key.with_suffix(".pub").read_text(encoding="utf-8")],
    )
    assert receipt.exists()
    assert not killswitch.is_stopped(state_root=state)
