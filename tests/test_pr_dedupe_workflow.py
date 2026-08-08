from __future__ import annotations

import json
import re
import subprocess
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
            title="report(governance): ops runs 2026-07-31 through 2026-08-06",
            head="ops/spine-adoption-pr-lifecycle-2026-07-31",
        ),
        _pr(
            1306,
            title="report(governance): ops run 2026-08-08T12:00Z",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1200Z",
        ),
        _pr(
            1307,
            title="report(governance): ops run from a fork",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08T1800Z",
            owner="fork-owner",
        ),
    ]

    assert _matching_numbers(rows) == [1173, 1306]


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
            7,
            # A human suffix on the lifecycle prefix is not the exact
            # timestamped automation lane and must survive cleanup.
            title="spine lifecycle report parser implementation",
            head="ops/spine-adoption-pr-lifecycle-2026-08-08-parser",
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
    ]

    assert _matching_numbers(rows) == []


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
