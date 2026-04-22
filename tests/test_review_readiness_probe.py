from __future__ import annotations

from pathlib import Path

from dharma_swarm.codex_overnight import GitSnapshot

from scripts.review_readiness_probe import build_check_specs, derive_overall_status


def _snapshot(*, dirty: bool) -> GitSnapshot:
    return GitSnapshot(
        branch="main",
        head="abc123",
        dirty=dirty,
        changed_files=[" M dharma_swarm/swarm.py"] if dirty else [],
        staged_count=0,
        unstaged_count=1 if dirty else 0,
        untracked_count=0,
    )


def test_build_check_specs_quick_keeps_runtime_smoke_only() -> None:
    specs = build_check_specs("quick", Path("/tmp/repo"))

    assert [spec.name for spec in specs] == ["desktop_runtime_smoke"]


def test_build_check_specs_full_includes_review_surface_builds_and_tests() -> None:
    specs = build_check_specs("full", Path("/tmp/repo"))
    names = [spec.name for spec in specs]

    assert "desktop_runtime_smoke" in names
    assert "dashboard_build" in names
    assert "desktop_shell_bundle" in names
    assert "desktop_shell_tests" in names
    assert "overnight_automation_tests" in names


def test_derive_overall_status_is_ready_when_tree_is_clean_and_checks_pass() -> None:
    status, ready, blockers = derive_overall_status(
        _snapshot(dirty=False),
        {
            "desktop_runtime_smoke": {
                "critical": True,
                "rc": 0,
            }
        },
    )

    assert status == "ready"
    assert ready is True
    assert blockers == []


def test_derive_overall_status_blocks_on_failed_check_and_dirty_tree() -> None:
    status, ready, blockers = derive_overall_status(
        _snapshot(dirty=True),
        {
            "desktop_runtime_smoke": {
                "critical": True,
                "rc": 1,
            }
        },
    )

    assert status == "blocked"
    assert ready is False
    assert any("failing checks" in blocker for blocker in blockers)
    assert any("dirty worktree" in blocker for blocker in blockers)
