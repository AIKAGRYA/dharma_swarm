"""The admission-parity bridge must not report a cancellation as a failure.

Observed twice on 2026-08-07, on two unrelated PRs:

    Onboarding session status   queued 03:24:07Z -> CANCELLED 04:55:09Z
    Onboarding admission parity created 04:55:10Z -> ran 05:17Z -> FAILURE

`pr-ci-health` supersedes a run whose checks have starved in the queue. The
bridge carries `always()`, so it still runs, and its body is

    test "${SESSION_STATUS_RESULT}" = "success"

With the dependency cancelled that compares "cancelled" against "success" and
reports hard `failure` on a REQUIRED context. The upstream job did not fail; it
was never given a runner. While the queue stays deep enough to starve
session-status, no PR can earn a green parity check at all.

Both halves of the condition are load-bearing and this file pins both:

  * `always()` must stay — without it a genuinely FAILING session-status would
    skip the bridge, and a skipped required check counts as success. That is the
    false-green the job's own comment exists to prevent.
  * `!= 'cancelled'` must stay — without it a supersession reads as a verdict.

Skipping on cancelled is safe because a cancellation means a newer run already
exists for this head and will report.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "active-track.yml"
)
JOB = "onboarding-admission-parity-compat"


def _condition() -> str:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return " ".join(str(doc["jobs"][JOB]["if"]).split())


def test_a_cancelled_dependency_does_not_report_as_failure() -> None:
    """THE regression. A superseded run must skip the bridge, not fail it."""
    assert "needs.onboarding-status.result != 'cancelled'" in _condition(), (
        "the parity bridge will report a cancelled dependency as a hard failure "
        "on a required context; a PR that did nothing wrong goes red"
    )


def test_always_is_retained_so_a_real_failure_still_blocks() -> None:
    """The opposite error: dropping always() would skip the bridge whenever
    session-status fails, and GitHub counts a skipped required check as
    success. That converts a real failure into a green merge."""
    assert "always()" in _condition(), (
        "always() removed — a failing session-status would now SKIP this bridge, "
        "and a skipped required check passes branch protection (false green)"
    )


def test_the_bridge_still_gates_on_the_session_status_result() -> None:
    """The condition decides whether the job runs; the body decides pass/fail.
    Neutralising the body would make the bridge decorative."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"][JOB]["steps"]
    body = " ".join(str(step.get("run", "")) for step in steps)
    assert "SESSION_STATUS_RESULT" in body
    assert "success" in body


def test_the_bridge_still_depends_on_session_status() -> None:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    needs = doc["jobs"][JOB]["needs"]
    needs = [needs] if isinstance(needs, str) else list(needs)
    assert "onboarding-status" in needs
