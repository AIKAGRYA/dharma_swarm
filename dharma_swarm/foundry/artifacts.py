"""Immutable, cumulative, replay-verified Foundry artifact lineage.

Each promoted delta is preserved separately while a cumulative patch is rebuilt
from one immutable upstream base. The manifest binds the declared evolve-file
scope, parent relation, delta bytes, cumulative bytes, and replayed scoped tree.
It does not independently attest that the surrounding checkout came from the
declared commit. Benchmark validity, full-tree pin custody, and promotion remain
separate proof obligations.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.patches import PatchReplayError, apply_unified_diff
from dharma_swarm.foundry.target_ingest import compute_tree_digest

LINEAGE_SCHEMA = "foundry_artifact_lineage.v1"
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class ArtifactReplayError(RuntimeError):
    """A promoted artifact cannot be reproduced from its declared base."""


@dataclass(frozen=True)
class PriorArtifact:
    path: Path
    metric: float
    manifest_path: Path | None = None
    manifest: dict[str, Any] | None = None

    def __iter__(self):
        """Compatibility with the historic ``(path, metric)`` return shape."""
        yield self.path
        yield self.metric


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_canonical_digest(value: str) -> bool:
    return value.startswith("sha256:") and _HEX_64.fullmatch(value[7:]) is not None


def _read_regular(path: Path, *, field: str) -> bytes:
    """Read one non-symlink regular file through the descriptor we inspect."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ArtifactReplayError(f"{field} missing or unreadable: {path}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ArtifactReplayError(f"{field} is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def _safe_relative(value: object, *, field: str) -> str:
    text = str(value)
    if not text or text.startswith("/") or "\\" in text or "\x00" in text:
        raise ArtifactReplayError(f"unsafe {field}: {text!r}")
    path = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ArtifactReplayError(f"unsafe {field}: {text!r}")
    return path.as_posix()


def _scoped_file(root: Path, relative: str, *, field: str) -> Path:
    try:
        root = Path(root).resolve(strict=True)
    except OSError as exc:
        raise ArtifactReplayError(f"{field} root is unavailable: {root}") from exc
    safe = _safe_relative(relative, field=field)
    lexical = root / safe
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise ArtifactReplayError(f"{field} is unavailable: {safe}") from exc
    if not resolved.is_relative_to(root):
        raise ArtifactReplayError(f"{field} escapes declared root: {safe}")
    cursor = root
    for part in PurePosixPath(safe).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ArtifactReplayError(f"{field} traverses a symlink: {safe}")
    if not resolved.is_file():
        raise ArtifactReplayError(f"{field} is not a regular file: {safe}")
    return resolved


def _copy_tree(source: Path) -> Path:
    work = Path(tempfile.mkdtemp(prefix="foundry-lineage-"))
    shutil.rmtree(work)
    shutil.copytree(
        source,
        work,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"),
    )
    return work


def _cumulative_patch(base_root: Path, candidate_root: Path, evolve_file: str) -> str:
    base_path = _scoped_file(base_root, evolve_file, field="base evolve file")
    candidate_path = _scoped_file(candidate_root, evolve_file, field="candidate evolve file")
    try:
        with base_path.open("r", encoding="utf-8", newline="") as handle:
            base_lines = handle.readlines()
        with candidate_path.open("r", encoding="utf-8", newline="") as handle:
            candidate_lines = handle.readlines()
    except UnicodeDecodeError as exc:
        raise ArtifactReplayError("binary evolve files are unsupported") from exc
    patch = "".join(
        difflib.unified_diff(
            base_lines,
            candidate_lines,
            fromfile=f"a/{evolve_file}",
            tofile=f"b/{evolve_file}",
        )
    )
    if not patch:
        raise ArtifactReplayError("promoted candidate is identical to immutable base")
    return patch if patch.endswith("\n") else patch + "\n"


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if not path.is_file() or path.is_symlink() or path.read_bytes() != data:
            raise ArtifactReplayError(f"content-address collision at {path}")


def _manifest_locator(root: Path, value: object, *, field: str) -> Path:
    relative = _safe_relative(value, field=field)
    root = root.resolve(strict=True)
    lexical = root / relative
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ArtifactReplayError(f"{field} traverses a symlink: {relative}")
    candidate = lexical.resolve(strict=False)
    if not candidate.is_relative_to(root):
        raise ArtifactReplayError(f"{field} escapes artifact root: {relative}")
    return lexical


def _verify_delta_relation(
    *,
    base_root: Path,
    artifact_root: Path,
    evolve_file: str,
    delta_bytes: bytes,
    parent_artifact_sha256: str,
    parent_candidate_tree_digest: str,
    candidate_tree_digest: str,
) -> None:
    """Prove that the delta transforms its declared parent into the candidate."""
    work = _copy_tree(base_root)
    try:
        if parent_artifact_sha256:
            parent_path = _manifest_locator(
                artifact_root,
                f"artifacts/{parent_artifact_sha256}.patch",
                field="parent_artifact",
            )
            parent_bytes = _read_regular(parent_path, field="parent artifact")
            if sha256_bytes(parent_bytes) != parent_artifact_sha256:
                raise ArtifactReplayError("parent artifact sha256 mismatch")
            try:
                apply_unified_diff(
                    work,
                    parent_bytes.decode("utf-8"),
                    allowed_paths=[evolve_file],
                )
            except (PatchReplayError, UnicodeDecodeError) as exc:
                raise ArtifactReplayError(f"parent artifact replay failed: {exc}") from exc
            actual_parent = compute_tree_digest(work, [evolve_file])
            if actual_parent != parent_candidate_tree_digest:
                raise ArtifactReplayError(
                    "replayed parent tree mismatch: "
                    f"expected={parent_candidate_tree_digest} actual={actual_parent}"
                )
        try:
            apply_unified_diff(
                work,
                delta_bytes.decode("utf-8"),
                allowed_paths=[evolve_file],
            )
        except (PatchReplayError, UnicodeDecodeError) as exc:
            raise ArtifactReplayError(f"delta artifact replay failed: {exc}") from exc
        actual_candidate = compute_tree_digest(work, [evolve_file])
        if actual_candidate != candidate_tree_digest:
            raise ArtifactReplayError(
                "delta replay candidate mismatch: "
                f"expected={candidate_tree_digest} actual={actual_candidate}"
            )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def verify_lineage(
    base_root: Path,
    manifest: dict[str, Any],
    *,
    artifact_path: Path,
    delta_path: Path | None = None,
    expected_parent_artifact_sha256: str | None = None,
) -> str:
    """Replay a cumulative patch and verify the final declared evolve-file tree."""
    required = {
        "schema_version",
        "target_id",
        "resolved_sha",
        "base_tree_digest",
        "delta_sha256",
        "cumulative_sha256",
        "candidate_tree_digest",
        "evolve_file",
        "parent_lineage_digest",
        "parent_artifact_sha256",
        "parent_candidate_tree_digest",
        "delta_artifact",
        "cumulative_artifact",
        "replay_verified",
        "lineage_digest",
        "manifest_path",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ArtifactReplayError(f"lineage manifest missing fields: {', '.join(missing)}")
    if manifest["schema_version"] != LINEAGE_SCHEMA:
        raise ArtifactReplayError(f"unsupported lineage schema: {manifest['schema_version']}")
    if not str(manifest["target_id"]).strip():
        raise ArtifactReplayError("lineage target_id is empty")
    if _HEX_40.fullmatch(str(manifest["resolved_sha"])) is None:
        raise ArtifactReplayError("lineage resolved_sha is not an exact commit")
    if manifest["replay_verified"] is not True:
        raise ArtifactReplayError("lineage does not claim a completed local replay")
    for field in ("delta_sha256", "cumulative_sha256"):
        if _HEX_64.fullmatch(str(manifest[field])) is None:
            raise ArtifactReplayError(f"lineage {field} is malformed")
    expected_delta_locator = f"artifacts/deltas/{manifest['delta_sha256']}.patch"
    expected_cumulative_locator = f"artifacts/{manifest['cumulative_sha256']}.patch"
    if manifest["delta_artifact"] != expected_delta_locator:
        raise ArtifactReplayError("delta artifact locator is not its canonical content address")
    if manifest["cumulative_artifact"] != expected_cumulative_locator:
        raise ArtifactReplayError("cumulative artifact locator is not its canonical content address")

    claimed_lineage = str(manifest.get("lineage_digest", ""))
    lineage_body = {
        key: value
        for key, value in manifest.items()
        if key not in {"lineage_digest", "manifest_path"}
    }
    if not claimed_lineage or canonical_digest(lineage_body) != claimed_lineage:
        raise ArtifactReplayError("lineage manifest digest mismatch")
    expected_manifest_locator = f"artifacts/manifests/{claimed_lineage[7:]}.json"
    if manifest["manifest_path"] != expected_manifest_locator:
        raise ArtifactReplayError(
            "manifest locator is not its canonical lineage address"
        )
    declared_parent = str(manifest["parent_artifact_sha256"])
    parent_tree = str(manifest["parent_candidate_tree_digest"])
    parent_lineage = str(manifest["parent_lineage_digest"])
    if len({bool(declared_parent), bool(parent_tree), bool(parent_lineage)}) != 1:
        raise ArtifactReplayError("parent manifest/artifact/tree relation is incomplete")
    if parent_lineage and not _is_canonical_digest(parent_lineage):
        raise ArtifactReplayError("parent lineage digest is malformed")
    if declared_parent and _HEX_64.fullmatch(declared_parent) is None:
        raise ArtifactReplayError("parent artifact sha256 is malformed")
    candidate_tree = str(manifest["candidate_tree_digest"])
    if declared_parent and candidate_tree == parent_tree:
        raise ArtifactReplayError("lineage candidate does not advance its declared parent")
    if not declared_parent and candidate_tree == str(manifest["base_tree_digest"]):
        raise ArtifactReplayError("genesis lineage candidate is identical to its base")
    if (
        expected_parent_artifact_sha256 is not None
        and declared_parent != expected_parent_artifact_sha256
    ):
        raise ArtifactReplayError(
            "parent artifact relation mismatch: "
            f"expected={expected_parent_artifact_sha256 or 'genesis'} "
            f"actual={declared_parent or 'genesis'}"
        )

    evolve_file = _safe_relative(manifest["evolve_file"], field="evolve_file")
    _scoped_file(Path(base_root), evolve_file, field="base evolve file")
    actual_base = compute_tree_digest(Path(base_root), [evolve_file])
    if actual_base != manifest["base_tree_digest"]:
        raise ArtifactReplayError(
            "seed base tree mismatch: "
            f"expected={manifest['base_tree_digest']} actual={actual_base}"
        )
    artifact_path = Path(artifact_path)
    if artifact_path.is_symlink():
        raise ArtifactReplayError("cumulative artifact must not be a symlink")
    artifact_root = artifact_path.parent.parent
    declared_cumulative = _manifest_locator(artifact_root, manifest["cumulative_artifact"], field="cumulative_artifact")
    if declared_cumulative.resolve(strict=False) != artifact_path.resolve(strict=False):
        raise ArtifactReplayError("cumulative artifact locator mismatch")
    artifact_bytes = _read_regular(artifact_path, field="cumulative artifact")
    if sha256_bytes(artifact_bytes) != manifest["cumulative_sha256"]:
        raise ArtifactReplayError("cumulative artifact sha256 mismatch")
    if parent_lineage:
        parent_manifest_path = _manifest_locator(
            artifact_root,
            f"artifacts/manifests/{parent_lineage[7:]}.json",
            field="parent_manifest",
        )
        try:
            parent_manifest = json.loads(_read_regular(parent_manifest_path, field="parent manifest"))
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            raise ArtifactReplayError("parent manifest missing or unreadable") from exc
        if not isinstance(parent_manifest, dict):
            raise ArtifactReplayError("parent manifest is not an object")
        if parent_manifest.get("lineage_digest") != parent_lineage:
            raise ArtifactReplayError("parent manifest lineage digest mismatch")
        for field in ("target_id", "resolved_sha", "base_tree_digest", "evolve_file"):
            if parent_manifest.get(field) != manifest[field]:
                raise ArtifactReplayError(f"parent manifest {field} mismatch")
        if parent_manifest.get("cumulative_sha256") != declared_parent:
            raise ArtifactReplayError("parent manifest cumulative artifact mismatch")
        if parent_manifest.get("candidate_tree_digest") != parent_tree:
            raise ArtifactReplayError("parent manifest candidate tree mismatch")
        if parent_manifest.get("replay_verified") is not True:
            raise ArtifactReplayError("parent manifest lacks verified replay")
        parent_artifact = _manifest_locator(
            artifact_root, parent_manifest.get("cumulative_artifact", ""), field="parent cumulative artifact"
        )
        verify_lineage(base_root, parent_manifest, artifact_path=parent_artifact)
    declared_delta = _manifest_locator(
        artifact_root, manifest["delta_artifact"], field="delta_artifact"
    )
    if delta_path is None:
        delta_path = declared_delta
    else:
        delta_path = Path(delta_path)
        if delta_path.is_symlink():
            raise ArtifactReplayError("delta artifact must not be a symlink")
        if delta_path.resolve(strict=False) != declared_delta.resolve(strict=False):
            raise ArtifactReplayError("delta artifact locator mismatch")
    delta_bytes = _read_regular(Path(delta_path), field="delta artifact")
    if sha256_bytes(delta_bytes) != manifest["delta_sha256"]:
        raise ArtifactReplayError("delta artifact sha256 mismatch")
    _verify_delta_relation(
        base_root=Path(base_root),
        artifact_root=artifact_root,
        evolve_file=evolve_file,
        delta_bytes=delta_bytes,
        parent_artifact_sha256=declared_parent,
        parent_candidate_tree_digest=parent_tree,
        candidate_tree_digest=str(manifest["candidate_tree_digest"]),
    )

    work = _copy_tree(Path(base_root))
    try:
        try:
            apply_unified_diff(
                work,
                artifact_bytes.decode("utf-8"),
                allowed_paths=[evolve_file],
            )
        except (PatchReplayError, UnicodeDecodeError) as exc:
            raise ArtifactReplayError(f"cumulative artifact replay failed: {exc}") from exc
        actual_candidate = compute_tree_digest(work, [evolve_file])
        if actual_candidate != manifest["candidate_tree_digest"]:
            raise ArtifactReplayError(
                "replayed candidate tree mismatch: "
                f"expected={manifest['candidate_tree_digest']} actual={actual_candidate}"
            )
        return actual_candidate
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_lineage(
    *,
    state_root: Path,
    target_id: str,
    resolved_sha: str,
    base_root: Path,
    seeded_root: Path,
    base_tree_digest: str,
    evolve_file: str,
    delta: str,
    parent_lineage_digest: str = "",
    parent_artifact_sha256: str = "",
    parent_candidate_tree_digest: str = "",
) -> dict[str, Any]:
    """Persist delta, cumulative patch, and manifest after exact replay."""
    if not target_id.strip():
        raise ArtifactReplayError("target_id must be non-empty")
    if _HEX_40.fullmatch(resolved_sha) is None:
        raise ArtifactReplayError("resolved_sha must be an exact lowercase commit")
    evolve_file = _safe_relative(evolve_file, field="evolve_file")
    _scoped_file(Path(base_root), evolve_file, field="base evolve file")
    _scoped_file(Path(seeded_root), evolve_file, field="seeded evolve file")
    actual_base = compute_tree_digest(Path(base_root), [evolve_file])
    if actual_base != base_tree_digest:
        raise ArtifactReplayError(
            f"lineage base changed before build: expected={base_tree_digest} actual={actual_base}"
        )
    seeded_digest = compute_tree_digest(Path(seeded_root), [evolve_file])
    parent_fields = (parent_lineage_digest, parent_artifact_sha256, parent_candidate_tree_digest)
    if any(parent_fields) and not all(parent_fields):
        raise ArtifactReplayError("parent manifest/artifact/tree relation is incomplete")
    if parent_lineage_digest and not _is_canonical_digest(parent_lineage_digest):
        raise ArtifactReplayError("parent lineage digest is malformed")
    if parent_artifact_sha256:
        if _HEX_64.fullmatch(parent_artifact_sha256) is None:
            raise ArtifactReplayError("parent artifact sha256 is malformed")
        if not parent_candidate_tree_digest:
            raise ArtifactReplayError("authoritative parent lacks candidate tree digest")
        if seeded_digest != parent_candidate_tree_digest:
            raise ArtifactReplayError("seeded tree does not match declared parent candidate tree")
    elif parent_candidate_tree_digest:
        raise ArtifactReplayError("parent candidate tree declared without parent artifact")
    elif seeded_digest != base_tree_digest:
        raise ArtifactReplayError("genesis lineage seeded tree differs from immutable base")

    delta_bytes = delta.encode("utf-8")
    delta_sha = sha256_bytes(delta_bytes)
    candidate_root = _copy_tree(Path(seeded_root))
    try:
        try:
            apply_unified_diff(candidate_root, delta, allowed_paths=[evolve_file])
        except PatchReplayError as exc:
            raise ArtifactReplayError(f"promoted delta failed to apply: {exc}") from exc
        candidate_digest = compute_tree_digest(candidate_root, [evolve_file])
        if candidate_digest == seeded_digest:
            raise ArtifactReplayError("promoted delta is a no-op against its seeded parent")
        cumulative = _cumulative_patch(Path(base_root), candidate_root, evolve_file)
        cumulative_bytes = cumulative.encode("utf-8")
        cumulative_sha = sha256_bytes(cumulative_bytes)
    finally:
        shutil.rmtree(candidate_root, ignore_errors=True)

    foundry_root = Path(state_root)
    delta_path = foundry_root / "artifacts" / "deltas" / f"{delta_sha}.patch"
    cumulative_path = foundry_root / "artifacts" / f"{cumulative_sha}.patch"
    _write_immutable(delta_path, delta_bytes)
    _write_immutable(cumulative_path, cumulative_bytes)

    body: dict[str, Any] = {
        "schema_version": LINEAGE_SCHEMA,
        "target_id": target_id,
        "resolved_sha": resolved_sha,
        "base_tree_digest": base_tree_digest,
        "parent_lineage_digest": parent_lineage_digest,
        "parent_artifact_sha256": parent_artifact_sha256,
        "parent_candidate_tree_digest": parent_candidate_tree_digest,
        "delta_sha256": delta_sha,
        "cumulative_sha256": cumulative_sha,
        "candidate_tree_digest": candidate_digest,
        "evolve_file": evolve_file,
        "delta_artifact": str(delta_path.relative_to(foundry_root)),
        "cumulative_artifact": str(cumulative_path.relative_to(foundry_root)),
        "replay_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body["lineage_digest"] = canonical_digest(body)
    manifest_path = (
        foundry_root
        / "artifacts"
        / "manifests"
        / f"{body['lineage_digest'].removeprefix('sha256:')}.json"
    )
    body["manifest_path"] = str(manifest_path.relative_to(foundry_root))
    manifest_bytes = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
    verify_lineage(base_root, body, artifact_path=cumulative_path)
    # Publish the claim only after its parent, delta, and cumulative replay all
    # verify. A failed build may leave harmless content-addressed patch blobs,
    # but it must never leave a manifest claiming ``replay_verified=true``.
    _write_immutable(manifest_path, manifest_bytes)
    return body
