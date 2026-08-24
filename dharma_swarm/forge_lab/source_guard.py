"""Immutable-source admission for any RSI command that can execute work."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

CANONICAL_REPOSITORY = "https://github.com/AIKAGRYA/dharma_swarm.git"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
            env={
                "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
            },
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return result.returncode, result.stdout.strip()


def _release_manifest(repo: Path) -> dict[str, Any] | None:
    path = repo.parent / "RELEASE_MANIFEST.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def execution_source_status(repo: Path | None = None) -> dict[str, Any]:
    """Return immutable-release evidence without changing the checkout."""

    configured_text = os.environ.get("RSI_LAB_REPO", "").strip()
    configured = repo or (Path(configured_text) if configured_text else None)
    if configured is None:
        base = Path(os.environ.get("RSI_LAB_BASE", Path.home() / ".dharma/rsi-lab/current"))
        configured = base / "repo"
    source = configured.expanduser().resolve(strict=False)
    reasons: list[str] = []

    base_text = os.environ.get("RSI_LAB_BASE", "").strip()
    expected = (
        (Path(base_text).expanduser().resolve(strict=False) / "repo").resolve(strict=False)
        if base_text
        else source
    )
    if source != expected:
        reasons.append("source_not_under_resolved_RSI_LAB_BASE")
    if not source.is_dir():
        reasons.append("source_checkout_missing")

    head_code, head = _git(source, "rev-parse", "HEAD")
    if head_code != 0 or not _SHA_RE.fullmatch(head):
        reasons.append("source_commit_unavailable")
    status_code, dirty = _git(source, "status", "--porcelain", "--untracked-files=normal")
    if status_code != 0:
        reasons.append("source_cleanliness_unavailable")
    elif dirty:
        reasons.append("source_checkout_dirty")
    remote_code, remote = _git(source, "config", "--get", "remote.origin.url")
    if remote_code != 0 or remote != CANONICAL_REPOSITORY:
        reasons.append("source_remote_not_canonical_AIKAGRYA")

    manifest = _release_manifest(source)
    manifest_commit = str((((manifest or {}).get("plan") or {}).get("commit") or ""))
    if manifest is None:
        reasons.append("release_manifest_missing")
    elif manifest_commit != head:
        reasons.append("release_manifest_commit_mismatch")
    if head and source.parent.name != head:
        reasons.append("release_directory_not_full_commit")

    return {
        "ready": not reasons,
        "repo": str(source),
        "expected_repo": str(expected),
        "commit": head or None,
        "remote": remote or None,
        "canonical_repository": CANONICAL_REPOSITORY,
        "release_manifest_present": manifest is not None,
        "release_manifest_commit": manifest_commit or None,
        "reasons": reasons,
    }


def require_execution_source(repo: Path | None = None) -> dict[str, Any]:
    status = execution_source_status(repo)
    if not status["ready"]:
        raise RuntimeError("noncanonical execution source: " + ",".join(status["reasons"]))
    return status


__all__ = ["CANONICAL_REPOSITORY", "execution_source_status", "require_execution_source"]
