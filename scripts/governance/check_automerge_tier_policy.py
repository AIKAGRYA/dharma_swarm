#!/usr/bin/env python3
"""Automerge tier-policy guard — the door's required CI check (PR-A).

Implements §§5-8 of the operator ruling of 2026-07-29
(DOOR = AUTO_WITH_DECORRELATED_REVIEW; record:
docs/ops/OPERATOR_RULING_2026-07-29_AUTO_WITH_DECORRELATED_REVIEW.md).

One proposition, checked fail-closed on every pull request:

    A PR labeled for unattended merge (`automerge` / `bot-pr`) satisfies the
    tier policy in scripts/governance/automerge_tier_policy.json — or this
    check is red and the manifest-driven automerge lane cannot dispatch it.

Enforced here:
- Tier 2 structural freeze: an automerge-labeled PR touching any tier-2
  (referee-layer) path fails outright. The system cannot amend its own
  referees; those paths are operator hand-merge forever.
- Diff ceilings: tier 0 <= 300 changed lines, tier 1 <= 600; larger fails
  (split it or drop the label and go the operator route).
- Decorrelated review count: tier 0 needs 1 APPROVED review, tier 1 needs 2,
  from reviewer identities in the policy's reviewer_families whose family
  differs from the author's family (and from each other where possible).
  Native GitHub reviews are the machine-checkable verdict artifact of v1.
  Reviews come from the REST endpoint (the same source pr_merge_control.py
  trusts): logins are matched EXACTLY against the policy's trusted
  "<app>[bot]" identities, and only a review whose commit_id equals the
  current head SHA counts — an approval of an earlier revision has not seen
  the current changes.
- Test-deletion sign-off (tier 1): a diff deleting test functions passes
  only if a QUALIFYING (trusted, decorrelated) APPROVED review body names
  every deleted test — an approval from an untrusted account never
  authorizes a deletion.
- Rate limit: at or above 20 automerge-lane merges in the last 24h, every
  further labeled PR fails this check until the window drains.
- Unlabeled PRs and drafts always pass (the check must be green context
  noise for the operator's own hand-merge lane).

This check going red never blocks the OPERATOR: hand-merge ignores it by
authority; it is required context only for the unattended lane's green-set.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "scripts" / "governance" / "automerge_tier_policy.json"
UNATTENDED_LABELS = {"automerge", "bot-pr"}
# `async def test_*` deletions must match too, or async tests bypass the
# named-sign-off requirement entirely (Codex review on PR #1160).
TEST_DELETION_RE = re.compile(
    r"^-\s*(?:async\s+)?def (test_[A-Za-z0-9_]+)", re.MULTILINE
)


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("schema") != "dharma.automerge_tier_policy.v1":
        raise SystemExit(f"unrecognized tier policy schema in {path}")
    return policy


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or fnmatch.fnmatch(path, pattern)


def tier2_hits(changed_paths: list[str], policy: dict) -> list[str]:
    patterns = policy["tiers"]["tier2"]["paths"]
    return sorted(
        {p for p in changed_paths for pattern in patterns if _matches(p, pattern)}
    )


def classify_tier(changed_paths: list[str], policy: dict) -> str:
    doc_only = policy["tiers"]["tier0"]["doc_only_paths"]
    if changed_paths and all(
        any(_matches(p, pattern) for pattern in doc_only) for p in changed_paths
    ):
        return "tier0"
    return "tier1"


def deleted_tests(diff_text: str) -> list[str]:
    return sorted(set(TEST_DELETION_RE.findall(diff_text)))


def _normalize_login(login: str) -> str:
    # Mirrors _normalize_login in scripts/runtime/pr_merge_control.py: EXACT
    # match only, "[bot]" suffix retained — the suffix is GitHub's
    # App-identity marker that no human account can hold.
    return (login or "").strip().lower()


# Review states that carry a standing verdict. A later COMMENTED review does
# not overwrite an approval (GitHub keeps the approval standing); a later
# CHANGES_REQUESTED does. DISMISSED approvals lose their state entirely.
_STATE_BEARING = {"APPROVED", "CHANGES_REQUESTED"}


def latest_approvals(reviews: list[dict], head_sha: str) -> list[dict]:
    """Reduce raw REST review rows to the standing approvals of *head_sha*.

    Keeps the latest state-bearing review per login, then keeps only the
    APPROVED ones whose commit_id equals the current head — a review of an
    earlier revision has not seen the current changes and never counts
    (same rule as github_review_status in scripts/runtime/pr_merge_control.py;
    Codex + Greptile reviews on PR #1160). An empty head_sha qualifies
    nothing: missing head identity fails closed.
    """
    latest: dict[str, dict] = {}
    for review in sorted(reviews, key=lambda r: str(r.get("submitted_at") or "")):
        login = _normalize_login(str((review.get("user") or {}).get("login") or ""))
        state = str(review.get("state") or "").upper()
        if login and state in _STATE_BEARING:
            latest[login] = review
    return [
        {
            "login": login,
            "state": "APPROVED",
            "body": str(review.get("body") or ""),
        }
        for login, review in sorted(latest.items())
        if str(review.get("state") or "").upper() == "APPROVED"
        and head_sha
        and str(review.get("commit_id") or "") == head_sha
    ]


def count_unique_merged(row_lists: list[object]) -> int:
    """Distinct merged-PR count across the per-label queries — a PR carrying
    both unattended labels is one merge, not two (Devin + Codex + Greptile
    reviews on PR #1160)."""
    numbers: set[int] = set()
    for rows in row_lists:
        if isinstance(rows, list):
            numbers.update(
                int(row["number"]) for row in rows if row.get("number") is not None
            )
    return len(numbers)


def evaluate(
    *,
    labels: list[str],
    is_draft: bool,
    changed_paths: list[str],
    diff_lines: int,
    diff_text: str,
    approved_reviews: list[dict],
    author: str,
    merged_last_24h: int,
    policy: dict,
    assume_unattended: bool = False,
) -> dict:
    """Pure policy evaluation. approved_reviews rows: {login, state, body}.

    assume_unattended binds the policy regardless of labels and draft state —
    the mode for any caller about to ARM an unattended merge (the mention
    router synthesizing the pass token), where "unlabeled → policy does not
    bind" would be a bypass (Codex review on PR #1160).
    """
    report: dict = {
        "schema": "dharma.automerge_tier_policy_report.v1",
        "labeled_for_unattended": (
            bool(UNATTENDED_LABELS & set(labels)) or assume_unattended
        ),
        "is_draft": is_draft,
        "tier": None,
        "tier2_hits": [],
        "violations": [],
        "passed": True,
    }
    if "canary-sandbox" in labels:
        # §9 reviewer-integrity loop: seeded canary PRs flow through the
        # normal review pipeline but must be structurally unmergeable by the
        # unattended lane, whatever any reviewer says about them.
        report["violations"] = [
            "canary-sandbox PR: seeded defect lane — never mergeable unattended"
        ]
        report["passed"] = False
        return report

    if not report["labeled_for_unattended"] or (is_draft and not assume_unattended):
        report["reason"] = "not in the unattended lane; policy does not bind"
        return report

    violations: list[str] = []

    hits = tier2_hits(changed_paths, policy)
    report["tier2_hits"] = hits
    if hits:
        violations.append(
            f"tier-2 referee paths in an unattended-labeled PR: {hits} — "
            "operator hand-merge forever; remove the automerge/bot-pr label"
        )

    tier = classify_tier(changed_paths, policy)
    report["tier"] = tier
    ceiling = policy["tiers"][tier]["max_diff_lines"]
    if diff_lines > ceiling:
        violations.append(
            f"{tier} diff ceiling exceeded: {diff_lines} > {ceiling} changed lines — "
            "split the PR or take the operator route"
        )

    # Exact-login trust boundary, mirroring TRUSTED_REVIEW_LOGINS in
    # scripts/runtime/pr_merge_control.py: prefix matching would both miss
    # the real "<app>[bot]" logins ('chatgpt-codex-connector[bot]' does not
    # start with 'codex') and admit lookalike accounts (Devin + Codex
    # reviews on PR #1160).
    families = {
        _normalize_login(login): family
        for login, family in policy["reviewer_families"].items()
    }
    author_family = policy["author_families"].get(author, f"unknown:{author}")
    qualifying = []
    trusted_reviews = []
    seen_families: set[str] = set()
    for row in approved_reviews:
        login = _normalize_login(row.get("login", ""))
        family = families.get(login)
        if family is None:
            continue
        trusted_reviews.append(row)
        if family == author_family or family in seen_families:
            continue
        seen_families.add(family)
        qualifying.append(login)
    needed = policy["tiers"][tier]["required_decorrelated_reviews"]
    report["qualifying_reviews"] = qualifying
    if len(qualifying) < needed:
        violations.append(
            f"{tier} needs {needed} decorrelated APPROVED review(s) "
            f"(family != author family '{author_family}'); have {len(qualifying)}: {qualifying}"
        )

    if tier == "tier1" and policy["tiers"]["tier1"]["test_deletion_needs_named_signoff"]:
        removed = deleted_tests(diff_text)
        if removed:
            # Only a TRUSTED reviewer's approval can authorize a deletion —
            # an APPROVED review from an arbitrary account naming the tests
            # is not a sign-off (Codex review on PR #1160).
            named_everywhere = [
                r for r in trusted_reviews
                if all(name in (r.get("body") or "") for name in removed)
            ]
            if not named_everywhere:
                violations.append(
                    f"test deletions {removed} lack a trusted APPROVED review "
                    "naming every deleted test"
                )
            report["deleted_tests"] = removed

    limit = policy["rate_limit_automerges_per_day"]
    report["merged_last_24h"] = merged_last_24h
    if merged_last_24h >= limit:
        violations.append(
            f"automerge rate limit reached: {merged_last_24h} >= {limit} in 24h — "
            "window must drain before further unattended merges"
        )

    report["violations"] = violations
    report["passed"] = not violations
    return report


# ------------------------------------------------------------- gathering


def _gh_json(args: list[str]) -> object | None:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _fetch_all_reviews(repo: str, pr: int) -> list | None:
    """Every REST review row, all pages. A single 100-row page could hide a
    reviewer's newer CHANGES_REQUESTED on page 2 behind a stale page-1
    approval (Greptile on PR #1160). Fails closed (None) if any page fails."""
    rows: list = []
    page = 1
    while True:
        data = _gh_json(
            ["api", f"repos/{repo}/pulls/{pr}/reviews?per_page=100&page={page}"]
        )
        if not isinstance(data, list):
            return None
        rows.extend(data)
        if len(data) < 100:
            return rows
        page += 1


def gather_pr(repo: str, pr: int) -> dict | None:
    """Gather the evaluation inputs, failing closed (None) on ANY partial
    read: an unavailable diff is not an empty diff (it would waive the
    deleted-test sign-off), and an unavailable review/rate-limit query is
    not an empty one (Codex + Greptile reviews on PR #1160)."""
    view = _gh_json(
        [
            "pr", "view", str(pr), "--repo", repo, "--json",
            "labels,isDraft,files,additions,deletions,author,headRefOid",
        ]
    )
    if not isinstance(view, dict):
        return None
    # Same REST source pr_merge_control.py trusts (fetch_pr_reviews): it
    # carries commit_id — the exact SHA each review saw — and App logins in
    # their "<app>[bot]" form, matching the policy's trusted identities.
    reviews = _fetch_all_reviews(repo, pr)
    if reviews is None:
        return None
    diff = subprocess.run(
        ["gh", "pr", "diff", str(pr), "--repo", repo],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if diff.returncode != 0:
        print(diff.stderr.strip(), file=sys.stderr)
        return None
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    label_rows: list[object] = []
    for label in sorted(UNATTENDED_LABELS):
        rows = _gh_json(
            [
                "pr", "list", "--repo", repo, "--state", "merged",
                "--label", label, "--search", f"merged:>={since}",
                "--json", "number", "--limit", "50",
            ]
        )
        if not isinstance(rows, list):
            return None
        label_rows.append(rows)
    return {
        "labels": [row["name"] for row in view.get("labels", [])],
        "is_draft": bool(view.get("isDraft")),
        "changed_paths": [f["path"] for f in view.get("files", [])],
        "diff_lines": int(view.get("additions", 0)) + int(view.get("deletions", 0)),
        "diff_text": diff.stdout,
        "approved_reviews": latest_approvals(
            reviews, str(view.get("headRefOid") or "")
        ),
        "author": view.get("author", {}).get("login", ""),
        "merged_last_24h": count_unique_merged(label_rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automerge tier-policy guard")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument(
        "--assume-unattended", action="store_true",
        help="bind the policy regardless of labels/draft state — required "
        "for any caller about to arm an unattended merge",
    )
    args = parser.parse_args(argv)

    policy = load_policy()
    gathered = gather_pr(args.repo, args.pr)
    if gathered is None:
        print("TIER_POLICY_UNKNOWN: could not gather PR state — failing closed",
              file=sys.stderr)
        return 2
    report = evaluate(
        policy=policy, assume_unattended=args.assume_unattended, **gathered
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["passed"]:
        print("TIER_POLICY_OK")
        return 0
    for violation in report["violations"]:
        print(f"TIER_POLICY_VIOLATION: {violation}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
