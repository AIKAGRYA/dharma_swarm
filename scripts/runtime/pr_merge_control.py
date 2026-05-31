#!/usr/bin/env python3
"""Governed PR queue, dual-agent review packets, and merge gates.

This script is intentionally local-first. It uses `gh` for live GitHub state,
writes receipts under ~/.dharma/pr_review by default, and never merges unless
an operator passes an explicit confirmation token.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = Path("~/.dharma/pr_review")
REQUIRED_COHERENCE_FIELDS = (
    "Organ touched",
    "Declared-vs-actual gap closed",
    "Proof that re-reads the map",
    "New drift introduced",
)
BAD_CONCLUSIONS = {
    "ACTION_REQUIRED",
    "CANCELLED",
    "FAILURE",
    "STALE",
    "STARTUP_FAILURE",
    "TIMED_OUT",
}
PASS_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
HOT_PATH_PATTERNS = (
    ".github/",
    "api/",
    "dashboard/",
    "dharma_swarm/dharma_kernel.py",
    "dharma_swarm/telos_gates.py",
    "dharma_swarm/orchestrator.py",
    "dharma_swarm/swarm.py",
    "dharma_swarm/signal_bus.py",
    "dharma_swarm/vsm_channels.py",
    "dharma_swarm/runtime_state.py",
    "dharma_swarm/operator_core/",
    "scripts/governance/",
    "scripts/runtime/",
    "Makefile",
)
CLAUDE_REVIEW_DEFAULT_BIN = Path("/Users/dhyana/.npm-global/bin/claude")


class PRControlError(Exception):
    """Raised when PR control cannot safely proceed."""


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, timeout: int = 120, check: bool = True) -> CommandResult:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    result = CommandResult(proc.returncode, proc.stdout, proc.stderr)
    if check and result.code != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PRControlError(f"{' '.join(cmd)} failed: {detail}")
    return result


def gh_json(args: list[str], *, timeout: int = 120) -> Any:
    result = run(["gh", *args], timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PRControlError(f"gh returned non-JSON output for {' '.join(args)}") from exc


def repo_name() -> str:
    result = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], timeout=30)
    name = result.stdout.strip()
    if not name or "/" not in name:
        raise PRControlError("could not determine GitHub repository name")
    return name


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_rollup(pr: dict[str, Any]) -> dict[str, Any]:
    rollup = pr.get("statusCheckRollup") or []
    failing: list[str] = []
    pending: list[str] = []
    passing: list[str] = []
    unknown: list[str] = []

    if not rollup:
        unknown.append("no status checks reported")

    for item in rollup:
        name = str(item.get("name") or item.get("context") or item.get("workflowName") or "unnamed")
        conclusion = str(item.get("conclusion") or "").upper()
        status = str(item.get("status") or "").upper()
        if conclusion in BAD_CONCLUSIONS:
            failing.append(name)
        elif status and status != "COMPLETED":
            pending.append(name)
        elif conclusion in PASS_CONCLUSIONS:
            passing.append(name)
        elif conclusion:
            failing.append(f"{name}:{conclusion}")
        else:
            unknown.append(name)

    return {
        "total": len(rollup),
        "passing": passing,
        "failing": failing,
        "pending": pending,
        "unknown": unknown,
    }


def classify_pr(pr: dict[str, Any]) -> dict[str, Any]:
    checks = check_rollup(pr)
    mergeable = str(pr.get("mergeable") or "UNKNOWN").upper()
    review_decision = str(pr.get("reviewDecision") or "").upper()
    reasons: list[str] = []

    if pr.get("isDraft"):
        reasons.append("draft")
        status = "DRAFT"
    elif mergeable == "CONFLICTING":
        reasons.append("merge conflict")
        status = "BLOCKED_CONFLICT"
    elif checks["failing"]:
        reasons.append(f"{len(checks['failing'])} failing checks")
        status = "BLOCKED_CHECKS"
    elif checks["unknown"]:
        reasons.append(f"{len(checks['unknown'])} unknown check states")
        status = "BLOCKED_CHECKS"
    elif review_decision == "CHANGES_REQUESTED":
        reasons.append("changes requested")
        status = "BLOCKED_REVIEW"
    elif checks["pending"]:
        reasons.append(f"{len(checks['pending'])} pending checks")
        status = "WAITING_CHECKS"
    elif mergeable != "MERGEABLE":
        reasons.append(f"mergeable={mergeable}")
        status = "NEEDS_REFRESH"
    elif review_decision not in {"APPROVED", ""}:
        reasons.append(f"reviewDecision={review_decision}")
        status = "NEEDS_AGENT_REVIEW"
    else:
        reasons.append("GitHub green; packet, dual review, and merge gate still required")
        status = "GITHUB_GREEN_NEEDS_PACKET"

    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "author": (pr.get("author") or {}).get("login") if isinstance(pr.get("author"), dict) else pr.get("author"),
        "headRefName": pr.get("headRefName"),
        "baseRefName": pr.get("baseRefName"),
        "updatedAt": pr.get("updatedAt"),
        "mergeable": mergeable,
        "reviewDecision": review_decision or "NONE",
        "checks": checks,
        "status": status,
        "reasons": reasons,
    }


def fetch_open_prs(limit: int) -> list[dict[str, Any]]:
    return gh_json([
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        str(limit),
        "--json",
        "number,title,author,headRefName,baseRefName,isDraft,mergeable,reviewDecision,statusCheckRollup,updatedAt,url",
    ])


def render_queue_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# PR Review Queue",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Repository: `{summary['repo']}`",
        f"- Open PRs scanned: `{summary['total']}`",
        "",
        "## Counts",
        "",
    ]
    for status, count in sorted(summary["counts"].items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Queue", ""])
    for item in summary["items"]:
        reason = "; ".join(item["reasons"]) if item["reasons"] else "no blocker detected"
        lines.append(
            f"- **#{item['number']}** `{item['status']}` "
            f"{item['title']} — {reason} ({item['url']})"
        )
    lines.append("")
    return "\n".join(lines)


def cmd_queue(args: argparse.Namespace) -> int:
    prs = fetch_open_prs(args.limit)
    items = [classify_pr(pr) for pr in prs]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    summary = {
        "schema": "dharma.pr_review.queue.v1",
        "generated_at": utc_now(),
        "repo": repo_name(),
        "total": len(items),
        "counts": counts,
        "items": items,
    }
    out_dir = expand(args.state_root) / "queue"
    write_json(out_dir / "latest.json", summary)
    write_text(out_dir / "latest.md", render_queue_markdown(summary))
    print(f"scanned={len(items)} output={out_dir / 'latest.md'}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    return 0


def fetch_pr_view(pr_number: int) -> dict[str, Any]:
    return gh_json([
        "pr",
        "view",
        str(pr_number),
            "--json",
            "number,title,body,author,baseRefName,headRefName,headRefOid,isDraft,mergeable,reviewDecision,statusCheckRollup,comments,commits,updatedAt,url",
    ])


def fetch_pr_files(pr_number: int, repo: str) -> list[dict[str, Any]]:
    return gh_json(["api", f"repos/{repo}/pulls/{pr_number}/files", "--paginate"], timeout=180)


def fetch_review_threads(pr_number: int, repo: str) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    nodes: list[dict[str, Any]] = []
    cursor = ""
    query = """
    query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              isResolved
              isOutdated
              comments(first: 5) {
                nodes {
                  author { login }
                  body
                  path
                  line
                  createdAt
                }
              }
            }
          }
        }
      }
    }
    """
    while True:
        result = run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "-F",
                f"owner={owner}",
                "-F",
                f"name={name}",
                "-F",
                f"number={pr_number}",
                "-F",
                f"cursor={cursor}",
            ],
            timeout=120,
            check=False,
        )
        if result.code != 0:
            return {"ok": False, "error": (result.stderr or result.stdout).strip(), "unresolved": None}
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"ok": False, "error": "GitHub GraphQL returned non-JSON output", "unresolved": None}
        threads = (
            payload.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
        )
        if not isinstance(threads, dict):
            return {"ok": False, "error": "GitHub GraphQL reviewThreads payload missing", "unresolved": None}
        nodes.extend(threads.get("nodes") or [])
        page_info = threads.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = str(page_info.get("endCursor") or "")
        if not cursor:
            return {"ok": False, "error": "GitHub GraphQL reviewThreads pagination cursor missing", "unresolved": None}
    unresolved = [
        node for node in nodes
        if not node.get("isResolved") and not node.get("isOutdated")
    ]
    return {"ok": True, "threads": nodes, "unresolved": unresolved, "unresolved_count": len(unresolved)}


def coherence_results(body: str) -> dict[str, Any]:
    lines = body.splitlines()
    results: dict[str, dict[str, Any]] = {}
    all_prefix_variants = tuple(
        prefix
        for known_field in REQUIRED_COHERENCE_FIELDS
        for prefix in (
            f"- {known_field}:",
            f"* {known_field}:",
            f"{known_field}:",
            f"- **{known_field}**:",
            f"- **{known_field}:**",
            f"* **{known_field}**:",
            f"* **{known_field}:**",
            f"**{known_field}**:",
            f"**{known_field}:**",
        )
    )
    for field in REQUIRED_COHERENCE_FIELDS:
        prefix_variants = (
            f"- {field}:",
            f"* {field}:",
            f"{field}:",
            f"- **{field}**:",
            f"- **{field}:**",
            f"* **{field}**:",
            f"* **{field}:**",
            f"**{field}**:",
            f"**{field}:**",
        )
        value = None
        for index, line in enumerate(lines):
            stripped = line.strip()
            match = next((prefix for prefix in prefix_variants if stripped.startswith(prefix)), None)
            if not match:
                continue
            first = stripped[len(match):].strip()
            tail: list[str] = []
            for next_line in lines[index + 1:]:
                next_stripped = next_line.strip()
                if not next_stripped:
                    continue
                if any(next_stripped.startswith(prefix) for prefix in all_prefix_variants):
                    break
                if next_stripped.startswith("#"):
                    break
                tail.append(next_stripped)
            value = "\n".join(part for part in [first, *tail] if part).strip()
            break
        normalized = (value or "").strip().lower().strip("`*_-. ")
        placeholder_values = {"", "n/a", "na", "tbd", "todo", "unknown", "placeholder"}
        if field != "New drift introduced":
            placeholder_values.update({"none", "none yet"})
        ok = bool(value) and normalized not in placeholder_values
        results[field] = {"ok": ok, "value": value or "", "reason": "" if ok else "missing or placeholder"}
    return {"ok": all(item["ok"] for item in results.values()), "fields": results}


def risk_from_files(files: list[dict[str, Any]]) -> dict[str, Any]:
    names = [str(item.get("filename") or "") for item in files]
    hot = [name for name in names if any(name == pattern or name.startswith(pattern) for pattern in HOT_PATH_PATTERNS)]
    deletions = [name for name, item in zip(names, files) if item.get("status") == "removed"]
    additions = sum(int(item.get("additions") or 0) for item in files)
    deletions_count = sum(int(item.get("deletions") or 0) for item in files)
    docs_only = bool(names) and all(name.startswith("docs/") or name.endswith(".md") for name in names)

    if any(name in {"dharma_swarm/dharma_kernel.py", "dharma_swarm/telos_gates.py"} for name in hot):
        level = "CRITICAL"
    elif len(names) > 25 or additions + deletions_count > 2000 or hot:
        level = "HIGH"
    elif docs_only or len(names) <= 3:
        level = "LOW"
    else:
        level = "MEDIUM"

    return {
        "level": level,
        "files_changed": len(names),
        "additions": additions,
        "deletions": deletions_count,
        "docs_only": docs_only,
        "hot_paths": hot,
        "removed_files": deletions,
    }


def render_agent_prompt(agent: str, packet_path: Path, pr_number: int) -> str:
    return f"""You are {agent}, reviewing Dharma Swarm PR #{pr_number}.

