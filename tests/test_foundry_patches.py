"""Tests for strict, scoped Foundry patch replay."""

from __future__ import annotations

import difflib
import os
import shutil
from pathlib import Path

import pytest

import dharma_swarm.foundry.artifacts as artifacts
import dharma_swarm.foundry.patches_atomic as patches_atomic
from dharma_swarm.foundry.artifacts import ArtifactReplayError, build_lineage
from dharma_swarm.foundry.patches import (
    PatchReplayError,
    apply_unified_diff,
    write_immutable_beneath,
)
from dharma_swarm.foundry.target_ingest import compute_tree_digest


def _patch(old: str, new: str, path: str = "src/value.py", *, context: int = 3) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=context,
        )
    )


def _target(root: Path, text: str = "VALUE = 1\n") -> Path:
    path = root / "src" / "value.py"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_exact_patch_replays_atomically_and_preserves_mode(tmp_path):
    target = _target(tmp_path)
    target.chmod(0o640)
    apply_unified_diff(
        tmp_path,
        _patch("VALUE = 1\n", "VALUE = 2\n"),
        allowed_paths=["src/value.py"],
    )
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert target.stat().st_mode & 0o777 == 0o640


def test_exact_patch_requires_the_pinned_preimage_inode(tmp_path):
    target = _target(tmp_path)
    metadata = target.stat()
    expected = (metadata.st_dev, metadata.st_ino, metadata.st_ctime_ns)
    apply_unified_diff(
        tmp_path,
        _patch("VALUE = 1\n", "VALUE = 2\n"),
        allowed_paths=["src/value.py"],
        expected_identity=expected,
    )
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"

    current = target.stat()
    with pytest.raises(PatchReplayError, match="identity drifted"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 2\n", "VALUE = 3\n"),
            allowed_paths=["src/value.py"],
            expected_identity=(current.st_dev, metadata.st_ino, current.st_ctime_ns),
        )
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"


def test_path_swap_before_replace_is_detected_without_patch_write(
    tmp_path, monkeypatch
):
    target = _target(tmp_path)
    original_create = patches_atomic._create_temp

    def swap_after_temp(parent_fd, mode, operation_id):
        descriptor, name, created = original_create(parent_fd, mode, operation_id)
        target.unlink()
        target.write_text("ATTACKER\n", encoding="utf-8")
        return descriptor, name, created

    monkeypatch.setattr(patches_atomic, "_create_temp", swap_after_temp)
    with pytest.raises(PatchReplayError, match="identity drifted before replace"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
        )
    assert target.read_text(encoding="utf-8") == "ATTACKER\n"
    assert not list(target.parent.glob(".foundry-replay-*"))


