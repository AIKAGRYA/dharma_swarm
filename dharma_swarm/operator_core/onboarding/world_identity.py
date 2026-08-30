"""Fetch-free world-identity observation for session status.

One World (``docs/plans/ONE_WORLD_2026-08-30.md``, Step 4): every session
prints which world it is in — commit, host, branch, and distance from the
LOCAL ``origin/main`` ref — so drift between checkouts is visible before it
splits the world. The comparison is deliberately fetch-free: it reads local
refs only and reports how stale that view is (last observed fetch), never
touching the network.

Collection only — no policy, no rendering, no writes, no network, no
admission authority. Warning thresholds are echoed as data; turning drift
into conditions is ``cli.py``'s job, rendering is ``render.py``'s. The
projection carries ages and host identity, so it stays out of the
deterministic ``--json`` machine view by doctrine.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]

SCHEMA = "dharma_swarm.onboard_world_identity.v1"
AUTHORITY = "advisory_only"
BASE_REF = "origin/main"
# One World Step 4 thresholds: warn loudly past these, never block.
DRIFT_WARN_BEHIND = 50
DIRTY_WARN_AGE_SECONDS = 24 * 60 * 60
FETCH_FREE = True


def _git_probe(*args: str) -> tuple[str, str]:
    """One read-only Git observation: ``(stdout, typed_error)``."""
    command = "git " + " ".join(args)
    try:
        proc = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "", f"timeout after 30s: {command}"
    except OSError as exc:
        return "", f"{type(exc).__name__}: {command}"
    if proc.returncode != 0:
        return "", f"exit {proc.returncode}: {command}"
    return proc.stdout.strip(), ""


def _host_label() -> str:
    return platform.node() or os.environ.get("HOSTNAME", "") or "unknown"


def _iso_from_unix(ts: int) -> str:
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _last_fetch_age_seconds(now: float) -> float | None:
    """Age of the newest FETCH_HEAD mtime, or None when never observed.

    FETCH_HEAD is per-worktree in modern Git; the shared common-dir copy is
    checked as a fallback so a linked worktree still reports the last fetch
    observed anywhere on this host. Both reads are local file stats.
    """
    candidates: list[Path] = []
    for args in (("rev-parse", "--git-path", "FETCH_HEAD"),):
        raw, error = _git_probe(*args)
        if not error and raw:
            candidates.append(Path(raw))
    common, error = _git_probe("rev-parse", "--git-common-dir")
    if not error and common:
        candidates.append(Path(common) / "FETCH_HEAD")
    ages: list[float] = []
    for candidate in candidates:
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        try:
            ages.append(max(0.0, now - candidate.stat().st_mtime))
        except OSError:
            continue
    return min(ages) if ages else None


def _porcelain_path(line: str) -> str:
    """Extract the tracked path from one ``git status --porcelain`` line."""
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[1]
    return path.strip().strip('"')


def _oldest_dirty_entry(now: float) -> tuple[float | None, str]:
    """Oldest mtime among dirty working-tree entries; deletions are skipped."""
    status, error = _git_probe("status", "--porcelain")
    if error or not status:
        return None, ""
    oldest_age: float | None = None
    oldest_path = ""
    for line in status.splitlines():
        relative = _porcelain_path(line)
        if not relative:
            continue
        try:
            age = max(0.0, now - (REPO_ROOT / relative).stat().st_mtime)
        except OSError:
            continue
        if oldest_age is None or age > oldest_age:
            oldest_age, oldest_path = age, relative
    return oldest_age, oldest_path


def collect_world_identity(
    live_state: Mapping[str, Any] | None = None,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Return the fetch-free world-identity projection (advisory, no authority).

    ``ahead``/``behind`` reuse the already-observed live state when supplied;
    otherwise they are probed against the local ``origin/main`` ref directly.
    """
    moment = time.time() if now is None else now
    head, head_error = _git_probe("rev-parse", "HEAD")
    branch, _branch_error = _git_probe("rev-parse", "--abbrev-ref", "HEAD")

    ahead: int | None = None
    behind: int | None = None
    if live_state is not None:
        raw_ahead = live_state.get("ahead")
        raw_behind = live_state.get("behind")
        if isinstance(raw_ahead, int) and isinstance(raw_behind, int):
            ahead, behind = raw_ahead, raw_behind
    if ahead is None or behind is None:
        counts, error = _git_probe(
            "rev-list", "--left-right", "--count", f"{BASE_REF}...HEAD"
        )
        if not error:
            left, _, right = counts.partition("\t")
            try:
                behind, ahead = int(left), int(right)
            except ValueError:
                ahead = behind = None

    base_tip_ts: int | None = None
    base_tip_iso = ""
    tip, tip_error = _git_probe("log", "-1", "--format=%ct", BASE_REF)
    if not tip_error and tip.isdigit():
        base_tip_ts = int(tip)
        base_tip_iso = _iso_from_unix(base_tip_ts)

    oldest_dirty_age, oldest_dirty_path = _oldest_dirty_entry(moment)

    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "fetch_free": FETCH_FREE,
        "host": _host_label(),
        "head": head if not head_error else "",
        "branch": branch,
        "base_ref": BASE_REF,
        "ahead": ahead,
        "behind": behind,
        "base_tip_committer_ts": base_tip_ts,
        "base_tip_committer_iso": base_tip_iso,
        "last_fetch_observed_age_seconds": _last_fetch_age_seconds(moment),
        "oldest_dirty_age_seconds": oldest_dirty_age,
        "oldest_dirty_path": oldest_dirty_path,
        "drift_warn_behind": DRIFT_WARN_BEHIND,
        "dirty_warn_age_seconds": DIRTY_WARN_AGE_SECONDS,
        "session_gate": False,
    }


__all__ = [
    "AUTHORITY",
    "BASE_REF",
    "DIRTY_WARN_AGE_SECONDS",
    "DRIFT_WARN_BEHIND",
    "FETCH_FREE",
    "REPO_ROOT",
    "SCHEMA",
    "collect_world_identity",
]
