"""Regression tests for cumulative, replay-verified artifact lineage."""

from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path

import pytest

from dharma_swarm.foundry.artifacts import (
    ArtifactReplayError,
    build_lineage,
    sha256_bytes,
    verify_lineage,
)
from dharma_swarm.foundry.evaluator import canonical_digest
from dharma_swarm.foundry.patches import apply_unified_diff
from dharma_swarm.foundry.target_ingest import compute_tree_digest

PIN = "a" * 40


def _patch(old: str, new: str, path: str = "src/value.py") -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _tree(root: Path, value: int) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "value.py").write_text(f"VALUE = {value}\n", encoding="utf-8")


def _first_lineage(tmp_path: Path) -> tuple[Path, Path, dict]:
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    lineage = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha=PIN,
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
        evolve_file="src/value.py",
        delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
    )
    return base, seeded, lineage


def _child_lineage(
    tmp_path: Path, base: Path, parent: dict, *, value: int = 3
) -> dict:
    seeded = tmp_path / f"seeded-{value}"
    shutil.copytree(base, seeded)
    apply_unified_diff(
        seeded,
        (tmp_path / "state" / parent["cumulative_artifact"]).read_text(),
        allowed_paths=["src/value.py"],
    )
    return build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha=PIN,
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
        evolve_file="src/value.py",
        delta=_patch(f"VALUE = {value - 1}\n", f"VALUE = {value}\n"),
        parent_lineage_digest=parent["lineage_digest"],
        parent_artifact_sha256=parent["cumulative_sha256"],
        parent_candidate_tree_digest=parent["candidate_tree_digest"],
    )


def _reseal(manifest: dict) -> dict:
    body = {
        key: value
        for key, value in manifest.items()
        if key not in {"lineage_digest", "manifest_path"}
    }
    manifest["lineage_digest"] = canonical_digest(body)
    manifest["manifest_path"] = (
        f"artifacts/manifests/{manifest['lineage_digest'][7:]}.json"
    )
    return manifest


def test_two_deltas_form_cumulative_lineage_and_replay(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    assert first["parent_artifact_sha256"] == ""
    assert first["delta_sha256"] == first["cumulative_sha256"]
    assert first["replay_verified"] is True

    second = _child_lineage(tmp_path, base, first)

    assert second["parent_artifact_sha256"] == first["cumulative_sha256"]
    assert second["delta_sha256"] != second["cumulative_sha256"]
    second_artifact = tmp_path / "state" / second["cumulative_artifact"]
    verify_lineage(
        base,
        second,
        artifact_path=second_artifact,
        expected_parent_artifact_sha256=first["cumulative_sha256"],
    )
    replay = tmp_path / "replay"
    shutil.copytree(base, replay)
    apply_unified_diff(
        replay,
        second_artifact.read_text(encoding="utf-8"),
        allowed_paths=["src/value.py"],
    )
    assert (replay / "src" / "value.py").read_text(encoding="utf-8") == "VALUE = 3\n"
    manifest = json.loads((tmp_path / "state" / second["manifest_path"]).read_text())
    assert manifest == second


def test_replay_fails_when_seed_base_does_not_match(tmp_path):
    base, _, lineage = _first_lineage(tmp_path)
    (base / "src" / "value.py").write_text("VALUE = 999\n", encoding="utf-8")
    with pytest.raises(ArtifactReplayError, match="seed base tree mismatch"):
        verify_lineage(
            base,
            lineage,
            artifact_path=tmp_path / "state" / lineage["cumulative_artifact"],
        )


def test_replay_fails_on_cumulative_artifact_byte_mismatch(tmp_path):
    base, _, lineage = _first_lineage(tmp_path)
    artifact = tmp_path / "state" / lineage["cumulative_artifact"]
    artifact.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ArtifactReplayError, match="cumulative artifact sha256 mismatch"):
        verify_lineage(base, lineage, artifact_path=artifact)


