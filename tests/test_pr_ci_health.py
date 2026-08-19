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


def _pr(
    number: int, base: str = "main", state: str = "clean", draft: bool = False
) -> dict:
    return {
        "number": number,
        "title": f"pr {number}",
        "base": {"ref": base},
        "head": {"ref": f"feat-{number}", "sha": f"sha{number}"},
        "draft": draft,
        "user": {"login": "tester"},
        "mergeable_state": state,
    }


def _review_gate(
    *,
    decision: str = "NONE",
    unresolved: int = 0,
    outdated: int = 0,
    paths: list[str] | None = None,
    authors: list[str] | None = None,
    error: str = "",
):
    return pr_ci_health.ReviewGateState(
        review_decision=decision,
        unresolved_threads=unresolved,
        outdated_unresolved_threads=outdated,
        unresolved_thread_paths=paths or [],
        unresolved_thread_authors=authors or [],
        error=error,
    )


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
        {
            "name": "Coherence Delta PR body",
            "conclusion": "success",
            "started_at": "2026-05-21T14:16:40Z",
        },
        {
            "name": "Coherence Delta PR body",
            "conclusion": "failure",
            "started_at": "2026-05-21T14:16:26Z",
        },
        {
            "name": "pytest (3.11)",
            "conclusion": "success",
            "started_at": "2026-05-21T14:16:25Z",
        },
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


def test_classify_pr_exposes_unresolved_threads():
    runs = [{"name": "pytest (3.11)", "conclusion": "success"}]
    review_gate = _review_gate(
        unresolved=2,
        outdated=2,
        paths=["docs/docops/assertions.yaml"],
        authors=["chatgpt-codex-connector", "devin-ai-integration"],
    )
    triage = classify_pr(
        _pr(1286, state="blocked"),
        runs,
        review_gate=review_gate,
    )
    assert set(triage.categories) == {"merge_blocked", "unresolved_threads"}
    assert triage.unresolved_threads == 2
    assert triage.outdated_unresolved_threads == 2
    assert triage.review_state_known is True
    assert triage.actionable is True


def test_render_markdown_names_unresolved_conversation_blocker():
    triage = classify_pr(
        _pr(1286, state="blocked"),
        [{"name": "pytest (3.11)", "conclusion": "success"}],
        review_gate=_review_gate(
            unresolved=2,
            outdated=2,
            paths=["docs/docops/assertions.yaml"],
            authors=["devin-ai-integration"],
        ),
    )
    report = pr_ci_health.render_markdown([triage])
    assert "unresolved conversations" in report
    assert "2 (2 outdated)" in report
    assert "docs/docops/assertions.yaml" in report
    assert "devin-ai-integration" in report
    assert "1 with unresolved conversations" in report


def test_review_decision_identifies_required_review():
    triage = classify_pr(
        _pr(1309, state="blocked"),
        [{"name": "pytest (3.11)", "conclusion": "success"}],
        review_gate=_review_gate(decision="REVIEW_REQUIRED"),
    )
    assert set(triage.categories) == {"merge_blocked", "review_required"}


def test_unknown_review_state_is_never_green_when_collector_passes_it():
    triage = classify_pr(
        _pr(1309),
        [{"name": "pytest (3.11)", "conclusion": "success"}],
        review_gate=_review_gate(
            decision="UNKNOWN",
            unresolved=-1,
            outdated=-1,
            error="GraphQL unavailable",
        ),
    )
    assert triage.categories == ["review_state_unknown"]
    assert triage.actionable is True


def test_unexplained_blocked_state_is_named_after_exact_review_checks():
    triage = classify_pr(
        _pr(1311, state="blocked"),
        [{"name": "pytest (3.11)", "conclusion": "success"}],
        behind_by=0,
        review_gate=_review_gate(),
    )
    assert set(triage.categories) == {
        "merge_blocked",
        "policy_blocker_unidentified",
    }


def test_missing_checks_do_not_claim_an_unidentified_policy_blocker():
    triage = classify_pr(
        _pr(1311, state="blocked"),
        [],
        review_gate=_review_gate(),
    )
    assert "policy_blocker_unidentified" not in triage.categories
    assert set(triage.categories) == {"merge_blocked", "ci_never_ran"}


def test_known_behind_state_explains_a_green_checks_policy_blocker():
    triage = classify_pr(
        _pr(1311, state="blocked"),
        [{"name": "pytest (3.11)", "conclusion": "success"}],
        behind_by=3,
        review_gate=_review_gate(),
    )
    assert "policy_blocker_unidentified" not in triage.categories
    assert set(triage.categories) == {"merge_blocked", "behind_main"}


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


