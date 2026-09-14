"""The backlog lane must survive GitHub refusing an expensive query.

Between 2026-08-26 and 2026-09-14 the hourly `merge-master-mike-backlog`
workflow failed 115 consecutive times. Every failure was the same line:

    ERROR: gh pr list --state open --limit 100 --json ...,statusCheckRollup,...
    failed: HTTP 502/504 (https://api.github.com/graphql)

`statusCheckRollup` expands to every check run on every PR, so requesting it
across a 100-PR page builds a query GitHub answers with a 5xx instead of a
result. `gh_json` had no retry and no paging, so that one call aborted the run
-- and nothing merged to main for 15 days.

Two properties are pinned here, and the second matters more than the first:

* the expensive field is not requested in bulk, and a transient 5xx is retried;
* a rollup that could NOT be fetched is never read as "no checks are failing".

The second is a real fail-open in `classify_pr`: a non-draft, mergeable,
unopposed PR carrying an empty rollup classifies as GITHUB_GREEN_NEEDS_PACKET,
which is one of DEFAULT_FANOUT_STATUSES -- a lane the backlog acts on. Making
the fetch resilient without that guard would have converted a network blip into
"this PR is green".
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.runtime import pr_merge_control as prc


def _pr(**overrides):
    pr = {
        "number": 7,
        "title": "t",
        "url": "u",
        "author": {"login": "a"},
        "headRefName": "h",
        "headRefOid": "sha",
        "baseRefName": "main",
        "baseRefOid": "base",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "updatedAt": "2026-09-14T00:00:00Z",
        "statusCheckRollup": [],
    }
    pr.update(overrides)
    return pr


# --------------------------------------------------------------------------
# The fail-open guard. These are the tests that matter.
# --------------------------------------------------------------------------


def test_unfetchable_rollup_is_never_classified_green():
    """A PR whose checks could not be read must not be called green."""
    pr = _pr(rollupUnavailable="HTTP 504: Gateway Timeout")
    result = prc.classify_pr(pr)

    assert result["status"] != "GITHUB_GREEN_NEEDS_PACKET"
    assert result["status"] == "BLOCKED_CHECKS_UNAVAILABLE"
    assert any("unavailable" in reason for reason in result["reasons"])


def test_unfetchable_rollup_status_is_not_a_lane_the_backlog_acts_on():
    """Skipping the PR is the conservative outcome; prove it is skipped."""
    assert "BLOCKED_CHECKS_UNAVAILABLE" not in prc.DEFAULT_FANOUT_STATUSES


def test_negative_control_same_pr_without_the_marker_still_reads_green():
    """Mutation check: the guard must fire on the marker, not on everything.

    Identical PR, marker removed. If this also came back blocked, the test
    above would pass for the wrong reason and the queue would stall on every
    genuinely-green PR.
    """
    assert prc.classify_pr(_pr())["status"] == "GITHUB_GREEN_NEEDS_PACKET"


def test_failed_hydration_marks_the_pr_instead_of_faking_an_empty_rollup(monkeypatch):
    """End to end: a 5xx on one PR's rollup must not read as green."""
    monkeypatch.setattr(prc, "gh_json", lambda args, **kw: [_pr()] if args[0] == "pr" and args[1] == "list" else None)

    def explode(_number):
        raise prc.PRControlError("HTTP 504: 504 Gateway Timeout")

    monkeypatch.setattr(prc, "fetch_pr_rollup", explode)

    (fetched,) = prc.fetch_open_prs(100)
    assert fetched["statusCheckRollup"] == []
    assert "504" in fetched["rollupUnavailable"]
    assert prc.classify_pr(fetched)["status"] == "BLOCKED_CHECKS_UNAVAILABLE"


# --------------------------------------------------------------------------
# The query that caused the outage
# --------------------------------------------------------------------------


def test_bulk_pr_list_does_not_request_status_check_rollup():
    """The exact field whose bulk expansion GitHub refused."""
    assert "statusCheckRollup" not in prc.PR_LIST_FIELDS
    for field in ("number", "headRefOid", "isDraft", "mergeable", "reviewDecision"):
        assert field in prc.PR_LIST_FIELDS, f"{field} is consumed downstream"


