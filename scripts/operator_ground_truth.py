#!/usr/bin/env python3
"""Operator Ground Truth v0.

A terminal-native, read-first control surface that reports the *real* local
state of the dharma_swarm project: git/worktree truth, runtime DB row counts,
relevant daemons, test surface, and a ranked warning list.

Design constraints:
    * Read-only by default. Writes only happen when ``--output`` is supplied.
    * No network calls. No GitHub CLI dependency.
    * Subprocess calls are time-bounded and degrade gracefully.
    * Avoids scanning huge folders (.git, node_modules, .venv, etc.).
    * Does not mutate, kill, or otherwise touch external state.

Usage:
    python scripts/operator_ground_truth.py
    python scripts/operator_ground_truth.py --json
    python scripts/operator_ground_truth.py --include-processes --include-runtime-dbs
    python scripts/operator_ground_truth.py --no-processes --no-runtime-dbs
    python scripts/operator_ground_truth.py --fail-on-critical
    python scripts/operator_ground_truth.py --output reports/operator_ground_truth/latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANONICAL_RUNTIME_TABLES: tuple[str, ...] = (
    "session_events",
    "task_claims",
    "delegation_runs",
    "artifact_records",
    "memory_facts",
    "context_bundles",
    "operator_actions",
)

# Folders that are noisy / huge / vendor / cache and should be skipped.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".next",
        ".swarm",  # excluded from runtime scan; included separately if needed
        "dist",
        "build",
        "vendor",
        ".gitnexus",
        ".mcp_data",
        ".playwright-mcp",
        ".claude-flow",
    }
)

PROCESS_PATTERNS: tuple[str, ...] = (
    "uvicorn",
    "pytest",
    "dharma_swarm",
    "dharma-swarm",
    "dgc ",
    "dgc_",
    "codex",
    "claude ",
    "next dev",
    "node dev",
    "litestream",
)

# Subprocess wall-clock timeout per call (seconds).
SUBPROC_TIMEOUT = 8.0

# Maximum directories visited during runtime DB discovery (cheap safety net).
MAX_SCAN_DIRS = 4000


# ---------------------------------------------------------------------------
# Datatypes
# ---------------------------------------------------------------------------


@dataclass
class Warning_:  # trailing underscore to avoid shadowing builtin Warning
    severity: str  # one of: "critical", "warning", "info"
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "message": self.message}


@dataclass
class Report:
    repo: dict[str, Any] = field(default_factory=dict)
    worktrees: list[dict[str, Any]] = field(default_factory=list)
    runtime_dbs: list[dict[str, Any]] = field(default_factory=list)
    processes: list[dict[str, Any]] = field(default_factory=list)
    test_surface: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    generated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "worktrees": self.worktrees,
            "runtime_dbs": self.runtime_dbs,
            "processes": self.processes,
            "test_surface": self.test_surface,
            "warnings": self.warnings,
            "summary": self.summary,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None, timeout: float = SUBPROC_TIMEOUT) -> str | None:
    """Run a command, return stdout on success, ``None`` on any failure.

    Stderr is silenced. Non-zero exit codes return ``None``. Any exception
    (timeout, missing binary, permission error) returns ``None``.
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def detect_repo_root(start: Path) -> Path | None:
    """Return the toplevel git directory containing ``start``, if any."""
    out = _run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if not out:
        return None
    p = Path(out.strip())
    return p if p.exists() else None


def parse_worktree_porcelain(text: str) -> list[dict[str, Any]]:
    """Parse the output of ``git worktree list --porcelain``.

    The porcelain format is a sequence of stanzas, each starting with a
    ``worktree <path>`` line, followed by zero or more ``HEAD <sha>``,
    ``branch <ref>``, ``detached``, ``bare``, ``locked``, ``prunable`` lines.
    Stanzas are separated by blank lines.
    """
    worktrees: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            if current is not None:
                worktrees.append(current)
                current = None
            continue
        if line.startswith("worktree "):
            if current is not None:
                worktrees.append(current)
            current = {
                "path": line[len("worktree "):].strip(),
                "head": None,
                "branch": None,
                "detached": False,
                "bare": False,
                "locked": False,
                "prunable": False,
            }
            continue
        if current is None:
            continue
        if line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].strip()
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    if current is not None:
        worktrees.append(current)
    return worktrees


