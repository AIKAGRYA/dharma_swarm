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
# Only a comment the workflow itself authored may be updated in place. The
# brief runs with GITHUB_TOKEN, so its comments are attributed to the
# Actions bot; a PAT-run variant would appear as the token's owner.
BRIEF_AUTHOR_LOGINS = frozenset({"github-actions[bot]"})

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


# The schedule fires at 21:00 UTC = 06:00 JST, so one walk-day's brief
# straddles the UTC midnight boundary. Bucketing on the raw UTC date would
# give a 21:00 run and a 00:30 rerun different markers, and the next
# morning's run would then edit the previous comment instead of posting
# (Codex review on PR #1166). Shifting by +3h puts the 21:00 UTC schedule
# at the start of its own bucket, which is the operator's walk day.
WALK_DAY_SHIFT_HOURS = 3


def _walk_day(generated_at: str) -> str:
    try:
        moment = datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError):
        return (generated_at or "")[:10]
    return (moment + timedelta(hours=WALK_DAY_SHIFT_HOURS)).strftime("%Y-%m-%d")


def _date_marker(generated_at: str) -> str:
    # Keys one comment per walk day: a rerun updates that day's brief
    # instead of duplicating the phone notification (Codex on PR #1158).
    return f"<!-- walking-brief:date:{_walk_day(generated_at)} -->"
BRIEF_ISSUE_LABEL = "walking-brief"
KILLSWITCH_PATH = "docs/ops/loop_control/KILLSWITCH"
CONTROL_REF = "loop-control"
WORD_BUDGET_NOTE = "Sections are hard-capped; follow links for detail."
MAX_ROWS = 8
MAX_NEEDS_JOHN = 5

AUTOMERGE_WORKFLOW = "automerge.yml"
ROUTER_WORKFLOW = "codex-mention-router.yml"
BACKLOG_WORKFLOW = "merge-master-mike-backlog.yml"
FOUNDRY_WORKFLOW = "foundry-lane.yml"

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _workflow_url(repo: str, workflow: str) -> str:
    """Return a same-repository URL rather than trusting API-supplied URLs."""
    if not _REPO_RE.fullmatch(repo):
        return ""
    return f"https://github.com/{repo}/actions/workflows/{workflow}"


def _pr_url(repo: str, number: object) -> str:
    if not _REPO_RE.fullmatch(repo):
        return ""
    try:
        pr_number = int(number)
    except (TypeError, ValueError):
        return ""
    if pr_number < 1:
        return ""
    return f"https://github.com/{repo}/pull/{pr_number}"


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_label(observed_at: object, generated_at: object) -> str:
    """Describe age relative to the receipt time, never the wall clock.

    `compose_brief` is intentionally deterministic: replaying the same gathered
    receipt later must not silently turn a fresh heartbeat into a stale one.
    """
    observed = _parse_timestamp(observed_at)
    generated = _parse_timestamp(generated_at)
    if observed is None or generated is None:
        return "age unknown"
    seconds = int((generated - observed).total_seconds())
    if seconds < 0:
        return "age unknown (future timestamp)"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


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


