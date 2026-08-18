"""Tests for Mike's automerge admission and native GitHub review bridge.

The admission regression keeps the active-track exemption removed and the
privileged workflow pinned to trusted default-branch policy data.

The bridge lets a trusted installed reviewer-App's GitHub review stand in as
that agent's review receipt when no local receipt file exists — the credential-
free, machine-independent cloud source. These tests are hermetic: they exercise
the pure verdict/selection/resolution logic, no network or gh calls.

The safety invariant under test: the bridge is ADDITIVE. It can satisfy a
MISSING receipt, but a CHANGES_REQUESTED review still blocks, an untrusted
login is never honored, and `claude` (no native reviewer) never bridges.
"""
from __future__ import annotations

from pathlib import Path

from scripts.runtime.pr_merge_control import (
    agent_review_blockers,
    github_review_status,
    resolve_agent_review_status,
)


def _review(login: str, state: str, when: str = "2026-06-24T00:00:00Z", commit: str = "") -> dict:
    # REST review shape: user.login / state / submitted_at / commit_id.
    return {"user": {"login": login}, "state": state, "submitted_at": when, "commit_id": commit}


def test_automerge_workflow_uses_only_manifest_required_contexts_as_authority():
    repo_root = Path(__file__).resolve().parents[1]
    workflow = (repo_root / ".github/workflows/automerge.yml").read_text(encoding="utf-8")

    assert "ADVISORY_CHECKS" not in workflow
    assert 'REQUIRED_CHECKS: "' not in workflow
    assert "Advisory (ignored)" not in workflow
    assert "ACTIVE_TRACK remains advisory" not in workflow
    assert "ref: ${{ github.event.repository.default_branch }}" in workflow
    assert "ref: ${{ github.workflow_sha }}" not in workflow
    assert "scripts/runtime/pr_merge_control.py automerge-required-contexts" not in workflow
    assert "scripts/governance/ci_parity_manifest.json" in workflow
    assert "jq -ce" in workflow
    assert "--argjson req" in workflow
    assert "required_not_green=" in workflow
    assert "select(.name as $name | $req | index($name))" in workflow
    assert "sort_by(.name, .observed_at, .ordinal)" in workflow
    assert "group_by(.name)" in workflow
    assert "map(last | del(.observed_at, .ordinal))" in workflow
    assert "Non-required checks remain visible but do not gain merge authority." in workflow