def collect_worktrees(repo_root: Path) -> list[dict[str, Any]]:
    out = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    if not out:
        return []
    parsed = parse_worktree_porcelain(out)
    enriched: list[dict[str, Any]] = []
    for w in parsed:
        wt_path = Path(w["path"])
        info = dict(w)
        info["exists"] = wt_path.exists()
        info["dirty"] = False
        info["modified"] = 0
        info["untracked"] = 0
        info["ahead"] = None
        info["behind"] = None
        info["warnings"] = []
        info["branch_name"] = _strip_refs_heads(info.get("branch"))
        if info["exists"]:
            status = _run(["git", "status", "--porcelain=v1"], cwd=wt_path)
            if status is not None:
                modified = 0
                untracked = 0
                for s in status.splitlines():
                    if s.startswith("?? "):
                        untracked += 1
                    elif s.strip():
                        modified += 1
                info["modified"] = modified
                info["untracked"] = untracked
                info["dirty"] = (modified + untracked) > 0
            # ahead/behind vs origin/main if tracking exists
            ab = _run(
                ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
                cwd=wt_path,
            )
            if ab:
                parts = ab.strip().split()
                if len(parts) == 2:
                    try:
                        info["ahead"] = int(parts[0])
                        info["behind"] = int(parts[1])
                    except ValueError:
                        pass
        enriched.append(info)
    return enriched


def collect_repo_identity(repo_root: Path) -> dict[str, Any]:
    branch = (_run(["git", "branch", "--show-current"], cwd=repo_root) or "").strip()
    head = (_run(["git", "rev-parse", "HEAD"], cwd=repo_root) or "").strip()
    origin_main = (_run(["git", "rev-parse", "origin/main"], cwd=repo_root) or "").strip()
    ahead_behind = _run(
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
        cwd=repo_root,
    )
    ahead: int | None = None
    behind: int | None = None
    if ahead_behind:
        parts = ahead_behind.strip().split()
        if len(parts) == 2:
            try:
                ahead = int(parts[0])
                behind = int(parts[1])
            except ValueError:
                pass
    return {
        "root": str(repo_root),
        "branch": branch or None,
        "head": head or None,
        "origin_main": origin_main or None,
        "ahead": ahead,
        "behind": behind,
    }


# ---------------------------------------------------------------------------
# Runtime DB discovery
# ---------------------------------------------------------------------------


def find_runtime_dbs(repo_root: Path) -> list[Path]:
    """Walk repo (skipping noisy dirs) for SQLite-looking files."""
    candidates: list[Path] = []
    visited = 0
    for dirpath, dirnames, filenames in os.walk(repo_root, followlinks=False):
        # In-place prune of skipped dirs.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        visited += 1
        if visited > MAX_SCAN_DIRS:
            break
        for name in filenames:
            if name.endswith(".db") or name.endswith(".sqlite") or name.endswith(".sqlite3"):
                p = Path(dirpath) / name
                # Skip obviously-non-runtime caches.
                rel = p.relative_to(repo_root).as_posix()
                if rel.startswith(".mypy_cache") or rel.startswith(".pytest_cache"):
                    continue
                candidates.append(p)
    # Stable ordering for reproducibility.
    candidates.sort()
    return candidates


