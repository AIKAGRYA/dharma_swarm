"""Durable value records for the governed repository-effect lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

if TYPE_CHECKING:
    from dharma_swarm.mission_control_effect_warrant import EffectBinding

EFFECT_TERMINAL_SCHEMA = "dharma.mission_control.effect_terminal.v1"


@dataclass(frozen=True, slots=True)
class ScratchTargetBinding:
    """Stable scratch custody plus the mutable target's pre-replace identity."""

    approved_scratch_root: str
    approved_root_device: int
    approved_root_inode: int
    approved_root_mode: int
    approved_root_uid: int
    approved_root_gid: int
    resolved_root: str
    root_device: int
    root_inode: int
    root_mode: int
    root_uid: int
    root_gid: int
    ancestry_sha256: str
    experiment_id: str
    base_sha: str
    source_path: str
    marker_sha256: str
    marker_device: int
    marker_inode: int
    marker_ctime_ns: int
    marker_mode: int
    marker_uid: int
    marker_gid: int
    marker_nlink: int
    git_executable_path: str
    git_executable_sha256: str
    git_executable_device: int
    git_executable_inode: int
    git_common_dir_path: str
    git_common_dir_device: int
    git_common_dir_inode: int
    git_worktree_registration_sha256: str
    git_index_sha256: str
    canonical_repo_identity: str
    target_device: int
    target_inode: int
    target_ctime_ns: int
    target_mode: int
    target_uid: int
    target_gid: int
    target_nlink: int
    preimage_sha256: str
    postimage_sha256: str
    scratch_identity: str

    def stable_identity_dict(self) -> dict[str, Any]:
        excluded = {
            "target_device", "target_inode", "target_ctime_ns",
            "preimage_sha256", "postimage_sha256", "scratch_identity",
        }
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__ if name not in excluded
        }

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class CanaryVerifierBinding:
    role: Literal["foundry_canary", "vibe_canary"]
    agent_uid: str
    run_id: str
    signer_public_key: str

    def to_dict(self, *, parent_run_id: str) -> dict[str, str]:
        return {
            "role": self.role, "agent_uid": self.agent_uid,
            "run_id": self.run_id, "parent_run_id": parent_run_id,
            "signer_public_key": self.signer_public_key,
        }


@dataclass(frozen=True, slots=True)
class OwnerStoreBinding:
    runtime_database_path: str
    runtime_database_device: int
    runtime_database_inode: int
    runtime_database_mode: int
    runtime_database_uid: int
    runtime_database_gid: int
    runtime_database_nlink: int
    runtime_ancestry_sha256: str
    task_database_path: str
    task_database_device: int
    task_database_inode: int
    task_database_mode: int
    task_database_uid: int
    task_database_gid: int
    task_database_nlink: int
    task_ancestry_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class EffectMutationResult:
    path: str
    preimage_sha256: str
    postimage_sha256: str
    scratch_identity: str
    observed_before_sha256: str
    target_device_before: int
    target_inode_before: int
    target_device_after: int
    target_inode_after: int
    target_mode_before: int
    target_uid_before: int
    target_gid_before: int
    target_nlink_before: int
    target_mode_after: int
    target_uid_after: int
    target_gid_after: int
    target_nlink_after: int


@dataclass(frozen=True, slots=True)
class EffectTerminalRecord:
    terminal_id: str
    terminal_receipt_id: str
    terminal_receipt_sha256: str
    fence_id: str
    effect_key: str
    binding_sha256: str
    candidate_bundle_sha256: str
    diff_sha256: str
    base_sha: str
    path: str
    preimage_sha256: str
    postimage_sha256: str
    scratch_identity: str
    warrant_sha256: str
    supervisor_id: str
    supervisor_process_boot_id: str
    claim_generation: int
    claimed_by: str
    target_device_before: int
    target_inode_before: int
    target_device_after: int
    target_inode_after: int
    target_mode_before: int
    target_uid_before: int
    target_gid_before: int
    target_nlink_before: int
    target_mode_after: int
    target_uid_after: int
    target_gid_after: int
    target_nlink_after: int
    fence_created_at: datetime
    consuming_at: datetime
    consumed_at: datetime
    recovery_finalized: bool
    recovery_supervisor_id: str
    recovery_supervisor_process_boot_id: str
    recovery_supervisor_authority_sha256: str
    recovery_owner_basis: str
    recovery_owner_observation_sha256: str
    repository_effect_authorized: Literal[True] = True
    repository_effect_performed: Literal[True] = True
    schema: str = EFFECT_TERMINAL_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            name: value.isoformat() if isinstance(value, datetime) else value
            for name, value in asdict(self).items()
        }


@dataclass(frozen=True, slots=True)
class EffectFenceRecord:
    fence_id: str
    state: str
    binding: EffectBinding
    fence_created_at: datetime
    warrant_issued_at: datetime
    warrant_expires_at: datetime
    claim_generation: int
    claimed_by: str
    consuming_at: datetime | None
    terminal: EffectTerminalRecord | None
    quarantine_reason: str
    observed_sha256: str
    quarantined_at: datetime | None

    def __bool__(self) -> None:
        raise TypeError("effect fence readback is evidence, not authority")


@dataclass(frozen=True, slots=True)
class EffectRefusal:
    blockers: tuple[str, ...]

    def __bool__(self) -> Literal[False]:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dharma.mission_control.effect_refusal.v1",
            "decision": "refused",
            "blockers": list(self.blockers),
        }


EffectConsumption: TypeAlias = EffectTerminalRecord | EffectRefusal


__all__ = [
    "EFFECT_TERMINAL_SCHEMA",
    "EffectConsumption",
    "EffectFenceRecord",
    "EffectMutationResult",
    "EffectRefusal",
    "EffectTerminalRecord",
]
