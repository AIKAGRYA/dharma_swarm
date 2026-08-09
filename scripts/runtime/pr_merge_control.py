#!/usr/bin/env python3
"""Governed PR queue, dual-agent review packets, and merge gates.

This script is intentionally local-first. It uses `gh` for live GitHub state,
writes receipts under ~/.dharma/pr_review by default, and never merges unless
an operator passes an explicit confirmation token.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import signal
import shlex
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

try:
    from scripts.runtime.ci_truth import (
        DEFAULT_CONTRACT_PATH as DEFAULT_CI_TRUTH_CONTRACT,
    )
    from scripts.runtime.ci_truth import evaluate_rollup as evaluate_ci_rollup
    from scripts.runtime.ci_truth import load_contract as load_ci_truth_contract
except ModuleNotFoundError:
    from ci_truth import DEFAULT_CONTRACT_PATH as DEFAULT_CI_TRUTH_CONTRACT
    from ci_truth import evaluate_rollup as evaluate_ci_rollup
    from ci_truth import load_contract as load_ci_truth_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NATS_CA_PEM_PATH = (
    REPO_ROOT / "dharma_swarm" / "a2a" / "nats" / "agni-ws-ca.pem"
)
DEFAULT_STATE_ROOT = Path("~/.dharma/pr_review")
REQUIRED_COHERENCE_FIELDS = (
    "Organ touched",
    "Declared-vs-actual gap closed",
    "Proof that re-reads the map",
    "New drift introduced",
)
BAD_CONCLUSIONS = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
PASS_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
REVIEW_VERDICTS = ("APPROVE", "REQUEST_CHANGES", "BLOCKED", "NEEDS_HUMAN")
GIT_COMMIT_OID_RE = re.compile(r"^[0-9a-f]{40}$")
REVIEW_EVIDENCE_FILES = (
    "FACTS.json",
    "PR_BODY.md",
    "changed_files.txt",
    "DIFF.patch",
    "REVIEW_PACKET.md",
)
MAX_REVIEW_EVIDENCE_BYTES = 512 * 1024
DEFAULT_AGENT_TIMEOUT_S = 600.0
DEFAULT_AGENT_KILL_GRACE_S = 5.0
DEFAULT_FANOUT_STATUSES = ("GITHUB_GREEN_NEEDS_PACKET", "NEEDS_AGENT_REVIEW")
DEFAULT_A2A_NATS_SUBJECTS = (
    "dharma.a2a.fleet",
    "dharma.a2a.merge_master_mike",
    "dharma.a2a.github_copilot",
    "dharma.a2a.claude",
    "dharma.a2a.devin",
    "dharma.a2a.codex",
    "dharma.a2a.hermes",
    "dharma.a2a.perplexity",
)
DEFAULT_REQUIRED_REVIEWERS = ("codex", "claude")
# PRs carrying this label are produced by trusted automation (automerge.yml
# enrolls bot/automated PRs). For these, Merge Master Mike waives the human/
# agent reviewer-receipt requirement. Review conversations remain native
# branch-protection blockers even when they are outdated or bot-authored.
# Every other gate (mergeable, failing/pending checks, CHANGES_REQUESTED,
# Coherence Delta, CI truth, HIGH/CRITICAL risk) still applies unchanged.
BOT_PR_LABEL = "bot-pr"
# Review bots whose threads are advisory in substance. They are identified for
# diagnostics, but native conversation-resolution policy still blocks every
# unresolved thread; this controller never claims a waiver GitHub will reject.
ADVISORY_REVIEW_BOTS = frozenset({"greptile-apps"})
MERGE_MASTER_MIKE_NATS_SECRET_NAMES = (
    "MERGE_MASTER_MIKE_NATS_URL",
    "MERGE_MASTER_MIKE_NATS_USER",
    "MERGE_MASTER_MIKE_NATS_PW",
)
DEVIN_NATS_SECRET_NAMES = ("DEVIN_NATS_URL", "DEVIN_NATS_USER", "DEVIN_NATS_PW")
NATS_REQUIRED_SECRET_NAMES = DEVIN_NATS_SECRET_NAMES
MERGE_MODES = ("off", "auto-when-clean")
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


@dataclass(frozen=True)
class NATSConfig:
    endpoint: str
    user: str
    credential: str
    missing: tuple[str, ...]
    ca_pem: str = ""
    tls_hostname: str = ""
    credential_family: str = "devin"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def run(
    cmd: list[str], *, cwd: Path = REPO_ROOT, timeout: int = 120, check: bool = True
) -> CommandResult:
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
        raise PRControlError(
            f"gh returned non-JSON output for {' '.join(args)}"
        ) from exc


def repo_name() -> str:
    result = run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        timeout=30,
    )
    name = result.stdout.strip()
    if not name or "/" not in name:
        raise PRControlError("could not determine GitHub repository name")
    return name


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ci_truth_contract_path(args: argparse.Namespace | None = None) -> Path:
    configured = ""
    if args is not None:
        configured = getattr(args, "ci_truth_contract", "") or ""
    configured = configured or os.environ.get("DHARMA_CI_TRUTH_CONTRACT", "")
    return expand(configured) if configured else DEFAULT_CI_TRUTH_CONTRACT


def ci_truth_for_pr(
    pr: dict[str, Any], args: argparse.Namespace | None = None
) -> dict[str, Any]:
    contract = load_ci_truth_contract(ci_truth_contract_path(args))
    return evaluate_ci_rollup(pr.get("statusCheckRollup") or [], contract)


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def review_output_path(out_dir: Path, agent: str) -> Path:
    if agent in {"codex", "claude"}:
        return out_dir / f"{agent}_review.md"
    return out_dir / f"{agent}_review.md"


def review_receipt_path(out_dir: Path, agent: str) -> Path:
    return out_dir / f"{agent}_review_receipt.json"


def review_prompt_path(out_dir: Path, agent: str) -> Path:
    prompt_name = "PROMPT_CLAUDE.md" if agent == "claude" else "PROMPT_CODEX.md"
    return out_dir / prompt_name


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_review_evidence_snapshot(out_dir: Path) -> dict[str, bytes]:
    """Capture each review input once so the reviewer never follows mutable paths."""

    snapshot: dict[str, bytes] = {}
    remaining = MAX_REVIEW_EVIDENCE_BYTES
    for name in REVIEW_EVIDENCE_FILES:
        path = out_dir / name
        try:
            with path.open("rb") as handle:
                payload = handle.read(remaining + 1)
        except OSError as exc:
            raise PRControlError(
                f"review evidence is missing or unreadable: {name}"
            ) from exc
        if len(payload) > remaining:
            raise PRControlError(
                "review evidence exceeds "
                f"{MAX_REVIEW_EVIDENCE_BYTES}-byte limit while reading {name}"
            )
        snapshot[name] = payload
        remaining -= len(payload)
    return snapshot


def review_evidence_digest(snapshot: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    if tuple(snapshot) != REVIEW_EVIDENCE_FILES:
        raise PRControlError("review evidence snapshot is incomplete or out of order")
    total_bytes = sum(len(payload) for payload in snapshot.values())
    if total_bytes > MAX_REVIEW_EVIDENCE_BYTES:
        raise PRControlError(
            f"review evidence exceeds {MAX_REVIEW_EVIDENCE_BYTES}-byte limit"
        )
    for name, payload in snapshot.items():
        encoded_name = name.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(4, "big"))
        digest.update(encoded_name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def review_evidence_sha256(out_dir: Path) -> str:
    """Hash the exact packet evidence a local reviewer is instructed to read."""

    return review_evidence_digest(read_review_evidence_snapshot(out_dir))


def review_label(agent: str) -> str:
    labels = {
        "copilot": "GitHub Copilot",
        "github_copilot": "GitHub Copilot",
        "codex": "Codex",
        "claude": "Claude",
        "devin": "Devin",
        "devin-roaming-2987d222": "Devin",
        "hermes": "Hermes",
        "perplexity": "Perplexity",
        "backup_opus": "Backup Opus",
        "backup_gemini": "Backup Gemini",
        "backup_hermes": "Backup Hermes",
        "backup_perplexity": "Backup Perplexity",
        "backup_warp_oz": "Backup Warp/Oz",
    }
    return labels.get(agent, agent.replace("_", " ").title())


def review_prompt_label(agent: str) -> str:
    if agent == "claude":
        return "Claude Code Opus"
    # All non-Claude local reviewer lanes intentionally share PROMPT_CODEX.md
    # and the Codex execution contract; keep its canonical bytes agent-stable.
    return "Codex"


def backup_reviewer_agents(args: argparse.Namespace) -> list[str]:
    raw = getattr(args, "backup_reviewers", "") or os.environ.get(
        "DHARMA_PR_BACKUP_REVIEWERS",
        "backup_opus,backup_gemini,backup_hermes,backup_perplexity",
    )
    return parse_csv_tokens(
        raw,
        default=("backup_opus", "backup_gemini", "backup_hermes", "backup_perplexity"),
    )


def check_rollup(pr: dict[str, Any]) -> dict[str, Any]:
    rollup = pr.get("statusCheckRollup") or []
    latest_by_name: dict[str, tuple[tuple[str, int], dict[str, Any]]] = {}
    for index, item in enumerate(rollup):
        name = str(
            item.get("name")
            or item.get("context")
            or item.get("workflowName")
            or "unnamed"
        )
        # startedAt identifies the newest run; an older run that finishes
        # after a newer failing run must not win on completion time.
        timestamp = str(item.get("startedAt") or item.get("completedAt") or "")
        current = latest_by_name.get(name)
        key = (timestamp, index)
        if current is None or key > current[0]:
            latest_by_name[name] = (key, item)

    failing: list[str] = []
    pending: list[str] = []
    passing: list[str] = []
    unknown: list[str] = []

    for name, (_, item) in latest_by_name.items():
        name = str(
            item.get("name")
            or item.get("context")
            or item.get("workflowName")
            or "unnamed"
        )
        conclusion = str(item.get("conclusion") or "").upper()
        status = str(item.get("status") or "").upper()
        if conclusion in BAD_CONCLUSIONS:
            failing.append(name)
        elif status and status != "COMPLETED":
            pending.append(name)
        elif conclusion in PASS_CONCLUSIONS:
            passing.append(name)
        elif conclusion:
            unknown.append(f"{name}:{conclusion}")
        else:
            unknown.append(name)

    return {
        "total": len(latest_by_name),
        "raw_total": len(rollup),
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
        reasons.append(
            "GitHub green; packet, dual review, and merge gate still required"
        )
        status = "GITHUB_GREEN_NEEDS_PACKET"

    if checks["unknown"]:
        reasons.append(f"{len(checks['unknown'])} unknown check states")

    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "author": (pr.get("author") or {}).get("login")
        if isinstance(pr.get("author"), dict)
        else pr.get("author"),
        "headRefName": pr.get("headRefName"),
        "head_sha": pr.get("headRefOid") or "",
        "baseRefName": pr.get("baseRefName"),
        "base_sha": pr.get("baseRefOid") or "",
        "updatedAt": pr.get("updatedAt"),
        "mergeable": mergeable,
        "reviewDecision": review_decision or "NONE",
        "checks": checks,
        "status": status,
        "reasons": reasons,
    }


def fetch_open_prs(limit: int) -> list[dict[str, Any]]:
    return gh_json(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,title,author,headRefName,headRefOid,baseRefName,baseRefOid,isDraft,mergeable,reviewDecision,statusCheckRollup,updatedAt,url",
        ]
    )


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
        reason = (
            "; ".join(item["reasons"]) if item["reasons"] else "no blocker detected"
        )
        lines.append(
            f"- **#{item['number']}** `{item['status']}` "
            f"{item['title']} — {reason} ({item['url']})"
        )
    lines.append("")
    return "\n".join(lines)


def cmd_queue(args: argparse.Namespace) -> int:
    prs = fetch_open_prs(args.limit)
    summary = build_queue_summary(prs, repo_name())
    out_dir = expand(args.state_root) / "queue"
    write_json(out_dir / "latest.json", summary)
    write_text(out_dir / "latest.md", render_queue_markdown(summary))
    print(f"scanned={len(summary['items'])} output={out_dir / 'latest.md'}")
    for status, count in sorted(summary["counts"].items()):
        print(f"{status}: {count}")
    return 0


def build_queue_summary(prs: list[dict[str, Any]], repo: str) -> dict[str, Any]:
    items = [classify_pr(pr) for pr in prs]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "schema": "dharma.pr_review.queue.v1",
        "generated_at": utc_now(),
        "repo": repo,
        "total": len(items),
        "counts": counts,
        "items": items,
    }


def fetch_pr_view(pr_number: int) -> dict[str, Any]:
    return gh_json(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,title,body,author,baseRefName,baseRefOid,headRefName,headRefOid,isDraft,labels,mergeable,reviewDecision,statusCheckRollup,comments,commits,updatedAt,url",
        ]
    )


def fetch_pr_files(pr_number: int, repo: str) -> list[dict[str, Any]]:
    return gh_json(
        ["api", f"repos/{repo}/pulls/{pr_number}/files", "--paginate"], timeout=180
    )


def valid_commit_oid(value: str) -> bool:
    return bool(GIT_COMMIT_OID_RE.fullmatch(value))


def fetch_pr_files_at_revision(
    repo: str, base_sha: str, head_sha: str
) -> list[dict[str, Any]]:
    """Fetch the changed files for one immutable base/head commit pair.

    The pull-files endpoint follows the branch's current ref, so using it after
    a separate PR-view request permits an A→B→A race. The compare endpoint is
    addressed only by full commit OIDs and therefore binds risk classification
    to the same revision pair recorded by the merge gate.
    """

    if not valid_commit_oid(base_sha):
        raise PRControlError("base SHA must be a full 40-character commit OID")
    if not valid_commit_oid(head_sha):
        raise PRControlError("head SHA must be a full 40-character commit OID")

    payload = gh_json(
        ["api", f"repos/{repo}/compare/{base_sha}...{head_sha}"], timeout=180
    )
    if not isinstance(payload, dict):
        raise PRControlError("immutable commit comparison returned a non-object")
    observed_base = str((payload.get("base_commit") or {}).get("sha") or "")
    if observed_base != base_sha:
        raise PRControlError(
            f"immutable commit comparison returned base {observed_base or '<missing>'}, "
            f"expected {base_sha}"
        )
    files = payload.get("files")
    if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
        raise PRControlError(
            "immutable commit comparison returned an invalid file list"
        )
    # GitHub caps compare responses at 300 changed files. Exactly 300 is
    # ambiguous, so fail closed rather than under-classifying a possibly
    # truncated CRITICAL surface as merely HIGH.
    if len(files) >= 300:
        raise PRControlError(
            "immutable commit comparison reached GitHub's 300-file cap"
        )
    validate_changed_files(files)

    # The compare endpoint paginates its `commits` array (30 entries by
    # default), so `commits[-1]` is not necessarily the requested head. Verify
    # the immutable head through its own full-OID endpoint instead. The compare
    # request itself is already addressed by the exact base/head pair; this
    # second read prevents a truncated commit page from becoming a permanent
    # false blocker while preserving fail-closed response validation.
    head_payload = gh_json(
        ["api", f"repos/{repo}/commits/{head_sha}"], timeout=180
    )
    if not isinstance(head_payload, dict):
        raise PRControlError("immutable head lookup returned a non-object")
    observed_head = str(head_payload.get("sha") or "")
    if observed_head != head_sha:
        raise PRControlError(
            f"immutable head lookup returned {observed_head or '<missing>'}, "
            f"expected {head_sha}"
        )
    return files


def fetch_pr_diff_at_revision(repo: str, base_sha: str, head_sha: str) -> str:
    """Fetch a patch addressed by the same immutable commits as risk."""

    if not valid_commit_oid(base_sha) or not valid_commit_oid(head_sha):
        raise PRControlError("immutable diff requires full base and head commit OIDs")
    result = run(
        [
            "gh",
            "api",
            f"repos/{repo}/compare/{base_sha}...{head_sha}",
            "-H",
            "Accept: application/vnd.github.diff",
        ],
        timeout=180,
    )
    return result.stdout


def fetch_review_merge_base(repo: str, base_sha: str, head_sha: str) -> str:
    """Resolve the immutable three-dot merge base for one review range."""

    if not valid_commit_oid(base_sha) or not valid_commit_oid(head_sha):
        raise PRControlError("review merge-base lookup requires full commit OIDs")
    payload = gh_json(
        ["api", f"repos/{repo}/compare/{base_sha}...{head_sha}"],
        timeout=180,
    )
    if not isinstance(payload, dict):
        raise PRControlError("review merge-base comparison returned a non-object")
    observed_base = str((payload.get("base_commit") or {}).get("sha") or "")
    merge_base = str((payload.get("merge_base_commit") or {}).get("sha") or "")
    if observed_base != base_sha:
        raise PRControlError(
            f"review merge-base comparison returned base {observed_base or '<missing>'}, "
            f"expected {base_sha}"
        )
    if not valid_commit_oid(merge_base):
        raise PRControlError("review merge-base comparison omitted a full merge-base OID")
    head_payload = gh_json(["api", f"repos/{repo}/commits/{head_sha}"], timeout=180)
    if not isinstance(head_payload, dict):
        raise PRControlError("review head lookup returned a non-object")
    observed_head = str(head_payload.get("sha") or "")
    if observed_head != head_sha:
        raise PRControlError(
            f"review head lookup returned {observed_head or '<missing>'}, expected {head_sha}"
        )
    return merge_base


def fetch_review_threads(pr_number: int, repo: str) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            nodes {
              isResolved
              isOutdated
            }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    }
    """
    nodes: list[dict[str, Any]] = []
    cursor = ""
    seen_cursors: set[str] = set()
    while True:
        command = [
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
        ]
        if cursor:
            command.extend(["-f", f"cursor={cursor}"])
        result = run(command, timeout=120, check=False)
        if result.code != 0:
            return {
                "ok": False,
                "error": (result.stderr or result.stdout).strip(),
                "unresolved": None,
            }
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "error": f"review-thread query returned invalid JSON: {exc}",
                "unresolved": None,
            }
        if not isinstance(payload, dict) or payload.get("errors"):
            return {
                "ok": False,
                "error": f"review-thread query returned GraphQL errors: {payload.get('errors') if isinstance(payload, dict) else payload!r}",
                "unresolved": None,
            }
        try:
            connection = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
            page_nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError):
            return {
                "ok": False,
                "error": "review-thread query returned incomplete connection data",
                "unresolved": None,
            }
        if not isinstance(page_nodes, list) or not all(
            isinstance(node, dict) for node in page_nodes
        ):
            return {
                "ok": False,
                "error": "review-thread query returned invalid thread nodes",
                "unresolved": None,
            }
        for node in page_nodes:
            if (
                type(node.get("isResolved")) is not bool
                or type(node.get("isOutdated")) is not bool
            ):
                return {
                    "ok": False,
                    "error": "review-thread query returned invalid resolution state",
                    "unresolved": None,
                }
        nodes.extend(page_nodes)
        if (
            not isinstance(page_info, dict)
            or type(page_info.get("hasNextPage")) is not bool
        ):
            return {
                "ok": False,
                "error": "review-thread query omitted thread pagination state",
                "unresolved": None,
            }
        if not page_info.get("hasNextPage"):
            break
        next_cursor = str(page_info.get("endCursor") or "")
        if not next_cursor or next_cursor in seen_cursors:
            return {
                "ok": False,
                "error": "review-thread pagination did not advance",
                "unresolved": None,
            }
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    unresolved = [
        node
        for node in nodes
        if not node.get("isResolved")
    ]
    unresolved_outdated_count = sum(
        1 for node in unresolved if node.get("isOutdated") is True
    )
    return {
        "ok": True,
        "threads": nodes,
        "unresolved": unresolved,
        "unresolved_count": len(unresolved),
        "unresolved_outdated_count": unresolved_outdated_count,
    }


