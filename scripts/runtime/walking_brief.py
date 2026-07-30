#!/usr/bin/env python3
"""Walking-mode Operator Brief — composed for a phone, delivered via GitHub.

PR-C of the walking-mode loop-closure plan
(docs/plans/GRAPH_OF_LOOPS_DESIGN_2026-07-29.md; operator ruling 2026-07-29,
DOOR = AUTO_WITH_DECORRELATED_REVIEW).

Why this exists instead of the ontology-native operator_brief package:
`dharma_swarm/operator_brief/` composes from `~/.dharma` runtime state and
writes markdown to `~/.dharma/artifacts/` (persistence.py:116-124) — state
that does not exist in a stateless CI runner — and its cron job is disabled
(`cron_jobs.json` `operator_brief.enabled: false`) behind an env flag that
is set nowhere. The `deliver:` routing contract in cron_scheduler.py:9,238
is documented but read by no dispatcher. This module therefore BYPASSES
that seam (it does not repair it): it gathers only GitHub-visible truth via
the `gh` CLI and posts one comment per day to the pinned walking-brief
issue — the only channel that reaches the operator's phone today.

Composition is a pure function over a gathered-data dict so tests never
need network. Every section whose producer has not landed yet says so
explicitly instead of rendering an empty table as false calm.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

BRIEF_MARKER = "<!-- walking-brief:v1 -->"

# Same absent-switch contract as the workflow guards
# (docs/ops/loop_control/README.md): 404 on the file OR on the branch — a
# repo where loop-control has never been created answers "No commit found
# for the ref loop-control" (Codex review on PR #1158).
_KILLSWITCH_ABSENT_RE = re.compile(
    r'HTTP 404|"status": *"404"|Not Found|No commit found', re.IGNORECASE
)

# Markdown metacharacters in externally-authored text (PR titles): a title
# like 'x](https://attacker.example)' must not rewrite links in the trusted
# brief (Codex review on PR #1158).
_MD_ESCAPE_RE = re.compile(r"([\\\[\]`*_<>])")


def _md_escape(text: str) -> str:
    return _MD_ESCAPE_RE.sub(r"\\\1", text)


def _date_marker(generated_at: str) -> str:
    # Keys one comment per day: a rerun updates today's brief instead of
    # duplicating the phone notification (Codex review on PR #1158).
    return f"<!-- walking-brief:date:{(generated_at or '')[:10]} -->"
BRIEF_ISSUE_LABEL = "walking-brief"
KILLSWITCH_PATH = "docs/ops/loop_control/KILLSWITCH"
CONTROL_REF = "loop-control"
WORD_BUDGET_NOTE = "Sections are hard-capped; follow links for detail."
MAX_ROWS = 8


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=timeout, check=False
    )


def _gh_json(args: list[str]) -> object | None:
    result = _gh(args)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- gathering


def gather_killswitch(repo: str) -> dict:
    result = _gh(["api", f"repos/{repo}/contents/{KILLSWITCH_PATH}?ref={CONTROL_REF}"])
    if result.returncode == 0:
        return {"engaged": True, "detail": "KILLSWITCH present on loop-control"}
    if _KILLSWITCH_ABSENT_RE.search(result.stdout + result.stderr):
        return {"engaged": False, "detail": ""}
    return {"engaged": None, "detail": "state UNKNOWN (API error) — treat as engaged"}


def gather_walk_ready(repo: str) -> list[dict] | None:
    data = _gh_json(
        [
            "pr", "list", "--repo", repo, "--state", "open",
            "--label", "walk-ready", "--json",
            "number,title,isDraft,url,labels", "--limit", "20",
        ]
    )
    # None on failure: an unavailable query must never render as the calm
    # "nothing awaiting you" (Codex + Greptile reviews on PR #1158).
    return data if isinstance(data, list) else None


def gather_automerge_log(repo: str) -> list[dict] | None:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    rows: list[dict] = []
    for label in ("automerge", "bot-pr"):
        data = _gh_json(
            [
                "pr", "list", "--repo", repo, "--state", "merged",
                "--label", label, "--search", f"merged:>={since}",
                "--json", "number,title,url,mergedAt", "--limit", "20",
            ]
        )
        if not isinstance(data, list):
            # Fail closed on ANY partial query: an incomplete revert audit
            # silently omitting automerges is worse than an explicit unknown
            # (Codex + Devin + Greptile reviews on PR #1158).
            return None
        rows.extend(data)
    # Newest first: the brief truncates this list, and the most recent
    # automerges are the ones most likely to need a one-tap revert
    # (Devin review on PR #1158).
    seen: set[int] = set()
    unique = []
    for row in sorted(rows, key=lambda r: r.get("mergedAt", ""), reverse=True):
        if row.get("number") not in seen:
            seen.add(row.get("number"))
            unique.append(row)
    return unique


def gather_nightly_main(repo: str) -> dict | None:
    data = _gh_json(
        [
            "api",
            f"repos/{repo}/actions/workflows/nightly-tests.yml/runs"
            "?branch=main&per_page=1",
        ]
    )
    runs = (data or {}).get("workflow_runs") if isinstance(data, dict) else None
    if not runs:
        return None
    run = runs[0]
    return {
        "conclusion": run.get("conclusion") or run.get("status"),
        "url": run.get("html_url", ""),
        "completed_at": run.get("updated_at", ""),
    }


def gather(repo: str) -> dict:
    return {
        "generated_at": _utc_now_iso(),
        "repo": repo,
        "killswitch": gather_killswitch(repo),
        "walk_ready": gather_walk_ready(repo),
        "automerge_log": gather_automerge_log(repo),
        "nightly_main": gather_nightly_main(repo),
        # Producers that land in later workstreams; compose_brief renders an
        # explicit not-landed line for each None/missing key.
        "lane_runs": None,        # PR-E hardening lane receipts
        "disagreements": None,    # PR-A decorrelated-review disagreement log
        "canary": None,           # PR-F weekly canary results
        "ingested": None,         # PR-F operator-comment ingestion echo
    }


# ---------------------------------------------------------------- composing


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"### {title}", *lines, ""]


def _not_landed(producer: str) -> list[str]:
    return [f"_no producer landed yet ({producer})_"]


def compose_brief(data: dict) -> str:
    out: list[str] = [
        BRIEF_MARKER,
        _date_marker(data.get("generated_at", "")),
        f"## 🥾 Walking Brief — {data.get('generated_at', '?')}",
        "",
    ]

    ks = data.get("killswitch") or {}
    if ks.get("engaged") is True:
        out += _section("🔴 KILLSWITCH", ["**ENGAGED** — all lanes halted. "
                                          "Resume: Actions → loop-resume."])
    elif ks.get("engaged") is None:
        out += _section("🟠 KILLSWITCH", [f"**{ks.get('detail', 'state unknown')}**"])
    else:
        out += _section("🟢 KILLSWITCH", ["not engaged"])

    ready = data.get("walk_ready")
    if ready is None:
        rows = ["_walk-ready query FAILED — state UNKNOWN, check the Actions run_"]
    elif ready:
        rows = [
            f"- #{p['number']} [{_md_escape(p['title'][:60])}]({p['url']})"
            + (" *(draft — flip ready, then merge)*" if p.get("isDraft") else "")
            for p in ready[:MAX_ROWS]
        ]
        if len(ready) > MAX_ROWS:
            rows.append(f"- …and {len(ready) - MAX_ROWS} more")
    else:
        rows = ["nothing awaiting you"]
    out += _section("👍 Merge window (walk-ready)", rows)

    merged = data.get("automerge_log")
    if merged is None:
        out += _section(
            "🤖 Automerges (24h)",
            ["_automerge-log query FAILED — state UNKNOWN, check the Actions run_"],
        )
    elif merged:
        merged_rows = [
            f"- #{p['number']} [{_md_escape(p['title'][:60])}]({p['url']}) "
            f"at {p.get('mergedAt', '?')}"
            for p in merged[:MAX_ROWS]
        ]
        if len(merged) > MAX_ROWS:
            merged_rows.append(f"- …and {len(merged) - MAX_ROWS} more")
        out += _section(
            "🤖 Automerges (24h, newest first) — tap PR → Revert to undo",
            merged_rows,
        )
    else:
        out += _section("🤖 Automerges (24h)", ["none"])

    night = data.get("nightly_main")
    if night is None:
        out += _section("🌙 Nightly main", ["no run found"])
    else:
        conclusion = str(night.get("conclusion") or "").lower()
        if conclusion == "success":
            icon = "🟢"
        elif conclusion in {"queued", "in_progress", "waiting", "pending", "requested"}:
            # Nonterminal statuses are pending, not failures — red is
            # reserved for a finished unsuccessful run (Greptile on #1158).
            icon = "🟡"
        else:
            icon = "🔴"
        out += _section(
            "🌙 Nightly main",
            [f"{icon} [{night.get('conclusion')}]({night.get('url')}) "
             f"at {night.get('completed_at')}"],
        )

    for key, title, producer in (
        ("lane_runs", "🔁 Lane runs + receipts", "hardening lane, PR-E"),
        ("disagreements", "⚖️ Review disagreements", "decorrelated review, PR-A"),
        ("canary", "🐤 Canary results", "watcher canary duty, PR-F"),
        ("ingested", "🎙️ Ingested from your comments", "ingestion, PR-F"),
    ):
        value = data.get(key)
        if value is None:
            out += _section(title, _not_landed(producer))
        elif isinstance(value, list) and value:
            out += _section(title, [f"- {item}" for item in value[:MAX_ROWS]])
        elif isinstance(value, dict) and value:
            out += _section(title, [f"- {k}: {v}" for k, v in list(value.items())[:MAX_ROWS]])
        else:
            out += _section(title, ["none"])

    out += [f"_{WORD_BUDGET_NOTE}_", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- delivery


def _pin_issue(repo: str, issue_number: int) -> bool:
    """Best-effort GraphQL pin: the bootstrap thread should reach the phone
    pinned, not merely ask to be pinned (Codex review on PR #1158)."""
    node = _gh_json(["api", f"repos/{repo}/issues/{issue_number}"])
    node_id = node.get("node_id") if isinstance(node, dict) else None
    if not node_id:
        return False
    result = _gh(
        [
            "api", "graphql",
            "-f",
            "query=mutation($id: ID!) "
            "{ pinIssue(input: {issueId: $id}) { issue { number } } }",
            "-f", f"id={node_id}",
        ]
    )
    return result.returncode == 0


def find_or_create_brief_issue(repo: str) -> int | None:
    data = _gh_json(
        [
            "issue", "list", "--repo", repo, "--state", "open",
            "--label", BRIEF_ISSUE_LABEL, "--json", "number", "--limit", "1",
        ]
    )
    if data is None:
        # Lookup FAILED (distinct from "no issue exists"): creating here
        # would fork a duplicate, unpinned thread the phone never sees
        # (Devin + Greptile reviews on PR #1158).
        print(
            "walking-brief: issue lookup failed — refusing to create a duplicate",
            file=sys.stderr,
        )
        return None
    if isinstance(data, list) and data:
        return int(data[0]["number"])
    _gh(
        [
            "label", "create", BRIEF_ISSUE_LABEL, "--repo", repo,
            "--color", "0E8A16",
            "--description", "Pinned walking-mode operator brief thread",
        ]
    )
    result = _gh(
        [
            "issue", "create", "--repo", repo,
            "--title", "Walking Ops — Daily Brief",
            "--label", BRIEF_ISSUE_LABEL,
            "--body",
            "Daily walking-mode brief lands here as comments. "
            "Reply with a dictated comment — that reply is the sole input door "
            "(ingestion lands with PR-F).",
        ]
    )
    if result.returncode != 0:
        return None
    try:
        issue_number = int(result.stdout.strip().rstrip("/").rsplit("/", 1)[-1])
    except ValueError:
        return None
    if not _pin_issue(repo, issue_number):
        print(
            f"walking-brief: could not pin issue #{issue_number} — pin it manually",
            file=sys.stderr,
        )
    return issue_number


def find_todays_brief_comment(repo: str, issue_number: int, date_marker: str) -> int | None:
    """Same-day marker comment id, else None. A rerun UPDATES today's brief
    instead of duplicating the phone notification; if this lookup itself
    fails we fall through to posting — one duplicate beats a silent day."""
    day = date_marker.rsplit(":", 1)[-1].split(" ")[0]
    data = _gh_json(
        [
            "api",
            f"repos/{repo}/issues/{issue_number}/comments"
            f"?since={day}T00:00:00Z&per_page=100",
        ]
    )
    if not isinstance(data, list):
        return None
    for row in reversed(data):
        if date_marker in str(row.get("body") or ""):
            ident = row.get("id")
            return int(ident) if ident is not None else None
    return None


def update_brief_comment(repo: str, comment_id: int, body: str) -> bool:
    result = _gh(
        [
            "api", "-X", "PATCH",
            f"repos/{repo}/issues/comments/{comment_id}",
            "-f", f"body={body}",
        ]
    )
    return result.returncode == 0


def post_brief(repo: str, issue_number: int, body: str) -> bool:
    result = _gh(
        ["issue", "comment", str(issue_number), "--repo", repo, "--body", body]
    )
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--post", action="store_true",
                        help="post to the pinned walking-brief issue")
    parser.add_argument("--output", default="", help="also write markdown here")
    args = parser.parse_args(argv)

    data = gather(args.repo)
    body = compose_brief(data)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(body)
    if args.post:
        issue = find_or_create_brief_issue(args.repo)
        if issue is None:
            print("walking-brief: could not find or create the brief issue", file=sys.stderr)
            return 2
        marker = _date_marker(data.get("generated_at", ""))
        existing = find_todays_brief_comment(args.repo, issue, marker)
        if existing is not None:
            if not update_brief_comment(args.repo, existing, body):
                print("walking-brief: failed to update today's brief comment",
                      file=sys.stderr)
                return 2
            print(f"walking-brief: updated today's brief on issue #{issue}")
        else:
            if not post_brief(args.repo, issue, body):
                print("walking-brief: failed to post the brief comment", file=sys.stderr)
                return 2
            print(f"walking-brief: posted to issue #{issue}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
