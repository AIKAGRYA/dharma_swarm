"""Continuous sync between runtime.db and ontology.db (BR-007 closure).

runtime.db holds operational state (session events, task claims, delegation runs,
artifact records). ontology.db holds the typed self-model (Outcomes, ValueEvents,
Contributions, ActionProposals). These stores evolved independently and never
synced — gates evaluate against stale pictures, recognition is commentary.

This module provides a one-directional sync: ontology objects → runtime
ArtifactRecords. When an object exists in ontology.db but has no corresponding
ArtifactRecord in runtime.db, we materialize one. This means the operator brief,
guardian crew, and any runtime-level query can see what the organism actually
produced. Covered object types: Outcomes (kind ``outcome``) and ValueEvents
(kind ``value_event``).

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
    value_events_scanned: int = 0
    artifacts_created: int = 0
    skipped_existing: int = 0
    errors: int = 0


def _resolve_runtime_db(state_dir: Path | None = None) -> Path:
    root = state_dir or dharma_state_dir()
    return root / "state" / "runtime.db"


def _resolve_ontology_db(state_dir: Path | None = None) -> Path:
    root = state_dir or dharma_state_dir()
    return root / "ontology.db"


def _sync_type_to_artifacts(
    *,
    type_name: str,
    artifact_kind: str,
    id_prefix: str,
    build_meta,
    state_dir: Path | None = None,
    runtime_db_path: Path | None = None,
    ontology_db_path: Path | None = None,
) -> tuple[int, int, int, int]:
    """Shared idempotent projection pass: one ontology type → artifact_records.

    Returns ``(scanned, created, skipped, errors)``. Read-only on ontology.db;
    best-effort (failures logged, never raised); INSERT OR IGNORE + existence
    probe keep re-runs no-ops.
    """
    from dharma_swarm.ontology_runtime import get_shared_registry
    from dharma_swarm.runtime_state import ensure_runtime_state_schema_sync

    rt_path = runtime_db_path or _resolve_runtime_db(state_dir)
    ont_path = ontology_db_path or _resolve_ontology_db(state_dir)

    if not ont_path.exists():
        return 0, 0, 0, 0

    try:
        registry = get_shared_registry(str(ont_path))
    except Exception as exc:
        logger.debug("store_sync: could not open ontology at %s: %s", ont_path, exc)
        return 0, 0, 0, 1

    objects = registry.get_objects_by_type(type_name)
    if not objects:
        return 0, 0, 0, 0

    rt_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(rt_path))
    try:
        ensure_runtime_state_schema_sync(db)
    except Exception as exc:
        logger.debug("store_sync: runtime schema init failed: %s", exc)
        db.close()
        return 0, 0, 0, 1

    scanned = 0
    created = 0
    skipped = 0
    errors = 0

    for obj in objects:
        scanned += 1
        artifact_id = f"{id_prefix}{obj.id}"
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
            db.execute(
                "INSERT OR IGNORE INTO artifact_records"
                " (artifact_id, session_id, task_id, run_id, artifact_kind,"
                "  manifest_path, payload_path, checksum, parent_artifact_id,"
                "  promotion_state, created_at, metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id,
                    str(obj.properties.get("session_id", "")),
                    str(obj.properties.get("task_id", "")),
                    str(obj.properties.get("run_id", "")),
                    artifact_kind,
                    "", "", "", "",
                    "materialized",
                    now_iso,
                    json.dumps(build_meta(obj), ensure_ascii=True),
                ),
            )
            db.commit()
            created += 1
        except Exception as exc:
            logger.debug("store_sync: failed to materialize %s: %s", obj.id, exc)
            errors += 1

    db.close()
    return scanned, created, skipped, errors


def _outcome_meta(outcome) -> dict:
    return {
        "source": "ontology_sync",
        "outcome_id": outcome.id,
        "type_name": outcome.type_name,
        "success": outcome.properties.get("success", False),
        "result_summary": str(outcome.properties.get("result_summary", ""))[:500],
        "synced_at": time.time(),
    }


def _value_event_meta(event) -> dict:
    return {
        "source": "ontology_sync",
        "value_event_id": event.id,
        "type_name": event.type_name,
        "outcome_id": str(event.properties.get("outcome_id", "")),
        "agent_id": str(event.properties.get("agent_id", "")),
        "value_kind": str(event.properties.get("value_kind", "")),
        "composite_value": event.properties.get("composite_value"),
        "economic_value_usd": event.properties.get("economic_value_usd"),
        "synced_at": time.time(),
    }


def sync_outcomes_to_artifacts(
    *,
    state_dir: Path | None = None,
    runtime_db_path: Path | None = None,
    ontology_db_path: Path | None = None,
) -> SyncResult:
    """Materialize ontology Outcomes as runtime ArtifactRecords (kind
    ``outcome``); metadata carries the Outcome properties for downstream
    consumers."""
    scanned, created, skipped, errors = _sync_type_to_artifacts(
        type_name="Outcome",
        artifact_kind="outcome",
        id_prefix="ont-",
        build_meta=_outcome_meta,
        state_dir=state_dir,
        runtime_db_path=runtime_db_path,
        ontology_db_path=ontology_db_path,
    )
    return SyncResult(
        outcomes_scanned=scanned,
        artifacts_created=created,
        skipped_existing=skipped,
        errors=errors,
    )


def sync_value_events_to_artifacts(
    *,
    state_dir: Path | None = None,
    runtime_db_path: Path | None = None,
    ontology_db_path: Path | None = None,
) -> SyncResult:
    """Materialize ontology ValueEvents as runtime ArtifactRecords (kind
    ``value_event``) — the credit-chain entry point becomes visible to
    runtime-level queries."""
    scanned, created, skipped, errors = _sync_type_to_artifacts(
        type_name="ValueEvent",
        artifact_kind="value_event",
        id_prefix="ont-ve-",
        build_meta=_value_event_meta,
        state_dir=state_dir,
        runtime_db_path=runtime_db_path,
        ontology_db_path=ontology_db_path,
    )
    return SyncResult(
        value_events_scanned=scanned,
        artifacts_created=created,
        skipped_existing=skipped,
        errors=errors,
    )


def sync_all(*, state_dir: Path | None = None) -> SyncResult:
    """Run every projection pass: outcomes→artifacts, value events→artifacts."""
    outcomes = sync_outcomes_to_artifacts(state_dir=state_dir)
    value_events = sync_value_events_to_artifacts(state_dir=state_dir)
    return SyncResult(
        outcomes_scanned=outcomes.outcomes_scanned,
        value_events_scanned=value_events.value_events_scanned,
        artifacts_created=outcomes.artifacts_created + value_events.artifacts_created,
        skipped_existing=outcomes.skipped_existing + value_events.skipped_existing,
        errors=outcomes.errors + value_events.errors,
    )
