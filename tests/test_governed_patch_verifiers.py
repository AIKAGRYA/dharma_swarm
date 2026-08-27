from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.governed_patch_evidence import NativePatchBindings
from scripts.runtime.governed_patch_verifier_common import (
    VerifierCustodyError,
    external_write_path,
    load_role_signing_principal,
    process_separation_blockers,
    record_verifier_identity,
    sign_closed_payload,
    verifier_identity,
    verify_signed_process_receipt,
    write_signed_process_receipt,
)


DELIVERY_ID = "d" * 24


def _bindings() -> NativePatchBindings:
    return NativePatchBindings(
        mission_id="mission-1",
        task_id="task-1",
        attempt_id="packet-1",
        lease_id=DELIVERY_ID,
        packet_id="packet-1",
        correlation_id="a2a_send:codex_composer:packet-1",
        delivery_id=DELIVERY_ID,
        proposal_id="proposal-1",
        base_sha="a" * 40,
        executor_agent_uid="codex_composer",
        executor_run_id="executor-run-1",
        executor_process_boot_id="boot-executor-1",
    )


def _write_key(path: Path, key: Ed25519PrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    path.chmod(0o600)


def _principal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    path = tmp_path / "foundry.key"
    _write_key(path, Ed25519PrivateKey.generate())
    monkeypatch.setenv("DHARMA_FOUNDRY_VERIFIER_KEY_FILE", str(path))
    monkeypatch.delenv("DHARMA_VIBE_VERIFIER_KEY_FILE", raising=False)
    return load_role_signing_principal(
        required_env="DHARMA_FOUNDRY_VERIFIER_KEY_FILE",
        forbidden_env="DHARMA_VIBE_VERIFIER_KEY_FILE",
    )


def test_role_key_is_owner_only_raw_ed25519_and_other_role_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    principal = _principal(monkeypatch, tmp_path)

    assert len(principal.public_key) == 64
    assert principal.key_inode > 0

    monkeypatch.setenv("DHARMA_VIBE_VERIFIER_KEY_FILE", "/not/allowed")
    with pytest.raises(VerifierCustodyError, match="must be absent"):
        load_role_signing_principal(
            required_env="DHARMA_FOUNDRY_VERIFIER_KEY_FILE",
            forbidden_env="DHARMA_VIBE_VERIFIER_KEY_FILE",
        )


@pytest.mark.parametrize("unsafe", ["mode", "symlink", "relative"])
def test_role_key_unsafe_file_forms_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    unsafe: str,
) -> None:
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "key"
    _write_key(path, key)
    supplied = path
    if unsafe == "mode":
        path.chmod(0o644)
    elif unsafe == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        supplied = link
    else:
        supplied = Path("relative-key")
    monkeypatch.setenv("ROLE_KEY", str(supplied))
    monkeypatch.delenv("OTHER_KEY", raising=False)

    with pytest.raises(VerifierCustodyError):
        load_role_signing_principal(
            required_env="ROLE_KEY",
            forbidden_env="OTHER_KEY",
        )


