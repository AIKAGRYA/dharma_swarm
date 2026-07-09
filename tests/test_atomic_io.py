"""Tests for dharma_swarm.atomic_io -- crash-safe atomic file writes."""

from __future__ import annotations

import json
import os
import stat

import pytest

from dharma_swarm.atomic_io import write_json_atomic, write_text_atomic


def _list_temp_leftovers(directory):
    """Any temp/hidden files atomic_io might have left behind."""
    return [
        p
        for p in directory.iterdir()
        if p.name.endswith(".tmp") or p.name.startswith(".")
    ]


def test_write_json_atomic_roundtrip(tmp_path):
    target = tmp_path / "state.json"
    obj = {"a": 1, "b": [1, 2, 3], "nested": {"x": True, "y": None}}

    write_json_atomic(target, obj)

    assert target.exists()
    assert json.loads(target.read_text()) == obj


def test_write_json_atomic_leaves_no_tmp_files(tmp_path):
    target = tmp_path / "state.json"
    write_json_atomic(target, {"k": "v"})

    # Only the final file remains -- no ".tmp" scratch files.
    assert _list_temp_leftovers(tmp_path) == []
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_write_json_atomic_default_callable(tmp_path):
    # default=str lets non-native objects serialize (e.g. a set).
    target = tmp_path / "state.json"
    write_json_atomic(target, {"s": {1, 2}}, default=str)
    assert "s" in json.loads(target.read_text())


def test_write_json_atomic_indent_passthrough(tmp_path):
    target = tmp_path / "state.json"
    write_json_atomic(target, {"a": 1}, indent=4)
    assert "\n    " in target.read_text()  # 4-space indent present


def test_write_text_atomic_roundtrip(tmp_path):
    target = tmp_path / "note.txt"
    write_text_atomic(target, "hello\nworld\n")
    assert target.read_text() == "hello\nworld\n"


def test_write_text_atomic_creates_missing_parent_dir(tmp_path):
    target = tmp_path / "deep" / "nested" / "note.txt"
    write_text_atomic(target, "ok")
    assert target.read_text() == "ok"


def test_permissions_best_effort_0600(tmp_path):
    target = tmp_path / "secret.json"
    write_json_atomic(target, {"token": "x"})
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600


def test_crash_during_replace_leaves_original_intact(tmp_path, monkeypatch):
    """If os.replace fails mid-write, the pre-existing file must survive
    unchanged and no temp file may be left behind."""
    target = tmp_path / "state.json"
    original = {"generation": 1, "critical": "do-not-lose-me"}
    write_json_atomic(target, original)
    assert json.loads(target.read_text()) == original

    boom = RuntimeError("simulated crash before rename commits")

    def exploding_replace(src, dst):
        raise boom

    monkeypatch.setattr("dharma_swarm.atomic_io.os.replace", exploding_replace)

    with pytest.raises(RuntimeError):
        write_json_atomic(target, {"generation": 2, "critical": "new-value"})

    # The original content is fully intact -- not truncated, not the new value.
    assert json.loads(target.read_text()) == original
    # The scratch temp file was cleaned up on the exception path.
    assert _list_temp_leftovers(tmp_path) == []
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]
