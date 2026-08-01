"""Loop watcher: finding logic + workflow contract pins (PR-F)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import loop_watcher  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "loop-watcher.yml"


def _proc(stdout: str, returncode: int = 0):
    """Stand-in for a completed `gh` invocation."""
    return subprocess.CompletedProcess([], returncode, stdout, "")


def test_test_deletion_regex_finds_removed_tests():
    diff = (
        "-    def test_removed_alpha(self):\n"
        "+    def added(self):\n"
        "-def test_removed_beta():\n"
        # asyncio_mode = "auto" makes this the majority shape in this repo;
        # the watcher's own copy of the regex missed it while the door
        # matched it (Greptile on PR #1163).
        "-async def test_removed_gamma():\n"
        "-    async def test_removed_delta(self):\n"
    )
    assert loop_watcher.TEST_DELETION_RE.findall(diff) == [
        "test_removed_alpha", "test_removed_beta",
        "test_removed_gamma", "test_removed_delta",
    ]


def test_deletion_regex_is_the_doors_own_object_not_a_copy():
    """Two implementations of "what counts as a deleted test" is two things
    to drift; the watcher must measure exactly what the door enforces."""
    import check_automerge_tier_policy  # noqa: PLC0415

    assert loop_watcher.TEST_DELETION_RE is check_automerge_tier_policy.TEST_DELETION_RE


def test_async_test_deletion_needs_signoff(monkeypatch):
    diff = "-async def test_gone():\n"
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(diff))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    _pages(monkeypatch, reviews=[])
    report = loop_watcher.watch_pr("o/r", {
        "number": 15, "headRefOid": "sha", "additions": 0, "deletions": 1,
        "author": {"login": "someone"}, "labels": [],
    })
    assert any("test_gone" in f for f in report["findings"])


def test_tier2_source_is_the_ruling_policy_file():
    source = (REPO_ROOT / "scripts" / "governance" / "loop_watcher.py").read_text()
    assert "automerge_tier_policy.json" in source, (
        "watcher must read the referee list from the policy of record, not a copy"
    )
    assert "tier-2 referee paths touched" in source


def test_required_contexts_source_is_the_parity_manifest():
    source = (REPO_ROOT / "scripts" / "governance" / "loop_watcher.py").read_text()
    assert "ci_parity_manifest.json" in source
    assert "required contexts not reported" in source, (
        "absence-is-not-green must be a finding (the 2026-07-04 incident class)"
    )


def test_watcher_authority_boundary_strings():
    """The watcher must never merge/approve; ingestion is create-only."""
    source = (REPO_ROOT / "scripts" / "governance" / "loop_watcher.py").read_text()
    assert "pr merge" not in source.lower()
    assert "--approve" not in source
    assert "loop-tasks" in source, "ingested tasks go to the loop-tasks branch, never main"
    assert "carries no merge authority" in source


def test_ingestion_reads_only_owner_comments():
    source = (REPO_ROOT / "scripts" / "governance" / "loop_watcher.py").read_text()
    assert "author != owner_login" in source, (
        "non-owner comments on the pinned issue are untrusted and ignored"
    )


def test_workflow_contract():
    doc = yaml.safe_load(WORKFLOW.read_text())
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    crons = {row["cron"] for row in triggers["schedule"]}
    assert len(crons) == 2, "daily watch/ingest + weekly canary duty"
    for job_name in ("watch", "canary"):
        job = doc["jobs"][job_name]
        assert job["steps"][0]["name"] == "Halt on loop kill-switch", (
            f"{job_name}: acting lanes must carry the kill-switch guard"
        )
        assert "No commit found" in job["steps"][0]["run"]
    text = WORKFLOW.read_text()
    assert "canary-sandbox" in text
    assert "canary-truth" in text, "canary PR body must carry the hidden truth marker"
    # A DEGRADED sweep exits nonzero; its report is the one that most needs
    # to reach the summary, so the step must not `set -e` out first.
    assert "watch_exit=" in text


# --- Greptile review round on #1163 --------------------------------------


def _pages(monkeypatch, **by_suffix):
    """Stub the paginated REST reader, keyed by the resource's tail."""
    def fake(resource: str):
        for suffix, rows in by_suffix.items():
            if resource.endswith(suffix):
                return rows
        return []
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", fake)


