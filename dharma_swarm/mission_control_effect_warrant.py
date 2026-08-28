"""Nominal authority types for one governed canary repository effect.

Signed Foundry/Vibe canary observations remain non-authorizing and explicitly
do not prove exclusive private-key custody.  Only their sealed conjunction,
an injected non-serializable supervisor custody capability, and the canonical
RuntimeState fence can mint an :class:`EffectWarrant`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypeAlias

from dharma_swarm.mission_control_effect_records import (
    CanaryVerifierBinding,
    EffectRefusal,
    OwnerStoreBinding,
    ScratchTargetBinding,
)

from dharma_swarm.runtime_state_effect_fence import EFFECT_KEY_PREFIX

CANARY_BINDING_SCHEMA = "dharma.mission_control.canary_patch_binding.v1"
FOUNDRY_CANARY_SCHEMA = "dharma.governed_patch.foundry_canary_evidence.v1"
INDEPENDENT_PATCH_VERIFICATION_SCHEMA = (
    "dharma.mission_control.independent_canary_patch_verification.v1"
)
SUPERVISOR_AUTHORITY_SCHEMA = "dharma.mission_control.effect_supervisor_authority.v1"
EFFECT_WARRANT_SCHEMA = "dharma.mission_control.effect_warrant.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CanaryPatchBinding:
    """All bytes, identities, and scratch custody both canaries must sign."""

    mission_id: str
    task_id: str
    mission_attempt_id: str
    mission_claim_id: str
    packet_id: str
    correlation_id: str
    delivery_id: str
    proposal_id: str
    a2a_content_sha256: str
    attempt_key: str
    operator_id: str
    assigned_by: str
    candidate_digest: str
    diff_sha256: str
    base_sha: str
    artifact_sha256: str
    candidate_bundle_sha256: str
    authorized_source_files: tuple[str, ...]
    executor_agent_uid: str
    executor_run_id: str
    executor_process_boot_id: str
    proposal_receipt_id: str
    proposal_receipt_sha256: str
    oracle_argv_sha256: str
    effect_key: str
    scratch: ScratchTargetBinding
    foundry_verifier: CanaryVerifierBinding
    vibe_verifier: CanaryVerifierBinding

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CANARY_BINDING_SCHEMA,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "mission_attempt_id": self.mission_attempt_id,
            "mission_claim_id": self.mission_claim_id,
            "packet_id": self.packet_id,
            "correlation_id": self.correlation_id,
            "delivery_id": self.delivery_id,
            "proposal_id": self.proposal_id,
            "a2a_content_sha256": self.a2a_content_sha256,
            "attempt_key": self.attempt_key,
            "operator_id": self.operator_id,
            "assigned_by": self.assigned_by,
            "candidate_digest": self.candidate_digest,
            "diff_sha256": self.diff_sha256,
            "base_sha": self.base_sha,
            "artifact_sha256": self.artifact_sha256,
            "candidate_bundle_sha256": self.candidate_bundle_sha256,
            "authorized_source_files": list(self.authorized_source_files),
            "executor": {
                "agent_uid": self.executor_agent_uid,
                "run_id": self.executor_run_id,
                "process_boot_id": self.executor_process_boot_id,
            },
            "proposal_receipt": {
                "receipt_id": self.proposal_receipt_id,
                "sha256": self.proposal_receipt_sha256,
            },
            "oracle_argv_sha256": self.oracle_argv_sha256,
            "effect_key": self.effect_key,
            "scratch": self.scratch.to_dict(),
            "foundry_verifier": self.foundry_verifier.to_dict(
                parent_run_id=self.executor_run_id
            ),
            "vibe_verifier": self.vibe_verifier.to_dict(
                parent_run_id=self.executor_run_id
            ),
        }

    @property
    def binding_sha256(self) -> str:
        return _digest(self.to_dict())


def effect_key_for(
    *,
    mission_attempt_id: str,
    mission_claim_id: str,
    proposal_id: str,
    candidate_bundle_sha256: str,
    scratch_identity: str,
) -> str:
    body = {
        "mission_attempt_id": mission_attempt_id,
        "mission_claim_id": mission_claim_id,
        "proposal_id": proposal_id,
        "candidate_bundle_sha256": candidate_bundle_sha256,
        "scratch_identity": scratch_identity,
    }
    return EFFECT_KEY_PREFIX + _digest(body)


def scratch_identity_for(binding: ScratchTargetBinding) -> str:
    return "sha256:" + _digest(binding.stable_identity_dict())


@dataclass(frozen=True, slots=True)
class IndependentPatchVerification:
    binding: CanaryPatchBinding
    foundry_canary_evidence_sha256: str
    foundry_process_receipt_sha256: str
    vibe_process_receipt_sha256: str
    vibe_patch_receipt_sha256: str
    schema: str = INDEPENDENT_PATCH_VERIFICATION_SCHEMA
    exclusive_private_key_custody_unproven: Literal[True] = field(
        default=True, init=False
    )
    authorizes_repository_effect: Literal[False] = field(default=False, init=False)
    _seal: object | None = field(default=None, init=False, repr=False, compare=False)

    def __bool__(self) -> bool:
        raise TypeError("verification evidence is not effect authority")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "binding": self.binding.to_dict(),
            "foundry_canary_evidence_sha256": self.foundry_canary_evidence_sha256,
            "foundry_process_receipt_sha256": self.foundry_process_receipt_sha256,
            "vibe_process_receipt_sha256": self.vibe_process_receipt_sha256,
            "vibe_patch_receipt_sha256": self.vibe_patch_receipt_sha256,
            "exclusive_private_key_custody_unproven": True,
            "authorizes_repository_effect": False,
        }


@dataclass(frozen=True, slots=True)
class SupervisorEffectAuthority:
    """Injected process-owned authority; never reconstructible from a receipt."""

    binding_sha256: str
    effect_key: str
    owner_stores_sha256: str
    scratch_identity: str
    approved_scratch_root: str
    git_executable_path: str
    git_executable_sha256: str
    git_executable_device: int
    git_executable_inode: int
    git_common_dir_path: str
    git_common_dir_device: int
    git_common_dir_inode: int
    git_worktree_registration_sha256: str
    canonical_repo_identity: str
    supervisor_id: str
    process_boot_id: str
    os_uid: int
    interpreter_sha256: str
    argv_sha256: str
    authority_public_key: str
    authority_key_id: str
    signed_payload_sha256: str
    signature: str
    issued_at: datetime
    expires_at: datetime
    custody_basis: str
    schema: str = SUPERVISOR_AUTHORITY_SCHEMA
    _ownership_token: object | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _seal: object | None = field(default=None, init=False, repr=False, compare=False)

    def __bool__(self) -> bool:
        raise TypeError("supervisor evidence is validated only by its issuer")


@dataclass(frozen=True, slots=True)
class EffectBinding:
    canary: CanaryPatchBinding
    owner_stores: OwnerStoreBinding
    independent_verification_sha256: str
    foundry_canary_evidence_sha256: str
    foundry_process_receipt_sha256: str
    vibe_process_receipt_sha256: str
    vibe_patch_receipt_sha256: str
    supervisor_authority_sha256: str
    supervisor_id: str
    supervisor_process_boot_id: str

    @property
    def binding_sha256(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "canary": self.canary.to_dict(),
            "owner_stores": self.owner_stores.to_dict(),
            "independent_verification_sha256": self.independent_verification_sha256,
            "foundry_canary_evidence_sha256": self.foundry_canary_evidence_sha256,
            "foundry_process_receipt_sha256": self.foundry_process_receipt_sha256,
            "vibe_process_receipt_sha256": self.vibe_process_receipt_sha256,
            "vibe_patch_receipt_sha256": self.vibe_patch_receipt_sha256,
            "supervisor_authority_sha256": self.supervisor_authority_sha256,
            "supervisor_id": self.supervisor_id,
            "supervisor_process_boot_id": self.supervisor_process_boot_id,
        }

    def __getattr__(self, name: str) -> Any:
        if name in CanaryPatchBinding.__dataclass_fields__:
            return getattr(self.canary, name)
        raise AttributeError(name)


@dataclass(frozen=True, slots=True)
class EffectWarrant:
    fence_id: str
    binding: EffectBinding
    issued_at: datetime
    expires_at: datetime
    warrant_token: str = field(repr=False)
    schema: str = EFFECT_WARRANT_SCHEMA
    _seal: object | None = field(default=None, init=False, repr=False, compare=False)

    def __bool__(self) -> bool:
        raise TypeError("warrant authority is validated against its canonical fence")


EffectAuthorization: TypeAlias = EffectWarrant | EffectRefusal


def effect_warrant_sha256(warrant: EffectWarrant) -> str:
    """Digest nominal warrant evidence; this function grants no authority."""

    if (
        type(warrant) is not EffectWarrant
        or type(warrant.warrant_token) is not str
        or len(warrant.warrant_token) != 64
    ):
        raise ValueError("exact nominal EffectWarrant required")
    return effect_warrant_evidence_sha256(
        fence_id=warrant.fence_id, binding=warrant.binding,
        issued_at=warrant.issued_at, expires_at=warrant.expires_at,
        warrant_token_sha256=hashlib.sha256(
            warrant.warrant_token.encode("ascii")
        ).hexdigest(),
    )


def effect_warrant_evidence_sha256(
    *, fence_id: str, binding: EffectBinding, issued_at: datetime,
    expires_at: datetime, warrant_token_sha256: str,
) -> str:
    """Public evidence digest; the raw one-shot bearer is never persisted."""

    return _digest({
        "fence_id": fence_id, "binding": binding.to_dict(),
        "issued_at": issued_at.isoformat(), "expires_at": expires_at.isoformat(),
        "warrant_token_sha256": warrant_token_sha256,
    })