def inspect_runtime_db(db_path: Path) -> dict[str, Any]:
    """Read-only inspect a SQLite DB for canonical runtime tables.

    Uses ``immutable=1`` URI mode so we never write. Degrades gracefully
    (returns ``error`` field) if the file is malformed or unreadable.
    """
    info: dict[str, Any] = {
        "path": str(db_path),
        "tables": [],
        "row_counts": {tbl: None for tbl in CANONICAL_RUNTIME_TABLES},
        "error": None,
    }
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sorted({row[0] for row in cur.fetchall() if row and row[0]})
        info["tables"] = tables
        for tbl in CANONICAL_RUNTIME_TABLES:
            if tbl not in tables:
                info["row_counts"][tbl] = None
                continue
            try:
                # Identifiers cannot be parameter-bound; tbl is from the
                # whitelist CANONICAL_RUNTIME_TABLES so this is safe.
                cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
                row = cur.fetchone()
                info["row_counts"][tbl] = int(row[0]) if row else 0
            except sqlite3.Error as exc:
                info["row_counts"][tbl] = None
                info.setdefault("table_errors", {})[tbl] = str(exc)
    except (sqlite3.Error, OSError) as exc:
        info["error"] = str(exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
    return info


def is_canonical_runtime_db(info: dict[str, Any]) -> bool:
    """Heuristic: a DB is "canonical-runtime-shaped" if it has at least
    one of the structured runtime tables (not just session_events)."""
    rc = info.get("row_counts") or {}
    structured = (
        "task_claims",
        "delegation_runs",
        "artifact_records",
        "memory_facts",
        "context_bundles",
        "operator_actions",
    )
    return any(rc.get(t) is not None for t in structured)


# ---------------------------------------------------------------------------
# Process discovery
# ---------------------------------------------------------------------------


def collect_processes(repo_root: Path, worktree_paths: set[str]) -> list[dict[str, Any]]:
    """List relevant running processes. Best-effort, never fails hard."""
    if shutil.which("ps") is None:
        return []
    out = _run(["ps", "-axo", "pid=,command="])
    if not out:
        return []
    procs: list[dict[str, Any]] = []
    repo_str = str(repo_root)
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pid_str, _, command = line.partition(" ")
            pid = int(pid_str)
        except ValueError:
            continue
        if not any(p in command for p in PROCESS_PATTERNS):
            continue
        # Skip self/parent shell noise
        if "operator_ground_truth" in command:
            continue
        if "ps -axo" in command:
            continue
        cwd = _process_cwd(pid)
        # Filter: prefer processes plausibly attached to dharma_swarm or its worktrees.
        if cwd is None:
            attached_to_repo = repo_str in command or any(w in command for w in worktree_paths)
        else:
            attached_to_repo = (
                cwd.startswith(repo_str)
                or any(cwd.startswith(w) for w in worktree_paths)
                or repo_str in command
                or any(w in command for w in worktree_paths)
            )
        if not attached_to_repo:
            continue
        procs.append(
            {
                "pid": pid,
                "command": command[:240],
                "cwd": cwd,
            }
        )
    return procs


def _process_cwd(pid: int) -> str | None:
    """Best-effort process cwd lookup using lsof. Returns ``None`` if unavailable."""
    if shutil.which("lsof") is None:
        return None
    out = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], timeout=2.0)
    if not out:
        return None
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:].strip()
    return None


# ---------------------------------------------------------------------------
# Test surface
# ---------------------------------------------------------------------------


def collect_test_surface(repo_root: Path) -> dict[str, Any]:
    tests_dir = repo_root / "tests"
    info: dict[str, Any] = {
        "tests_dir": str(tests_dir) if tests_dir.exists() else None,
        "pytest_files": 0,
        "suggested_smoke_command": None,
    }
    if not tests_dir.exists():
        return info
    count = 0
    for entry in tests_dir.rglob("test_*.py"):
        # Skip noisy dirs.
        parts = set(entry.parts)
        if parts & SKIP_DIRS:
            continue
        count += 1
    info["pytest_files"] = count
    smoke = tests_dir / "test_operator_ground_truth.py"
    if smoke.exists():
        info["suggested_smoke_command"] = (
            f"python -m pytest {smoke.relative_to(repo_root)} -q"
        )
    else:
        info["suggested_smoke_command"] = "python -m pytest tests -q -x --maxfail=1"
    return info


# ---------------------------------------------------------------------------
# Warning classifier
# ---------------------------------------------------------------------------


