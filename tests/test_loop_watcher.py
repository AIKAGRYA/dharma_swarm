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
    diff = "-    def test_removed_alpha(self):\n+    def added(self):\n-def test_removed_beta():\n"
    assert loop_watcher.TEST_DELETION_RE.findall(diff) == [
        "test_removed_alpha", "test_removed_beta",
    ]


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
           files=[{"filename": "docs/plans/BIG.md"}])
    report = loop_watcher.watch_pr("o/r", {
        "number": 11, "headRefOid": "sha", "additions": 400, "deletions": 0,
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
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: None)
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
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: (
        [{"number": 14, "headRefOid": "sha", "additions": 1, "deletions": 0,
          "author": {"login": "someone"}, "labels": []}]
        if args[:2] == ["pr", "list"] else {}
    ))
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
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