def test_parent_relation_and_delta_bytes_are_cryptographically_checked(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    base_digest = compute_tree_digest(base, ["src/value.py"])
    with pytest.raises(ArtifactReplayError, match="seeded tree does not match"):
        build_lineage(
            state_root=tmp_path / "state",
            target_id="target",
            resolved_sha=PIN,
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=base_digest,
            evolve_file="src/value.py",
            delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
            parent_lineage_digest="sha256:" + "f" * 64,
            parent_artifact_sha256="f" * 64,
            parent_candidate_tree_digest="sha256:not-the-seeded-tree",
        )

    lineage = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha=PIN,
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=base_digest,
        evolve_file="src/value.py",
        delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
    )
    delta = tmp_path / "state" / lineage["delta_artifact"]
    delta.write_text("tampered delta\n", encoding="utf-8")
    with pytest.raises(ArtifactReplayError, match="delta artifact sha256 mismatch"):
        verify_lineage(
            base,
            lineage,
            artifact_path=tmp_path / "state" / lineage["cumulative_artifact"],
            delta_path=delta,
        )


def test_orphan_parent_patch_cannot_publish_child_manifest(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    state = tmp_path / "state"
    seeded = tmp_path / "seeded-orphan-child"
    shutil.copytree(base, seeded)
    apply_unified_diff(
        seeded,
        (state / first["cumulative_artifact"]).read_text(encoding="utf-8"),
        allowed_paths=["src/value.py"],
    )
    (state / first["manifest_path"]).unlink()
    assert (state / first["cumulative_artifact"]).is_file()

    with pytest.raises(ArtifactReplayError, match="parent manifest missing"):
        build_lineage(
            state_root=state,
            target_id="target",
            resolved_sha=PIN,
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
            evolve_file="src/value.py",
            delta=_patch("VALUE = 2\n", "VALUE = 3\n"),
            parent_lineage_digest=first["lineage_digest"],
            parent_artifact_sha256=first["cumulative_sha256"],
            parent_candidate_tree_digest=first["candidate_tree_digest"],
        )
    manifests = state / "artifacts" / "manifests"
    assert not manifests.exists() or not list(manifests.iterdir())


def test_verifier_rejects_child_after_parent_manifest_disappears(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    second = _child_lineage(tmp_path, base, first)
    state = tmp_path / "state"
    (state / first["manifest_path"]).unlink()
    with pytest.raises(ArtifactReplayError, match="parent manifest missing"):
        verify_lineage(base, second, artifact_path=state / second["cumulative_artifact"])


def test_verifier_iteratively_requires_every_parent_manifest(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    second = _child_lineage(tmp_path, base, first)
    third = _child_lineage(tmp_path, base, second, value=4)
    state = tmp_path / "state"
    (state / first["manifest_path"]).unlink()
    with pytest.raises(ArtifactReplayError, match="parent manifest missing"):
        verify_lineage(base, third, artifact_path=state / third["cumulative_artifact"])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("target_id", "other-target", "target_id mismatch"),
        ("resolved_sha", "b" * 40, "resolved_sha mismatch"),
        ("base_tree_digest", "sha256:" + "0" * 64, "base_tree_digest mismatch"),
        ("evolve_file", "other.py", "evolve_file mismatch"),
        ("cumulative_sha256", "f" * 64, "cumulative artifact mismatch"),
        ("candidate_tree_digest", "sha256:" + "f" * 64, "candidate tree mismatch"),
        ("replay_verified", False, "lacks verified replay"),
    ],
)
def test_parent_manifest_identity_must_match_child(tmp_path, field, value, message):
    base, _, first = _first_lineage(tmp_path)
    second = _child_lineage(tmp_path, base, first)
    state = tmp_path / "state"
    forged_parent = _reseal({**first, field: value})
    (state / forged_parent["manifest_path"]).write_text(
        json.dumps(forged_parent), encoding="utf-8"
    )
    forged_child = _reseal(
        {**second, "parent_lineage_digest": forged_parent["lineage_digest"]}
    )
    with pytest.raises(ArtifactReplayError, match=message):
        verify_lineage(
            base, forged_child,
            artifact_path=state / forged_child["cumulative_artifact"],
        )


def test_parent_manifest_digest_is_verified(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    second = _child_lineage(tmp_path, base, first)
    state = tmp_path / "state"
    parent_path = state / first["manifest_path"]
    tampered = {**first, "created_at": "tampered-after-publication"}
    parent_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ArtifactReplayError, match="manifest digest mismatch"):
        verify_lineage(base, second, artifact_path=state / second["cumulative_artifact"])


def test_hidden_structural_delta_cannot_publish_lineage(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    state = tmp_path / "state"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    hidden_rename = (
        "diff --git a/grader.py b/grader-renamed.py\n"
        "similarity index 100%\n"
        "rename from grader.py\n"
        "rename to grader-renamed.py\n"
        + _patch("VALUE = 1\n", "VALUE = 2\n")
    )
    with pytest.raises(ArtifactReplayError, match="structural patch preamble"):
        build_lineage(
            state_root=state,
            target_id="target",
            resolved_sha=PIN,
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
            evolve_file="src/value.py",
            delta=hidden_rename,
        )
    assert list((state / "artifacts" / "manifests").glob("*.json")) == []

def test_non_genesis_delta_cannot_publish_an_identical_parent(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    seeded = tmp_path / "seeded-two"
    shutil.copytree(base, seeded)
    apply_unified_diff(
        seeded,
        (tmp_path / "state" / first["cumulative_artifact"]).read_text(
            encoding="utf-8"
        ),
        allowed_paths=["src/value.py"],
    )
    manifests = tmp_path / "state" / "artifacts" / "manifests"
    before = sorted(manifests.iterdir())
    same_content = (
        "--- a/src/value.py\n"
        "+++ b/src/value.py\n"
        "@@ -1 +1 @@\n"
        "-VALUE = 2\n"
        "+VALUE = 2\n"
    )

    with pytest.raises(ArtifactReplayError, match="no-op against its seeded parent"):
        build_lineage(
            state_root=tmp_path / "state",
            target_id="target",
            resolved_sha=PIN,
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
            evolve_file="src/value.py",
            delta=same_content,
            parent_lineage_digest=first["lineage_digest"],
            parent_artifact_sha256=first["cumulative_sha256"],
            parent_candidate_tree_digest=first["candidate_tree_digest"],
        )
    assert sorted(manifests.iterdir()) == before


def test_verifier_rejects_forged_non_advancing_parent_delta(tmp_path):
    base, _, first = _first_lineage(tmp_path)
    state = tmp_path / "state"
    same_content = (
        "--- a/src/value.py\n"
        "+++ b/src/value.py\n"
        "@@ -1 +1 @@\n"
        "-VALUE = 2\n"
        "+VALUE = 2\n"
    ).encode("utf-8")
    delta_sha = sha256_bytes(same_content)
    delta_path = state / "artifacts" / "deltas" / f"{delta_sha}.patch"
    delta_path.write_bytes(same_content)
    forged = {
        **first,
        "parent_lineage_digest": first["lineage_digest"],
        "parent_artifact_sha256": first["cumulative_sha256"],
        "parent_candidate_tree_digest": first["candidate_tree_digest"],
        "delta_sha256": delta_sha,
        "delta_artifact": f"artifacts/deltas/{delta_sha}.patch",
    }
    _reseal(forged)
    with pytest.raises(ArtifactReplayError, match="does not advance"):
        verify_lineage(
            base,
            forged,
            artifact_path=state / first["cumulative_artifact"],
        )


def test_delta_must_semantically_transform_parent_into_candidate(tmp_path):
    base, _, lineage = _first_lineage(tmp_path)
    state = tmp_path / "state"
    unrelated = _patch("VALUE = 1\n", "VALUE = 3\n").encode("utf-8")
    unrelated_digest = sha256_bytes(unrelated)
    unrelated_delta = state / "artifacts" / "deltas" / f"{unrelated_digest}.patch"
    unrelated_delta.write_bytes(unrelated)
    lineage["delta_sha256"] = unrelated_digest
    lineage["delta_artifact"] = (
        f"artifacts/deltas/{unrelated_digest}.patch"
    )
    _reseal(lineage)
    with pytest.raises(ArtifactReplayError, match="delta replay candidate mismatch"):
        verify_lineage(
            base,
            lineage,
            artifact_path=tmp_path / "state" / lineage["cumulative_artifact"],
        )


def test_verifier_rejects_alternate_or_symlinked_artifact_locators(tmp_path):
    base, _, lineage = _first_lineage(tmp_path)
    artifact = tmp_path / "state" / lineage["cumulative_artifact"]
    delta = tmp_path / "state" / lineage["delta_artifact"]
    alternate = tmp_path / "alternate.patch"
    alternate.write_bytes(delta.read_bytes())
    with pytest.raises(ArtifactReplayError, match="delta artifact locator mismatch"):
        verify_lineage(
            base,
            lineage,
            artifact_path=artifact,
            delta_path=alternate,
        )

    linked_artifact = tmp_path / "linked.patch"
    linked_artifact.symlink_to(artifact)
    with pytest.raises(ArtifactReplayError, match="must not be a symlink"):
        verify_lineage(base, lineage, artifact_path=linked_artifact)

    facade = tmp_path / "facade"
    facade.mkdir()
    (facade / "artifacts").symlink_to(artifact.parent)
    with pytest.raises(ArtifactReplayError, match="traverses a symlink"):
        verify_lineage(base, lineage, artifact_path=facade / lineage["cumulative_artifact"])


def test_verifier_requires_canonical_content_addressed_locator(tmp_path):
    base, _, lineage = _first_lineage(tmp_path)
    state = tmp_path / "state"
    canonical = state / lineage["cumulative_artifact"]
    renamed = state / "mutable" / "renamed.patch"
    renamed.parent.mkdir()
    renamed.write_bytes(canonical.read_bytes())
    forged = {**lineage, "cumulative_artifact": "mutable/renamed.patch"}
    lineage_body = {
        key: value
        for key, value in forged.items()
        if key not in {"lineage_digest", "manifest_path"}
    }
    forged["lineage_digest"] = canonical_digest(lineage_body)
    with pytest.raises(ArtifactReplayError, match="canonical content address"):
        verify_lineage(base, forged, artifact_path=renamed)


def test_manifest_locator_is_required_and_derived_from_lineage_digest(tmp_path):
    base, _, lineage = _first_lineage(tmp_path)
    artifact = tmp_path / "state" / lineage["cumulative_artifact"]

    forged = {**lineage, "manifest_path": "../../attacker-controlled.json"}
    with pytest.raises(ArtifactReplayError, match="canonical lineage address"):
        verify_lineage(base, forged, artifact_path=artifact)

    missing = dict(lineage)
    missing.pop("manifest_path")
    with pytest.raises(ArtifactReplayError, match="missing fields: manifest_path"):
        verify_lineage(base, missing, artifact_path=artifact)


def test_lineage_rejects_unpinned_sha_and_locator_escape(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    with pytest.raises(ArtifactReplayError, match="resolved_sha"):
        build_lineage(
            state_root=tmp_path / "state",
            target_id="target",
            resolved_sha="abc123",
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
            evolve_file="src/value.py",
            delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
        )

    _, _, lineage = _first_lineage(tmp_path / "valid")
    lineage["delta_artifact"] = "../escape.patch"
    lineage_body = {
        key: value
        for key, value in lineage.items()
        if key not in {"lineage_digest", "manifest_path"}
    }
    lineage["lineage_digest"] = canonical_digest(lineage_body)
    with pytest.raises(ArtifactReplayError, match="canonical content address"):
        verify_lineage(
            tmp_path / "valid" / "base",
            lineage,
            artifact_path=(
                tmp_path / "valid" / "state" / lineage["cumulative_artifact"]
            ),
        )


def test_lineage_rejects_missing_base_as_typed_failure(tmp_path):
    seeded = tmp_path / "seeded"
    _tree(seeded, 1)
    with pytest.raises(ArtifactReplayError, match="base evolve file root is unavailable"):
        build_lineage(
            state_root=tmp_path / "state",
            target_id="target",
            resolved_sha=PIN,
            base_root=tmp_path / "missing-base",
            seeded_root=seeded,
            base_tree_digest="sha256:" + "0" * 64,
            evolve_file="src/value.py",
            delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
        )
