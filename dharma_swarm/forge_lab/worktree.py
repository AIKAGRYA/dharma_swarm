"""Marked scratch worktree — packet §3 contract. Ordering is load-bearing.

1. ``git worktree add --detach <root>/<experiment_id>/repo <base_ref>``
2. Write the marker ATOMICALLY as the FIRST file (before it exists, a fresh
   dharma_swarm worktree matches the guard's protected-repo detection and even
   shadow writes are denied).
3. Append marker + lab artifact dirs to .git/info/exclude (untracked files
   would make RuntimeCodeIdentity report non_promotable forever).
4. Assert ``is_scratch_worktree(repo)[0]`` — catches the /tmp resolve trap.
5. Registry row so estate_hygiene can whitelist lab worktrees.
6. Remove at closeout: the archive is the durable record, the worktree is not.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.evolution_safety import (
    EVOLUTION_MARKER,
    evolution_worktree_roots,
    is_scratch_worktree,
)

REGISTRY_NAME = "registry.jsonl"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=300
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout.strip()


def create_marked_scratch_worktree(
    *,
    source_repo: Path,
    experiment_id: str,
    archive_path: Path,
    base_ref: str = "origin/main",
    category: str = "agent_evolution",
) -> Path:
    root = evolution_worktree_roots()[0]
    repo = (root / experiment_id / "repo").resolve()
    repo.parent.mkdir(parents=True, exist_ok=True)
    base_sha = _git(source_repo, "rev-parse", base_ref)
    _git(source_repo, "worktree", "add", "--detach", str(repo), base_sha)

    marker = {
        "experiment_id": experiment_id,
        "git_base_sha": base_sha,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archive_path": str(archive_path),
        "category": category,
    }
    tmp = repo / (EVOLUTION_MARKER + ".tmp")
    tmp.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    tmp.rename(repo / EVOLUTION_MARKER)

    exclude = repo / ".git"
    # linked worktrees have a .git FILE pointing at the real gitdir
    if exclude.is_file():
        gitdir = Path(exclude.read_text().split("gitdir:", 1)[1].strip())
        info = gitdir / "info"
    else:
        info = exclude / "info"
    info.mkdir(parents=True, exist_ok=True)
    with (info / "exclude").open("a", encoding="utf-8") as fh:
        fh.write(f"\n{EVOLUTION_MARKER}\nforge_lab_artifacts/\n")

    ok, _marker, reason = is_scratch_worktree(repo)
    if not ok:
        raise RuntimeError(f"scratch worktree failed guard validation: {reason}")

    registry = root / REGISTRY_NAME
    with registry.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "experiment_id": experiment_id,
                    "path": str(repo),
                    "created_at": marker["created_at"],
                    "state": "active",
                }
            )
            + "\n"
        )
    return repo


def remove_scratch_worktree(*, source_repo: Path, repo: Path, experiment_id: str) -> None:
    subprocess.run(
        ["git", "-C", str(source_repo), "worktree", "remove", "--force", str(repo)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    subprocess.run(
        ["git", "-C", str(source_repo), "worktree", "prune"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    root = evolution_worktree_roots()[0]
    registry = root / REGISTRY_NAME
    if registry.exists():
        with registry.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "experiment_id": experiment_id,
                        "path": str(repo),
                        "closed_at": datetime.now(timezone.utc).isoformat(),
                        "state": "closed",
                    }
                )
                + "\n"
            )


__all__ = ["create_marked_scratch_worktree", "remove_scratch_worktree", "REGISTRY_NAME"]
