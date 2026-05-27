"""TaskBoard adapter for Darshan decision deltas."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.models import Task, TaskPriority
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.venture_cell.darshan.bundle import validate_bundle
from dharma_swarm.venture_cell.darshan.schema import DecisionDelta


def default_task_db_path() -> Path:
    return dharma_state_dir("DHARMA_STATE_DIR") / "db" / "tasks.db"


async def create_followup_task(
    bundle_path: Path,
    *,
    db_path: Path | None = None,
) -> Task:
    result = validate_bundle(bundle_path)
    if not result.valid:
        raise ValueError("; ".join(result.errors))
    manifest = result.manifest
    if manifest is None:
        raise ValueError("bundle manifest missing")

    delta = DecisionDelta.model_validate(
        json.loads((result.bundle_path / "decision_delta.json").read_text(encoding="utf-8"))
    )
    task_db = db_path or default_task_db_path()
    task_db.parent.mkdir(parents=True, exist_ok=True)
    board = TaskBoard(task_db)
    await board.init_db()
    return await board.create(
        title=f"Darshan follow-up: {manifest.title}",
        description=delta.delta_summary or "Review Darshan decision delta and route next work.",
        priority=TaskPriority.NORMAL,
        created_by="darshan_venture_cell",
        metadata={
            "cell_id": "DARSHAN",
            "artifact_id": manifest.artifact_id,
            "bundle_path": str(result.bundle_path),
            "decision_delta_path": str(result.bundle_path / "decision_delta.json"),
            "affected_cells": delta.affected_cells,
            "followup_owner": delta.followup_owner,
        },
    )