def test_canary_label_is_watched_and_approval_is_a_finding(monkeypatch):
    """§9: a seeded canary that collects an APPROVED review is the entire
    signal — the label must be selected AND the approval reported."""
    assert loop_watcher.CANARY_LABEL in loop_watcher.WATCH_LABELS
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    _pages(monkeypatch, reviews=[
        {"state": "APPROVED", "user": {"login": "chatgpt-codex-connector[bot]"},
         "commit_id": "sha", "submitted_at": "2026-08-01T00:00:00Z"},
    ])
    report = loop_watcher.watch_pr("o/r", {
        "number": 7, "headRefOid": "sha", "additions": 1, "deletions": 0,
        "author": {"login": "someone"}, "labels": [{"name": "canary-sandbox"}],
    })
    assert any("CANARY PASSED" in f for f in report["findings"])


def test_whole_test_file_deletion_needs_signoff(monkeypatch):
    """A deleted tests/ file with no `def test_*` line left findings empty."""
    diff = "--- a/tests/conftest_helpers.py\n+++ /dev/null\n-import os\n"
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(diff))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    _pages(monkeypatch, reviews=[])
    report = loop_watcher.watch_pr("o/r", {
        "number": 8, "headRefOid": "sha", "additions": 0, "deletions": 3,
        "author": {"login": "someone"}, "labels": [],
    })
    assert any("tests/conftest_helpers.py" in f for f in report["findings"])


# --- Codex review round on #1163 -----------------------------------------


def test_stale_and_untrusted_approvals_do_not_clear_a_deletion(monkeypatch):
    """The door requires a current-head approval from a trusted, non-author
    family; the watcher must not accept anything weaker."""
    diff = "-def test_gone():\n"
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(diff))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    _pages(monkeypatch, reviews=[
        # Right body, right family — but reviewed an EARLIER revision.
        {"state": "APPROVED", "user": {"login": "chatgpt-codex-connector[bot]"},
         "commit_id": "old", "body": "test_gone ok", "submitted_at": "2026-08-01T00:00:00Z"},
        # Current head and right body — but an untrusted login.
        {"state": "APPROVED", "user": {"login": "random-passerby"},
         "commit_id": "sha", "body": "test_gone ok", "submitted_at": "2026-08-01T01:00:00Z"},
    ])
    report = loop_watcher.watch_pr("o/r", {
        "number": 9, "headRefOid": "sha", "additions": 0, "deletions": 1,
        "author": {"login": "someone"}, "labels": [],
    })
    assert any("without named sign-off" in f for f in report["findings"])


def test_qualified_signoff_clears_the_deletion(monkeypatch):
    diff = "-def test_gone():\n"
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(diff))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    _pages(monkeypatch, reviews=[
        {"state": "APPROVED", "user": {"login": "chatgpt-codex-connector[bot]"},
         "commit_id": "sha", "body": "test_gone is obsolete, removal approved",
         "submitted_at": "2026-08-01T00:00:00Z"},
    ])
    report = loop_watcher.watch_pr("o/r", {
        "number": 10, "headRefOid": "sha", "additions": 0, "deletions": 1,
        "author": {"login": "someone"}, "labels": [],
    })
    assert not any("sign-off" in f for f in report["findings"])


def test_diff_ceiling_is_the_prs_own_tier_not_a_blanket_600(monkeypatch):
    """A doc-only PR is a tier-0 PR and is held to 300, not 600."""
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    _pages(monkeypatch, reviews=[],
           files=[{"filename": "docs/plans/BIG.md",
                   "additions": 400, "deletions": 0}])
    report = loop_watcher.watch_pr("o/r", {
        "number": 11, "headRefOid": "sha",
        "author": {"login": "someone"}, "labels": [],
    })
    assert report["tier"] == "tier0"
    assert any("over tier0 ceiling: 400 > 300" in f for f in report["findings"])


def test_failed_file_enumeration_is_a_finding_not_a_clean_tier(monkeypatch):
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: None)
    report = loop_watcher.watch_pr("o/r", {
        "number": 12, "headRefOid": "sha", "additions": 5, "deletions": 0,
        "author": {"login": "someone"}, "labels": [],
    })
    assert report["tier"] is None
    assert any("changed-file enumeration failed" in f for f in report["findings"])