def test_workflow_validates_push_authority_before_rebase():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "pr-ci-health.yml"
    ).read_text(encoding="utf-8")

    assert (
        "secrets.PR_CI_HEALTH_PUSH_TOKEN || secrets.MERGEMASTERMIKE_PAT || github.token"
    ) in workflow
    assert (
        "PUSH_TOKEN: ${{ secrets.PR_CI_HEALTH_PUSH_TOKEN || "
        "secrets.MERGEMASTERMIKE_PAT }}"
    ) in workflow
    assert "Validate trusted rebase push authority" in workflow
    assert ".permissions.push // false" in workflow
    assert 'echo "HAS_PUSH_TOKEN=$has_push_token" >> "$GITHUB_ENV"' in workflow
    assert (
        "HAS_PUSH_TOKEN: ${{ secrets.PR_CI_HEALTH_PUSH_TOKEN != '' || "
        "secrets.MERGEMASTERMIKE_PAT != '' }}"
    ) not in workflow


def test_workflow_rebase_is_manual_and_targeted_not_scheduled():
    """Neither push nor cron may rewrite the open-PR backlog.

    Rebase remains available as a fail-closed recovery operation, but only for
    an explicit workflow_dispatch invocation whose selector matches one PR.
    """
    import yaml  # noqa: PLC0415

    path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "pr-ci-health.yml"
    )
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    triggers = doc.get("on", doc.get(True))
    assert "push" not in triggers, (
        "the merge-to-main rebase stampede is back: every merge will rebase the "
        "whole backlog and relaunch a full CI run per open PR"
    )
    assert "schedule" in triggers, "the hourly report backstop must remain"

    job = doc["jobs"]["triage-and-heal"]
    assert job["env"]["MODE"] == (
        "${{ github.event_name == 'workflow_dispatch' "
        "&& github.event.inputs.mode || 'report' }}"
    )

    # The rebase capability survives, but cron cannot satisfy its event guard.
    rebase_step = next(
        step
        for step in job["steps"]
        if step.get("name", "").startswith("Rebase conflict-free")
    )
    assert rebase_step["if"] == (
        "github.event_name == 'workflow_dispatch' && env.MODE == 'rebase'"
    )
    assert " | select(.number == $target_pr)" in rebase_step["run"]


def test_behind_main_is_detected_when_state_says_blocked():
    """GitHub's mergeable_state is single-valued and `blocked` outranks
    `behind`, so a PR that is behind main AND waiting on a required check
    reports `blocked`. Keying behind-main detection on the state therefore
    missed nearly every real case — which is exactly the PR the operator
    ends up rebasing by hand."""
    triage = classify_pr(_pr(2001, state="blocked"), [], behind_by=7)
    assert "behind_main" in triage.categories
    assert "merge_blocked" in triage.categories


def test_behind_by_zero_is_not_behind_main():
    triage = classify_pr(_pr(2002, state="blocked"), [], behind_by=0)
    assert "behind_main" not in triage.categories


def test_measured_zero_beats_a_stale_behind_state():
    """mergeable_state is computed asynchronously and goes stale. A measured
    behind_by == 0 must not be overridden by a leftover `behind`, or an
    up-to-date PR gets a no-op rebase attempt — and, with no trusted push
    token, a false ci-stranded-rebase-skipped label and comment (Greptile
    and Codex both, on PR #1178)."""
    triage = classify_pr(_pr(2005, state="behind"), [], behind_by=0)
    assert "behind_main" not in triage.categories


def test_unmeasured_behind_by_falls_back_to_the_state():
    """-1 means "not measured" and must never read as up to date; the
    mergeable_state fallback still catches the plain `behind` case."""
    assert "behind_main" in classify_pr(_pr(2003, state="behind"), []).categories
    assert "behind_main" not in classify_pr(_pr(2004, state="blocked"), []).categories


def test_compare_behind_by_fails_closed_on_a_read_error(monkeypatch):
    def boom(_args):
        raise OSError("network down")

    monkeypatch.setattr(pr_ci_health, "_gh_json", boom)
    assert pr_ci_health.compare_behind_by("o/r", "main", "deadbeef") == -1


def test_compare_behind_by_reads_the_count(monkeypatch):
    monkeypatch.setattr(pr_ci_health, "_gh_json", lambda args: {"behind_by": 12})
    assert pr_ci_health.compare_behind_by("o/r", "main", "deadbeef") == 12


