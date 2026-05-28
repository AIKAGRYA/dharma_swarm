"""Uplift guard #8: spine ownership declarations.

Every file under dharma_swarm/ that imports sqlite3 or aiosqlite must
declare its relationship to EvidenceReceipt via a '# spine: ...' header
comment. Files that existed before the spine are grandfathered; future
PRs shrink that list as each module declares its role.

Also verifies that spine package modules parse and export expected symbols.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_SPINE_DECL_RE = re.compile(r"^#\s*spine:\s*\S+", re.MULTILINE)

_SQLITE_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?:sqlite3|aiosqlite)|from\s+(?:sqlite3|aiosqlite)\s+import)",
    re.MULTILINE,
)


def _is_grandfathered(rel: Path) -> bool:
    """Files that existed before the spine are grandfathered.

    PR A grandfathers ALL existing files. Future PRs will shrink this list
    as each module declares its relation to EvidenceReceipt.
    """
    if str(rel).startswith("dharma_swarm/spine/"):
        return False
    return True


def _check_sqlite_declarations(repo_root: Path) -> list[str]:
    """Check .py files under dharma_swarm/ that import sqlite3/aiosqlite."""
    dharma_pkg = repo_root / "dharma_swarm"
    failures: list[str] = []

    for root, _dirs, files in os.walk(dharma_pkg):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            rel = fpath.relative_to(repo_root)

            try:
                content = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if not _SQLITE_IMPORT_RE.search(content):
                continue

            if _SPINE_DECL_RE.search(content):
                continue

            if _is_grandfathered(rel):
                continue

            failures.append(str(rel))

    return failures


def _check_spine_importable(repo_root: Path) -> list[str]:
    """Verify spine modules parse and export expected symbols."""
    failures: list[str] = []
    script = (
        "import sys, types, os\n"
        "root = os.environ['REPO_ROOT']\n"
        "sys.path.insert(0, root)\n"
        "sys.modules.setdefault('dharma_swarm', types.ModuleType('dharma_swarm'))\n"
        "sys.modules['dharma_swarm'].__path__ = [os.path.join(root, 'dharma_swarm')]\n"
        "sp = types.ModuleType('dharma_swarm.spine')\n"
        "sp.__path__ = [os.path.join(root, 'dharma_swarm', 'spine')]\n"
        "sys.modules['dharma_swarm.spine'] = sp\n"
        "from dharma_swarm.spine import receipt, routing, invoke\n"
        "assert hasattr(receipt, 'EvidenceReceipt'), 'missing EvidenceReceipt'\n"
        "assert hasattr(routing, 'RoutingDecision'), 'missing RoutingDecision'\n"
        "assert hasattr(invoke, 'invoke_agent'), 'missing invoke_agent'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "REPO_ROOT": str(repo_root)},
    )
    if result.returncode != 0:
        err = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
        failures.append(f"spine import failed: {err}")
    return failures


def check_spine_ownership(repo_root: Path) -> tuple[bool, str]:
    """Guard #8: verify spine ownership declarations.

    Returns (True, message) on pass, (False, message) on failure.
    Crash semantics: fail-closed (handled by run_pre_commit.py).
    """
    failures: list[str] = []
    failures.extend(_check_spine_importable(repo_root))
    failures.extend(_check_sqlite_declarations(repo_root))

    if failures:
        detail = "; ".join(failures[:3])
        return False, f"{len(failures)} spine-ownership failure(s): {detail}"

    return True, "spine-ownership: all declarations present"