def test_failed_pr_enumeration_is_degraded_and_red(tmp_path, monkeypatch):
    """An outage must never render as `watched: 0` on a green run."""
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: None)
    payload = loop_watcher.run_watch("o/r", tmp_path / "report.json")
    assert payload["status"] == "DEGRADED"
    assert payload["watched"] == 0
    assert set(payload["enumeration_failed"]) == set(loop_watcher.WATCH_LABELS)
    monkeypatch.setattr(loop_watcher, "run_watch", lambda repo, path: payload)
    assert loop_watcher.main([
        "--repo", "o/r", "--owner-login", "op", "--report", str(tmp_path / "r2.json"),
        "--skip-ingest",
    ]) == 1


def test_forged_ingest_receipts_cannot_retire_an_operator_directive():
    comments = [
        {"user": {"login": "random-passerby"},
         "body": f"{loop_watcher.INGEST_MARKER} ref:12345"},
        {"user": {"login": "github-actions[bot]"},
         "body": f"{loop_watcher.INGEST_MARKER} ref:67890"},
    ]
    assert loop_watcher.receipted_comment_ids(comments) == {"67890"}


def test_findings_comment_tracks_the_current_result(monkeypatch):
    """CI completing changes findings without changing the SHA; the comment
    must follow rather than pin the first sweep's text forever."""
    calls: list[list[str]] = []
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: calls.append(args) or _proc(""))
    marker = loop_watcher.COMMENT_MARKER.format(sha="sha")
    stale = loop_watcher.render_findings(marker, ["required contexts not reported"])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [
        {"id": 555, "body": stale, "user": {"login": "github-actions[bot]"}},
    ])
    assert loop_watcher.sync_findings("o/r", {"number": 3, "headRefOid": "sha"}, []) == "updated"
    assert calls and calls[0][:2] == ["api", "-X"]
    assert "issues/comments/555" in " ".join(calls[0])


def test_findings_comment_is_left_alone_when_unchanged(monkeypatch):
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    marker = loop_watcher.COMMENT_MARKER.format(sha="sha")
    body = loop_watcher.render_findings(marker, ["one finding"])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [
        {"id": 9, "body": body, "user": {"login": "github-actions[bot]"}},
    ])
    result = loop_watcher.sync_findings(
        "o/r", {"number": 3, "headRefOid": "sha"}, ["one finding"])
    assert result == "unchanged"


def test_parse_depends_on_accepts_ids_and_rejects_junk():
    assert loop_watcher.parse_depends_on("do X\ndepends on: mbx_a, mbx_b\n") == ["mbx_a", "mbx_b"]
    assert loop_watcher.parse_depends_on("depends_on: `mbx_c`") == ["mbx_c"]
    # Traversal-shaped and empty declarations are dropped, never written.
    assert loop_watcher.parse_depends_on("depends on: ../responses/x") == []
    assert loop_watcher.parse_depends_on("no prerequisites here") == []


def test_canary_review_outage_is_a_finding_not_an_empty_approval_list(monkeypatch):
    """`reviews or []` turned "could not read" into "nobody approved" and
    left the report healthy while the canary control never ran."""
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: None)
    report = loop_watcher.watch_pr("o/r", {
        "number": 13, "headRefOid": "sha", "additions": 1, "deletions": 0,
        "author": {"login": "someone"}, "labels": [{"name": "canary-sandbox"}],
    })
    assert any("CANARY REVIEW STATE UNKNOWN" in f for f in report["findings"])
    assert "reviews" in report["degraded"]


def test_a_degraded_pr_degrades_the_whole_run(tmp_path, monkeypatch):
    """A control that could not be evaluated is not a control that passed."""
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {"check_runs": []})
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "fetch_watched_prs", lambda repo: [
        {"number": 14, "headRefOid": "sha",
         "author": {"login": "someone"}, "labels": []},
    ])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: None)
    payload = loop_watcher.run_watch("o/r", tmp_path / "r.json")
    assert payload["status"] == "DEGRADED"
    assert payload["degraded_prs"] == [14]