def thread_is_advisory_only(thread: dict[str, Any]) -> bool:
    """True when every comment in a review thread was authored by an advisory
    review bot (see ADVISORY_REVIEW_BOTS).

    This is diagnostic classification only. Native conversation-resolution
    policy still blocks the unresolved thread. A thread with any non-advisory
    participant (human, Copilot, Codex, Devin, …) is never advisory-only.
    """
    comments = ((thread or {}).get("comments") or {}).get("nodes") or []
    if not comments:
        return False
    logins: set[str] = set()
    for comment in comments:
        author = (comment or {}).get("author")
        login = (
            str(author.get("login") or "").lower() if isinstance(author, dict) else ""
        )
        if not login:
            return False
        logins.add(login)
    advisory = {bot.lower() for bot in ADVISORY_REVIEW_BOTS}
    return logins <= advisory


def fetch_pr_diff(pr_number: int) -> str:
    result = run(
        ["gh", "pr", "diff", str(pr_number), "--patch"], timeout=180, check=False
    )
    if result.code != 0:
        detail = (result.stderr or result.stdout).strip()
        return f"# Diff unavailable\n\n`gh pr diff {pr_number} --patch` failed:\n\n```text\n{detail}\n```\n"
    return result.stdout


_COHERENCE_CHECKER_PATH = (
    REPO_ROOT / "scripts" / "governance" / "check_pr_coherence_delta.py"
)
_coherence_checker_module: Any = None


def _coherence_checker() -> Any:
    """The CI Coherence Delta checker, loaded as the gate's parser.

    scripts/governance/check_pr_coherence_delta.py is the single source of
    truth for Coherence Delta parsing (operator-ratified 2026-07-31): the gate
    accepts exactly what CI accepts. Fail closed — a missing or broken checker
    is a repo integrity error, never a silent fallback to a divergent parser.
    """
    global _coherence_checker_module
    if _coherence_checker_module is not None:
        return _coherence_checker_module
    module_name = "_dharma_check_pr_coherence_delta"
    spec = importlib.util.spec_from_file_location(module_name, _COHERENCE_CHECKER_PATH)
    if spec is None or spec.loader is None:
        raise PRControlError(
            f"cannot load Coherence Delta checker at {_COHERENCE_CHECKER_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    _coherence_checker_module = module
    return module


def coherence_results(body: str, comments: list[str] | None = None) -> dict[str, Any]:
    """Validate Coherence Delta fields by delegating to the CI checker.

    Accepts everything scripts/governance/check_pr_coherence_delta.py accepts —
    label aliases, bold/bullet variants (colon inside or outside the bold),
    HTML-comment stripping, and the PR-comment fallback — so the gate can never
    reject a body that CI passed."""
    checker = _coherence_checker()
    results, source = checker.validate_sources(body or "", list(comments or []))
    fields = {
        result.name: {
            "ok": result.ok,
            "value": result.value,
            "reason": "" if result.ok else (result.reason or "missing or placeholder"),
        }
        for result in results
    }
    return {
        "ok": all(result.ok for result in results),
        "fields": fields,
        "source": source,
    }


def validate_changed_files(files: list[dict[str, Any]]) -> None:
    """Reject partial or malformed compare entries before risk classification."""

    allowed_statuses = {
        "added",
        "removed",
        "modified",
        "renamed",
        "copied",
        "changed",
        "unchanged",
    }
    for index, item in enumerate(files):
        filename = item.get("filename")
        if (
            not isinstance(filename, str)
            or not filename
            or filename.startswith("/")
            or ".." in Path(filename).parts
        ):
            raise PRControlError(f"changed file {index} has an invalid filename")
        status = item.get("status")
        if status not in allowed_statuses:
            raise PRControlError(
                f"changed file {filename!r} has invalid status {status!r}"
            )
        for field in ("additions", "deletions"):
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PRControlError(
                    f"changed file {filename!r} has invalid {field} {value!r}"
                )
        if status == "renamed":
            previous = item.get("previous_filename")
            if (
                not isinstance(previous, str)
                or not previous
                or previous.startswith("/")
                or ".." in Path(previous).parts
            ):
                raise PRControlError(
                    f"renamed file {filename!r} has invalid previous_filename"
                )


def risk_from_files(files: list[dict[str, Any]]) -> dict[str, Any]:
    validate_changed_files(files)
    names = [str(item.get("filename") or "") for item in files]
    renamed_from = [
        str(item["previous_filename"])
        for item in files
        if item.get("status") == "renamed"
    ]
    risk_paths = names + renamed_from
    hot = [
        name
        for name in risk_paths
        if any(
            name == pattern or name.startswith(pattern) for pattern in HOT_PATH_PATTERNS
        )
    ]
    deletions = [
        name for name, item in zip(names, files) if item.get("status") == "removed"
    ] + renamed_from
    additions = sum(int(item.get("additions") or 0) for item in files)
    deletions_count = sum(int(item.get("deletions") or 0) for item in files)
    docs_only = bool(risk_paths) and all(
        name.startswith("docs/") or name.endswith(".md") for name in risk_paths
    )

    if any(
        name in {"dharma_swarm/dharma_kernel.py", "dharma_swarm/telos_gates.py"}
        for name in hot
    ):
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
        "renamed_from_files": renamed_from,
    }


