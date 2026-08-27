"""Tests for entry-, time-, and byte-bounded filesystem operations."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import dharma_swarm.bounded_fs as bounded_fs_module
from dharma_swarm.bounded_fs import bounded_glob, bounded_grep, bounded_read_lines


def test_bounded_glob_preserves_root_and_recursive_pattern_semantics(tmp_path: Path):
    root_file = tmp_path / "root.py"
    root_file.write_text("pass\n")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    nested_file = nested / "worker.py"
    nested_file.write_text("pass\n")

    direct = bounded_glob(
        tmp_path, "*.py", max_entries=20, max_matches=20, max_seconds=1
    )
    recursive = bounded_glob(
        tmp_path, "**/*.py", max_entries=20, max_matches=20, max_seconds=1
    )

    assert direct.paths == (root_file,)
    assert set(recursive.paths) == {root_file, nested_file}


def test_bounded_glob_counts_unmatched_entries_before_entry_cap(tmp_path: Path):
    for index in range(8):
        (tmp_path / f"unmatched-{index}.txt").write_text("x\n")

    result = bounded_glob(
        tmp_path, "*.py", max_entries=3, max_matches=20, max_seconds=1
    )

    assert result.paths == ()
    assert result.entries_seen == 3
    assert result.complete is False
    assert result.stop_reason == "entry_limit"


def test_bounded_glob_deadline_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr(bounded_fs_module.time, "monotonic", lambda: next(ticks))

    result = bounded_glob(
        tmp_path, "**/*", max_entries=20, max_matches=20, max_seconds=0.5
    )

    assert result.complete is False
    assert result.stop_reason == "deadline"
    assert result.entries_seen == 0


def test_bounded_glob_skips_bulk_directories_truthfully(tmp_path: Path):
    vendor = tmp_path / "node_modules"
    vendor.mkdir()
    (vendor / "hidden.py").write_text("pass\n")

    result = bounded_glob(
        tmp_path, "**/*.py", max_entries=20, max_matches=20, max_seconds=1
    )

    assert result.paths == ()
    assert result.complete is False
    assert result.stop_reason == "skipped_paths"
    assert result.skipped_directories == 1


def test_bounded_glob_does_not_follow_directory_symlinks(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "reachable.py").write_text("pass\n")
    root = tmp_path / "root"
    root.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)

    result = bounded_glob(
        root, "**/*.py", max_entries=20, max_matches=20, max_seconds=1
    )

    assert result.paths == ()
    assert result.complete is False
    assert result.skipped_symlinks == 1


def test_bounded_grep_discloses_skipped_file_symlink(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("needle\n")
    root = tmp_path / "root"
    root.mkdir()
    (root / "linked.txt").symlink_to(target)

    result = bounded_grep(
        root,
        "*.txt",
        re.compile("needle"),
        max_entries=20,
        max_candidates=20,
        max_file_bytes=100,
        max_total_bytes=100,
        max_matches=5,
        max_line_chars=80,
        max_seconds=1,
    )

    assert result.matches == ()
    assert result.discovery.complete is False
    assert result.discovery.skipped_symlinks == 1


def test_bounded_read_lines_caps_bytes_after_underreported_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "growing.txt"
    source.write_text("x" * 20)
    original_stat = Path.stat

    def underreported_stat(path: Path, *args, **kwargs):
        if path == source:
            return SimpleNamespace(st_size=1)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", underreported_stat)

    observed_bytes, lines = bounded_read_lines(
        source, offset=1, limit=5, max_file_bytes=10
    )

    assert observed_bytes == 11
    assert lines == []


def test_bounded_grep_stops_at_actual_total_byte_budget_after_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "candidate.txt"
    source.write_text("needle exceeds budget\n")
    original_stat = Path.stat

    def underreported_stat(path: Path, *args, **kwargs):
        if path == source:
            return SimpleNamespace(st_size=1)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", underreported_stat)

    result = bounded_grep(
        tmp_path,
        "*.txt",
        re.compile("needle"),
        max_entries=20,
        max_candidates=20,
        max_file_bytes=100,
        max_total_bytes=10,
        max_matches=5,
        max_line_chars=80,
        max_seconds=1,
    )

    assert result.matches == ()
    assert result.stop_reason == "byte_limit"
    assert result.bytes_considered == 0


def test_bounded_grep_clips_rendered_match_lines(tmp_path: Path):
    source = tmp_path / "long.txt"
    source.write_text("needle " + ("x" * 100) + "\n")

    result = bounded_grep(
        tmp_path,
        "*.txt",
        re.compile("needle"),
        max_entries=20,
        max_candidates=20,
        max_file_bytes=1_000,
        max_total_bytes=1_000,
        max_matches=5,
        max_line_chars=16,
        max_seconds=1,
    )

    assert len(result.matches[0].line) == 16
    assert result.clipped_lines == 1