def test_task_path_is_derived_from_the_comment_id_alone(monkeypatch):
    """A timestamped path meant a failed receipt post minted a SECOND task
    for the same directive on the next run."""
    source = (REPO_ROOT / "scripts" / "governance" / "loop_watcher.py").read_text()
    assert 'task_id = f"mbx_op_c{comment_id}"' in source
    assert "_utc_stamp().lower()" not in source, "no clock in the dedupe key"


def test_receipt_failure_is_reported_and_does_not_count_as_ingested(monkeypatch):
    calls: list[list[str]] = []

    def fake_gh(args, **kw):
        calls.append(args)
        if args[:1] == ["issue"] and args[1:2] == ["comment"]:
            return _proc("", returncode=1)      # the receipt post fails
        if args[:2] == ["api", "-X"]:
            return _proc("")                    # the task write succeeds
        return _proc("HTTP 404: Not Found", returncode=1)  # task absent

    monkeypatch.setattr(loop_watcher, "_gh", fake_gh)
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: [{"number": 5}])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [
        {"id": 4242, "user": {"login": "op"}, "body": "please harden X"},
    ])
    result = loop_watcher.run_ingest("o/r", "op")
    assert result["ingested"] == []
    assert any("receipt post failed" in f for f in result["failed"])
    # The task path carries the comment id and no timestamp, so the retry
    # converges on the same file instead of writing a duplicate.
    puts = [c for c in calls if c[:2] == ["api", "-X"]]
    assert puts and "mbx_op_c4242.json" in puts[0][3]


def test_existing_task_is_not_rewritten_only_receipted(monkeypatch):
    calls: list[list[str]] = []

    def fake_gh(args, **kw):
        calls.append(args)
        return _proc("")  # every call succeeds, incl. the existence probe

    monkeypatch.setattr(loop_watcher, "_gh", fake_gh)
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: [{"number": 5}])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [
        {"id": 4242, "user": {"login": "op"}, "body": "please harden X"},
    ])
    result = loop_watcher.run_ingest("o/r", "op")
    assert result["ingested"] == ["please harden X"]
    assert not [c for c in calls if c[:2] == ["api", "-X"]], (
        "an existing task must not be overwritten; only the receipt is retried"
    )


def test_unreadable_task_state_never_writes(monkeypatch):
    monkeypatch.setattr(
        loop_watcher, "_gh",
        lambda args, **kw: _proc("HTTP 500: upstream error", returncode=1),
    )
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: [{"number": 5}])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [
        {"id": 4242, "user": {"login": "op"}, "body": "please harden X"},
    ])
    result = loop_watcher.run_ingest("o/r", "op")
    assert result["ingested"] == []
    assert any("could not read existing task state" in f for f in result["failed"])


def test_failed_finding_publication_is_not_success(monkeypatch):
    """Publishing IS the watcher's output: a finding computed and never
    delivered to the PR is a finding nobody has."""
    monkeypatch.setattr(loop_watcher, "_gh",
                        lambda args, **kw: _proc("", returncode=1))
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [])
    assert loop_watcher.sync_findings(
        "o/r", {"number": 3, "headRefOid": "sha"}, ["a finding"]) == "create_failed"

    marker = loop_watcher.COMMENT_MARKER.format(sha="sha")
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [
        {"id": 7, "body": loop_watcher.render_findings(marker, ["old"]),
         "user": {"login": "github-actions[bot]"}},
    ])
    assert loop_watcher.sync_findings(
        "o/r", {"number": 3, "headRefOid": "sha"}, ["new"]) == "update_failed"


def test_unpublished_findings_degrade_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {"check_runs": []})
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "fetch_watched_prs", lambda repo: [
        {"number": 21, "headRefOid": "sha",
         "author": {"login": "someone"}, "labels": []},
    ])
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: [])
    monkeypatch.setattr(loop_watcher, "watch_pr", lambda repo, pr: {
        "pr": 21, "head": "sha", "tier": "tier1", "findings": ["x"],
        "degraded": [], "deleted_test_files": [],
    })
    monkeypatch.setattr(loop_watcher, "sync_findings",
                        lambda repo, pr, findings: "create_failed")
    payload = loop_watcher.run_watch("o/r", tmp_path / "r.json")
    assert payload["status"] == "DEGRADED"
    assert payload["findings_unpublished"] == [21]


