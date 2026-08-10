"""Failure closeout and scratch cleanup for paired experiments."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from dharma_swarm.forge_lab.run_receipts import _closeout


async def run_with_cleanup(
    implementation: Callable[..., Awaitable[dict[str, Any]]],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    try:
        return await implementation(**kwargs)
    except BaseException as exc:
        cfg, exp_dir, exp_id = kwargs["cfg"], kwargs["exp_dir"], kwargs["exp_id"]
        cleanup = cleanup_scratch(cfg, kwargs["seams"], kwargs.get("scratch"), exp_id)
        closeout = _closeout(
            exp_dir, exp_id, "blocked_with_evidence",
            reasons=[f"paired_setup_failure:{type(exc).__name__}:{exc}"[:1000]],
            started_at=kwargs["started_at"],
            stats={"evaluation_protocol": "paired_frozen_v1", "positive_lift_claimed": False,
                   "setup_failed_before_protocol_closeout": True},
            merkle_root=None,
            wall_seconds=round(time.monotonic() - kwargs["started_mono"], 1),
            scratch_worktree=cleanup,
        )
        if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
            raise
        return closeout


def cleanup_scratch(cfg: Any, seams: Any, scratch: Path | None, exp_id: str) -> dict[str, Any]:
    state = {
        "path": str(scratch) if scratch is not None else None,
        "keep_worktree": cfg.keep_worktree,
        "state": "not_created" if scratch is None else "kept" if cfg.keep_worktree else "pending_cleanup",
        "removed": None if scratch is None or cfg.keep_worktree else False,
    }
    if scratch is not None and not cfg.keep_worktree:
        try:
            seams.remove_worktree(source_repo=cfg.source_repo, repo=scratch, experiment_id=exp_id)
        except Exception as exc:
            state.update({"state": "cleanup_error", "removed": False,
                          "error": f"{type(exc).__name__}:{exc}"})
        else:
            removed = not scratch.exists()
            state.update({"state": "removed" if removed else "remove_unconfirmed", "removed": removed})
    return state


__all__ = ["cleanup_scratch", "run_with_cleanup"]
