"""Tests for the PR CI-health triage classifier (scripts/governance/pr_ci_health.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "pr_ci_health",
    Path(__file__).resolve().parents[1] / "scripts" / "governance" / "pr_ci_health.py",
)
assert _SPEC and _SPEC.loader
pr_ci_health = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = pr_ci_health
_SPEC.loader.exec_module(pr_ci_health)
classify_pr = pr_ci_health.classify_pr


def _pr(number: int, base: str = "main", state: str = "clean", draft: bool = False) -> dict:
    return {
        "number": number,
        "title": f"pr {number}",
        "base": {"ref": base},
        "head": {"ref": f"feat-{number}", "sha": f"sha{number}"},
        "draft": draft,
        "user": {"login": "tester"},
        "mergeable_state": state,
    }


def test_governance_body_gate_failures_map_to_categories():
    runs = [
        {"name": "Coherence Delta PR body", "conclusion": "failure"},
        {"name": "Fourfold Shakti Warrant", "conclusion": "failure"},
        {"name": "DocOps integrity gate", "conclusion": "failure"},
        {"name": "pytest (3.11)", "conclusion": "success"},
    ]
    triage = classify_pr(_pr(329, state="behind"), runs)
    assert set(triage.categories) == {
        "coherence_delta",
        "fourfold_warrant",
        "docops_drift",
        "behind_main",
    }


def test_umbrella_codeql_flake_is_transient_when_deep_job_passes():
    runs = [
        {"name": "CodeQL", "conclusion": "failure"},
        {"name": "codeql / python", "conclusion": "success"},
        {"name": "pytest (3.11)", "conclusion": "success"},
    ]
    assert classify_pr(_pr(332), runs).categories == ["transient_infra"]


def test_umbrella_codeql_failure_is_real_when_deep_job_also_fails():
    runs = [
        {"name": "CodeQL", "conclusion": "failure"},
        {"name": "codeql / python", "conclusion": "failure"},
    ]
    assert classify_pr(_pr(333), runs).categories == ["real_test_lint"]


def test_all_passing_clean_pr_is_green():
    triage = classify_pr(_pr(321), [{"name": "pytest (3.11)", "conclusion": "success"}])
    assert triage.categories == ["green"]
    assert triage.actionable is False


def test_passing_rerun_supersedes_earlier_failure():
    # Same check name twice: older run failed, newer re-run passed.
    runs = [
        {"name": "Coherence Delta PR body", "conclusion": "success", "started_at": "2026-05-21T14:16:40Z"},
        {"name": "Coherence Delta PR body", "conclusion": "failure", "started_at": "2026-05-21T14:16:26Z"},
        {"name": "pytest (3.11)", "conclusion": "success", "started_at": "2026-05-21T14:16:25Z"},
    ]
    assert classify_pr(_pr(314), runs).categories == ["green"]


def test_real_test_failure_and_merge_conflict():
    runs = [{"name": "pytest (3.12)", "conclusion": "failure"}]
    triage = classify_pr(_pr(400, state="dirty"), runs)
    assert set(triage.categories) == {"real_test_lint", "merge_conflict"}
    assert triage.actionable is True


def test_zero_check_runs_is_ci_never_ran_never_green():
    # Bot-rebase stranding signature: GITHUB_TOKEN pushes never trigger
    # workflows, so the rebased head has ZERO check runs. This used to fall
    # through the zero-categories fallback and report as green.
    triage = classify_pr(_pr(1060), [])
    assert "ci_never_ran" in triage.categories
    assert "green" not in triage.categories
    assert triage.actionable is True


def test_zero_check_runs_behind_main_carries_both_categories():
    triage = classify_pr(_pr(1004, state="behind"), [])
    assert set(triage.categories) == {"behind_main", "ci_never_ran"}
    assert triage.actionable is True


def test_blocked_merge_state_is_merge_blocked_not_green():
    runs = [{"name": "pytest (3.11)", "conclusion": "success"}]
    triage = classify_pr(_pr(987, state="blocked"), runs)
    assert triage.categories == ["merge_blocked"]
    assert triage.actionable is True


def test_blocked_state_with_zero_runs_carries_both_fail_closed_categories():
    triage = classify_pr(_pr(1066, state="blocked"), [])
    assert set(triage.categories) == {"merge_blocked", "ci_never_ran"}
    assert triage.actionable is True


def test_pending_runs_without_any_success_are_not_green():
    runs = [{"name": "pytest (3.11)", "conclusion": None, "status": "in_progress"}]
    triage = classify_pr(_pr(1024), runs)
    assert triage.categories == ["ci_pending"]
    assert triage.actionable is True


def test_report_summary_counts_ci_never_ran_separately():
    rows = [
        classify_pr(_pr(1060), []),
        classify_pr(_pr(321), [{"name": "pytest (3.11)", "conclusion": "success"}]),
    ]
    md = pr_ci_health.render_markdown(rows)
    assert "1 green" in md
    assert "1 actionable" in md
    assert "1 ci_never_ran" in md


def test_startup_failure_and_stale_are_real_failures_even_with_other_success():
    for conclusion in ("startup_failure", "stale"):
        runs = [
            {"name": "pytest (3.11)", "conclusion": "success"},
            {"name": "required gate", "conclusion": conclusion},
        ]
        triage = classify_pr(_pr(1083), runs)
        assert triage.categories == ["real_test_lint"]
        assert triage.actionable is True


def test_draft_with_passing_checks_is_not_green_or_actionable():
    runs = [{"name": "pytest (3.11)", "conclusion": "success"}]
    triage = classify_pr(_pr(1083, draft=True), runs)
    assert triage.categories == ["draft"]
    assert triage.actionable is False


def test_unknown_merge_state_with_passing_checks_is_not_green():
    runs = [{"name": "pytest (3.11)", "conclusion": "success"}]
    triage = classify_pr(_pr(1083, state="unknown"), runs)
    assert triage.categories == ["merge_unknown"]
    assert triage.actionable is True
