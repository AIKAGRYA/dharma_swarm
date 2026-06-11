"""Tests for the non-destructive parallel lane map renderer."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LANE_MAP_SCRIPT = REPO_ROOT / "scripts/governance/render_parallel_lane_map.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("render_parallel_lane_map", LANE_MAP_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


WORKTREE_SAMPLE = """worktree /repo
HEAD aaa111
branch refs/heads/main

worktree /tmp/lane
HEAD bbb222
branch refs/heads/codex/runtime-truth-nats-adapter-20260606

worktree /tmp/detached
HEAD ccc333
detached

worktree /tmp/missing
HEAD ddd444
branch refs/heads/cleanup/old-lane
prunable gitdir file points to non-existent location
"""


def test_parse_worktree_porcelain_keeps_detached_and_prunable_state() -> None:
    mod = _load_module()

    rows = mod.parse_worktree_porcelain(WORKTREE_SAMPLE)

    assert len(rows) == 4
    assert rows[0]["branch"] == "main"
    assert rows[1]["branch"] == "codex/runtime-truth-nats-adapter-20260606"
    assert rows[2]["detached"] is True
    assert rows[3]["prunable"] is True
    assert "non-existent" in rows[3]["prunable_reason"]


def test_dirty_status_is_grouped_by_governance_and_receipt_pressure() -> None:
    mod = _load_module()

    dirty = mod.parse_dirty_status(
        "\n".join(
            [
                " M docs/governance/ACTIVE_TRACK.yaml",
                " M scripts/governance/agent_onboard.py",
                "?? reports/agentops/work_packets/forge-cycle.json",
                "?? tests/test_new_gate.py",
            ]
        )
    )

    assert dirty["count"] == 4
    assert dirty["states"]["unstaged"] == 2
    assert dirty["states"]["untracked"] == 2
    assert dirty["categories"]["governance_docs"] == 1
    assert dirty["categories"]["governance_scripts"] == 1
    assert dirty["categories"]["agentops_work_packets"] == 1
    assert dirty["categories"]["tests"] == 1


def test_lane_classifier_matches_current_repo_lane_families() -> None:
    mod = _load_module()

    assert mod.classify_lane("codex/runtime-truth-nats-adapter-20260606") == "runtime-truth-spine"
    assert mod.classify_lane("lak-e2e metabolism ledger") == "living-agent-kernel"
    assert mod.classify_lane("rss/FU-WIRE-ZAI") == "rss-followups"
    assert mod.classify_lane("repair/pr-323-dkeys") == "pr-repair-backlog"
    assert mod.classify_lane("docs(research): Palantir grounding") == "research"


def test_render_markdown_is_non_destructive_snapshot_language() -> None:
    mod = _load_module()
    payload = {
        "generated_at": "2026-06-06T00:00:00Z",
        "doctrine": {
            "model": "one strategic active track; many coordinated work lanes",
            "active_track_role": "north-star",
            "lane_rule": "owned, scoped, isolated, verified, and receipted",
            "cleanup_rule": "never delete without review",
        },
        "summary": {
            "active_branch": "main",
            "head": "abc123",
            "worktree_count": 2,
            "branch_count_sampled": 3,
            "open_pr_count": 1,
            "dirty_count_current_worktree": 4,
            "cleanup_candidate_count": 1,
        },
        "lanes": {"governance": {"worktrees": 1, "branches": 1, "open_prs": 0, "recent_commits": 1}},
        "open_prs": [],
        "dirty_current_worktree": {"count": 4, "categories": {"governance_docs": 1}},
        "cleanup_candidates": [
            {"kind": "worktree", "path": "/tmp/old", "reason": "stale_review"}
        ],
        "recent_commits": [],
    }

    text = mod.render_markdown(payload)

    assert "non-destructive operating snapshot" in text
    assert "one strategic active track; many coordinated work lanes" in text
    assert "Cleanup Candidates For Review" in text
