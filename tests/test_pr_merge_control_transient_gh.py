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
    """End to end through the real fetch_pr_rollup: a 5xx must not read green."""
    def fake_gh_json(args, **_kw):
        if args[:2] == ["pr", "list"]:
            return [_pr()]
        raise prc.PRControlError("gh pr view failed: HTTP 504: 504 Gateway Timeout")

    monkeypatch.setattr(prc, "gh_json", fake_gh_json)

    (fetched,) = prc.fetch_open_prs(100)
    assert fetched["statusCheckRollup"] == []
    assert "504" in fetched["rollupUnavailable"]
    assert prc.classify_pr(fetched)["status"] == "BLOCKED_CHECKS_UNAVAILABLE"


# --------------------------------------------------------------------------
# The query that caused the outage
# --------------------------------------------------------------------------


def _capture_calls(monkeypatch, prs, rollup=None):
    """Record the real argv handed to gh, not just the constants."""
    calls: list[list[str]] = []
    payload = {"statusCheckRollup": rollup if rollup is not None else [
        {"name": "pytest (3.11)", "conclusion": "SUCCESS"}
    ]}

    def fake_gh_json(args, **_kw):
        calls.append(list(args))
        if args[:2] == ["pr", "list"]:
            return prs
        return payload

    monkeypatch.setattr(prc, "gh_json", fake_gh_json)
    return calls


def test_bulk_pr_list_query_as_actually_sent_omits_status_check_rollup(monkeypatch):
    """The exact field whose bulk expansion GitHub refused.

    Asserted against the argv `fetch_open_prs` really builds, not against
    PR_LIST_FIELDS. An earlier version of this test read the constant, so a
    change appending ",statusCheckRollup" at the call site -- reinstating the
    outage verbatim -- passed it.
    """
    calls = _capture_calls(monkeypatch, [_pr(number=1)])
    prc.fetch_open_prs(100)

    (listing,) = [c for c in calls if c[:2] == ["pr", "list"]]
    assert "--json" in listing
    sent_fields = listing[listing.index("--json") + 1]
    assert "statusCheckRollup" not in sent_fields, (
        f"the bulk query still requests the field GitHub refused: {sent_fields}"
    )
    for field in ("number", "headRefOid", "isDraft", "mergeable", "reviewDecision"):
        assert field in sent_fields, f"{field} is consumed downstream"


def test_rollup_is_hydrated_one_pr_at_a_time(monkeypatch):
    calls = _capture_calls(monkeypatch, [_pr(number=1), _pr(number=2)])
    prs = prc.fetch_open_prs(100)

    views = [c for c in calls if c[:2] == ["pr", "view"]]
    assert [c[2] for c in views] == ["1", "2"]
    for view in views:
        assert view[view.index("--json") + 1] == "statusCheckRollup"
    assert all(pr["statusCheckRollup"] for pr in prs)
    assert all("rollupUnavailable" not in pr for pr in prs)


# --------------------------------------------------------------------------
# A successful call that answers with nothing is still missing data
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload,why",
    [
        ({}, "gh omits the key when the last-commit node does not resolve"),
        ({"statusCheckRollup": None}, "explicit null"),
        ({"statusCheckRollup": "nope"}, "wrong type"),
    ],
)
def test_successful_but_empty_rollup_payload_raises(monkeypatch, payload, why):
    """`{}.get(x) or []` would have handed back a green-looking empty rollup."""
    monkeypatch.setattr(prc, "gh_json", lambda args, **kw: payload)
    with pytest.raises(prc.PRControlError):
        prc.fetch_pr_rollup(7)


def test_missing_rollup_key_end_to_end_is_blocked_not_green(monkeypatch):
    """The whole path: gh succeeds, answers with {}, PR must not read green."""
    def fake_gh_json(args, **_kw):
        if args[:2] == ["pr", "list"]:
            return [_pr(number=1)]
        return {}  # a real gh shape when the head commit does not resolve

    monkeypatch.setattr(prc, "gh_json", fake_gh_json)
    (fetched,) = prc.fetch_open_prs(100)
    assert fetched["rollupUnavailable"]
    assert prc.classify_pr(fetched)["status"] == "BLOCKED_CHECKS_UNAVAILABLE"


