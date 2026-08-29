"""Cumulative, replay-verified Foundry artifact lineage.

Every promoted candidate stores both its per-cycle delta and a cumulative patch
from the immutable upstream base.  The manifest binds base tree, parent,
delta, cumulative bytes, and the replayed candidate tree.  A mismatch is a
terminal replication failure; callers must never silently reset to a clean
tree and continue claiming a compound campaign.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.oracle_evaluator import apply_diff
from dharma_swarm.foundry.target_ingest import compute_tree_digest

LINEAGE_SCHEMA = "foundry_artifact_lineage.v2"


class ArtifactReplayError(RuntimeError):
    """A promoted artifact cannot be reproduced from its declared base."""


class DuplicateArtifact(RuntimeError):
    """A candidate reproduces a cumulative artifact already evaluated."""


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


def _copy_tree(source: Path) -> Path:
    work = Path(tempfile.mkdtemp(prefix="foundry_lineage_"))
    shutil.rmtree(work)
    shutil.copytree(
        source,
        work,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"),
    )
    return work


def _cumulative_patch(base_root: Path, candidate_root: Path, evolve_file: str) -> str:
    base_path = base_root / evolve_file
    candidate_path = candidate_root / evolve_file
    if not base_path.is_file() or not candidate_path.is_file():
        raise ArtifactReplayError(f"evolve file missing during lineage build: {evolve_file}")
    try:
        base_lines = base_path.read_text(encoding="utf-8").splitlines(keepends=True)
        candidate_lines = candidate_path.read_text(encoding="utf-8").splitlines(keepends=True)
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
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ArtifactReplayError(f"content-address collision at {path}")


def verify_lineage(
    base_root: Path,
    manifest: dict[str, Any],
    *,
    artifact_path: Path,
    delta_path: Path | None = None,
    expected_parent_artifact_sha256: str | None = None,
) -> str:
    """Replay a cumulative patch from its exact base and verify the final tree."""
    required = {
        "schema_version",
        "base_tree_digest",
        "delta_sha256",
        "cumulative_sha256",
        "candidate_tree_digest",
        "evolve_file",
        "parent_artifact_sha256",
        "parent_candidate_tree_digest",
        "evaluator_id",
        "evaluator_config_digest",
        "evaluator_image_digest",
        "claimed_score",
        "score_observations",
        "score_repetitions",
        "score_coefficient_of_variation",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ArtifactReplayError(f"lineage manifest missing fields: {', '.join(missing)}")
    if manifest["schema_version"] != LINEAGE_SCHEMA:
        raise ArtifactReplayError(f"unsupported lineage schema: {manifest['schema_version']}")
    try:
        claimed_score = float(manifest["claimed_score"])
        observations = [float(value) for value in manifest["score_observations"]]
        repetitions = int(manifest["score_repetitions"])
        coefficient = float(manifest["score_coefficient_of_variation"])
    except (TypeError, ValueError) as exc:
        raise ArtifactReplayError("lineage score evidence is malformed") from exc
    if not observations or repetitions != len(observations) or repetitions < 2:
        raise ArtifactReplayError("lineage lacks repeated score observations")
    if any(not math.isfinite(value) for value in observations):
        raise ArtifactReplayError("lineage score observations are non-finite")
    mean_score = sum(observations) / len(observations)
    if abs(mean_score - claimed_score) > 1e-9:
        raise ArtifactReplayError("claimed score differs from repeated observations")
    if not math.isfinite(claimed_score) or not math.isfinite(mean_score):
        raise ArtifactReplayError("lineage claimed score is non-finite")
    if not math.isfinite(coefficient) or coefficient < 0:
        raise ArtifactReplayError("lineage score variance is invalid")
    image_digest = str(manifest["evaluator_image_digest"])
    if not image_digest.startswith("sha256:") or len(image_digest) != 71:
        raise ArtifactReplayError("lineage evaluator image is not digest-pinned")
    if not str(manifest["evaluator_id"]) or not str(manifest["evaluator_config_digest"]).startswith("sha256:"):
        raise ArtifactReplayError("lineage evaluator identity is incomplete")
    claimed_lineage = str(manifest.get("lineage_digest", ""))
    lineage_body = {
        key: value
        for key, value in manifest.items()
        if key not in {"lineage_digest", "manifest_path"}
    }
    if not claimed_lineage or canonical_digest(lineage_body) != claimed_lineage:
        raise ArtifactReplayError("lineage manifest digest mismatch")
    declared_parent = str(manifest.get("parent_artifact_sha256", ""))
    parent_tree = str(manifest.get("parent_candidate_tree_digest", ""))
    if bool(declared_parent) != bool(parent_tree):
        raise ArtifactReplayError("parent artifact/tree relation is incomplete")
    if (
        expected_parent_artifact_sha256 is not None
        and declared_parent != expected_parent_artifact_sha256
    ):
        raise ArtifactReplayError(
            "parent artifact relation mismatch: "
            f"expected={expected_parent_artifact_sha256 or 'genesis'} "
            f"actual={declared_parent or 'genesis'}"
        )
    evolve_file = str(manifest["evolve_file"])
    actual_base = compute_tree_digest(Path(base_root), [evolve_file])
    if actual_base != manifest["base_tree_digest"]:
        raise ArtifactReplayError(
            "seed base tree mismatch: "
            f"expected={manifest['base_tree_digest']} actual={actual_base}"
        )
    try:
        artifact_bytes = Path(artifact_path).read_bytes()
    except OSError as exc:
        raise ArtifactReplayError(f"cumulative artifact missing: {artifact_path}") from exc
    if sha256_bytes(artifact_bytes) != manifest["cumulative_sha256"]:
        raise ArtifactReplayError("cumulative artifact sha256 mismatch")
    if delta_path is None:
        foundry_root = Path(artifact_path).resolve().parent.parent
        raw_delta = Path(str(manifest.get("delta_artifact", "")))
        delta_path = raw_delta if raw_delta.is_absolute() else foundry_root / raw_delta
    try:
        delta_bytes = Path(delta_path).read_bytes()
    except OSError as exc:
        raise ArtifactReplayError(f"delta artifact missing: {delta_path}") from exc
    if sha256_bytes(delta_bytes) != manifest["delta_sha256"]:
        raise ArtifactReplayError("delta artifact sha256 mismatch")

    work = _copy_tree(Path(base_root))
    try:
        failure = apply_diff(work, artifact_bytes.decode("utf-8"))
        if failure is not None:
            raise ArtifactReplayError(f"cumulative artifact replay failed: {failure}")
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
    evaluator_id: str,
    evaluator_config_digest: str,
    evaluator_image_digest: str,
    claimed_score: float,
    score_observations: list[float] | tuple[float, ...],
    parent_artifact_sha256: str = "",
    parent_candidate_tree_digest: str = "",
    reject_cumulative_sha256: set[str] | None = None,
) -> dict[str, Any]:
    """Persist delta+cumulative+manifest only after an exact replay succeeds."""
    actual_base = compute_tree_digest(Path(base_root), [evolve_file])
    if actual_base != base_tree_digest:
        raise ArtifactReplayError(
            f"lineage base changed before build: expected={base_tree_digest} actual={actual_base}"
        )
    seeded_digest = compute_tree_digest(Path(seeded_root), [evolve_file])
    if parent_artifact_sha256:
        if not parent_candidate_tree_digest:
            raise ArtifactReplayError("authoritative parent lacks candidate tree digest")
        if seeded_digest != parent_candidate_tree_digest:
            raise ArtifactReplayError(
                "seeded tree does not match declared parent candidate tree"
            )
    elif parent_candidate_tree_digest:
        raise ArtifactReplayError("parent candidate tree declared without parent artifact")
    elif seeded_digest != base_tree_digest:
        raise ArtifactReplayError("genesis lineage seeded tree differs from immutable base")
    delta_bytes = delta.encode("utf-8")
    delta_sha = sha256_bytes(delta_bytes)
    candidate_root = _copy_tree(Path(seeded_root))
    try:
        failure = apply_diff(candidate_root, delta)
        if failure is not None:
            raise ArtifactReplayError(f"promoted delta failed to apply: {failure}")
        cumulative = _cumulative_patch(Path(base_root), candidate_root, evolve_file)
        cumulative_bytes = cumulative.encode("utf-8")
        cumulative_sha = sha256_bytes(cumulative_bytes)
        candidate_digest = compute_tree_digest(candidate_root, [evolve_file])
    finally:
        shutil.rmtree(candidate_root, ignore_errors=True)

    if reject_cumulative_sha256 and cumulative_sha in reject_cumulative_sha256:
        raise DuplicateArtifact(
            f"cumulative artifact {cumulative_sha} already has receipt evidence"
        )
    if isinstance(claimed_score, bool):
        raise ArtifactReplayError("claimed score must be numeric")
    observations = [float(value) for value in score_observations]
    if len(observations) < 2 or any(
        not math.isfinite(value) for value in observations
    ):
        raise ArtifactReplayError("promotion requires at least two finite score repetitions")
    mean_score = sum(observations) / len(observations)
    if not math.isfinite(mean_score) or not math.isfinite(float(claimed_score)) or abs(
        mean_score - float(claimed_score)
    ) > 1e-9:
        raise ArtifactReplayError("claimed score does not match repeated observations")
    if (
        not evaluator_id
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", evaluator_config_digest)
    ):
        raise ArtifactReplayError("evaluator identity/config digest required")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", evaluator_image_digest):
        raise ArtifactReplayError("immutable evaluator image digest required")
    if mean_score:
        try:
            variance = sum(
                (value - mean_score) ** 2 for value in observations
            ) / len(observations)
        except OverflowError as exc:
            raise ArtifactReplayError("score variance evidence overflowed") from exc
        coefficient = (variance ** 0.5) / abs(mean_score)
    else:
        if not all(value == 0 for value in observations):
            raise ArtifactReplayError(
                "score variance is undefined around a zero repeated mean"
            )
        coefficient = 0.0
    if not math.isfinite(variance if mean_score else 0.0) or not math.isfinite(coefficient):
        raise ArtifactReplayError("score variance evidence is non-finite")

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
        "parent_artifact_sha256": parent_artifact_sha256,
        "parent_candidate_tree_digest": parent_candidate_tree_digest,
        "delta_sha256": delta_sha,
        "cumulative_sha256": cumulative_sha,
        "candidate_tree_digest": candidate_digest,
        "evolve_file": evolve_file,
        "delta_artifact": str(delta_path.relative_to(foundry_root)),
        "cumulative_artifact": str(cumulative_path.relative_to(foundry_root)),
        "replay_verified": True,
        "evaluator_id": evaluator_id,
        "evaluator_config_digest": evaluator_config_digest,
        "evaluator_image_digest": evaluator_image_digest,
        "claimed_score": mean_score,
        "score_observations": observations,
        "score_repetitions": len(observations),
        "score_coefficient_of_variation": coefficient,
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
    # manifest_path is a locator, not part of the sealed lineage body.
    manifest_bytes = (
        json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    _write_immutable(manifest_path, manifest_bytes)
    verify_lineage(base_root, body, artifact_path=cumulative_path)
    return body
