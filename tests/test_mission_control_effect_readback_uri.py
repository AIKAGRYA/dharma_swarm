"""SQLite read-only URI path percent-encoding regression for effect readback."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.mission_control_effect_readback import read_effect_fence
from dharma_swarm.runtime_state import RuntimeStateStore


def _make_runtime_database(path: Path) -> None:
    RuntimeStateStore(path, include_memory_plane=False).init_db_sync()


def test_read_effect_fence_percent_encodes_legal_path_containing_question_mark(
    tmp_path: Path,
) -> None:
    """A legal directory/file name containing ``?`` must not be misread as a query."""
    directory = tmp_path / "weird?dir"
    directory.mkdir()
    runtime_database = directory / "runtime.sqlite3"
    _make_runtime_database(runtime_database)

    assert read_effect_fence(runtime_database, "governed_patch_effect:missing") is None


def test_read_effect_fence_percent_encodes_legal_path_containing_hash(
    tmp_path: Path,
) -> None:
    """A legal directory/file name containing ``#`` must not be truncated as a fragment."""
    directory = tmp_path / "weird#dir"
    directory.mkdir()
    runtime_database = directory / "runtime.sqlite3"
    _make_runtime_database(runtime_database)

    assert read_effect_fence(runtime_database, "governed_patch_effect:missing") is None


def test_read_effect_fence_percent_encodes_legal_path_containing_both(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "weird?and#dir"
    directory.mkdir()
    runtime_database = directory / "runtime.sqlite3"
    _make_runtime_database(runtime_database)

    assert read_effect_fence(runtime_database, "governed_patch_effect:missing") is None
