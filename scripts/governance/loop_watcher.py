#!/usr/bin/env python3
"""Loop watcher — read-only counter-metrics over lane PRs + ingestion + canary (PR-F).

Three duties under the 2026-07-29 operator ruling (§9 and the PR-F
workstream), all fail-closed and none carrying merge/promote/policy-edit
authority:

1. WATCH (read-only): sweep open lane PRs (labels: lane-output, bot-pr,
   walk-ready, canary-sandbox) with four counter-metric checks:
   - test-deletion-without-signoff: diff deletes test functions/files while
     no approval QUALIFIED BY THE DOOR'S OWN RULES names them — current
     head, trusted reviewer family, never the author's family;
   - ci-actually-executed: every required context (from
     scripts/governance/ci_parity_manifest.json) REPORTED on the head SHA —
     absence is a finding, not green (the 2026-07-04 empty-rollup incident);
   - tier2-touch: changed paths hitting the referee layer
     (scripts/governance/automerge_tier_policy.json tiers.tier2.paths);
   - diff-sanity: changed lines over THAT PR's tier ceiling (tier0 300 /
     tier1 600 / tier2 400), classified the way the door classifies it.
   Findings → one PR comment per head SHA, kept equal to the current result
   (created / edited / left alone), + a JSON report for the daily brief.

   Every enumeration fails closed: a failed `gh pr list`, review page, or
   file page is recorded as DEGRADED and exits nonzero. "watched: 0" must
   mean no lane PRs, never a blind run.

2. INGEST (create-only): new operator comments on the pinned walking-brief
   issue become mailbox tasks for recipient `hardening-lane`, written to the
   `loop-tasks` branch under roaming_mailbox/tasks/ via the contents API —
   never to main, never merging anything. Only comments authored by the
   repo owner login are read; everything else on the issue is ignored as
   untrusted, and only the workflow's own identity may post the receipt
   that retires a directive. Each ingested comment is recorded in the
   report so the next brief can echo it (confirmation-by-visibility).

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
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The watcher measures the SAME policy the door enforces, so it imports the
# door's own qualification logic rather than re-deriving it: a second
# implementation of "which approval counts" is a second thing to drift
# (Codex on PR #1163, threads on trust-qualified sign-offs and pagination).
import check_automerge_tier_policy as door  # noqa: E402

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
# Only the workflow's own identity may retire an operator directive. The
# marker is public text in a public issue, so trusting any author let any
# participant who could read an owner comment's id suppress that directive
# forever by posting a forged receipt (Codex on PR #1163).
RECEIPT_AUTHOR_LOGINS = frozenset({"github-actions[bot]"})
# The door's regex, not a copy of it. The copy here had already drifted: it
# matched only `-def test_*`, so removing an `async def test_*` — the
# majority shape in a repo running asyncio_mode = "auto" — produced no
# finding at all, while the door itself matched it (fixed there on PR
# #1160). A counter-metric that re-derives what it measures drifts from it;
# that is the whole lesson of this review round (Greptile on PR #1163).
TEST_DELETION_RE = door.TEST_DELETION_RE
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


def _policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _required_contexts() -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [row["context"] for row in manifest["required_contexts"]]


def _fetch_all_pages(resource: str) -> list | None:
    """Every page of a REST list resource, fail closed (None) on any failure.

    One 100-row page is never complete: `gh pr list --json files` silently
    stops at 100, so a tier-2 referee path at position 101 produced no
    finding at all (Codex on PR #1163). Same collector the door uses.
    """
    return door._fetch_all_pages(resource)


def fetch_check_run_names(repo: str, sha: str) -> set[str] | None:
    """Every check-run NAME on *sha*, across ALL pages. None on any failure.

    The check-runs endpoint returns a dict (not a bare list), so it needs its
    own pager rather than _fetch_all_pages. Reading one page and deriving
    required-context ABSENCE from it reported a present required check as
    missing whenever the head carried more than 100 runs — this repo already
    reports ~45, and re-runs add rows on the same SHA (Greptile on PR #1163).
    """
    names: set[str] = set()
    page = 1
    while page <= 50:  # 5000 check runs; a bound, not an expected limit
        payload = _gh_json([
            "api",
            f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={page}",
        ])
        if not isinstance(payload, dict):
            return None
        rows = payload.get("check_runs")
        if not isinstance(rows, list):
            return None
        names.update(str(row.get("name") or "") for row in rows)
        if len(rows) < 100:
            return names
        page += 1
    return None  # ran past the bound: treat as unreadable, never as complete


def qualified_signoffs(reviews: list[dict], head_sha: str, author: str,
                       policy: dict) -> list[dict]:
    """Standing approvals that could authorize a test deletion.

    Applies the door's own qualification (check_automerge_tier_policy):
    latest state-bearing review per login, APPROVED, submitted against the
    CURRENT head, from a login in a trusted reviewer family, and never from
    the author's own family. A stale approval or an arbitrary reviewer must
    not silence a counter-metric (Codex on PR #1163).
    """
    families = {
        door._normalize_login(login): family
        for login, family in policy["reviewer_families"].items()
    }
    author_family = policy["author_families"].get(author, f"unknown:{author}")
    qualified = []
    for row in door.latest_approvals(reviews, head_sha):
        family = families.get(door._normalize_login(row.get("login", "")))
        if family is None or family == author_family:
            continue
        qualified.append({**row, "family": family})
    return qualified


# ------------------------------------------------------------------ watch


def watch_pr(repo: str, pr: dict) -> dict:
    number = pr["number"]
    head_sha = pr["headRefOid"]
    author = (pr.get("author") or {}).get("login", "")
    policy = _policy()
    findings: list[str] = []
    degraded: list[str] = []

    # One paginated review read serves both the sign-off qualification and
    # the §9 canary check; it carries commit_id (which SHA each review saw)
    # and the "<app>[bot]" logins the policy's families are keyed to.
    reviews = _fetch_all_pages(f"repos/{repo}/pulls/{number}/reviews")
    if reviews is None:
        degraded.append("reviews")

    diff = _gh(["pr", "diff", str(number), "--repo", repo])
    if diff.returncode != 0:
        # An unavailable diff is not an empty diff. Substituting "" waived
        # the test-deletion control entirely: a PR removing a whole test
        # file produced no finding and left the sweep healthy, because
        # nothing distinguished "read it, found nothing" from "could not
        # read it" (Greptile on PR #1163).
        findings.append(
            "diff unavailable — test-deletion state unknown on this head; "
            "the deletion control did NOT run"
        )
        degraded.append("diff")
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
        if reviews is None:
            findings.append(
                "review enumeration failed — sign-off state unknown, "
                f"cannot clear test deletions: {needs_signoff}"
            )
        else:
            approvals = qualified_signoffs(reviews, head_sha, author, policy)
            if not [r for r in approvals
                    if all(name in (r.get("body") or "") for name in needs_signoff)]:
                findings.append(
                    f"test deletions without named sign-off from a trusted, "
                    f"non-author reviewer family on the current head: {needs_signoff}"
                )

    # §9 reviewer-integrity: an APPROVED review on a seeded canary means the
    # reviewer passed a known defect. That is the entire signal the canary
    # exists to produce, so it is a finding regardless of anything else —
    # and unlike a deletion sign-off it is reported for ANY revision, since
    # approving a seeded defect once is the compromise.
    labels = {row.get("name") for row in pr.get("labels", [])}
    if CANARY_LABEL in labels:
        if reviews is None:
            # `reviews or []` would turn "could not read" into "nobody
            # approved" and leave the report healthy while the one control
            # the canary exists to run was never evaluated (Greptile on
            # PR #1163). Unknown is a finding, and it degrades the run.
            findings.append(
                "CANARY REVIEW STATE UNKNOWN — review enumeration failed; "
                "cannot tell whether a seeded defect was approved (ruling §9)"
            )
        else:
            passers = sorted({
                str((r.get("user") or {}).get("login") or "")
                for r in reviews
                if str(r.get("state") or "").upper() == "APPROVED"
            } - {""})
            if passers:
                findings.append(
                    f"CANARY PASSED by {passers} — a seeded defect was approved; "
                    "drop these reviewers from rotation until fixed (ruling §9)"
                )

    checks = fetch_check_run_names(repo, head_sha)
    if checks is None:
        # `checks or {}` made a failed read indistinguishable from "no checks
        # reported": the watcher published a missing-context finding and
        # still returned OK, so the run that LOST required-check visibility
        # looked exactly like a healthy one (Greptile on PR #1163). This is
        # the absence-is-not-green rule applied to the checker itself.
        findings.append(
            "check-run enumeration failed — required-context visibility lost "
            "on this head; absence of contexts here is unknown, not green"
        )
        degraded.append("checks")
    else:
        missing = [c for c in _required_contexts() if c not in checks]
        if missing:
            findings.append(f"required contexts not reported on head SHA: {missing}")

    # Paginated REST files, not the `gh pr list --json files` nested
    # connection: that one truncates at 100 and hid tier-2 paths beyond it.
    files = _fetch_all_pages(f"repos/{repo}/pulls/{number}/files")
    if files is None:
        findings.append("changed-file enumeration failed — tier classification unknown")
        degraded.append("files")
        tier = None
    else:
        changed = [row.get("filename", "") for row in files]
        hits = door.tier2_hits(changed, policy)
        if hits:
            findings.append(f"tier-2 referee paths touched: {hits}")
        # Same tier derivation the door uses, so the ceiling the watcher
        # reports is the ceiling that will actually be enforced: a doc-only
        # tier-0 PR is held to 300 and a referee-path PR to tier-2's own
        # ceiling, not a blanket 600 (Codex on PR #1163).
        tier = "tier2" if hits else door.classify_tier(changed, policy)
        lines = int(pr.get("additions", 0)) + int(pr.get("deletions", 0))
        ceiling = int(policy["tiers"][tier]["max_diff_lines"])
        if lines > ceiling:
            findings.append(
                f"diff over {tier} ceiling: {lines} > {ceiling} changed lines"
            )

    return {"pr": number, "head": head_sha, "tier": tier, "findings": findings,
            "degraded": sorted(set(degraded)),
            "deleted_test_files": deleted_test_files}


def render_findings(marker: str, findings: list[str]) -> str:
    body = ("\n".join(f"- {f}" for f in findings) if findings
            else "_No counter-metric findings on this head._")
    return (
        f"{marker}\n## 👁 Loop watcher findings (read-only)\n\n{body}\n\n"
        "_Counter-metric watch under the 2026-07-29 ruling; this comment "
        "carries no merge authority._\n\n---\n"
        "_Generated by [Claude Code](https://claude.ai/code)_"
    )


def sync_findings(repo: str, pr: dict, findings: list[str]) -> str:
    """Keep the watcher's per-SHA comment equal to the CURRENT result.

    CI completing and reviews arriving change the findings without changing
    the head SHA, so 'a marker exists → say nothing' pinned a stale warning
    to the PR forever and could never surface a newly applicable one
    (Codex on PR #1163). The comment is now created, edited, or left alone
    based on whether its rendered body still matches.

    Returns the disposition. "unknown", "create_failed" and "update_failed"
    all degrade the run: publishing IS the watcher's output, so a finding
    that was computed and never reached the PR is a finding nobody has
    (Greptile on PR #1163).
    """
    marker = COMMENT_MARKER.format(sha=pr["headRefOid"])
    desired = render_findings(marker, findings)
    # REST comments (not `gh pr view --json comments`): this carries the
    # numeric id needed to PATCH, and user.login for the authorship check.
    existing = _fetch_all_pages(f"repos/{repo}/issues/{pr['number']}/comments")
    if existing is None:
        return "unknown"
    mine = [
        row for row in existing
        if marker in str(row.get("body") or "")
        and str((row.get("user") or {}).get("login") or "") in RECEIPT_AUTHOR_LOGINS
    ]
    if not mine:
        if not findings:
            return "clean"
        posted = _gh([
            "pr", "comment", str(pr["number"]), "--repo", repo, "--body", desired,
        ])
        return "created" if posted.returncode == 0 else "create_failed"
    current = mine[-1]
    if str(current.get("body") or "") == desired:
        return "unchanged"
    patched = _gh(["api", "-X", "PATCH",
                   f"repos/{repo}/issues/comments/{current['id']}",
                   "-f", f"body={desired}"])
    return "updated" if patched.returncode == 0 else "update_failed"


# Dispositions that mean the current findings did NOT reach the PR.
UNPUBLISHED_STATES = frozenset({"unknown", "create_failed", "update_failed"})


def run_watch(repo: str, report_path: Path) -> dict:
    reports = []
    seen: set[int] = set()
    failed_labels: list[str] = []
    for label in WATCH_LABELS:
        rows = _gh_json([
            "pr", "list", "--repo", repo, "--state", "open", "--label", label,
            "--json",
            "number,headRefOid,additions,deletions,author,labels",
            "--limit", "100",
        ])
        if not isinstance(rows, list):
            # A failed enumeration is an OUTAGE, not "no lane PRs". Reporting
            # watched: 0 on an auth failure or a rate limit made a blind run
            # indistinguishable from a quiet one (Codex on PR #1163).
            failed_labels.append(label)
            continue
        for pr in rows:
            if pr["number"] in seen:
                continue
            seen.add(pr["number"])
            result = watch_pr(repo, pr)
            result["comment"] = sync_findings(repo, pr, result["findings"])
            reports.append(result)
    # A per-PR read failure degrades the whole run, not just that PR's row:
    # a control that could not be evaluated is not a control that passed.
    degraded_prs = sorted(r["pr"] for r in reports if r.get("degraded"))
    unpublished = sorted(
        r["pr"] for r in reports if r.get("comment") in UNPUBLISHED_STATES
    )
    payload = {"schema": "dharma.loop_watcher_report.v1",
               "generated_at": _utc_stamp(), "watched": len(reports),
               "enumeration_failed": sorted(failed_labels),
               "degraded_prs": degraded_prs,
               "findings_unpublished": unpublished,
               "status": ("DEGRADED"
                          if failed_labels or degraded_prs or unpublished
                          else "OK"),
               "reports": reports}
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return payload


# ----------------------------------------------------------------- ingest


def receipted_comment_ids(comments: list[dict]) -> set[str]:
    """Comment ids already ingested, per the workflow's OWN receipts.

    A receipt is public text in a public issue. Honoring one from any author
    let any participant retire a legitimate operator directive forever by
    posting `<!-- loop-watcher-ingested --> ref:<id>` (Codex on PR #1163),
    so only the workflow identity's receipts count.
    """
    receipted: set[str] = set()
    for row in comments:
        login = str((row.get("user") or {}).get("login") or "")
        body = str(row.get("body") or "")
        if login not in RECEIPT_AUTHOR_LOGINS or INGEST_MARKER not in body:
            continue
        receipted.update(re.findall(r"ref:([A-Za-z0-9_-]+)", body))
    return receipted


def task_path_exists(repo: str, task_id: str) -> bool | None:
    """Whether this comment's task already exists on the tasks branch.

    None on a read failure — unknown must not read as "not created yet",
    which would be a licence to write a second copy.
    """
    result = _gh([
        "api",
        f"repos/{repo}/contents/roaming_mailbox/tasks/{task_id}.json?ref={TASKS_BRANCH}",
    ])
    if result.returncode == 0:
        return True
    combined = f"{result.stdout}\n{result.stderr}"
    if re.search(r"HTTP 404|Not Found|No commit found", combined, re.IGNORECASE):
        return False
    return None


def run_ingest(repo: str, owner_login: str) -> dict | None:
    issues = _gh_json([
        "issue", "list", "--repo", repo, "--state", "open",
        "--label", BRIEF_ISSUE_LABEL, "--json", "number", "--limit", "1",
    ])
    if not isinstance(issues, list):
        return None  # outage, not "no brief issue"
    if not issues:
        return {"ingested": [], "failed": []}
    number = issues[0]["number"]
    # REST comments: user.login is the authorship the receipt check needs,
    # and the numeric id is stable across the PATCH/create round trip.
    comments = _fetch_all_pages(f"repos/{repo}/issues/{number}/comments")
    if comments is None:
        return None
    receipted = receipted_comment_ids(comments)
    ingested: list[str] = []
    failed: list[str] = []
    for comment in comments:
        author = str((comment.get("user") or {}).get("login") or "")
        body = str(comment.get("body") or "")
        if author != owner_login or INGEST_MARKER in body or "walking-brief:v1" in body:
            continue
        if str(comment.get("id", "")) in receipted:
            continue
        # The task path is derived ONLY from the comment id — no timestamp.
        # With a stamp in it, a run whose Contents PUT succeeded but whose
        # receipt post failed left the directive un-retired, and the next
        # run minted a DIFFERENT path for the same comment: two tasks, one
        # instruction (Greptile on PR #1163). An immutable path makes the
        # retry converge — the task is already there, so the run only has
        # the receipt left to post.
        comment_id = re.sub(r"[^A-Za-z0-9_-]", "", str(comment.get("id", "")))
        if not comment_id:
            # Without a stable id there is no dedupe key, and ingesting
            # would duplicate on every run. Report it instead.
            failed.append("comment with no usable id — cannot dedupe, skipped")
            continue
        task_id = f"mbx_op_c{comment_id}"
        exists = task_path_exists(repo, task_id)
        if exists is None:
            failed.append(f"{task_id}: could not read existing task state")
            continue
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
        if not exists:
            content = base64.b64encode(
                (json.dumps(task, indent=2, sort_keys=True) + "\n").encode()
            ).decode()
            put = _gh([
                "api", "-X", "PUT",
                f"repos/{repo}/contents/roaming_mailbox/tasks/{task_id}.json",
                "-f", f"message=watcher: ingest operator note as {task_id}",
                "-f", f"content={content}", "-f", f"branch={TASKS_BRANCH}",
            ])
            if put.returncode != 0:
                failed.append(f"{task_id}: task write failed")
                continue
        # The receipt is what RETIRES the directive, so a failed post is a
        # reported failure, not a silent success: the summary must not claim
        # "it appears in tomorrow's brief" when the operator will see the
        # same comment picked up again (Greptile on PR #1163). Next run the
        # task already exists, so only the receipt is retried.
        echo = _gh([
            "issue", "comment", str(number), "--repo", repo, "--body",
            f"{INGEST_MARKER} ref:{comment.get('id', '')}\n"
            f"🎙️ Understood as task `{task_id}` for the hardening lane: "
            f"“{task['summary']}”. It appears in tomorrow's brief.\n\n---\n"
            "_Generated by [Claude Code](https://claude.ai/code)_",
        ])
        if echo.returncode != 0:
            failed.append(f"{task_id}: task written but receipt post failed")
            continue
        ingested.append(task["summary"])
    return {"ingested": ingested, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loop watcher (read-only)")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--owner-login", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-ingest", action="store_true")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    payload = run_watch(args.repo, report_path)
    result = ({"ingested": [], "failed": []} if args.skip_ingest
              else run_ingest(args.repo, args.owner_login))
    if result is None:
        payload["status"] = "DEGRADED"
        payload["ingest_failed"] = ["enumeration failed"]
        result = {"ingested": [], "failed": []}
    elif result["failed"]:
        payload["status"] = "DEGRADED"
        payload["ingest_failed"] = result["failed"]
    ingested = result["ingested"]
    # The ingested summaries belong IN the report, not only in this job's
    # log: the brief runs as a separate workflow and can only read what was
    # persisted (Codex on PR #1163). Wiring the brief to consume this field
    # touches scripts/runtime/walking_brief.py, outside this packet's
    # allowed_files, and lands as the follow-up PR.
    payload["ingested"] = ingested
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": payload["status"],
                      "watched": payload["watched"],
                      "findings": sum(bool(r["findings"]) for r in payload["reports"]),
                      "ingested": ingested}, indent=2))
    # DEGRADED is a red run on purpose: a silent green with watched: 0 is
    # exactly how a blind watcher looked healthy.
    return 1 if payload["status"] == "DEGRADED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
