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
import subprocess
import sys
from datetime import datetime, timedelta, timezone

BRIEF_MARKER = "<!-- walking-brief:v1 -->"
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
    if "Not Found" in (result.stdout + result.stderr):
        return {"engaged": False, "detail": ""}
    return {"engaged": None, "detail": "state UNKNOWN (API error) — treat as engaged"}


def gather_walk_ready(repo: str) -> list[dict]:
    data = _gh_json(
        [
            "pr", "list", "--repo", repo, "--state", "open",
            "--label", "walk-ready", "--json",
            "number,title,isDraft,url,labels", "--limit", "20",
        ]
    )
    return data if isinstance(data, list) else []


def gather_automerge_log(repo: str) -> list[dict]:
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
        if isinstance(data, list):
            rows.extend(data)
    seen: set[int] = set()
    unique = []
    for row in sorted(rows, key=lambda r: r.get("mergedAt", "")):
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

    ready = data.get("walk_ready") or []
    if ready:
        rows = [
            f"- #{p['number']} [{p['title'][:60]}]({p['url']})"
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
        out += _section("🤖 Automerges (24h)", _not_landed("query failed"))
    elif merged:
        out += _section(
            "🤖 Automerges (24h) — tap PR → Revert to undo",
            [
                f"- #{p['number']} [{p['title'][:60]}]({p['url']}) at {p.get('mergedAt', '?')}"
                for p in merged[:MAX_ROWS]
            ],
        )
    else:
        out += _section("🤖 Automerges (24h)", ["none"])

    night = data.get("nightly_main")
    if night is None:
        out += _section("🌙 Nightly main", ["no run found"])
    else:
        icon = "🟢" if night.get("conclusion") == "success" else "🔴"
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


def find_or_create_brief_issue(repo: str) -> int | None:
    data = _gh_json(
        [
            "issue", "list", "--repo", repo, "--state", "open",
            "--label", BRIEF_ISSUE_LABEL, "--json", "number", "--limit", "1",
        ]
    )
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
            "Daily walking-mode brief lands here as comments. Pin this issue. "
            "Reply with a dictated comment — that reply is the sole input door "
            "(ingestion lands with PR-F).",
        ]
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip().rstrip("/").rsplit("/", 1)[-1])
    except ValueError:
        return None


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
        if not post_brief(args.repo, issue, body):
            print("walking-brief: failed to post the brief comment", file=sys.stderr)
            return 2
        print(f"walking-brief: posted to issue #{issue}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