Read the packet at:
{packet_path}

Then review the PR with a code-review stance: findings first, highest severity
first, with file/line evidence. Do not approve from vibes. Do not merge. Do not
modify files. Check:

- CI/check state and mergeability
- Coherence Delta fields and PR-body honesty
- changed files and hot-path blast radius
- unresolved review threads
- tests claimed vs tests actually relevant
- hidden substrate/adapter/router duplication
- docs drift, authority overclaiming, and anti-slop violations

Return markdown with exactly:

## Verdict
A single line containing exactly one of: APPROVE, REQUEST_CHANGES, BLOCKED, NEEDS_HUMAN.

## Findings
Numbered findings with severity, evidence, and why it matters.

## Missing Tests Or Proof
Concrete gaps only.

## Merge Conditions
The exact conditions that must be true before merge.
"""


def review_command_and_env(
    agent: str,
    base_env: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Return a reviewer command and environment.

    Claude Code should not inherit a depleted Anthropic Console key by default.
    The operator can opt back into API-key mode by setting
    DHARMA_CLAUDE_REVIEW_USE_API_KEY=1 or by supplying CLAUDE_REVIEW_COMMAND.
    """

    env = dict(base_env or os.environ)
    if agent == "claude":
        override = env.get("CLAUDE_REVIEW_COMMAND", "").strip()
        if override:
            command = shlex.split(override)
        elif CLAUDE_REVIEW_DEFAULT_BIN.exists():
            command = [CLAUDE_REVIEW_DEFAULT_BIN.as_posix(), "-p"]
        else:
            command = ["claude", "-p"]
        if env.get("DHARMA_CLAUDE_REVIEW_USE_API_KEY") != "1":
            env.pop("ANTHROPIC_API_KEY", None)
        return command, env

    override = env.get("CODEX_REVIEW_COMMAND", "").strip()
    command = shlex.split(override) if override else ["codex", "exec"]
    return command, env


