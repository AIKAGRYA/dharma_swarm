"""Filesystem + git-bound notary anchor.

Wraps the core `LocalFileAnchor` with actual git-HEAD binding via
subprocess and on-disk jsonl append. Kept in the rim because:

  - subprocess.run is Effect.SUBPROCESS \u2014 no static reasoning possible.
  - git behavior varies with git version, config, worktree state.
  - open(..., 'a') is Effect.FS_WRITE.

The core provides the abstract `NotaryAnchor` seam and a pure
`_build_receipt()`; Phase 1+ can swap in an RFC 3161 or OpenTimestamps
anchor behind the same interface without touching the verified core.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from telos_kernel.effects import Effect, effect
from telos_kernel.notary import AnchorReceipt, LocalFileAnchor
from telos_kernel.result import ERR_GIT_UNAVAILABLE, Err, KernelError, Ok, Result


class GitBoundLocalFileAnchor(LocalFileAnchor):
    """LocalFileAnchor with real git-HEAD binding and on-disk append.

    Overrides:
      * `_git_head_result()`: invokes `git rev-parse HEAD` via subprocess.
      * `anchor()`: writes each receipt to the append-only jsonl file.

    Everything else (pure receipt construction, Result-typed error
    handling) is inherited from the core LocalFileAnchor.
    """

    def __init__(self, path="~/.dharma/merkle_anchors.jsonl", git_repo=None):
        super().__init__(path=path, git_repo=git_repo)
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._git_repo = Path(git_repo).expanduser() if git_repo else None

    @effect(Effect.SUBPROCESS, Effect.FS_READ)
    def _git_head_result(self) -> Result:
        try:
            cwd = str(self._git_repo) if self._git_repo else None
            out = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5, check=False, cwd=cwd,
            )
            if out.returncode == 0:
                return Ok(out.stdout.strip())
            return Err(KernelError(
                ERR_GIT_UNAVAILABLE,
                f"git rev-parse returned {out.returncode}",
            ))
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            return Err(KernelError(ERR_GIT_UNAVAILABLE, f"git rev-parse failed: {e}"))

    @effect(Effect.FS_WRITE, Effect.SUBPROCESS)
    def anchor(self, root_hash: str) -> AnchorReceipt:
        receipt = self._build_receipt(root_hash)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt.__dict__, sort_keys=True) + "\n")
        return receipt
