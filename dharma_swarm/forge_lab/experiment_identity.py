"""Git source identity evidence for Forge Lab experiment receipts."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _git_identity(repo: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Record actual source HEAD; origin/main is comparison evidence only."""
    if dry_run:
        return {"repo": str(repo), "head_sha": "dryrun", "branch": "dryrun",
                "dirty": False, "dirty_short": "", "origin_main_sha": ""}
    dirty_short = _git(repo, "status", "--short")
    return {
        "repo": str(repo),
        "head_sha": _git(repo, "rev-parse", "HEAD") or "unknown",
        "branch": _git(repo, "branch", "--show-current") or "detached",
        "dirty": bool(dirty_short.strip()),
        "dirty_short": dirty_short,
        "origin_main_sha": _git(repo, "rev-parse", "origin/main"),
    }


def _git_sha(repo: Path) -> str:
    """Compatibility wrapper returning the actual source HEAD."""
    return str(_git_identity(repo).get("head_sha") or "unknown")


__all__ = ["_git", "_git_identity", "_git_sha"]