def render_packet_markdown(packet: dict[str, Any]) -> str:
    pr = packet["pr"]
    risk = packet["risk"]
    checks = packet["classification"]["checks"]
    lines = [
        f"# PR #{pr['number']} Review Packet",
        "",
        f"- Title: {pr['title']}",
        f"- URL: {pr['url']}",
        f"- Generated: `{packet['generated_at']}`",
        f"- Branch: `{pr['headRefName']}` → `{pr['baseRefName']}`",
        f"- Queue status: `{packet['classification']['status']}`",
        f"- Mergeable: `{packet['classification']['mergeable']}`",
        f"- Review decision: `{packet['classification']['reviewDecision']}`",
        f"- Risk: `{risk['level']}` ({risk['files_changed']} files, +{risk['additions']}/-{risk['deletions']})",
        f"- Checks: passing={len(checks['passing'])} failing={len(checks['failing'])} pending={len(checks['pending'])} unknown={len(checks['unknown'])}",
        f"- Coherence Delta: `{'pass' if packet['coherence']['ok'] else 'fail'}`",
        f"- Unresolved review threads: `{packet['review_threads'].get('unresolved_count')}`",
        "",
        "## Hot Paths",
        "",
    ]
    if risk["hot_paths"]:
        lines.extend(f"- `{path}`" for path in risk["hot_paths"])
    else:
        lines.append("- none detected")
    lines.extend(["", "## Changed Files", ""])
    for item in packet["files"]:
        lines.append(
            f"- `{item.get('filename')}` {item.get('status')} "
            f"+{item.get('additions', 0)}/-{item.get('deletions', 0)}"
        )
    lines.extend([
        "",
        "## Queue Reasons",
        "",
    ])
    if packet["classification"]["reasons"]:
        lines.extend(f"- {reason}" for reason in packet["classification"]["reasons"])
    else:
        lines.append("- no automatic blocker detected")
    lines.extend([
        "",
        "## Required Local Outputs",
        "",
        "- `codex_review.md`",
        "- `claude_review.md`",
        "- `MERGE_GATE.md`",
        "",
        "Generate reviews from `PROMPT_CODEX.md` and `PROMPT_CLAUDE.md` in this directory.",
        "",
    ])
    return "\n".join(lines)


