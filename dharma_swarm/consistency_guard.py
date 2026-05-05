"""NEW-05: Task-claim lifecycle consistency guard.

Cross-references task_board.tasks (status) against
runtime_state.task_claims (status) to find split-lifecycle mismatches
that indicate silent data loss.

Used by guardian_crew as part of the guardian cycle.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dharma_swarm.guardian_crew import GuardianFinding


def _runtime_db_candidates(state_dir: Path) -> list[Path]:
    """Return state-local runtime DB candidates."""
    return [
        state_dir / "state" / "runtime.db",
        state_dir / "runtime.db",
    ]


async def run_task_consistency_guard(
    state_dir: Path,
) -> list["GuardianFinding"]:
    """Detect COMPLETED tasks with still-OPEN claims in runtime_state.

    Returns a list of GuardianFinding instances (BLOCKER for mismatches,
    INFO when everything is consistent).
    """
    from dharma_swarm.guardian_crew import GuardianFinding

    findings: list[GuardianFinding] = []
    db_candidates = _runtime_db_candidates(state_dir)
    db_path: Path | None = None
    for c in db_candidates:
        if c.exists():
            db_path = c
            break
    if db_path is None:
        return findings

    try:
        db = sqlite3.connect(str(db_path))
        db.execute("PRAGMA busy_timeout=5000")
    except Exception:
        return findings

    try:
        for tbl in ("tasks", "task_claims"):
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (tbl,),
            ).fetchone()
            if exists is None:
                db.close()
                return findings

        mismatched = db.execute(
            "SELECT t.id, t.title, t.status, c.claim_id, c.status"
            " FROM tasks t"
            " JOIN task_claims c ON c.task_id = t.id"
            " WHERE t.status IN ('completed', 'done', 'failed')"
            "   AND c.status NOT IN ('released', 'completed', 'failed', 'expired')"
        ).fetchall()

        for row in mismatched:
            task_id, title, task_status, claim_id, claim_status = row
            findings.append(GuardianFinding(
                severity="BLOCKER",
                check="CONSISTENCY:task_claim_lifecycle",
                title=f"Split lifecycle: task {task_id[:8]} is {task_status} but claim {claim_id[:8]} is {claim_status}",
                detail=(
                    f"Task '{title}' (id={task_id}) has status={task_status} "
                    f"in task_board but claim {claim_id} still has "
                    f"status={claim_status} in runtime_state. "
                    f"This indicates a split-lifecycle mismatch (NEW-05). "
                    f"The claim should be released or completed when the task finishes."
                ),
                file="dharma_swarm/runtime_state.py",
                line=0,
                fix_hint="Close the claim when transitioning the task to completed/failed.",
            ))

        if not mismatched:
            findings.append(GuardianFinding(
                severity="INFO",
                check="CONSISTENCY:task_claim_lifecycle",
                title="Task-claim lifecycle consistency: OK",
                detail="All completed/failed tasks have properly closed claims.",
                file="dharma_swarm/guardian_crew.py",
            ))
    finally:
        db.close()

    return findings
