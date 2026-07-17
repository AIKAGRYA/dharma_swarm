from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.agent_runner import _resolve_local_tool_path


def test_resolve_local_tool_path_allows_relative_path_inside_workdir(tmp_path: Path) -> None:
    resolved = _resolve_local_tool_path("reports/out.md", workdir=tmp_path)

    assert resolved == (tmp_path / "reports" / "out.md").resolve(strict=False)


def test_resolve_local_tool_path_allows_absolute_path_inside_workdir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "out.md"

    resolved = _resolve_local_tool_path(str(target), workdir=tmp_path)

    assert resolved == target.resolve(strict=False)


def test_resolve_local_tool_path_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes workdir"):
        _resolve_local_tool_path("../outside.md", workdir=tmp_path)


def test_resolve_local_tool_path_rejects_absolute_path_outside_workdir(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-agent-runner.md"

    with pytest.raises(ValueError, match="escapes workdir"):
        _resolve_local_tool_path(str(outside), workdir=tmp_path)
