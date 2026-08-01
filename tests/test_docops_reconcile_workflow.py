"""WP-0G reconcile-workflow contract (TIT-008).

Strict DocOps was red on main while the rolling repair PR could lose its
checks. The reconcile commit applied its direct-main ``[skip ci]`` loop guard
to the Tier-2 PR head too, suppressing the checks that make the PR actionable.
An early byte-identical optimization could then report success without
checking that exact remote head. These tests pin the repaired delivery
contract of `.github/workflows/docops-reconcile-main.yml` structurally (the
workflow cannot run locally; its text is the enforceable surface, the pattern
used by the polyglot/hermetic contract tests).

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
    # pass the exact new head to verification before exiting.
    assert WORKFLOW.count("verify_head_checks") >= 3  # definition + 2 call sites
    assert WORKFLOW.count('verify_head_checks "$(git rev-parse HEAD)"') == 2


def test_check_verifier_is_bound_to_the_requested_exact_head() -> None:
    count_start = WORKFLOW.index("head_check_count() {")
    verify_start = WORKFLOW.index("verify_head_checks() {")
    verify_end = WORKFLOW.index("# Tier 2 uses one rolling PR.", verify_start)
    count_block = WORKFLOW[count_start:verify_start]
    verify_block = WORKFLOW[verify_start:verify_end]

    assert 'local head_sha="$1"' in count_block
    assert 'commits/${head_sha}/check-runs' in count_block
    assert 'local head_sha="$1"' in verify_block
    assert 'head_check_count "$head_sha"' in verify_block
    assert 'head_sha="$(git rev-parse HEAD)"' not in verify_block


def test_checkless_head_is_a_red_job_not_a_warning() -> None:
    verify_start = WORKFLOW.index("verify_head_checks() {")
    verify_end = WORKFLOW.index("# Tier 2 uses one rolling PR.", verify_start)
    verify_block = WORKFLOW[verify_start:verify_end]
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


def test_skip_ci_is_applied_only_to_tier_one_direct_main_commit() -> None:
    neutral_commit = WORKFLOW.index(
        'COMMIT_SUBJECT="chore(docops): reconcile generated counts"'
    )
    tier_one = WORKFLOW.index("# ---- Tier 1:", neutral_commit)
    tier_two = WORKFLOW.index("# ---- Tier 2:", tier_one)

    assert "[skip ci]" not in WORKFLOW[neutral_commit:tier_one]
    assert "git commit --amend" in WORKFLOW[tier_one:tier_two]
    assert '-m "${COMMIT_SUBJECT} [skip ci]"' in WORKFLOW[tier_one:tier_two]
    assert "[skip ci]" not in WORKFLOW[tier_two:]
    assert re.search(r"if:.*skip ci", WORKFLOW), (
        "the job must not re-trigger itself after Tier-1 direct-main delivery"
    )


def test_byte_identical_rolling_head_must_already_have_checks_to_skip() -> None:
    remote_compare = 'git diff --quiet "FETCH_HEAD" --'
    compare_start = WORKFLOW.index(remote_compare)
    commit_start = WORKFLOW.index("DocOps counts drifted; committing reconcile:")
    compare_block = WORKFLOW[compare_start:commit_start]

    assert 'remote_head="$(git rev-parse FETCH_HEAD)"' in compare_block
    assert 'remote_check_count="$(head_check_count "$remote_head")"' in compare_block
    assert 'if [ "$remote_check_count" -gt 0 ]; then' in compare_block
    assert "already match the open rolling PR" in compare_block
    assert "has ${remote_check_count} check run(s); no refresh needed" in compare_block
    assert "is checkless; refreshing it" in compare_block
    assert (
        "Canonical DocOps bytes already match the open rolling PR "
        "#${existing}; no refresh needed."
    ) not in compare_block


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