def test_empty_list_rollup_is_honoured_not_treated_as_missing(monkeypatch):
    """Negative control: a genuine zero-check PR is not an error.

    Without this, the guard above could be 'raise on anything falsy', which
    would break every PR whose checks have not started.
    """
    monkeypatch.setattr(prc, "gh_json", lambda args, **kw: {"statusCheckRollup": []})
    assert prc.fetch_pr_rollup(7) == []


# --------------------------------------------------------------------------
# Bounding the worst case
# --------------------------------------------------------------------------


def test_drafts_and_conflicts_are_not_hydrated(monkeypatch):
    """classify_pr short-circuits on both, so the round trip buys nothing."""
    calls = _capture_calls(
        monkeypatch,
        [
            _pr(number=1, isDraft=True),
            _pr(number=2, mergeable="CONFLICTING"),
            _pr(number=3),
        ],
    )
    prc.fetch_open_prs(100)
    views = [c[2] for c in calls if c[:2] == ["pr", "view"]]
    assert views == ["3"], f"hydrated PRs it never needed: {views}"


def test_breaker_stops_paying_the_retry_ladder_once_failure_is_systemic(monkeypatch):
    """A per-PR ladder across a whole backlog can outrun the job timeout."""
    attempted: list[int] = []

    def explode(number, **_kw):
        attempted.append(number)
        raise prc.PRControlError("HTTP 504: 504 Gateway Timeout")

    monkeypatch.setattr(prc, "gh_json", lambda args, **kw: [_pr(number=n) for n in range(1, 11)])
    monkeypatch.setattr(prc, "fetch_pr_rollup", explode)

    prs = prc.fetch_open_prs(100)
    assert len(attempted) == prc.GH_HYDRATE_BREAKER, (
        f"breaker did not trip; attempted {len(attempted)} of 10"
    )
    # Every PR is still accounted for, and none of them reads as green.
    assert all(pr["rollupUnavailable"] for pr in prs)
    assert {prc.classify_pr(pr)["status"] for pr in prs} == {
        "BLOCKED_CHECKS_UNAVAILABLE"
    }


def test_breaker_resets_on_success_so_one_bad_pr_does_not_stop_the_scan(monkeypatch):
    """Negative control: the breaker must mean 'systemic', not 'ever failed'."""
    seen: list[int] = []

    def flaky(number, **_kw):
        seen.append(number)
        if number % 2:
            raise prc.PRControlError("HTTP 502: 502 Bad Gateway")
        return []

    monkeypatch.setattr(prc, "gh_json", lambda args, **kw: [_pr(number=n) for n in range(1, 11)])
    monkeypatch.setattr(prc, "fetch_pr_rollup", flaky)

    prc.fetch_open_prs(100)
    assert seen == list(range(1, 11)), "an alternating failure tripped the breaker"


def test_pr_list_must_return_a_list(monkeypatch):
    monkeypatch.setattr(prc, "gh_json", lambda args, **kw: {"unexpected": "shape"})
    with pytest.raises(prc.PRControlError, match="expected a list"):
        prc.fetch_open_prs(100)


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
        ("HTTP 500: Internal Server Error", True),
        ("You have exceeded a secondary rate limit", True),
        # GitHub's canonical answer to an over-expensive GraphQL query is
        # HTTP 200 with an errors array, surfaced by gh as this message. It
        # is at least as common as the 502 and must be retried.
        (
            "gh: Something went wrong while executing your query. "
            "This may be the result of a timeout, or it could be a GitHub bug.",
            True,
        ),
        ('Post "https://api.github.com/graphql": net/http: TLS handshake timeout', True),
        ("read tcp 10.1.0.4:52000->140.82.121.6:443: connection reset by peer", True),
        ("dial tcp: lookup api.github.com: i/o timeout", True),
        ("unexpected EOF", True),
        ("HTTP 404: Not Found", False),
        ("unknown flag: --merge-mode", False),
        ("gh auth login required", False),
    ],
)
def test_transient_classifier(detail, expected):
    assert prc.is_transient_gh_error(detail) is expected