def test_backlog_workflow_is_scheduled_and_matches_cloud_review_quorum():
    repo_root = Path(__file__).resolve().parents[1]
    workflow = (
        repo_root / ".github/workflows/merge-master-mike-backlog.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert 'default: codex' in workflow
    assert 'REQUIRED_REVIEWERS: ${{ inputs.required_reviewers || \'codex\' }}' in workflow
    assert 'DHARMA_PR_ACCEPT_GITHUB_REVIEWS: "true"' in workflow


def test_cloud_lanes_never_require_copilot_receipts():
    # Operator ratification 2026-07-31: copilot reviews are accepted additively
    # (TRUSTED_REVIEW_LOGINS) but never REQUIRED — copilot posted zero reviews
    # repo-wide and kept the receipt gate permanently unclearable.
    repo_root = Path(__file__).resolve().parents[1]
    # Bind each workflow to its own fallback contract so no assertion can
    # accidentally observe only the final value assigned inside this loop.
    expected_fallbacks = {
        ".github/workflows/codex-mention-router.yml": (
            "REQUIRED_REVIEWERS: codex",
        ),
        # MERGE_MODE: "off" was listed here as a fallback until the merge
        # actuator was deleted. It pinned a mode on a code path that could
        # only ever return SKIPPED; both the env var and the flag it fed are
        # gone. The property it stood for -- this lane cannot merge -- is now
        # structural and pinned harder elsewhere: test_pr_merge_control.py
        # asserts the lane passes no merge flag, and
        # test_pr_merge_control_no_actuation.py asserts no merge path exists
        # to pass one to.
        ".github/workflows/merge-master-mike-backlog.yml": (
            "inputs.required_reviewers || 'codex'",
            "inputs.mode || 'packet-only'",
            "inputs.max_prs || '5'",
            "inputs.limit || '100'",
        ),
    }
    for name, fallbacks in expected_fallbacks.items():
        workflow = (repo_root / name).read_text(encoding="utf-8")
        offending = [
            line
            for line in workflow.splitlines()
            if ("REQUIRED_REVIEWERS" in line or "default:" in line)
            and "copilot" in line
        ]
        assert not offending, f"{name} requires copilot receipts: {offending}"
        assert 'DHARMA_PR_ACCEPT_GITHUB_REVIEWS: "true"' in workflow
        for fallback in fallbacks:
            assert fallback in workflow, f"{name} is missing fallback: {fallback}"


def test_codex_commented_review_counts_as_clean_receipt():
    status = github_review_status("codex", [_review("chatgpt-codex-connector[bot]", "COMMENTED")])
    assert status is not None
    assert status["source"] == "github_review"
    assert status["verdict"] == "PASS"
    # A commented (non-blocking) review from the trusted app satisfies the gate.
    assert agent_review_blockers(status, human_approved=False) == []


def test_copilot_approved_review_counts_as_clean_receipt():
    status = github_review_status("copilot", [_review("copilot-pull-request-reviewer[bot]", "APPROVED")])
    assert status is not None
    assert status["verdict"] == "APPROVE"
    assert agent_review_blockers(status, human_approved=False) == []


def test_bare_login_without_bot_suffix_is_rejected():
    # The trust boundary is the App identity ("[bot]"). A human/account with the
    # bare base login must NOT satisfy the bridge (Copilot review #1).
    assert github_review_status("codex", [_review("chatgpt-codex-connector", "APPROVED")]) is None
    assert github_review_status("copilot", [_review("copilot-pull-request-reviewer", "APPROVED")]) is None


def test_changes_requested_still_blocks():
    status = github_review_status("codex", [_review("chatgpt-codex-connector[bot]", "CHANGES_REQUESTED")])
    assert status is not None
    assert status["verdict"] == "REQUEST_CHANGES"
    assert agent_review_blockers(status, human_approved=False)  # non-empty: blocks


def test_latest_review_wins():
    reviews = [
        _review("chatgpt-codex-connector[bot]", "CHANGES_REQUESTED", "2026-06-24T00:00:00Z"),
        _review("chatgpt-codex-connector[bot]", "APPROVED", "2026-06-24T05:00:00Z"),
    ]
    status = github_review_status("codex", reviews)
    assert status["verdict"] == "APPROVE"


def test_dismissed_review_is_ignored():
    assert github_review_status("codex", [_review("chatgpt-codex-connector[bot]", "DISMISSED")]) is None


def test_review_of_stale_head_is_rejected():
    # A trusted review of an OLD commit must not satisfy the gate for a new head.
    reviews = [_review("chatgpt-codex-connector[bot]", "APPROVED", commit="oldsha")]
    assert github_review_status("codex", reviews, head_sha="newsha") is None


def test_review_of_current_head_is_accepted():
    reviews = [_review("chatgpt-codex-connector[bot]", "APPROVED", commit="headsha")]
    status = github_review_status("codex", reviews, head_sha="headsha")
    assert status is not None
    assert status["github_commit"] == "headsha"
    assert agent_review_blockers(status, human_approved=False) == []


def test_untrusted_login_is_never_a_receipt():
    # A human or random bot pretending to be a reviewer is not honored.
    assert github_review_status("codex", [_review("random-user", "APPROVED")]) is None
    assert github_review_status("codex", [_review("greptile-apps[bot]", "APPROVED")]) is None


def test_claude_never_bridges_no_native_reviewer():
    # claude has no trusted cloud reviewer login -> always None (deep/backup lane).
    assert github_review_status("claude", [_review("claude", "APPROVED")]) is None


def test_resolve_off_keeps_blocked_local(tmp_path: Path):
    # accept_github_reviews=False -> local (missing) status, with its blockers.
    status = resolve_agent_review_status(
        tmp_path, "codex",
        pr_reviews=[_review("chatgpt-codex-connector[bot]", "COMMENTED")],
        accept_github_reviews=False,
    )
    assert status["source"] == "local"
    assert agent_review_blockers(status, human_approved=False)  # missing receipt blocks


def test_resolve_on_bridges_missing_local(tmp_path: Path):
    status = resolve_agent_review_status(
        tmp_path, "codex",
        pr_reviews=[_review("chatgpt-codex-connector[bot]", "COMMENTED")],
        accept_github_reviews=True,
    )
    assert status["source"] == "github_review"
    assert agent_review_blockers(status, human_approved=False) == []


def test_resolve_on_no_trusted_review_keeps_local_blocked(tmp_path: Path):
    # accept on, but no trusted review present -> stays local/blocked (fails closed).
    status = resolve_agent_review_status(
        tmp_path, "codex",
        pr_reviews=[_review("random-user", "APPROVED")],
        accept_github_reviews=True,
    )
    assert status["source"] == "local"
    assert agent_review_blockers(status, human_approved=False)


def test_present_local_receipt_is_never_overridden_by_github_review(tmp_path: Path):
    # Fix for Copilot review #4: a PRESENT local artifact (even a negative one)
    # is authoritative — a clean GitHub review must not bridge over it.
    (tmp_path / "codex_review.md").write_text(
        "VERDICT: REQUEST_CHANGES\nThis change has a real problem that must be fixed first.\n"
    )
    status = resolve_agent_review_status(
        tmp_path, "codex",
        pr_reviews=[_review("chatgpt-codex-connector[bot]", "APPROVED")],
        accept_github_reviews=True,
    )
    assert status["source"] == "local"  # local present -> never overridden
    assert agent_review_blockers(status, human_approved=False)  # its REQUEST_CHANGES still blocks