def test_signed_payload_is_self_hashed_and_signature_verifies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    principal = _principal(monkeypatch, tmp_path)
    signed = sign_closed_payload(
        {"schema": "test.v1", "effect_performed": False},
        principal=principal,
        key_id="foundry-test",
    )
    signature = signed.pop("signature")
    message = json.dumps(
        signed,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    Ed25519PublicKey.from_public_bytes(bytes.fromhex(principal.public_key)).verify(
        bytes.fromhex(signature["signature"]),
        message,
    )
    assert len(signed["payload_sha256"]) == 64


def test_verifier_identity_is_durable_child_and_receipt_never_authorizes_effect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    principal = _principal(monkeypatch, tmp_path)
    bindings = _bindings()
    identity = verifier_identity(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        correlation_id=bindings.correlation_id,
        proposal_id=bindings.proposal_id,
        candidate_digest="sha256:" + "a" * 64,
        executor_agent_uid=bindings.executor_agent_uid,
        executor_run_id=bindings.executor_run_id,
        verifier_agent_uid="foundry-independent-verifier",
        verifier_run_id="foundry-run-1",
        role="foundry",
    )
    runtime_db = tmp_path / "runtime.db"

    recorded = record_verifier_identity(
        identity,
        runtime_db=runtime_db,
        role="foundry",
        public_key=principal.public_key,
    )
    receipt_path, _signed = write_signed_process_receipt(
        receipt_root=tmp_path / "receipts",
        role="foundry",
        identity=recorded,
        candidate_digest="sha256:" + "a" * 64,
        diff_sha256="b" * 64,
        outcome="foundry_inconclusive",
        reasons=("trial_ledger_unavailable",),
        evidence={
            "isolation": "blocked",
            "native_bindings": bindings.to_dict(),
        },
        principal=principal,
    )

    restarted = RuntimeStateStore(runtime_db, include_memory_plane=False)
    assert restarted.get_execution_identity_sync(identity.run_id) == recorded
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["identity"]["parent_run_id"] == "executor-run-1"
    assert receipt["repository_effect_authorized"] is False
    assert receipt["repository_effect_performed"] is False
    assert receipt["evidence_storage_effects_performed"] is True
    assert receipt["key_custody"]["exclusive_private_key_custody_proven"] is False
    assert receipt["signature"]["public_key"] == principal.public_key
    assert verify_signed_process_receipt(
        receipt,
        trusted_public_key=principal.public_key,
        expected_role="foundry",
        expected_identity=recorded,
        expected_bindings=bindings,
        expected_candidate_digest="sha256:" + "a" * 64,
        expected_diff_sha256="b" * 64,
        expected_outcome="foundry_inconclusive",
    )
    receipt["repository_effect_performed"] = True
    assert not verify_signed_process_receipt(
        receipt,
        trusted_public_key=principal.public_key,
        expected_role="foundry",
        expected_identity=recorded,
        expected_bindings=bindings,
        expected_candidate_digest="sha256:" + "a" * 64,
        expected_diff_sha256="b" * 64,
        expected_outcome="foundry_inconclusive",
    )


def test_process_receipt_verification_requires_exact_native_and_child_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    principal = _principal(monkeypatch, tmp_path)
    bindings = _bindings()
    identity = verifier_identity(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        correlation_id=bindings.correlation_id,
        proposal_id=bindings.proposal_id,
        candidate_digest="sha256:" + "a" * 64,
        executor_agent_uid=bindings.executor_agent_uid,
        executor_run_id=bindings.executor_run_id,
        verifier_agent_uid="foundry-independent-verifier",
        verifier_run_id="foundry-run-exact",
        role="foundry",
    )
    path, _signed = write_signed_process_receipt(
        receipt_root=tmp_path / "receipts-exact",
        role="foundry",
        identity=identity,
        candidate_digest="sha256:" + "a" * 64,
        diff_sha256="b" * 64,
        outcome="foundry_inconclusive",
        reasons=("trial_ledger_unavailable",),
        evidence={"native_bindings": bindings.to_dict()},
        principal=principal,
    )
    receipt = json.loads(path.read_text(encoding="utf-8"))

    assert not verify_signed_process_receipt(
        receipt,
        trusted_public_key=principal.public_key,
        expected_role="foundry",
        expected_identity=identity.with_updates(run_id="different-run"),
        expected_bindings=bindings,
        expected_candidate_digest="sha256:" + "a" * 64,
        expected_diff_sha256="b" * 64,
        expected_outcome="foundry_inconclusive",
    )
    assert not verify_signed_process_receipt(
        receipt,
        trusted_public_key=principal.public_key,
        expected_role="foundry",
        expected_identity=identity,
        expected_bindings=NativePatchBindings(
            **{**bindings.to_dict(), "mission_id": "different-mission"}
        ),
        expected_candidate_digest="sha256:" + "a" * 64,
        expected_diff_sha256="b" * 64,
        expected_outcome="foundry_inconclusive",
    )


def test_external_write_paths_exclude_release_bundle_and_symlink(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    bundle = tmp_path / "bundle"
    release.mkdir()
    bundle.mkdir()
    external = tmp_path / "runtime" / "state.db"

    assert external_write_path(
        external,
        release_root=release,
        candidate_bundle_root=bundle,
        field="runtime DB",
    ) == external
    for unsafe in (release / "receipt.json", bundle / "receipt.json"):
        with pytest.raises(VerifierCustodyError, match="outside"):
            external_write_path(
                unsafe,
                release_root=release,
                candidate_bundle_root=bundle,
                field="receipt root",
            )
    target = tmp_path / "target"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(VerifierCustodyError, match="symlink"):
        external_write_path(
            link,
            release_root=release,
            candidate_bundle_root=bundle,
            field="runtime DB",
        )


def test_verifier_run_cannot_alias_executor_run() -> None:
    with pytest.raises(VerifierCustodyError, match="must differ"):
        verifier_identity(
            mission_id="mission-1",
            task_id="task-1",
            correlation_id="correlation-1",
            proposal_id="proposal-1",
            candidate_digest="sha256:" + "a" * 64,
            executor_agent_uid="codex_composer",
            executor_run_id="same-run",
            verifier_agent_uid="verifier",
            verifier_run_id="same-run",
            role="foundry",
        )


@pytest.mark.parametrize(
    ("agent_uid", "run_id"),
    [
        (" codex_composer ", "foundry-run-1"),
        ("foundry-verifier", " run-with-space "),
        ("x" * 257, "foundry-run-1"),
        ("codex_composer", "foundry-run-1"),
    ],
)
def test_verifier_identity_rejects_normalization_and_size_bypasses(
    agent_uid: str,
    run_id: str,
) -> None:
    with pytest.raises(VerifierCustodyError, match="bounded exact token|must differ"):
        verifier_identity(
            mission_id="mission-1",
            task_id="task-1",
            correlation_id="correlation-1",
            proposal_id="proposal-1",
            candidate_digest="sha256:" + "a" * 64,
            executor_agent_uid="codex_composer",
            executor_run_id="executor-run-1",
            verifier_agent_uid=agent_uid,
            verifier_run_id=run_id,
            role="foundry",
        )


def test_key_material_never_appears_in_signed_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    principal = _principal(monkeypatch, tmp_path)
    secret = principal.signer.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    signed = sign_closed_payload(
        {"schema": "test.v1"},
        principal=principal,
        key_id="test",
    )

    assert secret.hex() not in json.dumps(signed, sort_keys=True)
    assert os.environ["DHARMA_FOUNDRY_VERIFIER_KEY_FILE"] not in json.dumps(signed)


def test_distinct_process_observations_still_do_not_overclaim_key_custody() -> None:
    base = {
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    foundry = {
        **base,
        "role": "foundry",
        "process": {"pid": 101, "boot_id": "boot-foundry"},
        "signature": {"public_key": "a" * 64},
        "key_custody": {
            "key_device": 1,
            "key_inode": 11,
            "exclusive_private_key_custody_proven": False,
        },
    }
    vibe = {
        **base,
        "role": "vibe_halt",
        "process": {"pid": 202, "boot_id": "boot-vibe"},
        "signature": {"public_key": "b" * 64},
        "key_custody": {
            "key_device": 1,
            "key_inode": 22,
            "exclusive_private_key_custody_proven": False,
        },
    }

    assert process_separation_blockers(foundry, vibe) == (
        "exclusive_private_key_custody_unproven",
    )

    foundry["key_custody"]["exclusive_private_key_custody_proven"] = True
    vibe["key_custody"]["exclusive_private_key_custody_proven"] = True
    assert process_separation_blockers(foundry, vibe) == (
        "exclusive_private_key_custody_unproven",
    )

    vibe["process"] = dict(foundry["process"])
    vibe["signature"] = dict(foundry["signature"])
    vibe["key_custody"] = dict(foundry["key_custody"])
    assert process_separation_blockers(foundry, vibe) == (
        "verifier_pid_not_separated",
        "verifier_boot_not_separated",
        "verifier_signer_not_separated",
        "verifier_private_key_inode_not_separated",
        "exclusive_private_key_custody_unproven",
    )
