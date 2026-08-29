"""Non-authorizing scratch inspection; same-UID hostility is limited by descriptor revalidation, not disproven by mode custody."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from dharma_swarm.evolution_safety import EVOLUTION_MARKER, REQUIRED_MARKER_FIELDS
from dharma_swarm.foundry.patches import (
    PatchReplayError,
    _replay,
    parse_unified_diff,
    scoped_regular_file,
)
from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    verify_candidate_bundle,
)
from dharma_swarm.governed_patch_effect_git import (
    EffectGitError,
    GitExecutableBinding,
    GitRepositoryBinding,
    inspect_registered_worktree,
)
from dharma_swarm.governed_patch_evidence import MAX_SOURCE_BYTES
from dharma_swarm.mission_control_effect_records import ScratchTargetBinding
from dharma_swarm.mission_control_effect_warrant import scratch_identity_for


class GovernedPatchEffectError(RuntimeError):
    """A candidate/worktree is unsafe, stale, or not exactly recoverable."""
@dataclass(frozen=True, slots=True)
class FileSnapshot:
    data: bytes
    sha256: str
    device: int
    inode: int
    ctime_ns: int
    mode: int
    uid: int
    gid: int
    nlink: int


@dataclass(frozen=True, slots=True)
class _MarkerSnapshot:
    payload: dict[str, Any]
    sha256: str
    device: int
    inode: int
    ctime_ns: int
    mode: int
    uid: int
    gid: int
    nlink: int

@dataclass(frozen=True, slots=True)
class PreparedEffectTarget:
    candidate: CandidateBundle
    root: Path
    approved_root: Path
    canonical_repo: Path
    marker: _MarkerSnapshot
    git_executable: GitExecutableBinding
    git_repository: GitRepositoryBinding
    source_path: str
    root_device: int
    root_inode: int
    root_mode: int
    root_uid: int
    root_gid: int
    approved_root_device: int
    approved_root_inode: int
    approved_root_mode: int
    approved_root_uid: int
    approved_root_gid: int
    ancestry_sha256: str
    preimage: bytes
    postimage: bytes
    observed: FileSnapshot
    scratch_identity: str

    @property
    def target_state(self) -> str:
        if self.observed.data == self.preimage:
            return "preimage"
        if self.observed.data == self.postimage:
            return "postimage"
        return "ambiguous"

    def to_binding(self) -> ScratchTargetBinding:
        binding = ScratchTargetBinding(
            approved_scratch_root=str(self.approved_root),
            approved_root_device=self.approved_root_device,
            approved_root_inode=self.approved_root_inode,
            approved_root_mode=self.approved_root_mode,
            approved_root_uid=self.approved_root_uid,
            approved_root_gid=self.approved_root_gid,
            resolved_root=str(self.root),
            root_device=self.root_device,
            root_inode=self.root_inode,
            root_mode=self.root_mode,
            root_uid=self.root_uid,
            root_gid=self.root_gid,
            ancestry_sha256=self.ancestry_sha256,
            experiment_id=str(self.marker.payload["experiment_id"]),
            base_sha=self.candidate.bindings.base_sha,
            source_path=self.source_path,
            marker_sha256=self.marker.sha256,
            marker_device=self.marker.device,
            marker_inode=self.marker.inode,
            marker_ctime_ns=self.marker.ctime_ns,
            marker_mode=self.marker.mode,
            marker_uid=self.marker.uid,
            marker_gid=self.marker.gid,
            marker_nlink=self.marker.nlink,
            git_executable_path=str(self.git_executable.path),
            git_executable_sha256=self.git_executable.sha256,
            git_executable_device=self.git_executable.device,
            git_executable_inode=self.git_executable.inode,
            git_common_dir_path=self.git_repository.common_dir_path,
            git_common_dir_device=self.git_repository.common_dir_device,
            git_common_dir_inode=self.git_repository.common_dir_inode,
            git_worktree_registration_sha256=(
                self.git_repository.worktree_registration_sha256
            ),
            git_index_sha256=self.git_repository.index_sha256,
            canonical_repo_identity=self.git_repository.canonical_repo_identity,
            target_device=self.observed.device,
            target_inode=self.observed.inode,
            target_ctime_ns=self.observed.ctime_ns,
            target_mode=self.observed.mode,
            target_uid=self.observed.uid,
            target_gid=self.observed.gid,
            target_nlink=self.observed.nlink,
            preimage_sha256=_sha(self.preimage),
            postimage_sha256=_sha(self.postimage),
            scratch_identity="",
        )
        return replace(binding, scratch_identity=scratch_identity_for(binding))

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_ctime_ns,
        value.st_mtime_ns,
    )


def _read_target(root: Path, source_path: str, *, expected_uid: int) -> FileSnapshot:
    target = scoped_regular_file(
        root,
        source_path,
        field="authorized effect target",
        error_type=GovernedPatchEffectError,
    )
    try:
        descriptor = os.open(
            target,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError as exc:
        raise GovernedPatchEffectError("authorized effect target is unsafe") from exc
    try:
        before = os.fstat(descriptor)
        mode = stat.S_IMODE(before.st_mode)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != expected_uid
            or mode & 0o022
            or before.st_nlink != 1
            or before.st_size > MAX_SOURCE_BYTES
        ):
            raise GovernedPatchEffectError("authorized effect target custody is unsafe")
        chunks: list[bytes] = []
        remaining = MAX_SOURCE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            len(data) > MAX_SOURCE_BYTES
            or len(data) != before.st_size
            or _identity(before) != _identity(after)
        ):
            raise GovernedPatchEffectError("authorized effect target changed while read")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GovernedPatchEffectError("authorized effect target is not UTF-8") from exc
        return FileSnapshot(
            data,
            _sha(data),
            before.st_dev,
            before.st_ino,
            before.st_ctime_ns,
            mode,
            before.st_uid,
            before.st_gid,
            before.st_nlink,
        )
    finally:
        os.close(descriptor)


def _read_marker(root: Path, *, expected_uid: int) -> _MarkerSnapshot:
    try:
        descriptor = os.open(
            root / EVOLUTION_MARKER,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError as exc:
        raise GovernedPatchEffectError("scratch marker is unavailable/unsafe") from exc
    try:
        before = os.fstat(descriptor)
        mode = stat.S_IMODE(before.st_mode)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != expected_uid
            or mode & 0o022
            or before.st_nlink != 1
            or not 0 < before.st_size <= 64 * 1024
        ):
            raise GovernedPatchEffectError("scratch marker custody is unsafe")
        raw = os.read(descriptor, 64 * 1024 + 1)
        after = os.fstat(descriptor)
        if len(raw) != before.st_size or _identity(before) != _identity(after):
            raise GovernedPatchEffectError("scratch marker changed while read")

        def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in values:
                if key in result:
                    raise GovernedPatchEffectError("scratch marker has duplicate keys")
                result[key] = value
            return result

        def constant(value: str) -> None:
            raise GovernedPatchEffectError(f"scratch marker is non-finite: {value}")

        try:
            payload = json.loads(
                raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
            )
        except GovernedPatchEffectError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise GovernedPatchEffectError("scratch marker is malformed") from exc
        if type(payload) is not dict or any(
            type(payload.get(field)) is not str
            or payload[field] != payload[field].strip()
            or not payload[field]
            or any(character in payload[field] for character in ("\x00", "\r", "\n"))
            for field in REQUIRED_MARKER_FIELDS
        ):
            raise GovernedPatchEffectError("scratch marker required fields are invalid")
        return _MarkerSnapshot(
            payload,
            _sha(raw),
            before.st_dev,
            before.st_ino,
            before.st_ctime_ns,
            mode,
            before.st_uid,
            before.st_gid,
            before.st_nlink,
        )
    finally:
        os.close(descriptor)


def _postimage(candidate: CandidateBundle) -> bytes:
    try:
        diff = candidate.diff_bytes.decode("utf-8")
        source = candidate.source_bytes.decode("utf-8")
        parsed = parse_unified_diff(diff)
        if parsed.path != candidate.authorized_source_path:
            raise GovernedPatchEffectError("candidate diff path is unauthorized")
        postimage = "".join(_replay(source.splitlines(keepends=True), parsed)).encode()
    except (UnicodeError, PatchReplayError) as exc:
        raise GovernedPatchEffectError("candidate effect is not exact/replayable") from exc
    if postimage == candidate.source_bytes:
        raise GovernedPatchEffectError("candidate effect has no byte change")
    return postimage


def _directory_identity(
    path: Path, *, expected_uid: int, allow_root_owner: bool = False,
) -> dict[str, int | str]:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise GovernedPatchEffectError("effect directory custody is unavailable") from exc
    mode = stat.S_IMODE(metadata.st_mode)
    root_sticky = allow_root_owner and metadata.st_uid == 0 and mode & stat.S_ISVTX
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid not in ({expected_uid, 0} if allow_root_owner else {expected_uid})
        or (mode & 0o022 and not root_sticky)
    ):
        raise GovernedPatchEffectError("effect directory custody is unsafe")
    return {
        "path": str(path),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": mode,
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def _directory_custody(
    approved: Path,
    root: Path,
    source_path: str,
    *,
    expected_uid: int,
) -> tuple[dict[str, int | str], dict[str, int | str], str, tuple[dict[str, int | str], ...]]:
    approved_identity = _directory_identity(approved, expected_uid=expected_uid)
    trusted_parents = tuple(
        _directory_identity(parent, expected_uid=expected_uid, allow_root_owner=True)
        for parent in reversed(approved.parents)
    )
    try:
        root_parts = root.relative_to(approved).parts
    except ValueError as exc:  # pragma: no cover - guarded by caller
        raise GovernedPatchEffectError("scratch is outside approved root") from exc
    cursor = approved
    ancestry: list[dict[str, int | str]] = []
    for part in root_parts:
        cursor /= part
        ancestry.append(_directory_identity(cursor, expected_uid=expected_uid))
    if not ancestry:
        raise GovernedPatchEffectError("scratch must be strictly beneath approved root")
    root_identity = ancestry[-1]
    target_cursor = root
    target_parents: list[dict[str, int | str]] = []
    for part in PurePosixPath(source_path).parts[:-1]:
        target_cursor /= part
        target_parents.append(
            _directory_identity(target_cursor, expected_uid=expected_uid)
        )
    custody = (*trusted_parents, approved_identity, *ancestry, *target_parents)
    ancestry_sha256 = _sha(
        json.dumps(
            custody,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    )
    return approved_identity, root_identity, ancestry_sha256, custody


def prepare_effect_target(
    candidate: CandidateBundle,
    scratch_worktree: Path,
    *,
    approved_scratch_root: Path,
    trusted_canonical_repo: Path,
    git_executable: Path,
    expected_os_uid: int,
    allowed_temp_path: str | None = None,
) -> PreparedEffectTarget:
    if type(expected_os_uid) is not int or expected_os_uid != os.getuid():
        raise GovernedPatchEffectError("effect supervisor OS uid is not current")
    try:
        candidate = verify_candidate_bundle(candidate)
    except Exception as exc:
        raise GovernedPatchEffectError("candidate bundle revalidation failed") from exc
    try:
        root = Path(scratch_worktree).resolve(strict=True)
        approved = Path(approved_scratch_root).resolve(strict=True)
        canonical = Path(trusted_canonical_repo).resolve(strict=True)
        candidate_repo = candidate.repo_root.resolve(strict=True)
    except OSError as exc:
        raise GovernedPatchEffectError("effect repository root is unavailable") from exc
    if candidate_repo != canonical:
        raise GovernedPatchEffectError("candidate repo is not supervisor-pinned canonical repo")
    if root == approved or not root.is_relative_to(approved):
        raise GovernedPatchEffectError("scratch is not beneath the pinned approved root")
    if root == canonical or root.is_relative_to(canonical):
        raise GovernedPatchEffectError("canonical/live checkout mutation is forbidden")
    approved_identity, root_identity, ancestry_sha256, custody_before = (
        _directory_custody(
            approved,
            root,
            candidate.authorized_source_path,
            expected_uid=expected_os_uid,
        )
    )
    marker = _read_marker(root, expected_uid=expected_os_uid)
    if marker.payload["git_base_sha"] != candidate.bindings.base_sha:
        raise GovernedPatchEffectError("scratch marker does not match candidate base")
    postimage = _postimage(candidate)
    observed = _read_target(
        root,
        candidate.authorized_source_path,
        expected_uid=expected_os_uid,
    )
    state = (
        "preimage"
        if observed.data == candidate.source_bytes
        else "postimage"
        if observed.data == postimage
        else "ambiguous"
    )
    try:
        git, repository = inspect_registered_worktree(
            root,
            canonical,
            executable_path=git_executable,
            base_sha=candidate.bindings.base_sha,
            source_path=candidate.authorized_source_path,
            target_state=state,
            allowed_temp_path=allowed_temp_path,
        )
    except EffectGitError as exc:
        raise GovernedPatchEffectError(str(exc)) from exc
    approved_after, root_after, ancestry_after, custody_after = _directory_custody(
        approved,
        root,
        candidate.authorized_source_path,
        expected_uid=expected_os_uid,
    )
    if (
        custody_after != custody_before
        or approved_after != approved_identity
        or root_after != root_identity
        or ancestry_after != ancestry_sha256
    ):
        raise GovernedPatchEffectError("effect directory custody changed during inspection")
    prepared = PreparedEffectTarget(
        candidate,
        root,
        approved,
        canonical,
        marker,
        git,
        repository,
        candidate.authorized_source_path,
        int(root_identity["device"]),
        int(root_identity["inode"]),
        int(root_identity["mode"]),
        int(root_identity["uid"]),
        int(root_identity["gid"]),
        int(approved_identity["device"]),
        int(approved_identity["inode"]),
        int(approved_identity["mode"]),
        int(approved_identity["uid"]),
        int(approved_identity["gid"]),
        ancestry_sha256,
        candidate.source_bytes,
        postimage,
        observed,
        "",
    )
    return replace(prepared, scratch_identity=prepared.to_binding().scratch_identity)


def inspect_effect_target(
    candidate: CandidateBundle,
    scratch_worktree: Path,
    *,
    approved_scratch_root: Path,
    trusted_canonical_repo: Path,
    git_executable: Path,
    expected_os_uid: int,
) -> ScratchTargetBinding:
    """Return one exact non-authorizing clean-preimage binding for issuance."""

    prepared = prepare_effect_target(
        candidate,
        scratch_worktree,
        approved_scratch_root=approved_scratch_root,
        trusted_canonical_repo=trusted_canonical_repo,
        git_executable=git_executable,
        expected_os_uid=expected_os_uid,
    )
    if prepared.target_state != "preimage":
        raise GovernedPatchEffectError("target inspection requires exact clean preimage")
    return prepared.to_binding()


__all__ = ["FileSnapshot", "GovernedPatchEffectError", "PreparedEffectTarget", "inspect_effect_target", "prepare_effect_target"]