def test_rollup_is_hydrated_one_pr_at_a_time(monkeypatch):
    calls: list[list[str]] = []

    def fake_gh_json(args, **_kw):
        calls.append(list(args))
        if args[:2] == ["pr", "list"]:
            return [_pr(number=1), _pr(number=2)]
        return {"statusCheckRollup": [{"name": "pytest (3.11)", "conclusion": "SUCCESS"}]}

    monkeypatch.setattr(prc, "gh_json", fake_gh_json)
    prs = prc.fetch_open_prs(100)

    assert [c[:2] for c in calls] == [["pr", "list"], ["pr", "view"], ["pr", "view"]]
    assert all(pr["statusCheckRollup"] for pr in prs)
    assert all("rollupUnavailable" not in pr for pr in prs)


# --------------------------------------------------------------------------
# Retry policy: narrow on purpose
# --------------------------------------------------------------------------


def test_transient_5xx_is_retried_and_then_succeeds(monkeypatch):
    attempts = {"n": 0}

    def fake_run(cmd, **_kw):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise prc.PRControlError("gh pr list failed: HTTP 502: 502 Bad Gateway")
        return prc.CommandResult(0, '{"ok": true}', "")

    monkeypatch.setattr(prc, "run", fake_run)
    monkeypatch.setattr(prc.time, "sleep", lambda _s: None)

    assert prc.gh_json(["pr", "list"]) == {"ok": True}
    assert attempts["n"] == 3


def test_timeout_is_retried_because_it_is_the_same_condition_as_a_504(monkeypatch):
    attempts = {"n": 0}

    def fake_run(cmd, **_kw):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise subprocess.TimeoutExpired(cmd, 120)
        return prc.CommandResult(0, "[]", "")

    monkeypatch.setattr(prc, "run", fake_run)
    monkeypatch.setattr(prc.time, "sleep", lambda _s: None)

    assert prc.gh_json(["pr", "list"]) == []
    assert attempts["n"] == 2


def test_deterministic_failure_is_not_retried(monkeypatch):
    """Negative control: retrying a 404 wastes time and hides the real error."""
    attempts = {"n": 0}

    def fake_run(cmd, **_kw):
        attempts["n"] += 1
        raise prc.PRControlError("gh pr view failed: HTTP 404: Not Found")

    monkeypatch.setattr(prc, "run", fake_run)
    monkeypatch.setattr(prc.time, "sleep", lambda _s: pytest.fail("slept on a 404"))

    with pytest.raises(prc.PRControlError, match="404"):
        prc.gh_json(["pr", "view", "1"])
    assert attempts["n"] == 1


def test_malformed_json_is_not_retried(monkeypatch):
    attempts = {"n": 0}

    def fake_run(cmd, **_kw):
        attempts["n"] += 1
        return prc.CommandResult(0, "not json", "")

    monkeypatch.setattr(prc, "run", fake_run)
    monkeypatch.setattr(prc.time, "sleep", lambda _s: pytest.fail("slept on bad JSON"))

    with pytest.raises(prc.PRControlError, match="non-JSON"):
        prc.gh_json(["pr", "list"])
    assert attempts["n"] == 1


def test_retry_gives_up_and_reports_the_real_error(monkeypatch):
    monkeypatch.setattr(
        prc,
        "run",
        lambda cmd, **_kw: (_ for _ in ()).throw(
            prc.PRControlError("failed: HTTP 504: 504 Gateway Timeout")
        ),
    )
    monkeypatch.setattr(prc.time, "sleep", lambda _s: None)

    with pytest.raises(prc.PRControlError, match="504"):
        prc.gh_json(["pr", "list"], attempts=2)


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("HTTP 502: 502 Bad Gateway", True),
        ("HTTP 504: 504 Gateway Timeout", True),
        ("HTTP 503: Service Unavailable", True),
        ("You have exceeded a secondary rate limit", True),
        ("HTTP 404: Not Found", False),
        ("unknown flag: --merge-mode", False),
        ("gh auth login required", False),
    ],
)
def test_transient_classifier(detail, expected):
    assert prc.is_transient_gh_error(detail) is expected
