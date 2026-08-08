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

  * a real FAILURE must still block — the condition must override the implicit
    needs-success gate, or a failing session-status would skip the bridge, and a
    skipped required check counts as success.
  * a CANCELLATION must not read as a verdict — neither as a failure (the
    original bug: a superseded run turned red) nor as a PASS.

The second half is why `!cancelled()` replaced an earlier `always() && result !=
'cancelled'` attempt. Skipping on cancelled looked safe on the assumption that a
cancellation implies a successor run — but an operator clicking "Cancel
workflow" has no successor, the job would be SKIPPED, and
scripts/runtime/pr_merge_control.py:53 counts SKIPPED as passing
(PASS_CONCLUSIONS = SUCCESS, SKIPPED, NEUTRAL). That converts an indeterminate
upstream into a definite green on a required gate, with `Onboarding session
status` not itself required so nothing else catches it. Caught in review.

`!cancelled()` cancels the job instead, and CANCELLED is in BAD_CONCLUSIONS.
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


def test_a_cancellation_cancels_the_bridge_rather_than_failing_it() -> None:
    """THE regression. A superseded run must not turn a required context red."""
    assert "!cancelled()" in _condition(), (
        "without !cancelled() the bridge runs after a cancellation and compares "
        "\"cancelled\" against \"success\", reporting hard failure on a required "
        "context for a PR that did nothing wrong"
    )


def test_a_cancellation_is_never_converted_into_a_pass() -> None:
    """The opposite and worse error, caught in review on PR #1287.

    Skipping the bridge on cancellation makes it report SKIPPED, and
    pr_merge_control.py:53 counts SKIPPED as passing. An operator-initiated
    cancel has no successor run, so the required gate would go green with the
    onboarding evidence never gathered."""
    condition = _condition()
    assert "result != 'cancelled'" not in condition, (
        "skip-on-cancelled is back: a cancellation with no successor run now "
        "SKIPS this required check, and SKIPPED counts as a pass"
    )
    assert "always()" not in condition, (
        "always() is back: the bridge will run after a cancellation and report "
        "that indeterminate state as a definite failure"
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
