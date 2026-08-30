"""Source-git identity probes for the forge_lab EXPLORE loop.

Leaf module of ``experiment``: records which source tree actually ran, as
evidence metadata for run receipts. No forge_lab imports — the dependency
direction is ``experiment`` → ``experiment_git`` only.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _git_identity(repo: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Source-code identity for run receipts.

    This is evidence metadata, not promotion authority.  Earlier forge_lab runs
    recorded ``origin/main`` as ``git_base_sha`` even when the operator was
    executing branch code via PYTHONPATH.  That made later receipts ambiguous.
    Record the actual source HEAD first, plus origin/main only as comparison.
    """

    if dry_run:
        return {
            "repo": str(repo),
            "head_sha": "dryrun",
            "branch": "dryrun",
            "dirty": False,
            "dirty_short": "",
            "origin_main_sha": "",
        }
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
    """Compatibility wrapper: return the actual source HEAD used for the run."""

    return str(_git_identity(repo).get("head_sha") or "unknown")
