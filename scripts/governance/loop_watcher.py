#!/usr/bin/env python3
"""Loop watcher — read-only counter-metrics over lane PRs + ingestion + canary (PR-F).

Three duties under the 2026-07-29 operator ruling (§9 and the PR-F
workstream), all fail-closed and none carrying merge/promote/policy-edit
authority:

1. WATCH (read-only): sweep open lane PRs (labels: lane-output, bot-pr,
   walk-ready) with four counter-metric checks:
   - test-deletion-without-signoff: diff deletes test functions/files while
     no APPROVED review names them;
   - ci-actually-executed: every required context (from
     scripts/governance/ci_parity_manifest.json) REPORTED on the head SHA —
     absence is a finding, not green (the 2026-07-04 empty-rollup incident);
   - tier2-touch: changed paths hitting the referee layer
     (scripts/governance/automerge_tier_policy.json tiers.tier2.paths);
   - diff-sanity: changed lines over the labeled tier's ceiling.
   Findings → one PR comment per head SHA (marker-deduped) + a JSON report
   for the daily brief.

2. INGEST (create-only): new operator comments on the pinned walking-brief
   issue become mailbox tasks for recipient `hardening-lane`, written to the
   `loop-tasks` branch under roaming_mailbox/tasks/ via the contents API —
   never to main, never merging anything. Only comments authored by the
   repo owner login are read; everything else on the issue is ignored as
   untrusted. Each ingested comment is echoed in the next brief
   (confirmation-by-visibility).

3. CANARY (weekly, §9): open a seeded-defect PR from sandbox/canary/
   fixtures, labeled `canary-sandbox` (structurally unmergeable by the
   unattended lane: check_automerge_tier_policy hard-fails that label,
   whatever any reviewer says). A reviewer that APPROVES a live canary is
   reported as compromised in the brief; dropping it from rotation is a
   Tier-2 operator action, deliberately not automated.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "scripts" / "governance" / "automerge_tier_policy.json"
MANIFEST_PATH = REPO_ROOT / "scripts" / "governance" / "ci_parity_manifest.json"
# canary-sandbox is watched for the §9 reviewer-integrity loop: a seeded
# canary that collects an APPROVED review is the whole signal, and a label
# the watcher never selects can never produce it (Greptile on PR #1163).
WATCH_LABELS = ("lane-output", "bot-pr", "walk-ready", "canary-sandbox")
CANARY_LABEL = "canary-sandbox"
COMMENT_MARKER = "<!-- loop-watcher:{sha} -->"
TASKS_BRANCH = "loop-tasks"
BRIEF_ISSUE_LABEL = "walking-brief"
INGEST_MARKER = "<!-- loop-watcher-ingested -->"
TEST_DELETION_RE = re.compile(r"^-\s*def (test_[A-Za-z0-9_]+)", re.MULTILINE)
# Operator-dictated prerequisites: "depends on: mbx_a, mbx_b" in the comment.
# Ids are validated against the mailbox's own grammar so a malformed or
# traversal-shaped id is dropped rather than written into a task record
# (dharma_swarm/roaming_mailbox.py; Greptile on PR #1163).
DEPENDS_ON_RE = re.compile(r"^\s*depends[-_ ]on\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def parse_depends_on(body: str) -> list[str]:
    deps: list[str] = []
    for match in DEPENDS_ON_RE.finditer(body or ""):
        for raw in re.split(r"[,\s]+", match.group(1).strip()):
            token = raw.strip().strip("`")
            if token and TASK_ID_RE.fullmatch(token):
                deps.append(token)
    return sorted(set(deps))


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _gh(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True,
                          timeout=timeout, check=False)


def _gh_json(args: list[str]) -> object | None:
    result = _gh(args)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _tier2_patterns() -> list[str]:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return policy["tiers"]["tier2"]["paths"]


def _required_contexts() -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [row["context"] for row in manifest["required_contexts"]]


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    return path == pattern or path.startswith(pattern.rstrip("*"))


# ------------------------------------------------------------------ watch


def watch_pr(repo: str, pr: dict) -> dict:
    number = pr["number"]
    findings: list[str] = []

    diff = _gh(["pr", "diff", str(number), "--repo", repo])
    diff_text = diff.stdout if diff.returncode == 0 else ""
    diff_lines = diff_text.splitlines()
    removed = sorted(set(TEST_DELETION_RE.findall(diff_text)))
    # Whole-file deletions under tests/ need sign-off on their own: a file
    # with no `def test_*` line (a conftest, a fixture module, golden data)
    # leaves `removed` empty, and the old condition then reported nothing
    # even though a test file vanished (Greptile on PR #1163).
    deleted_test_files = [
        line[len("--- a/"):].strip()
        for index, line in enumerate(diff_lines)
        if line.startswith("--- a/tests/")
        and index + 1 < len(diff_lines)
        and diff_lines[index + 1].startswith("+++ /dev/null")
    ]
    needs_signoff = sorted(set(removed) | set(deleted_test_files))
    if needs_signoff:
        approvals = [
            r for r in pr.get("latestReviews", []) if r.get("state") == "APPROVED"
        ]
        named = [r for r in approvals
                 if all(name in (r.get("body") or "") for name in needs_signoff)]
        if not named:
            findings.append(
                f"test deletions without named sign-off: {needs_signoff}"
            )

    # §9 reviewer-integrity: an APPROVED review on a seeded canary means the
    # reviewer passed a known defect. That is the entire signal the canary
    # exists to produce, so it is a finding regardless of anything else.
    labels = {row.get("name") for row in pr.get("labels", [])}
    if CANARY_LABEL in labels:
        passers = sorted({
            (r.get("author") or {}).get("login", "")
            for r in pr.get("latestReviews", []) if r.get("state") == "APPROVED"
        } - {""})
        if passers:
            findings.append(
                f"CANARY PASSED by {passers} — a seeded defect was approved; "
                "drop these reviewers from rotation until fixed (ruling §9)"
            )

    checks = _gh_json([
        "api", f"repos/{repo}/commits/{pr['headRefOid']}/check-runs?per_page=100",
    ])
    reported = {run.get("name") for run in (checks or {}).get("check_runs", [])} if isinstance(checks, dict) else set()
    missing = [c for c in _required_contexts() if c not in reported]
    if missing:
        findings.append(f"required contexts not reported on head SHA: {missing}")

    changed = [f["path"] for f in pr.get("files", [])]
    hits = sorted({p for p in changed for pat in _tier2_patterns() if _matches(p, pat)})
    if hits:
        findings.append(f"tier-2 referee paths touched: {hits}")

    lines = int(pr.get("additions", 0)) + int(pr.get("deletions", 0))
    if lines > 600:
        findings.append(f"diff over tier-1 ceiling: {lines} > 600 changed lines")

    return {"pr": number, "head": pr["headRefOid"], "findings": findings,
            "deleted_test_files": deleted_test_files}


def post_findings(repo: str, pr: dict, findings: list[str]) -> None:
    marker = COMMENT_MARKER.format(sha=pr["headRefOid"])
    existing = _gh_json([
        "pr", "view", str(pr["number"]), "--repo", repo, "--json", "comments",
    ])
    bodies = [c.get("body", "") for c in (existing or {}).get("comments", [])] if isinstance(existing, dict) else []
    if any(marker in b for b in bodies):
        return
    lines = "\n".join(f"- {f}" for f in findings)
    _gh([
        "pr", "comment", str(pr["number"]), "--repo", repo, "--body",
        f"{marker}\n## 👁 Loop watcher findings (read-only)\n\n{lines}\n\n"
        "_Counter-metric watch under the 2026-07-29 ruling; this comment "
        "carries no merge authority._\n\n---\n"
        "_Generated by [Claude Code](https://claude.ai/code)_",
    ])


def run_watch(repo: str, report_path: Path) -> dict:
    reports = []
    seen: set[int] = set()
    for label in WATCH_LABELS:
        rows = _gh_json([
            "pr", "list", "--repo", repo, "--state", "open", "--label", label,
            "--json",
            "number,headRefOid,files,additions,deletions,latestReviews,labels",
            "--limit", "30",
        ])
        for pr in rows if isinstance(rows, list) else []:
            if pr["number"] in seen:
                continue
            seen.add(pr["number"])
            result = watch_pr(repo, pr)
            reports.append(result)
            if result["findings"]:
                post_findings(repo, pr, result["findings"])
    payload = {"schema": "dharma.loop_watcher_report.v1",
               "generated_at": _utc_stamp(), "watched": len(reports),
               "reports": reports}
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return payload


# ----------------------------------------------------------------- ingest


def run_ingest(repo: str, owner_login: str) -> list[str]:
    issues = _gh_json([
        "issue", "list", "--repo", repo, "--state", "open",
        "--label", BRIEF_ISSUE_LABEL, "--json", "number", "--limit", "1",
    ])
    if not (isinstance(issues, list) and issues):
        return []
    number = issues[0]["number"]
    data = _gh_json([
        "issue", "view", str(number), "--repo", repo, "--json", "comments",
    ])
    comments = (data or {}).get("comments", []) if isinstance(data, dict) else []
    ingested: list[str] = []
    for comment in comments:
        author = (comment.get("author") or {}).get("login", "")
        body = comment.get("body", "")
        if author != owner_login or INGEST_MARKER in body or "walking-brief:v1" in body:
            continue
        if any(INGEST_MARKER in later.get("body", "")
               and f"ref:{comment.get('id', '')}" in later.get("body", "")
               for later in comments):
            continue
        # The comment id makes the task id collision-resistant: a
        # second-resolution stamp alone gave two comments ingested in the
        # same second the same Contents path, and the second create failed
        # with no task and no confirmation (Greptile on PR #1163).
        comment_id = re.sub(r"[^A-Za-z0-9_-]", "", str(comment.get("id", "")))
        task_id = f"mbx_op_{_utc_stamp().lower()}_{comment_id}" if comment_id \
            else f"mbx_op_{_utc_stamp().lower()}"
        depends_on = parse_depends_on(body)
        task = {
            "task_id": task_id, "recipient": "hardening-lane",
            "sender": f"operator:{owner_login}",
            "summary": body.strip().splitlines()[0][:80] if body.strip() else "operator note",
            "body": body,
            # "blocked" mirrors the mailbox's own encoding for dependent
            # work (dharma_swarm/roaming_mailbox.py): a legacy poller that
            # ignores depends_on must never claim a task whose prerequisite
            # is unanswered.
            "status": "blocked" if depends_on else "queued",
            "capabilities": [],
            "metadata": {"source": "walking-brief-issue", "comment_id": comment.get("id", "")},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "claimed_at": "", "claimed_by": "", "responded_at": "",
            "response_ref": "", "depends_on": depends_on,
        }
        content = base64.b64encode(
            (json.dumps(task, indent=2, sort_keys=True) + "\n").encode()
        ).decode()
        put = _gh([
            "api", "-X", "PUT",
            f"repos/{repo}/contents/roaming_mailbox/tasks/{task_id}.json",
            "-f", f"message=watcher: ingest operator note as {task_id}",
            "-f", f"content={content}", "-f", f"branch={TASKS_BRANCH}",
        ])
        if put.returncode == 0:
            ingested.append(task["summary"])
            _gh([
                "issue", "comment", str(number), "--repo", repo, "--body",
                f"{INGEST_MARKER} ref:{comment.get('id', '')}\n"
                f"🎙️ Understood as task `{task_id}` for the hardening lane: "
                f"“{task['summary']}”. It appears in tomorrow's brief.\n\n---\n"
                "_Generated by [Claude Code](https://claude.ai/code)_",
            ])
    return ingested


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loop watcher (read-only)")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--owner-login", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-ingest", action="store_true")
    args = parser.parse_args(argv)

    payload = run_watch(args.repo, Path(args.report))
    ingested = [] if args.skip_ingest else run_ingest(args.repo, args.owner_login)
    print(json.dumps({"watched": payload["watched"],
                      "findings": sum(bool(r["findings"]) for r in payload["reports"]),
                      "ingested": ingested}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