def render_agent_prompt(
    agent: str,
    packet_path: Path,
    pr_number: int,
    *,
    evidence_snapshot: dict[str, bytes] | None = None,
) -> str:
    snapshot = evidence_snapshot or read_review_evidence_snapshot(packet_path.parent)
    evidence_digest = review_evidence_digest(snapshot)
    evidence_blocks = []
    for name, payload in snapshot.items():
        evidence_blocks.extend(
            [
                f"--- BEGIN SNAPSHOT {name} sha256={sha256_bytes(payload)} bytes={len(payload)} ---",
                payload.decode("utf-8", errors="replace"),
                f"--- END SNAPSHOT {name} ---",
            ]
        )
    embedded_evidence = "\n".join(evidence_blocks)
    return f"""You are {agent}, reviewing Dharma Swarm PR #{pr_number}.

This is a bounded queue review, not an open-ended repo exploration. The exact
review evidence is embedded below as an immutable stdin snapshot with digest
`{evidence_digest}`. Review only that embedded snapshot. Do not open or re-read
the mutable packet paths while this review runs.

Then review the PR with a code-review stance: findings first, highest severity
first, with file/line evidence. Do not approve from vibes. Do not merge. Do not
modify files.

Keep tool use narrow: do not run broad repository searches, skill discovery, or
indexing. Read only the packet, diff, and exact changed files needed to validate
the diff. If the packet is insufficient, return NEEDS_HUMAN or BLOCKED with the
missing proof instead of expanding indefinitely. Target <= 120 lines.

Check:

- CI/check state and mergeability
- Coherence Delta fields and PR-body honesty
- changed files and hot-path blast radius
- unresolved review threads
- tests claimed vs tests actually relevant
- hidden substrate/adapter/router duplication
- docs drift, authority overclaiming, and anti-slop violations

Return markdown with exactly:

## Verdict
APPROVE | REQUEST_CHANGES | BLOCKED | NEEDS_HUMAN

## Findings
Numbered findings with severity, evidence, and why it matters.

## Missing Tests Or Proof
Concrete gaps only.

## Merge Conditions
The exact conditions that must be true before merge.

## Immutable Review Evidence

{embedded_evidence}
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
            command = [
                CLAUDE_REVIEW_DEFAULT_BIN.as_posix(),
                "-p",
                "--max-turns",
                env.get("DHARMA_CLAUDE_REVIEW_MAX_TURNS", "8"),
            ]
        else:
            command = [
                "claude",
                "-p",
                "--max-turns",
                env.get("DHARMA_CLAUDE_REVIEW_MAX_TURNS", "8"),
            ]
        if env.get("DHARMA_CLAUDE_REVIEW_USE_API_KEY") != "1":
            env.pop("ANTHROPIC_API_KEY", None)
        return command, env

    override = env.get("CODEX_REVIEW_COMMAND", "").strip()
    if override:
        command = shlex.split(override)
    else:
        effort = env.get("DHARMA_CODEX_REVIEW_REASONING_EFFORT", "medium")
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "-c",
            f'model_reasoning_effort="{effort}"',
        ]
        model = env.get("DHARMA_CODEX_REVIEW_MODEL", "").strip()
        if model:
            command.extend(["--model", model])
    return command, env


def render_packet_markdown(packet: dict[str, Any]) -> str:
    pr = packet["pr"]
    risk = packet["risk"]
    checks = packet["classification"]["checks"]
    ci_truth = packet.get("ci_truth") or {}
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
        f"- CI Truth: `{ci_truth.get('verdict', 'UNKNOWN')}`",
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
    lines.extend(
        [
            "",
            "## Queue Reasons",
            "",
        ]
    )
    if packet["classification"]["reasons"]:
        lines.extend(f"- {reason}" for reason in packet["classification"]["reasons"])
    else:
        lines.append("- no automatic blocker detected")
    lines.extend(["", "## CI Truth", ""])
    if ci_truth:
        lines.append(f"- Verdict: `{ci_truth.get('verdict')}`")
        lines.append(
            f"- Observed checks: `{ci_truth.get('observed_total')}` latest / `{ci_truth.get('raw_total')}` raw"
        )
        if ci_truth.get("merge_blockers"):
            lines.extend(
                f"- BLOCKER: {blocker}" for blocker in ci_truth["merge_blockers"]
            )
        else:
            lines.append("- Merge blockers: none")
        if ci_truth.get("warnings"):
            lines.extend(f"- Warning: {warning}" for warning in ci_truth["warnings"])
    else:
        lines.append("- not evaluated")
    lines.extend(
        [
            "",
            "## Required Local Outputs",
            "",
            "- `codex_review.md`",
            "- `claude_review.md`",
            "- `MERGE_GATE.md`",
            "- `DIFF.patch` contains the PR diff for bounded review.",
            "",
            "Generate reviews from `PROMPT_CODEX.md` and `PROMPT_CLAUDE.md` in this directory.",
            "",
        ]
    )
    return "\n".join(lines)


def packet_dir(state_root: Path, pr_number: int, packet_id: str | None = None) -> Path:
    base = state_root / f"pr-{pr_number}"
    if packet_id:
        return base / packet_id
    existing = sorted([path for path in base.glob("*") if path.is_dir()])
    if not existing:
        raise PRControlError(
            f"no packet directory exists for PR #{pr_number}; run packet first"
        )
    return existing[-1]


def cmd_packet(args: argparse.Namespace) -> int:
    root = expand(args.state_root)
    pr = fetch_pr_view(args.pr)
    repo = repo_name()
    head_sha = str(pr.get("headRefOid") or "")
    base_sha = str(pr.get("baseRefOid") or "")
    if not valid_commit_oid(head_sha) or not valid_commit_oid(base_sha):
        raise PRControlError(
            "packet creation requires full current base and head commit OIDs"
        )
    files = fetch_pr_files_at_revision(repo, base_sha, head_sha)
    threads = fetch_review_threads(args.pr, repo)
    if not threads.get("ok"):
        raise PRControlError(
            "cannot build review packet without complete review-thread state: "
            f"{threads.get('error') or 'unknown query failure'}"
        )
    diff = fetch_pr_diff_at_revision(repo, base_sha, head_sha)
    if files and not diff.strip():
        raise PRControlError("immutable diff is empty for a non-empty file comparison")
    classification = classify_pr(pr)
    coherence = coherence_results(pr.get("body") or "")
    ci_truth = ci_truth_for_pr(pr, args)
    risk = risk_from_files(files)
    packet_id = stamp()
    out_dir = root / f"pr-{args.pr}" / packet_id
    if out_dir.exists():
        raise PRControlError(f"review packet directory already exists: {out_dir}")
    packet_files = [
        {key: value for key, value in item.items() if key != "patch"}
        for item in files
    ]
    packet = {
        "schema": "dharma.pr_review.packet.v1",
        "generated_at": utc_now(),
        "repo": repo,
        "pr": pr,
        "classification": classification,
        "coherence": coherence,
        "ci_truth": ci_truth,
        "risk": risk,
        "files": packet_files,
        "review_threads": threads,
    }
    evidence_snapshot = {
        "FACTS.json": (
            json.dumps(packet, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "PR_BODY.md": str(pr.get("body") or "").encode("utf-8"),
        "changed_files.txt": (
            "\n".join(str(item.get("filename") or "") for item in files) + "\n"
        ).encode("utf-8"),
        "DIFF.patch": diff.encode("utf-8"),
        "REVIEW_PACKET.md": render_packet_markdown(packet).encode("utf-8"),
    }
    review_evidence_digest(evidence_snapshot)
    prompts = {
        "PROMPT_CODEX.md": render_agent_prompt(
            "Codex",
            out_dir / "REVIEW_PACKET.md",
            args.pr,
            evidence_snapshot=evidence_snapshot,
        ).encode("utf-8"),
        "PROMPT_CLAUDE.md": render_agent_prompt(
            "Claude Code Opus",
            out_dir / "REVIEW_PACKET.md",
            args.pr,
            evidence_snapshot=evidence_snapshot,
        ).encode("utf-8"),
    }

    root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".pr-{args.pr}-{packet_id}-", dir=root)
    )
    try:
        for artifacts in (evidence_snapshot, prompts):
            for name, payload in artifacts.items():
                (staging_dir / name).write_bytes(payload)
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        if out_dir.exists():
            raise PRControlError(f"review packet directory already exists: {out_dir}")
        staging_dir.rename(out_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
    print(f"packet={out_dir}")
    print(
        f"status={classification['status']} risk={risk['level']} coherence={'pass' if coherence['ok'] else 'fail'}"
    )
    return 0


def latest_or_arg_packet(args: argparse.Namespace) -> Path:
    root = expand(args.state_root)
    return expand(args.packet_dir) if args.packet_dir else packet_dir(root, args.pr)


def has_review(path: Path) -> bool:
    return path.exists() and len(path.read_text(encoding="utf-8").strip()) >= 40


def _single_review_verdict(text: str) -> str | None:
    candidate = text.strip()
    for prefix, suffix in (("**", "**"), ("__", "__"), ("`", "`")):
        if candidate.startswith(prefix) and candidate.endswith(suffix):
            candidate = candidate[len(prefix) : -len(suffix)].strip()
            break
    candidate = candidate.upper()
    return candidate if candidate in REVIEW_VERDICTS else None


def extract_review_verdict(text: str) -> str:
    """Parse one exact token from the first line of the Verdict section."""

    in_verdict = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            if in_verdict:
                break
            header = stripped.lstrip("#").strip().lower()
            in_verdict = header.startswith("verdict")
            if in_verdict:
                inline = stripped.lstrip("#").strip()[len("verdict") :]
                inline = inline.lstrip(":").strip()
                if inline:
                    return _single_review_verdict(inline) or "UNKNOWN"
            continue
        if in_verdict and stripped:
            return _single_review_verdict(stripped) or "UNKNOWN"
    return "UNKNOWN"


def load_agent_review_status(
    out_dir: Path,
    agent: str,
    *,
    repo: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
) -> dict[str, Any]:
    output_path = review_output_path(out_dir, agent)
    prompt_path = review_prompt_path(out_dir, agent)
    receipt_path = review_receipt_path(out_dir, agent)
    text = ""
    output_digest = ""
    if output_path.exists():
        output_bytes = output_path.read_bytes()
        output_digest = sha256_bytes(output_bytes)
        text = output_bytes.decode("utf-8", errors="replace")
    prompt_digest = (
        sha256_bytes(prompt_path.read_bytes()) if prompt_path.exists() else ""
    )
    evidence_digest = ""
    evidence_error = ""
    evidence_snapshot: dict[str, bytes] | None = None
    try:
        evidence_snapshot = read_review_evidence_snapshot(out_dir)
        evidence_digest = review_evidence_digest(evidence_snapshot)
    except PRControlError as exc:
        evidence_error = str(exc)
    canonical_prompt_digest = ""
    valid_pr_number = (
        not isinstance(pr_number, bool)
        and isinstance(pr_number, int)
        and pr_number > 0
    )
    if evidence_snapshot is not None and valid_pr_number:
        canonical_prompt = render_agent_prompt(
            review_prompt_label(agent),
            out_dir / "REVIEW_PACKET.md",
            pr_number,
            evidence_snapshot=evidence_snapshot,
        )
        canonical_prompt_digest = sha256_bytes(canonical_prompt.encode("utf-8"))

    receipt: dict[str, Any] | None = None
    receipt_error = ""
    if receipt_path.exists():
        try:
            payload = load_json(receipt_path)
            if isinstance(payload, dict):
                receipt = payload
            else:
                receipt_error = "receipt JSON is not an object"
        except (OSError, json.JSONDecodeError) as exc:
            receipt_error = str(exc)

    binding_errors: list[str] = []
    if receipt is not None:
        repo_parts = repo.split("/")
        if len(repo_parts) != 2 or not all(repo_parts):
            binding_errors.append("repository binding is missing or invalid")
        if not valid_pr_number:
            binding_errors.append("PR number binding is missing or invalid")
        if not valid_commit_oid(head_sha):
            binding_errors.append("current head SHA is missing or invalid")
        if not valid_commit_oid(base_sha):
            binding_errors.append("review base SHA is missing or invalid")
        parsed_verdict = extract_review_verdict(text) if text.strip() else "MISSING"
        expected_bindings = {
            "repo": repo,
            "pr": pr_number,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "output_sha256": output_digest,
            "prompt_sha256": canonical_prompt_digest,
            "evidence_sha256": evidence_digest,
            "agent": agent,
            "verdict": parsed_verdict,
        }
        for field, expected in expected_bindings.items():
            if receipt.get(field) != expected:
                binding_errors.append(
                    f"{field}={receipt.get(field)!r}, expected {expected!r}"
                )
        if not output_digest:
            binding_errors.append("review output is missing")
        if not prompt_digest:
            binding_errors.append("review prompt is missing")
        elif prompt_digest != canonical_prompt_digest:
            binding_errors.append(
                "review prompt is not the canonical evidence snapshot"
            )
        if not evidence_digest:
            binding_errors.append(evidence_error or "review evidence is missing")
    if binding_errors:
        receipt_error = "review binding mismatch: " + "; ".join(binding_errors)

    return {
        "agent": agent,
        "output": str(output_path),
        "output_present": output_path.exists() and len(text.strip()) >= 40,
        "receipt": str(receipt_path),
        "receipt_present": receipt_path.exists(),
        "receipt_valid": receipt is not None and not binding_errors,
        "receipt_error": receipt_error,
        "receipt_status": receipt.get("status") if receipt else None,
        "exit_code": receipt.get("exit_code") if receipt else None,
        "timed_out": bool(receipt.get("timed_out")) if receipt else False,
        "timeout_s": receipt.get("timeout_s") if receipt else None,
        "duration_s": receipt.get("duration_s") if receipt else None,
        "verdict": extract_review_verdict(text) if text.strip() else "MISSING",
        "reviewed_pr_number": receipt.get("pr") if receipt else None,
        "reviewed_head_sha": receipt.get("head_sha") if receipt else None,
        "reviewed_base_sha": receipt.get("base_sha") if receipt else None,
        "review_output_sha256": output_digest,
        "review_prompt_sha256": prompt_digest,
        "review_evidence_sha256": evidence_digest,
    }


def agent_review_blockers(status: dict[str, Any], *, human_approved: bool) -> list[str]:
    agent = str(status["agent"])
    title = review_label(agent)
    blockers: list[str] = []

    if not status["output_present"]:
        blockers.append(f"missing {agent}_review.md receipt")
    if not status["receipt_present"]:
        blockers.append(f"missing {agent}_review_receipt.json")
    elif not status["receipt_valid"]:
        blockers.append(
            f"invalid {agent}_review_receipt.json: {status['receipt_error']}"
        )
    elif status["timed_out"] or status["receipt_status"] == "timeout":
        blockers.append(f"{title} review timed out after {status.get('timeout_s')}s")
    elif status["exit_code"] not in (0, "0"):
        blockers.append(f"{title} review exited non-zero ({status['exit_code']})")

    verdict = status["verdict"]
    if verdict in {"MISSING", "UNKNOWN"}:
        if status["output_present"]:
            blockers.append(f"{title} review verdict is {verdict}")
    elif verdict in {"REQUEST_CHANGES", "BLOCKED"}:
        blockers.append(f"{title} review verdict={verdict}")
    elif verdict == "NEEDS_HUMAN" and not human_approved:
        blockers.append(f"{title} review verdict=NEEDS_HUMAN requires --human-approved")
    return blockers


# Native GitHub reviews that may count as an agent's review receipt — the
# always-on cloud SOURCE. Keyed by reviewer agent -> the trusted installed
# reviewer-App logins (lowercased, "[bot]" suffix stripped). ONLY these logins
# are trusted; a review from any other login is never a receipt. `claude` has no
# native cloud reviewer login, so it never bridges (it stays the deep/backup
# lane). This is strictly ADDITIVE: it can satisfy a missing receipt, never
# waives any other gate check (CI, conflict, unresolved threads, CHANGES_REQUESTED).
TRUSTED_REVIEW_LOGINS: dict[str, frozenset[str]] = {
    "codex": frozenset({"chatgpt-codex-connector[bot]"}),
    "copilot": frozenset({"copilot-pull-request-reviewer[bot]"}),
    "github_copilot": frozenset({"copilot-pull-request-reviewer[bot]"}),
}


def _normalize_login(login: str) -> str:
    # EXACT match only — do NOT strip the "[bot]" suffix. The suffix is GitHub's
    # App-identity marker that a human account cannot hold, so matching the full
    # "<app>[bot]" login keeps the trust boundary at the installed reviewer App
    # (a human "chatgpt-codex-connector" could never satisfy the bridge).
    return (login or "").strip().lower()


def fetch_pr_reviews(pr_number: int) -> list[dict[str, Any]]:
    """Native GitHub reviews on a PR via the REST API.

    Uses the REST endpoint (not `gh pr view --json reviews`) because it returns
    ``commit_id`` — the exact SHA each review saw — which the bridge needs to
    reject reviews of stale revisions.
    """
    repo = repo_name()
    data = gh_json(["api", f"repos/{repo}/pulls/{pr_number}/reviews", "--paginate"])
    return data if isinstance(data, list) else []


def fetch_pr_comments(pr_number: int) -> list[str]:
    """Issue-comment bodies for a PR, oldest first.

    The CI Coherence Delta check accepts a PR comment carrying all four fields
    (for agents that cannot edit the PR description); the gate fetches the same
    surface so its verdict can never be stricter than CI's. The surface is
    strictly additive — a failed fetch degrades to body-only validation (the
    pre-existing behavior), it never blocks."""
    try:
        repo = repo_name()
        data = gh_json(
            ["api", f"repos/{repo}/issues/{pr_number}/comments", "--paginate"]
        )
    except Exception:
        # Additive surface only: a blocked or failed fetch (offline jail,
        # missing gh, API error) must degrade to body-only validation, which
        # is exactly the pre-change gate. It must never block or crash.
        return []
    if not isinstance(data, list):
        return []
    return [
        str(item.get("body") or "")
        for item in data
        if isinstance(item, dict) and str(item.get("body") or "").strip()
    ]


def _review_login(review: dict[str, Any]) -> str:
    user = review.get("user") or review.get("author") or {}
    return (
        _normalize_login(str(user.get("login") or "")) if isinstance(user, dict) else ""
    )


def _review_commit(review: dict[str, Any]) -> str:
    commit = review.get("commit_id") or review.get("commit") or ""
    if isinstance(commit, dict):
        commit = commit.get("oid") or commit.get("sha") or ""
    return str(commit)


def _review_submitted(review: dict[str, Any]) -> str:
    return str(review.get("submitted_at") or review.get("submittedAt") or "")


def _github_review_verdict(state: str) -> str:
    state = (state or "").strip().upper()
    if state == "APPROVED":
        return "APPROVE"
    if state == "CHANGES_REQUESTED":
        return "REQUEST_CHANGES"
    if state in {"COMMENTED", "REVIEWED"}:
        # Canonical owner policy counts a COMMENTED review from the trusted App
        # as reviewed; substantive findings are enforced through the complete
        # review-thread surface fetched separately by the gate.
        return "PASS"
    return "UNKNOWN"


def github_review_status(
    agent: str, reviews: list[dict[str, Any]], head_sha: str = ""
) -> dict[str, Any] | None:
    """Status dict synthesized from the latest trusted GitHub review for *agent*,
    shaped like load_agent_review_status(). None if no trusted, non-dismissed review.

    When *head_sha* is given, only a review that actually saw THAT head counts —
    a review of an earlier revision must not satisfy the gate after new commits
    are pushed (the bridged reviewer has not seen the new changes)."""
    trusted = TRUSTED_REVIEW_LOGINS.get(agent)
    if not trusted:
        return None
    matched = [
        review
        for review in reviews
        if _review_login(review) in trusted
        and str(review.get("state") or "").upper() != "DISMISSED"
        and (not head_sha or _review_commit(review) == head_sha)
    ]
    if not matched:
        return None
    matched.sort(key=_review_submitted)
    latest = matched[-1]
    state = str(latest.get("state") or "")
    login = _review_login(latest)
    return {
        "agent": agent,
        "output": f"<github-review by {login} state={state or 'NONE'}>",
        "output_present": True,
        "receipt": f"<github-review:{login}>",
        "receipt_present": True,
        "receipt_valid": True,
        "receipt_error": "",
        "receipt_status": "ok",
        "exit_code": 0,
        "timed_out": False,
        "timeout_s": None,
        "duration_s": None,
        "verdict": _github_review_verdict(state),
        "source": "github_review",
        "github_login": login,
        "github_state": state,
        "github_commit": _review_commit(latest),
    }


def resolve_agent_review_status(
    out_dir: Path,
    agent: str,
    *,
    repo: str = "",
    pr_number: int = 0,
    base_sha: str = "",
    pr_reviews: list[dict[str, Any]],
    accept_github_reviews: bool,
    human_approved: bool = False,
    head_sha: str = "",
) -> dict[str, Any]:
    """Local receipt first; if it is absent and accept_github_reviews is on, fall
    back to a trusted native GitHub review OF THE CURRENT HEAD as the receipt SOURCE."""
    local = load_agent_review_status(
        out_dir,
        agent,
        repo=repo,
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
    )
    local.setdefault("source", "local")
    if not accept_github_reviews:
        return local
    # Bridge ONLY when the local artifacts are genuinely ABSENT. A present local
    # receipt — even a negative one (REQUEST_CHANGES / timeout / invalid JSON) —
    # is authoritative and must never be overridden by a GitHub review. The
    # bridge is an additive SOURCE for a missing receipt, not a bypass.
    if local.get("output_present") or local.get("receipt_present"):
        return local
    gh = github_review_status(agent, pr_reviews, head_sha=head_sha)
    if gh is not None and not agent_review_blockers(gh, human_approved=human_approved):
        return gh
    return local  # no trusted GitHub review of this head; keep local so its blockers surface


def run_agent_process(
    command: list[str],
    prompt: str,
    env: dict[str, str],
    *,
    timeout_s: float,
    kill_grace_s: float,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        return {
            "status": "spawn_failed",
            "exit_code": 127,
            "raw_return_code": 127,
            "timed_out": False,
            "killed": "none",
            "stdout": "",
            "stderr": str(exc),
            "duration_s": round(time.monotonic() - started, 3),
        }

    try:
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout_s)
        code = proc.returncode
        status = "completed" if code == 0 else "failed"
        timed_out = False
        killed = "none"
        raw_return_code = code
    except subprocess.TimeoutExpired:
        timed_out = True
        status = "timeout"
        killed = "term"
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=kill_grace_s)
        except subprocess.TimeoutExpired:
            killed = "kill"
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
        raw_return_code = proc.returncode
        code = 124

    return {
        "status": status,
        "exit_code": code,
        "raw_return_code": raw_return_code,
        "timed_out": timed_out,
        "killed": killed,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "duration_s": round(time.monotonic() - started, 3),
    }


def trim_log(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]...\n"


def render_agent_failure_review(
    agent: str,
    *,
    reason: str,
    command: list[str],
    timeout_s: float,
    duration_s: float,
    stdout: str,
    stderr: str,
) -> str:
    return "\n".join(
        [
            "## Verdict",
            "BLOCKED",
            "",
            "## Findings",
            f"1. **BLOCKER**: {agent} review did not complete cleanly. Reason: `{reason}`.",
            f"   Command: `{' '.join(shlex.quote(part) for part in command)}`.",
            f"   Timeout: `{timeout_s}s`; duration: `{duration_s}s`.",
            "",
            "## Missing Tests Or Proof",
            "- A complete reviewer artifact with an explicit `APPROVE`, `REQUEST_CHANGES`, `BLOCKED`, or `NEEDS_HUMAN` verdict.",
            "",
            "## Merge Conditions",
            "- Re-run the reviewer successfully and regenerate `MERGE_GATE.md`.",
            "",
            "## Captured Stdout",
            "",
            "```text",
            trim_log(stdout).strip(),
            "```",
            "",
            "## Captured Stderr",
            "",
            "```text",
            trim_log(stderr).strip(),
            "```",
            "",
        ]
    )


def build_gate(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = latest_or_arg_packet(args)
    original = load_json(out_dir / "FACTS.json")
    current_pr = fetch_pr_view(args.pr)
    repo = repo_name()
    current_threads = fetch_review_threads(args.pr, repo)
    current_classification = classify_pr(current_pr)
    current_coherence = coherence_results(
        current_pr.get("body") or "", comments=fetch_pr_comments(args.pr)
    )
    current_ci_truth = ci_truth_for_pr(current_pr, args)

    blockers: list[str] = []
    warnings: list[str] = []
    head_sha = str(current_pr.get("headRefOid") or "")
    base_sha = str(current_pr.get("baseRefOid") or "")
    packet_pr_raw = original.get("pr")
    packet_pr = packet_pr_raw if isinstance(packet_pr_raw, dict) else {}
    packet_repo = str(original.get("repo") or "")
    packet_pr_number = packet_pr.get("number")
    packet_head = str(packet_pr.get("headRefOid") or "")
    packet_base = str(packet_pr.get("baseRefOid") or "")
    packet_review_merge_base = ""
    live_review_merge_base = ""
    reused_review_range = False

    if current_pr.get("number") != args.pr:
        blockers.append("current PR number is missing or mismatched")
    if packet_repo != repo:
        blockers.append("packet repository is missing or mismatched")
    if packet_pr_number != args.pr:
        blockers.append("packet PR number is missing or mismatched")
    if not head_sha:
        blockers.append("current PR does not expose its head SHA")
    elif not valid_commit_oid(head_sha):
        blockers.append("current PR head SHA is not a full commit OID")
    if not base_sha:
        blockers.append("current PR does not expose its base SHA")
    elif not valid_commit_oid(base_sha):
        blockers.append("current PR base SHA is not a full commit OID")
    if not packet_head:
        blockers.append("packet does not record its head SHA")
    elif not valid_commit_oid(packet_head):
        blockers.append("packet head SHA is not a full commit OID")
    elif valid_commit_oid(head_sha) and packet_head != head_sha:
        blockers.append(
            f"stale packet: packet head {packet_head} != current head {head_sha}"
            " — rebuild the packet at the current head"
        )
    if not packet_base:
        blockers.append("packet does not record its base SHA")
    elif not valid_commit_oid(packet_base):
        blockers.append("packet base SHA is not a full commit OID")
    elif (
        valid_commit_oid(base_sha)
        and valid_commit_oid(head_sha)
        and packet_base != base_sha
    ):
        try:
            packet_review_merge_base = fetch_review_merge_base(
                repo, packet_base, head_sha
            )
            live_review_merge_base = fetch_review_merge_base(repo, base_sha, head_sha)
        except Exception as exc:
            blockers.append(
                "cannot prove unchanged review range after base change "
                f"({exc}) — rebuild the packet at the current base"
            )
        else:
            if packet_review_merge_base != live_review_merge_base:
                blockers.append(
                    "review range changed after base change: packet merge base "
                    f"{packet_review_merge_base} != live merge base "
                    f"{live_review_merge_base} — rebuild the packet and reviews"
                )
            else:
                reused_review_range = True
                warnings.append(
                    f"base changed from packet base {packet_base} to {base_sha}; "
                    f"unchanged review merge base {live_review_merge_base} permits "
                    "receipt reuse, while live risk and merge authority use the "
                    "current base"
                )
    if current_pr.get("isDraft"):
        blockers.append("PR is draft")
    if current_classification["mergeable"] != "MERGEABLE":
        blockers.append(f"mergeable={current_classification['mergeable']}")
    if current_classification["checks"]["failing"]:
        warnings.append(
            "reported failing checks: "
            f"{', '.join(current_classification['checks']['failing'])}; "
            "only CI Truth required contexts carry merge authority"
        )
    if current_classification["checks"]["pending"]:
        warnings.append(
            "reported pending checks: "
            f"{', '.join(current_classification['checks']['pending'])}; "
            "only CI Truth required contexts carry merge authority"
        )
    if current_classification["reviewDecision"] == "CHANGES_REQUESTED":
        blockers.append("GitHub review decision is CHANGES_REQUESTED")
    if not current_coherence["ok"]:
        blockers.append("Coherence Delta fields missing or placeholder")
    blockers.extend(current_ci_truth.get("merge_blockers", []))
    warnings.extend(current_ci_truth.get("warnings", []))
    pr_labels = [
        str((label or {}).get("name") or "").lower()
        for label in (current_pr.get("labels") or [])
        if isinstance(label, dict)
    ]
    is_bot_pr = BOT_PR_LABEL in pr_labels
    bot_pr_waivers: list[str] = []

    unresolved_raw = current_threads.get("unresolved")
    unresolved_count = current_threads.get("unresolved_count")
    thread_state_ok = (
        current_threads.get("ok") is True
        and isinstance(unresolved_raw, list)
        and type(unresolved_count) is int
        and unresolved_count == len(unresolved_raw)
    )
    if not thread_state_ok:
        detail = str(current_threads.get("error") or "incomplete thread result")
        blockers.append(f"cannot verify complete review-thread state ({detail})")
        unresolved_count = None
    blocking_unresolved_count = unresolved_count if thread_state_ok else None
    if is_bot_pr and blocking_unresolved_count:
        warnings.append(
            "native conversation-resolution policy does not waive unresolved "
            "threads on bot-pr pull requests"
        )
    if blocking_unresolved_count:
        blockers.append(f"{blocking_unresolved_count} unresolved review threads")

    required_reviewers = required_reviewer_agents(args)
    if is_bot_pr and required_reviewers:
        bot_pr_waivers.append(
            "bot-pr: waived required reviewer receipts "
            f"({', '.join(required_reviewers)}) — trusted automation merges when green"
        )
        required_reviewers = []
    accept_github_reviews = getattr(args, "accept_github_reviews", False)
    pr_reviews = (
        fetch_pr_reviews(args.pr)
        if accept_github_reviews and required_reviewers and valid_commit_oid(head_sha)
        else []
    )
    review_statuses = {
        agent: resolve_agent_review_status(
            out_dir,
            agent,
            repo=repo,
            pr_number=args.pr,
            base_sha=packet_base,
            pr_reviews=pr_reviews,
            accept_github_reviews=accept_github_reviews,
            human_approved=args.human_approved,
            head_sha=head_sha,
        )
        for agent in required_reviewers
    }
    backup_statuses = {
        agent: resolve_agent_review_status(
            out_dir,
            agent,
            repo=repo,
            pr_number=args.pr,
            base_sha=packet_base,
            pr_reviews=pr_reviews,
            accept_github_reviews=accept_github_reviews,
            human_approved=args.human_approved,
            head_sha=head_sha,
        )
        for agent in backup_reviewer_agents(args)
    }
    claude_blockers: list[str] = []
    for agent, status in review_statuses.items():
        agent_blockers = agent_review_blockers(
            status, human_approved=args.human_approved
        )
        if agent == "claude":
            claude_blockers = agent_blockers
        else:
            blockers.extend(agent_blockers)

    backup_policy = {
        "enabled": bool(getattr(args, "allow_backup_reviewer", False)),
        "reason": getattr(args, "backup_reviewer_reason", "") or "",
        "replaces": "claude",
        "reviewers": list(backup_statuses),
        "accepted_reviewer": "",
        "claude_blockers": claude_blockers,
    }
    if "claude" not in review_statuses:
        backup_policy["status"] = "not_applicable"
    elif not claude_blockers:
        backup_policy["status"] = "not_needed"
    elif not backup_policy["enabled"]:
        backup_policy["status"] = "disabled"
        blockers.extend(claude_blockers)
    else:
        accepted_backup = ""
        for agent, status in backup_statuses.items():
            if not agent_review_blockers(status, human_approved=args.human_approved):
                accepted_backup = agent
                break
        if not accepted_backup:
            backup_policy["status"] = "missing_or_blocked"
            blockers.extend(claude_blockers)
            blockers.append("no acceptable backup reviewer receipt present")
        elif not backup_policy["reason"]:
            backup_policy["status"] = "missing_reason"
            blockers.append("backup reviewer requires --backup-reviewer-reason")
        else:
            backup_policy["status"] = "accepted"
            backup_policy["accepted_reviewer"] = accepted_backup
            warnings.append(
                f"Claude review unavailable; accepted {review_label(accepted_backup)} backup reviewer because: {backup_policy['reason']}"
            )

    # Risk is recomputed from an immutable base/head commit pair — never from
    # the mutable pull-files endpoint or the packet snapshot. A separate PR
    # view followed by a branch-relative files read admits an A→B→A race, so
    # the comparison itself is addressed only by the captured commit OIDs.
    current_files = None
    current_risk: dict[str, Any] = {"level": "UNKNOWN", "files_changed": None}
    if valid_commit_oid(base_sha) and valid_commit_oid(head_sha):
        try:
            current_files = fetch_pr_files_at_revision(repo, base_sha, head_sha)
            current_risk = risk_from_files(current_files)
        except Exception as exc:
            blockers.append(
                "cannot fetch immutable current PR files to recompute risk "
                f"({exc}) — fail closed"
            )
    if current_files is not None:
        if current_risk["level"] in {"HIGH", "CRITICAL"} and not args.human_approved:
            blockers.append(f"{current_risk['level']} risk requires --human-approved")

    original_risk = original.get("risk", {}).get("level", "UNKNOWN")
    if original_risk != current_risk["level"]:
        warnings.append(
            f"risk drift: packet recorded {original_risk}, "
            f"current head computes {current_risk['level']}"
        )
    if current_classification["checks"]["unknown"]:
        warnings.append(
            f"unknown checks: {', '.join(current_classification['checks']['unknown'])}"
        )
    if bot_pr_waivers:
        warnings.extend(bot_pr_waivers)

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
        "ci_truth": current_ci_truth,
        "required_reviewers": required_reviewers,
        "accept_github_reviews": accept_github_reviews,
        "review_sources": {
            agent: status.get("source", "local")
            for agent, status in review_statuses.items()
        },
        "head_sha": head_sha,
        "base_sha": base_sha,
        "review_threads": {
            "ok": current_threads.get("ok"),
            "unresolved_count": unresolved_count,
            "unresolved_outdated_count": current_threads.get(
                "unresolved_outdated_count"
            ),
            "blocking_unresolved_count": blocking_unresolved_count,
        },
        "bot_pr": {
            "is_bot_pr": is_bot_pr,
            "label": BOT_PR_LABEL,
            "waivers": bot_pr_waivers,
            "advisory_review_bots": sorted(ADVISORY_REVIEW_BOTS),
        },
        "review_receipts": review_statuses,
        "backup_review_receipts": backup_statuses,
        "backup_review_policy": backup_policy,
        "risk": current_risk,
        "risk_snapshot": {"base_sha": base_sha, "head_sha": head_sha},
        "review_snapshot": {"base_sha": packet_base, "head_sha": packet_head},
        "review_range": {
            "packet_base_sha": packet_base,
            "live_base_sha": base_sha,
            "head_sha": head_sha,
            "packet_merge_base_sha": packet_review_merge_base,
            "live_merge_base_sha": live_review_merge_base,
            "reused_after_base_change": reused_review_range,
        },
        # Live policy does not currently prove a strict/up-to-date base CAS.
        # Keep gate evaluation useful, but prohibit merge execution until the
        # canonical policy consumer can set this from enforced repository state.
        "base_cas_enforced": False,
        "packet_risk": original.get("risk", {}),
        "packet_head": packet_head,
        "packet_base": packet_base,
    }


def render_gate_markdown(gate: dict[str, Any]) -> str:
    lines = [
        f"# PR #{gate['pr']} Merge Gate",
        "",
        f"- Generated: `{gate['generated_at']}`",
        f"- Decision: `{gate['decision']}`",
        f"- Packet: `{gate['packet_dir']}`",
        f"- Risk: `{gate.get('risk', {}).get('level', 'UNKNOWN')}`",
        f"- Required reviewers: `{', '.join(gate.get('required_reviewers', []))}`",
        f"- CI Truth: `{gate.get('ci_truth', {}).get('verdict', 'UNKNOWN')}`",
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
    ci_truth = gate.get("ci_truth") or {}
    lines.extend(["", "## CI Truth", ""])
    if ci_truth:
        lines.append(f"- Verdict: `{ci_truth.get('verdict')}`")
        lines.append(
            f"- Observed checks: `{ci_truth.get('observed_total')}` latest / `{ci_truth.get('raw_total')}` raw"
        )
        if ci_truth.get("merge_blockers"):
            lines.extend(
                f"- Required blocker: {blocker}"
                for blocker in ci_truth["merge_blockers"]
            )
        else:
            lines.append("- Required blockers: none")
        if ci_truth.get("warnings"):
            lines.extend(f"- Warning: {warning}" for warning in ci_truth["warnings"])
    else:
        lines.append("- not evaluated")
    lines.extend(["", "## Review Receipts", ""])
    receipts = gate["review_receipts"]
    for agent in receipts:
        status = receipts[agent]
        label = review_label(agent)
        lines.append(
            f"- {label}: output=`{status['output']}` output_present={status['output_present']} "
            f"receipt=`{status['receipt']}` receipt_present={status['receipt_present']} "
            f"receipt_status={status['receipt_status']} exit={status['exit_code']} "
            f"timed_out={status['timed_out']} verdict={status['verdict']}"
        )
    backup_policy = gate.get("backup_review_policy") or {}
    backup_receipts = gate.get("backup_review_receipts") or {}
    if backup_receipts:
        lines.extend(["", "## Backup Review Receipts", ""])
        lines.append(
            f"- Policy: enabled={backup_policy.get('enabled')} status={backup_policy.get('status')} "
            f"accepted={backup_policy.get('accepted_reviewer') or '-'}"
        )
        if backup_policy.get("reason"):
            lines.append(f"- Reason: {backup_policy['reason']}")
        for agent, status in backup_receipts.items():
            label = review_label(agent)
            lines.append(
                f"- {label}: output=`{status['output']}` output_present={status['output_present']} "
                f"receipt=`{status['receipt']}` receipt_present={status['receipt_present']} "
                f"receipt_status={status['receipt_status']} exit={status['exit_code']} "
                f"timed_out={status['timed_out']} verdict={status['verdict']}"
            )
    lines.append("")
    return "\n".join(lines)


def render_github_comment(
    packet: dict[str, Any],
    gate: dict[str, Any] | None,
    merge_receipt: dict[str, Any] | None = None,
) -> str:
    pr = packet["pr"]
    classification = packet["classification"]
    risk = (gate or {}).get("risk") or packet.get("risk") or {}
    packet_risk = (gate or {}).get("packet_risk") or packet.get("risk") or {}
    coherence = packet["coherence"]
    decision = gate.get("decision") if gate else "PACKET_ONLY"
    blockers = gate.get("blockers", []) if gate else []
    warnings = gate.get("warnings", []) if gate else []
    ci_truth = (gate or packet).get("ci_truth", {})

    def risk_summary(value: dict[str, Any]) -> str:
        level = str(value.get("level") or "UNKNOWN")
        counts = (
            value.get("files_changed"),
            value.get("additions"),
            value.get("deletions"),
        )
        if any(item is None for item in counts):
            return f"`{level}` (counts unavailable)"
        files_changed, additions, deletions = counts
        return f"`{level}` ({files_changed} files, +{additions}/-{deletions})"

    lines = [
        "<!-- dharma-pr-review-control:auto -->",
        "## Merge Master Mike / Dharma PR Review Control",
        "",
        f"- PR: `#{pr['number']}`",
        f"- Decision: `{decision}`",
        f"- Queue status: `{classification['status']}`",
        f"- Mergeable: `{classification['mergeable']}`",
        f"- Risk: {risk_summary(risk)}",
        *(
            [f"- Packet risk (historical): {risk_summary(packet_risk)}"]
            if gate is not None
            else []
        ),
        f"- CI Truth: `{ci_truth.get('verdict', 'UNKNOWN')}`",
        f"- Coherence Delta: `{'pass' if coherence['ok'] else 'fail'}`",
        "- Authority: `conditional_merge_after_clean_gate`",
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
    if merge_receipt:
        lines.extend(
            [
                "",
                "### Merge Request",
                "",
                f"- Status: `{merge_receipt.get('status')}`",
                f"- Reason: {merge_receipt.get('reason')}",
                f"- Method: `{merge_receipt.get('method')}`",
                f"- Auto-merge: `{merge_receipt.get('auto')}`",
            ]
        )
        if merge_receipt.get("exit_code") is not None:
            lines.append(f"- Exit code: `{merge_receipt.get('exit_code')}`")
    required_reviewers = (
        gate.get("required_reviewers", []) if gate else list(DEFAULT_REQUIRED_REVIEWERS)
    )
    lines.extend(
        [
            "",
            "### Authority Boundary",
            "",
            "- GitHub Action Mike may create packets, run deterministic gates, post this status comment, and run `gh pr merge --auto` only when explicitly asked to `merge when clean`.",
            "- Mike may not approve PRs, push code, mark human approval, resolve review threads, or bypass branch protection.",
            "- Branch protection and GitHub auto-merge remain enforcement layers after Mike's gate.",
            "",
            "### Required Review Receipts",
            "",
        ]
    )
    for reviewer in required_reviewers:
        lines.append(f"- `{reviewer}_review.md` plus `{reviewer}_review_receipt.json`")
    lines.extend(
        [
            "",
            "### Local Commands",
            "",
            "```bash",
            f"make pr-packet PR={pr['number']}",
            f"make pr-gate PR={pr['number']}",
            f'make pr-merge PR={pr["number"]} ARGS="--confirm automerge-policy-pass-{pr["number"]}"',
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def gh_merge_command(
    pr_number: int,
    *,
    method: str = "squash",
    auto: bool = True,
    match_head_commit: str = "",
    repo: str = "",
) -> list[str]:
    cmd = ["gh", "pr", "merge", str(pr_number), f"--{method}", "--delete-branch"]
    if auto:
        cmd.insert(4, "--auto")
    if repo:
        cmd.extend(["--repo", repo])
    if match_head_commit:
        cmd.extend(["--match-head-commit", match_head_commit])
    return cmd


def run_mike_merge_authority(
    *,
    pr_number: int,
    gate: dict[str, Any],
    method: str,
    auto: bool,
    runner: Callable[..., CommandResult] = run,
    pr_fetcher: Callable[[int], dict[str, Any]] = fetch_pr_view,
) -> dict[str, Any]:
    match_head_commit = str(gate.get("head_sha") or "")
    gate_base_commit = str(gate.get("base_sha") or "")
    gate_repo = str(gate.get("repo") or "")
    command = (
        gh_merge_command(
            pr_number,
            method=method,
            auto=auto,
            match_head_commit=match_head_commit,
            repo=gate_repo,
        )
        if valid_commit_oid(match_head_commit)
        else []
    )
    receipt: dict[str, Any] = {
        "schema": "dharma.pr_review.mike_merge_receipt.v1",
        "generated_at": utc_now(),
        "agent_uid": "merge_master_mike",
        "authority": "conditional_merge",
        "pr": pr_number,
        "method": method,
        "auto": auto,
        "gate_decision": gate.get("decision"),
        "gate_packet_dir": gate.get("packet_dir"),
        "head_sha": match_head_commit,
        "base_sha": gate_base_commit,
        "base_cas_enforced": gate.get("base_cas_enforced") is True,
        "required_reviewers": gate.get("required_reviewers", []),
        "risk": gate.get("risk", {}),
        "command": command,
        "status": "SKIPPED",
        "reason": "gate decision is not MERGE_CANDIDATE",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }
    if gate.get("decision") != "MERGE_CANDIDATE":
        receipt["blockers"] = gate.get("blockers", [])
        return receipt
    if not valid_commit_oid(match_head_commit):
        receipt["reason"] = "gate head SHA is missing or invalid"
        receipt["blockers"] = ["merge authority requires a full head commit OID"]
        return receipt
    if not valid_commit_oid(gate_base_commit):
        receipt["reason"] = "gate base SHA is missing or invalid"
        receipt["blockers"] = ["merge authority requires a full base commit OID"]
        return receipt
    if gate.get("pr") != pr_number:
        receipt["reason"] = "gate PR binding is missing or mismatched"
        receipt["blockers"] = ["merge authority requires the exact PR binding"]
        return receipt
    if not gate_repo or gate_repo.count("/") != 1:
        receipt["reason"] = "gate repository binding is missing or invalid"
        receipt["blockers"] = ["merge authority requires an explicit repository"]
        return receipt
    if gate.get("blockers"):
        receipt["reason"] = "candidate gate still records blockers"
        receipt["blockers"] = list(gate.get("blockers") or [])
        return receipt
    risk_snapshot = gate.get("risk_snapshot")
    if not isinstance(risk_snapshot, dict) or (
        risk_snapshot.get("base_sha") != gate_base_commit
        or risk_snapshot.get("head_sha") != match_head_commit
    ):
        receipt["reason"] = "gate risk snapshot is missing or mismatched"
        receipt["blockers"] = [
            "merge authority requires risk computed for the exact base/head pair"
        ]
        return receipt
    if gate.get("base_cas_enforced") is not True:
        receipt["reason"] = "strict base-CAS enforcement is not proven"
        receipt["blockers"] = [
            "merge execution is prohibited until canonical policy proves "
            "strict/up-to-date base enforcement"
        ]
        return receipt
    try:
        live_pr = pr_fetcher(pr_number)
    except Exception as exc:
        receipt["reason"] = "cannot refresh PR binding before merge"
        receipt["blockers"] = [f"live PR refresh failed: {exc}"]
        return receipt
    live_base = str(live_pr.get("baseRefOid") or "")
    live_head = str(live_pr.get("headRefOid") or "")
    live_number = live_pr.get("number")
    if (
        live_number != pr_number
        or live_base != gate_base_commit
        or live_head != match_head_commit
    ):
        receipt["reason"] = "live PR binding changed after gate evaluation"
        receipt["blockers"] = [
            "merge authority requires a fresh gate for the current PR/base/head"
        ]
        return receipt

    result = runner(command, timeout=300, check=False)
    receipt["exit_code"] = result.code
    receipt["stdout"] = result.stdout[-4000:]
    receipt["stderr"] = result.stderr[-4000:]
    if result.code == 0:
        receipt["status"] = "MERGE_COMMAND_ACCEPTED"
        receipt["reason"] = "gh pr merge accepted the conditional merge command"
    else:
        receipt["status"] = "MERGE_COMMAND_FAILED"
        receipt["reason"] = "gh pr merge returned non-zero"
    return receipt


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
    merge_path = out_dir / "MIKE_MERGE_RECEIPT.json"
    merge_receipt = load_json(merge_path) if merge_path.exists() else None
    comment = render_github_comment(packet, gate, merge_receipt)
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
    claude_auth_ready = bool(
        isinstance(claude_payload, dict) and claude_payload.get("loggedIn")
    )
    claude_probe: dict[str, Any] | None = None
    if args.live_probe:
        probe = run_agent_process(
            claude_command,
            "Reply with OK only.",
            claude_env,
            timeout_s=args.probe_timeout_s,
            kill_grace_s=DEFAULT_AGENT_KILL_GRACE_S,
        )
        claude_probe = {
            "status": probe["status"],
            "exit_code": probe["exit_code"],
            "timed_out": probe["timed_out"],
            "duration_s": probe["duration_s"],
            "stdout_excerpt": trim_log(probe["stdout"], 500),
            "stderr_excerpt": trim_log(probe["stderr"], 500),
        }

    result = {
        "schema": "dharma.pr_review.reviewers.v1",
        "generated_at": utc_now(),
        "claude": {
            "command": claude_command,
            "anthropic_credential_env_scrubbed": "ANTHROPIC_API_KEY" not in claude_env,
            "auth_status_exit": claude_proc.returncode,
            "auth_status": claude_payload,
            "auth_ready": claude_auth_ready,
            "live_probe": claude_probe,
            "ready": claude_auth_ready
            and (claude_probe is None or claude_probe["exit_code"] == 0),
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
    print(
        f"Claude credential env scrubbed: {result['claude']['anthropic_credential_env_scrubbed']}"
    )
    print(f"Claude auth ready: {result['claude']['auth_ready']}")
    if claude_probe is None:
        print(
            "Claude live probe: not run (use ARGS='--live-probe' to check quota/runtime)"
        )
    else:
        print(
            f"Claude live probe: status={claude_probe['status']} "
            f"exit={claude_probe['exit_code']} timed_out={claude_probe['timed_out']}"
        )
        probe_output = (
            claude_probe["stdout_excerpt"] or claude_probe["stderr_excerpt"]
        ).strip()
        if probe_output:
            print(f"Claude live probe output: {probe_output}")
    if isinstance(claude_payload, dict):
        print(f"Claude auth: {json.dumps(claude_payload, sort_keys=True)}")
    else:
        print("Claude auth: unavailable")
    print(f"Codex command: {' '.join(codex_command)}")
    print(f"Codex ready: {result['codex']['ready']}")
    return 0 if result["claude"]["ready"] else 2


def cmd_merge(args: argparse.Namespace) -> int:
    # Operator ruling 2026-07-29 (docs/ops/OPERATOR_RULING_2026-07-29_
    # AUTO_WITH_DECORRELATED_REVIEW.md): the old merge-pr-{N} token claimed
    # operator consent it never received (CI synthesized it from the PR
    # number). automerge-policy-pass-{N} is honest: it asserts machine policy
    # plus decorrelated review verdicts, and claims nothing about the
    # operator.
    expected = f"automerge-policy-pass-{args.pr}"
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
        command = gh_merge_command(
            args.pr,
            method=args.method,
            auto=args.auto,
            match_head_commit=str(gate.get("head_sha") or ""),
            repo=str(gate.get("repo") or ""),
        )
        print(f"dry_run=true command={' '.join(shlex.quote(part) for part in command)}")
        write_json(
            out_dir / "MIKE_MERGE_RECEIPT.json",
            {
                "schema": "dharma.pr_review.mike_merge_receipt.v1",
                "generated_at": utc_now(),
                "agent_uid": "merge_master_mike",
                "authority": "conditional_merge",
                "pr": args.pr,
                "method": args.method,
                "auto": args.auto,
                "gate_decision": gate.get("decision"),
                "head_sha": gate.get("head_sha", ""),
                "required_reviewers": gate.get("required_reviewers", []),
                "status": "DRY_RUN",
                "command": command,
            },
        )
        return 0
    merge_receipt = run_mike_merge_authority(
        pr_number=args.pr,
        gate=gate,
        method=args.method,
        auto=args.auto,
    )
    write_json(out_dir / "MIKE_MERGE_RECEIPT.json", merge_receipt)
    print(
        f"merge_status={merge_receipt['status']} pr={args.pr} method={args.method} auto={args.auto}"
    )
    return 0 if merge_receipt["status"] == "MERGE_COMMAND_ACCEPTED" else 2


def load_review_packet_binding(
    out_dir: Path,
    *,
    expected_pr_number: int,
    expected_repo: str = "",
) -> dict[str, Any]:
    """Load the immutable receipt bindings from one review packet."""

    facts = load_json(out_dir / "FACTS.json")
    if not isinstance(facts, dict):
        raise PRControlError("review packet facts must be a JSON object")
    facts_pr_value = facts.get("pr")
    facts_pr = facts_pr_value if isinstance(facts_pr_value, dict) else {}
    facts_repo = str(facts.get("repo") or "")
    facts_pr_number = facts_pr.get("number")
    facts_head = str(facts_pr.get("headRefOid") or "")
    facts_base = str(facts_pr.get("baseRefOid") or "")
    repo_parts = facts_repo.split("/")
    if len(repo_parts) != 2 or not all(repo_parts):
        raise PRControlError("review packet repository binding is missing or invalid")
    if expected_repo and facts_repo != expected_repo:
        raise PRControlError("review packet repository binding is mismatched")
    if facts_pr_number != expected_pr_number:
        raise PRControlError("review packet PR binding is missing or mismatched")
    if not valid_commit_oid(facts_head) or not valid_commit_oid(facts_base):
        raise PRControlError("review packet requires full base and head commit OIDs")
    return {
        "repo": facts_repo,
        "pr_number": expected_pr_number,
        "head_sha": facts_head,
        "base_sha": facts_base,
    }


def cmd_run_agent(args: argparse.Namespace) -> int:
    out_dir = latest_or_arg_packet(args)
    binding = load_review_packet_binding(
        out_dir,
        expected_pr_number=args.pr,
    )
    facts_repo = binding["repo"]
    facts_head = binding["head_sha"]
    facts_base = binding["base_sha"]
    evidence_snapshot = read_review_evidence_snapshot(out_dir)
    evidence_digest = review_evidence_digest(evidence_snapshot)
    prompt_path = review_prompt_path(out_dir, args.agent)
    prompt = render_agent_prompt(
        review_prompt_label(args.agent),
        out_dir / "REVIEW_PACKET.md",
        args.pr,
        evidence_snapshot=evidence_snapshot,
    )
    prompt_bytes = prompt.encode("utf-8")
    write_text(prompt_path, prompt)
    command, env = review_command_and_env(args.agent)
    timeout_s = (
        args.timeout_s
        if args.timeout_s is not None
        else env_float("DHARMA_PR_REVIEW_TIMEOUT_S", DEFAULT_AGENT_TIMEOUT_S)
    )
    kill_grace_s = (
        args.kill_grace_s
        if args.kill_grace_s is not None
        else DEFAULT_AGENT_KILL_GRACE_S
    )
    result = run_agent_process(
        command,
        prompt,
        env,
        timeout_s=timeout_s,
        kill_grace_s=kill_grace_s,
    )
    try:
        post_review_evidence_digest = review_evidence_sha256(out_dir)
    except PRControlError:
        post_review_evidence_digest = ""
    raw_output = (result["stdout"] or result["stderr"]).strip()
    exit_code = int(result["exit_code"])
    if post_review_evidence_digest != evidence_digest:
        result["status"] = "evidence_changed"
        exit_code = 2
        result["exit_code"] = exit_code
        review_text = render_agent_failure_review(
            args.agent,
            reason="evidence_changed",
            command=command,
            timeout_s=timeout_s,
            duration_s=result["duration_s"],
            stdout=result["stdout"],
            stderr=result["stderr"],
        )
    elif result["timed_out"] or result["status"] == "spawn_failed":
        review_text = render_agent_failure_review(
            args.agent,
            reason=result["status"],
            command=command,
            timeout_s=timeout_s,
            duration_s=result["duration_s"],
            stdout=result["stdout"],
            stderr=result["stderr"],
        )
    elif len(raw_output) < 40:
        result["status"] = "empty_output"
        exit_code = 2
        result["exit_code"] = exit_code
        review_text = render_agent_failure_review(
            args.agent,
            reason="empty_output",
            command=command,
            timeout_s=timeout_s,
            duration_s=result["duration_s"],
            stdout=result["stdout"],
            stderr=result["stderr"],
        )
    else:
        review_text = raw_output

    output_path = review_output_path(out_dir, args.agent)
    write_text(output_path, review_text)
    output_digest = sha256_bytes(output_path.read_bytes())
    write_json(
        review_receipt_path(out_dir, args.agent),
        {
            "schema": "dharma.pr_review.agent_receipt.v1",
            "generated_at": utc_now(),
            "agent": args.agent,
            "repo": facts_repo,
            "pr": args.pr,
            "base_sha": facts_base,
            "head_sha": facts_head,
            "command": command,
            "status": result["status"],
            "exit_code": exit_code,
            "raw_return_code": result["raw_return_code"],
            "timed_out": result["timed_out"],
            "killed": result["killed"],
            "timeout_s": timeout_s,
            "kill_grace_s": kill_grace_s,
            "duration_s": result["duration_s"],
            "stdout_bytes": len(result["stdout"].encode("utf-8")),
            "stderr_bytes": len(result["stderr"].encode("utf-8")),
            "verdict": extract_review_verdict(review_text),
            "output": str(output_path),
            "output_sha256": output_digest,
            "prompt_sha256": sha256_bytes(prompt_bytes),
            "evidence_sha256": evidence_digest,
        },
    )
    print(
        f"agent={args.agent} status={result['status']} exit={exit_code} "
        f"timed_out={result['timed_out']} output={output_path}"
    )
    return exit_code


def parse_csv_tokens(value: str | None, *, default: tuple[str, ...]) -> list[str]:
    if not value:
        return list(default)
    if value.strip().lower() in {"none", "no-reviewers", "no_reviewers", "-"}:
        return []
    tokens = [item.strip() for item in value.split(",") if item.strip()]
    return tokens or list(default)


def required_reviewer_agents(args: argparse.Namespace) -> list[str]:
    raw = getattr(args, "required_reviewers", "") or os.environ.get(
        "DHARMA_PR_REQUIRED_REVIEWERS", ""
    )
    return parse_csv_tokens(raw, default=DEFAULT_REQUIRED_REVIEWERS)


def _nats_config(env: dict[str, str], *, require_devin_secrets: bool) -> NATSConfig:
    if not require_devin_secrets and env.get("NATS_URL"):
        endpoint = env.get("NATS_URL", "")
        return NATSConfig(
            endpoint=endpoint,
            user=env.get("NATS_USER", ""),
            credential=env.get("NATS_PASSWORD", ""),
            missing=(),
            ca_pem=_resolve_nats_ca_pem(env, "NATS_CA_PEM", endpoint=endpoint),
            tls_hostname=env.get("NATS_TLS_HOSTNAME", "").strip(),
            credential_family="direct",
        )

    mike_present = any(env.get(name) for name in MERGE_MASTER_MIKE_NATS_SECRET_NAMES)
    credential_family = "merge_master_mike" if mike_present else "devin"
    endpoint = (
        env.get("MERGE_MASTER_MIKE_NATS_URL")
        or env.get("DEVIN_NATS_URL")
        or env.get("DHARMA_NATS_URL")
        or env.get("NATS_URL")
        or ""
    )
    user = (
        env.get("MERGE_MASTER_MIKE_NATS_USER")
        or env.get("DEVIN_NATS_USER")
        or env.get("DHARMA_NATS_USER")
        or env.get("NATS_USER")
        or ""
    )
    auth_value = (
        env.get("MERGE_MASTER_MIKE_NATS_PW")
        or env.get("MERGE_MASTER_MIKE_NATS_PASSWORD")
        or env.get("DEVIN_NATS_PW")
        or env.get("DEVIN_NATS_PASSWORD")
        or env.get("DHARMA_NATS_PW")
        or env.get("DHARMA_NATS_PASSWORD")
        or env.get("NATS_PASSWORD")
        or ""
    )
    ca_pem = _resolve_nats_ca_pem(
        env,
        "MERGE_MASTER_MIKE_NATS_CA_PEM",
        "DEVIN_NATS_CA_PEM",
        "DHARMA_NATS_CA_PEM",
        "NATS_CA_PEM",
        endpoint=endpoint,
    )
    tls_hostname = (
        env.get("MERGE_MASTER_MIKE_NATS_TLS_HOSTNAME")
        or env.get("DEVIN_NATS_TLS_HOSTNAME")
        or env.get("DHARMA_NATS_TLS_HOSTNAME")
        or env.get("NATS_TLS_HOSTNAME")
        or ""
    )
    if require_devin_secrets:
        required_names = (
            MERGE_MASTER_MIKE_NATS_SECRET_NAMES
            if mike_present
            else DEVIN_NATS_SECRET_NAMES
        )
        missing = [name for name in required_names if not env.get(name)]
    else:
        missing = (
            []
            if endpoint
            else [
                "MERGE_MASTER_MIKE_NATS_URL or DEVIN_NATS_URL or DHARMA_NATS_URL or NATS_URL"
            ]
        )
    return NATSConfig(
        endpoint=endpoint,
        user=user,
        credential=auth_value,
        missing=tuple(missing),
        ca_pem=ca_pem,
        tls_hostname=tls_hostname.strip(),
        credential_family=credential_family,
    )


def _normalize_ca_pem(value: str) -> str:
    normalized = value.strip()
    if "\\n" in normalized and "\n" not in normalized:
        normalized = normalized.replace("\\n", "\n")
    return (
        normalized + "\n"
        if normalized and not normalized.endswith("\n")
        else normalized
    )


def _nats_url_is_tls(endpoint: str) -> bool:
    return urlsplit(endpoint.strip()).scheme.lower() in {"wss", "tls"}


def _resolve_nats_ca_pem(
    env: dict[str, str],
    *preferred_names: str,
    endpoint: str = "",
) -> str:
    for name in preferred_names:
        pem = env.get(name, "").strip()
        if pem:
            return _normalize_ca_pem(pem)
    if DEFAULT_NATS_CA_PEM_PATH.exists() and _nats_url_is_tls(endpoint):
        return _normalize_ca_pem(DEFAULT_NATS_CA_PEM_PATH.read_text(encoding="utf-8"))
    return ""


def _is_publish_permission_violation(message: str, subject: str) -> bool:
    lowered = message.lower()
    if "permissions violation" not in lowered or "publish" not in lowered:
        return False
    return (
        subject in message
        or f'publish to "{subject}"' in message
        or f"publish to {subject}" in message
    )


def _redacted_nats_config(config: NATSConfig) -> dict[str, Any]:
    return {
        "endpoint": config.endpoint,
        "has_user": bool(config.user),
        "has_auth_credential": bool(config.credential),
        "has_ca_pem": bool(config.ca_pem),
        "tls_hostname": config.tls_hostname,
        "tls_trust": "custom_ca_pem" if config.ca_pem else "system_ca_store",
        "credential_family": config.credential_family,
        "missing": list(config.missing),
    }


def _nats_tls_kwargs(config: NATSConfig) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if config.ca_pem:
        tls_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        tls_context.load_verify_locations(cadata=config.ca_pem)
        kwargs["tls"] = tls_context
    if config.tls_hostname:
        kwargs["tls_hostname"] = config.tls_hostname
    return kwargs


def _a2a_target_for_subject(subject: str) -> str:
    if subject == "dharma.a2a.fleet":
        return "fleet"
    if subject == "dharma.a2a.merge_master_mike":
        return "merge_master_mike"
    if subject == "dharma.a2a.github_copilot":
        return "github_copilot"
    if subject == "dharma.a2a.claude":
        return "claude"
    if subject == "dharma.a2a.devin":
        return "devin-roaming-2987d222"
    if subject == "dharma.a2a.codex":
        return "codex"
    if subject == "dharma.a2a.hermes":
        return "hermes"
    if subject == "dharma.a2a.perplexity":
        return "perplexity"
    return subject.rsplit(".", 1)[-1]


def _a2a_kind_for_subject(subject: str) -> str:
    if subject == "dharma.a2a.fleet":
        return "pr_janitor_session_start"
    if subject == "dharma.a2a.merge_master_mike":
        return "pr_janitor_mike_fanout"
    if subject == "dharma.a2a.github_copilot":
        return "pr_janitor_copilot_review_request"
    if subject == "dharma.a2a.claude":
        return "pr_janitor_claude_review_request"
    if subject == "dharma.a2a.devin":
        return "pr_janitor_devin_coordination_request"
    if subject == "dharma.a2a.codex":
        return "pr_janitor_codex_verification_request"
    if subject == "dharma.a2a.hermes":
        return "pr_janitor_hermes_witness_request"
    if subject == "dharma.a2a.perplexity":
        return "pr_janitor_perplexity_research_request"
    return "pr_janitor_coordination"


def build_a2a_fanout_messages(
    *,
    repo: str,
    run_id: str,
    queue_summary: dict[str, Any],
    selected: list[dict[str, Any]],
    processed: list[dict[str, Any]],
    fanout_dir: Path,
    subjects: list[str],
    required_reviewers: list[str],
    merge_mode: str,
    dry_run: bool,
    packet_only: bool,
) -> list[dict[str, Any]]:
    selected_prs = [
        {
            "number": item.get("number"),
            "status": item.get("status"),
            "title": item.get("title"),
            "url": item.get("url"),
        }
        for item in selected
    ]
    processed_prs = [
        {
            "number": item.get("number"),
            "status": item.get("status"),
            "gate_decision": item.get("gate_decision"),
            "blockers": item.get("blockers", []),
            "packet_dir": item.get("packet_dir"),
        }
        for item in processed
    ]
    common = {
        "schema_version": "dharma.pr_review.a2a_nats_session.v1",
        "timestamp": utc_now(),
        "from": "github_actions_merge_master_mike",
        "authority": "conditional_merge"
        if merge_mode == "auto-when-clean"
        else "external_worker_evidence_only",
        "repo": repo,
        "goal": (
            "collaborative PR queue synthesis; conditional merge authority when gate-clean"
            if merge_mode == "auto-when-clean"
            else "collaborative PR queue synthesis; no merge authority"
        ),
        "run_id": run_id,
        "dry_run": dry_run,
        "packet_only": packet_only,
        "merge_mode": merge_mode,
        "queue_counts": queue_summary.get("counts", {}),
        "queue_total": queue_summary.get("total"),
        "required_reviewers": required_reviewers,
        "agent_roster": [_a2a_target_for_subject(subject) for subject in subjects],
        "selected_prs": selected_prs,
        "processed_prs": processed_prs,
        "receipt_path": str(fanout_dir / "receipt.json"),
        "summary_path": str(fanout_dir / "summary.md"),
        "allowed_actions": [
            "inspect_pr_queue",
            "create_review_packets",
            "run_merge_gate",
            "write_receipts",
            "recommend_next_actions",
            "conditional_merge_after_clean_gate"
            if merge_mode == "auto-when-clean"
            else "no_merge",
        ],
        "forbidden_actions": [
            "unconditional_merge",
            "approve_prs",
            "push_code",
            "mark_human_approval",
            "resolve_review_threads",
            "bypass_governance",
        ],
    }
    return [
        {
            "subject": subject,
            "payload": {
                **common,
                "kind": _a2a_kind_for_subject(subject),
                "to": _a2a_target_for_subject(subject),
            },
        }
        for subject in subjects
    ]


async def _publish_a2a_messages_async(
    config: NATSConfig,
    messages: list[dict[str, Any]],
    timeout_s: float,
) -> list[dict[str, Any]]:
    import nats

    nc = await nats.connect(
        servers=[str(config.endpoint)],
        user=config.user or None,
        password=config.credential or None,
        connect_timeout=timeout_s,
        allow_reconnect=False,
        max_reconnect_attempts=0,
        **_nats_tls_kwargs(config),
    )
    try:
        js = nc.jetstream()
        rows: list[dict[str, Any]] = []
        for message in messages:
            data = json.dumps(message["payload"], sort_keys=True).encode("utf-8")
            ack = await js.publish(str(message["subject"]), data, timeout=timeout_s)
            rows.append(
                {
                    "subject": message["subject"],
                    "kind": message["payload"].get("kind"),
                    "to": message["payload"].get("to"),
                    "ack_verified": True,
                    "ack_tier": "JETSTREAM_PUB_ACK",
                    "stream": ack.stream,
                    "seq": ack.seq,
                }
            )
        return rows
    finally:
        await nc.close()


async def _publish_a2a_messages_with_deadline(
    config: NATSConfig,
    messages: list[dict[str, Any]],
    timeout_s: float,
) -> list[dict[str, Any]]:
    overall_timeout_s = timeout_s * max(len(messages) + 2, 2)
    return await asyncio.wait_for(
        _publish_a2a_messages_async(config, messages, timeout_s),
        timeout=overall_timeout_s,
    )


def default_a2a_nats_publisher(
    config: NATSConfig,
    messages: list[dict[str, Any]],
    timeout_s: float,
) -> list[dict[str, Any]]:
    return asyncio.run(_publish_a2a_messages_with_deadline(config, messages, timeout_s))


A2ANatsPublisher = Callable[
    [NATSConfig, list[dict[str, Any]], float], list[dict[str, Any]]
]


def publish_a2a_fanout_session(
    *,
    repo: str,
    run_id: str,
    queue_summary: dict[str, Any],
    selected: list[dict[str, Any]],
    processed: list[dict[str, Any]],
    fanout_dir: Path,
    subjects: list[str],
    required_reviewers: list[str],
    merge_mode: str,
    dry_run: bool,
    packet_only: bool,
    required: bool,
    timeout_s: float,
    env: dict[str, str] | None = None,
    publisher: A2ANatsPublisher = default_a2a_nats_publisher,
) -> dict[str, Any]:
    config = _nats_config(
        dict(env if env is not None else os.environ),
        require_devin_secrets=required,
    )
    messages = build_a2a_fanout_messages(
        repo=repo,
        run_id=run_id,
        queue_summary=queue_summary,
        selected=selected,
        processed=processed,
        fanout_dir=fanout_dir,
        subjects=subjects,
        required_reviewers=required_reviewers,
        merge_mode=merge_mode,
        dry_run=dry_run,
        packet_only=packet_only,
    )
    receipt: dict[str, Any] = {
        "schema": "dharma.pr_review.a2a_nats_receipt.v1",
        "generated_at": utc_now(),
        "repo": repo,
        "run_id": run_id,
        "required": required,
        "config": _redacted_nats_config(config),
        "subjects": subjects,
        "messages": messages,
        "status": "BLOCKED",
        "code": "NATS_NOT_ATTEMPTED",
        "ack_tier": "NONE",
        "acks": [],
    }
    if config.missing:
        receipt["code"] = (
            "NATS_SECRETS_MISSING" if required else "NATS_ENDPOINT_MISSING"
        )
        receipt["reason"] = f"missing NATS configuration: {', '.join(config.missing)}"
        return receipt

    try:
        acks = publisher(config, messages, timeout_s)
    except Exception as exc:
        receipt["code"] = "NATS_PUBLISH_FAILED"
        receipt["reason"] = f"{type(exc).__name__}: {exc}"
        return receipt

    receipt["acks"] = acks
    if acks and all(row.get("ack_verified") for row in acks):
        receipt["status"] = "OK"
        receipt["code"] = "NATS_ACK_VERIFIED"
        receipt["ack_tier"] = "JETSTREAM_PUB_ACK"
        receipt["reason"] = (
            "all A2A PR janitor messages received JetStream publish acks"
        )
    else:
        receipt["code"] = "NATS_ACK_FAILED"
        receipt["reason"] = (
            "one or more A2A PR janitor messages did not receive a verified ack"
        )
    return receipt


def select_fanout_items(
    summary: dict[str, Any],
    *,
    statuses: list[str],
    max_prs: int,
) -> list[dict[str, Any]]:
    """Pick the next PRs Mike can review without changing repository state."""

    status_rank = {status: index for index, status in enumerate(statuses)}
    candidates = [
        item for item in summary.get("items", []) if item.get("status") in status_rank
    ]
    candidates.sort(
        key=lambda item: (
            status_rank.get(str(item.get("status")), 999),
            str(item.get("updatedAt") or ""),
            int(item.get("number") or 0),
        )
    )
    return candidates[: max(0, max_prs)]


def latest_packet_dir_or_none(state_root: Path, pr_number: int) -> Path | None:
    base = state_root / f"pr-{pr_number}"
    if not base.exists():
        return None
    existing = sorted(path for path in base.glob("*") if path.is_dir())
    return existing[-1] if existing else None


def _queue_item_fingerprint(item: dict[str, Any]) -> dict[str, str]:
    return {
        "head_sha": str(item.get("head_sha") or item.get("headRefOid") or ""),
        "base_sha": str(item.get("base_sha") or item.get("baseRefOid") or ""),
        "updated_at": str(item.get("updatedAt") or ""),
        "status": str(item.get("status") or ""),
        "review_decision": str(item.get("reviewDecision") or "NONE"),
    }


def _packet_fingerprint(packet_dir_path: Path) -> dict[str, str] | None:
    try:
        facts = load_json(packet_dir_path / "FACTS.json")
    except (OSError, json.JSONDecodeError):
        return None
    pr = facts.get("pr") if isinstance(facts, dict) else {}
    classification = facts.get("classification") if isinstance(facts, dict) else {}
    if not isinstance(pr, dict) or not isinstance(classification, dict):
        return None
    return {
        "head_sha": str(pr.get("headRefOid") or ""),
        "base_sha": str(pr.get("baseRefOid") or ""),
        "updated_at": str(pr.get("updatedAt") or ""),
        "status": str(classification.get("status") or ""),
        "review_decision": str(classification.get("reviewDecision") or "NONE"),
    }


def _packet_gate_summary(packet_dir_path: Path) -> dict[str, Any] | None:
    try:
        gate = load_json(packet_dir_path / "MERGE_GATE.json")
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(gate, dict):
        return None
    blockers = gate.get("blockers") if isinstance(gate.get("blockers"), list) else []
    return {
        "decision": str(gate.get("decision") or ""),
        "blockers": [str(blocker) for blocker in blockers],
    }


def current_fanout_receipt_for_item(
    state_root: Path, item: dict[str, Any]
) -> dict[str, Any]:
    pr_number = int(item.get("number") or 0)
    packet_path = latest_packet_dir_or_none(state_root, pr_number)
    expected = _queue_item_fingerprint(item)
    result: dict[str, Any] = {
        "current": False,
        "number": pr_number,
        "head_sha": expected["head_sha"],
        "updatedAt": expected["updated_at"],
        "packet_dir": str(packet_path) if packet_path else "",
        "reason": "",
    }
    if not packet_path:
        result["reason"] = "no prior packet"
        return result
    if not (packet_path / "MERGE_GATE.json").exists():
        result["reason"] = "latest packet has no merge gate"
        return result
    gate = _packet_gate_summary(packet_path)
    if gate is None:
        result["reason"] = "latest packet merge gate unreadable"
        return result
    result["gate"] = gate
    if gate["decision"] != "MERGE_CANDIDATE":
        result["reason"] = f"latest merge gate is {gate['decision'] or 'UNKNOWN'}"
        return result
    if gate["blockers"]:
        result["reason"] = "latest merge gate still has blockers"
        return result
    observed = _packet_fingerprint(packet_path)
    if observed is None:
        result["reason"] = "latest packet facts unreadable"
        return result
    result["observed"] = observed
    if not expected["head_sha"]:
        result["reason"] = "queue item has no head SHA"
        return result
    stable_keys = ("head_sha", "base_sha", "updated_at", "status", "review_decision")
    if all(observed.get(key) == expected.get(key) for key in stable_keys):
        result["current"] = True
        result["reason"] = (
            "latest clean packet/gate already matches PR head, base, update time, queue status, and review decision"
        )
        return result
    result["reason"] = (
        "PR head, base, update time, queue status, or review decision changed since latest packet/gate"
    )
    return result


def select_fanout_plan(
    summary: dict[str, Any],
    *,
    statuses: list[str],
    max_prs: int,
    state_root: Path,
    skip_current: bool,
) -> dict[str, list[dict[str, Any]]]:
    if max_prs <= 0:
        return {"selected": [], "skipped_current": []}

    status_rank = {status: index for index, status in enumerate(statuses)}
    candidates = [
        item for item in summary.get("items", []) if item.get("status") in status_rank
    ]
    candidates.sort(
        key=lambda item: (
            status_rank.get(str(item.get("status")), 999),
            str(item.get("updatedAt") or ""),
            int(item.get("number") or 0),
        )
    )

    selected: list[dict[str, Any]] = []
    skipped_current: list[dict[str, Any]] = []
    for item in candidates:
        if skip_current:
            current = current_fanout_receipt_for_item(state_root, item)
            if current["current"]:
                skipped_current.append(
                    {
                        "number": item.get("number"),
                        "title": item.get("title"),
                        "status": item.get("status"),
                        "packet_dir": current.get("packet_dir", ""),
                        "head_sha": current.get("head_sha", ""),
                        "updatedAt": current.get("updatedAt", ""),
                        "reason": current.get("reason", ""),
                    }
                )
                continue
        selected.append(item)
        if len(selected) >= max(0, max_prs):
            break
    return {"selected": selected, "skipped_current": skipped_current}


def should_skip_current_fanout(args: argparse.Namespace) -> bool:
    return bool(
        not args.reprocess_current and args.packet_only and args.merge_mode == "off"
    )


def render_fanout_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Merge Master Mike Fanout",
        "",
        f"- Generated: `{receipt['generated_at']}`",
        f"- Repository: `{receipt['repo']}`",
        f"- Dry run: `{receipt['dry_run']}`",
        f"- Selected: `{len(receipt['selected'])}`",
        f"- Processed: `{len(receipt['processed'])}`",
        f"- Skipped current: `{len(receipt.get('skipped_current', []))}`",
        f"- Required reviewers: `{', '.join(receipt.get('required_reviewers', []))}`",
        f"- Merge mode: `{receipt.get('merge_mode', 'off')}`",
        "",
        "## Selected",
        "",
    ]
    if receipt["selected"]:
        for item in receipt["selected"]:
            lines.append(f"- `#{item['number']}` `{item['status']}` {item['title']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Skipped Current", ""])
    if receipt.get("skipped_current"):
        for item in receipt["skipped_current"]:
            lines.append(
                f"- `#{item['number']}` `{item['status']}` {item['title']} — "
                f"{item.get('reason')} packet=`{item.get('packet_dir')}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Processed", ""])
    if receipt["processed"]:
        for item in receipt["processed"]:
            lines.append(
                f"- `#{item['number']}` gate=`{item.get('gate_decision')}` "
                f"packet=`{item.get('packet_dir')}` comment=`{item.get('comment_path')}`"
            )
            for reviewer in item.get("reviewers", []):
                lines.append(
                    f"  - {reviewer['agent']}: exit={reviewer['exit_code']} "
                    f"status=`{reviewer['status']}` verdict=`{reviewer.get('verdict')}`"
                )
            if item.get("blockers"):
                for blocker in item["blockers"]:
                    lines.append(f"  - BLOCKER: {blocker}")
            if item.get("merge"):
                merge = item["merge"]
                lines.append(
                    f"  - merge: status=`{merge.get('status')}` method=`{merge.get('method')}` "
                    f"auto=`{merge.get('auto')}` receipt=`{merge.get('receipt')}`"
                )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Authority",
            "",
            "- GitHub comment text is rendered locally only; posting remains a separate explicit action.",
            "- Merge is allowed only when `merge_mode=auto-when-clean` and the deterministic gate is clean.",
            "",
        ]
    )
    if receipt.get("merge_mode") == "auto-when-clean":
        lines.insert(
            -1,
            "- This fanout may run Mike's conditional merge command after a clean gate.",
        )
    else:
        lines.insert(-1, "- This fanout does not merge, approve, push, or edit source.")
    if receipt.get("a2a_nats"):
        nats = receipt["a2a_nats"]
        lines.extend(
            [
                "## A2A NATS",
                "",
                f"- Status: `{nats.get('status')}`",
                f"- Code: `{nats.get('code')}`",
                f"- Ack tier: `{nats.get('ack_tier')}`",
                f"- Receipt: `{nats.get('receipt_path')}`",
                "",
            ]
        )
    return "\n".join(lines)


def capture_fanout_stage(
    stage: str, action: Callable[[], Any]
) -> tuple[Any | None, dict[str, str] | None]:
    """Run one per-PR fanout stage without aborting unrelated queue items."""

    try:
        return action(), None
    except Exception as exc:
        message = str(exc).strip() or repr(exc)
        return None, {
            "stage": stage,
            "error_type": type(exc).__name__,
            "message": message,
        }


def fanout_failure_row(
    item: dict[str, Any],
    pr_number: int,
    failure: dict[str, str],
    *,
    packet_dir_path: Path | None = None,
    reviewers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render a fail-closed per-PR exception as durable fanout evidence."""

    stage = failure["stage"]
    error_type = failure["error_type"]
    message = failure["message"]
    row: dict[str, Any] = {
        "number": pr_number,
        "title": item.get("title"),
        "status": item.get("status"),
        "packet_status": "failed" if stage == "packet" else "created",
        "reviewers": reviewers or [],
        "failure_stage": stage,
        "error_type": error_type,
        "error": message,
        "gate_decision": "BLOCKED",
        "blockers": [f"{stage} failed ({error_type}): {message}"],
    }
    if packet_dir_path is not None:
        row["packet_dir"] = str(packet_dir_path)
    return row


