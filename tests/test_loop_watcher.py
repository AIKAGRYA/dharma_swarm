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


# --- Greptile review round on #1163 --------------------------------------


def test_canary_label_is_watched_and_approval_is_a_finding(monkeypatch):
    """§9: a seeded canary that collects an APPROVED review is the entire
    signal — the label must be selected AND the approval reported."""
    assert loop_watcher.CANARY_LABEL in loop_watcher.WATCH_LABELS
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(""))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    report = loop_watcher.watch_pr("o/r", {
        "number": 7, "headRefOid": "sha", "files": [], "additions": 1, "deletions": 0,
        "labels": [{"name": "canary-sandbox"}],
        "latestReviews": [{"state": "APPROVED", "author": {"login": "codex[bot]"}}],
    })
    assert any("CANARY PASSED" in f for f in report["findings"])


def test_whole_test_file_deletion_needs_signoff(monkeypatch):
    """A deleted tests/ file with no `def test_*` line left findings empty."""
    diff = "--- a/tests/conftest_helpers.py\n+++ /dev/null\n-import os\n"
    monkeypatch.setattr(loop_watcher, "_gh", lambda args, **kw: _proc(diff))
    monkeypatch.setattr(loop_watcher, "_gh_json", lambda args: {})
    report = loop_watcher.watch_pr("o/r", {
        "number": 8, "headRefOid": "sha", "files": [], "additions": 0, "deletions": 3,
        "labels": [], "latestReviews": [],
    })
    assert any("tests/conftest_helpers.py" in f for f in report["findings"])


def test_parse_depends_on_accepts_ids_and_rejects_junk():
    assert loop_watcher.parse_depends_on("do X\ndepends on: mbx_a, mbx_b\n") == ["mbx_a", "mbx_b"]
    assert loop_watcher.parse_depends_on("depends_on: `mbx_c`") == ["mbx_c"]
    # Traversal-shaped and empty declarations are dropped, never written.
    assert loop_watcher.parse_depends_on("depends on: ../responses/x") == []
    assert loop_watcher.parse_depends_on("no prerequisites here") == []