def test_fetch_review_gate_state_paginates_and_binds_the_head(monkeypatch):
    pages = [
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "sha1286",
                        "reviewDecision": None,
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "isResolved": False,
                                    "isOutdated": True,
                                    "path": "docs/docops/assertions.yaml",
                                    "comments": {
                                        "nodes": [
                                            {
                                                "author": {
                                                    "login": "devin-ai-integration"
                                                }
                                            }
                                        ]
                                    },
                                }
                            ],
                            "pageInfo": {
                                "hasNextPage": True,
                                "endCursor": "cursor-1",
                            },
                        },
                    }
                }
            }
        },
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "sha1286",
                        "reviewDecision": None,
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "isOutdated": False,
                                    "path": "fixed.py",
                                    "comments": {"nodes": []},
                                },
                                {
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "path": "current.py",
                                    "comments": {
                                        "nodes": [
                                            {
                                                "author": {
                                                    "login": "chatgpt-codex-connector"
                                                }
                                            }
                                        ]
                                    },
                                },
                            ],
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                        },
                    }
                }
            }
        },
    ]
    calls = []

    def fake_gh_json(args):
        calls.append(args)
        return pages[len(calls) - 1]

    monkeypatch.setattr(pr_ci_health, "_gh_json", fake_gh_json)
    state = pr_ci_health.fetch_review_gate_state(
        "owner/repo",
        1286,
        expected_head_sha="sha1286",
    )

    assert state.known is True
    assert state.review_decision == "NONE"
    assert state.unresolved_threads == 2
    assert state.outdated_unresolved_threads == 1
    assert state.unresolved_thread_paths == [
        "current.py",
        "docs/docops/assertions.yaml",
    ]
    assert state.unresolved_thread_authors == [
        "chatgpt-codex-connector",
        "devin-ai-integration",
    ]
    assert not any(arg == "after=cursor-1" for arg in calls[0])
    assert any(arg == "after=cursor-1" for arg in calls[1])


def test_fetch_review_gate_state_fails_closed_on_read_error(monkeypatch):
    def boom(_args):
        raise OSError("network down")

    monkeypatch.setattr(pr_ci_health, "_gh_json", boom)
    state = pr_ci_health.fetch_review_gate_state(
        "owner/repo",
        1286,
        expected_head_sha="sha1286",
    )
    assert state.known is False
    assert state.unresolved_threads == -1
    assert "network down" in state.error


def test_fetch_review_gate_state_rejects_null_or_partial_graphql_errors(monkeypatch):
    valid_pull_request = {
        "headRefOid": "sha1286",
        "reviewDecision": None,
        "reviewThreads": {
            "nodes": [],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    }
    responses = [
        {"data": None, "errors": [{"message": "permission denied"}]},
        {
            "data": {"repository": {"pullRequest": valid_pull_request}},
            "errors": [{"message": "partial reviewThreads failure"}],
        },
    ]

    for response in responses:
        monkeypatch.setattr(pr_ci_health, "_gh_json", lambda _args, row=response: row)
        state = pr_ci_health.fetch_review_gate_state(
            "owner/repo",
            1286,
            expected_head_sha="sha1286",
        )
        assert state.known is False
        assert state.unresolved_threads == -1
        assert "contains errors" in state.error


def test_fetch_review_gate_state_rejects_a_moved_head(monkeypatch):
    monkeypatch.setattr(
        pr_ci_health,
        "_gh_json",
        lambda _args: {
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "new-head",
                        "reviewDecision": None,
                        "reviewThreads": {
                            "nodes": [],
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                        },
                    }
                }
            }
        },
    )
    state = pr_ci_health.fetch_review_gate_state(
        "owner/repo",
        1286,
        expected_head_sha="old-head",
    )
    assert state.known is False
    assert "head moved" in state.error


def test_rebase_selection_uses_behind_by_not_mergeable_state():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "pr-ci-health.yml"
    ).read_text(encoding="utf-8")
    assert 'select(.mergeable_state == "behind")' not in workflow, (
        "state-keyed selection hides every behind-main PR that is also blocked"
    )
    assert 'select(.categories | index("behind_main"))' in workflow
    assert 'select(.categories | index("merge_conflict") | not)' in workflow, (
        "a rebase cannot resolve a conflicted branch"
    )


# --- Behavioural contract for the strand-label lifecycle -------------------
#
# `ci-stranded-rebase-skipped` was add-only: pr-ci-health applied it when it
# declined a rebase for want of push authority and never removed it, so a PR
# labelled once wore it permanently. Measured 2026-08-17: nine open PRs carried
# it while all nine merged cleanly against main.
#
# These tests EXECUTE the workflow step's shell against stub `gh` and a stub
# rebase helper, rather than asserting on the YAML text. An earlier version of
# this file asserted substring order instead; an adversarial review showed two
# mutants that kept those assertions green while the workflow deleted labels on
# rebases that never happened. Byte offsets are not behaviour.

