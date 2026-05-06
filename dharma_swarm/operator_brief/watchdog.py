"""LEDGER_WATCHER sub-check for empty operator-brief output.

Called by ``guardian_crew.run_ledger_watcher`` when a ``runtime.db`` is
available. Emits DEGRADED when the operator-brief cron has fired ≥10
times with zero ``artifact_records`` of kind ``operator_brief``, and
BLOCKER at ≥100 ticks.

See ``docs/plans/NEXT_10_SUBSTRATE_TODO.md`` item 8.
"""

from __future__ import annotations

import sqlite3

from dharma_swarm.guardian_crew import GuardianFinding

_DEGRADED_THRESHOLD = 10
_BLOCKER_THRESHOLD = 100


def _operator_brief_tick_count(db: sqlite3.Connection) -> int:
    """Count session_events that look like operator_brief cron ticks."""
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'session_events'",
    ).fetchone()
    if exists is None:
        return 0
    row = db.execute(
        "SELECT COUNT(*) FROM session_events WHERE event_name LIKE '%operator_brief%'",
    ).fetchone()
    return int(row[0] if row else 0)


def _operator_brief_artifact_count(db: sqlite3.Connection) -> int:
    """Count artifact_records with artifact_kind = 'operator_brief'."""
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'artifact_records'",
    ).fetchone()
    if exists is None:
        return 0
    row = db.execute(
        "SELECT COUNT(*) FROM artifact_records WHERE artifact_kind = 'operator_brief'",
    ).fetchone()
    return int(row[0] if row else 0)


def check_operator_brief_output(
    db: sqlite3.Connection,
    runtime_db_path: str,
) -> list[GuardianFinding]:
    """Return findings for empty operator-brief artifact output."""
    ticks = _operator_brief_tick_count(db)
    artifacts = _operator_brief_artifact_count(db)
    if ticks < _DEGRADED_THRESHOLD or artifacts > 0:
        return []
    severity = "BLOCKER" if ticks >= _BLOCKER_THRESHOLD else "DEGRADED"
    return [
        GuardianFinding(
            severity=severity,
            check="LEDGER_WATCHER:operator_brief_empty",
            title="Operator brief cron has fired without producing artifacts",
            detail=(
                f"{runtime_db_path} has {ticks} operator_brief session events "
                f"but {artifacts} artifact_records with "
                f"artifact_kind='operator_brief'. The cron is running but "
                "not materialising KnowledgeArtifact rows."
            ),
            file=runtime_db_path,
            fix_hint=(
                "Check DHARMA_OPERATOR_BRIEF_ENABLED=1, verify gate "
                "decisions are not all blocking, and inspect "
                "operator_brief persistence in RuntimeStateStore."
            ),
        )
    ]
