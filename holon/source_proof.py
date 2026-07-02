"""Source proof helpers for standalone Holon receipts."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from holon.receipts import stable_digest


def package_source_proof(package_root: Path | None = None) -> dict[str, Any]:
    """Return a deterministic digest for the installed Holon package files.

    When the package is running from a git checkout, include the current HEAD
    and dirty state as additional context. The file digest remains the portable
    proof for installed wheels where ``.git`` is absent.
    """

    root = package_root or Path(__file__).resolve().parent
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts:
            continue
        data = path.read_bytes()
        files.append(
            {
                "path": rel,
                "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    proof = {
        "schema_version": "holon.source_proof.v1",
        "package_root": str(root),
        "file_count": len(files),
        "files": files,
    }
    proof["source_tree_digest"] = stable_digest(
        {
            "schema_version": proof["schema_version"],
            "files": files,
        }
    )
    proof.update(_git_context(root))
    return proof


def _git_context(root: Path) -> dict[str, Any]:
    repo = _find_git_root(root)
    if repo is None:
        return {
            "git_available": False,
            "git_head": "",
            "git_dirty": None,
            "git_root": "",
        }
    head = _git(["rev-parse", "HEAD"], repo)
    status = _git(["status", "--short", "--", str(root)], repo)
    return {
        "git_available": bool(head),
        "git_head": head,
        "git_dirty": bool(status.strip()),
        "git_root": str(repo),
        "git_status_short_digest": stable_digest(status.splitlines()),
    }


def _find_git_root(path: Path) -> Path | None:
    current = path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _git(args: list[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()