# --------------------------------------------------------------------------
# The lane must stay loud. A silent green stall is worse than a red run.
# --------------------------------------------------------------------------


def _fanout_args(tmp_path):
    import argparse

    return argparse.Namespace(
        state_root=str(tmp_path),
        limit=100,
        statuses="GITHUB_GREEN_NEEDS_PACKET",
        agents="codex,claude",
        max_prs=4,
        dry_run=False,
        packet_only=True,
        reprocess_current=True,
        ci_truth_contract="unused.json",
        timeout_s=None,
        kill_grace_s=1.0,
        allow_pending=False,
        human_approved=False,
        allow_backup_reviewer=False,
        backup_reviewers="",
        backup_reviewer_reason="",
        required_reviewers="codex,claude",
        accept_github_reviews=False,
        merge_method="squash",
        merge_auto=True,
        nats_session=False,
        nats_subjects="",
        nats_required=False,
        nats_timeout_s=1.0,
    )


def _summary(statuses):
    return {
        "generated_at": "2026-09-14T00:00:00Z",
        "repo": "owner/repo",
        "total": len(statuses),
        "counts": {},
        "items": [
            {
                "number": 100 + i,
                "title": f"pr {i}",
                "status": status,
                "updatedAt": "2026-09-14T00:00:00Z",
                "reasons": [],
                "url": f"https://example.invalid/pull/{100 + i}",
            }
            for i, status in enumerate(statuses)
        ],
    }


def _run_fanout(tmp_path, monkeypatch, statuses):
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")
    monkeypatch.setattr(prc, "fetch_open_prs", lambda _limit: [])
    monkeypatch.setattr(
        prc, "build_queue_summary", lambda _prs, _repo: _summary(statuses)
    )
    monkeypatch.setattr(prc, "stamp", lambda: "20260914T000000Z")
    return prc.cmd_fanout(_fanout_args(tmp_path))


def test_fleetwide_unreadable_checks_exit_nonzero(tmp_path, monkeypatch):
    """The 115-run outage was visible because the lane went red.

    Classifying unreadable PRs as blocked keeps them out of the fanout, but on
    its own it would turn that same outage into a green workflow publishing an
    empty queue -- a silent stall, which is strictly harder to notice.
    """
    code = _run_fanout(
        tmp_path, monkeypatch, ["BLOCKED_CHECKS_UNAVAILABLE"] * 5
    )
    assert code != 0


def test_a_couple_of_unreadable_prs_is_a_bad_day_not_an_outage(tmp_path, monkeypatch):
    """Negative control: the lane must not go red over ordinary flakiness."""
    code = _run_fanout(
        tmp_path, monkeypatch, ["BLOCKED_CHECKS_UNAVAILABLE", "DRAFT", "DRAFT"]
    )
    assert code == 0


def test_healthy_scan_still_exits_zero(tmp_path, monkeypatch):
    assert _run_fanout(tmp_path, monkeypatch, ["DRAFT", "BLOCKED_CONFLICT"]) == 0


def test_unavailable_rollup_numbers_reads_only_the_unreadable(tmp_path):
    summary = _summary(
        ["DRAFT", "BLOCKED_CHECKS_UNAVAILABLE", "GITHUB_GREEN_NEEDS_PACKET"]
    )
    assert prc.unavailable_rollup_numbers(summary) == [101]


def test_repo_name_is_retried_because_it_is_the_first_gh_call_of_the_run(monkeypatch):
    """cmd_fanout calls repo_name() before fetch_open_prs().

    An unretried 5xx here aborts the run exactly the way the bulk query used
    to, so hardening only the PR fetch would have left the outage shape armed
    one call earlier.
    """
    attempts = {"n": 0}

    def fake_run(cmd, **_kw):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise prc.PRControlError("gh repo view failed: HTTP 502: 502 Bad Gateway")
        return prc.CommandResult(0, '"owner/repo"', "")

    monkeypatch.setattr(prc, "run", fake_run)
    monkeypatch.setattr(prc.time, "sleep", lambda _s: None)

    assert prc.repo_name() == "owner/repo"
    assert attempts["n"] == 2, "repo_name did not retry a transient failure"
