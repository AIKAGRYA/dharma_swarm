"""Tests for reviewer-quorum repair (request-only Copilot ask).

Pin the decision logic: request a trusted reviewer ONLY when it's the right,
non-noisy move — never on drafts, satisfied quorum, CHANGES_REQUESTED, or when a
Copilot review is already pending (idempotent). The gh request itself is a thin
side-effecting wrapper; this is the verifiable core.
"""
from __future__ import annotations

from scripts.runtime.reviewer_quorum_repair import (
    plan_quorum_repair,
    should_request_copilot,
)


def test_requests_when_quorum_missing() -> None:
    do, reason = should_request_copilot(
        {"number": 1, "isDraft": False, "has_required_receipt": False,
         "reviewDecision": None, "requested_reviewers": []})
    assert do is True and "request Copilot" in reason


def test_skips_draft() -> None:
    do, _ = should_request_copilot({"number": 2, "isDraft": True, "has_required_receipt": False})
    assert do is False


def test_skips_when_quorum_satisfied() -> None:
    do, _ = should_request_copilot({"number": 3, "isDraft": False, "has_required_receipt": True})
    assert do is False


def test_skips_changes_requested() -> None:
    do, reason = should_request_copilot(
        {"number": 4, "isDraft": False, "has_required_receipt": False,
         "reviewDecision": "CHANGES_REQUESTED", "requested_reviewers": []})
    assert do is False and "author" in reason


def test_idempotent_when_copilot_already_requested() -> None:
    do, reason = should_request_copilot(
        {"number": 5, "isDraft": False, "has_required_receipt": False,
         "reviewDecision": None, "requested_reviewers": ["copilot-pull-request-reviewer[bot]"]})
    assert do is False and "already requested" in reason


def test_plan_filters_to_only_actionable() -> None:
    prs = [
        {"number": 10, "isDraft": False, "has_required_receipt": False, "requested_reviewers": []},
        {"number": 11, "isDraft": True, "has_required_receipt": False},
        {"number": 12, "isDraft": False, "has_required_receipt": True},
    ]
    plan = plan_quorum_repair(prs)
    assert [p["number"] for p in plan] == [10]
    assert plan[0]["action"] == "request_copilot_review"
