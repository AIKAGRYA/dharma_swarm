"""WP-0G reconcile-workflow contract (TIT-008).

Strict DocOps was red on main while the rolling repair PR could lose its
checks: Tier-2 force-pushes made with GITHUB_TOKEN never trigger workflows,
so the refreshed head sat checkless while the job reported success. These
tests pin the repaired delivery contract of
`.github/workflows/docops-reconcile-main.yml` structurally (the workflow
cannot run locally; its text is the enforceable surface, the pattern used by
the polyglot/hermetic contract tests).

Authority: docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md (WP-0G).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "docops-reconcile-main.yml"
).read_text(encoding="utf-8")


def test_force_update_verifies_checks_on_the_new_head() -> None:
    """Delivery is not success: the refreshed head must receive check runs."""
    assert "verify_head_checks" in WORKFLOW
    assert "check-runs" in WORKFLOW
    # Both Tier-2 delivery paths (refresh existing PR, create new PR) must
    # run the verification before exiting.
    assert WORKFLOW.count("verify_head_checks") >= 3  # definition + 2 call sites


def test_checkless_head_is_a_red_job_not_a_warning() -> None:
    verify_block = WORKFLOW[WORKFLOW.index("verify_head_checks() {"):]
    assert "::error::" in verify_block
    assert "return 1" in verify_block
    # The historical disease: rejected/inert delivery downgraded to a warning.
    assert "::warning::" not in verify_block


def test_success_requires_delivery_to_main_or_actionable_pr() -> None:
    """Both failure tiers exit nonzero; no silent branch-push-only success."""
    assert "exit 1" in WORKFLOW
    assert "reconcile could not be delivered" in WORKFLOW
    # Tier-1 rejected push with a bypass token present is red, not warned.
    assert "bypass token present but the direct push was rejected" in WORKFLOW


def test_reconcile_commit_carries_skip_ci_loop_guard() -> None:
    assert "[skip ci]" in WORKFLOW
    assert re.search(r"if:.*skip ci", WORKFLOW), (
        "the job must not re-trigger itself on its own reconcile commit"
    )


def test_reconcile_stages_only_the_two_governed_files() -> None:
    assert (
        "git add docs/docops/AUTO_INVENTORY.md docs/governance/SOVEREIGN_MANIFEST.md"
        in WORKFLOW
    )
    command_lines = [
        line.strip() for line in WORKFLOW.splitlines()
        if not line.strip().startswith("#")
    ]
    assert not any(line.startswith("git add -A") for line in command_lines)


def test_reconcile_runs_are_serialized() -> None:
    assert "concurrency:" in WORKFLOW
    assert "group: docops-reconcile-main" in WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW
