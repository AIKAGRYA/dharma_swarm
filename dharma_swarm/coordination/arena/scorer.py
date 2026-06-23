"""Deterministic scorer / test-oracle — the SOLE correctness authority (spec §3, §6).

The Council NEVER judges correctness; this scorer does, and only this scorer.
It reads sealed labels from the taskpack (it is the scorer-only path) and exact-
matches normalized worker answers. It is hermetic, deterministic, and replayable:
the same submission against the same frozen taskpack always yields the same
scorecard and the same ``scorecard_hash``.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from typing import Any

from dharma_swarm.coordination.arena.taskpack import Taskpack, normalize_answer

SCORER_SCHEMA = "orchestration_arena_v1_scorecard.v1"


def score_one(taskpack: Taskpack, task_id: str, answer: str) -> bool:
    """True iff ``answer`` exactly matches the sealed label (normalized)."""
    return normalize_answer(answer) == normalize_answer(taskpack.sealed_label(task_id))


def score_submission(
    taskpack: Taskpack, submission: dict[str, str], *, arm: str
) -> dict[str, Any]:
    """Score one arm's per-task answers. Returns a deterministic scorecard.

    ``submission`` maps task_id -> answer string. Missing tasks score as wrong.
    """
    per_task: dict[str, bool] = {}
    for task_id in taskpack.task_ids():
        per_task[task_id] = score_one(taskpack, task_id, submission.get(task_id, ""))
    correct = sum(1 for v in per_task.values() if v)
    total = len(per_task)
    return {
        "schema": SCORER_SCHEMA,
        "arm": arm,
        "correct": correct,
        "total": total,
        "score": round(correct / total, 6) if total else 0.0,
        "per_task": per_task,
    }


def scorer_hash() -> str:
    """Hash of the scorer source — pins the correctness oracle per epoch."""
    src = inspect.getsource(inspect.getmodule(score_submission))
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def scorecard_hash(scorecard: dict[str, Any]) -> str:
    """Replay hash of a scorecard (same inputs -> same scorecard -> same hash)."""
    payload = json.dumps(scorecard, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "SCORER_SCHEMA",
    "score_one",
    "score_submission",
    "scorecard_hash",
    "scorer_hash",
]
