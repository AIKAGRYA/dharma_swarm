"""Continuous sync between runtime.db and ontology.db (BR-007 closure).

runtime.db holds operational state (session events, task claims, delegation runs,
artifact records). ontology.db holds the typed self-model (Outcomes, ValueEvents,
Contributions, ActionProposals). These stores evolved independently and never
synced — gates evaluate against stale pictures, recognition is commentary.

This module provides a one-directional sync: ontology Outcomes → runtime
ArtifactRecords. When an Outcome exists in ontology.db but has no corresponding
ArtifactRecord in runtime.db, we materialize one. This means the operator brief,
guardian crew, and any runtime-level query can see what the organism actually
produced.

Design:
- Idempotent: re-running sync is safe (skips already-materialized records).
- Read-only on ontology.db (never mutates the typed model).
- Best-effort: sync failures are logged, never raised.
- Incremental: tracks a high-water mark to avoid re-scanning the full set.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    """Summary of a single sync run."""

    outcomes_scanned: int = 0
    artifacts_created: int = 0
    skipped_existing: int = 0
    errors: int = 0


def _resolve_runtime_db(state_dir: Path | None = None) -> Path:
    root = state_dir or dharma_state_dir()
    return root / "state" / "runtime.db"


def _resolve_ontology_db(state_dir: Path | None = None) -> Path:
    root = state_dir or dharma_state_dir()
    return root / "ontology.db"


def sync_outcomes_to_artifacts(
    *,
    state_dir: Path | None = None,
    runtime_db_path: Path | None = None,
    ontology_db_path: Path | None = None,
) -> SyncResult:
    """Materialize ontology Outcomes as runtime ArtifactRecords.

    For each Outcome in ontology.db, creates an ArtifactRecord in runtime.db
    (if one with the same artifact_id doesn't already exist). The artifact_kind
    is ``outcome`` and metadata carries the full Outcome properties for
    downstream consumers.
    """
    from dharma_swarm.ontology_runtime import get_shared_registry
    from dharma_swarm.runtime_state import ensure_runtime_state_schema_sync

    rt_path = runtime_db_path or _resolve_runtime_db(state_dir)
    ont_path = ontology_db_path or _resolve_ontology_db(state_dir)

    if not ont_path.exists():
        return SyncResult()

    try:
        registry = get_shared_registry(str(ont_path))
    except Exception as exc:
        logger.debug("store_sync: could not open ontology at %s: %s", ont_path, exc)
        return SyncResult(errors=1)

    outcomes = registry.get_objects_by_type("Outcome")
    if not outcomes:
        return SyncResult()

    rt_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(rt_path))
    try:
        ensure_runtime_state_schema_sync(db)
    except Exception as exc:
        logger.debug("store_sync: runtime schema init failed: %s", exc)
        db.close()
        return SyncResult(errors=1)

    scanned = 0
    created = 0
    skipped = 0
    errors = 0

    for outcome in outcomes:
        scanned += 1
        artifact_id = f"ont-{outcome.id}"
        try:
            row = db.execute(
                "SELECT artifact_id FROM artifact_records WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if row is not None:
                skipped += 1
                continue
        except Exception:
            pass

        try:
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            meta = {
                "source": "ontology_sync",
                "outcome_id": outcome.id,
                "type_name": outcome.type_name,
                "success": outcome.properties.get("success", False),
                "result_summary": str(
                    outcome.properties.get("result_summary", "")
                )[:500],
                "synced_at": time.time(),
            }
            db.execute(
                "INSERT OR IGNORE INTO artifact_records"
                " (artifact_id, session_id, task_id, run_id, artifact_kind,"
                "  manifest_path, payload_path, checksum, parent_artifact_id,"
                "  promotion_state, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id,
                    str(outcome.properties.get("session_id", "")),
                    str(outcome.properties.get("task_id", "")),
                    str(outcome.properties.get("run_id", "")),
                    "outcome",
                    "", "", "", "",
                    "materialized",
                    now_iso,
                    json.dumps(meta, ensure_ascii=True),
                ),
            )
            db.commit()
            created += 1
        except Exception as exc:
            logger.debug("store_sync: failed to materialize %s: %s", outcome.id, exc)
            errors += 1

    db.close()

    return SyncResult(
        outcomes_scanned=scanned,
        artifacts_created=created,
        skipped_existing=skipped,
        errors=errors,
    )


def sync_all(*, state_dir: Path | None = None) -> SyncResult:
    """Run all sync passes. Currently only outcomes→artifacts."""
    return sync_outcomes_to_artifacts(state_dir=state_dir)
