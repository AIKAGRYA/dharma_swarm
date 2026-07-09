#!/usr/bin/env python3
"""Governance gate aggregator (deadlock-safe teeth for path-filtered gates).

The doctrine gates are path-filtered, so branch protection cannot require them
without deadlocking unrelated PRs (a required check that never runs never turns
green). This aggregator runs on EVERY PR, reads the check-runs recorded for the
head SHA, and fails only if an allowlisted gate reported a failing conclusion.
Anti-deadlock rule: a gate that DID NOT RUN (absent or still in flight) is NOT a
failure.

    aggregate_gate_verdicts.py --repo owner/name --sha <sha> [--wait-seconds N]
    aggregate_gate_verdicts.py --self-test    # no network; fixture check
Exit: 0 = all reporting gates passed; 1 = a real gate failed; 2 = operational
error (bad args / could not read check-runs).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

# Exact GitHub check-run names (== each gate job's `name:`), byte-for-byte.
# Em-dashes (U+2014) in two entries are intentional.
ALLOWLIST = (
    "semgrep",
    "Rule 10 — module line budget",
    "Quality ratchet - repo-wide fitness function",
    "Fourfold Shakti Warrant",
    "titanium-verify — sound purity/effect certification",
    "TCB import & AST boundary",
)

PASSING_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})


def latest_for(name, check_runs):
    """Most-recent check-run (max id) with this exact name, or None."""
    matches = [r for r in check_runs if r.get("name") == name]
    if not matches:
        return None
    return max(matches, key=lambda r: r.get("id") or 0)


def gate_verdict(name, check_runs):
    """Classify one gate -> (verdict, conclusion). verdict in PASS/FAIL/NOT-RUN;
    NOT-RUN covers absent gates and gates not yet in a terminal state."""
    run = latest_for(name, check_runs)
    if run is None:
        return "NOT-RUN", None
    if run.get("status") != "completed":
        return "NOT-RUN", run.get("status")
    concl = run.get("conclusion")
    if concl in PASSING_CONCLUSIONS:
        return "PASS", concl
    return "FAIL", concl


def classify(check_runs, allowlist=ALLOWLIST):
    """Pure classifier -> (exit_code, rows). exit_code is 0 unless at least one
    allowlisted gate FAILED. rows = list of (name, verdict, conclusion)."""
    rows = []
    failed = False
    for name in allowlist:
        verdict, concl = gate_verdict(name, check_runs)
        rows.append((name, verdict, concl))
        if verdict == "FAIL":
            failed = True
    return (1 if failed else 0), rows


def render_table(rows):
    width = max((len(n) for n, _, _ in rows), default=0)
    lines = ["", f"  {'GATE'.ljust(width)}  VERDICT   CONCLUSION"]
    lines.append(f"  {'-' * width}  --------  ----------")
    for name, verdict, concl in rows:
        lines.append(f"  {name.ljust(width)}  {verdict.ljust(8)}  {concl or '-'}")
    return "\n".join(lines)


def fetch_check_runs(repo, sha):
    """Fetch all check-runs for `repo` at `sha` via the gh CLI."""
    cmd = [
        "gh", "api", "--paginate",
        f"repos/{repo}/commits/{sha}/check-runs?per_page=100",
        "--jq", ".check_runs[]",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api failed: {proc.stderr.strip()}")
    runs = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            runs.append(json.loads(line))
    return runs


def _allowlisted_still_running(check_runs, allowlist=ALLOWLIST):
    for name in allowlist:
        run = latest_for(name, check_runs)
        if run is not None and run.get("status") != "completed":
            return True
    return False


def fetch_settled(repo, sha, wait_seconds, poll_interval):
    """Fetch, optionally polling until started allowlisted gates conclude. Gates
    that never appear (path-filtered out) are NOT waited on (anti-deadlock)."""
    deadline = time.monotonic() + max(0, wait_seconds)
    runs = fetch_check_runs(repo, sha)
    while wait_seconds > 0 and _allowlisted_still_running(runs):
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_interval)
        runs = fetch_check_runs(repo, sha)
    return runs


# self-test fixtures (no network)
_SELF_TEST_FIXTURES = {
    "all-success": (
        [{"id": i, "name": n, "status": "completed", "conclusion": "success"}
         for i, n in enumerate(ALLOWLIST)],
        0,
    ),
    "one-failure": (
        [{"id": 1, "name": "semgrep", "status": "completed",
          "conclusion": "failure"}],
        1,
    ),
    "not-run-is-ok": ([], 0),
    "unrelated-failure": (
        [{"id": 1, "name": "some-other-check", "status": "completed",
          "conclusion": "failure"}],
        0,
    ),
    "in-progress-is-not-run": (
        [{"id": 1, "name": "semgrep", "status": "in_progress",
          "conclusion": None}],
        0,
    ),
}


def run_self_test():
    ok = True
    for label, (fixture, expected) in _SELF_TEST_FIXTURES.items():
        code, _ = classify(fixture)
        ok = ok and (code == expected)
        mark = "ok" if code == expected else "FAIL"
        print(f"  [{mark}] {label}: exit={code} expected={expected}")
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aggregate governance gate verdicts.")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--sha", default=os.environ.get("GITHUB_SHA"))
    ap.add_argument("--wait-seconds", type=int, default=0,
                    help="Poll until started allowlisted gates conclude.")
    ap.add_argument("--poll-interval", type=int, default=20)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.repo or not args.sha:
        print("error: --repo and --sha (or GITHUB_REPOSITORY/GITHUB_SHA) required",
              file=sys.stderr)
        return 2

    try:
        runs = fetch_settled(args.repo, args.sha,
                             args.wait_seconds, args.poll_interval)
    except (RuntimeError, json.JSONDecodeError, OSError) as exc:
        print(f"error: could not read check-runs: {exc}", file=sys.stderr)
        return 2

    code, rows = classify(runs)
    print(f"Governance aggregate for {args.repo}@{args.sha}")
    print(render_table(rows))
    failures = [n for n, v, _ in rows if v == "FAIL"]
    if failures:
        print(f"\nFAIL: {len(failures)} governance gate(s) concluded failure: "
              + ", ".join(failures))
    else:
        print("\nPASS: no reporting governance gate failed "
              "(gates that did not run are not failures).")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
