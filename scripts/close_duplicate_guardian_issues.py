#!/usr/bin/env python3
"""Close duplicate [GUARDIAN] auto-issues, keeping the oldest of each group.

Usage:
    # Show what would happen, no writes:
    python scripts/close_duplicate_guardian_issues.py --dry-run

    # Actually close duplicates (requires `gh` authenticated):
    python scripts/close_duplicate_guardian_issues.py --execute

What it does:
    1. Lists open issues whose title starts with ``[GUARDIAN] ``.
    2. Groups them by normalized title (case-insensitive, prefix-stripped).
    3. For each group with >1 issue, keeps the OLDEST (lowest issue number)
       open and closes the rest with a comment pointing at the fix PR.
    4. If ``--keep-issue N`` is passed, that issue number is preserved in
       its group instead of the oldest.

Why this exists:
    The Guardian dedup logic in ``dharma_swarm/guardian_crew.py`` was
    buggy (see PR fixing it). Until that fix lands and the daemon is
    redeployed, 70+ duplicate issues exist for the same 3 underlying
    bugs (PalaceQuery.__init__, TelosGraph.get_by_name,
    TaskBoard.get_by_title). This script cleans the backlog.

Safety:
    - Defaults to ``--dry-run``. Closes nothing unless ``--execute`` is set.
    - Never closes the chosen "keeper" for each group.
    - Adds a comment before closing so the audit trail is preserved.
    - Caps at 200 closes per run; re-run if more remain.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from typing import Any


REPO = "AIKAGRYA/dharma_swarm"
MAX_CLOSES_PER_RUN = 200
DEFAULT_CLOSE_COMMENT = (
    "Closing as duplicate. The Guardian dedup logic has been hardened "
    "(see PR fixing the title-search bug + adding open-PR awareness + "
    "a max-open-duplicates circuit breaker). One issue per distinct "
    "finding is kept open; this one duplicates that canonical issue."
)


def _normalize(title: str) -> str:
    """Match the dedup normalization in guardian_crew._normalize_title_for_dedup."""
    s = title.strip()
    if s.startswith("[GUARDIAN]"):
        s = s[len("[GUARDIAN]"):].strip()
    return " ".join(s.lower().split())


def _list_open_guardian_issues() -> list[dict[str, Any]]:
    proc = subprocess.run(
        [
            "gh", "issue", "list",
            "--repo", REPO,
            "--state", "open",
            "--json", "number,title,createdAt",
            "--limit", "500",
        ],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if proc.returncode != 0:
        print(f"gh issue list failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)
    issues = json.loads(proc.stdout or "[]")
    return [i for i in issues if i.get("title", "").startswith("[GUARDIAN]")]


def _group_duplicates(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        key = _normalize(issue.get("title", ""))
        if key:
            groups[key].append(issue)
    # Sort each group by issue number ascending (oldest first)
    for key in groups:
        groups[key].sort(key=lambda i: i["number"])
    return groups


def _close_issue(number: int, comment: str, execute: bool) -> bool:
    if not execute:
        print(f"  [DRY-RUN] would close #{number} with comment")
        return True
    # Add comment then close
    c1 = subprocess.run(
        ["gh", "issue", "comment", str(number), "--repo", REPO, "--body", comment],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if c1.returncode != 0:
        print(f"  comment on #{number} failed: {c1.stderr}", file=sys.stderr)
        return False
    c2 = subprocess.run(
        ["gh", "issue", "close", str(number), "--repo", REPO, "--reason", "not planned"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if c2.returncode != 0:
        print(f"  close #{number} failed: {c2.stderr}", file=sys.stderr)
        return False
    print(f"  closed #{number}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True, help="Show plan only (default)")
    g.add_argument("--execute", action="store_true", help="Actually close duplicates")
    parser.add_argument("--keep-issue", type=int, action="append", default=[],
                        help="Issue number to preserve in its group (repeatable)")
    parser.add_argument("--comment", default=DEFAULT_CLOSE_COMMENT,
                        help="Close comment (default points at dedup-fix PR)")
    args = parser.parse_args()

    execute = args.execute
    keep_overrides = set(args.keep_issue)

    issues = _list_open_guardian_issues()
    print(f"Found {len(issues)} open [GUARDIAN] issues")
    if not issues:
        return 0

    groups = _group_duplicates(issues)
    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"Found {len(duplicate_groups)} groups with duplicates "
          f"(total duplicates: {sum(len(v) - 1 for v in duplicate_groups.values())})")
    print(f"Mode: {'EXECUTE' if execute else 'DRY-RUN'}")
    print()

    closed = 0
    for key, group in sorted(duplicate_groups.items(), key=lambda kv: -len(kv[1])):
        # Pick keeper: explicit override, else oldest (lowest number)
        override = next((i for i in group if i["number"] in keep_overrides), None)
        keeper = override or group[0]
        to_close = [i for i in group if i["number"] != keeper["number"]]
        print(f"Group: {key[:80]}  ({len(group)} issues, keeping #{keeper['number']})")
        for issue in to_close:
            if closed >= MAX_CLOSES_PER_RUN:
                print(f"  hit MAX_CLOSES_PER_RUN={MAX_CLOSES_PER_RUN}, stopping")
                return 0
            if _close_issue(issue["number"], args.comment, execute):
                closed += 1
        print()

    print(f"Done. {'Closed' if execute else 'Would close'} {closed} duplicate(s).")
    if not execute:
        print("Re-run with --execute to actually close them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
