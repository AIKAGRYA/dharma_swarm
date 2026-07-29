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
  Native GitHub reviews are the machine-checkable verdict artifact of v1
  (state APPROVED on the head SHA is API-verifiable execution, not prose).
- Test-deletion sign-off (tier 1): a diff deleting test functions passes
  only if an APPROVED review body names every deleted test.
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
TEST_DELETION_RE = re.compile(r"^-\s*def (test_[A-Za-z0-9_]+)", re.MULTILINE)


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
) -> dict:
    """Pure policy evaluation. approved_reviews rows: {login, state}."""
    report: dict = {
        "schema": "dharma.automerge_tier_policy_report.v1",
        "labeled_for_unattended": bool(UNATTENDED_LABELS & set(labels)),
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

    if not report["labeled_for_unattended"] or is_draft:
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

    families = policy["reviewer_families"]
    author_family = policy["author_families"].get(author, f"unknown:{author}")
    qualifying = []
    seen_families: set[str] = set()
    for row in approved_reviews:
        login = row.get("login", "")
        reviewer_key = next((k for k in families if login.startswith(k)), None)
        if reviewer_key is None:
            continue
        family = families[reviewer_key]
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
            named_everywhere = [
                r for r in approved_reviews
                if all(name in (r.get("body") or "") for name in removed)
            ]
            if not named_everywhere:
                violations.append(
                    f"test deletions {removed} lack an APPROVED review naming "
                    "every deleted test"
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


def gather_pr(repo: str, pr: int) -> dict | None:
    view = _gh_json(
        [
            "pr", "view", str(pr), "--repo", repo, "--json",
            "labels,isDraft,files,additions,deletions,author,latestReviews",
        ]
    )
    if not isinstance(view, dict):
        return None
    diff = subprocess.run(
        ["gh", "pr", "diff", str(pr), "--repo", repo],
        capture_output=True, text=True, timeout=120, check=False,
    )
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    merged = 0
    for label in sorted(UNATTENDED_LABELS):
        rows = _gh_json(
            [
                "pr", "list", "--repo", repo, "--state", "merged",
                "--label", label, "--search", f"merged:>={since}",
                "--json", "number", "--limit", "50",
            ]
        )
        if isinstance(rows, list):
            merged += len(rows)
    return {
        "labels": [l["name"] for l in view.get("labels", [])],
        "is_draft": bool(view.get("isDraft")),
        "changed_paths": [f["path"] for f in view.get("files", [])],
        "diff_lines": int(view.get("additions", 0)) + int(view.get("deletions", 0)),
        "diff_text": diff.stdout if diff.returncode == 0 else "",
        "approved_reviews": [
            {"login": r.get("author", {}).get("login", ""),
             "state": r.get("state", ""),
             "body": r.get("body", "")}
            for r in view.get("latestReviews", [])
            if r.get("state") == "APPROVED"
        ],
        "author": view.get("author", {}).get("login", ""),
        "merged_last_24h": merged,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automerge tier-policy guard")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    args = parser.parse_args(argv)

    policy = load_policy()
    gathered = gather_pr(args.repo, args.pr)
    if gathered is None:
        print("TIER_POLICY_UNKNOWN: could not gather PR state — failing closed",
              file=sys.stderr)
        return 2
    report = evaluate(policy=policy, **gathered)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["passed"]:
        print("TIER_POLICY_OK")
        return 0
    for violation in report["violations"]:
        print(f"TIER_POLICY_VIOLATION: {violation}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