def test_parent_component_swap_before_replace_is_detected_without_write(
    tmp_path, monkeypatch
):
    target = _target(tmp_path)
    original_create = patches_atomic._create_temp
    displaced = tmp_path / "displaced-src"

    def swap_parent_after_temp(parent_fd, mode, operation_id):
        descriptor, name, created = original_create(parent_fd, mode, operation_id)
        target.parent.rename(displaced)
        target.parent.mkdir()
        target.write_text("ATTACKER\n", encoding="utf-8")
        return descriptor, name, created

    monkeypatch.setattr(patches_atomic, "_create_temp", swap_parent_after_temp)
    with pytest.raises(PatchReplayError, match="directory pathname drifted"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
        )
    assert target.read_text(encoding="utf-8") == "ATTACKER\n"
    assert (displaced / "value.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not list(displaced.glob(".foundry-replay-*"))


def test_deterministic_temp_resumes_preimage_crash_window(tmp_path):
    target = _target(tmp_path)
    operation_id = "a" * 64
    temporary = target.parent / f".foundry-replay-{operation_id}"
    temporary.write_text("VALUE = 2\n", encoding="utf-8")
    metadata = target.stat()
    temporary.chmod(metadata.st_mode & 0o777)

    apply_unified_diff(
        tmp_path,
        _patch("VALUE = 1\n", "VALUE = 2\n"),
        allowed_paths=["src/value.py"],
        expected_identity=(metadata.st_dev, metadata.st_ino, metadata.st_ctime_ns),
        expected_root_identity=(tmp_path.stat().st_dev, tmp_path.stat().st_ino),
        operation_id=operation_id,
    )
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert not temporary.exists()


def test_deterministic_temp_rejects_hardlink_alias(tmp_path):
    target = _target(tmp_path)
    operation_id = "b" * 64
    alias = target.parent / "attacker-alias"
    alias.write_text("VALUE = 2\n", encoding="utf-8")
    alias.chmod(target.stat().st_mode & 0o777)
    temporary = target.parent / f".foundry-replay-{operation_id}"
    os.link(alias, temporary)
    metadata = target.stat()

    with pytest.raises(PatchReplayError, match="recovery temp does not match"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
            expected_identity=(metadata.st_dev, metadata.st_ino, metadata.st_ctime_ns),
            expected_root_identity=(tmp_path.stat().st_dev, tmp_path.stat().st_ino),
            operation_id=operation_id,
        )
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert alias.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert temporary.exists()
    assert temporary.stat().st_nlink == 2


def test_wrong_pinned_root_identity_refuses_before_write(tmp_path):
    target = _target(tmp_path)
    before = target.read_bytes()
    with pytest.raises(PatchReplayError, match="root identity drifted"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
            expected_root_identity=(tmp_path.stat().st_dev, tmp_path.stat().st_ino + 1),
        )
    assert target.read_bytes() == before


def test_stale_context_fails_without_mutating_target(tmp_path):
    target = _target(tmp_path, "VALUE = 9\n")
    before = target.read_bytes()
    with pytest.raises(PatchReplayError, match="context does not match"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
        )
    assert target.read_bytes() == before


def test_lf_patch_cannot_silently_normalize_crlf_target(tmp_path):
    target = _target(tmp_path)
    target.write_bytes(b"A\r\nB\r\n")
    before = target.read_bytes()
    with pytest.raises(PatchReplayError, match="context does not match"):
        apply_unified_diff(
            tmp_path,
            _patch("A\nB\n", "A\nC\n"),
            allowed_paths=["src/value.py"],
        )
    assert target.read_bytes() == before


def test_mixed_newlines_replay_only_the_encoded_line_change(tmp_path):
    target = _target(tmp_path)
    target.write_bytes(b"A\r\nB\n")
    apply_unified_diff(
        tmp_path,
        _patch("A\r\nB\n", "A\r\nC\n"),
        allowed_paths=["src/value.py"],
    )
    assert target.read_bytes() == b"A\r\nC\n"


def test_check_only_validates_without_writing(tmp_path):
    target = _target(tmp_path)
    before = target.read_bytes()
    apply_unified_diff(
        tmp_path,
        _patch("VALUE = 1\n", "VALUE = 2\n"),
        allowed_paths=["src/value.py"],
        check_only=True,
    )
    assert target.read_bytes() == before


@pytest.mark.parametrize(
    "path",
    ["../escape.py", "/absolute.py", "src/../../escape.py", "src\\escape.py"],
)
def test_unsafe_paths_are_rejected(tmp_path, path):
    _target(tmp_path)
    with pytest.raises(PatchReplayError, match="unsafe patch path"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n", path),
            allowed_paths=["src/value.py"],
        )


def test_out_of_scope_and_multifile_patches_are_rejected(tmp_path):
    _target(tmp_path)
    other = tmp_path / "other.py"
    other.write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(PatchReplayError, match="outside declared evolve scope"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n", "other.py"),
            allowed_paths=["src/value.py"],
        )
    multi = _patch("VALUE = 1\n", "VALUE = 2\n") + _patch(
        "VALUE = 1\n", "VALUE = 3\n", "other.py"
    )
    with pytest.raises(PatchReplayError, match="exactly one file"):
        apply_unified_diff(tmp_path, multi, allowed_paths=["src/value.py"])


def test_headerless_structural_git_preamble_cannot_hide_second_file(tmp_path):
    _target(tmp_path)
    hidden_rename = (
        "diff --git a/grader.py b/grader-renamed.py\n"
        "similarity index 100%\n"
        "rename from grader.py\n"
        "rename to grader-renamed.py\n"
        + _patch("VALUE = 1\n", "VALUE = 2\n")
    )
    with pytest.raises(PatchReplayError, match="structural patch preamble"):
        apply_unified_diff(
            tmp_path,
            hidden_rename,
            allowed_paths=["src/value.py"],
        )


def test_single_matching_git_preamble_is_accepted(tmp_path):
    target = _target(tmp_path)
    patch = (
        "diff --git a/src/value.py b/src/value.py\n"
        "index 1234567..89abcde 100644\n"
        + _patch("VALUE = 1\n", "VALUE = 2\n")
    )
    apply_unified_diff(tmp_path, patch, allowed_paths=["src/value.py"])
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"


def test_empty_evolve_scope_fails_closed(tmp_path):
    _target(tmp_path)
    with pytest.raises(PatchReplayError, match="evolve scope is empty"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=[],
        )


def test_context_only_patch_is_not_a_promoted_change(tmp_path):
    _target(tmp_path)
    context_only = (
        "--- a/src/value.py\n"
        "+++ b/src/value.py\n"
        "@@ -1 +1 @@\n"
        " VALUE = 1\n"
    )
    with pytest.raises(PatchReplayError, match="no changed lines"):
        apply_unified_diff(
            tmp_path,
            context_only,
            allowed_paths=["src/value.py"],
        )


def test_deletion_to_empty_file_uses_zero_count_coordinate(tmp_path):
    target = _target(tmp_path, "VALUE = 1\n")
    apply_unified_diff(
        tmp_path,
        _patch("VALUE = 1\n", "", context=0),
        allowed_paths=["src/value.py"],
    )
    assert target.read_bytes() == b""


def test_zero_context_middle_deletion_uses_previous_new_line_coordinate(tmp_path):
    target = _target(tmp_path, "A\nB\nC\n")
    apply_unified_diff(
        tmp_path,
        _patch("A\nB\nC\n", "A\nC\n", context=0),
        allowed_paths=["src/value.py"],
    )
    assert target.read_text(encoding="utf-8") == "A\nC\n"


def test_missing_target_is_a_typed_failure(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(PatchReplayError, match="patch target is unavailable"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
        )


def test_symlinked_target_is_rejected_even_when_link_resolves_inside_root(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    os.symlink(real, tmp_path / "src" / "value.py")
    with pytest.raises(PatchReplayError, match="symlinked patch path"):
        apply_unified_diff(
            tmp_path,
            _patch("VALUE = 1\n", "VALUE = 2\n"),
            allowed_paths=["src/value.py"],
        )


def _lineage_kwargs(tmp_path, state):
    base, seeded = tmp_path / "base", tmp_path / "seeded"
    _target(base)
    shutil.copytree(base, seeded)
    return {
        "state_root": state,
        "target_id": "target",
        "resolved_sha": "a" * 40,
        "base_root": base,
        "seeded_root": seeded,
        "base_tree_digest": compute_tree_digest(base, ["src/value.py"]),
        "evolve_file": "src/value.py",
        "delta": _patch("VALUE = 1\n", "VALUE = 2\n"),
    }


@pytest.mark.parametrize(
    "unsafe_parent", ["artifacts", "artifacts/deltas", "artifacts/manifests"]
)
def test_lineage_never_writes_through_symlinked_storage_parent(
    tmp_path, unsafe_parent
):
    state, outside = tmp_path / "state", tmp_path / "outside"
    state.mkdir()
    outside.mkdir()
    link = state / unsafe_parent
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactReplayError, match="artifact storage rejected"):
        build_lineage(**_lineage_kwargs(tmp_path, state))
    assert list(outside.iterdir()) == []


def test_lineage_rejects_symlinked_state_root_before_blob_write(tmp_path):
    outside, state = tmp_path / "outside", tmp_path / "state"
    outside.mkdir()
    state.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactReplayError, match="artifact storage rejected"):
        build_lineage(**_lineage_kwargs(tmp_path, state))
    assert list(outside.iterdir()) == []


def test_immutable_writer_does_not_follow_existing_symlink_leaf(tmp_path):
    root, outside = tmp_path / "state", tmp_path / "outside.patch"
    (root / "artifacts").mkdir(parents=True)
    outside.write_bytes(b"operator-owned")
    (root / "artifacts" / "blob.patch").symlink_to(outside)
    with pytest.raises(PatchReplayError, match="immutable artifact is unsafe"):
        write_immutable_beneath(root, "artifacts/blob.patch", b"attacker-data")
    assert outside.read_bytes() == b"operator-owned"


def test_content_addressed_writer_rejects_size_before_existing_file_read(tmp_path):
    root = tmp_path / "state"
    target = root / "artifacts" / "blob.patch"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * (1024 * 1024))
    target.chmod(0o600)

    with pytest.raises(PatchReplayError, match="content-address collision"):
        write_immutable_beneath(root, "artifacts/blob.patch", b"short")