def classify_warnings(report: Report) -> list[Warning_]:
    """Pure function: derive the ranked warning list from the report state.

    Kept pure (no I/O) so it's easy to unit-test.
    """
    out: list[Warning_] = []

    # Repo-level
    repo = report.repo or {}
    if repo.get("ahead") and repo["ahead"] > 0 and (repo.get("behind") or 0) > 0:
        out.append(
            Warning_(
                "critical",
                f"current branch is {repo['ahead']} ahead and {repo['behind']} behind origin/main",
            )
        )
    elif repo.get("behind") and repo["behind"] > 0:
        out.append(Warning_("warning", f"current branch is {repo['behind']} behind origin/main"))
    elif repo.get("ahead") and repo["ahead"] > 0:
        out.append(Warning_("info", f"current branch is {repo['ahead']} ahead of origin/main"))

    # Worktree-level
    branch_to_paths: dict[str, list[str]] = {}
    for w in report.worktrees:
        path = w.get("path", "?")
        branch = w.get("branch") or ("(detached)" if w.get("detached") else "(unknown)")
        branch_to_paths.setdefault(branch, []).append(path)
        if w.get("dirty"):
            out.append(
                Warning_(
                    "warning",
                    f"worktree {path} has dirty changes on {branch} "
                    f"(modified={w.get('modified', 0)} untracked={w.get('untracked', 0)})",
                )
            )
        if w.get("prunable"):
            out.append(Warning_("warning", f"worktree {path} is marked prunable by git"))
        if not w.get("exists", True):
            out.append(Warning_("warning", f"worktree {path} no longer exists on disk"))

    for branch, paths in branch_to_paths.items():
        if branch.startswith("(") or branch == "(detached)":
            continue
        if len(paths) > 1:
            out.append(
                Warning_(
                    "warning",
                    f"multiple worktrees on same branch {branch}: {', '.join(paths)}",
                )
            )

    # Runtime DB-level: session_events without structured rows
    for db in report.runtime_dbs:
        rc = db.get("row_counts") or {}
        if db.get("error"):
            out.append(
                Warning_(
                    "warning",
                    f"runtime db {db.get('path')} could not be read: {db['error']}",
                )
            )
            continue
        sev = rc.get("session_events") or 0
        structured_keys = (
            "task_claims",
            "delegation_runs",
            "artifact_records",
            "memory_facts",
            "context_bundles",
            "operator_actions",
        )
        structured_total = sum((rc.get(k) or 0) for k in structured_keys)
        any_structured_table = any(rc.get(k) is not None for k in structured_keys)
        if sev > 0 and any_structured_table and structured_total == 0:
            out.append(
                Warning_(
                    "warning",
                    f"runtime db {db.get('path')} has session_events={sev} "
                    f"but all structured runtime tables are empty",
                )
            )

    # Process-level: detect daemons attached to non-current worktrees
    repo_root = repo.get("root")
    for p in report.processes:
        cwd = p.get("cwd")
        if cwd and repo_root and not cwd.startswith(repo_root):
            out.append(
                Warning_(
                    "info",
                    f"process pid={p['pid']} cwd={cwd} appears attached to "
                    f"non-current repo root",
                )
            )

    if not report.processes:
        out.append(Warning_("info", "no relevant daemons detected"))

    # Severity ordering: critical > warning > info
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda w: (order.get(w.severity, 99), w.message))
    return out


# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------


def _strip_refs_heads(branch: str | None) -> str | None:
    if not branch:
        return None
    prefix = "refs/heads/"
    return branch[len(prefix):] if branch.startswith(prefix) else branch


def render_summary(report: Report) -> str:
    n_wt = len(report.worktrees)
    n_dirty = sum(1 for w in report.worktrees if w.get("dirty"))
    feature_branches: set[str] = set()
    for w in report.worktrees:
        b = _strip_refs_heads(w.get("branch"))
        if b and (b.startswith("feature/") or b.startswith("feat/")):
            feature_branches.add(b)
    structured_tables = (
        "task_claims",
        "delegation_runs",
        "artifact_records",
        "memory_facts",
        "context_bundles",
        "operator_actions",
    )
    n_runtime_with_structured_rows = sum(
        1
        for db in report.runtime_dbs
        if is_canonical_runtime_db(db)
        and any((db.get("row_counts") or {}).get(t) for t in structured_tables)
    )
    n_procs = len(report.processes)
    return (
        f"Current truth: {n_wt} worktrees found, {n_dirty} dirty, "
        f"{len(feature_branches)} active feature branch(es), "
        f"{n_runtime_with_structured_rows} runtime DB(s) with structured rows, "
        f"{n_procs} relevant daemon(s)."
    )


# ---------------------------------------------------------------------------
# Rendering (terminal)
# ---------------------------------------------------------------------------


def _hr(title: str) -> str:
    return f"\n=== {title} ".ljust(72, "=")


