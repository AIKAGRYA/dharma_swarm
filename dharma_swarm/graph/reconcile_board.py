"""Task-board settlement for graph reconcile passes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from dharma_swarm.runtime_state import RuntimeStateStore


async def settle_task_board(
    *,
    runtime_state: RuntimeStateStore,
    task_board: Any | None,
    report: Any,
    now: datetime,
    logger: logging.Logger,
) -> None:
    """Project reconciled delegation runs back into the optional task board."""
    if task_board is None:
        return
    settled = (
        [(run_id, "requeue") for run_id in report.requeued_runs]
        + [(run_id, "receipt") for run_id in report.completed_from_receipt]
        + [(run_id, "quarantine") for run_id in report.quarantined_runs]
    )
    for run_id, action in settled:
        run = await runtime_state.get_delegation_run(run_id)
        if run is None or not run.task_id:
            continue
        try:
            await _settle_one(task_board, run.task_id, run_id, action, run.status, now)
        except KeyError:
            logger.warning(
                "reconciler: task %s for run %s not on board", run.task_id, run_id
            )
        except Exception as exc:
            logger.error(
                "reconciler: task board settle (%s) failed for %s: %s",
                action,
                run.task_id,
                exc,
                exc_info=True,
            )
            report.errors.append(f"task:{run.task_id}:{type(exc).__name__}")


async def _settle_one(
    task_board: Any,
    task_id: str,
    run_id: str,
    action: str,
    run_status: str,
    now: datetime,
) -> None:
    metadata = {"reconciled_at": now.isoformat()}
    short_run_id = run_id[:12]
    if action == "requeue":
        await task_board.requeue(
            task_id,
            reason=f"Graph reconciler: orphaned run {short_run_id} requeued",
            metadata=metadata,
        )
    elif action == "receipt" and run_status == "completed":
        await task_board.complete(
            task_id,
            result=f"Graph reconciler: run {short_run_id} completed from receipt",
            metadata=metadata,
        )
    else:
        detail = (
            "quarantined (retry-exhausted)"
            if action == "quarantine"
            else "failed per receipt"
        )
        await task_board.fail(
            task_id,
            error=f"Graph reconciler: run {short_run_id} {detail}",
            metadata=metadata,
        )
