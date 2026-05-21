"""LEDGER_WATCHER sub-check for empty operator-brief output and control
surface envelope DEGRADED zones.

Called by ``guardian_crew.run_ledger_watcher`` when a ``runtime.db`` is
available. Emits DEGRADED when the operator-brief cron has fired ≥10
times with zero ``artifact_records`` of kind ``operator_brief``, and
BLOCKER at ≥100 ticks.

Also checks the ControlSurfaceEnvelope for DEGRADED zones and surfaces
them as GuardianFindings so the operator cockpit issues are visible in
the guardian report.

See ``docs/plans/NEXT_10_SUBSTRATE_TODO.md`` item 8.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from dharma_swarm.guardian_crew import GuardianFinding

logger = logging.getLogger(__name__)

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


def _operator_brief_artifacts_missing_trace(db: sqlite3.Connection) -> int:
    """Count operator_brief artifact records whose metadata lacks trace_id."""
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'artifact_records'",
    ).fetchone()
    if exists is None:
        return 0
    rows = db.execute(
        """
        SELECT metadata_json FROM artifact_records
        WHERE artifact_kind = 'operator_brief'
        """
    ).fetchall()
    missing = 0
    for row in rows:
        try:
            metadata = json.loads(row[0] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if not str(metadata.get("trace_id") or "").strip():
            missing += 1
    return missing


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


def check_operator_brief_trace_coverage(
    db: sqlite3.Connection,
    runtime_db_path: str,
) -> list[GuardianFinding]:
    """Return DEGRADED findings for operator-brief artifacts lacking trace_id."""
    artifacts = _operator_brief_artifact_count(db)
    if artifacts == 0:
        return []
    missing = _operator_brief_artifacts_missing_trace(db)
    if missing == 0:
        return []
    return [
        GuardianFinding(
            severity="DEGRADED",
            check="LEDGER_WATCHER:operator_brief_trace_coverage",
            title="Operator brief artifacts lack trace identity",
            detail=(
                f"{runtime_db_path} has {missing}/{artifacts} operator_brief "
                "artifact_records without metadata.trace_id. Trace Attractor can "
                "still project legacy aliases, but native causality is degraded."
            ),
            file=runtime_db_path,
            fix_hint=(
                "Run operator_brief under CorrelationContext and preserve "
                "metadata.trace_id / metadata.trace_id_source in RuntimeStateStore."
            ),
        )
    ]


def check_control_surface_envelope_degraded() -> list[GuardianFinding]:
    """Surface DEGRADED zones from the ControlSurfaceEnvelope.

    Builds the control surface projection and emits a GuardianFinding for
    each row whose coherence_state indicates drift or degradation, so that
    the operator cockpit issues are visible in the guardian report.
    """
    try:
        from dharma_swarm.operator_core.control_surface import (
            build_control_surface_rows,
        )
        from dharma_swarm.operator_core.control_surface_models import (
            ControlSurfaceEnvelope,
        )
    except ImportError:
        logger.debug("control_surface module not available; skipping envelope check")
        return []

    try:
        rows = build_control_surface_rows()
    except Exception as exc:
        logger.warning("control surface projection failed: %s", exc)
        return [
            GuardianFinding(
                severity="DEGRADED",
                check="LEDGER_WATCHER:control_surface_envelope",
                title="Control surface projection failed",
                detail=f"Could not build ControlSurfaceEnvelope: {exc}",
                fix_hint="Check control_surface.py and ACTIVE_SURFACE_MANIFEST.yaml",
            ),
        ]

    findings: list[GuardianFinding] = []
    degraded_states = ("drifted", "declared_only")

    for row in rows:
        if row.coherence_state in degraded_states:
            severity = "DEGRADED"
            findings.append(
                GuardianFinding(
                    severity=severity,
                    check="LEDGER_WATCHER:control_surface_envelope",
                    title=f"Control surface zone '{row.label}' is {row.coherence_state}",
                    detail=(
                        f"Row {row.id} (kind={row.kind}) has "
                        f"coherence_state={row.coherence_state}. "
                        f"Declared: {row.declared_state or 'N/A'}, "
                        f"Observed: {row.observed_state or 'N/A'}."
                    ),
                    file=row.owner_module or "",
                    fix_hint=row.next_action or "Investigate declared-vs-observed gap",
                ),
            )

    # Reference ControlSurfaceEnvelope to confirm wiring is live
    _ = ControlSurfaceEnvelope  # noqa: F841 — confirms import is exercised

    return findings
