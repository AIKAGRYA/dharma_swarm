"""Injected cryptographic supervisor custody for governed effects."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.mission_control_effect_warrant import (
    CanaryPatchBinding,
    OwnerStoreBinding,
    SupervisorEffectAuthority,
)
from dharma_swarm.spine.identity import process_boot_id

_MAX_AUTHORITY_SECONDS = 30


def _interpreter_sha256() -> str:
    digest = hashlib.sha256()
    with Path(sys.executable).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def supervisor_authority_payload(authority: SupervisorEffectAuthority) -> dict[str, Any]:
    excluded = {"signed_payload_sha256", "signature", "_ownership_token", "_seal"}
    result = {
        name: getattr(authority, name)
        for name in SupervisorEffectAuthority.__dataclass_fields__
        if name not in excluded
    }
    result["issued_at"] = authority.issued_at.isoformat()
    result["expires_at"] = authority.expires_at.isoformat()
    return result


def supervisor_authority_sha256(authority: SupervisorEffectAuthority) -> str:
    return canonical_sha256({
        **supervisor_authority_payload(authority),
        "signed_payload_sha256": authority.signed_payload_sha256,
        "signature": authority.signature,
    })


class SupervisorAuthorityIssuer:
    """A pinned Ed25519 signer plus a closure-owned custody sentinel."""

    def __init__(
        self, signer: Ed25519PrivateKey, *, key_id: str,
        trusted_public_keys: frozenset[str], supervisor_id: str,
    ) -> None:
        if not isinstance(signer, Ed25519PrivateKey) or not key_id or not supervisor_id:
            raise ValueError("trusted supervisor signer and key id are required")
        public_key = signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        if public_key not in trusted_public_keys:
            raise ValueError("supervisor signer is outside the pinned trust roots")
        self._signer = signer
        self._public_key = public_key
        self._key_id = key_id
        self._supervisor_id = supervisor_id
        self._creator_pid = os.getpid()
        self._sentinel = object()
        self._issued: dict[int, tuple[SupervisorEffectAuthority, str]] = {}

    def issue(
        self, binding: CanaryPatchBinding, owner_stores: OwnerStoreBinding, *,
        ttl_seconds: int = 15,
    ) -> SupervisorEffectAuthority:
        if os.getpid() != self._creator_pid:
            raise ValueError("supervisor issuer cannot cross a process boundary")
        if type(ttl_seconds) is not int or not 0 < ttl_seconds <= _MAX_AUTHORITY_SECONDS:
            raise ValueError("supervisor authority lifetime is not bounded")
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        for tracked_id, (tracked, _) in list(self._issued.items()):
            if tracked.expires_at <= issued_at:
                del self._issued[tracked_id]
        os_uid = os.getuid()
        scratch = binding.scratch
        if os_uid not in {
            scratch.approved_root_uid, scratch.root_uid,
            scratch.marker_uid, scratch.target_uid,
        } or len({
            scratch.approved_root_uid, scratch.root_uid,
            scratch.marker_uid, scratch.target_uid,
        }) != 1:
            raise ValueError("supervisor UID does not own the bound scratch custody")
        values = dict(
            binding_sha256=binding.binding_sha256, effect_key=binding.effect_key,
            owner_stores_sha256=canonical_sha256(owner_stores.to_dict()),
            scratch_identity=scratch.scratch_identity,
            approved_scratch_root=scratch.approved_scratch_root,
            git_executable_path=scratch.git_executable_path,
            git_executable_sha256=scratch.git_executable_sha256,
            git_executable_device=scratch.git_executable_device,
            git_executable_inode=scratch.git_executable_inode,
            git_common_dir_path=scratch.git_common_dir_path,
            git_common_dir_device=scratch.git_common_dir_device,
            git_common_dir_inode=scratch.git_common_dir_inode,
            git_worktree_registration_sha256=scratch.git_worktree_registration_sha256,
            canonical_repo_identity=scratch.canonical_repo_identity,
            supervisor_id=self._supervisor_id, process_boot_id=process_boot_id(),
            os_uid=os_uid, interpreter_sha256=_interpreter_sha256(),
            argv_sha256=canonical_sha256(sys.argv), authority_public_key=self._public_key,
            authority_key_id=self._key_id, issued_at=issued_at,
            expires_at=expires_at,
            custody_basis=(
                "host_pinned_ed25519_same_uid_and_fork_private_key_"
                "exclusivity_unproven"
            ),
        )
        provisional = SupervisorEffectAuthority(
            **values, signed_payload_sha256="", signature=""
        )
        body = supervisor_authority_payload(provisional)
        payload_sha = canonical_sha256(body)
        message = json.dumps(
            {**body, "signed_payload_sha256": payload_sha}, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        result = SupervisorEffectAuthority(
            **values, signed_payload_sha256=payload_sha,
            signature=self._signer.sign(message).hex(),
        )
        object.__setattr__(result, "_ownership_token", self._sentinel)
        self._issued[id(result)] = (result, supervisor_authority_sha256(result))
        return result

    def validates(
        self, authority: SupervisorEffectAuthority, *, binding: CanaryPatchBinding,
        owner_stores: OwnerStoreBinding,
    ) -> bool:
        current = datetime.now(timezone.utc)
        try:
            body = supervisor_authority_payload(authority)
            signed = {**body, "signed_payload_sha256": authority.signed_payload_sha256}
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(self._public_key)).verify(
                bytes.fromhex(authority.signature),
                json.dumps(
                    signed, sort_keys=True, separators=(",", ":"), allow_nan=False,
                ).encode("utf-8"),
            )
            scratch = binding.scratch
            registered = self._issued.get(id(authority))
            return bool(
                os.getpid() == self._creator_pid
                and type(authority) is SupervisorEffectAuthority
                and authority._ownership_token is self._sentinel  # noqa: SLF001
                and registered is not None and registered[0] is authority
                and registered[1] == supervisor_authority_sha256(authority)
                and authority.authority_public_key == self._public_key
                and authority.authority_key_id == self._key_id
                and authority.binding_sha256 == binding.binding_sha256
                and authority.effect_key == binding.effect_key
                and authority.owner_stores_sha256
                == canonical_sha256(owner_stores.to_dict())
                and authority.scratch_identity == scratch.scratch_identity
                and authority.os_uid == scratch.target_uid == scratch.marker_uid
                and authority.signed_payload_sha256 == canonical_sha256(body)
                and authority.issued_at <= current < authority.expires_at
                and (authority.expires_at - authority.issued_at).total_seconds()
                <= _MAX_AUTHORITY_SECONDS
            )
        except Exception:
            return False


__all__ = [
    "SupervisorAuthorityIssuer", "supervisor_authority_payload",
    "supervisor_authority_sha256",
]