def _synthetic_lineage(depth):
    return [
        {"lineage_digest": "sha256:" + f"{index:064x}", "index": index}
        for index in range(depth)
    ]


def test_lineage_walk_is_iterative_beyond_python_recursion_limit(tmp_path, monkeypatch):
    chain = _synthetic_lineage(1_200)
    calls = []

    def verify_node(base_root, manifest, **kwargs):
        index = manifest["index"]
        calls.append(index)
        parent = chain[index - 1] if index else None
        parent_path = tmp_path / f"{index - 1}.patch" if parent else None
        return f"tree-{index}", parent, parent_path

    monkeypatch.setattr(artifacts, "_verify_lineage_node", verify_node)
    result = artifacts.verify_lineage(
        tmp_path, chain[-1], artifact_path=tmp_path / "1199.patch"
    )
    assert result == "tree-1199"
    assert len(calls) == len(chain)


def test_lineage_walk_rejects_cycles(tmp_path, monkeypatch):
    first, second = _synthetic_lineage(2)

    def verify_node(base_root, manifest, **kwargs):
        parent = second if manifest is first else first
        return "tree", parent, tmp_path / "parent.patch"

    monkeypatch.setattr(artifacts, "_verify_lineage_node", verify_node)
    with pytest.raises(ArtifactReplayError, match="lineage cycle detected"):
        artifacts.verify_lineage(tmp_path, first, artifact_path=tmp_path / "child.patch")


def test_lineage_walk_propagates_deep_typed_failure(tmp_path, monkeypatch):
    chain = _synthetic_lineage(1_100)

    def verify_node(base_root, manifest, **kwargs):
        index = manifest["index"]
        if index == 100:
            raise ArtifactReplayError("deep parent is corrupt")
        parent = chain[index - 1] if index else None
        return "tree", parent, tmp_path / f"{index - 1}.patch" if parent else None

    monkeypatch.setattr(artifacts, "_verify_lineage_node", verify_node)
    with pytest.raises(ArtifactReplayError, match="deep parent is corrupt"):
        artifacts.verify_lineage(tmp_path, chain[-1], artifact_path=tmp_path / "head.patch")
