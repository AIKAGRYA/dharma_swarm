from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-dedupe.yml"
DOCOPS_RECONCILE = REPO_ROOT / ".github" / "workflows" / "docops-reconcile-main.yml"
ACTIVE_TRACK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "active-track.yml"
PR_CI_HEALTH = REPO_ROOT / ".github" / "workflows" / "pr-ci-health.yml"


def _snapshot_filter() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*SNAPSHOT_FILTER=\"\$\(cat <<'JQ'\n"
        r"(?P<program>.*?)"
        r"^\s*JQ\n^\s*\)\"",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "snapshot filter must be an extractable jq program"
    return match.group("program")


def _matching_numbers(rows: list[dict[str, object]]) -> list[int]:
    result = subprocess.run(
        ["jq", "-c", _snapshot_filter(), "--arg", "repo_owner", "owner"],
        input=json.dumps(rows),
        text=True,
        capture_output=True,
        check=True,
    )
    return [
        int(json.loads(line)["number"])
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _pr(
    number: int,
    *,
    title: str,
    head: str,
    owner: str = "owner",
) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "headRefName": head,
        "headRepositoryOwner": {"login": owner},
    }


def _step_script(name: str) -> str:
    marker = f"      - name: {name}\n        run: |\n"
    tail = WORKFLOW.read_text(encoding="utf-8").split(marker, 1)[1]
    return textwrap.dedent(tail.split("\n      - name:", 1)[0])


def _run_step(
    tmp_path: Path,
    *,
    name: str,
    rows: list[dict[str, object]],
    dry_run: bool,
    list_rc: int = 0,
    comment_rc: int = 0,
    close_rc: int = 0,
    delete_rc: int = 0,
    fail_jq: bool = False,
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    tmp_path.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "gh-calls.log"
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    gh = bin_dir / "gh"
    gh.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_CALL_LOG"
case "$1:$2" in
  pr:list)
    [ "${GH_LIST_RC:-0}" -eq 0 ] || exit "$GH_LIST_RC"
    printf '%s\\n' "$GH_ROWS"
    ;;
  pr:comment) exit "${GH_COMMENT_RC:-0}" ;;
  pr:close) exit "${GH_CLOSE_RC:-0}" ;;
  api:*) exit "${GH_DELETE_RC:-0}" ;;
  *) exit 64 ;;
