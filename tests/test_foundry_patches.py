"""Tests for strict, scoped Foundry patch replay."""

from __future__ import annotations

import difflib
import os
from pathlib import Path

import pytest

from dharma_swarm.foundry.patches import PatchReplayError, apply_unified_diff


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
