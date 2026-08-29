"""Closed canonical codecs for durable governed-effect records."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from dharma_swarm.mission_control_effect_records import (
    EFFECT_TERMINAL_SCHEMA,
    EffectTerminalRecord,
)
from dharma_swarm.mission_control_effect_warrant import (
    CANARY_BINDING_SCHEMA,
    CanaryPatchBinding,
    CanaryVerifierBinding,
    EffectBinding,
    OwnerStoreBinding,
    ScratchTargetBinding,
    effect_key_for,
    scratch_identity_for,
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _object(raw: str, *, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate {label} key")
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError(f"non-finite {label} value {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)
    if type(value) is not dict or canonical_json(value) != raw:
        raise ValueError(f"{label} is not one canonical object")
    return value


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _raw_sha(value: object) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _relative_source_path(value: object) -> bool:
    if type(value) is not str or not value or len(value) > 4096 or "\\" in value:
        return False
    path = PurePosixPath(value)
    return bool(
        not path.is_absolute() and str(path) == value
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _validate_binding(result: EffectBinding) -> None:
    canary, scratch, owners = result.canary, result.canary.scratch, result.owner_stores
    raw_hashes = (
        canary.a2a_content_sha256, canary.diff_sha256, canary.artifact_sha256,
        canary.candidate_bundle_sha256, canary.proposal_receipt_sha256,
        canary.oracle_argv_sha256, scratch.marker_sha256,
        scratch.git_executable_sha256, scratch.git_worktree_registration_sha256,
        scratch.git_index_sha256, scratch.preimage_sha256, scratch.postimage_sha256,
        result.independent_verification_sha256,
        result.foundry_canary_evidence_sha256,
        result.foundry_process_receipt_sha256, result.vibe_process_receipt_sha256,
        result.vibe_patch_receipt_sha256, result.supervisor_authority_sha256,
        scratch.ancestry_sha256, owners.runtime_ancestry_sha256,
        owners.task_ancestry_sha256,
    )
    path_values = (
        scratch.approved_scratch_root, scratch.resolved_root,
        scratch.git_executable_path, scratch.git_common_dir_path,
        owners.runtime_database_path, owners.task_database_path,
    )
    integer_values = tuple(
        getattr(scratch, name) for name in ScratchTargetBinding.__dataclass_fields__
        if name.endswith(("_device", "_inode", "_ctime_ns", "_mode", "_uid", "_gid", "_nlink"))
    ) + tuple(
        getattr(owners, name) for name in OwnerStoreBinding.__dataclass_fields__
        if name.endswith(("_device", "_inode", "_mode", "_uid", "_gid", "_nlink"))
    )
    text_values = tuple(
        value for value in canary.to_dict().values() if type(value) is str
    ) + (result.supervisor_id, result.supervisor_process_boot_id)
    if (
        not all(_raw_sha(value) for value in raw_hashes)
        or type(canary.candidate_digest) is not str
        or _SHA256.fullmatch(canary.candidate_digest) is None
        or type(canary.base_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", canary.base_sha) is None
        or type(scratch.scratch_identity) is not str
        or _SHA256.fullmatch(scratch.scratch_identity) is None
        or not canary.effect_key.startswith("governed_patch_effect:")
        or not _raw_sha(canary.effect_key.removeprefix("governed_patch_effect:"))
        or canary.authorized_source_files != (scratch.source_path,)
        or not _relative_source_path(scratch.source_path)
        or not all(Path(value).is_absolute() for value in path_values)
        or not all(_nonnegative_int(value) for value in integer_values)
        or any(not value or len(value) > 4096 for value in text_values)
        or scratch.target_nlink != 1 or scratch.marker_nlink != 1
        or owners.runtime_database_nlink != 1 or owners.task_database_nlink != 1
        or canary.foundry_verifier.role != "foundry_canary"
        or canary.vibe_verifier.role != "vibe_canary"
    ):
        raise ValueError("effect binding scalar domain mismatch")


def effect_binding_from_json(raw: str) -> EffectBinding:
    """Decode the complete binding; reject omitted or surplus authority fields."""

    value = _object(raw, label="effect binding")
    if set(value) != set(EffectBinding.__dataclass_fields__):
        raise ValueError("effect binding shape mismatch")
    canary_raw = value.pop("canary", None)
    owners_raw = value.pop("owner_stores", None)
    if type(canary_raw) is not dict or type(owners_raw) is not dict:
        raise ValueError("nested effect binding shape mismatch")
    canary = dict(canary_raw)
    if canary.pop("schema", None) != CANARY_BINDING_SCHEMA:
        raise ValueError("canary binding schema mismatch")
    flat = set(CanaryPatchBinding.__dataclass_fields__)
    flat -= {
        "executor_agent_uid", "executor_run_id", "executor_process_boot_id",
        "proposal_receipt_id", "proposal_receipt_sha256",
    }
    serialized = flat | {"executor", "proposal_receipt"}
    if set(canary) != serialized:
        raise ValueError("canary binding shape mismatch")
    scratch = canary.pop("scratch", None)
    foundry = canary.pop("foundry_verifier", None)
    vibe = canary.pop("vibe_verifier", None)
    executor = canary.pop("executor", None)
    proposal = canary.pop("proposal_receipt", None)
    if not all(
        type(item) is dict for item in (scratch, foundry, vibe, executor, proposal)
    ):
        raise ValueError("nested effect binding shape mismatch")
    if set(scratch) != set(ScratchTargetBinding.__dataclass_fields__):
        raise ValueError("scratch binding shape mismatch")
    verifier_fields = set(CanaryVerifierBinding.__dataclass_fields__)
    if set(executor) != {"agent_uid", "run_id", "process_boot_id"}:
        raise ValueError("executor binding shape mismatch")
    if set(proposal) != {"receipt_id", "sha256"}:
        raise ValueError("proposal receipt binding shape mismatch")
    for verifier in (foundry, vibe):
        if set(verifier) != verifier_fields | {"parent_run_id"}:
            raise ValueError("verifier binding shape mismatch")
        if verifier.pop("parent_run_id") != executor["run_id"]:
            raise ValueError("verifier parent binding mismatch")
    files = canary.get("authorized_source_files")
    if type(files) is not list or any(type(item) is not str for item in files):
        raise ValueError("authorized source binding mismatch")
    canary["authorized_source_files"] = tuple(files)
    canary["executor_agent_uid"] = executor["agent_uid"]
    canary["executor_run_id"] = executor["run_id"]
    canary["executor_process_boot_id"] = executor["process_boot_id"]
    canary["proposal_receipt_id"] = proposal["receipt_id"]
    canary["proposal_receipt_sha256"] = proposal["sha256"]
    canary["scratch"] = ScratchTargetBinding(**scratch)
    canary["foundry_verifier"] = CanaryVerifierBinding(**foundry)
    canary["vibe_verifier"] = CanaryVerifierBinding(**vibe)
    if set(owners_raw) != set(OwnerStoreBinding.__dataclass_fields__):
        raise ValueError("owner-store binding shape mismatch")
    canary_value = CanaryPatchBinding(**canary)
    if scratch_identity_for(canary_value.scratch) != canary_value.scratch.scratch_identity:
        raise ValueError("scratch identity digest mismatch")
    expected_effect_key = effect_key_for(
        mission_attempt_id=canary_value.mission_attempt_id,
        mission_claim_id=canary_value.mission_claim_id,
        proposal_id=canary_value.proposal_id,
        candidate_bundle_sha256=canary_value.candidate_bundle_sha256,
        scratch_identity=canary_value.scratch.scratch_identity,
    )
    if canary_value.effect_key != expected_effect_key:
        raise ValueError("effect key digest mismatch")
    result = EffectBinding(
        canary=canary_value,
        owner_stores=OwnerStoreBinding(**owners_raw),
        **value,
    )
    if canonical_json(result.to_dict()) != raw:
        raise ValueError("effect binding does not round-trip canonically")
    _validate_binding(result)
    return result


def terminal_from_json(raw: str) -> EffectTerminalRecord:
    value = _object(raw, label="effect terminal record")
    if set(value) != set(EffectTerminalRecord.__dataclass_fields__):
        raise ValueError("effect terminal record shape mismatch")
    for name in ("fence_created_at", "consuming_at", "consumed_at"):
        if type(value[name]) is not str:
            raise ValueError("effect terminal timestamp is not a string")
        parsed = datetime.fromisoformat(value[name])
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("effect terminal timestamp is naive")
        value[name] = parsed
    if (
        value.get("schema") != EFFECT_TERMINAL_SCHEMA
        or value.get("repository_effect_authorized") is not True
        or value.get("repository_effect_performed") is not True
    ):
        raise ValueError("effect terminal authority claims are malformed")
    result = EffectTerminalRecord(**value)
    if type(result.effect_key) is not str:
        raise ValueError("effect terminal key is malformed")
    digest = hashlib.sha256(result.effect_key.encode("utf-8")).hexdigest()
    integer_names = tuple(
        name for name in EffectTerminalRecord.__dataclass_fields__
        if name.startswith("target_") or name == "claim_generation"
    )
    if (
        result.terminal_id != "etr_" + digest
        or result.terminal_receipt_id != "rr_governed_patch_effect_" + digest
        or result.fence_id != "ef_" + digest
        or not result.effect_key.startswith("governed_patch_effect:")
        or not all(_raw_sha(getattr(result, name)) for name in (
            "terminal_receipt_sha256", "binding_sha256",
            "candidate_bundle_sha256", "diff_sha256", "preimage_sha256",
            "postimage_sha256", "warrant_sha256",
        ))
        or type(result.scratch_identity) is not str
        or not _SHA256.fullmatch(result.scratch_identity)
        or type(result.base_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", result.base_sha) is None
        or not _relative_source_path(result.path)
        or type(result.supervisor_id) is not str or not result.supervisor_id
        or type(result.supervisor_process_boot_id) is not str
        or not result.supervisor_process_boot_id
        or type(result.claimed_by) is not str or not result.claimed_by
        or not _positive_int(result.claim_generation)
        or not all(_nonnegative_int(getattr(result, name)) for name in integer_names)
        or result.target_nlink_before != 1 or result.target_nlink_after != 1
        or result.target_device_before != result.target_device_after
        or result.target_inode_before == result.target_inode_after
        or (result.target_mode_before, result.target_uid_before,
            result.target_gid_before, result.target_nlink_before)
        != (result.target_mode_after, result.target_uid_after,
            result.target_gid_after, result.target_nlink_after)
        or not result.fence_created_at <= result.consuming_at <= result.consumed_at
        or type(result.recovery_finalized) is not bool
        or (
            result.recovery_finalized
            and (
                type(result.recovery_supervisor_id) is not str
                or not result.recovery_supervisor_id
                or type(result.recovery_supervisor_process_boot_id) is not str
                or not result.recovery_supervisor_process_boot_id
                or not _raw_sha(result.recovery_supervisor_authority_sha256)
                or result.recovery_owner_basis not in {
                    "live_owner",
                    "expired_active",
                    "canonical_stale_recovery",
                    "canonical_terminal",
                }
                or not _raw_sha(result.recovery_owner_observation_sha256)
            )
        )
        or (
            not result.recovery_finalized
            and (
                result.recovery_supervisor_id,
                result.recovery_supervisor_process_boot_id,
                result.recovery_supervisor_authority_sha256,
                result.recovery_owner_basis,
                result.recovery_owner_observation_sha256,
            ) != ("", "", "", "", "")
        )
    ):
        raise ValueError("effect terminal scalar domain mismatch")
    if canonical_json(result.to_dict()) != raw:
        raise ValueError("effect terminal record does not round-trip canonically")
    return result


__all__ = [
    "canonical_json",
    "canonical_sha256",
    "effect_binding_from_json",
    "terminal_from_json",
]