def packet_dir(state_root: Path, pr_number: int, packet_id: str | None = None) -> Path:
    base = state_root / f"pr-{pr_number}"
    if packet_id:
        return base / packet_id
    existing = sorted([path for path in base.glob("*") if path.is_dir()])
    if not existing:
        raise PRControlError(f"no packet directory exists for PR #{pr_number}; run packet first")
    return existing[-1]


def cmd_packet(args: argparse.Namespace) -> int:
    root = expand(args.state_root)
    pr = fetch_pr_view(args.pr)
    repo = repo_name()
    files = fetch_pr_files(args.pr, repo)
    threads = fetch_review_threads(args.pr, repo)
    classification = classify_pr(pr)
    coherence = coherence_results(pr.get("body") or "")
    risk = risk_from_files(files)
    out_dir = root / f"pr-{args.pr}" / stamp()
    packet = {
        "schema": "dharma.pr_review.packet.v1",
        "generated_at": utc_now(),
        "repo": repo,
        "pr": pr,
        "classification": classification,
        "coherence": coherence,
        "risk": risk,
        "files": files,
        "review_threads": threads,
    }
    write_json(out_dir / "FACTS.json", packet)
    write_text(out_dir / "PR_BODY.md", pr.get("body") or "")
    write_text(out_dir / "changed_files.txt", "\n".join(str(item.get("filename") or "") for item in files) + "\n")
    write_text(out_dir / "REVIEW_PACKET.md", render_packet_markdown(packet))
    write_text(out_dir / "PROMPT_CODEX.md", render_agent_prompt("Codex", out_dir / "REVIEW_PACKET.md", args.pr))
    write_text(out_dir / "PROMPT_CLAUDE.md", render_agent_prompt("Claude Code Opus", out_dir / "REVIEW_PACKET.md", args.pr))
    print(f"packet={out_dir}")
    print(f"status={classification['status']} risk={risk['level']} coherence={'pass' if coherence['ok'] else 'fail'}")
    return 0


