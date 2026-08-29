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
    verify_lineage,
)
from dharma_swarm.foundry.oracle_evaluator import apply_diff
from dharma_swarm.foundry.target_ingest import compute_tree_digest

_EVIDENCE = {
    "evaluator_id": "test-evaluator",
    "evaluator_config_digest": "sha256:" + "c" * 64,
    "evaluator_image_digest": "sha256:" + "d" * 64,
    "claimed_score": 2.0,
    "score_observations": [2.0, 2.0],
}


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


def test_two_deltas_form_cumulative_lineage_and_replay(tmp_path):
    base = tmp_path / "base"
    seeded_one = tmp_path / "seeded-one"
    _tree(base, 1)
    shutil.copytree(base, seeded_one)
    base_digest = compute_tree_digest(base, ["src/value.py"])

    first = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha="abc123",
        base_root=base,
        seeded_root=seeded_one,
        base_tree_digest=base_digest,
        evolve_file="src/value.py",
        delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
        **_EVIDENCE,
    )
    assert first["parent_artifact_sha256"] == ""
    assert first["delta_sha256"] == first["cumulative_sha256"]
    assert first["replay_verified"] is True

    seeded_two = tmp_path / "seeded-two"
    shutil.copytree(base, seeded_two)
    first_artifact = tmp_path / "state" / first["cumulative_artifact"]
    assert apply_diff(seeded_two, first_artifact.read_text()) is None
    second = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha="abc123",
        base_root=base,
        seeded_root=seeded_two,
        base_tree_digest=base_digest,
        evolve_file="src/value.py",
        delta=_patch("VALUE = 2\n", "VALUE = 3\n"),
        **_EVIDENCE,
        parent_artifact_sha256=first["cumulative_sha256"],
        parent_candidate_tree_digest=first["candidate_tree_digest"],
    )

    assert second["parent_artifact_sha256"] == first["cumulative_sha256"]
    assert second["delta_sha256"] != second["cumulative_sha256"]
    second_artifact = tmp_path / "state" / second["cumulative_artifact"]
    verify_lineage(base, second, artifact_path=second_artifact)
    replay = tmp_path / "replay"
    shutil.copytree(base, replay)
    assert apply_diff(replay, second_artifact.read_text()) is None
    assert (replay / "src" / "value.py").read_text() == "VALUE = 3\n"
    manifest = json.loads((tmp_path / "state" / second["manifest_path"]).read_text())
    assert manifest == second


def test_replay_fails_when_seed_base_does_not_match(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    lineage = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha="abc123",
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
        evolve_file="src/value.py",
        delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
        **_EVIDENCE,
    )
    (base / "src" / "value.py").write_text("VALUE = 999\n", encoding="utf-8")
    with pytest.raises(ArtifactReplayError, match="seed base tree mismatch"):
        verify_lineage(
            base,
            lineage,
            artifact_path=tmp_path / "state" / lineage["cumulative_artifact"],
        )


def test_replay_fails_on_seeded_artifact_byte_mismatch(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    lineage = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha="abc123",
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
        evolve_file="src/value.py",
        delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
        **_EVIDENCE,
    )
    artifact = tmp_path / "state" / lineage["cumulative_artifact"]
    artifact.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ArtifactReplayError, match="sha256 mismatch"):
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
            resolved_sha="abc123",
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=base_digest,
            evolve_file="src/value.py",
            delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
            **_EVIDENCE,
            parent_artifact_sha256="f" * 64,
            parent_candidate_tree_digest="sha256:not-the-seeded-tree",
        )

    lineage = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha="abc123",
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=base_digest,
        evolve_file="src/value.py",
        delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
        **_EVIDENCE,
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


def test_nonfinite_or_undefined_variance_never_leaves_promotion_artifacts(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    _tree(base, 1)
    shutil.copytree(base, seeded)
    state = tmp_path / "state"
    with pytest.raises(ArtifactReplayError, match="variance is undefined"):
        build_lineage(
            state_root=state,
            target_id="target",
            resolved_sha="abc123",
            base_root=base,
            seeded_root=seeded,
            base_tree_digest=compute_tree_digest(base, ["src/value.py"]),
            evolve_file="src/value.py",
            delta=_patch("VALUE = 1\n", "VALUE = 2\n"),
            evaluator_id="test-evaluator",
            evaluator_config_digest="sha256:" + "c" * 64,
            evaluator_image_digest="sha256:" + "d" * 64,
            claimed_score=0.0,
            score_observations=[1e308, -1e308],
        )
    assert not (state / "artifacts").exists()
