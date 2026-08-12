#!/usr/bin/env python3
"""Fail-closed unattended-merge authority guard.

The safe-P0 boundary is deliberately asymmetric:

* strict docs-low needs deterministic gates and current-head trusted AI
  evidence;
* code additionally needs an exact current-head allowlisted-operator warrant;
* referee/high-risk changes are operator-only and never receive a Mike permit.

AI review is evidence, not operator identity.  Safe P0 emits only a canonical
``AuthorizationEvidence<repo, pr, head, base, policy, intent, authority>``
snapshot.  It deliberately cannot construct ``MergeAuthorized``: authenticated
provenance and server-side base-CAS proofs are not live yet.  A label, aggregate
review decision, caller boolean, or predictable confirmation string cannot
promote this evidence into merge authority.

Unlabeled PRs stay outside the unattended lane so the operator's manual route
is not wedged by this required context. Removing a label does not grant Mike
authority; it only selects the separate operator route.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The reversibility gate's import chain is stdlib-only by contract
# (dharma_swarm/risk_patterns.py) so this import works on the referee
# workflow's bare python3. An ImportError here crashes the check red —
# fail closed, never "no gate, no floor".
sys.path.insert(0, str(REPO_ROOT))
from dharma_swarm.operator_core.reversibility_gate import (  # noqa: E402
    ActionClass,
    classify_action,
)
POLICY_PATH = REPO_ROOT / "scripts" / "governance" / "automerge_tier_policy.json"
UNATTENDED_LABELS = {"automerge", "bot-pr"}
# `async def test_*` deletions must match too, or async tests bypass the
# named-sign-off requirement entirely (Codex review on PR #1160).
TEST_DELETION_RE = re.compile(
    r"^-\s*(?:async\s+)?def (test_[A-Za-z0-9_]+)", re.MULTILINE
)


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("schema") != "dharma.automerge_tier_policy.v3":
        raise SystemExit(f"unrecognized tier policy schema in {path}")
    return policy


def canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def policy_digest(policy: dict) -> str:
    return canonical_digest(policy)


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**") and not any(
        marker in pattern[:-3] for marker in ("*", "?", "[")
    ):
        return path.startswith(pattern[:-2])
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or fnmatch.fnmatch(path, pattern)


def tier2_hits(changed_paths: list[str], policy: dict) -> list[str]:
    patterns = policy["tiers"]["tier2"]["paths"]
    return sorted(
        {p for p in changed_paths for pattern in patterns if _matches(p, pattern)}
    )


def operator_only_hits(changed_paths: list[str], policy: dict) -> list[str]:
    patterns = policy["authority_policy"]["operator_only_paths"]
    return sorted(
        set(tier2_hits(changed_paths, policy))
        | {p for p in changed_paths for pattern in patterns if _matches(p, pattern)}
    )


def is_docs_low_path(path: str, policy: dict) -> bool:
    authority = policy["authority_policy"]
    allowed = any(_matches(path, pattern) for pattern in authority["docs_low_allow"])
    denied = any(_matches(path, pattern) for pattern in authority["docs_low_deny"])
    return allowed and not denied


def classify_tier(changed_paths: list[str], policy: dict) -> str:
    if operator_only_hits(changed_paths, policy):
        return "tier2"
    if changed_paths and all(is_docs_low_path(path, policy) for path in changed_paths):
        return "tier0"
    return "tier1"


def deleted_tests(diff_text: str) -> list[str]:
    return sorted(set(TEST_DELETION_RE.findall(diff_text)))


def unsafe_diff_modes(diff_text: str) -> list[str]:
    findings = []
    for line in diff_text.splitlines():
        stripped = line.strip()
        if stripped in {
            "new file mode 100755",
            "new file mode 120000",
            "new file mode 160000",
            "new mode 100755",
            "new mode 120000",
            "new mode 160000",
        }:
            findings.append(stripped)
    return sorted(set(findings))


_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|testdata|fixtures?|goldens?)(/|$)|"
    r"(^|/)[^/]+\.(test|spec)\.[^/]+$",
    re.IGNORECASE,
)


def removed_or_renamed_test_paths(file_changes: list[dict] | None) -> list[str]:
    findings: set[str] = set()
    for row in file_changes or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        if status not in {"removed", "renamed"}:
            continue
        for key in ("filename", "previous_filename"):
            path = str(row.get(key) or "")
            if path and _TEST_PATH_RE.search(path):
                findings.add(path)
    return sorted(findings)


def authority_class_for(
    *,
    changed_paths: list[str],
    diff_text: str,
    title: str,
    policy: dict,
    file_changes: list[dict] | None = None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    hits = operator_only_hits(changed_paths, policy)
    if hits:
        reasons.append(f"operator-only paths: {hits}")
    removed = deleted_tests(diff_text)
    if removed:
        reasons.append(f"test deletions: {removed}")
    removed_paths = removed_or_renamed_test_paths(file_changes)
    if removed_paths:
        reasons.append(f"removed or renamed test paths: {removed_paths}")
    unsafe_modes = unsafe_diff_modes(diff_text)
    if unsafe_modes:
        reasons.append(f"unsafe file modes: {unsafe_modes}")
    decision = classify_action(title, operator_reachable=False)
    if decision.action_class is ActionClass.OPERATOR_ONLY:
        reasons.append("reversibility floor classifies intent OPERATOR_ONLY")
    if reasons:
        return "operator_only", reasons
    if changed_paths and all(is_docs_low_path(path, policy) for path in changed_paths):
        return "docs_low", []
    return "code", []


def _normalize_login(login: str) -> str:
    # Mirrors _normalize_login in scripts/runtime/pr_merge_control.py: EXACT
    # match only, "[bot]" suffix retained — the suffix is GitHub's
    # App-identity marker that no human account can hold.
    return (login or "").strip().lower()


# Review states that carry a standing verdict. A later COMMENTED review does
# not overwrite an approval (GitHub keeps the approval standing); a later
# CHANGES_REQUESTED does. DISMISSED is state-bearing too: the REST API
# normally mutates the dismissed review's own state to DISMISSED, but if a
# dismissal ever surfaces as a separate later row it must still clear the
# login's standing approval (Greptile review on PR #1160).
_STATE_BEARING = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
_AI_EVIDENCE_STATES = {"APPROVED", "COMMENTED", "CHANGES_REQUESTED", "DISMISSED"}


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


def latest_ai_evidence(
    reviews: list[dict], head_sha: str, policy: dict
) -> list[dict]:
    """Return current-head review evidence from exact trusted App identities.

    COMMENTED proves that a review ran but does not become a GitHub approval.
    A later CHANGES_REQUESTED or DISMISSED row clears the login's evidence.
    """
    trusted = {_normalize_login(login) for login in policy["reviewer_families"]}
    latest: dict[str, dict] = {}
    for review in sorted(
        reviews,
        key=lambda row: (
            str(row.get("submitted_at") or ""),
            int(row.get("id") or 0),
        ),
    ):
        login = _normalize_login(str((review.get("user") or {}).get("login") or ""))
        state = str(review.get("state") or "").upper()
        if login in trusted and state in _AI_EVIDENCE_STATES:
            latest[login] = review
    evidence: list[dict] = []
    for login, review in sorted(latest.items()):
        state = str(review.get("state") or "").upper()
        if state not in {"APPROVED", "COMMENTED"}:
            continue
        if not head_sha or str(review.get("commit_id") or "") != head_sha:
            continue
        evidence.append(
            {
                "id": int(review.get("id") or 0),
                "login": login,
                "state": state,
                "body": str(review.get("body") or ""),
                "head_sha": head_sha,
            }
        )
    return evidence


def qualifying_operator_warrants(
    reviews: list[dict], head_sha: str, policy: dict
) -> list[dict]:
    """Reduce native GitHub approvals to exact-head operator warrants.

    Mutable issue comments are intentionally not accepted in safe P0: they are
    editable/deletable and the required policy check has no authenticated
    comment-to-check bridge.  Self-authored operator PRs therefore stay on the
    manual merge route.
    """
    operators = {
        _normalize_login(login)
        for login in policy["authority_policy"]["operator_identities"]
    }
    latest_reviews: dict[str, dict] = {}
    for review in sorted(
        reviews,
        key=lambda row: (
            str(row.get("submitted_at") or ""),
            int(row.get("id") or 0),
        ),
    ):
        login = _normalize_login(str((review.get("user") or {}).get("login") or ""))
        if login in operators and str(review.get("state") or "").upper() in _STATE_BEARING:
            latest_reviews[login] = review
    warrants: list[dict] = []
    for login, review in sorted(latest_reviews.items()):
        if (
            str(review.get("state") or "").upper() == "APPROVED"
            and head_sha
            and str(review.get("commit_id") or "") == head_sha
        ):
            warrants.append(
                {
                    "kind": "github_review",
                    "id": int(review.get("id") or 0),
                    "actor": login,
                    "head_sha": head_sha,
                }
            )

    return warrants


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
    title: str,
    changed_paths: list[str],
    diff_lines: int,
    diff_text: str,
    approved_reviews: list[dict],
    ai_evidence: list[dict] | None = None,
    operator_warrants: list[dict] | None = None,
    repo: str = "",
    pr: int = 0,
    head_sha: str = "",
    base_sha: str = "",
    base_ref: str = "",
    file_changes: list[dict] | None = None,
    author: str,
    merged_last_24h: int,
    policy: dict,
    assume_unattended: bool = False,
) -> dict:
    """Pure authority evaluation over already authenticated GitHub evidence.

    assume_unattended binds the policy regardless of labels and draft state —
    the mode for any caller about to ARM an unattended merge (the mention
    router synthesizing the pass token), where "unlabeled → policy does not
    bind" would be a bypass (Codex review on PR #1160).
    """
    report: dict = {
        "schema": "dharma.automerge_tier_policy_report.v2",
        "labeled_for_unattended": (
            bool(UNATTENDED_LABELS & set(labels)) or assume_unattended
        ),
        "is_draft": is_draft,
        "tier": None,
        "tier2_hits": [],
        "authority_class": None,
        "authorization_evidence": None,
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

    hits = operator_only_hits(changed_paths, policy)
    report["tier2_hits"] = hits
    authority_class, authority_reasons = authority_class_for(
        changed_paths=changed_paths,
        diff_text=diff_text,
        title=title,
        policy=policy,
        file_changes=file_changes,
    )
    tier = {"docs_low": "tier0", "code": "tier1", "operator_only": "tier2"}[
        authority_class
    ]
    report["tier"] = tier
    report["authority_class"] = authority_class
    report["authority_reasons"] = authority_reasons

    # Reversibility floor (operator ruling 2026-07-30): the gate's verdict on
    # the declared merge intent, evaluated with operator_reachable=False — CI
    # is by definition the unattended context. OPERATOR_ONLY (a NEVER_AUTO
    # denylist hit, or CRITICAL-risk vocabulary) bars the unattended lane at
    # every tier; the decorrelated quorum stands in for the execution lease on
    # everything milder. Title text can only ADD floor hits, never remove the
    # path floor or the quorum, so a crafted title fails closed.
    decision = classify_action(title, operator_reachable=False)
    report["reversibility"] = {
        "action_class": decision.action_class.value,
        "risk": decision.risk.value,
        "never_auto_hit": decision.never_auto_hit,
    }
    if decision.action_class is ActionClass.OPERATOR_ONLY:
        detail = (
            f"never-auto hit '{decision.never_auto_hit}'"
            if decision.never_auto_hit
            else f"risk={decision.risk.value}"
        )
        violations.append(
            f"reversibility floor: title classifies OPERATOR_ONLY ({detail}) — "
            "the irreversible/illegal floor stays operator hand-merge"
        )
    if authority_class == "operator_only":
        violations.append(
            "operator-only authority class: Mike may report evidence but never "
            f"actuate this PR ({'; '.join(authority_reasons)})"
        )

    ceiling = policy["tiers"][tier]["max_diff_lines"]
    if diff_lines > ceiling:
        violations.append(
            f"{tier} diff ceiling exceeded: {diff_lines} > {ceiling} changed lines — "
            "split the PR or take the operator route"
        )

    # Exact-login trust boundary. AI authority evidence must be the richer,
    # current-head rows produced by latest_ai_evidence; an APPROVED summary row
    # without its head/evidence identity is not promotable.
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
        if family == author_family:
            # Same-family approvals are excluded EVERYWHERE, including the
            # deletion sign-off pool below — a Copilot-family approval must
            # not authorize deletions on a Copilot-authored PR (Greptile
            # review on PR #1160).
            continue
        trusted_reviews.append(row)
        if family in seen_families:
            continue
        seen_families.add(family)
        qualifying.append(login)
    evidence_rows = list(ai_evidence or [])
    trusted_evidence = [
        row
        for row in evidence_rows
        if _normalize_login(str(row.get("login") or "")) in families
        and str(row.get("state") or "").upper() in {"APPROVED", "COMMENTED"}
        and head_sha
        and str(row.get("head_sha") or "") == head_sha
        and isinstance(row.get("id"), int)
        and row["id"] > 0
    ]
    needed = policy["authority_policy"]["classes"][authority_class][
        "required_ai_evidence"
    ]
    report["qualifying_reviews"] = qualifying
    report["ai_evidence"] = trusted_evidence
    if len(trusted_evidence) < needed:
        violations.append(
            f"{authority_class} needs {needed} current-head trusted AI review "
            f"evidence row(s); have {len(trusted_evidence)}"
        )

    operator_logins = {
        _normalize_login(login)
        for login in policy["authority_policy"]["operator_identities"]
    }
    warrants = [
        row
        for row in (operator_warrants or [])
        if isinstance(row, dict)
        and _normalize_login(str(row.get("actor") or "")) in operator_logins
        and head_sha
        and str(row.get("head_sha") or "") == head_sha
        and row.get("kind") == "github_review"
        and isinstance(row.get("id"), int)
        and row["id"] > 0
    ]
    report["operator_warrants"] = warrants
    needs_warrant = policy["authority_policy"]["classes"][authority_class][
        "operator_warrant"
    ]
    if needs_warrant and authority_class != "operator_only" and not warrants:
        violations.append(
            "code authority requires an exact current-head allowlisted-operator warrant"
        )

    limit = policy["rate_observation_advisory_per_day"]
    report["merged_last_24h"] = merged_last_24h
    report["rate_limit"] = limit
    report["rate_limit_advisory"] = (
        "retained-label counts are mutable and non-atomic; enforce any future "
        "actuation ceiling with a serialized append-only admission lease"
    )

    report["violations"] = violations
    report["passed"] = not violations
    if report["passed"]:
        evidence = {
            "schema": policy["authority_policy"]["authorization_evidence_schema"],
            "repo": repo,
            "pr": pr,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "base_ref": base_ref,
            "policy_sha256": policy_digest(policy),
            "intent_sha256": canonical_digest(title),
            "authority_class": authority_class,
            "ai_evidence_ids": sorted(
                int(row.get("id") or 0) for row in trusted_evidence
            ),
            "operator_warrant": warrants[0] if warrants else None,
            "provenance": "unsigned-github-snapshot",
            "actuation_eligible": False,
        }
        evidence["digest"] = canonical_digest(evidence)
        report["authorization_evidence"] = evidence
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


def _fetch_all_pages(resource: str) -> list | None:
    """Every row of a REST list resource, all pages, fail closed (None) on
    any failed page. One 100-row page is never treated as complete: a
    truncated review list could hide a newer CHANGES_REQUESTED, and a
    truncated file list could hide a tier-2 referee path at position 101
    (Greptile reviews on PR #1160)."""
    rows: list = []
    page = 1
    while True:
        joiner = "&" if "?" in resource else "?"
        data = _gh_json(["api", f"{resource}{joiner}per_page=100&page={page}"])
        if not isinstance(data, list):
            return None
        rows.extend(data)
        if len(data) < 100:
            return rows
        page += 1


def gather_pr(repo: str, pr: int, policy: dict | None = None) -> dict | None:
    """Gather the evaluation inputs, failing closed (None) on ANY partial
    read: an unavailable diff is not an empty diff (it would waive the
    deleted-test sign-off), and an unavailable review/rate-limit query is
    not an empty one (Codex + Greptile reviews on PR #1160)."""
    effective_policy = policy or load_policy()
    view = _gh_json(
        [
            "pr", "view", str(pr), "--repo", repo, "--json",
            "labels,isDraft,title,additions,deletions,author,baseRefName,baseRefOid,headRefOid",
        ]
    )
    if not isinstance(view, dict):
        return None
    # Same REST source pr_merge_control.py trusts (fetch_pr_reviews): it
    # carries commit_id — the exact SHA each review saw — and App logins in
    # their "<app>[bot]" form, matching the policy's trusted identities.
    reviews = _fetch_all_pages(f"repos/{repo}/pulls/{pr}/reviews")
    if reviews is None:
        return None
    # Changed paths via the paginated REST files endpoint — `gh pr view
    # --json files` silently stops at 100 files, which would let a large PR
    # hide a tier-2 path from the freeze.
    files = _fetch_all_pages(f"repos/{repo}/pulls/{pr}/files")
    if files is None:
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
    head_sha = str(view.get("headRefOid") or "")
    base_sha = str(view.get("baseRefOid") or "")
    base_ref = str(view.get("baseRefName") or "")
    file_changes = [
        {
            "filename": str(row.get("filename") or ""),
            "previous_filename": str(row.get("previous_filename") or ""),
            "status": str(row.get("status") or ""),
        }
        for row in files
    ]
    changed_paths = sorted(
        {
            path
            for row in file_changes
            for path in (row["filename"], row["previous_filename"])
            if path
        }
    )
    return {
        "repo": repo,
        "pr": pr,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "base_ref": base_ref,
        "labels": [row["name"] for row in view.get("labels", [])],
        "is_draft": bool(view.get("isDraft")),
        "title": str(view.get("title") or ""),
        "changed_paths": changed_paths,
        "file_changes": file_changes,
        "diff_lines": int(view.get("additions", 0)) + int(view.get("deletions", 0)),
        "diff_text": diff.stdout,
        "approved_reviews": latest_approvals(
            reviews, head_sha
        ),
        "ai_evidence": latest_ai_evidence(reviews, head_sha, effective_policy),
        "operator_warrants": qualifying_operator_warrants(
            reviews, head_sha, effective_policy
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
    parser.add_argument(
        "--output",
        type=Path,
        help="write the exact evaluated report/permit for the next gate invocation",
    )
    args = parser.parse_args(argv)

    policy = load_policy()
    gathered = gather_pr(args.repo, args.pr, policy)
    if gathered is None:
        print("TIER_POLICY_UNKNOWN: could not gather PR state — failing closed",
              file=sys.stderr)
        return 2
    report = evaluate(
        policy=policy, assume_unattended=args.assume_unattended, **gathered
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