def latest_or_arg_packet(args: argparse.Namespace) -> Path:
    root = expand(args.state_root)
    return expand(args.packet_dir) if args.packet_dir else packet_dir(root, args.pr)


def has_review(path: Path) -> bool:
    return path.exists() and len(path.read_text(encoding="utf-8").strip()) >= 40


def review_receipt_status(path: Path, *, expected_head_sha: str = "") -> dict[str, Any]:
    if not has_review(path):
        return {"ok": False, "verdict": "", "reason": "missing or too short", "reviewed_head_sha": ""}
    receipt_path = path.with_name(path.stem.replace("_review", "_review_receipt") + ".json")
    if not receipt_path.exists():
        return {"ok": False, "verdict": "", "reason": "missing reviewer receipt JSON", "reviewed_head_sha": ""}
    try:
        receipt = load_json(receipt_path)
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "verdict": "", "reason": "invalid reviewer receipt JSON", "reviewed_head_sha": ""}
    reviewed_head_sha = str(receipt.get("reviewed_head_sha") or "")
    if receipt.get("exit_code") != 0:
        return {"ok": False, "verdict": "", "reason": f"review command exited {receipt.get('exit_code')}", "reviewed_head_sha": reviewed_head_sha}
    if expected_head_sha and reviewed_head_sha != expected_head_sha:
        return {"ok": False, "verdict": "", "reason": "reviewed head SHA mismatch", "reviewed_head_sha": reviewed_head_sha}
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    if "error:" in lowered or "failed to initialize" in lowered or "traceback" in lowered:
        return {"ok": False, "verdict": "", "reason": "review command failed", "reviewed_head_sha": reviewed_head_sha}
    lines = [line.strip() for line in text.splitlines()]
    allowed = {"APPROVE", "REQUEST_CHANGES", "BLOCKED", "NEEDS_HUMAN"}
    for index, line in enumerate(lines):
        if line.lower() != "## verdict":
            continue
        for candidate in lines[index + 1:]:
            if not candidate:
                continue
            verdict = candidate.strip("`*_-. ")
            if verdict in allowed:
                return {"ok": True, "verdict": verdict, "reason": "", "reviewed_head_sha": reviewed_head_sha}
            return {"ok": False, "verdict": verdict, "reason": "invalid verdict", "reviewed_head_sha": reviewed_head_sha}
    return {"ok": False, "verdict": "", "reason": "missing ## Verdict section", "reviewed_head_sha": reviewed_head_sha}


