"""Canonical daemon version identity.

build_id = f"{__version__}+{git_short_sha}"  e.g. "0.1.0+9c76b2106".

Source of truth:
  - dharma_swarm.__version__  (the package version, currently "0.1.0")
  - `git rev-parse --short HEAD` of the checkout this code runs from.

Both are resolved once at import and cached. NOTHING here may raise: a missing
git binary, a non-repo checkout, or an import-order problem all degrade to
"+unknown" rather than crashing the daemon's liveness probe.
"""
from __future__ import annotations

import os
import subprocess
import time
from functools import lru_cache
from pathlib import Path

_UNKNOWN_SHA = "unknown"
_PROCESS_STARTED_AT = time.time()


def _package_version() -> str:
    try:
        from dharma_swarm import __version__  # local import: never fail at module load

        return str(__version__)
    except Exception:
        return "0.0.0"


def _repo_root() -> Path:
    # daemon_version.py -> versioning -> dharma_swarm -> repo root
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def git_short_sha() -> str:
    """Short SHA of the checkout this module lives in. Never raises.

    Honors DHARMA_BUILD_SHA override (set in container builds where .git is
    absent). Appends ".dirty" for local checkout builds with uncommitted or
    untracked changes. Falls back to "unknown".
    """
    override = os.environ.get("DHARMA_BUILD_SHA")
    if override:
        return override.strip()[:12] or _UNKNOWN_SHA
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        sha = (out.stdout or "").strip()
        if out.returncode == 0 and sha:
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(_repo_root()),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if dirty.returncode == 0 and (dirty.stdout or "").strip():
                return f"{sha}.dirty"
            return sha
    except Exception:
        pass
    return _UNKNOWN_SHA


@lru_cache(maxsize=1)
def daemon_version() -> str:
    """Return the canonical build_id, e.g. "0.1.0+9c76b2106"."""
    return f"{_package_version()}+{git_short_sha()}"


def version_stamp() -> dict:
    """Return the full version stamp dict for /health and metric tagging.

    Five keys, always present, never raises: build_id, daemon_version,
    git_sha, started_at (process start, epoch float), pid.
    """
    return {
        "build_id": daemon_version(),
        "daemon_version": _package_version(),
        "git_sha": git_short_sha(),
        "started_at": _PROCESS_STARTED_AT,
        "pid": os.getpid(),
    }
