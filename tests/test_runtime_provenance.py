"""Tests for scripts/runtime/runtime_provenance.py (Honest Spine v2 Phase 0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "runtime" / "runtime_provenance.py"

spec = importlib.util.spec_from_file_location("runtime_provenance", SCRIPT)
rp = importlib.util.module_from_spec(spec)
sys.modules["runtime_provenance"] = rp
spec.loader.exec_module(rp)


def test_git_provenance_resolves_this_repo() -> None:
    prov = rp._git_provenance(str(REPO_ROOT))
    assert prov["resolved"] is True
    assert prov["branch"]
    assert prov["head"]
    assert isinstance(prov["dirty_files"], int)


def test_git_provenance_unresolved_for_non_git_dir(tmp_path) -> None:
    prov = rp._git_provenance(str(tmp_path))
    assert prov["resolved"] is False


def test_git_provenance_unresolved_for_empty_cwd() -> None:
    prov = rp._git_provenance("")
    assert prov["resolved"] is False


def test_render_reports_absence_when_nothing_running() -> None:
    text = rp.render([])
    assert "nothing claims to be live" in text


def test_render_flags_drift() -> None:
    text = rp.render([
        {
            "process": "dharma_daemon", "pid": 1, "command": "x",
            "resolved": True, "worktree": "/w", "branch": "b", "head": "h",
            "ahead_of_main": 0, "behind_main": 3, "dirty_files": 12,
        },
    ])
    assert "!!" in text and "behind main by 3" in text and "12 dirty files" in text
