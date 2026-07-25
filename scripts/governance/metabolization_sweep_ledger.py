#!/usr/bin/env python3
"""Maintain the 2026-07-01 metabolization sweep ledger.

The script scans the shared dharma_swarm checkout read-only, updates the JSONL
ledger in the isolated sweep clone, and applies conservative terminal decisions.
It never deletes branches or worktrees.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SHARED = Path("/Users/dhyana/dharma_swarm")
DEFAULT_LEDGER = Path("reports/governance/metabolization_sweep_ledger.jsonl")
EVIDENCE_PACKET = "reports/governance/metabolization_priority_evidence_2026-07-01.md"
PR_VECTOR = "https://github.com/AmitabhainArunachala/dharma_swarm/pull/736"
TERMINAL_STATUSES = {"pr_opened", "archived", "flagged_for_operator", "keep_active"}


def run(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(args)}\n{proc.stderr}"
        )
    return proc.stdout.strip()


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-C", str(repo), *args], check=check)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        entries[item["id"]] = item
    return entries


def write_jsonl(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    ordered = sorted(entries.values(), key=lambda item: (item["kind"], item["path_or_name"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.chmod(0o644)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for item in ordered:
                handle.write(json.dumps(item, sort_keys=True) + "\n")
        os.replace(tmp_path, path)
        path.chmod(0o444)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def validate_ledger_file(path: Path) -> dict[str, Any]:
    ids: list[str] = []
    invalid_status_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        ids.append(item["id"])
        if item.get("status") not in TERMINAL_STATUSES:
            invalid_status_ids.append(item["id"])
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    for item_id in ids:
        if item_id in seen and item_id not in duplicate_ids:
            duplicate_ids.append(item_id)
        seen.add(item_id)
    return {
        "line_count": len(ids),
        "unique_id_count": len(seen),
        "duplicate_count": len(duplicate_ids),
        "duplicate_ids": duplicate_ids[:50],
        "invalid_status_count": len(invalid_status_ids),
        "invalid_status_ids": invalid_status_ids[:50],
    }


def ensure_entry(
    entries: dict[str, dict[str, Any]],
    item_id: str,
    kind: str,
    path_or_name: str,
) -> dict[str, Any]:
    if item_id not in entries:
        entries[item_id] = {
            "id": item_id,
            "kind": kind,
            "path_or_name": path_or_name,
            "last_commit_date": None,
            "ahead": None,
            "behind": None,
            "tied_to_active_track": None,
            "bucket": None,
            "status": "untriaged",
            "evidence": {},
            "pr_url_or_tag": None,
            "last_updated": now_utc(),
        }
    return entries[item_id]


def rev_counts(repo: Path, left: str, right: str = "origin/main") -> tuple[int | None, int | None]:
    raw = git(repo, "rev-list", "--left-right", "--count", f"{left}...{right}", check=False)
    parts = raw.split()
    if len(parts) != 2:
        return None, None
    return int(parts[0]), int(parts[1])


def commit_date(repo: Path, rev: str) -> str | None:
    raw = git(repo, "log", "-1", "--format=%cI", rev, check=False)
    return raw or None


def commit_subject(repo: Path, rev: str) -> str | None:
    raw = git(repo, "log", "-1", "--format=%s", rev, check=False)
    return raw or None


def commit_exists(repo: Path, sha: str | None) -> bool:
    if not sha:
        return False
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def parse_worktrees(shared: Path) -> list[dict[str, str]]:
    raw = git(shared, "worktree", "list", "--porcelain")
    result: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            if cur:
                result.append(cur)
                cur = {}
            continue
        key, _, value = line.partition(" ")
        cur[key] = value
    if cur:
        result.append(cur)
    return result


def short_ref(refname: str) -> str:
    if refname.startswith("refs/heads/"):
        return refname.removeprefix("refs/heads/")
    if refname.startswith("refs/remotes/"):
        return refname.removeprefix("refs/remotes/")
    return refname


def scan_branches(shared: Path, clone: Path) -> list[dict[str, str]]:
    raw = git(
        shared,
        "for-each-ref",
        "refs/heads",
        "refs/remotes",
        "--format=%(refname)%00%(objectname)%00%(committerdate:iso-strict)",
    )
    branches: list[dict[str, str]] = []
    for line in raw.splitlines():
        refname, sha, date = line.split("\0")
        if refname.endswith("/HEAD"):
            continue
        source = "local" if refname.startswith("refs/heads/") else "remote"
        branches.append(
            {
                "name": short_ref(refname),
                "sha": sha,
                "date": date,
                "source": source,
            }
        )

    current = git(clone, "branch", "--show-current", check=False)
    if current:
        branches.append(
            {
                "name": current,
                "sha": git(clone, "rev-parse", current),
                "date": commit_date(clone, current) or "",
                "source": "isolated-local",
            }
        )
    return branches


def dirty_paths(path: Path) -> list[str]:
    raw = git(path, "status", "--porcelain", check=False)
    return raw.splitlines() if raw else []


def classify_track(text: str) -> str | None:
    low = text.lower()
    if "nats" in low or "a2a" in low:
        return "runtime-truth-nats-2026-06"
    if "spine" in low or "langgraph" in low:
        return "runtime-truth-spine-adoption-2026-06"
    if "telos" in low or "cashclaw" in low or "revenue" in low or "livelihood" in low:
        return "telos-ai-morning-refinery-2026-06"
    if "helm" in low or "terminal" in low:
        return "helm-worldclass-terminal-2026-06"
    if "loop" in low or "cybernetics" in low:
        return "loop-closure-2026-06"
    if "semantic" in low or "admission" in low:
        return "agent-admission-semantic-commons-2026-06"
    return None


def open_prs(clone: Path) -> dict[str, dict[str, Any]]:
    raw = run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,headRefName,url,isDraft,updatedAt",
        ],
        cwd=clone,
        check=False,
    )
    if not raw:
        return {}
    return {item["headRefName"]: item for item in json.loads(raw)}


def archive_tag_name(name: str, sha: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._/-]+", "-", name).strip("/.")
    cleaned = cleaned.replace("//", "/")
    if len(cleaned) > 120:
        cleaned = cleaned[:120].rstrip("/.")
    suffix = sha[:12] if sha else "unknown"
    return f"archive/metabolization/20260701/{cleaned}-{suffix}"


def create_archive_tag(clone: Path, name: str, sha: str | None) -> str | None:
    if not commit_exists(clone, sha):
        return None
    tag = archive_tag_name(name, sha)
    existing = git(clone, "tag", "--list", tag, check=False)
    if existing:
        return tag
    git(clone, "tag", tag, sha or "HEAD")
    return tag


def set_terminal(
    entry: dict[str, Any],
    status: str,
    bucket: str,
    reason: str,
    updated_at: str,
    pr_url_or_tag: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    entry["status"] = status
    entry["bucket"] = bucket
    entry["last_updated"] = updated_at
    if pr_url_or_tag is not None:
        entry["pr_url_or_tag"] = pr_url_or_tag
    evidence = entry.get("evidence") if isinstance(entry.get("evidence"), dict) else {}
    evidence["terminal_reason"] = reason
    evidence["evidence_packet"] = EVIDENCE_PACKET
    if extra:
        evidence.update(extra)
    entry["evidence"] = evidence


def update_worktrees(
    shared: Path,
    clone: Path,
    entries: dict[str, dict[str, Any]],
    prs: dict[str, dict[str, Any]],
    origin_main: str,
    magpie_gap: dict[str, int | None],
    updated_at: str,
) -> tuple[set[str], set[str]]:
    seen_paths: set[str] = set()
    worktree_branches: set[str] = set()
    for wt in parse_worktrees(shared):
        path = wt["worktree"]
        seen_paths.add(path)
        head = wt.get("HEAD")
        branch_ref = wt.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        if branch:
            worktree_branches.add(branch)
        entry = ensure_entry(entries, f"worktree::{path}", "worktree", path)
        ahead, behind = rev_counts(shared, head or "HEAD")
        dirty = dirty_paths(Path(path))
        entry.update(
            {
                "branch": branch,
                "head_sha": head,
                "last_commit_date": commit_date(shared, head or "HEAD"),
                "ahead": ahead,
                "behind": behind,
                "tied_to_active_track": classify_track(f"{path} {branch or ''}"),
                "last_updated": updated_at,
                "evidence": {
                    "latest_scan": updated_at,
                    "present_in_latest_worktree_scan": True,
                    "origin_main_sha": origin_main,
                    "dirty_summary": "clean" if not dirty else f"dirty:{len(dirty)}",
                    "dirty_count": len(dirty),
                    "last_subject": commit_subject(shared, head or "HEAD"),
                    "agent_magpie_seed_gap": magpie_gap if path == str(shared) else None,
                },
            }
        )

        if branch in prs:
            pr = prs[branch]
            if dirty:
                set_terminal(
                    entry,
                    "flagged_for_operator",
                    "dirty_pr_worktree",
                    "open PR exists, but this worktree has local dirty paths outside the pushed branch",
                    updated_at,
                    pr["url"],
                    {"pr_number": pr["number"], "pr_title": pr["title"]},
                )
            else:
                set_terminal(
                    entry,
                    "pr_opened",
                    "merge_candidate",
                    "worktree branch has an open GitHub PR",
                    updated_at,
                    pr["url"],
                    {"pr_number": pr["number"], "pr_title": pr["title"]},
                )
        elif path == str(shared):
            set_terminal(
                entry,
                "keep_active",
                "primary_live_checkout",
                "primary shared checkout is live and dirty; record gap but do not archive",
                updated_at,
                None,
                {"agent_magpie_seed_gap": magpie_gap},
            )
        elif dirty:
            set_terminal(
                entry,
                "flagged_for_operator",
                "dirty_worktree",
                "worktree has uncommitted local state; no archive or merge choice made",
                updated_at,
            )
        elif branch is None:
            tag = create_archive_tag(clone, f"detached-{path}", head)
            set_terminal(
                entry,
                "archived",
                "detached_clean_scratch",
                "detached clean worktree; no branch decision available",
                updated_at,
                tag,
            )
        elif ahead == 0:
            tag = create_archive_tag(clone, branch, head)
            set_terminal(
                entry,
                "archived",
                "no_unique_commit_worktree",
                "clean worktree branch has no unique commits relative to origin/main",
                updated_at,
                tag,
            )
        else:
            set_terminal(
                entry,
                "keep_active",
                "active_clean_worktree",
                "clean active worktree has unique commits and no open PR; retained for operator follow-up",
                updated_at,
            )

    for entry in entries.values():
        if entry.get("kind") != "worktree":
            continue
        if entry["path_or_name"] in seen_paths:
            continue
        evidence = entry.get("evidence") if isinstance(entry.get("evidence"), dict) else {}
        evidence["present_in_latest_worktree_scan"] = False
        evidence["latest_scan"] = updated_at
        entry["evidence"] = evidence
        set_terminal(
            entry,
            "archived",
            "stale_worktree_entry",
            "ledger worktree item is not present in the latest full worktree scan",
            updated_at,
            entry.get("pr_url_or_tag"),
        )
    return seen_paths, worktree_branches


def update_branches(
    shared: Path,
    clone: Path,
    entries: dict[str, dict[str, Any]],
    prs: dict[str, dict[str, Any]],
    worktree_branches: set[str],
    origin_main: str,
    magpie_gap: dict[str, int | None],
    updated_at: str,
) -> set[str]:
    seen_branches: set[str] = set()
    for info in scan_branches(shared, clone):
        name = info["name"]
        seen_branches.add(name)
        entry = ensure_entry(entries, f"branch::{name}", "branch", name)
        repo = clone if info["source"] == "isolated-local" else shared
        ahead, behind = rev_counts(repo, name)
        entry.update(
            {
                "branch": name,
                "head_sha": info["sha"],
                "last_commit_date": info["date"],
                "ahead": ahead,
                "behind": behind,
                "tied_to_active_track": classify_track(name),
                "last_updated": updated_at,
                "evidence": {
                    "latest_scan": updated_at,
                    "present_in_latest_branch_scan": True,
                    "source": info["source"],
                    "origin_main_sha": origin_main,
                    "has_worktree": name in worktree_branches,
                    "last_subject": commit_subject(repo, name),
                    "agent_magpie_seed_gap": magpie_gap if name == "agent/magpie-seed" else None,
                },
            }
        )

        pr_head = name
        if name.startswith("origin/"):
            pr_head = name.removeprefix("origin/")
        if pr_head in prs:
            pr = prs[pr_head]
            set_terminal(
                entry,
                "pr_opened",
                "merge_candidate",
                "branch has an open GitHub PR",
                updated_at,
                pr["url"],
                {"pr_number": pr["number"], "pr_title": pr["title"]},
            )
        elif name == "codex/metabolization-ledger-20260701":
            set_terminal(
                entry,
                "keep_active",
                "sweep_control_branch",
                "current sweep control branch; terminalized as active until PR publication",
                updated_at,
            )
        elif info["source"] == "remote":
            set_terminal(
                entry,
                "keep_active",
                "remote_tracking_ref",
                "remote tracking ref included for git branch -a coverage; not a local archive/delete target",
                updated_at,
            )
        elif name in worktree_branches:
            set_terminal(
                entry,
                "keep_active",
                "active_worktree_branch",
                "local branch has an active worktree; branch is retained and worktree row carries dirty/PR decision",
                updated_at,
            )
        elif ahead == 0:
            tag = create_archive_tag(clone, name, info["sha"])
            set_terminal(
                entry,
                "archived",
                "no_unique_commits",
                "local branch has no unique commits relative to origin/main; archive tag recorded where available",
                updated_at,
                tag,
            )
        elif name == "agent/magpie-seed":
            set_terminal(
                entry,
                "keep_active",
                "primary_live_branch",
                "primary live branch retained; ahead/behind gap recorded",
                updated_at,
                None,
                {"agent_magpie_seed_gap": magpie_gap},
            )
        else:
            low = name.lower()
            if "forge" in low or "darwin" in low or "evolution" in low:
                bucket = "operator_reconciliation"
                reason = "unique unmerged branch overlaps Forge or Darwin/evolution reconciliation"
            else:
                bucket = "unique_unmerged_branch"
                reason = "unique unmerged local branch has no open PR and no active worktree"
            set_terminal(
                entry,
                "flagged_for_operator",
                bucket,
                reason,
                updated_at,
            )

    for entry in entries.values():
        if entry.get("kind") != "branch":
            continue
        if entry["path_or_name"] in seen_branches:
            continue
        remote_shadow = f"origin/{entry['path_or_name']}"
        evidence = entry.get("evidence") if isinstance(entry.get("evidence"), dict) else {}
        evidence["present_in_latest_branch_scan"] = False
        evidence["latest_scan"] = updated_at
        entry["evidence"] = evidence
        if not entry["path_or_name"].startswith("origin/") and remote_shadow in seen_branches:
            set_terminal(
                entry,
                "keep_active",
                "stale_local_shadow_remote_live",
                "local branch ref is absent, but matching origin remote-tracking ref is present and retained",
                updated_at,
                entry.get("pr_url_or_tag"),
                {"remote_tracking_ref": remote_shadow},
            )
            continue
        tag = create_archive_tag(clone, entry["path_or_name"], entry.get("head_sha"))
        set_terminal(
            entry,
            "archived",
            "stale_branch_entry",
            "ledger branch item is not present in the latest full branch scan",
            updated_at,
            tag or entry.get("pr_url_or_tag"),
        )
    return seen_branches


def apply_priority_overrides(entries: dict[str, dict[str, Any]], updated_at: str) -> None:
    vector_ids = {
        "branch::codex/metabolize-vector-fallback-guard-20260701",
        "branch::origin/codex/metabolize-vector-fallback-guard-20260701",
    }
    for item_id in vector_ids:
        entry = entries.get(item_id)
        if not entry:
            continue
        set_terminal(
            entry,
            "pr_opened",
            "merge_candidate",
            "clean vector fallback guard extracted and draft PR opened",
            updated_at,
            PR_VECTOR,
            {
                "priority_item": "vector_store.py fallback scan guard",
                "validation": "/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q tests/test_vector_store.py => 30 passed, 24 warnings",
            },
        )

    for entry in entries.values():
        text = f"{entry.get('path_or_name')} {entry.get('branch', '')}".lower()
        if "forge" in text and entry.get("status") not in {"pr_opened"}:
            if entry.get("status") == "keep_active" and entry.get("kind") == "branch":
                evidence = entry.get("evidence") if isinstance(entry.get("evidence"), dict) else {}
                evidence["operator_note"] = "Forge branch retained; consolidation choice is flagged in evidence packet"
                entry["evidence"] = evidence
            elif entry.get("status") != "archived":
                set_terminal(
                    entry,
                    "flagged_for_operator",
                    "forge_consolidation",
                    "Forge surfaces are fragmented; consolidation root must be chosen by operator",
                    updated_at,
                    entry.get("pr_url_or_tag"),
                )

        if "darwin" in text or "evolution" in text:
            if entry.get("status") not in {"pr_opened", "archived"}:
                set_terminal(
                    entry,
                    "flagged_for_operator",
                    "darwin_reconciliation",
                    "Darwin/evolution branch touches self-modifying code; do not choose automatically",
                    updated_at,
                    entry.get("pr_url_or_tag"),
                )


def summarize(
    entries: dict[str, dict[str, Any]],
    seen_worktrees: set[str],
    seen_branches: set[str],
    magpie_gap: dict[str, int | None],
    origin_main: str,
    updated_at: str,
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    kind_status_counts: dict[str, int] = {}
    nonterminal: list[str] = []
    archived_without_artifact: list[str] = []
    archived_remote_live_shadows: list[str] = []
    for item in entries.values():
        status = item.get("status")
        status_counts[status] = status_counts.get(status, 0) + 1
        key = f"{item.get('kind')}:{status}"
        kind_status_counts[key] = kind_status_counts.get(key, 0) + 1
        if status not in TERMINAL_STATUSES:
            nonterminal.append(item["id"])
        if status == "archived" and not item.get("pr_url_or_tag"):
            archived_without_artifact.append(item["id"])
            name = item.get("path_or_name", "")
            if item.get("kind") == "branch" and f"origin/{name}" in seen_branches:
                archived_remote_live_shadows.append(item["id"])
    new_worktrees = [
        f"worktree::{path}"
        for path in seen_worktrees
        if f"worktree::{path}" not in entries
    ]
    new_branches = [
        f"branch::{name}"
        for name in seen_branches
        if f"branch::{name}" not in entries
    ]
    return {
        "updated_at": updated_at,
        "entries": len(entries),
        "statuses": dict(sorted(status_counts.items())),
        "kind_statuses": dict(sorted(kind_status_counts.items())),
        "latest_worktree_scan_count": len(seen_worktrees),
        "latest_branch_scan_count": len(seen_branches),
        "new_worktrees_not_in_ledger": new_worktrees,
        "new_branches_not_in_ledger": new_branches,
        "nonterminal_count": len(nonterminal),
        "nonterminal_ids": nonterminal[:50],
        "archived_without_artifact_count": len(archived_without_artifact),
        "archived_without_artifact_ids": archived_without_artifact[:50],
        "archived_remote_live_shadow_count": len(archived_remote_live_shadows),
        "archived_remote_live_shadow_ids": archived_remote_live_shadows[:50],
        "agent_magpie_seed_gap": magpie_gap,
        "origin_main_sha": origin_main,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared", type=Path, default=DEFAULT_SHARED)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    clone = Path.cwd()
    ledger = args.ledger if args.ledger.is_absolute() else clone / args.ledger
    updated_at = now_utc()
    entries = load_jsonl(ledger)
    origin_main = git(args.shared, "rev-parse", "origin/main")
    magpie_ahead, magpie_behind = rev_counts(args.shared, "agent/magpie-seed")
    magpie_gap = {"ahead": magpie_ahead, "behind": magpie_behind}
    prs = open_prs(clone)

    seen_worktrees, worktree_branches = update_worktrees(
        args.shared,
        clone,
        entries,
        prs,
        origin_main,
        magpie_gap,
        updated_at,
    )
    seen_branches = update_branches(
        args.shared,
        clone,
        entries,
        prs,
        worktree_branches,
        origin_main,
        magpie_gap,
        updated_at,
    )
    apply_priority_overrides(entries, updated_at)
    summary = summarize(entries, seen_worktrees, seen_branches, magpie_gap, origin_main, updated_at)
    if not args.verify_only:
        write_jsonl(ledger, entries)
        summary["ledger_file_check"] = validate_ledger_file(ledger)
    print(json.dumps(summary, indent=2, sort_keys=True))
    file_check = summary.get("ledger_file_check", {})
    return 1 if (
        summary["nonterminal_count"]
        or summary["archived_without_artifact_count"]
        or summary["archived_remote_live_shadow_count"]
        or file_check.get("duplicate_count")
        or file_check.get("invalid_status_count")
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