def gather_automerge_log(repo: str, generated_at: str | None = None) -> list[dict] | None:
    anchor = _parse_timestamp(generated_at) or datetime.now(timezone.utc)
    since = (anchor - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
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


def gather_workflow_state(repo: str, workflow: str) -> dict:
    """Gather an enablement fact with an explicit true/false/unknown value."""
    data = _gh_json(["api", f"repos/{repo}/actions/workflows/{workflow}"])
    state = str(data.get("state") or "") if isinstance(data, dict) else ""
    if state == "active":
        enabled: bool | None = True
    elif state.startswith("disabled"):
        enabled = False
    else:
        enabled = None
    return {
        "enabled": enabled,
        "state": state or "unknown",
        "url": _workflow_url(repo, workflow),
    }


def _gather_latest_workflow_run(
    repo: str,
    workflow: str,
    *,
    event: str | None = None,
    status: str | None = None,
) -> dict | None:
    query = ["per_page=1"]
    if event:
        query.append(f"event={event}")
    if status:
        query.append(f"status={status}")
    data = _gh_json(
        [
            "api",
            f"repos/{repo}/actions/workflows/{workflow}/runs?{'&'.join(query)}",
        ]
    )
    if not isinstance(data, dict):
        return None
    runs = data.get("workflow_runs")
    if not isinstance(runs, list):
        return None
    if not runs:
        return {"found": False, "url": _workflow_url(repo, workflow)}
    run = runs[0]
    if not isinstance(run, dict):
        return None
    return {
        "found": True,
        "conclusion": run.get("conclusion") or run.get("status") or "unknown",
        "completed_at": run.get("updated_at") or run.get("created_at") or "",
        # A stable workflow URL stays useful even if a run is later deleted,
        # and cannot be redirected by malformed gathered input.
        "url": _workflow_url(repo, workflow),
        "head_sha": run.get("head_sha") or "",
    }


def gather_scanner_heartbeat(repo: str) -> dict | None:
    # This workflow currently emits packets; it is not a merge authority.
    return _gather_latest_workflow_run(repo, BACKLOG_WORKFLOW)


def gather_router_progress(repo: str) -> dict | None:
    # Show the newest explicitly-dispatched activity, including failures. A
    # green workflow is not proof that a gate passed or a merge occurred.
    return _gather_latest_workflow_run(repo, ROUTER_WORKFLOW, event="workflow_dispatch")


def gather_foundry(repo: str) -> dict | None:
    # The Sublimation Foundry lane is report-only; its last run's conclusion is
    # the phone signal. A KILL kill-metric verdict fails the lane on purpose, so
    # red here means "look", not merely "a job errored".
    return _gather_latest_workflow_run(repo, FOUNDRY_WORKFLOW)


def gather(repo: str) -> dict:
    generated_at = _utc_now_iso()
    return {
        "generated_at": generated_at,
        "repo": repo,
        "killswitch": gather_killswitch(repo),
        "walk_ready": gather_walk_ready(repo),
        "automerge_log": gather_automerge_log(repo, generated_at),
        "nightly_main": gather_nightly_main(repo),
        "router_workflow": gather_workflow_state(repo, ROUTER_WORKFLOW),
        "automerge_workflow": gather_workflow_state(repo, AUTOMERGE_WORKFLOW),
        "scanner_heartbeat": gather_scanner_heartbeat(repo),
        "router_progress": gather_router_progress(repo),
        "foundry": gather_foundry(repo),
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


def _safe_action_title(value: object) -> str:
    # A PR title is untrusted. Besides markdown metacharacters, remove raw
    # URLs so each item has exactly one action URL: the canonical repo link.
    without_urls = re.sub(r"https?://\S+", "[external URL removed]", str(value or ""))
    return _md_escape(without_urls[:60])


def derive_needs_john(data: dict) -> tuple[list[str], int]:
    """Build the bounded phone queue, with control-plane failures first."""
    repo = str(data.get("repo") or "")
    items: list[str] = []

    for label, workflow, state in (
        ("Merge router", ROUTER_WORKFLOW, data.get("router_workflow")),
        ("Automerge", AUTOMERGE_WORKFLOW, data.get("automerge_workflow")),
    ):
        state = state if isinstance(state, dict) else {}
        enabled = state.get("enabled")
        url = _workflow_url(repo, workflow)
        if not url:
            continue
        if enabled is False:
            raw_state = _safe_action_title(state.get("state") or "disabled")
            items.append(
                f"- 🔴 [{label}: {raw_state}]({url}) — keep disarmed until the "
                "P0 repair is reviewed; then make the explicit operator decision."
            )
        elif enabled is None:
            items.append(
                f"- 🟠 [{label}: state UNKNOWN]({url}) — API evidence is "
                "unavailable; verify before treating this control as enabled."
            )

    ready = data.get("walk_ready")
    if isinstance(ready, list):
        for pr in ready:
            if not isinstance(pr, dict):
                continue
            url = _pr_url(repo, pr.get("number"))
            if not url:
                continue
            draft = " — draft: flip ready before merging" if pr.get("isDraft") else ""
            items.append(
                f"- 👍 [#{int(pr['number'])} {_safe_action_title(pr.get('title'))}]"
                f"({url}){draft}"
            )

    overflow = max(0, len(items) - MAX_NEEDS_JOHN)
    return items[:MAX_NEEDS_JOHN], overflow


def _workflow_state_line(label: str, state: object) -> str:
    state = state if isinstance(state, dict) else {}
    enabled = state.get("enabled")
    raw = _md_escape(str(state.get("state") or "unknown"))
    if enabled is True:
        return f"🟢 {label}: **enabled** (`{raw}`)"
    if enabled is False:
        return f"🔴 {label}: **DISABLED** (`{raw}`)"
    return f"🟠 {label}: **UNKNOWN** — API evidence unavailable"


def _progress_line(progress: object, generated_at: object) -> str:
    if progress is None:
        return "🟠 Latest router workflow activity: **UNKNOWN** (API query failed)"
    if not isinstance(progress, dict) or progress.get("found") is not True:
        return "🟡 Latest router workflow activity: none found"
    conclusion = str(progress.get("conclusion") or "unknown").lower()
    icon = "🟢" if conclusion == "success" else "🔴"
    return (
        f"{icon} Latest router `workflow_dispatch` activity (not proof of merge): "
        f"`{conclusion}` — "
        f"{_age_label(progress.get('completed_at'), generated_at)} "
        f"(head `{str(progress.get('head_sha') or '?')[:12]}`)"
    )


def _scanner_lines(heartbeat: object, generated_at: object) -> list[str]:
    disclaimer = "**Packet scanner only — this is not merge authority or merge progress.**"
    if heartbeat is None:
        return [disclaimer, "🟠 heartbeat UNKNOWN (API query failed)"]
    if not isinstance(heartbeat, dict) or heartbeat.get("found") is not True:
        return [disclaimer, "🟡 no backlog run found"]
    conclusion = str(heartbeat.get("conclusion") or "unknown").lower()
    icon = "🔴" if conclusion not in {"success", "queued", "in_progress"} else "🔵"
    return [
        disclaimer,
        f"{icon} latest scanner run: `{conclusion}` — "
        f"{_age_label(heartbeat.get('completed_at'), generated_at)}",
    ]


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

    needs_john, needs_overflow = derive_needs_john(data)
    if needs_john:
        needs_rows = list(needs_john)
        if needs_overflow:
            needs_rows.append(
                f"- …and {needs_overflow} additional Needs John item(s) omitted"
            )
    else:
        needs_rows = ["none"]
    out += _section(f"📱 Needs John (max {MAX_NEEDS_JOHN})", needs_rows)

    out += _section(
        "🔐 Merge arm + router activity",
        [
            _workflow_state_line("Router", data.get("router_workflow")),
            _workflow_state_line("Automerge", data.get("automerge_workflow")),
            _progress_line(data.get("router_progress"), data.get("generated_at")),
        ],
    )
    out += _section(
        "🔎 Mike scanner heartbeat",
        _scanner_lines(data.get("scanner_heartbeat"), data.get("generated_at")),
    )

    ready = data.get("walk_ready")
    if ready is None:
        rows = ["_walk-ready query FAILED — state UNKNOWN, check the Actions run_"]
    elif ready:
        repo = str(data.get("repo") or "")
        rows = [
            f"- #{p['number']} [{_safe_action_title(p['title'])}]"
            f"({_pr_url(repo, p['number'])})"
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

    foundry = data.get("foundry")
    if foundry is None or not foundry.get("found"):
        foundry_lines = ["_foundry lane not yet run_"]
    else:
        conclusion = str(foundry.get("conclusion") or "").lower()
        if conclusion == "success":
            icon = "🟢"
        elif conclusion in {"queued", "in_progress", "waiting", "pending", "requested"}:
            icon = "🟡"
        else:
            # A KILL kill-metric verdict fails the lane on purpose — red = look.
            icon = "🔴"
        foundry_lines = [
            f"{icon} lane [{foundry.get('conclusion')}]({foundry.get('url')}) "
            f"at {foundry.get('completed_at')}"
        ]
    foundry_lines.append(
        "Waiting on you (one-time): 4 provider accounts + wedge 'yes' → "
        "docs/foundry/OPERATOR_UNBLOCKS.md"
    )
    out += _section("🏭 Sublimation Foundry", foundry_lines)

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
            "**Pin this issue** if it is not already pinned — the run pins it "
            "automatically, but that best-effort pin can fail on token scope "
            "or the repository's pin limit, and only a pinned thread is one "
            "tap away on a phone (Codex review on PR #1166). "
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
    """Same-day marker comment id, else None. A rerun UPDATES that day's
    brief instead of duplicating the phone notification; if this lookup
    itself fails we fall through to posting — one duplicate beats a silent
    day.

    Every page is searched: this issue is also the operator's input door, so
    a busy day can push the brief past the first 100 comments and a
    single-page lookup would post a duplicate (Greptile on PR #1166). Only a
    comment authored by the workflow identity is eligible — the marker is
    predictable, and a human or bot comment carrying it must never be
    overwritten (Codex on PR #1166)."""
    day = date_marker.rsplit(":", 1)[-1].split(" ")[0]
    # The walk-day bucket starts before its UTC date, so widen the window a
    # day and let the marker itself do the exact matching.
    since = (
        datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        - timedelta(days=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list = []
    page = 1
    while True:
        data = _gh_json(
            [
                "api",
                f"repos/{repo}/issues/{issue_number}/comments"
                f"?since={since}&per_page=100&page={page}",
            ]
        )
        if not isinstance(data, list):
            return None
        rows.extend(data)
        if len(data) < 100:
            break
        page += 1
    for row in reversed(rows):
        if str((row.get("user") or {}).get("login") or "") not in BRIEF_AUTHOR_LOGINS:
            continue
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
