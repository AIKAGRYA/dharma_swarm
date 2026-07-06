"""Scratch worktree lifecycle for Forge Lab experiments."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.evolution_safety import (
    EVOLUTION_MARKER,
    is_scratch_worktree,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_worktree_root() -> Path:
    return Path(os.environ.get("DHARMA_EVOLUTION_WORKTREE_ROOT", "") or Path.home() / ".dharma" / "evolution_worktrees")


def _run_git(args: list[str], *, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr or proc.stdout}")
    return proc.stdout.strip()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


@dataclass(frozen=True)
class ScratchWorktree:
    experiment_id: str
    category: str
    root: Path
    repo: Path
    archive_path: Path
    git_base_sha: str
    registry_path: Path

    @property
    def marker_path(self) -> Path:
        return self.repo / EVOLUTION_MARKER

    def validate(self) -> None:
        ok, _marker, reason = is_scratch_worktree(self.repo)
        if not ok:
            raise RuntimeError(f"scratch worktree validation failed: {reason}")


def create_marked_scratch_worktree(
    *,
    experiment_id: str,
    category: str,
    archive_path: Path,
    source_repo: Path,
    base_ref: str = "origin/main",
    worktree_root: Path | None = None,
) -> ScratchWorktree:
    """Create a detached git worktree and immediately mark it for PR-001."""

    source_repo = source_repo.expanduser().resolve()
    base_sha = _run_git(["rev-parse", base_ref], cwd=source_repo)
    root = (worktree_root or _default_worktree_root()).expanduser().resolve()
    exp_root = root / experiment_id
    repo = exp_root / "repo"
    if repo.exists():
        raise FileExistsError(f"experiment worktree already exists: {repo}")

    exp_root.mkdir(parents=True, exist_ok=True)
    try:
        _run_git(["worktree", "add", "--detach", str(repo), base_sha], cwd=source_repo)
        marker = {
            "experiment_id": experiment_id,
            "git_base_sha": base_sha,
            "created_at": _now_iso(),
            "archive_path": str(archive_path.expanduser()),
            "category": category,
        }
        tmp_marker = repo / f"{EVOLUTION_MARKER}.tmp"
        tmp_marker.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_marker.replace(repo / EVOLUTION_MARKER)

        git_dir = Path(_run_git(["rev-parse", "--git-dir"], cwd=repo)).expanduser()
        if not git_dir.is_absolute():
            git_dir = (repo / git_dir).resolve()
        exclude = git_dir / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write(f"\n# Forge Lab experiment artifacts\n{EVOLUTION_MARKER}\n.forge_lab/\n")

        scratch = ScratchWorktree(
            experiment_id=experiment_id,
            category=category,
            root=exp_root,
            repo=repo.resolve(),
            archive_path=archive_path.expanduser(),
            git_base_sha=base_sha,
            registry_path=root / "registry.jsonl",
        )
        scratch.validate()
        _append_jsonl(
            scratch.registry_path,
            {
                "experiment_id": experiment_id,
                "category": category,
                "path": str(scratch.repo),
                "archive_path": str(scratch.archive_path),
                "git_base_sha": base_sha,
                "created_at": marker["created_at"],
                "state": "active",
            },
        )
        return scratch
    except Exception:
        try:
            _run_git(["worktree", "remove", "--force", str(repo)], cwd=source_repo)
        except Exception:
            shutil.rmtree(exp_root, ignore_errors=True)
        raise


def close_scratch_worktree(
    scratch: ScratchWorktree,
    *,
    source_repo: Path,
    keep_worktree: bool = False,
    state: str = "closed",
) -> None:
    if keep_worktree:
        state = "kept"
    else:
        _run_git(["worktree", "remove", "--force", str(scratch.repo)], cwd=source_repo.expanduser().resolve())
        _run_git(["worktree", "prune"], cwd=source_repo.expanduser().resolve())
    _append_jsonl(
        scratch.registry_path,
        {
            "experiment_id": scratch.experiment_id,
            "category": scratch.category,
            "path": str(scratch.repo),
            "archive_path": str(scratch.archive_path),
            "git_base_sha": scratch.git_base_sha,
            "closed_at": _now_iso(),
            "state": state,
        },
    )
