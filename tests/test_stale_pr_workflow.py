"""The stale-PR lane must not tell a draft it is about to be auto-closed.

`stale-pr.yml` documents its own contract in its header: "Draft PRs: label only
(never auto-closed)". The close branch honoured that -- it is guarded by
`[ "$is_draft" != "true" ]`. The warn branch was not guarded at all, so a draft
past its close threshold fell through to the warning and was told:

    It will be **auto-closed in -2 days** unless updated.
    To keep it open:
    - Convert to a draft PR (exempt from auto-close)

Both halves are false for a draft: the countdown has gone negative, and the
advice is to do the thing the PR already did. Seventeen PRs received that
comment on 2026-09-14 (run 34847211633, "Closed: 2, Warned: 17"); the text
above is verbatim from PR #1061.

These tests execute the step's real shell against a stub `gh`, so they pin
behaviour rather than wording -- a reworded comment still passes, a
resurrected countdown does not.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/stale-pr.yml"

pytestmark = pytest.mark.skipif(
    not (shutil.which("jq") and shutil.which("bash")),
    reason="the step's shell needs jq and bash",
)

# gh stub: serves `pr list` from a fixture and logs every mutating call.
GH_STUB = """#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
  cat "$STALE_FIXTURE"
  exit 0
fi
printf '%s\\n' "$(printf '%s' "$*" | tr '\\n' ' ')" >> "$STALE_CALLS"
exit 0
"""


def _step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["stale-pr-lifecycle"]["steps"]:
        if step.get("name") == "Process stale PRs":
            return step["run"]
    raise AssertionError("the 'Process stale PRs' step disappeared")


def _pr(number, *, days_stale, is_draft, author="AmitabhainArunachala", labels=()):
    import datetime as dt

    updated = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_stale, hours=1)
    return {
        "number": number,
        "title": f"PR {number}",
        "author": {"login": author},
        "updatedAt": updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "isDraft": is_draft,
        "headRefName": f"branch-{number}",
        "labels": [{"name": n} for n in labels],
    }


def _run(tmp_path: Path, prs: list[dict]) -> tuple[str, list[str]]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)

    fixture = tmp_path / "prs.json"
    fixture.write_text(json.dumps(prs), encoding="utf-8")
    calls = tmp_path / "calls.txt"
    calls.touch()
    summary = tmp_path / "summary.md"

    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "STALE_FIXTURE": str(fixture),
        "STALE_CALLS": str(calls),
        "GITHUB_STEP_SUMMARY": str(summary),
        "GH_REPO": "AIKAGRYA/dharma_swarm",
        "GH_TOKEN": "stub",
        "DRY_RUN": "false",
        "BOT_WARN_DAYS": "11",
        "BOT_CLOSE_DAYS": "14",
        "HUMAN_WARN_DAYS": "27",
        "HUMAN_CLOSE_DAYS": "30",
    }
    proc = subprocess.run(
        ["bash", "-c", _step_script()],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"step failed: {proc.stderr}"
    # `gh label create` runs unconditionally as setup; it is not a per-PR action.
    actions = [
        line
        for line in calls.read_text(encoding="utf-8").splitlines()
        if not line.startswith("label create")
    ]
    return proc.stdout, actions


# --------------------------------------------------------------------------
# The regression
# --------------------------------------------------------------------------


def test_stale_draft_is_labelled_but_never_warned_about_auto_close(tmp_path):
    """The exact shape of PR #1061: a draft, 32 days stale, close_days 30."""
    stdout, calls = _run(tmp_path, [_pr(1061, days_stale=32, is_draft=True)])

    assert any(call.startswith("pr edit 1061") and "stale" in call for call in calls)
    assert not any(call.startswith("pr comment 1061") for call in calls), (
        f"a draft was sent an auto-close warning: {calls}"
    )
    assert not any(call.startswith("pr close") for call in calls)
    assert "Labelled: 1" in stdout


def test_no_comment_ever_contains_a_negative_countdown(tmp_path):
    """Property, not wording: the countdown must never go negative.

    Sweeps the whole threshold neighbourhood in both draft states.
    """
    prs = [
        _pr(1000 + i, days_stale=days, is_draft=draft)
        for i, (days, draft) in enumerate(
            (d, b) for d in (27, 29, 30, 31, 40, 90) for b in (True, False)
        )
    ]
    _, calls = _run(tmp_path, prs)
    offenders = [c for c in calls if "auto-closed in -" in c or "in -" in c]
    assert not offenders, f"negative countdown emitted: {offenders}"


def test_draft_is_never_advised_to_become_a_draft(tmp_path):
    _, calls = _run(tmp_path, [_pr(1, days_stale=40, is_draft=True)])
    assert not any("Convert to a draft" in call for call in calls)


# --------------------------------------------------------------------------
# Negative controls: the guard must not swallow the lane's real job
# --------------------------------------------------------------------------


def test_non_draft_past_threshold_is_still_closed(tmp_path):
    """Mutation check: if drafts short-circuited everything, this would fail."""
    stdout, calls = _run(tmp_path, [_pr(1067, days_stale=32, is_draft=False)])

    assert any(call.startswith("pr close 1067") for call in calls), calls
    assert "Closed: 1" in stdout


def test_non_draft_inside_the_window_still_gets_a_real_warning(tmp_path):
    stdout, calls = _run(tmp_path, [_pr(42, days_stale=28, is_draft=False)])

    comments = [c for c in calls if c.startswith("pr comment 42")]
    assert comments, calls
    assert "auto-closed in 2 days" in comments[0]
    assert "Warned: 1" in stdout


def test_bot_author_keeps_its_shorter_threshold(tmp_path):
    _, calls = _run(tmp_path, [_pr(9, days_stale=15, is_draft=False, author="dependabot[bot]")])
    assert any(call.startswith("pr close 9") for call in calls), calls


def test_already_labelled_draft_is_not_relabelled_every_week(tmp_path):
    _, calls = _run(
        tmp_path, [_pr(5, days_stale=40, is_draft=True, labels=("stale",))]
    )
    assert calls == [], f"expected no repeat action, got {calls}"


def test_fresh_pr_is_left_alone(tmp_path):
    _, calls = _run(tmp_path, [_pr(7, days_stale=3, is_draft=False)])
    assert calls == []