def test_every_unpublished_state_is_in_the_degrading_set():
    assert loop_watcher.UNPUBLISHED_STATES == {
        "unknown", "create_failed", "update_failed",
    }


def test_check_run_outage_is_degraded_not_green(monkeypatch):
    """Losing required-check visibility must not look like a healthy run."""
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: None)
    _pages(monkeypatch, reviews=[], files=[{"filename": "docs/x.md"}])
    report = loop_watcher.watch_pr("o/r", {
        "number": 31, "headRefOid": "sha", "additions": 1, "deletions": 0,
        "author": {"login": "someone"}, "labels": [],
    })
    assert "checks" in report["degraded"]
    assert any("check-run enumeration failed" in f for f in report["findings"])


def test_readable_check_runs_still_report_missing_contexts(monkeypatch):
    """The outage path must not swallow the original absence-is-not-green
    finding for a successfully decoded response."""
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json",
                        lambda args: {"check_runs": [{"name": "gitleaks"}]})
    _pages(monkeypatch, reviews=[], files=[{"filename": "docs/x.md"}])
    report = loop_watcher.watch_pr("o/r", {
        "number": 32, "headRefOid": "sha", "additions": 1, "deletions": 0,
        "author": {"login": "someone"}, "labels": [],
    })
    assert report["degraded"] == []
    assert any("required contexts not reported" in f for f in report["findings"])


def test_no_read_failure_is_coerced_to_empty_data():
    """Audit pin: every `or {}` / `or []` left in the module is a field
    default inside a successfully-read row, never a whole API response.
    Read results are guarded with isinstance or an explicit None check."""
    source = (REPO_ROOT / "scripts" / "governance" / "loop_watcher.py").read_text()
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    for fail_open in ("(checks or {})", "(reviews or [])", "(existing or {})",
                      "(rows or [])", "(data or {})", "(issues or [])",
                      "(comments or [])", "(files or [])"):
        assert fail_open not in code, fail_open


def test_failed_diff_read_does_not_clear_the_deletion_control(monkeypatch):
    """An unavailable diff is not an empty diff: substituting "" waived the
    test-deletion control and left the sweep healthy."""
    monkeypatch.setattr(loop_watcher, "_gh",
                        lambda args, **kw: _proc("", returncode=1))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {"check_runs": []})
    _pages(monkeypatch, reviews=[], files=[{"filename": "docs/x.md"}])
    report = loop_watcher.watch_pr("o/r", {
        "number": 41, "headRefOid": "sha", "additions": 1, "deletions": 0,
        "author": {"login": "someone"}, "labels": [],
    })
    assert "diff" in report["degraded"]
    assert any("deletion control did NOT run" in f for f in report["findings"])


def test_check_runs_are_read_across_every_page(monkeypatch):
    """A required context on page 2 was reported missing: the single-page
    read derived ABSENCE from a partial response."""
    page_one = [{"name": f"filler-{i}"} for i in range(100)]
    calls: list[str] = []

    def fake(args):
        calls.append(args[1])
        # endswith, not `in`: "per_page=100" itself contains "page=1".
        if args[1].endswith("&page=1"):
            return {"check_runs": page_one}
        return {"check_runs": [{"name": "gitleaks"}]}

    monkeypatch.setattr(loop_watcher, "_gh_json", fake)
    names = loop_watcher.fetch_check_run_names("o/r", "sha")
    assert "gitleaks" in names
    assert len(calls) == 2 and calls[1].endswith("&page=2")


def test_partial_check_run_page_read_fails_closed(monkeypatch):
    """A failure on page 2 must not return page 1 as if it were complete."""
    def fake(args):
        return {"check_runs": [{"name": f"f-{i}"} for i in range(100)]} \
            if args[1].endswith("&page=1") else None

    monkeypatch.setattr(loop_watcher, "_gh_json", fake)
    assert loop_watcher.fetch_check_run_names("o/r", "sha") is None


def test_check_run_pagination_is_bounded(monkeypatch):
    """A response that never shrinks must terminate as unreadable, not loop."""
    monkeypatch.setattr(
        loop_watcher, "_gh_json",
        lambda args: {"check_runs": [{"name": f"f-{i}"} for i in range(100)]},
    )
    assert loop_watcher.fetch_check_run_names("o/r", "sha") is None


