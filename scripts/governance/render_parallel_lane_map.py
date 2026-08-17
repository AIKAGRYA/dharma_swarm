#!/usr/bin/env python3
"""Render the non-destructive parallel lane map for dharma_swarm.

The active track owns strategic intent. This report owns a snapshot of the
operational highway: local worktrees, branches, open PRs, recent commits, and
dirty pressure. It never prunes, deletes, checks out, resets, or closes
anything. Cleanup candidates are review queues, not actions.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports/governance"
REPORT_JSON = REPORT_DIR / "parallel_lane_map.json"
REPORT_MD = REPORT_DIR / "parallel_lane_map.md"


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    ok: bool
    error: str = ""


def run_cmd(args: list[str], *, cwd: Path = REPO_ROOT, timeout: int = 30) -> CommandResult:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult("", False, type(exc).__name__)
    return CommandResult(result.stdout.rstrip(), result.returncode == 0, result.stderr.strip())


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_worktree_porcelain(text: str) -> list[dict[str, Any]]:
    worktrees: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            current.setdefault("branch", None)
            current.setdefault("head", None)
            current.setdefault("detached", False)
            current.setdefault("prunable", False)
            current.setdefault("prunable_reason", "")
            worktrees.append(current)
        current = None

    for raw in [*text.splitlines(), ""]:
        line = raw.rstrip()
        if not line:
            flush()
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            flush()
            current = {"path": value}
        elif current is None:
            continue
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key == "detached":
            current["detached"] = True
        elif key == "prunable":
            current["prunable"] = True
            current["prunable_reason"] = value
    return worktrees


def parse_branch_refs(text: str) -> list[dict[str, str]]:
    branches: list[dict[str, str]] = []
    for line in text.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        committed_at, name, sha, subject = parts
        branches.append(
            {
                "committed_at": committed_at,
                "name": name,
                "sha": sha,
                "subject": subject,
            }
        )
    return branches


def parse_recent_commits(text: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for line in text.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        sha, committed_at, author, subject = parts
        commits.append(
            {
                "sha": sha,
                "committed_at": committed_at,
                "author": author,
                "subject": subject,
                "lane": classify_lane(subject),
            }
        )
    return commits


def dirty_category(path: str) -> str:
    if path.startswith("docs/governance/") or path in {"CLAUDE.md", "ACTIVE_SURFACE_MANIFEST.yaml"}:
        return "governance_docs"
    if path.startswith("reports/governance/"):
        return "governance_reports"
    if path.startswith("scripts/governance/"):
        return "governance_scripts"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith("reports/agentops/work_packets/"):
        return "agentops_work_packets"
    if path.startswith("reports/forge/") or path.startswith("docs/specs/forge_packets/"):
        return "forge_measurement"
    if path.startswith("dharma_swarm/capital_lab/") or path.startswith("reports/capital_lab/"):
        return "capital_lab"
    if path.startswith("scripts/runtime/"):
        return "runtime_scripts"
    if path.startswith("docs/research/"):
        return "research_docs"
    return path.split("/", 1)[0] if "/" in path else "repo_root"


def parse_dirty_status(text: str) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    categories: Counter[str] = Counter()
    states: Counter[str] = Counter()
    for line in text.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        category = dirty_category(path)
        items.append({"status": status, "path": path, "category": category})
        categories[category] += 1
        if status == "??":
            states["untracked"] += 1
        elif status[0] != " " and status[1] != " ":
            states["staged_and_unstaged"] += 1
        elif status[0] != " ":
            states["staged"] += 1
        else:
            states["unstaged"] += 1
    return {
        "count": len(items),
        "states": dict(states),
        "categories": dict(categories.most_common()),
        "items_sample": items[:40],
    }


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", title.lower()).strip()
    cleaned = re.sub(r"\b20\d{6,}\b", "DATE", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def classify_lane(value: str | None) -> str:
    text = (value or "").lower()
    if "runtime-truth" in text or "runtime truth" in text or "nats" in text:
        return "runtime-truth-spine"
    if "spine-adoption" in text or "spine adoption" in text or "go-ingest" in text:
        return "spine-adoption"
    if "lak-e2e" in text or "living agent kernel" in text or "metabolism" in text:
        return "living-agent-kernel"
    if "parallel-lane" in text or "active_track" in text or "governance" in text:
        return "governance"
    if text.startswith("rss/") or "fu-" in text:
        return "rss-followups"
    if text.startswith("pr-") or "repair/pr-" in text or "backlog" in text:
        return "pr-repair-backlog"
    if "merge-master" in text or text.startswith("mmm-") or "mike" in text:
        return "merge-master-mike"
    if "live-ops" in text or "cockpit" in text:
        return "live-ops-cockpit"
    if text.startswith(("cleanup/", "review/", "backup/", "archive/")) or "cleanup_worktrees" in text:
        return "parked-cleanup"
    if "forge" in text or "arena" in text or "measurement" in text:
        return "forge-measurement"
    if "capital_lab" in text or "capital lab" in text:
        return "capital-lab"
    if "research/" in text or "docs(research)" in text or "palantir" in text:
        return "research"
    return "unclassified"


def load_open_prs(*, skip_github: bool) -> tuple[list[dict[str, Any]], list[str]]:
    if skip_github:
        return [], ["github_pr_scan_skipped"]
    result = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            "AIKAGRYA/dharma_swarm",
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,headRefName,baseRefName,author,createdAt,updatedAt,isDraft,mergeStateStatus,url,statusCheckRollup",
        ],
        timeout=45,
    )
    if not result.ok:
        return [], [f"github_pr_scan_failed:{result.error or 'unknown'}"]
    try:
        raw = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return [], ["github_pr_scan_failed:json_decode"]

    prs: list[dict[str, Any]] = []
    for pr in raw:
        checks = pr.get("statusCheckRollup") or []
        conclusions = Counter(
            str(check.get("conclusion") or check.get("status") or "UNKNOWN")
            for check in checks
            if isinstance(check, dict)
        )
        title = str(pr.get("title") or "")
        head = str(pr.get("headRefName") or "")
        prs.append(
            {
                "number": pr.get("number"),
                "title": title,
                "url": pr.get("url"),
                "head": head,
                "base": pr.get("baseRefName"),
                "author": (pr.get("author") or {}).get("login"),
                "is_draft": bool(pr.get("isDraft")),
                "merge_state": pr.get("mergeStateStatus"),
                "updated_at": pr.get("updatedAt"),
                "lane": classify_lane(f"{head} {title}"),
                "check_summary": dict(conclusions),
            }
        )
    return prs, []


def branch_age_days(committed_at: str, *, today: date) -> int | None:
    try:
        when = date.fromisoformat(committed_at)
    except ValueError:
        return None
    return (today - when).days


def build_lane_map(*, skip_github: bool = False, max_branches: int = 200) -> dict[str, Any]:
    today = datetime.now(tz=timezone.utc).date()
    active_branch = run_cmd(["git", "branch", "--show-current"]).stdout or "(detached)"
    head = run_cmd(["git", "rev-parse", "--short=10", "HEAD"]).stdout

    worktrees = parse_worktree_porcelain(run_cmd(["git", "worktree", "list", "--porcelain"], timeout=45).stdout)
    branch_refs = parse_branch_refs(
        run_cmd(
            [
                "git",
                "for-each-ref",
                "refs/heads",
                "--sort=-committerdate",
                "--format=%(committerdate:short)%09%(refname:short)%09%(objectname:short)%09%(subject)",
                f"--count={max_branches}",
            ],
            timeout=45,
        ).stdout
    )
    branch_by_name = {branch["name"]: branch for branch in branch_refs}
    dirty = parse_dirty_status(run_cmd(["git", "status", "--porcelain=v1"], timeout=30).stdout)
    prs, warnings = load_open_prs(skip_github=skip_github)
    pr_heads = {str(pr["head"]) for pr in prs}

    recent_commits = parse_recent_commits(
        run_cmd(
            [
                "git",
                "log",
                "--since=14 days ago",
                "--date=short",
                "--pretty=format:%h%x09%ad%x09%an%x09%s",
                "--no-merges",
                "--all",
                "--max-count=160",
            ],
            timeout=45,
        ).stdout
    )

    lane_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"worktrees": 0, "branches": 0, "open_prs": 0, "recent_commits": 0}
    )
    cleanup_candidates: list[dict[str, Any]] = []

    enriched_worktrees: list[dict[str, Any]] = []
    for wt in worktrees:
        branch = wt.get("branch")
        lane = classify_lane(f"{branch or ''} {wt.get('path') or ''}")
        ref = branch_by_name.get(branch or "", {})
        age = branch_age_days(str(ref.get("committed_at") or ""), today=today) if ref else None
        state = "current" if Path(str(wt.get("path"))).resolve() == REPO_ROOT.resolve() else "worktree"
        if wt.get("detached"):
            state = "detached"
        elif wt.get("prunable"):
            state = "prunable"
        elif branch in pr_heads:
            state = "open_pr"
        elif age is not None and age > 21:
            state = "stale_review"
        row = {
            **wt,
            "lane": lane,
            "state": state,
            "committed_at": ref.get("committed_at"),
            "subject": ref.get("subject"),
            "age_days": age,
        }
        enriched_worktrees.append(row)
        lane_groups[lane]["worktrees"] += 1
        if state in {"detached", "prunable", "stale_review"}:
            cleanup_candidates.append(
                {
                    "kind": "worktree",
                    "path": wt.get("path"),
                    "branch": branch,
                    "reason": state,
                    "review_only": True,
                }
            )

    for branch in branch_refs:
        lane = classify_lane(f"{branch['name']} {branch['subject']}")
        lane_groups[lane]["branches"] += 1
        age = branch_age_days(branch["committed_at"], today=today)
        branch["lane"] = lane
        branch["age_days"] = age
        if (
            age is not None
            and age > 21
            and branch["name"] not in pr_heads
            and branch["name"].startswith(("cleanup/", "review/", "backup/", "archive/", "repair/"))
        ):
            cleanup_candidates.append(
                {
                    "kind": "branch",
                    "branch": branch["name"],
                    "reason": f"{age}d old, no open PR head",
                    "review_only": True,
                }
            )

    for pr in prs:
        lane_groups[pr["lane"]]["open_prs"] += 1

    for commit in recent_commits:
        lane_groups[commit["lane"]]["recent_commits"] += 1

    title_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pr in prs:
        title_groups[normalize_title(str(pr["title"]))].append(pr)
    for title, group in title_groups.items():
        if len(group) > 1:
            cleanup_candidates.append(
                {
                    "kind": "duplicate_pr_intent",
                    "title_key": title,
                    "prs": [pr["number"] for pr in group],
                    "reason": "multiple open PRs normalize to same title",
                    "review_only": True,
                }
            )

    if dirty["categories"].get("agentops_work_packets", 0) > 20:
        cleanup_candidates.append(
            {
                "kind": "dirty_pressure",
                "category": "agentops_work_packets",
                "count": dirty["categories"]["agentops_work_packets"],
                "reason": "large untracked receipt/work-packet backlog needs lane ownership or archival",
                "review_only": True,
            }
        )

    summary = {
        "active_branch": active_branch,
        "head": head,
        "worktree_count": len(worktrees),
        "branch_count_sampled": len(branch_refs),
        "open_pr_count": len(prs),
        "dirty_count_current_worktree": dirty["count"],
        "cleanup_candidate_count": len(cleanup_candidates),
        "lane_count": len(lane_groups),
    }

    return {
        "schema": "dharma.parallel_lane_map.v1",
        "generated_at": now_iso(),
        "doctrine": {
            "model": "one strategic active track; many coordinated work lanes",
            "active_track_role": "north-star, acceptance gates, non-goals, authority boundaries",
            "lane_rule": "parallel work is allowed only when owned, scoped, isolated, verified, and receipted",
            "cleanup_rule": "never delete branches/worktrees from this report without receipt review and explicit operator approval",
        },
        "summary": summary,
        "warnings": warnings,
        "dirty_current_worktree": dirty,
        "lanes": dict(sorted(lane_groups.items())),
        "open_prs": prs,
        "worktrees": enriched_worktrees,
        "recent_branches": branch_refs,
        "recent_commits": recent_commits,
        "cleanup_candidates": cleanup_candidates[:120],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Parallel Lane Map",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "This is a non-destructive operating snapshot. It is not approval to prune, close, merge, or reset anything.",
        "",
        "## Doctrine",
        "",
        f"- Model: {payload['doctrine']['model']}",
        f"- Active track role: {payload['doctrine']['active_track_role']}",
        f"- Lane rule: {payload['doctrine']['lane_rule']}",
        f"- Cleanup rule: {payload['doctrine']['cleanup_rule']}",
        "",
        "## Summary",
        "",
        f"- Active branch: `{summary['active_branch']}` at `{summary['head']}`",
        f"- Worktrees: {summary['worktree_count']}",
        f"- Branches sampled: {summary['branch_count_sampled']}",
        f"- Open PRs: {summary['open_pr_count']}",
        f"- Dirty entries in current worktree: {summary['dirty_count_current_worktree']}",
        f"- Cleanup candidates for review: {summary['cleanup_candidate_count']}",
        "",
        "## Lane Groups",
        "",
        "| Lane | Worktrees | Branches | Open PRs | Recent commits |",
        "|---|---:|---:|---:|---:|",
    ]
    for lane, counts in payload["lanes"].items():
        lines.append(
            f"| `{lane}` | {counts['worktrees']} | {counts['branches']} | "
            f"{counts['open_prs']} | {counts['recent_commits']} |"
        )

    lines.extend(["", "## Open PRs", ""])
    if payload["open_prs"]:
        lines.extend(["| PR | Lane | State | Head | Title |", "|---:|---|---|---|---|"])
        for pr in payload["open_prs"]:
            state = "draft" if pr["is_draft"] else str(pr.get("merge_state") or "")
            lines.append(
                f"| [#{pr['number']}]({pr['url']}) | `{pr['lane']}` | {state} | "
                f"`{pr['head']}` | {pr['title']} |"
            )
    else:
        lines.append("(No open PRs found, or GitHub scan skipped/failed.)")

    lines.extend(["", "## Current Worktree Dirty Pressure", ""])
    dirty = payload["dirty_current_worktree"]
    lines.append(f"Total dirty entries: {dirty['count']}")
    if dirty["categories"]:
        lines.extend(["", "| Category | Count |", "|---|---:|"])
        for category, count in dirty["categories"].items():
            lines.append(f"| `{category}` | {count} |")

    lines.extend(["", "## Cleanup Candidates For Review", ""])
    if payload["cleanup_candidates"]:
        for item in payload["cleanup_candidates"][:40]:
            label = item.get("branch") or item.get("path") or item.get("title_key") or item.get("category")
            lines.append(f"- `{item['kind']}` `{label}`: {item.get('reason')}")
        if len(payload["cleanup_candidates"]) > 40:
            lines.append(f"- ... {len(payload['cleanup_candidates']) - 40} more in JSON")
    else:
        lines.append("(No cleanup candidates detected.)")

    lines.extend(["", "## Recent Commits", ""])
    for commit in payload["recent_commits"][:30]:
        lines.append(
            f"- `{commit['sha']}` {commit['committed_at']} `{commit['lane']}` "
            f"{commit['subject']} ({commit['author']})"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON payload to stdout.")
    parser.add_argument("--skip-github", action="store_true", help="Skip gh PR lookup.")
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--max-branches", type=int, default=200)
    args = parser.parse_args()

    payload = build_lane_map(skip_github=args.skip_github, max_branches=args.max_branches)
    out_json = args.output_dir / "parallel_lane_map.json"
    out_md = args.output_dir / "parallel_lane_map.md"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"wrote {out_json}")
        print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
