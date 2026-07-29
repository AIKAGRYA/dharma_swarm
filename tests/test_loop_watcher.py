"""Loop watcher: finding logic + workflow contract pins (PR-F)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import loop_watcher  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "loop-watcher.yml"


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