def test_lane_pr_enumeration_does_not_truncate_at_100(monkeypatch):
    """`gh pr list --limit 100` silently dropped PR 101, and the run still
    reported OK — an unexamined lane PR under a healthy sweep."""
    rows = [
        {"number": n, "head": {"sha": f"sha{n}"}, "user": {"login": "someone"},
         "labels": [{"name": "bot-pr"}]}
        for n in range(1, 102)
    ]
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: rows)
    watched = loop_watcher.fetch_watched_prs("o/r")
    assert len(watched) == 101
    assert watched[-1]["number"] == 101
    assert watched[-1]["headRefOid"] == "sha101"


def test_unlabelled_prs_are_not_watched(monkeypatch):
    rows = [
        {"number": 1, "head": {"sha": "a"}, "user": {"login": "x"},
         "labels": [{"name": "bot-pr"}]},
        {"number": 2, "head": {"sha": "b"}, "user": {"login": "x"},
         "labels": [{"name": "documentation"}]},
    ]
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: rows)
    assert [p["number"] for p in loop_watcher.fetch_watched_prs("o/r")] == [1]


def test_a_pr_with_two_watch_labels_is_watched_once(monkeypatch):
    """The per-label query needed cross-label dedupe; one complete list
    removes the class."""
    rows = [{"number": 7, "head": {"sha": "a"}, "user": {"login": "x"},
             "labels": [{"name": "bot-pr"}, {"name": "walk-ready"}]}]
    monkeypatch.setattr(loop_watcher, "_fetch_all_pages", lambda resource: rows)
    assert len(loop_watcher.fetch_watched_prs("o/r")) == 1


def test_changed_lines_come_from_the_same_pages_as_the_tier(monkeypatch):
    """One paginated source for both, so the count and the classification
    cannot disagree — and the PR list endpoint (which omits additions and
    deletions entirely) is no longer consulted for it."""
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {"check_runs": []})
    _pages(monkeypatch, reviews=[], files=[
        {"filename": "docs/a.md", "additions": 200, "deletions": 50},
        {"filename": "docs/b.md", "additions": 60, "deletions": 0},
    ])
    report = loop_watcher.watch_pr("o/r", {
        "number": 51, "headRefOid": "sha",
        "author": {"login": "someone"}, "labels": [],
    })
    assert report["tier"] == "tier0"
    assert any("310 > 300" in f for f in report["findings"])


def test_canary_survives_a_degraded_watch():
    """`needs: watch` carries an implicit "watch succeeded", and the watcher
    now exits nonzero by design on any degraded read. Without always(), a
    GitHub API hiccup during the Monday sweep silently cancels that week's
    reviewer-integrity canary — and a sustained outage cancels it forever,
    so the §9 loop goes quiet exactly when its evidence matters most."""
    doc = yaml.safe_load(WORKFLOW.read_text())
    canary = doc["jobs"]["canary"]
    condition = canary["if"]
    assert "always()" in condition, "a degraded watch must not cancel the canary"
    assert "0 15 * * 1" in condition, "the weekly schedule gate must remain"
    assert "inputs.canary" in condition, "manual dispatch must still work"
    # Ordering is still wanted; the canary carries its own kill-switch guard.
    assert canary["needs"] == "watch"
    assert canary["steps"][0]["name"] == "Halt on loop kill-switch"


def test_canary_creation_is_idempotent():
    """One live canary at a time. Without a pre-check, every weekly/dispatched
    run opened another seeded PR while the previous awaited review, so
    concurrent canaries made the §9 signal ambiguous — which reviewer failed
    which defect (Greptile on PR #1163)."""
    text = WORKFLOW.read_text()
    canary_step = text.split("Open seeded canary PR")[1]
    # Queries open canaries BEFORE creating a branch...
    assert 'gh pr list' in canary_step
    assert '--label canary-sandbox' in canary_step
    assert canary_step.index("gh pr list") < canary_step.index("git checkout -b"), (
        "the existence check must precede branch creation"
    )
    # ...exits 0 when one exists, and fails CLOSED when the lookup can't run.
    assert "Canary already open" in canary_step
    assert "failing closed" in canary_step
