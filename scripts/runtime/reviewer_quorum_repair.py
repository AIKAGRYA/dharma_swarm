#!/usr/bin/env python3
"""reviewer_quorum_repair.py — auto-request a TRUSTED reviewer when a PR is stuck
on a missing required-reviewer receipt (the hands-free #700 blocker).

REQUEST-ONLY by design: it never approves, merges, pushes, or waives a gate. It
asks the ALREADY-TRUSTED Copilot reviewer-App (copilot-pull-request-reviewer[bot],
already in pr_merge_control.TRUSTED_REVIEW_LOGINS) for a review; the resulting
review becomes a receipt through the existing, head-SHA-gated github_review_status
bridge — zero new trust surface. Idempotent: it will not re-request when a Copilot
review is already pending. Default is DRY-RUN — it never fires a request without
an explicit --execute, so it can be wired into Mike's advisory cycle safely.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO = "AmitabhainArunachala/dharma_swarm"
COPILOT_REVIEWER = "copilot-pull-request-reviewer[bot]"  # exact trusted App login


def should_request_copilot(pr: dict) -> tuple[bool, str]:
    """Pure decision. pr keys: number, isDraft, reviewDecision,
    requested_reviewers (list of logins), has_required_receipt (bool).
    Returns (do_request, reason). Never requests when it would be wrong or noisy."""
    if pr.get("isDraft"):
        return False, "draft — not eligible"
    if pr.get("has_required_receipt"):
        return False, "quorum already satisfied"
    if str(pr.get("reviewDecision") or "").upper() == "CHANGES_REQUESTED":
        return False, "CHANGES_REQUESTED — needs the author, not a new reviewer"
    requested = {str(r).lower() for r in (pr.get("requested_reviewers") or [])}
    if any("copilot" in r for r in requested):
        return False, "Copilot review already requested (idempotent skip)"
    return True, "missing quorum — request Copilot review"


def plan_quorum_repair(prs) -> list[dict]:
    """Pure. Map the decision over PRs; returns the request plan (advisory)."""
    plan = []
    for pr in prs:
        do, reason = should_request_copilot(pr)
        if do:
            plan.append({"number": pr["number"], "action": "request_copilot_review", "reason": reason})
    return plan


def request_copilot_review(pr_number: int, repo: str = REPO) -> dict:
    """Side-effecting: ask Copilot for a review (best-effort). REQUEST only.
    Returns a result dict; never raises (a failed request is data, not a crash)."""
    try:
        proc = subprocess.run(
            ["gh", "api", "--method", "POST",
             f"/repos/{repo}/pulls/{pr_number}/requested_reviewers",
             "-f", f"reviewers[]={COPILOT_REVIEWER}"],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
        )
        return {"number": pr_number, "ok": proc.returncode == 0,
                "detail": (proc.stdout or proc.stderr or "").strip()[:200]}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"number": pr_number, "ok": False, "detail": f"{type(exc).__name__}: {exc}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="actually request reviews (default: DRY-RUN, plan only)")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args(argv)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))  # repo-root only — never shadow bare names
    from scripts.runtime.pr_merge_control import fetch_open_prs  # noqa: E402
    prs = fetch_open_prs(args.limit)
    plan = plan_quorum_repair(prs)
    print(json.dumps({"mode": "execute" if args.execute else "dry-run", "plan": plan}, indent=2))
    if args.execute:
        for item in plan:
            print(json.dumps(request_copilot_review(item["number"])))
    return 0  # advisory/request-only — always exits 0


if __name__ == "__main__":
    raise SystemExit(main())
