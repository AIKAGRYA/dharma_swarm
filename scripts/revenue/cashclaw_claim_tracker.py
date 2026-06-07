#!/usr/bin/env python3
"""CashClaw Claim Tracker — polls submitted PRs for status changes.

Checks open claims in ~/.cashclaw/evolution.db and updates:
- pr_merged: PR was merged, bounty earned
- pr_closed: PR was closed without merge
- pr_submitted: still open, no change
- competition_count: how many competing PRs exist

Outputs a status report.
"""
import sqlite3
import subprocess
import json
import os
import sys
from datetime import datetime


def gh_api(path, jq=None):
    cmd = ["gh", "api", path]
    if jq:
        cmd += ["--jq", jq]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None
    if jq:
        return r.stdout.strip()
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.stdout.strip()


def get_pr_status(pr_url):
    """Get PR status: merged, closed, or open."""
    m = pr_url.rstrip("/").split("/")
    owner = m[-4]
    repo = m[-3]
    number = m[-1]

    data = gh_api(f"repos/{owner}/{repo}/pulls/{number}")
    if not data:
        return {"status": "unknown", "error": "API failed"}

    state = data.get("state", "unknown")
    merged = data.get("merged", False)
    mergeable = data.get("mergeable")
    review_comments = data.get("review_comments", 0)
    additions = data.get("additions", 0)
    deletions = data.get("deletions", 0)

    status = "open"
    if merged:
        status = "merged"
    elif state == "closed":
        status = "closed"

    return {
        "status": status,
        "state": state,
        "merged": merged,
        "mergeable": mergeable,
        "review_comments": review_comments,
        "additions": additions,
        "deletions": deletions,
    }


def main():
    db_path = os.path.expanduser("~/.cashclaw/evolution.db")
    if not os.path.exists(db_path):
        print("No evolution DB found at ~/.cashclaw/evolution.db")
        sys.exit(1)

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    claims = db.execute(
        "SELECT * FROM claims WHERE status NOT IN ('paid', 'rejected')"
    ).fetchall()

    if not claims:
        print("No active claims to track.")
        db.close()
        return

    print(f"Tracking {len(claims)} active claims...\n")

    updated = []
    for claim in claims:
        pr_url = claim["pr_url"]
        if not pr_url:
            continue

        result = get_pr_status(pr_url)
        new_status = claim["status"]
        now = datetime.utcnow().isoformat() + "Z"

        if result["status"] == "merged":
            new_status = "pr_merged"
        elif result["status"] == "closed":
            new_status = "pr_closed"

        db.execute(
            "UPDATE claims SET status = ?, updated_at = ?, result = ? WHERE claim_id = ?",
            (new_status, now, json.dumps(result), claim["claim_id"]),
        )

        value = claim["value_cents"] / 100
        status_marker = {
            "pr_submitted": "...",
            "pr_merged": "EARNED",
            "pr_closed": "LOST",
            "open": "...",
        }.get(new_status, new_status)

        print(f"  ${value:>7.0f}  [{status_marker:>10}]  {claim['title'][:60]}")
        print(f"          PR: {pr_url}")
        if result.get("review_comments"):
            print(f"          Review comments: {result['review_comments']}")
        print()

        updated.append(claim["claim_id"])

    db.commit()

    # Summary
    all_claims = db.execute("SELECT status, SUM(value_cents) as total FROM claims GROUP BY status").fetchall()
    print("=== PORTFOLIO ===")
    for row in all_claims:
        print(f"  {row['status']:15s}: ${row['total']/100:>8.0f}")

    earned = db.execute("SELECT SUM(value_cents) FROM claims WHERE status = 'pr_merged'").fetchone()[0] or 0
    pending = db.execute("SELECT SUM(value_cents) FROM claims WHERE status = 'pr_submitted'").fetchone()[0] or 0
    print(f"\n  Earned:  ${earned/100:.0f}")
    print(f"  Pending: ${pending/100:.0f}")

    db.close()


if __name__ == "__main__":
    main()