esac
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    if fail_jq:
        jq = bin_dir / "jq"
        jq.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        jq.chmod(0o755)

    script = _step_script(name)
    for filename in ("open_prs.json", "snapshot_prs.jsonl", "dupe_groups.jsonl"):
        script = script.replace(f"/tmp/{filename}", str(tmp_path / filename))
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "GH_TOKEN": "test-token",
            "GH_REPO": "owner/repo",
            "GH_ROWS": json.dumps(rows),
            "GH_CALL_LOG": str(calls),
            "GH_LIST_RC": str(list_rc),
            "GH_COMMENT_RC": str(comment_rc),
            "GH_CLOSE_RC": str(close_rc),
            "GH_DELETE_RC": str(delete_rc),
            "DRY_RUN": "true" if dry_run else "false",
            "GITHUB_STEP_SUMMARY": str(summary),
        }
    )
    result = subprocess.run(
        ["/bin/bash", "-c", script],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return (
        result,
        summary.read_text(encoding="utf-8"),
        calls.read_text(encoding="utf-8") if calls.exists() else "",
    )


def test_snapshot_filter_closes_trusted_unmarked_ops_reports() -> None:
    rows = [
        _pr(
            950,
            title="chore(governance): ops report 2026-07-15 — spine 93.8%",
            head="chore/ops-report-20260715",
        ),
        _pr(
            953,
            title="chore(governance): ops report 2026-07-15T0600Z",
            head="chore/ops-report-20260715T0600",
        ),
    ]

    assert _matching_numbers(rows) == [950, 953]


def test_snapshot_filter_closes_live_spine_lifecycle_branch_shape() -> None:
    rows = [
        _pr(
            1173,
            title=(
                "report(governance): ops runs 2026-07-31 through "
                "2026-08-06T18:00Z — spine adoption saturated at 93.8% "
                "(21 runs), 57 open, only 6 PRs fail a required check"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-07-31",
        ),
        _pr(
            1283,
            title=(
                "report(governance): ops runs 2026-08-07T00:00Z + 06:00Z — "
                "spine adoption saturated at 93.8%, 58 open, 0 auto-closes, "
                "95% target blocked by legacy hatch not by code"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-08-07",
        ),
        _pr(
            1292,
            title=(
                "report(governance): ops run 2026-08-07T12:00Z — spine "
                "adoption 93.8% (unmoved), 56→55 open, 1 age-eligible "
                "auto-close, 0 auto-grounding duplicates"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-08-07T1200Z",
        ),
        _pr(
            1304,
            title=(
                "report(governance): ops run 2026-08-07T18:00Z — spine "
                "adoption 93.8% (unmoved), 53 open, 0 auto-closes, "
                "0 auto-grounding duplicates"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-08-07T1800Z",
        ),
        _pr(
            1305,
            title=(
                "report(governance): ops run 2026-08-08T00:00Z — spine "
                "adoption 93.8% (unmoved), 54 open, 0 auto-closes, "
                "0 auto-grounding duplicates"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T0000Z",
        ),
        _pr(
            1306,
            title=(
                "report(governance): ops run 2026-08-08T12:00Z — spine "
                "adoption 93.8% (unmoved), 55 open, 0 auto-closes, "
                "0 auto-grounding duplicates"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1200Z",
        ),
        _pr(
            1307,
            # Every other predicate matches; owner is the sole exclusion.
            title=(
                "report(governance): ops run 2026-08-08T18:00Z — spine "
                "adoption snapshot from a fork"
            ),
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1800Z",
            owner="fork-owner",
        ),
    ]

    assert _matching_numbers(rows) == [1173, 1283, 1292, 1304, 1305, 1306]


def test_snapshot_filter_remains_fail_closed_for_untrusted_or_real_work() -> None:
    rows = [
        _pr(
            1,
            title="chore(governance): ops report 2026-07-15",
            head="chore/ops-report-20260715",
            owner="fork-owner",
        ),
        _pr(
            2,
            title="ops report parser implementation",
            head="feature/ops-report-parser",
        ),
        _pr(
            5,
            # A human topic branch under the chore/ops-report- prefix must
            # never match: the branch predicate requires the timestamped
            # automation shape, and pass 1 deletes matched heads.
            title="ops report parser implementation",
            head="chore/ops-report-parser",
        ),
        _pr(
            6,
            # Anchoring matters: a timestamped prefix with a human suffix is
            # still a human branch, not the automation lane.
            title="ops report parser implementation",
            head="chore/ops-report-20260715-parser",
        ),
        _pr(
            13,
            # Even the exact legacy automation branch is insufficient: its
            # title must satisfy that lane's anchored governance grammar.
            title="ops report: fix bug",
            head="chore/ops-report-20260715",
        ),
        _pr(
            7,
            # A human suffix on the lifecycle prefix is not the exact
            # timestamped automation lane and must survive cleanup.
            title="spine lifecycle report parser implementation",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08-parser",
        ),
        _pr(
            8,
            # Even the exact reserved-looking branch shape is only an
            # automation signal, not enough authority to close real work.
            title="feat: implement real spine lifecycle behavior",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1800Z",
        ),
        _pr(
            9,
            # Broad legacy title language cannot authorize the reserved
            # lifecycle branch without its anchored governance report title.
            title="fix: ops report renderer",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1900Z",
        ),
        _pr(
            10,
            title="chore: refresh spine adoption metric docs",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T2000Z",
        ),
        _pr(
            11,
            # The intent word alone is not authority: the observed report
            # title grammar includes a real ISO date immediately after it.
            title="report(governance): ops run! implement real lifecycle work",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T2100Z",
        ),
        _pr(
            12,
            title="report(governance): ops run fake snapshot renderer",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T2200Z",
        ),
        _pr(
            3,
            title="chore(docops): reconcile generated counts",
            head="chore/docops-autorefresh",
        ),
        _pr(
            4,
            title="[automated] ordinary dependency update",
            head="chore/dependency-update",
        ),
        _pr(
            14,
            # A marker plus broad report language is still not an admitted
            # Pass 1 branch grammar.
            title="[automated] ops report: fix bug",
            head="chore/unrelated-automation",
        ),
        _pr(
            15,
            title="[auto] refresh spine adoption metric",
            head="ops/pr-lifecycle-spine-experiment",
        ),
    ]

    assert _matching_numbers(rows) == []

    # Pass 1 closes a projection, but cannot destroy its recovery ref. Pass 2
    # retains its existing duplicate-automation cleanup behavior.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    snapshot_step = workflow.split(
        "- name: Close ephemeral snapshot-report PRs", 1
    )[1].split("- name: Find and close duplicate automated PRs", 1)[0]
    assert 'git/refs/heads/${head_ref}' not in snapshot_step
    assert "--method DELETE" not in snapshot_step


def test_dedupe_reporting_is_outcome_bound_and_filter_errors_fail_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    snapshot_step, duplicate_step = workflow.split(
        "- name: Close ephemeral snapshot-report PRs", 1
    )[1].split("- name: Find and close duplicate automated PRs", 1)

    assert "/tmp/snapshot_prs.jsonl || true" not in snapshot_step
    assert "/tmp/dupe_groups.jsonl || true" not in duplicate_step
    for step in (snapshot_step, duplicate_step):
        assert "**WOULD CLOSE**" in step
        assert "**FAILED TO CLOSE**" in step
        assert "**FAILED TO LIST OPEN PRS**" in step
        assert "**FAILED TO CLASSIFY" in step
        assert "governance comment failed" in step
        assert "echo -e" not in step
        assert step.index('if gh pr close "$number"') < step.index(
            "printf -- '- **CLOSED**"
        )


def test_dedupe_steps_report_dry_run_and_api_outcomes_honestly(
    tmp_path: Path,
) -> None:
    snapshot_rows = [
        _pr(
            1306,
            title="report(governance): ops run 2026-08-08T12:00Z — snapshot",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1200Z",
        )
    ]
    duplicate_rows = [
        {
            **_pr(
                number,
                title=f"[automated] refresh 2026-08-08T{hour}:00Z",
                head=f"chore/refresh-{number}",
            ),
            "author": {"is_bot": True, "login": "refresh[bot]"},
            "labels": [],
        }
        for number, hour in ((20, "00"), (21, "06"))
    ]
    cases = (
        ("Close ephemeral snapshot-report PRs", snapshot_rows),
        ("Find and close duplicate automated PRs", duplicate_rows),
    )

    for index, (name, rows) in enumerate(cases):
        result, summary, calls = _run_step(
            tmp_path / f"dry-{index}", name=name, rows=rows, dry_run=True
        )
        assert result.returncode == 0, result.stderr
        assert "**WOULD CLOSE**" in summary
        assert "**CLOSED**" not in summary
        assert "pr close" not in calls

        result, summary, _ = _run_step(
            tmp_path / f"comment-{index}",
            name=name,
            rows=rows,
            dry_run=False,
            comment_rc=9,
        )
        assert result.returncode == 0, result.stderr
        assert "**CLOSED**" in summary
        assert "governance comment failed" in summary

        result, summary, _ = _run_step(
            tmp_path / f"close-{index}",
            name=name,
            rows=rows,
            dry_run=False,
            close_rc=8,
        )
        assert result.returncode == 0, result.stderr
        assert "**FAILED TO CLOSE**" in summary
        assert "**CLOSED**" not in summary

    result, summary, calls = _run_step(
        tmp_path / "delete-failure",
        name="Find and close duplicate automated PRs",
        rows=duplicate_rows,
        dry_run=False,
        delete_rc=11,
    )
    assert result.returncode == 0, result.stderr
    assert "**CLOSED**" in summary
    assert "branch cleanup failed" in summary
    assert "api --method DELETE" in calls


def test_dedupe_steps_do_not_report_empty_state_when_jq_fails(
    tmp_path: Path,
) -> None:
    for index, name in enumerate(
        (
            "Close ephemeral snapshot-report PRs",
            "Find and close duplicate automated PRs",
        )
    ):
        result, summary, _ = _run_step(
            tmp_path / str(index),
            name=name,
            rows=[],
            dry_run=False,
            fail_jq=True,
        )
        assert result.returncode == 7
        assert "**FAILED TO CLASSIFY" in summary
        assert "No snapshot-report PRs open." not in summary
        assert "No duplicate automated PRs found." not in summary


def test_dedupe_steps_report_list_failures_before_classification(
    tmp_path: Path,
) -> None:
    for index, name in enumerate(
        (
            "Close ephemeral snapshot-report PRs",
            "Find and close duplicate automated PRs",
        )
    ):
        result, summary, calls = _run_step(
            tmp_path / str(index),
            name=name,
            rows=[],
            dry_run=False,
            list_rc=12,
        )
        assert result.returncode == 12
        assert "**FAILED TO LIST OPEN PRS**" in summary
        assert "pr close" not in calls


def test_docops_reconcile_skips_remote_byte_identical_refresh() -> None:
    text = DOCOPS_RECONCILE.read_text(encoding="utf-8")

    remote_compare = 'git diff --quiet "FETCH_HEAD" --'
    assert remote_compare in text
    assert "Canonical DocOps bytes already match the open rolling PR" in text
    assert text.index(remote_compare) < text.index("git commit")
    assert text.index(remote_compare) < text.index('git push --force origin')

    # The skip must be purity-gated: byte-identical canonical files alone
    # cannot preserve noncanonical paths on the rolling branch.
    purity_probe = 'git diff --name-only "${merge_base:-HEAD}" FETCH_HEAD --'
    assert purity_probe in text
    assert "carries noncanonical paths" in text
    assert text.index(purity_probe) < text.index("no refresh needed")


def test_pr_ci_health_rebase_excludes_docops_rolling_lane() -> None:
    text = PR_CI_HEALTH.read_text(encoding="utf-8")
    rebase_step = text.split("- name: Rebase conflict-free behind-main branches", 1)[1]

    exclusion = '[ "$head" = "chore/docops-autorefresh" ]'
    helper_invoke = "python3 scripts/governance/pr_ci_safe_rebase.py"
    assert exclusion in rebase_step
    assert helper_invoke in rebase_step
    # DocOps rolling-lane exclusion remains before helper invocation.
    assert rebase_step.index(exclusion) < rebase_step.index(helper_invoke)


def test_pr_ci_health_never_rebases_session_entry_packet_branches() -> None:
    """Workflow delegates to fail-closed helper; no inline PR-head mutation."""
    text = PR_CI_HEALTH.read_text(encoding="utf-8")
    helper = "scripts/governance/pr_ci_safe_rebase.py"
    assert helper in text
    assert "pr_ci_safe_rebase.py" in text
    # Helper owns all PR-head mutation; workflow must not do it inline.
    assert 'git fetch origin "$head"' not in text
    assert 'git checkout -B "ci-rebase/$head"' not in text
    assert "git rebase origin/main" not in text
    assert 'git push origin "ci-rebase/$head:$head"' not in text
    assert "gh api --paginate" not in text
    assert "SESSION_ENTRY_PACKET_PREFIX" not in text
    # Invocation carries identity binding flags.
    assert "--expected-base" in text
    assert "--expected-head" in text


def test_pr_ci_health_docops_exclusion_before_helper() -> None:
    """DocOps rolling-lane exclusion must precede helper invocation."""
    text = PR_CI_HEALTH.read_text(encoding="utf-8")
    step = text.split("- name: Rebase conflict-free behind-main branches", 1)[1]
    exclusion = '[ "$head" = "chore/docops-autorefresh" ]'
    helper = "python3 scripts/governance/pr_ci_safe_rebase.py"
    assert exclusion in step and helper in step
    assert step.index(exclusion) < step.index(helper)


def test_pr_ci_health_delegates_to_helper_no_direct_pr_head_mutation() -> None:
    """Mirror helper-owned mutation surface (moved from helper unit tests)."""
    text = PR_CI_HEALTH.read_text(encoding="utf-8")
    assert "scripts/governance/pr_ci_safe_rebase.py" in text
    assert 'git fetch origin "$head"' not in text
    assert 'git checkout -B "ci-rebase/$head"' not in text
    assert "git rebase origin/main" not in text
    assert 'git push origin "ci-rebase/$head:$head"' not in text
    assert "gh api --paginate" not in text
    assert "SESSION_ENTRY_PACKET_PREFIX" not in text


def test_active_track_pr_gate_installs_executable_criterion_dependencies() -> None:
    # The evaluate lane must install the full [dev] environment so test_passes
    # and command_passes criteria execute under the same dependency surface as
    # generated/status; a pyyaml-only install falsely downgraded passing tracks.
    # The exact install mechanics (editable vs git-archive source) may evolve;
    # the invariant is the [dev] extra and the absence of the pyyaml-only lane.
    text = ACTIVE_TRACK_WORKFLOW.read_text(encoding="utf-8")
    gate_setup = text.split(
        "- name: Evaluate ACTIVE_TRACK.yaml against tree", 1
    )[0]

    assert "[dev]" in gate_setup
    assert "python3 -m pip install pyyaml" not in gate_setup