def finalize_fanout_item(
    args: argparse.Namespace,
    item: dict[str, Any],
    pr_number: int,
    out_dir: Path,
    reviewer_rows: list[dict[str, Any]],
    gate: dict[str, Any],
) -> dict[str, Any]:
    """Write post-gate artifacts and return one completed fanout row."""

    write_json(out_dir / "MERGE_GATE.json", gate)
    write_text(out_dir / "MERGE_GATE.md", render_gate_markdown(gate))
    packet = load_json(out_dir / "FACTS.json")
    comment_path = out_dir / "GITHUB_COMMENT.md"
    merge_summary: dict[str, Any] | None = None
    merge_receipt: dict[str, Any] | None = None
    if args.merge_mode == "auto-when-clean":
        merge_receipt = run_mike_merge_authority(
            pr_number=pr_number,
            gate=gate,
            method=args.merge_method,
            auto=args.merge_auto,
        )
        write_json(out_dir / "MIKE_MERGE_RECEIPT.json", merge_receipt)
        merge_summary = {
            "status": merge_receipt.get("status"),
            "reason": merge_receipt.get("reason"),
            "method": merge_receipt.get("method"),
            "auto": merge_receipt.get("auto"),
            "receipt": str(out_dir / "MIKE_MERGE_RECEIPT.json"),
            "exit_code": merge_receipt.get("exit_code"),
        }
    write_text(comment_path, render_github_comment(packet, gate, merge_receipt))
    return {
        "number": pr_number,
        "title": item.get("title"),
        "status": item.get("status"),
        "packet_dir": str(out_dir),
        "reviewers": reviewer_rows,
        "gate_decision": gate["decision"],
        "blockers": gate["blockers"],
        "warnings": gate["warnings"],
        "comment_path": str(comment_path),
        "merge": merge_summary,
    }


