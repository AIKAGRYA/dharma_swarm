"""Regression proof for store-sync atomic insert accounting."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from dharma_swarm.engine.store_sync import sync_value_events_to_artifacts
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.ontology_hub import OntologyHub
from dharma_swarm.runtime_state import ensure_runtime_state_schema_sync


def test_insert_ignore_race_is_reported_as_skipped(tmp_path: Path) -> None:
    """A competing insert between discovery and write is not reported created.

    The BEFORE INSERT trigger deterministically models another worker winning
    the unique artifact-id race immediately before this worker's INSERT OR
    IGNORE is applied. The outer statement must report ``rowcount == 0`` and
    the public SyncResult must classify that disposition as skipped_existing.
    """

    ontology_path = tmp_path / "ontology.db"
    registry = OntologyRegistry.create_dharma_registry()
    value_event, errors = registry.create_object(
        "ValueEvent",
        properties={
            "outcome_id": "out-race",
            "agent_id": "agent-race",
            "task_id": "task-race",
            "composite_value": 0.5,
            "value_kind": "task",
        },
        created_by="test",
    )
    assert not errors and value_event is not None

    hub = OntologyHub(db_path=ontology_path)
    hub.sync_from_registry(registry)
    hub.close()

    runtime_path = tmp_path / "state" / "runtime.db"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(runtime_path))
    ensure_runtime_state_schema_sync(db)
    db.execute("PRAGMA recursive_triggers = OFF")
    target_id = f"ont-ve-{value_event.id}"
    db.executescript(
        f"""
        CREATE TRIGGER inject_competing_artifact
        BEFORE INSERT ON artifact_records
        WHEN NEW.artifact_id = '{target_id}'
        BEGIN
            INSERT OR IGNORE INTO artifact_records
            (artifact_id, session_id, task_id, run_id, artifact_kind,
             manifest_path, payload_path, checksum, parent_artifact_id,
             promotion_state, created_at, metadata_json)
            VALUES
            (NEW.artifact_id, NEW.session_id, NEW.task_id, NEW.run_id,
             NEW.artifact_kind, NEW.manifest_path, NEW.payload_path,
             NEW.checksum, NEW.parent_artifact_id, NEW.promotion_state,
             NEW.created_at, NEW.metadata_json);
        END;
        """
    )
    db.commit()
    db.close()

    result = sync_value_events_to_artifacts(
        ontology_db_path=ontology_path,
        runtime_db_path=runtime_path,
    )

    assert result.value_events_scanned == 1
    assert result.artifacts_created == 0
    assert result.skipped_existing == 1
    assert result.errors == 0

    db = sqlite3.connect(str(runtime_path))
    count = db.execute(
        "SELECT COUNT(*) FROM artifact_records WHERE artifact_id = ?",
        (target_id,),
    ).fetchone()[0]
    db.close()
    assert count == 1