def render_terminal(report: Report) -> str:
    lines: list[str] = []
    repo = report.repo
    lines.append(_hr("A. Repo Identity"))
    lines.append(f"  root        : {repo.get('root')}")
    lines.append(f"  branch      : {repo.get('branch')}")
    lines.append(f"  HEAD        : {repo.get('head')}")
    lines.append(f"  origin/main : {repo.get('origin_main')}")
    if repo.get("ahead") is not None:
        lines.append(f"  ahead/behind: {repo.get('ahead')}/{repo.get('behind')} vs origin/main")

    lines.append(_hr("B. Worktrees"))
    if not report.worktrees:
        lines.append("  (none)")
    for w in report.worktrees:
        flag = "DIRTY" if w.get("dirty") else "clean"
        branch = w.get("branch_name") or w.get("branch") or ("detached" if w.get("detached") else "?")
        head = (w.get("head") or "")[:10]
        ab = ""
        if w.get("ahead") is not None:
            ab = f" [+{w['ahead']}/-{w['behind']} vs origin/main]"
        lines.append(
            f"  [{flag:5s}] {w.get('path')}  branch={branch}  HEAD={head}"
            f"  M={w.get('modified', 0)} U={w.get('untracked', 0)}{ab}"
        )

    lines.append(_hr("C. Runtime DBs"))
    if not report.runtime_dbs:
        lines.append("  (none discovered)")
    for db in report.runtime_dbs:
        lines.append(f"  {db.get('path')}")
        if db.get("error"):
            lines.append(f"    error: {db['error']}")
            continue
        rc = db.get("row_counts") or {}
        for tbl in CANONICAL_RUNTIME_TABLES:
            v = rc.get(tbl)
            shown = "—" if v is None else str(v)
            lines.append(f"    {tbl:<18s} {shown}")

    lines.append(_hr("D. Processes"))
    if not report.processes:
        lines.append("  (none relevant)")
    for p in report.processes:
        lines.append(f"  pid={p['pid']:>6}  cwd={p.get('cwd') or '-'}  cmd={p['command']}")

    lines.append(_hr("E. Test Surface"))
    ts = report.test_surface
    lines.append(f"  tests_dir              : {ts.get('tests_dir')}")
    lines.append(f"  pytest_files           : {ts.get('pytest_files')}")
    lines.append(f"  suggested smoke command: {ts.get('suggested_smoke_command')}")

    lines.append(_hr("F. Warnings"))
    if not report.warnings:
        lines.append("  (none)")
    for w in report.warnings:
        lines.append(f"  [{w['severity'].upper():8s}] {w['message']}")

    lines.append(_hr("G. Summary"))
    lines.append(f"  {report.summary}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def build_report(
    repo_root: Path,
    *,
    include_processes: bool = True,
    include_runtime_dbs: bool = True,
    include_tests: bool = True,
) -> Report:
    """Build a full ground-truth report. Pure orchestration; no I/O writes."""
    report = Report()
    report.repo = collect_repo_identity(repo_root)
    report.worktrees = collect_worktrees(repo_root)

    worktree_paths = {w["path"] for w in report.worktrees if w.get("path")}

    if include_runtime_dbs:
        for db_path in find_runtime_dbs(repo_root):
            report.runtime_dbs.append(inspect_runtime_db(db_path))

    if include_processes:
        report.processes = collect_processes(repo_root, worktree_paths)

    if include_tests:
        report.test_surface = collect_test_surface(repo_root)

    report.warnings = [w.to_dict() for w in classify_warnings(report)]
    report.summary = render_summary(report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="operator_ground_truth",
        description="Read-only operator ground truth report for dharma_swarm.",
    )
    p.add_argument("--json", action="store_true", help="emit JSON to stdout instead of human text")
    p.add_argument("--repo-root", type=Path, default=None, help="override repo root")
    p.add_argument(
        "--include-processes",
        action="store_true",
        default=True,
        help="include relevant running processes (default: on)",
    )
    p.add_argument(
        "--no-processes",
        dest="include_processes",
        action="store_false",
        help="skip process discovery",
    )
    p.add_argument(
        "--include-runtime-dbs",
        action="store_true",
        default=True,
        help="include runtime DB inspection (default: on)",
    )
    p.add_argument(
        "--no-runtime-dbs",
        dest="include_runtime_dbs",
        action="store_false",
        help="skip runtime DB scan",
    )
    p.add_argument(
        "--include-tests",
        action="store_true",
        default=True,
        help="include test surface (default: on)",
    )
    p.add_argument(
        "--no-tests",
        dest="include_tests",
        action="store_false",
        help="skip test surface discovery",
    )
    p.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="exit non-zero if a critical warning is present",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional path to write the JSON report to (creates parents)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root or detect_repo_root(Path.cwd())
    if repo_root is None:
        print("error: not inside a git repo (and no --repo-root given)", file=sys.stderr)
        return 2
    repo_root = repo_root.resolve()

    report = build_report(
        repo_root,
        include_processes=args.include_processes,
        include_runtime_dbs=args.include_runtime_dbs,
        include_tests=args.include_tests,
    )

    payload = report.to_dict()

    if args.output:
        out_path = args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_terminal(report))

    if not args.fail_on_critical:
        return 0

    # Optional non-zero mode lets CI / shell users branch on critical warnings.
    has_critical = any(w["severity"] == "critical" for w in report.warnings)
    return 1 if has_critical else 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
