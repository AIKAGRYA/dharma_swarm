"""Shared custody primitives for the two governed-patch verifier processes.

This module records an admitted process environment, an owner-only key file,
and a declared child identity in a caller-selected RuntimeState store. It does
not prove the store is canonical, that the parent was observed, or hostile-user
key isolation; it does not mint a promotion warrant and cannot authorize a
repository effect.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.foundry.patches import write_immutable_beneath
from dharma_swarm.governed_patch_evidence import NativePatchBindings
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity, process_boot_id

MAX_KEY_BYTES = 32
SIGNED_PROCESS_RECEIPT_SCHEMA = "dharma.governed_patch.signed_process_receipt.v1"
_SIGNED_RECEIPT_KEYS = frozenset(
    {
        "schema",
        "role",
        "identity",
        "candidate_digest",
        "diff_sha256",
        "outcome",
        "reasons",
        "evidence",
        "process",
        "key_custody",
        "repository_effect_authorized",
        "repository_effect_performed",
        "evidence_storage_effects_performed",
        "payload_sha256",
        "signature",
    }
)
_SIGNATURE_KEYS = frozenset({"scheme", "key_id", "public_key", "signature"})
_VERIFIER_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,255}$")


class VerifierCustodyError(RuntimeError):
    """A verifier process cannot establish its narrow signing boundary."""


@dataclass(frozen=True, slots=True)
class SigningPrincipal:
    signer: Ed25519PrivateKey
    public_key: str
    key_path: str
    key_device: int
    key_inode: int


def load_role_signing_principal(
    *,
    required_env: str,
    forbidden_env: str,
) -> SigningPrincipal:
    """Load one raw Ed25519 seed from an owner-only, no-follow file.

    Environment separation is challengeable evidence, not proof that another
    same-user process cannot discover and open the path independently.
    """

    raw_path = os.environ.get(required_env, "").strip()
    if not raw_path:
        raise VerifierCustodyError(f"{required_env} is required")
    if os.environ.get(forbidden_env, "").strip():
        raise VerifierCustodyError(
            f"{forbidden_env} must be absent from this verifier process"
        )
    path = Path(raw_path)
    if not path.is_absolute():
        raise VerifierCustodyError(f"{required_env} must be an absolute path")
    try:
        lexical = path.lstat()
    except OSError as exc:
        raise VerifierCustodyError("verifier signing key is unavailable") from exc
    if stat.S_ISLNK(lexical.st_mode):
        raise VerifierCustodyError("verifier signing key must not be a symlink")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise VerifierCustodyError("verifier signing key cannot be opened") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.getuid()
            or metadata.st_size != MAX_KEY_BYTES
        ):
            raise VerifierCustodyError(
                "verifier signing key must be an owner-only 32-byte regular file"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            seed = handle.read(MAX_KEY_BYTES + 1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(seed) != MAX_KEY_BYTES:
        raise VerifierCustodyError("verifier signing key has invalid length")
    try:
        key = Ed25519PrivateKey.from_private_bytes(seed)
    except ValueError as exc:
        raise VerifierCustodyError("verifier signing key is malformed") from exc
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return SigningPrincipal(
        signer=key,
        public_key=public_key,
        key_path=str(path),
        key_device=metadata.st_dev,
        key_inode=metadata.st_ino,
    )


def sign_closed_payload(
    payload: Mapping[str, Any],
    *,
    principal: SigningPrincipal,
    key_id: str,
    signature_field: str = "signature",
) -> dict[str, Any]:
    """Self-hash and sign one finite JSON mapping using the Vibe convention."""

    if signature_field in payload or "payload_sha256" in payload:
        raise ValueError("unsigned payload must not contain signature/hash fields")
    body = dict(payload)
    # Round-trip with allow_nan=False rejects non-finite and non-JSON values.
    encoded_body = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if not isinstance(json.loads(encoded_body), dict):
        raise ValueError("signed payload must be a JSON object")
    signed = {**body, "payload_sha256": canonical_sha256(body)}
    message = json.dumps(
        signed,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    signed[signature_field] = {
        "scheme": "ed25519",
        "key_id": key_id,
        "public_key": principal.public_key,
        "signature": principal.signer.sign(message).hex(),
    }
    return signed


def verify_signed_process_receipt(
    receipt: Mapping[str, Any],
    *,
    trusted_public_key: str,
    expected_role: str,
    expected_identity: ExecutionIdentity,
    expected_bindings: NativePatchBindings,
    expected_candidate_digest: str,
    expected_diff_sha256: str,
    expected_outcome: str,
) -> bool:
    """Verify one closed, non-authorizing process receipt and exact binding."""

    try:
        data = dict(receipt)
        if frozenset(data) != _SIGNED_RECEIPT_KEYS:
            return False
        signature = data.get("signature")
        if not isinstance(signature, Mapping) or frozenset(signature) != _SIGNATURE_KEYS:
            return False
        if (
            data.get("schema") != SIGNED_PROCESS_RECEIPT_SCHEMA
            or data.get("role") != expected_role
            or data.get("identity") != expected_identity.to_dict()
            or data.get("candidate_digest") != expected_candidate_digest
            or data.get("diff_sha256") != expected_diff_sha256
            or data.get("outcome") != expected_outcome
            or data.get("repository_effect_authorized") is not False
            or data.get("repository_effect_performed") is not False
            or data.get("evidence_storage_effects_performed") is not True
            or signature.get("scheme") != "ed25519"
            or signature.get("key_id") != f"governed-patch-{expected_role}"
            or signature.get("public_key") != trusted_public_key
            or len(str(signature.get("signature") or "")) != 128
        ):
            return False
        unsigned = {key: value for key, value in data.items() if key != "signature"}
        body = {
            key: value for key, value in unsigned.items() if key != "payload_sha256"
        }
        if unsigned.get("payload_sha256") != canonical_sha256(body):
            return False
        message = json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_public_key)).verify(
            bytes.fromhex(str(signature["signature"])),
            message,
        )
        identity = data.get("identity")
        process = data.get("process")
        custody = data.get("key_custody")
        evidence = data.get("evidence")
        reasons = data.get("reasons")
        return bool(
            isinstance(identity, Mapping)
            and identity == expected_identity.to_dict()
            and identity.get("task_id") == expected_bindings.task_id
            and identity.get("correlation_id") == expected_bindings.correlation_id
            and identity.get("proposal_id") == expected_bindings.proposal_id
            and identity.get("parent_run_id") == expected_bindings.executor_run_id
            and identity.get("artifact_id") == expected_candidate_digest
            and identity.get("agent_id") != expected_bindings.executor_agent_uid
            and isinstance(process, Mapping)
            and frozenset(process) == {"pid", "boot_id"}
            and type(process.get("pid")) is int
            and process["pid"] > 0
            and isinstance(process.get("boot_id"), str)
            and bool(process["boot_id"])
            and process.get("boot_id")
            == expected_identity.metadata.get("process_boot_id")
            and isinstance(custody, Mapping)
            and frozenset(custody)
            == {
                "owner_only_regular_file",
                "key_device",
                "key_inode",
                "exclusive_private_key_custody_proven",
            }
            and custody.get("owner_only_regular_file") is True
            and type(custody.get("key_device")) is int
            and type(custody.get("key_inode")) is int
            and custody.get("exclusive_private_key_custody_proven") is False
            and isinstance(reasons, list)
            and all(
                type(reason) is str and 0 < len(reason) <= 512
                for reason in reasons
            )
            and len(set(reasons)) == len(reasons)
            and isinstance(evidence, Mapping)
            and evidence.get("native_bindings") == expected_bindings.to_dict()
        )
    except (KeyError, TypeError, ValueError):
        return False
    except Exception:
        return False


def verifier_identity(
    *,
    mission_id: str,
    task_id: str,
    correlation_id: str,
    proposal_id: str,
    candidate_digest: str,
    executor_agent_uid: str,
    executor_run_id: str,
    verifier_agent_uid: str,
    verifier_run_id: str,
    role: str,
) -> ExecutionIdentity:
    """Construct one exact declared-child identity for a verifier role."""

    for value, field_name in (
        (verifier_agent_uid, "verifier agent"),
        (verifier_run_id, "verifier run"),
        (executor_agent_uid, "executor agent"),
        (executor_run_id, "executor run"),
    ):
        if type(value) is not str or _VERIFIER_TOKEN_RE.fullmatch(value) is None:
            raise VerifierCustodyError(f"{field_name} must be a bounded exact token")
    if verifier_agent_uid == executor_agent_uid:
        raise VerifierCustodyError("verifier agent must differ from executor agent")
    if verifier_run_id == executor_run_id:
        raise VerifierCustodyError("verifier run must differ from executor run")
    if role not in {"foundry", "vibe_halt"}:
        raise VerifierCustodyError("unsupported verifier role")
    return ExecutionIdentity.new(
        task_id=task_id,
        trace_id=f"trace:{verifier_run_id}",
        correlation_id=correlation_id,
        run_id=verifier_run_id,
        claim_id=f"claim:{verifier_run_id}",
        idempotency_key=(
            f"idem:governed_patch:{role}:{proposal_id}:{candidate_digest}"
        ),
        causation_id=candidate_digest,
        parent_run_id=executor_run_id,
        agent_id=verifier_agent_uid,
        session_id=f"mission:{mission_id}",
        artifact_id=candidate_digest,
        proposal_id=proposal_id,
        metadata={
            "authority_semantics": "evidence_only",
            "repository_effect_performed": False,
            "evidence_storage_effects_performed": True,
            "repository_effect_authorized": False,
            "role": role,
            "process_boot_id": process_boot_id(),
        },
    )


def record_verifier_identity(
    identity: ExecutionIdentity,
    *,
    runtime_db: Path,
    role: str,
    public_key: str,
) -> ExecutionIdentity:
    """Record one exact identity in the caller-selected RuntimeState store."""

    store = RuntimeStateStore(runtime_db, include_memory_plane=False)
    exact_identity = identity.with_updates(
        metadata={
            "signer_public_key": public_key,
            "process_boot_id": process_boot_id(),
        }
    )
    return store.record_execution_identity_exact_sync(
        exact_identity,
        source=f"governed_patch_{role}_verifier",
    )


def external_write_path(
    raw: str | Path,
    *,
    release_root: Path,
    candidate_bundle_root: Path,
    field: str,
) -> Path:
    """Resolve one writable path while excluding both immutable input roots."""

    supplied = Path(raw)
    if not supplied.is_absolute():
        raise VerifierCustodyError(f"{field} must be an absolute external path")
    if supplied.is_symlink():
        raise VerifierCustodyError(f"{field} must not be a symlink")
    try:
        resolved = supplied.resolve(strict=False)
        protected = (
            Path(release_root).resolve(strict=True),
            Path(candidate_bundle_root).resolve(strict=True),
        )
    except OSError as exc:
        raise VerifierCustodyError(f"{field} cannot be resolved safely") from exc
    if any(resolved == root or resolved.is_relative_to(root) for root in protected):
        raise VerifierCustodyError(
            f"{field} must be outside the release and candidate bundle roots"
        )
    return resolved


def write_signed_process_receipt(
    *,
    receipt_root: Path,
    role: str,
    identity: ExecutionIdentity,
    candidate_digest: str,
    diff_sha256: str,
    outcome: str,
    reasons: tuple[str, ...],
    evidence: Mapping[str, Any],
    principal: SigningPrincipal,
) -> tuple[Path, dict[str, Any]]:
    """Persist a content-addressed, non-authorizing process receipt."""

    body = {
        "schema": SIGNED_PROCESS_RECEIPT_SCHEMA,
        "role": role,
        "identity": identity.to_dict(),
        "candidate_digest": candidate_digest,
        "diff_sha256": diff_sha256,
        "outcome": outcome,
        "reasons": list(reasons),
        "evidence": dict(evidence),
        "process": {
            "pid": os.getpid(),
            "boot_id": process_boot_id(),
        },
        "key_custody": {
            "owner_only_regular_file": True,
            "key_device": principal.key_device,
            "key_inode": principal.key_inode,
            "exclusive_private_key_custody_proven": False,
        },
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    signed = sign_closed_payload(
        body,
        principal=principal,
        key_id=f"governed-patch-{role}",
    )
    encoded = (
        json.dumps(signed, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    digest = canonical_sha256(signed)
    path = write_immutable_beneath(
        receipt_root,
        f"{role}/{digest}.json",
        encoded,
    )
    return path, signed


def process_separation_blockers(
    foundry_receipt: Mapping[str, Any],
    vibe_receipt: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return why two process receipts cannot prove independent custody.

    Distinct observed PIDs, boot IDs, public keys, and key inodes establish a
    useful refusal canary. They still cannot prove that same-user processes
    were unable to open each other's key files, so the custody blocker remains
    until composition supplies a stronger OS/key-service boundary.
    """

    blockers: list[str] = []
    if foundry_receipt.get("role") != "foundry":
        blockers.append("foundry_role_mismatch")
    if vibe_receipt.get("role") != "vibe_halt":
        blockers.append("vibe_role_mismatch")
    foundry_process = foundry_receipt.get("process")
    vibe_process = vibe_receipt.get("process")
    if not isinstance(foundry_process, Mapping) or not isinstance(
        vibe_process, Mapping
    ):
        blockers.append("missing_process_observation")
    else:
        if foundry_process.get("pid") == vibe_process.get("pid"):
            blockers.append("verifier_pid_not_separated")
        if foundry_process.get("boot_id") == vibe_process.get("boot_id"):
            blockers.append("verifier_boot_not_separated")
    foundry_signature = foundry_receipt.get("signature")
    vibe_signature = vibe_receipt.get("signature")
    if not isinstance(foundry_signature, Mapping) or not isinstance(
        vibe_signature, Mapping
    ):
        blockers.append("missing_verifier_signature")
    elif foundry_signature.get("public_key") == vibe_signature.get("public_key"):
        blockers.append("verifier_signer_not_separated")
    foundry_custody = foundry_receipt.get("key_custody")
    vibe_custody = vibe_receipt.get("key_custody")
    if not isinstance(foundry_custody, Mapping) or not isinstance(
        vibe_custody, Mapping
    ):
        blockers.append("missing_key_custody_observation")
    else:
        foundry_inode = (
            foundry_custody.get("key_device"),
            foundry_custody.get("key_inode"),
        )
        vibe_inode = (
            vibe_custody.get("key_device"),
            vibe_custody.get("key_inode"),
        )
        if foundry_inode == vibe_inode:
            blockers.append("verifier_private_key_inode_not_separated")
    # These same-user process observations cannot establish exclusive private-key
    # custody. A self-authored receipt boolean is evidence under review, never a
    # proof that the other process was unable to open the signing key.
    blockers.append("exclusive_private_key_custody_unproven")
    if (
        foundry_receipt.get("repository_effect_authorized") is not False
        or vibe_receipt.get("repository_effect_authorized") is not False
        or foundry_receipt.get("repository_effect_performed") is not False
        or vibe_receipt.get("repository_effect_performed") is not False
        or foundry_receipt.get("evidence_storage_effects_performed") is not True
        or vibe_receipt.get("evidence_storage_effects_performed") is not True
    ):
        blockers.append("verifier_receipt_claims_effect_authority")
    return tuple(dict.fromkeys(blockers))


__all__ = [
    "SIGNED_PROCESS_RECEIPT_SCHEMA",
    "SigningPrincipal",
    "VerifierCustodyError",
    "external_write_path",
    "load_role_signing_principal",
    "process_separation_blockers",
    "record_verifier_identity",
    "sign_closed_payload",
    "verifier_identity",
    "verify_signed_process_receipt",
    "write_signed_process_receipt",
]
