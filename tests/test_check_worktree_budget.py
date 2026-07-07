"""Tests for scripts/governance/check_worktree_budget.py — the enforcer
behind CLAUDE.md's worktree-budget rule."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/check_worktree_budget.py"

spec = importlib.util.spec_from_file_location("check_worktree_budget", SCRIPT)
wb = importlib.util.module_from_spec(spec)
sys.modules["check_worktree_budget"] = wb
spec.loader.exec_module(wb)


PORCELAIN = """\
worktree /Users/op/repo
HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
branch refs/heads/main

worktree /Users/op/repo-loop-lane
HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
branch refs/heads/codex/loop-closure-work-20260702

worktree /Users/op/scratch-x
HEAD cccccccccccccccccccccccccccccccccccccccc
detached
"""


def test_parse_worktree_porcelain():
    trees = wb.parse_worktree_porcelain(PORCELAIN)
    assert len(trees) == 3
    assert trees[0]["path"] == "/Users/op/repo"
    assert trees[0]["branch"] == "main"
    assert trees[1]["branch"] == "codex/loop-closure-work-20260702"
    assert trees[2]["detached"] is True
    assert trees[2]["branch"] is None


def test_evaluate_within_budget():
    trees = wb.parse_worktree_porcelain(PORCELAIN)
    v = wb.evaluate(trees, ["loop-closure-2026-06"], repo_root=Path("/Users/op/repo"))
    # budget = 1 active + 1 canonical + 2 scratch = 4 >= 3 trees
    assert v["budget"] == 4
    assert v["count"] == 3
    assert v["over_budget"] is False
    assert v["over_by"] == 0


def test_evaluate_over_budget_and_unmapped():
    extra = "".join(
        f"worktree /Users/op/lane-{i}\nHEAD {'d' * 40}\n"
        f"branch refs/heads/misc/lane-{i}\n\n"
        for i in range(5)
    )
    trees = wb.parse_worktree_porcelain(PORCELAIN + extra)
    v = wb.evaluate(trees, ["loop-closure-2026-06"], repo_root=Path("/Users/op/repo"))
    assert v["count"] == 8
    assert v["budget"] == 4
    assert v["over_budget"] is True
    assert v["over_by"] == 4
    # canonical tree and the loop-closure lane are mapped; scratch + 5 misc are not
    unmapped_paths = {w["path"] for w in v["unmapped"]}
    assert "/Users/op/repo" not in unmapped_paths
    assert "/Users/op/repo-loop-lane" not in unmapped_paths
    assert "/Users/op/scratch-x" in unmapped_paths
    assert v["unmapped_count"] == 6


def test_track_stem_strips_date():
    assert wb._track_stem("loop-closure-2026-06") == "loop-closure"
    assert wb._track_stem("organism-rewire-2026-07") == "organism-rewire"
    assert wb._track_stem("no-date-suffix") == "no-date-suffix"


def test_evaluate_for_repo_runs_against_this_repo():
    # Integration smoke: parses real `git worktree list` output and the real
    # ACTIVE_TRACK.yaml without raising; verdict fields are present.
    v = wb.evaluate_for_repo(REPO_ROOT)
    assert v["count"] >= 1
    assert v["budget"] == v["active_tracks"] + v["canonical"] + v["scratch"]
    assert isinstance(v["unmapped"], list)
