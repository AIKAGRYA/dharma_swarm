"""Consume one sealed governed-patch warrant in its exact scratch target.

Authority and terminal state belong to ``mission_control_effect_fence``.  This
module contributes only the warrant-bound filesystem callback; it never mints
authority, writes a generic receipt, or targets a canonical checkout.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.foundry.patches import PatchReplayError, apply_unified_diff
from dharma_swarm.foundry.patches_atomic import fsync_exact_replacement
from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    verify_candidate_bundle,
)
from dharma_swarm.governed_patch_effect_target import (
    FileSnapshot,
    GovernedPatchEffectError,
    PreparedEffectTarget,
    inspect_effect_target,
    prepare_effect_target,
)
from dharma_swarm.mission_control_effect_records import (
    EffectMutationResult,
    ScratchTargetBinding,
)
from dharma_swarm.mission_control_effect_warrant import (
    CanaryPatchBinding,
    EffectBinding,
    scratch_identity_for,
)


@dataclass(frozen=True, slots=True)
class _EffectStateObservation:
    state: Literal["preimage", "postimage", "ambiguous"]
    disposition: Literal["reissuable", "recovery_finalizable", "quarantine"]
    reason: str
    path: str
    observed_sha256: str
    target_device: int
    target_inode: int
    target_ctime_ns: int
    target_mode: int
    target_uid: int
    target_gid: int
    target_nlink: int


def _require_candidate_binding(
    candidate: CandidateBundle,
    canary: CanaryPatchBinding,
) -> None:
    native = candidate.bindings
    actual = (
        native.mission_id,
        native.task_id,
        native.attempt_id,
        native.lease_id,
        native.packet_id,
        native.correlation_id,
        native.delivery_id,
        native.proposal_id,
        native.base_sha,
        native.executor_agent_uid,
        native.executor_run_id,
        native.executor_process_boot_id,
        candidate.request_content_sha256,
        candidate.candidate_digest,
        candidate.diff_sha256,
        candidate.bundle_sha256,
        candidate.source_sha256,
        candidate.authorized_source_path,
        canonical_sha256(list(candidate.oracle_argv)),
    )
    expected = (
        canary.mission_id,
        canary.task_id,
        canary.packet_id,
        canary.delivery_id,
        canary.packet_id,
        canary.correlation_id,
        canary.delivery_id,
        canary.proposal_id,
        canary.base_sha,
        canary.executor_agent_uid,
        canary.executor_run_id,
        canary.executor_process_boot_id,
        canary.a2a_content_sha256,
        canary.candidate_digest,
        canary.diff_sha256,
        canary.candidate_bundle_sha256,
        canary.scratch.preimage_sha256,
        canary.scratch.source_path,
        canary.oracle_argv_sha256,
    )
    if actual != expected or canary.authorized_source_files != (
        candidate.authorized_source_path,
    ):
        raise GovernedPatchEffectError(
            "candidate does not match the sealed one-file effect binding"
        )


def _operation_id(binding: EffectBinding) -> str:
    return hashlib.sha256(binding.effect_key.encode("utf-8")).hexdigest()


def _temporary_path(source_path: str, operation_id: str) -> str:
    source = PurePosixPath(source_path)
    return (source.parent / f".foundry-replay-{operation_id}").as_posix()


def _recovery_temp_state(
    prepared: PreparedEffectTarget,
    temporary_path: str,
) -> Literal["absent", "exact", "invalid"]:
    """Classify a deterministic crash temp without trusting its pathname."""

    path = prepared.root / temporary_path
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "invalid"
    try:
        before = os.fstat(descriptor)
        try:
            parent = path.parent.stat(follow_symlinks=False)
        except OSError:
            return "invalid"
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_dev != parent.st_dev
            or before.st_dev != prepared.observed.device
            or stat.S_IMODE(before.st_mode) != prepared.observed.mode
            or before.st_uid != prepared.observed.uid
            or before.st_gid != prepared.observed.gid
            or before.st_nlink != 1
            or before.st_size != len(prepared.postimage)
        ):
            return "invalid"
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                return "invalid"
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            return "invalid"
        after = os.fstat(descriptor)
        def identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
            return (
                value.st_dev,
                value.st_ino,
                value.st_size,
                value.st_ctime_ns,
                value.st_mtime_ns,
            )
        if b"".join(chunks) != prepared.postimage or identity(before) != identity(after):
            return "invalid"
        return "exact"
    finally:
        os.close(descriptor)


def _prepare_bound_target(
    binding: EffectBinding,
    candidate: CandidateBundle,
    *,
    allowed_temp_path: str | None,
) -> PreparedEffectTarget:
    scratch = binding.canary.scratch
    prepared = prepare_effect_target(
        candidate,
        Path(scratch.resolved_root),
        approved_scratch_root=Path(scratch.approved_scratch_root),
        trusted_canonical_repo=candidate.repo_root,
        git_executable=Path(scratch.git_executable_path),
        expected_os_uid=scratch.target_uid,
        allowed_temp_path=allowed_temp_path,
    )
    observed = prepared.to_binding()
    if (
        observed.stable_identity_dict() != scratch.stable_identity_dict()
        or observed.scratch_identity != scratch.scratch_identity
        or scratch_identity_for(observed) != scratch.scratch_identity
        or observed.preimage_sha256 != scratch.preimage_sha256
        or observed.postimage_sha256 != scratch.postimage_sha256
    ):
        raise GovernedPatchEffectError("sealed scratch target binding drifted")
    return prepared


def _verify_bound_candidate(
    binding: EffectBinding,
    candidate: CandidateBundle,
) -> CandidateBundle:
    try:
        candidate = verify_candidate_bundle(candidate)
    except Exception as exc:
        raise GovernedPatchEffectError("candidate bundle revalidation failed") from exc
    _require_candidate_binding(candidate, binding.canary)
    return candidate


def _observation(
    prepared: PreparedEffectTarget,
    *,
    disposition: Literal["reissuable", "recovery_finalizable", "quarantine"],
    reason: str,
) -> _EffectStateObservation:
    observed = prepared.observed
    return _EffectStateObservation(
        state=prepared.target_state,
        disposition=disposition,
        reason=reason,
        path=prepared.source_path,
        observed_sha256=observed.sha256,
        target_device=observed.device,
        target_inode=observed.inode,
        target_ctime_ns=observed.ctime_ns,
        target_mode=observed.mode,
        target_uid=observed.uid,
        target_gid=observed.gid,
        target_nlink=observed.nlink,
    )


def _classify_prevalidated_effect(
    binding: EffectBinding,
    candidate: CandidateBundle,
) -> _EffectStateObservation:
    """Classify restart bytes without writing, after fence prevalidation."""

    candidate = _verify_bound_candidate(binding, candidate)
    scratch = binding.canary.scratch
    operation_id = _operation_id(binding)
    temporary_path = _temporary_path(candidate.authorized_source_path, operation_id)
    prepared = _prepare_bound_target(
        binding,
        candidate,
        allowed_temp_path=temporary_path,
    )
    original = (
        prepared.observed.device,
        prepared.observed.inode,
        prepared.observed.ctime_ns,
    ) == (scratch.target_device, scratch.target_inode, scratch.target_ctime_ns)
    temp_state = _recovery_temp_state(prepared, temporary_path)
    if prepared.target_state == "preimage":
        if original:
            if temp_state == "invalid":
                return _observation(
                    prepared,
                    disposition="quarantine",
                    reason="invalid_recovery_temp",
                )
            return _observation(
                prepared,
                disposition="reissuable",
                reason=(
                    "exact_original_preimage_with_recovery_temp"
                    if temp_state == "exact"
                    else "exact_original_preimage"
                ),
            )
        return _observation(
            prepared,
            disposition="quarantine",
            reason="preimage_on_replacement_inode",
        )
    if prepared.target_state == "postimage":
        if temp_state != "absent":
            return _observation(
                prepared,
                disposition="quarantine",
                reason="postimage_with_recovery_temp",
            )
        if (
            prepared.observed.device == scratch.target_device
            and prepared.observed.inode != scratch.target_inode
        ):
            return _observation(
                prepared,
                disposition="recovery_finalizable",
                reason="exact_atomic_postimage",
            )
        return _observation(
            prepared,
            disposition="quarantine",
            reason=(
                "postimage_on_original_inode"
                if prepared.observed.inode == scratch.target_inode
                else "postimage_on_wrong_device"
            ),
        )
    return _observation(
        prepared,
        disposition="quarantine",
        reason="ambiguous_target_bytes",
    )


def _durably_classify_prevalidated_effect(
    binding: EffectBinding,
    candidate: CandidateBundle,
) -> _EffectStateObservation:
    """Classify, durably sync, and reclassify one exact atomic postimage."""

    candidate = _verify_bound_candidate(binding, candidate)
    observed = _classify_prevalidated_effect(binding, candidate)
    if observed.disposition != "recovery_finalizable":
        return observed
    prepared = _prepare_bound_target(binding, candidate, allowed_temp_path=None)
    if (
        prepared.target_state != "postimage"
        or prepared.observed.device != observed.target_device
        or prepared.observed.inode != observed.target_inode
        or prepared.observed.sha256 != observed.observed_sha256
    ):
        raise GovernedPatchEffectError("exact postimage drifted before durability sync")
    fsync_exact_replacement(
        prepared.root,
        prepared.source_path,
        expected_root_identity=(
            binding.canary.scratch.root_device,
            binding.canary.scratch.root_inode,
        ),
        expected_replacement_identity=(
            observed.target_device,
            observed.target_inode,
            len(prepared.postimage),
            observed.target_mode,
            observed.target_uid,
            observed.target_gid,
            observed.target_nlink,
        ),
        expected_bytes=prepared.postimage,
    )
    confirmed = _classify_prevalidated_effect(binding, candidate)
    if confirmed != observed:
        raise GovernedPatchEffectError("exact postimage drifted across durability sync")
    return confirmed


def _require_exact_preimage(
    prepared: PreparedEffectTarget,
    scratch: ScratchTargetBinding,
) -> None:
    if prepared.target_state != "preimage" or prepared.to_binding() != scratch:
        raise GovernedPatchEffectError("effect mutation requires the exact bound preimage")


def _postimage_result(
    before: PreparedEffectTarget,
    after: PreparedEffectTarget,
) -> EffectMutationResult:
    if (
        after.target_state != "postimage"
        or after.observed.device != before.observed.device
        or after.observed.inode == before.observed.inode
        or (
            after.observed.mode,
            after.observed.uid,
            after.observed.gid,
            after.observed.nlink,
        )
        != (
            before.observed.mode,
            before.observed.uid,
            before.observed.gid,
            before.observed.nlink,
        )
    ):
        raise GovernedPatchEffectError(
            "effect replacement did not produce an exact atomic postimage"
        )
    return EffectMutationResult(
        path=before.source_path,
        preimage_sha256=hashlib.sha256(before.preimage).hexdigest(),
        postimage_sha256=hashlib.sha256(after.postimage).hexdigest(),
        scratch_identity=after.scratch_identity,
        observed_before_sha256=before.observed.sha256,
        target_device_before=before.observed.device,
        target_inode_before=before.observed.inode,
        target_device_after=after.observed.device,
        target_inode_after=after.observed.inode,
        target_mode_before=before.observed.mode,
        target_uid_before=before.observed.uid,
        target_gid_before=before.observed.gid,
        target_nlink_before=before.observed.nlink,
        target_mode_after=after.observed.mode,
        target_uid_after=after.observed.uid,
        target_gid_after=after.observed.gid,
        target_nlink_after=after.observed.nlink,
    )


def _perform_prevalidated_effect(
    binding: EffectBinding,
    candidate: CandidateBundle,
) -> EffectMutationResult:
    """Perform the fence-prevalidated one exact replacement.

    This is deliberately private.  The fence calls it only inside its nonce/CAS
    transaction after validating the non-serializable registered capability.
    All filesystem and Git inputs are then derived from that exact binding.
    """

    candidate = _verify_bound_candidate(binding, candidate)
    operation_id = _operation_id(binding)
    temporary_path = _temporary_path(
        candidate.authorized_source_path,
        operation_id,
    )
    before = _prepare_bound_target(
        binding,
        candidate,
        allowed_temp_path=temporary_path,
    )
    scratch = binding.canary.scratch
    _require_exact_preimage(before, scratch)

    try:
        apply_unified_diff(
            before.root,
            candidate.diff_bytes.decode("utf-8"),
            allowed_paths=(candidate.authorized_source_path,),
            expected_identity=(
                scratch.target_device,
                scratch.target_inode,
                scratch.target_ctime_ns,
            ),
            expected_root_identity=(scratch.root_device, scratch.root_inode),
            operation_id=operation_id,
        )
    except (PatchReplayError, UnicodeDecodeError) as exc:
        # A visible rename whose full atomic primitive failed is not durable
        # authority.  The issued fence remains recoverable, but only a later
        # fresh supervisor may sync and terminalize the exact postimage.
        raise GovernedPatchEffectError(
            "exact atomic postimage replacement failed closed"
        ) from exc

    observed = _durably_classify_prevalidated_effect(binding, candidate)
    if observed.disposition != "recovery_finalizable":
        raise GovernedPatchEffectError("durable atomic postimage is not exact")
    after = _prepare_bound_target(binding, candidate, allowed_temp_path=None)
    return _postimage_result(before, after)

__all__ = [
    "FileSnapshot",
    "GovernedPatchEffectError",
    "PreparedEffectTarget",
    "inspect_effect_target",
    "prepare_effect_target",
]