import os as _os
import shutil as _shutil
import subprocess as _subprocess
import textwrap as _textwrap

_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pr-ci-health.yml"
)
_STRAND_LABEL = "ci-stranded-rebase-skipped"


def _rebase_step_script() -> str:
    """The `run:` body of the rebase step, dedented for execution."""
    lines = _WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, ln in enumerate(lines)
        if "Rebase conflict-free behind-main branches" in ln
    )
    run_at = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run_at]) - len(lines[run_at].lstrip())
    body = []
    for ln in lines[run_at + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= indent:
            break
        body.append(ln)
    return _textwrap.dedent("\n".join(body))


def _run_rebase_step(tmp_path, helper_stdout: str, helper_rc: int = 0) -> tuple[str, list[str]]:
    """Execute the step with stubbed `gh` and stubbed rebase helper.

    Returns (combined output, list of gh argument-lines the step invoked).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "gh_calls.log"
    (bin_dir / "gh").write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$*" >> "{calls}"\n'
        'case "$*" in\n'
        f'  *"--jq .labels[].name"*) printf "%s\\n" "{_STRAND_LABEL}"; exit 0 ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    (bin_dir / "gh").chmod(0o755)
    (bin_dir / "git").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "git").chmod(0o755)

    helper = tmp_path / "scripts" / "governance"
    helper.mkdir(parents=True)
    (helper / "pr_ci_safe_rebase.py").write_text(
        f"import sys\nprint({helper_stdout!r})\nsys.exit({helper_rc})\n"
    )
    # The step selects its target from triage.json, written by an earlier
    # step. Supplying a real eligible row exercises the actual jq selector
    # rather than bypassing it.
    (tmp_path / "triage.json").write_text(
        '[{"number": 904, "head": "feat/x", "base": "main",'
        ' "categories": ["behind_main"]}]'
    )

    script = _rebase_step_script()
    # `set -u` is active: every variable the step reads must be supplied, or
    # bash aborts before the code under test runs.
    env = dict(_os.environ)
    env.update(
        PATH=f"{bin_dir}:{env['PATH']}",
        REPO="AIKAGRYA/dharma_swarm",
        HAS_PUSH_TOKEN="true",
        STRAND_LABEL=_STRAND_LABEL,
        GH_TOKEN="stub",
        TARGET_PR="904",
        MODE="rebase",
    )
    proc = _subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=60,
    )
    logged = calls.read_text().splitlines() if calls.exists() else []
    return proc.stdout + proc.stderr, logged


def _deleted_the_label(gh_calls: list[str]) -> bool:
    return any("DELETE" in c and _STRAND_LABEL in c for c in gh_calls)


def test_label_is_cleared_when_the_helper_reports_a_real_rebase(tmp_path):
    out, calls = _run_rebase_step(tmp_path, "REBASED PR #904: feat@abc onto origin/main")
    assert _deleted_the_label(calls), (
        f"a confirmed rebase must clear the stale label; gh calls were {calls}\n{out}"
    )


def test_label_survives_a_skip_that_exits_zero(tmp_path):
    """The defect this contract exists for.

    pr_ci_safe_rebase.py returns exit code 0 on all 38 `raise Skip` paths and
    marks real success only with a `REBASED PR #<n>:` prefix — see its own
    test_lease_rejection_does_not_report_success. A push rejected by the lease
    means the PR was NOT rebased and is still stranded, so the label is still
    true and must survive.
    """
    out, calls = _run_rebase_step(
        tmp_path, "SKIP PR #904: push rejected (lease or remote): stale info"
    )
    assert not _deleted_the_label(calls), (
        f"the label was cleared on a SKIP — a rebase that never happened.\n"
        f"gh calls: {calls}\n{out}"
    )


def test_label_survives_a_rebase_conflict_skip(tmp_path):
    out, calls = _run_rebase_step(tmp_path, "SKIP PR #904: rebase conflict; aborted")
    assert not _deleted_the_label(calls), f"cleared on a conflict skip: {calls}\n{out}"


def test_label_survives_a_helper_hard_failure(tmp_path):
    out, calls = _run_rebase_step(tmp_path, "ERROR PR #904: unexpected", helper_rc=1)
    assert not _deleted_the_label(calls), f"cleared on a helper error: {calls}\n{out}"


def test_the_harness_can_actually_observe_a_delete(tmp_path):
    """Guard against the whole suite passing because nothing is ever detected."""
    _, calls = _run_rebase_step(tmp_path, "REBASED PR #904: feat@abc onto origin/main")
    assert calls, "no gh calls captured at all — the harness is not exercising the step"