def cmd_fanout(args: argparse.Namespace) -> int:
    root = expand(args.state_root)
    repo = repo_name()
    queue_summary = build_queue_summary(fetch_open_prs(args.limit), repo)
    queue_dir = root / "queue"
    write_json(queue_dir / "latest.json", queue_summary)
    write_text(queue_dir / "latest.md", render_queue_markdown(queue_summary))

    statuses = parse_csv_tokens(args.statuses, default=DEFAULT_FANOUT_STATUSES)
    agents = parse_csv_tokens(args.agents, default=("codex", "claude"))
    required_reviewers = required_reviewer_agents(args)
    invalid_agents = sorted(set(agents) - {"codex", "claude"})
    if invalid_agents:
        raise PRControlError(
            f"unsupported fanout agent(s): {', '.join(invalid_agents)}"
        )

    plan = select_fanout_plan(
        queue_summary,
        statuses=statuses,
        max_prs=args.max_prs,
        state_root=root,
        skip_current=should_skip_current_fanout(args),
    )
    selected = plan["selected"]
    skipped_current = plan["skipped_current"]
    run_id = stamp()
    fanout_dir = root / "mike_fanout" / run_id
    processed: list[dict[str, Any]] = []

    for item in selected:
        pr_number = int(item["number"])
        if args.dry_run:
            continue

        packet_args = argparse.Namespace(
            state_root=str(root),
            pr=pr_number,
            ci_truth_contract=args.ci_truth_contract,
        )
        packet_result, failure = capture_fanout_stage(
            "packet", lambda: int(cmd_packet(packet_args))
        )
        if failure is not None:
            processed.append(fanout_failure_row(item, pr_number, failure))
            continue
        assert isinstance(packet_result, int)
        packet_code = packet_result
        if packet_code != 0:
            processed.append(
                {
                    "number": pr_number,
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "packet_status": "failed",
                    "packet_exit": packet_code,
                    "reviewers": [],
                    "gate_decision": "BLOCKED",
                    "blockers": [f"packet command exited {packet_code}"],
                }
            )
            continue

        packet_dir_result, failure = capture_fanout_stage(
            "packet-directory", lambda: packet_dir(root, pr_number)
        )
        if failure is not None:
            processed.append(fanout_failure_row(item, pr_number, failure))
            continue
        assert isinstance(packet_dir_result, Path)
        out_dir = packet_dir_result
        reviewer_rows: list[dict[str, Any]] = []
        review_failed = False
        review_binding: dict[str, Any] | None = None
        if not args.packet_only:
            binding_result, failure = capture_fanout_stage(
                "packet-binding",
                lambda: load_review_packet_binding(
                    out_dir,
                    expected_pr_number=pr_number,
                    expected_repo=repo,
                ),
            )
            if failure is not None:
                processed.append(
                    fanout_failure_row(
                        item,
                        pr_number,
                        failure,
                        packet_dir_path=out_dir,
                    )
                )
                continue
            assert isinstance(binding_result, dict)
            review_binding = binding_result
            for agent in agents:
                run_args = argparse.Namespace(
                    state_root=str(root),
                    pr=pr_number,
                    packet_dir=str(out_dir),
                    agent=agent,
                    timeout_s=args.timeout_s,
                    kill_grace_s=args.kill_grace_s,
                )
                review_result, failure = capture_fanout_stage(
                    f"review:{agent}",
                    lambda: (
                        cmd_run_agent(run_args),
                        load_agent_review_status(
                            out_dir,
                            agent,
                            **review_binding,
                        ),
                    ),
                )
                if failure is not None:
                    reviewer_rows.append(
                        {
                            "agent": agent,
                            "exit_code": None,
                            "status": "failed",
                            "error_type": failure["error_type"],
                            "error": failure["message"],
                        }
                    )
                    processed.append(
                        fanout_failure_row(
                            item,
                            pr_number,
                            failure,
                            packet_dir_path=out_dir,
                            reviewers=reviewer_rows,
                        )
                    )
                    review_failed = True
                    break
                assert review_result is not None
                exit_code, status = review_result
                reviewer_rows.append(
                    {
                        "agent": agent,
                        "exit_code": exit_code,
                        "status": status.get("receipt_status"),
                        "receipt_valid": status.get("receipt_valid"),
                        "receipt_error": status.get("receipt_error"),
                        "timed_out": status.get("timed_out"),
                        "duration_s": status.get("duration_s"),
                        "verdict": status.get("verdict"),
                        "output": status.get("output"),
                        "receipt": status.get("receipt"),
                    }
                )
        if review_failed:
            continue

        gate_args = argparse.Namespace(
            state_root=str(root),
            pr=pr_number,
            packet_dir=str(out_dir),
            allow_pending=args.allow_pending,
            human_approved=args.human_approved,
            allow_backup_reviewer=args.allow_backup_reviewer,
            backup_reviewers=args.backup_reviewers,
            backup_reviewer_reason=args.backup_reviewer_reason,
            required_reviewers=args.required_reviewers,
            accept_github_reviews=getattr(args, "accept_github_reviews", False),
            ci_truth_contract=args.ci_truth_contract,
        )
        gate_result, failure = capture_fanout_stage(
            "gate", lambda: build_gate(gate_args)
        )
        if failure is not None:
            processed.append(
                fanout_failure_row(
                    item,
                    pr_number,
                    failure,
                    packet_dir_path=out_dir,
                    reviewers=reviewer_rows,
                )
            )
            continue
        assert isinstance(gate_result, dict)
        gate = gate_result
        final_result, failure = capture_fanout_stage(
            "post-gate",
            lambda: finalize_fanout_item(
                args,
                item,
                pr_number,
                out_dir,
                reviewer_rows,
                gate,
            ),
        )
        if failure is not None:
            processed.append(
                fanout_failure_row(
                    item,
                    pr_number,
                    failure,
                    packet_dir_path=out_dir,
                    reviewers=reviewer_rows,
                )
            )
            continue
        assert isinstance(final_result, dict)
        processed.append(final_result)

    receipt = {
        "schema": "dharma.pr_review.mike_fanout.v1",
        "generated_at": utc_now(),
        "repo": repo,
        "run_id": run_id,
        "dry_run": args.dry_run,
        "packet_only": args.packet_only,
        "limit": args.limit,
        "max_prs": args.max_prs,
        "statuses": statuses,
        "agents": agents,
        "required_reviewers": required_reviewers,
        "merge_mode": args.merge_mode,
        "merge_method": args.merge_method,
        "merge_auto": args.merge_auto,
        "queue_path": str(queue_dir / "latest.json"),
        "selected": selected,
        "skipped_current": skipped_current,
        "processed": processed,
        "authority": {
            "agent_uid": "merge_master_mike",
            "can_merge": args.merge_mode == "auto-when-clean",
            "merge_policy": "conditional_on_merge_gate_clean",
            "can_approve_prs": False,
            "can_push": False,
            "can_edit_source": False,
            "github_comment_posting": "not_performed",
        },
    }

    if args.nats_session:
        nats_subjects = parse_csv_tokens(
            args.nats_subjects, default=DEFAULT_A2A_NATS_SUBJECTS
        )
        nats_receipt = publish_a2a_fanout_session(
            repo=repo,
            run_id=run_id,
            queue_summary=queue_summary,
            selected=selected,
            processed=processed,
            fanout_dir=fanout_dir,
            subjects=nats_subjects,
            required_reviewers=required_reviewers,
            merge_mode=args.merge_mode,
            dry_run=args.dry_run,
            packet_only=args.packet_only,
            required=args.nats_required,
            timeout_s=args.nats_timeout_s,
        )
        nats_receipt_path = fanout_dir / "a2a_nats_receipt.json"
        write_json(nats_receipt_path, nats_receipt)
        receipt["a2a_nats"] = {
            "status": nats_receipt.get("status"),
            "code": nats_receipt.get("code"),
            "ack_tier": nats_receipt.get("ack_tier"),
            "subjects": nats_subjects,
            "receipt_path": str(nats_receipt_path),
        }

    write_json(fanout_dir / "receipt.json", receipt)
    write_text(fanout_dir / "summary.md", render_fanout_markdown(receipt))

    print(f"mike_fanout={fanout_dir / 'summary.md'}")
    print(f"selected={len(selected)} processed={len(processed)} dry_run={args.dry_run}")
    if args.nats_session:
        nats_summary = receipt.get("a2a_nats", {})
        print(
            f"a2a_nats={nats_summary.get('receipt_path')} "
            f"status={nats_summary.get('status')} code={nats_summary.get('code')}"
        )
    for item in selected:
        print(f"SELECTED #{item['number']} {item['status']} {item['title']}")
    for item in skipped_current:
        print(f"SKIPPED_CURRENT #{item['number']} {item['status']} {item['title']}")
    for item in processed:
        print(
            f"PROCESSED #{item['number']} gate={item.get('gate_decision')} packet={item.get('packet_dir')}"
        )
    if (
        args.nats_session
        and args.nats_required
        and receipt.get("a2a_nats", {}).get("status") != "OK"
    ):
        return 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-root",
        default=str(DEFAULT_STATE_ROOT),
        help="Receipt root (default: ~/.dharma/pr_review)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_backup_reviewer_flags(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--allow-backup-reviewer",
            action="store_true",
            help="Allow one configured backup reviewer receipt to stand in when Claude is unavailable.",
        )
        command.add_argument(
            "--backup-reviewers",
            default=os.environ.get(
                "DHARMA_PR_BACKUP_REVIEWERS",
                "backup_opus,backup_gemini,backup_hermes,backup_perplexity",
            ),
            help="Comma-separated backup reviewer receipt names checked when --allow-backup-reviewer is set.",
        )
        command.add_argument(
            "--backup-reviewer-reason",
            default=os.environ.get("DHARMA_PR_BACKUP_REVIEWER_REASON", ""),
            help="Required written reason when a backup reviewer replaces Claude.",
        )

    def add_reviewer_policy_flags(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--required-reviewers",
            default=os.environ.get(
                "DHARMA_PR_REQUIRED_REVIEWERS", ",".join(DEFAULT_REQUIRED_REVIEWERS)
            ),
            help="Comma-separated required reviewer receipt names before merge.",
        )
        command.add_argument(
            "--accept-github-reviews",
            action="store_true",
            default=os.environ.get("DHARMA_PR_ACCEPT_GITHUB_REVIEWS", "")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"},
            help=(
                "Count a trusted installed reviewer-App's native GitHub review "
                "(Codex App = codex, Copilot = copilot) as that agent's review "
                "receipt when no local receipt file exists. ADDITIVE: never waives "
                "any other gate check. Lets the quorum clear in the cloud with no "
                "credential or operator machine."
            ),
        )

    def add_ci_truth_flags(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--ci-truth-contract",
            default=os.environ.get(
                "DHARMA_CI_TRUTH_CONTRACT", str(DEFAULT_CI_TRUTH_CONTRACT)
            ),
            help="Path to the CI truth contract consumed by packet and merge-gate evaluation.",
        )

    def add_legacy_pending_flag(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--allow-pending",
            action="store_true",
            help=(
                "Deprecated compatibility flag; required CI contexts always block "
                "while pending, and non-required contexts never carry merge authority."
            ),
        )

    queue = sub.add_parser("queue", help="Classify all open PRs")
    queue.add_argument("--limit", type=int, default=100)
    queue.set_defaults(func=cmd_queue)

    fanout = sub.add_parser(
        "fanout", help="Merge Master Mike PR packet -> reviewer -> gate fanout"
    )
    fanout.add_argument(
        "--limit", type=int, default=100, help="Open PRs to scan before selection"
    )
    fanout.add_argument(
        "--max-prs", type=int, default=3, help="Maximum PRs to process this run"
    )
    fanout.add_argument(
        "--statuses",
        default=",".join(DEFAULT_FANOUT_STATUSES),
        help="Comma-separated queue statuses Mike may process",
    )
    fanout.add_argument(
        "--agents",
        default="codex,claude",
        help="Comma-separated reviewer agents: codex,claude",
    )
    fanout.add_argument(
        "--timeout-s", type=float, default=None, help="Reviewer wall-clock timeout"
    )
    fanout.add_argument(
        "--kill-grace-s", type=float, default=DEFAULT_AGENT_KILL_GRACE_S
    )
    add_legacy_pending_flag(fanout)
    fanout.add_argument("--human-approved", action="store_true")
    add_reviewer_policy_flags(fanout)
    add_backup_reviewer_flags(fanout)
    add_ci_truth_flags(fanout)
    fanout.add_argument(
        "--packet-only",
        action="store_true",
        help="Create packets and gates without reviewer fanout",
    )
    fanout.add_argument(
        "--dry-run",
        action="store_true",
        help="Select PRs and write Mike receipt without processing them",
    )
    fanout.add_argument(
        "--reprocess-current",
        action="store_true",
        help="Process PRs even when the latest packet/gate already matches the current PR head and status",
    )
    fanout.add_argument(
        "--merge-mode",
        choices=MERGE_MODES,
        default="off",
        help="Mike merge authority mode",
    )
    fanout.add_argument(
        "--merge-method", choices=("squash", "merge", "rebase"), default="squash"
    )
    fanout.add_argument(
        "--no-merge-auto", dest="merge_auto", action="store_false", default=True
    )
    fanout.add_argument(
        "--nats-session",
        action="store_true",
        help="Publish a PR janitor session announcement to A2A NATS",
    )
    fanout.add_argument(
        "--nats-required",
        action="store_true",
        help="Return non-zero if A2A NATS publish is not ack-verified",
    )
    fanout.add_argument(
        "--nats-timeout-s", type=float, default=5.0, help="NATS connect/publish timeout"
    )
    fanout.add_argument(
        "--nats-subjects",
        default=",".join(DEFAULT_A2A_NATS_SUBJECTS),
        help="Comma-separated A2A NATS subjects for PR janitor coordination",
    )
    fanout.set_defaults(func=cmd_fanout)

    packet = sub.add_parser(
        "packet", help="Create a dual-agent review packet for one PR"
    )
    packet.add_argument("--pr", type=int, required=True)
    add_ci_truth_flags(packet)
    packet.set_defaults(func=cmd_packet)

    gate = sub.add_parser("gate", help="Run the merge gate for one PR")
    gate.add_argument("--pr", type=int, required=True)
    gate.add_argument("--packet-dir")
    add_legacy_pending_flag(gate)
    gate.add_argument("--human-approved", action="store_true")
    add_reviewer_policy_flags(gate)
    add_backup_reviewer_flags(gate)
    add_ci_truth_flags(gate)
    gate.set_defaults(func=cmd_gate)

    merge = sub.add_parser("merge", help="Dry-run or execute a gated merge")
    merge.add_argument("--pr", type=int, required=True)
    merge.add_argument("--packet-dir")
    add_legacy_pending_flag(merge)
    merge.add_argument("--human-approved", action="store_true")
    add_reviewer_policy_flags(merge)
    add_backup_reviewer_flags(merge)
    add_ci_truth_flags(merge)
    merge.add_argument(
        "--method", choices=("squash", "merge", "rebase"), default="squash"
    )
    merge.add_argument(
        "--auto", action="store_true", help="Use gh pr merge --auto when executing"
    )
    merge.add_argument("--confirm", required=True)
    merge.add_argument("--execute", action="store_true")
    merge.set_defaults(func=cmd_merge)

    comment = sub.add_parser(
        "comment", help="Render a GitHub comment for the latest packet/gate"
    )
    comment.add_argument("--pr", type=int, required=True)
    comment.add_argument("--packet-dir")
    comment.add_argument("--output")
    comment.set_defaults(func=cmd_comment)

    reviewers = sub.add_parser(
        "reviewers", help="Check local reviewer command/auth readiness"
    )
    reviewers.add_argument("--json", action="store_true")
    reviewers.add_argument(
        "--live-probe",
        action="store_true",
        help="Run a tiny Claude command to catch quota/runtime failures",
    )
    reviewers.add_argument("--probe-timeout-s", type=float, default=45.0)
    reviewers.set_defaults(func=cmd_reviewers)

    run_agent = sub.add_parser(
        "run-agent", help="Run Codex or Claude against an existing packet"
    )
    run_agent.add_argument("--pr", type=int, required=True)
    run_agent.add_argument("--packet-dir")
    run_agent.add_argument("--agent", choices=("codex", "claude"), required=True)
    run_agent.add_argument(
        "--timeout-s",
        type=float,
        default=None,
        help="Reviewer wall-clock timeout (default: DHARMA_PR_REVIEW_TIMEOUT_S or 600)",
    )
    run_agent.add_argument(
        "--kill-grace-s",
        type=float,
        default=DEFAULT_AGENT_KILL_GRACE_S,
        help="Seconds to wait after SIGTERM before SIGKILL",
    )
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