def build_gate(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = latest_or_arg_packet(args)
    original = load_json(out_dir / "FACTS.json")
    current_pr = fetch_pr_view(args.pr)
    repo = repo_name()
    current_threads = fetch_review_threads(args.pr, repo)
    current_classification = classify_pr(current_pr)
    current_coherence = coherence_results(current_pr.get("body") or "")
    packet_head_sha = str((original.get("pr") or {}).get("headRefOid") or "")
    current_head_sha = str(current_pr.get("headRefOid") or "")

    blockers: list[str] = []
    warnings: list[str] = []
    if not packet_head_sha:
        blockers.append("packet is missing reviewed head SHA")
    if current_head_sha and packet_head_sha and current_head_sha != packet_head_sha:
        blockers.append("PR head changed since packet generation")
    if current_pr.get("isDraft"):
        blockers.append("PR is draft")
    if current_classification["mergeable"] != "MERGEABLE":
        blockers.append(f"mergeable={current_classification['mergeable']}")
    if current_classification["checks"]["failing"]:
        blockers.append(f"failing checks: {', '.join(current_classification['checks']['failing'])}")
    if current_classification["checks"]["unknown"]:
        blockers.append(f"unknown checks: {', '.join(current_classification['checks']['unknown'])}")
    if current_classification["checks"]["pending"] and not args.allow_pending:
        blockers.append(f"pending checks: {', '.join(current_classification['checks']['pending'])}")
    if current_classification["reviewDecision"] == "CHANGES_REQUESTED":
        blockers.append("GitHub review decision is CHANGES_REQUESTED")
    if not current_coherence["ok"]:
        blockers.append("Coherence Delta fields missing or placeholder")
    unresolved_count = current_threads.get("unresolved_count")
    if not current_threads.get("ok"):
        blockers.append(f"could not verify review threads: {current_threads.get('error') or 'unknown error'}")
    if unresolved_count:
        blockers.append(f"{unresolved_count} unresolved review threads")

    codex_path = out_dir / "codex_review.md"
    claude_path = out_dir / "claude_review.md"
    codex_receipt = review_receipt_status(codex_path, expected_head_sha=current_head_sha)
    claude_receipt = review_receipt_status(claude_path, expected_head_sha=current_head_sha)
    if not codex_receipt["ok"]:
        blockers.append(f"invalid codex_review.md receipt: {codex_receipt['reason']}")
    elif codex_receipt["verdict"] != "APPROVE":
        blockers.append(f"codex_review.md verdict is {codex_receipt['verdict']}")
    if not claude_receipt["ok"]:
        blockers.append(f"invalid claude_review.md receipt: {claude_receipt['reason']}")
    elif claude_receipt["verdict"] != "APPROVE":
        blockers.append(f"claude_review.md verdict is {claude_receipt['verdict']}")

    original_risk = original.get("risk", {}).get("level", "UNKNOWN")
    if original_risk in {"HIGH", "CRITICAL"} and not args.human_approved:
        blockers.append(f"{original_risk} risk requires --human-approved")
    if original_risk in {"HIGH", "CRITICAL"} and args.human_approved and not args.human_approval_note.strip():
        blockers.append(f"{original_risk} risk requires --human-approval-note")
    return {
        "schema": "dharma.pr_review.merge_gate.v1",
        "generated_at": utc_now(),
        "repo": repo,
        "pr": args.pr,
        "packet_dir": str(out_dir),
        "decision": "MERGE_CANDIDATE" if not blockers else "BLOCKED",
        "blockers": blockers,
        "warnings": warnings,
        "classification": current_classification,
        "coherence": current_coherence,
        "review_threads": {
            "ok": current_threads.get("ok"),
            "unresolved_count": unresolved_count,
        },
        "review_receipts": {
            "codex": str(codex_path),
            "codex_present": has_review(codex_path),
            "codex_valid": codex_receipt["ok"],
            "codex_verdict": codex_receipt["verdict"],
            "codex_reviewed_head_sha": codex_receipt["reviewed_head_sha"],
            "claude": str(claude_path),
            "claude_present": has_review(claude_path),
            "claude_valid": claude_receipt["ok"],
            "claude_verdict": claude_receipt["verdict"],
            "claude_reviewed_head_sha": claude_receipt["reviewed_head_sha"],
        },
        "head_sha": {
            "packet": packet_head_sha,
            "current": current_head_sha,
        },
        "risk": original.get("risk", {}),
        "human_approval": {
            "approved": bool(args.human_approved),
            "note": args.human_approval_note.strip(),
        },
    }


def render_gate_markdown(gate: dict[str, Any]) -> str:
    lines = [
        f"# PR #{gate['pr']} Merge Gate",
        "",
        f"- Generated: `{gate['generated_at']}`",
        f"- Decision: `{gate['decision']}`",
        f"- Packet: `{gate['packet_dir']}`",
        f"- Risk: `{gate.get('risk', {}).get('level', 'UNKNOWN')}`",
        "",
        "## Blockers",
        "",
    ]
    if gate["blockers"]:
        lines.extend(f"- {blocker}" for blocker in gate["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if gate["warnings"]:
        lines.extend(f"- {warning}" for warning in gate["warnings"])
    else:
        lines.append("- none")
    lines.extend(["", "## Review Receipts", ""])
    receipts = gate["review_receipts"]
    lines.append(
        f"- Codex: `{receipts['codex']}` present={receipts['codex_present']} "
        f"valid={receipts['codex_valid']} verdict={receipts['codex_verdict'] or 'NONE'} "
        f"head={receipts['codex_reviewed_head_sha'] or 'NONE'}"
    )
    lines.append(
        f"- Claude: `{receipts['claude']}` present={receipts['claude_present']} "
        f"valid={receipts['claude_valid']} verdict={receipts['claude_verdict'] or 'NONE'} "
        f"head={receipts['claude_reviewed_head_sha'] or 'NONE'}"
    )
    lines.append("")
    return "\n".join(lines)


def render_github_comment(packet: dict[str, Any], gate: dict[str, Any] | None) -> str:
    pr = packet["pr"]
    classification = packet["classification"]
    risk = packet["risk"]
    coherence = packet["coherence"]
    decision = gate.get("decision") if gate else "GATE_MISSING"
    blockers = gate.get("blockers", []) if gate else ["merge gate output missing or gate execution failed"]
    warnings = gate.get("warnings", []) if gate else []

    lines = [
        "<!-- dharma-pr-review-control:auto -->",
        "## Dharma PR Review Control",
        "",
        f"- PR: `#{pr['number']}`",
        f"- Decision: `{decision}`",
        f"- Queue status: `{classification['status']}`",
        f"- Mergeable: `{classification['mergeable']}`",
        f"- Risk: `{risk['level']}` ({risk['files_changed']} files, +{risk['additions']}/-{risk['deletions']})",
        f"- Coherence Delta: `{'pass' if coherence['ok'] else 'fail'}`",
        "",
        "### Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- none from deterministic gate")
    lines.extend(["", "### Warnings", ""])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend([
        "",
        "### Required Local Review Receipts",
        "",
        "Run these from the repo root on the operator machine:",
        "",
        "```bash",
        f"make pr-packet PR={pr['number']}",
        f"make pr-run-codex PR={pr['number']}",
        f"make pr-run-claude PR={pr['number']}",
        f"make pr-gate PR={pr['number']}",
        "```",
        "",
        "Merge remains local and confirmation-gated:",
        "",
        "```bash",
        f"make pr-merge PR={pr['number']} ARGS=\"--confirm merge-pr-{pr['number']}\"",
        "```",
    ])
    return "\n".join(lines) + "\n"


def cmd_gate(args: argparse.Namespace) -> int:
    gate = build_gate(args)
    out_dir = Path(gate["packet_dir"])
    write_json(out_dir / "MERGE_GATE.json", gate)
    write_text(out_dir / "MERGE_GATE.md", render_gate_markdown(gate))
    print(f"decision={gate['decision']} gate={out_dir / 'MERGE_GATE.md'}")
    if gate["blockers"]:
        for blocker in gate["blockers"]:
            print(f"BLOCKER: {blocker}")
        return 2
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    out_dir = latest_or_arg_packet(args)
    packet = load_json(out_dir / "FACTS.json")
    gate_path = out_dir / "MERGE_GATE.json"
    gate = load_json(gate_path) if gate_path.exists() else None
    comment = render_github_comment(packet, gate)
    if args.output:
        write_text(expand(args.output), comment)
        print(args.output)
    else:
        print(comment)
    return 0


def cmd_reviewers(args: argparse.Namespace) -> int:
    claude_command, claude_env = review_command_and_env("claude")
    codex_command, _ = review_command_and_env("codex")

    claude_proc = subprocess.run(
        [claude_command[0], "auth", "status", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=claude_env,
        timeout=30,
        check=False,
    )
    claude_payload: dict[str, Any] | None = None
    try:
        claude_payload = json.loads(claude_proc.stdout)
    except json.JSONDecodeError:
        claude_payload = None

    result = {
        "schema": "dharma.pr_review.reviewers.v1",
        "generated_at": utc_now(),
        "claude": {
            "command": claude_command,
            "credential_env_scrubbed": "ANTHROPIC_API_KEY" not in claude_env,
            "auth_status_exit": claude_proc.returncode,
            "auth_status": claude_payload,
            "ready": bool(isinstance(claude_payload, dict) and claude_payload.get("loggedIn")),
        },
        "codex": {
            "command": codex_command,
            "ready": True,
        },
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["claude"]["ready"] else 2

    print(f"Claude command: {' '.join(claude_command)}")
    print(f"Claude credential env scrubbed: {result['claude']['credential_env_scrubbed']}")
    print(f"Claude ready: {result['claude']['ready']}")
    if isinstance(claude_payload, dict):
        print(f"Claude auth: {json.dumps(claude_payload, sort_keys=True)}")
    else:
        print("Claude auth: unavailable")
    print(f"Codex command: {' '.join(codex_command)}")
    print(f"Codex ready: {result['codex']['ready']}")
    return 0 if result["claude"]["ready"] else 2


def cmd_merge(args: argparse.Namespace) -> int:
    expected = f"merge-pr-{args.pr}"
    if args.confirm != expected:
        raise PRControlError(f"merge requires --confirm {expected!r}")
    gate = build_gate(args)
    out_dir = Path(gate["packet_dir"])
    write_json(out_dir / "MERGE_GATE.json", gate)
    write_text(out_dir / "MERGE_GATE.md", render_gate_markdown(gate))
    if gate["blockers"]:
        print(f"decision=BLOCKED gate={out_dir / 'MERGE_GATE.md'}")
        for blocker in gate["blockers"]:
            print(f"BLOCKER: {blocker}")
        return 2
    if not args.execute:
        print("decision=MERGE_CANDIDATE")
        print(
            "dry_run=true command="
            f"gh pr merge {args.pr} --{args.method} --delete-branch "
            f"--match-head-commit {gate['head_sha']['current']}"
        )
        return 0
    run(
        [
            "gh",
            "pr",
            "merge",
            str(args.pr),
            f"--{args.method}",
            "--delete-branch",
            "--match-head-commit",
            gate["head_sha"]["current"],
        ],
        timeout=300,
    )
    print(f"merged=pr-{args.pr} method={args.method}")
    return 0


def cmd_run_agent(args: argparse.Namespace) -> int:
    out_dir = latest_or_arg_packet(args)
    packet = load_json(out_dir / "FACTS.json")
    reviewed_head_sha = str((packet.get("pr") or {}).get("headRefOid") or "")
    prompt_name = "PROMPT_CLAUDE.md" if args.agent == "claude" else "PROMPT_CODEX.md"
    output_name = "claude_review.md" if args.agent == "claude" else "codex_review.md"
    prompt = (out_dir / prompt_name).read_text(encoding="utf-8")
    command, env = review_command_and_env(args.agent)
    result = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
    )
    write_text(out_dir / output_name, result.stdout or result.stderr)
    write_json(
        out_dir / f"{args.agent}_review_receipt.json",
        {
            "schema": "dharma.pr_review.agent_receipt.v1",
            "generated_at": utc_now(),
            "agent": args.agent,
            "command": command,
            "exit_code": result.returncode,
            "reviewed_head_sha": reviewed_head_sha,
            "output": str(out_dir / output_name),
        },
    )
    print(f"agent={args.agent} exit={result.returncode} output={out_dir / output_name}")
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT), help="Receipt root (default: ~/.dharma/pr_review)")
    sub = parser.add_subparsers(dest="command", required=True)

    queue = sub.add_parser("queue", help="Classify all open PRs")
    queue.add_argument("--limit", type=int, default=100)
    queue.set_defaults(func=cmd_queue)

    packet = sub.add_parser("packet", help="Create a dual-agent review packet for one PR")
    packet.add_argument("--pr", type=int, required=True)
    packet.set_defaults(func=cmd_packet)

    gate = sub.add_parser("gate", help="Run the merge gate for one PR")
    gate.add_argument("--pr", type=int, required=True)
    gate.add_argument("--packet-dir")
    gate.add_argument("--allow-pending", action="store_true")
    gate.add_argument("--human-approved", action="store_true")
    gate.add_argument("--human-approval-note", default="")
    gate.set_defaults(func=cmd_gate)

    merge = sub.add_parser("merge", help="Dry-run or execute a gated merge")
    merge.add_argument("--pr", type=int, required=True)
    merge.add_argument("--packet-dir")
    merge.add_argument("--allow-pending", action="store_true")
    merge.add_argument("--human-approved", action="store_true")
    merge.add_argument("--human-approval-note", default="")
    merge.add_argument("--method", choices=("squash", "merge", "rebase"), default="squash")
    merge.add_argument("--confirm", required=True)
    merge.add_argument("--execute", action="store_true")
    merge.set_defaults(func=cmd_merge)

    comment = sub.add_parser("comment", help="Render a GitHub comment for the latest packet/gate")
    comment.add_argument("--pr", type=int, required=True)
    comment.add_argument("--packet-dir")
    comment.add_argument("--output")
    comment.set_defaults(func=cmd_comment)

    reviewers = sub.add_parser("reviewers", help="Check local reviewer command/auth readiness")
    reviewers.add_argument("--json", action="store_true")
    reviewers.set_defaults(func=cmd_reviewers)

    run_agent = sub.add_parser("run-agent", help="Run Codex or Claude against an existing packet")
    run_agent.add_argument("--pr", type=int, required=True)
    run_agent.add_argument("--packet-dir")
    run_agent.add_argument("--agent", choices=("codex", "claude"), required=True)
    run_agent.set_defaults(func=cmd_run_agent)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PRControlError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
