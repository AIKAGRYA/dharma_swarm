"""BSP helper functions for :mod:`dharma_swarm.orchestrator`.

These helpers keep Pregel/BSP hardening logic decomposed from the already-large
orchestrator module while preserving Orchestrator's public/private method names.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from dharma_swarm.models import TaskStatus

if TYPE_CHECKING:
    from dharma_swarm.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def combine_results(fragments: list[str]) -> str:
    """Associative combiner: deduplicate structured findings when present."""
    import re as _re

    if not fragments:
        return ""
    if len(fragments) == 1:
        return fragments[0]
    finding_blocks: list[str] = []
    remainder_blocks: list[str] = []
    for fragment in fragments:
        match = _re.search(
            r"(?:##\s+(?:Findings|Results|Summary)[^\n]*\n)(.+?)(?=\n##|\Z)",
            fragment,
            _re.S | _re.I,
        )
        if match:
            finding_blocks.append(match.group(1).strip())
        else:
            remainder_blocks.append(fragment.strip())
    if not finding_blocks:
        return "\n\n---\n\n".join(fragments)
    seen: set[str] = set()
    deduped: list[str] = []
    for block in finding_blocks:
        for line in block.splitlines():
            key = line.strip().lstrip("-* ").lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(line)
    combined = "## Combined Findings\n" + "\n".join(deduped)
    if remainder_blocks:
        combined += "\n\n" + "\n\n---\n\n".join(remainder_blocks)
    return combined


async def collect_completed_with_barrier(orch: "Orchestrator") -> tuple[int, int]:
    """Hard BSP barrier: wait for all running S_n tasks before returning."""
    barrier_recovered = 0
    if orch._running_tasks:
        pending_by_task = {
            task_id: atask
            for task_id, atask in orch._running_tasks.items()
            if not atask.done()
        }
        if pending_by_task:
            barrier_recovered = await _cancel_barrier_stragglers(orch, pending_by_task)
    settled, recovered = await orch._collect_completed()
    return settled, recovered + barrier_recovered


async def _cancel_barrier_stragglers(
    orch: "Orchestrator",
    pending_by_task: dict[str, asyncio.Task],
) -> int:
    barrier_timeout = orch._default_timeout_seconds + 60.0
    _done, still_pending = await asyncio.wait(
        pending_by_task.values(),
        timeout=barrier_timeout,
        return_when=asyncio.ALL_COMPLETED,
    )
    if not still_pending:
        return 0
    atask_to_task_id = {atask: task_id for task_id, atask in pending_by_task.items()}
    for straggler in still_pending:
        straggler.cancel()
        logger.warning("BSP barrier: cancelled straggler task after %.0fs", barrier_timeout)
    await asyncio.wait(still_pending, timeout=5.0, return_when=asyncio.ALL_COMPLETED)
    recovered = 0
    for straggler in still_pending:
        task_id = atask_to_task_id.get(straggler)
        if task_id is not None:
            recovered += await _settle_cancelled_straggler(
                orch, task_id, straggler, barrier_timeout
            )
    return recovered


async def _settle_cancelled_straggler(
    orch: "Orchestrator",
    task_id: str,
    atask: asyncio.Task,
    barrier_timeout: float,
) -> int:
    """Settle only a stopped straggler whose exact custody was released."""
    if not atask.done() or orch._running_tasks.get(task_id) is not atask:
        logger.error("BSP barrier retained live custody for task %s", task_id)
        return 0
    td = orch._active_dispatches.get(task_id)
    if td is None:
        orch._running_tasks.pop(task_id, None)
        owner = orch._running_dispatch_owners.get(task_id)
        if owner is not None and owner[0] is atask:
            orch._running_dispatch_owners.pop(task_id, None)
        return 0
    task = await orch._safe_get_task(task_id)
    from dharma_swarm.orchestrator_execution import release_generic_dispatch

    if not await release_generic_dispatch(orch, td):
        logger.error("BSP barrier retained unreleased custody for task %s", task_id)
        return 0
    orch._running_tasks.pop(task_id, None)
    owner = orch._running_dispatch_owners.get(task_id)
    if owner is not None and owner[0] is atask:
        orch._running_dispatch_owners.pop(task_id, None)
    await orch._handle_task_failure(
        td=td,
        task=task,
        error=f"BSP barrier cancelled straggler after {barrier_timeout:.1f}s",
        source="bsp_barrier_timeout",
    )
    return 1


class _SuperstepSnapshot(BaseModel):
    superstep_id: int
    running_task_ids: list[str]
    saved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


async def save_superstep_checkpoint(orch: "Orchestrator") -> None:
    """Atomic write of current superstep state for crash recovery."""
    checkpoint_dir = orch._runtime_root() / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / "orchestrator_superstep.json"
    data = _SuperstepSnapshot(
        superstep_id=orch._superstep_id,
        running_task_ids=list(orch._running_tasks.keys()),
    )
    tmp_path = ""
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=checkpoint_dir,
            suffix=".tmp",
            prefix="superstep_",
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(data.model_dump_json())
        os.replace(tmp_path, path)
    except OSError as exc:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        logger.debug("Superstep checkpoint write failed (non-fatal): %s", exc)


async def clear_stale_claims(orch: "Orchestrator") -> None:
    """Strip active_claim from tasks that settled this superstep."""
    if orch._board is None:
        return
    for status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        try:
            tasks = await orch._board.list_tasks(status=status, limit=200)
        except (AttributeError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("claim clear list failed for %s: %s", status.value, exc)
            continue
        for task in tasks:
            meta = dict(task.metadata or {})
            if "active_claim" not in meta:
                continue
            meta.pop("active_claim")
            meta["claim_cleared_superstep"] = orch._superstep_id
            await orch._safe_update_task(task.id, metadata=meta)


async def is_globally_halted(orch: "Orchestrator") -> bool:
    """True when all vertices are inactive/idle and no work/messages remain."""
    if orch._running_tasks:
        return False
    if not await _board_quiescent(orch):
        return False
    if not await _pool_quiescent(orch):
        return False
    return await _bus_quiescent(orch)


async def _board_quiescent(orch: "Orchestrator") -> bool:
    if orch._board is None:
        return True
    try:
        return not bool(await orch._board.get_ready_tasks())
    except (AttributeError, RuntimeError, OSError, ValueError) as exc:
        logger.debug("halt check board read failed: %s", exc)
        return False


async def _pool_quiescent(orch: "Orchestrator") -> bool:
    if orch._pool is None:
        return True
    try:
        agents = await orch._pool.list_agents()
    except (AttributeError, RuntimeError, OSError, ValueError) as exc:
        logger.debug("halt check pool read failed: %s", exc)
        return False
    active_statuses = {"busy", "starting"}
    return not any(
        str(getattr(agent, "status", "")).lower() in active_statuses
        for agent in agents
    )


async def _bus_quiescent(orch: "Orchestrator") -> bool:
    if orch._bus is None:
        return True
    try:
        stats = await orch._bus.get_stats()
    except (AttributeError, RuntimeError, OSError, ValueError) as exc:
        logger.debug("halt check bus stats failed: %s", exc)
        return False
    return int(stats.get("unread_messages", 0)) <= 0
