from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-dedupe.yml"
DOCOPS_RECONCILE = REPO_ROOT / ".github" / "workflows" / "docops-reconcile-main.yml"
ACTIVE_TRACK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "active-track.yml"


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
    text = (
        REPO_ROOT / ".github" / "workflows" / "pr-ci-health.yml"
    ).read_text(encoding="utf-8")

    exclusion = '[ "$head" = "chore/docops-autorefresh" ]'
    push_command = 'git push origin "ci-rebase/$head:$head" --force-with-lease'
    assert exclusion in text
    assert push_command in text
    # The exclusion must guard the force-with-lease push, not follow it.
    assert text.index(exclusion) < text.index(push_command)


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
